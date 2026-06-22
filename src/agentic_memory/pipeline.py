"""End-to-end orchestration — one ticket, all the way through, over the seams.

`process_ticket` is the reusable heart of the running system: fetch a ticket (any
`TicketSource`), drive the BA→SA loop, and publish the results back (any `Publisher`).
A CLI, a poller, or a webhook handler all call this one function — so "plug it into the
workforce" is wiring triggers/tools around `process_ticket`, not new agent logic.

Everything is the existing seams, so it runs fully offline with fakes (tests) and live with
real adapters (`make_model_client` / `GraphitiMemoryStore` / `JiraTicketSource` /
`make_publisher`) with no change here.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pydantic import BaseModel

from .agents import BAAgent, SAAgent
from .events import EventLog
from .fsm import FSM, TERMINAL_STATES
from .graph import MemoryStore
from .models import ModelClient
from .observability import NullTracer, Tracer, TracingModelClient
from .publish import Publisher
from .tickets import TicketSource
from .loop import run_loop


class PipelineResult(BaseModel):
    ticket_key: str
    final_state: str
    terminal: bool
    reached_decision: bool
    requirements_count: int = 0
    omitted_count: int = 0
    requirements_ref: str | None = None   # where the requirements were published (e.g. JIRA comment id)
    adr_ref: str | None = None            # where the ADR was published (e.g. Confluence page URL)


def process_ticket(
    ticket_key: str,
    *,
    source: TicketSource,
    model_client: ModelClient,
    store: MemoryStore,
    publisher: Publisher | None = None,
    tracer: Tracer | None = None,
    group_id: str | None = None,
) -> PipelineResult:
    """Run one ticket end-to-end: fetch → BA→SA loop → publish back.

    ``group_id`` namespaces this ticket's memory (defaults to the ticket key). If ``publisher``
    is given, requirements and any ADR are published. If ``tracer`` is given, model calls are
    traced (wrapped transparently). Returns a summary with the published references.
    """
    tracer = tracer or NullTracer()
    client: ModelClient = TracingModelClient(model_client, tracer)
    gid = group_id or ticket_key

    ticket = source.fetch(ticket_key)
    ba, sa = BAAgent(client, store), SAAgent(client, store)
    fsm = FSM(EventLog(Path(tempfile.mkdtemp()) / "events.jsonl"))

    with tracer.run(name=f"dlc:{ticket_key}", ticket_id=ticket_key, group_id=gid):
        result = run_loop(ticket, ba=ba, sa=sa, fsm=fsm, group_id=gid)
    tracer.flush()

    art, adr = result.artifact, result.adr
    req_ref = adr_ref = None
    if publisher and art is not None:
        req_ref = publisher.publish_requirements(art, ticket_key=ticket_key)
        if adr is not None:
            adr_ref = publisher.publish_adr(adr, art, ticket_key=ticket_key)

    omitted = adr.omitted_requirement_ids(art) if (adr and art) else set()
    return PipelineResult(
        ticket_key=ticket_key,
        final_state=str(result.final_state),
        terminal=result.final_state in TERMINAL_STATES,
        reached_decision=adr is not None,
        requirements_count=len(art.requirements) if art else 0,
        omitted_count=len(omitted),
        requirements_ref=req_ref,
        adr_ref=adr_ref,
    )
