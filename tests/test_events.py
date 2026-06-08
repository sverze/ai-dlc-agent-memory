"""Tests for the append-only event log."""

from agentic_memory import EventLog, EventType, StateChange


def test_append_assigns_monotonic_seq(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    e0 = log.append(EventType.TOOL_CALL, {"tool": "jira"})
    e1 = log.append(EventType.AGENT_WRITE, {"node": "req-1"})
    e2 = log.append(EventType.VALIDATION, {"ok": True})
    assert [e0.seq, e1.seq, e2.seq] == [0, 1, 2]


def test_read_all_returns_entries_in_order(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    log.append(EventType.TOOL_CALL, {"i": 0})
    log.append(EventType.TOOL_CALL, {"i": 1})
    entries = log.read_all()
    assert [e.payload["i"] for e in entries] == [0, 1]


def test_seq_continues_across_reopen(tmp_path):
    path = tmp_path / "events.jsonl"
    first = EventLog(path)
    first.append(EventType.TOOL_CALL, {})
    first.append(EventType.TOOL_CALL, {})

    reopened = EventLog(path)  # must not reuse seq 0/1
    e = reopened.append(EventType.TOOL_CALL, {})
    assert e.seq == 2


def test_state_change_alias_roundtrip(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    log.append(
        EventType.FSM_TRANSITION,
        {"reason": "ready"},
        agent="business-analyst",
        state=StateChange(from_state="intake", to_state="analysis"),
    )
    raw = (tmp_path / "events.jsonl").read_text()
    assert '"from":"intake"' in raw
    assert '"to":"analysis"' in raw

    entry = log.read_all()[0]
    assert entry.state.from_state == "intake"
    assert entry.state.to_state == "analysis"


def test_replay_reducer(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    for _ in range(3):
        log.append(EventType.AGENT_WRITE, {})
    log.append(EventType.TOOL_CALL, {})

    writes = log.replay(
        lambda acc, e: acc + (1 if e.type == EventType.AGENT_WRITE else 0), 0
    )
    assert writes == 3
