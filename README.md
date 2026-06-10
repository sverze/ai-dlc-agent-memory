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

> **Checkpoint (2026-06-10) — integration swap #1 done.** The full BA→SA hypothesis loop runs
> **end-to-end and is deterministically tested with zero external services** — every boundary
> (model, memory) has a fake behind a stable interface. **The real `ModelClient` is now
> implemented** (Anthropic + Gemini) and the **seam is proven by live smoke tests** (real text +
> real token usage, both providers). Remaining for a *live loop* run: real-model **structured
> output** (swap #1.5, see [Continuing this work](#continuing-this-work-handoff)), then a Graphiti
> backend, the JIRA tool, and OTel.

| Stage | Scope | State |
|-------|-------|-------|
| **1 — Substrate** | typed artifacts, append-only event log, deterministic FSM | ✅ **Complete** |
| **2 — Core loop** | BA/SA agents, L4 memory, FSM negotiation, model seam | 🟡 **Offline complete; real ModelClient done (seam proven); real-loop structured output + Graphiti/JIRA/OTel pending** |
| 3 — Make it visible, then judge it ← **HYPOTHESIS GATE** | OTel→Langfuse, frozen scenarios, architect verdict, advisory eval + κ | ⬜ Not started |
| 4 — Breadth | Confluence / Notion / Miro ingestion | ⬜ Not started |
| 5 — Properties & robustness | conflict resolution, replay verification, V2 stubs, demo | ⬜ Not started |

**What "offline" means for Stage 2:** the agent logic, the memory model, and the negotiation
loop are real and fully exercised; the model client and graph store are fakes. The interfaces
(`ModelClient`, `MemoryStore`) are the integration seams — dropping in real implementations
behind them requires no change to agent or loop code.

### Modules

| Module | What it provides | Status |
|--------|------------------|--------|
| `src/agentic_memory/artifacts.py` | Typed data contracts: `RequirementsArtifact`, `ADR` (with `RequirementTrace` / `AddedConstraint` encoding the eval rubric), `KnowledgeEntry` write envelope | ✅ Done |
| `src/agentic_memory/events.py` | Append-only JSONL `EventLog` with monotonic sequence numbers + `replay()` reducer | ✅ Done |
| `src/agentic_memory/fsm.py` | `FSM` orchestrator: `intake → analysis ⇄ clarification → decision (+ escalation)`, whitelist transitions, clarify-round cap with forced escalation, `replay_final_state()` | ✅ Done |
| `src/agentic_memory/models.py` | `ModelClient` seam + offline `FakeModelClient` + **real `AnthropicModelClient` / `GeminiModelClient`** (lazy SDK imports, env keys, fence-normalized) and `make_model_client()` routing factory. Live smoke tests prove real calls + token usage. | ✅ Seam + real clients done; live loop pending structured output (OD4) |
| `src/agentic_memory/graph.py` | L4 `MemoryStore` seam over Graphiti: node/edge types from our artifacts (D10), domain writes (`write_requirements`/`write_adr`), and omission + key-fact queries. Offline `InMemoryMemoryStore` fake; real Graphiti backend pending services. | ✅ Seam done (Stage 2) |
| `src/agentic_memory/agents.py` | `BAAgent` (ticket → `RequirementsArtifact` → memory) and `SAAgent` (memory → `ADR` or clarifications), both over the `ModelClient` + `MemoryStore` seams. | ✅ Done (offline) |
| `src/agentic_memory/loop.py` | `run_loop` — drives the FSM through `intake → analysis ⇄ clarification → decision (+ escalation)`; the full BA→SA roundtrip, logged and replayable. | ✅ Done (offline) |

`43 passed` offline — `tests/test_{artifacts,events,fsm,models,graph,loop}.py`. Plus
`tests/test_live_models.py` (gated, opt-in): 2 live smoke tests (real Anthropic + Gemini calls)
and 1 `xfail` end-to-end loop test (the swap-#1.5 target). Decisions in [`DECISIONS.md`](DECISIONS.md).

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
│   ├── graph.py             # MemoryStore seam + InMemoryMemoryStore  ← swap point (Graphiti)
│   ├── agents.py            # BAAgent / SAAgent
│   └── loop.py              # run_loop — the FSM-driven roundtrip
├── tests/                   # pytest suite (43 offline + 3 gated live)
├── Plans/                   # design proposals (e.g. graphiti-entity-edge-model.md → D10)
├── DECISIONS.md             # durable decision log (D1–D13) — read this first
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
| Graph extraction LLM | Gemini Flash |
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

1. **Real model clients** — ✅ **Done (swap #1).** `AnthropicModelClient` / `GeminiModelClient` /
   `make_model_client()` in `models.py`, behind the `live` extra; seam proven by the live smoke
   tests. Swap `FakeModelClient()` → `make_model_client()` and the same `run_loop` drives real models.
1.5. **Real-model structured output** ← **DO THIS NEXT (OD4).** The seam works, but real models
   don't yet emit schema-conformant artifacts: they wrap JSON in markdown fences (already fixed in
   the client) *and* omit required `RequirementsArtifact` fields / use out-of-enum `priority`
   values, because `BA_SYSTEM` names the schema without including it. Fix by injecting the Pydantic
   schema into `BA_SYSTEM`/`SA_SYSTEM` (prompt-only) and/or threading `response_schema` (Gemini) /
   tool-use (Anthropic) through the seam. The `xfail` `test_live_loop_reaches_terminal` is the
   target to turn green. *This is the gate to the live loop running end-to-end.*
2. **Real graph store** — implement `MemoryStore` (see `graph.py`) as `GraphitiMemoryStore`
   over `graphiti-core`. Backend: Kuzu (embedded) for local dev, Neo4j for shared/demo (D10/OC2).
   Add a `docker-compose.yml`. The node/edge model is settled in `Plans/graphiti-entity-edge-model.md`.
3. **JIRA `ToolAdapter`** — direct API (`httpx`) → `TicketInput`. This is the only tool needed
   to reach the hypothesis gate (D6).
4. **OTel → Langfuse** — instrument each `ModelClient.complete` call; the `Usage` field on
   `ModelResponse` is already there to feed token metrics (FR10).

Then Stage 3 (the gate): a frozen, externally-authored scenario set + a senior architect's
accept/revise/reject verdict (D7). **Open decision OD3** — where the architect records verdicts —
must be resolved here. Build nothing below the gate until acceptance ≥70% / reject <10% holds.

**Start here:** read `DECISIONS.md` (D1–D13, esp. D13 + OD4), then run
`uv run pytest tests/test_loop.py -s -k happy` to watch the loop, then pick up integration
step **1.5** (real-model structured output) — the gate to the live loop running end-to-end.

## Roadmap (build in dependency order, no calendar)

1. **Stage 1 — substrate** ✅ artifacts, event log, FSM
2. **Stage 2 — the core loop** 🟡 BA/SA agents + FSM negotiation + model/memory seams done **offline**; **real `ModelClient` done (swap #1, seam proven)**; real-model structured output (swap #1.5), Graphiti backend, JIRA adapter, and OTel pending (see [Continuing this work](#continuing-this-work-handoff))
3. **Stage 3 — make it visible, then judge it** ← **HYPOTHESIS GATE**: OTel→Langfuse, example tickets, architect verdict, advisory eval + κ. *If it fails here, fix retrieval/prompts before building anything below.*
4. **Stage 4 — breadth**: Confluence / Notion / Miro ingestion
5. **Stage 5 — properties & robustness**: conflict resolution, replay verification, V2 interface stubs, honest demo

---

*V1 = the de-scoped prototype: BA+SA, L2+L4 memory, human gate, ideation-tool ingestion.
Success = a senior architect accepts the SA's ADRs at ≥70%. Everything else is roadmap.*
