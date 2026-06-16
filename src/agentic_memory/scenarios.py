"""Frozen scenario set — the fixed corpus the Stage-3 gate judges the loop against.

A scenario is a delivery ticket plus provenance. The set lives in-repo as markdown files
with simple `key: value` frontmatter (prose bodies need no JSON escaping; diffs cleanly), is
loaded through the existing ``TicketSource`` seam (so ``run_loop`` is unchanged), and is
``fingerprint()``-ed so every eval result is attributable to an exact set version (NFR1).

**Validity boundary (D9 — read this).** The credibility of the gate comes entirely from the
scenarios being *externally authored and anonymized*. This module is only the machinery to
freeze, load, and attribute such a corpus — it cannot supply the validity, which lives in who
wrote the tickets. The scenarios shipped in ``scenarios/`` are clearly-labelled **illustrative
placeholders** (``source: illustrative``); the real gate corpus is dropped in by an external
author. Nothing here generates gate content.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from .agents import TicketInput
from .tickets import TicketSource

_TRUE = {"true", "yes", "1"}


class Scenario(BaseModel):
    """One frozen delivery ticket + provenance.

    ``id/title/body`` are what the BA consumes; ``source/anonymized/author`` are provenance the
    architect trusts; ``expected_key_requirements/notes`` are OPTIONAL author-supplied hints for
    the advisory omission metric (never derived by us, never required).
    """

    id: str
    title: str
    body: str
    source: str = "unspecified"
    anonymized: bool = False
    author: str = "unspecified"
    expected_key_requirements: list[str] = Field(default_factory=list)
    notes: str | None = None

    def canonical(self) -> dict:
        """Content used for the set fingerprint — stable, ordering-independent."""
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "source": self.source,
            "anonymized": self.anonymized,
            "author": self.author,
            "expected_key_requirements": sorted(self.expected_key_requirements),
            "notes": self.notes,
        }


def parse_scenario(text: str) -> Scenario:
    """Parse one markdown+frontmatter scenario.

    Frontmatter is the first ``---``-delimited block of ``key: value`` lines; everything after
    is the ticket body. Only the FIRST block is treated as frontmatter, so a body may itself
    contain ``---`` rules. Dep-free (no pyyaml).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("scenario must start with a '---' frontmatter block")

    fm: dict[str, str] = {}
    body_start = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            body_start = i + 1
            break
        line = lines[i]
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    if body_start is None:
        raise ValueError("scenario frontmatter block is not closed with '---'")

    body = "\n".join(lines[body_start:]).strip()
    reqs = [r.strip() for r in fm.get("expected_key_requirements", "").split(";") if r.strip()]
    return Scenario(
        id=fm.get("id") or _required("id"),
        title=fm.get("title") or _required("title"),
        body=body,
        source=fm.get("source", "unspecified"),
        anonymized=fm.get("anonymized", "false").strip().lower() in _TRUE,
        author=fm.get("author", "unspecified"),
        expected_key_requirements=reqs,
        notes=fm.get("notes") or None,
    )


def _required(field: str) -> str:
    raise ValueError(f"scenario frontmatter missing required field: {field}")


class ScenarioSet(BaseModel):
    """An ordered, frozen collection of scenarios with a content fingerprint."""

    scenarios: list[Scenario]

    def model_post_init(self, _ctx) -> None:
        seen: set[str] = set()
        for s in self.scenarios:
            if s.id in seen:
                raise ValueError(f"duplicate scenario id: {s.id}")
            seen.add(s.id)

    def ids(self) -> list[str]:
        return [s.id for s in self.scenarios]

    def get(self, scenario_id: str) -> Scenario:
        for s in self.scenarios:
            if s.id == scenario_id:
                return s
        raise KeyError(f"no such scenario: {scenario_id}")

    def __iter__(self):  # type: ignore[override]
        return iter(self.scenarios)

    def __len__(self) -> int:
        return len(self.scenarios)

    def fingerprint(self) -> str:
        """Deterministic sha256 over canonical content, ordering-independent.

        Identifies a set *version*: the same content always hashes the same regardless of file
        order; any content change moves the hash. Eval runs record this to stay attributable.
        """
        payload = sorted((s.canonical() for s in self.scenarios), key=lambda c: c["id"])
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_scenarios(directory: str | Path) -> ScenarioSet:
    """Load every ``*.md`` scenario in ``directory`` (sorted by id; README.md skipped)."""
    path = Path(directory)
    if not path.is_dir():
        raise FileNotFoundError(f"scenario directory not found: {path}")
    scenarios: list[Scenario] = []
    for md in sorted(path.glob("*.md")):
        if md.name.lower() == "readme.md":
            continue
        scenarios.append(parse_scenario(md.read_text(encoding="utf-8")))
    scenarios.sort(key=lambda s: s.id)
    return ScenarioSet(scenarios=scenarios)


class ScenarioTicketSource(TicketSource):
    """Feed a frozen ScenarioSet into the loop through the TicketSource seam.

    The body the BA sees is ``title\\n\\n body`` — symmetric with ``JiraTicketSource`` — so a
    scenario and a real JIRA ticket are indistinguishable to the agents.
    """

    def __init__(self, scenario_set: ScenarioSet) -> None:
        self._set = scenario_set

    def fetch(self, key: str) -> TicketInput:
        try:
            s = self._set.get(key)
        except KeyError:
            raise KeyError(f"ticket not found: {key}") from None
        body = f"{s.title}\n\n{s.body}".strip()
        return TicketInput(id=s.id, body=body)
