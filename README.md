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

## Current status — Stage 1 (substrate) complete

What's built and tested today is the **deterministic substrate** the agent loop will run on.
No agents, no Graphiti, no LLM calls yet.

| Module | What it provides | Status |
|--------|------------------|--------|
| `src/agentic_memory/artifacts.py` | Typed data contracts: `RequirementsArtifact`, `ADR` (with `RequirementTrace` / `AddedConstraint` encoding the eval rubric), `KnowledgeEntry` write envelope | ✅ Done |
| `src/agentic_memory/events.py` | Append-only JSONL `EventLog` with monotonic sequence numbers + `replay()` reducer | ✅ Done |
| `src/agentic_memory/fsm.py` | `FSM` orchestrator: `intake → analysis ⇄ clarification → decision (+ escalation)`, whitelist transitions, clarify-round cap with forced escalation, `replay_final_state()` | ✅ Done |
| `src/agentic_memory/models.py` | `ModelClient` seam (one model hardcoded per role, router-ready) + offline `FakeModelClient` for tests/local dev. No real provider calls yet. | ✅ Seam done (Stage 2) |
| `src/agentic_memory/graph.py` | L4 `MemoryStore` seam over Graphiti: node/edge types from our artifacts (D10), domain writes (`write_requirements`/`write_adr`), and omission + key-fact queries. Offline `InMemoryMemoryStore` fake; real Graphiti backend pending services. | ✅ Seam done (Stage 2) |

`37 passed` — `tests/test_{artifacts,events,fsm,models,graph}.py`. Decisions are logged in [`DECISIONS.md`](DECISIONS.md).

> The structural omission check already lives in the type system:
> `ADR.omitted_requirement_ids(artifact)` returns any source requirement that is neither
> addressed nor explicitly deferred — i.e. silently dropped in transit.

## Getting started

Requires **Python 3.12+** and [**uv**](https://docs.astral.sh/uv/).

```bash
# install deps (creates .venv from the committed uv.lock)
uv sync

# run the tests
uv run pytest
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
├── src/agentic_memory/      # the package (substrate)
│   ├── artifacts.py         # typed hand-offs (Pydantic v2)
│   ├── events.py            # append-only event log + replay
│   └── fsm.py               # deterministic orchestrator
├── tests/                   # pytest suite (16 tests)
├── Plans/                   # build planning (empty placeholder)
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

## Roadmap (build in dependency order, no calendar)

1. **Stage 1 — substrate** ✅ artifacts, event log, FSM
2. **Stage 2 — the core loop**: Graphiti+Neo4j, BA agent (JIRA→artifact→graph), SA agent (graph→ADR), wire the FSM negotiation loop, `ModelClient` per role
3. **Stage 3 — make it visible, then judge it** ← **HYPOTHESIS GATE**: OTel→Langfuse, example tickets, architect verdict, advisory eval + κ. *If it fails here, fix retrieval/prompts before building anything below.*
4. **Stage 4 — breadth**: Confluence / Notion / Miro ingestion
5. **Stage 5 — properties & robustness**: conflict resolution, replay verification, V2 interface stubs, honest demo

---

*V1 = the de-scoped prototype: BA+SA, L2+L4 memory, human gate, ideation-tool ingestion.
Success = a senior architect accepts the SA's ADRs at ≥70%. Everything else is roadmap.*
