#!/usr/bin/env python3
"""Run mapping and SPARK phases 1–6 on local RTL, with all results in its folder."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import re
import shutil
import sys
import dataset as D

DEFAULT = D.ROOT / 'verilog_ip_partial'


def discover(root):
    """Only top-level inputs; generated sources and delivered RTL are never inputs."""
    files = sorted(root.glob('*.v'))
    if not files:
        raise ValueError(f'No top-level .v inputs in {root}')
    for path in files:
        if not re.fullmatch(r'[a-z0-9_-]+', path.stem):
            raise ValueError(f'Input filename must use a lowercase design slug: {path.name}')
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f'Input symlink leaves the dataset directory: {path}')
    return files


def snapshot(core, path, root):
    headers = sorted([*root.glob('*.vh'), *root.glob('*.h')])
    for header in headers:
        if not header.resolve().is_relative_to(root.resolve()):
            raise ValueError(f'Header symlink leaves the dataset directory: {header}')
    hashes = {p.name: D.digest(p) for p in [path, *headers]}
    destination = root/'sources'/core
    provenance = destination/'.spark-provenance.json'
    if provenance.exists():
        previous = D.read(provenance)
        if previous.get('input_sha256') == hashes:
            # Verify the private snapshot too, rather than trusting its marker.
            if all((destination/name).is_file() and D.digest(destination/name) == sha for name, sha in hashes.items()):
                return {'core': core, 'status': 'fetched', 'cached': True, **previous}
        archive = root/'source_history'/core/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        archive.parent.mkdir(parents=True, exist_ok=True)
        destination.rename(archive)
    elif destination.exists():
        raise ValueError(f'Existing snapshot without provenance left untouched: {destination}')
    destination.mkdir(parents=True)
    for source in [path, *headers]: shutil.copy2(source, destination/source.name)
    record = {'transport': 'local', 'source_file': str(path.relative_to(D.ROOT)),
              'revision': 'sha256:' + hashes[path.name], 'input_sha256': hashes,
              'fetched_utc': D.stamp(), 'files': D.inventory(destination),
              'origin_note': 'User-provided local RTL; no upstream source or licence inferred.'}
    D.write(provenance, record)
    return {'core': core, 'status': 'fetched', **record}


def prepare_local(args):
    files = discover(args.root)
    names = [p.stem for p in files]
    if args.core and set(args.core)-set(names):
        raise ValueError(f'Unknown input designs: {sorted(set(args.core)-set(names))}')
    old = (args.root/'cores.txt').read_text().splitlines() if (args.root/'cores.txt').exists() else []
    # Retain retired generated inputs and deliveries, without touching original .v files.
    for core in set(old)-set(names):
        if not re.fullmatch(r'[a-z0-9_-]+', core): raise ValueError('Invalid existing manifest entry')
        archive = args.root/'previous'/core/('removed-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        for folder, source in [('sources', args.root/'sources'/core), ('rtl', args.root/'rtl'/f'{core}.v'),
                               ('redacted', args.root/'redacted'/core), ('reports', args.root/'reports'/core)]:
            if source.exists():
                archive.mkdir(parents=True, exist_ok=True)
                source.rename(archive/source.name if folder=='rtl' else archive/folder)
    (args.root/'cores.txt').write_text(''.join(n+'\n' for n in names))
    index = D.read(args.root/'fetch_index.json') if (args.root/'fetch_index.json').exists() else {'cores': {}}
    for path in files:
        if args.core and path.stem not in args.core: continue
        index['cores'][path.stem] = snapshot(path.stem, path, args.root)
        D.write(args.root/'fetch_index.json', index)
    prepared = D.prepare(args)
    D.check_inputs(args)
    return prepared


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', nargs='?', default='all', choices=['all','prepare','run','status'])
    ap.add_argument('--root', type=Path, default=DEFAULT)
    ap.add_argument('--core', action='append', help='Process only this filename stem; repeat to select several')
    ap.add_argument('--model', default='qwen3.8:27b')
    ap.add_argument('--prepare-timeout', type=int, default=180)
    ap.add_argument('--phase-timeout', type=int, default=7200)
    ap.add_argument('--force', action='store_true', help='Rerun completed pipelines, retaining previous deliveries')
    args = ap.parse_args(argv)
    args.root = args.root.resolve()
    if args.root == D.ROOT or not args.root.is_relative_to(D.ROOT) or not args.root.is_dir():
        ap.error('--root must be an existing dataset directory inside this repository')
    if not args.model.startswith('qwen3.8:'): ap.error('Use an installed Ollama qwen3.8 model tag')
    if min(args.prepare_timeout,args.phase_timeout) <= 0: ap.error('Timeouts must be positive')
    args.overrides = args.root/'dataset3_overrides.json'
    # Match the working dataset2 inference setting. Explicit user overrides persist.
    os.environ.setdefault('GREAT_LLM_THINK', '0')
    if args.action == 'status':
        if not (args.root/'cores.txt').exists():
            print(f'{len(discover(args.root))} local RTL inputs; preparation not started')
            return 0
        rows = D.status(args)
        for row in rows: print(f"{row['core']}: prepare={row['prepare']}, pipeline={row['run']}")
        return 0
    lock = (args.root/'.dataset3.lock').open('a+')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: ap.error('Another dataset3 command is running for this directory')
    try:
        if args.action in {'all','prepare'}: prepare_local(args)
        if args.action in {'all','run'}:
            if not (args.root/'prepare_index.json').exists():
                raise ValueError('Run make prepare-dataset3 first, or use the all action')
            D.run(args)
    except Exception as exc:
        print(f'[dataset3] {exc}', file=sys.stderr)
        if (args.root/'cores.txt').exists(): D.status(args)
        return 1
    rows = D.status(args)
    key, good = ('prepare', {'ready'}) if args.action=='prepare' else ('run', {'completed','completed_sim_only'})
    return 0 if rows and all(row[key] in good for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
