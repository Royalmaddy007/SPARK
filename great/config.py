"""Central configuration for the GREAT/DAC-26 redaction pipeline."""
from __future__ import annotations
import os, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXAMPLES_DIR = Path(os.environ.get("GREAT_EXAMPLES_DIR", ROOT / "examples" / "rtl")).resolve()
# Unmodified upstream sibling modules needed to *elaborate* two of the targets.
# They are never transformed and never shipped -- context for the tools only.
DEPS_DIR     = Path(os.environ.get("GREAT_DEPS_DIR", ROOT / "examples" / "deps")).resolve()
PIPELINE_DIR = Path(os.environ.get("GREAT_PIPELINE_DIR", ROOT / "pipeline")).resolve()
CACHE_DIR    = Path(os.environ.get("GREAT_CACHE_DIR", PIPELINE_DIR / ".llm_cache")).resolve()
LOG_DIR      = PIPELINE_DIR / "genai_logs"

PHASE_DIRS = {
    0:  PIPELINE_DIR / "phase0_netlist",
    1:  PIPELINE_DIR / "phase1_profiling",
    2:  PIPELINE_DIR / "phase2_sensitivity",
    3:  PIPELINE_DIR / "phase3_strategy",
    4:  PIPELINE_DIR / "phase4_transform",
    5:  PIPELINE_DIR / "phase5_verification",
    6:  PIPELINE_DIR / "phase6_leakage",
    "4b": PIPELINE_DIR / "phase4b_overhead",
    "6c": PIPELINE_DIR / "phase6c_sat_attack",
    "6d": PIPELINE_DIR / "phase6d_dana_attack",
    "6e": PIPELINE_DIR / "phase6e_removal_attack",
    "6b": PIPELINE_DIR / "phase6b_escalation",
    "tb": PIPELINE_DIR / "testbench",
    7:  PIPELINE_DIR / "report",
}

# ---------------------------------------------------------------- LLM
OLLAMA_HOST  = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
LLM_MODEL    = os.environ.get("GREAT_MODEL", "qwen3.8:latest")
LLM_TIMEOUT  = int(os.environ.get("GREAT_LLM_TIMEOUT", "900"))
LLM_MAX_CTX  = int(os.environ.get("GREAT_LLM_MAX_CTX", "16384"))
LLM_CACHE    = os.environ.get("GREAT_LLM_CACHE", "1") != "0"

# Three local personas by default. effective_jurors optionally assigns a
# separately configured API model and records the effective run identity.
ENSEMBLE = [
    {"id": "juror_a", "temperature": 0.0, "seed": 11,
     "persona": "a conservative hardware security auditor who over-tags when unsure"},
    {"id": "juror_b", "temperature": 0.6, "seed": 22,
     "persona": "a pragmatic RTL designer who tags only genuine crown-jewel logic"},
    {"id": "juror_c", "temperature": 0.9, "seed": 33,
     "persona": "an offensive red-team reverse engineer who tags whatever helps an attacker"},
]

TIER_RANK = {"LOW": 0, "MED": 1, "HIGH": 2}
RANK_TIER = {v: k for k, v in TIER_RANK.items()}

# Table III -- transformation set by attacker budget tier.
BUDGET_TRANSFORMS = {
    "B0": ["4b", "4c", "4e", "4f", "4i"],
    "B1": ["4b", "4c", "4e", "4f", "4i", "4a", "4d", "4g"],
    "B2": ["4b", "4c", "4e", "4f", "4i", "4a", "4d", "4g", "4h", "4j", "4k"],
}
BUDGET_ORDER = ["B0", "B1", "B2"]

# Phase 6B escalation thresholds, in bits of KL leakage.
TAU_LOW, TAU_HIGH = 1.0, 4.0
R_MAX = int(os.environ.get("GREAT_RMAX", "2"))

# HMAC key for deterministic identifier anonymisation (Step 4b).
RENAME_KEY = os.environ.get("GREAT_RENAME_KEY", "seal-challengers-dac26").encode()

# ---------------------------------------------------------------- tools
def _tool(name: str, *fallbacks: str) -> str | None:
    """Prefer a working system binary over a broken conda shim."""
    for cand in (*fallbacks, name):
        if cand and (os.path.isabs(cand) and os.access(cand, os.X_OK) or shutil.which(cand)):
            return cand
    return None

IVERILOG = _tool("iverilog", "/usr/bin/iverilog")
VVP      = _tool("vvp", "/usr/bin/vvp")
YOSYS    = _tool("yosys")
VERILATOR= _tool("verilator")

_DEP_CACHE: dict = {}


def _dep_index() -> dict:
    """{module name -> file} and {file -> modules instantiated} over examples/deps."""
    if _DEP_CACHE:
        return _DEP_CACHE
    import re
    defines, uses = {}, {}
    if DEPS_DIR.exists():
        for p in sorted(DEPS_DIR.glob("*.v")):
            txt = p.read_text()
            # strip comments cheaply so a commented-out instance is not counted
            txt = re.sub(r"//[^\n]*|/\*.*?\*/", " ", txt, flags=re.S)
            mods = re.findall(r"\bmodule\s+([A-Za-z_]\w*)", txt)
            for m in mods:
                defines[m] = str(p)
            # `foo u_foo (` -- an instantiation, not a declaration or a keyword
            uses[str(p)] = {m for m in re.findall(
                r"^\s*([A-Za-z_]\w*)\s+[A-Za-z_]\w*\s*\(", txt, re.M)
                if m not in ("module", "input", "output", "inout", "wire", "reg",
                             "assign", "always", "if", "case", "for", "return",
                             "function", "task", "parameter", "localparam", "integer")}
    _DEP_CACHE["defines"] = defines
    _DEP_CACHE["uses"] = uses
    return _DEP_CACHE


def dep_files(design: str | None = None) -> list[str]:
    """Sibling modules needed to elaborate `design`, and nothing more.

    Two of the dependency files are themselves redaction targets, and several
    are unrelated to any given design.  Handing every file to iverilog/yosys
    every time would both re-declare the module under test and distort the
    synthesised gate count used for the overhead axis, so the closure is
    resolved from the design's own instantiations instead.
    """
    idx = _dep_index()
    if design is None:
        return list(dict.fromkeys(idx["defines"].values()))
    src_file = EXAMPLES_DIR / f"{design}.v"
    if not src_file.exists():
        return []
    import re
    txt = re.sub(r"//[^\n]*|/\*.*?\*/", " ", src_file.read_text(), flags=re.S)
    own = set(re.findall(r"\bmodule\s+([A-Za-z_]\w*)", txt))
    want = {m for m in re.findall(r"^\s*([A-Za-z_]\w*)\s+[A-Za-z_]\w*\s*\(",
                                  txt, re.M)} - own
    files, seen = [], set()
    while want:
        m = want.pop()
        f = idx["defines"].get(m)
        if not f or f in seen:
            continue
        seen.add(f)
        files.append(f)
        # a dependency's own dependencies, minus anything the design defines
        want |= {u for u in idx["uses"].get(f, set())
                 if u not in own and u in idx["defines"]}
    return sorted(files)


def phase_dir(p, sub: str | None = None) -> Path:
    d = PHASE_DIRS[p] if sub is None else PHASE_DIRS[p] / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def effective_jurors():
    """Resolve optional cross-model configuration without silently changing providers."""
    import warnings
    jurors = [dict(j) for j in ENSEMBLE]
    for juror in jurors:
        juror.setdefault("backend", "ollama")
        juror.setdefault("model", LLM_MODEL)
    model = os.environ.get("GREAT_CROSS_MODEL")
    key = os.environ.get("GREAT_CROSS_MODEL_API_KEY")
    url = os.environ.get("GREAT_CROSS_MODEL_API_URL")
    if model and key and url:
        jurors[-1].update(backend="api", model=model)
    else:
        warnings.warn("Cross-model juror unavailable: set GREAT_CROSS_MODEL, "
                      "GREAT_CROSS_MODEL_API_KEY and GREAT_CROSS_MODEL_API_URL "
                      "(OpenAI-compatible chat completions endpoint); using single-model personas.")
    return jurors


def ensemble_kind(jurors):
    return ("cross_model_partial" if len({j["model"] for j in jurors}) > 1
            else "single_model_multi_persona")
