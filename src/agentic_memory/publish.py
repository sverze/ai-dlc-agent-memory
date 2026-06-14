"""Publisher seam — the human-facing output surface (the review gate, FR8/US4).

The agents' artifacts only matter if a human can review them where they already work.
This module renders the BA's ``RequirementsArtifact`` and the SA's ``ADR`` into the
formats Atlassian expects and places them:

- **Requirements → a structured comment** on the source JIRA ticket (ADF). Additive,
  reversible, non-destructive (the user's chosen shape).
- **ADR → a Confluence page** (storage XHTML) linked back from the ticket by a comment.
  The page leads with decision + rationale and embeds the **requirement-traceability
  table** — the one thing the architect must see to judge *faithful transformation* —
  plus a reserved "Diagrams" section for a future Miro embed and an "Architect verdict"
  section so the review the gate exists for is possible today (verdict capture itself is
  OD3 / Stage 3).

Design (D17): renderers are PURE functions building ADF/XHTML directly from the typed
artifacts (we already hold the structure — no lossy markdown hop). Publishers only place
rendered content; the real one lazy-imports httpx (the `jira` extra) and reuses the
ATLASSIAN_* env. Writes are additive only. Re-running a ticket posts a fresh comment and a
fresh page (distinguished by the run group_id / timestamp); dedup is a documented V2 concern.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from html import escape
from typing import Any

from .artifacts import ADR, RequirementsArtifact

_TIMEOUT_S = 30.0


# --- ADF rendering (JIRA comment bodies) ----------------------------------
#
# JIRA Cloud REST v3 requires comment bodies in ADF (Atlassian Document Format, a
# JSON tree). We build it directly from the artifact — text rides JSON string values,
# so special characters need no escaping here (the inverse of the XHTML path below).


def _adf_text(s: str) -> dict[str, Any]:
    return {"type": "text", "text": s}


def _adf_para(s: str) -> dict[str, Any]:
    return {"type": "paragraph", "content": [_adf_text(s)]} if s else {"type": "paragraph", "content": []}


def _adf_heading(s: str, level: int = 3) -> dict[str, Any]:
    return {"type": "heading", "attrs": {"level": level}, "content": [_adf_text(s)]}


def _adf_bullet_list(items: list[str]) -> dict[str, Any]:
    return {
        "type": "bulletList",
        "content": [
            {"type": "listItem", "content": [_adf_para(item)]} for item in items
        ],
    }


def _adf_cell(s: str, *, header: bool = False) -> dict[str, Any]:
    return {
        "type": "tableHeader" if header else "tableCell",
        "attrs": {},
        "content": [_adf_para(s)],
    }


def _adf_row(cells: list[str], *, header: bool = False) -> dict[str, Any]:
    return {"type": "tableRow", "content": [_adf_cell(c, header=header) for c in cells]}


def render_requirements_adf(artifact: RequirementsArtifact) -> dict[str, Any]:
    """The BA's requirements as an ADF document for a JIRA comment."""
    content: list[dict[str, Any]] = [
        _adf_heading("🤖 Requirements extracted by the BA agent", 3),
        _adf_para(artifact.summary or ""),
    ]

    if artifact.requirements:
        rows = [_adf_row(["ID", "Priority", "Requirement"], header=True)]
        for r in artifact.requirements:
            priority = r.priority.value if r.priority else "—"
            rows.append(_adf_row([r.id, priority, r.text]))
        content.append({"type": "table", "attrs": {"layout": "default"}, "content": rows})

    for label, items in (
        ("Acceptance criteria", [c.text for c in artifact.acceptance_criteria]),
        ("Key facts", artifact.key_facts),
        ("Open questions for the SA", artifact.open_questions),
    ):
        if items:
            content.append(_adf_heading(label, 4))
            content.append(_adf_bullet_list(items))

    return {"type": "doc", "version": 1, "content": content}


# --- XHTML rendering (Confluence storage-format page bodies) --------------
#
# Confluence Cloud pages store body as `storage` representation (an XHTML subset).
# Here text IS interpolated into markup, so every user string MUST be escaped.


def _h(s: str) -> str:
    return escape(str(s or ""), quote=False)


def render_adr_html(adr: ADR, artifact: RequirementsArtifact | None = None) -> str:
    """The SA's ADR as Confluence storage XHTML.

    Leads with decision + rationale; embeds the requirement-traceability table (the
    review hero); labels architect-added constraints; reserves a Diagrams section for
    Miro; ends with an Architect-verdict section so review is possible pre-OD3.
    """
    req_text = {r.id: r.text for r in (artifact.requirements if artifact else [])}

    parts: list[str] = [
        f"<h2>Decision</h2><p>{_h(adr.decision)}</p>",
        f"<h2>Rationale</h2><p>{_h(adr.rationale)}</p>",
        f"<h2>Context</h2><p>{_h(adr.context)}</p>",
    ]

    # The hero: requirement traceability — what went in vs how it was addressed.
    parts.append("<h2>Requirement traceability</h2>")
    if adr.requirement_traces:
        rows = [
            "<table><tbody>",
            "<tr><th>Requirement</th><th>Status</th><th>How / why</th></tr>",
        ]
        for t in adr.requirement_traces:
            status = "✓ addressed" if t.addressed else "↪ deferred"
            detail = t.how if t.addressed else t.deferred_reason
            label = req_text.get(t.requirement_id, "")
            req_cell = f"{_h(t.requirement_id)}: {_h(label)}" if label else _h(t.requirement_id)
            rows.append(f"<tr><td>{req_cell}</td><td>{status}</td><td>{_h(detail or '')}</td></tr>")
        rows.append("</tbody></table>")
        parts.append("".join(rows))
    else:
        parts.append("<p><em>No requirement traces recorded.</em></p>")

    if adr.added_constraints:
        parts.append("<h2>Architect-added constraints</h2><ul>")
        for c in adr.added_constraints:
            parts.append(
                f"<li><strong>{_h(c.text)}</strong> "
                f"<em>(architect-added — {_h(c.justification)})</em></li>"
            )
        parts.append("</ul>")

    if adr.consequences:
        parts.append("<h2>Consequences</h2><ul>")
        parts.extend(f"<li>{_h(x)}</li>" for x in adr.consequences)
        parts.append("</ul>")

    # Reserved for a Miro board embed (wired in a later swap).
    parts.append(
        "<h2>Diagrams</h2><p><em>Architecture diagrams (Miro) — coming soon.</em></p>"
    )
    # Review surface — the verdict the gate exists to capture (mechanism is OD3).
    # NB: storage format is strict XHTML — use literal chars, never named entities
    # like &nbsp; (only the 5 XML entities are valid, emitted via html.escape).
    parts.append(
        "<h2>Architect verdict</h2>"
        "<p><strong>Verdict:</strong> ☐ Accept · ☐ Revise · ☐ Reject</p>"
        "<p><strong>Notes:</strong> </p>"
    )
    parts.append(
        f"<hr/><p><em>Generated by the SA agent for ticket "
        f"{_h(adr.source_requirements_id)} — ADR {_h(adr.id)}.</em></p>"
    )
    return "".join(parts)


def adr_page_title(adr: ADR, ticket_key: str) -> str:
    return f"ADR: {adr.title} [{ticket_key}]"


# --- the Publisher seam ----------------------------------------------------


class Publisher(ABC):
    """Where rendered artifacts get placed. Returns a human-followable reference."""

    @abstractmethod
    def publish_requirements(
        self, artifact: RequirementsArtifact, *, ticket_key: str
    ) -> str:
        """Place the BA requirements; return a reference (e.g. comment id)."""
        ...

    @abstractmethod
    def publish_adr(
        self, adr: ADR, artifact: RequirementsArtifact | None = None, *, ticket_key: str
    ) -> str:
        """Place the SA ADR; return a reference (e.g. the page URL)."""
        ...


class InMemoryPublisher(Publisher):
    """Offline fake — records what would be published; returns deterministic refs."""

    def __init__(self) -> None:
        self.requirements: list[tuple[str, dict[str, Any]]] = []
        self.adrs: list[tuple[str, str]] = []  # (ticket_key, html)

    def publish_requirements(
        self, artifact: RequirementsArtifact, *, ticket_key: str
    ) -> str:
        self.requirements.append((ticket_key, render_requirements_adf(artifact)))
        return f"memory://{ticket_key}/comment/{len(self.requirements)}"

    def publish_adr(
        self, adr: ADR, artifact: RequirementsArtifact | None = None, *, ticket_key: str
    ) -> str:
        self.adrs.append((ticket_key, render_adr_html(adr, artifact)))
        return f"memory://{ticket_key}/adr/{len(self.adrs)}"


class AtlassianPublisher(Publisher):
    """Real publisher: requirements → JIRA comment, ADR → Confluence page + JIRA link.

    JIRA and Confluence share one Atlassian site, auth, and host — so one httpx client
    serves both (paths differ: /rest/api/3 vs /wiki/api/v2).
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        space_key: str | None = None,
        space_id: str | None = None,
        client: Any | None = None,
    ) -> None:
        self._url = (url or os.getenv("ATLASSIAN_URL") or "").rstrip("/")
        self._email = email or os.getenv("ATLASSIAN_EMAIL") or ""
        self._token = (
            api_token
            or os.getenv("ATLASSIAN_API_TOKEN")
            or os.getenv("ATLASIAN_API_TOKEN")
            or ""
        )
        self._space_key = space_key or os.getenv("CONFLUENCE_SPACE_KEY")
        self._space_id = space_id  # tests/callers may pin it to skip discovery
        for name, value in (
            ("ATLASSIAN_URL", self._url),
            ("ATLASSIAN_EMAIL", self._email),
            ("ATLASSIAN_API_TOKEN", self._token),
        ):
            if not value:
                raise RuntimeError(
                    f"{name} not set — export it (see .env.example) or pass it explicitly."
                )

        if client is not None:
            self._client = client
        else:
            import httpx  # lazy: offline import must not require the jira extra

            self._client = httpx.Client(
                base_url=self._url, auth=(self._email, self._token), timeout=_TIMEOUT_S
            )

    # -- helpers ------------------------------------------------------------

    def _check(self, resp: Any, *, what: str) -> Any:
        if resp.status_code in (401, 403):
            raise RuntimeError(
                f"Atlassian auth failed ({resp.status_code}) on {what} — check "
                "ATLASSIAN_EMAIL / ATLASSIAN_API_TOKEN (token never logged)."
            )
        if resp.status_code == 404:
            raise RuntimeError(f"{what}: not found (404) — check the key/site.")
        if resp.status_code == 409:
            raise RuntimeError(
                f"{what}: conflict (409) — a page with this title likely already exists "
                "in the space. Re-runs use a timestamped title to avoid this; if you hit "
                "it, the title collided within the same minute."
            )
        if resp.status_code >= 300:
            raise RuntimeError(f"{what} failed ({resp.status_code}): {resp.text[:200]}")
        return resp

    def _resolve_space_id(self) -> str:
        if self._space_id:
            return self._space_id
        if self._space_key:
            resp = self._check(
                self._client.get("/wiki/api/v2/spaces", params={"keys": self._space_key}),
                what="Confluence space lookup",
            )
        else:
            resp = self._check(
                self._client.get("/wiki/api/v2/spaces", params={"limit": 1}),
                what="Confluence space discovery",
            )
        results = resp.json().get("results", [])
        if not results:
            raise RuntimeError(
                "no Confluence space found — enable Confluence on the site and create a "
                "space, or set CONFLUENCE_SPACE_KEY."
            )
        self._space_id = str(results[0]["id"])
        return self._space_id

    # -- the seam -----------------------------------------------------------

    def publish_requirements(
        self, artifact: RequirementsArtifact, *, ticket_key: str
    ) -> str:
        body = render_requirements_adf(artifact)
        resp = self._check(
            self._client.post(f"/rest/api/3/issue/{ticket_key}/comment", json={"body": body}),
            what=f"JIRA comment on {ticket_key}",
        )
        return str(resp.json().get("id", ""))

    def _post_link_comment(self, ticket_key: str, url: str) -> None:
        body = {
            "type": "doc", "version": 1,
            "content": [{
                "type": "paragraph",
                "content": [
                    _adf_text("🏛️ SA agent published an ADR → "),
                    {"type": "text", "text": url,
                     "marks": [{"type": "link", "attrs": {"href": url}}]},
                ],
            }],
        }
        self._check(
            self._client.post(f"/rest/api/3/issue/{ticket_key}/comment", json={"body": body}),
            what=f"JIRA ADR-link comment on {ticket_key}",
        )

    def publish_adr(
        self, adr: ADR, artifact: RequirementsArtifact | None = None, *, ticket_key: str
    ) -> str:
        space_id = self._resolve_space_id()
        # Confluence page titles must be unique within a space; a re-run of the same
        # ticket would 409 on a fixed title. Timestamp the title so re-runs coexist
        # (additive, honest) — dedup/versioning is a documented V2 concern.
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        title = f"{adr_page_title(adr, ticket_key)} · {stamp}"
        payload = {
            "spaceId": space_id,
            "status": "current",
            "title": title,
            "body": {"representation": "storage", "value": render_adr_html(adr, artifact)},
        }
        resp = self._check(
            self._client.post("/wiki/api/v2/pages", json=payload),
            what="Confluence page create",
        )
        data = resp.json()
        links = data.get("_links", {})
        base = links.get("base") or f"{self._url}/wiki"
        page_url = f"{base}{links.get('webui', '')}" if links.get("webui") else base
        self._post_link_comment(ticket_key, page_url)
        return page_url


def make_publisher(**kwargs: Any) -> Publisher:
    """Real publisher factory — drop-in for ``InMemoryPublisher()`` in a live run.

    Connection from ATLASSIAN_* env (+ optional CONFLUENCE_SPACE_KEY) unless overridden.
    """
    return AtlassianPublisher(**kwargs)
