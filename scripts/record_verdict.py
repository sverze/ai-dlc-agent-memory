"""Record one architect verdict on an ADR (Stage 3 #3, D20) — the gate's primary signal.

This is for the reviewing architect (ideally not on the build team). It writes a verdict file
to verdicts/ , tied to the scenario, the ADR, and the scenario-set fingerprint, plus a gate
readout so far. The LLM judge is a SEPARATE stream (#4) — nothing here is machine-generated.

    uv run python scripts/record_verdict.py \
        --scenario SCEN-001 --adr adr-1 --fingerprint <set-fingerprint> \
        --verdict accept --reviewer "a.architect" --notes "clear, traceable"

Run with no args to be prompted. Use the fingerprint printed by scripts/run_scenarios.py.
"""

from __future__ import annotations

import sys

from agentic_memory import (
    FileVerdictStore,
    Verdict,
    VerdictDecision,
    summarize_verdicts,
)


def _arg(args: list[str], flag: str) -> str | None:
    return args[args.index(flag) + 1] if flag in args else None


def main() -> int:
    args = sys.argv[1:]
    directory = _arg(args, "--dir") or "verdicts"

    def ask(flag: str, prompt: str, *, required: bool = True) -> str:
        val = _arg(args, flag)
        if val is None:
            val = input(f"{prompt}: ").strip()
        if required and not val:
            print(f"  {flag} is required.")
            raise SystemExit(2)
        return val

    scenario_id = ask("--scenario", "scenario id (e.g. SCEN-001)")
    adr_id = ask("--adr", "ADR id (e.g. adr-1)")
    fingerprint = ask("--fingerprint", "scenario-set fingerprint (from run_scenarios.py)")
    raw = ask("--verdict", "verdict [accept|revise|reject]").lower()
    try:
        verdict = VerdictDecision(raw)
    except ValueError:
        print(f"  '{raw}' is not one of accept|revise|reject.")
        return 2
    reviewer = ask("--reviewer", "reviewer (name/handle — ideally NOT the build team)")
    notes = _arg(args, "--notes")
    if notes is None:
        notes = input("notes (optional): ").strip()

    store = FileVerdictStore(directory)
    store.record(
        Verdict(
            scenario_id=scenario_id, adr_id=adr_id, set_fingerprint=fingerprint,
            verdict=verdict, reviewer=reviewer, notes=notes,
        )
    )
    print(f"\n  ✓ recorded {verdict.value.upper()} for {scenario_id} (adr {adr_id}) → {directory}/{scenario_id}.md")

    readout = summarize_verdicts(store.all(), set_fingerprint=fingerprint)
    print("\n  gate readout for this set version so far:")
    print(f"    verdicts: {readout.total}  (accept {readout.accept} / revise {readout.revise} / reject {readout.reject})")
    print(f"    accept rate: {readout.accept_rate:.0%}  (95% lower bound {readout.accept_lower95:.0%})")
    print(f"    reject rate: {readout.reject_rate:.0%}")
    print(f"    meets gate (≥70% accept lower-95, <10% reject): {readout.meets_gate}")
    print("    NB: advisory machine metrics (LLM judge / κ) are Stage 3 #4 — measured against this, not merged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
