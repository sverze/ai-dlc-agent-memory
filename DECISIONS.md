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

## Open decisions (not yet settled — needed to start Stage 2)

- **OD1 — Graphiti entity/edge model.** Exact node and relationship shapes for requirements
  and ADRs in the temporal graph. **This is the Stage-2 entry blocker.** (PRD §15 Q2.)
- **OD2 — Graph backend.** Neo4j Community (spec default) vs. FalkorDB / Kuzu (lighter free
  alternatives). Default to Neo4j unless local footprint is a concern.
- **OD3 — Architect verdict capture.** Langfuse annotations vs. a separate review sheet
  feeding the eval log. (PRD §15 Q4 — resolve at Stage 3.)
