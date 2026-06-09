"""run_loop — drives the FSM through one BA→SA roundtrip.

The agents *act* per state and the FSM *executes* transitions (D2). This is the end-to-end
core-hypothesis loop: ticket → requirements (BA) → shared memory → ADR (SA), with an
analysis⇄clarification negotiation and a clarify-round cap that forces escalation. Every
step is logged, so the run replays to identical state.
"""

from __future__ import annotations

from pydantic import BaseModel

from .agents import BAAgent, ClarificationRequest, SAAgent, TicketInput
from .artifacts import ADR, AgentPersona, RequirementsArtifact
from .fsm import FSM, DLCState, TransitionProposal
from .graph import DEFAULT_GROUP

_BA = AgentPersona.BUSINESS_ANALYST.value
_SA = AgentPersona.SOLUTION_ARCHITECT.value


class LoopResult(BaseModel):
    final_state: DLCState
    artifact: RequirementsArtifact | None = None
    adr: ADR | None = None
    clarify_rounds: int = 0
    escalated: bool = False

    @property
    def accepted_terminal(self) -> bool:
        return self.final_state is DLCState.DECISION


def run_loop(
    ticket: TicketInput,
    *,
    ba: BAAgent,
    sa: SAAgent,
    fsm: FSM,
    group_id: str = DEFAULT_GROUP,
    max_steps: int = 50,
) -> LoopResult:
    artifact: RequirementsArtifact | None = None
    adr: ADR | None = None
    pending: list[tuple[str, ClarificationRequest]] = []

    steps = 0
    while not fsm.is_terminal() and steps < max_steps:
        steps += 1
        state = fsm.state

        if state is DLCState.INTAKE:
            artifact = ba.intake(ticket, group_id=group_id)
            fsm.propose(TransitionProposal(
                to_state=DLCState.ANALYSIS, agent=_BA,
                reason="requirements extracted from ticket", confidence=0.95,
            ))

        elif state is DLCState.ANALYSIS:
            assert artifact is not None
            response, written = sa.analyze(artifact, round=fsm.clarify_rounds + 1, group_id=group_id)
            if response.is_decision:
                adr = response.adr
                fsm.propose(TransitionProposal(
                    to_state=DLCState.DECISION, agent=_SA,
                    reason="requirements sufficient; ADR committed", confidence=0.9,
                ))
            else:
                pending = written
                fsm.propose(TransitionProposal(
                    to_state=DLCState.CLARIFICATION, agent=_SA,
                    reason=f"{len(written)} open question(s)", confidence=0.8,
                ))

        elif state is DLCState.CLARIFICATION:
            ba.answer(pending, group_id=group_id)
            pending = []
            fsm.propose(TransitionProposal(
                to_state=DLCState.ANALYSIS, agent=_BA,
                reason="clarifications answered", confidence=0.9,
            ))

        fsm.step()  # FSM executes (or rejects/forces) the proposal

    return LoopResult(
        final_state=fsm.state,
        artifact=artifact,
        adr=adr,
        clarify_rounds=fsm.clarify_rounds,
        escalated=fsm.state is DLCState.ESCALATION,
    )
