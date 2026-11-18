#!/usr/bin/env python3
"""Import two MIT-CEP benchmarks and only their dependency closure, with provenance."""
import argparse, hashlib, json, re, shutil, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, util
REPO = 'https://github.com/mit-ll/CEP'
BASE = Path('generators/mitll-blocks/src/main/resources/vsrc')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--commit', help='pin upstream revision; existing checkout is otherwise preserved')
    args = ap.parse_args()
    upstream = C.ROOT / 'examples/upstream/mit-cep'
    if not upstream.exists():
        subprocess.run(['git', 'clone', REPO, str(upstream)], check=True)
    if args.commit:
        subprocess.run(['git', '-C', str(upstream), 'checkout', args.commit], check=True)
    commit = subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip()
    citation = C.ROOT / 'examples/CITATIONS.json'
    manifest = json.loads(citation.read_text())
    entries = []
    for group, filename, target in [('des3', 'des3.v', 'des3'), ('sha256', 'sha256.v', 'sha256_core_cep')]:
        folder = upstream / BASE / group
        sources = list(folder.glob('*.v'))
        definitions = {name: path for path in sources for name in re.findall(r'\bmodule\s+(\w+)', path.read_text())}
        needed, todo = set(), [folder / filename]
        while todo:
            path = todo.pop()
            if path in needed:
                continue
            needed.add(path)
            text = re.sub(r'//[^\n]*|/\*.*?\*/', ' ', path.read_text(), flags=re.S)
            uses = re.findall(r'^\s*(\w+)\s+(?:#\s*\([^;]*?\)\s*)?\w+\s*\(', text, re.M)
            todo.extend(definitions[u] for u in uses if u in definitions and definitions[u] != path)
        for path in sorted(needed):
            local = (C.EXAMPLES_DIR / f'{target}.v' if path.name == filename else C.DEPS_DIR / f'cep_{group}_{path.name}')
            # Preserve bytes and upstream module names; target namespace is the filename.
            local.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, local)
            entries.append({'file': str(local.relative_to(C.ROOT)), 'upstream_repository': 'mit-ll/CEP',
                            'upstream_url': REPO, 'upstream_path': str(path.relative_to(upstream)),
                            'commit': commit, 'permalink': f'{REPO}/blob/{commit}/{path.relative_to(upstream)}',
                            'license': 'see preserved per-file copyright and CEP component licenses',
                            'license_file': 'examples/licenses/mit-cep.LICENSE.Components.md',
                            'sha256': hashlib.sha256(local.read_bytes()).hexdigest(),
                            'description': f'MIT-CEP {group}; source module names unchanged'})
    files = {e['file'] for e in entries}
    manifest['designs'] = [e for e in manifest['designs'] if e['file'] not in files] + entries
    util.write_json(citation, manifest)
    for name in ('LICENSE.md', 'LICENSE.Components.md'):
        shutil.copyfile(upstream / name, C.ROOT / 'examples/licenses' / f'mit-cep.{name}')
    md = C.ROOT / 'examples/CITATIONS.md'
    marker = '\n## MIT-CEP benchmark overlap\n'
    body = md.read_text().split(marker)[0]
    body += marker + f'\nUpstream: {REPO}, pinned commit `{commit}`. Source bytes are unchanged.\n\n'
    body += '`des3` imports module `des3`; `sha256_core_cep` imports module `sha256`.\n'
    body += 'Dependencies are recorded individually in CITATIONS.json. No claim of GPS/round overlap is made.\n\n'
    body += '\n'.join(f'- [{e["file"]}]({e["permalink"]})' for e in entries) + '\n'
    md.write_text(body)
    print(f'Imported {len(entries)} source files at {commit}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
