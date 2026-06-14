"""AtlassianPublisher — gated behind `-m jira` (needs the httpx extra).

Mocked-transport tests assert the production publish path: request URLs, bodies, and
the requirements-comment / Confluence-page / back-link sequence — no network. Plus one
env-gated live publish to the user's sandbox.

    uv run --extra jira python -m pytest -m jira -v
"""

import os

import pytest

httpx = pytest.importorskip("httpx", reason="jira extra not installed")

from agentic_memory import (  # noqa: E402
    ADR,
    AtlassianPublisher,
    Requirement,
    RequirementsArtifact,
    RequirementTrace,
)

pytestmark = pytest.mark.jira


def _artifact() -> RequirementsArtifact:
    return RequirementsArtifact(
        id="req-1", source_ticket_id="SCRUM-1", title="Password reset",
        summary="Reset via email.",
        requirements=[Requirement(id="r-1", text="link expires 30 min")],
    )


def _adr() -> ADR:
    return ADR(
        id="adr-1", source_requirements_id="SCRUM-1", title="Token reset",
        context="c", decision="JWT", rationale="stateless",
        requirement_traces=[RequirementTrace(requirement_id="r-1", addressed=True, how="TTL")],
    )


def _publisher(handler, **kw) -> AtlassianPublisher:
    client = httpx.Client(
        base_url="https://sverze.atlassian.net",
        transport=httpx.MockTransport(handler),
    )
    return AtlassianPublisher(
        url="https://sverze.atlassian.net", email="e@x.com", api_token="tok",
        client=client, **kw,
    )


def test_publish_requirements_posts_adf_comment():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        import json
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "10001"})

    ref = _publisher(handler).publish_requirements(_artifact(), ticket_key="SCRUM-1")
    assert ref == "10001"
    assert seen["path"] == "/rest/api/3/issue/SCRUM-1/comment"
    assert seen["body"]["body"]["type"] == "doc"  # ADF document


def test_publish_adr_creates_page_then_links_from_ticket():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == "/wiki/api/v2/pages":
            return httpx.Response(200, json={
                "id": "555",
                "_links": {"base": "https://sverze.atlassian.net/wiki", "webui": "/spaces/SD/pages/555/ADR"},
            })
        return httpx.Response(201, json={"id": "10002"})

    # space_id pinned → no discovery call
    url = _publisher(handler, space_id="900").publish_adr(_adr(), _artifact(), ticket_key="SCRUM-1")
    assert url == "https://sverze.atlassian.net/wiki/spaces/SD/pages/555/ADR"
    # page created, then a link comment posted back to the ticket
    assert ("POST", "/wiki/api/v2/pages") in calls
    assert ("POST", "/rest/api/3/issue/SCRUM-1/comment") in calls


def test_space_discovery_when_not_pinned():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wiki/api/v2/spaces":
            return httpx.Response(200, json={"results": [{"id": "900", "key": "SD"}]})
        if request.url.path == "/wiki/api/v2/pages":
            import json
            assert json.loads(request.content)["spaceId"] == "900"
            return httpx.Response(200, json={"id": "555", "_links": {"webui": "/x"}})
        return httpx.Response(201, json={"id": "1"})

    _publisher(handler).publish_adr(_adr(), _artifact(), ticket_key="SCRUM-1")


def test_auth_failure_mapped():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="")

    with pytest.raises(RuntimeError, match="auth failed"):
        _publisher(handler).publish_requirements(_artifact(), ticket_key="SCRUM-1")


def test_missing_space_is_clear_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})  # no spaces

    with pytest.raises(RuntimeError, match="no Confluence space"):
        _publisher(handler).publish_adr(_adr(), _artifact(), ticket_key="SCRUM-1")


_HAVE_ENV = bool(
    os.getenv("ATLASSIAN_URL")
    and os.getenv("ATLASSIAN_EMAIL")
    and (os.getenv("ATLASSIAN_API_TOKEN") or os.getenv("ATLASIAN_API_TOKEN"))
)


@pytest.mark.skipif(not _HAVE_ENV, reason="ATLASSIAN_* env not set")
def test_live_publish_requirements_to_sandbox():
    """Posts a real requirements comment to JIRA_TEST_TICKET (default SCRUM-1)."""
    key = os.getenv("JIRA_TEST_TICKET", "SCRUM-1")
    ref = AtlassianPublisher().publish_requirements(_artifact(), ticket_key=key)
    assert ref
    print(f"\nLIVE comment id on {key}: {ref}")
