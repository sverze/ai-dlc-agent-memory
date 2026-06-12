"""GraphitiMemoryStore against a real Neo4j — gated behind `-m graph`.

Needs the graph extra and a running server:

    docker compose up -d
    uv run --extra graph python -m pytest -m graph -v

Each test uses a unique group_id so runs never pollute each other; the suite
mirrors the InMemoryMemoryStore behaviors in tests/test_graph.py — the point is
that the real store is behaviorally identical through the same seam.
"""

import uuid

import pytest

pytest.importorskip("graphiti_core", reason="graph extra not installed")

from agentic_memory import (  # noqa: E402
    ADR,
    AgentPersona,
    EdgeType,
    GraphitiMemoryStore,
    GraphNode,
    InMemoryMemoryStore,
    NodeType,
    Requirement,
    RequirementsArtifact,
    RequirementTrace,
)

pytestmark = pytest.mark.graph


@pytest.fixture(scope="module")
def store() -> GraphitiMemoryStore:
    s = GraphitiMemoryStore()
    try:
        s._all_group_ids()  # connectivity probe
    except Exception as exc:
        pytest.skip(f"Neo4j not reachable (docker compose up -d): {exc}")
    return s


@pytest.fixture()
def group() -> str:
    return f"test-{uuid.uuid4().hex[:8]}"


def _node(id: str, group: str, *, type=NodeType.REQUIREMENT, text="some text") -> GraphNode:
    return GraphNode(
        id=id, type=type, author=AgentPersona.BUSINESS_ANALYST,
        group_id=group, attrs={"text": text, "nested": {"a": [1, 2]}},
    )


def _artifact(ticket_id: str) -> RequirementsArtifact:
    return RequirementsArtifact(
        id="req-1",
        source_ticket_id=ticket_id,
        title="Zero-downtime deploys",
        summary="Ship without dropping requests.",
        requirements=[
            Requirement(id="r-1", text="No request dropped during a deploy"),
            Requirement(id="r-2", text="Roll back within 30 seconds"),
            Requirement(id="r-3", text="Audit log every deploy"),
        ],
        key_facts=["target platform is Kubernetes"],
    )


def _adr(trace_ids, *, deferred=None) -> ADR:
    traces = [RequirementTrace(requirement_id=i, addressed=True, how="by design") for i in trace_ids]
    for i in deferred or []:
        traces.append(RequirementTrace(requirement_id=i, addressed=False, deferred_reason="v2"))
    return ADR(
        id="adr-1", source_requirements_id="req-1", title="Blue-green",
        context="ctx", decision="blue-green", rationale="atomic cutover",
        requirement_traces=traces,
    )


def test_node_roundtrip_preserves_everything(store, group):
    store.add_node(_node("r-1", group))
    back = store.get_node("r-1", group_id=group)
    assert back is not None
    assert back.id == "r-1"
    assert back.type is NodeType.REQUIREMENT
    assert back.author is AgentPersona.BUSINESS_ANALYST
    assert back.attrs == {"text": "some text", "nested": {"a": [1, 2]}}
    assert back.canonical is False


def test_get_missing_node_returns_none(store, group):
    assert store.get_node("nope", group_id=group) is None


def test_add_existing_id_replaces(store, group):
    store.add_node(_node("r-1", group, text="first"))
    store.add_node(_node("r-1", group, text="second"))
    nodes = [n for n in store.nodes(group_id=group) if n.id == "r-1"]
    assert len(nodes) == 1
    assert nodes[0].attrs["text"] == "second"


def test_group_isolation(store, group):
    other = f"{group}-b"
    store.add_node(_node("r-1", group, text="in-A"))
    store.add_node(_node("r-1", other, text="in-B"))
    assert store.get_node("r-1", group_id=group).attrs["text"] == "in-A"
    assert store.get_node("r-1", group_id=other).attrs["text"] == "in-B"


def test_promote_canonical_persists(store, group):
    store.add_node(_node("adr-x", group, type=NodeType.ADR))
    store.promote_canonical("adr-x", group_id=group)
    assert store.get_node("adr-x", group_id=group).canonical is True


def test_promote_missing_raises(store, group):
    with pytest.raises(KeyError):
        store.promote_canonical("ghost", group_id=group)


def test_write_requirements_builds_graph(store, group):
    store.write_requirements(_artifact("JIRA-9"), group_id=group)
    reqs = store.requirements_for("JIRA-9", group_id=group)
    assert {r.id for r in reqs} == {"r-1", "r-2", "r-3"}
    facts = store.key_facts("JIRA-9", group_id=group)
    assert [f.attrs["text"] for f in facts] == ["target platform is Kubernetes"]


def test_omission_query_matches_fake(store, group):
    art = _artifact("JIRA-9")
    adr = _adr(["r-1"], deferred=["r-2"])  # r-3 silently dropped

    fake = InMemoryMemoryStore()
    fake.write_requirements(art, group_id=group)
    fake.write_adr(adr, group_id=group)

    store.write_requirements(art, group_id=group)
    store.write_adr(adr, group_id=group)

    real_omitted = store.omitted_requirement_ids("JIRA-9", "adr-1", group_id=group)
    assert real_omitted == fake.omitted_requirement_ids("JIRA-9", "adr-1", group_id=group)
    assert real_omitted == {"r-3"}


def test_edge_filters(store, group):
    store.write_requirements(_artifact("JIRA-9"), group_id=group)
    store.write_adr(_adr(["r-1", "r-2", "r-3"]), group_id=group)
    addressed = store.edges(type=EdgeType.ADDRESSES, src="adr-1", group_id=group)
    assert {e.dst for e in addressed} == {"r-1", "r-2", "r-3"}
    one = store.edges(type=EdgeType.ADDRESSES, src="adr-1", dst="r-2", group_id=group)
    assert len(one) == 1 and one[0].attrs["how"] == "by design"


def test_answer_clarification_updates_node(store, group):
    store.write_requirements(_artifact("JIRA-9"), group_id=group)
    clar_id = store.write_clarification(
        question="Which platform?", requirement_id="r-1",
        asker=AgentPersona.SOLUTION_ARCHITECT, round=1, group_id=group,
    )
    store.answer_clarification(
        clar_id, answer="Kubernetes", requirement_id="r-1",
        answerer=AgentPersona.BUSINESS_ANALYST, group_id=group,
    )
    node = store.get_node(clar_id, group_id=group)
    assert node.attrs["answer"] == "Kubernetes"
    answered = store.edges(type=EdgeType.ANSWERED_BY, src=clar_id, group_id=group)
    assert len(answered) == 1


def test_retrieve_through_seam(store, group):
    store.write_requirements(_artifact("JIRA-9"), group_id=group)
    hits = store.retrieve("kubernetes", group_id=group)
    assert any("Kubernetes" in str(h.attrs.get("text")) for h in hits)
