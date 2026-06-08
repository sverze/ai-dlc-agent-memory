# PRD — Collective Agentic Memory, V1 (Prototype)

**Date:** 2026-06-08
**Status:** Draft v1.0 — for review
**Owner:** sverze
**Destination:** Prosperity / AI DLC
**Related:**
- Research — `2026-06-08-collective-agentic-memory-research.md`
- Technical spec — `2026-06-08-collective-agentic-memory-prototype-spec.md` (the build-level detail; this PRD is the product framing)

> **V1 = the prototype.** This PRD describes the first thing we build: a de-scoped, two-persona, two-memory-layer system whose sole job is to prove — to a standard a human architect will accept — that a requirement can pass through shared agentic memory and be faithfully transformed by another agent. Everything beyond that is roadmap (§12).

---

## 1. Summary

We are building a collective agentic memory system for an AI Delivery Life Cycle (AI DLC) swarm. V1 proves the foundational loop with two agent personas — a Business Analyst (BA) and a Solution Architect (SA) — sharing a temporal knowledge graph. The BA reads a delivery ticket and writes structured requirements into shared memory; the SA reads from that memory, negotiates open questions with the BA, and produces an Architecture Decision Record (ADR). A senior human architect judges whether the ADR is acceptable. If it is, the core hypothesis holds and we earn the right to build the deferred layers.

## 2. Problem

Enterprise delivery agents cannot share context reliably. The context window is finite, prose hand-offs lose meaning, and multi-agent flows are non-deterministic and unauditable. Teams reach for vendor memory tools (Pinecone, Mem0, Zep) as if one product solves it — but collective memory is a layered architecture, and the foundational risk is unproven: **does a requirement survive transformation through shared memory well enough that a human expert accepts the result?** Until that is answered, every higher layer is speculation.

## 3. Goals & Non-Goals

### Goals (V1)
- **G1** — Prove semantic roundtrip fidelity: BA requirement → shared graph → SA ADR, accepted by a human architect (≥70% accept, <10% reject).
- **G2** — Establish a deterministic, replayable orchestration substrate (FSM + append-only event log) that higher layers can build on.
- **G3** — Validate that shared temporal memory (Graphiti) is the right L4 substrate for DLC artifacts.
- **G4** — Demonstrate ingestion from four ideation-layer tools (JIRA, Confluence, Notion, Miro) into shared memory.
- **G5** — Stand up honest instrumentation: human-gated quality, with machine metrics measured *against* the human verdict.

### Non-Goals (V1 — see §12 roadmap)
- Persona memory (Mem0), episodic/learning memory (Zep/Hindsight), Skill Registry — deferred.
- Multi-LLM routing / cost optimization — one model hardcoded per role.
- Personas beyond BA + SA (Security, QA, Ops) — deferred.
- Second-tier tools (GitLab, Wiz, Snyk, Datadog, New Relic, ServiceNow) — deferred.
- Figma integration — deferred (Dev seat + designer convention dependency).
- Production data — V1 runs on anonymized, frozen scenarios only.
- Scale/concurrency hardening — V1 is single-tenant, low-throughput.

## 4. Users & Personas

### Human users
- **Delivery teams** (BAs, architects) whose hand-offs the system augments.
- **The architect-reviewer** — a senior SA, *not on the build team*, who is the acceptance authority and the literal success gate.
- **The platform owner** (sverze) — evaluates whether the hypothesis holds and whether to fund V2.

### Agent personas (V1)
- **BA Agent** — reads delivery tickets/specs, extracts structured requirements, writes to shared memory, answers SA clarifications. Model: Gemini Flash.
- **SA Agent** — reads requirements from shared memory, raises clarifications, produces ADRs with justified architectural decisions. Model: Claude Sonnet.

## 5. Core Hypothesis & Success Criteria

> **Hypothesis:** A requirement written by one agent into a shared temporal graph can be retrieved and faithfully *transformed* (not merely copied) by another agent into an architecture decision a senior human would accept.

**The gate (primary):** Senior architect accept/revise/reject on the frozen scenario set — **≥70% accept (lower 95% CI), <10% reject.** This is pass/fail for V1.

**Supporting signals (advisory, measured against the human):**
- Judge-vs-human agreement (Cohen's κ ≥ 0.6 before the LLM judge is trusted at all)
- Memory hit rate ≥90% (tagged key facts retrievable from the graph)
- Omission rate <5% (no silent dropping of stated requirements)
- FSM replay determinism (event log replays to identical state)
- Call-graph stability (Jaccard ≥0.8 on identical inputs)

Full metric definitions, CIs, and halt thresholds: see spec §Instrumentation.

## 6. Key User Stories

- **US1** — As a BA agent, I read a delivery ticket and write structured, attributed requirements to shared memory, so the SA can consume them without re-reading the source tool.
- **US2** — As an SA agent, when a requirement is underspecified, I raise a clarification and get an answer from the BA *before* committing a decision — modelling the real negotiation, not a one-shot hand-off.
- **US3** — As an SA agent, I produce an ADR that addresses the requirement and adds justified architectural constraints, traceable back to the source.
- **US4** — As the architect-reviewer, I review each ADR against its source ticket and record accept/revise/reject, and my verdict is the system's success measure.
- **US5** — As the platform owner, I can replay any run from the event log and see exactly what each agent did, in what order, with what tokens and latency.
- **US6** — As an operator, I can ingest content from JIRA, Confluence, Notion, and Miro into the same shared memory and have agents reason over it uniformly.

## 7. Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR1 | FSM orchestrator with states `intake → analysis ⇄ clarification → decision (+ escalation)`; agents propose transitions, FSM is sole executor | P0 |
| FR2 | BA↔SA clarification loop with a configurable `MAX_CLARIFY_ROUNDS` cap (default 3) → forced escalation on exceed | P0 |
| FR3 | Shared temporal graph (Graphiti) with append-only, attributed, timestamped writes and a `canonical` promotion flag | P0 |
| FR4 | Structured JSON artifact hand-offs (typed `RequirementsArtifact`, `ADR`) — no prose hand-offs | P0 |
| FR5 | Immutable append-only event log as ground truth; full run replay to identical state | P0 |
| FR6 | ToolAdapter interface; JIRA via direct API to the gate | P0 |
| FR7 | Confluence, Notion, Miro ingestion into Graphiti (post-gate) | P1 |
| FR8 | Human review workflow: produce ADRs in a reviewable form; capture accept/revise/reject + notes | P0 |
| FR9 | Advisory eval harness (split rubric: traceability + omission/grounding) with judge-vs-human κ tracking | P1 |
| FR10 | OTel instrumentation on every agent call → Langfuse (tokens, latency, clarify-rounds) | P0 |
| FR11 | Conflict resolution: role hierarchy + temporal recency tiebreaker (deterministic) | P1 |
| FR12 | Hardcoded model-per-role behind a thin interface (router-ready for V2) | P0 |

## 8. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR1 | **Determinism & auditability** — every state transition and write is logged and replayable. No hidden agent state. |
| NFR2 | **Data safety** — anonymized scenarios only; nothing client-identifying leaves the local perimeter. |
| NFR3 | **Cost ceiling** — standing infra cost ~$0 (self-hosted); only Anthropic pay-as-you-go, single-digit dollars for the scenario set. |
| NFR4 | **Honest measurement** — all rates reported with 95% CIs; human verdict never overridden by machine score. |
| NFR5 | **Swappability** — Graphiti backend (Neo4j/FalkorDB/Kuzu), observability platform, and model provider behind interfaces. |
| NFR6 | **Reproducibility** — frozen scenario set under version control; pinned dependencies (uv lockfile). |

## 9. Technology Stack (Confirmed)

**Decision: Python-first.** The memory/agent/eval ecosystem (Graphiti, Mem0, DeepEval, RAGAS, LiteLLM) is Python-native; going Python-first removes the polyglot seam rather than bridging it with sidecars.

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language / runtime | **Python 3.12+**, managed with **uv** | Native fit for every core library; fast modern toolchain |
| Orchestration / FSM | **Hand-rolled FSM** (or lightweight `transitions`); **not** an agentic framework | Council ruling: deterministic FSM, not an agent-orchestrator. If LangGraph is used, only its deterministic graph/state primitives — never autonomous routing. |
| Agents | Direct provider SDKs (`anthropic`, `google-genai`) behind a `ModelClient` interface | Router-ready for V2; no premature LiteLLM dependency |
| L4 semantic memory | **Graphiti** (OSS) | Temporal knowledge graph — the core hypothesis substrate |
| Graph backend | **Neo4j Community** (Docker); FalkorDB/Kuzu as free fallbacks | Free, self-hosted |
| Graph extraction LLM | **Gemini Flash** (free tier) | Avoids Graphiti's default OpenAI cost |
| L2 working memory | In-process structured artifacts (Pydantic models) | Typed hand-offs, no prose |
| Tool integration | `ToolAdapter` protocol; JIRA direct API (`httpx`); MCP servers post-gate | Per Q4 — direct to gate, MCP for breadth |
| Observability | **Langfuse** (self-hosted) + OpenTelemetry | Free, OTel-native, swappable |
| Advisory eval | **DeepEval + RAGAS** (Python-native) | First-class now that the stack is Python |
| Event log | Append-only **JSONL** | Simple, replayable ground truth |
| Data validation | **Pydantic v2** | Typed artifacts and schema enforcement |
| Testing | **pytest** | Standard |

**Deferred stack (V2):** Mem0 (L1), Zep/Hindsight (L5), LiteLLM routing, Pinecone/pgvector (Skill Registry vectors), Figma Dev Mode MCP.

## 10. Scope

**In:** BA + SA agents; L2 + L4 memory; FSM with negotiation loop; event log + replay; JIRA (to gate) + Confluence/Notion/Miro (post-gate); human gate + advisory eval; conflict resolution; OTel/Langfuse.

**Out (V2 roadmap):** persona memory, episodic memory, skill registry, routing, additional personas, second-tier tools, Figma, production data, scale hardening.

## 11. Build Order

No calendar. We build in **dependency order** — substrate first, then the core loop, then prove it, then add breadth and robustness. Each stage names the goals and user stories it satisfies. The one meaningful checkpoint is the **hypothesis gate** at the end of Stage 3 — a logical go/no-go, not a date.

### Stage 1 — Foundations (the deterministic substrate)
Build the things every later stage depends on, before any agent exists.
- Data contracts: `RequirementsArtifact` and `ADR` as Pydantic models *(FR4)*
- Append-only JSONL event log + replay *(FR5)*
- FSM core: states + suggestion queue, agents propose / FSM executes *(FR1)*
- **Satisfies:** G2 · **Stories:** US5

### Stage 2 — The core loop (the hypothesis, end to end)
The minimum that makes the BA→SA roundtrip real.
- Graphiti + Neo4j up; define the entity/edge model for requirements and ADRs *(FR3)*
- BA agent: JIRA ticket (direct API behind ToolAdapter) → `RequirementsArtifact` → Graphiti *(FR6)*
- SA agent: read Graphiti → produce `ADR` *(US3)*
- Wire FSM `intake → analysis → decision`, then add the `clarification` loop with `MAX_CLARIFY_ROUNDS` *(FR1, FR2)*
- Hardcoded model-per-role behind `ModelClient` *(FR12)*
- **Satisfies:** G3 + foundation of G1 · **Stories:** US1, US2, US3

### Stage 3 — Make it visible, then judge it  ← **HYPOTHESIS GATE**
Instrument, run against example inputs, and get a human verdict.
- OTel instrumentation on every agent call → Langfuse (tokens, latency, clarify-rounds) *(FR10)*
- Assemble example tickets to run against (synthetic, or anonymised real — see §13)
- Produce ADRs in reviewable form; architect records accept/revise/reject *(FR8)*
- Advisory eval harness (split rubric) + judge-vs-human κ *(FR9)*
- **Gate:** architect acceptance ≥70% / reject <10%. **If it fails here, stop and fix retrieval/prompts before building anything below.**
- **Satisfies:** G1, G5 · **Stories:** US4

### Stage 4 — Breadth (only after the loop is proven)
- Confluence, Notion, Miro ingestion into Graphiti *(FR7)*
- Re-check quality holds with multi-tool inputs (no regression)
- **Satisfies:** G4 · **Stories:** US6

### Stage 5 — Properties & robustness
- Conflict resolution: role hierarchy + temporal recency *(FR11)*
- Replay verification: event log → identical state *(NFR1)*
- V2 interface stubs (Mem0 / Zep / router slots)
- Demo with honest metrics (CIs reported)
- **Satisfies:** G2 (hardening) · **Stories:** US5

## 12. Roadmap (post-V1, on a successful gate)

1. **L1 Persona memory (Mem0)** — measure lift over static persona headers.
2. **L5 Episodic memory (Zep/Hindsight)** — learning loop; expect clarification-rounds to trend down.
3. **L3 Skill Registry** — procedural memory; the long-term determinism play.
4. **Multi-LLM routing (LiteLLM)** — sensitivity gate + role registry + complexity escalation.
5. **More personas** — Security, QA, Ops.
6. **Second-tier tools** — GitLab, Snyk, Datadog/New Relic, ServiceNow; **Wiz** (enterprise contract).
7. **Scale & concurrency** — the concurrent-write/validation-queue question.

## 13. Dependencies & Procurement

API keys, `.env` template, Docker services, MCP servers, and cost summary: **spec Appendix A.** Standing cost ~$0/month; Anthropic pay-as-you-go is the only real spend in V1.

### Example inputs (needed at Stage 3, not before)

To judge whether the loop works, the BA agent needs sample tickets to read. This is **not** a precondition to starting — Stages 1–2 build fine without it. Choose the level of effort when you reach Stage 3:

- **Synthetic (simplest):** hand-write a handful of realistic tickets. Good enough to develop and demo against.
- **Anonymised real (more realistic):** take real tickets from a delivery team and strip anything sensitive (client names, internal product/IP) before use. Closer to production behaviour.

**Optional rigor (add only when you want to *trust the score*, not just see it work):** have someone outside the build team write the example set and fix it before evaluating, so the build isn't quietly tuned to its own test. Worth it for a credible success claim; skip it while iterating.

A human reviewer (a senior architect) is needed at the Stage 3 gate to give the accept/reject verdict.

## 14. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| No access to real tickets / external author / architect-reviewer | High | Week 0 precondition; surface immediately if blocked |
| Graphiti retrieval fidelity below gate | High | The gate is *designed* to catch this in Week 1 before further build |
| Negotiation loop fails to converge (always hits MAX_CLARIFY) | Medium | Loop cap + escalation; treat as a finding, tune SA prompt/requirements depth |
| Same-family LLM judge inflates scores | Medium | Human gate is primary; 20% cross-family (Gemini) κ check |
| 3-week timeline slips | Medium | Week 3 buffer day; scope is already cut to the gate |
| Tool API rate limits (Notion 3 req/s, Atlassian) | Low | Post-gate only; request queue + backoff |

## 15. Open Questions

*None of these block starting Stage 1 — they resolve as the build reaches the relevant stage.*

1. **(Stage 1)** FSM implementation: hand-rolled vs `transitions` vs LangGraph graph-primitives. Decide at build start.
2. **(Stage 2)** Graphiti entity/edge model — exact node and relationship shapes for requirements and ADRs.
3. **(Stage 3)** Example inputs — synthetic vs anonymised real, and how much eval rigor (see §13).
4. **(Stage 3)** Where the architect records verdicts — Langfuse annotations vs a separate review sheet feeding the eval log.
5. **(later)** Statistical confidence — human verdict alone, or a larger set for tighter CIs.

---

*PRD V1 produced 2026-06-08. Scope: the de-scoped prototype (BA+SA, L2+L4, human gate, 4 ideation tools). Stack: Python-first. Success = a senior architect accepts the SA's ADRs at ≥70%. Everything else is roadmap. Companion to the technical spec (v1.1) and research document.*
