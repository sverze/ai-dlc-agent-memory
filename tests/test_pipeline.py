"""End-to-end orchestration — offline (all fakes): ticket → loop → publish."""

from agentic_memory import (
    ADR,
    FakeModelClient,
    InMemoryMemoryStore,
    InMemoryPublisher,
    InMemoryTicketSource,
    RequirementsArtifact,
    process_ticket,
)


def _ba_json() -> str:
    return RequirementsArtifact(
        id="req-1", source_ticket_id="PROJ-1", title="Reset", summary="reset via email",
        requirements=[],
    ).model_dump_json()


def _sa_json() -> str:
    adr = ADR(
        id="adr-1", source_requirements_id="req-1", title="Token reset",
        context="c", decision="d", rationale="r",
        requirement_traces=[],
    )
    return f'{{"adr": {adr.model_dump_json()}}}'


def test_process_ticket_runs_and_publishes():
    source = InMemoryTicketSource({"PROJ-1": "As a user I want to reset my password."})
    # BA returns a RequirementsArtifact, SA returns an SAResponse with an ADR.
    client = FakeModelClient([_ba_json(), _sa_json()])
    store = InMemoryMemoryStore()
    publisher = InMemoryPublisher()

    res = process_ticket("PROJ-1", source=source, model_client=client, store=store, publisher=publisher)

    assert res.ticket_key == "PROJ-1"
    assert res.terminal is True
    assert res.reached_decision is True
    assert res.requirements_ref is not None      # requirements published
    assert res.adr_ref is not None                # ADR published
    assert len(publisher.requirements) == 1 and len(publisher.adrs) == 1


def test_process_ticket_without_publisher_is_safe():
    source = InMemoryTicketSource({"PROJ-1": "ticket body"})
    client = FakeModelClient([_ba_json(), _sa_json()])
    res = process_ticket("PROJ-1", source=source, model_client=client,
                         store=InMemoryMemoryStore(), publisher=None)
    assert res.reached_decision is True
    assert res.requirements_ref is None and res.adr_ref is None  # nothing published, no error


def test_process_ticket_namespaces_memory_by_ticket():
    source = InMemoryTicketSource({"PROJ-9": "body"})
    store = InMemoryMemoryStore()
    process_ticket("PROJ-9", source=source, model_client=FakeModelClient([_ba_json(), _sa_json()]),
                   store=store)
    # the requirements were written under the ticket's group id
    assert any(n.group_id == "PROJ-9" for n in store.nodes())
