"""TicketSource seam — offline tests (fake + ADF flattening, no httpx needed)."""

import pytest

from agentic_memory import InMemoryTicketSource, adf_to_text


def test_fake_fetch_roundtrip():
    src = InMemoryTicketSource({"JIRA-1": "As a user I want X."})
    t = src.fetch("JIRA-1")
    assert t.id == "JIRA-1"
    assert t.body == "As a user I want X."


def test_fake_missing_raises():
    with pytest.raises(KeyError, match="ticket not found"):
        InMemoryTicketSource().fetch("NOPE-1")


def test_adf_simple_paragraphs():
    doc = {
        "type": "doc", "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "First line."}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "Second line."}]},
        ],
    }
    assert adf_to_text(doc) == "First line.\nSecond line."


def test_adf_nested_bullet_list():
    doc = {
        "type": "doc", "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Requirements:"}]},
            {"type": "bulletList", "content": [
                {"type": "listItem", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "expire after 30 minutes"}]},
                ]},
                {"type": "listItem", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "log all attempts"}]},
                    {"type": "bulletList", "content": [
                        {"type": "listItem", "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "accessible to security"}]},
                        ]},
                    ]},
                ]},
            ]},
        ],
    }
    text = adf_to_text(doc)
    # Every requirement leaf must survive flattening — a dropped item here would
    # become a phantom omission downstream.
    assert "expire after 30 minutes" in text
    assert "log all attempts" in text
    assert "accessible to security" in text


def test_adf_mention_and_code_block():
    doc = {
        "type": "doc", "version": 1,
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "Ask "},
                {"type": "mention", "attrs": {"id": "x", "text": "@alice"}},
            ]},
            {"type": "codeBlock", "content": [{"type": "text", "text": "POST /reset"}]},
        ],
    }
    text = adf_to_text(doc)
    assert "@alice" in text
    assert "POST /reset" in text


def test_adf_none_and_plain_string():
    assert adf_to_text(None) == ""
    assert adf_to_text("already plain") == "already plain"


def test_adf_unknown_node_types_fail_soft():
    """Real-world ADF (mediaSingle, inlineCard, tables) must never crash the
    flattener — unknown types recurse, text survives, nothing throws."""
    doc = {
        "type": "doc", "version": 1,
        "content": [
            {"type": "mediaSingle", "attrs": {"layout": "center"}, "content": [
                {"type": "media", "attrs": {"id": "x", "type": "file"}},
            ]},
            {"type": "inlineCard", "attrs": {"url": "https://example.com"}},
            {"type": "table", "content": [
                {"type": "tableRow", "content": [
                    {"type": "tableCell", "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "cell text survives"}]},
                    ]},
                ]},
            ]},
            {"type": "paragraph", "content": [{"type": "text", "text": "tail"}, {"type": "hardBreak"}]},
        ],
    }
    text = adf_to_text(doc)
    assert "cell text survives" in text
    assert "tail" in text
