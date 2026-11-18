#!/usr/bin/env python3
"""Direct source acquisition and resumable, one-core-at-a-time dataset2 execution."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import fcntl
import os
from pathlib import Path
import shutil
import tempfile
import dataset as D
import dataset2 as M


def download(core, args):
    source = args.root/'sources'/core
    archived = args.root/'excluded/sources'/core
    if not source.exists() and (archived/'.spark-provenance.json').exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(archived), str(source))
    if (source/'.spark-provenance.json').exists():
        metadata = D.read(source/'.spark-provenance.json')
        if metadata.get('identity_validated') is False:
            return {'core': core, **metadata, 'status': 'fetch_failed', 'error': metadata['identity_issue']}
        return {'core': core, 'status': 'fetched', 'cached': True, **D.read(source/'.spark-provenance.json')}
    attempts = []
    source.parent.mkdir(parents=True, exist_ok=True)
    providers = D.read(M.ROOT/'source_mirrors.json') if (M.ROOT/'source_mirrors.json').exists() else {}
    provider = providers.get(core)
    url = provider['url'] if provider else f'https://github.com/freecores/{core}.git'
    try:
        with tempfile.TemporaryDirectory(prefix=f'.direct-{core}-', dir=source.parent) as tmp:
            stage = Path(tmp)/'source'
            clone = ['git', 'clone', '--depth', '1', '--no-tags']
            if provider and provider.get('branch'): clone += ['--branch', provider['branch']]
            D.command(clone + [url, stage],
                      timeout=args.fetch_timeout, env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))
            revision = D.command(['git', 'rev-parse', 'HEAD'], cwd=stage).strip()
            record = {'project_url': f'https://opencores.org/projects/{core}', 'source_url': url,
                      'transport': ('git-author-mirror' if url.startswith('https://github.com/ZipCPU/') else 'git-recorded-mirror') if provider else 'git-mirror', 'revision': revision, 'fetched_utc': D.stamp(),
                      'mirror_note': 'User-authorized recorded mirror snapshot; not asserted identical to current SVN',
                      'branch': provider.get('branch') if provider else None,
                      'files': D.inventory(stage), 'reference': provider.get('reference') if provider else None}
            D.write(stage/'.spark-provenance.json', record)
            stage.rename(source)
            return {'core': core, 'status': 'fetched', **record}
    except Exception as exc:
        attempts.append({'url': url, 'error': str(exc)})
    # Preserve failed direct attempt, then try the pinned OpenCores snapshot transport.
    fallback = copy.copy(args); fallback.no_mirrors = True; fallback.http_only = True
    row = D.fetch_one(core, fallback)
    row['direct_attempts'] = attempts
    return row


def save_status(root, names, fetch, admission):
    names = (root/'requested_cores.txt').read_text().splitlines()
    lines = ['# Dataset 2 execution status', '', f'Updated: {D.stamp()}', '',
             '| Core | Download | Admission | Details |', '|---|---|---|---|']
    for core in names:
        f = fetch.get(core, {}); a = admission.get(core, {})
        reason = str(a.get('reason', f.get('error', ''))).replace('|', '/').replace('\n', ' ')[:400]
        lines.append(f"| {core} | {f.get('status', 'pending')} | {a.get('status', 'pending')} | {reason} |")
    (root/'STATUS.md').write_text('\n'.join(lines)+'\n')


def process(core, args, overrides, settings, admission, prepared, approved):
    source = args.root/'sources'/core
    result = {'updated_utc': D.stamp()}
    try:
        if not (source/'.spark-provenance.json').exists(): raise RuntimeError('Source download unavailable')
        provenance = D.read(source/'.spark-provenance.json')
        if provenance.get('identity_validated') is False:
            raise RuntimeError(provenance['identity_issue'])
        (args.root/'work'/core).mkdir(parents=True, exist_ok=True)
        files = D.source_files(source, overrides.get(core, {}))
        if not files and D.archive_bundles(source):
            unpacked, _ = D.unpack_source(source, args.root/'work'/core, overrides.get(core, {}), args.prepare_timeout)
            files = D.source_files(unpacked, overrides.get(core, {}))
        if not files or {p.suffix.lower() for p in files} != {'.v'}:
            result.update(status='excluded', reason='No pure native Verilog implementation in selected synthesis sources')
        else:
            row = D.prepare_one(core, args, overrides)
            prepared[core] = row
            D.write(args.root/'prepare_index.json', {'cores': prepared})
            if row['status'] != 'ready':
                result.update(status='prepare_blocked', reason=row.get('error'))
            else:
                test_source = D.ROOT/row['file_root']
                result = M.simulate(core, args.root/'rtl'/f'{core}.v', test_source, row, settings.get(core), args.simulation_timeout)
                if result['status'] == 'passed':
                    target = M.ROOT/'rtl'/f'{core}.v'; target.parent.mkdir(exist_ok=True)
                    shutil.copy2(args.root/'rtl'/f'{core}.v', target)
                    approved[core] = dict(row, input=str(target.relative_to(D.ROOT)))
    except Exception as exc:
        result.update(status='blocked', reason=str(exc))
    admission[core] = result
    # A newly failed validation revokes previous admission without touching raw sources.
    if result['status'] != 'passed':
        approved.pop(core, None)
        target = M.ROOT/'rtl'/f'{core}.v'
        if target.exists():
            retired = M.ROOT/'previous'/core/'revoked-input.v'; retired.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(retired))
    D.write(M.ROOT/'admission.json', {'cores': admission})
    D.write(M.ROOT/'prepare_index.json', {'cores': approved})
    (M.ROOT/'cores.txt').write_text(''.join(c+'\n' for c in approved))
    print(f"validate {core}: {result['status']} {result.get('reason', '')[:250]}", flush=True)
    if result['status'] == 'passed' and not args.validate_only:
        runargs = copy.copy(args); runargs.root = M.ROOT; runargs.core = [core]
        print(f'pipeline {core}: starting phases 0–6', flush=True)
        try:
            D.run(runargs)
        except Exception as exc:
            D.write(M.ROOT/'work'/core/'runner_error.json', {'error': str(exc), 'updated_utc': D.stamp()})
            print(f'pipeline {core}: blocked {exc}', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--download-only', action='store_true')
    ap.add_argument('--validate-only', action='store_true')
    ap.add_argument('--skip-download', action='store_true')
    ap.add_argument('--core', action='append')
    ap.add_argument('--model', default='qwen3.8:27b')
    ap.add_argument('--fetch-timeout', type=int, default=90)
    ap.add_argument('--fetch-workers', type=int, default=8)
    ap.add_argument('--prepare-timeout', type=int, default=180)
    ap.add_argument('--simulation-timeout', type=int, default=120)
    ap.add_argument('--phase-timeout', type=int, default=7200)
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()
    os.environ.setdefault('GREAT_LLM_THINK', '0')
    args.root = M.ROOT/'candidates'; args.root.mkdir(parents=True, exist_ok=True)
    args.overrides = M.ROOT/'overrides.json'; args.no_mirrors = False; args.http_only = True
    lock = (M.ROOT/('.downloads.lock' if args.download_only else '.dataset.lock')).open('a+')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: ap.error('Dataset2 is already running; inspect STATUS.md/build.log')
    names = (M.ROOT/'requested_cores.txt').read_text().splitlines()
    if args.core:
        if set(args.core)-set(names): ap.error('Unknown core name')
        names = [c for c in names if c in args.core]
    shutil.copy2(M.ROOT/'requested_cores.txt', args.root/'cores.txt')
    for config in ('source_paths.json', 'source_mirrors.json'):
        if (M.ROOT/config).exists(): shutil.copy2(M.ROOT/config, args.root/config)
    fetch = D.read(args.root/'fetch_index.json').get('cores', {}) if (args.root/'fetch_index.json').exists() else {}
    admission = D.read(M.ROOT/'admission.json').get('cores', {}) if (M.ROOT/'admission.json').exists() else {}
    if not args.skip_download:
        with ThreadPoolExecutor(max_workers=args.fetch_workers) as pool:
            jobs = {pool.submit(download, core, args): core for core in names}
            for future in as_completed(jobs):
                core = jobs[future]
                try: row = future.result()
                except Exception as exc: row = {'core': core, 'status': 'fetch_failed', 'error': str(exc)}
                fetch[core] = row
                D.write(args.root/'fetch_index.json', {'cores': fetch, 'updated_utc': D.stamp()})
                save_status(M.ROOT, names, fetch, admission)
                print(f"download {core}: {row['status']}", flush=True)
    if args.download_only: return 0 if all(fetch.get(c, {}).get('status') == 'fetched' for c in names) else 1
    prepared = D.read(args.root/'prepare_index.json').get('cores', {}) if (args.root/'prepare_index.json').exists() else {}
    approved = D.read(M.ROOT/'prepare_index.json').get('cores', {}) if (M.ROOT/'prepare_index.json').exists() else {}
    overrides = D.read(args.overrides) if args.overrides.exists() else {}
    settings = D.read(M.ROOT/'testbenches.json') if (M.ROOT/'testbenches.json').exists() else {}
    if not (M.ROOT/'sources').is_symlink() and not (M.ROOT/'sources').exists():
        (M.ROOT/'sources').symlink_to('candidates/sources', target_is_directory=True)
    for core in names:
        process(core, args, overrides, settings, admission, prepared, approved)
        save_status(M.ROOT, names, fetch, admission)
    D.write(M.ROOT/'execution_summary.json', {'updated_utc': D.stamp(), 'requested': len(names),
            'admitted': len(approved), 'statuses': {c: admission.get(c, {}).get('status') for c in names}})
    eligible = [c for c in names if admission.get(c, {}).get('status') == 'passed']
    if not eligible: return 1
    if not args.validate_only:
        runs = D.read(M.ROOT/'run_index.json').get('cores', {}) if (M.ROOT/'run_index.json').exists() else {}
        if any(runs.get(c, {}).get('status') not in {'completed', 'completed_sim_only'} for c in eligible): return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
