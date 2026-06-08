"""Tests for the typed data contracts."""

from agentic_memory import (
    ADR,
    AddedConstraint,
    AgentPersona,
    Requirement,
    RequirementsArtifact,
    RequirementTrace,
)


def _artifact() -> RequirementsArtifact:
    return RequirementsArtifact(
        source_ticket_id="JIRA-101",
        title="Zero-downtime deploys",
        summary="The service must deploy without dropping requests.",
        requirements=[
            Requirement(id="r-1", text="No dropped requests during deploy"),
            Requirement(id="r-2", text="Rollback within 5 minutes"),
            Requirement(id="r-3", text="Health checks gate traffic"),
        ],
        key_facts=["zero-downtime", "rollback<=5m"],
    )


def test_requirements_artifact_roundtrips():
    art = _artifact()
    restored = RequirementsArtifact.model_validate_json(art.model_dump_json())
    assert restored == art
    assert restored.author is AgentPersona.BUSINESS_ANALYST
    assert len(restored.requirements) == 3


def test_ids_are_generated_and_unique():
    a, b = Requirement(text="x"), Requirement(text="y")
    assert a.id != b.id
    assert a.id.startswith("r-")


def test_added_constraint_is_labelled_architect_added():
    c = AddedConstraint(text="Use circuit breakers", justification="Avoid cascading failure")
    assert c.origin == "architect-added"


def test_addressed_and_omitted_requirements():
    art = _artifact()
    adr = ADR(
        source_requirements_id=art.id,
        title="Blue-green deploys",
        context="Need zero-downtime",
        decision="Adopt blue-green deployment",
        rationale="Cleanest path to no dropped requests",
        requirement_traces=[
            RequirementTrace(requirement_id="r-1", addressed=True, how="blue-green"),
            RequirementTrace(
                requirement_id="r-2", addressed=False, deferred_reason="separate runbook"
            ),
            # r-3 deliberately untraced -> should count as omitted
        ],
    )
    assert adr.addressed_requirement_ids() == {"r-1"}
    # r-2 is deferred (not omitted); r-3 is silently dropped.
    assert adr.omitted_requirement_ids(art) == {"r-3"}


def test_no_omissions_when_all_traced():
    art = _artifact()
    adr = ADR(
        source_requirements_id=art.id,
        title="t",
        context="c",
        decision="d",
        rationale="r",
        requirement_traces=[
            RequirementTrace(requirement_id="r-1", addressed=True),
            RequirementTrace(requirement_id="r-2", addressed=True),
            RequirementTrace(requirement_id="r-3", addressed=True),
        ],
    )
    assert adr.omitted_requirement_ids(art) == set()
