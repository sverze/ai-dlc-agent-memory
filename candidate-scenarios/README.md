# Candidate scenarios — AI DRAFTS, not the gate corpus

These `CAND-*.md` files are **AI-drafted candidate tickets** (by Coco), created to lower the
activation energy for assembling the real gate corpus. They are deliberately kept **out of
`scenarios/`** so they cannot be mistaken for the gate corpus or pollute its fingerprint.

## ⚠️ They do NOT count until a human owns them (D9/D7)

A scenario set is only a credible gate if it's **externally authored and anonymized** — if the
build team or a model writes the tickets, the gate measures self-consistency, not capability. These
drafts are a *starting point*, not the corpus. Before any of these counts:

1. A person **not on the build team** (a senior BA/PM) reads each draft, **edits it to reflect real
   delivery work**, and **anonymizes** it (no client/person/system identifiers).
2. They set truthful provenance: `source:` to the real source (e.g. `anonymized-delivery-2026Q2`),
   `author:` to themselves, and confirm `anonymized: true`.
3. They **move the vetted file into `scenarios/`** (renaming to a `SCEN-*` id). Only files in
   `scenarios/` are the gate corpus.

Discard any draft that doesn't map to something real. Aim for **15–20** vetted tickets in
`scenarios/` (the gate's Wilson lower bound needs roughly that many to be able to clear ≥70%).

## Previewing the drafts (optional, spends model quota)

```bash
uv run --extra live python scripts/run_scenarios.py --dir candidate-scenarios --review
```

This runs the loop over the drafts and prints each ADR — useful to sanity-check that a draft is
"meaty" enough to produce a real architecture decision. It is **not** a gate run (these aren't the
corpus). The header will note they're not the real set.
