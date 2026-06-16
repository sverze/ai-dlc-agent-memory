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
    SAAgent,
    ScenarioTicketSource,
    TERMINAL_STATES,
    load_scenarios,
    make_model_client,
    run_loop,
)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ENV_PATH, override=False)


def _run_scenario(source: ScenarioTicketSource, scenario_id: str, *, ba_model: str | None) -> dict:
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
            return {"id": scenario_id, "ok": False, "error": f"{type(exc).__name__}: {str(exc)[:100]}"}
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

    scenario_set = load_scenarios(directory)
    source = ScenarioTicketSource(scenario_set)

    all_illustrative = len(scenario_set) > 0 and all(
        s.source == "illustrative" for s in scenario_set
    )

    print("═" * 72)
    print("🧪 FROZEN SCENARIO SET")
    print("═" * 72)
    print(f"  dir:         {directory}")
    print(f"  scenarios:   {len(scenario_set)}  ({', '.join(scenario_set.ids())})")
    print(f"  fingerprint: {scenario_set.fingerprint()}")
    non_anon = [s.id for s in scenario_set if not s.anonymized]
    if non_anon:
        print(f"  ⚠️  NOT anonymized (must not happen for real data, D9): {non_anon}")
    if all_illustrative:
        print()
        print("  " + "!" * 66)
        print("  !! ILLUSTRATIVE SET — NOT A VALID GATE CORPUS (D9).")
        print("  !! This run demonstrates the harness. It is NOT a gate verdict —")
        print("  !! the gate requires an EXTERNALLY-AUTHORED, anonymized corpus.")
        print("  " + "!" * 66)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("\n  (no ANTHROPIC_API_KEY — set keys in .env to run the loop; set loaded above)")
        return 0

    print("\n" + "═" * 72)
    print("▶️  RUNNING each scenario through the real loop")
    print("═" * 72)
    results = []
    for sid in scenario_set.ids():
        print(f"  … {sid}")
        results.append(_run_scenario(source, sid, ba_model=ba_model))

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
    if all_illustrative:
        print("  ⚠️  ILLUSTRATIVE run — NOT a gate result (D9): the corpus is placeholder, not external.")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
