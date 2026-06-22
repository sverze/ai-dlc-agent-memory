"""Run the frozen scenario set through the real loop — the Stage-3 gate runner.

Loads scenarios/ , prints the set fingerprint (so results are attributable to an exact
version), then drives each scenario through run_loop with real models, summarising the
outcome per scenario. The produced ADRs are what a senior architect then judges (the gate).

    uv run --extra live python scripts/run_scenarios.py
    uv run --extra live python scripts/run_scenarios.py --dir scenarios --ba-model gemini-2.5-flash-lite

Mind Gemini's free tier (20 requests/day/model — ~2 calls per scenario). A single scenario
failure (transient 5xx, schema miss) is reported, not fatal to the batch.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

from agentic_memory import (  # noqa: E402
    AgentPersona,
    BAAgent,
    EventLog,
    FSM,
    InMemoryMemoryStore,
    RunRecord,
    SAAgent,
    ScenarioTicketSource,
    TERMINAL_STATES,
    load_scenarios,
    make_model_client,
    run_exists,
    run_loop,
    save_run,
)


def _is_quota_error(exc: Exception) -> bool:
    s = str(exc)
    return "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower()


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ENV_PATH, override=False)


def _print_adr_for_review(scenario_id: str, art, adr, fingerprint: str) -> None:
    """Print the full ADR for a human to read, then the ready-to-paste verdict command."""
    print("\n" + "─" * 72)
    print(f"📄 REVIEW {scenario_id} — ADR {adr.id}: {adr.title}")
    print("─" * 72)
    print(f"  decision : {adr.decision}")
    print(f"  rationale: {adr.rationale}")
    print(f"  requirement traceability ({len(adr.requirement_traces)}):")
    for t in adr.requirement_traces:
        mark = "✓ addressed" if t.addressed else f"→ deferred ({t.deferred_reason})"
        print(f"    - {t.requirement_id}: {mark}  {t.how or ''}")
    if adr.added_constraints:
        print(f"  architect-added constraints ({len(adr.added_constraints)}):")
        for c in adr.added_constraints:
            print(f"    - {c.text}  (why: {c.justification})")
    omitted = adr.omitted_requirement_ids(art)
    print(f"  ⚖️  omission check: {omitted if omitted else 'NONE ✅'}")
    print(f"\n  ▶ YOUR VERDICT — copy, set accept|revise|reject + notes, run it:")
    print(
        f"    uv run python scripts/record_verdict.py --scenario {scenario_id} "
        f"--adr {adr.id} --fingerprint {fingerprint} \\\n"
        f"        --verdict accept --reviewer \"you\" --notes \"...\""
    )


def _run_scenario(
    source: ScenarioTicketSource, scenario_id: str, *, ba_model: str | None,
    review: bool = False, fingerprint: str = "",
) -> dict:
    override = {AgentPersona.BUSINESS_ANALYST: ba_model} if ba_model else None
    client = make_model_client(model_by_role=override)
    store = InMemoryMemoryStore()
    ba, sa = BAAgent(client, store), SAAgent(client, store)
    fsm = FSM(EventLog(Path(tempfile.mkdtemp()) / "events.jsonl"))
    ticket = source.fetch(scenario_id)

    for _ in range(3):  # transient 5xx → retry
        try:
            r = run_loop(ticket, ba=ba, sa=sa, fsm=fsm)
            art = r.artifact
            omitted = r.adr.omitted_requirement_ids(art) if (r.adr and art) else set()
            # Persist the run so eval never has to regenerate it (decoupled generate/eval).
            save_run(RunRecord(
                scenario_id=scenario_id, set_fingerprint=fingerprint,
                final_state=str(r.final_state), artifact=art, adr=r.adr,
            ))
            if review and r.adr and art:
                _print_adr_for_review(scenario_id, art, r.adr, fingerprint)
            return {
                "id": scenario_id, "ok": True,
                "terminal": r.final_state in TERMINAL_STATES,
                "state": str(r.final_state),
                "reqs": len(art.requirements) if art else 0,
                "omitted": len(omitted),
                "adr": bool(r.adr),
            }
        except Exception as exc:
            if any(s in str(exc) for s in ("503", "UNAVAILABLE", "overload")):
                time.sleep(6)
                continue
            quota = _is_quota_error(exc)
            return {
                "id": scenario_id, "ok": False, "quota": quota,
                "error": f"{type(exc).__name__}: {str(exc)[:100]}",
            }
    return {"id": scenario_id, "ok": False, "error": "provider unavailable after retries"}


def main() -> int:
    _load_dotenv()
    args = sys.argv[1:]
    directory = "scenarios"
    if "--dir" in args:
        i = args.index("--dir"); directory = args[i + 1]; del args[i : i + 2]
    ba_model = None
    if "--ba-model" in args:
        i = args.index("--ba-model"); ba_model = args[i + 1]; del args[i : i + 2]
    review = "--review" in args  # print each full ADR + a ready-to-paste verdict command
    if review:
        args.remove("--review")
    force = "--force" in args  # regenerate even scenarios already saved in runs/
    if force:
        args.remove("--force")

    scenario_set = load_scenarios(directory)
    source = ScenarioTicketSource(scenario_set)

    # Any non-real provenance means this is NOT a valid gate corpus (D9).
    _SYNTHETIC = {"illustrative", "draft-candidate", "synthetic-dry-run"}
    not_real = len(scenario_set) > 0 and any(s.source in _SYNTHETIC for s in scenario_set)

    print("═" * 72)
    print("🧪 FROZEN SCENARIO SET")
    print("═" * 72)
    print(f"  dir:         {directory}")
    print(f"  scenarios:   {len(scenario_set)}  ({', '.join(scenario_set.ids())})")
    print(f"  fingerprint: {scenario_set.fingerprint()}")
    non_anon = [s.id for s in scenario_set if not s.anonymized]
    if non_anon:
        print(f"  ⚠️  NOT anonymized (must not happen for real data, D9): {non_anon}")
    if not_real:
        srcs = sorted({s.source for s in scenario_set if s.source in _SYNTHETIC})
        print()
        print("  " + "!" * 66)
        print(f"  !! NON-GATE SET ({', '.join(srcs)}) — NOT A VALID GATE CORPUS (D9).")
        print("  !! This run demonstrates the harness / is a dress rehearsal. It is NOT a")
        print("  !! gate verdict — the gate requires an EXTERNALLY-AUTHORED, anonymized corpus.")
        print("  " + "!" * 66)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("\n  (no ANTHROPIC_API_KEY — set keys in .env to run the loop; set loaded above)")
        return 0

    print("\n" + "═" * 72)
    print("▶️  RUNNING each scenario through the real loop")
    print("═" * 72)
    fp = scenario_set.fingerprint()
    results = []
    for sid in scenario_set.ids():
        if not force and run_exists(sid, fp):
            print(f"  … {sid}  (cached — skipping; --force to regenerate)")
            results.append({"id": sid, "ok": True, "terminal": True, "state": "cached",
                            "reqs": "-", "omitted": "-", "adr": True})
            continue
        print(f"  … {sid}")
        r = _run_scenario(source, sid, ba_model=ba_model, review=review, fingerprint=fp)
        results.append(r)
        if r.get("quota"):  # daily free-tier cap won't recover within the run — stop cleanly
            done = sum(1 for x in results if x.get("ok"))
            print("\n  " + "!" * 66)
            print(f"  !! QUOTA EXHAUSTED (429) on {sid}. Stopping — {done} scenario(s) saved to runs/.")
            print("  !! Re-run after your daily quota resets (or try --ba-model gemini-2.5-flash-lite);")
            print("  !! already-saved scenarios are skipped, so it resumes where it left off.")
            print("  " + "!" * 66)
            break

    print("\n" + "═" * 72)
    print("📊 SUMMARY — the ADRs produced are what an architect then judges")
    print("═" * 72)
    for r in results:
        src = scenario_set.get(r["id"]).source
        if r.get("ok"):
            print(f"  {r['id']} [{src}]: ✅ {r['state']:<10} reqs={r['reqs']}  omitted={r['omitted']}  adr={r['adr']}")
        else:
            print(f"  {r['id']} [{src}]: ❌ {r['error']}")
    ok = sum(1 for r in results if r.get("ok") and r.get("terminal"))
    print(f"  terminal: {ok}/{len(results)}   |   set fingerprint: {scenario_set.fingerprint()[:12]}…")
    if not_real:
        print("  ⚠️  NON-GATE run — NOT a gate result (D9): the corpus is synthetic/illustrative, not external.")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
