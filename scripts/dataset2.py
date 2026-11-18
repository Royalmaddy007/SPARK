#!/usr/bin/env python3
"""Isolated Verilog dataset with mandatory upstream ModelSim testbench admission."""
import argparse
import copy
import fcntl
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import dataset as D

ROOT = D.ROOT / 'datasets/opencores2'
ERROR = r'(?im)\*\*\s+(?:Error|Fatal):|\b(?:TB_FAIL|TEST_FAILED|mismatch|failed)\b|^#\s*(?:FAIL|ERROR)\b'


def successful(transcript, pass_regex):
    return (bool(re.search(pass_regex, transcript, re.M))
            and not re.search(ERROR, transcript)
            and '$finish' in transcript)


def simulate(core, candidate, source, row, config, timeout):
    """Use the combined DUT and upstream checker; never compare a DUT to itself."""
    work = ROOT / 'modelsim' / core
    work.mkdir(parents=True, exist_ok=True)
    result = {'status': 'test_blocked', 'input_sha256': row['sha256'], 'updated_utc': D.stamp()}
    try:
        if not config:
            # Discover only a checker with an explicit final success message and failure branch.
            possible = []
            for path in source.rglob('*'):
                if path.suffix.lower() not in {'.v', '.sv'}: continue
                text = path.read_text(errors='replace')
                if not re.search(r'\b' + re.escape(row['top']) + r'\s*(?:#\s*\([^;]*?\)\s*)?\w+\s*\(', text, re.S): continue
                messages = re.findall(r'\$display\s*\(\s*"([^"\n]+)"', text)
                passes = [s for s in messages if re.search(r'(?i)\b(?:all tests passed|test passed|tests passed|simulation passed|TB_PASS)\b', s) and '%' not in s]
                if not passes or not re.search(r'(?i)\b(?:fail|failed|error|mismatch)\b|\$fatal', text): continue
                if '$finish' not in text: continue
                modules = re.findall(r'\bmodule\s+(\w+)', text)
                if len(modules) == 1:
                    possible.append({'files': [str(path.relative_to(source))], 'top': modules[0],
                                     'pass_regex': re.escape(passes[-1]), 'discovery': 'upstream explicit pass/fail checker'})
            if len(possible) != 1:
                raise RuntimeError(f'Need reviewed self-checking testbench configuration; discovered {len(possible)} unambiguous checkers')
            config = possible[0]
        for key in ('top', 'pass_regex'):
            if not config.get(key): raise ValueError(f'Missing testbench setting: {key}')
        files = [D.local_path(source, f) for f in config.get('files', [])]
        files += [D.local_path(ROOT, f) for f in config.get('repo_files', [])]
        if not files: raise ValueError('No testbench sources configured')
        includes = [D.local_path(source, f) for f in config.get('include_dirs', [])]
        cwd = D.local_path(source, config['cwd']) if 'cwd' in config else files[0].parent
        # Keep upstream relative data-file paths, put simulator library and logs in private workspace.
        assets = [D.local_path(source, f) for f in config.get('assets', [])]
        result['asset_sha256'] = {str(p.relative_to(source)): D.digest(p) for p in assets}
        lib = work / 'work'
        if lib.exists(): shutil.rmtree(lib)
        version = D.command(['vsim', '-version'], timeout=20)
        result.update(testbench=config, simulator=version.strip(), files={str(p.relative_to(D.ROOT)) if p.is_relative_to(D.ROOT) else str(p): D.digest(p) for p in files})
        D.command(['vlib', str(lib)], timeout=30, log=work/'vlib.log')
        compile_args = ['vlog', '-work', str(lib)]
        if any(p.suffix == '.sv' for p in files): compile_args += ['-sv']
        compile_args += ['+incdir+' + str(p) for p in includes]
        compile_args += ['+define+' + str(d) for d in config.get('defines', [])]
        compile_args += [str(candidate)] + [str(p) for p in files]
        D.command(compile_args, cwd=cwd, timeout=timeout, log=work/'compile.log')
        script = 'onerror {quit -code 3}; onbreak {quit -code 4}; run -all; quit -f -code 0'
        output = D.command(['vsim', '-c', '-onfinish', 'stop', '-l', str(work/'transcript'), '-wlf', str(work/'waves.wlf'),
                            str(lib)+'.'+config['top'], '-do', script], cwd=cwd, timeout=timeout, log=work/'simulate.log')
        if not successful(output, config['pass_regex']):
            raise RuntimeError('No clean $finish with expected self-checking PASS; see ModelSim logs')
        if config.get('fail_regex') and re.search(config['fail_regex'], output, re.M):
            raise RuntimeError('Configured failure expression matched transcript')
        if config.get('check_regex'):
            count = len(re.findall(config['check_regex'], output, re.M))
            result['checks'] = count
            if count < config.get('minimum_checks', 1):
                raise RuntimeError(f'Only {count} checks completed')
        result['status'] = 'passed'
    except Exception as exc:
        result['reason'] = str(exc)
    result['logs'] = str(work.relative_to(D.ROOT))
    D.write(work/'result.json', result)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['all', 'fetch', 'validate', 'run', 'status'], default='all', nargs='?')
    ap.add_argument('--model', default='qwen3.8:27b')
    ap.add_argument('--fetch-timeout', type=int, default=90)
    ap.add_argument('--fetch-workers', type=int, default=4)
    ap.add_argument('--prepare-timeout', type=int, default=180)
    ap.add_argument('--simulation-timeout', type=int, default=120)
    ap.add_argument('--phase-timeout', type=int, default=7200)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--core', action='append')
    args = ap.parse_args()
    os.environ.setdefault('GREAT_LLM_THINK', '0')
    ROOT.mkdir(parents=True, exist_ok=True)
    lock = (ROOT/'.dataset.lock').open('a+')
    if args.action != 'status': fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    staging = ROOT/'candidates'
    staging.mkdir(exist_ok=True)
    # Shared pipeline expects provenance under the delivery dataset's sources path.
    if not (ROOT/'sources').is_symlink() and not (ROOT/'sources').exists():
        (ROOT/'sources').symlink_to('candidates/sources', target_is_directory=True)
    ca = copy.copy(args)
    ca.root = staging; ca.overrides = ROOT/'overrides.json'; ca.no_mirrors = False; ca.http_only = True
    if not (staging/'cores.txt').exists(): shutil.copy2(ROOT/'requested_cores.txt', staging/'cores.txt')
    for name in ('source_paths.json', 'source_mirrors.json'):
        if (ROOT/name).exists(): shutil.copy2(ROOT/name, staging/name)
    if args.action in {'all', 'fetch'}:
        # Revisit the complete requested catalog, including previously excluded candidates.
        shutil.copy2(ROOT/'requested_cores.txt', staging/'cores.txt')
        D.fetch(ca)
    if args.action in {'all', 'validate'}:
        D.filter_verilog(ca)
        prepared = D.prepare(ca)['cores']
        D.check_inputs(ca)
        settings = D.read(ROOT/'testbenches.json') if (ROOT/'testbenches.json').exists() else {}
        admission = D.read(ROOT/'admission.json') if (ROOT/'admission.json').exists() else {'cores': {}}
        for core in D.cores(ca):
            row = prepared.get(core, {})
            if row.get('status') != 'ready':
                admission['cores'][core] = {'status': 'prepare_blocked', 'reason': row.get('error')}
            else:
                admission['cores'][core] = simulate(core, staging/'rtl'/f'{core}.v', staging/'sources'/core,
                                                    row, settings.get(core), args.simulation_timeout)
            D.write(ROOT/'admission.json', admission)
            print(f"modelsim {core}: {admission['cores'][core]['status']}", flush=True)
        # Rebuild delivery inputs from proven candidates only. No speculative admissions.
        approved = {}; rtl = ROOT/'rtl'; rtl.mkdir(exist_ok=True)
        for old in rtl.glob('*.v'): old.unlink()
        for core, test in admission['cores'].items():
            row = prepared.get(core, {})
            if test['status'] != 'passed' or row.get('status') != 'ready' or test.get('input_sha256') != row.get('sha256'): continue
            target = rtl/f'{core}.v'; shutil.copy2(staging/'rtl'/f'{core}.v', target)
            approved[core] = dict(row, input=str(target.relative_to(D.ROOT)))
        (ROOT/'cores.txt').write_text(''.join(c+'\n' for c in approved))
        D.write(ROOT/'prepare_index.json', {'cores': approved})
        if (staging/'fetch_index.json').exists(): shutil.copy2(staging/'fetch_index.json', ROOT/'fetch_index.json')
    if args.action in {'all', 'run'}:
        args.root = ROOT; args.overrides = ROOT/'overrides.json'
        if (ROOT/'cores.txt').exists() and (ROOT/'cores.txt').read_text().strip():
            proof = D.read(ROOT/'admission.json')['cores']
            for core in D.cores(args):
                if proof.get(core, {}).get('status') != 'passed' or D.digest(ROOT/'rtl'/f'{core}.v') != proof[core].get('input_sha256'):
                    raise RuntimeError(f'{core}: missing or stale ModelSim admission')
            D.run(args)
        else: print('No ModelSim-validated designs admitted; pipeline not started.', flush=True)
    admission = D.read(ROOT/'admission.json') if (ROOT/'admission.json').exists() else {'cores': {}}
    from collections import Counter
    print('Admission:', dict(Counter(x['status'] for x in admission['cores'].values())))
    if (ROOT/'run_index.json').exists():
        for core, row in D.read(ROOT/'run_index.json')['cores'].items():
            current = [name for name, phase in row.get('phases', {}).items() if phase.get('status') == 'running']
            print(f"pipeline {core}: {row['status']}" + (' (' + ', '.join(current) + ')' if current else ''))
    completed_rows = D.read(ROOT/'run_index.json').get('cores', {}) if (ROOT/'run_index.json').exists() else {}
    for core, row in admission['cores'].items():
        if row['status'] == 'passed' and core not in completed_rows:
            print(f'pipeline {core}: queued')
    for name in ('fetch', 'prepare'):
        index = staging/f'{name}_index.json'
        if index.exists():
            print(name + ':', dict(Counter(x['status'] for x in D.read(index)['cores'].values())))
    if args.action in {'all', 'validate'} and not any(x['status'] == 'passed' for x in admission['cores'].values()):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
