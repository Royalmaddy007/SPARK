#!/usr/bin/env python3
"""Re-fetch the original Verilog benchmarks from their upstream repositories.

The original benchmarks ship with the repository, so fetching is optional. This
script exists so the provenance in examples/CITATIONS.json can be re-verified
(and the pinned commits re-checked) at any time.
"""
from __future__ import annotations
import json, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, util


def main() -> int:
    man = json.loads((C.ROOT / "examples" / "CITATIONS.json").read_text())
    ok = bad = 0
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for d in man["designs"]:
            repo, commit = d["upstream_url"], d["commit"]
            clone = td / Path(repo).name
            if not clone.exists():
                util.info(f"cloning {repo}")
                r = subprocess.run(["git", "clone", "-q", repo, str(clone)],
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    util.warn(f"clone failed: {r.stderr.strip()[:200]}")
                    bad += 1
                    continue
            result = subprocess.run(["git", "-C", str(clone), "checkout", "-q", commit],
                                    capture_output=True, text=True)
            if result.returncode:
                util.warn(f"{d['file']}: checkout failed: {result.stderr.strip()[:200]}")
                bad += 1
                continue
            up = clone / d["upstream_path"]
            local = C.ROOT / d["file"]
            if not up.exists():
                util.warn(f"{d['file']}: upstream path missing at {commit}")
                bad += 1
                continue
            if local.exists() and up.read_bytes() == local.read_bytes():
                util.info(f"{d['file']}: verified identical to {repo}@{commit[:8]}")
                ok += 1
            else:
                local.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(up, local)
                util.warn(f"{d['file']}: differed from upstream -- refreshed")
                ok += 1
    util.info(f"{ok} verified, {bad} failed")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
