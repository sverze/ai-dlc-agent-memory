"""LangfuseTracer with an injected mock client — gated behind `-m observability`.

Asserts the production tracer maps onto the Langfuse v4 API correctly (observation
type, model, usage_details, flush) without a real Langfuse server. The mock mimics the
``start_as_current_observation`` context-manager → span-with-.update() shape.
"""

import pytest

pytest.importorskip("langfuse", reason="observability extra not installed")

from agentic_memory import (  # noqa: E402
    AgentPersona,
    FakeModelClient,
    LangfuseTracer,
    Message,
    MessageRole,
    TracingModelClient,
)

pytestmark = pytest.mark.observability


class _MockSpan:
    def __init__(self, store):
        self._store = store

    def update(self, **kwargs):
        self._store.update(kwargs)


class _MockObservationCM:
    def __init__(self, store):
        self._store = store

    def __enter__(self):
        return _MockSpan(self._store)

    def __exit__(self, *exc):
        return False


class MockLangfuse:
    def __init__(self, auth=True):
        self.observations = []
        self.flushed = 0
        self._auth = auth

    def start_as_current_observation(self, **kwargs):
        record = dict(kwargs)
        self.observations.append(record)
        return _MockObservationCM(record)

    def flush(self):
        self.flushed += 1

    def auth_check(self):
        return self._auth


def test_langfuse_tracer_emits_generation_with_model_and_usage():
    mock = MockLangfuse()
    tracer = LangfuseTracer(client=mock)
    traced = TracingModelClient(FakeModelClient("answer"), tracer)

    with tracer.run(name="dlc-run:SCRUM-1", ticket_id="SCRUM-1"):
        traced.complete(
            [Message(role=MessageRole.USER, content="extract")],
            persona=AgentPersona.BUSINESS_ANALYST,
        )
    tracer.flush()

    # one run (chain) + one generation
    types = [o.get("as_type") for o in mock.observations]
    assert "chain" in types
    gen = next(o for o in mock.observations if o.get("as_type") == "generation")
    assert gen["model"] == "gemini-2.5-flash"
    assert gen["metadata"]["persona"] == "business-analyst"
    # usage written back via span.update(usage_details=...)
    assert gen["output"] == "answer"
    assert gen["usage_details"] == {"input": gen["usage_details"]["input"], "output": gen["usage_details"]["output"]}
    assert gen["usage_details"]["output"] >= 1
    assert mock.flushed == 1


def test_verify_reflects_auth_check():
    assert LangfuseTracer(client=MockLangfuse(auth=True)).verify() is True
    assert LangfuseTracer(client=MockLangfuse(auth=False)).verify() is False
