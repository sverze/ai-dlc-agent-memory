"""Append-only event log — the ground truth for the prototype.

Every meaningful action (FSM transition, agent write, validation, escalation,
tool call) is appended as one JSON line. The log is never rewritten; state is
reconstructed by replaying it. This is what makes runs auditable and replayable
(spec NFR1, and the success criterion "event logs replay to identical state").
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EventType(StrEnum):
    FSM_TRANSITION = "fsm_transition"
    AGENT_WRITE = "agent_write"
    VALIDATION = "validation"
    ESCALATION = "escalation"
    TOOL_CALL = "tool_call"


class StateChange(BaseModel):
    # ``from`` is a reserved word; expose it via alias, keep a clean attribute.
    model_config = ConfigDict(populate_by_name=True)

    from_state: str = Field(alias="from")
    to_state: str = Field(alias="to")


class EventLogEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    seq: int                       # monotonic, never reused
    type: EventType
    timestamp: datetime = Field(default_factory=_utcnow)
    agent: str | None = None
    state: StateChange | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


State = TypeVar("State")


class EventLog:
    """Append-only JSONL event log with monotonic sequence numbers."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._next_seq = 0
        if self.path.exists():
            # Continue the sequence across restarts; never reuse a seq.
            last = -1
            for entry in self.iter_entries():
                last = max(last, entry.seq)
            self._next_seq = last + 1
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        type: EventType,
        payload: dict[str, Any] | None = None,
        *,
        agent: str | None = None,
        state: StateChange | None = None,
    ) -> EventLogEntry:
        entry = EventLogEntry(
            seq=self._next_seq,
            type=type,
            agent=agent,
            state=state,
            payload=payload or {},
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json(by_alias=True) + "\n")
        self._next_seq += 1
        return entry

    def read_all(self) -> list[EventLogEntry]:
        return list(self.iter_entries())

    def iter_entries(self) -> Iterator[EventLogEntry]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield EventLogEntry.model_validate_json(line)

    def replay(
        self, apply: Callable[[State, EventLogEntry], State], initial: State
    ) -> State:
        """Fold the log into a final state with a pure reducer."""
        state = initial
        for entry in self.iter_entries():
            state = apply(state, entry)
        return state
