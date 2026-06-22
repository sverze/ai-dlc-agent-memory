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
from .agents import (
    Agent,
    BAAgent,
    ClarificationRequest,
    SAAgent,
    SAResponse,
    TicketInput,
)
from .events import EventLog, EventLogEntry, EventType, StateChange
from .loop import LoopResult, run_loop
from .graph import (
    DEFAULT_GROUP,
    EdgeType,
    GraphEdge,
    GraphNode,
    InMemoryMemoryStore,
    MemoryStore,
    NodeType,
)
from .graphiti_store import GraphitiMemoryStore, make_memory_store
from .tickets import InMemoryTicketSource, JiraTicketSource, TicketSource, adf_to_text
from .publish import (
    AtlassianPublisher,
    InMemoryPublisher,
    Publisher,
    adr_page_title,
    make_publisher,
    render_adr_html,
    render_requirements_adf,
)
from .observability import (
    GenerationSpan,
    LangfuseTracer,
    NullTracer,
    Tracer,
    TracingModelClient,
    make_tracer,
)
from .scenarios import (
    Scenario,
    ScenarioSet,
    ScenarioTicketSource,
    load_scenarios,
    parse_scenario,
)
from .verdicts import (
    FileVerdictStore,
    GateReadout,
    InMemoryVerdictStore,
    Verdict,
    VerdictDecision,
    VerdictStore,
    load_verdicts,
    parse_verdict,
    summarize_verdicts,
    wilson_lower_bound,
)
from .eval import (
    EvalReport,
    JudgeAgreement,
    JudgeVerdict,
    TraceabilityScore,
    build_eval_report,
    cohens_kappa,
    judge_adr,
    judge_agreement,
    kappa_band,
    score_traceability,
)
from .runs import RunRecord, load_runs, run_exists, save_run
from .models import (
    DEFAULT_MODEL_BY_ROLE,
    AnthropicModelClient,
    FakeModelClient,
    GeminiModelClient,
    Message,
    MessageRole,
    ModelCall,
    ModelClient,
    ModelResponse,
    RoutingModelClient,
    Usage,
    make_model_client,
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
    # agents + loop
    "Agent",
    "BAAgent",
    "SAAgent",
    "ClarificationRequest",
    "SAResponse",
    "TicketInput",
    "LoopResult",
    "run_loop",
    # tickets (ToolAdapter seam)
    "InMemoryTicketSource",
    "JiraTicketSource",
    "TicketSource",
    "adf_to_text",
    # publish (human-review surface)
    "AtlassianPublisher",
    "InMemoryPublisher",
    "Publisher",
    "adr_page_title",
    "make_publisher",
    "render_adr_html",
    "render_requirements_adf",
    # observability (Langfuse tracing)
    "GenerationSpan",
    "LangfuseTracer",
    "NullTracer",
    "Tracer",
    "TracingModelClient",
    "make_tracer",
    # scenarios (frozen gate corpus)
    "Scenario",
    "ScenarioSet",
    "ScenarioTicketSource",
    "load_scenarios",
    "parse_scenario",
    # verdicts (human gate signal)
    "FileVerdictStore",
    "GateReadout",
    "InMemoryVerdictStore",
    "Verdict",
    "VerdictDecision",
    "VerdictStore",
    "load_verdicts",
    "parse_verdict",
    "summarize_verdicts",
    "wilson_lower_bound",
    # eval (advisory machine metrics)
    "EvalReport",
    "JudgeAgreement",
    "JudgeVerdict",
    "TraceabilityScore",
    "build_eval_report",
    "cohens_kappa",
    "judge_adr",
    "judge_agreement",
    "kappa_band",
    "score_traceability",
    # runs (persisted loop output — decouples generate/eval)
    "RunRecord",
    "load_runs",
    "run_exists",
    "save_run",
    # graph (L4 shared memory)
    "DEFAULT_GROUP",
    "EdgeType",
    "GraphEdge",
    "GraphNode",
    "GraphitiMemoryStore",
    "InMemoryMemoryStore",
    "MemoryStore",
    "NodeType",
    "make_memory_store",
    # models
    "DEFAULT_MODEL_BY_ROLE",
    "AnthropicModelClient",
    "FakeModelClient",
    "GeminiModelClient",
    "Message",
    "MessageRole",
    "ModelCall",
    "ModelClient",
    "ModelResponse",
    "RoutingModelClient",
    "Usage",
    "make_model_client",
    # fsm
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATES",
    "DLCState",
    "FSM",
    "TransitionProposal",
    "TransitionResult",
    "replay_final_state",
]
