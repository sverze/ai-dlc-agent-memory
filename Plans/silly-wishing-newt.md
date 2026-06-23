# Plan — Unblock the immediate Vertex 429 on Claude Opus 4.8 (Coco Cloud)

## Context

After wiring the Vertex AI Model Garden backend (D25) and fixing ADC auth, the first live run
(`live_demo.py --jira SCRUM-5 --vertex`) failed immediately with:

```
RateLimitError: Error code: 429 - Quota exceeded for
aiplatform.googleapis.com/global_online_prediction_requests_per_base_model
```

We need to (a) understand why a *first* call 429s, and (b) make the system handle this class of
error gracefully so a pilot isn't derailed by throttling.

## Root-cause diagnosis (already established, read-only)

- **Auth is fixed.** ADC now mints a token; quota project = `cloud-coco-2fbfe4`. Not a credential issue.
- **It's the Claude (SA) call, not Gemini.** Our config routes SA = `claude-opus-4-8` @ region `global`,
  BA = `gemini-2.5-flash` @ `us-central1`. The error metric is the **global** online-prediction quota →
  the Claude call. The Gemini/BA call is on a different region/quota and is unaffected.
- **429, not 404 → the model id + region are CORRECT.** A bad model string would 404. So no
  `VERTEX_SA_MODEL` change is needed — `claude-opus-4-8` @ `global` resolves fine.
- **Why it failed on the first request:** a newly-enabled Anthropic partner model on a fresh project
  has little/zero provisioned `online_prediction_requests_per_base_model` quota until granted. This is a
  **provisioning gap, not contention** — which is also why retrying alone won't fix it.
- **Why `live_demo` failed instantly:** its retry loop (`scripts/live_demo.py` ~L131–141) only backs off
  on `503/UNAVAILABLE/overload`; a `429` falls straight through to `raise`.

## Fix — two parts

### Part 1 (PRIMARY, user action in GCP console) — get quota for the Claude base model

This is the actual unblock; no code can substitute for provisioned quota.

1. Console → **IAM & Admin → Quotas & System Limits** (project `cloud-coco-2fbfe4`).
2. Filter **Service = "Vertex AI API"**; search the metric
   `online_prediction_requests_per_base_model` (a.k.a. "Online prediction requests per base model per
   minute per region").
3. Find the row for **region `global`** and the **Anthropic / Claude Opus 4.8 base model**. If the limit
   is `0` or very low, select it → **Edit / Request increase** → submit a modest QPM (e.g. 10–60).
4. Partner-model quota requests are sometimes auto-approved, sometimes manually reviewed (hours–days).
   - **Alternative to confirm:** whether Opus 4.8 in this project should be consumed via **Dynamic
     Shared Quota (DSQ)** (no fixed per-project quota). If DSQ applies, there's nothing to raise and the
     429 is transient contention — which Part 2's backoff handles. Check the model's Model Garden page /
     Anthropic-on-Vertex docs for whether DSQ or explicit quota applies to Opus 4.8.

### Part 2 (SECONDARY, code resilience) — treat 429 as a backoff-retryable transient

Regardless of Part 1, the loop should ride out throttling (DSQ contention, momentary 429s) instead of
dying on the first one.

- **`scripts/live_demo.py`** (retry block ~L131–141): widen the retry predicate to also match
  `429` / `RESOURCE_EXHAUSTED` (reuse the same token list already used in
  `scripts/serve_jira.py::_is_quota_error`), and use **exponential backoff** (e.g. 6s → 12s → 24s) over
  the existing 4 attempts rather than a flat 6s. On final exhaustion, surface a clear "quota — request an
  increase or wait for DSQ" message (distinguish hard-quota from transient by message text where possible).
- **`scripts/serve_jira.py`** (`_sweep`, uses `_is_quota_error` ~L78): currently *stops the sweep* on any
  429 (correct for a daily cap). Add a **bounded per-ticket backoff-retry** (2–3 attempts) before
  treating it as a stop, so a transient Vertex 429 doesn't end the whole sweep; keep the clean-stop +
  "not marked done, will retry" behaviour as the final fallback.
- *(Optional, cleaner)* lift the shared retry/backoff into a tiny helper in `src/agentic_memory/` (e.g.
  `models.py` or a new `retry.py`) so both scripts and any future webhook use one implementation. Keep it
  dependency-free. Only do this if it doesn't balloon scope.

### Files to modify

- `scripts/live_demo.py` — broaden retry predicate + exponential backoff (Part 2).
- `scripts/serve_jira.py` — bounded backoff-retry before quota-stop (Part 2).
- *(optional)* `src/agentic_memory/retry.py` (new) + import in both scripts — shared backoff helper.
- `DECISIONS.md` — short note under D25 recording the quota gotcha + the 429-backoff behaviour.
- No change to `.env` or model id (already correct).

## Verification (end-to-end)

1. **Auth sanity (no cost):** `gcloud auth application-default print-access-token >/dev/null && echo OK`.
2. **Isolate the SA call (1 paid Opus call):** minimal one-shot Claude-on-Vertex call (e.g. a tiny
   `python -c` using `VertexAnthropicModelClient`, or `live_demo.py` with inline text) — once quota is
   granted this returns text instead of 429.
3. **Full loop:** `uv run --extra vertex --extra jira python scripts/live_demo.py --jira SCRUM-5 --vertex`
   → expect a terminal ADR with token usage (BA Gemini + SA Opus both on Vertex).
4. **Resilience unit check (offline, no cost):** a test asserting the retry predicate matches `429` /
   `RESOURCE_EXHAUSTED` and that backoff is bounded — added to the suite (keeps the default run free).
5. **Poller:** label a ticket `ai-dlc`, run `serve_jira.py --vertex`, confirm a transient 429 retries
   rather than aborting the sweep.

## Notes / open items

- If, after a granted quota increase, calls still 429 immediately, the next hypothesis is DSQ-only
  consumption for Opus 4.8 (Part 1 alternative) — then the code backoff is the real fix and no quota
  edit is needed.
- The 429-vs-404 signal already rules out a model-id problem, so `VERTEX_SA_MODEL=claude-opus-4-8`
  stays as-is.

---

## Status (2026-06-23)

Vertex integration is **functionally complete and committed** (D25): `VertexAnthropic/Gemini` clients,
`make_model_client(provider="vertex")`, `--vertex` flag, env-overridable model ids, and `retry.py`
backoff. Live probe confirms **BA Gemini@vertex works**; **SA Opus@vertex is 429-blocked only by quota**
(`base_model: anthropic-claude-opus`, region `global`). Quota increase **requested, pending Google's
email approval**. Auth (ADC), model id, and region are all correct. 135 offline tests green.

## Next steps (post-Vertex integration)

Ordered by dependency. The through-line: GCP work is **pilot enablement**, not the gate — the V1
acceptance hypothesis is still the critical path.

1. **Unblock + first real Vertex ADR (immediate, on quota grant).** When the approval email lands:
   re-run the probe, then the full loop —
   `uv run --extra vertex --extra jira python scripts/live_demo.py --jira SCRUM-5 --vertex` — and
   confirm a terminal ADR (Gemini BA + Opus SA, both on Vertex). First end-to-end run on the enterprise
   model plane. If it still 429s immediately after grant, the model is DSQ-only → the `retry.py` backoff
   is the real fix and a re-run rides it out.
2. **Cloud Run hosting (D25 step 2).** Containerize the poller/webhook so a pilot team hits an
   always-on service, not a laptop. Switch from personal ADC to a **service account** with
   `roles/aiplatform.user`. Prefer a **JIRA-webhook → Cloud Run → `process_ticket`** trigger over
   polling for production (lower latency, no idle cost). `process_ticket` already is the single entry
   point, so this is wiring, not new core.
3. **The real V1 gate (still the critical path, unchanged by GCP).** Externally-authored, anonymized
   scenario corpus (D9) replacing the synthetic dry-run set, + real senior-architect verdicts (D20) →
   `run_eval.py` produces the go/no-go. Vertex/hosting just make a real pilot *possible*; they don't
   move the accept-rate.
4. **Pilot-enablement loose ends (parallel, non-gating).** Miro diagram adapter once creds land (the
   reserved ADR "Diagrams" slot, D17); the **SA↔human conversational review loop** (north-star A in
   `v2-memory-evolution-northstar.md`) so an architect can revise an ADR and the swarm responds.
5. **Agent Engine (deferred until the gate holds + mandate bites, D25 step 4).** Study Agent Engine's
   session/memory bank as input to the V2 memory-evolution layers (L1/L3/L5); port the runtime onto
   Agent Engine only once V1 is validated. The seam design keeps this swap-not-rewrite.
