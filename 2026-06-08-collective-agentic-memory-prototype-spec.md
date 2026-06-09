# Collective Agentic Memory — Prototype Specification

**Date:** 2026-06-08
**Status:** Draft v1.1 — revised after independent adversarial review
**Precursor:** `2026-06-08-collective-agentic-memory-research.md`
**Source:** Council debate (5 agents — Distributed Systems Architect, Principal Engineer, Security/Compliance Architect, Product Engineer, Knowledge Systems Researcher), revised per independent review council (scope-cutter, memory-research scientist, delivery lead, contrarian, LLMOps engineer)
**Destination:** Prosperity / AI DLC prototype

> ⚠️ **Superseded language (noted 2026-06-09).** This spec predates the confirmed **Python-first**
> decision (PRD §9, DECISIONS.md **D1**) and still says "Scaffold TS project (bun)" (Build
> Sequence) and lists TypeScript/bun in the Technology Stack Summary. **The PRD and the code are
> authoritative — the implementation is Python (uv/Pydantic/pytest).** Read the language/runtime
> references here as historical. Everything else (architecture, FSM, memory model, gate, metrics)
> stands and has been implemented as specified.

---

## Revision Note (v1.1 — Independent Review Response)

An independent council reviewed v1.0 and returned a verdict of **"not ready to build — revise first."** Five P0 changes were applied:

1. **De-scoped to two memory layers.** The prototype now builds only L2 (Working / structured handoffs) and L4 (Semantic / Graphiti). Persona memory (Mem0/L1), Skill Registry (L3), episodic memory (Zep/L5) and LLM routing are **documented as v2, not built** — they are not on the critical path for the one thing the prototype must prove.
2. **Human acceptance is now the halt-gate.** The LLM-as-judge ≥80% gate is demoted to a supporting signal. The real gate is a senior architect's accept/reject on anonymized real tickets.
3. **Fidelity rubric split.** The old rubric penalised the SA for adding constraints — i.e. it punished the exact transformation that makes architecture valuable. The rubric now separates *traceability* (did the ADR address the requirement?) from *omission* (did it drop something?), and treats justified new constraints as a positive, not a hallucination.
4. **Evaluation scenarios externally authored and frozen.** Scenarios are derived from anonymized real tickets, written by someone who is not building the agents, and frozen before Week 1. No grading homework set by the same people who wrote it.
5. **FSM now models the BA↔SA negotiation loop.** The old linear `intake→analysis→decision` modelled away the actual hard problem. A `clarification` state and an analysis↔clarification loop are added.

The cheap risk-reducers from v1.0 are retained: FSM orchestrator, ToolAdapter interface, append-only event log.

---

## Architectural Decisions (Council Resolved)

### Q1 — Orchestrator: FSM, not agent ✅

The orchestrator is a **finite state machine with a suggestion queue**. Agents never directly execute state transitions — they propose them. The FSM is the sole executor.

**Rationale:** An agent orchestrator with its own memory creates a non-deterministic second brain. No audit trail, no replay, no deterministic failure analysis. FSM states are enumerable, transitions are observable, and failure modes are diagnosable without re-running inference.

**Suggestion queue pattern:**
```
Agent → proposes: { from: "intake", to: "analysis", reason: "...", confidence: 0.87 }
FSM validates preconditions → executes OR rejects with reason
All transitions logged to immutable event log
```

### Q2 — Memory write authority: Append-only with async validation ✅

All agents can write to the shared knowledge graph. Writes are **append-only, always attributed, always timestamped**. The orchestrator runs async validation and promotes facts to `canonical: true` status. Downstream agents may consume all facts but must filter on `canonical` for authoritative lookups.

**Schema contract:**
```typescript
interface KnowledgeEntry {
  id: string
  author: AgentPersona          // "business-analyst" | "solution-architect" | ...
  timestamp: ISO8601
  content: string
  entities: string[]
  canonical: boolean            // set by orchestrator validation only
  confidence?: number           // optional in v1, reserved for v2 resolution logic
  supersedes?: string           // id of entry this replaces
}
```

**Rationale:** Never blocking agents on write (throughput). Validation async (consistency). Attribution mandatory (conflict resolution and audit).

### Q3 — Conflict resolution: Role hierarchy + temporal recency ✅

| Domain | Authority |
|--------|-----------|
| Architecture / technology decisions | Solution Architect > Business Analyst |
| Acceptance criteria / requirements | Business Analyst > Solution Architect |
| Security findings | Security Engineer > all others |
| Test coverage / quality gates | QA Engineer > all others |
| Incident / operational state | Ops agent (ServiceNow) > all others |

**Tiebreaker within same role domain:** most recent timestamp wins.

**Confidence scoring:** Added as optional schema field in v1. Resolution logic ignores it until v2, when calibration data exists to make it meaningful.

**Human escalation:** Always available. Any agent can flag a conflict for human review. All escalations audit-logged with the conflicting entries attached.

### Q4 — Tool integration: Direct API for prototype, MCP for v1.1 ✅

Prototype uses direct API calls to JIRA (and JIRA only). MCP server pattern is the v1.1 migration target once the memory patterns are proven.

**Rationale:** MCP wins at swarm scale (write once, all agents reuse). But it costs setup time the prototype cannot afford. Direct API ships faster; the learning from the prototype directly justifies the migration work.

**Migration contract:** All tool-call code must be isolated behind a thin adapter interface from day one. The adapter swaps from direct API to MCP without changing agent code.

```typescript
interface ToolAdapter {
  getTicket(id: string): Promise<Ticket>
  searchTickets(query: TicketQuery): Promise<Ticket[]>
  getADR(id: string): Promise<ADR>
  // etc.
}
// v0: JiraDirectAdapter implements ToolAdapter
// v1.1: JiraMCPAdapter implements ToolAdapter
```

### Q6 — LLM Routing: Three-layer stack, FSM-managed — DESIGN APPROVED, BUILD DEFERRED TO v2 ⏸️

> **v1.1 review change:** Routing is sound design but it is **not on the critical path** for proving semantic roundtrip fidelity. Building LiteLLM + a model registry + complexity escalation in the prototype adds a sixth library and a tuning surface that contributes nothing to the halt-gate. **The prototype hardcodes one model per agent role** (BA → Gemini Flash, SA → Sonnet). The three-layer design below is the v2 target, documented now so the prototype's model calls are written behind a thin interface that the router can later own.

The FSM is the authority on model assignment. Agents do not select their own model — the orchestrator resolves it at task dispatch using a three-layer stack.

**Layer 1 — Sensitivity gate (deterministic, zero LLM calls):**
At task creation, if `data_classification = SENSITIVE` → force local Ollama/Llama. No cloud inference. No exceptions.

**Layer 2 — Role-based registry (config-driven):**
A versioned YAML model registry keyed by `agent_role + task_type`. This is the source of truth for model assignment. It evolves as evidence accumulates from production signal.

```yaml
routes:
  - role: business-analyst
    task: requirement-extraction
    model: gemini/gemini-2.0-flash
    fallback: claude-haiku-4-5
  - role: solution-architect
    task: adr-generation
    model: claude-sonnet-4-6
    fallback: gemini/gemini-2.5-pro
  - role: orchestrator
    task: plan-decompose
    model: claude-opus-4-8
    fallback: claude-sonnet-4-6
sensitivity_gate:
  HIGH: ollama/llama3
  MEDIUM: inherit_role_default
  LOW: inherit_role_default
```

**Layer 3 — Complexity escalation (runtime, <1ms):**
LiteLLM Complexity Router scores the incoming task. If `COMPLEX` is detected regardless of role default, escalate one tier. This handles edge cases like an unusually ambiguous JIRA ticket routing to the BA agent.

**LiteLLM as unified proxy:** All agent LLM calls route through LiteLLM. It provides a single OpenAI-compatible interface across Anthropic, Google, and Ollama — fallbacks, retries, and spend tracking unified.

### Q5 — Data residency: Self-hosted for production, managed for prototype only ✅

| Environment | Graphiti | Mem0 | Episodic (Zep preferred over Hindsight) |
|-------------|----------|------|----------------------------------------|
| **Prototype** | Managed (Docker local or cloud) | Managed (mem0.ai) | Zep managed |
| **Production** | Self-hosted (Docker/K8s) | Self-hosted | Zep self-hosted |

**Hard rule:** Prototype uses **synthetic data only** — fake JIRA tickets, fictional ADRs, no real delivery IP. Migration path to self-hosted must be documented before any real enterprise data is introduced.

**Why Zep over Hindsight for episodic:** Zep is faster to stand up, has a managed tier for prototype use, and has a clear self-hosted path. Hindsight (MIT) remains an option for pure self-hosted production if licensing becomes a factor.

---

## Minimum Viable Prototype

### Scope

Two agents. Two memory layers (L2 + L4). One tool to the gate, three more after it. FSM with a negotiation loop.

```
Agents:   Business Analyst + Solution Architect
Memory:   L2 Working (structured JSON handoffs) + L4 Semantic (Graphiti temporal graph)
Tools:    JIRA (direct API) to the fidelity gate;
          Confluence + Notion + Miro added AFTER the gate passes (all feed L4)
Observ.:  Langfuse self-hosted + OTel spans (human eval primary; LLM judge supporting)
FSM:      intake → analysis ⇄ clarification → decision  (+ escalation)
Log:      Immutable event log from day one (append-only JSONL)
Data:     Externally-authored, anonymized-real-ticket scenarios, frozen before Week 1
```

**Deferred to v2 — documented, not built in the prototype:**
- L1 Persona memory (Mem0) — add once roundtrip fidelity is proven
- L3 Skill Registry — procedural memory, highest-ROI but not gate-critical
- L5 Episodic memory (Zep) — the learning loop comes after the base loop works
- LLM routing (LiteLLM + registry + complexity escalation) — hardcode one model per role for now
- Figma — requires Dev seat budget and designer convention agreement

**Why de-scoped:** The prototype exists to prove one thing — semantic roundtrip fidelity through a shared graph, accepted by a human. Every other layer is a multiplier on a result we have not yet earned. Build the two layers the gate depends on; stub the interfaces for the rest.

### The Riskiest Assumption

**Semantic roundtrip fidelity — judged by a human, not a model.** Does the SA agent's architectural decision faithfully reflect the BA agent's requirement after it has passed through the shared graph — to the standard a senior architect would actually accept?

This is the single test the prototype must pass before anything else matters. If the retrieval or prompt design is broken, nothing downstream — persona memory, skill registries, episodic memory, conflict resolution — will work.

> **The frame the v1.0 rubric got wrong:** a requirement does not have a single frozen "ground truth" that must be reproduced. The SA's *job* is to transform requirements and add justified constraints. The gate must measure *faithful transformation*, not lossless copying. Penalising new constraints as "hallucination" punishes the exact behaviour that makes an architect valuable.

**Primary gate — human acceptance:**
- A senior solution architect (not on the build team) reviews each produced ADR against its source ticket and returns **accept / revise / reject**
- Target: **≥ 70% accept, < 10% reject** across the frozen scenario set
- This is the halt-gate. If it fails, halt and fix retrieval / prompt design before proceeding.

**Supporting signal — split rubric (LLM judge + structured checks, advisory only):**

*Traceability (is the requirement addressed?)*
1. Core requirement addressed by the decision (1pt)
2. Acceptance criteria reflected or explicitly deferred with reason (1pt)
3. Architectural decision traceable to a stated requirement (1pt)

*Omission & grounding (did it drop or fabricate?)*
4. No silent omission of a stated requirement (1pt)
5. New constraints are justified and labelled as architect-added, not attributed to the source (1pt)

Score 5/5 = strong, 4/5 = acceptable, ≤3 = review. **Justified new constraints score positively under #5** — they are the value-add, not a defect. The LLM-judge score is reported alongside the human verdict to measure how well the cheap signal predicts the expensive one; it never overrides it.

---

## System Design

### Component Map

```
┌──────────────────────────────────────────────────────────────────────┐
│                      FSM Orchestrator                                │
│  states: intake → analysis ⇄ clarification → decision (+ escalation)│
│  suggestion queue (async)  |  hardcoded model-per-role (v1)         │
│  immutable event log (JSONL append-only)                             │
└──────────┬───────────────────────────────┬───────────────────────────┘
           │                               │
  ┌────────▼──────────┐         ┌──────────▼──────────┐
  │    BA Agent        │◄───────►│    SA Agent          │
  │  reads: tools      │ clarify │  reads: Graphiti     │
  │  writes: Graphiti  │  loop   │  writes: Graphiti    │
  │  model: Gemini Flash│        │  model: Sonnet       │
  └────────┬───────────┘         └──────────┬───────────┘
           │                                │
           └────────────┬───────────────────┘
                        │  (v2: LiteLLM proxy owns model selection)
              ┌─────────▼──────────┐
              │     Graphiti       │
              │  temporal graph    │  ← L4 Semantic (prototype-critical)
              │  append-only writes│
              │  canonical flag    │
              │  async validation  │
              └─────────┬──────────┘
                        │
           ┌────────────┼─────────────────────┐
           │            │                     │
  ┌────────▼──────┐  ┌──▼──────────┐  ┌──────▼────────┐  ┌──────────────┐
  │ JIRA Adapter  │  │ Confluence  │  │ Notion Adapter │  │ Miro Adapter │
  │ direct API v0 │  │ mcp-atlassian│  │ official MCP  │  │ MCP + webhook│
  │ (to the gate) │  │ (post-gate)  │  │ (post-gate)   │  │ (post-gate)  │
  └───────────────┘  └─────────────┘  └───────────────┘  └──────────────┘

              ┌─────────────────────┐
              │  Langfuse (OTel)    │  ← all agent spans flow here
              │  HUMAN eval = gate  │    architect accept/reject is primary
              │  LLM judge = support │    DeepEval advisory only
              └─────────────────────┘

  Deferred to v2 (stubbed interfaces): Mem0 (L1) · Skill Registry (L3)
  · Zep episodic (L5) · LiteLLM routing
```

### FSM State Definitions

The hard problem in a BA→SA handoff is not the handoff — it is the **negotiation**. A real SA reads a requirement, finds it underspecified, and asks the BA to clarify before committing to a decision. A linear `intake→analysis→decision` models that away. v1.1 adds a `clarification` state and an `analysis ⇄ clarification` loop.

```typescript
type DLCState =
  | "intake"          // BA reads ticket, extracts requirements, writes to Graphiti
  | "analysis"        // SA reads from Graphiti, drafts ADR or raises a clarification
  | "clarification"   // SA has open questions; BA answers; loop back to analysis
  | "decision"        // SA commits ADR to Graphiti with canonical: true
  | "escalation"      // unresolved after N loops, or genuine conflict → human review

interface StateTransition {
  from: DLCState
  to: DLCState
  agent: AgentPersona
  reason: string
  confidence: number
  timestamp: ISO8601
}
```

**Negotiation loop rules:**
- From `analysis`, the SA may propose `→ clarification` (open questions exist) or `→ decision` (requirement is sufficient).
- `clarification → analysis` after the BA writes answers to Graphiti.
- **Loop cap:** after `MAX_CLARIFY_ROUNDS` (default 3) without reaching `decision`, the FSM forces `→ escalation`. This both prevents infinite loops and surfaces the cases where the requirement genuinely cannot be resolved agent-to-agent — which is itself a finding worth capturing.
- Every clarification round is a row in the event log. The number of rounds to reach `decision` is a first-class metric (see Instrumentation): a healthy system trends *down* over time as persona/episodic memory (v2) accumulates.

> **Persona memory (Mem0 / L1) is deferred to v2.** The schema below is retained as the v2 target so the agent code reserves a `persona` interface slot now and fills it later. In the prototype, persona context is a static, hand-written header per agent — no Mem0 dependency.

### Persona Memory Schema (Mem0) — v2 target

Each agent gets a dedicated Mem0 namespace. Bootstrapped with role knowledge; accumulates from runs.

**BA Agent memory examples:**
- "Project Alpha: core requirement is zero-downtime deploys"
- "Stakeholder Priya Singh: prefers acceptance criteria in Given/When/Then format"
- "JIRA tickets tagged #performance require Datadog SLO reference in ADR"

**SA Agent memory examples:**
- "Project Alpha: microservices pattern, no monolith changes approved"
- "GitLab CI pipeline uses shared runners — no GPU nodes available"
- "ADRs must reference the relevant Confluence decision log ID"

### Event Log Schema

```typescript
interface EventLogEntry {
  seq: number               // monotonic, never reused
  timestamp: ISO8601
  type: "fsm_transition" | "agent_write" | "validation" | "escalation" | "tool_call"
  agent?: AgentPersona
  state?: { from: DLCState; to: DLCState }
  payload: Record<string, unknown>
}
```

The event log is the ground truth. All other stores (Graphiti, and v2's Mem0/Zep) are derived from it and can be replayed.

---

## Instrumentation and Evaluation Harness

> **v1.1 review change — the human is the gate.** v1.0 made an LLM judge the arbiter of success, with the judge drawn from the same model family that produced the output. That is homework marking itself. v1.1 inverts it: a senior architect's accept/reject is the gate; the LLM judge and structured checks are *advisory signals whose only job is to predict the human verdict cheaply*. We measure that prediction quality explicitly (judge-vs-human agreement) before ever trusting the judge to stand alone.

### Eval Pipeline (runs after every scenario)

```
Scenario (externally authored from anonymized real ticket, frozen pre-Week-1)
    ↓
Agent pipeline runs — all spans emitted to Langfuse via OTel
    ↓
Graphiti write — post-write entity assertion (memory hit rate)
    ↓
SA Agent produces ADR (possibly after N clarification rounds)
    ↓
PRIMARY GATE — human architect: accept / revise / reject  ← the verdict that counts
    ↓
SUPPORTING SIGNALS (advisory, DeepEval — never override the human):
  1. Schema validator   — ADR has all required sections
  2. LLM judge (split)  — traceability score + omission/grounding score
  3. Grounding check    — claims attributed to source vs. labelled architect-added
  4. Memory fidelity    — cosine(input key facts, Graphiti-retrieved entities)
    ↓
Both human verdict and machine scores → eval log → Langfuse dashboard
    ↓
Track judge-vs-human agreement (Cohen's κ) — the meta-metric
```

### Metrics Tracked per Run

Report every rate with a **95% confidence interval** (Wilson). 20 scenarios is a small n — a point estimate without error bars is misleading. The targets below are lower-CI-bound targets, not point estimates.

| Metric | Definition (precise) | Target | Halt threshold |
|--------|---------------------|--------|----------------|
| **Architect acceptance rate** | % of ADRs marked `accept` by the human reviewer | ≥ 70% (lower CI bound) | < 50% → halt, redesign |
| **Architect reject rate** | % marked `reject` (not merely `revise`) | < 10% | > 20% → halt |
| Judge-vs-human agreement | Cohen's κ between LLM-judge accept/reject and human | report; aim κ ≥ 0.6 | κ < 0.4 → judge is noise, ignore it |
| Memory hit rate (Graphiti) | A "hit" = a pre-tagged key fact from the source ticket is retrievable as a Graphiti entity in the SA's query result. "Miss" = absent or not retrieved. Key facts are tagged in the frozen scenario set. | ≥ 90% | < 80% → fix write/read path |
| Clarification rounds to decision | # of analysis⇄clarification loops before `decision` | report; expect to fall in v2 | hitting MAX_CLARIFY every time → requirements too thin or SA prompt broken |
| Token efficiency | Total tokens across all agent hops per accepted ADR | baseline Week 1 | > 2× baseline → investigate |
| Latency per FSM hop | Wall-clock per state transition (OTel span) | baseline Week 1 | > 3× baseline → investigate |
| Task completion rate | % of scenarios reaching `decision` or a *legitimate* `escalation` | 100% (escalation counts as completion) | crashes/hangs → fix FSM |
| Omission rate | % of ADRs that silently drop a tagged source requirement (rubric #4 fail) | < 5% | > 15% → halt, fix retrieval |
| Call graph stability | Jaccard of agent-call sets across identical inputs | ≥ 0.8 | < 0.7 → non-determinism leak |

**Note on what is NOT a metric:** "no new constraints" is deliberately absent. Architect-added constraints are the value-add (rubric #5), not a defect to be minimised.

### LLM Judge Rules (advisory tier)

- The judge is **advisory until κ ≥ 0.6** against the human reviewer. Below that it is reported but not acted on.
- **Do not trust a same-family judge alone.** The judge is `claude-sonnet-4-6`, but a large fraction of ADRs are produced by Sonnet too — same-family grading inflates scores. Cross-check a 20% sample with a different-family judge (Gemini 2.5 Pro) and report the delta. If the families disagree materially, the human verdict settles it and the judge stays advisory.
- Judge prompts are versioned alongside code — changing a judge prompt invalidates historical comparisons.
- Silent semantic failure (plausible output, wrong meaning) is the primary failure mode — output presence is not a quality signal. This is *why* the human gate exists.

---

## Build Sequence

**Reframed for v1.1:** three weeks of *working* days, but de-scoped to two memory layers, one tool to the gate, and a human as the arbiter. The libraries cut (Mem0, Zep, LiteLLM, DeepEval-as-gate) are the ones that bought no signal toward the halt-gate. Note the explicit slack — the v1.0 plan had none, which the delivery reviewer flagged as the single most reliable predictor of a 3-week prototype becoming a 3-month one.

### Week 0 (pre-work, before the clock starts) — author and freeze the eval set

| Task | Done when |
|------|-----------|
| Source 15–20 real tickets from a delivery team; anonymize (strip names, IP, client refs) | Anonymized ticket set reviewed for leakage |
| A person **not on the build team** writes the scenario set + tags the key facts per ticket | Scenario set + key-fact tags committed and **frozen** (git tag) |
| Recruit the senior architect reviewer; align them on the accept/revise/reject rubric | Reviewer briefed; rubric agreed; calibration on 2 sample ADRs done |

> If Week 0 cannot happen (no access to real tickets, no external author, no architect), **say so now** — the prototype's gate is only as credible as this set, and that is the whole point.

### Week 1 — Skeleton + JIRA + the gate (prove roundtrip fidelity)

| Day | Task | Done when |
|-----|------|-----------|
| 1 | Scaffold TS project (bun), FSM stub (incl. clarification loop), event log writer | `bun test` passes, log writes JSONL |
| 1 | Stand up Graphiti (Docker) + Langfuse (self-hosted Docker) — **two services, not six** | Both ping; OTel span lands in Langfuse |
| 2 | BA agent: JIRA ToolAdapter (direct API), reads ticket, writes requirements to Graphiti. Model hardcoded (Gemini Flash). | One ticket → Graphiti requirements node |
| 2 | SA agent: reads Graphiti, drafts ADR OR raises clarification. Model hardcoded (Sonnet). | One node → one ADR or one clarification |
| 3 | Wire FSM: intake → analysis ⇄ clarification → decision (+ escalation, MAX_CLARIFY cap) | Full loop runs incl. at least one clarification round |
| 3 | Instrument all agent calls with OTel spans → Langfuse | Per-hop tokens + latency + clarify-rounds visible |
| 4 | Run the frozen scenario set; capture machine signals; produce ADRs for human review | All scenarios produce an ADR or legitimate escalation |
| 5 | **Human gate:** architect reviews every ADR accept/revise/reject; compute rates + CI + judge-vs-human κ | ≥ 70% accept (lower CI), < 10% reject — or halt and redesign |

### Week 2 — Tool breadth as L4 sources (only if Week 1 gate passed)

| Day | Task | Done when |
|-----|------|-----------|
| 6 | Confluence: mcp-atlassian (same package as JIRA), CQL extraction, polling sync to Graphiti | Confluence page → Graphiti entity |
| 7 | Notion: official MCP + webhook receiver (idempotency keys, dead-letter) → Graphiti | Notion change → Graphiti episode within 5s |
| 8 | Miro: MCP + webhook + **frame-based** extraction (require named frames; no spatial clustering) → Graphiti | Named Miro frame → Graphiti entities |
| 9 | Re-author a second frozen scenario slice that spans multiple tools (still external, still frozen) | Multi-tool scenario set committed |
| 10 | Re-run the gate on multi-tool scenarios | Acceptance rate holds vs. Week 1 (no regression) |

### Week 3 — Conflict, replay, demo (prove the properties, then show it)

| Day | Task | Done when |
|-----|------|-----------|
| 11 | Conflict resolution: inject contradictory facts, verify role-hierarchy + recency resolution deterministically | 100% of injected conflicts resolve as specified |
| 12 | FSM replay: replay event log → assert identical final state | Replay is bit-identical |
| 13 | Buffer / overflow day — absorb slippage from Weeks 1–2 (there will be some) | Plan back on track or scope re-cut explicitly |
| 14 | Document v2 deferrals as stubbed interfaces: Mem0 (L1), Skill Registry (L3), Zep (L5), LiteLLM routing | Interface stubs + v2 runbook written |
| 15 | Demo: 5 showcase scenarios, human verdicts + machine signals side by side, honest metric summary with CIs | Demo-ready artifact; results stated with error bars |

---

## Success Criteria

The gate is the first row. Everything below it is a supporting property — necessary, but it does not by itself mean the prototype succeeded. A prototype that scores perfectly on machine metrics and gets rejected by the architect has failed.

| Criterion | Target | Measured by |
|-----------|--------|-------------|
| **Architect acceptance rate (THE GATE)** | **≥ 70% accept (lower 95% CI), < 10% reject** | Senior architect, not on build team, on frozen scenarios |
| Judge-vs-human agreement | Cohen's κ ≥ 0.6 (else judge stays advisory) | κ over the scenario set |
| Memory hit rate | ≥ 90% of tagged key facts retrievable | Post-write Graphiti entity assertion vs. frozen tags |
| Omission rate | < 5% of ADRs silently drop a tagged requirement | Split-rubric check #4 |
| No-regression on tool breadth | Week 2 acceptance ≥ Week 1 acceptance | Re-run gate on multi-tool set |
| Conflict resolution determinism | 100% of injected conflicts resolve as specified | Test suite |
| Call graph stability | Jaccard ≥ 0.8 on identical inputs | MAESTRO methodology |
| FSM replay | All event logs replay to identical final state | Replay test |
| Eval-set integrity | Scenarios externally authored, frozen pre-Week-1, key facts tagged | Git tag + authorship audit |
| No real IP in external stores | Anonymized tickets only; nothing client-identifying leaves the perimeter | Data audit |

**Deliberately removed from v1.0's criteria:** "semantic preservation by LLM judge" as a gate (demoted to advisory), "episodic improvement" and "sensitivity gate enforcement" (both deferred to v2 with the layers they measure), and "all four tools" as a hard gate (tool breadth is a Week-2 stretch, not a pass/fail on the core hypothesis).

---

## Deferred to v2 — Layers Documented but Not Built in the Prototype

These are designed (see the research document) and have reserved interface slots in the prototype code, but they are off the critical path for the fidelity gate and are built only after it passes:

| Layer / capability | Why deferred | Re-introduce when |
|--------------------|--------------|-------------------|
| **L1 Persona memory (Mem0)** | Static hand-written persona headers suffice to test roundtrip fidelity | Gate passes; measure whether persona memory lifts acceptance rate |
| **L3 Skill Registry** | Highest long-term ROI but contributes nothing to the gate | After episodic loop; it needs accumulated run signal to be worth anything |
| **L5 Episodic memory (Zep)** | The learning loop only matters once the base loop works | Gate passes; measure clarification-rounds trending down |
| **LLM routing (LiteLLM + registry + complexity)** | One hardcoded model per role removes a whole tuning surface | After the gate; cost optimisation is meaningless on a system that doesn't yet work |

## Open Questions Deferred to v2

1. **Concurrent semantic writes at scale:** The suggestion queue defers the tension between agent write throughput and graph consistency. At >5 agents writing simultaneously, the async validation queue may become a bottleneck. This is the first v2 architectural question.

2. **Confidence scoring calibration:** Schema field reserved in v1. Needs ~200 scored scenarios before the calibration data is meaningful enough to influence conflict resolution.

3. **Model registry governance:** Who owns the registry update cadence? Anthropic and Google release model updates every 6–8 weeks. Needs a quarterly review process or automated benchmarking to prevent drift.

4. **Bandit-feedback router migration:** BaRP and PILOT (online learning routers that update routing rules from production signal) will replace the static YAML registry at scale. Watch for OSS maturity in 2026 Q3–Q4.

5. **Figma acceptance criteria conventions:** Requires agreement with design team on frame naming before automated extraction is reliable. Plan designer onboarding before v1.1.

6. **Miro spatial clustering:** DBSCAN on (x, y) coordinates for boards without frame structure. Deferred until frame-convention-based extraction is proven and the spatial case is well-understood.

7. **Skill Registry evolution:** At what size does YAML-per-persona need to migrate to vector-embedded retrieval? Hypothesis: ~50 skills per agent. Will validate during Week 3.

8. **GitLab, Wiz/Snyk, Datadog, ServiceNow integration:** Second-tier tools for CI/CD, security, observability, and ops personas. Sequenced after the ideation-layer tools (JIRA/Confluence/Notion/Miro) are proven in the prototype.

---

## Technology Stack Summary

| Component | Prototype (v1.1) | Production |
|-----------|------------------|------------|
| Language | TypeScript (bun) | TypeScript (bun) |
| FSM (incl. clarification loop) | Custom (xstate or hand-rolled) | Same |
| Event log | JSONL (append-only file) | JSONL → object store (S3/GCS) |
| Semantic graph (L4) | Graphiti (Docker) | Graphiti (self-hosted K8s) |
| **Eval — primary** | **Human architect accept/reject** | Human spot-check + calibrated judge |
| Eval — supporting | DeepEval split rubric + RAGAS (advisory) | Same + golden dataset (grows from runs) |
| Observability | Langfuse self-hosted (Docker) | Langfuse self-hosted |
| Tool: JIRA | Direct API behind ToolAdapter (to the gate) | mcp-atlassian |
| Tool: Confluence | mcp-atlassian polling (post-gate) | Same (self-hosted) |
| Tool: Notion | Official MCP + webhooks (post-gate) | Same |
| Tool: Miro | MCP + webhooks, frame-based (post-gate) | Same + spatial clustering |
| Model selection | **Hardcoded per role** (Gemini Flash / Sonnet) | LiteLLM proxy + registry + complexity router |
| Data | Anonymized real tickets, frozen scenario set | Real delivery data (post self-hosted migration) |
| *L1 Persona (Mem0)* | *Deferred to v2 — static headers* | Mem0 self-hosted |
| *L3 Skill Registry* | *Deferred to v2* | YAML → pgvector at ~50 skills/agent |
| *L5 Episodic (Zep)* | *Deferred to v2* | Zep self-hosted |
| *Tool: Figma* | *Deferred — Dev seat + convention* | Dev Mode MCP (requires Dev seats) |

---

## Appendix A — Setup & Procurement

### A.1 — API keys checklist (prototype only)

| Key | Used by | Where to get it | Cost |
|-----|---------|-----------------|------|
| `GOOGLE_API_KEY` | BA agent + Graphiti entity extraction | Google AI Studio | Free tier (Gemini Flash, daily rate limits) |
| `ANTHROPIC_API_KEY` | SA agent + LLM judge | console.anthropic.com | Pay-as-you-go (~single-digit $ at 20–40 scenarios) |
| `ATLASSIAN_API_TOKEN` | JIRA + Confluence (one token, both) | id.atlassian.com → API tokens | Free (Cloud free tier, ≤10 users) |
| `NOTION_API_TOKEN` | Notion integration | notion.so/my-integrations | Free plan + free API |
| `MIRO_API_TOKEN` | Miro boards | Miro dev portal | Free dev access |
| `OPENROUTER_API_KEY` *(optional)* | Cross-family judge (Gemini vs Claude) | openrouter.ai | Pay-as-you-go; used only for the 20% κ cross-check |

**Not needed in the prototype** (v2): Mem0, Zep/Hindsight, Pinecone, LiteLLM (no key — self-host), Figma (paid Dev seats), and all second-tier DLC tools (GitLab/Snyk/Datadog/New Relic/ServiceNow/Wiz).

### A.2 — `.env` template

```bash
# --- LLM providers ---
GOOGLE_API_KEY=                       # Gemini Flash — free tier
ANTHROPIC_API_KEY=                    # Claude Sonnet — pay-as-you-go
# OPENROUTER_API_KEY=                 # optional cross-family judge

# --- Graph backend (Neo4j Community, local) ---
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=change-me

# --- Graphiti (point extraction at Gemini to stay on free tier) ---
GRAPHITI_LLM_PROVIDER=google

# --- Observability (Langfuse self-hosted) ---
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=

# --- Tools ---
ATLASSIAN_URL=https://your-org.atlassian.net
ATLASSIAN_EMAIL=
ATLASSIAN_API_TOKEN=
NOTION_API_TOKEN=
MIRO_API_TOKEN=
```

### A.3 — Docker services (everything self-hosted is free)

| Service | Image | Purpose | Cost |
|---------|-------|---------|------|
| `neo4j` | `neo4j:community` | Graphiti's graph backend | Free (Community Edition) |
| `graphiti` | Graphiti server image / Python sidecar | L4 temporal graph | Free (OSS) |
| `langfuse` (+ `postgres` + `clickhouse`) | `langfuse/langfuse` | OTel traces, cost analytics | Free (self-host) |

The bespoke code (FSM, agents, ToolAdapters, event log) runs under **bun** — not containerized for the prototype. Free-tier alternatives if you'd rather not run Neo4j: **FalkorDB** or **Kuzu** (both free OSS Graphiti backends).

### A.4 — MCP servers

| MCP server | Covers | Source | License |
|-----------|--------|--------|---------|
| `sooperset/mcp-atlassian` | JIRA + Confluence | GitHub | OSS |
| Notion official MCP | Notion | developers.notion.com | First-party |
| `k-jarzyna/mcp-miro` | Miro | GitHub | OSS |

Note: per Q4, JIRA is reached via **direct API behind the ToolAdapter** to the fidelity gate; the MCP servers come in post-gate (Week 2) and at v1.1 for JIRA.

### A.5 — Cost summary

**Standing cost of the prototype: ~$0/month.** Everything self-hosted (Graphiti, Neo4j, Langfuse) and every tool (Atlassian/Notion/Miro free tiers) and Gemini (free tier) cost nothing. The only real spend is **Anthropic pay-as-you-go** for the SA agent and judge — single-digit dollars across the frozen scenario set. The unavoidable *future* costs, both correctly deferred: **Figma Dev seats** (~$12–15/seat/mo) and **Wiz** (enterprise contract, no free tier).

> Pricing and free-tier limits drift quarterly; verify live quotas before committing budget.

---

*Specification produced 2026-06-08 from Council debate (5 Q resolved) + Extensive research (routing, instrumentation, tool integrations). **Revised to v1.1** 2026-06-08 after an independent adversarial review council returned "not ready to build." Five P0 changes applied: de-scoped to L2+L4, human acceptance as the halt-gate, split fidelity rubric, externally-authored frozen scenarios, BA↔SA negotiation loop in the FSM. Riskiest assumption: semantic roundtrip fidelity, judged by a human, must clear the gate in Week 1 before any deferred layer is built. The one change that most increases success odds: the human-architect accept/reject gate replacing the self-graded LLM judge. Last updated: 2026-06-08.*
