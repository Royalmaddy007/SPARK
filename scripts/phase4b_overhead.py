#!/usr/bin/env python3
"""Phase 4b: measure mapped area, critical-path delay and estimated power."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import util, overhead

def main():
    ap = util.design_args(__doc__)
    ap.add_argument('--strict', action='store_true', help='exit nonzero for unavailable/failed measurements')
    args = ap.parse_args()
    results = [overhead.analyse(p.stem) for p in util.resolve_designs(args)]
    for r in results:
        util.info(f"{r['design']}: {r['status']} {r.get('reason', r.get('overhead'))}")
    return int(args.strict and any(r['status'] != 'ok' for r in results))

if __name__ == '__main__':
    raise SystemExit(main())
