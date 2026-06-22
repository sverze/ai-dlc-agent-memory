"""JiraTicketSource — gated behind `-m jira` (needs the httpx extra).

Two layers:
- mocked-transport tests (no network): request shape, ADF parsing, error mapping.
- ONE live test (additionally needs ATLASSIAN_* env): fetches a real ticket.

    uv run --extra jira python -m pytest -m jira -v
"""

import json
import os

import pytest

httpx = pytest.importorskip("httpx", reason="jira extra not installed")

from agentic_memory import JiraTicketSource  # noqa: E402

pytestmark = pytest.mark.jira


def _source_with(handler) -> JiraTicketSource:
    client = httpx.Client(
        base_url="https://example.atlassian.net",
        transport=httpx.MockTransport(handler),
    )
    return JiraTicketSource(
        url="https://example.atlassian.net",
        email="test@example.com",
        api_token="not-a-real-token",
        client=client,
    )


def test_fetch_builds_ticket_from_summary_and_adf():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/api/3/issue/SCRUM-1"
        assert request.url.params["fields"] == "summary,description"
        return httpx.Response(200, json={
            "key": "SCRUM-1",
            "fields": {
                "summary": "Password reset via email",
                "description": {
                    "type": "doc", "version": 1,
                    "content": [
                        {"type": "paragraph", "content": [
                            {"type": "text", "text": "Link expires after 30 minutes."},
                        ]},
                    ],
                },
            },
        })

    t = _source_with(handler).fetch("SCRUM-1")
    assert t.id == "SCRUM-1"
    assert t.body == "Password reset via email\n\nLink expires after 30 minutes."


def test_fetch_handles_missing_description():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "key": "SCRUM-2", "fields": {"summary": "Just a summary", "description": None},
        })

    t = _source_with(handler).fetch("SCRUM-2")
    assert t.body == "Just a summary"


def test_404_maps_to_ticket_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"errorMessages": ["Issue does not exist"]})

    with pytest.raises(KeyError, match="ticket not found: NOPE-9"):
        _source_with(handler).fetch("NOPE-9")


def test_401_maps_to_clear_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="")

    with pytest.raises(RuntimeError, match="auth failed"):
        _source_with(handler).fetch("SCRUM-1")


def test_missing_env_raises_named_var(monkeypatch):
    for var in ("ATLASSIAN_URL", "ATLASSIAN_EMAIL", "ATLASSIAN_API_TOKEN", "ATLASIAN_API_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError, match="ATLASSIAN_URL not set"):
        JiraTicketSource()


_HAVE_ENV = bool(
    os.getenv("ATLASSIAN_URL")
    and os.getenv("ATLASSIAN_EMAIL")
    and (os.getenv("ATLASSIAN_API_TOKEN") or os.getenv("ATLASIAN_API_TOKEN"))
)


def test_search_returns_keys():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/api/3/search/jql"
        assert "labels" in request.url.params["jql"]
        return httpx.Response(200, json={"issues": [{"key": "PROJ-1"}, {"key": "PROJ-2"}]})

    keys = _source_with(handler).search('labels = "ai-dlc" AND labels != "ai-dlc-done"')
    assert keys == ["PROJ-1", "PROJ-2"]


def test_add_label_puts_update():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(204)

    _source_with(handler).add_label("PROJ-1", "ai-dlc-done")
    assert seen["path"] == "/rest/api/3/issue/PROJ-1"
    assert seen["body"] == {"update": {"labels": [{"add": "ai-dlc-done"}]}}


@pytest.mark.skipif(not _HAVE_ENV, reason="ATLASSIAN_* env not set")
def test_live_fetch_real_ticket():
    """Fetches the ticket named in JIRA_TEST_TICKET (default SCRUM-1) from the real site."""
    key = os.getenv("JIRA_TEST_TICKET", "SCRUM-1")
    t = JiraTicketSource().fetch(key)
    assert t.id == key
    assert t.body.strip() != ""
    print(f"\nLIVE TICKET {key}: {json.dumps(t.body[:200])}")
