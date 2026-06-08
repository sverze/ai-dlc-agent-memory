"""Tests for the FSM orchestrator."""

from agentic_memory import (
    DLCState,
    EventLog,
    FSM,
    TransitionProposal,
    replay_final_state,
)

BA = "business-analyst"
SA = "solution-architect"


def _fsm(tmp_path, **kw) -> FSM:
    return FSM(EventLog(tmp_path / "events.jsonl"), **kw)


def _prop(state: DLCState, agent: str = SA, reason: str = "ok", conf: float = 0.9):
    return TransitionProposal(to_state=state, agent=agent, reason=reason, confidence=conf)


def test_happy_path_intake_to_decision(tmp_path):
    fsm = _fsm(tmp_path)
    fsm.propose(_prop(DLCState.ANALYSIS, agent=BA))
    fsm.propose(_prop(DLCState.DECISION))
    results = fsm.run()

    assert [r.executed for r in results] == [True, True]
    assert fsm.state is DLCState.DECISION
    assert fsm.is_terminal()


def test_clarification_loop(tmp_path):
    fsm = _fsm(tmp_path)
    fsm.propose(_prop(DLCState.ANALYSIS, agent=BA))
    fsm.propose(_prop(DLCState.CLARIFICATION))     # SA has questions
    fsm.propose(_prop(DLCState.ANALYSIS, agent=BA))  # BA answered
    fsm.propose(_prop(DLCState.DECISION))
    fsm.run()

    assert fsm.state is DLCState.DECISION
    assert fsm.clarify_rounds == 1


def test_illegal_transition_is_rejected(tmp_path):
    fsm = _fsm(tmp_path)
    fsm.propose(_prop(DLCState.DECISION))  # intake -> decision is illegal
    result = fsm.step()

    assert result is not None
    assert result.executed is False
    assert "illegal transition" in result.rejection_reason
    assert fsm.state is DLCState.INTAKE


def test_clarify_cap_forces_escalation(tmp_path):
    fsm = _fsm(tmp_path, max_clarify_rounds=2)
    fsm.propose(_prop(DLCState.ANALYSIS, agent=BA))
    # Two legitimate clarification rounds.
    for _ in range(2):
        fsm.propose(_prop(DLCState.CLARIFICATION))
        fsm.propose(_prop(DLCState.ANALYSIS, agent=BA))
    # Third clarification attempt should be overridden to escalation.
    fsm.propose(_prop(DLCState.CLARIFICATION))
    results = fsm.run()

    last = results[-1]
    assert last.forced is True
    assert last.to_state is DLCState.ESCALATION
    assert fsm.state is DLCState.ESCALATION
    assert fsm.is_terminal()


def test_no_transitions_after_terminal(tmp_path):
    fsm = _fsm(tmp_path)
    fsm.propose(_prop(DLCState.ANALYSIS, agent=BA))
    fsm.propose(_prop(DLCState.DECISION))
    fsm.run()

    # Queue another proposal after reaching a terminal state.
    fsm.propose(_prop(DLCState.ANALYSIS))
    result = fsm.step()
    assert result.executed is False
    assert "terminal" in result.rejection_reason


def test_replay_reconstructs_final_state(tmp_path):
    path = tmp_path / "events.jsonl"
    fsm = FSM(EventLog(path))
    fsm.propose(_prop(DLCState.ANALYSIS, agent=BA))
    fsm.propose(_prop(DLCState.CLARIFICATION))
    fsm.propose(_prop(DLCState.ANALYSIS, agent=BA))
    fsm.propose(_prop(DLCState.DECISION))
    fsm.run()

    # A fresh reader of the log alone must arrive at the same final state.
    replayed = replay_final_state(EventLog(path))
    assert replayed == fsm.state == DLCState.DECISION
