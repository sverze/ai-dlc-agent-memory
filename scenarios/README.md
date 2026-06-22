# Scenario set — the gate corpus directory

Each `*.md` here is one delivery ticket: `---` frontmatter + a prose body. Loaded via
`agentic_memory.load_scenarios("scenarios")`, fed to the loop through `ScenarioTicketSource`
(so a scenario is indistinguishable from a real JIRA ticket to the agents), and fingerprinted
so every eval result is attributable to an exact set version.

## ⚠️ Current contents are a SYNTHETIC DRY-RUN set — NOT a valid gate corpus

The `SCEN-1xx` files here today are **AI-authored** (`source: synthetic-dry-run`), produced in a
BA/PM persona to let the full human-in-the-loop pipeline be exercised end-to-end on a realistic-sized
set. **A run against them is a dress rehearsal, not the hypothesis gate** — `run_scenarios.py` and
`run_eval.py` both print a loud NON-GATE warning when they detect synthetic sources.

**Why they can't be the real gate (D9/D7):** a scenario set is only credible if it is *externally
authored and anonymized*. If the build team — or a model — writes the tickets, the gate measures
self-consistency, not capability. To produce a **real** gate result, an external author (a senior
BA/PM not on the build team) must replace these with anonymized tickets drawn from real delivery
work, setting truthful `source:`/`author:` and `anonymized: true`, then run the gate.

## File format

```markdown
---
id: SCEN-201
title: One-line ticket summary (the JIRA "summary")
source: anonymized-delivery-2026Q2     # truthful provenance; synthetic sets use synthetic-dry-run
anonymized: true
author: the external author             # a person not on the build team, for the real corpus
expected_key_requirements: a; b; c      # OPTIONAL, ';'-separated, author-supplied
notes: anything the reviewer should know  # OPTIONAL
---
The ticket body as prose. Free to contain multiple paragraphs and even `---` rules;
only the first frontmatter block is parsed.
```

Required: `id`, `title`, body. Provenance: `source`, `anonymized`, `author`. Optional (advisory
omission metric, never derived by us): `expected_key_requirements`, `notes`.

## Running

```bash
uv run --extra live python scripts/run_scenarios.py --review     # produce + read each ADR, get a verdict command
uv run --extra live python scripts/run_eval.py                   # the dashboard (gate readout + advisory metrics)
```
(Mind Gemini's 20-requests/day/model free-tier limit — ~2–3 calls per scenario.)
