"""Lightweight, comment-aware Verilog-2001 source analysis and rewriting.

Deliberately *not* a full parser.  Everything here operates on the token stream
so that rewrites are byte-precise and never disturb code the pipeline did not
intend to touch -- the property the paper's fault taxonomy (partial substitution,
duplicated declaration, dangling wire) is mostly about.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

KEYWORDS = set("""
module endmodule input output inout wire reg integer real time realtime parameter
localparam assign always initial begin end if else case casex casez endcase default
for while repeat forever function endfunction task endtask generate endgenerate
genvar posedge negedge or and not xor xnor nand nor buf bufif0 bufif1 notif0 notif1
signed unsigned automatic specify endspecify primitive endprimitive table endtable
defparam disable fork join wait event force release assign deassign supply0 supply1
tri triand trior tri0 tri1 trireg wand wor scalared vectored small medium large
pulldown pullup strong0 strong1 weak0 weak1 highz0 highz1 edge include define ifdef
ifndef endif else elsif undef timescale celldefine endcelldefine unconnected_drive
nettype macromodule pmos nmos cmos rcmos rpmos rnmos rtran tran tranif0 tranif1
""".split())

# token kinds: code, lcomment, bcomment, string, directive
_TOK = re.compile(r"""
    (?P<lcomment>//[^\n]*)
  | (?P<bcomment>/\*.*?\*/)
  | (?P<string>"(?:\\.|[^"\\])*")
  | (?P<directive>^[ \t]*`[A-Za-z_]\w*[^\n]*)
""", re.S | re.M | re.X)

IDENT = re.compile(r"\\\S+\s|[A-Za-z_][A-Za-z0-9_$]*")
SIZED_LIT = re.compile(r"\b(\d+)\s*'\s*([bBoOdDhH])\s*([0-9a-fA-FxXzZ_?]+)")


def _is_member_ref(text: str, start: int) -> bool:
    """True if the identifier at `start` is the name-side of a `.` reference.

    In Verilog a `.` immediately before an identifier means it is a child
    module's port or parameter name (``.clk(sig)``, ``#(.WIDTH(8))``) or a
    hierarchical/struct member -- never a signal in the enclosing module.
    Renaming such a token rewrites the *child's* port name and breaks the
    instantiation, so signal/port renaming and the residual-leakage scan must
    both leave it alone.  The RHS ``sig`` inside the parentheses is a normal
    reference and is still renamed.
    """
    j = start - 1
    while j >= 0 and text[j] in " \t\n":
        j -= 1
    return j >= 0 and text[j] == "."


@dataclass
class Span:
    kind: str
    start: int
    end: int


def scan(src: str) -> list[Span]:
    """Split the source into code / comment / string / directive spans."""
    spans, pos = [], 0
    for m in _TOK.finditer(src):
        if m.start() > pos:
            spans.append(Span("code", pos, m.start()))
        spans.append(Span(m.lastgroup, m.start(), m.end()))
        pos = m.end()
    if pos < len(src):
        spans.append(Span("code", pos, len(src)))
    return spans


def code_mask(src: str) -> list[bool]:
    """True at every character position that is real code (not comment/string)."""
    mask = [False] * len(src)
    for sp in scan(src):
        if sp.kind == "code":
            for i in range(sp.start, sp.end):
                mask[i] = True
    return mask


def is_tool_pragma(comment: str) -> bool:
    """Tool-control comments are executable synthesis/simulation metadata."""
    return bool(re.match(r"\s*(?://|/\*)\s*(?:synthesis|synopsys|pragma|verilator|cadence|altera|xilinx)\b",
                         comment, re.I))


def strip_comments(src: str, keep_directives: bool = True) -> str:
    out, mask = [], scan(src)
    for sp in mask:
        if sp.kind in ("lcomment", "bcomment"):
            out.append("\n" * src.count("\n", sp.start, sp.end))
        else:
            out.append(src[sp.start:sp.end])
    return "".join(out)


def code_only(src: str) -> str:
    """Comments blanked to spaces, newlines preserved (offsets unchanged)."""
    buf = list(src)
    for sp in scan(src):
        if sp.kind in ("lcomment", "bcomment", "string"):
            for i in range(sp.start, sp.end):
                if buf[i] != "\n":
                    buf[i] = " "
    return "".join(buf)


def analysis_view(src: str, limit: int) -> tuple[str, dict]:
    """Bound analysis prompts without letting large literal ROMs hide all logic.

    This changes only the LLM view, never synthesis or transformation inputs.
    Retain both ends of long runs of literal ROM assignments and record their
    digest so that omitted rows remain auditable.
    """
    import hashlib
    row = re.compile(r"(?m)^[ \t]*\d+\s*'[bBoOdDhH][0-9a-fA-F_]+\s*:\s*"
                     r"[A-Za-z_]\w*\s*=\s*\d+\s*'[bBoOdDhH][0-9a-fA-F_]+\s*;[^\n]*(?:\n|$)")
    matches, groups = list(row.finditer(src)), []
    for match in matches:
        if groups and not code_only(src[groups[-1][-1].end():match.start()]).strip():
            groups[-1].append(match)
        else:
            groups.append([match])
    edits, omitted = [], 0
    for group in groups:
        if len(src) <= limit:
            break
        if len(group) < 32:
            continue
        start, end = group[4].start(), group[-5].end()
        count = len(group) - 8
        digest = hashlib.sha256(src[start:end].encode()).hexdigest()
        edits.append((start, end, f"// {count} literal ROM rows omitted from analysis view; SHA256 {digest}\n"))
        omitted += count
    view = src
    for start, end, replacement in reversed(edits):
        view = view[:start] + replacement + view[end:]
    comments_removed = len(view) > limit
    if comments_removed:
        view = strip_comments(view)
    compact_length = len(view)
    if len(view) > limit:
        view = view[:limit] + "\n// ... analysis view truncated ...\n"
    return view, {"original_characters": len(src), "compact_characters": compact_length,
                  "omitted_literal_rom_rows": omitted,
                  "omission_digests": [hashlib.sha256(src[a:b].encode()).hexdigest() for a,b,_ in edits],
                  "comments_removed_for_budget": comments_removed,
                  "truncated": compact_length > limit}


# ------------------------------------------------------------- identifiers
def identifiers(src: str) -> dict[str, list[int]]:
    """Identifier -> code-position occurrences (comments and strings excluded)."""
    cs, out = code_only(src), {}
    for m in IDENT.finditer(cs):
        name = m.group(0).strip()
        if name in KEYWORDS or name[0].isdigit():
            continue
        out.setdefault(name, []).append(m.start())
    return out


def rename(src: str, mapping: dict[str, str], *, in_comments: bool = False) -> tuple[str, dict]:
    """Whole-token rename across code (never inside comments unless asked).

    Returns (new_source, per-identifier occurrence counts) -- the count is the
    audit evidence against the paper's 'partial substitution' fault.
    """
    if not mapping:
        return src, {}
    counts = {k: 0 for k in mapping}
    spans = scan(src)
    pieces = []
    for sp in spans:
        chunk = src[sp.start:sp.end]
        editable = sp.kind == "code" or (in_comments and sp.kind in ("lcomment", "bcomment"))
        if editable:
            def sub(m, _chunk=chunk):
                nm = m.group(0)
                if nm in mapping and not _is_member_ref(_chunk, m.start()):
                    counts[nm] += 1
                    return mapping[nm]
                return nm
            chunk = IDENT.sub(sub, chunk)
        pieces.append(chunk)
    return "".join(pieces), counts


def residual_occurrences(src: str, names) -> dict[str, list[str]]:
    """grep -w equivalent used as the post-rename verification pass (Step 4b).

    Token-based rather than a bare `\b` regex: `\bb0\b` matches the "b0" inside
    the literal `1'b0`, which would report a spurious surviving identifier every
    time a design renames a signal whose name looks like a base specifier.
    """
    wanted = set(names)
    hits: dict[str, list[str]] = {}
    for ln, line in enumerate(src.splitlines(), 1):
        # blank out sized literals so their base+digits cannot look like an ident
        clean = SIZED_LIT.sub(lambda m: " " * len(m.group(0)), line)
        clean = re.sub(r"'[bodhBODH][0-9a-fA-FxXzZ_]*", lambda m: " " * len(m.group(0)),
                       clean)
        for m in IDENT.finditer(clean):
            n = m.group(0).strip()
            if n in wanted and not _is_member_ref(clean, m.start()):
                hits.setdefault(n, []).append(f"{ln}: {line.strip()}")
    return hits


# ----------------------------------------------------------------- modules
@dataclass
class Module:
    name: str
    start: int              # offset of 'module'
    header_end: int         # offset just past the header ');'
    end: int                # offset just past 'endmodule'
    ports: list = field(default_factory=list)   # {name, dir, width, msb, lsb}
    src: str = ""


def _match_paren(s: str, i: int) -> int:
    depth = 0
    while i < len(s):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def parse_modules(src: str) -> list[Module]:
    cs = code_only(src)
    mods = []
    for m in re.finditer(r"\bmodule\b", cs):
        st = m.start()
        endm = cs.find("endmodule", st)
        if endm == -1:
            continue
        po = cs.find("(", st)
        semi = cs.find(";", st)
        name = re.search(r"\bmodule\s+(\\\S+|[A-Za-z_]\w*)", cs[st:st + 200])
        nm = name.group(1) if name else "?"
        # A parameterized header has two parenthesized lists. Only the
        # second list declares ports; scanning the #(...) list loses all ANSI
        # ports and can make equivalence simulation vacuous.
        if po != -1 and (semi == -1 or po < semi):
            prefix = cs[st:po].rstrip()
            if prefix.endswith("#"):
                parameter_end = _match_paren(cs, po)
                after_parameters = parameter_end + 1
                while after_parameters < len(cs) and cs[after_parameters].isspace():
                    after_parameters += 1
                po = after_parameters if cs[after_parameters:after_parameters + 1] == "(" else -1
        if po != -1 and (semi == -1 or po < semi):
            pc = _match_paren(cs, po)
            hdr_end = cs.find(";", pc) + 1
            plist = cs[po + 1:pc]
        else:
            hdr_end, plist = semi + 1, ""
        mod = Module(nm, st, hdr_end, endm + len("endmodule"))
        mod.src = src[mod.start:mod.end]
        # NOTE: the body must come from the comment-blanked text.  Step 4i
        # deliberately injects prose comments, and a comment such as
        # "Final calibrated output register for channel A" would otherwise be
        # parsed as a port declaration named `register`.
        mod.ports = parse_ports(plist, cs[hdr_end:mod.end])
        mods.append(mod)
    return mods


def header_parameter_declarations(module: Module) -> list[str]:
    """Default top parameters for a standalone testbench's port ranges.

    Preserve Verilog expressions and types; the HDL compiler evaluates them.
    Split at outer commas so function calls and concatenations remain intact.
    """
    header = module.src[:module.header_end - module.start]
    clean = code_only(header)
    match = re.search(r"#\s*\(", clean)
    if not match:
        return []
    opening = clean.find("(", match.start())
    closing = _match_paren(clean, opening)
    blob = header[opening + 1:closing]
    masked = code_only(blob)
    entries, start, depth = [], 0, 0
    for i, char in enumerate(masked):
        if char in "([{": depth += 1
        elif char in ")]}": depth -= 1
        elif char == "," and depth == 0:
            entries.append(blob[start:i]); start = i + 1
    entries.append(blob[start:])
    declarations = []; inherited_type = ""
    for entry in entries:
        entry = strip_comments(entry).strip()
        if re.match(r"parameter\b", entry):
            entry = re.sub(r"^parameter\s*", "", entry)
            inherited_type = ""
        match = re.match(r"(.*?)([A-Za-z_]\w*)\s*=", entry, re.S)
        if not match:
            raise ValueError("Unsupported parameter declaration in top header")
        explicit_type = match.group(1).strip()
        if explicit_type: inherited_type = explicit_type
        prefix = (inherited_type + " ") if inherited_type else ""
        declarations.append("localparam " + prefix + entry[match.start(2):] + ";")
    return declarations


_PORTDECL = re.compile(
    r"\b(input|output|inout)\b\s*(?:(wire|reg|logic)\b\s*)?(?:(signed)\b\s*)?"
    r"(?:\[\s*([^\]:]+?)\s*:\s*([^\]]+?)\s*\]\s*)?(?P<names>[A-Za-z_]\w*(?:\s*,\s*(?!(?:input|output|inout|wire|reg|logic|parameter|localparam)\b)[A-Za-z_]\w*)*)")


_SUBPROG = re.compile(r"\bfunction\b.*?\bendfunction\b|\btask\b.*?\bendtask\b",
                      re.S | re.I)


def _strip_subprograms(text: str) -> str:
    """Blank out function/task bodies (offset-preserving).

    A `function [31:0] le(input [31:0] w);` declares `w` as a *function
    argument*, not a module port.  The non-ANSI port scan below walks the whole
    module body for `input`/`output` declarations, so without this a subprogram
    argument is mistaken for an 11th top-level port -- which then breaks any
    instantiation the verifier builds against that phantom port.
    """
    return _SUBPROG.sub(lambda m: " " * len(m.group(0)), text)


def parse_ports(plist: str, body: str) -> list[dict]:
    ports, order = {}, []
    body = _strip_subprograms(body)
    for text in (plist, body):
        for m in _PORTDECL.finditer(text):
            direction, msb, lsb, names = m.group(1), m.group(4), m.group(5), m.group(6)
            for n in [x.strip() for x in names.split(",")]:
                # A name list never crosses into the next declaration: the first
                # keyword encountered (input/output/wire/reg/...) ends it.
                if not n or n in KEYWORDS:
                    break
                if n not in ports:
                    order.append(n)
                ports[n] = {"name": n, "dir": direction, "msb": msb, "lsb": lsb,
                            "width": None if msb is None else f"[{msb}:{lsb}]"}
    # Non-ANSI header (`module m(a, b, c); input a; ...`): the bare name list
    # fixes the port *order*.  This only applies when EVERY entry is bare -- an
    # ANSI header such as `input wire clk, reset_n,` also contains bare-looking
    # entries and must not be mistaken for one.
    entries = [x for x in plist.split(",") if x.strip()]
    bare = [x.strip() for x in entries if re.fullmatch(r"\s*\w+\s*", x)]
    if entries and len(bare) == len(entries) and all(b in ports for b in bare):
        order = bare
    return [ports[n] for n in order if n in ports]


# ------------------------------------------------------- declarations & nets
DECL = re.compile(
    r"^[ \t]*(?P<kw>input|output|inout|wire|reg|localparam|parameter|integer|genvar)\b"
    r"(?P<mid>[^;]*?);", re.M | re.S)


def declarations(src: str) -> list[dict]:
    cs, out = code_only(src), []
    for m in DECL.finditer(cs):
        mid = m.group("mid")
        rng = re.search(r"\[\s*([^\]:]+?)\s*:\s*([^\]]+?)\s*\]", mid)
        # strip the range, then take identifiers before any '=' initialiser
        body = mid[rng.end():] if rng else mid
        names = []
        for part in body.split(","):
            head = part.split("=")[0]
            ids = [x for x in IDENT.findall(head) if x not in KEYWORDS]
            if ids:
                names.append(ids[0])
        out.append({"kw": m.group("kw"), "names": names,
                    "msb": rng.group(1) if rng else None,
                    "lsb": rng.group(2) if rng else None,
                    "start": m.start(), "end": m.end(),
                    "text": src[m.start():m.end()]})
    return out


ASSIGN = re.compile(r"\bassign\b\s+(?P<lhs>[^=;]+?)=(?P<rhs>[^;]+);")
NBA    = re.compile(r"(?P<lhs>[A-Za-z_]\w*(?:\s*\[[^\]]*\])*)\s*<=\s*(?P<rhs>[^;]+);")
BA     = re.compile(r"(?P<lhs>[A-Za-z_]\w*(?:\s*\[[^\]]*\])*)\s*(?<![<>=!])=\s*(?P<rhs>[^;]+);")


def _lhs_name(t: str) -> str | None:
    ids = [x for x in IDENT.findall(t) if x not in KEYWORDS]
    return ids[0] if ids else None


def driver_graph(src: str) -> dict[str, set[str]]:
    """signal -> set of signals that drive it (continuous + procedural)."""
    cs = code_only(src)
    g: dict[str, set[str]] = {}
    for rx in (ASSIGN, NBA, BA):
        for m in rx.finditer(cs):
            lhs = _lhs_name(m.group("lhs"))
            if not lhs:
                continue
            rhs = {x for x in IDENT.findall(m.group("rhs")) if x not in KEYWORDS
                   and not x[0].isdigit()}
            g.setdefault(lhs, set()).update(rhs)
    return g


def dependency_closure(src: str, seeds) -> set[str]:
    """Transitive fan-in *and* fan-out closure of `seeds` (paper Listing 18).

    Fan-out is what stops the 'dangling wire' fault: a wire exclusively driven by
    a HIGH signal is itself HIGH and must move with it.
    """
    g = driver_graph(src)
    rev: dict[str, set[str]] = {}
    for dst, srcs in g.items():
        for s in srcs:
            rev.setdefault(s, set()).add(dst)
    seen, work = set(seeds), list(seeds)
    while work:
        n = work.pop()
        for nxt in list(g.get(n, ())) + list(rev.get(n, ())):
            if nxt not in seen:
                seen.add(nxt)
                work.append(nxt)
    return seen


def tag_placement_scan(src: str, tagged_names) -> list[str]:
    """Tag-placement validation (RL-RGOT design note Section 2.2): before RTL
    annotation, verify every name about to be tagged is a real identifier
    that literally appears in the source and not a reserved Verilog keyword.

    Catches the failure mode where a tier tag gets attached to the wrong
    token (e.g. a keyword picked up by a loose regex, or a name the LLM
    invented that never existed in the RTL). Returns a list of problem
    descriptions; empty means clean.
    """
    problems: list[str] = []
    present = set(IDENT.findall(code_only(src))) - KEYWORDS
    for name in tagged_names:
        if name in KEYWORDS:
            problems.append(f"tag placed on reserved keyword, not an identifier: '{name}'")
        elif name not in present:
            problems.append(f"tagged signal '{name}' not found as an identifier in the RTL")
    return problems


# ------------------------------------------------------------------ literals
def sized_literals(src: str) -> list[dict]:
    cs, out = code_only(src), []
    for m in SIZED_LIT.finditer(cs):
        width, base, digits = int(m.group(1)), m.group(2).lower(), m.group(3)
        clean = digits.replace("_", "")
        if re.search(r"[xXzZ?]", clean) or width == 0:
            continue
        try:
            val = int(clean, {"b": 2, "o": 8, "d": 10, "h": 16}[base])
        except ValueError:
            continue
        out.append({"start": m.start(), "end": m.end(), "text": m.group(0),
                    "width": width, "base": base, "value": val,
                    "line": src.count("\n", 0, m.start()) + 1})
    return out


def line_of(src: str, off: int) -> int:
    return src.count("\n", 0, off) + 1


def localparams(src: str) -> list[dict]:
    out = []
    for d in declarations(src):
        if d["kw"] not in ("localparam", "parameter"):
            continue
        for m in re.finditer(r"([A-Za-z_]\w*)\s*=\s*([^,;]+)", d["text"]):
            out.append({"name": m.group(1), "value": m.group(2).strip(),
                        "kw": d["kw"], "decl_start": d["start"], "decl_end": d["end"],
                        "decl_text": d["text"], "msb": d["msb"], "lsb": d["lsb"]})
    return out


def case_items(src: str) -> list[dict]:
    """Every `case` block with its item labels -- FSM discovery input."""
    cs, out = code_only(src), []
    for m in re.finditer(r"\bcase[xz]?\s*\(", cs):
        close = _match_paren(cs, cs.index("(", m.start()))
        endc = cs.find("endcase", close)
        if endc == -1:
            continue
        body = cs[close + 1:endc]
        labels = [lab.strip() for lab in re.findall(r"^\s*([^:;\n]+?)\s*:", body, re.M)]
        out.append({"select": cs[cs.index("(", m.start()) + 1:close].strip(),
                    "labels": [l for l in labels if l and l != "default"],
                    "start": m.start(), "end": endc + 7})
    return out
