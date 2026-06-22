"""Advisory eval over the frozen scenario set (Stage 3 #4) — the gate dashboard.

For each scenario: run the loop (real models) → score traceability/omission (deterministic) →
run the cross-family LLM judge (advisory) → load the human verdict (if recorded). Then print:
the structured scores, the HUMAN gate readout (the actual gate), and judge-vs-human κ (advisory,
measured against the human, never moving the gate).

    uv run --extra live python scripts/run_eval.py
    uv run --extra live python scripts/run_eval.py --ba-model gemini-2.5-flash-lite

Each scenario costs ~3 model calls (BA + SA + judge) — mind Gemini's free tier. The judge runs
on the BA's Gemini binding (cross-family to the SA's Claude ADR, D7).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

from agentic_memory import (  # noqa: E402
    AgentPersona,
    JudgeVerdict,
    build_eval_report,
    judge_adr,
    load_runs,
    load_scenarios,
    load_verdicts,
    make_model_client,
    score_traceability,
)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ENV_PATH, override=False)


def _judge_cache_path(fingerprint: str, scenario_id: str) -> Path:
    return Path("runs") / fingerprint / "judge" / f"{scenario_id}.json"


def _load_cached_judge(fingerprint: str, scenario_id: str) -> JudgeVerdict | None:
    p = _judge_cache_path(fingerprint, scenario_id)
    return JudgeVerdict.model_validate_json(p.read_text()) if p.exists() else None


def _save_judge(fingerprint: str, jv: JudgeVerdict) -> None:
    p = _judge_cache_path(fingerprint, jv.scenario_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(jv.model_dump_json(indent=2), encoding="utf-8")


def _is_quota_error(exc: Exception) -> bool:
    s = str(exc)
    return "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower()


def main() -> int:
    _load_dotenv()
    args = sys.argv[1:]
    scen_dir = args[args.index("--dir") + 1] if "--dir" in args else "scenarios"
    verdict_dir = args[args.index("--verdicts") + 1] if "--verdicts" in args else "verdicts"
    ba_model = args[args.index("--ba-model") + 1] if "--ba-model" in args else None

    scenario_set = load_scenarios(scen_dir)
    fp = scenario_set.fingerprint()
    runs = load_runs(fp)  # ADRs generated + persisted by run_scenarios.py — NOT regenerated here
    try:
        human_verdicts = [v for v in load_verdicts(verdict_dir) if v.set_fingerprint == fp]
    except FileNotFoundError:
        human_verdicts = []

    _SYNTHETIC = {"illustrative", "draft-candidate", "synthetic-dry-run"}
    not_real = any(s.source in _SYNTHETIC for s in scenario_set)

    print("═" * 72)
    print("🧮 ADVISORY EVAL — scores are advisory; the gate is the HUMAN verdict (D7)")
    print("═" * 72)
    print(f"  set fingerprint: {fp}")
    print(f"  stored ADRs: {len(runs)}   human verdicts on this set: {len(human_verdicts)}")
    if not_real:
        srcs = sorted({s.source for s in scenario_set if s.source in _SYNTHETIC})
        print(f"  ⚠️  NON-GATE corpus ({', '.join(srcs)}) — this is a DRESS REHEARSAL, not a valid")
        print("      hypothesis gate (D9). A real result needs an externally-authored, anonymized corpus.")

    if not runs:
        print("\n  No stored ADRs for this set — generate them first (cheap to resume):")
        print("    uv run --extra live python scripts/run_scenarios.py")
        return 1

    # Score (free) + judge (1 model call each, cached). NO loop regeneration here.
    override = {AgentPersona.BUSINESS_ANALYST: ba_model} if ba_model else None
    client = make_model_client(model_by_role=override) if os.getenv("ANTHROPIC_API_KEY") else None
    traceability, judge_verdicts = [], []
    for sid, rec in runs.items():
        if not (rec.artifact and rec.adr):
            continue
        traceability.append(score_traceability(rec.artifact, rec.adr, scenario_id=sid))
        cached = _load_cached_judge(fp, sid)
        if cached is not None:
            judge_verdicts.append(cached)
            print(f"  … {sid}  (judge cached)")
            continue
        if client is None:
            continue  # no keys → structured scores only, skip judging
        print(f"  … {sid}  (judging)")
        try:
            jv = judge_adr(client, rec.artifact, rec.adr, scenario_id=sid)
            _save_judge(fp, jv)
            judge_verdicts.append(jv)
        except Exception as exc:
            if _is_quota_error(exc):
                print(f"\n  ⚠️ QUOTA EXHAUSTED (429) judging {sid}. Stopping — judged verdicts are cached.")
                print("     Re-run after reset (or --ba-model gemini-2.5-flash-lite); it resumes from the cache.")
                break
            print(f"      ⚠️ {sid} judge failed: {type(exc).__name__}: {str(exc)[:80]}")

    report = build_eval_report(traceability, human_verdicts, judge_verdicts, set_fingerprint=fp)

    print("\n" + "═" * 72)
    print("📊 REPORT")
    print("═" * 72)
    print("  Deterministic (structured):")
    print(f"    mean omission rate:     {report.mean_omission_rate:.0%}   (target <5%)")
    print(f"    mean traceability rate: {report.mean_traceability_rate:.0%}")
    g = report.human_gate
    print("  Human gate (THE gate, D7):")
    if g.total == 0:
        print("    no human verdicts recorded for this set yet — record them with scripts/record_verdict.py")
    else:
        print(f"    accept {g.accept}/{g.total} ({g.accept_rate:.0%}, lower-95 {g.accept_lower95:.0%}) "
              f"reject {g.reject_rate:.0%} → meets_gate={g.meets_gate}")
    print("  Judge (ADVISORY — compared to human, never gating):")
    if report.judge is None:
        print("    no overlap of judge + human verdicts yet (record human verdicts to compute κ)")
    else:
        j = report.judge
        caveat = ""
        if j.degenerate:
            caveat = "  ⚠️ degenerate (one verdict only — κ proves nothing)"
        elif j.insufficient_sample:
            caveat = "  ⚠️ insufficient sample (κ unstable < ~30)"
        print(f"    n={j.n}  agreement={j.agreement_rate:.0%}  κ={j.kappa:.2f} ({j.band})  "
              f"trusted={j.trusted}{caveat}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
