"""ModelSim (Intel FPGA Starter Edition) batch-mode driver.

Thin, robust wrappers around `vlib` / `vlog` / `vsim -c` so the pipeline can
compile and simulate a design + testbench headlessly and parse a machine
verdict.  The user's install is Intel FPGA Starter Edition (`modelsim_ase`),
discovered on PATH or under the usual intelFPGA_lite location.
"""
from __future__ import annotations
import os, re, shutil, subprocess, tempfile
from pathlib import Path


def _find_bindir() -> str | None:
    v = shutil.which("vsim")
    if v:
        return str(Path(v).parent)
    for cand in (Path.home().glob("intelFPGA*/**/modelsim_ase/bin"),):
        for p in cand:
            if (p / "vsim").exists():
                return str(p)
    for base in ("/opt", str(Path.home())):
        for root, _dirs, files in os.walk(base):
            if "vsim" in files and "modelsim" in root.lower():
                return root
    return None


BINDIR = _find_bindir()
AVAILABLE = BINDIR is not None


def _env() -> dict:
    e = dict(os.environ)
    if BINDIR:
        e["PATH"] = BINDIR + os.pathsep + e.get("PATH", "")
    return e


def _run(cmd, cwd, timeout, inp=None):
    return subprocess.run(cmd, cwd=cwd, env=_env(), input=inp,
                          capture_output=True, text=True, timeout=timeout)


def simulate(sources: list[str], tb_top: str, workdir: Path,
             timeout: int = 900, vlog_extra: list[str] | None = None) -> dict:
    """Compile `sources` and run `tb_top` in ModelSim batch mode.

    The testbench is expected to `$display` a line containing `TB_PASS <n>` or
    `TB_FAIL <n>` and then `$finish`.  Returns a verdict dict; never raises.
    """
    if not AVAILABLE:
        return {"available": False, "compiled": False, "ran": False,
                "passed": None, "reason": "ModelSim (vsim) not found"}
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        _run(["vlib", "work"], workdir, 60)
        _run(["vmap", "work", "work"], workdir, 60)
        # compile everything together; -sv for SystemVerilog testbenches
        vlog_cmd = ["vlog", "-quiet", "-sv", *(vlog_extra or []), *map(str, sources)]
        c = _run(vlog_cmd, workdir, timeout)
        clog = c.stdout + c.stderr
        if re.search(r"^\*\* Error", clog, re.M) or "Errors: 0" not in clog:
            # some vlog builds omit the summary on success; treat explicit Error as fail
            if re.search(r"^\*\* Error", clog, re.M):
                return {"available": True, "compiled": False, "ran": False,
                        "passed": None, "stage": "vlog",
                        "log": clog[-4000:]}
        # run
        do = "onerror {quit -code 3}; run -all; quit -f"
        s = _run(["vsim", "-c", "-quiet", "-do", do, tb_top], workdir, timeout)
        slog = s.stdout + s.stderr
        mp = re.search(r"TB_PASS\s+(\d+)", slog)
        mf = re.search(r"TB_FAIL\s+(\d+)", slog)
        sim_err = re.search(r"^\*\* (Error|Fatal)", slog, re.M)
        passed = bool(mp) and not mf
        return {"available": True, "compiled": True, "ran": True,
                "passed": passed,
                "n_vectors": int(mp.group(1)) if mp else None,
                "n_fail": int(mf.group(1)) if mf else None,
                "sim_error": bool(sim_err),
                "mismatches": re.findall(r"^# MISMATCH.*$", slog, re.M)[:15],
                "log": slog[-4000:]}
    except subprocess.TimeoutExpired:
        return {"available": True, "compiled": None, "ran": False, "passed": None,
                "reason": f"ModelSim timed out after {timeout}s"}
    except Exception as exc:                                    # noqa: BLE001
        return {"available": True, "compiled": None, "ran": False, "passed": None,
                "reason": f"{type(exc).__name__}: {exc}"}
