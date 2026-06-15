"""Observability seam — offline tests (no langfuse needed): pass-through, fault-swallow, null."""

from contextlib import contextmanager

from agentic_memory import (
    AgentPersona,
    FakeModelClient,
    GenerationSpan,
    Message,
    MessageRole,
    NullTracer,
    Tracer,
    TracingModelClient,
    make_tracer,
)


def _user(text: str) -> Message:
    return Message(role=MessageRole.USER, content=text)


class _RecordingSpan(GenerationSpan):
    def __init__(self) -> None:
        self.completed: tuple[str, int, int] | None = None

    def complete(self, text, *, input_tokens=0, output_tokens=0):
        self.completed = (text, input_tokens, output_tokens)


class RecordingTracer(Tracer):
    """Captures every generation opened — the offline stand-in for Langfuse."""

    def __init__(self) -> None:
        self.runs: list[str] = []
        self.generations: list[dict] = []
        self.spans: list[_RecordingSpan] = []
        self.flushed = 0

    @contextmanager
    def run(self, *, name, **attrs):
        self.runs.append(name)
        yield None

    @contextmanager
    def generation(self, *, name, model, persona, input_text):
        span = _RecordingSpan()
        self.generations.append(
            {"name": name, "model": model, "persona": persona, "input": input_text}
        )
        self.spans.append(span)
        yield span

    def flush(self):
        self.flushed += 1


def test_tracing_client_is_passthrough():
    inner = FakeModelClient("hello")
    traced = TracingModelClient(inner, RecordingTracer())
    resp = traced.complete([_user("hi")], persona=AgentPersona.SOLUTION_ARCHITECT)
    assert resp.text == "hello"
    assert resp.model == "claude-sonnet-4-6"
    assert resp.persona is AgentPersona.SOLUTION_ARCHITECT


def test_tracing_client_opens_a_generation_per_call_with_metadata():
    tracer = RecordingTracer()
    traced = TracingModelClient(FakeModelClient(["a", "b"]), tracer)
    traced.complete([_user("one")], persona=AgentPersona.BUSINESS_ANALYST)
    traced.complete([_user("two")], persona=AgentPersona.SOLUTION_ARCHITECT)

    assert len(tracer.generations) == 2
    g0 = tracer.generations[0]
    assert g0["persona"] == "business-analyst"
    assert g0["model"] == "gemini-2.5-flash"
    assert g0["input"] == "one"
    # usage recorded onto the span
    assert tracer.spans[0].completed is not None
    assert tracer.spans[0].completed[0] == "a"  # output text


def test_ba_and_sa_are_distinguishable():
    tracer = RecordingTracer()
    traced = TracingModelClient(FakeModelClient("x"), tracer)
    traced.complete([_user("q")], persona=AgentPersona.BUSINESS_ANALYST)
    traced.complete([_user("q")], persona=AgentPersona.SOLUTION_ARCHITECT)
    personas = {g["persona"] for g in tracer.generations}
    assert personas == {"business-analyst", "solution-architect"}


def test_model_for_delegates():
    traced = TracingModelClient(FakeModelClient(), RecordingTracer())
    assert traced.model_for(AgentPersona.BUSINESS_ANALYST) == "gemini-2.5-flash"


class _ExplodingTracer(Tracer):
    def run(self, *, name, **attrs):
        raise RuntimeError("tracer down")

    def generation(self, *, name, model, persona, input_text):
        raise RuntimeError("tracer down")


def test_tracer_fault_never_breaks_the_call():
    # The hard constraint: a broken tracer must not stop or alter the response.
    traced = TracingModelClient(FakeModelClient("still-works"), _ExplodingTracer())
    resp = traced.complete([_user("hi")], persona=AgentPersona.BUSINESS_ANALYST)
    assert resp.text == "still-works"


def test_null_tracer_context_managers_noop():
    tracer = NullTracer()
    with tracer.run(name="r"):
        with tracer.generation(name="g", model="m", persona="p", input_text="i") as span:
            span.complete("out", input_tokens=1, output_tokens=2)  # must not raise
    tracer.flush()


def test_make_tracer_is_null_without_keys(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert isinstance(make_tracer(), NullTracer)


def test_tracing_client_is_a_model_client():
    from agentic_memory import ModelClient
    assert isinstance(TracingModelClient(FakeModelClient()), ModelClient)
