"""Run real tickets through the real BA→SA loop and show everything measurable.

The quantifiable input/output surface of the prototype, in one command:

    uv run --extra live python scripts/live_demo.py
    uv run --extra live python scripts/live_demo.py "your ticket text here"
    uv run --extra live python scripts/live_demo.py --runs 5   # reliability/cost table

    # FULL REAL STACK — real models + real Graphiti graph (docker compose up -d first):
    uv run --extra live --extra graph python scripts/live_demo.py --graph

    # COMPLETE PIPELINE — pull from JIRA, publish back (requirements comment + Confluence ADR):
    uv run --extra live --extra graph --extra jira python scripts/live_demo.py \
        --graph --jira SCRUM-1 --publish

    # + OBSERVABILITY — send per-agent metrics to Langfuse (needs LANGFUSE_* env):
    uv run --extra live --extra observability python scripts/live_demo.py --trace

Prints: the input ticket, the BA's extracted RequirementsArtifact, the FSM path
from the event log, the SA's ADR with requirement traces, the structural omission
check, and real token usage per model call (the raw material of the token-efficiency
metric, FR10). With ``--runs N`` it repeats the loop N times and prints a
reliability/cost table (terminal rate, schema-parse failures, token spread) —
schema-in-prompt (D14) is best-effort, so conformance is a *rate*, not a fact.
Needs ANTHROPIC_API_KEY + GEMINI_API_KEY in the environment.
"""

from __future__ import annotations

import sys
import tempfile
import time
import uuid as uuid_mod
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from agentic_memory import (
    DEFAULT_GROUP,
    AgentPersona,
    BAAgent,
    EventLog,
    FSM,
    InMemoryMemoryStore,
    Message,
    ModelClient,
    ModelResponse,
    SAAgent,
    TERMINAL_STATES,
    TicketInput,
    make_model_client,
    run_loop,
)

DEFAULT_TICKET = (
    "As a user I want to reset my password via email so I can regain access "
    "if I forget it. The reset link must expire after 30 minutes and all reset "
    "attempts must be logged for the security team."
)


class UsageRecorder(ModelClient):
    """Wraps the real client and records (persona, model, usage) per call."""

    def __init__(self, inner: ModelClient) -> None:
        super().__init__()
        self.inner = inner
        self.calls: list[tuple[AgentPersona, str, int, int]] = []

    def model_for(self, persona: AgentPersona) -> str:
        return self.inner.model_for(persona)

    def complete(
        self,
        messages: Sequence[Message],
        *,
        persona: AgentPersona,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        resp = self.inner.complete(
            messages, persona=persona, system=system, temperature=temperature
        )
        self.calls.append(
            (persona, resp.model, resp.usage.input_tokens, resp.usage.output_tokens)
        )
        return resp


def _run_once(
    ticket: TicketInput,
    *,
    verbose: bool,
    use_graph: bool = False,
    ba_model: str | None = None,
    publish: bool = False,
    trace: bool = False,
) -> dict:
    """One full loop run; returns measurable outcomes. Prints detail if verbose."""
    from agentic_memory import NullTracer, TracingModelClient, make_tracer

    log_path = Path(tempfile.mkdtemp()) / "events.jsonl"
    override = {AgentPersona.BUSINESS_ANALYST: ba_model} if ba_model else None
    recorder = UsageRecorder(make_model_client(model_by_role=override))
    # Langfuse tracing wraps the client; no-op (NullTracer) unless LANGFUSE_* keys are set.
    tracer = make_tracer() if trace else NullTracer()
    client = TracingModelClient(recorder, tracer) if trace else recorder
    if use_graph:
        from agentic_memory import GraphitiMemoryStore  # needs the `graph` extra

        group = f"demo-{uuid_mod.uuid4().hex[:8]}"  # per-run namespace (OC3/D10)
        store: InMemoryMemoryStore | GraphitiMemoryStore = GraphitiMemoryStore()
    else:
        group = DEFAULT_GROUP
        store = InMemoryMemoryStore()
    ba, sa = BAAgent(client, store), SAAgent(client, store)
    fsm = FSM(EventLog(log_path))

    stats: dict = {"ok": False, "error": None}
    started = time.monotonic()
    try:
        result = None
        # One Langfuse trace per run; model-call generations nest under it.
        with tracer.run(name=f"dlc-run:{ticket.id}", ticket_id=ticket.id, group_id=group):
            for attempt in range(4):  # transient provider 5xx happen; retry a few times
                try:
                    result = run_loop(ticket, ba=ba, sa=sa, fsm=fsm, group_id=group)
                    break
                except Exception as exc:
                    if any(s in str(exc) for s in ("503", "UNAVAILABLE", "overload")):
                        if verbose:
                            print(f"  … provider busy (attempt {attempt + 1}), retrying")
                        time.sleep(6)
                        continue
                    raise
        if result is None:
            stats["error"] = "provider unavailable after retries"
            return stats
    except ValidationError as exc:
        # The D14 reliability gap made measurable: model output failed the schema.
        stats["error"] = f"schema-parse failure: {str(exc).splitlines()[0]}"
        return stats
    except Exception as exc:
        stats["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        return stats
    finally:
        stats["wall_s"] = time.monotonic() - started
        # usage lives on the recorder; with --trace `client` is the TracingModelClient wrapper.
        stats["tokens_in"] = sum(c[2] for c in recorder.calls)
        stats["tokens_out"] = sum(c[3] for c in recorder.calls)
        stats["calls"] = len(recorder.calls)

    art = result.artifact
    assert art is not None
    omitted = result.adr.omitted_requirement_ids(art) if result.adr else None
    stats.update(
        ok=True,
        terminal=result.final_state in TERMINAL_STATES,
        final_state=str(result.final_state),
        clarify_rounds=result.clarify_rounds,
        escalated=result.escalated,
        requirements=len(art.requirements),
        omitted=len(omitted) if omitted is not None else None,
    )
    if not verbose:
        return stats

    print()
    print("═" * 72)
    print("🧾 BA OUTPUT — RequirementsArtifact (real Gemini, schema-validated)")
    print("═" * 72)
    print(f"  title:   {art.title}")
    print(f"  summary: {art.summary}")
    print(f"  requirements ({len(art.requirements)}):")
    for r in art.requirements:
        print(f"    - [{r.priority or 'unset'}] {r.id}: {r.text}")
    for label, items in (
        ("acceptance_criteria", [c.text for c in art.acceptance_criteria]),
        ("key_facts", art.key_facts),
        ("open_questions", art.open_questions),
    ):
        if items:
            print(f"  {label} ({len(items)}):")
            for it in items:
                print(f"    - {it}")

    print()
    print("═" * 72)
    print("🔀 FSM PATH (from the append-only event log)")
    print("═" * 72)
    for entry in fsm.event_log.read_all():
        if entry.state is not None:
            forced = "  ⚠️ forced" if entry.payload.get("forced") else ""
            print(
                f"  {entry.seq}: {entry.state.from_state} → {entry.state.to_state}"
                f"  ({entry.agent}: {entry.payload.get('reason')}){forced}"
            )
    print(f"  final: {result.final_state}  (terminal={stats['terminal']}, "
          f"clarify_rounds={result.clarify_rounds}, escalated={result.escalated})")

    if result.adr:
        adr = result.adr
        print()
        print("═" * 72)
        print("🏛️  SA OUTPUT — ADR (real Claude)")
        print("═" * 72)
        print(f"  title:    {adr.title}")
        print(f"  decision: {adr.decision}")
        print(f"  rationale:{adr.rationale}")
        print(f"  traces ({len(adr.requirement_traces)}):")
        for t in adr.requirement_traces:
            mark = "✓ addressed" if t.addressed else f"→ deferred ({t.deferred_reason})"
            print(f"    - {t.requirement_id}: {mark}")
        if adr.added_constraints:
            print(f"  architect-added constraints ({len(adr.added_constraints)}):")
            for c in adr.added_constraints:
                print(f"    - {c.text}  (why: {c.justification})")
        print(f"  ⚖️  omission check: {omitted if omitted else 'NONE ✅'}")

    print()
    print("═" * 72)
    print("📊 QUANTIFIED — real token usage per call (FR10 raw material)")
    print("═" * 72)
    print("  (input tokens include the injected JSON schema — D14 overhead, by design)")
    for i, (persona, model, t_in, t_out) in enumerate(recorder.calls, 1):
        print(f"  call {i}: {persona.value:<20} {model:<22} in={t_in:>6}  out={t_out:>6}")
    print(f"  TOTAL: {stats['calls']} calls   in={stats['tokens_in']}  "
          f"out={stats['tokens_out']}  all={stats['tokens_in'] + stats['tokens_out']} tokens"
          f"   wall={stats['wall_s']:.1f}s")
    print(f"  event log: {log_path}")

    if use_graph:
        # Independent evidence straight from Neo4j (raw Cypher, not our mapping):
        records, _, _ = store._run(  # type: ignore[union-attr]
            store._driver.execute_query(  # type: ignore[union-attr]
                "MATCH (n:Entity {group_id: $g}) "
                "OPTIONAL MATCH (n)-[r:RELATES_TO {group_id: $g}]->() "
                "RETURN count(DISTINCT n) AS nodes, count(DISTINCT r) AS edges",
                g=group,
            )
        )
        print()
        print("═" * 72)
        print("🕸️  IN THE GRAPH — raw Cypher count from Neo4j (independent of our code)")
        print("═" * 72)
        print(f"  group_id: {group}")
        print(f"  nodes: {records[0]['nodes']}   edges: {records[0]['edges']}")
        print("  inspect in the browser: http://localhost:7474 →")
        print(f"    MATCH (n:Entity {{group_id: '{group}'}})-[r]-(m) RETURN n, r, m")

    if publish:
        from agentic_memory import make_publisher  # needs the `jira` extra + ATLASSIAN_* env

        pub = make_publisher()
        print()
        print("═" * 72)
        print("📨 PUBLISHED — the human-review surface (additive writes)")
        print("═" * 72)
        comment_ref = pub.publish_requirements(art, ticket_key=ticket.id)
        print(f"  requirements → JIRA comment on {ticket.id}  (id {comment_ref})")
        if result.adr:
            page_url = pub.publish_adr(result.adr, art, ticket_key=ticket.id)
            print(f"  ADR → Confluence page: {page_url}")
            print(f"  (+ back-link comment on {ticket.id})")
        print("  the architect now reviews the ADR page against the requirements ✦")

    if trace:
        tracer.flush()  # OTel batches — force spans out before the process exits
        print()
        print("═" * 72)
        print("📡 TRACED — per-agent metrics sent to Langfuse")
        print("═" * 72)
        if isinstance(tracer, NullTracer):
            print("  LANGFUSE_* not set → tracing was a no-op. Set the keys to see traces.")
        else:
            print("  run + per-call generations sent (persona, model, tokens, latency).")
            print("  open your Langfuse project → Traces → 'dlc-run:" + ticket.id + "'")
    return stats


def _load_dotenv() -> None:
    """Load a local .env (cwd/parents) so keys can live there, not just shell exports.

    Existing shell exports win (override=False). No-op if python-dotenv isn't installed.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(override=False)


def main() -> int:
    _load_dotenv()
    args = sys.argv[1:]
    runs = 1
    if "--runs" in args:
        i = args.index("--runs")
        runs = max(1, int(args[i + 1]))
        del args[i : i + 2]
    use_graph = "--graph" in args
    if use_graph:
        args.remove("--graph")
    ba_model = None
    if "--ba-model" in args:  # e.g. --ba-model gemini-2.5-flash-lite (per-model quotas)
        i = args.index("--ba-model")
        ba_model = args[i + 1]
        del args[i : i + 2]
    jira_key = None
    if "--jira" in args:  # pull the ticket from real JIRA (needs ATLASSIAN_* env)
        i = args.index("--jira")
        jira_key = args[i + 1]
        del args[i : i + 2]
    publish = "--publish" in args  # write results back to JIRA/Confluence (pair with --jira)
    if publish:
        args.remove("--publish")
    trace = "--trace" in args  # send per-agent metrics to Langfuse (needs LANGFUSE_* env)
    if trace:
        args.remove("--trace")

    if jira_key:
        from agentic_memory import JiraTicketSource  # needs the `jira` extra

        ticket = JiraTicketSource().fetch(jira_key)
    else:
        ticket = TicketInput(id="DEMO-1", body=args[0] if args else DEFAULT_TICKET)

    print("═" * 72)
    print("📥 INPUT — delivery ticket")
    print("═" * 72)
    print(f"  id:   {ticket.id}")
    print(f"  body: {ticket.body}")

    results = []
    for n in range(runs):
        if runs > 1:
            print(f"\n--- run {n + 1}/{runs} ---")
        r = _run_once(ticket, verbose=(n == 0), use_graph=use_graph, ba_model=ba_model,
                      publish=publish, trace=trace)
        if not r.get("ok"):
            print(f"  ❌ run {n + 1} failed: {r.get('error')}")
        results.append(r)

    if runs > 1:
        ok = [r for r in results if r.get("ok")]
        totals = [r["tokens_in"] + r["tokens_out"] for r in results if "tokens_in" in r]
        print()
        print("═" * 72)
        print(f"📈 RELIABILITY / COST over {runs} runs (schema-in-prompt is best-effort — D14)")
        print("═" * 72)
        print(f"  terminal-success: {len(ok)}/{runs}  "
              f"({100 * len(ok) / runs:.0f}%)")
        for n, r in enumerate(results, 1):
            if r.get("ok"):
                print(f"  run {n}: ✅ {r['final_state']:<12} reqs={r['requirements']}  "
                      f"omitted={r['omitted']}  clarify={r['clarify_rounds']}  "
                      f"tokens={r['tokens_in'] + r['tokens_out']}  wall={r['wall_s']:.0f}s")
            else:
                print(f"  run {n}: ❌ {r['error']}")
        if totals:
            print(f"  tokens/run: min={min(totals)}  max={max(totals)}  "
                  f"mean={sum(totals) // len(totals)}")

    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
