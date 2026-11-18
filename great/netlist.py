"""ASAP7 technology mapping + netlist knowledge graph.

This module adds a *netlist-aware* front-end to the redaction pipeline:

  1. `map_to_asap7`   -- synthesise a Verilog design to the open-source ASAP7
                         7.5-track standard cells with Yosys, producing a
                         gate-level netlist (.v + .json).
  2. `build_graph`    -- turn the mapped netlist into a directed driver->load
                         knowledge graph (networkx), with per-cell metadata.
  3. `structural_features` -- for every RTL-visible signal, measure its actual
                         gate-level footprint (logic-cone size, depth, gate
                         mix, fan-out, register-loop membership).  This is the
                         evidence later phases feed to the LLM so that
                         sensitivity/redaction decisions are grounded in the
                         real synthesised structure, not just the source text.
  4. `to_d3_html`     -- render the graph as a self-contained interactive
                         d3.js force-directed webpage.

Everything here is deterministic and local: Yosys + the ASAP7 Liberty. ASAP7 is
an open predictive PDK (BSD-3-Clause), not a foundry NDA PDK.
"""
from __future__ import annotations
import json, re, subprocess, tempfile
from pathlib import Path

from . import config as C
from . import vlog

PDK_DIR = C.ROOT / "pdk" / "asap7"
ASAP7_LIB = PDK_DIR / "asap7sc7p5t_RVT_TT.lib"


# ----------------------------------------------------------------- liberty
_LIB_PINCACHE: dict | None = None


def liberty_pins(lib: Path = ASAP7_LIB) -> dict:
    """{cell_type -> {"pins": {name: 'input'|'output'}, "seq": bool, "area": float}}.

    Yosys' JSON does not carry pin directions for abc-mapped cells, so they are
    recovered once from the Liberty and cached.
    """
    global _LIB_PINCACHE
    if _LIB_PINCACHE is not None:
        return _LIB_PINCACHE
    txt = lib.read_text(errors="ignore")
    out: dict = {}
    for m in re.finditer(r'\bcell\s*\(\s*"?([A-Za-z0-9_]+)"?\s*\)\s*\{', txt):
        name = m.group(1)
        # brace-balanced cell body
        i = txt.index("{", m.start()); depth = 0; j = i
        while j < len(txt):
            ch = txt[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        body = txt[i:j + 1]
        pins: dict[str, str] = {}
        for pm in re.finditer(r'\bpin\s*\(\s*"?([A-Za-z0-9_]+)"?\s*\)\s*\{', body):
            pend = body.find("}", pm.end())
            seg = body[pm.end():body.find("pin", pm.end()) if "pin" in body[pm.end():] else len(body)]
            dirm = re.search(r'\bdirection\s*:\s*(\w+)', body[pm.end():pm.end() + 400])
            pins[pm.group(1)] = dirm.group(1) if dirm else "input"
        seq = bool(re.search(r'\b(ff|latch)\s*\(', body))
        am = re.search(r'\barea\s*:\s*([0-9.]+)', body)
        out[name] = {"pins": pins, "seq": seq, "area": float(am.group(1)) if am else 0.0}
    _LIB_PINCACHE = out
    return out


def load_mapped_json(path):
    """Read Phase-0 raw JSON, including its existing gzip cache format."""
    import gzip
    path = Path(path)
    if path.exists() and path.suffix != '.gz':
        return json.loads(path.read_text())
    compressed = path if path.suffix == '.gz' else Path(str(path) + '.gz')
    with gzip.open(compressed, 'rt') as stream:
        return json.load(stream)


def cell_area(mapped_json, strict=False):
    modules = load_mapped_json(mapped_json)['modules']
    mod = next((m for m in modules.values() if m.get('attributes', {}).get('top', '').endswith('1')),
               next(iter(modules.values())))
    cells = liberty_pins()
    unknown = {c['type'] for c in mod['cells'].values()} - cells.keys() - {'$scopeinfo'}
    if strict and unknown:
        raise ValueError(f'unmapped/unknown cells: {sorted(unknown)}')
    return sum(cells.get(c['type'], {}).get('area', 0.0) for c in mod['cells'].values())


def gate_family(cell_type: str) -> str:
    """Coarse functional family of an ASAP7 cell, for colouring / summaries."""
    t = cell_type.replace("_ASAP7_75t_R", "").replace("_ASAP7_75t_L", "")
    t = re.sub(r"(x\w+)$", "", t)          # drop drive strength suffix
    tu = t.upper()
    if tu.startswith(("DFF", "SDF", "DHL", "SDHL", "ASYNC")):
        return "flop"
    if tu.startswith(("ICG", "CKGATE", "CLKGATE")):
        return "clock-gate"
    if tu.startswith("INV") or tu.startswith("BUF") or tu.startswith("HB"):
        return "buffer/inverter"
    if tu.startswith("XNOR"):
        return "xnor"
    if tu.startswith("XOR"):
        return "xor"
    if tu.startswith("MAJ"):
        return "majority"
    if tu.startswith("FA") or tu.startswith("HA"):
        return "adder"
    if tu.startswith("NAND"):
        return "nand"
    if tu.startswith("NOR"):
        return "nor"
    if tu.startswith("AND"):
        return "and"
    if tu.startswith("OR"):
        return "or"
    if tu.startswith(("AOI", "OAI")):
        return "aoi/oai"
    if tu.startswith(("AO", "OA")):
        return "and-or/or-and"
    if tu.startswith("MUX") or "MUX" in tu:
        return "mux"
    if tu in ("TIEHIx1", "TIELOx1") or tu.startswith("TIE"):
        return "tie"
    return "other"


# ----------------------------------------------------------------- mapping
_YS = """
read_verilog {rtl}
{deps}
hierarchy -check -top {top}
delete t:$print
# `synth` runs proc + memory (ROM/RAM -> logic) + fsm + generic techmap; without
# its memory pass a constant ROM (e.g. an S-box / round-constant table) is left
# as a $mem primitive that ABC cannot map, yielding an empty gate netlist.
synth {flatten} -top {top}
dfflibmap -liberty {lib}
abc -liberty {lib}
setattr -mod -unset keep
opt_clean
stat -liberty {lib}
write_json {out_json}
write_verilog -noattr {out_v}
"""


def map_to_asap7(rtl_path: Path, top: str, out_dir: Path,
                 deps: list[str] | None = None, flatten: bool = True,
                 timeout: int = 600) -> dict:
    """Synthesise `rtl_path` to ASAP7. Returns a result dict (never raises)."""
    if not C.YOSYS:
        return {"ok": False, "reason": "Yosys unavailable"}
    if not ASAP7_LIB.is_file():
        return {"ok": False, "reason": "ASAP7 Liberty unavailable"}
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / f"{rtl_path.stem}.mapped.json"
    out_v = out_dir / f"{rtl_path.stem}.mapped.v"
    dep_lines = "\n".join(f"read_verilog {d}" for d in (deps or []))
    script = _YS.format(rtl=rtl_path, deps=dep_lines, top=top, lib=ASAP7_LIB,
                        flatten="-flatten" if flatten else "",
                        out_json=out_json, out_v=out_v)
    with tempfile.TemporaryDirectory() as td:
        ys = Path(td) / "map.ys"
        ys.write_text(script)
        try:
            r = subprocess.run([C.YOSYS, "-q", "-s", str(ys)],
                               capture_output=True, text=True, timeout=timeout)
        except OSError as exc:
            return {"ok": False, "reason": str(exc)}
        except subprocess.TimeoutExpired:
            return {"ok": False, "reason": f"yosys timed out after {timeout}s"}
    log = (r.stdout + r.stderr)
    if r.returncode != 0 or not out_json.exists():
        return {"ok": False, "reason": "yosys failed",
                "log_tail": log[-2500:]}
    # Derive cell counts and area from the mapped JSON + Liberty (reliable),
    # not from fragile stat-log scraping.
    pindir = liberty_pins()
    dj = json.loads(out_json.read_text())
    mod = dj["modules"][next(iter(dj["modules"]))]
    hist: dict[str, int] = {}
    area = 0.0
    for c in mod["cells"].values():
        t = c["type"]; hist[t] = hist.get(t, 0) + 1
        area += pindir.get(t, {}).get("area", 0.0)
    return {"ok": True, "mapped_json": str(out_json), "mapped_v": str(out_v),
            "chip_area_um2": round(cell_area(out_json), 3), "cell_histogram": hist,
            "n_std_cells": sum(n for t, n in hist.items() if t in pindir), "log_tail": log[-1500:]}


# -------------------------------------------------------------- graph build
def _iter_bits(bits):
    for b in bits:
        if isinstance(b, int):
            yield b            # a real net id; strings "0"/"1"/"x"/"z" are consts


def build_graph(mapped_json: str, pindir: dict | None = None):
    """Directed driver->load knowledge graph over ASAP7 cells + primary ports.

    Node kinds: 'input' / 'output' (primary ports) and 'cell' (std cells).
    Each edge carries the net id it travels on.  Sequential cells break
    combinational cones (their inputs are cut points), so a purely combinational
    fan-in walk terminates at flop outputs and primary inputs.
    """
    import networkx as nx
    pindir = pindir or liberty_pins()
    d = load_mapped_json(mapped_json)
    top = next(iter(d["modules"]))
    m = d["modules"][top]

    g = nx.MultiDiGraph(name=top)
    # net -> driver node, and net -> [load nodes]
    drivers: dict[int, str] = {}
    loads: dict[int, list[str]] = {}
    seq_cells: set[str] = set()

    # primary ports are nodes; an input drives its bits, an output loads them
    port_bit: dict[int, str] = {}
    for pname, p in m["ports"].items():
        kind = "input" if p["direction"] == "input" else "output"
        nid = f"port:{pname}"
        g.add_node(nid, kind=kind, label=pname, family="port", width=len(p["bits"]))
        for b in _iter_bits(p["bits"]):
            if kind == "input":
                drivers.setdefault(b, nid)
            else:
                loads.setdefault(b, []).append(nid)
            port_bit.setdefault(b, nid)

    for cname, c in m["cells"].items():
        ctype = c["type"]
        info = pindir.get(ctype, {"pins": {}, "seq": False, "area": 0.0})
        fam = gate_family(ctype)
        seq = info["seq"] or fam in ("flop", "clock-gate")
        nid = f"cell:{cname}"
        g.add_node(nid, kind="cell", label=ctype, celltype=ctype, family=fam,
                   area=info["area"], seq=bool(seq))
        if seq:
            seq_cells.add(nid)
        for pin, bits in c["connections"].items():
            direction = info["pins"].get(pin)
            if direction is None:
                # unknown pin: guess by common ASAP7 output pin names
                direction = "output" if pin in ("Y", "Q", "QN", "SO", "CON", "S", "CO") else "input"
            for b in _iter_bits(bits):
                if direction == "output":
                    drivers[b] = nid
                else:
                    loads.setdefault(b, []).append(nid)

    # net names: prefer the RTL-visible (public) name for each bit
    bit_name: dict[int, str] = {}
    for nn, v in m["netnames"].items():
        if v.get("hide_name") == 1:
            continue
        for idx, b in enumerate(_iter_bits(v["bits"])):
            bit_name.setdefault(b, nn if len(v["bits"]) == 1 else f"{nn}[{idx}]")

    for b, dr in drivers.items():
        for ld in loads.get(b, []):
            if dr != ld:
                g.add_edge(dr, ld, net=b, netname=bit_name.get(b, f"$n{b}"))

    g.graph["seq_cells"] = seq_cells
    g.graph["bit_name"] = bit_name
    g.graph["public_nets"] = {
        nn: [x for x in _iter_bits(v["bits"])]
        for nn, v in m["netnames"].items() if v.get("hide_name") == 0
    }
    g.graph["ports"] = {p: m["ports"][p]["direction"] for p in m["ports"]}
    return g


# ------------------------------------------------------ structural features
def structural_features(g, max_signals: int = 400) -> dict:
    """Per-public-signal gate-level footprint + a design-level summary.

    For each RTL-visible net we compute the *combinational* fan-in cone (walking
    backwards, stopping at flops and primary inputs): its cell count, logic
    depth, gate-family mix, plus fan-out and whether it feeds a primary output
    or sits inside a register loop.  These are exactly the structural cues that
    tell the LLM which signals anchor real, deep, security-relevant logic.
    """
    import networkx as nx
    seq = g.graph["seq_cells"]
    bit_name = g.graph["bit_name"]

    # bit -> the graph node that drives it (cell or input port)
    driver_of: dict[int, str] = {}
    for u, v, data in g.edges(data=True):
        driver_of[data["net"]] = u

    # combinational predecessors of a node: skip through nets, stop at seq/inputs
    def comb_fanin(seed_node):
        seen, depth = set(), {}
        stack = [(seed_node, 0)]
        while stack:
            n, dpth = stack.pop()
            if n in seen:
                depth[n] = max(depth.get(n, 0), dpth)
                continue
            seen.add(n); depth[n] = dpth
            if n in seq or (g.nodes[n].get("kind") == "input"):
                continue                     # cut point
            for p in g.predecessors(n):
                stack.append((p, dpth + 1))
        return seen, (max(depth.values()) if depth else 0)

    feats: dict[str, dict] = {}
    # rank public signals by width*driver so we profile the meaningful ones first
    pub = g.graph["public_nets"]
    ordered = sorted(pub.items(), key=lambda kv: -len(kv[1]))
    for name, bits in ordered[:max_signals]:
        cone_nodes: set[str] = set()
        max_depth = 0
        fanout = 0
        drives_out = False
        for b in bits:
            dn = driver_of.get(b)
            if dn is None:
                continue
            nodes, dpth = comb_fanin(dn)
            cone_nodes |= nodes
            max_depth = max(max_depth, dpth)
            # loads of this bit
            for succ in g.successors(dn):
                pass
        # fan-out = number of distinct loads over the signal's bits
        loadset = set()
        for u, v, data in g.edges(data=True):
            if data["net"] in bits:
                loadset.add(v)
                if g.nodes[v].get("kind") == "output":
                    drives_out = True
        cone_cells = [n for n in cone_nodes if g.nodes[n].get("kind") == "cell"]
        famhist: dict[str, int] = {}
        for n in cone_cells:
            f = g.nodes[n].get("family", "other")
            famhist[f] = famhist.get(f, 0) + 1
        feats[name] = {
            "width": len(bits),
            "cone_cells": len(cone_cells),
            "cone_depth": max_depth,
            "fanout": len(loadset),
            "drives_primary_output": drives_out,
            "gate_families": dict(sorted(famhist.items(), key=lambda x: -x[1])),
        }

    # register loops = SCCs of size>1 among cells (FSM / accumulator state)
    reg_loops = []
    try:
        comp = list(nx.strongly_connected_components(nx.DiGraph(g)))
        reg_loops = [len(c) for c in comp if len(c) > 1]
    except Exception:                                       # noqa: BLE001
        pass

    cells = [n for n in g.nodes if g.nodes[n].get("kind") == "cell"]
    fam_summary: dict[str, int] = {}
    for n in cells:
        f = g.nodes[n]["family"]; fam_summary[f] = fam_summary.get(f, 0) + 1
    # high-fanout nets (candidate control/enable/clock-ish signals)
    fo: dict[str, int] = {}
    for u, v, data in g.edges(data=True):
        nm = data["netname"]; fo[nm] = fo.get(nm, 0) + 1
    def is_clockreset(nm):
        b = re.sub(r"\[.*", "", nm).lower()
        return bool(re.fullmatch(r"clk|clock|clk_i|rst|reset|rst_n|reset_n|resetn|"
                                 r"aresetn|rst_ni|scan_clk", b))
    high_fanout = sorted(((k, v) for k, v in fo.items() if not k.startswith("$")),
                         key=lambda x: -x[1])[:12]
    high_fanout_control = sorted(
        ((k, v) for k, v in fo.items() if not k.startswith("$") and not is_clockreset(k)),
        key=lambda x: -x[1])[:12]

    summary = {
        "n_cells": len(cells),
        "n_sequential_cells": len(seq),
        "n_register_loops": len(reg_loops),
        "largest_register_loop": max(reg_loops) if reg_loops else 0,
        "gate_family_histogram": dict(sorted(fam_summary.items(), key=lambda x: -x[1])),
        "high_fanout_signals": [{"signal": k, "fanout": v} for k, v in high_fanout],
        "high_fanout_control": [{"signal": k, "fanout": v} for k, v in high_fanout_control],
        "deepest_signals": sorted(
            ({"signal": k, "cone_depth": v["cone_depth"], "cone_cells": v["cone_cells"]}
             for k, v in feats.items()),
            key=lambda x: -x["cone_depth"])[:12],
    }
    return {"per_signal": feats, "summary": summary}


# ----------------------------------------------------------------- d3 html
def to_d3_html(g, meta: dict, out_html: Path, node_cap: int = 700) -> Path:
    """Self-contained interactive d3.js force-directed view of the netlist graph.

    For large designs the view is capped to the `node_cap` highest-degree nodes
    (plus all primary ports) so the force layout stays legible; the full graph
    always lives in the companion graph.json.
    """
    import networkx as nx
    simple = nx.DiGraph()
    for u, v, data in g.edges(data=True):
        if simple.has_edge(u, v):
            simple[u][v]["w"] += 1
        else:
            simple.add_edge(u, v, w=1)
    for n in g.nodes:
        if n not in simple:
            simple.add_node(n)

    deg = dict(simple.degree())
    ports = [n for n in simple if g.nodes[n].get("kind") in ("input", "output")]
    keep = set(ports)
    for n, _ in sorted(deg.items(), key=lambda x: -x[1]):
        if len(keep) >= node_cap:
            break
        keep.add(n)
    truncated = len(keep) < simple.number_of_nodes()

    idx = {n: i for i, n in enumerate(keep)}
    nodes = []
    for n in keep:
        a = g.nodes[n]
        nodes.append({"id": idx[n], "name": a.get("label", n),
                      "kind": a.get("kind", "cell"), "family": a.get("family", "other"),
                      "deg": deg.get(n, 1), "seq": bool(a.get("seq", False))})
    links = [{"source": idx[u], "target": idx[v], "w": data["w"]}
             for u, v, data in simple.edges(data=True) if u in keep and v in keep]

    payload = {"nodes": nodes, "links": links, "meta": meta,
               "truncated": truncated, "shown": len(keep),
               "total_nodes": simple.number_of_nodes()}
    data_js = json.dumps(payload)

    html = _D3_TEMPLATE.replace("__DATA__", data_js)
    out_html.write_text(html)
    return out_html


_D3_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Netlist Knowledge Graph</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  :root { color-scheme: light dark; }
  body { margin:0; font:13px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
         background:#0f1115; color:#e6e6e6; }
  #hdr { padding:10px 16px; border-bottom:1px solid #2a2f3a; background:#151922; }
  #hdr h1 { margin:0 0 4px; font-size:15px; font-weight:600; }
  #hdr .sub { color:#9aa4b2; font-size:12px; }
  #wrap { display:flex; height:calc(100vh - 58px); }
  #graph { flex:1; }
  #side { width:300px; border-left:1px solid #2a2f3a; padding:12px 14px; overflow:auto;
          background:#131722; }
  #side h2 { font-size:12px; text-transform:uppercase; letter-spacing:.06em;
             color:#8891a0; margin:14px 0 6px; }
  .kv { display:flex; justify-content:space-between; padding:2px 0; border-bottom:1px dotted #232937; }
  .kv b { color:#cfd6e2; font-weight:600; }
  .legend span { display:inline-flex; align-items:center; margin:2px 8px 2px 0; }
  .legend i { width:10px; height:10px; border-radius:2px; margin-right:5px; display:inline-block; }
  .node { stroke:#0f1115; stroke-width:.6px; cursor:pointer; }
  .link { stroke:#3a4256; stroke-opacity:.5; }
  .node.sel { stroke:#fff; stroke-width:2px; }
  #tip { position:fixed; pointer-events:none; background:#000c; color:#fff; padding:5px 8px;
         border-radius:4px; font-size:12px; display:none; max-width:280px; }
  .muted { color:#8891a0; }
</style></head>
<body>
<div id="hdr"><h1 id="title">Netlist Knowledge Graph</h1>
  <div class="sub" id="subtitle"></div></div>
<div id="wrap">
  <svg id="graph"></svg>
  <div id="side">
    <div class="legend" id="legend"></div>
    <h2>Design summary</h2><div id="summary"></div>
    <h2>Selected node</h2><div id="sel" class="muted">click a node…</div>
  </div>
</div>
<div id="tip"></div>
<script>
const DATA = __DATA__;
const COLORS = {
  "port":"#e8c547","input":"#e8c547","output":"#e8975c",
  "flop":"#e0508a","clock-gate":"#b06ad6",
  "buffer/inverter":"#6c7a8c","nand":"#4c9be8","nor":"#5aa9d6","and":"#57a773",
  "or":"#6bbf59","xor":"#d98a2b","xnor":"#c77b25","aoi/oai":"#8a7de0",
  "and-or/or-and":"#7d8ae0","majority":"#d05a5a","adder":"#e05252","mux":"#39b3a6",
  "tie":"#556","other":"#8891a0"
};
const color = d => COLORS[d.family] || COLORS[d.kind] || "#8891a0";
document.getElementById("title").textContent = "Netlist Knowledge Graph — " + (DATA.meta.design||"");
document.getElementById("subtitle").innerHTML =
  `${DATA.meta.top_module||""} · mapped to ASAP7 (${DATA.meta.n_std_cells||0} std cells, `+
  `area ${DATA.meta.chip_area_um2||"?"} µm²) · showing ${DATA.shown}/${DATA.total_nodes} nodes`+
  (DATA.truncated? ` <span class="muted">(top-degree subset; full graph in graph.json)</span>`:``);

// legend
const fams=[...new Set(DATA.nodes.map(n=>n.family))];
document.getElementById("legend").innerHTML =
  fams.map(f=>`<span><i style="background:${COLORS[f]||'#888'}"></i>${f}</span>`).join("");

// summary panel
const S = DATA.meta.summary||{};
const sdiv=document.getElementById("summary");
function kv(k,v){return `<div class="kv"><span class="muted">${k}</span><b>${v}</b></div>`;}
sdiv.innerHTML =
  kv("std cells", S.n_cells??"?")+kv("sequential", S.n_sequential_cells??"?")+
  kv("register loops", S.n_register_loops??0)+kv("largest loop", S.largest_register_loop??0)+
  `<h2>gate families</h2>`+
  Object.entries(S.gate_family_histogram||{}).map(([k,v])=>kv(k,v)).join("")+
  `<h2>high fan-out signals</h2>`+
  (S.high_fanout_signals||[]).map(o=>kv(o.signal,o.fanout)).join("");

const svg=d3.select("#graph"), g=svg.append("g");
function size(){const r=svg.node().getBoundingClientRect();svg.attr("width",r.width).attr("height",r.height);return r;}
let R=size();
svg.call(d3.zoom().scaleExtent([0.1,6]).on("zoom",e=>g.attr("transform",e.transform)));

const link=g.append("g").selectAll("line").data(DATA.links).join("line")
  .attr("class","link").attr("stroke-width",d=>Math.min(3,0.5+Math.log2(1+d.w)));
const node=g.append("g").selectAll("circle").data(DATA.nodes).join("circle")
  .attr("class","node").attr("r",d=>d.kind==="input"||d.kind==="output"?7:Math.min(9,3+Math.sqrt(d.deg)))
  .attr("fill",color).call(drag()).on("click",select).on("mousemove",tip).on("mouseout",()=>d3.select("#tip").style("display","none"));

const sim=d3.forceSimulation(DATA.nodes)
  .force("link",d3.forceLink(DATA.links).id(d=>d.id).distance(28).strength(.4))
  .force("charge",d3.forceManyBody().strength(-38))
  .force("center",d3.forceCenter(R.width/2,R.height/2))
  .force("collide",d3.forceCollide(8))
  .on("tick",()=>{
    link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y).attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
    node.attr("cx",d=>d.x).attr("cy",d=>d.y);
  });
function drag(){return d3.drag()
  .on("start",(e,d)=>{if(!e.active)sim.alphaTarget(.3).restart();d.fx=d.x;d.fy=d.y;})
  .on("drag",(e,d)=>{d.fx=e.x;d.fy=e.y;})
  .on("end",(e,d)=>{if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null;});}
function tip(e,d){d3.select("#tip").style("display","block").style("left",(e.clientX+12)+"px")
  .style("top",(e.clientY+12)+"px").html(`<b>${d.name}</b><br>${d.kind} · ${d.family}<br>degree ${d.deg}`);}
function select(e,d){node.classed("sel",n=>n===d);
  document.getElementById("sel").innerHTML=
    kv("name",d.name)+kv("kind",d.kind)+kv("family",d.family)+kv("degree",d.deg)+kv("sequential",d.seq);}
window.addEventListener("resize",()=>{R=size();sim.force("center",d3.forceCenter(R.width/2,R.height/2)).alpha(.3).restart();});
</script></body></html>
"""


# ---------------------------------------------------- consumption by phases
def load_features(design: str) -> dict | None:
    """Load Phase-0 structural evidence for a design, or None if not mapped."""
    p = C.PHASE_DIRS[0] / f"{design}.netlist.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    return d if d.get("mapped") else None


def context_blurb(feats: dict) -> str:
    """A compact design-level netlist summary for an LLM profiling prompt."""
    if not feats:
        return "(netlist not available)"
    s = feats["summary"]
    fam = ", ".join(f"{k}:{v}" for k, v in list(s["gate_family_histogram"].items())[:6])
    hf = ", ".join(f"{o['signal']}(fanout {o['fanout']})"
                   for o in s.get("high_fanout_control", [])[:5])
    deep = ", ".join(f"{o['signal']}(depth {o['cone_depth']}/{o['cone_cells']} cells)"
                     for o in s.get("deepest_signals", [])[:5])
    return (f"ASAP7-mapped: {feats['n_std_cells']} std cells, area "
            f"{feats['chip_area_um2']} um^2, {s['n_sequential_cells']} flip-flops, "
            f"{s['n_register_loops']} register loop(s) (largest {s['largest_register_loop']} "
            f"cells -> FSM/datapath state). Gate mix: {fam}. "
            f"High-fanout control nets: {hf or 'none'}. "
            f"Deepest logic cones: {deep or 'none'}.")


def signal_hint(feats: dict, name: str) -> str:
    """One-line structural footprint for a specific RTL signal, or '' if none."""
    if not feats:
        return ""
    f = feats.get("per_signal", {}).get(name)
    if not f:
        base = re.sub(r"\[.*", "", name)
        f = feats.get("per_signal", {}).get(base)
    if not f or f.get("cone_cells", 0) == 0:
        return ""
    fam = max(f.get("gate_families", {"?": 0}).items(), key=lambda x: x[1])[0]
    out = " ->PO" if f.get("drives_primary_output") else ""
    return (f"cone {f['cone_cells']} cells / depth {f['cone_depth']}, "
            f"fanout {f['fanout']}, mostly {fam}{out}")


def structural_significance(feats: dict, name: str,
                            depth_thresh: int = 6, cone_thresh: int = 20) -> dict | None:
    """Is a signal structurally significant enough that a LOW tag is suspect?

    Returns a reason dict when the synthesised netlist shows the signal anchors
    substantial logic -- a deep/large combinational cone that reaches a primary
    output, or a wide fan-out -- which is exactly the kind of signal a source-only
    reader may under-rate but a silicon attacker can probe.
    """
    if not feats:
        return None
    base = re.sub(r"\[.*", "", name)
    # Clock, reset and scan nets have trivially huge fan-out and no logic cone --
    # they are the opposite of crown jewels and must never be promoted.
    if re.fullmatch(r"clk|clock|clk_i|rst|reset|rst_n|reset_n|resetn|aresetn|rst_ni|"
                    r"scan_clk|scan_en|scan_in|scan_out|test_mode|test_se|se|en",
                    base, re.I):
        return None
    f = feats.get("per_signal", {}).get(name) \
        or feats.get("per_signal", {}).get(base)
    if not f:
        return None
    reasons = []
    if f["cone_depth"] >= depth_thresh and f["cone_cells"] >= cone_thresh \
            and f["drives_primary_output"]:
        reasons.append(f"deep cone (depth {f['cone_depth']}, {f['cone_cells']} cells) "
                       f"reaching a primary output")
    # High fan-out is only meaningful for a *derived* control net (one with its own
    # logic cone), not a raw primary-input clock/enable which has an empty cone.
    if f["fanout"] >= 16 and f["cone_cells"] >= 4:
        reasons.append(f"high fan-out ({f['fanout']}) with logic cone -- likely "
                       f"control/enable")
    if not reasons:
        return None
    return {"cone_cells": f["cone_cells"], "cone_depth": f["cone_depth"],
            "fanout": f["fanout"], "drives_primary_output": f["drives_primary_output"],
            "reasons": reasons}
