"""Publisher surface — offline tests: pure renderers + the in-memory fake (no httpx)."""

from agentic_memory import (
    ADR,
    AddedConstraint,
    InMemoryPublisher,
    Priority,
    Requirement,
    RequirementsArtifact,
    RequirementTrace,
    adr_page_title,
    render_adr_html,
    render_requirements_adf,
)


def _artifact() -> RequirementsArtifact:
    return RequirementsArtifact(
        id="req-1",
        source_ticket_id="SCRUM-1",
        title="Password reset",
        summary="Users reset passwords via email.",
        requirements=[
            Requirement(id="r-1", text="Reset link expires in 30 minutes", priority=Priority.MUST),
            Requirement(id="r-2", text="Log all reset attempts <including failures>"),
        ],
        key_facts=["email-based reset"],
        open_questions=["rate limiting?"],
    )


def _adr() -> ADR:
    return ADR(
        id="adr-1",
        source_requirements_id="SCRUM-1",
        title="Token-based reset & audit",
        context="ctx",
        decision="Signed JWT, 30-min TTL <hashed at rest>",
        rationale="Tamper-evident & stateless",
        requirement_traces=[
            RequirementTrace(requirement_id="r-1", addressed=True, how="30-min token TTL"),
            RequirementTrace(requirement_id="r-2", addressed=False, deferred_reason="logging in v2"),
        ],
        added_constraints=[
            AddedConstraint(text="Rate-limit reset requests", justification="prevents enumeration"),
        ],
    )


# --- requirements ADF ------------------------------------------------------

def test_requirements_adf_is_valid_doc():
    doc = render_requirements_adf(_artifact())
    assert doc["type"] == "doc" and doc["version"] == 1
    assert doc["content"][0]["type"] == "heading"


def test_requirements_adf_has_a_table_row_per_requirement():
    doc = render_requirements_adf(_artifact())
    table = next(b for b in doc["content"] if b["type"] == "table")
    # 1 header row + 2 requirement rows
    assert len(table["content"]) == 3
    header = table["content"][0]["content"]
    assert [c["content"][0]["content"][0]["text"] for c in header] == ["ID", "Priority", "Requirement"]


def test_requirements_adf_empty_sections_omitted():
    art = _artifact().model_copy(update={"acceptance_criteria": [], "open_questions": []})
    doc = render_requirements_adf(art)
    headings = [b["content"][0]["text"] for b in doc["content"] if b["type"] == "heading"]
    assert "Open questions for the SA" not in headings
    assert "Key facts" in headings  # this one is still present


def test_requirements_adf_priority_none_renders_dash():
    doc = render_requirements_adf(_artifact())
    table = next(b for b in doc["content"] if b["type"] == "table")
    r2_priority = table["content"][2]["content"][1]["content"][0]["content"][0]["text"]
    assert r2_priority == "—"


# --- ADR XHTML -------------------------------------------------------------

def test_adr_html_leads_with_decision_and_rationale():
    html = render_adr_html(_adr(), _artifact())
    assert html.index("Decision") < html.index("Rationale") < html.index("traceability")


def test_adr_html_has_traceability_with_status():
    html = render_adr_html(_adr(), _artifact())
    assert "✓ addressed" in html
    assert "↪ deferred" in html
    assert "logging in v2" in html
    assert "r-1: Reset link expires in 30 minutes" in html  # joined to requirement text


def test_adr_html_labels_architect_added_constraints():
    html = render_adr_html(_adr(), _artifact())
    assert "architect-added" in html
    assert "prevents enumeration" in html


def test_adr_html_reserves_diagrams_and_verdict_sections():
    html = render_adr_html(_adr(), _artifact())
    assert "Diagrams" in html and "coming soon" in html
    assert "Architect verdict" in html and "Accept" in html


def test_adr_html_escapes_special_chars():
    html = render_adr_html(_adr(), _artifact())
    # the literal "<hashed at rest>" must be escaped, not emitted as a tag
    assert "&lt;hashed at rest&gt;" in html
    assert "<hashed at rest>" not in html
    # storage format is strict XHTML — no named entities (only &amp;/&lt;/&gt;…)
    assert "&nbsp;" not in html and "&mdash;" not in html


def test_requirements_adf_does_not_need_escaping_but_preserves_text():
    # ADF carries text as JSON values, so angle brackets survive verbatim (no escaping).
    doc = render_requirements_adf(_artifact())
    table = next(b for b in doc["content"] if b["type"] == "table")
    r2_text = table["content"][2]["content"][2]["content"][0]["content"][0]["text"]
    assert r2_text == "Log all reset attempts <including failures>"


def test_page_title_includes_ticket_key():
    assert adr_page_title(_adr(), "SCRUM-1") == "ADR: Token-based reset & audit [SCRUM-1]"


# --- in-memory fake --------------------------------------------------------

def test_fake_records_and_returns_refs():
    pub = InMemoryPublisher()
    r1 = pub.publish_requirements(_artifact(), ticket_key="SCRUM-1")
    r2 = pub.publish_adr(_adr(), _artifact(), ticket_key="SCRUM-1")
    assert r1.startswith("memory://SCRUM-1/comment/")
    assert r2.startswith("memory://SCRUM-1/adr/")
    assert len(pub.requirements) == 1 and len(pub.adrs) == 1
