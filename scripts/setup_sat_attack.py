#!/usr/bin/env python3
"""Fetch PSAT with immutable provenance; prebuilt Linux binary supplied upstream."""
import argparse, json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, util

REPO = 'https://github.com/DfX-NYUAD/PSAT'

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--commit', help='upstream commit to pin (initial fetch defaults to HEAD)')
    args = ap.parse_args()
    dest = C.ROOT / 'tools/PSAT'
    if not dest.exists():
        subprocess.run(['git', 'clone', REPO, str(dest)], check=True)
    if args.commit:
        subprocess.run(['git', '-C', str(dest), 'checkout', args.commit], check=True)
    commit = subprocess.check_output(['git', '-C', str(dest), 'rev-parse', 'HEAD'], text=True).strip()
    binary = dest / 'bin/sld'
    if not binary.is_file():
        raise RuntimeError('upstream sld binary missing')
    util.write_json(C.ROOT / 'tools/PSAT.PROVENANCE.json',
                    {'repository': REPO, 'commit': commit, 'license': 'GPL-3.0', 'binary': str(binary.relative_to(C.ROOT))})
    subprocess.run(['ldd', str(binary)], check=True)
    print('Conventional SAT mode uses a .stoch file with sampling disabled.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
