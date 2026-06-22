"""Persisted run records — offline round-trip + resume helpers."""

from agentic_memory import (
    ADR,
    Requirement,
    RequirementsArtifact,
    RunRecord,
    load_runs,
    run_exists,
    save_run,
)


def _record(scenario_id: str, fp: str) -> RunRecord:
    return RunRecord(
        scenario_id=scenario_id,
        set_fingerprint=fp,
        final_state="decision",
        artifact=RequirementsArtifact(
            id="req-1", source_ticket_id=scenario_id, title="t", summary="s",
            requirements=[Requirement(id="r-1", text="a")],
        ),
        adr=ADR(id="adr-1", source_requirements_id="req-1", title="t",
                context="c", decision="d", rationale="r"),
    )


def test_save_and_load_round_trip(tmp_path):
    save_run(_record("SCEN-1", "fp-abc"), directory=tmp_path)
    save_run(_record("SCEN-2", "fp-abc"), directory=tmp_path)
    loaded = load_runs("fp-abc", directory=tmp_path)
    assert set(loaded) == {"SCEN-1", "SCEN-2"}
    assert loaded["SCEN-1"].adr.decision == "d"
    assert loaded["SCEN-1"].artifact.requirements[0].id == "r-1"


def test_run_exists_and_resume(tmp_path):
    assert run_exists("SCEN-1", "fp-abc", directory=tmp_path) is False
    save_run(_record("SCEN-1", "fp-abc"), directory=tmp_path)
    assert run_exists("SCEN-1", "fp-abc", directory=tmp_path) is True
    assert run_exists("SCEN-1", "fp-other", directory=tmp_path) is False  # keyed by fingerprint


def test_load_missing_set_is_empty(tmp_path):
    assert load_runs("nope", directory=tmp_path) == {}
