# Collective Agentic Memory — AI DLC (V1 Prototype)

A collective agentic memory system for an **AI Delivery Life Cycle (AI DLC)** swarm.

V1 exists to answer one question, to a standard a human architect will accept:

> **Can a requirement written by one agent into shared temporal memory be retrieved and
> faithfully *transformed* (not merely copied) by another agent into an architecture
> decision a senior human would accept?**

Everything else — more personas, more memory layers, multi-model routing — is roadmap
that we only earn the right to build once that hypothesis holds.

## The loop we're proving

```
delivery ticket ──▶ BA agent ──▶ shared temporal graph (L4) ──▶ SA agent ──▶ ADR ──▶ human architect verdict
                  (requirements)        (Graphiti)              (decision)        (accept / revise / reject)
```

- **BA agent** (Gemini Flash): reads a delivery ticket, extracts structured, attributed
  requirements, writes them to shared memory.
- **SA agent** (Claude Sonnet): reads requirements from memory, raises clarifications,
  produces an Architecture Decision Record (ADR) with justified, traceable decisions.
- **Human architect** (not on the build team): the literal success gate.

**Success gate:** senior architect accepts ≥70% of ADRs (lower 95% CI), rejects <10%.
Machine metrics (memory-hit-rate, omission rate, judge-vs-human κ, replay determinism)
are *advisory* and always measured against the human verdict — never used to override it.

## Design principles (load-bearing, not decoration)

- **Determinism & auditability.** A finite-state machine is the sole executor of
  transitions; agents only *propose*. Every transition and write is appended to an
  immutable event log, and any run replays to identical state.
- **No prose hand-offs.** Agents exchange typed Pydantic artifacts, so "faithful
  transformation" is *structurally* checkable (traceability and omission are fields,
  not vibes).
- **Honest measurement.** Human gate is primary; all rates reported with 95% CIs.

## Development status

> **Checkpoint (2026-06-15) — the full round-trip is live-verified.** Every integration swap is
> done and proven against real services: a real JIRA ticket → real Gemini (requirements) → real
> Graphiti/Neo4j graph → real Claude (ADR) → **written back as a JIRA comment + a Confluence ADR
> page** (D17). Confirmed end-to-end against a real Atlassian site. One command runs the whole thing:
>
> ```bash
> docker compose up -d                              # Neo4j (browser: http://localhost:7474)
> uv run --extra live --extra graph --extra jira python scripts/live_demo.py \
>     --graph --jira <YOUR-TICKET-KEY> --publish
> ```
>
> **Stage 2 (the core loop) is functionally complete.** What's left is **Stage 3 — the hypothesis
> gate**: judge whether the ADRs are actually good enough (a senior architect accepting ≥70%). See
> [Continuing this work](#continuing-this-work-handoff).

| Stage | Scope | State |
|-------|-------|-------|
| **1 — Substrate** | typed artifacts, append-only event log, deterministic FSM | ✅ **Complete** |
| **2 — Core loop** | BA/SA agents, L4 memory, FSM negotiation, model + memory + JIRA + publish seams | ✅ **Complete & live-verified** (swaps #1, #1.5, #2, #3, D17) |
| 3 — Make it visible, then judge it ← **HYPOTHESIS GATE** | OTel→Langfuse ✅, frozen-scenario harness ✅, verdict capture ✅, advisory eval + κ ✅ | 🟢 **Build complete** (#1–#4 D18–D21). Gate is *runnable*; awaits the external corpus + real architect verdicts to run for real |
| 4 — Breadth | Confluence / Notion / Miro ingestion | ⬜ Not started |
| 5 — Properties & robustness | conflict resolution, replay verification, V2 stubs, demo | ⬜ Not started |

**Two ways to run everything:** the **offline path** (default — `FakeModelClient`,
`InMemoryMemoryStore`, `InMemoryTicketSource`, `InMemoryPublisher`, `NullTracer`; zero
keys/services/spend, 111 deterministic tests) and the **real path** (real model clients,
Graphiti/Neo4j, JIRA, Atlassian publisher, Langfuse tracing — gated behind the
`live`/`graph`/`jira`/`observability` extras). Both sit behind the same seams (`ModelClient`,
`MemoryStore`, `TicketSource`, `Publisher`, `Tracer`), so agent and loop code is identical in
both — that's decision D11, and the gated parity tests prove it holds.

### Modules

| Module | What it provides | Status |
|--------|------------------|--------|
| `src/agentic_memory/artifacts.py` | Typed data contracts: `RequirementsArtifact`, `ADR` (with `RequirementTrace` / `AddedConstraint` encoding the eval rubric), `KnowledgeEntry` write envelope | ✅ Done |
| `src/agentic_memory/events.py` | Append-only JSONL `EventLog` with monotonic sequence numbers + `replay()` reducer | ✅ Done |
| `src/agentic_memory/fsm.py` | `FSM` orchestrator: `intake → analysis ⇄ clarification → decision (+ escalation)`, whitelist transitions, clarify-round cap with forced escalation, `replay_final_state()` | ✅ Done |
| `src/agentic_memory/models.py` | `ModelClient` seam + offline `FakeModelClient` + **real `AnthropicModelClient` / `GeminiModelClient`** (lazy SDK imports, env keys, fence-normalized) and `make_model_client()` routing factory with per-role model override (`--ba-model`). | ✅ Done (swaps #1/#1.5) |
| `src/agentic_memory/graph.py` | L4 `MemoryStore` seam over Graphiti: node/edge types from our artifacts (D10), domain writes (`write_requirements`/`write_adr`), and omission + key-fact queries. Offline `InMemoryMemoryStore` fake. | ✅ Done |
| `src/agentic_memory/graphiti_store.py` | **Real `GraphitiMemoryStore`** — the six seam primitives over graphiti-core EntityNode/EntityEdge on Neo4j (D15): namespaced uuids, lossless `attrs_json`, one event loop per store. 11 gated tests prove fake/real parity. | ✅ Done (swap #2) |
| `src/agentic_memory/tickets.py` | `TicketSource` seam (D6/D16): `InMemoryTicketSource` fake + **real `JiraTicketSource`** (REST v3, basic auth, deterministic ADF→text flattening, mapped errors, `jira` extra). | ✅ Done (swap #3) |
| `src/agentic_memory/publish.py` | `Publisher` seam (D17/FR8): pure ADF/XHTML renderers + `InMemoryPublisher` fake + **`AtlassianPublisher`** — BA requirements → JIRA comment, SA ADR → Confluence page (traceability table + verdict + Miro slot) + ticket back-link. | ✅ Done (review surface) |
| `src/agentic_memory/observability.py` | `Tracer` seam (D18/FR10): `NullTracer` + **`LangfuseTracer`** + `TracingModelClient` wrapper — one Langfuse generation per model call (persona/model/tokens/latency), strictly additive (faults swallowed). `observability` extra. | ✅ Done (Stage 3 #1) |
| `src/agentic_memory/scenarios.py` | Frozen gate corpus (D19/D9): `Scenario` + markdown-frontmatter loader + fingerprinted `ScenarioSet` + `ScenarioTicketSource` (feeds the loop unchanged). `scenarios/` currently holds a **synthetic dry-run** set (D22), not the real gate corpus. | ✅ Harness done (Stage 3 #2) |
| `src/agentic_memory/verdicts.py` | Architect verdict capture (D20/D7): `Verdict` + `VerdictStore` seam (file/in-memory) + `summarize_verdicts()` (accept rate w/ Wilson 95% lower bound). Human-only sink. `scripts/record_verdict.py`; log in `verdicts/`. | ✅ Done (Stage 3 #3) |
| `src/agentic_memory/eval.py` | Advisory eval (D21/FR9): deterministic `score_traceability` + cross-family LLM `judge_adr` + `cohens_kappa`/`judge_agreement` + `build_eval_report`. Judge is structurally non-gating (gate = human verdicts only); degeneracy-guarded κ. `scripts/run_eval.py`. | ✅ Done (Stage 3 #4) |
| `src/agentic_memory/agents.py` | `BAAgent` (ticket → `RequirementsArtifact` → memory) and `SAAgent` (memory → `ADR` or clarifications), both over the `ModelClient` + `MemoryStore` seams; prompts carry type-derived JSON schemas (D14). | ✅ Done |
| `src/agentic_memory/loop.py` | `run_loop` — drives the FSM through `intake → analysis ⇄ clarification → decision (+ escalation)`; the full BA→SA roundtrip, logged and replayable; proven on the full real stack. | ✅ Done |

`111 passed` offline (renderers, fakes, seam pass-through — zero keys/services). Plus four
gated opt-in suites, all passing: `-m live` (real provider calls + end-to-end loop), `-m graph`
(11 tests, `GraphitiMemoryStore` ≡ fake against dockerized Neo4j), `-m jira` (mocked-transport
+ env-gated live fetch/publish), and `-m observability` (Langfuse tracer via injected mock
client). Decisions in [`DECISIONS.md`](DECISIONS.md).

> See the loop run end-to-end (prints requirements, FSM path, ADR, omission check):
> ```bash
> uv run pytest tests/test_loop.py -s -k happy
> ```

> The structural omission check already lives in the type system:
> `ADR.omitted_requirement_ids(artifact)` returns any source requirement that is neither
> addressed nor explicitly deferred — i.e. silently dropped in transit.

## Getting started

Requires **Python 3.12+** and [**uv**](https://docs.astral.sh/uv/).

```bash
# install deps (creates .venv from the committed uv.lock)
uv sync

# run the offline tests (no keys, no network, no spend)
uv run pytest
```

**Credentials:** copy `.env.example` → `.env` and fill in the keys you need. The demo and the
gated tests **auto-load `.env`** (via `python-dotenv`); shell `export`s still take precedence if set.

To exercise the **real** model clients you need the `live` extra and provider keys
(`ANTHROPIC_API_KEY`, `GEMINI_API_KEY` — see `.env.example`):

```bash
uv sync --extra live
# NOTE: use `python -m pytest`, not bare `pytest` — the console script misses the extra.
uv run --extra live python -m pytest -m live -v   # makes real API calls (costs money)
```

To exercise the **real graph store** you need the `graph` extra and Neo4j running:

```bash
docker compose up -d                                          # Neo4j on :7687 / :7474
uv run --extra graph python -m pytest -m graph -v             # 11 fake/real parity tests
```

To pull **real JIRA tickets** (and write results back), you need the `jira` extra and the
`ATLASSIAN_*` env vars (see `.env.example`):

```bash
uv run --extra jira python -m pytest -m jira -v   # mocked-transport tests + env-gated live fetch/publish
# complete pipeline: pull from JIRA → run → publish back (requirements comment + Confluence ADR page):
uv run --extra live --extra graph --extra jira python scripts/live_demo.py --graph --jira SCRUM-1 --publish
```

**What a human sees (the review surface, D17).** `--publish` writes back additively: the BA's
requirements become a **comment on the source ticket**, and the SA's ADR becomes a **Confluence
page** (linked from the ticket) leading with the decision and the **requirement-traceability
table** — the join an architect reviews — plus a Miro-diagram placeholder and an "Architect
verdict" section. No one needs Neo4j or a terminal: they open the ticket, follow the link, judge
the ADR. Needs Confluence enabled on the site; set `CONFLUENCE_SPACE_KEY` to target a space
(otherwise the first space is used — the printed page URL shows which).

To send **per-agent metrics to Langfuse**, you need the `observability` extra and Langfuse keys
(`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` — see `.env.example`):

```bash
uv run --extra observability python -m pytest -m observability -v   # injected-mock-client tests
uv run --extra live --extra observability python scripts/live_demo.py --trace   # real run → Langfuse
```

Each model call becomes a Langfuse **generation** tagged with persona/model/tokens/latency, nested
under a per-run span — so BA (Gemini) and SA (Claude) are comparable in the Traces view (left nav →
**Tracing → Traces → `dlc-run:<ticket>`**). **No keys = silent no-op** (the loop is never affected).
`--trace` runs `auth_check()` and prints **✓ connection verified** or a **✗** that names the problem,
so a misconfig is obvious in one run.

> ⚠️ **`LANGFUSE_HOST` must match your keys' region** — Langfuse keys are region-specific. US-region
> keys against the EU host (or vice versa) fail with a silent `401` and traces never appear. US Cloud
> → `https://us.cloud.langfuse.com`, EU Cloud → `https://cloud.langfuse.com`, self-host → your
> `LANGFUSE_HOST`. (Self-host infra isn't bundled here; D9 self-host applies once you handle
> non-anonymized data.)

*Ollama / local models are V2 (D8 router) but would be traced for free through the same wrapper.*

**Neo4j console:** http://localhost:7474 — username `neo4j`, password `devpassword`
(the docker-compose local-dev default; override via `NEO4J_AUTH` + `NEO4J_PASSWORD` for
anything shared). After a `--graph` demo run, paste the Cypher the demo prints to see that
run's graph, e.g.:

```cypher
MATCH (n:Entity {group_id: '<group_id from the demo output>'})-[r]-(m) RETURN n, r, m
-- all runs in the store:  MATCH (n:Entity) RETURN DISTINCT n.group_id
```

> Gemini free tier allows **20 requests/day/model** — roughly a handful of full runs per model
> per day. **A 429 RESOURCE_EXHAUSTED from the demo means quota, not a regression.** Point the BA
> at a sibling quota bucket to keep going: `scripts/live_demo.py --ba-model gemini-2.5-flash-lite`.

```python
from agentic_memory import EventLog, FSM, DLCState, TransitionProposal, replay_final_state

log = EventLog("run.jsonl")
fsm = FSM(log, max_clarify_rounds=3)

fsm.propose(TransitionProposal(to_state=DLCState.ANALYSIS, agent="ba", reason="ticket read", confidence=0.9))
fsm.propose(TransitionProposal(to_state=DLCState.DECISION, agent="sa", reason="requirements clear", confidence=0.8))
fsm.run()

assert fsm.state is DLCState.DECISION
assert replay_final_state(log) is fsm.state   # the log replays to identical state
```

## Layout

```
.
├── src/agentic_memory/      # the package
│   ├── artifacts.py         # typed hand-offs (Pydantic v2)
│   ├── events.py            # append-only event log + replay
│   ├── fsm.py               # deterministic orchestrator
│   ├── models.py            # ModelClient seam + FakeModelClient + real Anthropic/Gemini clients ✅
│   ├── graph.py             # MemoryStore seam + InMemoryMemoryStore fake
│   ├── graphiti_store.py    # real GraphitiMemoryStore over Neo4j ✅ (D15)
│   ├── tickets.py           # TicketSource seam + real JiraTicketSource ✅ (D16)
│   ├── publish.py           # Publisher seam: requirements→JIRA comment, ADR→Confluence ✅ (D17)
│   ├── observability.py     # Tracer seam + LangfuseTracer + TracingModelClient ✅ (D18)
│   ├── scenarios.py         # frozen gate corpus: ScenarioSet + ScenarioTicketSource ✅ (D19)
│   ├── verdicts.py          # architect verdict capture + honest gate readout ✅ (D20)
│   ├── eval.py              # advisory scorers + LLM judge + judge-vs-human κ ✅ (D21)
│   ├── agents.py            # BAAgent / SAAgent (schema-in-prompt, D14)
│   └── loop.py              # run_loop — the FSM-driven roundtrip
├── scripts/live_demo.py     # one command: ticket → ADR + token usage (+ --graph, --jira, --runs)
├── scripts/run_scenarios.py # run the frozen scenario set; prints fingerprint + summary
├── scripts/record_verdict.py# record an architect accept/revise/reject verdict
├── scripts/run_eval.py      # advisory eval dashboard: scores + human gate + judge κ
├── verdicts/                # architect verdict log (human-only; none shipped)
├── scenarios/               # frozen gate corpus (illustrative examples + D9 boundary README)
├── docker-compose.yml       # Neo4j for the real graph store
├── tests/                   # pytest suite (111 offline + gated live/graph/jira/observability)
├── Plans/                   # design proposals (e.g. graphiti-entity-edge-model.md → D10)
├── DECISIONS.md             # durable decision log (D1–D22) — read this first
├── .env.example             # setup template (spec Appendix A.2)
├── pyproject.toml           # uv project; pytest config
├── uv.lock                  # pinned deps (committed — NFR6 reproducibility)
└── 2026-06-08-collective-agentic-memory-*.md   # PRD, spec, research
```

## Documentation

- **PRD v1** — `2026-06-08-collective-agentic-memory-prd-v1.md` (product framing, goals, scope, build order)
- **Prototype spec** — `2026-06-08-collective-agentic-memory-prototype-spec.md` (build-level detail, instrumentation, Appendix A: keys/services/cost)
- **Research** — `2026-06-08-collective-agentic-memory-research.md` (the memory-layer landscape and why this architecture)

## Tech stack (V1, confirmed)

Python-first, because the memory/agent/eval ecosystem is Python-native.

| Layer | Choice |
|-------|--------|
| Runtime / packaging | Python 3.12+, uv |
| Orchestration | Hand-rolled deterministic FSM (no agent framework) |
| Agents | Direct provider SDKs (`anthropic`, `google-genai`) behind a `ModelClient` interface |
| L4 semantic memory | Graphiti (temporal knowledge graph) on Neo4j Community |
| Graph writes | Deterministic from typed artifacts — **no LLM extraction in the V1 loop** (D10); Graphiti extraction reserved for V2 free-text |
| L2 working memory | In-process Pydantic artifacts |
| Event log | Append-only JSONL |
| Observability | Langfuse + OpenTelemetry (self-hosted) |
| Advisory eval | DeepEval + RAGAS |
| Testing | pytest |

**Deferred to V2:** persona memory (Mem0), episodic memory (Zep/Hindsight), skill registry,
LiteLLM routing, more personas (Security/QA/Ops), second-tier tools, Figma.

## Continuing this work (handoff)

The architecture is **fakes behind interfaces** (D11): every external boundary has a deterministic
fake so the loop runs offline, and going live = implementing the same interface with a real backend.
**All four integration swaps are done and live-verified** — none touched `agents.py` / `loop.py`:

1. **Real model clients** — ✅ swap #1/#1.5 (D13/D14): `make_model_client()` (Anthropic + Gemini), schema-in-prompt so real models conform.
2. **Real graph store** — ✅ swap #2 (D15): `GraphitiMemoryStore` over Neo4j; 11 parity tests; `--graph`.
3. **JIRA in** — ✅ swap #3 (D16): `JiraTicketSource` pulls real tickets; `--jira KEY`.
4. **Publish out** — ✅ D17: `AtlassianPublisher` — requirements → JIRA comment, ADR → Confluence page; `--publish`.

### What's next — Stage 3, the hypothesis gate

This is the **go/no-go**: does the loop produce ADRs a senior architect actually accepts (≥70% accept,
<10% reject, D7)? The machine is built; now we measure it. Four pieces, in rough order:

1. **OTel → Langfuse instrumentation** — ✅ **Done (D18).** `TracingModelClient` wraps the
   `ModelClient` seam and emits one Langfuse generation per call (persona, model, tokens, latency)
   under a per-run span; `make_tracer()` is a no-op without keys. Run with `--trace`; works against
   Langfuse Cloud or self-host. BA and SA are comparable side by side in the Traces view.
2. **A frozen scenario set** — ✅ **Harness done (D19).** `scenarios/` is loaded via `ScenarioTicketSource`
   (loop unchanged) and fingerprinted. It currently holds a **15-ticket synthetic dry-run set** (D22,
   `source: synthetic-dry-run`) so the full pipeline runs end-to-end — `run_scenarios.py`/`run_eval.py`
   loudly flag it as NON-GATE. **Still needed for a real result: an externally-authored, anonymized
   corpus** (D9) replacing it, reviewed by an independent senior architect (D7).
3. **Architect verdict capture** — ✅ **Done (D20, resolves OD3).** In-repo verdict log
   (`verdicts.py` + `verdicts/`), `scripts/record_verdict.py` to record one; verdicts tie to
   scenario + set fingerprint + ADR; `summarize_verdicts()` gives the honest gate readout (accept
   rate with a Wilson 95% lower bound, reject rate, pass/fail per D7). **Human-only sink** — the
   judge never writes here.
4. **Advisory eval harness** — ✅ **Done (D21, FR9).** `eval.py`: deterministic traceability/omission
   scorers + a cross-family LLM judge + judge-vs-human Cohen's κ (trusted only at κ≥0.6, n≥10, and
   non-degenerate). Structurally non-gating — the gate reads human verdicts only; a test proves a
   hostile judge can't move it. `scripts/run_eval.py` is the dashboard. All *advisory* (NFR4).

**Stage 3's build is complete (D18–D21). The gate is now runnable — what remains is not code:** the
externally-authored anonymized **scenario corpus** (D9) and the senior architect's real **verdicts**
(D20), then `run_eval.py` produces the gate result. Past the gate (if it holds, D7) lies V2: the
evolution layers (L1 persona / L3 skills / L5 episodic + the "dreaming" consolidation engine),
deferred pending the gate and lab research on consolidation.

**Also queued (not gating):** Miro diagrams in the ADR (the reserved "Diagrams" section, D17).

**Only if the gate passes:** Stage 4 (Confluence/Notion/Miro *ingestion* for breadth) and Stage 5
(conflict resolution, replay verification, V2 interface stubs, honest demo). **Build nothing below
the gate until it holds** (D7).

**Start here:** read `DECISIONS.md` (D1–D22), run the full round-trip
(`docker compose up -d && uv run --extra live --extra graph --extra jira python scripts/live_demo.py --graph --jira <KEY> --publish`),
then pick up Stage 3 step **#1** (Langfuse instrumentation) or **#3** (verdict capture, OD3).

## Roadmap (build in dependency order, no calendar)

1. **Stage 1 — substrate** ✅ artifacts, event log, FSM
2. **Stage 2 — the core loop** ✅ **complete & live-verified** — BA/SA agents + FSM negotiation, and the full real round-trip: JIRA ticket → real models → Graphiti/Neo4j graph → JIRA comment + Confluence ADR page (swaps #1, #1.5, #2, #3, D17). Run it: `scripts/live_demo.py --graph --jira <KEY> --publish`
3. **Stage 3 — make it visible, then judge it** ← **HYPOTHESIS GATE (next)**: OTel→Langfuse, a frozen external scenario set, architect verdict capture (OD3), advisory eval + κ. *If it fails here, fix retrieval/prompts before building anything below.*
4. **Stage 4 — breadth**: Confluence / Notion / Miro ingestion
5. **Stage 5 — properties & robustness**: conflict resolution, replay verification, V2 interface stubs, honest demo

---

*V1 = the de-scoped prototype: BA+SA, L2+L4 memory, human gate, ideation-tool ingestion.
Success = a senior architect accepts the SA's ADRs at ≥70%. Everything else is roadmap.*
