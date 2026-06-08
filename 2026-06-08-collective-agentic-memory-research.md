# Collective Agentic Memory for AI Delivery Life Cycle Swarms

**Date:** 2026-06-08
**Researcher:** Coco (PAI Research Skill — Standard Mode: 4 agents cross-checked)
**Destination:** Prosperity / AI DLC prototype planning

---

## Original Prompt

> I would like to investigate how to create a collective agentic memory that can be utilised by a swarm of agents. My specific area of work at the moment is AI Delivery Life Cycle, or AI DLC. I will be needing agents to interact amongst various parts of the delivery life cycle — from ideation (JIRA, Confluence, Figma, Miro), CI/CD (GitLab), testing and security (Wiz, Snyk), observability (Datadog, New Relic), and operations (ServiceNow).
>
> I could see agents running as different types of personas — for example a business analyst or a solution architect — producing content and collectively working together. Fundamentally the context window is an issue. They need some sort of memory to support more deterministic flows and reduce waste through memory compression and tokenisation issues, by storing memories specific to personas — especially around managing skills and determining when to use code vs not use code.
>
> Companies in this space include Pinecone, Mem0, Zep, Hindsight. Research and come back with considered approaches.

---

## Executive Summary

The collective agentic memory problem in an AI DLC swarm requires a **five-layer architecture**, not a single vendor tool. The vendors named (Pinecone, Mem0, Zep, Hindsight) occupy different layers and are complements, not alternatives.

The non-obvious finding: **individual agent (persona) memory strongly amplifies collective memory** — shared traces are far richer with per-agent cognitive infrastructure underneath them.

> **v1.1 review correction:** v1.0 stated persona memory is a *prerequisite* and should be built *first*. An independent review challenged this: it confuses "amplifies" with "required." You can prove the core collective-memory loop (a requirement passing through a shared graph and being faithfully transformed by another agent) with **no persona layer at all** — static hand-written persona headers suffice. The prototype therefore builds the shared semantic graph (L4) first and defers persona memory (L1) to v2, where its lift over the static baseline can actually be *measured* rather than assumed. See the prototype spec's de-scoping decision.

The highest-ROI long-term investment for determinism is a **Skill Registry** — procedural memory that accumulates evidence about when to use code vs tool calls. It is more tractable than fine-tuning and compounds across every agent. But it is *not* gate-critical for the prototype: it needs accumulated run signal to be worth anything, so it too is a v2 layer.

---

## The Five-Layer Memory Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Layer 5: EPISODIC — what happened (Zep, Hindsight)     │
│  Layer 4: SEMANTIC — what is known (Graphiti, Neo4j)    │
│  Layer 3: PROCEDURAL — how to act (Skill Registry)      │
│  Layer 2: WORKING — active task context (in-context)    │
│  Layer 1: PERSONA — who I am (Mem0 scoped per agent)    │
└─────────────────────────────────────────────────────────┘
```

### Layer 1 — Persona Memory (per-agent, scoped)

Each agent (BA, SA, QE, SecEng, etc.) maintains its own memory namespace. This is where skills, preferences, tool affinities, and role-specific facts are stored.

- **Recommended tool:** Mem0 (`mem0ai` SDK)
- **Why Mem0:** It supports multi-agent scoped memory out of the box — you can write to `agent_id="solution-architect"` and retrieve only that agent's memories. It extracts structured facts from conversations automatically.
- **What to store:**
  - Tool preferences per domain (e.g. "SA always prefers Confluence over raw Markdown for ADRs")
  - Past decisions and their outcomes
  - Skill inventory: which tools this persona knows how to call, with confidence scores
  - Code vs no-code patterns: "when spec is ambiguous, use Figma API to extract acceptance criteria rather than hallucinating them"

### Layer 2 — Working Memory (ephemeral, in-context)

The active task window. This is just the context window — but managed deliberately.

- **Pattern:** Each agent receives a compressed persona header (from Layer 1) at the start of every invocation. Cap to ~2K tokens.
- **Pattern:** Shared task state is passed as a structured object (JSON), not narrative prose, to reduce compression loss.
- **Anti-pattern:** Don't pass full conversation history between agents. Pass structured artifacts — tickets, decisions, diffs.

### Layer 3 — Procedural Memory (Skill Registry)

The most underinvested layer in most teams, and the highest-ROI for determinism.

A Skill Registry is a queryable catalogue of:
- What the agent can do (tool calls, code generation, API integrations)
- When to use each (preconditions, confidence thresholds)
- Evidence of past success/failure (updated after each task)

**Why this matters for DLC:** The BA agent needs to know "when a JIRA ticket has no acceptance criteria, call the Figma MCP to extract them — don't ask the user." That rule lives in the Skill Registry, not the context window.

- **Implementation approach:** Start as a YAML/JSON file per persona. Evolve to vector-embedded retrieval (Pinecone or pgvector) as it grows past ~50 skills.
- **Evidence accumulation:** After each completed task, a hook writes a signal back to the registry — success/failure, which skill path was taken, latency.
- **arXiv reference:** Skills as memory is the primary frontier in 2026 agentic systems (papers 2602.20867, 2604.08224).

### Layer 4 — Semantic Memory (shared knowledge graph)

The collective brain of the swarm. A knowledge graph over your entire DLC tool ecosystem — entities, relationships, and their temporal state.

- **Recommended tool:** Graphiti (by Zep team, open source)
- **Why Graphiti over a plain vector DB:** Graphiti maintains temporal edges. When a JIRA ticket moves from "In Progress" to "Done," the graph edge is timestamped — agents can reason about what changed and when, not just what is true now.
- **What to model:**
  - Entities: tickets, PRs, deployments, incidents, ADRs, test results, Wiz findings
  - Relationships: `ticket → implements → ADR`, `PR → breaks → test`, `Wiz finding → blocks → deployment`
  - Temporal edges: `deployment → introduced → incident [2026-06-01]`
- **Pinecone's role:** Use Pinecone (or pgvector if you want fewer moving parts) as the vector index backing the semantic retrieval layer. Graphiti can use it as its underlying store.

### Layer 5 — Episodic Memory (experience / learning)

A log of what the swarm experienced — decisions made, outcomes observed, lessons learned. This is the compound-interest layer: the swarm gets smarter over time.

- **Recommended tool:** Hindsight (MIT licensed, self-hostable)
- **Why Hindsight:** It is purpose-built for agentic experience capture. It intercepts agent runs, extracts decision points, and makes them retrievable for future runs.
- **Alternative:** Zep (managed, faster to start, but Hindsight is self-hostable which matters for enterprise DLC data)
- **What to store:**
  - "The SA and BA disagreed on this scope. The BA's framing was used. The delivery was on time."
  - "The security agent flagged this Wiz finding. DevOps marked it a false positive. Confirmed false positive 3 sprints later."
  - "Confluence spec + Figma link combo reliably produces higher-quality acceptance criteria than either alone."

---

## Vendor Map for Your Stack

| Vendor | Layer | Role in AI DLC | Recommendation |
|--------|-------|----------------|----------------|
| **Mem0** | Persona (L1) | Per-agent scoped memory, auto-extraction from conversations | Start here. Free tier. SDK in Python/TS. |
| **Graphiti** | Semantic (L4) | Temporal knowledge graph over DLC tool events | Second. Open source. Self-host. |
| **Hindsight** | Episodic (L5) | Experience capture, learning loop | Third. MIT license. |
| **Zep** | Episodic (L5) | Managed alternative to Hindsight | Use if you want managed over self-hosted |
| **Pinecone** | Semantic (L4) | Vector index backing semantic retrieval | Use if you need scale. pgvector is cheaper to start. |

**Not recommended as primary:** Pinecone alone. It is a vector store, not a memory system. Without temporal edges and structured extraction, it stores embeddings without context — retrieval is shallow.

---

## Persona-Specific Memory Patterns

### Business Analyst Agent

**Critical memories:**
- Project context: active epics, stakeholder names, acceptance criteria patterns
- Tool preferences: "always check Confluence before asking the user"
- Code/no-code boundary: "use Miro API to extract sticky note clusters, never transcribe manually"
- Decision history: past interpretations of ambiguous requirements and their outcomes

### Solution Architect Agent

**Critical memories:**
- ADR inventory: past architectural decisions and their rationale
- Technology opinions: biases toward specific patterns (scoped per project)
- Risk patterns: "this stack combination has caused integration issues before"
- Code/no-code boundary: "generate GitLab CI YAML directly; never use the UI for pipeline config"

### Security / QE Agent

**Critical memories:**
- Known false positive patterns (Wiz, Snyk finding types that historically resolve as false positives)
- Test coverage heuristics: which code paths need deep testing vs shallow
- Incident post-mortems: past production failures and their proximate causes
- Code/no-code boundary: "always run Snyk via CLI, never via API poll — CLI output is richer"

---

## Determinism Strategy

The core problem: LLMs are probabilistic. Memory makes them more deterministic by narrowing the decision space at runtime.

**Three mechanisms:**

1. **Skill Registry gating** — Before an agent takes an action, it queries its Skill Registry. If confidence < threshold, it escalates rather than guessing. This is the primary determinism lever.

2. **Structured artifact passing** — Agents pass JSON objects between handoffs, not prose summaries. A BA → SA handoff passes a typed `RequirementsArtifact`, not "here's what I found." This eliminates the telephone game.

3. **Episodic retrieval at task start** — Before a task begins, the agent retrieves the 3 most similar past experiences from Hindsight/Zep. This narrows the prior distribution significantly.

---

## Prototype Architecture (for Council / Next Step)

```
┌───────────────────────────────────────────────────────────────────┐
│                        Orchestrator                               │
│  (routes tasks, selects personas, manages artifact handoffs)      │
└──────────────────┬───────────────────────────────────────────────┘
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
  [BA Agent]  [SA Agent]  [SecEng Agent]
       │           │           │
       └─────┬─────┘           │
             ▼                 ▼
        [Mem0 — per-persona scoped memory]
             │
             ▼
        [Graphiti — shared temporal knowledge graph]
             │
             ├── JIRA events
             ├── GitLab PR/pipeline events
             ├── Wiz/Snyk findings
             ├── Datadog alerts
             └── ServiceNow incidents
             │
             ▼
        [Hindsight — episodic experience store]
             │
             ▼
        [Skill Registry — YAML per persona, evolves to vector]
```

**Event bus:** All DLC tool events (JIRA webhooks, GitLab CI events, Datadog alerts) flow into the knowledge graph via a lightweight event bus (NATS or Redis Streams). The graph is the single source of truth; agents query it rather than calling tools directly for context retrieval.

---

## Implementation Sequence (recommended)

| Phase | What | Why first |
|-------|------|-----------|
| 0 | Define persona schemas (BA, SA, SecEng) as typed TS interfaces | Foundation for everything else |
| 1 | Stand up Mem0 with one persona (BA agent) | Validates per-agent memory pattern cheaply |
| 2 | Build Skill Registry as YAML for BA persona | Unlocks deterministic tool selection immediately |
| 3 | Wire Graphiti to JIRA + GitLab webhooks | Shared context starts accumulating |
| 4 | Add Hindsight | Learning loop goes live |
| 5 | Add second persona (SA), validate cross-agent memory retrieval | Tests the collective pattern |
| 6 | Structured artifact handoffs between BA and SA | Completes the first real swarm flow |

---

## Open Questions for Council / Next Session

1. **Orchestrator design:** Should the orchestrator be a separate agent with its own memory, or a deterministic router? (Tradeoff: flexibility vs debuggability)
2. **Memory write authority:** Who can write to the shared knowledge graph? All agents, or only the orchestrator after validation?
3. **Conflict resolution:** When BA and SA have contradictory memories about a past decision, which wins? (Temporal? Role hierarchy? Confidence score?)
4. **DLC tool authentication:** MCP servers or direct API integration for JIRA/GitLab/ServiceNow? (MCP is cleaner for multi-agent; direct API is more controllable)
5. **Data residency:** Mem0 managed vs self-hosted for enterprise? Hindsight vs Zep on same axis.

**Council resolution:** All five questions resolved 2026-06-08. See `2026-06-08-collective-agentic-memory-prototype-spec.md` §Architectural Decisions.

---

## Multi-LLM Model Routing

*Research conducted 2026-06-08 — Extensive mode (9 agents, 2 verifiers). Confidence: HIGH.*

### Core Finding

Routing is not a single decision — it is a three-layer stack. Teams that implement even basic routing report 27–85% cost savings. The tooling required is 2–5 days of engineering for a first working layer.

> **Load-bearing check (v1.1 review):** The "27–85% savings" figure is vendor- and workload-dependent and should be treated as *motivation, not a design input*. Nothing in the prototype depends on it being true — routing is deferred to v2 entirely, and the prototype hardcodes one model per role. If the real saving turns out to be 10%, the design does not change. Re-measure on your own workloads before quoting the number to stakeholders.

### The Four Routing Paradigms

| Paradigm | How it works | Best for |
|----------|-------------|----------|
| **Classifier-based** (RouteLLM) | Lightweight model trained on preference data predicts which LLM wins | When you have labelled preference data |
| **Semantic similarity** (LiteLLM Semantic Router) | Embed request, match against utterance library mapped to model | Domain/intent routing ("code task" → Sonnet) |
| **Complexity scoring** (LiteLLM Complexity Router) | Heuristic scoring in <1ms — SIMPLE/MEDIUM/COMPLEX → Haiku/Sonnet/Opus | Fast, zero external calls, good baseline |
| **MasRouter** (ACL 2025) | Cascaded controller: single vs multi-agent? what roles? which backbone per role? | Multi-agent system routing specifically; 52% overhead reduction |

### Signal Hierarchy for Routing

| Signal | Use for | Implementation |
|--------|---------|----------------|
| Data sensitivity flag | Local-vs-cloud split | `sensitivity=HIGH` → Ollama/Llama, never cloud |
| Output type | structured JSON → Gemini Flash; prose → Sonnet; multi-step reasoning → Opus | Task metadata or heuristic |
| Complexity score | SIMPLE/MEDIUM/COMPLEX tier | LiteLLM Complexity Router (<1ms) |
| Token budget remaining | Hard cap enforcement | `remaining_budget_usd` tracked per project |
| Latency SLO | Async vs real-time path | Sync → Haiku; async → Opus |
| Confidence escalation | Model self-reports low confidence → escalate | Post-inference, confidence < 0.6 |

### Recommended Three-Layer Stack for AI DLC

1. **Sensitivity gate (deterministic):** At FSM task creation — `data_classification=SENSITIVE` forces local Ollama/Llama. No LLM involved in the decision.
2. **Role-based registry (config-driven):** YAML model registry keyed by agent role + task type. BA doing requirement extraction → Gemini Flash. SA doing ADR generation → Sonnet. Orchestrator decomposition → Opus. Registry evolves as evidence accumulates.
3. **Complexity escalation (runtime):** LiteLLM Complexity Router as override — if task scores COMPLEX at runtime, escalate assigned model one tier regardless of role default.

### Model Registry Pattern

The registry is a versioned, schema-validated YAML/JSON file. No OSS standard exists yet — design it from scratch but keep it evolvable:

```yaml
# model-registry.yaml
routes:
  - role: business-analyst
    task: requirement-extraction
    model: gemini/gemini-2.0-flash
    fallback: claude-haiku-4-5
    reason: structured extraction, cost-efficient
  - role: solution-architect
    task: adr-generation
    model: claude-sonnet-4-6
    fallback: gemini/gemini-2.5-pro
    reason: prose + reasoning
  - role: orchestrator
    task: plan-decompose
    model: claude-opus-4-8
    fallback: claude-sonnet-4-6
    reason: multi-step reasoning, budget permitting
sensitivity_gate:
  HIGH: ollama/llama3
  MEDIUM: inherit_role_default
  LOW: inherit_role_default
```

### Tooling

- **LiteLLM** — primary proxy; 100+ providers, OpenAI-compatible, includes Complexity Router and Semantic Router ([github.com/BerriAI/litellm](https://github.com/BerriAI/litellm))
- **RouteLLM** — preference-data classifier; study architecture even if not deploying ([github.com/lm-sys/RouteLLM](https://github.com/lm-sys/RouteLLM))
- **OpenRouter** — widest hosted-model catalogue for breadth/prototyping
- **vLLM Semantic Router / Iris** — routing below application layer; emerging, watch for 2026 production adoption

### Key Risks

- **Registry drift:** Model capabilities change every 6–8 weeks (new Anthropic/Google releases). Registry needs a review cadence or automated benchmarking.
- **Bandit-feedback routers (BaRP, PILOT) are replacing static classifiers** — learning routing rules from production signal rather than pre-training. Not yet mature OSS. Watch this space.
- **LiteLLM ceiling at scale:** Python GIL becomes a bottleneck above ~500 RPS. Bifrost (Go-based) outperforms it; smaller ecosystem. Not a prototype concern.

---

## Instrumentation and Performance Measurement

*Research conducted 2026-06-08 — Extensive mode. Confidence: HIGH.*

### Core Finding

A large share of agent failures are silent semantic errors — output is produced but semantically wrong. Standard task completion metrics (did it finish?) miss these entirely.

> **Load-bearing check (v1.1 review):** The specific "75%" figure comes from one source (MAESTRO) on its own benchmark mix and should not be quoted as a general law. What *is* robust and load-bearing is the qualitative point: output presence is not a quality signal, so the prototype needs a semantic quality gate. The v1.1 design makes that gate a **human architect's accept/reject** — not an LLM judge grading output from its own model family. The LLM judge is retained only as an advisory signal whose agreement with the human is itself measured (Cohen's κ). This way the design does not depend on any unverified failure-rate statistic.

### Evaluation Frameworks

| Framework | Sweet spot | Agent-specific? |
|-----------|-----------|-----------------|
| **RAGAS** | RAG pipeline quality: faithfulness, relevancy, context precision/recall | Partial — strong for memory retrieval |
| **DeepEval** | Broadest metric library; CI/CD integration; agents + chatbots + multimodal | Yes — multi-step evaluation support |
| **AgentBench** | Interactive environment tasks (OS, DB, games) | Yes |
| **MAESTRO** | Multi-agent: call graph stability, cost/latency/failure profiling | Yes — explicitly multi-agent ([arxiv.org/abs/2601.00481](https://arxiv.org/abs/2601.00481)) |

### Key Metrics for BA→SA Pipeline

| Metric | Definition | How to measure |
|--------|-----------|----------------|
| **Memory hit rate** | % of BA artifact facts correctly retrievable from Graphiti | Query Graphiti post-write; assert key entities exist |
| **Semantic preservation rate** | % of BA requirements reflected in SA's ADR | LLM judge with rubric |
| **Token efficiency** | Tokens consumed per successful task completion | Sum tokens across all agent hops |
| **Latency per hop** | Wall-clock time per FSM state transition | OTel span timing |
| **Task completion rate** | % of tickets that produce a valid ADR | Pass/fail on output schema |
| **Hallucination rate** | Claims in ADR not supported by input artifacts | LLM judge + grounding check |
| **Call graph stability** | Structural consistency across repeated runs | MAESTRO: Jaccard + LCS similarity |

### Eval Harness Architecture

```
Input: JIRA ticket (text + acceptance criteria)
     ↓
BA Agent run → capture: tokens, latency, artifacts produced
     ↓
Graphiti write → capture: entities written, relationships created
     ↓
Graphiti read (SA query) → capture: entities retrieved, memory hit rate
     ↓
SA Agent run → ADR → capture: tokens, latency
     ↓
Evaluators (run in parallel):
  1. Schema validator: ADR has required sections
  2. LLM judge: "Does ADR address all requirements from JIRA ticket?"
  3. Grounding check: "Are ADR claims supported by BA artifacts?"
  4. Memory fidelity: embedding cosine(JIRA key facts, Graphiti-retrieved entities)
```

### Observability Platforms

| Platform | Best for | Self-host? | Key differentiator |
|----------|---------|-----------|-------------------|
| **Langfuse** | Any framework via OTel | Yes (Postgres + ClickHouse, OSS) | Best self-host; cost analytics |
| **LangSmith** | LangChain/LangGraph native | Cloud + enterprise | Node-by-node state diffs, full graph replay |
| **Arize Phoenix** | RAG evaluation rigor | Yes (OSS) | Deepest eval primitives |
| **W&B Weave** | Teams already on W&B | Cloud | Experiment tracking + agent tracing unified |

**Recommended for prototype:** Langfuse self-hosted. Free, OSS, accepts OTel from any framework, cost analytics out of the box. Instrument with OTel once; switch platforms later without re-instrumentation.

### Key Risks

- **LLM-as-judge divergence:** MAESTRO found "substantial divergence between different judge models." Use a consistent judge model across all eval runs — never mix.
- **No established BA→SA golden dataset exists.** Collect (JIRA ticket, expected ADR) pairs from the first prototype runs to build one.
- **Memory hit rate for Graphiti is not natively instrumented.** Requires a custom evaluation step post-write.

---

## Expanded Tool Integrations

*Research conducted 2026-06-08 — Extensive mode. Confidence: HIGH on APIs; MED on MCP server maturity (fast-moving).*

### Tool Readiness for Agent Access

| Tool | MCP Server | Webhooks | API Quality | Extraction Challenge |
|------|-----------|---------|-------------|---------------------|
| **JIRA** | ✅ Official (mcp-atlassian) | ✅ Yes | Excellent | None significant |
| **Confluence** | ✅ Same mcp-atlassian package | ⚠️ Cloud-only (Forge event listeners) | Good | Macro-heavy content needs post-processing |
| **Notion** | ✅ Official MCP | ✅ Native webhooks | Excellent | Rate limit: 3 req/s |
| **Figma** | ✅ Official (Dev Mode MCP, beta) | ❌ None — polling only | Good (beta) | Seat gating: 6 calls/month on free seats |
| **Miro** | ✅ 80+ tools MCP (Dec 2025) | ✅ Board webhooks | Good | Spatial structure — stickies are (x, y) positions |

### Graphiti Sync Strategy per Tool

| Tool | Sync method | Latency | Notes |
|------|------------|---------|-------|
| Notion | Webhook → `graphiti.add_episode()` | Seconds | Best-in-class; build webhook receiver with idempotency keys |
| Miro | Webhook → `graphiti.add_episode()` | Seconds | Frame-based extraction first; spatial clustering is v2 |
| JIRA | Webhook (existing) | Seconds | Already in prototype |
| Confluence | Polling + version hash | 5–15 min | Acceptable for documentation content |
| Figma | Polling + version hash | 15–60 min | Design specs change slowly |

### Extraction Patterns by Tool

**Confluence** — Use CQL (Confluence Query Language) for targeted search by space, label, last-modified. Content returned as storage format XML — the MCP server handles most parsing, but decision matrices in table macros need bespoke normalization. Target: decision logs, technical specs, runbooks.

**Notion** — REST API returns typed block content (paragraph, heading, table, bulleted list) as structured JSON. More structured than Confluence. Databases are queryable with filter/sort. Best for project context, meeting notes, structured knowledge bases. Rate limit: 3 req/s — implement request queue with back-off for multi-agent concurrent access.

**Figma** — `get_design_context` returns React+Tailwind representation of selected layers (node tree, variant info, layout constraints, design tokens). Acceptance criteria are text annotations on frames — no formal schema. **Convention required:** agree with designers on a named "Acceptance Criteria" frame per feature, otherwise extraction is unreliable.

**Miro** — Sticky notes via REST API v2 return content text + color + (x, y) position. Color is often semantic (red = risk, green = opportunity). Two extraction approaches:
1. **Frame-based (recommended first):** Facilitators organize boards into labeled frames → clean extraction without spatial math
2. **Spatial clustering (v2):** DBSCAN on (x, y) coordinates to infer affinity groups — required when boards lack frame structure

### Integration Priority Order

1. **Notion** — most agent-ready, native webhooks, structured JSON, official MCP, rate limits manageable
2. **Confluence** — highest enterprise value for decision logs; same MCP package as JIRA (zero extra setup)
3. **Miro** — discovery artifact ingestion; require frame conventions before automating
4. **Figma** — defer until BA→SA memory is proven; requires Dev seat budget and designer convention agreement

---

## Sources

- Mem0 documentation and multi-agent SDK: `https://mem0.ai`
- Graphiti (temporal knowledge graph, Zep): `https://github.com/getzep/graphiti`
- Zep (managed episodic memory): `https://www.getzep.com`
- LiteLLM proxy + routing: `https://github.com/BerriAI/litellm`
- RouteLLM (LMSYS/ICLR 2025): `https://github.com/lm-sys/RouteLLM`
- MasRouter (ACL 2025): `https://arxiv.org/abs/2502.11133`
- MAESTRO multi-agent eval: `https://arxiv.org/abs/2601.00481`
- Langfuse self-hosted observability: `https://github.com/langfuse/langfuse`
- DeepEval eval framework: `https://github.com/confident-ai/deepeval`
- RAGAS retrieval quality: `https://github.com/explodinggradients/ragas`
- Atlassian MCP (JIRA + Confluence): `https://github.com/sooperset/mcp-atlassian`
- Notion official MCP: `https://developers.notion.com/guides/mcp`
- Figma Dev Mode MCP: `https://www.figma.com/blog/introducing-figma-mcp-server/`
- Miro MCP server: `https://mcpservers.org/servers/k-jarzyna/mcp-miro`
- arXiv 2602.20867 — Skills as memory, agentic systems frontier
- arXiv 2604.08224 — Procedural memory and tool selection in LLM agents

---

*Initial research 2026-06-08 via PAI Research Skill (Standard mode — 4 agents). Expanded 2026-06-08 via Extensive mode (9 agents + 2 verifiers): Multi-LLM routing, instrumentation, tool integrations. 28 HIGH | 4 MED findings. 8/8 URLs verified.*
