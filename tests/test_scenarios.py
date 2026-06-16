"""Frozen scenario set — offline tests: parse, load, fingerprint, ticket-source, loop."""

import pytest

from agentic_memory import (
    ADR,
    BAAgent,
    EventLog,
    FSM,
    FakeModelClient,
    InMemoryMemoryStore,
    RequirementsArtifact,
    ScenarioSet,
    ScenarioTicketSource,
    SAAgent,
    load_scenarios,
    parse_scenario,
    run_loop,
)

_SCENARIO = """\
---
id: SCEN-001
title: Password reset
source: illustrative
anonymized: true
author: ext
expected_key_requirements: link expires 30 min; attempts logged
notes: keep it simple
---
As a user I want to reset my password via email.

Some more context.
"""


# --- parsing ---------------------------------------------------------------

def test_parse_extracts_frontmatter_and_body():
    s = parse_scenario(_SCENARIO)
    assert s.id == "SCEN-001"
    assert s.title == "Password reset"
    assert s.source == "illustrative"
    assert s.anonymized is True
    assert s.author == "ext"
    assert s.expected_key_requirements == ["link expires 30 min", "attempts logged"]
    assert s.notes == "keep it simple"
    assert s.body.startswith("As a user")
    assert "Some more context." in s.body


def test_parse_anonymized_coerced_to_bool():
    assert parse_scenario(_SCENARIO.replace("anonymized: true", "anonymized: false")).anonymized is False
    assert parse_scenario(_SCENARIO.replace("anonymized: true", "anonymized: yes")).anonymized is True


def test_parse_body_may_contain_horizontal_rule():
    text = _SCENARIO + "\n---\n\nA trailing section after a rule."
    s = parse_scenario(text)
    assert "trailing section after a rule" in s.body  # only the first --- block is frontmatter


def test_parse_missing_required_field_raises():
    bad = _SCENARIO.replace("title: Password reset\n", "")
    with pytest.raises(ValueError, match="title"):
        parse_scenario(bad)


def test_parse_requires_frontmatter():
    with pytest.raises(ValueError, match="frontmatter"):
        parse_scenario("no frontmatter here")


# --- set + fingerprint -----------------------------------------------------

def _set() -> ScenarioSet:
    a = parse_scenario(_SCENARIO)
    b = parse_scenario(_SCENARIO.replace("SCEN-001", "SCEN-002").replace("Password reset", "Export CSV"))
    return ScenarioSet(scenarios=[a, b])


def test_set_get_ids_iter():
    s = _set()
    assert s.ids() == ["SCEN-001", "SCEN-002"]
    assert s.get("SCEN-002").title == "Export CSV"
    assert [sc.id for sc in s] == ["SCEN-001", "SCEN-002"]
    with pytest.raises(KeyError):
        s.get("nope")


def test_duplicate_ids_raise():
    a = parse_scenario(_SCENARIO)
    with pytest.raises(ValueError, match="duplicate scenario id"):
        ScenarioSet(scenarios=[a, a])


def test_fingerprint_is_order_independent_and_stable():
    a = parse_scenario(_SCENARIO)
    b = parse_scenario(_SCENARIO.replace("SCEN-001", "SCEN-002"))
    fp1 = ScenarioSet(scenarios=[a, b]).fingerprint()
    fp2 = ScenarioSet(scenarios=[b, a]).fingerprint()
    assert fp1 == fp2  # order-independent
    assert len(fp1) == 64  # sha256 hex


def test_fingerprint_changes_with_content():
    base = _set().fingerprint()
    a = parse_scenario(_SCENARIO.replace("via email", "via SMS"))
    b = parse_scenario(_SCENARIO.replace("SCEN-001", "SCEN-002").replace("Password reset", "Export CSV"))
    assert ScenarioSet(scenarios=[a, b]).fingerprint() != base


def test_fingerprint_covers_provenance_and_expectations():
    base = _set().fingerprint()
    # changing provenance must move the hash (results are attributable to provenance too)
    prov = _SCENARIO.replace("source: illustrative", "source: anonymized-prod-2026Q2")
    b = parse_scenario(_SCENARIO.replace("SCEN-001", "SCEN-002").replace("Password reset", "Export CSV"))
    assert ScenarioSet(scenarios=[parse_scenario(prov), b]).fingerprint() != base
    # changing expected_key_requirements must move the hash
    exp = _SCENARIO.replace("link expires 30 min; attempts logged", "link expires 15 min")
    assert ScenarioSet(scenarios=[parse_scenario(exp), b]).fingerprint() != base


# --- ticket source + loop --------------------------------------------------

def test_ticket_source_body_is_title_plus_body():
    src = ScenarioTicketSource(_set())
    t = src.fetch("SCEN-001")
    assert t.id == "SCEN-001"
    assert t.body.startswith("Password reset\n\n")
    assert "reset my password" in t.body


def test_ticket_source_unknown_raises():
    with pytest.raises(KeyError, match="ticket not found"):
        ScenarioTicketSource(_set()).fetch("SCEN-999")


def test_scenario_drives_run_loop(tmp_path):
    # The scenario flows through the SAME run_loop as any ticket (scripted fake models).
    artifact = RequirementsArtifact(
        id="req-1", source_ticket_id="SCEN-001", title="Password reset",
        summary="reset via email", requirements=[],
    )
    adr = ADR(
        id="adr-1", source_requirements_id="req-1", title="Token reset",
        context="c", decision="d", rationale="r", requirement_traces=[],
    )
    ba = BAAgent(FakeModelClient([artifact.model_dump_json()]), InMemoryMemoryStore())
    store = ba.store
    sa = SAAgent(FakeModelClient([f'{{"adr": {adr.model_dump_json()}}}']), store)
    fsm = FSM(EventLog(tmp_path / "e.jsonl"))

    src = ScenarioTicketSource(_set())
    result = run_loop(src.fetch("SCEN-001"), ba=ba, sa=sa, fsm=fsm)
    assert result.adr is not None
    assert result.artifact.source_ticket_id == "SCEN-001"


# --- the shipped illustrative corpus --------------------------------------

def test_shipped_scenarios_load_and_are_labelled():
    s = load_scenarios("scenarios")
    assert len(s) >= 2
    for sc in s:
        assert sc.anonymized is True, f"{sc.id} must be anonymized (D9)"
        assert sc.source != "real", f"{sc.id} must not claim to be the real gate corpus"
        assert sc.body.strip()
    # fingerprint is computable on the real corpus
    assert len(s.fingerprint()) == 64
