# Frozen scenario set — the Stage-3 gate corpus

These are the delivery tickets the loop is judged against (D7/D9). Each `*.md` file is one
scenario: a `---` frontmatter block + a prose ticket body. Loaded via
`agentic_memory.load_scenarios("scenarios")` and fed to the loop through `ScenarioTicketSource`,
so a scenario is indistinguishable from a real JIRA ticket to the agents. The set is
fingerprinted (`ScenarioSet.fingerprint()`) so every eval result is attributable to an exact version.

## ⚠️ Validity boundary — read before adding scenarios (D9)

**The gate is only credible if the scenarios are *externally authored and anonymized*.** If the
build team — or a model — writes the tickets, the gate measures self-consistency, not capability
(the same reason a same-family LLM judge can't grade itself, D7). The harness can freeze, load, and
attribute a corpus; it **cannot** supply that validity.

So:
- Every file shipped here today is an **illustrative placeholder** (`source: illustrative`) — a
  *format example*, **not** part of the real gate corpus.
- The real corpus must be authored by someone **not on the build team** (e.g. a senior SA), drawn
  from real delivery work, and **anonymized** (no client/person/system identifiers) before it lands here.
- Every scenario must carry `anonymized: true` and a truthful `source`/`author`.

## File format

```markdown
---
id: SCEN-001
title: One-line ticket summary (acts as the JIRA "summary")
source: illustrative            # or e.g. "anonymized-prod-2026Q2"
anonymized: true
author: build-team (ILLUSTRATIVE)   # the real corpus names the external author
expected_key_requirements: link expires in 30 min; attempts logged   # OPTIONAL, ';'-separated, author-supplied
notes: anything the reviewer should know                              # OPTIONAL
---
The ticket body as prose — a user story, context, constraints. Free to contain
multiple paragraphs and even `---` rules; only the first frontmatter block is parsed.
```

Required: `id`, `title`, body. Provenance: `source`, `anonymized`, `author`. Optional (for the
advisory omission metric, never derived by us): `expected_key_requirements`, `notes`.

## Running the set

```bash
uv run --extra live python scripts/run_scenarios.py        # real models; prints fingerprint + per-scenario summary
```
(Mind Gemini's 20-requests/day/model free-tier limit — a handful of scenarios is fine.)
