"""Architect verdict capture — the gate's PRIMARY signal (D7, resolves OD3).

A senior architect (not on the build team) records accept/revise/reject + notes on each ADR.
Verdicts are stored in-repo (markdown+frontmatter under ``verdicts/``), tied to the scenario
id, the ADR id, and the scenario-set ``fingerprint`` — so each verdict is attributable to an
exact corpus version and the gate is replayable.

**Human-only sink (the invariant, D7/NFR4).** This store holds *human* verdicts only. The LLM
judge (Stage 3 #4) is a SEPARATE stream that is *compared* against these verdicts (Cohen's κ);
it must never write a ``Verdict`` here. That separation is what keeps "machine score never
overrides the human verdict" structurally true rather than a promise.

The gate readout (``summarize_verdicts``) reports the accept rate with a **Wilson 95% lower
bound** (D7 says "≥70% accept, lower 95% CI") plus the reject rate — honest about small samples,
stdlib math only.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class VerdictDecision(StrEnum):
    ACCEPT = "accept"
    REVISE = "revise"
    REJECT = "reject"


class Verdict(BaseModel):
    """One human verdict on one ADR, attributable to a scenario + set version."""

    scenario_id: str
    adr_id: str
    set_fingerprint: str
    verdict: VerdictDecision
    reviewer: str
    reviewed_at: str = Field(default_factory=lambda: date.today().isoformat())
    notes: str = ""

    def to_markdown(self) -> str:
        return (
            "---\n"
            f"scenario_id: {self.scenario_id}\n"
            f"adr_id: {self.adr_id}\n"
            f"set_fingerprint: {self.set_fingerprint}\n"
            f"verdict: {self.verdict.value}\n"
            f"reviewer: {self.reviewer}\n"
            f"reviewed_at: {self.reviewed_at}\n"
            "---\n"
            f"{self.notes}\n"
        )


def parse_verdict(text: str) -> Verdict:
    """Parse one markdown+frontmatter verdict (notes are the body). Dep-free."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("verdict must start with a '---' frontmatter block")
    fm: dict[str, str] = {}
    body_start = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            body_start = i + 1
            break
        if ":" in lines[i]:
            key, _, value = lines[i].partition(":")
            fm[key.strip()] = value.strip()
    if body_start is None:
        raise ValueError("verdict frontmatter block is not closed with '---'")
    return Verdict(
        scenario_id=fm["scenario_id"],
        adr_id=fm["adr_id"],
        set_fingerprint=fm["set_fingerprint"],
        verdict=VerdictDecision(fm["verdict"].strip().lower()),
        reviewer=fm.get("reviewer", "unspecified"),
        reviewed_at=fm.get("reviewed_at", date.today().isoformat()),
        notes="\n".join(lines[body_start:]).strip(),
    )


class VerdictStore(ABC):
    """Human-only sink for verdicts. NOTHING machine-generated is ever recorded here."""

    @abstractmethod
    def record(self, verdict: Verdict) -> None: ...

    @abstractmethod
    def all(self) -> list[Verdict]: ...


class InMemoryVerdictStore(VerdictStore):
    """Offline fake. Recording the same scenario_id replaces (latest verdict wins)."""

    def __init__(self) -> None:
        self._by_scenario: dict[str, Verdict] = {}

    def record(self, verdict: Verdict) -> None:
        self._by_scenario[verdict.scenario_id] = verdict

    def all(self) -> list[Verdict]:
        return list(self._by_scenario.values())


class FileVerdictStore(VerdictStore):
    """Verdicts as ``<dir>/<scenario_id>.md``. Re-recording overwrites that scenario's file."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def record(self, verdict: Verdict) -> None:
        (self.directory / f"{verdict.scenario_id}.md").write_text(
            verdict.to_markdown(), encoding="utf-8"
        )

    def all(self) -> list[Verdict]:
        return load_verdicts(self.directory)


def load_verdicts(directory: str | Path) -> list[Verdict]:
    """Load every ``*.md`` verdict (README.md skipped), sorted by scenario id."""
    path = Path(directory)
    if not path.is_dir():
        raise FileNotFoundError(f"verdict directory not found: {path}")
    out = [
        parse_verdict(md.read_text(encoding="utf-8"))
        for md in sorted(path.glob("*.md"))
        if md.name.lower() != "readme.md"
    ]
    out.sort(key=lambda v: v.scenario_id)
    return out


def wilson_lower_bound(successes: int, n: int, *, z: float = 1.96) -> float:
    """Wilson score interval lower bound for a proportion (95% by default).

    Honest small-sample lower bound: 0/0 → 0.0; for a fixed success rate it rises toward the
    point estimate as n grows. This is what D7's "≥70% accept (lower 95% CI)" measures against.
    """
    if n == 0:
        return 0.0
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return max(0.0, (centre - margin) / denom)


class GateReadout(BaseModel):
    """The honest human-gate result for a set of verdicts (D7)."""

    total: int
    accept: int
    revise: int
    reject: int
    accept_rate: float
    accept_lower95: float
    reject_rate: float
    meets_gate: bool
    set_fingerprint: str | None = None


def summarize_verdicts(
    verdicts: list[Verdict], *, set_fingerprint: str | None = None
) -> GateReadout:
    """Aggregate human verdicts into the gate readout.

    If ``set_fingerprint`` is given, only verdicts on that corpus version are counted —
    results stay attributable to an exact set. Gate (D7): accept lower-95 ≥ 0.70 AND reject < 0.10.
    """
    vs = [v for v in verdicts if set_fingerprint is None or v.set_fingerprint == set_fingerprint]
    total = len(vs)
    accept = sum(1 for v in vs if v.verdict is VerdictDecision.ACCEPT)
    revise = sum(1 for v in vs if v.verdict is VerdictDecision.REVISE)
    reject = sum(1 for v in vs if v.verdict is VerdictDecision.REJECT)
    accept_rate = accept / total if total else 0.0
    reject_rate = reject / total if total else 0.0
    accept_lower95 = wilson_lower_bound(accept, total)
    return GateReadout(
        total=total, accept=accept, revise=revise, reject=reject,
        accept_rate=accept_rate, accept_lower95=accept_lower95, reject_rate=reject_rate,
        meets_gate=(total > 0 and accept_lower95 >= 0.70 and reject_rate < 0.10),
        set_fingerprint=set_fingerprint,
    )
