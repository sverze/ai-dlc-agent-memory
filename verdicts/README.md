# Architect verdicts — the gate's primary signal (D7 / D20)

One file per ADR-under-review: `<scenario_id>.md`, markdown+frontmatter. These record a senior
architect's **accept / revise / reject** + notes on each ADR the loop produced for a scenario.
This is **the** success measure for V1 (≥70% accept on the lower 95% CI, <10% reject — D7); the
machine metrics (LLM judge, κ) are *advisory* and measured **against** these, never overriding them.

```markdown
---
scenario_id: SCEN-001
adr_id: adr-1
set_fingerprint: c79db637958e…        # from scripts/run_scenarios.py — ties the verdict to a corpus version
verdict: accept                        # accept | revise | reject
reviewer: a.architect (external)
reviewed_at: 2026-06-18
---
Free-text notes: what was good, what was missing, why this verdict.
```

Record one with the CLI (prompts if args omitted):

```bash
uv run python scripts/record_verdict.py --scenario SCEN-001 --adr adr-1 \
    --fingerprint <set-fingerprint> --verdict accept --reviewer "a.architect" --notes "…"
```

## ⚠️ Who may record a verdict (read before adding files)

- The verdict must come from a **senior architect not on the build team** — the same
  independence that makes the scenario corpus credible (D9) makes the verdict credible (D7).
- This directory is a **human-only sink.** Nothing machine-generated is ever written here — the
  LLM judge lives in a separate stream and is *compared* to these verdicts (κ), never merged in.
  That separation is what keeps "the human verdict is never overridden" structurally true.
- No verdicts are shipped in the repo: a fabricated verdict would invalidate the gate exactly as a
  fabricated scenario would. Real verdicts accrue here as the external reviewer works through the set.
