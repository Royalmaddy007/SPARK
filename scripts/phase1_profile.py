#!/usr/bin/env python3
"""Phase 1 -- Target Selection & Design Profiling.

Static profile of each candidate design (module hierarchy, ports, literals,
FSM candidates, arithmetic operators, silicon-bound flag) combined with an LLM
design summary that flags likely crown-jewel regions.  The output primes Phase 2
without requiring a full manual inspection, and the selection criteria of the
paper (security-critical logic, synthesisable, testbench-able, open licence) are
scored explicitly so target selection is auditable.
"""
from __future__ import annotations
import os, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, llm, vlog, util
from great import netlist as N
from great.changelog import ChangeLog

SYSTEM = ("You are a hardware security analyst profiling open-source Verilog RTL. "
          "You answer only with a single JSON object. Never emit prose or markdown.")

PROMPT = """Profile the Verilog module(s) below for a hardware IP redaction study.

Return ONE JSON object with exactly these keys:
{{
  "design_purpose": "<one sentence: what this hardware does>",
  "security_role": "<one sentence: why an attacker would care about it>",
  "crown_jewel_regions": [
     {{"name":"<signal/localparam/module/expression>",
       "why":"<short reason this is the crown jewel>"}}
  ],
  "primary_datapaths": ["<signal name>", ...],
  "likely_fsms": ["<state register name>", ...],
  "contains_crypto_constants": true|false,
  "contains_access_control": true|false,
  "silicon_bound": true|false,
  "confidence": 0.0-1.0
}}

Rules:
- "crown_jewel_regions" must name identifiers that literally appear in the RTL.
- List at most 6 crown-jewel regions, most important first.
- Every string value must be under 20 words. Keep the whole object compact.
- "silicon_bound" is true if this block plausibly reaches fabricated silicon
  (a real datapath/keystore), false if it is glue, debug or test scaffolding.

MODULE FILE: {fname}
STATIC FACTS (computed by the orchestration script, trust these over your own count):
{facts}

SYNTHESISED NETLIST FACTS (ASAP7 gate-level map -- use this to judge which logic
is real, deep and silicon-bound versus glue):
{netlist}

VERILOG:
```verilog
{rtl}
```"""

ARITH_OPS = re.compile(r"(?<![\w'])([+\-*/%])(?![\w'])")


def static_profile(src: str) -> dict:
    mods = vlog.parse_modules(src)
    lits = vlog.sized_literals(src)
    lps = vlog.localparams(src)
    cases = vlog.case_items(src)
    decls = vlog.declarations(src)
    cs = vlog.code_only(src)
    regs = [n for d in decls if d["kw"] == "reg" for n in d["names"]]
    fsm_candidates = []
    for c in cases:
        sel = c["select"].strip()
        base = re.sub(r"\[.*", "", sel).strip()
        symbolic = [l for l in c["labels"] if re.search(r"[A-Za-z_]", l)]
        if symbolic and base in regs:
            fsm_candidates.append({"state_reg": base, "n_states": len(symbolic),
                                   "labels": symbolic})
    ops = ARITH_OPS.findall(cs)
    return {
        "modules": [{"name": m.name, "n_ports": len(m.ports),
                     "ports": m.ports} for m in mods],
        "n_modules": len(mods),
        "n_lines": src.count("\n") + 1,
        "n_sized_literals": len(lits),
        "distinct_literal_values": len({(l["width"], l["value"]) for l in lits}),
        "wide_literals": [l["text"] for l in lits if l["width"] >= 8][:40],
        "localparams": [{"name": l["name"], "value": l["value"]} for l in lps],
        "n_case_blocks": len(cases),
        "fsm_candidates": fsm_candidates,
        "arithmetic_operator_counts": {op: ops.count(op) for op in set(ops)},
        "n_registers": len(regs),
        "has_testbench_hooks": bool(re.search(r"\bDEBUG\b|\$display", cs)),
    }


def selection_score(prof: dict, llm_prof: dict, *, audited_license: bool) -> dict:
    """Paper Phase 1 selection criteria, scored 0/1 each."""
    crit = {
        "contains_security_critical_logic":
            bool(llm_prof.get("contains_crypto_constants")
                 or llm_prof.get("contains_access_control")
                 or prof["fsm_candidates"]),
        "synthesisable_rtl": prof["n_modules"] > 0,
        "has_identifiable_crown_jewel": len(llm_prof.get("crown_jewel_regions", [])) > 0,
        # The original benchmark corpus is audited in examples/CITATIONS.json.
        # A downloaded dataset project has not undergone that licence audit.
        "open_source_licence": audited_license,
    }
    return {"criteria": crit, "score": sum(crit.values()), "max": len(crit),
            "selected": sum(crit.values()) >= 3}


def compile_check(path: Path) -> dict:
    if not C.IVERILOG:
        return {"ran": False, "reason": "iverilog not found"}
    out = subprocess.run([C.IVERILOG, "-t", "null", "-g2005", "-s", vlog.parse_modules(path.read_text())[0].name, str(path),
                          *C.dep_files(path.stem)], capture_output=True, text=True)
    return {"ran": True, "ok": out.returncode == 0,
            "stderr": out.stderr.strip()[:2000]}


def profile_one(path: Path) -> dict:
    src = path.read_text()
    cl = ChangeLog("phase1_profiling", path.stem, str(path.relative_to(C.ROOT)))
    prof = static_profile(src)
    comp = compile_check(path)
    cl.note(static_profile=prof, standalone_compile=comp)

    facts = (f"modules={[m['name'] for m in prof['modules']]}; "
             f"lines={prof['n_lines']}; sized_literals={prof['n_sized_literals']}; "
             f"localparams={[l['name'] for l in prof['localparams']][:20]}; "
             f"case_blocks={prof['n_case_blocks']}; "
             f"fsm_candidates={[f['state_reg'] for f in prof['fsm_candidates']]}; "
             f"arith_ops={prof['arithmetic_operator_counts']}")
    netfeat = N.load_features(path.stem)
    netblurb = N.context_blurb(netfeat) if netfeat else "(design not mapped to ASAP7)"
    if netfeat:
        cl.change("1", "netlist_context_added", target=path.stem, origin="script",
                  after=netblurb[:300],
                  rationale="Phase-0 ASAP7 gate-level map supplied to profiling so the "
                            "LLM grounds crown-jewel and silicon-bound judgements in the "
                            "synthesised structure, not just the source text")
    rtl, view_meta = vlog.analysis_view(src, 24000)
    cl.note(analysis_view=view_meta)
    parsed, rec = llm.generate_json(
        PROMPT.format(fname=path.name, facts=facts, rtl=rtl, netlist=netblurb)
        + "\nEND OF RTL INPUT. Analyse its purpose and crown jewels; do not write Verilog. Return only the requested compact JSON object.",
        system=SYSTEM, temperature=0.0, seed=7, num_predict=3000, key_hint="crown_jewel_regions",
        tag=f"p1:{path.stem}", phase="1")

    if parsed is None:
        cl.fault("1", "unparseable_profile",
                 "LLM design summary could not be parsed as JSON after one repair retry",
                 "fell back to the static profile only; no downstream phase depends "
                 "on the narrative summary", resolved=True)
        parsed = {"design_purpose": "", "security_role": "", "crown_jewel_regions": [],
                  "primary_datapaths": [], "likely_fsms": [],
                  "contains_crypto_constants": prof["n_sized_literals"] > 16,
                  "contains_access_control": bool(prof["fsm_candidates"]),
                  "silicon_bound": True, "confidence": 0.0}

    # Fault check: hallucinated identifiers in crown_jewel_regions.
    idents = set(vlog.identifiers(src))
    kept, dropped = [], []
    for r in parsed.get("crown_jewel_regions", []) or []:
        nm = str(r.get("name", "")).strip()
        base = re.sub(r"\[.*|\(.*", "", nm).strip()
        if base and (base in idents or base in {m["name"] for m in prof["modules"]}):
            kept.append(r)
        else:
            dropped.append(r)
    if dropped:
        cl.fault("1", "hallucinated_identifier",
                 f"LLM named {len(dropped)} crown-jewel region(s) absent from the RTL: "
                 f"{[d.get('name') for d in dropped]}",
                 "orchestration script cross-checks every named identifier against the "
                 "source symbol table and drops non-existent ones before Phase 2")
    parsed["crown_jewel_regions"] = kept
    parsed["_dropped_hallucinated_regions"] = dropped

    for r in kept:
        cl.change("1", "crown_jewel_flagged", target=str(r.get("name")),
                  after=str(r.get("why", "")), origin="llm",
                  rationale="LLM design profiling flagged this as a likely crown jewel")

    citations = util.read_json(C.ROOT / "examples" / "CITATIONS.json")
    audited_license = not os.environ.get("GREAT_DATASET_MODE") and any(
        path == C.ROOT / entry["file"] for entry in citations["designs"]
    )
    sel = selection_score(prof, parsed, audited_license=bool(audited_license))
    cl.summarise(design_purpose=parsed.get("design_purpose"),
                 security_role=parsed.get("security_role"),
                 n_crown_jewels=len(kept), selection=sel,
                 silicon_bound=bool(parsed.get("silicon_bound")),
                 standalone_compiles=comp.get("ok"),
                 llm_validation=rec)

    out_dir = C.phase_dir(1)
    profile = {"analysis_valid": bool(rec.get("parsed") and parsed.get("design_purpose")),
               "design": path.stem, "source_file": str(path.relative_to(C.ROOT)),
               "static": prof, "llm": parsed, "selection": sel,
               "standalone_compile": comp,
               "netlist": (netfeat["summary"] if netfeat else None),
               "netlist_mapped": bool(netfeat),
               "silicon_bound": bool(parsed.get("silicon_bound"))}
    util.write_json(out_dir / f"{path.stem}.profile.json", profile)
    cl.artifact("profile", out_dir / f"{path.stem}.profile.json")
    cl.write(out_dir / f"{path.stem}.changelog.json")
    return profile


def main() -> int:
    ap = util.design_args(__doc__)
    args = ap.parse_args()
    llm.start_log("phase1")
    util.banner("PHASE 1 -- Target Selection & Design Profiling")
    index = []
    for p in util.resolve_designs(args):
        util.info(f"profiling {p.name}")
        pr = profile_one(p)
        util.info(f"    purpose : {(pr['llm'].get('design_purpose') or '?')[:78]}")
        util.info(f"    selected: {pr['selection']['selected']} "
                  f"({pr['selection']['score']}/{pr['selection']['max']})  "
                  f"crown jewels: {len(pr['llm']['crown_jewel_regions'])}  "
                  f"compiles: {pr['standalone_compile'].get('ok')}")
        index.append({"design": pr["design"], "source_file": pr["source_file"],
                      "analysis_valid": pr["analysis_valid"],
                      "selected": pr["selection"]["selected"],
                      "silicon_bound": pr["silicon_bound"],
                      "purpose": pr["llm"].get("design_purpose", "")})
    util.write_json(C.phase_dir(1) / "index.json",
                    {"phase": 1, "designs": index, "llm_stats": llm.stats()})
    util.info(f"{sum(d['selected'] for d in index)}/{len(index)} designs selected")
    return int(any(not row["analysis_valid"] for row in index))


if __name__ == "__main__":
    raise SystemExit(main())
