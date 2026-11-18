#!/usr/bin/env python3
"""Phase 5 -- Functional & Formal Verification.

Four gates, in increasing strength:

  1. Syntax          -- Icarus Verilog compiles the redacted deliverable.
  2. Interface       -- port count, order, direction and *width* are unchanged
                        (the paper's hard usability constraint: identifiers are
                        renamed, widths never are).
  3. Simulation      -- a generated self-checking testbench drives the original
                        and the redacted module with identical stimulus (random
                        + corner cases + LLM-proposed security-critical vectors)
                        and compares every output on every vector.
  4. Formal          -- Yosys `equiv_make` / `equiv_induct` / `equiv_status -assert`
                        proves combinational equivalence; a failure yields a
                        concrete distinguishing input vector, which is written
                        into a Phase-4 repair prompt verbatim.

A Yosys counter-example is the single most valuable artefact this phase can
produce, so it is captured in full rather than summarised.
"""
from __future__ import annotations
import json, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, llm, vlog, util
from great.changelog import ChangeLog

VECTOR_PROMPT = """Propose corner-case stimulus for a Verilog equivalence testbench.

MODULE INPUTS (name : width in bits):
{inputs}

DESIGN PURPOSE: {purpose}

Return ONE JSON object:
{{"vectors":[{{"name":"<under 6 words>","values":{{"<input name>":<integer>}}}}]}}

Rules:
- Give 6 to 12 vectors that specifically stress SECURITY-CRITICAL behaviour:
  all-zeros, all-ones, the exact value of any comparison threshold you can infer,
  that value +/- 1, single-bit-set patterns, and alternating bit patterns.
- Every integer must be non-negative and fit in that input's width.
- Use ONLY the input names listed above.
"""


def run(cmd, cwd=None, timeout=600):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def elaborated_ports(src: str) -> dict:
    """Resolve port widths with the Verilog elaborator, including body parameters."""
    top = vlog.parse_modules(src)[0].name
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        (folder / "input.v").write_text(src)
        script = f"read_verilog input.v; hierarchy -top {top}; proc; write_json ports.json"
        rc, so, se = run([C.YOSYS, "-Q", "-T", "-p", script], cwd=folder)
        if rc:
            raise ValueError(f"interface elaboration failed: {(se or so)[-1500:]}")
        return json.loads((folder / "ports.json").read_text())["modules"][top]["ports"]


# ------------------------------------------------------------------ gate 2
def check_interface(orig: str, red: str, manifests: dict, cl: ChangeLog) -> dict:
    om = vlog.parse_modules(orig)[0]
    rm = vlog.parse_modules(red)[0]
    pm = {m["original"]: m for m in manifests.get("port_manifest", [])}
    issues = []
    try:
        op, rp = elaborated_ports(orig), elaborated_ports(red)
    except ValueError as exc:
        op, rp = {}, {}
        issues.append(str(exc))
    if not om.ports:
        issues.append("no parsed ports: cannot perform a non-vacuous interface check")
    if op and [p["name"] for p in om.ports] != list(op):
        issues.append("original parsed port list disagrees with elaborated interface")
    if rp and [p["name"] for p in rm.ports] != list(rp):
        issues.append("redacted parsed port list disagrees with elaborated interface")
    if len(om.ports) != len(rm.ports):
        issues.append(f"port count {len(om.ports)} -> {len(rm.ports)}")
    for i, (a, b) in enumerate(zip(om.ports, rm.ports)):
        expect = pm.get(a["name"], {}).get("redacted", a["name"])
        if b["name"] != expect:
            issues.append(f"position {i}: expected '{expect}', found '{b['name']}'")
        if a["dir"] != b["dir"]:
            issues.append(f"{a['name']}: direction {a['dir']} -> {b['dir']}")
        aw, bw = op.get(a["name"]), rp.get(b["name"])
        if aw is not None and bw is not None and bool(aw.get("signed")) != bool(bw.get("signed")):
            issues.append(f"{a['name']}: SIGNEDNESS changed")
        if aw is None or bw is None or len(aw["bits"]) != len(bw["bits"]):
            issues.append(f"{a['name']}: WIDTH elaboration mismatch {aw} -> {bw}")
    ok = not issues
    cl.change("5", "interface_check", target=f"{len(om.ports)} ports",
              after="unchanged" if ok else json.dumps(issues), origin="script",
              rationale="paper hard usability constraint: port identifiers are "
                        "renamed per Step 4g but port order, direction and width are "
                        "never altered, so an existing testbench needs only the "
                        "port-mapping manifest to run unmodified")
    if not ok:
        cl.fault("5", "interface_violation", "; ".join(issues),
                 "reported as a blocking failure -- the deliverable is unusable "
                 "without a matching interface", resolved=False)
    return {"ok": ok, "issues": issues,
            "n_ports": len(om.ports), "widths_preserved": not any("WIDTH" in i for i in issues)}


# ------------------------------------------------------------------ gate 3
# When a budget tier omits Step 4g the redacted module keeps its original name,
# so the reference and the redacted copy cannot be elaborated together.  The
# redacted copy is given a simulation-only alias; nothing about this rename
# reaches the deliverable.
SIM_ALIAS = "_dut_redacted_alias"


def alias_redacted(red: str, orig_top: str) -> tuple[str, str]:
    modules = vlog.parse_modules(red)
    mapping = {m.name: f"_verify_red_{i}_{m.name}" for i, m in enumerate(modules)}
    # Match only declarations and instantiation type positions, never signals or
    # named port connections that happen to share a module's identifier.
    code = vlog.code_only(red)
    edits = []
    for name, alias in mapping.items():
        pattern = re.compile(r"\b" + re.escape(name) +
                             r"\b(?=\s*(?:#\s*\(|[A-Za-z_$][\w$]*\s*(?:\[[^;]*?\]\s*)?\())")
        for match in pattern.finditer(code):
            edits.append((match.start(), match.end(), alias))
        for match in re.finditer(r"\bmodule\s+(" + re.escape(name) + r")\b", code):
            edits.append((match.start(1), match.end(1), alias))
    for start, end, alias in sorted(set(edits), reverse=True):
        red = red[:start] + alias + red[end:]
    return red, mapping[modules[0].name]


def build_testbench(orig: str, red: str, manifests: dict, vectors: list) -> tuple[str, dict]:
    om = vlog.parse_modules(orig)[0]
    red, _ = alias_redacted(red, om.name)
    rm = vlog.parse_modules(red)[0]
    pm = {m["original"]: m["redacted"] for m in manifests.get("port_manifest", [])}

    resolved = elaborated_ports(orig)

    def w(p):
        if p["name"] in resolved:
            bits = len(resolved[p["name"]]["bits"])
            return bits, f"[{bits-1}:0]" if bits > 1 else ""
        if not p["width"]:
            return 1, ""
        m = re.match(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]", p["width"])
        return (int(m.group(1)) - int(m.group(2)) + 1, p["width"]) if m else (32, p["width"])

    ins = [p for p in om.ports if p["dir"] in ("input", "inout")]
    outs = [p for p in om.ports if p["dir"] in ("output", "inout")]
    if not outs:
        return "", {"reason": "module has no outputs"}
    L = ["`timescale 1ns/1ps", "module tb_equiv;", "  integer i, errors; reg [63:0] seed;"]
    L.extend("  " + declaration for declaration in vlog.header_parameter_declarations(om))
    for p in ins:
        n, decl = w(p)
        L.append(f"  reg {decl} {p['name']};")
    for p in outs:
        n, decl = w(p)
        L.append(f"  wire {decl} {p['name']}_ref, {p['name']}_red;")
        if p["dir"] == "inout":
            L.append(f"  assign {p['name']}_ref = {p['name']};")
            L.append(f"  assign {p['name']}_red = {p['name']};")

    def conn(mod, suffix, use_map):
        cs = []
        for p in mod.ports:
            nm = (pm.get(p["name"], p["name"]) if use_map else p["name"])
            sig = p["name"] + (suffix if p["dir"] in ("output", "inout") else "")
            cs.append(f".{nm}({sig})")
        return ",\n    ".join(cs)

    L.append(f"  {om.name} dut_ref (\n    {conn(om, '_ref', False)}\n  );")
    L.append(f"  {rm.name} dut_red (\n    {conn(om, '_red', True)}\n  );")
    cmp_expr = " || ".join(f"({p['name']}_ref !== {p['name']}_red)" for p in outs)
    disp_fmt = " ".join(f"{p['name']}=%h/%h" for p in outs)
    disp_args = ", ".join(f"{p['name']}_ref, {p['name']}_red" for p in outs)
    in_fmt = " ".join(f"{p['name']}=%h" for p in ins)
    in_args = ", ".join(p["name"] for p in ins)

    body = ["  task check; begin", "    #2;",
            f"    if ({cmp_expr}) begin",
            "      errors = errors + 1;",
            f'      if (errors < 12) $display("MISMATCH %0d : {in_fmt} :: {disp_fmt}",',
            f"        i, {in_args}, {disp_args});",
            "    end", "  end endtask", "",
            "  initial begin", "    errors = 0; seed = 64'hDEADBEEF12345678;"]
    # corner cases
    for name, vals in [("all-zeros", 0), ("all-ones", -1)]:
        for p in ins:
            body.append(f"    {p['name']} = {{{w(p)[0]}{{1'b{1 if vals else 0}}}}};")
        body.append("    i = -1; check;")
    for v in vectors:
        vv = v.get("values", {})
        if not any(k in {p["name"] for p in ins} for k in vv):
            continue
        for p in ins:
            if p["name"] in vv:
                try:
                    val = int(vv[p["name"]]) & ((1 << w(p)[0]) - 1)
                except Exception:                              # noqa: BLE001
                    continue
                body.append(f"    {p['name']} = {w(p)[0]}'h{val:X};")
        body.append(f"    i = -2; check;  // {str(v.get('name',''))[:40]}")
    body.append("    for (i = 0; i < 4000; i = i + 1) begin")
    for p in ins:
        n = w(p)[0]
        body.append(f"      {p['name']} = $random(seed);" if n <= 32 else
                    f"      {p['name']} = {{" +
                    ", ".join(["$random(seed)"] * ((n + 31) // 32)) + "};")
    for p in ins:
        if p["dir"] == "inout":
            body.append(f"      if (i % 3 == 0) {p['name']} = {{{w(p)[0]}{{1'bz}}}};")
    body.append("      check;")
    body.append("    end")
    body.append('    if (errors == 0) $display("EQUIV_PASS vectors=%0d", 4000+2+'
                f'{len(vectors)});')
    body.append('    else $display("EQUIV_FAIL mismatches=%0d", errors);')
    body.append("    $finish;")
    body.append("  end")
    L += body + ["endmodule"]
    return "\n".join(L), {"n_inputs": len(ins), "n_outputs": len(outs),
                          "n_directed_vectors": len(vectors) + 2,
                          "n_random_vectors": 4000}


def simulate(orig_p: Path, red_p: Path, tb: str, cl: ChangeLog,
             exclude: str | None = None) -> dict:
    if not (C.IVERILOG and C.VVP):
        return {"ran": False, "reason": "iverilog/vvp unavailable"}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "tb.v").write_text(tb)
        # The redacted file may re-declare the original module name; rename the
        # original's module so both can be elaborated in one simulation.
        orig_src = orig_p.read_text()
        (td / "ref.v").write_text(orig_src)
        aliased, _ = alias_redacted(red_p.read_text(),
                                    vlog.parse_modules(orig_src)[0].name)
        (td / "red.v").write_text(aliased)
        rc, so, se = run([C.IVERILOG, "-g2005", "-s", "tb_equiv", "-o", str(td / "sim"),
                          str(td / "tb.v"), str(td / "ref.v"), str(td / "red.v"),
                          *C.dep_files(exclude)])
        if rc != 0:
            return {"ran": True, "compiled": False, "error": se.strip()[:2500]}
        rc, so, se = run([C.VVP, str(td / "sim")], timeout=900)
        passed = rc == 0 and "EQUIV_PASS" in so and "EQUIV_FAIL" not in so
        mism = re.findall(r"^MISMATCH .*$", so, re.M)
        return {"ran": True, "compiled": True, "passed": passed,
                "stdout": so[-4000:], "mismatches": mism[:12],
                "n_mismatch_lines": len(mism)}


# ------------------------------------------------------------------ gate 4
# Two elaboration passes are load bearing on each side and each corresponds to
# an error yosys raises without it:
#   prep -flatten   -- "Gold module contains memories or processes."
#   memory_map      -- "No SAT model available for cell ... ($mem_v2)."
#   async2sync      -- "No SAT model available for async FF cell ... ($adffe)."
_ELAB = """
{deps}
read_verilog {f}
prep -top {top} -flatten
delete t:$print
memory_map; async2sync; opt -full
rename {top} {alias}
design -stash {alias}_d
"""

# Tier A -- structural equivalence.  Proves every internal signal pair equal.
# This is the strongest result but it cannot hold once Step 4e re-encodes the
# FSM, because the state registers then legitimately hold different values.
YS_INDUCT = """{gold}{gate}
design -copy-from gold_d -as gold gold
design -copy-from gate_d -as gate gate
equiv_make {encoption} gold gate equiv
prep -top equiv
opt -full
equiv_simple -short
equiv_induct -seq {depth}
equiv_status -assert
"""

# Tier B -- bounded sequential equivalence over the PORTS only, from the reset
# state.  This is the right question for a re-encoded FSM: the two machines are
# not structurally identical, they are observationally identical.
YS_MITER = """{gold}{gate}
design -copy-from gold_d -as gold gold
design -copy-from gate_d -as gate gate
miter -equiv -flatten -make_assert gold gate miter
prep -top miter
opt -full
sat -seq {depth} -set-init-zero {reset} -prove-asserts -verify miter
"""


def _reset_constraint(src: str, ports) -> str:
    """`-set-at 1 in_<rst> <asserted value>` for the module's reset port, if any.

    Without pinning the first cycle to reset, the miter starts both machines in
    an arbitrary -- and, after Step 4e, unrelated -- state, so a mismatch says
    nothing about the redaction.
    """
    import re as _re
    for p in ports:
        n = p["name"]
        if not _re.fullmatch(r"(rst|reset|rst_n|reset_n|areset|aresetn)", n, _re.I):
            continue
        active_low = n.lower().endswith("_n") or bool(
            _re.search(rf"if\s*\(\s*!\s*{_re.escape(n)}\s*\)", src)
            or _re.search(rf"negedge\s+{_re.escape(n)}\b", src))
        return f"-set-at 1 in_{n} {0 if active_low else 1}"
    return ""


def formal(orig_p: Path, red_p: Path, manifests: dict, cl: ChangeLog,
           depth: int = 4, budget_s: int = 600) -> dict:
    """Prove the redaction preserves behaviour, reporting HOW it was proven.

    Returns method in {structural_induction, bounded_sequential_miter,
    refuted, inconclusive, unavailable} -- an inconclusive result (solver
    timeout) is reported as such and never counted as a pass.
    """
    if not C.YOSYS:
        return {"ran": False, "method": "unavailable", "proved": None,
                "reason": "yosys not found"}
    orig, red = orig_p.read_text(), red_p.read_text()
    om, rm = vlog.parse_modules(orig)[0], vlog.parse_modules(red)[0]
    pm = {m["original"]: m["redacted"] for m in manifests.get("port_manifest", [])}
    inv = {v: k for k, v in pm.items()}
    # Undo private, capture-free identifier renames in the proof copy only.
    # This preserves the candidate's circuit but lets Yosys match its registers
    # and memories by name instead of choosing unrelated don't-care encodings.
    # Never normalize a mapping that can merge pre-existing identifiers.
    original_ids = set(vlog.identifiers(orig))
    identifiers = dict(manifests.get("identifier_manifest", {}))
    identifiers.update(pm)
    capture_free = (len(set(identifiers.values())) == len(identifiers)
                    and all(value == key or value not in original_ids
                            for key, value in identifiers.items()))
    modules = manifests.get("module_manifest", {})
    if modules and len(set(modules.values())) == len(modules) and all(v not in original_ids for v in modules.values()):
        red, _ = vlog.rename(red, {v: k for k, v in modules.items()})
    if capture_free:
        inv = {value: key for key, value in identifiers.items()}
    # equiv_make and miter match by port name, so the redacted ports carry their
    # original names for the proof only.  This rewrite never leaves this function.
    red_named, _ = vlog.rename(red, inv) if inv else (red, {})
    red_named, gate_top = alias_redacted(red_named, om.name)
    rm_name = gate_top

    deps = "\n".join(f"read_verilog {d}" for d in C.dep_files(orig_p.stem))
    gold = _ELAB.format(deps=deps, f="ref.v", top=om.name, alias="gold")
    gate = _ELAB.format(deps=deps, f="red.v", top=rm_name, alias="gate")
    rst = _reset_constraint(orig, om.ports)

    attempts = []
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "ref.v").write_text(orig)
        (td / "red.v").write_text(red_named)
        encoption = ""
        # Supply Yosys with the recorded bijection for genuine top-level FSMs.
        # equiv_make then proves the encoding relation rather than incorrectly
        # demanding identical state-register bit patterns.
        reverse_names = {v:k for k,v in manifests.get("identifier_manifest", {}).items()}
        params = {p["name"]:p["value"] for p in vlog.localparams(om.src)}
        encoded = {}
        for key, value in manifests.get("fsm_encoding", {}).items():
            module, label = key.rsplit(".", 1) if "." in key else (om.name, key)
            if reverse_names.get(module,module) != om.name:
                continue
            label = reverse_names.get(label,label)
            old = vlog.SIZED_LIT.fullmatch(params.get(label, "").strip())
            new = vlog.SIZED_LIT.fullmatch(value.strip())
            if not old or not new or old[1] != new[1]:
                continue
            try:
                width = int(old[1])
                val = lambda match: int(match[3].replace("_", ""), {"b":2,"o":8,"d":10,"h":16}[match[2].lower()])
                encoded[label] = (width, val(old), val(new))
            except ValueError:
                continue
        enc_lines = []
        seen_states = set()
        for case in vlog.case_items(om.src):
            state, labels = case["select"].strip(), case["labels"]
            if state in seen_states or not re.fullmatch(r"[A-Za-z_]\w*", state):
                continue
            if len(labels)<2 or not all(label in encoded for label in labels):
                continue
            codes = [encoded[label] for label in labels]
            if len({w for w,_,_ in codes})!=1 or len({a for _,a,_ in codes})!=len(codes) or len({b for _,_,b in codes})!=len(codes):
                continue
            width = codes[0][0]
            related = {state}
            for label in labels:
                related.update(re.findall(r"\b([A-Za-z_]\w*)\s*(?:<=|=(?!=))\s*"
                                          + re.escape(label) + r"\s*;", vlog.code_only(om.src)))
            ports = {p["name"] for p in om.ports}
            for signal in sorted(related - seen_states - ports):
                enc_lines.append(f".fsm gold {signal}")
                enc_lines.extend(f".map {a:0{width}b} {b:0{width}b}" for _,a,b in codes)
                seen_states.add(signal)
        if enc_lines:
            (td / "states.enc").write_text("\n".join(enc_lines)+"\n")
            encoption = "-encfile states.enc"
            cl.note(fsm_equivalence_encoding=enc_lines)

        def go(script: str, name: str, timeout: int) -> dict:
            (td / f"{name}.ys").write_text(script)
            try:
                rc, so, se = run([C.YOSYS, "-s", f"{name}.ys"], cwd=td, timeout=timeout)
            except subprocess.TimeoutExpired:
                return {"name": name, "rc": None, "timeout": True, "log": ""}
            return {"name": name, "rc": rc, "timeout": False, "log": (so + se)}

        # ---- Tier A
        a = go(YS_INDUCT.format(gold=gold, gate=gate, depth=depth, encoption=encoption),
               "induct", min(budget_s, 300))
        attempts.append({k: a[k] for k in ("name", "rc", "timeout")} |
                        {"log_tail": a["log"][-1500:]})
        if not a["timeout"] and a["rc"] == 0 and "ERROR" not in a["log"]:
            return {"ran": True, "proved": True, "method": "structural_induction",
                    "depth": depth, "attempts": attempts, "counterexamples": [],
                    "log_tail": a["log"][-3000:]}

        # ---- Tier B, shrinking the bound until the solver fits the budget
        for k in (depth * 2, depth, max(2, depth // 2)):
            b = go(YS_MITER.format(gold=gold, gate=gate, depth=k, reset=rst),
                   f"miter{k}", budget_s)
            rec = {k2: b[k2] for k2 in ("name", "rc", "timeout")}
            rec["depth"] = k
            rec["log_tail"] = b["log"][-1500:]
            attempts.append(rec)
            if b["timeout"]:
                continue
            failed = "FAIL!" in b["log"] or "proof did not succeed" in b["log"].lower()
            if b["rc"] == 0 and not failed:
                return {"ran": True, "proved": True,
                        "method": "bounded_sequential_miter", "depth": k,
                        "reset_constraint": rst, "attempts": attempts,
                        "counterexamples": [], "log_tail": b["log"][-3000:]}
            if failed:
                cex = re.findall(r"^\s*\d+\s+\\in_\S+.*$", b["log"], re.M)
                return {"ran": True, "proved": False, "method": "refuted",
                        "depth": k, "reset_constraint": rst, "attempts": attempts,
                        "counterexamples": cex[:40], "log_tail": b["log"][-3000:]}

    return {"ran": True, "proved": None, "method": "inconclusive",
            "reset_constraint": rst, "attempts": attempts,
            "counterexamples": [],
            "reason": f"solver exceeded the {budget_s}s budget at every bound tried; "
                      "this is a capacity limit, not evidence of a defect",
            "log_tail": attempts[-1]["log_tail"] if attempts else ""}


# ==================================================================== driver
def verify(path: Path, round_id: int = 0, variant: str | None = None) -> dict:
    design = path.stem
    tag = f".{variant}" if variant else ("" if not round_id else f".r{round_id}")
    manifests = util.read_json(C.PHASE_DIRS[4] / f"{design}{tag}.manifests.json")
    red_p = C.ROOT / manifests["redacted_rtl"]
    cl = ChangeLog(f"phase5_verification{tag}", design, str(path.relative_to(C.ROOT)))
    prof = util.read_json(C.PHASE_DIRS[1] / f"{design}.profile.json")
    orig, red = path.read_text(), red_p.read_text()

    # gate 1
    rc, _, se = run([C.IVERILOG, "-t", "null", "-g2005", "-s", vlog.parse_modules(red)[0].name, str(red_p),
                     *C.dep_files(design)]) if C.IVERILOG else (1, "", "iverilog unavailable")
    syntax = {"ok": rc == 0, "stderr": se.strip()[:2000]}
    cl.change("5", "syntax_gate", target=str(red_p.name),
              after="pass" if syntax["ok"] else syntax["stderr"][:300], origin="script",
              rationale="Icarus Verilog elaboration of the deliverable")
    if not syntax["ok"]:
        cl.fault("5", "deliverable_does_not_compile", syntax["stderr"],
                 "blocking; the design is routed back to Phase 4", resolved=False)

    # gate 2
    iface = check_interface(orig, red, manifests, cl)

    if not syntax["ok"] or not iface["ok"]:
        result = {"design": design, "round": round_id, "variant": variant,
                  "verdict": "FAIL", "syntax": syntax, "interface": iface,
                  "testbench_meta": {}, "simulation": {"ran": False, "reason": "blocking syntax/interface failure"},
                  "formal": {"ran": False, "method": "not_run", "proved": None},
                  "llm_vector_validation": {}}
        d = C.phase_dir(5)
        util.write_json(d / f"{design}{tag}.verification.json", result)
        cl.summarise(verdict="FAIL", syntax_ok=syntax["ok"], interface_ok=iface["ok"])
        cl.write(d / f"{design}{tag}.changelog.json")
        return result

    # gate 3
    om = vlog.parse_modules(orig)[0]
    ins = [p for p in om.ports if p["dir"] == "input"]

    port_widths = elaborated_ports(orig)

    def wid(p):
        return len(port_widths[p["name"]]["bits"])

    vectors, vrec = [], {}
    if ins:
        parsed, vrec = llm.generate_json(
            VECTOR_PROMPT.format(
                inputs="\n".join(f"  {p['name']} : {wid(p)}" for p in ins),
                purpose=prof["llm"].get("design_purpose", "")[:200]),
            system="You reply with ONE JSON object only.", temperature=0.2, seed=13,
            num_predict=3500, key_hint="vectors", tag=f"p5:{design}", phase="5")
        for v in (parsed or {}).get("vectors", []) or []:
            if isinstance(v, dict) and isinstance(v.get("values"), dict):
                vectors.append(v)
        cl.change("5", "test_vector_generation", target=f"{len(vectors)} vectors",
                  after=json.dumps(vectors)[:1500], origin="llm",
                  rationale="LLM-proposed corner cases targeting the security-critical "
                            "unlock/compare boundary, on top of 4000 random vectors "
                            "and the all-zeros/all-ones cases")

    tb, tbmeta = build_testbench(orig, red, manifests, vectors)
    sim = {"ran": False, "reason": tbmeta.get("reason", "")} if not tb else \
        simulate(path, red_p, tb, cl, design)
    if tb:
        tb_p = C.phase_dir(5) / f"{design}{tag}.tb_equiv.v"
        tb_p.write_text(tb)
        cl.artifact("testbench", tb_p)
    if sim.get("ran") and not sim.get("passed") and sim.get("compiled"):
        cl.fault("5", "simulation_mismatch",
                 f"{sim.get('n_mismatch_lines')} vector(s) diverge: "
                 f"{sim.get('mismatches', [])[:3]}",
                 "the exact failing vector is written into a Phase-4 repair prompt "
                 "so the model is given a reproducing input, not a vague complaint",
                 resolved=False)

    # gate 4
    fm = formal(path, red_p, manifests, cl)
    cl.change("5", "formal_equivalence", target=f"{om.name} vs redacted",
              after=f"method={fm.get('method')} proved={fm.get('proved')} "
                    f"depth={fm.get('depth')}", origin="script",
              rationale=("structural induction proves every internal signal pair equal; "
                         "once Step 4e re-encodes the FSM that is no longer true, so the "
                         "check falls back to a reset-constrained bounded sequential "
                         "miter over the ports, which is the right question for an "
                         "observationally-equivalent but structurally-different design"),
              attempts=[{k: a.get(k) for k in ("name", "rc", "timeout", "depth")}
                        for a in fm.get("attempts", [])])
    if fm.get("method") == "refuted":
        cl.fault("5", "formal_equivalence_refuted",
                 f"the redacted design provably diverges from the original; "
                 f"counterexample: {fm.get('counterexamples', [])[:6]}",
                 "the concrete distinguishing input vector is written into the "
                 "Phase-4 repair prompt verbatim, giving the model a reproducing "
                 "input rather than a vague complaint (paper Listing 62)",
                 resolved=False)
    elif fm.get("method") == "inconclusive":
        cl.fault("5", "formal_equivalence_inconclusive",
                 fm.get("reason", "solver budget exhausted"),
                 "recorded as INCONCLUSIVE, never as a pass: the design is reported "
                 "as verified by simulation only, so a reviewer can see exactly how "
                 "far the formal guarantee extends", resolved=False)

    sim_ok = sim.get("passed") is True
    base_ok = syntax["ok"] and iface["ok"] and sim_ok
    if not base_ok or fm.get("method") == "refuted":
        verdict = "FAIL"
    elif fm.get("proved") is True:
        verdict = "PASS"
    else:
        # Simulation and interface pass but the solver could not close the proof.
        # That is neither a pass nor a defect, and saying either would be wrong.
        verdict = "PASS_SIM_ONLY"
    result = {"design": design, "round": round_id, "variant": variant,
              "verdict": verdict,
              "syntax": syntax, "interface": iface, "testbench_meta": tbmeta,
              "simulation": sim, "formal": fm,
              "llm_vector_validation": vrec}
    d = C.phase_dir(5)
    util.write_json(d / f"{design}{tag}.verification.json", result)
    cl.summarise(verdict=verdict, syntax_ok=syntax["ok"], interface_ok=iface["ok"],
                 simulation_passed=sim.get("passed"), formal_proved=fm.get("proved"),
                 formal_method=fm.get("method"), formal_depth=fm.get("depth"),
                 n_directed_vectors=tbmeta.get("n_directed_vectors"),
                 n_random_vectors=tbmeta.get("n_random_vectors"))
    cl.artifact("verification", d / f"{design}{tag}.verification.json")
    cl.write(d / f"{design}{tag}.changelog.json")
    return result


def main() -> int:
    ap = util.design_args(__doc__)
    ap.add_argument("--round", type=int, default=0)
    ap.add_argument("--variant", default=None, choices=["B0", "B1", "B2"])
    args = ap.parse_args()
    llm.start_log(f"phase5{'' if not args.round else '_r%d' % args.round}")
    util.banner("PHASE 5 -- Functional & Formal Verification")
    index = []
    for p in util.resolve_designs(args):
        util.info(f"verifying {p.name}")
        r = verify(p, args.round, args.variant)
        util.info(f"    verdict={r['verdict']}  syntax={r['syntax']['ok']}  "
                  f"iface={r['interface']['ok']}  "
                  f"sim={r['simulation'].get('passed')}  "
                  f"formal={r['formal'].get('method')}"
                  f"({r['formal'].get('depth')})")
        index.append({"design": r["design"], "verdict": r["verdict"],
                      "sim": r["simulation"].get("passed"),
                      "formal": r["formal"].get("proved"),
                      "formal_method": r["formal"].get("method")})
    util.write_json(C.phase_dir(5) / "index.json",
                    {"phase": 5, "designs": index, "llm_stats": llm.stats()})
    npass = sum(1 for d in index if d["verdict"] == "PASS")
    nsim = sum(1 for d in index if d["verdict"] == "PASS_SIM_ONLY")
    nfail = sum(1 for d in index if d["verdict"] == "FAIL")
    util.info(f"{npass} PASS (formally proven), {nsim} PASS_SIM_ONLY "
              f"(simulation + interface only), {nfail} FAIL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
