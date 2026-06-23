"""Vertex AI Model Garden clients (D25) — offline.

Both Vertex clients reuse their parent's wire-mapping/usage logic unchanged; only
SDK construction differs. So we exercise the inherited ``complete()`` via an injected
fake SDK client (no network, no vertex extra) and prove the construction error paths
fire before any SDK import — keeping these in the default free suite.
"""

from types import SimpleNamespace

import pytest

from agentic_memory import (
    AgentPersona,
    Message,
    MessageRole,
    VertexAnthropicModelClient,
    VertexGeminiModelClient,
    make_model_client,
    make_vertex_model_client,
)

_PROJECT_VARS = ("GOOGLE_CLOUD_PROJECT", "VERTEX_PROJECT_ID")


def _user(text: str) -> Message:
    return Message(role=MessageRole.USER, content=text)


class _FakeAnthropicVertex:
    """Mimics anthropic's client surface: ``.messages.create(**kwargs)`` → response."""

    def __init__(self, text: str, *, in_tok: int = 11, out_tok: int = 7) -> None:
        self._text, self._in, self._out = text, in_tok, out_tok
        self.seen: dict = {}
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.seen = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self._text)],
            usage=SimpleNamespace(input_tokens=self._in, output_tokens=self._out),
        )


def test_vertex_anthropic_complete_maps_strips_fence_and_reports_usage():
    fake = _FakeAnthropicVertex('```json\n{"adr": "x"}\n```')
    client = VertexAnthropicModelClient(client=fake)

    resp = client.complete(
        [_user("draft an ADR")],
        persona=AgentPersona.SOLUTION_ARCHITECT,
        system="You are an architect.",
    )

    assert resp.text == '{"adr": "x"}'                       # whole-response fence stripped
    assert resp.model == "claude-sonnet-4-5"                 # Vertex SA default (D25)
    assert resp.persona is AgentPersona.SOLUTION_ARCHITECT
    assert resp.usage.input_tokens == 11 and resp.usage.output_tokens == 7
    assert fake.seen["model"] == "claude-sonnet-4-5"         # routed model id reached the SDK
    assert fake.seen["system"] == "You are an architect."    # system passed out-of-band


def test_vertex_anthropic_uses_vertex_model_defaults():
    client = VertexAnthropicModelClient(client=_FakeAnthropicVertex("ok"))
    assert client.model_for(AgentPersona.SOLUTION_ARCHITECT) == "claude-sonnet-4-5"


def test_vertex_anthropic_missing_project_raises(monkeypatch):
    for var in _PROJECT_VARS:
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
        VertexAnthropicModelClient()  # no client injected → resolves project first, raises


def test_vertex_gemini_missing_project_raises(monkeypatch):
    for var in _PROJECT_VARS:
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
        VertexGeminiModelClient()


def test_make_model_client_vertex_requires_project(monkeypatch):
    for var in _PROJECT_VARS:
        monkeypatch.delenv(var, raising=False)
    # provider switch reaches the Vertex factory, which fails fast on missing GCP config
    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
        make_model_client(provider="vertex")


def test_make_vertex_model_client_requires_project(monkeypatch):
    for var in _PROJECT_VARS:
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
        make_vertex_model_client()


def test_make_model_client_unknown_provider_raises():
    with pytest.raises(ValueError, match="unknown model provider"):
        make_model_client(provider="bogus")


def test_make_model_client_provider_from_env(monkeypatch):
    for var in _PROJECT_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MODEL_PROVIDER", "vertex")
    # env-selected vertex provider still routes through the vertex factory (then fails on project)
    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
        make_model_client()


def test_vertex_clients_inherit_matching_backend_complete():
    """Each Vertex client reuses its OWN backend's complete() — they are NOT a shared
    method against one SDK shape. Anthropic-Vertex → messages.create; Gemini-Vertex →
    generate_content. This is the safety guarantee behind the subclass-reuse approach."""
    from agentic_memory.models import (
        AnthropicModelClient,
        GeminiModelClient,
    )

    assert VertexAnthropicModelClient.complete is AnthropicModelClient.complete
    assert VertexGeminiModelClient.complete is GeminiModelClient.complete
    # …and the two backends are genuinely different SDK surfaces, never conflated.
    assert AnthropicModelClient.complete is not GeminiModelClient.complete


def test_vertex_model_ids_overridable_by_env(monkeypatch):
    """`.env` drives model selection: defaults < VERTEX_*_MODEL env < explicit arg."""
    from agentic_memory.models import _vertex_models

    monkeypatch.setenv("VERTEX_SA_MODEL", "claude-opus-4-8")
    monkeypatch.delenv("VERTEX_BA_MODEL", raising=False)
    resolved = _vertex_models(None)
    assert resolved[AgentPersona.SOLUTION_ARCHITECT] == "claude-opus-4-8"  # env override
    assert resolved[AgentPersona.BUSINESS_ANALYST] == "gemini-2.5-flash"   # default kept

    # an explicit per-call arg still wins over the env override
    explicit = _vertex_models({AgentPersona.SOLUTION_ARCHITECT: "claude-sonnet-4-5"})
    assert explicit[AgentPersona.SOLUTION_ARCHITECT] == "claude-sonnet-4-5"


def test_vertex_region_defaults_split_by_backend(monkeypatch):
    """Claude-on-Vertex is region-gated (us-east5), Gemini lives elsewhere (us-central1).
    The defaults must differ per backend — a shared region would 404 one provider."""
    for var in (*_PROJECT_VARS, "VERTEX_REGION", "CLOUD_ML_REGION", "VERTEX_LOCATION", "GOOGLE_CLOUD_LOCATION"):
        monkeypatch.delenv(var, raising=False)
    import inspect

    import agentic_memory.models as m

    src = inspect.getsource(m)
    assert '"us-east5"' in src      # Anthropic/Claude default region
    assert '"us-central1"' in src   # Gemini default location
