"""Typed data contracts for the AI DLC collective-memory prototype.

These are the artifacts agents pass to one another and write into shared
memory. They are deliberately strict: the type system encodes the v1.1
evaluation rubric so that "faithful transformation" is structurally
expressible rather than left to prose.

- ``RequirementsArtifact`` — produced by the BA agent from a delivery ticket.
- ``ADR`` — produced by the SA agent from a ``RequirementsArtifact``. Its
  ``requirement_traces`` make traceability and omission measurable, and its
  ``added_constraints`` force architect-added constraints to be labelled and
  justified, never silently attributed to the source.
- ``KnowledgeEntry`` — the append-only write envelope for the shared graph (L4).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    """Short, readable, unique id, e.g. ``req-3f9a2c1d``."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class AgentPersona(StrEnum):
    BUSINESS_ANALYST = "business-analyst"
    SOLUTION_ARCHITECT = "solution-architect"
    SECURITY_ENGINEER = "security-engineer"
    QA_ENGINEER = "qa-engineer"
    OPS = "ops"
    ORCHESTRATOR = "orchestrator"


class Priority(StrEnum):
    MUST = "must"
    SHOULD = "should"
    COULD = "could"
    WONT = "wont"


# --- BA output ------------------------------------------------------------


class Requirement(BaseModel):
    id: str = Field(default_factory=lambda: new_id("r"))
    text: str
    priority: Priority | None = None
    source_ref: str | None = None  # where in the ticket this came from


class AcceptanceCriterion(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ac"))
    text: str
    given: str | None = None
    when: str | None = None
    then: str | None = None


class RequirementsArtifact(BaseModel):
    """What the BA agent extracts from a delivery ticket and writes to memory."""

    id: str = Field(default_factory=lambda: new_id("req"))
    source_ticket_id: str
    title: str
    summary: str
    requirements: list[Requirement] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)    # stated in the ticket
    open_questions: list[str] = Field(default_factory=list)  # BA-flagged ambiguities
    key_facts: list[str] = Field(default_factory=list)       # tagged for memory-hit-rate
    author: AgentPersona = AgentPersona.BUSINESS_ANALYST
    created_at: datetime = Field(default_factory=_utcnow)


# --- SA output ------------------------------------------------------------


class ADRStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"


class DecisionOption(BaseModel):
    name: str
    description: str
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)


class RequirementTrace(BaseModel):
    """Links a source requirement to how the decision addresses it.

    Drives the rubric's traceability (addressed) and omission (not addressed
    and not deferred) checks.
    """

    requirement_id: str
    addressed: bool
    how: str | None = None              # how the decision satisfies it
    deferred_reason: str | None = None  # why, if intentionally not addressed


class AddedConstraint(BaseModel):
    """A constraint the architect adds that was not in the source.

    This is the value-add of the SA, not a hallucination — but it must be
    justified, and it is always labelled architect-added so it is never
    mistaken for a source requirement.
    """

    text: str
    justification: str
    origin: str = Field(default="architect-added", frozen=True)


class ADR(BaseModel):
    """What the SA agent produces from a ``RequirementsArtifact``."""

    id: str = Field(default_factory=lambda: new_id("adr"))
    source_requirements_id: str
    title: str
    status: ADRStatus = ADRStatus.PROPOSED
    context: str
    decision: str
    rationale: str
    considered_options: list[DecisionOption] = Field(default_factory=list)
    consequences: list[str] = Field(default_factory=list)
    requirement_traces: list[RequirementTrace] = Field(default_factory=list)
    added_constraints: list[AddedConstraint] = Field(default_factory=list)
    author: AgentPersona = AgentPersona.SOLUTION_ARCHITECT
    created_at: datetime = Field(default_factory=_utcnow)

    def addressed_requirement_ids(self) -> set[str]:
        return {t.requirement_id for t in self.requirement_traces if t.addressed}

    def omitted_requirement_ids(self, artifact: RequirementsArtifact) -> set[str]:
        """Requirements with no addressed trace and no deferral — silently dropped.

        This is the structural omission check (rubric #4): a requirement that is
        neither addressed nor explicitly deferred has been lost in transit.
        """
        traced = {t.requirement_id: t for t in self.requirement_traces}
        omitted: set[str] = set()
        for r in artifact.requirements:
            t = traced.get(r.id)
            if t is None or (not t.addressed and not t.deferred_reason):
                omitted.add(r.id)
        return omitted


# --- Shared-memory write envelope (L4) ------------------------------------


class KnowledgeEntry(BaseModel):
    """Append-only write envelope for the shared temporal graph (Graphiti)."""

    id: str = Field(default_factory=lambda: new_id("ke"))
    author: AgentPersona
    timestamp: datetime = Field(default_factory=_utcnow)
    content: str
    entities: list[str] = Field(default_factory=list)
    canonical: bool = False           # promoted by orchestrator validation only
    confidence: float | None = None   # reserved for v2 conflict resolution
    supersedes: str | None = None
