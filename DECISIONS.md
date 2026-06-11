# Decision Log

Durable project memory. The rationale behind this project used to live only in chat
transcripts — and we nearly lost it. Settled decisions live here now, in version control,
so they survive any lost session. New decisions are appended; superseded ones are marked,
not deleted.

Format: each entry has a status, the decision, why, and a pointer to fuller detail in the
PRD/spec where one exists.

---

## D1 — Language & runtime: Python-first ✅ (supersedes the spec's TypeScript references)

**Decision.** The prototype is built in **Python 3.12+, managed with uv**. Not TypeScript/bun.

**Why.** The memory/agent/eval ecosystem (Graphiti, Mem0, DeepEval, RAGAS, LiteLLM) is
Python-native. Going Python-first removes the polyglot seam instead of bridging it with
sidecars. (PRD §9 — "Technology Stack (Confirmed)".)

**⚠️ Known stale docs.** The prototype spec (v1.1) predates this call and still says
"Scaffold TS project (bun)" (Build Sequence, Week 1) and lists TypeScript/bun in its
Technology Stack Summary. **The PRD and the actual code are authoritative; the spec's
language references are stale and should be corrected on its next revision.** Recorded here
so this isn't re-litigated.

---

## D2 — Orchestrator: deterministic FSM, not an agent ✅

**Decision.** A finite-state machine is the **sole executor** of state transitions. Agents
only *propose* transitions; the FSM validates against a whitelist and executes. Hand-rolled
(no agent-orchestration framework). If a graph library is ever used, only its deterministic
graph/state primitives — never autonomous routing.

**Why.** Determinism and auditability are load-bearing requirements (NFR1). An agent that
decides its own control flow is neither replayable nor auditable. (Spec Q1; implemented in
`src/agentic_memory/fsm.py`.)

---

## D3 — Memory writes: append-only with async validation ✅

**Decision.** All writes to shared memory are **append-only, attributed, and timestamped**.
A `canonical` flag is promoted only by orchestrator validation, never by the writing agent
directly. State is reconstructed by replaying the append-only event log.

**Why.** Append-only is the only write model that is both replayable and conflict-safe
without locks. (Spec Q2; envelope is `KnowledgeEntry` in `artifacts.py`; ground-truth log
is `events.py`.)

---

## D4 — Typed artifact hand-offs, no prose ✅

**Decision.** Agents exchange **typed Pydantic artifacts** (`RequirementsArtifact`, `ADR`),
never prose. The eval rubric is encoded in the types: `RequirementTrace` makes traceability
and omission measurable; `AddedConstraint` forces architect-added constraints to be labelled
and justified.

**Why.** "Faithful transformation" must be structurally checkable, not a matter of opinion.
(PRD FR4; implemented in `artifacts.py`, incl. `ADR.omitted_requirement_ids()`.)

---

## D5 — Conflict resolution: role hierarchy + temporal recency ✅

**Decision.** Conflicts resolve deterministically by **role hierarchy first, temporal
recency as tiebreaker**. (Build target: Stage 5 / Week 3.)

**Why.** Deterministic resolution keeps the system replayable; a confidence-scored model is
deferred to V2 (needs ~200 scored scenarios to calibrate). (Spec Q3.)

---

## D6 — Tool integration: direct API to the gate, MCP for breadth ✅

**Decision.** JIRA is integrated via **direct API behind a `ToolAdapter`** interface to
reach the hypothesis gate fastest. Confluence/Notion/Miro come **post-gate via MCP**.

**Why.** One tool, direct, is the shortest path to proving the core loop. Breadth is a
Week-2 stretch, not a gate. (Spec Q4.)

---

## D7 — Success gate: the human architect is primary ✅

**Decision.** A senior architect's accept/revise/reject is **the** success metric:
**≥70% accept (lower 95% CI), <10% reject**. LLM judge and structured checks are *advisory*,
measured against the human verdict (Cohen's κ ≥ 0.6 before the judge is trusted at all) and
never allowed to override it.

**Why.** A same-family LLM judge grading same-family output is homework marking itself.
(PRD §5; spec Instrumentation.)

---

## D8 — Model selection: hardcoded per role, router-ready ✅

**Decision.** One model **hardcoded per role** (BA = Gemini Flash, SA = Claude Sonnet)
behind a thin `ModelClient` interface. No LiteLLM/routing in V1.

**Why.** Hardcoding removes a whole tuning surface while proving the loop; the interface
keeps V2 routing a drop-in. (PRD FR12; spec Q6 — design approved, build deferred to V2.)

---

## D9 — Data residency: anonymized & frozen for the prototype ✅

**Decision.** V1 runs on **anonymized, frozen scenario sets only**; nothing
client-identifying leaves the local perimeter. Self-hosted services (Neo4j, Langfuse).

**Why.** The gate is only as credible as an externally-authored, frozen eval set; real data
is a production concern. (Spec Q5; PRD NFR2.)

---

## D10 — Graphiti entity/edge model: structured-first ✅ (resolves OD1)

**Decision.** Graph facts that originate in a typed artifact are written **deterministically
from the Pydantic objects** — no LLM extraction in the loop. Graphiti's LLM extraction is
reserved for free-text we don't pre-structure (raw ticket prose, clarification answers).
Node types: `Ticket`, `Requirement`, `AcceptanceCriterion`, `KeyFact`, `Clarification`,
`ADR`, `AddedConstraint`. Edges: `DERIVED_FROM`, `VALIDATES`, `STATED_IN`, `ASKED_ABOUT`,
`ANSWERED_BY`, `ADDRESSES`, `DEFERS`, `ADDS`, `SUPERSEDES`. The `ADDRESSES`/`DEFERS` edges
are the graph projection of `RequirementTrace`, so omission and memory-hit-rate are graph
queries, not bespoke bookkeeping.

**Why.** Determinism is load-bearing (D2 / NFR1). Extraction over already-structured data
adds non-determinism for no gain and would conflate extraction misses with retrieval misses
in the metrics. (Full proposal: `Plans/graphiti-entity-edge-model.md`, OC1.)

**Resolved sub-choices:** OC2 → **Kuzu (embedded) for local dev, Neo4j for shared/demo**.
OC3 → **one graph namespace (`group_id`) per run** for V1; cross-run memory is a V2 episodic
concern. OC4 → **key facts are nodes** (directly queryable for the ≥90% hit-rate metric).

---

## D11 — Offline-first: a fake behind every external boundary ✅

**Decision.** Every external dependency (LLM provider, graph backend, and later the JIRA tool)
is reached through an **interface with a deterministic in-process fake**: `ModelClient` /
`FakeModelClient`, `MemoryStore` / `InMemoryMemoryStore`. Agent and loop code depend only on
the interfaces. Going live = implementing the same interface with a real backend; no caller
changes.

**Why.** It lets the entire core-hypothesis loop be built and **fully tested with zero services
and zero API spend**, keeps tests deterministic (NFR1), and makes the integration points
explicit and swappable (NFR5). The whole BA→SA roundtrip is exercised in `test_loop.py` this way.

**How to apply.** New external dependency → define its interface + a fake **first**, write the
logic against the interface, then add the real implementation as a separate class. Reuse the
existing offline tests to validate the real implementation.

---

## D12 — Agent / loop contract ✅

**Decision.** Separation of responsibility in the loop:
- **Agents** (`BAAgent`, `SAAgent`) build prompts, call their bound model, parse the typed
  response, and own **their** writes to shared memory.
- **`run_loop`** drives the FSM: it reads state, lets the agent act, and submits a
  `TransitionProposal`; the **FSM alone** executes/rejects/forces transitions (consistent with D2).
- **Model wire contract:** the BA model returns `RequirementsArtifact` JSON; the SA model returns
  `SAResponse` JSON — either `clarifications[]` (→ negotiation) or a full `ADR` (→ decision).
  This contract is the integration point for real provider clients.

**Why.** Keeps the deterministic executor (FSM) separate from non-deterministic actors (agents),
and fixes a stable, typed boundary so real LLM clients are a drop-in. (Implemented in
`agents.py` / `loop.py`.)

---

## D13 — Real `ModelClient` clients implemented; seam proven, terminal loop deferred ✅ (integration swap #1)

**Decision.** Implemented the real provider clients behind the `ModelClient` seam (D8/D11):
`AnthropicModelClient` (SA → `claude-sonnet-4-6`), `GeminiModelClient` (BA →
`gemini-2.5-flash`, via the unified `google-genai` SDK), and a `RoutingModelClient` +
`make_model_client()` factory that is a drop-in for `FakeModelClient`. SDKs live in an
**optional `live` extra** (`uv sync --extra live`), imported **lazily** so the offline path
(43-test suite) needs nothing installed. Keys come from env only; never logged. The seam is
**proven by gated live smoke tests** — one real call per provider asserting non-empty text,
correct model id, and real (non-zero) token usage. `agents.py` / `loop.py` kept at **zero diff**.

**The two-layer finding (why the *full* loop isn't green yet).** Running the real `run_loop`
end-to-end surfaced two distinct gaps the `FakeModelClient` had masked:
1. **Markdown fences** — real models wrap JSON in ```` ```json … ``` ````. **Fixed** in the
   client (`_strip_code_fence`, applied to both providers) — the right layer, since the seam
   carries no per-call format hint and the BA makes mixed JSON/free-text calls.
2. **Schema non-conformance** — real Gemini emits JSON that doesn't match `RequirementsArtifact`
   (omits required `source_ticket_id` / `title` / `summary`; `priority="Unspecified"` vs the
   `must/should/could/wont` enum), because `BA_SYSTEM` *names* the schema without *including* it.
   This needs the schema **in the prompt** (agents.py) or `response_schema`/tool-use threaded
   through the seam — **both touch surfaces frozen for this swap.**

**Why ship now (vs. expanding scope).** Swap #1's deliverable is the **client seam**, and that
is proven. Layer 2 is a genuine `ISC-24 (loop works)` vs `ISC-27 (agents.py frozen)` contradiction
that is **not the model-client's concern** — it is agent-prompt / structured-output work. Bundling
it would dilute a clean, surgical swap and silently change a stated anti-criterion. So the full
real-model terminal loop becomes the **explicit next increment** ("swap #1.5 — real-model
structured output"); the live loop test (`test_live_loop_reaches_terminal`) is marked `xfail`
documenting the target. (Decision made by the principal after advisor escalation of the contradiction.)

**Gotcha.** Run live tests with `uv run --extra live python -m pytest -m live` — the bare `pytest`
console script resolves to an interpreter without the `live` extra and the SDK imports fail.

---

## D14 — Real-model structured output: schema-in-prompt, derived from the types ✅ (resolves OD4, swap #1.5)

**Decision.** Real models are made schema-conformant by **injecting the artifact JSON schema
into the per-call prompt**, where the schema text is **generated from the Pydantic classes**
(`model_json_schema()`) by `_schema_block()` in `agents.py` — never hand-written, so prompt and
code cannot drift. The schema rides the *per-call* user prompt (BA intake → `RequirementsArtifact`,
SA analyze → `SAResponse`), **not** the persona system header, because the BA also answers
clarifications as free text and a blanket JSON-only rule would corrupt those calls.
Provider-native structured output (Gemini `response_schema`, Anthropic tool-use) was considered
and **deferred**: it requires threading a format hint through the frozen `complete()` seam — a
v2 router-era change (D8).

**Result.** The real-model loop now completes end-to-end: `test_live_loop_reaches_terminal` is a
normal passing live test (xfail removed), and `scripts/live_demo.py` shows the full quantifiable
surface in one command — input ticket → validated `RequirementsArtifact` → FSM path → ADR with
traces and labelled architect-added constraints → omission check → **real token usage per call**
(FR10). Reference run: 2 calls, ~4.7k tokens, ~58s wall, omissions NONE.

**Why.** Smallest change that closes the conformance gap (D13's layer 2), keeps the seam frozen,
keeps determinism boundaries intact (prompts are still pure strings), and makes the fidelity the
Stage-3 gate measures (D7) observable *now* rather than after Graphiti/JIRA land.

**Honest limits (state them, don't gloss them).**
- **Schema-in-prompt is best-effort, not enforced.** A model can still emit a near-miss on any
  given call; conformance is a *rate*, measured — `scripts/live_demo.py --runs N` exists exactly
  for this (reference: 3/3 terminal, 0 omissions, mean ≈4.6k tokens/run, ≈55s/run). The enforced
  path (provider-native `response_schema` / tool-use) remains the v2 upgrade.
- **Extraction tolerance lives in the *client*, not the agents:** `_strip_code_fence` (D13)
  normalizes whole-response markdown fences. `agents.py` stays prompt-string-only; parsing is
  still bare `model_validate_json`. A schema-parse failure surfaces as a counted ❌ in the demo's
  reliability table, not a silent fallback.
- **The schema costs tokens on every call** (it dominates BA intake input). The demo's usage
  readout includes this overhead by design — it is part of the real cost surface FR10 measures.
- Temperature is pinned at the seam default (0.0) for all loop calls.

---

## Open decisions

- **OD2 — Graph backend** — *partially resolved by D10/OC2* (Kuzu local, Neo4j shared);
  confirm once `graphiti-core` backend support is verified against the real library.
- **OD3 — Architect verdict capture.** Langfuse annotations vs. a separate review sheet
  feeding the eval log. (PRD §15 Q4 — resolve at Stage 3.)
