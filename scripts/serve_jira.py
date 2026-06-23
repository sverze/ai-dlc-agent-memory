"""Background JIRA poller — the swarm running against real tickets, no script-per-ticket.

This is the "plug it into the workforce" entry point. It polls JIRA for tickets a human has
flagged for the swarm (a label), runs each end-to-end (`process_ticket`: BA→SA→graph→publish),
and marks it done so it isn't reprocessed. Outputs land back in JIRA (requirements comment) and
Confluence (ADR page) where the BAs and architects already work.

    uv run --extra live --extra graph --extra jira python scripts/serve_jira.py            # one sweep
    uv run --extra live --extra graph --extra jira python scripts/serve_jira.py --watch 120 # poll every 120s

Config (env / .env): ATLASSIAN_*, ANTHROPIC_API_KEY, GEMINI_API_KEY, plus optional
  AIDLC_TRIGGER_LABEL (default "ai-dlc"), AIDLC_DONE_LABEL (default "ai-dlc-done"),
  CONFLUENCE_SPACE_KEY, NEO4J_* (if --graph). Trigger a ticket by adding the label in JIRA.

A human stays in the loop: the swarm DRAFTS (requirements + ADR); the architect reviews and
decides in Confluence/JIRA. Nothing here makes an irreversible call on the work itself.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

from agentic_memory import (  # noqa: E402
    GraphitiMemoryStore,
    InMemoryMemoryStore,
    JiraTicketSource,
    make_model_client,
    make_publisher,
    make_tracer,
    process_ticket,
)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ENV_PATH, override=False)


def _is_quota_error(exc: Exception) -> bool:
    s = str(exc)
    return "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower()


def _sweep(*, jira, use_graph: bool, ba_model: str | None, provider: str | None) -> int:
    from agentic_memory import AgentPersona

    trigger = os.getenv("AIDLC_TRIGGER_LABEL", "ai-dlc")
    done = os.getenv("AIDLC_DONE_LABEL", "ai-dlc-done")
    jql = f'labels = "{trigger}" AND labels != "{done}" ORDER BY created ASC'
    keys = jira.search(jql)
    print(f"  trigger '{trigger}': {len(keys)} ticket(s) to process  ({', '.join(keys) or 'none'})")

    override = {AgentPersona.BUSINESS_ANALYST: ba_model} if ba_model else None
    processed = 0
    for key in keys:
        print(f"  ▶ {key}")
        store = GraphitiMemoryStore() if use_graph else InMemoryMemoryStore()
        try:
            res = process_ticket(
                key, source=jira,
                model_client=make_model_client(provider=provider, model_by_role=override),
                store=store, publisher=make_publisher(), tracer=make_tracer(),
            )
            print(f"      {res.final_state}: reqs={res.requirements_count} omitted={res.omitted_count} "
                  f"adr={'published' if res.adr_ref else 'none'}")
            if res.adr_ref:
                print(f"        ADR → {res.adr_ref}")
            jira.add_label(key, done)  # mark processed so the next sweep skips it
            processed += 1
        except Exception as exc:
            if _is_quota_error(exc):
                print(f"      ⚠️ quota exhausted on {key} — stopping sweep; resume after reset (label not set, so it retries).")
                break
            print(f"      ⚠️ {key} failed: {type(exc).__name__}: {str(exc)[:120]} (not marked done — will retry)")
    return processed


def main() -> int:
    _load_dotenv()
    args = sys.argv[1:]
    use_graph = "--graph" in args
    if use_graph:
        args.remove("--graph")
    ba_model = args[args.index("--ba-model") + 1] if "--ba-model" in args else None
    watch = int(args[args.index("--watch") + 1]) if "--watch" in args else 0
    provider = "vertex" if "--vertex" in args else None  # route both models via Vertex (D25)

    # Direct providers need ANTHROPIC_API_KEY; Vertex needs a GCP project instead.
    have_models = os.getenv("GOOGLE_CLOUD_PROJECT") if provider == "vertex" else os.getenv("ANTHROPIC_API_KEY")
    if not (os.getenv("ATLASSIAN_URL") and have_models):
        need = "ATLASSIAN_* + GOOGLE_CLOUD_PROJECT" if provider == "vertex" else "ATLASSIAN_* + ANTHROPIC_API_KEY + GEMINI_API_KEY"
        print(f"Set {need} in .env first.")
        return 2

    jira = JiraTicketSource()
    print("═" * 72)
    print("🛰️  AI-DLC swarm — JIRA poller (agents draft; humans review & decide)")
    print("═" * 72)

    if not watch:
        _sweep(jira=jira, use_graph=use_graph, ba_model=ba_model, provider=provider)
        return 0

    print(f"  watching — polling every {watch}s (Ctrl-C to stop)")
    while True:
        _sweep(jira=jira, use_graph=use_graph, ba_model=ba_model, provider=provider)
        time.sleep(watch)


if __name__ == "__main__":
    sys.exit(main())
