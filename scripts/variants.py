#!/usr/bin/env python3
"""Novel Extension 2 -- build and evaluate the redaction variant family.

The paper: "Rather than a single redacted deliverable, Phase 3/4 under this
extension produce a small family of redacted variants {R_B0, R_B1, R_B2} of
increasing transformation depth and area/verification cost. Phase 6 is then run
against each variant ... producing a leakage-vs-overhead Pareto curve."

For each design this runs Phase 4, 5 and 6 three times -- once per budget tier --
and writes pipeline/report/pareto_variants.{csv,png}, so a design team can pick
the variant whose overhead their actual sharing scenario justifies rather than
over- or under-protecting by default.
"""
from __future__ import annotations
import csv, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from great import config as C, llm, util
import phase4_transform as P4
import phase5_verify as P5
import phase6_leakage as P6
from report import gate_count


def main() -> int:
    args = util.design_args(__doc__).parse_args()
    llm.start_log("variants")
    util.banner("NOVEL EXTENSION 2 -- Redaction variant family {R_B0, R_B1, R_B2}")
    rows = []
    for p in util.resolve_designs(args):
        g_orig = gate_count(p, p.stem)
        util.info(f"{p.name} (original: {g_orig} cells)")
        for tier in C.BUDGET_ORDER:
            m = P4.transform(p, variant=tier)
            v = P5.verify(p, variant=tier)
            l = P6.analyse(p, variant=tier)
            g_red = gate_count(C.ROOT / m["redacted_rtl"], p.stem)
            ovh = (round(100 * (g_red - g_orig) / g_orig, 2)
                   if (g_orig and g_red) else None)
            b = l["binary_score"]
            rows.append({
                "design": p.stem, "tier": tier,
                "steps": ",".join(m["applied_steps"]),
                "compiles": m["compiles"], "verdict": v["verdict"],
                "formal_proved": (v["formal"] or {}).get("proved"),
                "n_renamed": len(m["identifier_manifest"]),
                "n_masked": len(m["masked_constants"]),
                "n_decoys": len(m["decoy_manifest"]),
                "recovery": b["constant_recovery_accuracy"],
                "role_identified": b["role_identified"],
                "misdirected": b["misdirected_by_false_identity"],
                "L": l["L_leakage_fraction"],
                "gates_original": g_orig, "gates_redacted": g_red,
                "gate_overhead_pct": ovh,
            })
            util.info(f"    {tier}: verdict={v['verdict']} "
                      f"formal={(v['formal'] or {}).get('proved')} "
                      f"L={l['L_leakage_fraction']} overhead={ovh}%")
    out = C.phase_dir(7)
    with (out / "pareto_variants.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["design"])
        w.writeheader(); w.writerows(rows)
    util.write_json(out / "variants.json", {"rows": rows, "llm_stats": llm.stats()})

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        pts = [r for r in rows if r["gate_overhead_pct"] is not None]
        if pts:
            fig, ax = plt.subplots(figsize=(7.5, 4.8))
            designs = sorted({r["design"] for r in pts})
            cmap = plt.get_cmap("tab10")
            for i, d in enumerate(designs):
                s = sorted([r for r in pts if r["design"] == d],
                           key=lambda r: C.BUDGET_ORDER.index(r["tier"]))
                ax.plot([r["gate_overhead_pct"] for r in s],
                        [r["recovery"] for r in s], "o-", color=cmap(i % 10),
                        label=d, markersize=6)
                for r in s:
                    ax.annotate(r["tier"], (r["gate_overhead_pct"], r["recovery"]),
                                fontsize=7, xytext=(4, 4), textcoords="offset points")
            ax.set_xlabel("synthesis gate-count overhead (%)")
            ax.set_ylabel("red-team constant recovery accuracy")
            ax.set_title("Leakage vs. overhead Pareto curve across budget tiers")
            ax.grid(alpha=.3)
            ax.legend(fontsize=7, ncol=2)
            fig.tight_layout(); fig.savefig(out / "pareto_variants.png", dpi=150)
            util.info(f"wrote {out / 'pareto_variants.png'}")
    except Exception as exc:                                   # noqa: BLE001
        util.warn(f"plot skipped: {exc}")
    util.info(f"wrote {out / 'pareto_variants.csv'} ({len(rows)} variants)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
