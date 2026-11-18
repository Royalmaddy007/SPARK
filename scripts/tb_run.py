#!/usr/bin/env python3
"""Exhaustive phase-travelling testbench harness (ModelSim).

Writes ONE self-checking comparator testbench per design (frozen original as
golden reference vs. the design at the current phase), then evaluates it at
EVERY incremental phase of the flow -- baseline (pre-redaction), the annotated
RTL (Phase 3), the redacted RTL (Phase 4), and each Phase-6B escalation round --
recording pass/fail for each on ModelSim.  The stimulus/checking is written
once; only the DUT binding transforms per phase (from the Phase-4 manifests).
If a phase's binding breaks the testbench, the local LLM repairs it.

Output: pipeline/testbench/<design>.{tb.sv, <phase>.tb.sv, tb_results.json,
        changelog.json}
"""
from __future__ import annotations
import json, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, vlog, util, llm
from great import testbench as TB
from great import netlist as N
from great import modelsim as MS
from great.changelog import ChangeLog


def phase_states(design: str, orig: Path):
    """(phase_label, rtl_path, port_map) for every phase whose RTL we can check."""
    top = vlog.parse_modules(orig.read_text())[0].name
    states = [("0_baseline", orig, {}),
              ("1_profiling", orig, {}),
              ("2_sensitivity", orig, {})]
    ann = C.PHASE_DIRS[3] / f"{design}.annotated.v"
    states.append(("3_strategy", ann if ann.exists() else orig, {}))
    mf_p = C.PHASE_DIRS[4] / f"{design}.manifests.json"
    if mf_p.exists():
        mf = json.loads(mf_p.read_text())
        red = C.ROOT / mf["redacted_rtl"]
        pmap = {m["original"]: m["redacted"] for m in mf.get("port_manifest", [])}
        if red.exists():
            states.append(("4_transform", red, pmap))
    # Phase-6B escalation rounds
    esc_p = C.PHASE_DIRS["6b"] / f"{design}.escalation.json"
    if esc_p.exists():
        esc = json.loads(esc_p.read_text())
        for h in esc.get("history", []):
            r = h.get("round", 0)
            if r and h.get("artifact"):
                art = C.ROOT / h["artifact"]
                rmf = C.PHASE_DIRS[4] / f"{design}.r{r}.manifests.json"
                pm = {}
                if rmf.exists():
                    pm = {m["original"]: m["redacted"]
                          for m in json.loads(rmf.read_text()).get("port_manifest", [])}
                if art.exists():
                    states.append((f"6b_round{r}", art, pm))
    return states


def run_design(path: Path) -> dict:
    design = path.stem
    cl = ChangeLog("testbench", design, str(path.relative_to(C.ROOT)))
    d = C.phase_dir("tb")
    ports = vlog.parse_modules(path.read_text())[0].ports
    deps = C.dep_files(design)

    if not MS.AVAILABLE:
        cl.fault("tb", "modelsim_unavailable", "ModelSim (vsim) not found on PATH",
                 "install/point to modelsim_ase; the harness cannot run", resolved=False)
        cl.write(d / f"{design}.changelog.json")
        return {"design": design, "ok": False, "reason": "no modelsim"}

    # scenarios: elicited ONCE (netlist-aware), baked into the single testbench
    netfeat = N.load_features(design)
    scenarios = TB.scenario_vectors(design, ports, netfeat, cl)
    plan = TB.stimulus_plan(ports)
    cl.note(sequential=plan["sequential"], data_bits=plan["data_bits"],
            exhaustive=plan["exhaustive"], n_scenarios=len(scenarios),
            deps=[Path(x).name for x in deps], modelsim=MS.BINDIR)

    work = C.ROOT / "pipeline" / ".tb_work"
    states = phase_states(design, path)
    results = []
    canonical_saved = False
    for label, rtl, pmap in states:
        res, tb_text = TB.run_phase(design, label, path, rtl, deps, ports,
                                    scenarios, pmap, work, cl)
        # save the once-written canonical TB (from the baseline binding) + per-phase
        if not canonical_saved:
            (d / f"{design}.tb.sv").write_text(tb_text)
            canonical_saved = True
        (d / f"{design}.{label}.tb.sv").write_text(tb_text)
        entry = {"phase": label, "rtl": str(Path(rtl).relative_to(C.ROOT)),
                 "compiled": res.get("compiled"), "passed": res.get("passed"),
                 "n_vectors": res.get("n_vectors"), "n_fail": res.get("n_fail"),
                 "tb_repaired_tries": res.get("tb_repaired_tries", 0),
                 "reason": res.get("reason")}
        results.append(entry)
        verdict = ("PASS" if res.get("passed") else
                   "REPAIRED+PASS" if res.get("passed") and res.get("tb_repaired_tries")
                   else "FAIL" if res.get("compiled") else "COMPILE_FAIL")
        cl.change("tb", "phase_check", target=label, origin="script",
                  after=f"{verdict}: {res.get('n_vectors')} vectors, "
                        f"{res.get('n_fail') or 0} mismatch(es), "
                        f"repairs={res.get('tb_repaired_tries', 0)}",
                  rationale="comparator testbench (golden original vs this phase's RTL) "
                            "run on ModelSim over comprehensive stimulus")
        if res.get("compiled") is False:
            cl.fault("tb", "testbench_compile_failed_at_phase",
                     f"testbench did not compile at {label} even after "
                     f"{res.get('tb_repaired_tries', 0)} LLM repair attempt(s)",
                     "reported; the LLM repair loop is bounded to avoid spinning",
                     resolved=False, phase=label)
        elif res.get("passed") is False:
            cl.fault("tb", "functional_mismatch_at_phase",
                     f"the design at {label} diverges from the golden original: "
                     f"{res.get('mismatches', [])[:3]}",
                     "flags a real functional regression at this phase -- the "
                     "transformation broke behaviour", resolved=False, phase=label)

    npass = sum(1 for r in results if r["passed"])
    out = {"design": design, "modelsim": MS.BINDIR,
           "sequential": plan["sequential"], "exhaustive": plan["exhaustive"],
           "n_scenarios": len(scenarios), "phases": results,
           "all_phases_pass": all(r["passed"] for r in results),
           "n_phases": len(results), "n_pass": npass}
    util.write_json(d / f"{design}.tb_results.json", out)
    cl.artifact("tb_results", d / f"{design}.tb_results.json")
    cl.artifact("testbench", d / f"{design}.tb.sv")
    cl.summarise(all_phases_pass=out["all_phases_pass"], n_pass=npass,
                 n_phases=len(results), sequential=plan["sequential"],
                 exhaustive=plan["exhaustive"])
    cl.write(d / f"{design}.changelog.json")
    shutil.rmtree(work, ignore_errors=True)
    return out


def main() -> int:
    args = util.design_args(__doc__).parse_args()
    llm.start_log("testbench")
    util.banner("TESTBENCH HARNESS -- exhaustive phase-travelling checks (ModelSim)")
    if not MS.AVAILABLE:
        util.warn("ModelSim (vsim) not found -- cannot run the testbench harness.")
        return 1
    util.info(f"ModelSim: {MS.BINDIR}")
    index = []
    for p in util.resolve_designs(args):
        util.info(f"testbench {p.name}")
        r = run_design(p)
        if r.get("ok") is False:
            util.warn(f"    {r.get('reason')}")
            index.append({"design": r["design"], "ok": False})
            continue
        util.info(f"    {r['n_pass']}/{r['n_phases']} phases PASS  "
                  f"(exhaustive={r['exhaustive']}, sequential={r['sequential']}, "
                  f"scenarios={r['n_scenarios']})")
        for ph in r["phases"]:
            v = ("PASS" if ph["passed"] else
                 "FAIL" if ph["compiled"] else "COMPILE_FAIL")
            util.info(f"      {ph['phase']:14} {v:12} "
                      f"vec={ph['n_vectors']} repairs={ph['tb_repaired_tries']}")
        index.append({"design": r["design"], "ok": True,
                      "all_pass": r["all_phases_pass"],
                      "n_pass": r["n_pass"], "n_phases": r["n_phases"]})
    util.write_json(C.phase_dir("tb") / "index.json",
                    {"phase": "tb", "designs": index, "llm_stats": llm.stats()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
