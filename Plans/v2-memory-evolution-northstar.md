# V2 North-Star — the evolving swarm

**Status: north-star (design intent), not a build plan to execute now.** V2 is gated on the V1
hypothesis holding (a senior architect accepts ≥70% of ADRs, D7). This document locks the
*destination* so the project stops drifting into plumbing — it is the answer to "what is this
ultimately for," and it centres the two things V1 deliberately deferred: **how humans and agents
interact**, and **how the agents evolve**.

Companion to: PRD `2026-06-08-collective-agentic-memory-prd-v1.md` (§12 roadmap), the research doc
(the 5-layer memory model), and `DECISIONS.md` (D1–D23).

---

## 1. Where V1 ends

The research doc defines a **five-layer memory model**. V1 built the substrate and the proving loop:

```
L5  EPISODIC    — what happened across runs (Zep/Hindsight)      ⬜ V2  ← the compound-interest layer
L4  SEMANTIC    — the shared temporal graph (Graphiti/Neo4j)      ✅ V1 (D10/D15)
L3  PROCEDURAL  — how to act: the Skill Registry                  ⬜ V2
L2  WORKING     — in-process typed artifacts                      ✅ V1
L1  PERSONA     — who I am: per-agent memory (Mem0)               ⬜ V2
```

V1 proved a requirement can pass through L4 shared memory and be faithfully transformed (BA→graph→SA→ADR),
with a runnable human gate + advisory eval (D18–D21). **The agents today are stateless across tickets**
(per-run `group_id`, OC3) and run on **static persona headers**. They do not learn. That is the gap V2 closes.

**Seams V1 already left for V2 (this is why V2 is drop-in, not a rebuild):**
- `ModelClient.complete(system=…)` — the `system` slot is the reserved injection point for L1 persona memory (Mem0).
- Graphiti is **bi-temporal** — it can host L5 episodic memory directly; the per-run `group_id` becomes a cross-run namespace.
- The **negotiation FSM** (`analysis ⇄ clarification`, D12) is a propose→push-back→revise→converge loop — extend it to SA↔human.
- The **eval harness** (D21) is the measurement instrument: clarification-rounds, omission rate, accept-rate, judge-κ — the dials that show whether the swarm is getting smarter.
- `RunRecord` + verdicts + set fingerprints (D20/D23) make every run attributable — the substrate for longitudinal learning signals.

---

## 2. The unifying thesis (why the two missing dimensions are one loop)

The human review conversation **is the teaching signal**; the "dreaming" consolidation **is what turns
it into an evolved persona**:

```
   run  ─▶  experience            L5 episodic: the artifacts, the BA↔SA negotiation,
            │                      and the architect's comments + verdict
            ▼
   dream ─▶ consolidate            offline reflection: "on auth tickets the architect always
            │                      pushes on rate-limiting" → fold into who the SA *is* (L1)
            ▼                      and how it acts (L3)
   next run ─▶ evolved persona     proposes better options up front; needs less back-and-forth
```

V1 asked *"does one requirement survive transformation?"* **V2 asks *"does the swarm get measurably
smarter, ticket over ticket, taught by its human reviewers?"*** The PRD already predicted the
measurable signature: as L5 accumulates, **clarification-rounds trend down**.

---

## 3. Dimension A — the human-interaction review loop

V1's verdict capture (D20) is *measurement*, not the lived workflow. A senior SA doesn't click a
radio button — they discuss optionality and iterate. The real design:

- **Optioned ADRs.** The SA emits ADRs that lead with `considered_options` (the `DecisionOption`
  pros/cons we already model) — a *proposal to discuss*, not a decree.
- **Review as negotiation.** The human comments where they already work (Confluence/JIRA, D17); the
  SA agent reads the comments and **revises** the ADR — another negotiation round. This is the BA↔SA
  clarification loop (D12) extended one level up to **SA↔human**, reusing the FSM, with the same
  clarify-cap → escalation discipline.
- **Verdict as terminal state.** accept/revise/reject is the *outcome* of the conversation (captured
  as a byproduct, feeding D20), not a form the human fills first.

**Measured by:** number of review rounds to convergence (should fall as personas evolve), accept-rate, omission.

**Open design choices:** revise = new ADR version on the page vs in-place edit; JIRA vs Confluence as the
comment channel; how the agent detects a new human comment and decides revise-vs-ask-vs-hold.

---

## 4. Dimension B — the memory-evolution layers

Build order mirrors the research doc and the measure-don't-assume ethos (each layer's lift is *measured*
against the human gate before the next is built — the same discipline that made V1 build L4 before L1).

### L5 — Episodic memory (first; cheapest lever, foundation of everything)
Capture each run's experience across runs (artifacts, the negotiation, the human verdict + comments).
Lift the per-run `group_id` restriction → a cross-run episodic namespace in Graphiti (bi-temporal already).
At task start, retrieve the N most-similar past experiences to narrow the prior.
**Measured:** clarification-rounds ↓, omission ↓ as episodes accumulate. **Kills the "agents have amnesia" gap.**

### L1 — Persona memory (Mem0, via the reserved `system` slot)
Per-agent scoped memory (preferences, role facts, tool affinities) injected as a compressed persona header.
**Measured:** lift over the static V1 header — the comparison the v1.1 review deferred so it could be *measured, not assumed*.

### L3 — Skill Registry (procedural memory)
A queryable catalogue of "when to use code vs a tool," starting as YAML per persona, evolving to
vector-retrieval past ~50 skills. An evidence hook after each task writes success/failure/path-taken.
**Measured:** fewer wrong tool-path choices; the primary long-term determinism lever.

### The "dreaming" consolidation engine (LAST — research-led, deferred)
The offline phase that reads accumulated L5 episodes + human verdicts/comments and **rewrites** L1
persona memory + L3 skills — i.e. personas that *evolve*, not just *accumulate*. This is the genuinely
novel, highest-risk/highest-reward piece, and the original docs under-specify it.

> **Explicitly research-flagged (sverze's steer, 2026-06).** The "dreaming/consolidation" pattern is
> new in public LLM offerings (Claude / Claude Code have only recently shipped memory of this kind).
> **Ride the labs' learnings — investigate via internet research (Claude memory, sleep-time compute,
> Generative Agents "reflection," memory-consolidation literature) before designing.** Do not invent it
> from first principles now.

**The hard problems this engine must answer (do not hand-wave):**
- **Drift & catastrophic forgetting** — personas degrading as they self-rewrite.
- **Auditability vs determinism (NFR1)** — an evolving prompt is a moving target; persona versions must be
  **pinned, fingerprinted, and diffable** (exactly like the scenario set), so a run is attributable to a persona version.
- **Governance** — a human reviews/approves a persona's evolution. A self-rewriting SA that no one
  supervises is how you get confident nonsense at scale.
- **Cadence** — idle-time / threshold (N new episodes) / scheduled.

---

## 5. Measurement discipline (the project's spine, carried into V2)

Every layer earns its place by **measured lift against the human verdict**, never assumed (D7/NFR4). The
V1 eval harness is the instrument; V2 makes the metrics **longitudinal**, not single-shot:
clarification-rounds/ticket, accept-rate, omission rate, judge-κ — tracked *over time* as memory accumulates.
The human gate stays primary throughout; the machine metrics only ever explain it.

---

## 6. Sequencing & gates

1. **Gate first.** Run the V1 hypothesis gate on a real external corpus. If it fails, fix V1 (the eval
   harness shows where) before any V2 work. **Build nothing below the gate (D7).**
2. If it holds: **L5 episodic** → **L1 persona** → **L3 skills**, each measured before the next.
3. **Dreaming engine** last, after the internet research, with the governance/auditability guardrails above.
4. Dimension A (the conversational review loop) can land alongside L5 — it produces the richest episodic signal.

Also deferred (PRD §12, not gating): more personas (Security/QA/Ops), LiteLLM routing (+ local models
like Ollama — the `ModelClient` seam already makes them drop-in, observed by Langfuse for free), Figma,
second-tier tools, production data + scale hardening.

---

## 7. The one-line destination

V1 is a memory **substrate** that works. V2 is the memory **system**: personas that learn from the
humans who review them — measurably getting better, ticket over ticket. That is the product worth building.
