"""Live smoke tests for the real provider clients.

These hit real APIs and cost money, so they are EXCLUDED from the default run
(`addopts = -q -m 'not live'`). Run them explicitly and only with keys present:

    uv run --extra live pytest -m live -s

Each test makes ONE minimal call and asserts the seam round-trips: non-empty text,
real (non-zero) token usage, and the persona's bound model id on the response.
"""

import os
import time

import pytest

from agentic_memory import (
    AgentPersona,
    AnthropicModelClient,
    BAAgent,
    EventLog,
    FSM,
    GeminiModelClient,
    InMemoryMemoryStore,
    Message,
    MessageRole,
    SAAgent,
    TERMINAL_STATES,
    TicketInput,
    make_model_client,
    run_loop,
)

pytestmark = pytest.mark.live

_HAVE_BOTH = bool(os.getenv("ANTHROPIC_API_KEY")) and bool(
    os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
)


def _user(text: str) -> Message:
    return Message(role=MessageRole.USER, content=text)


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set"
)
def test_anthropic_live_roundtrip():
    client = AnthropicModelClient(max_tokens=16)
    resp = client.complete(
        [_user("Reply with the single word: OK")],
        persona=AgentPersona.SOLUTION_ARCHITECT,
        system="You are a terse assistant.",
    )
    assert resp.text.strip() != ""
    assert resp.model == "claude-sonnet-4-6"
    assert resp.persona is AgentPersona.SOLUTION_ARCHITECT
    assert resp.usage.total_tokens > 0


@pytest.mark.skipif(
    not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
    reason="GEMINI_API_KEY/GOOGLE_API_KEY not set",
)
def test_gemini_live_roundtrip():
    client = GeminiModelClient()
    resp = client.complete(
        [_user("Reply with the single word: OK")],
        persona=AgentPersona.BUSINESS_ANALYST,
        system="You are a terse assistant.",
    )
    assert resp.text.strip() != ""
    assert resp.model == "gemini-2.5-flash"
    assert resp.persona is AgentPersona.BUSINESS_ANALYST
    assert resp.usage.total_tokens > 0


@pytest.mark.skipif(not _HAVE_BOTH, reason="need both ANTHROPIC and GEMINI keys")
def test_live_loop_reaches_terminal(tmp_path):
    """The point of Stage 2 going live: the SAME run_loop drives real Claude +
    Gemini to a terminal state with a real, schema-validated artifact and ADR.
    Green since schema injection (D14) — the prompts now carry the artifact JSON
    schemas derived from the Pydantic classes. Network-dependent; retries
    transient 5xx a couple of times."""
    client = make_model_client()
    store = InMemoryMemoryStore()
    ba = BAAgent(client, store)
    sa = SAAgent(client, store)
    fsm = FSM(EventLog(tmp_path / "events.jsonl"))
    ticket = TicketInput(
        id="JIRA-1",
        body=(
            "As a user I want to reset my password via email so I can regain "
            "access if I forget it."
        ),
    )

    last_exc = None
    for _ in range(3):
        try:
            result = run_loop(ticket, ba=ba, sa=sa, fsm=fsm)
            break
        except Exception as exc:  # transient provider 5xx / overload
            last_exc = exc
            if "503" in str(exc) or "UNAVAILABLE" in str(exc) or "overload" in str(exc).lower():
                time.sleep(3)
                continue
            raise
    else:
        pytest.skip(f"provider unavailable after retries: {last_exc}")

    assert result.final_state in TERMINAL_STATES
    assert result.artifact is not None
    assert len(result.artifact.requirements) >= 1
