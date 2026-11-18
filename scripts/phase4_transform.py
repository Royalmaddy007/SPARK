#!/usr/bin/env python3
"""Phase 4 -- GenAI-Assisted RTL Transformation (Steps 4a-4l).

Runs the transformation steps selected by the Phase-3 budget tier, in order, each
one recording every individual edit into the change log with before/after text.

Step ownership
--------------
  4a module extraction              script (closure-aware), LLM names the child
  4b name anonymisation             script (HMAC-keyed), verified by grep -w
  4c algebraic constant masking     script (algebraically checked)
  4d comparison chain obfuscation   script
  4e FSM state re-encoding          script (collision- and reset-checked)
  4f final structural pass          script + LLM residual-leakage scan
  4g I/O port name obfuscation      script, manifest retained privately
  4h arithmetic structural decomp.  script (ripple-carry expansion)
  4i misleading comment injection   LLM (false identity + annotations)
  4i* CoT-aware comment steering    LLM (attacker reasoning trace elicited first)
  4j decoy crown-jewel injection    LLM narrative + script-built inert cone
  4k non-idiomatic style transfer   script
  4l SCA-aware mask rotation        script only, by explicit paper mandate

Every step is followed by an Icarus Verilog syntax gate; a step whose output
fails to compile is rolled back and logged as a fault rather than propagated.
"""
from __future__ import annotations
import copy, json, random, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, llm, vlog, util
from great import transforms as T
from great.changelog import ChangeLog


# --------------------------------------------------------------------- gate
def compiles(src: str, extra: str = "", exclude: str | None = None) -> tuple[bool, str]:
    if not C.IVERILOG:
        return False, "iverilog unavailable -- cannot validate transformation"
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "u.v"
        f.write_text(src + "\n" + extra)
        r = subprocess.run([C.IVERILOG, "-t", "null", "-g2005", "-s", vlog.parse_modules(src)[0].name, str(f),
                            *C.dep_files(exclude)], capture_output=True, text=True)
        return r.returncode == 0, r.stderr.strip()[:1500]


class Stage:
    """Applies one step and rolls it back if the syntax gate fails."""

    def __init__(self, cl: ChangeLog, state: dict):
        self.cl, self.state = cl, state
        self.outcomes = []

    _KEEP = ("rtl", "rng", "high_lines")

    def _rollback(self, before: str, snapshot: dict) -> None:
        # Restore the RTL and every snapshotted key, AND drop any key the step
        # newly introduced.  A step that adds a manifest key (`port_manifest`,
        # `rename_map`, ...) and is then rolled back must not leave that
        # bookkeeping behind, or the manifest would claim renames that never
        # reached the deliverable -- exactly what breaks the Phase-5 interface
        # check on hierarchical designs.
        self.state["rtl"] = before
        for k in [k for k in self.state
                  if k not in snapshot and k not in self._KEEP]:
            del self.state[k]
        for k, v in snapshot.items():                     # e.g. `aux`, manifests
            self.state[k] = v

    def apply(self, step: str, fn):
        before = self.state["rtl"]
        snapshot = copy.deepcopy({k: v for k, v in self.state.items()
                                  if k not in self._KEEP})
        try:
            fn()
        except Exception as exc:                          # noqa: BLE001
            self._rollback(before, snapshot)
            self.cl.fault(step, "step_exception", f"{type(exc).__name__}: {exc}",
                          "step rolled back; the pipeline continues with the "
                          "pre-step RTL so one failing transformation cannot "
                          "destroy the deliverable", resolved=True)
            self.outcomes.append({"step": step, "status": "rolled_back", "reason": "exception"})
            return False
        ok, err = compiles(self.state["rtl"], self.state.get("aux", ""),
                           self.state.get("design"))
        if not ok:
            self._rollback(before, snapshot)
            self.cl.fault(step, "syntax_gate_failure",
                          f"Icarus rejected the output of step {step}: {err}",
                          "step rolled back to the last compiling RTL "
                          "(paper: Icarus is run on every output immediately "
                          "after the transformation)", resolved=True)
            self.outcomes.append({"step": step, "status": "rolled_back", "reason": "syntax"})
            return False
        if before != self.state["rtl"]:
            # Syntax alone cannot establish that a width-sensitive rewrite is
            # safe. Use independent reference/candidate elaborations and reject
            # a step as soon as differential simulation finds a counterexample.
            import phase5_verify as verifier
            after = self.state["rtl"]
            op, rp = vlog.parse_modules(before)[0].ports, vlog.parse_modules(after)[0].ports
            manifest = {"port_manifest": [{"original": a["name"], "redacted": b["name"]}
                                          for a, b in zip(op, rp)]}
            try:
                interface = verifier.check_interface(before, after, manifest, self.cl)
                tb, meta = verifier.build_testbench(before, after, manifest, [])
                with tempfile.TemporaryDirectory() as folder:
                    a, b = Path(folder) / "before.v", Path(folder) / "after.v"
                    a.write_text(before); b.write_text(after)
                    result = verifier.simulate(a, b, tb, self.cl, self.state.get("design")) if tb else meta
                safe = interface["ok"] and result.get("passed", False)
            except Exception as exc:
                safe, result = False, {"error": str(exc)}
            checkpoint = C.phase_dir(4) / "checkpoints" / self.state.get("design", "unknown")
            checkpoint.mkdir(parents=True, exist_ok=True)
            reference_path, candidate_path = checkpoint / f"{step}.reference.v", checkpoint / f"{step}.candidate.v"
            reference_path.write_text(before)
            candidate_path.write_text(after)
            util.write_json(checkpoint / f"{step}.gate.json", {"accepted": safe, "simulation": result,
                                                               "port_manifest": manifest["port_manifest"]})
            self.cl.artifact(f"{step}_reference", reference_path)
            self.cl.artifact(f"{step}_candidate", candidate_path)
            self.cl.change(step, "step_equivalence_simulation", after=result, origin="script")
            if not safe:
                self._rollback(before, snapshot)
                self.cl.fault(step, "step_equivalence_gate_failure", json.dumps(result),
                              "transformation rolled back; final independent simulation and formal verification remain mandatory",
                              resolved=True)
                self.outcomes.append({"step": step, "status": "rolled_back", "reason": "equivalence"})
                return False
        self.outcomes.append({"step": step, "status": "applied" if before != self.state["rtl"] else "no_change"})
        return True


# ================================================================== Step 4a
def step_4a(st: dict, cl: ChangeLog) -> None:
    """Closure-aware extraction of HIGH logic into an anonymised child module."""
    src, strat = st["rtl"], st["strategy"]
    high = st["high"]
    if not high:
        return
    mods = vlog.parse_modules(src)
    if len(mods) != 1:
        cl.fault("4a", "multi_module_source",
                 f"source declares {len(mods)} modules; hierarchy extraction is only "
                 "attempted on single-module files",
                 "step skipped -- the design already has a hierarchy that hides the "
                 "sensitive cone", resolved=True)
        return
    top = mods[0]
    port_names = {p["name"] for p in top.ports}

    # The extraction set: HIGH signals plus their dependency closure, minus the
    # top-level ports (which must stay on the boundary, renamed in 4g).
    extract = (high | set(strat["also_extract_closure"])) - port_names
    if not extract:
        return

    decls = vlog.declarations(src)
    cs = vlog.code_only(src)
    body_start, body_end = top.header_end, top.end - len("endmodule")

    # Collect the statements that must move: declarations of extracted signals and
    # continuous assignments whose LHS is extracted.  Procedural blocks are left in
    # place -- moving an always block requires moving its clock domain, which is the
    # single largest source of the paper's extraction faults.
    moves: list[tuple[int, int, str]] = []
    moved_names: set[str] = set()
    for d in decls:
        if d["kw"] in ("input", "output", "inout"):
            continue
        if d["start"] < body_start or d["end"] > body_end:
            continue
        names = set(d["names"])
        if names and names <= extract and d["kw"] in ("wire", "localparam", "parameter"):
            moves.append((d["start"], d["end"], src[d["start"]:d["end"]]))
            moved_names |= names
    for m in vlog.ASSIGN.finditer(cs):
        if not (body_start <= m.start() < body_end):
            continue
        lhs = vlog._lhs_name(m.group("lhs"))
        if lhs in extract:
            moves.append((m.start(), m.end(), src[m.start():m.end()]))
            moved_names.add(lhs)
    if not moves:
        cl.fault("4a", "nothing_extractable",
                 "no self-contained declaration or continuous assignment was fully "
                 "inside the HIGH closure",
                 "step skipped; the sensitive logic is protected by 4b/4c/4d/4e "
                 "in place instead", resolved=True)
        return

    moves.sort()
    child_name = st["child_name"]
    moved_text = "\n".join(t.strip() for _, _, t in moves)
    moved_ids = {i for i in vlog.IDENT.findall(vlog.code_only(moved_text))
                 if i not in vlog.KEYWORDS and not i[0].isdigit()}

    # Port synthesis.  Direction is derived from *dataflow*, not from naming or
    # position -- the mitigation for the paper's "wrong port direction" fault.
    remaining = src[:moves[0][0]] + "".join(
        src[a:b] for (_, a), (b, _) in zip([(0, moves[0][1])] + [(0, e) for _, e, _ in moves[:-1]],
                                           [(s, 0) for s, _, _ in moves[1:]] + [(body_end, 0)]))
    remaining_cs = vlog.code_only(remaining)
    remaining_ids = {i for i in vlog.IDENT.findall(remaining_cs)
                     if i not in vlog.KEYWORDS and not i[0].isdigit()}

    child_ports = []
    for name in sorted(moved_ids):
        if name == top.name or name in ("clk", "reset_n", "rst", "rst_n"):
            if name in port_names:
                child_ports.append({"name": name, "dir": "input",
                                    "width": _width_of(decls, top, name)})
            continue
        if name in moved_names:
            # driven inside the child.  Output only if the parent still reads it.
            if name in remaining_ids:
                child_ports.append({"name": name, "dir": "output",
                                    "width": _width_of(decls, top, name)})
        elif name in remaining_ids or name in port_names:
            child_ports.append({"name": name, "dir": "input",
                                "width": _width_of(decls, top, name)})

    # Duplicated-declaration fault: any moved signal that the parent still declares
    # locally AND that is now a child output must lose its parent declaration.
    child_outputs = {p["name"] for p in child_ports if p["dir"] == "output"}
    dup = []
    keep_moves = list(moves)
    for d in decls:
        if d["kw"] in ("wire", "reg") and set(d["names"]) & child_outputs \
                and body_start <= d["start"] < body_end \
                and not any(a <= d["start"] < b for a, b, _ in moves):
            dup.append((d["start"], d["end"], set(d["names"]) & child_outputs))
    if dup:
        cl.fault("4a", "duplicated_declaration",
                 f"{len(dup)} signal(s) would be declared both as a child output port "
                 f"and as a local net in the parent: "
                 f"{sorted({n for _, _, ns in dup for n in ns})}",
                 "symbol-table diff computed after extraction; the leftover top-level "
                 "declaration is deleted before the linter runs (paper Listing 24)")

    cuts = sorted([(a, b) for a, b, _ in keep_moves] + [(a, b) for a, b, _ in dup])
    new_top_body = []
    pos = body_start
    for a, b in cuts:
        new_top_body.append(src[pos:a]); pos = b
    new_top_body.append(src[pos:body_end])

    inst = [f"\n  // Extracted sensitive logic cone (Step 4a).",
            f"  {child_name} u_{child_name.lstrip('_')} ("]
    inst += [f"    .{p['name']}({p['name']})," for p in child_ports[:-1]]
    if child_ports:
        inst.append(f"    .{child_ports[-1]['name']}({child_ports[-1]['name']})")
    inst.append("  );\n")

    # The parent must still declare, as plain wires, the child outputs it reads.
    reads = sorted(n for n in child_outputs if n in remaining_ids)
    wire_decls = [f"  wire {_width_of(decls, top, n) or ''} {n};".replace("  ", " ")
                  for n in reads]

    child_hdr = [f"\nmodule {child_name}("]
    for i, p in enumerate(child_ports):
        comma = "," if i < len(child_ports) - 1 else ""
        w = (p["width"] + " ") if p["width"] else ""
        child_hdr.append(f"  {p['dir']} wire {w}{p['name']}{comma}")
    child_hdr.append(");")
    child = "\n".join(child_hdr) + "\n" + moved_text + "\nendmodule\n"

    st["rtl"] = (src[:body_start] + "\n" + "\n".join(wire_decls) + "\n"
                 + "".join(new_top_body) + "\n".join(inst)
                 + "endmodule\n" + child)
    st["child_ports"] = child_ports
    cl.change("4a", "module_extraction", target=child_name,
              before=moved_text[:1200], after=f"module {child_name} with "
              f"{len(child_ports)} ports ({len(child_outputs)} outputs)",
              origin="script",
              rationale="HIGH-tagged logic plus its transitive dependency closure "
                        "moved into an anonymised child; the top-level port list is "
                        "unchanged at this stage",
              moved_statements=len(moves), moved_signals=sorted(moved_names),
              ports=[{k: p[k] for k in ("name", "dir", "width")} for p in child_ports],
              deleted_duplicate_declarations=[src[a:b].strip() for a, b, _ in dup])


def _width_of(decls, top, name) -> str:
    for p in top.ports:
        if p["name"] == name and p["width"]:
            return p["width"]
    for d in decls:
        if name in d["names"] and d["msb"] is not None:
            return f"[{d['msb']}:{d['lsb']}]"
    return ""


# ================================================================== Step 4b
def step_4b(st: dict, cl: ChangeLog) -> None:
    src = st["rtl"]
    sens = st["sensitivity"]["signals"]
    mods = vlog.parse_modules(src)
    top_ports = {p["name"] for p in mods[0].ports}
    targets = {n for n, v in sens.items()
               if v["tier"] in ("HIGH", "MED") and n not in top_ports
               and n not in ("clk", "reset_n", "rst", "rst_n")}
    lp_names = {l["name"] for l in vlog.localparams(src)}
    present = set(vlog.identifiers(src))
    targets &= present
    if not targets:
        return

    def kind_of(n):
        return "pm" if n in lp_names else ("rg" if _is_reg(src, n) else "sg")

    mapping = T.build_rename_map(targets, kind_of)
    new, counts = vlog.rename(src, mapping)
    st["rtl"] = new
    st["rename_map"] = {**st.get("rename_map", {}), **mapping}

    # Verification pass: grep -w for every original name in the output (paper 4b).
    residual = vlog.residual_occurrences(vlog.code_only(new), mapping)
    if residual:
        cl.fault("4b", "partial_substitution",
                 f"{len(residual)} original identifier(s) survived the rename: "
                 f"{list(residual)[:8]}",
                 "the rename is token-exact over the code span set, so this indicates "
                 "an identifier reachable only through a construct the tokenizer did "
                 "not treat as code; the surviving occurrences are listed verbatim",
                 residual=residual, resolved=False)
    for orig, repl in sorted(mapping.items()):
        cl.change("4b", "identifier_rename", target=orig, before=orig, after=repl,
                  origin="script", occurrences=counts.get(orig, 0),
                  rationale=f"{sens[orig]['tier']}-tier semantic name replaced with a "
                            f"keyed HMAC-SHA256 opaque identifier")
    cl.change("4b", "rename_verification", target="grep -w residual scan",
              after=f"{len(mapping)} identifiers renamed, "
                    f"{sum(counts.values())} occurrences rewritten, "
                    f"{len(residual)} residual hits", origin="script",
              rationale="post-substitution word-boundary scan (paper Step 4b "
                        "mitigation for partial substitution)")


def _is_reg(src, name) -> bool:
    return any(d["kw"] == "reg" and name in d["names"] for d in vlog.declarations(src))


# ================================================================== Step 4c
def step_4c(st: dict, cl: ChangeLog) -> None:
    """Split sensitive literals into (v ^ A) + B chains resolved only at runtime."""
    rng = st["rng"]
    src = st["rtl"]
    high_lines = st["high_lines"](src)
    lits = [l for l in vlog.sized_literals(src)
            if 4 <= l["width"] <= 64 and l["line"] in high_lines]
    # Do not touch literals inside a `case` item label -- those are FSM codes and
    # belong to Step 4e; masking them here would break the case match.
    case_ranges = [(c["start"], c["end"]) for c in vlog.case_items(src)]
    edits, n_skipped = [], 0
    for l in lits:
        if any(a <= l["start"] < b for a, b in case_ranges):
            n_skipped += 1
            continue
        m = T.mask_constant(l["width"], l["value"], rng)
        if not m:
            n_skipped += 1
            continue
        expr = (f"((({T.lit(m['width'], m['masked'])} - {T.lit(m['width'], m['add'])})"
                f" & {T.lit(m['width'], (1 << m['width']) - 1)}) ^ {T.lit(m['width'], m['xor'])})")
        edits.append((l, m, expr))
    if not edits:
        if n_skipped:
            cl.change("4c", "no_maskable_literal", target=f"{n_skipped} candidates",
                      after="skipped", origin="script",
                      rationale="all sensitive literals were FSM case labels (owned by "
                                "Step 4e) or outside the maskable width range")
        return
    out, pos = [], 0
    for l, m, expr in edits:
        out.append(src[pos:l["start"]]); out.append(expr); pos = l["end"]
    out.append(src[pos:])
    st["rtl"] = "".join(out)
    st.setdefault("masked_constants", []).extend(
        {"line": l["line"], "original": l["text"], **{k: m[k] for k in
         ("width", "value", "xor", "add", "masked")}} for l, m, _ in edits)
    for l, m, expr in edits:
        cl.change("4c", "constant_masking", target=l["text"], line=l["line"],
                  before=l["text"], after=expr, origin="script",
                  rationale="literal secret replaced by an algebraically equivalent "
                            "XOR/ADD chain; static extraction now yields the mask, "
                            "not the value",
                  mask={"xor": T.lit(m["width"], m["xor"]),
                        "add": T.lit(m["width"], m["add"]),
                        "masked": T.lit(m["width"], m["masked"])},
                  verified_inverse=True)
    cl.change("4c", "mask_quality_check", target=f"{len(edits)} masks",
              after="all masks non-zero, non-all-ones, Hamming>=3 from the secret",
              origin="script",
              rationale="mitigation for the paper's 'trivial masks' fault: masks of 0, "
                        "all-ones or low Hamming distance are rejected and regenerated")


# ================================================================== Step 4d
CMP = re.compile(r"(?P<lhs>[A-Za-z_]\w*(?:\s*\[[^\]]*\])?)\s*(?P<op>==|!=)\s*"
                 r"(?P<rhs>\d+\s*'\s*[bBoOdDhH][0-9a-fA-F_]+)")


def step_4d(st: dict, cl: ChangeLog) -> None:
    """Replace `x == K` with a cascaded subtract/compare-to-zero chain."""
    src, rng = st["rtl"], st["rng"]
    high_lines = st["high_lines"](src)
    cs = vlog.code_only(src)
    edits = []
    for m in CMP.finditer(cs):
        line = vlog.line_of(src, m.start())
        if line not in high_lines:
            continue
        lit_m = vlog.SIZED_LIT.match(m.group("rhs").replace(" ", ""))
        if not lit_m:
            continue
        w = int(lit_m.group(1))
        if not (4 <= w <= 64):
            continue
        try:
            val = int(lit_m.group(3).replace("_", ""),
                      {"b": 2, "o": 8, "d": 10, "h": 16}[lit_m.group(2).lower()])
        except ValueError:
            continue
        mask = (1 << w) - 1
        x = rng.randrange(1, mask)
        off = rng.randrange(1, mask)
        # (((lhs ^ X) - OFF) & mask) == ((val ^ X) - OFF) & mask
        target = ((val ^ x) - off) & mask
        chain = (f"((((({m.group('lhs')} ^ {T.lit(w, x)}) - {T.lit(w, off)})"
                 f" & {T.lit(w, mask)}) {m.group('op')} {T.lit(w, target)}))")
        # A wider LHS must not be truncated to the literal's width: upper
        # bits distinguish e.g. 8'h20 from 5'h00. The concatenation makes the
        # upper-bit test unsigned even for a signed LHS.
        upper = f"(({{1'b0, {m.group('lhs')}}} >> {w}) {'==' if m.group('op') == '==' else '!='} 0)"
        chain = f"({upper} {'&&' if m.group('op') == '==' else '||'} {chain})"
        edits.append((m.start(), m.end(), m.group(0), chain, line,
                      {"xor": T.lit(w, x), "offset": T.lit(w, off),
                       "target": T.lit(w, target)}))
    if not edits:
        return
    out, pos = [], 0
    for a, b, _, chain, _, _ in edits:
        out.append(src[pos:a]); out.append(chain); pos = b
    out.append(src[pos:])
    st["rtl"] = "".join(out)
    for a, b, before, after, line, meta in edits:
        cl.change("4d", "comparison_chain", target=before, line=line,
                  before=before, after=after, origin="script", chain=meta,
                  rationale="single-line equality against a literal replaced by an "
                            "intermediate XOR/subtract chain, so the compared "
                            "threshold no longer appears in the source")


# ================================================================== Step 4e
def step_4e(st: dict, cl: ChangeLog) -> None:
    # State labels are module-local identifiers. In a combined RTL file the
    # same label (e.g. IDLE) may belong to unrelated machines of different widths.
    src, parts, pos, encodings = st["rtl"], [], 0, {}
    for module in vlog.parse_modules(src):
        local = dict(st, rtl=src[module.start:module.end])
        local.pop("fsm_encoding", None)
        _step_4e_module(local, cl)
        parts.extend([src[pos:module.start], local["rtl"]])
        encodings.update({module.name + "." + name: value
                          for name, value in local.get("fsm_encoding", {}).items()})
        pos = module.end
    parts.append(src[pos:])
    st["rtl"] = "".join(parts)
    if encodings:
        st["fsm_encoding"] = encodings


def _step_4e_module(st: dict, cl: ChangeLog) -> None:
    """Re-encode FSM state localparams to pseudo-random codes and strip the names.

    Order matters: the declarations are deleted FIRST, by source span, and only
    then are the symbolic references substituted.  Substituting first turns
    `localparam CTRL_IDLE = 3'h0;` into `localparam 3'h5 = 3'h0;`, which is a
    syntax error and no longer matches any name-based deletion pattern.
    """
    src, rng = st["rtl"], st["rng"]
    lps = vlog.localparams(src)
    cases = vlog.case_items(src)

    # A `case` whose select expression reads a top-level INPUT is not an FSM --
    # it is an externally-visible decode (a register-address map, a mode-select).
    # Its labels are part of the module's contract with the outside world, and
    # re-encoding them silently changes behaviour: `parameter ADDR_VERSION =
    # 8'h02` compared against an `address` input is the module's address map,
    # not a state code.  Only labels of internally-driven selects are eligible.
    mods = vlog.parse_modules(src)
    inputs = {p["name"] for p in mods[0].ports if p["dir"] in ("input", "inout")}
    eligible, external = set(), set()
    for c in cases:
        sel_ids = {t for t in vlog.IDENT.findall(c["select"])
                   if t not in vlog.KEYWORDS}
        # A case over an instruction/CSR/address decode is not a state
        # machine just because its select is an internal register. Require
        # assignments of the symbolic labels to that select register itself.
        base = c["select"].strip()
        assigned_labels = set()
        if re.fullmatch(r"[A-Za-z_]\w*", base):
            for assignment in re.finditer(r"\b" + re.escape(base) + r"\s*<=\s*([A-Za-z_]\w*)\s*;", vlog.code_only(src)):
                assigned_labels.add(assignment.group(1))
        is_fsm = bool(assigned_labels & set(c["labels"]))
        if sel_ids & inputs or not is_fsm:
            external.update(c["labels"])
        else:
            # Include every symbolic state assignment even when several case
            # items share one source line; partial re-encoding can collide with
            # an untouched state code.
            eligible.update(set(c["labels"]) | assigned_labels)
    external_only = external - eligible
    if external_only:
        cl.fault("4e", "externally_visible_decode_constants",
                 f"{len(external_only)} case label(s) select on a top-level input and "
                 f"are therefore part of the module's external contract, not FSM "
                 f"state: {sorted(external_only)[:10]}",
                 "these are excluded from re-encoding; re-encoding them would change "
                 "the module's address/mode map and break functional equivalence "
                 "while still passing a naive syntax check", resolved=True)

    labels_used = eligible - external
    fsm_lps = [l for l in lps if l["name"] in labels_used
               and vlog.SIZED_LIT.search(l["value"] or "")]
    if not fsm_lps:
        return

    by_width: dict[int, list] = {}
    for l in fsm_lps:
        w = int(vlog.SIZED_LIT.search(l["value"]).group(1))
        by_width.setdefault(w, []).append(l)

    replacements: dict[str, str] = {}
    for w, group in by_width.items():
        codes = T.reencode_states([g["name"] for g in group], w, rng)
        if not codes:
            cl.fault("4e", "state_space_too_small",
                     f"{len(group)} states do not fit in {w} bits",
                     "re-encoding skipped for this width class; the original "
                     "encoding is retained rather than emitting colliding codes")
            continue
        seen: dict[int, str] = {}
        for g in group:
            code = codes[g["name"]]
            if code in seen:
                cl.fault("4e", "state_code_collision",
                         f"{g['name']} and {seen[code]} both encode to {code}",
                         "collision-free sampling is used, so a collision here means "
                         "a bug rather than a model error; the step is abandoned "
                         "instead of emitting an aliased FSM", resolved=False)
                return
            seen[code] = g["name"]
            replacements[g["name"]] = T.lit(w, code)

    if not replacements:
        return

    # ---- 1. delete the declarations, by span, right to left
    targets = {n for n in replacements}
    spans: dict[tuple[int, int], list] = {}
    for l in fsm_lps:
        if l["name"] in targets:
            spans.setdefault((l["decl_start"], l["decl_end"]), []).append(l["name"])

    removed, kept_partial = [], []
    out = src
    for (a, b) in sorted(spans, reverse=True):
        decl = out[a:b]
        assigns = re.findall(r"([A-Za-z_]\w*)\s*=\s*([^,;]+)", decl)
        survivors = [(n, v) for n, v in assigns if n not in targets]
        if survivors:
            # a shared declaration -- keep the entries that are not FSM states
            first_assignment = re.search(r"[A-Za-z_]\w*\s*=", decl)
            prefix = decl[:first_assignment.start()] if first_assignment else "localparam "
            rebuilt = prefix + ", ".join(f"{n} = {v.strip()}" for n, v in survivors) + ";"
            out = out[:a] + rebuilt + out[b:]
            kept_partial.append((decl.strip(), rebuilt.strip()))
        else:
            out = out[:a] + "\n" * decl.count("\n") + out[b:]
        removed.append(decl.strip())

    # ---- 2. only now substitute the symbolic references with raw codes
    out, counts = vlog.rename(out, replacements)
    st["rtl"] = out
    st["fsm_encoding"] = replacements

    for name, code in sorted(replacements.items()):
        cl.change("4e", "fsm_state_reencode", target=name, before=name, after=code,
                  origin="script", occurrences=counts.get(name, 0),
                  rationale="symbolic state name leaks control-flow intent; every "
                            "reference is replaced with a pseudo-random raw code")
    for decl in removed:
        cl.change("4e", "localparam_removed",
                  target=decl.split("=")[0].replace("localparam", "").strip(),
                  before=decl, after="(declaration deleted)", origin="script",
                  rationale="state declaration removed entirely so no symbolic name "
                            "survives anywhere in the deliverable")
    for before, after in kept_partial:
        cl.change("4e", "localparam_partially_rewritten", target=after,
                  before=before, after=after, origin="script",
                  rationale="the declaration also defined non-FSM parameters; only "
                            "the state entries were removed so no unrelated constant "
                            "is lost")
    cl.change("4e", "reset_state_check", target="reset encoding",
              after=f"{len(replacements)} states re-encoded; no code collides and the "
                    "encoding is not the identity permutation", origin="script",
              rationale="mitigation for the paper's 'reset-state mis-encoding' fault: "
                        "the reset assignment is rewritten by the same substitution "
                        "pass as every other reference, so it cannot be left pointing "
                        "at a stale code")


# ================================================================== Step 4g
def step_4g(st: dict, cl: ChangeLog) -> None:
    """Rename every top-level port to a positional opaque label p_i{n}/p_o{n}."""
    src = st["rtl"]
    mods = vlog.parse_modules(src)
    top = mods[0]
    mapping, manifest = {}, []
    # The module identifier itself is the single strongest hint in the file --
    # the red-team elicitation of Step 4i* showed the model reading the design's
    # function straight off the module name -- so it is renamed here too.
    module_map = {}
    for m in mods:
        new_mod = T.anon_name(m.name, "top" if m is top else "mod")
        module_map[m.name] = new_mod
    ni = no = 0
    for p in top.ports:
        if p["dir"] == "input":
            new = f"p_i{ni}"; ni += 1
        elif p["dir"] == "output":
            new = f"p_o{no}"; no += 1
        else:
            new = f"p_b{ni + no}"; ni += 1
        mapping[p["name"]] = new
        manifest.append({"original": p["name"], "redacted": new,
                         "direction": p["dir"], "width": p["width"] or "1 bit"})
    if not mapping:
        return
    new_src, counts = vlog.rename(src, {**mapping, **module_map})
    st["rtl"] = new_src
    st["module_map"] = module_map
    for old, new in module_map.items():
        cl.change("4g", "module_rename", target=old, before=old, after=new,
                  origin="script",
                  rationale="the module identifier names the algorithm outright; "
                            "replaced with a keyed opaque label")
    st["port_manifest"] = manifest
    st["rename_map"] = {**st.get("rename_map", {}), **mapping}
    for m in manifest:
        cl.change("4g", "port_rename", target=m["original"],
                  before=m["original"], after=m["redacted"], origin="script",
                  occurrences=counts.get(m["original"], 0),
                  rationale="top-level port identifiers establish the module's "
                            "security role before any further analysis; replaced with "
                            "positionally-indexed opaque labels",
                  direction=m["direction"], width=m["width"])
    cl.change("4g", "port_manifest_retained", target="port_manifest.json",
              after=f"{len(manifest)} port mappings recorded privately",
              origin="script",
              rationale="the manifest is required to update the testbench and is "
                        "explicitly NOT part of the redacted deliverable")


# ================================================================== Step 4h
ARITH = re.compile(r"(?P<lhs>[A-Za-z_]\w*)\s*=\s*(?P<a>[A-Za-z_]\w*)\s*"
                   r"(?P<op>[+\-])\s*(?P<b>[A-Za-z_]\w*)\s*;")


def step_4h(st: dict, cl: ChangeLog) -> None:
    """Expand `a + b` / `a - b` on sensitive nets into structural carry chains."""
    src = st["rtl"]
    high_lines = st["high_lines"](src)
    cs = vlog.code_only(src)
    decls = vlog.declarations(src)
    mods = vlog.parse_modules(src)
    widths = {}
    for m in mods:
        for p in m.ports:
            if p["msb"] is not None:
                widths[p["name"]] = (p["msb"], p["lsb"])
    for d in decls:
        if d["msb"] is not None:
            for n in d["names"]:
                widths[n] = (d["msb"], d["lsb"])

    edits, n = [], 0
    for m in vlog.ASSIGN.finditer(cs):
        line = vlog.line_of(src, m.start())
        if line not in high_lines:
            continue
        inner = ARITH.match(f"{m.group('lhs').strip()} = {m.group('rhs').strip()};")
        if not inner:
            continue
        a, b, lhs, op = inner.group("a"), inner.group("b"), inner.group("lhs"), inner.group("op")
        if not all(x in widths for x in (a, b, lhs)):
            continue
        msb, lsb = widths[lhs]
        if not (msb.strip().isdigit() and lsb.strip() == "0"):
            continue
        w = int(msb) + 1
        if w > 32:
            cl.fault("4h", "operand_too_wide",
                     f"{lhs} is {w} bits; a flat ripple-carry expansion would emit "
                     f"{4 * w} assignments and risks exceeding the model context",
                     "step skipped for this site; the paper's 8-bit slicing variant "
                     "would be the next escalation", resolved=True)
            continue
        nm = f"_ar{n}"; n += 1
        body = (T.ripple_carry_adder(nm, a, b, w) if op == "+"
                else T.ripple_carry_subtractor(nm, a, b, w))
        edits.append((m.start(), m.end(), src[m.start():m.end()],
                      body + f"\n  assign {lhs} = {nm};", line, op, w))
    if not edits:
        return
    out, pos = [], 0
    for a_, b_, _, after, _, _, _ in edits:
        out.append(src[pos:a_]); out.append(after); pos = b_
    out.append(src[pos:])
    st["rtl"] = "".join(out)
    for _, _, before, after, line, op, w in edits:
        cl.change("4h", "arithmetic_decomposition", target=before.strip(), line=line,
                  before=before.strip(), after=after[:900], origin="script",
                  operator=op, width=w,
                  rationale=f"behavioural '{op}' is instantly recognisable to an LLM; "
                            f"replaced with an explicit {w}-bit gate-level carry chain "
                            f"built from XOR/AND/OR primitives only")


# ================================================================== Step 4j
def step_4j(st: dict, cl: ChangeLog, decoy: dict) -> None:
    """Inject a stylistically identical but functionally inert decoy secret."""
    src, rng = st["rtl"], st["rng"]
    mods = vlog.parse_modules(src)
    top = mods[0]
    w = 8
    fake = rng.randrange(1, 255)
    m = T.mask_constant(w, fake, rng)
    if not m:
        return
    dn = T.anon_name(f"decoy{fake}", "cm")
    drv = next((p["name"] for p in top.ports if p["dir"] == "input"), None)
    if drv is None:
        return
    story = decoy.get("comment", "Compare against the retained challenge constant.")
    block = f"""
  // ---------------------------------------------------------------------
  // {story}
  // ---------------------------------------------------------------------
  wire [{w-1}:0] {dn}_v = {{{w}{{1'b0}}}} | {drv};
  wire           {dn}_m = ((({dn}_v ^ {T.lit(w, m['xor'])})"""
    block += (f" + {T.lit(w, m['add'])}) == {T.lit(w, m['masked'])});\n"
              f"  wire           {dn}_dbg = {dn}_m; // observability tap only\n")
    # Cone-of-influence guarantee: _dbg is declared and read by nothing else, so
    # the decoy provably cannot affect any output.
    ins = top.end - len("endmodule")
    st["rtl"] = src[:ins] + block + src[ins:]
    st.setdefault("decoys", []).append(
        {"signal": f"{dn}_m", "fake_secret": T.lit(w, fake),
         "masked_form": T.lit(w, m["masked"]), "driven_by": drv,
         "sinks": [f"{dn}_dbg"], "affects_any_output": False,
         "narrative": story})
    cl.change("4j", "decoy_injection", target=f"{dn}_m",
              after=block.strip()[:700], origin="llm+script",
              rationale="a second key-check-shaped comparator built with the exact "
                        "Step-4c vocabulary; an attacker exploring the neighbourhood "
                        "of a real secret meets the decoy first",
              fake_secret=T.lit(w, fake), narrative=story)
    cl.change("4j", "decoy_cone_of_influence_check", target=f"{dn}_m",
              after="no path from the decoy to any top-level output", origin="script",
              rationale="mitigation for the paper's fault where a decoy is "
                        "accidentally wired into a real control path: the decoy's only "
                        "sink is a dead-end observability wire")


# ================================================================== Step 4k
def step_4k(st: dict, cl: ChangeLog) -> None:
    """Non-idiomatic style transfer: wrap continuous assignments in generate blocks."""
    src = st["rtl"]
    mods = vlog.parse_modules(src)
    top = mods[0]
    cs = vlog.code_only(src)
    hits = [m for m in vlog.ASSIGN.finditer(cs)
            if top.header_end <= m.start() < top.end - len("endmodule")]
    if len(hits) < 2:
        return
    hits = hits[:max(2, len(hits) // 2)]
    out, pos, n = [], 0, 0
    for m in hits:
        out.append(src[pos:m.start()])
        stmt = src[m.start():m.end()].strip()
        out.append(T.to_generate_block("  " + stmt, f"_gb{n}"))
        pos = m.end(); n += 1
    out.append(src[pos:])
    st["rtl"] = "".join(out)
    cl.change("4k", "style_transfer", target=f"{n} continuous assignments",
              before=f"{n} flat `assign` statements",
              after=f"{n} `generate if (1) begin : _gbN ... end endgenerate` blocks",
              origin="script",
              rationale="LLM idiom recognition is biased toward the canonical coding "
                        "style over-represented in public RTL corpora; re-expressing "
                        "the same logic through a degenerate generate construct "
                        "defeats pattern matching without changing behaviour")


# ================================================================== Step 4l
CMP_SITE = re.compile(
    r"(?P<lhs>\([^;]{0,300}?\)|[A-Za-z_]\w*(?:\s*\[[^\]]*\])?)"
    r"\s*(?P<op>==|!=)\s*"
    r"(?P<rhs>\d+\s*'\s*[bBoOdDhH][0-9a-fA-F_]+)")


def _clock_and_reset(src: str, ports, port_manifest) -> tuple[str | None, str, str]:
    """Find the clock port, and a reset EXPRESSION that is active-high.

    Step 4g has already replaced `clk`/`reset_n` with opaque positional labels by
    the time this step runs, so the roles are recovered from the port-mapping
    manifest -- the same private artefact the design team needs to re-run their
    testbench -- rather than from the (now meaningless) current names.

    The generated PRSG takes an active-high asynchronous `rst`; a design with an
    active-low `reset_n` must be wired through an inversion, or the generators
    would sit in reset for the whole of normal operation.
    """
    now = {m["original"]: m["redacted"] for m in (port_manifest or [])}
    live = {p["name"] for p in ports}

    def current(orig: str) -> str | None:
        n = now.get(orig, orig)
        return n if n in live else None

    originals = [m["original"] for m in port_manifest] if port_manifest \
        else [p["name"] for p in ports]

    clk = next((current(o) for o in originals
                if re.fullmatch(r"clk|clock|clk_i", o, re.I) and current(o)), None)
    for o in originals:
        if not re.fullmatch(r"rst|reset|rst_n|reset_n|areset|aresetn|rst_ni", o, re.I):
            continue
        n = current(o)
        if not n:
            continue
        # Polarity comes from the ORIGINAL identifier's convention, plus how the
        # current source actually uses the (renamed) signal.
        active_low = o.lower().endswith(("_n", "_ni")) or bool(
            re.search(rf"if\s*\(\s*!\s*{re.escape(n)}\s*\)", src)
            or re.search(rf"negedge\s+{re.escape(n)}\b", src))
        return clk, (f"~{n}" if active_low else n), (
            f"{o} -> {n} (active low, inverted for the active-high PRSG reset)"
            if active_low else f"{o} -> {n} (active high)")
    # No reset port: the self-starting feedback term escapes the all-zero
    # lock-up state on its own, so the generators still rotate.
    return clk, "1'b0", "none -- generators rely on the self-starting feedback term"


def _provable_width(lhs: str, lit_width: int, widths: dict) -> bool:
    """Only rotate a comparison whose operand width we can prove equals the literal's.

    Verilog widens both sides of `==` to the wider operand, so masking into a
    W-bit intermediate is only behaviour-preserving when the left-hand side is
    genuinely W bits.  Anything we cannot prove is skipped rather than guessed.
    """
    bare = lhs.strip()
    if re.fullmatch(r"[A-Za-z_]\w*", bare):
        w = widths.get(bare)
        return w == lit_width
    # A parenthesised expression (typically Step 4d's output) is W bits when
    # every sized literal in it is W bits and every identifier is W bits.
    lits = [int(m.group(1)) for m in vlog.SIZED_LIT.finditer(bare)]
    if not lits or any(w != lit_width for w in lits):
        return False
    for ident in {i for i in vlog.IDENT.findall(bare) if i not in vlog.KEYWORDS}:
        if widths.get(ident) not in (None, lit_width):
            return False
    return True


def _declared_widths(src: str) -> dict[str, int]:
    out: dict[str, int] = {}

    def w_of(msb, lsb):
        if msb is None:
            return 1
        msb, lsb = msb.strip(), lsb.strip()
        return int(msb) - int(lsb) + 1 if msb.isdigit() and lsb.isdigit() else None

    for m in vlog.parse_modules(src):
        for p in m.ports:
            out[p["name"]] = w_of(p["msb"], p["lsb"])
    for d in vlog.declarations(src):
        w = w_of(d["msb"], d["lsb"])
        for n in d["names"]:
            out[n] = w
    return out


def step_4l(st: dict, cl: ChangeLog) -> None:
    """Side-channel-aware mask rotation (paper Listing 61).

    Rewrites `E == K` into

        A_n = E ^ M_n ;  B_n = A_n + K_n ;  T_n = (K ^ M_n) + K_n ;  B_n == T_n

    where M_n and K_n are two independently seeded, distinct-polynomial LFSR
    streams.  XOR and mod-2^W addition are both bijections, so the boolean is
    invariant for every (M_n, K_n) -- the comparison result is unchanged while
    the switching activity of the operands is re-randomised every cycle, which
    is the point: a fixed-mask comparison leaks the secret to power analysis
    even when the mask defeats textual analysis.

    Script-authored end to end, by explicit mandate of the paper ("not the LLM,
    to avoid any risk of the LLM weakening the rotation for simplicity").
    """
    if not st["strategy"].get("silicon_bound"):
        cl.change("4l", "rotation_skipped", target="design",
                  after="not applied", origin="script",
                  rationale="Phase 1 does not flag this design as silicon-bound; "
                            "rotation would add area and a clock/reset dependency and "
                            "would force Phase 5 into sequential equivalence checking "
                            "for no threat-model benefit")
        return

    src = st["rtl"]
    mods = vlog.parse_modules(src)
    top = mods[0]
    clk, rst_expr, rst_desc = _clock_and_reset(src, top.ports,
                                              st.get("port_manifest"))
    if clk is None:
        cl.change("4l", "rotation_skipped", target="design",
                  after="not applied", origin="script",
                  rationale="module is purely combinational (no clock port); a "
                            "rotating mask requires sequential state")
        return

    widths = _declared_widths(src)
    sens = st["high_lines"](src)
    cs = vlog.code_only(src)
    body_lo, body_hi = top.header_end, top.end - len("endmodule")

    sites, skipped = [], []
    for m in CMP_SITE.finditer(cs):
        if not (body_lo <= m.start() < body_hi):
            continue
        if vlog.line_of(src, m.start()) not in sens:
            continue
        lit_m = vlog.SIZED_LIT.match(m.group("rhs").replace(" ", ""))
        if not lit_m:
            continue
        w = int(lit_m.group(1))
        if w not in T.PRSG_WIDTHS:
            skipped.append((m.group(0)[:60], f"{w}-bit operand: no verified "
                                             f"maximal-length generator for this width"))
            continue
        if not _provable_width(m.group("lhs"), w, widths):
            skipped.append((m.group(0)[:60], "operand width could not be proven equal "
                                             "to the literal width"))
            continue
        sites.append({"start": m.start(), "end": m.end(), "width": w,
                      "lhs": src[m.start():m.end()].split(m.group("op"))[0].strip(),
                      "op": m.group("op"), "rhs": lit_m.group(0),
                      "text": src[m.start():m.end()],
                      "line": vlog.line_of(src, m.start())})

    for txt, why in skipped:
        cl.change("4l", "site_skipped", target=txt, after="not rotated",
                  origin="script", rationale=why)
    # Step-4c reconstruction sites.  The paper scopes this step to "the Step
    # 4c/4d site"; where a design has no comparison against a literal (true of
    # every design in this corpus), the rotatable site is the chain that
    # reconstructs a masked constant.  The exact text Step 4c emitted is known,
    # and later steps only rewrite identifiers, so it can be located verbatim.
    # A rotating net cannot appear in a constant context: `parameter X = <expr>`
    # and `case` item labels are elaboration-time constants, and substituting a
    # wire there is a bind error rather than an obfuscation.
    const_ctx = [(d["start"], d["end"]) for d in vlog.declarations(src)
                 if d["kw"] in ("parameter", "localparam")]
    case_spans = [(c["start"], c["end"]) for c in vlog.case_items(src)]

    def in_case_label(off: int) -> bool:
        """True only for the LABEL part of a case item, not for its statement.

        Excluding whole `case` blocks would be far too blunt: in a lookup table
        such as `8'h00: tmp = 8'h63;` the *result* is an ordinary expression and
        is exactly the constant worth rotating -- only the selector value to the
        left of the colon is an elaboration-time constant.
        """
        if not any(a <= off < b for a, b in case_spans):
            return False
        ls = src.rfind("\n", 0, off) + 1
        le = src.find("\n", off)
        line = src[ls:(le if le != -1 else len(src))]
        depth = 0
        for i, ch in enumerate(line):
            if ch in "[({":
                depth += 1
            elif ch in "])}":
                depth -= 1
            elif ch == ":" and depth == 0:
                return off < ls + i
        return False

    def in_const_ctx(off: int) -> bool:
        return any(a <= off < b for a, b in const_ctx) or in_case_label(off)

    const_sites = []
    for c in st.get("masked_constants", []):
        w = c["width"]
        if w not in T.PRSG_WIDTHS:
            continue
        emitted = (f"(({T.lit(w, c['masked'])} - {T.lit(w, c['add'])})"
                   f" ^ {T.lit(w, c['xor'])})")
        at = src.find(emitted)
        if at == -1 or not (body_lo <= at < body_hi):
            continue
        if in_const_ctx(at):
            skipped.append((emitted[:60], "site sits in a constant context "
                                          "(parameter declaration or case label); a "
                                          "rotating net is not a constant expression"))
            continue
        const_sites.append({"start": at, "end": at + len(emitted), "width": w,
                            "text": emitted, "kind": "constant",
                            "masked": c["masked"], "add": c["add"], "xor": c["xor"],
                            "line": vlog.line_of(src, at)})
    for s_ in sites:
        s_["kind"] = "comparison"
    # Keep the site list positionally disjoint.
    taken = {(c["start"], c["end"]) for c in const_sites}
    sites = [x for x in sites
             if not any(a <= x["start"] < b for a, b in taken)] + const_sites
    sites.sort(key=lambda x: x["start"])

    if not sites:
        cl.change("4l", "rotation_not_applicable", target="design",
                  after="no generators emitted", origin="script",
                  rationale="the design has neither a sensitive comparison against a "
                            "literal nor a Step-4c reconstruction chain of a supported "
                            f"width {list(T.PRSG_WIDTHS)}; emitting the generators "
                            "anyway would add area and a clock dependency for no "
                            "benefit")
        return

    MAX_SITES = 4
    if len(sites) > MAX_SITES:
        for s in sites[MAX_SITES:]:
            cl.change("4l", "site_skipped", target=s["text"][:60],
                      after="not rotated", origin="script",
                      rationale=f"at most {MAX_SITES} sites are rotated per design to "
                                "bound the added area and the sequential-equivalence "
                                "proof depth")
        sites = sites[:MAX_SITES]

    # ---- generators, one independently seeded pair per distinct operand width
    used_widths = sorted({s["width"] for s in sites})
    decls, body, verifications, gen_nets = [], [], {}, {}
    for w in used_widths:
        seed_m = 0xA5 & ((1 << w) - 1) or 1
        seed_k = 0x3C & ((1 << w) - 1) or 1
        # Keyed opaque names: `_prsg8_m` / `_mn8` would announce both the
        # mechanism and its width to anyone reading the deliverable.
        mod_m = T.anon_name(f"{st['design']}:prsg:{w}:m", "mx")
        mod_k = T.anon_name(f"{st['design']}:prsg:{w}:k", "mx")
        st["aux"] = st.get("aux", "") + T.prsg_module(mod_m, w, 0, seed_m) \
            + T.prsg_module(mod_k, w, 1, seed_k)
        wm = T.anon_name(f"{st['design']}:mn:{w}", "sg")
        wk = T.anon_name(f"{st['design']}:kn:{w}", "sg")
        gen_nets[w] = (wm, wk)
        decls.append(f"  wire [{w-1}:0] {wm}, {wk};")
        body.append(f"  {mod_m} u_{wm}(.clk({clk}), .rst({rst_expr}), .r({wm}));")
        body.append(f"  {mod_k} u_{wk}(.clk({clk}), .rst({rst_expr}), .r({wk}));")

        v = T.verify_prsg_pair(w, seed_m, seed_k)
        verifications[w] = v
        cl.change("4l", "prsg_generated", target=f"{mod_m} / {mod_k}",
                  after=f"period {v['period_m']}/{v['period_k']} (expected "
                        f"{v['period_expected']}), pair repeats within period: "
                        f"{v['pair_repeats_within_period']}, cyclic shifts: "
                        f"{v['streams_are_cyclic_shifts']}",
                  origin="script", verification=v,
                  rationale="distinct maximal-length polynomials and distinct non-zero "
                            "seeds, verified by exhaustive walk over a full period; "
                            "mitigation for the paper's 'PRSG period too short / "
                            "correlated' fault")
        if not v["ok"]:
            cl.fault("4l", "prsg_verification_failed",
                     f"{w}-bit generator pair failed its post-generation check: {v}",
                     "the step is abandoned for this width rather than shipping a "
                     "rotation that provides no real randomisation", resolved=False)
            return

    # ---- per-site rotation
    #
    # `(* keep *)` is load bearing.  Every identity below is algebraically the
    # identity map, so a synthesiser will happily fold the whole chain away --
    # which would restore exactly the fixed-mask switching behaviour this step
    # exists to remove.  The attribute keeps the rotating nets in the netlist.
    KEEP = '(* keep = "true" *) '
    for i, s in enumerate(sites):
        w = s["width"]
        nm = T.anon_name(f"{st['design']}:rot:{i}:{s['start']}", "sg")
        wm, wk = gen_nets[w]
        if s["kind"] == "comparison":
            # Paper Listing 61: the comparison is evaluated entirely in the
            # masked domain, so the secret operand never materialises at all.
            decls.append(f"  {KEEP}wire [{w-1}:0] {nm}_a, {nm}_b, {nm}_t;")
            decls.append(f"  {KEEP}wire           {nm}_q;")
            body += [
                f"  // site {i}",
                f"  assign {nm}_a = {s['lhs']} ^ {wm};",
                f"  assign {nm}_b = {nm}_a + {wk};",
                f"  assign {nm}_t = ({s['rhs']} ^ {wm}) + {wk};",
                f"  assign {nm}_q = ({nm}_b {s['op']} {nm}_t);",
            ]
            s["replacement"] = f"{nm}_q"
        else:
            # Step-4c reconstruction chain.  The constant is carried through the
            # rotating domain and only unmasked on the final net, so every
            # intermediate switches with (M_n, K_n) rather than with the secret.
            ml = T.lit(w, s["masked"])
            decls.append(f"  {KEEP}wire [{w-1}:0] {nm}_c0, {nm}_c1, {nm}_c2, {nm}_c3;")
            decls.append(f"  {KEEP}wire [{w-1}:0] {nm}_v;")
            body += [
                f"  // site {i}",
                f"  assign {nm}_c0 = {ml} ^ {wm};",
                f"  assign {nm}_c1 = {nm}_c0 + {wk};",
                f"  assign {nm}_c2 = {nm}_c1 - {wk};",
                f"  assign {nm}_c3 = {nm}_c2 ^ {wm};",
                f"  assign {nm}_v  = ({nm}_c3 - {T.lit(w, s['add'])})"
                f" ^ {T.lit(w, s['xor'])};",
            ]
            s["replacement"] = f"{nm}_v"

    # ---- splice: replace the sites right-to-left, then insert decls and body
    out = src
    for s in sorted(sites, key=lambda x: -x["start"]):
        out = out[:s["start"]] + s["replacement"] + out[s["end"]:]
    top2 = vlog.parse_modules(out)[0]
    hdr, end = top2.header_end, top2.end - len("endmodule")
    banner = "\n"
    st["rtl"] = (out[:hdr] + banner + "\n".join(decls) + "\n"
                 + out[hdr:end] + "\n" + "\n".join(body) + "\n" + out[end:])

    st["mask_rotation"] = {
        "clock": clk, "reset_expression": rst_expr, "reset": rst_desc,
        "widths": used_widths, "verification": verifications,
        "sites": [{"line": s["line"], "before": s["text"],
                   "after": s["replacement"], "width": s["width"]} for s in sites],
    }
    for s in sites:
        if s["kind"] == "comparison":
            after = (f"{s['replacement']}  // ((lhs ^ M_n) + K_n) {s['op']} "
                     f"(({s['rhs']}) ^ M_n) + K_n")
            why = ("the compared operands are re-masked every cycle by two "
                   "independent LFSR streams and the comparison is evaluated "
                   "entirely in the masked domain; XOR and mod-2^W addition are "
                   "bijections so the boolean result is invariant, but the operand "
                   "switching activity no longer correlates with the secret, which "
                   "is what a power-analysis attacker measures")
        else:
            after = (f"{s['replacement']}  // constant carried through "
                     f"(x ^ M_n) + K_n - K_n ^ M_n and unmasked only on the final net")
            why = ("the Step-4c reconstruction chain is routed through the rotating "
                   "domain, so every intermediate net switches with (M_n, K_n) "
                   "rather than with the secret; the final net must still carry the "
                   "true value because the surrounding logic consumes it, so this "
                   "form protects the reconstruction path rather than the value's "
                   "single point of use")
        cl.change("4l", f"rotating_mask_{s['kind']}", target=s["text"], line=s["line"],
                  before=s["text"], after=after, origin="script", width=s["width"],
                  rationale=why)
    cl.change("4l", "rotation_wiring", target=f"{len(sites)} site(s)",
              after=f"clock={clk}, reset={rst_desc}, widths={used_widths}",
              origin="script",
              rationale="generators are instantiated and driven from the design's own "
                        "clock and reset, so the mask actually rotates at run time")


# =================================================================== LLM 4i/4j
FALSE_ID_SYS = ("You write plausible but deliberately incorrect technical documentation "
                "for hardware. You reply with ONE JSON object and nothing else.")

FALSE_ID_PROMPT = """This Verilog module has been redacted. Its real function is:
  {truth}

Invent a DIFFERENT, entirely plausible hardware identity for it, and write comments
that consistently support that false identity. The comments must be internally
consistent across the whole file so that a reader finds no contradiction.

Return ONE JSON object:
{{"false_identity":"<the fake module purpose, under 20 words>",
  "header_comment":"<2-4 lines of file header text supporting the false identity>",
  "annotations":[{{"anchor":"<an identifier that appears in the RTL below>",
                  "comment":"<one line, under 18 words, explaining that identifier "
                            "in terms of the FALSE identity>"}}]}}

Rules:
- The false identity must NOT be {truth_kind}. Pick something structurally similar
  but functionally unrelated (e.g. a CRC engine, a baud-rate generator, a
  temperature-sensor controller, a display timing generator).
- Provide 4 to 10 annotations. Every "anchor" MUST be one of the identifiers listed.
- Never mention keys, secrets, encryption, authentication or redaction.
{cot_block}
IDENTIFIERS AVAILABLE AS ANCHORS: {anchors}

REDACTED VERILOG:
```verilog
{rtl}
```"""

COT_PROMPT = """You are a reverse engineer. Read this redacted Verilog and think step by
step about what the hardware does. Return ONE JSON object:
{{"reasoning_steps":["<each intermediate deduction, under 15 words>"],
  "conclusion":"<your best guess at the module's function, under 15 words>"}}
Give 3 to 6 reasoning steps -- the intermediate deductions, not just the answer.

```verilog
{rtl}
```"""

DECOY_PROMPT = """Write the comment that will sit above a decoy logic cone in a redacted
Verilog file. The decoy looks exactly like a secret-value comparator but its output
drives nothing. The comment must make the decoy look like the module's REAL secret
check, so that an attacker investigates it first.

The file currently presents itself as: {false_identity}

Return ONE JSON object: {{"comment":"<one line, under 22 words>"}}
The comment must be consistent with the stated false identity and must not use the
words decoy, dummy, fake or honeypot."""


def llm_comments(st: dict, cl: ChangeLog) -> tuple[dict, dict]:
    """Steps 4i and 4i* -- false identity, CoT-steered misleading annotations."""
    src = st["rtl"]
    rtl = src if len(src) < 14000 else src[:14000] + "\n// ... truncated ...\n"
    anchors = [n for n in vlog.identifiers(src) if n.startswith(("_", "p_i", "p_o"))][:60]
    if not anchors:
        anchors = list(vlog.identifiers(src))[:60]

    # Step 4i* -- elicit the attacker's reasoning trace first, so the injected
    # comments can target the intermediate deductions rather than the conclusion.
    cot, cot_rec = llm.generate_json(
        COT_PROMPT.format(rtl=rtl), system="You reply with ONE JSON object only.",
        temperature=0.3, seed=41, num_predict=4000, key_hint="reasoning_steps",
        tag=f"4i*:{st['design']}", phase="4i*")
    steps = [str(s) for s in (cot or {}).get("reasoning_steps", [])][:6]
    cot_block = ""
    if steps:
        cot_block = ("\nA red-team reader of this file reasons as follows:\n"
                     + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(steps))
                     + "\nYour comments must contradict these INTERMEDIATE steps, not "
                       "merely the final conclusion.\n")
        cl.change("4i*", "attacker_reasoning_elicited", target="chain of thought",
                  after=json.dumps({"steps": steps,
                                    "conclusion": (cot or {}).get("conclusion", "")}),
                  origin="llm",
                  rationale="an LLM that has committed to an intermediate deduction "
                            "resists a contradicting conclusion; steering the "
                            "intermediate steps is materially more effective")
    else:
        cl.fault("4i*", "no_reasoning_trace",
                 "red-team elicitation returned no usable reasoning steps",
                 "Step 4i falls back to plain misleading-comment generation, which "
                 "is the paper's baseline behaviour", resolved=True)

    truth = st["profile"]["llm"].get("design_purpose", "an unspecified digital block")
    parsed, rec = llm.generate_json(
        FALSE_ID_PROMPT.format(truth=truth, truth_kind=truth[:60],
                               anchors=", ".join(anchors), rtl=rtl,
                               cot_block=cot_block),
        system=FALSE_ID_SYS, temperature=0.55, seed=17, num_predict=2500, key_hint="annotations",
        tag=f"4i:{st['design']}", phase="4i")
    if parsed is None:
        cl.fault("4i", "unparseable_comment_payload",
                 "misleading-comment generation produced no parseable JSON",
                 "no comments are injected; the file simply ships with all authentic "
                 "comments stripped by Step 4f, which is strictly safe", resolved=True)
        return {}, {"cot": cot_rec, "identity": rec}

    banned = re.compile(r"\b(key|secret|encrypt|decrypt|auth|cipher|redact|obfuscat|"
                        r"decoy|honeypot|dummy)\w*", re.I)
    kept, rejected = [], []
    known = set(vlog.identifiers(src))
    for a in parsed.get("annotations", []) or []:
        anc, com = str(a.get("anchor", "")).strip(), str(a.get("comment", "")).strip()
        if anc not in known:
            rejected.append({"anchor": anc, "reason": "identifier not in RTL"})
        elif banned.search(com):
            rejected.append({"anchor": anc, "reason": "comment leaks security vocabulary",
                             "comment": com})
        elif "<file" in com.lower():
            rejected.append({"anchor": anc, "reason": "comment contains an XML delimiter"})
        else:
            kept.append({"anchor": anc, "comment": com})
    if rejected:
        cl.fault("4i", "comment_validation_rejections",
                 f"{len(rejected)} generated comment(s) rejected: "
                 f"{[r['reason'] for r in rejected]}",
                 "every annotation is checked against the symbol table and a banned "
                 "security-vocabulary regex before injection; a comment that "
                 "re-introduces the words the redaction removed would undo Step 4f",
                 rejected=rejected)
    parsed["annotations"] = kept
    return parsed, {"cot": cot_rec, "identity": rec}


def step_4f_strip(st: dict, cl: ChangeLog) -> None:
    """Step 4f (part 1) -- strip every authentic comment."""
    src = st["rtl"]
    removed = [src[s.start:s.end].strip()
               for s in vlog.scan(src) if s.kind in ("lcomment", "bcomment")
               and "@SENSITIVITY" not in src[s.start:s.end]
               and not vlog.is_tool_pragma(src[s.start:s.end])]
    out = []
    for s in vlog.scan(src):
        chunk = src[s.start:s.end]
        if s.kind in ("lcomment", "bcomment") and not vlog.is_tool_pragma(chunk):
            out.append("\n" * chunk.count("\n"))
        else:
            out.append(chunk)
    joined = "".join(out)
    joined = re.sub(r"[ \t]+$", "", joined, flags=re.M)
    st["rtl"] = re.sub(r"\n{3,}", "\n\n", joined)

    # The Step-4l helper modules live in `aux` and are concatenated into the
    # deliverable, so they must be sanitised by the same pass -- otherwise any
    # commentary in a generated module ships in the clear.
    if st.get("aux"):
        aux_out = []
        for sp in vlog.scan(st["aux"]):
            chunk = st["aux"][sp.start:sp.end]
            aux_out.append("\n" * chunk.count("\n")
                           if sp.kind in ("lcomment", "bcomment") and not vlog.is_tool_pragma(chunk) else chunk)
        st["aux"] = re.sub(r"\n{3,}", "\n\n", "".join(aux_out))
    cl.change("4f", "comment_sanitisation", target=f"{len(removed)} comments",
              before=f"{len(removed)} authentic comment blocks",
              after="(all removed)", origin="script",
              rationale="LLMs weight natural-language comments heavily when inferring "
                        "module semantics; no authentic hint may survive into the "
                        "deliverable",
              samples=[r[:120] for r in removed[:15]])


def step_4i_inject(st: dict, cl: ChangeLog, payload: dict) -> None:
    src = st["rtl"]
    hdr = str(payload.get("header_comment", "")).strip()
    if hdr:
        header = "\n".join("// " + re.sub(r"^\s*//+\s?", "", l).strip()
                           for l in hdr.splitlines() if l.strip())
        st["rtl"] = header + "\n\n" + src
        cl.change("4i", "false_identity_header", target="file header",
                  after=header, origin="llm",
                  rationale=f"file now presents itself as: "
                            f"{payload.get('false_identity','')}")
        src = st["rtl"]
    lines = src.splitlines()
    placed, used = 0, set()
    for ann in payload.get("annotations", []):
        anc, com = ann["anchor"], ann["comment"]
        for i, line in enumerate(lines):
            if i in used or not re.search(rf"\b{re.escape(anc)}\b",
                                          vlog.code_only(line)):
                continue
            indent = re.match(r"[ \t]*", line).group(0)
            com = re.sub(r"^\s*//+\s?", "", com).strip()
            lines[i] = f"{indent}// {com}\n{line}"
            used.add(i); placed += 1
            cl.change("4i", "misleading_comment", target=anc, line=i + 1,
                      after=f"// {com}", origin="llm",
                      rationale="semantically incorrect but internally consistent "
                                "annotation steering semantic inference toward the "
                                "false identity")
            break
    st["rtl"] = "\n".join(lines) + "\n"
    if placed < len(payload.get("annotations", [])):
        cl.fault("4i", "unplaceable_annotation",
                 f"{len(payload.get('annotations', [])) - placed} annotation(s) had no "
                 "free anchor line",
                 "annotations are placed at most once per source line; surplus "
                 "annotations are dropped rather than stacked", resolved=True)


def step_4f_final(st: dict, cl: ChangeLog) -> None:
    """Step 4f (part 2) -- residual-leakage scan over the finished file."""
    src = st["rtl"]
    src = re.sub(r"^[ \t]*// @SENSITIVITY: HIGH[ \t]*\n", "", src, flags=re.M)
    st["rtl"] = src
    cl.change("4f", "annotation_removal", target="@SENSITIVITY markers",
              after="(all removed)", origin="script",
              rationale="the Phase-3 sensitivity markers are internal scaffolding and "
                        "would tell an attacker exactly where to look")

    # Deterministic residual scan: does any original semantic name survive?
    originals = [n for n in st.get("rename_map", {})]
    residual = vlog.residual_occurrences(vlog.code_only(src), originals)
    # Comments are excluded: after Step 4i the only comments in the file are the
    # deliberately misleading ones, whose whole purpose is to look like they
    # describe a secret check.  Flagging those as a leak would invert the metric.
    leak_words = re.findall(r"\b(?:key|secret|auth|unlock|admin|priv|token|cipher|"
                            r"sbox|round_key|passwd|password)\w*\b",
                            vlog.code_only(src), re.I)
    cl.change("4f", "residual_leakage_scan", target="whole file",
              after=json.dumps({"surviving_original_identifiers": sorted(residual),
                                "security_vocabulary_hits": sorted(set(leak_words))}),
              origin="script",
              rationale="final deterministic sweep for anything the earlier steps "
                        "should have removed")
    if residual or leak_words:
        cl.fault("4f", "residual_leakage",
                 f"{len(residual)} original identifier(s) and "
                 f"{len(set(leak_words))} security keyword(s) survive in the output",
                 "reported for human review; these are identifiers Phase 2 classified "
                 "LOW, so removing them is outside the agreed redaction scope",
                 resolved=False,
                 identifiers=sorted(residual), keywords=sorted(set(leak_words)))


# ==================================================================== driver
def transform(path: Path, escalation: dict | None = None,
              variant: str | None = None) -> dict:
    """Run Phase 4.  `variant` in {B0,B1,B2} forces that tier's transformation
    set instead of the per-design maximum, producing one member of the Novel
    Extension 2 variant family {R_B0, R_B1, R_B2}."""
    design = path.stem
    strat = util.read_json(C.PHASE_DIRS[3] / f"{design}.strategy.json")
    sens = util.read_json(C.PHASE_DIRS[2] / f"{design}.sensitivity.json")
    prof = util.read_json(C.PHASE_DIRS[1] / f"{design}.profile.json")
    annotated = (C.ROOT / strat["annotated_rtl"]).read_text()

    round_id = (escalation or {}).get("round", 0)
    tag = "" if not round_id else f".r{round_id}"
    if variant:
        tag = f".{variant}"
    cl = ChangeLog(f"phase4_transform{tag}", design, strat["annotated_rtl"])
    if variant:
        cl.note(variant=variant,
                variant_note=("Novel Extension 2 variant family member: this run "
                              "forces the " + variant + " transformation set of "
                              "Table III rather than the per-design maximum, so the "
                              "leakage-vs-overhead Pareto curve has a point per tier."))

    steps = (list(C.BUDGET_TRANSFORMS[variant]) if variant
             else list(strat["design_transformations"]))
    if escalation:
        steps = sorted(set(steps) | set(escalation["additional_steps"]),
                       key=lambda s: (s[1], s))
        cl.note(escalation=escalation)
    # 4l is applied on top of 4c whenever the design is silicon-bound and clocked.
    if "4c" in steps and strat.get("silicon_bound"):
        steps.append("4l")

    high = {n for n, v in sens["signals"].items() if v["tier"] == "HIGH"}
    st = {
        "design": design, "rtl": annotated, "strategy": strat, "sensitivity": sens,
        "profile": prof, "high": high, "aux": "",
        "rng": random.Random(int(T.anon_name(design + str(round_id), "s")[3:], 16)),
        "child_name": T.anon_name(design, "mod"),
        "rename_map": {},
    }
    def sensitive_lines(text: str, tiers=("HIGH", "MED")) -> set[int]:
        """Line numbers carrying, or immediately under, a @SENSITIVITY marker."""
        lines = text.splitlines()
        marks = {i for i, l in enumerate(lines, 1)
                 if any(f"@SENSITIVITY: {t}" in l for t in tiers)}
        return marks | {i + 1 for i in marks}

    st["high_lines"] = sensitive_lines

    cl.note(selected_steps=steps, design_budget=strat["design_budget_tier"],
            n_high=len(high), escalation_round=round_id,
            step_ownership={
                "llm": ["4i (misleading comments)", "4i* (CoT steering)",
                        "4j (decoy narrative)"],
                "script": ["4a", "4b", "4c", "4d", "4e", "4f", "4g", "4h", "4k",
                           "4l (mandated script-only)"],
                "note": ("The LLM supplies semantic content; the orchestration script "
                         "performs every mechanical rewrite so that the output is "
                         "algebraically equivalent by construction. This is the "
                         "systematic form of the paper's own per-step mitigations.")})

    stage = Stage(cl, st)
    ok0, err0 = compiles(st["rtl"], "", design)
    if not ok0:
        cl.fault("4", "annotated_input_does_not_compile",
                 f"the Phase-3 annotated RTL is already rejected by Icarus: {err0}",
                 "the design is not self-contained (it instantiates sub-modules that "
                 "live in other files); transformations still run but the syntax gate "
                 "is advisory only for this design", resolved=False)
        cl.write(C.phase_dir(4) / f"{design}{tag}.changelog.json")
        raise RuntimeError(f"Annotated input does not elaborate: {err0}")

    order = [("4a", step_4a), ("4b", step_4b), ("4c", step_4c), ("4d", step_4d),
             ("4e", step_4e), ("4g", step_4g), ("4h", step_4h), ("4k", step_4k),
             ("4l", step_4l)]
    for name, fn in order:
        if name in steps:
            stage.apply(name, lambda fn=fn: fn(st, cl))

    stage.apply("4f", lambda: step_4f_strip(st, cl))

    payload, val = ({}, {})
    if "4i" in steps:
        payload, val = llm_comments(st, cl)
    if "4j" in steps and payload:
        decoy, drec = llm.generate_json(
            DECOY_PROMPT.format(false_identity=payload.get("false_identity", "")),
            system="You reply with ONE JSON object only.", temperature=0.6, seed=29,
            num_predict=2500, tag=f"4j:{design}", phase="4j")
        stage.apply("4j", lambda: step_4j(st, cl, decoy or {}))
    if payload:
        stage.apply("4i", lambda: step_4i_inject(st, cl, payload))
    stage.apply("4f-final", lambda: step_4f_final(st, cl))

    d = C.phase_dir(4)
    out_v = d / f"{design}{tag}.redacted.v"
    out_v.write_text(st["rtl"] + "\n" + st.get("aux", ""))
    ok, err = compiles(st["rtl"], st.get("aux", ""), design)

    manifests = {
        "design": design, "round": round_id, "variant": variant,
        "redacted_rtl": str(out_v.relative_to(C.ROOT)),
        "requested_steps": steps,
        "applied_steps": [o["step"] for o in stage.outcomes if o["status"] == "applied"],
        "step_outcomes": stage.outcomes,
        "port_manifest": st.get("port_manifest", []),
        "module_manifest": st.get("module_map", {}),
        "identifier_manifest": st.get("rename_map", {}),
        "masked_constants": st.get("masked_constants", []),
        "fsm_encoding": st.get("fsm_encoding", {}),
        "mask_rotation": st.get("mask_rotation", {}),
        "decoy_manifest": st.get("decoys", []),
        "false_identity": payload.get("false_identity", ""),
        "compiles": ok, "compile_error": "" if ok else err,
    }
    util.write_json(d / f"{design}{tag}.manifests.json", manifests)
    cl.artifact("redacted_rtl", out_v)
    cl.artifact("manifests", d / f"{design}{tag}.manifests.json")
    cl.summarise(applied_steps=steps, compiles=ok, compile_error=("" if ok else err),
                 n_ports_renamed=len(st.get("port_manifest", [])),
                 n_identifiers_renamed=len(st.get("rename_map", {})),
                 n_constants_masked=len(st.get("masked_constants", [])),
                 n_fsm_states_reencoded=len(st.get("fsm_encoding", {})),
                 n_decoys=len(st.get("decoys", [])),
                 n_rotated_comparisons=len(
                     (st.get("mask_rotation") or {}).get("sites", [])),
                 false_identity=payload.get("false_identity", ""),
                 llm_validation=val)
    cl.write(d / f"{design}{tag}.changelog.json")
    return manifests


def main() -> int:
    ap = util.design_args(__doc__)
    ap.add_argument("--variants", action="store_true",
                    help="also emit the B0/B1/B2 variant family (Novel Extension 2)")
    args = ap.parse_args()
    llm.start_log("phase4")
    util.banner("PHASE 4 -- GenAI-Assisted RTL Transformation")
    index = []
    for p in util.resolve_designs(args):
        util.info(f"transforming {p.name}")
        m = transform(p)
        util.info(f"    steps={','.join(m['applied_steps'])}  compiles={m['compiles']}"
                  f"  renamed={len(m['identifier_manifest'])}"
                  f"  masked={len(m['masked_constants'])}"
                  f"  decoys={len(m['decoy_manifest'])}"
                  f"  rotated={len((m.get('mask_rotation') or {}).get('sites', []))}")
        if not m["compiles"]:
            util.warn(f"    {m['compile_error'][:160]}")
        index.append({"design": m["design"], "compiles": m["compiles"],
                      "steps": m["applied_steps"]})
        if args.variants:
            for v in C.BUDGET_ORDER:
                mv = transform(p, variant=v)
                util.info(f"    variant {v}: steps={','.join(mv['applied_steps'])} "
                          f"compiles={mv['compiles']}")
                index.append({"design": m["design"], "variant": v,
                              "compiles": mv["compiles"],
                              "steps": mv["applied_steps"]})
    util.write_json(C.phase_dir(4) / "index.json",
                    {"phase": 4, "designs": index, "llm_stats": llm.stats()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
