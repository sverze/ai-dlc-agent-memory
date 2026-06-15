"""Observability seam — trace per-agent model calls into Langfuse (FR10).

Instrumentation is **strictly additive**: it wraps the ``ModelClient`` seam from the
outside (``TracingModelClient``) and opens a parent run span at the entry point, so
``agents.py`` / ``loop.py`` never change and a tracer fault can never alter or break a
run. With no Langfuse configured it is a silent no-op (``NullTracer``) and the offline
path needs nothing installed (D11).

Each model call becomes a Langfuse **generation** tagged with persona, model, token
usage, and latency — so the BA (Gemini) and SA (Claude) are comparable side by side,
and a future local model (Ollama, V2 router) would be observed for free through the
same wrapper.

Langfuse v4 API (pinned 2026-06-16): ``Langfuse(public_key, secret_key, host)`` +
``start_as_current_observation(name, as_type=..., model, input, usage_details, metadata)``
(OTel-context nesting) + ``.update(...)`` + ``.flush()``. The langfuse import is lazy.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from .artifacts import AgentPersona
from .models import Message, ModelClient, ModelResponse


class GenerationSpan(ABC):
    """Handle yielded inside a ``generation`` context — record the call's output."""

    @abstractmethod
    def complete(self, text: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None: ...


class Tracer(ABC):
    """The observability seam. Default behaviour (``NullTracer``) is to do nothing."""

    @abstractmethod
    def run(self, *, name: str, **attrs: Any) -> Any:
        """Context manager for a whole run — the parent span generations nest under."""
        ...

    @abstractmethod
    def generation(
        self, *, name: str, model: str, persona: str, input_text: str
    ) -> Any:
        """Context manager yielding a :class:`GenerationSpan` for one model call."""
        ...

    def flush(self) -> None:
        """Force any buffered spans out (no-op unless overridden)."""

    def verify(self) -> bool | None:
        """Check the backend actually accepts our credentials.

        Returns True/False for a real tracer, or None when there's nothing to verify
        (NullTracer). Lets callers confirm delivery instead of assuming it — "sent"
        without this is optimistic, because span export is async and faults are swallowed.
        """
        return None


class _NullSpan(GenerationSpan):
    def complete(self, text: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        pass


class NullTracer(Tracer):
    """The offline default — every operation is a no-op."""

    @contextmanager
    def run(self, *, name: str, **attrs: Any) -> Iterator[None]:
        yield None

    @contextmanager
    def generation(
        self, *, name: str, model: str, persona: str, input_text: str
    ) -> Iterator[GenerationSpan]:
        yield _NullSpan()


class _LangfuseSpan(GenerationSpan):
    def __init__(self, span: Any) -> None:
        self._span = span

    def complete(self, text: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        try:
            self._span.update(
                output=text,
                usage_details={"input": input_tokens, "output": output_tokens},
            )
        except Exception:
            pass  # observability must never break the loop


class LangfuseTracer(Tracer):
    """Real tracer. Emits a Langfuse generation per model call under a run span."""

    def __init__(self, client: Any | None = None) -> None:
        if client is not None:
            self._lf = client
        else:
            from langfuse import Langfuse  # lazy: offline import must not require langfuse

            self._lf = Langfuse(
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                host=os.getenv("LANGFUSE_HOST"),
            )

    @contextmanager
    def run(self, *, name: str, **attrs: Any) -> Iterator[None]:
        try:
            cm = self._lf.start_as_current_observation(
                name=name, as_type="chain", metadata=attrs
            )
        except Exception:
            yield None  # never let a tracer fault stop the run
            return
        with cm:
            yield None

    @contextmanager
    def generation(
        self, *, name: str, model: str, persona: str, input_text: str
    ) -> Iterator[GenerationSpan]:
        try:
            cm = self._lf.start_as_current_observation(
                name=name, as_type="generation", model=model,
                input=input_text, metadata={"persona": persona},
            )
        except Exception:
            yield _NullSpan()
            return
        with cm as span:
            yield _LangfuseSpan(span)

    def flush(self) -> None:
        try:
            self._lf.flush()
        except Exception:
            pass

    def verify(self) -> bool | None:
        # auth_check validates the keys against the configured host — the single
        # best signal for the classic "sent but empty UI" case (region/host/key mismatch).
        try:
            return bool(self._lf.auth_check())
        except Exception:
            return False


def make_tracer() -> Tracer:
    """Return a ``LangfuseTracer`` iff Langfuse keys are present, else ``NullTracer``.

    Never instantiates Langfuse keyless — no config means no-op, the offline default.
    """
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        return LangfuseTracer()
    return NullTracer()


class TracingModelClient(ModelClient):
    """Wraps any ``ModelClient`` and traces each ``complete`` as a generation.

    Pure pass-through: the inner response is returned unchanged; a tracer fault is
    swallowed so observation can never alter or break the call (the first-principles
    hard constraint). Drop-in wherever a ``ModelClient`` is expected.
    """

    def __init__(self, inner: ModelClient, tracer: Tracer | None = None) -> None:
        super().__init__(dict(inner.model_by_role))
        self._inner = inner
        self._tracer = tracer or NullTracer()

    def model_for(self, persona: AgentPersona) -> str:
        return self._inner.model_for(persona)

    def complete(
        self,
        messages: Sequence[Message],
        *,
        persona: AgentPersona,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        model = self._inner.model_for(persona)
        last = messages[-1].content if messages else ""
        try:
            cm = self._tracer.generation(
                name=f"{persona.value}.complete", model=model,
                persona=persona.value, input_text=last,
            )
        except Exception:
            return self._inner.complete(
                messages, persona=persona, system=system, temperature=temperature
            )
        with cm as span:
            resp = self._inner.complete(
                messages, persona=persona, system=system, temperature=temperature
            )
            try:
                span.complete(
                    resp.text,
                    input_tokens=resp.usage.input_tokens,
                    output_tokens=resp.usage.output_tokens,
                )
            except Exception:
                pass  # passthrough is sacred; recording is best-effort
            return resp
