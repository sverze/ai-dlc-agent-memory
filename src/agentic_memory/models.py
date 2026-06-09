"""Model-provider seam — one model hardcoded per role, router-ready for v2.

Agents never import a provider SDK directly; they call a :class:`ModelClient`.
v1 binds each role to a fixed model (BA → Gemini Flash, SA → Claude Sonnet); v2
swaps this for a LiteLLM-backed router behind the *same* interface, so agent code
never changes (decision D8 / FR12).

``FakeModelClient`` is the offline, deterministic implementation used by tests and
local development — no network, no keys, fully scriptable, and it records every
call for assertions. Real provider clients (anthropic, google-genai) land in
Stage 2 once keys and the agent code exist.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from enum import StrEnum

from pydantic import BaseModel, Field

from .artifacts import AgentPersona


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    role: MessageRole
    content: str


class Usage(BaseModel):
    """Token accounting for one model call — feeds the token-efficiency metric."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class ModelResponse(BaseModel):
    text: str
    model: str
    persona: AgentPersona
    usage: Usage = Field(default_factory=Usage)


# One model hardcoded per role (D8 / FR12). v2 replaces the map with a router.
DEFAULT_MODEL_BY_ROLE: dict[AgentPersona, str] = {
    AgentPersona.BUSINESS_ANALYST: "gemini-2.5-flash",
    AgentPersona.SOLUTION_ARCHITECT: "claude-sonnet-4-6",
}


class ModelClient(ABC):
    """The single seam agents call instead of a provider SDK.

    The interface is intentionally identical to what a v2 router will expose:
    given a persona, the client resolves the bound model and returns a response.
    """

    def __init__(self, model_by_role: dict[AgentPersona, str] | None = None) -> None:
        self.model_by_role = dict(model_by_role or DEFAULT_MODEL_BY_ROLE)

    def model_for(self, persona: AgentPersona) -> str:
        try:
            return self.model_by_role[persona]
        except KeyError:
            raise ValueError(f"no model bound for role {persona}") from None

    @abstractmethod
    def complete(
        self,
        messages: Sequence[Message],
        *,
        persona: AgentPersona,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Generate a completion for ``persona``'s bound model.

        ``system`` carries the static persona header in v1 — the reserved slot
        that v2 persona memory (Mem0) will populate dynamically (spec note on the
        persona interface slot).
        """
        ...


# A scripted handler: receives the call's messages + persona, returns the reply text.
ResponseHandler = Callable[[list[Message], AgentPersona], str]


class ModelCall(BaseModel):
    """A recorded invocation — what the fake client captures for assertions."""

    persona: AgentPersona
    model: str
    messages: list[Message]
    system: str | None = None
    temperature: float = 0.0


class FakeModelClient(ModelClient):
    """Deterministic, offline ``ModelClient`` for tests and local development.

    ``responses`` may be:
      - a single ``str`` — returned for every call,
      - a sequence of ``str`` — consumed in order (raises when exhausted),
      - a callable ``(messages, persona) -> str`` — computed per call.
    """

    def __init__(
        self,
        responses: str | Sequence[str] | ResponseHandler = "ok",
        *,
        model_by_role: dict[AgentPersona, str] | None = None,
    ) -> None:
        super().__init__(model_by_role)
        self.calls: list[ModelCall] = []
        if isinstance(responses, str):
            self._mode = "fixed"
            self._fixed = responses
        elif callable(responses):
            self._mode = "handler"
            self._handler: ResponseHandler = responses
        else:
            self._mode = "script"
            self._script: list[str] = list(responses)

    def complete(
        self,
        messages: Sequence[Message],
        *,
        persona: AgentPersona,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        model = self.model_for(persona)
        msgs = list(messages)

        if self._mode == "fixed":
            text = self._fixed
        elif self._mode == "handler":
            text = self._handler(msgs, persona)
        else:
            if not self._script:
                raise AssertionError("FakeModelClient script exhausted")
            text = self._script.pop(0)

        self.calls.append(
            ModelCall(
                persona=persona,
                model=model,
                messages=msgs,
                system=system,
                temperature=temperature,
            )
        )
        return ModelResponse(
            text=text,
            model=model,
            persona=persona,
            usage=_estimate_usage(system, msgs, text),
        )


def _estimate_usage(
    system: str | None, messages: Sequence[Message], output: str
) -> Usage:
    """Rough, deterministic token estimate (word count). Real clients report
    provider-supplied counts; this keeps the fake's metrics non-zero and stable."""
    parts = [system] if system else []
    parts.extend(m.content for m in messages)
    input_text = " ".join(parts)
    return Usage(input_tokens=_tok(input_text), output_tokens=_tok(output))


def _tok(text: str) -> int:
    return len(text.split())
