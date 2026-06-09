# Proposal — Graphiti entity/edge model (resolves OD1)

**Status: ✅ ACCEPTED (2026-06-09) → DECISIONS.md D10.** OC1 = structured-first, OC2 = Kuzu
local / Neo4j shared, OC3 = per-run namespace, OC4 = key facts as nodes. The node/edge model is
implemented in `src/agentic_memory/graph.py` and exercised by `tests/test_graph.py`; this
document is retained as the design rationale. A real `GraphitiMemoryStore` against `graphiti-core`
is the remaining build step (see README → Continuing this work).

> Confidence note: the *domain* model below is grounded in our own artifacts
> (`artifacts.py`) and is high-confidence. The exact Graphiti API surface (custom
> entity/edge classes, episode ingestion signatures) is described at design level and will
> be pinned against the real library when we add the `graphiti-core` dependency in Stage 2.

---

## 1. What Graphiti gives us

Graphiti is a **bi-temporal knowledge graph**: every node and edge records both *event time*
(when the fact was true) and *ingestion time* (when we learned it). You feed it **episodes**
(a chunk of text, or structured JSON); it extracts/links **entities** (nodes) and **facts**
(edges). You can define **custom entity and edge types as Pydantic models** so extraction
targets *our* schema instead of generic ones, and query by semantic + keyword + graph search.

This maps cleanly onto our needs: attribution (`author`), timestamps, a `canonical` flag, and
`supersedes` are all already fields on our `KnowledgeEntry` envelope — Graphiti's temporal
model is the natural home for them.

## 2. The core design fork (needs your call)

**How much do we let Graphiti's LLM *infer* vs. write structured facts deterministically?**

- **Option A — Structured-first (recommended).** For everything that originates in a typed
  artifact (`RequirementsArtifact`, `ADR`), we write the nodes/edges *explicitly* from the
  Pydantic objects — no LLM extraction in the loop. We use Graphiti's LLM extraction *only*
  for free-text we don't pre-structure (raw ticket prose, clarification answers).
  - *Why:* determinism is load-bearing (D2 / NFR1; "event logs replay to identical state").
    LLM extraction over already-structured data adds a non-deterministic step for no gain,
    and would muddy the memory-hit-rate metric (we couldn't tell extraction misses from
    retrieval misses).
- **Option B — Extraction-first.** Hand Graphiti the artifact as an episode and let it
  extract entities/edges. Less code, more "graphiti-native", but non-deterministic and
  harder to audit.

**Recommendation: A.** It keeps the substrate deterministic and makes the ≥90% memory-hit /
<5% omission metrics measure *retrieval*, which is the actual hypothesis — not extraction luck.

## 3. Proposed node types

| Node | Origin | Key attributes (beyond Graphiti's temporal fields) |
|------|--------|----------------------------------------------------|
| `Ticket` | JIRA via ToolAdapter | `source_ticket_id`, `title`, `summary` |
| `Requirement` | BA → `Requirement` | `req_id` (our `r-…`), `text`, `priority`, `source_ref` |
| `AcceptanceCriterion` | BA → `AcceptanceCriterion` | `ac_id`, `text`, optional `given/when/then` |
| `KeyFact` | BA → `key_facts[]` | `text` — **the unit the memory-hit-rate metric checks for retrievability** |
| `Clarification` | SA↔BA negotiation | `question`, `answer?`, `round` |
| `ADR` | SA → `ADR` | `adr_id`, `title`, `status`, `decision`, `rationale` |
| `AddedConstraint` | SA → `AddedConstraint` | `text`, `justification`, `origin="architect-added"` |

Every node carries `author` (AgentPersona), `created_at`, and a `canonical` flag (promoted only
by orchestrator validation, never by the writing agent — D3).

## 4. Proposed edge types (facts)

```
Requirement        --DERIVED_FROM-->        Ticket
AcceptanceCriterion --VALIDATES-->          Requirement
KeyFact            --STATED_IN-->           Ticket
Clarification      --ASKED_ABOUT-->         Requirement     (author = SA)
Clarification      --ANSWERED_BY-->         Requirement     (author = BA; sets answer + round)
ADR                --ADDRESSES-->           Requirement     {how: str}            ← traceability
ADR                --DEFERS-->              Requirement     {deferred_reason: str} ← legitimate non-omission
ADR                --ADDS-->                AddedConstraint
ADR                --SUPERSEDES-->          ADR             (temporal revision)
```

The `ADDRESSES` / `DEFERS` edges are the graph projection of `RequirementTrace`. With them, the
two headline metrics become **graph queries**, not bespoke bookkeeping:

- **Omission (<5%):** `Requirement` nodes for a ticket with **no** inbound `ADDRESSES` *and* no
  `DEFERS` edge from the ADR = silently dropped. (Mirrors `ADR.omitted_requirement_ids()`.)
- **Memory hit rate (≥90%):** every `KeyFact` node for the ticket is retrievable in the SA's
  query result.

## 5. How a run writes to the graph (Option A)

1. **intake** — BA writes `Ticket`, `Requirement[]`, `AcceptanceCriterion[]`, `KeyFact[]`
   nodes + `DERIVED_FROM` / `VALIDATES` / `STATED_IN` edges, all attributed, non-canonical.
2. **analysis ⇄ clarification** — each round writes a `Clarification` node + `ASKED_ABOUT`
   then `ANSWERED_BY` edges (one episode per round → one event-log row, matching the FSM).
3. **decision** — SA writes the `ADR` node, `ADDRESSES`/`DEFERS` edges per requirement, and
   `ADDS` edges for constraints; orchestrator validation promotes the ADR to `canonical=true`.

## 6. Open choices for you (sign-off)

- **OC1 — The fork in §2:** confirm Option A (structured-first, recommended) vs B.
- **OC2 — Backend (OD2):** Neo4j Community (spec default) vs. Kuzu (embedded, no Docker —
  lightest for local dev). Recommendation: **Kuzu for local dev, Neo4j for the shared/demo
  env** if Graphiti supports both cleanly; otherwise Neo4j.
- **OC3 — Group/namespace scope:** one Graphiti `group_id` per ticket/run (clean isolation,
  easy replay) vs. one shared graph across runs (enables cross-run memory but muddies the
  per-run metrics). Recommendation: **per-run group_id for V1**; cross-run is a V2 episodic
  concern.
- **OC4 — `KeyFact` as nodes vs. attributes:** nodes (recommended — directly queryable for the
  hit-rate metric) vs. a list attribute on `Ticket` (less granular).

## 7. If approved → next build steps

1. Add `graphiti-core` + backend driver to `pyproject.toml`; pin in `uv.lock`.
2. `docker-compose.yml` for the chosen backend (+ Langfuse later).
3. `src/agentic_memory/graph.py` — a `MemoryStore` interface wrapping Graphiti, with the
   node/edge types above as Pydantic models, and an in-memory fake (mirroring `FakeModelClient`)
   so the agent loop is testable offline before any Docker is up.
4. Wire BA/SA agents to write/read through `MemoryStore`.
