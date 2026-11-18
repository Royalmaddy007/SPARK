#!/usr/bin/env python3
"""Download and prepare the ASAP7 standard-cell Liberty for technology mapping.

ASAP7 is an open predictive 7nm PDK (BSD-3-Clause) from ASU / The OpenROAD
Project -- NOT a foundry NDA PDK, so it is safe to fetch and redistribute. The
7.5-track cell Liberty files live in the `asap7sc7p5t_28` repo under
`LIB/NLDM/*.lib.7z` (7-zip compressed, Git-LFS-free).

This script fetches only the five RVT / TT (regular-Vt, typical corner) groups
via a non-cone sparse checkout (so ~7 MB, not the multi-GB full PDK), extracts
them, and merges them into a single `pdk/asap7/asap7sc7p5t_RVT_TT.lib` that
Yosys' `dfflibmap`/`abc` consume.  It is idempotent: if the merged Liberty is
already present it exits immediately unless `--force` is given.
"""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, util

REPO = "https://github.com/The-OpenROAD-Project/asap7sc7p5t_28"
GROUPS = {  # group -> date suffix on the RVT/TT file
    "SIMPLE": "211120", "INVBUF": "220122", "AO": "211120",
    "OA": "211120", "SEQ": "220123",
}
PDK = C.ROOT / "pdk" / "asap7"
MERGED = PDK / "asap7sc7p5t_RVT_TT.lib"


def run(cmd, cwd=None, timeout=600):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _merge(lib_dir: Path) -> int:
    libs = sorted(lib_dir.glob("*.lib"))
    if not libs:
        return 0

    def cell_blocks(txt):
        out = []
        for m in re.finditer(r"\bcell\s*\(", txt):
            i = txt.index("{", m.start()); depth = 0; j = i
            while j < len(txt):
                c = txt[j]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            out.append(txt[m.start():j + 1])
        return out

    t0 = libs[0].read_text(errors="ignore")
    header = t0[:re.search(r"\bcell\s*\(", t0).start()]
    cells, templates = [], {}
    for f in libs:
        txt = f.read_text(errors="ignore")
        cells += cell_blocks(txt)
        # Timing and power templates differ between cell groups. Keeping only
        # the first header silently discards SEQ/INVBUF tables and breaks STA.
        for m in re.finditer(r"\b(lu_table_template|power_lut_template)\s*\(\s*([^)]*)\)\s*\{", txt):
            start = txt.index("{", m.start())
            depth, end = 1, start + 1
            while depth:
                depth += (txt[end] == "{") - (txt[end] == "}")
                end += 1
            block = txt[m.start():end]
            key = (m[1], m[2])
            if key in templates and re.sub(r"\s+", "", templates[key]) != re.sub(r"\s+", "", block):
                raise ValueError(f"conflicting Liberty template {key}")
            templates[key] = block
    extra = [block for (kind, name), block in templates.items()
             if not re.search(r"\b" + kind + r"\s*\(\s*" + re.escape(name) + r"\s*\)", header)]
    MERGED.write_text(header + "\n".join(extra + cells) + "\n}\n")
    return len(cells)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    args = ap.parse_args()
    util.banner("ASAP7 PDK setup (open-source, BSD-3-Clause)")

    if MERGED.exists() and not args.force:
        n = sum(1 for _ in re.finditer(r"\bcell\s*\(", MERGED.read_text(errors='ignore')))
        util.info(f"already present: {MERGED.relative_to(C.ROOT)} ({n} cells)")
        return 0
    if not shutil.which("7z"):
        util.warn("7z not found -- install p7zip (e.g. apt-get install p7zip-full)")
        return 1

    PDK.mkdir(parents=True, exist_ok=True)
    (PDK / "lib").mkdir(exist_ok=True)
    work = PDK / ".fetch"
    shutil.rmtree(work, ignore_errors=True)

    util.info("sparse-checkout of RVT/TT Liberty (.lib.7z only)")
    r = run(["git", "clone", "--no-checkout", "--depth", "1", "--filter=blob:none",
             REPO, str(work)], timeout=600)
    if r.returncode != 0:
        util.warn(f"clone failed: {r.stderr[-300:]}")
        return 1
    run(["git", "sparse-checkout", "init", "--no-cone"], cwd=work)
    run(["git", "sparse-checkout", "set",
         "/LIB/NLDM/asap7sc7p5t_*_RVT_TT_nldm_*.lib.7z"], cwd=work)
    r = run(["git", "checkout", "main"], cwd=work, timeout=600)
    if r.returncode != 0:
        util.warn(f"checkout failed: {r.stderr[-300:]}")
        return 1

    nldm = work / "LIB" / "NLDM"
    got = list(nldm.glob("*.lib.7z"))
    util.info(f"downloaded {len(got)} compressed Liberty groups")
    for z in got:
        run(["7z", "e", "-y", f"-o{PDK / 'lib'}", str(z)], timeout=300)
    n = _merge(PDK / "lib")
    util.info(f"merged -> {MERGED.relative_to(C.ROOT)} ({n} cells)")

    util.write_json(PDK / "PROVENANCE.json", {
        "pdk": "ASAP7 7.5-track standard cells (asap7sc7p5t)",
        "source_repo": REPO, "branch": "main", "path": "LIB/NLDM/",
        "corner": "RVT / TT (regular-Vt, typical)",
        "license": "BSD-3-Clause (open predictive PDK; not a foundry NDA PDK)",
        "groups": list(GROUPS), "merged_liberty": MERGED.name, "n_cells": n,
        "retrieved_via": "git sparse-checkout (no-cone, blob:none) of *.lib.7z + 7z extract",
    })
    shutil.rmtree(work, ignore_errors=True)
    util.info("done")
    return 0 if n > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
