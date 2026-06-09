"""Collective agentic memory for AI DLC — V1 prototype.

Stage 1 (substrate): typed artifacts, append-only event log, FSM core.
"""

from .artifacts import (
    ADR,
    AcceptanceCriterion,
    AddedConstraint,
    ADRStatus,
    AgentPersona,
    DecisionOption,
    KnowledgeEntry,
    Priority,
    Requirement,
    RequirementsArtifact,
    RequirementTrace,
    new_id,
)
from .events import EventLog, EventLogEntry, EventType, StateChange
from .models import (
    DEFAULT_MODEL_BY_ROLE,
    FakeModelClient,
    Message,
    MessageRole,
    ModelCall,
    ModelClient,
    ModelResponse,
    Usage,
)
from .fsm import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    DLCState,
    FSM,
    TransitionProposal,
    TransitionResult,
    replay_final_state,
)

__all__ = [
    # artifacts
    "ADR",
    "AcceptanceCriterion",
    "AddedConstraint",
    "ADRStatus",
    "AgentPersona",
    "DecisionOption",
    "KnowledgeEntry",
    "Priority",
    "Requirement",
    "RequirementsArtifact",
    "RequirementTrace",
    "new_id",
    # events
    "EventLog",
    "EventLogEntry",
    "EventType",
    "StateChange",
    # models
    "DEFAULT_MODEL_BY_ROLE",
    "FakeModelClient",
    "Message",
    "MessageRole",
    "ModelCall",
    "ModelClient",
    "ModelResponse",
    "Usage",
    # fsm
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATES",
    "DLCState",
    "FSM",
    "TransitionProposal",
    "TransitionResult",
    "replay_final_state",
]
