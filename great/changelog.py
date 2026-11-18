"""Uniform per-phase JSON change log.

Every phase writes exactly one <design>.changelog.json recording, for each
individual edit: the step id, what was changed, the before/after text, the
rationale, and whether the edit came from the LLM or from the deterministic
orchestration script.
"""
from __future__ import annotations
import json, platform, time
from pathlib import Path
from . import config as C
from . import llm


class ChangeLog:
    def __init__(self, phase: str, design: str, source_file: str = ""):
        self.data = {
            "schema": "great-dac26/changelog/1.0",
            "phase": phase,
            "design": design,
            "source_file": source_file,
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "model": C.LLM_MODEL,
            "host": platform.node(),
            "inputs": {},
            "summary": {},
            "changes": [],
            "faults_detected": [],
            "artifacts": {},
        }
        self._t0 = time.time()

    # --------------------------------------------------------------- record
    def change(self, step: str, kind: str, *, target: str = "", before=None,
               after=None, rationale: str = "", origin: str = "script",
               line: int | None = None, **extra):
        rec = {"seq": len(self.data["changes"]) + 1, "step": step, "kind": kind,
               "target": target, "origin": origin}
        if line is not None:
            rec["line"] = line
        if before is not None:
            rec["before"] = before
        if after is not None:
            rec["after"] = after
        if rationale:
            rec["rationale"] = rationale
        rec.update(extra)
        self.data["changes"].append(rec)
        return rec

    def fault(self, step: str, name: str, detail: str, mitigation: str,
              resolved: bool = True, **extra):
        """A fault from the paper's taxonomy that the script caught and fixed."""
        rec = {"step": step, "fault": name, "detail": detail,
               "mitigation": mitigation, "resolved": resolved}
        rec.update(extra)
        self.data["faults_detected"].append(rec)
        return rec

    def artifact(self, name: str, path) -> None:
        self.data["artifacts"][name] = str(Path(path).relative_to(C.ROOT))

    def note(self, **kw):
        self.data["inputs"].update(kw)

    def summarise(self, **kw):
        self.data["summary"].update(kw)

    # ---------------------------------------------------------------- write
    def write(self, path) -> Path:
        by_step: dict[str, int] = {}
        for ch in self.data["changes"]:
            by_step[ch["step"]] = by_step.get(ch["step"], 0) + 1
        self.data["summary"].setdefault("total_changes", len(self.data["changes"]))
        self.data["summary"]["changes_by_step"] = by_step
        self.data["summary"]["faults_detected"] = len(self.data["faults_detected"])
        self.data["llm_stats"] = llm.stats()
        self.data["wall_seconds"] = round(time.time() - self._t0, 2)
        self.data["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))
        return path


def load(path):
    return json.loads(Path(path).read_text())
