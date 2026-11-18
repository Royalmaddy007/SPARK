#!/usr/bin/env python3
"""Final deliverable assembly (paper Section V, Deliverables 1-7).

Collects every phase's artefacts into one place and writes:
  * pipeline/report/REDACTION_REPORT.md   -- the before/after analysis
  * pipeline/report/summary.json          -- machine-readable roll-up
  * pipeline/report/pareto.csv/.png       -- leakage-vs-overhead Pareto curve
  * pipeline/report/deliverables/         -- the shipped package per design,
                                             with the confidential manifests kept
                                             separate from the redacted RTL
"""
from __future__ import annotations
import csv, json, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, util, vlog


def gate_count(v: Path, exclude: str | None = None) -> int | None:
    """Synthesised cell count of `v`'s top module, for the Pareto overhead axis."""
    if not C.YOSYS:
        return None
    import re
    mods = vlog.parse_modules(v.read_text())
    if not mods:
        return None
    top = mods[0].name
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        shutil.copy(v, td / "d.v")
        deps = "".join(f"read_verilog -sv {d}\n" for d in C.dep_files(exclude))
        # Pin the top explicitly and flatten, so `stat` reports one whole-design
        # count.  Step 4l appends script-generated PRSG helper modules; letting
        # yosys auto-elect a top, or reading the last "N cells" line, would
        # report a helper's size instead of the design's.
        (td / "s.ys").write_text(deps + "read_verilog -sv d.v\n"
                                 f"hierarchy -check -top {top}\n"
                                 "proc; flatten; opt; techmap; opt\n"
                                 "stat\n")
        r = subprocess.run([C.YOSYS, "-s", "s.ys"], cwd=td,
                           capture_output=True, text=True)
        if r.returncode != 0:
            return None
        out = r.stdout + r.stderr
        block = re.search(rf"===\s*\\?{re.escape(top)}\s*===(.*?)(?====|\Z)", out, re.S)
        scope = block.group(1) if block else out
        m = re.findall(r"^\s*(\d+)\s+cells\s*$", scope, re.M)
        return int(m[0]) if m else None


def load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else None


def collect(design: str) -> dict:
    d = {"design": design}
    d["profile"] = load(C.PHASE_DIRS[1] / f"{design}.profile.json")
    d["sensitivity"] = load(C.PHASE_DIRS[2] / f"{design}.sensitivity.json")
    d["strategy"] = load(C.PHASE_DIRS[3] / f"{design}.strategy.json")
    d["manifests"] = load(C.PHASE_DIRS[4] / f"{design}.manifests.json")
    d["verification"] = load(C.PHASE_DIRS[5] / f"{design}.verification.json")
    d["leakage"] = load(C.PHASE_DIRS[6] / f"{design}.leakage.json")
    d["escalation"] = load(C.PHASE_DIRS["6b"] / f"{design}.escalation.json")
    for phase, key, suffix in (("4b", "overhead", "overhead"), ("6c", "sat", "sat"),
                               ("6d", "dana", "dana"), ("6e", "removal", "removal")):
        d[key] = load(C.PHASE_DIRS[phase] / f"{design}.{suffix}.json")
        record = d[key]
        artifact = (d.get('manifests') or {}).get('redacted_rtl')
        if record and record.get('artifact_sha256') and artifact:
            from great.overhead import digest
            if digest(C.ROOT / artifact) != record['artifact_sha256']:
                record['status'] = 'stale'
                record['outcome'] = 'stale'
                record['reason'] = 'Phase-4 artifact changed since measurement; rerun evaluation'
                if key == 'removal':
                    for variant in ('full', 'stripped'):
                        record[variant] = {'leakage_status': 'stale'}
    d["changelogs"] = {}
    for ph, key in ((1, "phase1"), (2, "phase2"), (3, "phase3"), (4, "phase4"),
                    (5, "phase5"), (6, "phase6"), ("6b", "phase6b")):
        c = load(C.PHASE_DIRS[ph] / f"{design}.changelog.json")
        if c:
            d["changelogs"][key] = {"total_changes": c["summary"].get("total_changes"),
                                    "by_step": c["summary"].get("changes_by_step"),
                                    "faults": len(c.get("faults_detected", []))}
    return d


def package(design: str, data: dict, out: Path) -> dict:
    """Deliverables 1-3: redacted RTL ships; manifests are confidential."""
    pkg = out / design
    (pkg / "confidential").mkdir(parents=True, exist_ok=True)
    files = {}
    mf = data.get("manifests") or {}
    esc = data.get("escalation") or {}
    src_v = C.ROOT / (esc.get("delivered_artifact") or mf.get("redacted_rtl", ""))
    if src_v.is_file():
        shutil.copy(src_v, pkg / f"{design}.redacted.v")
        files["redacted_rtl"] = f"{design}.redacted.v"
    util.write_json(pkg / "confidential" / "port_mapping_manifest.json",
                    {"design": design, "warning": "CONFIDENTIAL -- never ship this "
                     "with the redacted RTL", "ports": mf.get("port_manifest", []),
                     "identifiers": mf.get("identifier_manifest", {})})
    util.write_json(pkg / "confidential" / "decoy_manifest.json",
                    {"design": design, "warning": "CONFIDENTIAL -- identifies the "
                     "honeypot logic so the design team never mistakes it for real "
                     "logic; the decoy has no path to any output",
                     "decoys": mf.get("decoy_manifest", [])})
    util.write_json(pkg / "confidential" / "constant_mask_manifest.json",
                    {"design": design, "masked_constants": mf.get("masked_constants", []),
                     "fsm_encoding": mf.get("fsm_encoding", {})})
    if data.get("verification"):
        util.write_json(pkg / "verification_report.json", data["verification"])
        files["verification"] = "verification_report.json"
    if data.get("leakage"):
        util.write_json(pkg / "leakage_analysis.json", data["leakage"])
        files["leakage"] = "leakage_analysis.json"
    return files


def md_table(rows, headers):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def metric(value):
    return "not measured" if value is None else f"{value:.6g}"


def evaluation_sections(all_data):
    md = ["", "## § PPA Overhead (ASAP7)", "",
          "A: µm², D: ps, P: mW. OvhA/OvhD/OvhP are redacted/original ratios (×). "
          "Arithmetic averages include only complete measured rows. Pre-layout ASAP7 RVT TT; "
          "default 1 ns period, 1 fF output load and 0.1 activity. These are vectorless estimates, "
          "not a replication of HIPR's physical-design constraints.", ""]
    rows, measured = [], []
    for name, d in all_data.items():
        p = d.get('overhead') or {}
        if p.get('status') == 'ok':
            values = [p['original'][k] for k in ('area_um2', 'delay_ps', 'power_mw')]
            values += [p['overhead'][k] for k in ('area_x', 'delay_x', 'power_x')]
            measured.append(values)
            rows.append([name, *map(metric, values)])
        else:
            rows.append([name, *(['not measured'] * 6)])
            md.append(f"- {name}: {p.get('reason', 'Phase 4b not run')}")
    if measured:
        rows.append(['Average', *[metric(sum(v[i] for v in measured)/len(measured)) for i in range(6)]])
    md += ['', md_table(rows, ['design', 'A (µm²)', 'D (ps)', 'P (mW)', 'OvhA (×)', 'OvhD (×)', 'OvhP (×)']), '',
           '## § Adversarial Attack Resistance', '',
           'SAT uses PSAT with scan-cut interfaces where alignable. `not_applicable_no_key` means '
           'redaction exposes no hidden key inputs; it is not a successful defense against SAT. '
           '`io_mismatch` is an interface limitation, not evidence of resistance. SAT runtime excludes conversion. '
           'Structural clustering uses NetworkX connected components over FF-to-FF paths: '
           '**DANA-inspired, not the hal plugin**. Its cluster counts are not interchangeable with DANA results.', '']
    rows = []
    for name, d in all_data.items():
        sat, dana = d.get('sat') or {}, d.get('dana') or {}
        rows.append([name, sat.get('outcome', 'not run'), metric(sat.get('runtime_s')),
                     sat.get('recovered_key') or 'none',
                     dana.get('cluster_count') if dana.get('status') == 'ok' else 'not measured',
                     metric(dana.get('runtime_s'))])
    md += [md_table(rows, ['design', 'SAT outcome', 'SAT time (s)', 'recovered key',
                          'DANA-inspired clusters', 'clustering time (s)']), '',
           '## § Cross-model Juror Audit', '',
           'Cross-model disagreement counts require the two local personas to agree and the third juror '
           'to return a different tier. Later faults are Phase 4/5/6 changelog occurrences on the same '
           'design, a descriptive co-occurrence rather than causal evidence.', '']
    rows = []
    for name, d in all_data.items():
        sensitivity = d.get('sensitivity') or {}
        cross = set(sensitivity.get('cross_model_disagreements', []))
        rgot = {r['signal'] for r in (sensitivity.get('rgot_cross_check') or {}).get('disagreements', [])}
        faults = sum((d.get('changelogs', {}).get(f'phase{phase}') or {}).get('faults', 0) for phase in (4, 5, 6))
        rows.append([name, sensitivity.get('ensemble_kind', 'not run'), len(cross),
                     len(rgot & cross), len(rgot - cross), faults, bool(cross and faults)])
    md += [md_table(rows, ['design', 'ensemble kind', 'cross-model disagreements',
                          'RGoT disagreements involving cross-model dissent', 'other RGoT disagreements',
                          'later faults', 'dissent and later faults']), '',
           '## § Removal-Attack Ablation', '',
           'The stripped variant removes manifest-listed decoy wires and replaces supported constant '
           'reconstruction chains with their masked literals. This intentionally may change functionality. '
           'FSM encoding, rotating comparison masks and PRSG helpers remain. The detector sees RTL only, '
           'using Yosys elaboration and NetworkX reachability to outputs/register inputs; flags may include '
           'benign dead logic. No improvement is claimed without valid paired LLM measurements.', '']
    rows = []
    for name, d in all_data.items():
        attack = d.get('removal') or {}
        for variant in ('full', 'stripped'):
            v = attack.get(variant) or {}
            lk = v.get('leakage') or {}
            valid = v.get('leakage_status') == 'ok'
            binary = lk.get('binary_score') or {}
            rows.append([name, variant, v.get('leakage_status', 'not run'),
                         metric(binary.get('constant_recovery_accuracy')) if valid else 'not measured',
                         metric(binary.get('constant_recovery_corroborated')) if valid else 'not measured',
                         metric(lk.get('L_leakage_fraction')) if valid else 'not measured',
                         v.get('detector', {}).get('flag', 'not measured')])
    md += [md_table(rows, ['design', 'variant', 'LLM status', 'recovery', 'corroborated', 'L',
                          'unobservable logic flag']), '']
    return md


def main() -> int:
    args = util.design_args(__doc__).parse_args()
    util.banner("REPORT -- Deliverable Assembly")
    out = C.phase_dir(7)
    pkg_dir = out / "deliverables"
    designs = [p.stem for p in util.resolve_designs(args)]

    rows, pareto, all_data = [], [], {}
    for design in designs:
        data = collect(design)
        if not data.get("manifests"):
            util.warn(f"{design}: no Phase-4 output, skipping")
            continue
        all_data[design] = data
        files = package(design, data, pkg_dir)
        orig = C.ROOT / data["profile"]["source_file"]
        red = C.ROOT / (data["manifests"]["redacted_rtl"])
        g_o, g_r = gate_count(orig, design), gate_count(red, design)
        overhead = (round(100 * (g_r - g_o) / g_o, 2)
                    if (g_o and g_r) else None)
        ver, lk = data["verification"] or {}, data["leakage"] or {}
        b = (lk.get("binary_score") or {})
        rows.append([design, data["strategy"]["design_budget_tier"],
                     data["sensitivity"]["tier_counts"]["HIGH"],
                     len(data["manifests"]["identifier_manifest"]),
                     len(data["manifests"]["masked_constants"]),
                     len(data["manifests"]["decoy_manifest"]),
                     ver.get("verdict", "-"),
                     (ver.get("formal") or {}).get("method", "-"),
                     f"{b.get('constant_recovery_accuracy', 0):.0%}",
                     f"{b.get('constant_recovery_corroborated', 0):.0%}",
                     lk.get("L_leakage_fraction"),
                     f"{overhead}%" if overhead is not None else "-"])
        esc = data.get("escalation") or {}
        for h in esc.get("pareto", []) or [{"tier": data["strategy"]["design_budget_tier"],
                                            "round": 0,
                                            "L": lk.get("L_leakage_fraction")}]:
            pareto.append({"design": design, "tier": h["tier"], "round": h["round"],
                           "L": h["L"], "gate_overhead_pct": overhead,
                           "gates_original": g_o, "gates_redacted": g_r})
        util.info(f"{design}: packaged -> {pkg_dir / design}")

    hdr = ["design", "tier", "HIGH", "renamed", "masked", "decoys", "phase5",
           "formal method", "recovery", "corroborated", "L", "gate overhead"]
    with (out / "pareto.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["design", "tier", "round", "L",
                                           "gate_overhead_pct", "gates_original",
                                           "gates_redacted"])
        w.writeheader(); w.writerows(pareto)

    # ---- Pareto plot
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        pts = [p for p in pareto if p["L"] is not None and p["gate_overhead_pct"] is not None]
        if pts:
            fig, ax = plt.subplots(figsize=(7, 4.5))
            colors = {"B0": "#4C72B0", "B1": "#DD8452", "B2": "#55A868"}
            for t in ("B0", "B1", "B2"):
                s = [p for p in pts if p["tier"] == t]
                if s:
                    ax.scatter([p["gate_overhead_pct"] for p in s],
                               [p["L"] for p in s], label=t, s=60,
                               color=colors[t], edgecolor="white", zorder=3)
            for p in pts:
                ax.annotate(p["design"][:14], (p["gate_overhead_pct"], p["L"]),
                            fontsize=7, xytext=(4, 3), textcoords="offset points")
            ax.set_xlabel("synthesis gate-count overhead (%)")
            ax.set_ylabel("information-theoretic leakage fraction L")
            ax.set_title("Leakage vs. overhead by attacker budget tier")
            ax.grid(alpha=.3, zorder=0); ax.legend(title="budget tier")
            fig.tight_layout(); fig.savefig(out / "pareto.png", dpi=150)
            plt.close(fig)
            util.info("wrote pareto.png")
    except Exception as exc:                                   # noqa: BLE001
        util.warn(f"pareto plot skipped: {exc}")

    # ---- Markdown report
    md = ["# Redaction Report -- GenAI-Assisted RTL Hardware IP Redaction", "",
          f"Default model: `{C.LLM_MODEL}`. Effective Phase-2 jurors are recorded per design. Designs: {len(rows)}.", "",
          "## 1. Per-design summary", "", md_table(rows, hdr), "",
          "`recovery` is the paper's metric: the fraction of masked HIGH-tier "
          "constants whose value appears anywhere in the red team's answer. It is a "
          "shotgun metric -- a model that simply enumerated every byte would score "
          "100% -- so `corroborated` reports the stricter figure, counting a secret "
          "only when the red team's own elicited posterior also contains it. Where "
          "the two disagree, the change log carries an "
          "`uncorroborated_binary_recovery` fault naming how many constants were "
          "claimed in total. `L` is the information-theoretic leakage fraction of "
          "Novel Extension 6 (0 = the attacker's posterior stayed uniform; 1 = full "
          "recovery), and it is the figure that actually distinguishes a break from "
          "a coincidence.\n\n"
          "> **Note on these numbers.** The final red-team pass runs the local model "
          "with its reasoning pass disabled (`think:false`) for tractability. Without "
          "reasoning the model's guesses and posteriors are *noisy* -- both "
          "directions -- so treat per-design `recovery`/`L` as indicative, not "
          "authoritative (re-run Phase 6 with `think=True` for authoritative "
          "figures; earlier full-reasoning runs showed ~0% recovery). The real, "
          "reasoning-independent correctness guarantee is the **Phase-5 formal "
          "equivalence proof**. Trivial constants (0 / all-ones, e.g. masked reset "
          "values) are excluded from the secret set so they cannot inflate recovery.", "",
          "## 2. Verification", ""]
    vrows = []
    for design, d in all_data.items():
        v = d["verification"] or {}
        f = v.get("formal") or {}
        vrows.append([design, v.get("verdict", "-"),
                      (v.get("syntax") or {}).get("ok"),
                      (v.get("interface") or {}).get("ok"),
                      (v.get("interface") or {}).get("widths_preserved"),
                      (v.get("simulation") or {}).get("passed"),
                      (v.get("testbench_meta") or {}).get("n_random_vectors", "-"),
                      f.get("method", "-"), f.get("depth", "-")])
    md += [md_table(vrows, ["design", "verdict", "syntax", "interface", "widths kept",
                            "simulation", "random vectors", "formal method", "bound"]),
           "",
           "`structural_induction` proves every internal signal pair equal. Once Step 4e "
           "re-encodes an FSM the state registers legitimately differ, so no structural "
           "proof can exist and the check falls back to `bounded_sequential_miter`: a "
           "reset-constrained proof that the two designs are observationally identical "
           "on their ports for every input sequence up to `bound` cycles. "
           "`inconclusive` means the solver ran out of budget -- reported as "
           "`PASS_SIM_ONLY`, never as a pass. `refuted` means a real counterexample "
           "was found and is recorded in the verification report.", "",
           "## 3. Faults detected and mitigated", ""]
    frows = {}
    for design in all_data:
        for ph in (1, 2, 3, 4, 5, 6, "6b"):
            c = load(C.PHASE_DIRS[ph] / f"{design}.changelog.json")
            for f in (c or {}).get("faults_detected", []):
                fault_name = f['fault']
                if fault_name == 'rgot_ensemble_disagreement':
                    sensitivity = all_data[design].get('sensitivity') or {}
                    cross = set(sensitivity.get('cross_model_disagreements', []))
                    rgot = {x['signal'] for x in (sensitivity.get('rgot_cross_check') or {}).get('disagreements', [])}
                    fault_name += ':cross_model_dissent' if cross & rgot else ':without_cross_model_dissent'
                k = (f["step"], fault_name)
                frows.setdefault(k, {"n": 0, "resolved": 0, "designs": set()})
                frows[k]["n"] += 1
                frows[k]["resolved"] += bool(f.get("resolved"))
                frows[k]["designs"].add(design)
    md += [md_table([[s, f, v["n"], v["resolved"], len(v["designs"])]
                     for (s, f), v in sorted(frows.items())],
                    ["step", "fault", "occurrences", "auto-resolved", "designs"]), "",
           "Most of the faults above are ones the paper's Phase-4 taxonomy "
           "anticipates, and the orchestration script detects and mitigates each "
           "rather than letting it reach the deliverable. Two are **not** in the "
           "paper and were found by this pipeline's own verification: "
           "`externally_visible_decode_constants` (Step 4e re-encoding an address or "
           "mode constant that is compared against a top-level input, which changes "
           "the module's external contract) and `ensemble_under_tagging` (the N=3 "
           "ensemble returning zero HIGH signals on a design Phase 1 profiled as "
           "security-critical). A row with `auto-resolved` below `occurrences` is one "
           "the pipeline reports for human review rather than silently repairing.",
           "",
           "## 4. Escalation (Phase 6B)", ""]
    erows = []
    for design, d in all_data.items():
        e = d.get("escalation")
        if e:
            erows.append([design, e["final_round"], e["final_tier"], e["final_L"],
                          e["stop_reason"], len(e["human_review_sites"])])
    md += [md_table(erows, ["design", "rounds", "final tier", "final L",
                            "stop reason", "human-review sites"]) if erows
           else "_not run_", "",
           "## 4b. Exhaustive testbench (ModelSim, per phase)", ""]
    trows = []
    for design in all_data:
        t = load(C.PHASE_DIRS["tb"] / f"{design}.tb_results.json")
        if not t:
            continue
        per = {p["phase"]: ("PASS" if p["passed"] else
                            "FAIL" if p["compiled"] else "CFAIL")
               for p in t.get("phases", [])}
        trows.append([design,
                      "seq" if t.get("sequential") else "comb",
                      "yes" if t.get("exhaustive") else "no",
                      t.get("n_scenarios"),
                      per.get("0_baseline", "-"), per.get("3_strategy", "-"),
                      per.get("4_transform", "-"),
                      f"{t.get('n_pass')}/{t.get('n_phases')}"])
    md += [md_table(trows, ["design", "type", "exhaustive", "scenarios",
                            "baseline", "phase3", "phase4", "phases pass"]) if trows
           else "_not run (ModelSim required)_", "",
           "A single self-checking comparator testbench per design (frozen original as "
           "golden vs. the design at each phase) is run on **ModelSim** at every "
           "incremental phase. `baseline` is the un-redacted design; `phase4` is the "
           "redacted deliverable with its DUT binding adapted from the port-mapping "
           "manifest. Every phase must reproduce the golden outputs on comprehensive "
           "stimulus (exhaustive where the input space permits). A testbench that "
           "fails to compile is repaired by the local LLM.", "",
           "## 5. Deliverable package", "",
           "`pipeline/report/deliverables/<design>/` contains the shipped redacted "
           "`.v`, the verification report and the leakage analysis. The port-mapping, "
           "decoy and constant-mask manifests live under `confidential/` and are "
           "explicitly **not** part of what is handed to a third party.", "",
           "## 6. Provenance", "",
           "All source designs are unmodified open-source Verilog; see "
           "`examples/CITATIONS.md` for repository, commit hash, permalink and "
           "licence of each file.", ""]
    evaluations = evaluation_sections(all_data)
    removal_start = evaluations.index('## § Removal-Attack Ablation')
    verification_start = md.index('## 2. Verification')
    md[verification_start:verification_start] = evaluations[removal_start:] + ['']
    md += evaluations[:removal_start]
    (out / "REDACTION_REPORT.md").write_text("\n".join(md))
    util.write_json(out / "summary.json",
                    {"model": C.LLM_MODEL, "designs": list(all_data),
                     "table": [dict(zip(hdr, r)) for r in rows], "pareto": pareto,
                     "evaluations": {name: {k: d.get(k) for k in ("overhead", "sat", "dana", "removal")}
                                     for name, d in all_data.items()}})
    util.info(f"wrote {out / 'REDACTION_REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
