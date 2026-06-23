"""Test setup: load a local .env so the gated live suites (-m live/graph/jira/observability)
pick up credentials from .env, not only shell exports. Offline tests don't read these vars,
so this is harmless for the default run. Shell exports take precedence (override=False)."""

import os
from pathlib import Path

import pytest

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:  # python-dotenv is a dev dep; absent in a bare install
    pass


def _have_atlassian_env() -> bool:
    return bool(
        os.getenv("ATLASSIAN_URL")
        and os.getenv("ATLASSIAN_EMAIL")
        and (os.getenv("ATLASSIAN_API_TOKEN") or os.getenv("ATLASIAN_API_TOKEN"))
    )


@pytest.fixture
def live_jira_read_key() -> str:
    """A real, existing JIRA issue key to fetch (READ-ONLY).

    Resolution: explicit ``JIRA_TEST_TICKET`` wins; otherwise we *discover* the most
    recently created issue via the real ``search()`` JQL — so the live read test never
    assumes a fixed key like ``SCRUM-1`` exists. Skips (never fails) when there's no
    Atlassian env or the site has no issues at all.
    """
    if not _have_atlassian_env():
        pytest.skip("ATLASSIAN_* env not set")
    pytest.importorskip("httpx", reason="jira extra not installed")
    from agentic_memory import JiraTicketSource

    explicit = os.getenv("JIRA_TEST_TICKET")
    if explicit:
        return explicit
    # JIRA's /search/jql rejects unbounded JQL ("add a search restriction"), so anchor with a
    # wide date floor that still matches every real issue, newest first.
    keys = JiraTicketSource().search(
        'created >= "2000-01-01" ORDER BY created DESC', max_results=1
    )
    if not keys:
        pytest.skip("no JIRA issues found to read (create one, or set JIRA_TEST_TICKET)")
    return keys[0]


@pytest.fixture
def live_jira_write_key() -> str:
    """A JIRA issue key safe to write a test comment to (WRITE).

    Requires an explicit ``JIRA_TEST_TICKET`` — we deliberately do NOT auto-discover a
    write target, because posting a test comment onto an arbitrary real work ticket would
    be unwanted noise. Skips with guidance when no sandbox ticket is designated.
    """
    if not _have_atlassian_env():
        pytest.skip("ATLASSIAN_* env not set")
    key = os.getenv("JIRA_TEST_TICKET")
    if not key:
        pytest.skip("set JIRA_TEST_TICKET to a sandbox ticket to run the live publish test")
    return key
