"""Architect verdict capture — offline tests: model, store, wilson, gate summary."""

import pytest

from agentic_memory import (
    FileVerdictStore,
    InMemoryVerdictStore,
    Verdict,
    VerdictDecision,
    load_verdicts,
    parse_verdict,
    summarize_verdicts,
    wilson_lower_bound,
)


def _v(scenario_id: str, decision: VerdictDecision, *, fp: str = "fp-1") -> Verdict:
    return Verdict(
        scenario_id=scenario_id, adr_id="adr-1", set_fingerprint=fp,
        verdict=decision, reviewer="ext.architect", notes="some notes",
    )


# --- model round-trip ------------------------------------------------------

def test_verdict_markdown_round_trips():
    v = _v("SCEN-001", VerdictDecision.ACCEPT)
    back = parse_verdict(v.to_markdown())
    assert back == v


def test_parse_requires_frontmatter():
    with pytest.raises(ValueError, match="frontmatter"):
        parse_verdict("just text")


def test_parse_bad_decision_raises():
    md = _v("SCEN-001", VerdictDecision.ACCEPT).to_markdown().replace("verdict: accept", "verdict: maybe")
    with pytest.raises(ValueError):
        parse_verdict(md)


# --- stores ----------------------------------------------------------------

def test_inmemory_store_latest_wins():
    s = InMemoryVerdictStore()
    s.record(_v("SCEN-001", VerdictDecision.REVISE))
    s.record(_v("SCEN-001", VerdictDecision.ACCEPT))
    assert len(s.all()) == 1
    assert s.all()[0].verdict is VerdictDecision.ACCEPT


def test_file_store_record_and_load(tmp_path):
    store = FileVerdictStore(tmp_path)
    store.record(_v("SCEN-001", VerdictDecision.ACCEPT))
    store.record(_v("SCEN-002", VerdictDecision.REJECT))
    loaded = store.all()
    assert {v.scenario_id for v in loaded} == {"SCEN-001", "SCEN-002"}
    assert load_verdicts(tmp_path)[0] == _v("SCEN-001", VerdictDecision.ACCEPT)


def test_load_missing_dir_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_verdicts(tmp_path / "nope")


# --- wilson lower bound ----------------------------------------------------

def test_wilson_edge_and_monotonic():
    assert wilson_lower_bound(0, 0) == 0.0
    assert wilson_lower_bound(1, 1) > 0.0
    # same 100% rate, larger n → tighter (higher) lower bound
    assert wilson_lower_bound(10, 10) > wilson_lower_bound(2, 2)
    # lower bound is always ≤ the point estimate
    assert wilson_lower_bound(7, 10) <= 0.7


# --- gate summary ----------------------------------------------------------

def test_summary_counts_and_rates():
    vs = [
        _v("S1", VerdictDecision.ACCEPT), _v("S2", VerdictDecision.ACCEPT),
        _v("S3", VerdictDecision.REVISE), _v("S4", VerdictDecision.REJECT),
    ]
    r = summarize_verdicts(vs)
    assert (r.total, r.accept, r.revise, r.reject) == (4, 2, 1, 1)
    assert r.accept_rate == 0.5
    assert r.reject_rate == 0.25
    assert r.meets_gate is False  # 50% accept, 25% reject — fails D7


def test_summary_filters_by_fingerprint():
    vs = [_v("S1", VerdictDecision.ACCEPT, fp="fp-A"), _v("S2", VerdictDecision.REJECT, fp="fp-B")]
    rA = summarize_verdicts(vs, set_fingerprint="fp-A")
    assert rA.total == 1 and rA.accept == 1 and rA.meets_gate is False  # n=1 lower bound < 0.70


def test_gate_passes_with_strong_accept():
    # 20/20 accepts → Wilson lower bound clears 0.70, no rejects → gate passes
    vs = [_v(f"S{i}", VerdictDecision.ACCEPT) for i in range(20)]
    r = summarize_verdicts(vs)
    assert r.accept_lower95 >= 0.70
    assert r.meets_gate is True


def test_empty_set_does_not_pass_gate():
    assert summarize_verdicts([]).meets_gate is False
