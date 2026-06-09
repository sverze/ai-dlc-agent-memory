"""Tests for the L4 shared-memory store (in-memory fake)."""

import pytest

from agentic_memory import (
    ADR,
    AcceptanceCriterion,
    AddedConstraint,
    EdgeType,
    InMemoryMemoryStore,
    NodeType,
    Requirement,
    RequirementsArtifact,
    RequirementTrace,
)


def _artifact() -> RequirementsArtifact:
    return RequirementsArtifact(
        source_ticket_id="JIRA-1",
        title="Zero-downtime deploys",
        summary="Ship without downtime.",
        requirements=[
            Requirement(id="r-1", text="No request dropped during deploy"),
            Requirement(id="r-2", text="Rollback within 30s"),
            Requirement(id="r-3", text="Audit log of each deploy"),
        ],
        acceptance_criteria=[AcceptanceCriterion(id="ac-1", text="zero 5xx during rollout")],
        key_facts=["target is Kubernetes", "SLA is 99.95%"],
    )


def _adr_addressing(req_ids, *, deferred=None, constraints=None) -> ADR:
    traces = [RequirementTrace(requirement_id=i, addressed=True, how="handled") for i in req_ids]
    for i in deferred or []:
        traces.append(RequirementTrace(requirement_id=i, addressed=False, deferred_reason="later"))
    return ADR(
        id="adr-1",
        source_requirements_id="req-1",
        title="Blue-green deploys",
        context="ctx",
        decision="use blue-green",
        rationale="because",
        requirement_traces=traces,
        added_constraints=[AddedConstraint(text=c, justification="j") for c in (constraints or [])],
    )


def test_write_requirements_creates_nodes_and_edges():
    store = InMemoryMemoryStore()
    store.write_requirements(_artifact())

    assert store.get_node("JIRA-1").type is NodeType.TICKET
    reqs = store.requirements_for("JIRA-1")
    assert {r.id for r in reqs} == {"r-1", "r-2", "r-3"}
    # each requirement is DERIVED_FROM the ticket
    assert len(store.edges(type=EdgeType.DERIVED_FROM, dst="JIRA-1")) == 3


def test_key_facts_are_nodes_and_retrievable():
    store = InMemoryMemoryStore()
    store.write_requirements(_artifact())

    facts = {n.attrs["text"] for n in store.key_facts("JIRA-1")}
    assert facts == {"target is Kubernetes", "SLA is 99.95%"}


def test_retrieve_substring_search():
    store = InMemoryMemoryStore()
    store.write_requirements(_artifact())

    hits = store.retrieve("kubernetes")
    assert any(h.type is NodeType.KEY_FACT for h in hits)


def test_adr_addresses_edges_written():
    store = InMemoryMemoryStore()
    store.write_requirements(_artifact())
    store.write_adr(_adr_addressing(["r-1", "r-2", "r-3"]))

    addressed = store.edges(type=EdgeType.ADDRESSES, src="adr-1")
    assert {e.dst for e in addressed} == {"r-1", "r-2", "r-3"}
    assert all(e.attrs["how"] == "handled" for e in addressed)


def test_omission_detected_when_requirement_unaddressed():
    store = InMemoryMemoryStore()
    store.write_requirements(_artifact())
    # r-3 is neither addressed nor deferred → silently dropped
    store.write_adr(_adr_addressing(["r-1", "r-2"]))

    assert store.omitted_requirement_ids("JIRA-1", "adr-1") == {"r-3"}


def test_deferred_requirement_is_not_an_omission():
    store = InMemoryMemoryStore()
    store.write_requirements(_artifact())
    store.write_adr(_adr_addressing(["r-1", "r-2"], deferred=["r-3"]))

    assert store.omitted_requirement_ids("JIRA-1", "adr-1") == set()
    assert len(store.edges(type=EdgeType.DEFERS, src="adr-1")) == 1


def test_added_constraints_written_as_nodes():
    store = InMemoryMemoryStore()
    store.write_requirements(_artifact())
    store.write_adr(_adr_addressing(["r-1", "r-2", "r-3"], constraints=["use mTLS"]))

    adds = store.edges(type=EdgeType.ADDS, src="adr-1")
    assert len(adds) == 1
    constraint = store.get_node(adds[0].dst)
    assert constraint.type is NodeType.ADDED_CONSTRAINT
    assert constraint.attrs["origin"] == "architect-added"


def test_canonical_promotion():
    store = InMemoryMemoryStore()
    store.write_requirements(_artifact())
    store.write_adr(_adr_addressing(["r-1", "r-2", "r-3"]))

    assert store.get_node("adr-1").canonical is False
    store.promote_canonical("adr-1")
    assert store.get_node("adr-1").canonical is True


def test_promote_missing_node_raises():
    store = InMemoryMemoryStore()
    with pytest.raises(KeyError):
        store.promote_canonical("nope")


def test_group_isolation():
    store = InMemoryMemoryStore()
    store.write_requirements(_artifact(), group_id="run-A")
    # A different run's ticket id collides, but lives in its own namespace.
    other = _artifact()
    store.write_requirements(other, group_id="run-B")

    assert len(store.requirements_for("JIRA-1", group_id="run-A")) == 3
    assert len(store.nodes(type=NodeType.TICKET, group_id="run-A")) == 1
    assert len(store.nodes(type=NodeType.TICKET, group_id="run-B")) == 1
    # retrieve respects the namespace
    assert store.retrieve("kubernetes", group_id="run-A")
    assert all(n.group_id == "run-A" for n in store.retrieve("kubernetes", group_id="run-A"))
