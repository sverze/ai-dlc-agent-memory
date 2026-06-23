"""Model-provider seam — one model hardcoded per role, router-ready for v2.

Agents never import a provider SDK directly; they call a :class:`ModelClient`.
v1 binds each role to a fixed model (BA → Gemini Flash, SA → Claude Sonnet); v2
swaps this for a LiteLLM-backed router behind the *same* interface, so agent code
never changes (decision D8 / FR12).

``FakeModelClient`` is the offline, deterministic implementation used by tests and
local development — no network, no keys, fully scriptable, and it records every
call for assertions. The real provider clients (``AnthropicModelClient``,
``GeminiModelClient``) live alongside it and import their SDKs lazily, so importing
this module never requires the provider packages — the offline path stays intact
with nothing installed. ``make_model_client`` wires the two into a single
persona-routing client that drops in wherever ``FakeModelClient`` was used.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from enum import StrEnum
from typing import Any

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

# Same two roles, but Vertex AI Model Garden model ids (D25). Both Gemini and Claude
# run under a single GCP project — one billing/governance/IAM plane, enterprise quotas.
# Vertex Claude ids may need a publisher/version suffix (e.g. ``claude-sonnet-4-5@20250929``)
# depending on the project's Model Garden; these are the configurable defaults.
DEFAULT_VERTEX_MODEL_BY_ROLE: dict[AgentPersona, str] = {
    AgentPersona.BUSINESS_ANALYST: "gemini-2.5-flash",
    AgentPersona.SOLUTION_ARCHITECT: "claude-sonnet-4-5",
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


def _strip_code_fence(text: str) -> str:
    """Unwrap a whole-response markdown code fence if present.

    Real models routinely wrap JSON in ```json … ``` even when asked for raw JSON.
    The seam carries no per-call format hint and the agents parse the returned text
    directly (``model_validate_json``), so the *client* normalizes this provider
    quirk into clean text — the right layer, leaving agents.py untouched. Only a
    fence enclosing the entire (stripped) response is removed; inline fences within
    prose are left alone. Provider-native JSON mode is deferred to v2, where a
    format hint on the seam lets each call opt in per turn (BA intake is JSON but
    BA clarification answers are free text, so it cannot be set blanket-on here).
    """
    s = text.strip()
    if not s.startswith("```"):
        return text
    lines = s.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


# --- Real provider clients -------------------------------------------------
#
# Both import their SDK *lazily* (inside __init__/complete), never at module top,
# so this module imports cleanly with nothing installed and the offline path is
# never coupled to the provider packages. Keys come from the environment and are
# never logged, stored, or placed in a ModelCall.

DEFAULT_MAX_TOKENS = 4096


class AnthropicModelClient(ModelClient):
    """Real ``ModelClient`` for Claude (the Solution Architect's bound model).

    Maps the seam's ``Message`` list to anthropic's messages array (system passed
    out-of-band via the ``system`` kwarg) and reports provider-supplied token usage.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: object | None = None,
        model_by_role: dict[AgentPersona, str] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        super().__init__(model_by_role)
        self.max_tokens = max_tokens
        self._client: Any
        if client is not None:
            self._client = client
        else:
            key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if not key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY not set — export it or pass api_key= "
                    "to AnthropicModelClient."
                )
            import anthropic  # lazy: offline import must not require the SDK

            self._client = anthropic.Anthropic(api_key=key)

    def complete(
        self,
        messages: Sequence[Message],
        *,
        persona: AgentPersona,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        model = self.model_for(persona)
        wire = [
            {"role": _ANTHROPIC_ROLE[m.role], "content": m.content}
            for m in messages
            if m.role is not MessageRole.SYSTEM
        ]
        kwargs: dict[str, object] = {
            "model": model,
            "max_tokens": self.max_tokens,
            "messages": wire,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        resp = self._client.messages.create(**kwargs)

        text = _strip_code_fence(
            "".join(
                block.text
                for block in resp.content
                if getattr(block, "type", None) == "text"
            )
        )
        usage = Usage(
            input_tokens=getattr(resp.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(resp.usage, "output_tokens", 0) or 0,
        )
        return ModelResponse(text=text, model=model, persona=persona, usage=usage)


class GeminiModelClient(ModelClient):
    """Real ``ModelClient`` for Gemini (the Business Analyst's bound model).

    Uses the unified ``google-genai`` SDK. The system prompt rides the config's
    ``system_instruction`` slot; ``ASSISTANT`` turns map to Gemini's ``model`` role.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: object | None = None,
        model_by_role: dict[AgentPersona, str] | None = None,
    ) -> None:
        super().__init__(model_by_role)
        self._client: Any
        if client is not None:
            self._client = client
        else:
            key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not key:
                raise RuntimeError(
                    "GEMINI_API_KEY (or GOOGLE_API_KEY) not set — export it or pass "
                    "api_key= to GeminiModelClient."
                )
            from google import genai  # lazy: offline import must not require the SDK

            self._client = genai.Client(api_key=key)

    def complete(
        self,
        messages: Sequence[Message],
        *,
        persona: AgentPersona,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        from google.genai import types  # lazy

        model = self.model_for(persona)
        contents = [
            types.Content(
                role=_GEMINI_ROLE[m.role],
                parts=[types.Part(text=m.content)],
            )
            for m in messages
            if m.role is not MessageRole.SYSTEM
        ]
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=temperature,
        )
        resp = self._client.models.generate_content(
            model=model, contents=contents, config=config
        )

        meta = getattr(resp, "usage_metadata", None)
        usage = Usage(
            input_tokens=getattr(meta, "prompt_token_count", 0) or 0,
            output_tokens=getattr(meta, "candidates_token_count", 0) or 0,
        )
        return ModelResponse(
            text=_strip_code_fence(resp.text or ""),
            model=model,
            persona=persona,
            usage=usage,
        )


# Seam role (MessageRole) → provider wire role.
_ANTHROPIC_ROLE: dict[MessageRole, str] = {
    MessageRole.USER: "user",
    MessageRole.ASSISTANT: "assistant",
}
_GEMINI_ROLE: dict[MessageRole, str] = {
    MessageRole.USER: "user",
    MessageRole.ASSISTANT: "model",
}


# --- Vertex AI Model Garden clients (D25) ----------------------------------
#
# The enterprise target standardizes on Vertex AI, so both providers route through
# one GCP project. These reuse the parent clients' wire-mapping and usage handling
# *unchanged* — the ONLY difference is how the SDK client is constructed (Vertex
# auth via project/region, not a raw API key). Tests inject ``client=`` to exercise
# the inherited ``complete()`` offline; the SDK import stays lazy, so the offline
# path never requires the vertex extra. Credentials come from Application Default
# Credentials (gcloud auth / a service account) — never an API key in code.


def _vertex_project(project_id: str | None) -> str:
    project = (
        project_id
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("VERTEX_PROJECT_ID")
        or ""
    )
    if not project:
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT (or VERTEX_PROJECT_ID) not set — export it or pass "
            "project_id= ; Vertex auth uses Application Default Credentials "
            "(run `gcloud auth application-default login` or set a service account)."
        )
    return project


class VertexAnthropicModelClient(AnthropicModelClient):
    """Claude via Vertex AI Model Garden (``anthropic.AnthropicVertex``).

    Inherits ``complete()`` from :class:`AnthropicModelClient` verbatim — AnthropicVertex
    exposes the same ``messages.create`` surface — so only construction differs.
    """

    def __init__(
        self,
        *,
        project_id: str | None = None,
        region: str | None = None,
        client: object | None = None,
        model_by_role: dict[AgentPersona, str] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        if client is None:
            project = _vertex_project(project_id)
            region = region or os.getenv("VERTEX_REGION") or os.getenv("CLOUD_ML_REGION") or "us-east5"
            from anthropic import AnthropicVertex  # lazy: offline import must not require the SDK

            client = AnthropicVertex(project_id=project, region=region)
        super().__init__(
            client=client,
            model_by_role=model_by_role or DEFAULT_VERTEX_MODEL_BY_ROLE,
            max_tokens=max_tokens,
        )


class VertexGeminiModelClient(GeminiModelClient):
    """Gemini via Vertex AI (``google-genai`` in Vertex mode).

    Inherits ``complete()`` from :class:`GeminiModelClient` verbatim — the genai client
    in Vertex mode exposes the same ``models.generate_content`` surface.
    """

    def __init__(
        self,
        *,
        project_id: str | None = None,
        location: str | None = None,
        client: object | None = None,
        model_by_role: dict[AgentPersona, str] | None = None,
    ) -> None:
        if client is None:
            project = _vertex_project(project_id)
            location = (
                location
                or os.getenv("VERTEX_LOCATION")
                or os.getenv("GOOGLE_CLOUD_LOCATION")
                or "us-central1"
            )
            from google import genai  # lazy: offline import must not require the SDK

            client = genai.Client(vertexai=True, project=project, location=location)
        super().__init__(
            client=client,
            model_by_role=model_by_role or DEFAULT_VERTEX_MODEL_BY_ROLE,
        )


class RoutingModelClient(ModelClient):
    """Routes each persona to its own real client — the drop-in for ``FakeModelClient``.

    v1 keeps one model hardcoded per role (D8); this routes the *client* per role too,
    so the BA's calls hit Gemini and the SA's hit Claude through a single object that
    agents and ``run_loop`` use exactly like the fake.
    """

    def __init__(self, by_persona: dict[AgentPersona, ModelClient]) -> None:
        # Inherit a model map for model_for() introspection; routing is by persona.
        super().__init__()
        self._by_persona = dict(by_persona)

    def _client_for(self, persona: AgentPersona) -> ModelClient:
        try:
            return self._by_persona[persona]
        except KeyError:
            raise ValueError(f"no client routed for role {persona}") from None

    def model_for(self, persona: AgentPersona) -> str:
        return self._client_for(persona).model_for(persona)

    def complete(
        self,
        messages: Sequence[Message],
        *,
        persona: AgentPersona,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        return self._client_for(persona).complete(
            messages, persona=persona, system=system, temperature=temperature
        )


def make_vertex_model_client(
    *,
    project_id: str | None = None,
    region: str | None = None,
    location: str | None = None,
    model_by_role: dict[AgentPersona, str] | None = None,
) -> ModelClient:
    """Build the Vertex-backed persona-routing client: BA → Gemini, SA → Claude (D25).

    Both providers run under one GCP project via Vertex AI Model Garden — unified
    billing/IAM/data-residency and enterprise quotas (no consumer free-tier 503s).
    Auth is Application Default Credentials; no API keys. Raises a clear ``RuntimeError``
    naming the missing project var if GCP config is absent. Drop-in for the direct client.
    """
    merged = {**DEFAULT_VERTEX_MODEL_BY_ROLE, **(model_by_role or {})}
    return RoutingModelClient(
        {
            AgentPersona.BUSINESS_ANALYST: VertexGeminiModelClient(
                project_id=project_id, location=location, model_by_role=merged
            ),
            AgentPersona.SOLUTION_ARCHITECT: VertexAnthropicModelClient(
                project_id=project_id, region=region, model_by_role=merged
            ),
        }
    )


def make_model_client(
    *,
    provider: str | None = None,
    anthropic_key: str | None = None,
    gemini_key: str | None = None,
    model_by_role: dict[AgentPersona, str] | None = None,
) -> ModelClient:
    """Build the real persona-routing client: BA → Gemini, SA → Anthropic.

    ``provider`` selects the backend (defaults to env ``MODEL_PROVIDER`` then ``"direct"``):
      - ``"direct"`` — consumer API keys (``ANTHROPIC_API_KEY`` / ``GEMINI_API_KEY``).
      - ``"vertex"`` — both models via Vertex AI Model Garden under one GCP project (D25);
        delegates to :func:`make_vertex_model_client` (keys args are ignored).

    Reads keys/config from the environment unless passed explicitly. Raises a clear
    ``RuntimeError`` (via the sub-clients) if a required key/var is missing — the
    drop-in replacement for ``FakeModelClient()`` in a real run.

    ``model_by_role`` overrides the per-role model defaults (merged, so a partial
    override keeps the other role's binding) — useful when a free-tier per-model
    daily quota is exhausted (e.g. swap the BA to ``gemini-2.5-flash-lite``, which
    draws from a separate quota bucket).
    """
    provider = (provider or os.getenv("MODEL_PROVIDER") or "direct").lower()
    if provider == "vertex":
        return make_vertex_model_client(model_by_role=model_by_role)
    if provider != "direct":
        raise ValueError(f"unknown model provider {provider!r} (expected 'direct' or 'vertex')")

    merged = {**DEFAULT_MODEL_BY_ROLE, **(model_by_role or {})}
    return RoutingModelClient(
        {
            AgentPersona.BUSINESS_ANALYST: GeminiModelClient(
                api_key=gemini_key, model_by_role=merged
            ),
            AgentPersona.SOLUTION_ARCHITECT: AnthropicModelClient(
                api_key=anthropic_key, model_by_role=merged
            ),
        }
    )
