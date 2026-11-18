"""Comparable ASAP7 synthesis and OpenSTA estimates; no layout parasitics."""
from __future__ import annotations
import hashlib, json, math, os, re, shutil, subprocess
from pathlib import Path
from . import config as C, netlist as N, vlog, util


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mapped_area(path):
    """Use exactly the cell-area lookup used by Phase 0, refusing unknown cells."""
    return N.cell_area(path, strict=True)


def inputs(design):
    mf = json.loads((C.PHASE_DIRS[4] / f"{design}.manifests.json").read_text())
    return C.ROOT / mf["redacted_rtl"], mf


def _redacted_mapping(design):
    rtl, mf = inputs(design)
    out = C.phase_dir("4b")
    fingerprint = {"rtl": digest(rtl), "liberty": digest(N.ASAP7_LIB),
                   "deps": {d: digest(d) for d in C.dep_files(design)},
                   "yosys": C.YOSYS}
    cache = out / f"{design}.mapping.json"
    if cache.exists():
        old = json.loads(cache.read_text())
        if old.get("fingerprint") == fingerprint and all(Path(old[k]).exists() for k in ("mapped_json", "mapped_v")):
            return old
    top = vlog.parse_modules(rtl.read_text())[0].name
    result = N.map_to_asap7(rtl, top, out, deps=C.dep_files(design))
    if not result["ok"]:
        raise RuntimeError(str(result))
    result.update(top=top, fingerprint=fingerprint)
    util.write_json(cache, result)
    return result


def redacted_mapping(design):
    import fcntl
    with (C.phase_dir('4b') / f'{design}.mapping.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _redacted_mapping(design)


def sta_binary():
    return os.environ.get("GREAT_OPENSTA") or shutil.which("sta") or str(C.ROOT / "tools/opensta/usr/bin/sta")


def timing_power(netlist, top, out):
    """Explicit units, zero I/O delays, 1 fF load, 1 ns period, activity estimate."""
    period = float(os.environ.get("GREAT_PPA_PERIOD_PS", "1000"))
    load = float(os.environ.get("GREAT_PPA_LOAD_FF", "1"))
    activity = float(os.environ.get("GREAT_PPA_ACTIVITY", "0.1"))
    if period <= 0 or load < 0 or not 0 <= activity <= 1:
        raise ValueError("invalid PPA period/load/activity")
    # ASAP7 Liberty uses ps and fF.
    mapped = N.load_mapped_json(Path(netlist).with_suffix('.json'))['modules'][top]
    clock_bits = {b for cell in mapped['cells'].values()
                  for pin, bits in cell['connections'].items()
                  if pin.upper() in ('CLK', 'CK', 'CP') for b in bits}
    clock_ports = [name for name, p in mapped['ports'].items()
                   if p['direction'] == 'input' and set(p['bits']) & clock_bits]
    clock_constraints = "\n".join(
        f'create_clock -name design_clk_{i} -period {period} [get_ports {{{name}}}]'
        for i, name in enumerate(clock_ports))
    # OpenSTA's structural Verilog parser rejects concatenated assignment LHS.
    # Re-export the cached netlist with scalar LHS; no synthesis or remapping.
    sta_v = Path(str(out) + '.sta.v')
    ys = Path(str(out) + '.sta.ys')
    ys.write_text(f'read_verilog {netlist}\nwrite_verilog -noattr -simple-lhs {sta_v}\n')
    normal = subprocess.run([C.YOSYS, '-q', '-s', str(ys)], capture_output=True, text=True, timeout=60)
    if normal.returncode:
        raise RuntimeError('STA netlist re-export failed: ' + normal.stderr[-500:])
    sta_v.write_text(re.sub(r'\bwire\s+signed\b', 'wire', sta_v.read_text()))
    tcl = f'''read_liberty {{{N.ASAP7_LIB}}}
read_verilog {{{sta_v}}}
link_design {{{top}}}
set_cmd_units -time ps -capacitance fF -power mW
create_clock -name virtual_clk -period {period}
{clock_constraints}
set_input_delay 0 -clock virtual_clk [all_inputs]
set_output_delay 0 -clock virtual_clk [all_outputs]
set_input_transition 10 [all_inputs]
set_load {load} [all_outputs]
set_power_activity -global -activity {activity}
# Units explicitly set above
report_checks -path_delay max -unconstrained -digits 9
report_power -digits 12
exit
'''
    Path(str(out) + ".tcl").write_text(tcl)
    r = subprocess.run([sta_binary(), "-exit", str(Path(str(out) + '.tcl'))], capture_output=True, text=True, timeout=600)
    log = r.stdout + r.stderr
    Path(str(out) + ".log").write_text(log)
    if r.returncode or re.search(r"(^|\n)Error[: ]", log):
        raise RuntimeError(f"OpenSTA failed; see {Path(str(out) + '.log')}")
    delays = re.findall(r"([\d.eE+\-]+)\s+data arrival time", log)
    power = re.search(r"^Total\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)", log, re.M)
    if not delays or not power:
        raise RuntimeError(f"missing timing/power results; see {Path(str(out) + '.log')}")
    delay, watts = max(map(float, delays)), float(power[4])
    if not all(math.isfinite(v) and v > 0 for v in (delay, watts)):
        raise ValueError('OpenSTA returned nonpositive/nonfinite delay or power')
    # report_power always prints watts in this OpenSTA version, independent of
    # command input units. The integration run uses OpenSTA 2.0.17.
    return {"area_um2": mapped_area(Path(netlist).with_suffix('.json')),
            "delay_ps": delay, "power_mw": watts * 1000}


def analyse(design):
    out = C.phase_dir("4b")
    result = {"design": design, "status": "error", "original": None, "redacted": None, "overhead": None,
              "method": "ASAP7 RVT TT; OpenSTA; pre-layout; vectorless activity",
              "period_ps": float(os.environ.get("GREAT_PPA_PERIOD_PS", "1000")),
              "load_ff": float(os.environ.get("GREAT_PPA_LOAD_FF", "1")),
              "activity": float(os.environ.get("GREAT_PPA_ACTIVITY", "0.1"))}
    try:
        original = C.PHASE_DIRS[0] / f"{design}.mapped.v"
        if not original.exists():
            raise FileNotFoundError(f"cached Phase-0 mapping missing: {original}; run phase0")
        mapping = redacted_mapping(design)
        top = vlog.parse_modules(original.read_text())[0].name
        result["original"] = timing_power(original, top, out / f"{design}.original")
        result["redacted"] = timing_power(mapping["mapped_v"], mapping["top"], out / f"{design}.redacted")
        result["overhead"] = {k + "_x": result["redacted"][field] / result["original"][field]
                              for k, field in (("area", "area_um2"), ("delay", "delay_ps"), ("power", "power_mw"))}
        result.update(status="ok", artifact_sha256=digest(inputs(design)[0]),
                      original_sha256=digest(original), liberty_sha256=digest(N.ASAP7_LIB))
    except (OSError, ValueError, ZeroDivisionError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result["reason"] = str(exc)
    util.write_json(out / f"{design}.overhead.json", result)
    return result
