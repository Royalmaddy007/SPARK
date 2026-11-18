#!/usr/bin/env python3
"""Phase 0 -- ASAP7 Technology Mapping & Netlist Knowledge Graph.

For every design this phase:

  1. synthesises the RTL to the open-source ASAP7 7.5-track standard cells with
     Yosys (`dfflibmap` + `abc`), producing a gate-level netlist;
  2. builds a directed driver->load *knowledge graph* of that netlist (cells,
     primary ports, connectivity), with per-cell gate-family / area / sequential
     metadata;
  3. computes, for every RTL-visible signal, its true gate-level footprint --
     logic-cone size and depth, gate mix, fan-out, whether it feeds a primary
     output, and register-loop membership;
  4. renders the graph as a self-contained interactive d3.js webpage; and
  5. writes `<design>.netlist.json`, the structural evidence that Phases 1 and 2
     consume so the LLM's sensitivity and redaction decisions are *netlist
     aware* -- grounded in the synthesised structure, not just the source text.

Output: pipeline/phase0_netlist/<design>.{mapped.v,mapped.json,graph.json,
        kg.html,netlist.json,changelog.json}
"""
from __future__ import annotations
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, vlog, util
from great import netlist as N
from great.changelog import ChangeLog


def graph_to_json(g, node_cap: int = 12000) -> dict:
    """Serialise the knowledge graph (portable, for programmatic use).

    Bounded for very large designs: a 99k-cell netlist would otherwise emit an
    ~90 MB JSON that no tool loads comfortably.  Above `node_cap` we keep every
    primary port and sequential cell plus the highest-degree combinational cells,
    and always report the true totals and a gate-family adjacency summary so the
    export stays representative and useful.
    """
    import networkx as nx
    full_nodes, full_edges = g.number_of_nodes(), g.number_of_edges()
    keep = set(g.nodes)
    truncated = full_nodes > node_cap
    if truncated:
        deg = dict(g.degree())
        seq = g.graph.get("seq_cells", set())
        keep = {n for n in g.nodes if g.nodes[n].get("kind") in ("input", "output")}
        keep |= set(seq)
        for n, _ in sorted(deg.items(), key=lambda x: -x[1]):
            if len(keep) >= node_cap:
                break
            keep.add(n)
    nodes = [{"id": n, **{k: (list(v) if isinstance(v, set) else v)
                          for k, v in g.nodes[n].items()}} for n in keep]
    edges = [{"src": u, "dst": v, "net": d.get("net"), "netname": d.get("netname")}
             for u, v, d in g.edges(data=True) if u in keep and v in keep]
    # gate-family adjacency (family -> family -> edge count): a compact,
    # size-independent summary of how the netlist's logic families interconnect.
    fam_adj: dict[str, dict[str, int]] = {}
    for u, v, d in g.edges(data=True):
        fu = g.nodes[u].get("family", "port"); fv = g.nodes[v].get("family", "port")
        fam_adj.setdefault(fu, {}); fam_adj[fu][fv] = fam_adj[fu].get(fv, 0) + 1
    return {"top": g.graph.get("name"),
            "n_nodes": full_nodes, "n_edges": full_edges,
            "exported_nodes": len(nodes), "truncated": truncated,
            "family_adjacency": fam_adj,
            "nodes": nodes, "edges": edges,
            "ports": g.graph.get("ports", {})}


def process(path: Path) -> dict:
    design = path.stem
    src = path.read_text()
    mods = vlog.parse_modules(src)
    top = mods[0].name
    cl = ChangeLog("phase0_netlist", design, str(path.relative_to(C.ROOT)))
    d = C.phase_dir(0)

    if not N.ASAP7_LIB.exists():
        cl.fault("0", "asap7_missing",
                 f"ASAP7 Liberty not found at {N.ASAP7_LIB.relative_to(C.ROOT)}",
                 "run `make asap7` (scripts/setup_asap7.py) to fetch it", resolved=False)
        cl.write(d / f"{design}.changelog.json")
        return {"design": design, "ok": False, "reason": "no asap7 lib"}

    deps = C.dep_files(design)
    cl.note(top_module=top, asap7_lib=str(N.ASAP7_LIB.relative_to(C.ROOT)),
            dep_files=[Path(x).name for x in deps])

    res = N.map_to_asap7(path, top, d, deps=deps, timeout=600)
    if not res["ok"]:
        cl.fault("0", "technology_mapping_failed",
                 f"Yosys could not map {design} to ASAP7: {res.get('reason')}",
                 "the design is skipped for netlist-aware features; later phases "
                 "fall back to source-only analysis (this happens for RTL that does "
                 "not elaborate standalone)", resolved=False,
                 log_tail=res.get("log_tail", "")[-800:])
        cl.summarise(mapped=False, reason=res.get("reason"))
        cl.write(d / f"{design}.changelog.json")
        util.write_json(d / f"{design}.netlist.json",
                        {"design": design, "mapped": False,
                         "reason": res.get("reason"), "log_tail": res.get("log_tail", "")})
        return {"design": design, "ok": False, "reason": res.get("reason")}

    cl.change("0", "technology_mapping", target=design, origin="script",
              after=f"{res['n_std_cells']} ASAP7 std cells, area {res['chip_area_um2']} um^2",
              rationale="RTL synthesised to the open-source ASAP7 7.5-track cells via "
                        "Yosys dfflibmap + abc; the gate-level netlist is the basis for "
                        "the netlist knowledge graph")

    g = N.build_graph(res["mapped_json"])
    feats = N.structural_features(g)
    # compress the raw yosys JSON (kept for provenance; not read by later phases)
    import gzip, shutil as _sh
    mj = Path(res["mapped_json"])
    if mj.exists() and mj.stat().st_size > 1_000_000:
        with mj.open("rb") as fi, gzip.open(str(mj) + ".gz", "wb") as fo:
            _sh.copyfileobj(fi, fo)
        mj.unlink()
        res["mapped_json_gz"] = mj.name + ".gz"
    meta = {"design": design, "top_module": top,
            "n_std_cells": res["n_std_cells"], "chip_area_um2": res["chip_area_um2"],
            "cell_histogram": res["cell_histogram"], "summary": feats["summary"]}

    cl.change("0", "knowledge_graph_built", target=design, origin="script",
              after=f"{g.number_of_nodes()} nodes, {g.number_of_edges()} edges, "
                    f"{feats['summary']['n_sequential_cells']} flops, "
                    f"{feats['summary']['n_register_loops']} register loops",
              rationale="directed driver->load graph over ASAP7 cells + primary ports; "
                        "register loops mark FSM/accumulator state, high-fanout nets "
                        "mark control/enables")

    graph_json = graph_to_json(g)
    util.write_json(d / f"{design}.graph.json", graph_json)
    cl.artifact("graph", d / f"{design}.graph.json")

    html = N.to_d3_html(g, meta, d / f"{design}.kg.html")
    cl.change("0", "d3_visualisation", target=str(html.name), origin="script",
              after=f"interactive d3.js force graph ({html.stat().st_size} bytes)",
              rationale="self-contained webpage; nodes coloured by gate family, sized "
                        "by degree; the full graph is in graph.json")
    cl.artifact("kg_html", html)

    # the structural evidence Phases 1/2 consume
    netlist_out = {
        "design": design, "mapped": True, "top_module": top,
        "n_std_cells": res["n_std_cells"], "chip_area_um2": res["chip_area_um2"],
        "cell_histogram": res["cell_histogram"],
        "summary": feats["summary"],
        "per_signal": feats["per_signal"],
        "artifacts": {"mapped_v": Path(res["mapped_v"]).name,
                      "mapped_json": Path(res["mapped_json"]).name,
                      "graph_json": f"{design}.graph.json",
                      "kg_html": f"{design}.kg.html"},
    }
    util.write_json(d / f"{design}.netlist.json", netlist_out)
    cl.artifact("netlist_features", d / f"{design}.netlist.json")

    cl.summarise(mapped=True, n_std_cells=res["n_std_cells"],
                 chip_area_um2=res["chip_area_um2"],
                 n_sequential=feats["summary"]["n_sequential_cells"],
                 n_register_loops=feats["summary"]["n_register_loops"],
                 graph_nodes=g.number_of_nodes(), graph_edges=g.number_of_edges())
    cl.write(d / f"{design}.changelog.json")
    return {"design": design, "ok": True, **meta}


def main() -> int:
    args = util.design_args(__doc__).parse_args()
    util.banner("PHASE 0 -- ASAP7 Technology Mapping & Netlist Knowledge Graph")
    if not N.ASAP7_LIB.exists():
        util.warn(f"ASAP7 Liberty missing ({N.ASAP7_LIB.relative_to(C.ROOT)}); "
                  "run `make asap7` first. Continuing (designs will be marked "
                  "unmapped and later phases fall back to source-only).")
    index = []
    for p in util.resolve_designs(args):
        util.info(f"mapping + graphing {p.name}")
        r = process(p)
        if r["ok"]:
            util.info(f"    {r['n_std_cells']} cells, area {r['chip_area_um2']} um^2, "
                      f"{r['summary']['n_sequential_cells']} flops, "
                      f"{r['summary']['n_register_loops']} reg-loops  -> "
                      f"{r['design']}.kg.html")
        else:
            util.warn(f"    not mapped: {r.get('reason')}")
        index.append({"design": r["design"], "mapped": r["ok"],
                      "n_std_cells": r.get("n_std_cells"),
                      "area": r.get("chip_area_um2")})
    util.write_json(C.phase_dir(0) / "index.json", {"phase": 0, "designs": index})
    n_ok = sum(1 for d in index if d["mapped"])
    util.info(f"{n_ok}/{len(index)} designs mapped to ASAP7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
