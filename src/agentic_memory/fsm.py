"""Deterministic finite-state machine orchestrator.

Per the council ruling, the orchestrator is an FSM, not an agent: agents
*propose* transitions, the FSM is the sole executor. States and transitions are
enumerable, every transition is logged, and the final state can be reconstructed
by replaying the event log.

States::

    intake -> analysis <-> clarification -> decision   (+ escalation)

The analysis<->clarification loop models the real BA<->SA negotiation. A cap
(``max_clarify_rounds``) forces escalation rather than looping forever — and a
forced escalation is itself a finding worth capturing.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from .events import EventLog, EventType, StateChange


class DLCState(StrEnum):
    INTAKE = "intake"
    ANALYSIS = "analysis"
    CLARIFICATION = "clarification"
    DECISION = "decision"
    ESCALATION = "escalation"


TERMINAL_STATES: frozenset[DLCState] = frozenset(
    {DLCState.DECISION, DLCState.ESCALATION}
)

# Whitelist of legal transitions. Anything not listed is rejected.
ALLOWED_TRANSITIONS: dict[DLCState, frozenset[DLCState]] = {
    DLCState.INTAKE: frozenset({DLCState.ANALYSIS, DLCState.ESCALATION}),
    DLCState.ANALYSIS: frozenset(
        {DLCState.CLARIFICATION, DLCState.DECISION, DLCState.ESCALATION}
    ),
    DLCState.CLARIFICATION: frozenset({DLCState.ANALYSIS, DLCState.ESCALATION}),
    DLCState.DECISION: frozenset(),
    DLCState.ESCALATION: frozenset(),
}


class TransitionProposal(BaseModel):
    """An agent's suggestion to move the machine. The FSM decides."""

    to_state: DLCState
    agent: str
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class TransitionResult(BaseModel):
    executed: bool
    from_state: DLCState
    to_state: DLCState            # resulting state (== from_state if rejected)
    proposed_state: DLCState
    forced: bool = False          # FSM overrode the proposal (e.g. clarify cap)
    rejection_reason: str | None = None


class FSM:
    """The sole executor of state transitions. Agents propose; this decides."""

    def __init__(
        self,
        event_log: EventLog,
        *,
        max_clarify_rounds: int = 3,
        start: DLCState = DLCState.INTAKE,
    ) -> None:
        self.event_log = event_log
        self.max_clarify_rounds = max_clarify_rounds
        self.state = start
        self.clarify_rounds = 0
        self._queue: list[TransitionProposal] = []

    # -- proposals --------------------------------------------------------

    def propose(self, proposal: TransitionProposal) -> None:
        """Enqueue a proposal. Agents call this; the FSM executes via step()."""
        self._queue.append(proposal)

    def pending(self) -> int:
        return len(self._queue)

    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    # -- execution --------------------------------------------------------

    def step(self) -> TransitionResult | None:
        """Process the next queued proposal. Returns None if the queue is empty."""
        if not self._queue:
            return None
        return self._handle(self._queue.pop(0))

    def run(self) -> list[TransitionResult]:
        """Drain the queue, stopping early if a terminal state is reached."""
        results: list[TransitionResult] = []
        while self._queue and not self.is_terminal():
            result = self.step()
            if result is not None:
                results.append(result)
        return results

    # -- internals --------------------------------------------------------

    def _handle(self, proposal: TransitionProposal) -> TransitionResult:
        if self.is_terminal():
            return self._reject(proposal, f"machine is terminal ({self.state})")

        target = proposal.to_state

        # Clarification cap: once rounds are exhausted, another clarification
        # proposal is overridden to escalation rather than looping forever.
        forced = False
        if (
            target == DLCState.CLARIFICATION
            and self.clarify_rounds >= self.max_clarify_rounds
        ):
            target = DLCState.ESCALATION
            forced = True

        if target not in ALLOWED_TRANSITIONS[self.state]:
            return self._reject(
                proposal, f"illegal transition {self.state} -> {target}"
            )

        return self._execute(proposal, target, forced)

    def _execute(
        self, proposal: TransitionProposal, target: DLCState, forced: bool
    ) -> TransitionResult:
        from_state = self.state
        if target == DLCState.CLARIFICATION:
            self.clarify_rounds += 1
        self.state = target

        event_type = (
            EventType.ESCALATION
            if target == DLCState.ESCALATION
            else EventType.FSM_TRANSITION
        )
        self.event_log.append(
            event_type,
            agent=proposal.agent,
            state=StateChange(from_state=from_state.value, to_state=target.value),
            payload={
                "reason": proposal.reason,
                "confidence": proposal.confidence,
                "proposed_state": proposal.to_state.value,
                "forced": forced,
                "clarify_rounds": self.clarify_rounds,
            },
        )
        return TransitionResult(
            executed=True,
            from_state=from_state,
            to_state=target,
            proposed_state=proposal.to_state,
            forced=forced,
        )

    def _reject(self, proposal: TransitionProposal, reason: str) -> TransitionResult:
        self.event_log.append(
            EventType.VALIDATION,
            agent=proposal.agent,
            payload={
                "rejected": True,
                "proposed_state": proposal.to_state.value,
                "current_state": self.state.value,
                "reason": reason,
            },
        )
        return TransitionResult(
            executed=False,
            from_state=self.state,
            to_state=self.state,
            proposed_state=proposal.to_state,
            rejection_reason=reason,
        )


def replay_final_state(
    event_log: EventLog, *, start: DLCState = DLCState.INTAKE
) -> DLCState:
    """Reconstruct the final FSM state purely from the event log.

    Used to verify determinism: running the machine and replaying its log must
    yield the same final state.
    """
    state = start
    for entry in event_log.iter_entries():
        if entry.state is not None and entry.type in (
            EventType.FSM_TRANSITION,
            EventType.ESCALATION,
        ):
            state = DLCState(entry.state.to_state)
    return state
