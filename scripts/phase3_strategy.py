#!/usr/bin/env python3
"""Phase 3 -- Redaction Strategy & Budget Tier Definition (with Novel Extension 2).

Two jobs:

1.  Assign each HIGH/MED signal an attacker budget tier B0/B1/B2 (Novel
    Extension 2 -- Differential Redaction Budgets per Threat Model).  The LLM
    proposes the tier from the signal's exposure at the design boundary; the
    orchestration script enforces hard floors so that no genuinely reachable
    secret can be assigned a weak budget.

2.  Expand each budget tier into the concrete transformation set of Table III
    and emit the annotated RTL that Phase 4 consumes -- every construct that
    touches a HIGH signal carries a `// @SENSITIVITY: HIGH` marker, and the
    dependency-closure set is emitted as an explicit ALSO_EXTRACT list.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, llm, vlog, util
from great.changelog import ChangeLog

SYSTEM = ("You are a hardware IP redaction strategist. You reply with ONE JSON "
          "object and nothing else.")

PROMPT = """Assign an attacker-budget tier to each sensitive signal of this Verilog design.

Budget tiers describe how much effort an attacker will spend on THAT SIGNAL:
  B0 -- single-query static attacker: one LLM prompt, no tools. Use for internal
        signals that are hard to reach and cheap to guess wrong.
  B1 -- multi-turn analyst: several dependent queries, cross-referencing,
        chain-of-thought, but no simulation. Use for signals reachable through a
        few hops of reasoning from the port list.
  B2 -- full agentic attacker: simulation, synthesis, waveform inspection. Use
        for signals a testbench or grading harness will directly exercise -- i.e.
        anything observable at or one hop from the top-level ports.

Return ONE JSON object:
{{"assignments":[{{"name":"<identifier>","budget":"B0"|"B1"|"B2",
                  "reason":"<under 15 words>"}}],
  "strategy_summary":"<under 40 words: the overall redaction approach>"}}

Rules:
- Cover every signal in SENSITIVE SIGNALS below, and nothing else.
- Signals that are top-level ports, or drive/are driven by top-level ports,
  should be B2. Deeply internal constants can be B0.

DESIGN: {fname} -- {purpose}
TOP-LEVEL PORTS: {ports}
SENSITIVE SIGNALS (tier from Phase 2):
{sigs}"""


def hard_floor(name: str, tier: str, port_names: set[str],
               boundary: set[str], silicon_bound: bool) -> str | None:
    """Non-negotiable minimum budget, enforced by the script, not the model."""
    if name in port_names:
        return "B2"
    if name in boundary:
        return "B1"
    if tier == "HIGH" and silicon_bound:
        return "B1"
    return None


def annotate(src: str, high: set[str], med: set[str], cl: ChangeLog) -> str:
    """Insert `// @SENSITIVITY: <tier>` above every construct touching a tagged signal.

    MED constructs are annotated as well as HIGH.  Phase 4a extracts on HIGH
    only, but Steps 4c/4d/4h are selected per signal by budget tier, and a design
    whose ensemble produced no HIGH signals at all would otherwise receive no
    constant masking whatsoever.

    Tag placement validation (RL-RGOT design note Section 2.2): before any
    annotation is written, every tagged name is checked against the real
    source identifier set so a tag can never land on a reserved keyword or an
    identifier that was never actually declared in this RTL.
    """
    problems = vlog.tag_placement_scan(src, high | med)
    if problems:
        cl.fault("3", "tag_placement_invalid",
                 f"{len(problems)} tagged name(s) failed placement validation: "
                 f"{problems[:10]}",
                 "offending names are dropped from the annotation set before "
                 "any `// @SENSITIVITY` marker is written, so a tag can never "
                 "attach to a keyword or a name absent from the RTL")
        bad = set()
        for p in problems:
            m = re.search(r"'([^']+)'", p)
            if m:
                bad.add(m.group(1))
        high, med = high - bad, med - bad
    cs = vlog.code_only(src)
    lines = src.splitlines()
    code_lines = cs.splitlines()
    marked: dict[int, str] = {}
    for i, cline in enumerate(code_lines):
        toks = {t for t in vlog.IDENT.findall(cline) if t not in vlog.KEYWORDS}
        if toks & high:
            tier = "HIGH"
        elif toks & med:
            tier = "MED"
        else:
            continue
        # only annotate declaration / assignment / case-item lines, not `end`
        if not re.search(r"[=;(]|\bcase\b|\balways\b|\bmodule\b", cline):
            continue
        marked[i] = tier
    out = []
    for i, line in enumerate(lines):
        if i in marked:
            indent = re.match(r"[ \t]*", line).group(0)
            out.append(f"{indent}// @SENSITIVITY: {marked[i]}")
        out.append(line)
    n_high = sum(1 for t in marked.values() if t == "HIGH")
    cl.change("3", "sensitivity_annotation", target=f"{len(marked)} source lines",
              after=f"{n_high} HIGH and {len(marked) - n_high} MED markers inserted",
              origin="script",
              rationale="Phase 4a extracts verbatim on these markers; annotating "
                        "constructs rather than signals gives the model an "
                        "unambiguous, complete set of nodes to move")
    return "\n".join(out) + "\n"


def strategise(path: Path) -> dict:
    src = path.read_text()
    cl = ChangeLog("phase3_strategy", path.stem, str(path.relative_to(C.ROOT)))
    sens = util.read_json(C.PHASE_DIRS[2] / f"{path.stem}.sensitivity.json")
    prof = util.read_json(C.PHASE_DIRS[1] / f"{path.stem}.profile.json")

    mods = vlog.parse_modules(src)
    top = mods[0]
    port_names = {p["name"] for p in top.ports}
    graph = vlog.driver_graph(src)
    boundary = set()
    for dst, srcs in graph.items():
        if dst in port_names:
            boundary |= srcs
        if srcs & port_names:
            boundary.add(dst)

    sensitive = {n: v for n, v in sens["signals"].items() if v["tier"] != "LOW"}
    if not sensitive:
        util.warn("no HIGH/MED signals -- nothing to redact")

    sig_lines = "\n".join(f"  {n} [{v['tier']}] -- {(v['reasons'] or [''])[0][:70]}"
                          for n, v in list(sensitive.items())[:80])
    parsed, rec = llm.generate_json(
        PROMPT.format(fname=path.name,
                      purpose=prof["llm"].get("design_purpose", "")[:160],
                      ports=", ".join(sorted(port_names)), sigs=sig_lines),
        system=SYSTEM, temperature=0.1, seed=5, num_predict=3500, key_hint="assignments",
        tag=f"p3:{path.stem}", phase="3")
    proposed = {}
    for a in (parsed or {}).get("assignments", []) or []:
        nm, b = str(a.get("name", "")).strip(), str(a.get("budget", "")).strip().upper()
        if nm in sensitive and b in C.BUDGET_TRANSFORMS:
            proposed[nm] = {"budget": b, "reason": str(a.get("reason", ""))[:160]}
    if parsed is None:
        cl.fault("3", "unparseable_budget_assignment",
                 "LLM produced no parseable budget assignment",
                 "every sensitive signal falls back to its script-computed hard floor, "
                 "or B1 for HIGH / B0 for MED when no floor applies")

    silicon = bool(prof.get("silicon_bound"))
    plan, escalated, missing = {}, 0, 0
    for n, v in sensitive.items():
        p = proposed.get(n)
        if p is None:
            missing += 1
            b = "B1" if v["tier"] == "HIGH" else "B0"
            reason, origin = "no LLM assignment; script default by tier", "script"
        else:
            b, reason, origin = p["budget"], p["reason"], "llm"
        floor = hard_floor(n, v["tier"], port_names, boundary, silicon)
        if floor and C.BUDGET_ORDER.index(floor) > C.BUDGET_ORDER.index(b):
            cl.change("3", "budget_floor_enforced", target=n, before=b, after=floor,
                      origin="script",
                      rationale=("signal is a top-level port" if n in port_names else
                                 "signal is one hop from a top-level port" if n in boundary
                                 else "HIGH-tier signal in a silicon-bound design") +
                                "; a weaker budget would under-protect it")
            b, escalated = floor, escalated + 1
            origin = "script-floor"
        plan[n] = {"name": n, "tier": v["tier"], "budget": b,
                   "transformations": C.BUDGET_TRANSFORMS[b],
                   "reason": reason, "assigned_by": origin,
                   "is_port": n in port_names, "is_boundary": n in boundary}
        cl.change("3", "budget_assignment", target=n, before=v["tier"], after=b,
                  origin=origin, rationale=reason,
                  transformations=C.BUDGET_TRANSFORMS[b])
    if missing:
        cl.fault("3", "incomplete_budget_coverage",
                 f"LLM omitted {missing} of {len(sensitive)} sensitive signals",
                 "script fills the gap deterministically (HIGH->B1, MED->B0) and then "
                 "applies the hard floors, so no signal is ever left unassigned")

    high = {n for n, v in sensitive.items() if v["tier"] == "HIGH"}
    med = {n for n, v in sensitive.items() if v["tier"] == "MED"}

    # Under-tagging guard.  The paper calls an under-tagged HIGH signal "the most
    # expensive class of error" because it is never transformed and leaks in the
    # clear.  A design that Phase 1 profiled as carrying crypto constants and
    # named crown-jewel regions, but for which the ensemble produced no HIGH
    # signal at all, is exactly that failure -- so the crown jewels are promoted
    # and the disagreement is recorded rather than silently accepted.
    if not high and prof["llm"].get("crown_jewel_regions"):
        promoted = []
        for r in prof["llm"]["crown_jewel_regions"]:
            nm = str(r.get("name", "")).strip()
            if nm in sensitive:
                sensitive[nm]["tier"] = "HIGH"
                promoted.append(nm)
        if promoted:
            high = set(promoted)
            med -= high
            cl.fault("3", "ensemble_under_tagging",
                     f"Phase 2 returned zero HIGH signals for a design Phase 1 "
                     f"profiled as security-critical; promoting its crown-jewel "
                     f"regions {promoted} to HIGH",
                     "an under-tagged HIGH signal is never transformed and leaks in "
                     "the clear, which the paper identifies as the most expensive "
                     "single error in the pipeline; the promotion is recorded so a "
                     "human reviewer can see the ensemble disagreed with Phase 1")
            for nm in promoted:
                cl.change("3", "under_tag_promotion", target=nm,
                          before=plan[nm]["tier"] if nm in plan else "MED/LOW",
                          after="HIGH", origin="script",
                          rationale="Phase-1 crown jewel with no HIGH tag anywhere "
                                    "in the ensemble output")
                if nm in plan:
                    # keep the emitted plan consistent with the tier actually used
                    plan[nm]["tier"] = "HIGH"
    annotated = annotate(src, high, med, cl)
    d = C.phase_dir(3)
    ann_p = d / f"{path.stem}.annotated.v"
    ann_p.write_text(annotated)

    # The union of every signal's transformation set drives Phase 4 for the design;
    # per-signal sets remain in the plan so Phase 4 can gate site by site.
    design_budget = max((p["budget"] for p in plan.values()),
                        key=lambda b: C.BUDGET_ORDER.index(b), default="B0")
    steps = sorted({s for p in plan.values() for s in p["transformations"]},
                   key=lambda s: (s[1], s))

    out = {"design": path.stem, "source_file": str(path.relative_to(C.ROOT)),
           "annotated_rtl": str(ann_p.relative_to(C.ROOT)),
           "top_module": top.name, "top_ports": [p["name"] for p in top.ports],
           "silicon_bound": silicon,
           "strategy_summary": (parsed or {}).get("strategy_summary", ""),
           "design_budget_tier": design_budget,
           "design_transformations": steps,
           "also_extract_closure": sens["closure_set"],
           "budget_counts": {b: sum(1 for p in plan.values() if p["budget"] == b)
                             for b in C.BUDGET_ORDER},
           "plan": plan}
    util.write_json(d / f"{path.stem}.strategy.json", out)
    cl.summarise(design_budget_tier=design_budget, n_sensitive=len(sensitive),
                 budget_counts=out["budget_counts"], floors_enforced=escalated,
                 transformations=steps, llm_validation=rec)
    cl.artifact("strategy", d / f"{path.stem}.strategy.json")
    cl.artifact("annotated_rtl", ann_p)
    cl.write(d / f"{path.stem}.changelog.json")
    return out


def main() -> int:
    args = util.design_args(__doc__).parse_args()
    llm.start_log("phase3")
    util.banner("PHASE 3 -- Redaction Strategy & Budget Tier Definition")
    index = []
    for p in util.resolve_designs(args):
        util.info(f"planning {p.name}")
        r = strategise(p)
        util.info(f"    budget {r['design_budget_tier']}  {r['budget_counts']}  "
                  f"steps={','.join(r['design_transformations'])}")
        index.append({"design": r["design"], "budget": r["design_budget_tier"],
                      "counts": r["budget_counts"]})
    util.write_json(C.phase_dir(3) / "index.json",
                    {"phase": 3, "designs": index, "llm_stats": llm.stats()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
