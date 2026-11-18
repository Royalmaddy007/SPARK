from __future__ import annotations
import argparse, json, os, sys, tempfile
from pathlib import Path
from . import config as C


def design_args(desc: str) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=desc)
    ap.add_argument("--design", "-d", action="append", default=None,
                    help="design stem (repeatable); default = all in examples/rtl")
    ap.add_argument("--no-cache", action="store_true", help="bypass the LLM disk cache")
    return ap


def resolve_designs(args) -> list[Path]:
    if args.no_cache:
        C.LLM_CACHE = False
    if args.design:
        out = []
        for d in args.design:
            p = Path(d)
            if not p.is_file():
                p = C.EXAMPLES_DIR / f"{p.stem}.v"
            if not p.is_file():
                sys.exit(f"[FATAL] unknown design {d!r}; run make list-designs")
            out.append(p.resolve())
        return out
    return sorted(C.EXAMPLES_DIR.glob("*.v"))


def read_json(p):
    p = Path(p)
    if not p.exists():
        sys.exit(f"[FATAL] missing input {p} -- run the preceding phase first")
    return json.loads(p.read_text())


def write_json(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    # Reports may read while independent evaluation phases finish under make -j.
    # Publish complete JSON atomically instead of exposing a partial document.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=p.parent, encoding='utf-8',
                                         prefix=p.name + '.', suffix='.tmp', delete=False) as fh:
            temporary = Path(fh.name)
            json.dump(obj, fh, indent=2, ensure_ascii=False)
        os.replace(temporary, p)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return p


def banner(text: str):
    print(f"\n\033[1;36m{'=' * 72}\n {text}\n{'=' * 72}\033[0m", flush=True)


def info(text: str):
    print(f"  \033[0;32m*\033[0m {text}", flush=True)


def warn(text: str):
    print(f"  \033[0;33m!\033[0m {text}", flush=True)
