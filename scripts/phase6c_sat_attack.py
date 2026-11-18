#!/usr/bin/env python3
"""PSAT harness; unkeyed redaction is explicitly not a key-recovery experiment."""
import json, os, re, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, bench, overhead, util


def classify(log, returncode, key_count):
    if re.search(r'(?:I/O|io|input/output).*mismatch', log, re.I):
        return 'io_mismatch', None
    key = re.search(r'^key=([01]+)\s*$', log, re.M)
    if returncode == 0 and key and len(key[1]) == key_count and key_count:
        # PSAT's randomized key verification is empirical, not a formal proof.
        hd = re.search(r'Average Hamming distance:\s*([\d.]+)', log)
        if hd and float(hd[1]) == 0 and 'UNSAT model' not in log:
            return 'SAT', key[1]
        return 'candidate_key_unverified', key[1]
    return 'tool_error', None


def analyse(design):
    out = C.phase_dir('6c')
    result = {'design': design, 'outcome': 'error', 'runtime_s': None, 'recovered_key': None,
              'tool': 'DfX-NYUAD/PSAT sld', 'timeout_s': int(os.environ.get('GREAT_SAT_TIMEOUT', '7200'))}
    try:
        verified = json.loads((C.PHASE_DIRS[5] / f'{design}.verification.json').read_text())
        if verified.get('verdict') != 'PASS' or not verified.get('formal', {}).get('proved'):
            result.update(outcome='not_verified', reason='Phase-5 formal equivalence proof required')
            return result
        mapped = overhead.redacted_mapping(design)
        rtl, mf = overhead.inputs(design)
        result['artifact_sha256'] = overhead.digest(rtl)
        golden = bench.convert(C.PHASE_DIRS[0] / f'{design}.mapped.json', out / f'{design}.original.bench')
        redacted = bench.convert(mapped['mapped_json'], out / f'{design}.redacted.bench',
                                 {p['redacted']: p['original'] for p in mf['port_manifest']},
                                 {v: k for k, v in mf['identifier_manifest'].items()})
        result.update(golden=golden, redacted=redacted)
        if golden['signature'] != redacted['signature'] or golden.get('unresolved_state_names') or redacted.get('unresolved_state_names'):
            result.update(outcome='io_mismatch', reason='Scan-cut interfaces cannot be aligned; not evidence of resistance')
            return result
        text = Path(redacted['bench']).read_text()
        count = len(re.findall(r'INPUT\(keyinput[^)]*\)', text))
        result['key_inputs'] = count
        if not count:
            result.update(outcome='not_applicable_no_key', reason='Equivalent RTL redaction has no hidden key inputs; PSAT key recovery is inapplicable')
            return result
        exe = os.environ.get('GREAT_SAT_BINARY', str(C.ROOT / 'tools/PSAT/bin/sld'))
        if not Path(exe).is_file():
            result.update(outcome='tool_unavailable', reason='run scripts/setup_sat_attack.py')
            return result
        Path(redacted['bench'] + '.stoch').write_text('# OUTPUT_SAMPLING_ON OUTPUT_SAMPLING_ITERATIONS OUTPUT_SAMPLING_FOR_TEST_ON TEST_PATTERNS\nfalse 1 false 10000\nNEXT_GATE\n')
        start = time.monotonic()
        try:
            r = subprocess.run([exe, redacted['bench'], golden['bench']], capture_output=True, text=True, timeout=result['timeout_s'], env=dict(os.environ, OMP_NUM_THREADS=os.environ.get('OMP_NUM_THREADS', '1')))
            log = r.stdout+r.stderr
            result['outcome'], result['recovered_key'] = classify(log, r.returncode, count)
            result['returncode'] = r.returncode
        except subprocess.TimeoutExpired as exc:
            log = (exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout, bytes) else (exc.stdout or '')
            result['outcome'] = 'TO'
        result['runtime_s'] = time.monotonic()-start
        (out / f'{design}.sat.log').write_text(log)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result['reason'] = str(exc)
    finally:
        util.write_json(out / f'{design}.sat.json', result)
    return result


def main():
    ap = util.design_args(__doc__)
    ap.add_argument('--strict', action='store_true', help='exit nonzero for unavailable/failed measurements')
    args = ap.parse_args()
    results = [analyse(p.stem) for p in util.resolve_designs(args)]
    for r in results:
        util.info(f"{r['design']}: {r['outcome']} {r.get('reason', '')}")
    return int(args.strict and any(r['outcome'] in ('error', 'tool_error', 'not_verified', 'tool_unavailable') for r in results))

if __name__ == '__main__':
    raise SystemExit(main())
