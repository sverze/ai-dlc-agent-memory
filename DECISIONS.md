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

## D15 — GraphitiMemoryStore: Neo4j everywhere; Kuzu retired before adoption ✅ (resolves OD2, swap #2)

**Decision.** The real L4 store is `GraphitiMemoryStore` (`graphiti_store.py`), implementing the
seam's six primitives over graphiti-core `EntityNode`/`EntityEdge` against **Neo4j only**
(`docker-compose.yml`, browser at :7474). D10/OC2's "Kuzu for local dev" is **retired before it
was ever adopted**: pinning against the real library (graphiti-core 0.29) surfaced a deprecation —
upstream Kuzu is unmaintained and graphiti will remove the backend. One backend everywhere beats
an embedded one on life support. (FalkorDB is graphiti's other supported option if Docker-free
local dev ever matters.)

**Mapping (all proven empirically before design freeze, then by 11 gated tests):**
- uuid = `{group_id}:{id}` — graphiti uuids are global PKs, our ids are per-group (the fake keys
  on `(group_id, id)`); the composite preserves both contracts.
- our `attrs` dict rides one `attrs_json` string property (Neo4j properties can't nest); node
  type / author / canonical are flat attributes; domain id round-trips via `node_id`.
- **Placeholder embeddings `[0.0]`** on nodes and edges — graphiti's Neo4j save unconditionally
  calls `db.create.setNodeVectorProperty`/`setRelationshipVectorProperty`, which NPE on null
  (its pipeline assumes an embedder ran). V1 does no semantic search (D10), so a deterministic
  placeholder satisfies the contract; V2's real embedder overwrites.
- **One event loop per store** (daemon thread, `run_coroutine_threadsafe`) — the neo4j async
  driver binds its pool to the first loop, so per-call `asyncio.run` fails with "Future attached
  to a different loop".
- No LLM client is constructed anywhere in the store (D10 structured-first holds).

**Proof.** `pytest -m graph` (11 tests vs dockerized Neo4j) mirrors the fake's behaviors —
including omission-metric parity fake-vs-real. The **full real stack** ran end-to-end:
`scripts/live_demo.py --graph` → real models + real graph, terminal state, 0 omissions,
18 nodes / 19 edges verified by raw Cypher under a per-run `group_id` (OC3 honored).

**Operational note (quota).** Gemini free tier is **20 requests/day/model**
(`GenerateRequestsPerDayPerProjectPerModel-FreeTier`). When `gemini-2.5-flash` is spent,
`make_model_client(model_by_role=...)` / the demo's `--ba-model gemini-2.5-flash-lite` swaps the
BA to a separate quota bucket without touching the D8 defaults. **A 429 from the demo means
quota, not regression.**

**Honest limits (for the next engineer).**
- **`retrieve()` is client-side.** It is the seam ABC's shared naive substring scan over
  `nodes()` — Neo4j hydrates the nodes, Python does the matching. Real graph-native retrieval
  (Graphiti semantic+keyword search, requiring real embeddings) is V2; the Stage-3 memory-hit-rate
  metric must be read with that scope in mind, not overclaimed as semantic retrieval.
- **No vector index exists** in the compose Neo4j; placeholder `[0.0]` embeddings are inert. If
  V2 adds Graphiti search, embeddings must be regenerated with a real embedder and dimensions
  made consistent before any vector index is created.
- The store's uuid namespace delimiter is `:` — group_ids containing a colon are rejected
  (`_uuid` guard) to prevent cross-group uuid collisions.
- `GraphitiMemoryStore.close()` releases the driver and stops the store's event loop; per-call
  timeout is 60s. The loop thread is a daemon, so process exit without `close()` is safe but
  unclean.

---

## D16 — JIRA ToolAdapter: direct REST, config-only environment switch ✅ (implements D6, swap #3)

**Decision.** Tickets enter the loop through a `TicketSource` seam (`tickets.py`):
`InMemoryTicketSource` (offline fake, D11) and `JiraTicketSource` — JIRA Cloud REST v3 via
`httpx` (optional `jira` extra, lazy import), basic auth from `ATLASSIAN_URL` /
`ATLASSIAN_EMAIL` / `ATLASSIAN_API_TOKEN`. **No MCP** — D6 stands: direct API to the gate,
MCP for post-gate breadth. The description field arrives as **ADF** (Atlassian Document
Format JSON); `adf_to_text` flattens it deterministically, collecting every text leaf
(paragraphs, nested lists, code blocks, mentions) — a dropped list item here would surface
downstream as a phantom requirement omission, so flattening fidelity is tested explicitly.

**Environment switch is pure configuration.** Testing runs against a personal Atlassian
site with an unscoped API token (defaults to the account's own capabilities); pointing at a
work site later means changing the three env vars, nothing else. Errors are mapped (401 →
"check email/token", 404 → "ticket not found") and the token value is never logged.

**Test layers.** Offline: fake + ADF flattener (in the default suite). `-m jira` (extra
only, no network): mocked-transport request-shape and error-mapping tests. Live (env-gated,
skips cleanly): one real fetch, ticket key via `JIRA_TEST_TICKET`. Demo: `--jira KEY` makes
the complete pipeline real — JIRA → BA → graph → SA → ADR.

---

## D17 — Human-review surface: requirements → JIRA comment, ADR → Confluence page ✅ (FR8/US4)

**Decision.** Agent output reaches the human reviewer through a `Publisher` seam (`publish.py`):
`InMemoryPublisher` (offline fake) and `AtlassianPublisher` (real). The BA's requirements are
posted as a **structured comment** on the source ticket (ADF — table of requirements + ACs/key
facts/open questions); the SA's ADR is published as a **Confluence page** (storage XHTML) with a
**back-link comment** on the ticket. One httpx client serves both products (same site/auth; paths
`/rest/api/3/...` vs `/wiki/api/v2/...`). Confluence space resolves from `CONFLUENCE_SPACE_KEY` or
auto-discovery (the printed page URL reveals which space, so a wrong pick is visible).

**Why this shape (user's call).** Comment over sub-tasks/new-issue: additive, reversible, doesn't
reshape anyone's board. Confluence over a JIRA comment for the ADR: an ADR is a real document and
Confluence is its natural home — and the room where an embedded **Miro** diagram will live (reserved
"Diagrams" section now; wired in a later swap).

**The review hero.** The ADR page embeds the **requirement-traceability table** (each requirement id
→ addressed/deferred → how/why), because that join is exactly what the architect is paid to verify
(ApertureOscillation surfaced that a comment-here/page-there split would force them to re-join it
mentally — the page must be self-sufficient). The page ends with an **"Architect verdict"** section
so review is *possible today*; the verdict-capture mechanism itself stays OD3 / Stage 3.

**Design.** Renderers are pure functions building ADF/XHTML directly from the typed artifacts (no
markdown hop); storage XHTML uses only the 5 XML entities (named entities like `&nbsp;` are rejected
by Confluence — tested). Writes are additive only; no LLM in the publisher. Page titles are
timestamped so a **re-run coexists** rather than 409-ing on a duplicate title (and 409 is mapped to a
clear error as backstop). Token never logged; 401/403/404/409 mapped.

**Honest limits.** No idempotency/dedup — a re-run posts a fresh comment and a fresh (timestamped)
page; versioning is V2. Auto space-discovery picks the first space if `CONFLUENCE_SPACE_KEY` is
unset — fine for a single-space personal site, set the key explicitly for anything shared. Live
publish requires Confluence enabled on the site; if it isn't, the requirements comment still works
and the ADR step reports a clear "enable Confluence / set a space" error.

**Verified live 2026-06-15** — with Confluence enabled on the personal Atlassian site, the full
round-trip ran end-to-end: requirements comment on the ticket and an ADR page in Confluence, both
confirmed. Stage 2 is functionally complete; Stage 3 (the gate) is next.

---

## D18 — Observability: Langfuse tracing by wrapping the seam ✅ (FR10, Stage 3 #1)

**Decision.** Per-agent model calls are traced into Langfuse through a `Tracer` seam
(`observability.py`): `NullTracer` (offline default, all no-ops) + `LangfuseTracer` (lazy
`langfuse`, optional `observability` extra) + `make_tracer()` (returns Langfuse only when keys
are present, else Null — never instantiates Langfuse keyless). A `TracingModelClient` **wraps**
any `ModelClient` and emits one Langfuse **generation** per `complete()` — tagged with persona,
model id, token usage, latency — nested under a parent run span. So the BA (Gemini) and SA
(Claude) are comparable side by side, and `agents.py` / `loop.py` / `models.py` stay zero-diff.

**Hard constraints (FirstPrinciples).** Observability is *strictly additive*: a tracer fault is
swallowed and the model response always passes through unchanged — a Langfuse outage can never
break or alter a run. No keys → no-op (D11). `flush()` before process exit because OTel batches
spans (a short demo would otherwise drop them). The "instrumentation must live inside the measured
code" assumption is rejected — wrapping the seam externally gives full visibility with zero intrusion.

**Deploy is config, not code.** Works against **Langfuse Cloud** (free tier — set the 3 env vars,
fastest way to see it) or **self-hosted** (set `LANGFUSE_HOST`). The heavy self-host infra
(postgres + clickhouse + redis + minio) is documented, not bundled in our compose. D9 (self-host
for real data) applies once non-anonymized data is involved; the anonymized prototype can use Cloud.

**Ollama / local models (the user's interest)** stay V2 — they're a *router* concern (D8 defers
LiteLLM). But because tracing wraps the `ModelClient` seam, a future Ollama client is observed in
Langfuse for free, no instrumentation change.

**Langfuse v4 API (pinned 2026-06-16):** `Langfuse(public_key, secret_key, host)` +
`start_as_current_observation(name, as_type="generation"|"chain", model, input, usage_details,
metadata)` (OTel-context nesting) + `.update()` + `.flush()`. Demo `--trace` wires it.

**Verified live 2026-06-16** (US Cloud). Operational lessons, now guarded in code/docs:
- **`.env` is auto-loaded** at the entry points (demo + `tests/conftest.py`, via `python-dotenv`,
  `override=False` so shell wins) — loaded from the **repo-root** `.env` explicitly, because bare
  `find_dotenv()` under `uv run` resolves to `~/.env`. Library code still just reads `os.getenv`.
- **`LANGFUSE_HOST` must match the keys' region** — US keys vs the EU host (the default I shipped)
  fail with a silent `401`; "sent" without verification is a lie. `Tracer.verify()` → `auth_check()`
  now confirms delivery, and `--trace` prints ✓/✗ with the region hint. `.env.example` spells out
  US/EU/self-host. This was the whole "sent but empty UI" saga — root cause was a host/region mismatch.

---

## D19 — Frozen scenario set: in-repo harness, external authorship is the validity ✅ (Stage 3 #2, D9)

**Decision.** The gate's input corpus lives **in-repo** as markdown+frontmatter files under
`scenarios/`, loaded by `scenarios.py` (`Scenario`, `ScenarioSet`, `load_scenarios`) and fed to
the loop through a `ScenarioTicketSource(TicketSource)` — so a scenario is indistinguishable from
a real JIRA ticket to the agents, and `run_loop` is unchanged. In-repo (vs authoring in JIRA)
because the set must be version-controlled, immutable, and replayable (NFR1); `ScenarioSet.fingerprint()`
is an order-independent sha256 over canonical content **including provenance and expectations**, so
every eval result is attributable to an exact set version. Parsing is dep-free (frontmatter is simple
`key:value`; bodies are prose, may contain `---`). `scripts/run_scenarios.py` runs the set and summarises.

**The validity boundary (the load-bearing point, D9/D7).** A scenario set is only a credible gate
if it is **externally authored and anonymized** — if the build team or a model writes the tickets,
the gate measures self-consistency, not capability (the inputs-side twin of the same-family-LLM-judge
anti-pattern, D7). The harness can freeze/load/attribute a corpus; it **cannot** supply that validity.
So: the 3 scenarios shipped are **illustrative placeholders** (`source: illustrative`, `anonymized: true`)
— format examples, not the gate corpus. Enforced, not just documented: a test asserts every shipped
scenario is anonymized and not labelled `real`, and `run_scenarios.py` prints a loud "ILLUSTRATIVE —
NOT A VALID GATE CORPUS" banner + per-row source labels so a green illustrative run can never be
mistaken for a gate verdict. The real corpus is dropped in later by a senior architect not on the build team.

**Schema (from per-consumer analysis):** required `id/title/body` (the BA's ticket); provenance
`source/anonymized/author` (architect trust); optional `expected_key_requirements/notes` (author-supplied
hints for the *advisory* omission metric — never derived by us, never required).

**Verified:** harness exercised end-to-end — the 3 illustrative scenarios ran through the real loop
3/3 terminal, 0 omissions. 86 offline tests; agents/loop/models/etc zero-diff; no new runtime dep.

---

## D20 — Architect verdict capture: in-repo verdict log, human-only sink ✅ (Stage 3 #3, resolves OD3)

**Decision.** The architect's accept/revise/reject is captured as an **in-repo verdict log** —
`Verdict` files (markdown+frontmatter) under `verdicts/`, behind a `VerdictStore` seam
(`verdicts.py`: `FileVerdictStore` + `InMemoryVerdictStore` fake). Each verdict carries
`scenario_id` + `adr_id` + `set_fingerprint` + reviewer + notes, so it's attributable to an exact
ADR on an exact corpus version (replayable). Chosen over Langfuse score annotations / a Confluence
page field (the other OD3 candidates) for being version-controlled, dependency-free, and replayable;
either can be added later behind the same seam. `scripts/record_verdict.py` records one (prompts or args).

**The invariant (FirstPrinciples / D7 / NFR4): a human-only sink.** `VerdictStore` records *human*
verdicts only — no machine score is ever written as a `Verdict`. The LLM judge (Stage 3 #4) is a
**separate stream**, *compared* to these verdicts via Cohen's κ, never merged. That structural
separation is what makes "the human verdict is never overridden by a machine score" true rather than
a promise. Verified: `.record()` has no machine caller; no verdicts are shipped in the repo (a
fabricated verdict would invalidate the gate exactly as a fabricated scenario would).

**Honest gate readout.** `summarize_verdicts()` reports accept rate with a **Wilson 95% lower bound**
(D7 says "≥70% accept, lower 95% CI" — not the point estimate), reject rate, and `meets_gate`
(accept-lower-95 ≥ 0.70 AND reject < 0.10), optionally filtered to one set fingerprint. Small samples
correctly fail (e.g. 1/1 accept → 100% rate but 21% lower bound → not a pass). stdlib math, no dep.

**Verified:** 97 offline tests (model round-trip, store record/load, Wilson edge/monotonic, gate
boolean per D7); CLI records + prints the readout; agents/loop/etc zero-diff; no new runtime dep.

---

## Open decisions

- *(none — OD1 resolved by D10, OD2 by D15, OD3 by D20, OD4 by D14.)* Remaining Stage-3 work is
  tracked in the README "Continuing this work": the advisory eval harness + κ (#4), and — outside the
  build — sourcing the externally-authored scenario corpus (D9) and architect verdicts (D20).
