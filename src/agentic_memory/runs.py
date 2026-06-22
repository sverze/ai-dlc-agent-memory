"""Persisted loop outputs — so generation and evaluation are decoupled.

`run_scenarios.py` generates an ADR per scenario (the expensive BA→SA model calls) and saves a
`RunRecord` here, keyed by the scenario-set fingerprint. `run_eval.py` then *reads* these instead
of re-running the loop — so re-evaluating costs no generation calls, and a free-tier quota wall
can't cost you work already done (re-running resumes from what's saved).

Layout: ``runs/<fingerprint>/<scenario_id>.json``. Regenerable cache — gitignored.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from .artifacts import ADR, RequirementsArtifact


class RunRecord(BaseModel):
    scenario_id: str
    set_fingerprint: str
    final_state: str = ""
    artifact: RequirementsArtifact | None = None
    adr: ADR | None = None


def _set_dir(fingerprint: str, directory: str | Path) -> Path:
    return Path(directory) / fingerprint


def save_run(record: RunRecord, *, directory: str | Path = "runs") -> Path:
    d = _set_dir(record.set_fingerprint, directory)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{record.scenario_id}.json"
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return path


def run_exists(scenario_id: str, fingerprint: str, *, directory: str | Path = "runs") -> bool:
    return (_set_dir(fingerprint, directory) / f"{scenario_id}.json").exists()


def load_runs(fingerprint: str, *, directory: str | Path = "runs") -> dict[str, RunRecord]:
    """All saved run records for a set version, keyed by scenario id (judge cache skipped)."""
    d = _set_dir(fingerprint, directory)
    if not d.is_dir():
        return {}
    out: dict[str, RunRecord] = {}
    for f in sorted(d.glob("*.json")):
        rec = RunRecord.model_validate_json(f.read_text(encoding="utf-8"))
        out[rec.scenario_id] = rec
    return out
