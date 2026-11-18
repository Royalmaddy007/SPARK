#!/usr/bin/env python3
"""Phase 6B -- Adversarial-Feedback-Driven Escalation Loop (Algorithm 1).

    for r = 1 .. R_max:
        run Phase 6, obtain I_leak(s) and the red team's reasoning trace
        S_acc  = { s : I_leak(s) <  tau_low  }      accepted
        S_esc  = { s : tau_low <= I_leak(s) < tau_high }  escalated
        S_fail = { s : I_leak(s) >= tau_high }      mandatory human review
        if S_fail non-empty: flag for human review
        if S_esc empty: return R_{r-1}
        R_r = re-run Phase 4 for the escalated sites only, one tier up the
              Table III ladder, annotated with the red team's own reasoning
        re-run the FULL Phase 5 suite before accepting R_r as the new baseline

The two guardrails from the paper are enforced literally: an escalated variant
that fails Phase 5 is rejected regardless of how much it improved leakage, and
the loop is bounded by R_max and by the hard-failure bucket.
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, llm, util
from great.changelog import ChangeLog

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase4_transform as P4
import phase5_verify as P5
import phase6_leakage as P6


def next_tier(t: str) -> str:
    i = C.BUDGET_ORDER.index(t)
    return C.BUDGET_ORDER[min(i + 1, len(C.BUDGET_ORDER) - 1)]


def escalate(path: Path) -> dict:
    design = path.stem
    cl = ChangeLog("phase6b_escalation", design, str(path.relative_to(C.ROOT)))
    strat = util.read_json(C.PHASE_DIRS[3] / f"{design}.strategy.json")

    baseline_leak = util.read_json(C.PHASE_DIRS[6] / f"{design}.leakage.json")
    baseline_ver = util.read_json(C.PHASE_DIRS[5] / f"{design}.verification.json")
    history = [{"round": 0, "tier": strat["design_budget_tier"],
                "L": baseline_leak["L_leakage_fraction"],
                "recovery": baseline_leak["binary_score"]["constant_recovery_accuracy"],
                "buckets": {k: len(v) for k, v in baseline_leak["buckets"].items()},
                "verdict": baseline_ver["verdict"], "accepted": True,
                "artifact": baseline_leak["redacted_rtl"]}]
    cl.note(tau_low=C.TAU_LOW, tau_high=C.TAU_HIGH, r_max=C.R_MAX,
            baseline=history[0])

    accepted = history[0]
    leak, tier = baseline_leak, strat["design_budget_tier"]
    human_review: list[str] = []
    stop = "converged"

    for r in range(1, C.R_MAX + 1):
        esc = list(leak["buckets"]["escalated"])
        fail = list(leak["buckets"]["hard_failure"])

        # The KL buckets only ever see *literal constants*.  A design can leak
        # badly without leaking a constant -- the red team naming the module's
        # real security role is precisely that case, and the paper lists it as a
        # separate success criterion.  Treat a failed criterion as an escalation
        # signal in its own right, otherwise a design that flunks Phase 6
        # outright would exit this loop having done nothing.
        unmet = [k for k, v in leak.get("success_criteria", {}).items() if not v]
        if unmet and not esc:
            esc = [f"criterion:{k}" for k in unmet]
            cl.change("6b", "criterion_escalation", target=", ".join(unmet),
                      after=f"{len(unmet)} unmet Phase-6 success criterion/criteria "
                            "escalated", origin="script",
                      rationale="no individual constant fell in the escalated KL "
                                "bucket, but the red team still met or beat a stated "
                                "success threshold at the design level (typically by "
                                "identifying the module's security role from surviving "
                                "structure rather than from any single constant)",
                      round=r, red_team_guess=(leak.get("red_team_output", {}) or {})
                      .get("module_purpose", ""))
        if fail:
            human_review += fail
            cl.change("6b", "mandatory_human_review", target=", ".join(fail),
                      after=f"{len(fail)} site(s) flagged", origin="script",
                      rationale=f"I_leak >= tau_high ({C.TAU_HIGH} bits): a large "
                                "single-pass recovery usually means the secret is also "
                                "derivable from an un-redacted neighbour, which more "
                                "transformation intensity will not fix")
        if not esc:
            cl.change("6b", "loop_terminated", target=f"round {r}",
                      after="no site in the escalated bucket", origin="script",
                      rationale="Algorithm 1 line 10: every remaining site is in the "
                                "accepted bucket, so escalation would spend budget for "
                                "no measurable gain")
            stop = "no_escalated_sites"
            break

        new_tier = next_tier(tier)
        extra = sorted(set(C.BUDGET_TRANSFORMS[new_tier]) -
                       set(strat["design_transformations"]))
        if new_tier == tier and "4j" in strat["design_transformations"]:
            extra = ["4j"]      # already at B2: regenerate a fresh decoy in place
        reasoning = (leak.get("red_team_output", {}) or {}).get("reasoning", [])[:6]

        cl.change("6b", "escalation", target=", ".join(esc),
                  before=f"tier {tier}, steps {strat['design_transformations']}",
                  after=f"tier {new_tier}, additional steps {extra}", origin="script",
                  rationale="sites in [tau_low, tau_high) are returned to Phase 4 one "
                            "tier up the Table III ladder, annotated with the specific "
                            "red-team reasoning that partially recovered them",
                  red_team_reasoning=reasoning, round=r)

        esc_spec = {"round": r, "tier": new_tier, "sites": esc,
                    "additional_steps": extra, "red_team_reasoning": reasoning}
        util.info(f"    round {r}: {tier} -> {new_tier}, +{extra}, "
                  f"{len(esc)} escalated site(s)")
        P4.transform(path, escalation=esc_spec)
        ver = P5.verify(path, round_id=r)

        # Guardrail 1: an escalation that breaks equivalence is rejected outright.
        if ver["verdict"] != "PASS":
            cl.fault("6b", "escalation_broke_equivalence",
                     f"round {r} variant failed Phase 5 ({ver['verdict']}): "
                     f"syntax={ver['syntax']['ok']} iface={ver['interface']['ok']} "
                     f"sim={ver['simulation'].get('passed')} "
                     f"formal={ver['formal'].get('proved')}",
                     "variant rejected and the previous baseline retained -- an "
                     "escalation is rejected exactly as any other Phase-4 fault "
                     "would be, regardless of whether it improved leakage",
                     resolved=True, round=r)
            history.append({"round": r, "tier": new_tier, "verdict": ver["verdict"],
                            "accepted": False, "reason": "failed phase 5"})
            stop = "escalation_rejected"
            break

        new_leak = P6.analyse(path, round_id=r)
        entry = {"round": r, "tier": new_tier,
                 "L": new_leak["L_leakage_fraction"],
                 "recovery": new_leak["binary_score"]["constant_recovery_accuracy"],
                 "buckets": {k: len(v) for k, v in new_leak["buckets"].items()},
                 "verdict": ver["verdict"], "accepted": True,
                 "artifact": new_leak["redacted_rtl"],
                 "additional_steps": extra}
        history.append(entry)
        cl.change("6b", "round_accepted", target=f"round {r}",
                  before=f"L={leak['L_leakage_fraction']}",
                  after=f"L={new_leak['L_leakage_fraction']}", origin="script",
                  rationale="variant passed the full Phase-5 suite and becomes the new "
                            "baseline R_r")
        accepted, leak, tier = entry, new_leak, new_tier
        if r == C.R_MAX:
            stop = "r_max_reached"

    result = {"design": design, "history": history,
              "final_round": accepted["round"], "final_tier": accepted["tier"],
              "final_L": accepted.get("L"), "stop_reason": stop,
              "human_review_sites": sorted(set(human_review)),
              "delivered_artifact": accepted.get("artifact"),
              "pareto": [{"tier": h["tier"], "round": h["round"], "L": h.get("L")}
                         for h in history if h.get("accepted")]}
    d = C.phase_dir("6b")
    util.write_json(d / f"{design}.escalation.json", result)
    cl.summarise(rounds_run=len(history) - 1, stop_reason=stop,
                 final_L=accepted.get("L"), final_tier=accepted["tier"],
                 human_review_sites=result["human_review_sites"])
    cl.artifact("escalation", d / f"{design}.escalation.json")
    cl.write(d / f"{design}.changelog.json")
    return result


def main() -> int:
    args = util.design_args(__doc__).parse_args()
    llm.start_log("phase6b")
    util.banner(f"PHASE 6B -- Adversarial-Feedback Escalation (R_max={C.R_MAX})")
    index = []
    for p in util.resolve_designs(args):
        util.info(f"escalating {p.name}")
        r = escalate(p)
        util.info(f"    rounds={r['final_round']}  tier={r['final_tier']}  "
                  f"L={r['final_L']}  stop={r['stop_reason']}  "
                  f"human_review={len(r['human_review_sites'])}")
        index.append({"design": r["design"], "rounds": r["final_round"],
                      "final_tier": r["final_tier"], "final_L": r["final_L"],
                      "stop_reason": r["stop_reason"]})
    util.write_json(C.phase_dir("6b") / "index.json",
                    {"phase": "6b", "designs": index, "llm_stats": llm.stats()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
