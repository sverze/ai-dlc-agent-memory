"""Shared temporal memory (L4) — the MemoryStore seam over Graphiti.

Per decision D10, facts originating in a typed artifact are written *structurally* and
deterministically from the Pydantic objects — no LLM extraction in the loop. This module
defines the node/edge vocabulary, the abstract :class:`MemoryStore` the agents call, and an
offline :class:`InMemoryMemoryStore` fake (mirroring ``FakeModelClient``) so the BA→SA loop
runs and is testable end-to-end before any Graphiti/Neo4j/Kuzu service exists.

The real ``GraphitiMemoryStore`` lands when we add ``graphiti-core`` and stand up a backend;
it implements the same abstract primitives, so agent code never changes.

Two headline metrics fall out of the edge model as plain graph queries:

- **Omission (<5%)** — a ``Requirement`` with no ``ADDRESSES`` and no ``DEFERS`` edge from the
  ADR was silently dropped (see :meth:`MemoryStore.omitted_requirement_ids`).
- **Memory hit rate (≥90%)** — every ``KeyFact`` for a ticket is retrievable
  (see :meth:`MemoryStore.key_facts` / :meth:`MemoryStore.retrieve`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .artifacts import ADR, AgentPersona, RequirementsArtifact, new_id

DEFAULT_GROUP = "default"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NodeType(StrEnum):
    TICKET = "ticket"
    REQUIREMENT = "requirement"
    ACCEPTANCE_CRITERION = "acceptance_criterion"
    KEY_FACT = "key_fact"
    CLARIFICATION = "clarification"
    ADR = "adr"
    ADDED_CONSTRAINT = "added_constraint"


class EdgeType(StrEnum):
    DERIVED_FROM = "derived_from"        # Requirement -> Ticket
    VALIDATES = "validates"              # AcceptanceCriterion -> Ticket
    STATED_IN = "stated_in"              # KeyFact -> Ticket
    ASKED_ABOUT = "asked_about"          # Clarification -> Requirement
    ANSWERED_BY = "answered_by"          # Clarification -> Requirement
    ADDRESSES = "addresses"              # ADR -> Requirement   (traceability)
    DEFERS = "defers"                    # ADR -> Requirement   (legitimate non-omission)
    ADDS = "adds"                        # ADR -> AddedConstraint
    SUPERSEDES = "supersedes"            # ADR -> ADR


class GraphNode(BaseModel):
    """A node in the shared graph. ``canonical`` is promoted by orchestrator
    validation only, never by the writing agent (D3)."""

    id: str
    type: NodeType
    author: AgentPersona
    group_id: str = DEFAULT_GROUP
    attrs: dict[str, Any] = Field(default_factory=dict)
    canonical: bool = False
    created_at: datetime = Field(default_factory=_utcnow)


class GraphEdge(BaseModel):
    id: str = Field(default_factory=lambda: new_id("e"))
    type: EdgeType
    src: str  # source node id
    dst: str  # destination node id
    author: AgentPersona
    group_id: str = DEFAULT_GROUP
    attrs: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)


class MemoryStore(ABC):
    """The seam every agent reads/writes through.

    Subclasses implement four primitives (``add_node``, ``add_edge``, ``nodes``,
    ``edges``); the domain-level write/query helpers below are concrete and shared,
    so the fake and the real Graphiti store behave identically.
    """

    # -- primitives (backend-specific) ------------------------------------

    @abstractmethod
    def add_node(self, node: GraphNode) -> GraphNode: ...

    @abstractmethod
    def add_edge(self, edge: GraphEdge) -> GraphEdge: ...

    @abstractmethod
    def get_node(self, node_id: str, *, group_id: str = DEFAULT_GROUP) -> GraphNode | None: ...

    @abstractmethod
    def nodes(
        self, *, type: NodeType | None = None, group_id: str | None = None
    ) -> list[GraphNode]: ...

    @abstractmethod
    def edges(
        self,
        *,
        type: EdgeType | None = None,
        src: str | None = None,
        dst: str | None = None,
        group_id: str | None = None,
    ) -> list[GraphEdge]: ...

    @abstractmethod
    def promote_canonical(self, node_id: str, *, group_id: str = DEFAULT_GROUP) -> None:
        """Mark a node canonical — orchestrator validation only (D3)."""
        ...

    # -- domain writes (shared) -------------------------------------------

    def write_requirements(
        self, artifact: RequirementsArtifact, *, group_id: str = DEFAULT_GROUP
    ) -> None:
        """BA output → Ticket + Requirement/AcceptanceCriterion/KeyFact nodes + edges."""
        author = artifact.author
        ticket_id = artifact.source_ticket_id
        self.add_node(
            GraphNode(
                id=ticket_id,
                type=NodeType.TICKET,
                author=author,
                group_id=group_id,
                attrs={
                    "title": artifact.title,
                    "summary": artifact.summary,
                    "constraints": artifact.constraints,
                    "open_questions": artifact.open_questions,
                },
            )
        )
        for r in artifact.requirements:
            self.add_node(
                GraphNode(
                    id=r.id,
                    type=NodeType.REQUIREMENT,
                    author=author,
                    group_id=group_id,
                    attrs={"text": r.text, "priority": r.priority, "source_ref": r.source_ref},
                )
            )
            self.add_edge(
                GraphEdge(
                    type=EdgeType.DERIVED_FROM, src=r.id, dst=ticket_id,
                    author=author, group_id=group_id,
                )
            )
        for ac in artifact.acceptance_criteria:
            # NOTE: the artifact carries no per-requirement AC link, so ACs validate the
            # ticket as a whole for now. Per-requirement linkage awaits an artifact schema
            # field (ac.requirement_id) — tracked as a future enhancement.
            self.add_node(
                GraphNode(
                    id=ac.id,
                    type=NodeType.ACCEPTANCE_CRITERION,
                    author=author,
                    group_id=group_id,
                    attrs={"text": ac.text, "given": ac.given, "when": ac.when, "then": ac.then},
                )
            )
            self.add_edge(
                GraphEdge(
                    type=EdgeType.VALIDATES, src=ac.id, dst=ticket_id,
                    author=author, group_id=group_id,
                )
            )
        for fact in artifact.key_facts:
            kf_id = new_id("kf")
            self.add_node(
                GraphNode(
                    id=kf_id, type=NodeType.KEY_FACT, author=author,
                    group_id=group_id, attrs={"text": fact},
                )
            )
            self.add_edge(
                GraphEdge(
                    type=EdgeType.STATED_IN, src=kf_id, dst=ticket_id,
                    author=author, group_id=group_id,
                )
            )

    def write_adr(self, adr: ADR, *, group_id: str = DEFAULT_GROUP) -> None:
        """SA output → ADR node + ADDRESSES/DEFERS edges (per trace) + ADDS edges."""
        author = adr.author
        self.add_node(
            GraphNode(
                id=adr.id,
                type=NodeType.ADR,
                author=author,
                group_id=group_id,
                attrs={
                    "title": adr.title,
                    "status": adr.status,
                    "context": adr.context,
                    "decision": adr.decision,
                    "rationale": adr.rationale,
                    "source_requirements_id": adr.source_requirements_id,
                },
            )
        )
        for trace in adr.requirement_traces:
            if trace.addressed:
                self.add_edge(
                    GraphEdge(
                        type=EdgeType.ADDRESSES, src=adr.id, dst=trace.requirement_id,
                        author=author, group_id=group_id, attrs={"how": trace.how},
                    )
                )
            elif trace.deferred_reason:
                self.add_edge(
                    GraphEdge(
                        type=EdgeType.DEFERS, src=adr.id, dst=trace.requirement_id,
                        author=author, group_id=group_id,
                        attrs={"deferred_reason": trace.deferred_reason},
                    )
                )
        for c in adr.added_constraints:
            c_id = new_id("ac-add")
            self.add_node(
                GraphNode(
                    id=c_id, type=NodeType.ADDED_CONSTRAINT, author=author,
                    group_id=group_id,
                    attrs={"text": c.text, "justification": c.justification, "origin": c.origin},
                )
            )
            self.add_edge(
                GraphEdge(
                    type=EdgeType.ADDS, src=adr.id, dst=c_id,
                    author=author, group_id=group_id,
                )
            )

    # -- domain queries (shared) ------------------------------------------

    def requirements_for(
        self, ticket_id: str, *, group_id: str = DEFAULT_GROUP
    ) -> list[GraphNode]:
        derived = self.edges(type=EdgeType.DERIVED_FROM, dst=ticket_id, group_id=group_id)
        ids = {e.src for e in derived}
        return [n for n in self.nodes(type=NodeType.REQUIREMENT, group_id=group_id) if n.id in ids]

    def key_facts(
        self, ticket_id: str, *, group_id: str = DEFAULT_GROUP
    ) -> list[GraphNode]:
        stated = self.edges(type=EdgeType.STATED_IN, dst=ticket_id, group_id=group_id)
        ids = {e.src for e in stated}
        return [n for n in self.nodes(type=NodeType.KEY_FACT, group_id=group_id) if n.id in ids]

    def omitted_requirement_ids(
        self, ticket_id: str, adr_id: str, *, group_id: str = DEFAULT_GROUP
    ) -> set[str]:
        """Graph projection of ``ADR.omitted_requirement_ids``: requirements with no
        ADDRESSES and no DEFERS edge from this ADR were silently dropped."""
        addressed = {e.dst for e in self.edges(type=EdgeType.ADDRESSES, src=adr_id, group_id=group_id)}
        deferred = {e.dst for e in self.edges(type=EdgeType.DEFERS, src=adr_id, group_id=group_id)}
        accounted = addressed | deferred
        return {
            r.id for r in self.requirements_for(ticket_id, group_id=group_id)
            if r.id not in accounted
        }

    def retrieve(
        self, query: str, *, group_id: str = DEFAULT_GROUP, limit: int = 10
    ) -> list[GraphNode]:
        """Naive substring search over node text — the fake's stand-in for Graphiti's
        semantic+keyword search. Enough for the offline loop and metric plumbing."""
        q = query.lower()
        hits = [
            n for n in self.nodes(group_id=group_id)
            if q in str(n.attrs.get("text", "")).lower()
            or q in str(n.attrs.get("summary", "")).lower()
            or q in str(n.attrs.get("title", "")).lower()
        ]
        return hits[:limit]


class InMemoryMemoryStore(MemoryStore):
    """Offline, deterministic ``MemoryStore`` for tests and local development.

    Adding a node with an existing id replaces it (append-only semantics live in the
    event log; this is the materialized current view a real graph would hold)."""

    def __init__(self) -> None:
        # Keyed by (group_id, id): the same id may exist in different run namespaces.
        self._nodes: dict[tuple[str, str], GraphNode] = {}
        self._edges: list[GraphEdge] = []

    def add_node(self, node: GraphNode) -> GraphNode:
        self._nodes[(node.group_id, node.id)] = node
        return node

    def add_edge(self, edge: GraphEdge) -> GraphEdge:
        self._edges.append(edge)
        return edge

    def get_node(self, node_id: str, *, group_id: str = DEFAULT_GROUP) -> GraphNode | None:
        return self._nodes.get((group_id, node_id))

    def nodes(
        self, *, type: NodeType | None = None, group_id: str | None = None
    ) -> list[GraphNode]:
        return [
            n for n in self._nodes.values()
            if (type is None or n.type == type)
            and (group_id is None or n.group_id == group_id)
        ]

    def edges(
        self,
        *,
        type: EdgeType | None = None,
        src: str | None = None,
        dst: str | None = None,
        group_id: str | None = None,
    ) -> list[GraphEdge]:
        return [
            e for e in self._edges
            if (type is None or e.type == type)
            and (src is None or e.src == src)
            and (dst is None or e.dst == dst)
            and (group_id is None or e.group_id == group_id)
        ]

    def promote_canonical(self, node_id: str, *, group_id: str = DEFAULT_GROUP) -> None:
        key = (group_id, node_id)
        node = self._nodes.get(key)
        if node is None:
            raise KeyError(f"no such node: {node_id} (group {group_id})")
        self._nodes[key] = node.model_copy(update={"canonical": True})
