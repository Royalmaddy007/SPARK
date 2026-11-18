"""Exhaustive, phase-travelling self-checking testbench (ModelSim).

The testbench is written ONCE per design and then *travels with the design as it
transforms*.  It is a dual-instance comparator: it instantiates the frozen
ORIGINAL design as the golden reference alongside the design AS IT STANDS AT THE
CURRENT PHASE, drives both with identical comprehensive/exhaustive stimulus, and
checks their outputs match on every vector.  This works for combinational and
sequential designs alike without hand-coding a per-design reference model or
protocol -- the golden instance *is* the reference.

Across phases only the current-DUT binding changes (module name + port map,
taken from the Phase-4 manifests); the stimulus and checking logic are fixed.
If a phase's binding makes the testbench fail to compile/elaborate, the local
LLM is asked to repair the testbench (bounded retries).  Everything runs on
ModelSim.
"""
from __future__ import annotations
import json, re
from pathlib import Path

from . import config as C, vlog, llm
from . import modelsim as MS

EXHAUSTIVE_MAX_BITS = 16          # enumerate the full input space up to this many bits
RANDOM_VECTORS = 3000
CLOCK_RE = re.compile(r"clk|clock|clk_i|clock_i", re.I)
RESET_RE = re.compile(r"rst|reset|rst_n|reset_n|resetn|aresetn|rst_ni", re.I)


# --------------------------------------------------------------- port helpers
def _width(p) -> int:
    if p["msb"] is None:
        return 1
    m, l = p["msb"].strip(), p["lsb"].strip()
    return int(m) - int(l) + 1 if m.isdigit() and l.isdigit() else 32


def _decl(p) -> str:
    return f"[{p['msb']}:{p['lsb']}]" if p["msb"] is not None else ""


def classify_ports(ports):
    ins = [p for p in ports if p["dir"] == "input"]
    outs = [p for p in ports if p["dir"] == "output"]
    clk = next((p["name"] for p in ins if CLOCK_RE.fullmatch(p["name"])), None)
    rst = None
    rst_al = False
    for p in ins:
        if RESET_RE.fullmatch(p["name"]):
            rst = p["name"]
            rst_al = p["name"].lower().endswith(("_n", "_ni")) or "resetn" in p["name"].lower()
            break
    data_ins = [p for p in ins if p["name"] not in (clk, rst)]
    return {"clk": clk, "rst": rst, "rst_active_low": rst_al,
            "data_ins": data_ins, "outs": outs, "all_ins": ins}


def _alias_top(rtl_text: str, old_top: str, new_top: str) -> str:
    """Rename only the top module definition (keep child instantiations intact)."""
    return re.sub(rf"(\bmodule\s+){re.escape(old_top)}\b", rf"\g<1>{new_top}", rtl_text, count=1)


# --------------------------------------------------------------- stimulus
def scenario_vectors(design: str, ports, netfeat, cl=None) -> list[dict]:
    """LLM-proposed, netlist-aware corner scenarios (best-effort; may be empty)."""
    info = classify_ports(ports)
    ins = info["data_ins"]
    if not ins:
        return []
    hints = ""
    if netfeat:
        deep = ", ".join(f"{o['signal']}(depth {o['cone_depth']})"
                         for o in netfeat["summary"].get("deepest_signals", [])[:5])
        hints = f"\nSynthesised netlist -- deepest logic cones: {deep}"
    prompt = (
        f"Propose corner-case input vectors that exercise ALL important scenarios "
        f"of this hardware, for an exhaustive equivalence testbench.\n"
        f"MODULE: {design}\nDATA INPUTS (name : width bits):\n" +
        "\n".join(f"  {p['name']} : {_width(p)}" for p in ins) + hints +
        "\n\nReturn ONE JSON object: {\"vectors\":[{\"name\":\"..\",\"values\":"
        "{\"<input>\":<non-negative integer>}}]}\n"
        "Give 8-16 vectors covering: all-zeros, all-ones, single-bit-set, "
        "alternating bits, any security-critical threshold you can infer and that "
        "value +/-1. Use only the input names above.")
    parsed, rec = llm.generate_json(
        prompt, system="You reply with ONE JSON object only.",
        temperature=0.2, seed=61, num_predict=2500, think=False, key_hint="vectors",
        tag=f"tb:{design}", phase="tb")
    if cl is not None:
        cl.change("tb", "scenario_elicitation", target=design, origin="llm",
                  after=json.dumps((parsed or {}).get("vectors", []))[:600],
                  rationale="LLM-proposed, netlist-aware corner scenarios baked into "
                            "the exhaustive testbench")
    out = []
    known = {p["name"] for p in ins}
    for v in (parsed or {}).get("vectors", []) or []:
        vals = v.get("values", {})
        if isinstance(vals, dict) and any(k in known for k in vals):
            out.append({"name": str(v.get("name", ""))[:40], "values": vals})
    return out


def stimulus_plan(ports) -> dict:
    """Decide exhaustive vs comprehensive-directed+random from the input space."""
    info = classify_ports(ports)
    data_bits = sum(_width(p) for p in info["data_ins"])
    exhaustive = (info["clk"] is None and 0 < data_bits <= EXHAUSTIVE_MAX_BITS)
    return {"sequential": info["clk"] is not None, "data_bits": data_bits,
            "exhaustive": exhaustive, **info}


# --------------------------------------------------------------- TB emission
def emit_tb(design: str, ports, golden_top: str, cur_top: str,
            port_map: dict, scenarios: list[dict]) -> str:
    """Emit the SystemVerilog comparator testbench (golden vs current DUT)."""
    plan = stimulus_plan(ports)
    info = plan
    clk, rst = info["clk"], info["rst"]
    ins, outs = info["all_ins"], info["outs"]
    data_ins = info["data_ins"]
    pm = port_map or {}

    def cur(n):                       # current-phase port name for an original port
        return pm.get(n, n)

    L = ["`timescale 1ns/1ps", "", "module tb_golden_compare;",
         "  integer i, j, errors, vectors; reg [63:0] seed;"]
    for p in ins:
        L.append(f"  reg  {_decl(p)} {p['name']};")
    for p in outs:
        L.append(f"  wire {_decl(p)} {p['name']}_gold, {p['name']}_cur;")

    def conn(top, suffix, mapper):
        parts = []
        for p in ins:
            parts.append(f".{mapper(p['name'])}({p['name']})")
        for p in outs:
            parts.append(f".{mapper(p['name'])}({p['name']}_{suffix})")
        return ",\n    ".join(parts)

    L.append(f"  {golden_top} gold (\n    {conn(golden_top, 'gold', lambda n: n)}\n  );")
    L.append(f"  {cur_top} dut (\n    {conn(cur_top, 'cur', cur)}\n  );")

    cmp_expr = " || ".join(f"({p['name']}_gold !== {p['name']}_cur)" for p in outs) or "1'b0"
    in_fmt = " ".join(f"{p['name']}=%h" for p in ins)
    in_args = ", ".join(p["name"] for p in ins)
    out_fmt = " ".join(f"{p['name']}=%h/%h" for p in outs)
    out_args = ", ".join(f"{p['name']}_gold, {p['name']}_cur" for p in outs)

    L += ["", "  task check; begin", "    #2;",
          f"    vectors = vectors + 1;",
          f"    if ({cmp_expr}) begin",
          "      errors = errors + 1;",
          f'      if (errors <= 15) $display("# MISMATCH v%0d : {in_fmt} :: {out_fmt}",',
          f"        vectors, {in_args}, {out_args});",
          "    end", "  end endtask", ""]

    def set_all(expr):
        return "\n".join(f"    {p['name']} = {{{_width(p)}{{{expr}}}}};" for p in data_ins)

    if clk:
        L += [f"  always #5 {clk} = ~{clk};", ""]

    L.append("  initial begin")
    L.append("    errors = 0; vectors = 0; seed = 64'hCAFEF00D_12345678;")
    for p in ins:
        L.append(f"    {p['name']} = 0;")
    if clk:
        # reset sequence
        rval0 = "1'b0" if info["rst_active_low"] else "1'b1"
        rval1 = "1'b1" if info["rst_active_low"] else "1'b0"
        if rst:
            L.append(f"    {rst} = {rval0};")
        L.append(f"    {clk} = 1'b0;")
        L.append("    repeat (4) @(posedge %s);" % clk)
        if rst:
            L.append(f"    {rst} = {rval1};")
        L.append("    @(negedge %s);" % clk)

    def apply_block(body_lines, clocked):
        b = []
        b += body_lines
        if clocked:
            b.append(f"    @(posedge {clk}); check; @(negedge {clk});")
        else:
            b.append("    check;")
        return "\n".join(b)

    # corner cases
    L.append("    // corner: all-zeros")
    L.append(apply_block([set_all("1'b0")], bool(clk)))
    L.append("    // corner: all-ones")
    L.append(apply_block([set_all("1'b1")], bool(clk)))
    for p in data_ins:
        w = _width(p)
        if w <= 1:
            continue
        L.append(f"    // walking-one on {p['name']}")
        zero_all = set_all("1'b0").lstrip()
        L.append(f"    for (j = 0; j < {w}; j = j + 1) begin")
        L.append("      " + zero_all)
        L.append(f"      {p['name']} = (1 << j);")
        L.append(apply_block([], bool(clk)))
        L.append("    end")

    # LLM scenario vectors
    for sv in scenarios:
        vals = sv["values"]
        lines = [set_all("1'b0")]
        for p in data_ins:
            if p["name"] in vals:
                try:
                    val = int(vals[p["name"]]) & ((1 << _width(p)) - 1)
                except Exception:                              # noqa: BLE001
                    continue
                lines.append(f"    {p['name']} = {_width(p)}'h{val:X};")
        L.append(f"    // scenario: {sv['name'][:40]}")
        L.append(apply_block(lines, bool(clk)))

    # exhaustive or random body
    if plan["exhaustive"]:
        total = 1 << plan["data_bits"]
        # pack the flat index across the data inputs
        L.append(f"    // exhaustive enumeration of {total} input combinations")
        L.append(f"    for (i = 0; i < {total}; i = i + 1) begin")
        bit = 0
        for p in data_ins:
            w = _width(p)
            L.append(f"      {p['name']} = (i >> {bit}) & {(1 << w) - 1};")
            bit += w
        L.append(apply_block([], bool(clk)))
        L.append("    end")
    else:
        L.append(f"    // {RANDOM_VECTORS} deterministic random vectors (all scenarios)")
        L.append(f"    for (i = 0; i < {RANDOM_VECTORS}; i = i + 1) begin")
        for p in data_ins:
            w = _width(p)
            nchunks = (w + 31) // 32
            expr = "$random(seed)" if nchunks == 1 else \
                   "{" + ", ".join(["$random(seed)"] * nchunks) + "}"
            L.append(f"      {p['name']} = {expr};")
        L.append(apply_block([], bool(clk)))
        L.append("    end")

    L += ['    if (errors == 0) $display("TB_PASS %0d", vectors);',
          '    else $display("TB_FAIL %0d", errors);',
          "    $finish;", "  end", "endmodule"]
    return "\n".join(L)


# --------------------------------------------------------------- LLM repair
REPAIR_SYS = ("You are a SystemVerilog testbench-repair assistant. You are given a "
              "testbench and the exact ModelSim compiler/elaboration error. Return "
              "ONLY the corrected full testbench source, no prose, no markdown fences.")


def repair_tb(tb_text: str, error_log: str, design: str, cl=None) -> str | None:
    prompt = (f"This ModelSim testbench for design '{design}' failed to compile or "
              f"elaborate. Fix ONLY what the error requires; keep the stimulus and the "
              f"golden-vs-DUT comparison intact. Output the complete corrected "
              f"testbench.\n\n=== ModelSim error ===\n{error_log[-1500:]}\n\n"
              f"=== testbench ===\n{tb_text}")
    out = llm.generate(prompt, system=REPAIR_SYS, temperature=0.1, seed=71,
                       num_predict=6000, think=False, tag=f"tbfix:{design}", phase="tb")
    out = llm.strip_reasoning(out)
    m = re.search(r"```(?:systemverilog|verilog|sv)?\s*(.*?)```", out, re.S)
    fixed = (m.group(1) if m else out).strip()
    if "module tb_golden_compare" not in fixed:
        return None
    if cl is not None:
        cl.change("tb", "testbench_repair", target=design, origin="llm",
                  after=f"LLM repaired the testbench ({len(fixed)} chars)",
                  rationale="the phase binding produced a compile/elaboration error; "
                            "the local LLM corrected the testbench")
    return fixed


# --------------------------------------------------------------- run a phase
def run_phase(design: str, phase_label: str, original_rtl: Path, current_rtl: Path,
              deps: list[str], ports, scenarios: list[dict], port_map: dict,
              workroot: Path, cl=None, repair_tries: int = 2) -> dict:
    """Build (or reuse) the comparator TB for this phase, run it on ModelSim,
    repairing the TB with the LLM if it will not compile."""
    top = vlog.parse_modules(original_rtl.read_text())[0].name
    golden_top = f"{top}__gold"
    cur_top_orig = vlog.parse_modules(current_rtl.read_text())[0].name
    cur_top = f"{top}__cur"

    wd = Path(workroot) / f"{design}_{phase_label}"
    wd.mkdir(parents=True, exist_ok=True)
    (wd / "golden.v").write_text(_alias_top(original_rtl.read_text(), top, golden_top))
    (wd / "current.v").write_text(_alias_top(current_rtl.read_text(), cur_top_orig, cur_top))

    tb_text = emit_tb(design, ports, golden_top, cur_top, port_map, scenarios)
    tb_path = wd / "tb.sv"
    tb_path.write_text(tb_text)

    rtl_sources = ["golden.v", "current.v", *[str(d) for d in deps]]
    sources = [*rtl_sources, "tb.sv"]
    # Pre-check: compile the RTL alone.  If the ORIGINAL/redacted RTL itself does
    # not compile (e.g. a design that references undeclared signals), that is an
    # RTL defect, not a testbench bug -- LLM testbench repair cannot fix it, so
    # skip the repair loop and report it honestly.
    rtl_only = MS.simulate(rtl_sources, "tb_golden_compare", wd / "_rtlchk", timeout=300)
    rtl_broken = (rtl_only.get("available") and rtl_only.get("compiled") is False)

    res = MS.simulate(sources, "tb_golden_compare", wd, timeout=900)
    tries = 0
    while (not rtl_broken and res.get("available") and res.get("compiled") is False
           and tries < repair_tries):
        tries += 1
        fixed = repair_tb(tb_text, res.get("log", ""), design, cl)
        if not fixed:
            break
        tb_text = fixed
        tb_path.write_text(tb_text)
        res = MS.simulate(sources, "tb_golden_compare", wd, timeout=900)

    res["phase"] = phase_label
    res["tb_repaired_tries"] = tries
    if rtl_broken:
        res["rtl_uncompilable"] = True
        res.setdefault("reason", "design RTL does not compile standalone "
                       "(not a testbench bug; LLM repair skipped)")
    res["dut_module"] = cur_top_orig
    return res, tb_text
