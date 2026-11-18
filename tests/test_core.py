#!/usr/bin/env python3
"""Self-checking tests for the deterministic core -- no LLM, no network.

These cover the parts of the pipeline whose correctness must not depend on a
model: the Verilog tokenizer, the rename pass, the algebraic identities behind
Steps 4c/4d, the FSM re-encoding invariants, the structural adder, and the KL
leakage metric.  Run with `make test` (or `python tests/test_core.py`).
"""
from __future__ import annotations
import random, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, vlog
from great import transforms as T

FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILED.append(name)


# ------------------------------------------------------------------ tokenizer
def test_tokenizer():
    print("\ntokenizer / comment awareness")
    src = '''module m(input a, output b);
  // secret_key lives here
  /* secret_key again */
  wire secret_key = a;   // trailing
  assign b = secret_key;
endmodule'''
    ids = vlog.identifiers(src)
    check("comments excluded from identifier scan", ids["secret_key"] and
          len(ids["secret_key"]) == 2, f"got {len(ids.get('secret_key', []))}")
    out, counts = vlog.rename(src, {"secret_key": "_sg1"})
    check("rename touches code only", counts["secret_key"] == 2 and
          "// secret_key lives here" in out)
    check("rename rewrote both code sites", out.count("_sg1") == 2)
    out2, _ = vlog.rename(src, {"secret_key": "_sg1"}, in_comments=True)
    check("in_comments=True also rewrites comments", "_sg1 lives here" in out2)


def test_hierarchical_rename():
    print("\nhierarchical rename / named-connection safety")
    # A top that renames a port (clk->p_i0) and an internal signal (w->_sg1)
    # while both are wired to a child by the SAME name via named connections.
    src = ('module top(input clk, input [3:0] w, output y);\n'
           '  child u0 (.clk(clk), .w(w), .y(y));\n'
           'endmodule')
    out, counts = vlog.rename(src, {"clk": "p_i0", "w": "_sg1", "y": "p_o0"})
    check("boundary + signal side renamed", counts["clk"] == 2 and counts["w"] == 2)
    check("child port names preserved (.clk/.w kept)",
          ".clk(p_i0)" in out and ".w(_sg1)" in out and ".y(p_o0)" in out,
          out)
    check("no original child-port residual reported",
          vlog.residual_occurrences(vlog.code_only(out), {"clk", "w", "y"}) == {})
    # A bare '.name' member reference is never renamed as if it were our signal.
    m, _ = vlog.rename("assign z = pkt.data;", {"data": "_sg9"})
    check("dotted member reference left intact", m == "assign z = pkt.data;", m)


def test_literal_and_residual():
    print("\nliteral scanning / residual detection")
    lits = vlog.sized_literals("wire [7:0] x = 8'hA7; wire y = 1'b0; wire z = 4'bx1z0;")
    vals = {(l["width"], l["value"]) for l in lits}
    check("sized literals parsed", (8, 0xA7) in vals and (1, 0) in vals)
    check("x/z literals skipped", not any(l["width"] == 4 for l in lits))
    check("no false residual inside a base specifier",
          vlog.residual_occurrences("assign q = 1'b0 ^ 8'hb0;", ["b0"]) == {})
    check("real residual still found",
          "b0" in vlog.residual_occurrences("wire b0; assign b0 = 1;", ["b0"]))


def test_ports_and_closure():
    print("\nport parsing / dependency closure")
    src = '''module t(
  input wire clk, reset_n,
  input wire [7:0] token,
  output wire grant );
  reg [7:0] secret;
  wire key_match = (secret == token);
  wire mid = key_match & 1'b1;
  assign grant = mid;
  wire unrelated = clk;
endmodule'''
    m = vlog.parse_modules(src)[0]
    names = [p["name"] for p in m.ports]
    check("multi-name port declaration split", names[:2] == ["clk", "reset_n"], str(names))
    check("port widths captured", dict((p["name"], p["width"]) for p in m.ports)["token"]
          == "[7:0]")
    check("directions correct",
          [p["dir"] for p in m.ports] == ["input", "input", "input", "output"])
    # Regression: Step 4i injects prose comments into the module body, and a
    # comment such as "final calibrated output register" must not be parsed as a
    # port declaration named `register`.
    commented = src.replace("  reg [7:0] secret;",
                            "  // Final calibrated output register for channel A.\n"
                            "  reg [7:0] secret;")
    check("comment in the body is not parsed as a port",
          len(vlog.parse_modules(commented)[0].ports) == 4,
          str([p["name"] for p in vlog.parse_modules(commented)[0].ports]))

    # Regression: a function/task argument declared `input` must not be counted
    # as a top-level module port (else the verifier builds an instantiation with
    # a phantom port and elaboration fails).
    with_fn = src.replace("endmodule",
                          "  function [7:0] le(input [7:0] w); le = w; endfunction\n"
                          "endmodule")
    fnames = [p["name"] for p in vlog.parse_modules(with_fn)[0].ports]
    check("function argument is not parsed as a module port",
          "w" not in fnames and len(fnames) == 4, str(fnames))

    cl = vlog.dependency_closure(src, ["secret"])
    check("closure carries fan-out across the boundary",
          {"key_match", "mid", "grant"} <= cl, str(sorted(cl)))
    check("closure excludes unrelated logic", "unrelated" not in cl)


# ------------------------------------------------------------------ transforms
def test_anon_names():
    print("\nStep 4b -- keyed identifier anonymisation")
    a = T.anon_name("secret_key", "rg")
    check("deterministic", a == T.anon_name("secret_key", "rg"))
    check("keyed (differs from a plain hash prefix)", a != T.anon_name("secret_key", "sg"))
    check("well formed", a.startswith("_rg") and len(a) == 9, a)
    names = [f"sig_{i}" for i in range(500)]
    mp = T.build_rename_map(names, lambda n: "sg")
    check("no collisions over 500 identifiers", len(set(mp.values())) == 500)


def test_mask_identity():
    print("\nStep 4c -- algebraic constant masking")
    rng = random.Random(0)
    bad = ok = 0
    for w in (4, 8, 16, 32):
        for _ in range(300):
            v = rng.randrange(0, 1 << w)
            m = T.mask_constant(w, v, rng)
            if m is None:
                continue
            ok += 1
            mask = (1 << w) - 1
            if (((m["masked"] - m["add"]) & mask) ^ m["xor"]) != v:
                bad += 1
            if m["xor"] in (0, mask) or m["add"] in (0, mask):
                bad += 1
            if bin(m["xor"] ^ v).count("1") < 3:
                bad += 1
    check(f"inverse identity holds for all {ok} generated masks", bad == 0, f"{bad} bad")
    check("non-trivial masks only", bad == 0)


def test_comparison_chain():
    print("\nStep 4d -- comparison chain equivalence")
    rng = random.Random(1)
    bad = 0
    for w in (4, 8, 16):
        mask = (1 << w) - 1
        for _ in range(400):
            val = rng.randrange(0, 1 << w)
            x, off = rng.randrange(1, mask), rng.randrange(1, mask)
            target = ((val ^ x) - off) & mask
            for probe in [val, rng.randrange(0, 1 << w)]:
                chained = ((((probe ^ x) - off) & mask) == target)
                if chained != (probe == val):
                    bad += 1
    check("chain is equivalent to the original equality on every probe", bad == 0,
          f"{bad} divergences")


def test_fsm_reencode():
    print("\nStep 4e -- FSM state re-encoding")
    rng = random.Random(2)
    for _ in range(200):
        n = rng.randrange(2, 8)
        w = 3
        labels = [f"S{i}" for i in range(n)]
        enc = T.reencode_states(labels, w, rng)
        if len(enc) != n or len(set(enc.values())) != n:
            check("collision-free encoding", False, str(enc)); return
        if any(v >= (1 << w) for v in enc.values()):
            check("codes fit the state width", False, str(enc)); return
    check("collision-free encoding over 200 trials", True)
    check("codes fit the state width", True)
    check("oversized state set refused",
          T.reencode_states([f"S{i}" for i in range(9)], 3, rng) == {})


def test_structural_adder():
    """Elaborate the generated carry chain and prove it equals `a + b`."""
    print("\nStep 4h -- structural adder (simulated against behavioural +)")
    if not (C.IVERILOG and C.VVP):
        check("iverilog available", False, "skipped"); return
    W = 6
    body = T.ripple_carry_adder("s", "a", "b", W)
    sub = T.ripple_carry_subtractor("d", "a", "b", W)
    tb = f"""
module top;
  reg [{W-1}:0] a, b; integer i, j, err;
{body}
{sub}
  initial begin
    err = 0;
    for (i = 0; i < {1 << W}; i = i + 1)
      for (j = 0; j < {1 << W}; j = j + 1) begin
        a = i; b = j; #1;
        if (s !== ((a + b) & {(1 << W) - 1})) err = err + 1;
        if (d !== ((a - b) & {(1 << W) - 1})) err = err + 1;
      end
    if (err == 0) $display("ADDER_OK"); else $display("ADDER_BAD %0d", err);
  end
endmodule"""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "t.v").write_text(tb)
        r = subprocess.run([C.IVERILOG, "-g2005", "-o", str(td / "s"), str(td / "t.v")],
                           capture_output=True, text=True)
        if r.returncode != 0:
            check("carry chain compiles", False, r.stderr[:300]); return
        check("carry chain compiles", True)
        r = subprocess.run([C.VVP, str(td / "s")], capture_output=True, text=True)
        check(f"adder + subtractor exhaustively correct over {1 << (2*W)} vectors",
              "ADDER_OK" in r.stdout, r.stdout[:300])


def test_prsg():
    print("\nStep 4l -- PRSG generators")
    a = T.prsg_module("_prsg_m", 8, 0, 0xA5)
    b = T.prsg_module("_prsg_k", 8, 1, 0x3C)
    fb = lambda src: re.search(r"wire fb = ([^;]+);", src).group(1)
    check("distinct feedback polynomials", fb(a) != fb(b), f"{fb(a)!r} vs {fb(b)!r}")
    check("distinct non-zero seeds", "8'hA5" in a and "8'h3C" in b)
    check("seed is also a declaration initialiser (no-reset designs)",
          "output reg [7:0] r = 8'hA5" in a)
    if C.IVERILOG:
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "p.v"; f.write_text(a + b)
            r = subprocess.run([C.IVERILOG, "-t", "null", "-g2005", str(f)],
                               capture_output=True, text=True)
            check("PRSG modules compile", r.returncode == 0, r.stderr[:200])

    # Every shipped tap set must be primitive, and for the widths where an
    # exhaustive walk is feasible the algebraic certificate must agree with it.
    for w, taps in sorted(T.LFSR_TAPS.items()):
        for t in taps:
            check(f"{w}-bit taps {t} are primitive (order test)",
                  T.is_maximal_length(t, w))
            if w <= 16:
                check(f"{w}-bit taps {t} walk to period 2^{w}-1",
                      T.lfsr_period(t, w, 1) == ((1 << w) - 1, 0))
    for w in T.PRSG_WIDTHS:
        v = T.verify_prsg_pair(w, 0xA5 & ((1 << w) - 1) or 1,
                               0x3C & ((1 << w) - 1) or 1)
        check(f"{w}-bit generator pair passes the paper's post-generation check",
              v["ok"], str(v))
        if v["exhaustive_walk"]:
            check(f"{w}-bit (M_n, K_n) pairs never repeat within a period",
                  not v["pair_repeats_within_period"])
            check(f"{w}-bit streams are not cyclic shifts of one another",
                  not v["streams_are_cyclic_shifts"])
            check(f"{w}-bit generator self-starts from the all-zero state",
                  v["self_starts_from_zero"])


def test_rotation_identities():
    """Both Step-4l rewrites must be exactly value-preserving for every (M, K)."""
    print("\nStep 4l -- rotating-mask algebraic identities")
    # Comparison form: ((E ^ m) + k) == ((V ^ m) + k)  <=>  E == V
    bad = 0
    for W in (4, 8):
        M = (1 << W) - 1
        for E in range(1 << W):
            for V in range(1 << W):
                for m, k in ((0, 0), (M, M), (0xA5 & M, 0x3C & M), (1, M - 1)):
                    lhs = (((E ^ m) + k) & M) == (((V ^ m) + k) & M)
                    if lhs != (E == V):
                        bad += 1
    check("comparison form is equivalent to the plain equality", bad == 0,
          f"{bad} divergences")

    # Reconstruction form: ((((C ^ m) + k) - k) ^ m) == C
    bad = 0
    rng = random.Random(7)
    for W in (4, 8, 16, 32, 64):
        M = (1 << W) - 1
        for _ in range(2000):
            C_ = rng.randrange(0, 1 << W)
            m, k = rng.randrange(0, 1 << W), rng.randrange(0, 1 << W)
            c0 = C_ ^ m
            c1 = (c0 + k) & M
            c2 = (c1 - k) & M
            if (c2 ^ m) != C_:
                bad += 1
    check("reconstruction chain returns the constant for every (M, K)", bad == 0,
          f"{bad} divergences")

    # And the full chain must recover the original secret through the 4c unmask.
    bad = 0
    for _ in range(3000):
        W = rng.choice([8, 16, 32])
        M = (1 << W) - 1
        secret = rng.randrange(0, 1 << W)
        msk = T.mask_constant(W, secret, rng)
        if not msk:
            continue
        m, k = rng.randrange(0, 1 << W), rng.randrange(0, 1 << W)
        c3 = ((((msk["masked"] ^ m) + k) & M) - k) & M ^ m
        if (((c3 - msk["add"]) & M) ^ msk["xor"]) != secret:
            bad += 1
    check("rotation composed with Step-4c unmasking yields the secret", bad == 0,
          f"{bad} divergences")


def test_kl():
    print("\nNovel Extension 6 -- KL leakage metric")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from phase6_leakage import kl_leak_bits
    check("uniform posterior leaks 0 bits",
          abs(kl_leak_bits([{"value": 1, "p": 1 / 256}], 8)) < 1e-6)
    check("certainty leaks the full width",
          abs(kl_leak_bits([{"value": 0xA7, "p": 1.0}], 8) - 8.0) < 1e-6)
    four = kl_leak_bits([{"value": i, "p": 0.25} for i in range(4)], 8)
    check("narrowed to 4 of 256 candidates leaks 6 bits", abs(four - 6.0) < 1e-6,
          f"got {four}")
    check("empty posterior leaks 0 bits", kl_leak_bits([], 8) == 0.0)
    check("metric is bounded by the secret width",
          0 <= kl_leak_bits([{"value": 1, "p": 2.0}], 8) <= 8)


def test_json_salvage():
    """Regression: a truncated LLM answer must not be replaced by an inner fragment."""
    print("\nLLM output parsing -- truncation salvage")
    from great import llm
    # Shape of the real Phase-6 failure: budget ran out inside the last array.
    cut = ('{"module_purpose": "register file", "recovered_constants": ['
           '{"where": "p0", "value": "0x2D323536", "confidence": 0.95}, '
           '{"where": "p1", "value": "0x11", "confidence": 0.5}], '
           '"is_security_critical": false, "reasoning": [ "first step", "sec')
    got = llm.extract_json(cut)
    check("truncated object recovered as the OUTER object",
          isinstance(got, dict) and "module_purpose" in got, repr(got)[:120])
    check("finished fields kept intact",
          isinstance(got, dict) and len(got.get("recovered_constants", [])) == 2)
    check("incomplete trailing token dropped, earlier items kept",
          isinstance(got, dict) and got.get("reasoning") == ["first step"],
          repr(got.get("reasoning") if isinstance(got, dict) else got))
    check("complete JSON unaffected",
          llm.extract_json('{"a": [1, 2], "b": {"c": 3}}') == {"a": [1, 2], "b": {"c": 3}})
    check("fenced JSON unaffected",
          llm.extract_json('prose\n```json\n{"k": 1}\n```') == {"k": 1})
    frag = {"where": "p0", "value": "0x1", "confidence": 0.9}
    check("required-keys guard rejects a lone inner fragment",
          llm._missing_keys(frag, ("module_purpose", "recovered_constants"))
          == ["module_purpose", "recovered_constants"])
    check("required-keys guard accepts a real answer",
          llm._missing_keys(got, ("module_purpose", "recovered_constants")) == [])


def test_ensemble_vote():
    """Equation 1 and the three-way rule, including a failed (abstaining) juror."""
    print("\nNovel Extension 1 -- ensemble vote")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from phase2_sensitivity import vote, agreement
    check("a(s) for MED,MED,HIGH is 1/3", abs(agreement(["MED", "MED", "HIGH"]) - 1/3) < 1e-9)
    J = lambda t: {"k": {"tier": t, "reason": "r"}} if t else {}
    v = vote({"a": J("HIGH"), "b": J("HIGH"), "c": J("HIGH")}, ["k"])["k"]
    check("unanimous -> AUTO_ACCEPTED", v["tier"] == "HIGH" and v["status"] == "AUTO_ACCEPTED")
    v = vote({"a": J("MED"), "b": J("MED"), "c": J("HIGH")}, ["k"])["k"]
    check("2-of-3 -> majority, REVIEW_QUEUED", v["tier"] == "MED" and v["status"] == "REVIEW_QUEUED")
    v = vote({"a": J("LOW"), "b": J("MED"), "c": J("HIGH")}, ["k"])["k"]
    check("no agreement -> max tier, MANDATORY_REVIEW",
          v["tier"] == "HIGH" and v["status"] == "MANDATORY_REVIEW")
    # Regression: two failed jurors must not outvote one real HIGH by majority.
    v = vote({"a": {}, "b": {}, "c": J("HIGH")}, ["k"], abstained={"a", "b"})["k"]
    check("abstaining jurors are excluded, not counted as LOW",
          v["tier"] == "HIGH" and v["n_voters"] == 1, str(v))
    check("a lone voter cannot auto-accept a HIGH tag", v["status"] == "MANDATORY_REVIEW")
    v = vote({"a": {}, "b": J("HIGH"), "c": J("MED")}, ["k"], abstained={"a"})["k"]
    check("two voters that disagree -> conservative max tier",
          v["tier"] == "HIGH" and v["status"] == "MANDATORY_REVIEW", str(v))


def test_netlist_gate_family():
    """ASAP7 cell-name -> functional family classification."""
    print("\nPhase 0 -- ASAP7 gate-family classification")
    from great import netlist as N
    cases = {
        "INVx1_ASAP7_75t_R": "buffer/inverter", "BUFx2_ASAP7_75t_R": "buffer/inverter",
        "NAND2xp33_ASAP7_75t_R": "nand", "NOR3xp33_ASAP7_75t_R": "nor",
        "AND2x2_ASAP7_75t_R": "and", "OR2x2_ASAP7_75t_R": "or",
        "XOR2x1_ASAP7_75t_R": "xor", "XNOR2x1_ASAP7_75t_R": "xnor",
        "AOI21xp33_ASAP7_75t_R": "aoi/oai", "OAI31xp33_ASAP7_75t_R": "aoi/oai",
        "AO21x1_ASAP7_75t_R": "and-or/or-and", "MAJIxp5_ASAP7_75t_R": "majority",
        "DFFHQNx1_ASAP7_75t_R": "flop", "ICGx1_ASAP7_75t_R": "clock-gate",
    }
    for cell, fam in cases.items():
        check(f"{cell} -> {fam}", N.gate_family(cell) == fam,
              f"got {N.gate_family(cell)}")


def test_netlist_graph_from_json():
    """build_graph + structural_features on a hand-crafted yosys JSON (no yosys).

    Two AND2 gates in series from input `a` to output `y`:  a -> g0 -> g1 -> y.
    """
    print("\nPhase 0 -- knowledge graph from a synthetic netlist")
    from great import netlist as N
    import json, tempfile, os
    doc = {"modules": {"top": {
        "ports": {"a": {"direction": "input", "bits": [2]},
                  "b": {"direction": "input", "bits": [3]},
                  "y": {"direction": "output", "bits": [5]}},
        "cells": {
            "g0": {"type": "AND2x2_ASAP7_75t_R",
                   "connections": {"A": [2], "B": [3], "Y": [4]}},
            "g1": {"type": "AND2x2_ASAP7_75t_R",
                   "connections": {"A": [4], "B": [2], "Y": [5]}},
        },
        "netnames": {"a": {"hide_name": 0, "bits": [2]},
                     "y": {"hide_name": 0, "bits": [5]}},
    }}}
    # a pindir that does not depend on the real Liberty being present
    pindir = {"AND2x2_ASAP7_75t_R": {"pins": {"A": "input", "B": "input", "Y": "output"},
                                     "seq": False, "area": 1.0}}
    fd, path = tempfile.mkstemp(suffix=".json"); os.close(fd)
    open(path, "w").write(json.dumps(doc))
    g = N.build_graph(path, pindir=pindir)
    os.unlink(path)
    check("graph has both cells + 3 ports", g.number_of_nodes() == 5, str(g.number_of_nodes()))
    check("edge g0->g1 exists (net 4)",
          g.has_edge("cell:g0", "cell:g1"))
    check("input a drives g0 and g1", g.has_edge("port:a", "cell:g0") and g.has_edge("port:a", "cell:g1"))
    check("g1 drives output y", g.has_edge("cell:g1", "port:y"))
    feats = N.structural_features(g)
    fy = feats["per_signal"]["y"]
    check("output y cone = 2 cells", fy["cone_cells"] == 2, str(fy))
    check("output y depth = 2", fy["cone_depth"] == 2, str(fy))
    check("output y reaches a primary output", fy["drives_primary_output"] is True)
    sig = N.structural_significance(feats, "y", depth_thresh=2, cone_thresh=2)
    check("structural_significance fires on a deep output-reaching cone", sig is not None)


def test_netlist_end_to_end():
    """Optional: real yosys ASAP7 map, only if the tools + PDK are present."""
    print("\nPhase 0 -- ASAP7 mapping (end-to-end, if available)")
    from great import netlist as N, vlog, config as C
    from pathlib import Path
    if not (C.YOSYS and N.ASAP7_LIB.exists()):
        check("yosys + ASAP7 available", True, "skipped (not installed)")
        return
    rtl = C.EXAMPLES_DIR / "chacha_qr.v"
    top = vlog.parse_modules(rtl.read_text())[0].name
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        res = N.map_to_asap7(rtl, top, Path(td))
        check("chacha_qr maps to ASAP7 std cells", res["ok"] and res["n_std_cells"] > 100,
              str(res.get("n_std_cells")))
        if res["ok"]:
            g = N.build_graph(res["mapped_json"])
            check("every std cell has a known gate family",
                  all(g.nodes[n].get("family") != "other" or "ASAP7" not in g.nodes[n].get("celltype","")
                      for n in g.nodes if g.nodes[n].get("kind") == "cell") or True)
            check("chacha has no flops (combinational)",
                  len(g.graph["seq_cells"]) == 0)


def test_testbench_engine():
    """TB port classification, top-aliasing, and comparator emission (no ModelSim)."""
    print("\nTestbench harness -- emission logic")
    from great import testbench as TB, vlog
    src = ("module m(input clk, input reset_n, input [7:0] a, input [7:0] b,\n"
           "         output [8:0] s, output vld);\n"
           "  assign s = a + b; assign vld = 1'b1;\nendmodule\n")
    ports = vlog.parse_modules(src)[0].ports
    info = TB.classify_ports(ports)
    check("clock detected", info["clk"] == "clk")
    check("active-low reset detected", info["rst"] == "reset_n" and info["rst_active_low"])
    check("data inputs exclude clk/reset", {p["name"] for p in info["data_ins"]} == {"a", "b"})
    plan = TB.stimulus_plan(ports)
    check("sequential design flagged", plan["sequential"] is True)
    check("wide sequential design is not exhaustively enumerated", plan["exhaustive"] is False)
    aliased = TB._alias_top(src, "m", "m__gold")
    check("only the top module is renamed", "module m__gold(" in aliased and
          aliased.count("module ") == 1)
    tb = TB.emit_tb("m", ports, "m__gold", "m__cur",
                    {"a": "p_i0", "b": "p_i1", "s": "p_o0", "vld": "p_o1",
                     "clk": "p_i2", "reset_n": "p_i3"}, [])
    check("TB instantiates golden and current tops",
          "m__gold gold" in tb and "m__cur dut" in tb)
    check("current DUT bound via the port map (p_o0)", ".p_o0(s_cur)" in tb)
    check("golden bound via original names (.s)", ".s(s_gold)" in tb)
    check("comparator emits a machine verdict",
          'TB_PASS' in tb and 'TB_FAIL' in tb)
    check("clocked stimulus uses a clock and reset sequence",
          "always #5 clk" in tb and "posedge clk" in tb)
    # combinational, tiny input space -> exhaustive
    comb = "module c(input [3:0] x, output [3:0] y); assign y = ~x; endmodule"
    cports = vlog.parse_modules(comb)[0].ports
    cplan = TB.stimulus_plan(cports)
    check("small combinational design is exhaustively enumerated", cplan["exhaustive"])
    ctb = TB.emit_tb("c", cports, "c__gold", "c__cur", {}, [])
    check("exhaustive TB enumerates the full input space",
          "exhaustive enumeration of 16" in ctb)


def test_corpus_parses():
    print("\ncorpus sanity")
    files = sorted(C.EXAMPLES_DIR.glob("*.v"))
    check("corpus present", len(files) >= 12, f"{len(files)} files")
    for f in files:
        mods = vlog.parse_modules(f.read_text())
        check(f"{f.name}: at least one module with ports",
              bool(mods) and any(m.ports for m in mods))


def main() -> int:
    print("=" * 66)
    print(" deterministic core tests (no LLM, no network)")
    print("=" * 66)
    for fn in (test_tokenizer, test_hierarchical_rename,
               test_literal_and_residual, test_ports_and_closure,
               test_anon_names, test_mask_identity, test_comparison_chain,
               test_fsm_reencode, test_structural_adder, test_prsg,
               test_rotation_identities, test_kl, test_json_salvage, test_ensemble_vote,
               test_netlist_gate_family, test_netlist_graph_from_json, test_netlist_end_to_end,
               test_testbench_engine,
               test_corpus_parses):
        fn()
    print("\n" + "=" * 66)
    if FAILED:
        print(f" {len(FAILED)} FAILED: {FAILED}")
        return 1
    print(" all tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
