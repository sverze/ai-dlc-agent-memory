"""BA and SA agents — the two personas of the V1 loop.

Each agent does exactly three things: build a prompt, call its bound model through the
``ModelClient`` seam, and parse the typed JSON response into our artifacts. Agents own their
own writes to shared memory; the FSM (driven by ``run_loop``) owns state transitions. With
``FakeModelClient`` + ``InMemoryMemoryStore`` the whole loop runs offline and deterministically
— no provider keys, no Graphiti service.

Model wire-contract (V1): the BA returns a ``RequirementsArtifact`` as JSON; the SA returns an
``SAResponse`` — either a list of clarifications, or a full ``ADR``. Real provider clients land
in Stage 2 behind the same ``ModelClient`` interface, so this code does not change.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .artifacts import ADR, AgentPersona, RequirementsArtifact
from .graph import DEFAULT_GROUP, MemoryStore
from .models import Message, MessageRole, ModelClient

BA_SYSTEM = (
    "You are a Business Analyst. Read the delivery ticket and extract structured, "
    "attributed requirements as JSON matching the RequirementsArtifact schema. "
    "Tag key facts. Flag ambiguities as open questions."
)
SA_SYSTEM = (
    "You are a Solution Architect. Read the requirements from shared memory. If any are "
    "underspecified, return clarifications. Otherwise return an ADR with a requirement_trace "
    "for every requirement (addressed or explicitly deferred) and justified added constraints."
)


class ClarificationRequest(BaseModel):
    requirement_id: str
    question: str


class SAResponse(BaseModel):
    """The SA model's structured output: clarify, or decide with an ADR."""

    clarifications: list[ClarificationRequest] = Field(default_factory=list)
    adr: ADR | None = None

    @property
    def is_decision(self) -> bool:
        return self.adr is not None


class TicketInput(BaseModel):
    """A delivery ticket as the BA receives it (stand-in for the JIRA adapter output)."""

    id: str
    body: str


class Agent:
    """Common wiring: a persona, its model client, and the shared store."""

    persona: AgentPersona
    system: str

    def __init__(self, model: ModelClient, store: MemoryStore) -> None:
        self.model = model
        self.store = store

    def _ask(self, prompt: str) -> str:
        resp = self.model.complete(
            [Message(role=MessageRole.USER, content=prompt)],
            persona=self.persona,
            system=self.system,
        )
        return resp.text


class BAAgent(Agent):
    persona = AgentPersona.BUSINESS_ANALYST
    system = BA_SYSTEM

    def intake(self, ticket: TicketInput, *, group_id: str = DEFAULT_GROUP) -> RequirementsArtifact:
        """Ticket → RequirementsArtifact → shared memory."""
        text = self._ask(f"Ticket {ticket.id}:\n{ticket.body}\n\nReturn RequirementsArtifact JSON.")
        artifact = RequirementsArtifact.model_validate_json(text)
        # The model shouldn't invent the source id; bind it to the real ticket.
        artifact = artifact.model_copy(update={"source_ticket_id": ticket.id})
        self.store.write_requirements(artifact, group_id=group_id)
        return artifact

    def answer(
        self,
        clarifications: list[tuple[str, ClarificationRequest]],
        *,
        group_id: str = DEFAULT_GROUP,
    ) -> None:
        """Answer each open clarification and write the answer back to memory."""
        for clar_id, req in clarifications:
            answer = self._ask(f"Answer this clarification about {req.requirement_id}: {req.question}")
            self.store.answer_clarification(
                clar_id, answer=answer, requirement_id=req.requirement_id, answerer=self.persona,
                group_id=group_id,
            )


class SAAgent(Agent):
    persona = AgentPersona.SOLUTION_ARCHITECT
    system = SA_SYSTEM

    def analyze(
        self, artifact: RequirementsArtifact, *, round: int, group_id: str = DEFAULT_GROUP
    ) -> tuple[SAResponse, list[tuple[str, ClarificationRequest]]]:
        """Read requirements → decide. Returns the parsed response and, if clarifying, the
        list of (clarification_node_id, request) it wrote to memory."""
        reqs = self.store.requirements_for(artifact.source_ticket_id, group_id=group_id)
        summary = "; ".join(f"{r.id}: {r.attrs.get('text')}" for r in reqs)
        text = self._ask(f"Requirements: {summary}\n\nReturn SAResponse JSON (clarify or decide).")
        response = SAResponse.model_validate_json(text)

        written: list[tuple[str, ClarificationRequest]] = []
        if response.is_decision:
            assert response.adr is not None
            self.store.write_adr(response.adr, group_id=group_id)
            self.store.promote_canonical(response.adr.id, group_id=group_id)
        else:
            for req in response.clarifications:
                clar_id = self.store.write_clarification(
                    question=req.question, requirement_id=req.requirement_id,
                    asker=self.persona, round=round, group_id=group_id,
                )
                written.append((clar_id, req))
        return response, written
