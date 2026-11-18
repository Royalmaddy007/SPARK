#!/usr/bin/env python3
"""Fetch, prepare and sequentially redact the isolated OpenCores dataset."""
from __future__ import annotations
import argparse
import fcntl
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tarfile
import zipfile
import urllib.request
import urllib.parse
from html.parser import HTMLParser
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from great import vlog

DEFAULT = ROOT / 'datasets/opencores'
PHASES = [('0_netlist', 'phase0_netlist.py', 'phase0_netlist', 'netlist'),
          ('1_profile', 'phase1_profile.py', 'phase1_profiling', 'profile'),
          ('2_sensitivity', 'phase2_sensitivity.py', 'phase2_sensitivity', 'sensitivity'),
          ('3_strategy', 'phase3_strategy.py', 'phase3_strategy', 'strategy'),
          ('4_transform', 'phase4_transform.py', 'phase4_transform', 'manifests'),
          ('5_verify', 'phase5_verify.py', 'phase5_verification', 'verification'),
          ('6_redteam', 'phase6_leakage.py', 'phase6_leakage', 'leakage')]
HDL = {'.v', '.sv', '.vhd', '.vhdl'}
EXCLUDE = {'test', 'tests', 'tb', 'testbench', 'testbenches', 'bench', 'sim', 'simulation',
           'doc', 'docs', 'documentation', 'demo', 'demos', 'example', 'examples',
           'tags', 'branches', '.git', '.svn'}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def read(p):
    return json.loads(Path(p).read_text())


def write(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=p.parent, delete=False) as f:
        json.dump(obj, f, indent=2); f.write('\n'); tmp = f.name
    os.replace(tmp, p)


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links += [v for k, v in attrs if k == 'href']


def http_export(url, stage, timeout, source_subdirs=None):
    """Pinned SVN browser snapshot when SVN REPORT requests fail server-side.

    Omit generated tool caches, retain RTL, build files, data, docs and licences.
    """
    deadline = time.monotonic() + timeout
    skipped = []
    def get(link):
        last = None
        for attempt in range(3):
            if time.monotonic() > deadline: raise TimeoutError('HTTP source snapshot exceeded fetch timeout')
            try:
                address = link.replace('https://opencores.org/', 'http://opencores.org/', 1) if attempt == 1 else link
                with urllib.request.urlopen(address, timeout=min(20, max(1, deadline-time.monotonic()))) as r:
                    return r.read()
            except Exception as e:
                last = e
                if getattr(e, 'code', None) in {401, 403, 404}: raise
                time.sleep(0.3 * (attempt + 1))
        raise last
    root_text = get(url + '/').decode()
    match = re.search(r'Revision (\d+)', root_text)
    if not match: raise ValueError('Response is not an OpenCores SVN directory listing')
    revision = match.group(1)
    base = url.rstrip('/') + '/'
    todo = ['']; seen = set(); downloads = []
    while todo:
        relative = todo.pop()
        if relative in seen: continue
        seen.add(relative)
        address = base + urllib.parse.quote(relative, safe='/') + '?p=' + revision
        text = get(address).decode()
        if not re.search(r'Revision ' + revision + r'\b', text): raise ValueError('SVN snapshot revision changed')
        parser = Links(); parser.feed(text)
        for href in parser.links:
            parsed = urllib.parse.urlsplit(href)
            part = urllib.parse.unquote(parsed.path)
            if parsed.scheme or part.startswith(('/', '..')) or not part: continue
            rel = relative + part
            p = Path(rel)
            if '..' in p.parts: raise ValueError('Unsafe source listing path')
            if any(x.lower() in {'.git', '.svn', 'work', 'db', 'incremental_db', 'output_files', 'doc', 'docs', 'documentation', 'implement', 'example_design', 'simulation', 'synthesis', '_xmsgs', 'xst'} or x.lower().endswith(('.runs', '.cache', '.sim')) for x in p.parts) or p.suffix.lower() in {'.qtl', '.o', '.exe', '.dll', '.so', '.sof', '.pof'}:
                skipped.append(rel); continue
            if part.endswith('/'):
                if not relative and source_subdirs is not None and part.rstrip('/') not in source_subdirs:
                    skipped.append(rel); continue
                todo.append(rel)
            else:
                retained = HDL | {'.vh', '.svh', '.h', '.hex', '.mif', '.coe', '.mem', '.bin', '.dat', '.f', '.prj', '.qsf', '.qip', '.sdc', '.tcl', '.xdc', '.ucf', '.xco', '.sby', '.vqm', '.edf', '.edn', '.txt', '.md'}
                if p.suffix.lower() not in retained and not re.search(r'licen[cs]e|copying|copyright|readme|makefile', p.name, re.I):
                    skipped.append(rel); continue
                downloads.append(rel)
    def download(rel):
        target = stage / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(get(base + urllib.parse.quote(rel, safe='/') + '?p=' + revision))
    # Two concurrent files per project keep browser snapshots practical while
    # limiting load on the public server (project concurrency is also bounded).
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(download, downloads))
    if not stage.exists(): raise ValueError('SVN snapshot contains no files')
    return revision, skipped


def command(args, *, cwd=None, timeout=300, env=None, log=None, live_log=False):
    if log and live_log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        with Path(log).open('w') as stream:
            result = subprocess.run([str(a) for a in args], cwd=cwd, env=env,
                                    stdout=stream, stderr=subprocess.STDOUT, text=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(f'{Path(str(args[0])).name} exited {result.returncode}: {Path(log).read_text()[-1800:]}')
        return ''
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=env,
                            capture_output=True, text=True, errors='replace', timeout=timeout)
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        Path(log).write_text(result.stdout + '\n' + result.stderr)
    if result.returncode:
        raise RuntimeError(f'{Path(str(args[0])).name} exited {result.returncode}: {result.stderr[-1800:]}')
    return result.stdout


def cores(args):
    listed = [s.strip() for s in (args.root / 'cores.txt').read_text().splitlines()
              if s.strip() and not s.startswith('#')]
    if len(set(listed)) != len(listed) or any(not re.fullmatch('[a-z0-9_-]+', s) for s in listed):
        raise ValueError('Core names must be unique lowercase project slugs')
    if args.core:
        unknown = set(args.core) - set(listed)
        if unknown:
            raise ValueError(f'Unknown requested cores: {sorted(unknown)}')
        listed = [s for s in listed if s in args.core]
    return listed


def project_source(root, core):
    active = root / 'sources' / core
    return active if active.exists() else root / 'excluded/sources' / core


def filter_verilog(args):
    """Keep native Verilog designs active; retain other snapshots for audit."""
    requested = args.root / 'requested_cores.txt'
    if not requested.exists(): shutil.copy2(args.root / 'cores.txt', requested)
    names = [s.strip() for s in requested.read_text().splitlines() if s.strip() and not s.startswith('#')]
    if len(set(names)) != len(names) or any(not re.fullmatch('[a-z0-9_-]+', name) for name in names):
        raise ValueError('Requested core names must be unique project slugs')
    overrides = read(args.overrides) if args.overrides.exists() else {}
    kept, excluded = [], {}
    for core in names:
        source = project_source(args.root, core)
        workspace = args.root / ('excluded/work' if (args.root / 'excluded/work' / core).exists() and not (args.root / 'work' / core).exists() else 'work') / core
        workspace.mkdir(parents=True, exist_ok=True)
        override = overrides.get(core, {})
        try:
            if not (source / '.spark-provenance.json').exists(): raise ValueError('No fetched source snapshot')
            if override.get('archive'):
                view, _ = unpack_source(source, workspace, override, args.prepare_timeout)
                files = source_files(view, override)
            else:
                view = source; files = source_files(view, override)
                if not files and archive_bundles(source):
                    view, _ = unpack_source(source, workspace, override, args.prepare_timeout)
                    files = source_files(view, override)
            extensions = {p.suffix.lower() for p in files}
            if not files: raise ValueError('No RTL implementation found')
            if extensions != {'.v'}:
                raise ValueError('Not a native Verilog-only design: ' + ', '.join(sorted(extensions)))
            if not any(vlog.parse_modules(p.read_text(errors='replace')) for p in files):
                raise ValueError('No Verilog module declarations found')
            kept.append(core)
            target = args.root / 'sources' / core
            if source != target:
                target.parent.mkdir(exist_ok=True); source.rename(target)
        except Exception as e:
            excluded[core] = {'reason': str(e), 'archived_paths': {}}
            for part in ('sources', 'work', 'redacted', 'reports'):
                current = args.root / part / core
                if current.exists():
                    target = args.root / 'excluded' / part / core
                    if target.exists():
                        target = args.root / 'excluded/history' / core / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') / part
                    target.parent.mkdir(parents=True, exist_ok=True); current.rename(target)
                    excluded[core]['archived_paths'][part] = str(target.relative_to(ROOT))
                elif (args.root / 'excluded' / part / core).exists():
                    excluded[core]['archived_paths'][part] = str((args.root / 'excluded' / part / core).relative_to(ROOT))
            current = args.root / 'rtl' / f'{core}.v'
            if current.exists():
                target = args.root / 'excluded/rtl' / current.name
                target.parent.mkdir(parents=True, exist_ok=True); current.replace(target)
    legacy_smoke = args.root / 'smoke_test.json'
    if legacy_smoke.exists() and read(legacy_smoke).get('core') in excluded:
        destination = args.root / 'excluded' / legacy_smoke.name
        destination.parent.mkdir(exist_ok=True); legacy_smoke.replace(destination)
    (args.root / 'cores.txt').write_text('\n'.join(kept) + '\n')
    history = args.root / 'excluded/index_history' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    for name in ('fetch', 'prepare', 'run'):
        path = args.root / f'{name}_index.json'
        if not path.exists(): continue
        data = read(path)
        if set(data.get('cores', {})) - set(kept):
            history.mkdir(parents=True, exist_ok=True); shutil.copy2(path, history / path.name)
            data['cores'] = {c: row for c, row in data['cores'].items() if c in kept}; write(path, data)
    record = {'updated_utc': stamp(), 'policy': 'native .v only; no VHDL conversion or mixed-language designs',
              'requested': len(names), 'active': kept, 'excluded': excluded}
    write(args.root / 'verilog_filter.json', record)
    lines = ['# Excluded dataset projects', '', '| Project | Reason |', '|---|---|']
    lines += [f"| {c} | {row['reason'].replace('|', '/').replace(chr(10), ' ')[:300]} |" for c, row in excluded.items()]
    (args.root / 'EXCLUDED.md').write_text('\n'.join(lines) + '\n')
    print(f'Verilog filter: {len(kept)} active, {len(excluded)} excluded', flush=True)
    return record


def inventory(source):
    rows = []
    for p in sorted(source.rglob('*')):
        if not p.is_file() or any(x in {'.git', '.svn'} for x in p.relative_to(source).parts):
            continue
        if p.suffix.lower() in HDL or p.suffix.lower() in {'.vh', '.svh'} or re.search(r'licen[cs]e|copying|copyright', p.name, re.I):
            rows.append({'path': str(p.relative_to(source)), 'bytes': p.stat().st_size,
                         'sha256': digest(p), 'language': p.suffix.lower().lstrip('.')})
    return rows


def fetch_one(core, args):
    dest = args.root / 'sources' / core
    provenance = dest / '.spark-provenance.json'
    if provenance.exists():
        data = read(provenance)
        provider_file = args.root / 'source_mirrors.json'
        provider = read(provider_file).get(core) if provider_file.exists() else None
        has_hdl = any(x.get('language') in {'v', 'sv', 'vhd', 'vhdl'} for x in data.get('files', []))
        meaningful_files = [p for p in dest.iterdir() if p.name not in {'.spark-provenance.json', '.git'}]
        mirror_url = provider['url'] if provider else f'https://github.com/freecores/{core}.git'
        # Some current SVN trunks are empty or only contain a GitHub pointer.
        # Preserve that snapshot before replacing it with an identified source.
        if not has_hdl and not archive_bundles(dest) and not args.no_mirrors and (provider or not meaningful_files) and data.get('empty_snapshot_mirror_attempt', {}).get('url') != mirror_url:
            try:
                with tempfile.TemporaryDirectory(prefix=f'.{core}-', dir=dest.parent) as td:
                    stage = Path(td) / 'source'
                    command(['git', 'clone', '--depth', '1', '--no-tags', mirror_url, stage],
                            timeout=min(120, args.fetch_timeout), env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))
                    files = inventory(stage)
                    if not any(x['language'] in {'v', 'sv', 'vhd', 'vhdl'} for x in files) and not archive_bundles(stage):
                        raise ValueError('Mirror also contains no HDL sources or source bundle')
                    rev = command(['git', 'rev-parse', 'HEAD'], cwd=stage).strip()
                    old = args.root / 'source_history' / core / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                    replacement = {'project_url': f'https://opencores.org/projects/{core}',
                                   'transport': 'git-author-mirror' if provider else 'git-mirror',
                                   'source_url': mirror_url, 'revision': rev, 'fetched_utc': stamp(),
                                   'files': files, 'previous_snapshot': str(old.relative_to(ROOT)),
                                   'reference': provider.get('reference') if provider else None,
                                   'mirror_note': 'Recorded mirror replacing an empty/pointer-only SVN snapshot; not asserted identical to current SVN'}
                    write(stage / '.spark-provenance.json', replacement)
                    old.parent.mkdir(parents=True, exist_ok=True); dest.rename(old); stage.rename(dest)
                    data = replacement
            except Exception as e:
                data['empty_snapshot_mirror_attempt'] = {'url': mirror_url, 'error': str(e), 'checked_utc': stamp()}
                write(provenance, data)
        return {'core': core, 'status': 'fetched', 'cached': True, **data}
    if dest.exists():
        return {'core': core, 'status': 'fetch_failed', 'error': 'Existing source directory has no provenance; left untouched'}
    attempts = []
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f'.{core}-', dir=dest.parent) as td:
        stage = Path(td) / 'source'
        svn = None if getattr(args, 'http_only', False) else shutil.which('svn')
        if svn:
            for scheme in ('https', 'http'):
                url = f'{scheme}://opencores.org/ocsvn/{core}/{core}/trunk'
                try:
                    info = command([svn, 'info', '--xml', '--non-interactive', url], timeout=min(25, args.fetch_timeout))
                    entry = ET.fromstring(info).find('entry')
                    rev = entry.attrib['revision']
                    command([svn, 'export', '--non-interactive', '--ignore-externals', '-r', rev,
                             url + '@' + rev, stage], timeout=args.fetch_timeout)
                    data = {'project_url': f'https://opencores.org/projects/{core}', 'transport': 'svn',
                            'source_url': url, 'revision': rev, 'fetched_utc': stamp(), 'attempts': attempts}
                    break
                except Exception as e:
                    attempts.append({'url': url, 'error': str(e)})
                    if stage.exists(): shutil.rmtree(stage)
            else:
                data = None
        else:
            data = None
            attempts.append({'note': 'SVN export bypassed for browser-only retrieval'} if getattr(args, 'http_only', False) else {'error': 'svn executable not installed'})
        provider_file = args.root / 'source_mirrors.json'
        provider = read(provider_file).get(core) if provider_file.exists() else None
        if data is None and provider and not args.no_mirrors:
            url = provider['url']
            if not re.fullmatch(r'https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git', url):
                raise ValueError('Recorded source mirrors must be HTTPS GitHub repositories')
            try:
                command(['git', 'clone', '--depth', '1', '--no-tags', url, stage],
                        timeout=args.fetch_timeout, env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))
                rev = command(['git', 'rev-parse', 'HEAD'], cwd=stage).strip()
                data = {'project_url': f'https://opencores.org/projects/{core}', 'transport': 'git-author-mirror',
                        'source_url': url, 'revision': rev, 'fetched_utc': stamp(), 'attempts': attempts,
                        'reference': provider['reference'], 'mirror_note': 'Author repository linked by the OpenCores project; not asserted identical to SVN snapshot'}
            except Exception as e:
                attempts.append({'url': url, 'error': str(e)})
                if stage.exists(): shutil.rmtree(stage)
        if data is None:
            url = f'https://opencores.org/ocsvn/{core}/{core}/trunk'
            try:
                settings_file = args.root / 'source_paths.json'
                subdirs = read(settings_file).get(core) if settings_file.exists() else None
                revision, skipped = http_export(url, stage, args.fetch_timeout, subdirs)
                data = {'project_url': f'https://opencores.org/projects/{core}', 'transport': 'svn-http-snapshot',
                        'source_url': url, 'revision': revision, 'fetched_utc': stamp(), 'attempts': attempts,
                        'omitted_paths': skipped,
                        'source_subdirs': subdirs,
                        'snapshot_scope': 'HDL, headers, memory data, build files and licences; software, documents and generated binaries omitted'}
            except Exception as e:
                attempts.append({'url': url, 'transport': 'http-snapshot', 'error': str(e)})
                if stage.exists(): shutil.rmtree(stage)
        if data is None and not args.no_mirrors:
            url = f'https://github.com/freecores/{core}.git'
            try:
                env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
                command(['git', 'clone', '--depth', '1', '--no-tags', url, stage],
                        timeout=args.fetch_timeout, env=env)
                rev = command(['git', 'rev-parse', 'HEAD'], cwd=stage).strip()
                data = {'project_url': f'https://opencores.org/projects/{core}', 'transport': 'git-mirror',
                        'source_url': url, 'revision': rev, 'fetched_utc': stamp(), 'attempts': attempts,
                        'mirror_note': 'FreeCores mirror snapshot; not asserted identical to current OpenCores SVN'}
            except Exception as e:
                attempts.append({'url': url, 'error': str(e)})
        if data is None:
            return {'core': core, 'status': 'fetch_failed', 'attempts': attempts}
        data['files'] = inventory(stage)
        write(stage / '.spark-provenance.json', data)
        stage.rename(dest)
    return {'core': core, 'status': 'fetched', **data}


def fetch(args):
    index = read(args.root / 'fetch_index.json') if (args.root / 'fetch_index.json').exists() else {'cores': {}}
    with ThreadPoolExecutor(max_workers=args.fetch_workers) as pool:
        pending = {pool.submit(fetch_one, core, args): core for core in cores(args)}
        for future in as_completed(pending):
            core = pending[future]
            try: row = future.result()
            except Exception as e: row = {'core': core, 'status': 'fetch_failed', 'error': str(e)}
            index['cores'][core] = row
            index['updated_utc'] = stamp()
            write(args.root / 'fetch_index.json', index)
            print(f"fetch {core}: {row['status']}", flush=True)
    return index


def local_path(base, value):
    p = (base / value).resolve()
    if not p.is_relative_to(base.resolve()):
        raise ValueError(f'Path escapes core source directory: {value}')
    return p


def source_files(source, override):
    if 'files' in override:
        paths = [local_path(source, p) for p in override['files']]
        if not paths or any(not p.is_file() for p in paths): raise ValueError('Configured source file is missing')
        return paths
    paths = [p for p in sorted(source.rglob('*')) if p.is_file() and p.suffix.lower() in HDL
             and not ({part.lower() for part in p.relative_to(source).parts[:-1]} & EXCLUDE)
             and not re.search(r'(^tb_|_tb$|testbench|_test$)', p.stem, re.I)]
    if override.get('source_dirs'):
        roots = [local_path(source, p) for p in override['source_dirs']]
        paths = [p for p in paths if any(p.is_relative_to(root) for root in roots)]
    # Most SVN mirrors include trunk plus historical revisions. Prefer trunk.
    trunk = [p for p in paths if 'trunk' in p.relative_to(source).parts]
    return trunk or paths


def archive_bundles(source):
    return [p for p in sorted(source.rglob('*')) if p.is_file() and '.git' not in p.parts
            and p.name.lower().endswith(('.zip', '.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tar.xz', '.rar'))]


def unpack_source(source, workspace, override, timeout):
    bundles = [local_path(source, override['archive'])] if override.get('archive') else archive_bundles(source)
    if len(bundles) != 1:
        raise ValueError(f'Found {len(bundles)} archives; configure archive explicitly')
    archive = bundles[0]
    identity = {'archive': str(archive.relative_to(source)), 'sha256': digest(archive)}
    target = workspace / 'unpacked' / identity['sha256'][:16]
    marker = target / '.archive_identity.json'
    if marker.exists() and read(marker) == identity: return target, identity
    if target.exists(): raise ValueError('Incomplete archive workspace exists; use a fresh dataset workspace')
    target.parent.mkdir(exist_ok=True)
    def safe(name):
        normalized = name.replace('\\', '/')
        p = Path(normalized)
        if p.is_absolute() or '..' in p.parts or re.match(r'^[A-Za-z]:', normalized):
            raise ValueError(f'Unsafe archive entry: {name}')
    with tempfile.TemporaryDirectory(dir=target.parent) as td:
        stage = Path(td) / 'source'; stage.mkdir()
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as z:
                entries = z.infolist()
                if len(entries) > 100000 or sum(e.file_size for e in entries) > 2 * 1024**3:
                    raise ValueError('Archive exceeds 100,000 files or 2 GiB expanded size')
                for e in entries: safe(e.filename)
                z.extractall(stage)
        elif tarfile.is_tarfile(archive):
            with tarfile.open(archive) as t:
                entries = t.getmembers()
                if len(entries) > 100000 or sum(e.size for e in entries) > 2 * 1024**3:
                    raise ValueError('Archive exceeds 100,000 files or 2 GiB expanded size')
                for e in entries: safe(e.name)
                t.extractall(stage, filter='data')
        elif archive.suffix.lower() == '.rar':
            seven = shutil.which('7z') or shutil.which('7zz')
            if not seven: raise RuntimeError('RAR source bundle requires p7zip (make setup)')
            listing = command([seven, 'l', '-slt', archive], timeout=timeout).split('----------', 1)[-1]
            names = re.findall(r'^Path = (.*)$', listing, re.M)
            if len(names) > 100000 or sum(int(x) for x in re.findall(r'^Size = (\d+)$', listing, re.M)) > 2 * 1024**3:
                raise ValueError('Archive exceeds 100,000 files or 2 GiB expanded size')
            if 'Symbolic Link =' in listing or 'Hard Link =' in listing:
                raise ValueError('RAR archive links require manual review before extraction')
            for name in names: safe(name)
            command([seven, 'x', '-y', '-o' + str(stage), archive], timeout=timeout)
        else:
            raise ValueError('Unsupported archive format')
        write(stage / '.archive_identity.json', identity)
        stage.rename(target)
    return target, identity


def choose_top(files, override, core=None):
    definitions, used = {}, set()
    for p in files:
        text = p.read_text(errors='replace')
        if p.suffix.lower() in {'.v', '.sv'}:
            text = vlog.code_only(text)
            for name in re.findall(r'\bmodule\s+(?:automatic\s+)?([A-Za-z_]\w*)', text):
                if name in definitions: raise ValueError(f'Duplicate module {name}; configure files explicitly')
                definitions[name] = str(p)
            used.update(re.findall(r'\b([A-Za-z_]\w*)\s*(?:#\s*\([^;]*?\)\s*)?[A-Za-z_]\w*\s*\(', text))
        else:
            text = re.sub(r'--[^\n]*', '', text)
            for name in re.findall(r'\bentity\s+(\w+)\s+is\b', text, re.I):
                if name.lower() in definitions: raise ValueError(f'Duplicate entity {name}; configure files explicitly')
                definitions[name.lower()] = str(p)
            used.update(s.lower() for s in re.findall(r'\bentity\s+(?:\w+\.)?(\w+)\s*(?:\(|\bgeneric\b|\bport\b)', text, re.I))
            used.update(s.lower() for s in re.findall(r':\s*(\w+)\s+(?:generic|port)\s+map', text, re.I))
    top = override.get('top')
    if top:
        if top not in definitions and top.lower() not in definitions:
            raise ValueError(f'Configured top {top} not declared in selected sources')
        return top, definitions
    candidates = sorted(set(definitions) - used)
    if core:
        normalized = lambda x: re.sub(r'[^a-z0-9]', '', x.lower())
        matches = [c for c in candidates if normalized(c) == normalized(core)]
        if len(matches) == 1: return matches[0], definitions
    if len(candidates) != 1:
        raise ValueError(f'Configure top/files: found {len(candidates)} possible tops: {candidates[:40]}')
    return candidates[0], definitions


def top_first(text, top):
    modules = vlog.parse_modules(text)
    selected = [m for m in modules if m.name == top]
    if len(selected) != 1: raise ValueError(f'Expected exactly one module {top} after preprocessing/conversion')
    if modules[0].name == top: return text
    # Retain directives/global declarations between modules and move only blocks.
    m = selected[0]
    first = modules[0].start
    return text[:first] + text[m.start:m.end] + '\n' + text[first:m.start] + text[m.end:]


def prepare_one(core, args, overrides):
    source = args.root / 'sources' / core
    original_source = source
    if not (source / '.spark-provenance.json').exists():
        return {'core': core, 'status': 'not_fetched'}
    override = overrides.get(core, {})
    workspace = args.root / 'work' / core
    workspace.mkdir(parents=True, exist_ok=True)
    pipeline_input = args.root / 'rtl' / f'{core}.v'
    if pipeline_input.exists():
        previous_input = workspace / 'previous_inputs' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.v')
        previous_input.parent.mkdir(exist_ok=True); pipeline_input.rename(previous_input)
    files = []; archive_identity = None
    try:
        archive_identity = None
        if override.get('archive'):
            source, archive_identity = unpack_source(source, workspace, override, args.prepare_timeout)
            files = source_files(source, override)
        else:
            files = source_files(source, override)
            if not files and archive_bundles(source):
                source, archive_identity = unpack_source(source, workspace, override, args.prepare_timeout)
                files = source_files(source, override)
        if not files: raise ValueError('No supported HDL source files found')
        dependencies = []; dependency_includes = []
        for dep in override.get('dependencies', []):
            name = dep['core']
            if name not in cores(argparse.Namespace(root=args.root, core=None)):
                raise ValueError(f'Dependency {name} is not in this dataset manifest')
            dep_root = args.root / 'sources' / name
            dep_files = [local_path(dep_root, p) for p in dep['files']]
            if any(not p.is_file() for p in dep_files): raise ValueError(f'Missing dependency files for {name}')
            dependencies.append({'core': name, 'revision': read(dep_root / '.spark-provenance.json')['revision'],
                                 'files': [{'path': str(p.relative_to(dep_root)), 'sha256': digest(p)} for p in dep_files]})
            dependency_includes += [local_path(dep_root, p) for p in dep.get('include_dirs', [])]
            dependency_includes += [p.parent for p in dep_files]
            files += [p for p in dep_files if p not in files]
        if any(p.suffix.lower() not in {'.v', '.vh', '.h'} for p in files):
            raise ValueError('Native Verilog-only dataset: VHDL, SystemVerilog and mixed-language inputs are excluded')
        output = workspace / 'merged.v'
        includes = [local_path(source, x) for x in override.get('include_dirs', [])]
        includes += dependency_includes
        includes += sorted({p.parent for p in files})
        includes += sorted({p.parent for p in source.rglob('*') if p.suffix.lower() in {'.vh', '.svh'}})
        iv = shutil.which('iverilog')
        if not iv: raise RuntimeError('iverilog is required to preprocess Verilog')
        # Included Verilog compilation units are already expanded by Icarus.
        # Passing them again would create duplicate module declarations.
        included = set()
        for file in files:
            for name in re.findall(r'^\s*`include\s+"([^"]+)"', file.read_text(errors='replace'), re.M):
                found = next((p.resolve() for p in [file.parent / name, *(d / name for d in includes)] if p.is_file()), None)
                if found: included.add(found)
        compilation_units = [p for p in files if p.resolve() not in included] or files
        cmd = [iv, '-E', '-g2005']
        for p in includes: cmd += ['-I', p]
        for define in override.get('defines', []): cmd += ['-D', define]
        pre = workspace / 'preprocessed.v'
        command(cmd + ['-o', pre, *compilation_units], cwd=source, timeout=args.prepare_timeout,
                log=workspace / 'prepare.log')
        text = re.sub(r'^\s*`line[^\n]*\n', '', pre.read_text(errors='replace'), flags=re.M)
        preprocessing = 'Native Verilog compilation units merged by Icarus preprocessing; module hierarchy retained'
        top_selection = 'configured or unique module root'
        try:
            top, _ = choose_top([pre], override, core)
        except ValueError as e:
            if override.get('top') or 'possible tops' not in str(e): raise
            yosys = shutil.which('yosys')
            if not yosys: raise RuntimeError('yosys is required to select the design hierarchy')
            tree = workspace / 'auto_top.json'; ys = workspace / 'auto_top.ys'
            ys.write_text(f'read_verilog {json.dumps(str(pre))}\nhierarchy -check -auto-top\nproc\nwrite_json {json.dumps(str(tree))}\n')
            command([yosys, '-Q', '-s', ys], cwd=source, timeout=args.prepare_timeout, log=workspace / 'auto_top.log')
            tops = [name for name, mod in read(tree)['modules'].items() if str(mod.get('attributes', {}).get('top', 0)).strip('0') == '1']
            if len(tops) != 1: raise ValueError('Could not resolve one top; configure top/files explicitly')
            top = tops[0]; top_selection = 'Yosys hierarchy -auto-top (largest module hierarchy)'
        output.write_text(top_first(text, top))
        iv = shutil.which('iverilog')
        if not iv: raise RuntimeError('iverilog required for preparation elaboration gate')
        command([iv, '-t', 'null', '-g2005', '-s', top, output], cwd=source,
                timeout=args.prepare_timeout, log=workspace / 'elaborate.log')
        # Reject constructs unsupported by the downstream Verilog frontend before LLM use.
        yosys = shutil.which('yosys')
        if not yosys: raise RuntimeError('yosys required for preparation hierarchy gate')
        ys = workspace / 'prepare.ys'
        ys.write_text(f'read_verilog {json.dumps(str(output))}\nhierarchy -check -top {top}\n')
        command([yosys, '-Q', '-s', ys], cwd=source, timeout=args.prepare_timeout,
                log=workspace / 'hierarchy.log')
        pipeline_input.parent.mkdir(exist_ok=True)
        temporary_input = pipeline_input.with_suffix('.tmp')
        shutil.copy2(output, temporary_input); temporary_input.replace(pipeline_input)
        return {'core': core, 'status': 'ready', 'top': top, 'top_selection': top_selection,
                'language': 'verilog', 'single_file': True, 'representation': preprocessing,
                'input': str(pipeline_input.relative_to(ROOT)), 'sha256': digest(pipeline_input),
                'source_revision': read(original_source / '.spark-provenance.json')['revision'],
                'file_root': str(source.relative_to(ROOT)), 'archive': archive_identity,
                'files': [str(p.relative_to(source)) if p.is_relative_to(source) else str(p.relative_to(ROOT)) for p in files],
                'dependencies': dependencies, 'override': override}
    except Exception as e:
        return {'core': core, 'status': 'prepare_blocked', 'error': str(e),
                'file_root': str(source.relative_to(ROOT)), 'archive': archive_identity,
                'files': [str(p.relative_to(source)) if p.is_relative_to(source) else str(p.relative_to(ROOT)) for p in files],
                'log_dir': str(workspace.relative_to(ROOT))}


def prepare(args):
    overrides = read(args.overrides) if args.overrides.exists() else {}
    index = read(args.root / 'prepare_index.json') if (args.root / 'prepare_index.json').exists() else {'cores': {}}
    for core in cores(args):
        row = prepare_one(core, args, overrides)
        index['cores'][core] = row
        write(args.root / 'prepare_index.json', index)
        print(f"prepare {core}: {row['status']} {row.get('error', '')[:180]}", flush=True)
    return index


def check_inputs(args):
    index = read(args.root / 'prepare_index.json').get('cores', {})
    expected = set(); checked = []
    for core in cores(args):
        row = index.get(core, {})
        if row.get('status') != 'ready': continue
        path = args.root / 'rtl' / f'{core}.v'
        if row.get('language') != 'verilog' or not row.get('single_file'):
            raise ValueError(f'{core}: input is not recorded as native merged Verilog')
        if (ROOT / row['input']).resolve() != path.resolve() or not path.is_file() or digest(path) != row['sha256']:
            raise ValueError(f'{core}: missing or changed consolidated input')
        text = path.read_text()
        if re.search(r'^\s*`(?:include|line)\b', text, re.M): raise ValueError(f'{core}: unresolved source-file references')
        names = [m.name for m in vlog.parse_modules(text)]
        if not names or names[0] != row['top'] or len(names) != len(set(names)):
            raise ValueError(f'{core}: invalid combined module hierarchy')
        expected.add(path.name); checked.append({'core': core, 'input': row['input'], 'sha256': row['sha256'], 'modules': len(names)})
    # For a full-dataset check the visible input folder must contain exactly the
    # ready designs, each represented by one .v file and no sidecar RTL files.
    if not args.core and {p.name for p in (args.root / 'rtl').glob('*') if p.is_file()} != expected:
        raise ValueError('The rtl/ folder does not match the ready single-file input manifest')
    write(args.root / 'input_audit.json', {'updated_utc': stamp(), 'policy': 'native Verilog; one .v input per design', 'checked': checked})
    print(f'Input audit: {len(checked)} native Verilog single-file designs verified', flush=True)
    return checked


def environment(args, core):
    work = args.root / 'work' / core
    env = dict(os.environ)
    for name in list(env):
        if name.startswith('GREAT_CROSS_MODEL'): env.pop(name)
    env.update(GREAT_MODEL=args.model, GREAT_EXAMPLES_DIR=str(args.root / 'rtl'),
               GREAT_DEPS_DIR=str(work / 'deps'), GREAT_PIPELINE_DIR=str(work / 'pipeline'),
               GREAT_DATASET_MODE='1')
    if getattr(args, 'model_digest', None):
        env['GREAT_CACHE_DIR'] = str(work / 'pipeline/.llm_cache' / args.model_digest.replace(':', '_'))
    (work / 'deps').mkdir(parents=True, exist_ok=True)
    return env


def run(args):
    check_inputs(args)
    prepared = read(args.root / 'prepare_index.json') if (args.root / 'prepare_index.json').exists() else {'cores': {}}
    ready = [c for c in cores(args) if prepared['cores'].get(c, {}).get('status') == 'ready']
    if not ready:
        raise RuntimeError('No prepared designs; inspect prepare_index.json and configure overrides.json')
    for tool in ('iverilog', 'vvp', 'yosys'):
        if not shutil.which(tool): raise RuntimeError(f'Required tool missing: {tool}')
    if not (ROOT / 'pdk/asap7/asap7sc7p5t_RVT_TT.lib').exists(): raise RuntimeError('Run make asap7 first')
    if not args.model.startswith('qwen3.8:'): raise ValueError('This dataset experiment requires Ollama qwen3.8')
    host = os.environ.get('OLLAMA_HOST', 'http://localhost:11434').rstrip('/')
    with urllib.request.urlopen(host + '/api/tags', timeout=15) as response: models = json.load(response)['models']
    model = next((m for m in models if m['name'] == args.model), None)
    if not model: raise RuntimeError(f'Ollama model {args.model} is not installed')
    args.model_digest = model['digest']
    index = read(args.root / 'run_index.json') if (args.root / 'run_index.json').exists() else {'cores': {}}
    pipeline_hash = hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT / 'great').glob('*.py'))) +
                                   b''.join((ROOT / 'scripts' / x[1]).read_bytes() for x in PHASES) + Path(__file__).read_bytes()).hexdigest()
    for core in cores(args):
        prep = prepared['cores'].get(core, {})
        if prep.get('status') != 'ready':
            index['cores'][core] = {'status': 'blocked', 'reason': prep.get('error', prep.get('status', 'not prepared'))}
            write(args.root / 'run_index.json', index); continue
        if prep.get('language') != 'verilog' or not prep.get('single_file'):
            index['cores'][core] = {'status': 'blocked', 'reason': 'Re-run prepare to create a native Verilog single-file input'}
            write(args.root / 'run_index.json', index); continue
        src = ROOT / prep['input']
        if not src.exists() or digest(src) != prep['sha256']:
            index['cores'][core] = {'status': 'blocked', 'reason': 'Prepared input changed; run prepare again'}
            write(args.root / 'run_index.json', index); continue
        fingerprint = hashlib.sha256(json.dumps({'input': prep['sha256'], 'model': model['digest'],
                                                 'pipeline': pipeline_hash,
                                                 'liberty': digest(ROOT / 'pdk/asap7/asap7sc7p5t_RVT_TT.lib'),
                                                 'settings': {k: v for k, v in os.environ.items() if k.startswith('GREAT_') and not k.startswith('GREAT_CROSS_MODEL')}}, sort_keys=True).encode()).hexdigest()
        previous = index['cores'].get(core, {})
        final = args.root / 'redacted' / core / f'{core}.redacted.v'
        reports = args.root / 'reports' / core
        report_hashes = previous.get('report_sha256', {})
        reports_ok = bool(report_hashes) and all((reports / p).exists() and digest(reports / p) == h for p, h in report_hashes.items())
        if not args.force and reports_ok and previous.get('status') in {'completed', 'completed_sim_only'} and previous.get('fingerprint') == fingerprint and final.exists() and digest(final) == previous.get('redacted_sha256'):
            print(f'run {core}: already completed', flush=True); continue
        # A stale previously published artifact must not represent a failed rerun.
        if final.parent.exists():
            archive = args.root / 'previous' / core / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            archive.mkdir(parents=True, exist_ok=True)
            final.parent.rename(archive / 'redacted')
            if reports.exists(): reports.rename(archive / 'reports')
        row = {'status': 'running', 'fingerprint': fingerprint, 'started_utc': stamp(),
               'model': args.model, 'model_digest': model['digest'], 'phases': {}}
        index['cores'][core] = row
        work = args.root / 'work' / core
        env = environment(args, core)
        try:
            for name, script, folder, suffix in PHASES:
                print(f'run {core}: {name}', flush=True)
                row['phases'][name] = {'status': 'running', 'started_utc': stamp()}
                write(args.root / 'run_index.json', index)
                command([sys.executable, ROOT / 'scripts' / script, '-d', src], env=env,
                        cwd=ROOT, timeout=args.phase_timeout, log=work / 'logs' / f'{name}.log', live_log=True)
                artifact = work / 'pipeline' / folder / f'{core}.{suffix}.json'
                result = read(artifact)
                row['phases'][name] = {'status': 'done', 'artifact': str(artifact.relative_to(ROOT)), 'sha256': digest(artifact)}
                if suffix == 'netlist' and not result.get('mapped'):
                    raise RuntimeError('Phase 0 mapping failed; see phase0 log (source-only fallback is not a dataset success)')
                if suffix == 'verification' and result.get('verdict') not in {'PASS', 'PASS_SIM_ONLY'}:
                    raise RuntimeError(f"Phase 5 rejected redaction: {result.get('verdict')}")
                if suffix == 'leakage' and not result.get('measurement_valid'):
                    raise RuntimeError('Phase 6 returned an invalid measurement')
                write(args.root / 'run_index.json', index)
            verified = read(work / 'pipeline/phase5_verification' / f'{core}.verification.json')
            manifests = read(work / 'pipeline/phase4_transform' / f'{core}.manifests.json')
            redacted = (ROOT / manifests['redacted_rtl']).resolve()
            if not redacted.is_relative_to((work / 'pipeline').resolve()): raise ValueError('Phase 4 artifact escaped isolated workspace')
            final.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(redacted, final)
            reports.mkdir(parents=True, exist_ok=True)
            shutil.copy2(work / 'pipeline/phase5_verification' / f'{core}.verification.json', reports / 'verification.json')
            shutil.copy2(work / 'pipeline/phase6_leakage' / f'{core}.leakage.json', reports / 'leakage.json')
            row.update(status='completed' if verified['verdict'] == 'PASS' else 'completed_sim_only',
                       verification_verdict=verified['verdict'], redacted_rtl=str(final.relative_to(ROOT)),
                       redacted_sha256=digest(final))
            write(reports / 'provenance.json', {'source': read(args.root / 'sources' / core / '.spark-provenance.json'), 'preparation': prep,
                                                    'run': row, 'license_note': 'Original licensing files remain in sources; consult them for redistribution terms'})
            row['report_sha256'] = {p.name: digest(p) for p in reports.glob('*.json')}
        except (Exception, KeyboardInterrupt) as e:
            if final.parent.exists():
                withheld = work / ('withheld_delivery_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
                final.parent.rename(withheld)
            if row['phases'].get(name, {}).get('status') == 'running':
                row['phases'][name].update(status='failed', error=str(e))
            row.update(status='interrupted' if isinstance(e, KeyboardInterrupt) else 'failed', error=str(e))
            row['finished_utc'] = stamp(); write(args.root / 'run_index.json', index)
            if isinstance(e, KeyboardInterrupt): raise
        row['finished_utc'] = stamp()
        write(args.root / 'run_index.json', index)
        print(f"run {core}: {row['status']} {row.get('error', '')[:160]}", flush=True)
    return index


def status(args):
    rows = []
    indexes = {name: read(args.root / f'{name}_index.json').get('cores', {}) if (args.root / f'{name}_index.json').exists() else {}
               for name in ('fetch', 'prepare', 'run')}
    for core in cores(args):
        f, p, r = [indexes[n].get(core, {}) for n in ('fetch', 'prepare', 'run')]
        hdl = [x for x in f.get('files', []) if x.get('language') in {'v', 'sv', 'vhd', 'vhdl'}]
        if p.get('files'):
            hdl = [{'language': Path(x).suffix.lower().lstrip('.')} for x in p.get('files', []) if Path(x).suffix.lower() in HDL]
        reason = r.get('error') or r.get('reason') or p.get('error') or f.get('error', '')
        if not reason and f.get('status') == 'fetch_failed': reason = 'Retrieval failed; see fetch_index.json attempts'
        if not reason and f.get('status') == 'fetched' and not hdl: reason = 'Snapshot contains no HDL source files'
        if not hdl and archive_bundles(args.root / 'sources' / core):
            reason = reason if p.get('error') or r.get('error') else 'HDL may be packaged in source archives; prepare expands the selected bundle'
        rows.append({'core': core, 'fetch': f.get('status', 'pending'), 'prepare': p.get('status', 'pending'),
                     'run': r.get('status', 'pending'), 'hdl_files': len(hdl),
                     'languages': sorted({x['language'] for x in hdl}), 'source_url': f.get('source_url'),
                     'revision': f.get('revision'), 'reason': reason})
    write(args.root / 'status.json', {'updated_utc': stamp(), 'cores': rows})
    lines = ['# OpenCores dataset status', '', f'Requested projects: {len(rows)}', '',
             '| Core | Fetch | HDL files | Prepare | Pipeline | Details |', '|---|---|---:|---|---|---|']
    for row in rows:
        lines.append('| ' + ' | '.join(str(row[k]).replace('|', '\\|').replace('\n', ' ')[:300]
                                       for k in ('core', 'fetch', 'hdl_files', 'prepare', 'run', 'reason')) + ' |')
    (args.root / 'STATUS.md').write_text('\n'.join(lines) + '\n')
    for key in ('fetch', 'prepare', 'run'):
        from collections import Counter
        print(key + ': ' + str(dict(Counter(r[key] for r in rows))))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['fetch', 'filter', 'prepare', 'check-inputs', 'run', 'all', 'status'])
    ap.add_argument('--root', type=Path, default=DEFAULT)
    ap.add_argument('--core', action='append')
    ap.add_argument('--overrides', type=Path)
    ap.add_argument('--model', default='qwen3.8:27b')
    ap.add_argument('--no-mirrors', action='store_true')
    ap.add_argument('--http-only', action='store_true', help='Skip SVN export; acquire a pinned browser source snapshot')
    ap.add_argument('--fetch-workers', type=int, default=4)
    ap.add_argument('--fetch-timeout', type=int, default=180)
    ap.add_argument('--prepare-timeout', type=int, default=180)
    ap.add_argument('--phase-timeout', type=int, default=7200)
    ap.add_argument('--force', action='store_true', help='Rerun completed pipelines; preserve old delivered outputs under previous/')
    args = ap.parse_args()
    args.root = args.root.resolve()
    if not args.root.is_relative_to(ROOT) or args.root == ROOT:
        ap.error('--root must be a subdirectory of this repository (pipeline artifact paths are repository-relative)')
    args.overrides = args.overrides or args.root / 'overrides.json'
    args.root.mkdir(parents=True, exist_ok=True)
    if not (args.root / 'cores.txt').exists():
        shutil.copy2(DEFAULT / 'cores.txt', args.root / 'cores.txt')
    if args.fetch_workers < 1: ap.error('--fetch-workers must be positive')
    lock = None
    if args.action != 'status':
        lock = (args.root / '.dataset.lock').open('a+')
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: ap.error('Another dataset command is writing this dataset; wait for it to finish')
    try:
        if args.action in {'fetch', 'all'}: fetch(args)
        if args.action in {'filter', 'prepare', 'all'}: filter_verilog(args)
        if args.action in {'prepare', 'all'}: prepare(args)
        if args.action in {'check-inputs', 'prepare', 'all'}: check_inputs(args)
        if args.action in {'run', 'all'}: run(args)
    except Exception as e:
        print(f'[dataset] {e}', file=sys.stderr)
        status(args)
        return 1
    rows = status(args)
    if args.action in {'status', 'filter', 'check-inputs'}: return 0
    key, good = {'fetch': ('fetch', {'fetched'}), 'prepare': ('prepare', {'ready'}),
                 'run': ('run', {'completed', 'completed_sim_only'}), 'all': ('run', {'completed', 'completed_sim_only'})}[args.action]
    return 0 if all(r[key] in good for r in rows) else 1


if __name__ == '__main__':
    sys.exit(main())
