"""Advisory eval harness — offline tests: scorers, κ, judge (fake), report, advisory invariant."""

from agentic_memory import (
    ADR,
    FakeModelClient,
    Requirement,
    RequirementsArtifact,
    RequirementTrace,
    Verdict,
    VerdictDecision,
    build_eval_report,
    cohens_kappa,
    judge_adr,
    judge_agreement,
    kappa_band,
    score_traceability,
)
from agentic_memory.eval import JudgeVerdict


def _artifact(reqs=3) -> RequirementsArtifact:
    return RequirementsArtifact(
        id="req-1", source_ticket_id="SCEN-1", title="t", summary="s",
        requirements=[Requirement(id=f"r-{i}", text=f"req {i}") for i in range(1, reqs + 1)],
    )


def _adr(addressed, deferred=()) -> ADR:
    traces = [RequirementTrace(requirement_id=i, addressed=True, how="x") for i in addressed]
    traces += [RequirementTrace(requirement_id=i, addressed=False, deferred_reason="v2") for i in deferred]
    return ADR(
        id="adr-1", source_requirements_id="req-1", title="t",
        context="c", decision="d", rationale="r", requirement_traces=traces,
    )


# --- Tier A: traceability ---------------------------------------------------

def test_traceability_full_coverage():
    s = score_traceability(_artifact(3), _adr(["r-1", "r-2", "r-3"]), scenario_id="SCEN-1")
    assert (s.addressed, s.deferred, s.omitted) == (3, 0, 0)
    assert s.omission_rate == 0.0 and s.traceability_rate == 1.0


def test_traceability_with_omission_and_deferral():
    # r-1 addressed, r-2 deferred, r-3 silently dropped
    s = score_traceability(_artifact(3), _adr(["r-1"], deferred=["r-2"]))
    assert s.addressed == 1 and s.deferred == 1 and s.omitted == 1
    assert s.omission_rate == 1 / 3
    assert s.traceability_rate == 2 / 3


def test_traceability_zero_requirements_no_div0():
    s = score_traceability(_artifact(0), _adr([]))
    assert s.omission_rate == 0.0 and s.traceability_rate == 0.0


# --- Cohen's κ --------------------------------------------------------------

def test_kappa_perfect_agreement():
    pairs = [("accept", "accept"), ("reject", "reject"), ("revise", "revise"), ("accept", "accept")]
    assert cohens_kappa(pairs) == 1.0


def test_kappa_total_disagreement_is_negative_or_zero():
    pairs = [("accept", "reject"), ("reject", "accept")]
    assert cohens_kappa(pairs) <= 0.0


def test_kappa_single_category_both_agree():
    # both raters only ever said "accept" → pe == 1, perfect agreement → 1.0
    assert cohens_kappa([("accept", "accept")] * 5) == 1.0


def test_kappa_empty():
    assert cohens_kappa([]) == 0.0


def test_kappa_bands():
    assert kappa_band(0.9) == "almost perfect"
    assert kappa_band(0.7) == "substantial"
    assert kappa_band(0.5) == "moderate"
    assert kappa_band(-0.1).startswith("poor")


# --- Tier B: judge via fake client -----------------------------------------

def test_judge_adr_parses_scripted_verdict():
    client = FakeModelClient('{"verdict": "accept", "rationale": "sound and traceable"}')
    jv = judge_adr(client, _artifact(2), _adr(["r-1", "r-2"]), scenario_id="SCEN-1")
    assert jv.scenario_id == "SCEN-1"
    assert jv.verdict is VerdictDecision.ACCEPT
    assert jv.rationale.startswith("sound")
    # default judge persona is the BA's (Gemini) — cross-family to the SA's Claude ADR
    assert jv.judge_model == "gemini-2.5-flash"


# --- agreement flags --------------------------------------------------------

def test_agreement_insufficient_sample_and_trust():
    pairs = [(VerdictDecision.ACCEPT, VerdictDecision.ACCEPT)] * 4
    a = judge_agreement(pairs, min_n=10)
    assert a.insufficient_sample is True
    assert a.trusted is False  # high agreement but too few samples


def test_agreement_trusted_with_enough_strong_agreement():
    pairs = [(VerdictDecision.ACCEPT, VerdictDecision.ACCEPT)] * 8 + [
        (VerdictDecision.REJECT, VerdictDecision.REJECT)] * 4
    a = judge_agreement(pairs, min_n=10)
    assert a.insufficient_sample is False and a.degenerate is False
    assert a.kappa == 1.0 and a.trusted is True


def test_degenerate_single_category_never_trusted():
    # Both always "accept" over a big sample: κ=1.0, n≥min — but ZERO discrimination shown.
    pairs = [(VerdictDecision.ACCEPT, VerdictDecision.ACCEPT)] * 20
    a = judge_agreement(pairs, min_n=10)
    assert a.agreement_rate == 1.0 and a.kappa == 1.0
    assert a.degenerate is True
    assert a.trusted is False  # the honesty fix: base-rate agreement is not trust


# --- report assembly + THE advisory invariant ------------------------------

def _verdicts(spec) -> list[Verdict]:
    return [
        Verdict(scenario_id=s, adr_id="adr-1", set_fingerprint="fp", verdict=v, reviewer="ext")
        for s, v in spec
    ]


def test_report_gate_from_humans_only_and_judge_kappa_on_overlap():
    trace = [score_traceability(_artifact(3), _adr(["r-1", "r-2", "r-3"]), scenario_id="SCEN-1")]
    humans = _verdicts([("SCEN-1", VerdictDecision.ACCEPT), ("SCEN-2", VerdictDecision.REJECT)])
    judges = [
        JudgeVerdict(scenario_id="SCEN-1", verdict=VerdictDecision.ACCEPT),
        JudgeVerdict(scenario_id="SCEN-3", verdict=VerdictDecision.ACCEPT),  # no human → excluded
    ]
    r = build_eval_report(trace, humans, judges, set_fingerprint="fp")
    assert r.human_gate.total == 2          # gate counts humans
    assert r.mean_traceability_rate == 1.0
    assert r.judge is not None and r.judge.n == 1   # only SCEN-1 overlaps


def test_judge_cannot_move_the_gate():
    # THE invariant (D7/NFR4): flipping every judge verdict must not change meets_gate.
    trace = [score_traceability(_artifact(1), _adr(["r-1"]), scenario_id=f"S{i}") for i in range(20)]
    humans = _verdicts([(f"S{i}", VerdictDecision.ACCEPT) for i in range(20)])
    no_judge = build_eval_report(trace, humans, [], set_fingerprint="fp")
    hostile = build_eval_report(
        trace, humans,
        [JudgeVerdict(scenario_id=f"S{i}", verdict=VerdictDecision.REJECT) for i in range(20)],
        set_fingerprint="fp",
    )
    assert no_judge.human_gate.meets_gate == hostile.human_gate.meets_gate
    # 20/20 human accepts clears the Wilson lower bound regardless of the judge
    assert hostile.human_gate.meets_gate is True
