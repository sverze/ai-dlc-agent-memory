"""Tests for the ModelClient seam and its offline fake."""

import pytest

from agentic_memory import (
    DEFAULT_MODEL_BY_ROLE,
    AgentPersona,
    FakeModelClient,
    Message,
    MessageRole,
    ModelClient,
)


def _user(text: str) -> Message:
    return Message(role=MessageRole.USER, content=text)


def test_default_model_per_role():
    client = FakeModelClient()
    assert client.model_for(AgentPersona.BUSINESS_ANALYST) == "gemini-2.5-flash"
    assert client.model_for(AgentPersona.SOLUTION_ARCHITECT) == "claude-sonnet-4-6"


def test_response_carries_resolved_model_and_persona():
    client = FakeModelClient("hello")
    resp = client.complete([_user("hi")], persona=AgentPersona.SOLUTION_ARCHITECT)

    assert resp.text == "hello"
    assert resp.model == "claude-sonnet-4-6"
    assert resp.persona is AgentPersona.SOLUTION_ARCHITECT


def test_unbound_role_raises():
    client = FakeModelClient()
    with pytest.raises(ValueError, match="no model bound"):
        client.model_for(AgentPersona.SECURITY_ENGINEER)


def test_model_binding_override():
    client = FakeModelClient(
        model_by_role={AgentPersona.SOLUTION_ARCHITECT: "claude-opus-4-8"}
    )
    assert client.model_for(AgentPersona.SOLUTION_ARCHITECT) == "claude-opus-4-8"


def test_scripted_responses_consumed_in_order():
    client = FakeModelClient(["first", "second"])
    r1 = client.complete([_user("a")], persona=AgentPersona.BUSINESS_ANALYST)
    r2 = client.complete([_user("b")], persona=AgentPersona.BUSINESS_ANALYST)

    assert (r1.text, r2.text) == ("first", "second")


def test_scripted_exhaustion_raises():
    client = FakeModelClient(["only"])
    client.complete([_user("a")], persona=AgentPersona.BUSINESS_ANALYST)
    with pytest.raises(AssertionError, match="script exhausted"):
        client.complete([_user("b")], persona=AgentPersona.BUSINESS_ANALYST)


def test_handler_sees_messages_and_persona():
    def handler(messages, persona):
        return f"{persona.value}:{messages[-1].content}"

    client = FakeModelClient(handler)
    resp = client.complete([_user("draft adr")], persona=AgentPersona.SOLUTION_ARCHITECT)
    assert resp.text == "solution-architect:draft adr"


def test_calls_are_recorded():
    client = FakeModelClient("ok")
    client.complete(
        [_user("extract requirements")],
        persona=AgentPersona.BUSINESS_ANALYST,
        system="You are a BA.",
        temperature=0.2,
    )

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call.persona is AgentPersona.BUSINESS_ANALYST
    assert call.model == "gemini-2.5-flash"
    assert call.system == "You are a BA."
    assert call.temperature == 0.2


def test_usage_is_estimated_and_nonzero():
    client = FakeModelClient("two words")
    resp = client.complete(
        [_user("one two three")],
        persona=AgentPersona.BUSINESS_ANALYST,
        system="sys header",
    )
    # input = "sys header" + "one two three" = 5 words; output = 2 words.
    assert resp.usage.input_tokens == 5
    assert resp.usage.output_tokens == 2
    assert resp.usage.total_tokens == 7


def test_fake_is_a_model_client():
    assert isinstance(FakeModelClient(), ModelClient)


def test_default_map_is_not_mutated_by_client():
    client = FakeModelClient()
    client.model_by_role[AgentPersona.OPS] = "x"
    assert AgentPersona.OPS not in DEFAULT_MODEL_BY_ROLE
