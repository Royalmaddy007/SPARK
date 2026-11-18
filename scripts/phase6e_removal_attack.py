#!/usr/bin/env python3
"""Compare full redaction against manifest-guided decoy/mask removal."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, llm, overhead, removal, util
from scripts import phase6_leakage


def analyse(path, skip_llm=False):
    design = path.stem
    full, mf = overhead.inputs(design)
    out = C.phase_dir('6e')
    stripped = out / f'{design}.stripped.v'
    text, edits = removal.strip(full.read_text(), mf)
    stripped.write_text(text)
    result = {'design': design, 'artifact_sha256': overhead.digest(full), 'edits': edits,
              'full': {'detector': removal.plausibility(full, design)},
              'stripped': {'detector': removal.plausibility(stripped, design)}}
    for name, rtl in [('full', full), ('stripped', stripped)]:
        if skip_llm:
            result[name]['leakage_status'] = 'not_run'
        else:
            measured = phase6_leakage.analyse(path, variant=f'removal_{name}',
                        manifests_override=mf, rtl_override=rtl, output_dir=out)
            result[name].update(leakage=measured,
                               leakage_status='ok' if measured.get('measurement_valid') else 'invalid_llm_response')
    util.write_json(out / f'{design}.removal.json', result)
    return result


def main():
    ap = util.design_args(__doc__)
    ap.add_argument('--skip-llm', action='store_true', help='only generate variants and run the independent detector')
    args = ap.parse_args()
    llm.start_log('phase6e')
    for path in util.resolve_designs(args):
        try:
            analyse(path, args.skip_llm)
        except (OSError, ValueError, RuntimeError) as exc:
            util.write_json(C.phase_dir('6e') / f'{path.stem}.removal.json',
                            {'design': path.stem, 'status': 'error', 'reason': str(exc)})
            util.warn(f'{path.stem}: {exc}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
