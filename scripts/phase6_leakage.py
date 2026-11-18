#!/usr/bin/env python3
"""Phase 6 -- Leakage Analysis & Reporting (with Novel Extension 6).

A red-team LLM sees ONLY the redacted RTL -- no manifests, no original, no
Phase 1-4 context.  It is asked to (a) name the module's purpose, (b) recover the
secret constants, (c) infer the comparison conditions, (d) reconstruct the FSM,
(e) explain every port and (f) say whether the gate-level structures implement
arithmetic.  Its answers are then scored against the truth held in the manifests.

Two scores are produced:

  * the paper's binary recovery accuracy (fraction of HIGH secrets exactly
    recovered, and the module-role identification rate), and

  * Novel Extension 6, the information-theoretic score: the red team also emits a
    ranked posterior over candidate values per secret, and leakage is

        I_leak(s) = D_KL(P_red(s) || U(s))   in bits, 0 <= I_leak <= W

    with L = sum_s I_leak(s) / sum_s W_s reported as a fraction.
"""
from __future__ import annotations
import hashlib, json, math, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, llm, vlog, util, transforms as T
from great.changelog import ChangeLog

RED_SYS = ("You are an offensive hardware reverse engineer. You are given a Verilog "
           "file with no documentation and no context. Recover as much of the "
           "original design intent as you can. You reply with ONE JSON object only.")

RED_PROMPT = """Reverse engineer this Verilog module. You have no other context.

Return ONE JSON object:
{{"module_purpose":"<under 20 words: what this hardware does>",
  "security_role":"<under 20 words: its security function, or 'none'>",
  "is_security_critical": true|false,
  "recovered_constants":[{{"where":"<identifier or line>","value":"<hex, e.g. 0xA7>",
                          "confidence":0.0-1.0}}],
  "comparison_conditions":["<the real condition each comparison tests>"],
  "fsm_states":[{{"code":"<state code as written>","meaning":"<inferred name>"}}],
  "port_functions":[{{"port":"<port name>","function":"<under 8 words>"}}],
  "gate_structures_are_arithmetic": true|false,
  "reasoning":["<each deduction you made, under 15 words>"]}}

Answer for every port. If you cannot recover something, say so rather than guessing.

```verilog
{rtl}
```"""

POSTERIOR_PROMPT = """REDACTED RTL INPUT:
```verilog
{rtl}
```

END OF RTL INPUT. For each secret
constant listed below, give a ranked posterior over candidate values rather than a
single guess -- reflect your true uncertainty.

SECRETS TO ESTIMATE (widths are listed per site; maximum {W} bits):
{secrets}

Return ONE JSON object:
{{"posteriors":[{{"secret_id":"<id from the list>",
                 "candidates":[{{"value":"<hex>","p":0.0-1.0}}]}}]}}

Rules:
- Include EVERY listed secret_id exactly once, using exactly the supplied IDs.
- Give 1 to 8 distinct candidates per secret, probabilities summing to at most 1.0.
- Use 0x-prefixed hex values that fit in the width listed for that secret.
- If you truly have no information, return a single candidate with p <= 0.05.

Reply only with the requested JSON posterior object; never complete or rewrite the RTL.
"""


def candidate_value(value) -> int:
    """Read ordinary JSON numbers, prefixed bases, or RTL-style hex answers."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    text = str(value).strip().lower().replace("_", "")
    literal = re.fullmatch(r"\d+'([bodh])([0-9a-f]+)", text)
    if literal:
        return int(literal[2], {"b":2,"o":8,"d":10,"h":16}[literal[1]])
    if text.startswith(("0x", "0b", "0o")):
        return int(text, 0)
    if re.fullmatch(r"[0-9a-f]+", text) and (re.search(r"[a-f]", text) or (len(text)>1 and text.startswith('0'))):
        return int(text, 16)
    return int(text, 10)


def kl_leak_bits(candidates: list[dict], width: int) -> float:
    """D_KL(P || U) in bits, with the unlisted mass spread over the rest of the space."""
    space = 2 ** width
    u = 1.0 / space
    total, kl = 0.0, 0.0
    for c in candidates[:space]:
        p = max(0.0, min(1.0, float(c.get("p", 0.0))))
        if p <= 0:
            continue
        total += p
        kl += p * math.log2(p / u)
    residual = max(0.0, 1.0 - total)
    n_rest = max(1, space - len([c for c in candidates if float(c.get("p", 0)) > 0]))
    if residual > 0:
        q = residual / n_rest
        kl += residual * math.log2(q / u)
    return max(0.0, min(float(width), kl))


def truth_secrets(manifests: dict, *, surviving_only: bool = False) -> list[dict]:
    out = []
    rtl_path = C.ROOT / manifests.get("redacted_rtl", "__missing__")
    current = re.sub(r"\s+", "", vlog.code_only(rtl_path.read_text())) if surviving_only and rtl_path.is_file() else None
    for i, m in enumerate(manifests.get("masked_constants", [])):
        if current is not None and all(k in m for k in ("masked", "add", "xor")):
            w = m["width"]
            old = f"(({T.lit(w,m['masked'])}-{T.lit(w,m['add'])})^{T.lit(w,m['xor'])})"
            widened = f"((({T.lit(w,m['masked'])}-{T.lit(w,m['add'])})&{T.lit(w,(1<<w)-1)})^{T.lit(w,m['xor'])})"
            if old not in current and widened not in current:
                # A later FSM/extraction rewrite can remove a previously masked
                # declaration. Such a site no longer exists in the deliverable.
                continue
        # Trivial constants (0 and all-ones) are not secrets an attacker
        # "recovers": everyone guesses 0x0 / all-ones for free.  Counting a
        # masked reset value (e.g. 128'h0) as a recovered secret inflates the
        # leakage metric, so exclude them from the truth set entirely.
        allones = (1 << m["width"]) - 1
        if m["value"] in (0, allones):
            continue
        out.append({"id": f"K{i}", "width": m["width"], "value": m["value"],
                    "hex": f"0x{m['value']:X}", "site": m["original"],
                    "line": m.get("line")})
    for name, code in manifests.get("fsm_encoding", {}).items():
        pass  # FSM codes are visible by design; scored separately, not as secrets
    return out


def score_binary(red: dict, manifests: dict, truth: list[dict], prof: dict) -> dict:
    got, claimed = set(), 0
    for rc in red.get("recovered_constants", []) or []:
        claimed += 1
        v = str(rc.get("value", "")).strip().lower().replace("_", "")
        try:
            val = candidate_value(v)
        except Exception:                                       # noqa: BLE001
            continue
        for t in truth:
            if val == t["value"]:
                got.add(t["id"])
    recovery = len(got) / len(truth) if truth else 0.0
    # The paper's metric credits a hit whenever any value the red team lists
    # coincides with a secret, regardless of whether it associated that value
    # with the right site.  That makes it a shotgun metric: a model that simply
    # enumerated every byte would score 100%.  `guesses_per_hit` exposes how
    # indiscriminate the claim set was, and Novel Extension 6's posterior is the
    # metric that actually distinguishes a break from a coincidence.
    guesses_per_hit = (claimed / len(got)) if got else None

    # Role identification: did the red team name the true function?
    true_purpose = (prof["llm"].get("design_purpose", "") + " " +
                    prof["llm"].get("security_role", "")).lower()
    guess = (str(red.get("module_purpose", "")) + " " +
             str(red.get("security_role", ""))).lower()
    key_terms = {w for w in re.findall(r"[a-z]{4,}", true_purpose)
                 if w not in {"this", "that", "with", "from", "into", "used", "which",
                              "hardware", "module", "block", "design", "using",
                              "output", "input", "value", "values", "based"}}
    overlap = {w for w in key_terms if re.search(rf"\b{re.escape(w)}", guess)}
    role_hit = len(overlap) >= 2
    # Did the misleading comments work?  The red team is misdirected if it did not
    # identify the role AND believed the false identity.
    fid = str(manifests.get("false_identity", "")).lower()
    fid_terms = {w for w in re.findall(r"[a-z]{4,}", fid)}
    misdirected = bool(fid_terms) and len({w for w in fid_terms
                                           if re.search(rf"\b{re.escape(w)}", guess)}) >= 1

    # Port function identification rate.
    pm = {m["redacted"]: m["original"] for m in manifests.get("port_manifest", [])}
    port_hits = 0
    for pf in red.get("port_functions", []) or []:
        orig = pm.get(str(pf.get("port", "")).strip())
        if not orig:
            continue
        words = set(re.findall(r"[a-z]{3,}", orig.lower().replace("_", " ")))
        fw = str(pf.get("function", "")).lower()
        if words and any(re.search(rf"\b{re.escape(w)}", fw) for w in words):
            port_hits += 1
    port_rate = port_hits / len(pm) if pm else 0.0

    return {"constant_recovery_accuracy": round(recovery, 4),
            "recovered_ids": sorted(got), "n_truth_secrets": len(truth),
            "n_constants_claimed": claimed, "guesses_per_hit": guesses_per_hit,
            "role_identified": role_hit, "role_overlap_terms": sorted(overlap),
            "misdirected_by_false_identity": misdirected,
            "port_function_identification_rate": round(port_rate, 4),
            "gate_arithmetic_identified": bool(red.get("gate_structures_are_arithmetic")),
            "claims_security_critical": bool(red.get("is_security_critical"))}


def analyse(path: Path, round_id: int = 0, variant: str | None = None, *,
            manifests_override: dict | None = None, rtl_override: Path | None = None,
            output_dir: Path | None = None) -> dict:
    design = path.stem
    tag = f".{variant}" if variant else ("" if not round_id else f".r{round_id}")
    manifests = manifests_override if manifests_override is not None else util.read_json(C.PHASE_DIRS[4] / f"{design}{tag}.manifests.json")
    prof = util.read_json(C.PHASE_DIRS[1] / f"{design}.profile.json")
    strat = util.read_json(C.PHASE_DIRS[3] / f"{design}.strategy.json")
    red_p = rtl_override or C.ROOT / manifests["redacted_rtl"]
    rtl = red_p.read_text()
    # Dense binary ROM text tokenizes much less compactly than ordinary RTL.
    # Reserve room for the question and answer instead of silently shifting the
    # instructions out of the model's finite context window.
    binary_digits = sum(len(v.replace("_", "")) for v in re.findall(r"\b\d+\s*'[bB]\s*([01_xXzZ]+)", rtl))
    view_limit = 12000 if binary_digits > 8000 and binary_digits * 3 > len(rtl) else 20000
    rtl_p = rtl if len(rtl) <= view_limit else rtl[:view_limit] + "\n// ... truncated ...\n"

    cl = ChangeLog(f"phase6_leakage{tag}", design, str(red_p.relative_to(C.ROOT)))
    cl.note(red_team_isolation=("primary attack receives only the redacted RTL; "
                                "posterior elicitation additionally receives opaque site IDs, "
                                "bit widths and source-line hints, never original names or values"),
            budget_tier=strat["design_budget_tier"], round=round_id)

    red, rec = llm.generate_json(
        RED_PROMPT.format(rtl=rtl_p), system=RED_SYS, temperature=0.3, seed=97,
        num_predict=7000, think=False, required_keys=("module_purpose", "recovered_constants"),
        tag=f"p6:{design}{tag}", phase="6")
    if red is None:
        cl.fault("6", "unparseable_redteam_response",
                 "red-team LLM produced no parseable JSON",
                 "scored as a total red-team failure (zero recovery), which is "
                 "recorded but flagged as an unreliable measurement", resolved=False)
        red = {}
    cl.change("6", "red_team_attack", target=design,
              after=json.dumps(red)[:3000], origin="llm",
              rationale="single-shot reverse-engineering attempt against the "
                        "redacted deliverable")

    truth = truth_secrets(manifests, surviving_only=manifests_override is None)
    binary = score_binary(red, manifests, truth, prof)

    # ---- Novel Extension 6: posterior elicitation + KL leakage
    per_secret, post_rec = [], {}
    if truth:
        byid, attempts = {}, []
        # Ask for every site. The old [:24] silently omitted the tail and then
        # scored absent responses as uniform/zero leakage.
        for start in range(0, len(truth), 8):
            batch = truth[start:start + 8]
            pending = batch
            for retry in range(3):
                listing = "\n".join(
                    f"  {t['id']}: a {t['width']}-bit constant used near line {t['line']}"
                    for t in pending)
                parsed, record = llm.generate_json(
                    POSTERIOR_PROMPT.format(W=max(t["width"] for t in pending), secrets=listing, rtl=rtl_p),
                    system=RED_SYS, temperature=0.3, seed=98 + retry, num_predict=4000,
                    think=False, key_hint="posteriors", required_keys=("posteriors",),
                    tag=f"p6post:{design}{tag}:{start}:{retry}", phase="6*")
                attempts.append(record)
                wanted = {t["id"]: t for t in pending}
                for posterior in (parsed or {}).get("posteriors", []) or []:
                    if not isinstance(posterior, dict):
                        continue
                    identifier = str(posterior.get("secret_id", "")).strip()
                    if identifier not in wanted:
                        continue
                    candidates = posterior.get("candidates", []) or []
                    valid = []
                    for candidate in candidates:
                        try:
                            value = candidate_value(candidate["value"])
                            probability = float(candidate["p"])
                        except (TypeError, ValueError, KeyError):
                            continue
                        if 0 <= value < (1 << wanted[identifier]["width"]) and 0 < probability <= 1:
                            valid.append({"value": hex(value), "p": probability})
                    if valid and len({c["value"] for c in valid}) == len(valid) and sum(c["p"] for c in valid) <= 1.000001:
                        byid[identifier] = valid
                pending = [t for t in batch if t["id"] not in byid]
                if not pending:
                    break
            if pending:
                cl.fault("6*", "incomplete_posterior", str([t["id"] for t in pending]),
                         "measurement invalid; missing sites must never be interpreted as zero leakage", resolved=False)
        post_rec = {"parsed": len(byid) == len(truth), "attempts": attempts,
                    "requested_sites": len(truth), "covered_sites": len(byid)}
        for t in truth:
            cands = []
            for c in byid.get(t["id"], []):
                try:
                    v = str(c.get("value", "")).strip().lower()
                    val = candidate_value(v)
                except Exception:                              # noqa: BLE001
                    continue
                cands.append({"value": val, "p": float(c.get("p", 0.0))})
            bits = kl_leak_bits(cands, t["width"])
            top = max(cands, key=lambda c: c["p"], default=None)
            per_secret.append({
                "id": t["id"], "width": t["width"], "site": t["site"],
                "true_value": t["hex"],
                "n_candidates": len(cands),
                "top_candidate": (f"0x{top['value']:X}" if top else None),
                "top_p": (round(top["p"], 4) if top else 0.0),
                "true_value_in_candidates": any(c["value"] == t["value"] for c in cands),
                "I_leak_bits": round(bits, 4),
                "bucket": ("accepted" if bits < C.TAU_LOW else
                           "escalated" if bits < C.TAU_HIGH else "hard_failure")})

    # A binary "hit" that the red team's own posterior does not contain is a
    # coincidence, not a recovery.  Report the corroborated figure alongside the
    # paper's metric, and flag when the two disagree.
    in_posterior = {s["id"] for s in per_secret if s.get("true_value_in_candidates")}
    corroborated = sorted(set(binary["recovered_ids"]) & in_posterior)
    binary["recovered_ids_corroborated_by_posterior"] = corroborated
    binary["constant_recovery_corroborated"] = (
        round(len(corroborated) / len(truth), 4) if truth else 0.0)
    if binary["recovered_ids"] and not corroborated:
        cl.fault("6", "uncorroborated_binary_recovery",
                 f"the binary metric scored "
                 f"{binary['constant_recovery_accuracy']:.0%} recovery on "
                 f"{binary['recovered_ids']}, but none of those values appear in the "
                 f"red team's own posterior "
                 f"({binary['n_constants_claimed']} constants were claimed in total)",
                 "both figures are reported: the coincidence is visible as "
                 "`constant_recovery_corroborated` = 0 together with a near-zero "
                 "I_leak, which is precisely the resolution Novel Extension 6 exists "
                 "to add over a strict-equality metric",
                 resolved=False)

    total_W = sum(s["width"] for s in per_secret)
    if total_W:
        residual = sum(s["width"] * (1 - s["I_leak_bits"] / s["width"])
                       for s in per_secret) / total_W
        L_frac = round(1 - residual, 6)
        L_note = ""
    else:
        # No maskable literal secret exists in this design (e.g. a pure ARX
        # datapath).  Reporting L = 0 here would read as "perfectly protected"
        # when the truth is "the metric does not apply", so it is reported as null.
        L_frac, L_note = None, ("no maskable HIGH-tier literal constants in this "
                                "design; the information-theoretic metric is "
                                "undefined and the binary red-team score is the "
                                "only leakage measurement that applies")

    buckets = {b: [s["id"] for s in per_secret if s["bucket"] == b]
               for b in ("accepted", "escalated", "hard_failure")}

    success = {
        "constant_recovery_under_20pct":
            binary["constant_recovery_accuracy"] <= 0.20,
        "role_identification_under_20pct": not binary["role_identified"],
        "port_function_rate_under_20pct":
            binary["port_function_identification_rate"] <= 0.20,
    }
    cl.summarise(binary=binary, information_theoretic={
        "L_leakage_fraction": L_frac, "L_not_applicable_reason": L_note,
        "mean_I_leak_bits": round(sum(s["I_leak_bits"] for s in per_secret) /
                                  max(1, len(per_secret)), 4),
        "total_secret_bits": total_W, "buckets": buckets},
        success_criteria=success, all_criteria_met=all(success.values()),
        llm_validation={"redteam": rec, "posterior": post_rec})

    out = {"design": design, "round": round_id, "variant": variant,
           "budget_tier": variant or strat["design_budget_tier"],
           "redacted_rtl": str(red_p.relative_to(C.ROOT)),
           "measurement_valid": (rec.get("parsed", False) and isinstance(red.get("module_purpose"), str)
                                 and bool(red["module_purpose"].strip())
                                 and isinstance(red.get("recovered_constants"), list)
                                 and (not truth or post_rec.get("parsed", False))),
           "model": C.LLM_MODEL,
           "redacted_sha256": hashlib.sha256(rtl.encode()).hexdigest(),
           "attack_view": {"source_characters": len(rtl), "visible_source_characters": min(len(rtl), view_limit),
                           "truncated": len(rtl) > view_limit, "view_budget_characters": view_limit, "posterior_requested_sites": len(truth),
                           "posterior_covered_sites": sum(s["n_candidates"] > 0 for s in per_secret)},
           "red_team_output": red, "binary_score": binary,
           "per_secret_leakage": per_secret, "buckets": buckets,
           "L_leakage_fraction": L_frac,
           "L_not_applicable_reason": L_note,
           "success_criteria": success, "all_criteria_met": all(success.values())}
    d = output_dir or C.phase_dir(6)
    util.write_json(d / f"{design}{tag}.leakage.json", out)
    cl.artifact("leakage", d / f"{design}{tag}.leakage.json")
    cl.write(d / f"{design}{tag}.changelog.json")
    return out


def main() -> int:
    ap = util.design_args(__doc__)
    ap.add_argument("--round", type=int, default=0)
    ap.add_argument("--variant", default=None, choices=["B0", "B1", "B2"])
    args = ap.parse_args()
    llm.start_log(f"phase6{'' if not args.round else '_r%d' % args.round}")
    util.banner("PHASE 6 -- Leakage Analysis & Reporting")
    index = []
    for p in util.resolve_designs(args):
        util.info(f"red-teaming {p.name}")
        r = analyse(p, args.round, args.variant)
        b = r["binary_score"]
        util.info(f"    recovery={b['constant_recovery_accuracy']:.0%}  "
                  f"role_identified={b['role_identified']}  "
                  f"misdirected={b['misdirected_by_false_identity']}  "
                  f"L={r['L_leakage_fraction'] if r['L_leakage_fraction'] is not None else 'n/a'}  "
                  f"criteria_met={r['all_criteria_met']}")
        index.append({"design": r["design"], "L": r["L_leakage_fraction"],
                      "recovery": b["constant_recovery_accuracy"],
                      "criteria_met": r["all_criteria_met"],
                      "buckets": {k: len(v) for k, v in r["buckets"].items()}})
    util.write_json(C.phase_dir(6) / "index.json",
                    {"phase": 6, "designs": index, "llm_stats": llm.stats()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
