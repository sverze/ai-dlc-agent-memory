"""Ticket sources — the ToolAdapter seam that feeds the loop real delivery tickets.

Per D6: JIRA is integrated via **direct REST API** behind a small ``TicketSource``
interface (MCP is post-gate breadth for Confluence/Notion/Miro). Per D11: the
interface ships with an in-process fake, so the loop and tests never need a JIRA;
the real ``JiraTicketSource`` lazy-imports ``httpx`` from the optional ``jira`` extra.

The personal→work environment switch is pure configuration: ``ATLASSIAN_URL``,
``ATLASSIAN_EMAIL``, ``ATLASSIAN_API_TOKEN`` (basic auth, unscoped API token). No
code change is needed to point at a different Atlassian site (D16).

JIRA Cloud REST v3 returns the description as **ADF** (Atlassian Document Format,
a JSON tree). ``adf_to_text`` flattens it deterministically — every text leaf is
collected, blocks join with newlines — because a dropped list item here would
surface downstream as a phantom requirement omission.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

from .agents import TicketInput

_TIMEOUT_S = 30.0


class TicketSource(ABC):
    """Where delivery tickets come from. ``fetch`` returns the loop's input type."""

    @abstractmethod
    def fetch(self, key: str) -> TicketInput: ...


class InMemoryTicketSource(TicketSource):
    """Offline fake — a dict of key → body (mirrors FakeModelClient/InMemoryMemoryStore)."""

    def __init__(self, tickets: dict[str, str] | None = None) -> None:
        self._tickets = dict(tickets or {})

    def add(self, key: str, body: str) -> None:
        self._tickets[key] = body

    def fetch(self, key: str) -> TicketInput:
        try:
            return TicketInput(id=key, body=self._tickets[key])
        except KeyError:
            raise KeyError(f"ticket not found: {key}") from None


def adf_to_text(node: Any) -> str:
    """Flatten an ADF (Atlassian Document Format) tree to plain text.

    Collects every ``text`` leaf; block-level nodes (paragraph, heading, listItem,
    codeBlock, ...) contribute newline separation. Mentions/emojis fall back to
    their display text in ``attrs``. Lossless for textual content — formatting is
    intentionally discarded (the BA consumes prose, not markup).
    """
    if node is None:
        return ""
    if isinstance(node, str):  # already plain text (REST v2 style or test input)
        return node

    block_types = {
        "paragraph", "heading", "listItem", "codeBlock", "blockquote",
        "tableRow", "rule",
    }

    def walk(n: Any) -> str:
        # Fail-soft: real-world ADF contains node types we don't model
        # (mediaSingle, inlineCard, tables, ...). Unknown types recurse into
        # their content; non-dict oddities stringify; nothing ever throws —
        # a first contact with real ADF must degrade to imperfect text, not crash.
        if not isinstance(n, dict):
            return str(n) if n is not None else ""
        if n.get("type") == "text":
            return str(n.get("text", ""))
        if n.get("type") in ("mention", "emoji"):
            return str((n.get("attrs") or {}).get("text", ""))
        parts = [walk(c) for c in n.get("content", []) or []]
        joiner = "\n" if any(
            (c or {}).get("type") in block_types for c in n.get("content", []) or []
        ) else ""
        return joiner.join(p for p in parts if p)

    return walk(node).strip()


class JiraTicketSource(TicketSource):
    """Real ticket source over JIRA Cloud REST v3 with basic auth (email + API token).

    Connection resolution: explicit kwargs > environment. The unscoped personal API
    token defaults to the account's own capabilities — enough to read issues.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        client: Any | None = None,
    ) -> None:
        self._url = (url or os.getenv("ATLASSIAN_URL") or "").rstrip("/")
        self._email = email or os.getenv("ATLASSIAN_EMAIL") or ""
        # Tolerate the single-S spelling that has appeared in local setups.
        self._token = (
            api_token
            or os.getenv("ATLASSIAN_API_TOKEN")
            or os.getenv("ATLASIAN_API_TOKEN")
            or ""
        )
        for name, value in (
            ("ATLASSIAN_URL", self._url),
            ("ATLASSIAN_EMAIL", self._email),
            ("ATLASSIAN_API_TOKEN", self._token),
        ):
            if not value:
                raise RuntimeError(
                    f"{name} not set — export it (see .env.example) or pass it "
                    "explicitly to JiraTicketSource."
                )

        if client is not None:
            self._client = client
        else:
            import httpx  # lazy: offline import must not require the jira extra

            self._client = httpx.Client(
                base_url=self._url,
                auth=(self._email, self._token),
                timeout=_TIMEOUT_S,
            )

    def fetch(self, key: str) -> TicketInput:
        resp = self._client.get(
            f"/rest/api/3/issue/{key}", params={"fields": "summary,description"}
        )
        if resp.status_code == 401:
            raise RuntimeError(
                "JIRA auth failed (401) — check ATLASSIAN_EMAIL and "
                "ATLASSIAN_API_TOKEN (token value is never logged)."
            )
        if resp.status_code == 404:
            raise KeyError(f"ticket not found: {key}")
        if resp.status_code != 200:
            raise RuntimeError(
                f"JIRA request failed ({resp.status_code}): {resp.text[:200]}"
            )

        fields = resp.json().get("fields", {})
        summary = fields.get("summary") or ""
        description = adf_to_text(fields.get("description"))
        body = f"{summary}\n\n{description}".strip() if description else summary
        return TicketInput(id=key, body=body)
