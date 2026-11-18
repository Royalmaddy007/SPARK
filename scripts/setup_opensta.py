#!/usr/bin/env python3
"""Check OpenSTA or extract a Debian package locally without root permissions."""
import argparse, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, overhead, util


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--deb', type=Path, help='extract an existing compatible OpenSTA .deb')
    ap.add_argument('--download', action='store_true', help='download with apt-get and extract locally')
    args = ap.parse_args()
    if args.deb:
        subprocess.run(['dpkg-deb', '-x', str(args.deb.resolve()), str(C.ROOT / 'tools/opensta')], check=True)
    elif args.download:
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(['apt-get', 'download', 'opensta'], cwd=td, check=True)
            packages = list(Path(td).glob('opensta*.deb'))
            if len(packages) != 1:
                raise RuntimeError('expected one OpenSTA package')
            subprocess.run(['dpkg-deb', '-x', str(packages[0]), str(C.ROOT / 'tools/opensta')], check=True)
    try:
        r = subprocess.run([overhead.sta_binary(), '-version'], capture_output=True, text=True, check=True)
    except OSError:
        util.warn('OpenSTA unavailable; use --download on Debian/Ubuntu or GREAT_OPENSTA=/path/to/sta')
        return 1
    util.write_json(C.ROOT / 'tools/OpenSTA.PROVENANCE.json',
                    {'source': 'https://github.com/The-OpenROAD-Project/OpenSTA',
                     'version': r.stdout.strip(), 'license': 'GPL-3.0', 'binary': overhead.sta_binary()})
    print(r.stdout.strip())
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
