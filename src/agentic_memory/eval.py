"""Advisory eval harness (FR9) — machine metrics measured AGAINST the human verdict.

Three grader tiers (Evals skill): deterministic structured scorers, an advisory LLM judge,
and the human verdict (primary, D20). This module is the first two; the human gate stays in
`verdicts.py`.

**The advisory constraint is structural, not polite (D7/NFR4).** `build_eval_report` computes
the gate from HUMAN verdicts only (`summarize_verdicts`); the LLM judge lives in a separate
stream and its verdict exists *only* to be scored against the human via Cohen's κ. Nothing the
judge emits can reach `meets_gate` — the gate function never receives judge output. A test proves
changing the judge cannot move the gate.

**Cross-family judge (D7).** The judge runs on the BA's Gemini binding by default — deliberately a
different model family from the SA's Claude ADR, so it isn't grading its own family (same-family
judges over-rate their own output). κ ≥ 0.6 (the conventional "substantial agreement" bar) and a
minimum sample are required before the judge is even called "trusted" — and trust only governs how
much attention its advice gets, never whether it can block.
"""

from __future__ import annotations

import json
from collections import Counter

from pydantic import BaseModel

from .artifacts import ADR, AgentPersona, RequirementsArtifact
from .models import Message, MessageRole, ModelClient
from .verdicts import GateReadout, Verdict, VerdictDecision, summarize_verdicts

# κ is unstable below this many dual-labelled ADRs (Evals skill: ~30–50 ideal).
MIN_KAPPA_SAMPLE = 10


# --- Tier A: deterministic structured scorers ------------------------------


class TraceabilityScore(BaseModel):
    scenario_id: str
    requirements: int
    addressed: int
    deferred: int
    omitted: int
    omission_rate: float
    traceability_rate: float


def score_traceability(
    artifact: RequirementsArtifact, adr: ADR, *, scenario_id: str = ""
) -> TraceabilityScore:
    """Deterministic: did every source requirement get an addressed/deferred trace?

    Pure structural check over the typed ADR (reuses `ADR.addressed_requirement_ids` /
    `omitted_requirement_ids`) — no judgment. Semantic adequacy is the judge's job, not this.
    """
    n = len(artifact.requirements)
    addressed = adr.addressed_requirement_ids()
    omitted = adr.omitted_requirement_ids(artifact)
    deferred = {
        t.requirement_id
        for t in adr.requirement_traces
        if not t.addressed and t.deferred_reason
    }
    return TraceabilityScore(
        scenario_id=scenario_id,
        requirements=n,
        addressed=len(addressed),
        deferred=len(deferred),
        omitted=len(omitted),
        omission_rate=(len(omitted) / n) if n else 0.0,
        traceability_rate=((n - len(omitted)) / n) if n else 0.0,
    )


# --- Tier B: advisory LLM judge (cross-family, never gating) ---------------


JUDGE_SYSTEM = (
    "You are an INDEPENDENT senior reviewer scoring an Architecture Decision Record against the "
    "requirements it was meant to satisfy. You are ADVISORY ONLY — a human architect makes the "
    "real decision and your score never overrides theirs. Judge whether the ADR is sound, "
    "traceable, and honest about trade-offs and consequences."
)


class JudgeVerdict(BaseModel):
    """The judge's advisory verdict — exists ONLY to be compared to the human via κ."""

    scenario_id: str
    verdict: VerdictDecision
    rationale: str = ""
    judge_model: str = ""


def judge_adr(
    client: ModelClient,
    artifact: RequirementsArtifact,
    adr: ADR,
    *,
    scenario_id: str,
    judge_persona: AgentPersona = AgentPersona.BUSINESS_ANALYST,
) -> JudgeVerdict:
    """Run the advisory judge over one ADR. Returns a verdict for κ comparison only.

    ``judge_persona`` defaults to the BA's binding (Gemini) — deliberately cross-family to the
    SA's Claude ADR (D7). Pass a different persona/client to change the judge model.
    """
    reqs = "; ".join(f"{r.id}: {r.text}" for r in artifact.requirements)
    traces = "; ".join(
        f"{t.requirement_id}:{'addressed' if t.addressed else 'deferred'}"
        for t in adr.requirement_traces
    )
    prompt = (
        f"Requirements:\n{reqs}\n\n"
        f"ADR decision: {adr.decision}\n"
        f"ADR rationale: {adr.rationale}\n"
        f"Requirement traces: {traces}\n"
        f"Added constraints: {len(adr.added_constraints)}\n\n"
        "Return ONLY raw JSON: "
        '{"verdict": "accept" | "revise" | "reject", "rationale": "<one or two sentences>"}'
    )
    resp = client.complete(
        [Message(role=MessageRole.USER, content=prompt)],
        persona=judge_persona,
        system=JUDGE_SYSTEM,
    )
    data = json.loads(resp.text)
    return JudgeVerdict(
        scenario_id=scenario_id,
        verdict=VerdictDecision(str(data["verdict"]).strip().lower()),
        rationale=str(data.get("rationale", "")),
        judge_model=resp.model,
    )


# --- judge-vs-human agreement (Cohen's κ) ----------------------------------


def cohens_kappa(pairs: list[tuple[str, str]]) -> float:
    """Unweighted Cohen's κ over paired (rater_a, rater_b) labels.

    κ = (po − pe) / (1 − pe). Perfect agreement → 1.0; pe == 1 (both raters used a single
    identical category) → 1.0 if they agree else 0.0. Empty → 0.0.
    """
    n = len(pairs)
    if n == 0:
        return 0.0
    po = sum(1 for a, b in pairs if a == b) / n
    a_marg = Counter(a for a, _ in pairs)
    b_marg = Counter(b for _, b in pairs)
    labels = set(a_marg) | set(b_marg)
    pe = sum((a_marg[l] / n) * (b_marg[l] / n) for l in labels)
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return (po - pe) / (1 - pe)


def kappa_band(k: float) -> str:
    if k < 0.0:
        return "poor (worse than chance)"
    if k < 0.20:
        return "slight"
    if k < 0.40:
        return "fair"
    if k < 0.60:
        return "moderate"
    if k < 0.80:
        return "substantial"
    return "almost perfect"


class JudgeAgreement(BaseModel):
    n: int
    agreement_rate: float
    kappa: float
    band: str
    trusted: bool
    insufficient_sample: bool
    degenerate: bool  # only one verdict category present → κ carries no discrimination signal


def judge_agreement(
    pairs: list[tuple[VerdictDecision, VerdictDecision]], *, min_n: int = MIN_KAPPA_SAMPLE
) -> JudgeAgreement:
    """Agreement between judge and human over paired verdicts.

    ``trusted`` requires κ ≥ 0.6 AND a sufficient sample (n ≥ min_n) AND a non-degenerate label
    distribution. The last guard matters: if every pair is the same single verdict (e.g. all
    "accept"), κ is mathematically 1.0 but **proves nothing** — the judge never demonstrated it can
    tell a good ADR from a bad one. Such a set is never "trusted" no matter how high agreement looks.
    ``min_n`` is the operational floor (10); κ is only really *stable* at ~30+ dual-labels, so read
    n between 10 and 30 with the ``insufficient_sample`` caution in mind. Trust governs how much
    weight the judge's advice gets — never whether it can block (always the human's call).
    """
    str_pairs = [(a.value, b.value) for a, b in pairs]
    n = len(str_pairs)
    k = cohens_kappa(str_pairs)
    agree = (sum(1 for a, b in str_pairs if a == b) / n) if n else 0.0
    distinct = {lbl for pair in str_pairs for lbl in pair}
    degenerate = n > 0 and len(distinct) < 2
    insufficient = n < min_n
    return JudgeAgreement(
        n=n,
        agreement_rate=agree,
        kappa=k,
        band=kappa_band(k),
        trusted=(k >= 0.60 and not insufficient and not degenerate),
        insufficient_sample=insufficient,
        degenerate=degenerate,
    )


# --- the assembled report --------------------------------------------------


class EvalReport(BaseModel):
    set_fingerprint: str | None
    n_scenarios: int
    human_gate: GateReadout            # from HUMAN verdicts only — the gate
    mean_omission_rate: float
    mean_traceability_rate: float
    judge: JudgeAgreement | None = None  # advisory; compared to human, never gating


def build_eval_report(
    traceability: list[TraceabilityScore],
    human_verdicts: list[Verdict],
    judge_verdicts: list[JudgeVerdict],
    *,
    set_fingerprint: str | None = None,
) -> EvalReport:
    """Assemble the eval report. The gate comes from HUMAN verdicts only (structural advisory).

    Judge κ is computed only over scenarios with BOTH a human and a judge verdict.
    """
    # The gate — humans only. Judge verdicts are deliberately NOT passed here.
    human_gate = summarize_verdicts(human_verdicts, set_fingerprint=set_fingerprint)

    n_trace = len(traceability)
    mean_omission = sum(t.omission_rate for t in traceability) / n_trace if n_trace else 0.0
    mean_trace = sum(t.traceability_rate for t in traceability) / n_trace if n_trace else 0.0

    # Judge agreement — pair on scenario_id where both exist.
    human_by_id = {v.scenario_id: v.verdict for v in human_verdicts}
    judge_by_id = {j.scenario_id: j.verdict for j in judge_verdicts}
    overlap = sorted(set(human_by_id) & set(judge_by_id))
    judge = (
        judge_agreement([(human_by_id[s], judge_by_id[s]) for s in overlap])
        if overlap
        else None
    )

    return EvalReport(
        set_fingerprint=set_fingerprint,
        n_scenarios=n_trace,
        human_gate=human_gate,
        mean_omission_rate=mean_omission,
        mean_traceability_rate=mean_trace,
        judge=judge,
    )
