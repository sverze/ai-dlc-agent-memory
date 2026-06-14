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

> **Checkpoint (2026-06-12) — the FULL REAL STACK runs.** Swap #1 (real `ModelClient`),
> swap #1.5 (schema-in-prompt, D14), and **swap #2 (real Graphiti graph over Neo4j, D15)**
> are done. One command runs a real ticket through real models into a **real temporal graph**:
>
> ```bash
> docker compose up -d                              # Neo4j (browser: http://localhost:7474)
> uv run --extra live --extra graph python scripts/live_demo.py --graph
> ```
>
> The demo prints requirements, ADR with traces, omission check, token usage — and a raw
> Cypher count of the nodes/edges the run left in Neo4j (reference: 18 nodes / 19 edges,
> per-run `group_id`). Remaining for Stage 2: the JIRA tool (swap #3), OTel (swap #4).

| Stage | Scope | State |
|-------|-------|-------|
| **1 — Substrate** | typed artifacts, append-only event log, deterministic FSM | ✅ **Complete** |
| **2 — Core loop** | BA/SA agents, L4 memory, FSM negotiation, model seam | 🟡 **Full real stack runs (swaps #1, #1.5, #2 ✅); JIRA adapter built (#3 ✅); OTel pending** |
| 3 — Make it visible, then judge it ← **HYPOTHESIS GATE** | OTel→Langfuse, frozen scenarios, architect verdict, advisory eval + κ | ⬜ Not started |
| 4 — Breadth | Confluence / Notion / Miro ingestion | ⬜ Not started |
| 5 — Properties & robustness | conflict resolution, replay verification, V2 stubs, demo | ⬜ Not started |

**Two ways to run everything:** the **offline path** (default — `FakeModelClient` +
`InMemoryMemoryStore`, zero keys/services/spend, 43 deterministic tests) and the **real path**
(`make_model_client()` + `GraphitiMemoryStore`, gated behind the `live`/`graph` extras). Both
sit behind the same seams (`ModelClient`, `MemoryStore`), so agent and loop code is identical
in both — that's decision D11, and the gated parity tests prove it holds.

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
| `src/agentic_memory/agents.py` | `BAAgent` (ticket → `RequirementsArtifact` → memory) and `SAAgent` (memory → `ADR` or clarifications), both over the `ModelClient` + `MemoryStore` seams; prompts carry type-derived JSON schemas (D14). | ✅ Done |
| `src/agentic_memory/loop.py` | `run_loop` — drives the FSM through `intake → analysis ⇄ clarification → decision (+ escalation)`; the full BA→SA roundtrip, logged and replayable; proven on the full real stack. | ✅ Done |

`43 passed` offline — `tests/test_{artifacts,events,fsm,models,graph,loop}.py`. Plus two
gated opt-in suites, both passing: `-m live` (real provider calls + end-to-end loop) and
`-m graph` (11 tests proving `GraphitiMemoryStore` is behaviorally identical to the fake
against dockerized Neo4j). Decisions in [`DECISIONS.md`](DECISIONS.md).

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
│   ├── agents.py            # BAAgent / SAAgent (schema-in-prompt, D14)
│   └── loop.py              # run_loop — the FSM-driven roundtrip
├── scripts/live_demo.py     # one command: ticket → ADR + token usage (+ --graph, --jira, --runs)
├── docker-compose.yml       # Neo4j for the real graph store
├── tests/                   # pytest suite (43 offline + gated live/graph)
├── Plans/                   # design proposals (e.g. graphiti-entity-edge-model.md → D10)
├── DECISIONS.md             # durable decision log (D1–D17) — read this first
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

The architecture is **fakes behind interfaces** (decision D11): every external boundary has a
deterministic fake so the loop is testable offline, and going live means implementing the same
interface with a real backend. The remaining Stage-2 work is exactly those swaps — none require
touching `agents.py` or `loop.py`:

1. **Real model clients** — ✅ **Done (swap #1, D13).** `AnthropicModelClient` / `GeminiModelClient` /
   `make_model_client()` in `models.py`, behind the `live` extra; seam proven by the live smoke
   tests. Swap `FakeModelClient()` → `make_model_client()` and the same `run_loop` drives real models.
   **Swap #1.5 also done (D14):** prompts carry the artifact JSON schemas derived from the Pydantic
   classes (`_schema_block` in `agents.py`), so the real loop completes —
   `test_live_loop_reaches_terminal` passes and `scripts/live_demo.py` shows the whole run.
2. **Real graph store** — ✅ **Done (swap #2, D15).** `GraphitiMemoryStore` over graphiti-core on
   Neo4j (`docker compose up -d`); Kuzu was retired before adoption (deprecated upstream — D15).
   11 gated tests prove fake/real parity; `--graph` on the demo runs the full real stack and
   shows the run's nodes/edges in Neo4j.
3. **JIRA `ToolAdapter`** — ✅ **Built (swap #3, D16).** `TicketSource` seam in `tickets.py`:
   offline fake + `JiraTicketSource` (REST v3, ADF→text, `jira` extra). Demo `--jira KEY`
   runs the complete pipeline JIRA → BA → graph → SA → ADR. Set `ATLASSIAN_URL` /
   `ATLASSIAN_EMAIL` / `ATLASSIAN_API_TOKEN`; the personal→work switch is env-only.
4. **OTel → Langfuse** ← **DO THIS NEXT** — instrument each `ModelClient.complete` call; the
   `Usage` field on `ModelResponse` is already there to feed token metrics (FR10).

Then Stage 3 (the gate): a frozen, externally-authored scenario set + a senior architect's
accept/revise/reject verdict (D7). **Open decision OD3** — where the architect records verdicts —
must be resolved here. Build nothing below the gate until acceptance ≥70% / reject <10% holds.

**Start here:** read `DECISIONS.md` (D1–D17), run the full real stack
(`docker compose up -d && uv run --extra live --extra graph python scripts/live_demo.py --graph`),
then pick up integration step **#3** (JIRA ToolAdapter) — the last piece before the Stage-3 gate.

## Roadmap (build in dependency order, no calendar)

1. **Stage 1 — substrate** ✅ artifacts, event log, FSM
2. **Stage 2 — the core loop** 🟡 BA/SA agents + FSM negotiation done; **full real stack runs — real models + real Graphiti/Neo4j graph (swaps #1, #1.5, #2 ✅, see `scripts/live_demo.py --graph`)**; JIRA adapter and OTel pending (see [Continuing this work](#continuing-this-work-handoff))
3. **Stage 3 — make it visible, then judge it** ← **HYPOTHESIS GATE**: OTel→Langfuse, example tickets, architect verdict, advisory eval + κ. *If it fails here, fix retrieval/prompts before building anything below.*
4. **Stage 4 — breadth**: Confluence / Notion / Miro ingestion
5. **Stage 5 — properties & robustness**: conflict resolution, replay verification, V2 interface stubs, honest demo

---

*V1 = the de-scoped prototype: BA+SA, L2+L4 memory, human gate, ideation-tool ingestion.
Success = a senior architect accepts the SA's ADRs at ≥70%. Everything else is roadmap.*
