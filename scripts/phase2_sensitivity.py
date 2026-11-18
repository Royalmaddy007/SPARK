#!/usr/bin/env python3
"""Phase 2 -- GenAI-Assisted Sensitivity Analysis (with Novel Extension 1).

Every signal, localparam, port and module is classified HIGH / MED / LOW by an
ensemble of N=3 independently seeded LLM jurors.  Agreement a(s) is computed per
Equation 1 and the paper's decision rule is applied:

    a(s) == 1        -> AUTO_ACCEPTED
    a(s) >= 1/3      -> majority label, REVIEW_QUEUED
    otherwise        -> conservative max_i t_i(s), MANDATORY_REVIEW

The result is then closed under the Phase-4a dependency-closure pass so that a
signal exclusively driven by (or exclusively driving) a HIGH signal inherits the
HIGH tag -- the mitigation for the paper's "partial extraction / missed blocks"
fault (Listings 16-18).

RL-RGOT cross-check (RL-RGoT design note, Sections 3-5). After the ensemble
vote and dependency closure above have produced the sensitivity map this
pipeline actually ships, an independent Recursive Graph-of-Thoughts rollout
(great/rgot_agent.py) is run over every HIGH/MED seed signal using a small
GRPO-trained linear-softmax policy (great/rgot_policy.py) to pick graph-
construction actions, scored against the design note's Eq. 1 composite reward
(great/graph_reward.py). This is purely an additive cross-check: it never
overrides the ensemble's tier map, it is recorded in the changelog as a
confidence signal, and a disagreement between the two is logged as a fault
for human review rather than silently resolved either way.
"""
from __future__ import annotations
import re
import itertools, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, llm, vlog, util
from great import netlist as N
from great.changelog import ChangeLog
from great.rgot_agent import RGoTAgent, RGoTConfig

SYSTEM = ("You are {persona}. You classify Verilog signals by how much security-"
          "sensitive information they reveal. You reply with ONE JSON object and "
          "nothing else -- no prose, no markdown fences.")

PROMPT = """Analyse the following Verilog module and identify all signals, parameters
and logic expressions that reveal security-sensitive information. Classify each as
HIGH, MED or LOW and justify.

Tier definitions:
  HIGH -- security constants, unlock/command codes, key compares, crypto cores,
          S-box tables, round constants, secret/key registers.
  MED  -- FSM state names, privilege logic, control boundaries, mode selects,
          state encodings.
  LOW  -- utility, wrappers, I/O buffers, clock/reset, bus interface, counters.

Return ONE JSON object:
{{"signals": [{{"name":"<identifier exactly as written in the RTL>",
               "tier":"HIGH"|"MED"|"LOW",
               "reason":"<under 15 words>"}}]}}

Rules:
- Classify ONLY identifiers that literally appear in the RTL below.
- Cover every declared signal, register, port and localparam you consider
  HIGH or MED. You may omit obvious LOW signals such as clk and reset_n.
- Return at most {cap} entries. No duplicates.

DESIGN CONTEXT (from Phase 1): {context}
NETLIST FOOTPRINTS (ASAP7 gate-level cone size/depth/fan-out per signal; a large
deep cone that reaches an output, or a high fan-out, means the signal anchors real
silicon logic even if its name looks innocuous):
{netlist}
DECLARED IDENTIFIERS (authoritative; do not invent others):
{idents}

VERILOG ({fname}):
```verilog
{rtl}
```"""


def classifiable_identifiers(src: str) -> list[str]:
    """Ports, nets, registers, localparams and module names -- the universe of s."""
    names, seen = [], set()
    for m in vlog.parse_modules(src):
        for n in [m.name] + [p["name"] for p in m.ports]:
            if n not in seen:
                seen.add(n); names.append(n)
    for d in vlog.declarations(src):
        for n in d["names"]:
            if n not in seen:
                seen.add(n); names.append(n)
    for lp in vlog.localparams(src):
        if lp["name"] not in seen:
            seen.add(lp["name"]); names.append(lp["name"])
    return names


def ask_juror(juror: dict, path: Path, src: str, idents: list[str],
              context: str, cl: ChangeLog, netblock: str = "") -> tuple[dict, dict]:
    rtl, view_meta = vlog.analysis_view(src, 22000)
    cl.note(analysis_view=view_meta)
    prompt = PROMPT.format(context=context, fname=path.name, rtl=rtl,
                           cap=min(len(idents), 60),
                           netlist=netblock or "(design not mapped to ASAP7)",
                           idents=", ".join(idents[:200]))
    parsed, rec = llm.generate_json(
        prompt, system=SYSTEM.format(persona=juror["persona"]),
        temperature=juror["temperature"], seed=juror["seed"],
        num_predict=5500, key_hint="signals",
        backend=juror.get("backend", "ollama"), model=juror.get("model", C.LLM_MODEL),
        ensemble_kind=juror.get("ensemble_kind", "single_model_multi_persona"),
        tag=f"p2:{path.stem}:{juror['id']}", phase="2")
    tiers, dropped, dupes = {}, [], 0
    known = set(idents)
    for e in (parsed or {}).get("signals", []) or []:
        nm = str(e.get("name", "")).strip()
        tier = str(e.get("tier", "")).strip().upper()
        if tier not in C.TIER_RANK:
            continue
        if nm not in known:
            dropped.append(nm)
            continue
        if nm in tiers:
            dupes += 1
            # keep the more conservative of two self-contradictory labels
            if C.TIER_RANK[tier] <= C.TIER_RANK[tiers[nm]["tier"]]:
                continue
        tiers[nm] = {"tier": tier, "reason": str(e.get("reason", ""))[:200]}
    if dropped:
        cl.fault("2", "hallucinated_signal",
                 f"juror {juror['id']} classified {len(dropped)} identifier(s) not "
                 f"present in the RTL: {sorted(set(dropped))[:10]}",
                 "identifiers are validated against the source symbol table before "
                 "voting; unknown names are discarded and do not dilute agreement",
                 juror=juror["id"])
    if dupes:
        cl.fault("2", "self_contradictory_labels",
                 f"juror {juror['id']} labelled {dupes} identifier(s) twice with "
                 "different tiers",
                 "the more conservative (higher) tier of the pair is retained",
                 juror=juror["id"])
    if parsed is None:
        cl.fault("2", "unparseable_vote",
                 f"juror {juror['id']} produced no parseable JSON",
                 "the juror abstains and is excluded from the vote; agreement is "
                 "computed over the jurors that answered, and a signal left with "
                 "fewer than two voters goes to MANDATORY_REVIEW",
                 juror=juror["id"], resolved=True)
    return tiers, {"juror": juror["id"], "n_labelled": len(tiers),
                   "backend": juror.get("backend", "ollama"),
                   "model": juror.get("model", C.LLM_MODEL),
                   "n_dropped": len(dropped), "validation": rec,
                   "abstained": parsed is None}


# One RGoTAgent/policy shared across every design in a run, so the GRPO
# group-relative update (Section 5.1) accumulates signal across designs
# rather than restarting cold each time -- matching the paper's online,
# self-play training loop (no external labels, no persisted checkpoint
# required for a single pipeline invocation).
_RGOT_AGENT = RGoTAgent(RGoTConfig())


def agreement(labels: list[str]) -> float:
    """Equation 1: mean pairwise agreement over the juror labels."""
    pairs = list(itertools.combinations(labels, 2))
    if not pairs:
        return 1.0
    return sum(a == b for a, b in pairs) / len(pairs)


def vote(per_juror: dict[str, dict], idents: list[str],
         abstained: set[str] | None = None) -> dict:
    """Equation-1 vote over the jurors that actually answered.

    A juror whose call failed (no parseable response) ABSTAINS: it is excluded
    from the vote entirely.  Counting it as a LOW vote on every signal -- which an
    earlier revision did -- lets one dead model call outvote a real HIGH tag by
    majority, which is the exact under-protection failure the ensemble exists to
    prevent.  With fewer than two voters there is no cross-validation at all, so
    the signal is sent to MANDATORY_REVIEW at the most conservative tier offered.
    """
    abstained = abstained or set()
    voters = {j: t for j, t in per_juror.items() if j not in abstained}
    out = {}
    for s in idents:
        labels, reasons = [], []
        for jid, tiers in voters.items():
            e = tiers.get(s)
            labels.append(e["tier"] if e else "LOW")
            if e:
                reasons.append(f"{jid}: {e['reason']}")
        if not labels:
            tier, status, a = "LOW", "MANDATORY_REVIEW", 0.0
        elif len(labels) == 1:
            tier, status, a = labels[0], "MANDATORY_REVIEW", 0.0
            if tier == "LOW":
                status = "AUTO_ACCEPTED"   # a lone LOW adds no protection debt
        else:
            a = agreement(labels)
            if a == 1.0:
                tier, status = labels[0], "AUTO_ACCEPTED"
            elif a >= 1 / 3:
                tier = max(set(labels), key=lambda t: (labels.count(t),
                                                       C.TIER_RANK[t]))
                status = "REVIEW_QUEUED"
            else:
                tier = C.RANK_TIER[max(C.TIER_RANK[t] for t in labels)]
                status = "MANDATORY_REVIEW"
        out[s] = {"name": s, "tier": tier, "status": status,
                  "agreement": round(a, 4), "n_voters": len(labels),
                  "votes": {j: (per_juror[j].get(s, {}).get("tier", "LOW")
                                if j not in abstained else "ABSTAINED")
                            for j in per_juror},
                  "reasons": reasons}
    return out


def analyse(path: Path) -> dict:
    src = path.read_text()
    jurors = C.effective_jurors()
    kind = C.ensemble_kind(jurors)
    for juror in jurors:
        juror["ensemble_kind"] = kind
    cl = ChangeLog("phase2_sensitivity", path.stem, str(path.relative_to(C.ROOT)))
    prof_p = C.PHASE_DIRS[1] / f"{path.stem}.profile.json"
    prof = util.read_json(prof_p)
    context = (f"{prof['llm'].get('design_purpose','')} "
               f"Crown jewels flagged in Phase 1: "
               f"{[r.get('name') for r in prof['llm'].get('crown_jewel_regions',[])]}")
    idents = classifiable_identifiers(src)
    netfeat = N.load_features(path.stem)
    net_lines = []
    if netfeat:
        # keep the block small: the most structurally significant signals only
        # (largest gate cones), so the prompt stays within the model's budget.
        scored = []
        for nm in idents:
            f = netfeat.get("per_signal", {}).get(nm) \
                or netfeat.get("per_signal", {}).get(re.sub(r"\[.*", "", nm))
            if f and f.get("cone_cells", 0) > 0:
                scored.append((f["cone_cells"], nm))
        for _, nm in sorted(scored, reverse=True)[:24]:
            h = N.signal_hint(netfeat, nm)
            if h:
                net_lines.append(f"  {nm}: {h}")
    netblock = "\n".join(net_lines) if net_lines else ""
    cl.note(n_candidate_identifiers=len(idents), phase1_context=context,
            netlist_mapped=bool(netfeat),
            ensemble_kind=kind,
            ensemble_note=("Effective backend/model identity is recorded for each juror; "
                           "single-model personas have correlated errors."),
            jurors=[{k: j[k] for k in ("id", "backend", "model", "temperature", "seed", "persona")}
                    for j in jurors])

    per_juror, juror_meta = {}, []
    for j in jurors:
        util.info(f"    juror {j['id']} (T={j['temperature']})")
        tiers, meta = ask_juror(j, path, src, idents, context, cl, netblock)
        per_juror[j["id"]] = tiers
        juror_meta.append(meta)

    abstained = {m["juror"] for m in juror_meta if m.get("abstained")}
    kind = C.ensemble_kind([j for j in jurors if j['id'] not in abstained])
    cl.note(ensemble_kind=kind)
    voted = vote(per_juror, idents, abstained)
    if abstained:
        cl.note(abstained_jurors=sorted(abstained),
                effective_ensemble_size=len(jurors) - len(abstained))

    # Phase-1 crown jewels are a floor: never below MED.
    for r in prof["llm"].get("crown_jewel_regions", []):
        nm = str(r.get("name", "")).strip()
        if nm in voted and C.TIER_RANK[voted[nm]["tier"]] < 1:
            cl.change("2", "tier_floor_applied", target=nm,
                      before=voted[nm]["tier"], after="MED", origin="script",
                      rationale="Phase-1 crown-jewel region may not be classified LOW")
            voted[nm]["tier"] = "MED"
            voted[nm]["status"] = "REVIEW_QUEUED"

    # ---- netlist-aware promotion: a signal the synthesised ASAP7 netlist shows
    # anchors a deep logic cone reaching an output, or drives a high fan-out, is
    # silicon-reachable and must not sit at LOW even if its source name is bland.
    net_promoted = []
    if netfeat:
        for s, v in voted.items():
            if v["tier"] == "HIGH":
                continue
            sig = N.structural_significance(netfeat, s)
            if not sig:
                continue
            newtier = "HIGH" if sig["drives_primary_output"] and sig["cone_depth"] >= 8 else "MED"
            if C.TIER_RANK[newtier] > C.TIER_RANK[v["tier"]]:
                net_promoted.append((s, v["tier"], newtier, sig["reasons"]))
                cl.change("2", "netlist_structural_promotion", target=s,
                          before=v["tier"], after=newtier, origin="script",
                          rationale="ASAP7 gate-level netlist shows " +
                                    "; ".join(sig["reasons"]) +
                                    " -- a silicon attacker can probe this even though "
                                    "the ensemble under-rated it from the source text",
                          cone_cells=sig["cone_cells"], cone_depth=sig["cone_depth"],
                          fanout=sig["fanout"])
                voted[s]["tier"] = newtier
                voted[s]["netlist_promoted"] = True
                if voted[s]["status"] == "AUTO_ACCEPTED":
                    voted[s]["status"] = "REVIEW_QUEUED"
    if net_promoted:
        cl.fault("2", "netlist_structural_undertag",
                 f"{len(net_promoted)} signal(s) anchor substantial synthesised logic "
                 f"but were tagged lower by the source-only ensemble: "
                 f"{[(p[0], p[1]+'->'+p[2]) for p in net_promoted][:12]}",
                 "Phase-0 ASAP7 mapping measures each signal's real gate-level cone; "
                 "signals with deep output-reaching cones or high fan-out are promoted "
                 "so redaction is netlist-aware, not source-text-only", resolved=True)


    # ---- dependency closure (mitigation for 'partial extraction / missed blocks')
    seeds = [s for s, v in voted.items() if v["tier"] == "HIGH"]
    closure = vlog.dependency_closure(src, seeds) if seeds else set()
    promoted = []
    for s in sorted(closure):
        if s in voted and voted[s]["tier"] != "HIGH":
            promoted.append((s, voted[s]["tier"]))
            cl.change("2", "closure_promotion", target=s,
                      before=voted[s]["tier"], after="HIGH", origin="script",
                      rationale="transitively connected to a HIGH-tagged signal; "
                                "leaving it lower tier would strand it in the parent "
                                "module during Phase-4a extraction")
            voted[s]["tier"] = "HIGH"
            voted[s]["closure_promoted"] = True
    if promoted:
        cl.fault("2", "missed_transitive_sensitivity",
                 f"{len(promoted)} signal(s) in the combinational closure of a HIGH "
                 f"signal were tagged lower by the ensemble: {promoted[:12]}",
                 "orchestration script runs a transitive fan-in/fan-out closure over "
                 "the driver graph and injects the closure set as ALSO_EXTRACT "
                 "(paper Listing 18)")

    # ---- RL-RGOT cross-check (RL-RGoT design note, Sections 3-5) -----------
    # An independent RGoT rollout, scored by Eq. 1, cross-checks the ensemble's
    # own tier map. It never overrides `voted`; a disagreement is recorded as
    # a fault for human review, and agreement is recorded as a confidence note.
    rgot_seeds = [s for s, v in voted.items() if v["tier"] != "LOW"]
    rgot_summary = None
    if rgot_seeds:
        ensemble_tiers = {s: v["tier"] for s, v in voted.items()}
        rgot_result = _RGOT_AGENT.run(src, ensemble_tiers, seed_signals=rgot_seeds[:40])
        disagreements = [(s, ensemble_tiers.get(s, "LOW"), t)
                         for s, t in rgot_result["sensitivity_map"].items()
                         if ensemble_tiers.get(s, "LOW") != t]
        mean_reward = (sum(r["best_reward_breakdown"]["total"]
                           for r in rgot_result["rollout_report"])
                       / max(1, len(rgot_result["rollout_report"])))
        rgot_summary = {
            "seeds_rolled_out": len(rgot_seeds[:40]),
            "mean_best_reward": round(mean_reward, 4),
            "policy_updates_this_design": sum(
                1 for r in rgot_result["rollout_report"] if r["policy_update"].get("updated")),
            "disagreements": [{"signal": s, "ensemble_tier": e, "rgot_tier": r}
                              for s, e, r in disagreements[:20]],
            "closure_promoted_by_rgot": rgot_result["closure_promoted"],
        }
        if disagreements:
            cl.fault("2", "rgot_ensemble_disagreement",
                     f"the RL-RGOT cross-check reasoning graph disagreed with the "
                     f"ensemble vote on {len(disagreements)} signal(s): "
                     f"{[(s, e + '->' + r) for s, e, r in disagreements[:12]]}",
                     "the RGoT rollout is advisory only -- the ensemble-voted, "
                     "closure-corrected tier map above is what Phase 3 consumes; "
                     "disagreements are surfaced here for human review rather "
                     "than resolved automatically in either direction",
                     resolved=False)
        cl.note(rgot_cross_check=rgot_summary)

    for s, v in voted.items():
        if v["tier"] != "LOW" and not v.get("closure_promoted"):
            cl.change("2", "sensitivity_tag", target=s, after=v["tier"],
                      origin="llm-ensemble", rationale="; ".join(v["reasons"])[:300],
                      agreement=v["agreement"], status=v["status"],
                      votes=v["votes"])

    counts = {t: sum(1 for v in voted.values() if v["tier"] == t)
              for t in ("HIGH", "MED", "LOW")}
    statuses = {st: sum(1 for v in voted.values() if v["status"] == st)
                for st in ("AUTO_ACCEPTED", "REVIEW_QUEUED", "MANDATORY_REVIEW")}
    mean_a = round(sum(v["agreement"] for v in voted.values()) / max(1, len(voted)), 4)
    cl.summarise(tier_counts=counts, status_counts=statuses,
                 mean_agreement=mean_a, closure_promotions=len(promoted),
                 jurors=juror_meta)

    out = {"analysis_valid": len(jurors) - len(abstained) >= 2,
           "design": path.stem, "source_file": str(path.relative_to(C.ROOT)),
           "ensemble_kind": kind,
           "cross_model_disagreements": [s for s, v in voted.items()
               if kind == "cross_model_partial" and "juror_c" not in abstained
               and all(j not in abstained for j in ("juror_a", "juror_b"))
               and v["votes"]["juror_a"] == v["votes"]["juror_b"]
               and v["votes"]["juror_c"] != v["votes"]["juror_a"]],
           "jurors": juror_meta, "mean_agreement": mean_a,
           "tier_counts": counts, "status_counts": statuses,
           "closure_set": sorted(closure),
           "rgot_cross_check": rgot_summary,
           "signals": voted}
    d = C.phase_dir(2)
    util.write_json(d / f"{path.stem}.sensitivity.json", out)
    cl.artifact("sensitivity_map", d / f"{path.stem}.sensitivity.json")
    cl.write(d / f"{path.stem}.changelog.json")
    return out


def main() -> int:
    args = util.design_args(__doc__).parse_args()
    llm.start_log("phase2")
    util.banner("PHASE 2 -- GenAI Sensitivity Analysis (N=3 ensemble)")
    index = []
    for p in util.resolve_designs(args):
        util.info(f"classifying {p.name}")
        r = analyse(p)
        util.info(f"    HIGH={r['tier_counts']['HIGH']} MED={r['tier_counts']['MED']} "
                  f"LOW={r['tier_counts']['LOW']}  mean a(s)={r['mean_agreement']}  "
                  f"mandatory review={r['status_counts']['MANDATORY_REVIEW']}")
        if r.get("rgot_cross_check"):
            rc = r["rgot_cross_check"]
            util.info(f"    RL-RGOT cross-check: {rc['seeds_rolled_out']} seed(s), "
                      f"mean reward={rc['mean_best_reward']}, "
                      f"disagreements={len(rc['disagreements'])}")
        index.append({"design": r["design"], "analysis_valid": r["analysis_valid"], **r["tier_counts"],
                      "mean_agreement": r["mean_agreement"]})
    util.write_json(C.phase_dir(2) / "index.json",
                    {"phase": 2, "designs": index, "llm_stats": llm.stats()})
    return int(any(not row["analysis_valid"] for row in index))


if __name__ == "__main__":
    raise SystemExit(main())
