"""End-to-end BA→SA loop tests.

`test_happy_path_roundtrip` prints a readable trace of the whole run — see it with:

    uv run pytest tests/test_loop.py -s -k happy
"""

from agentic_memory import (
    ADR,
    AcceptanceCriterion,
    BAAgent,
    ClarificationRequest,
    DLCState,
    EventLog,
    FakeModelClient,
    FSM,
    InMemoryMemoryStore,
    Requirement,
    RequirementsArtifact,
    RequirementTrace,
    SAAgent,
    SAResponse,
    TicketInput,
    run_loop,
)

TICKET = TicketInput(
    id="JIRA-42",
    body="As a user I want zero-downtime deploys with fast rollback and an audit trail.",
)


def _artifact() -> RequirementsArtifact:
    return RequirementsArtifact(
        id="req-1",
        source_ticket_id="JIRA-42",
        title="Zero-downtime deploys",
        summary="Ship releases without dropping requests; support fast rollback; audit each deploy.",
        requirements=[
            Requirement(id="r-1", text="No request dropped during a deploy"),
            Requirement(id="r-2", text="Roll back a bad release within 30 seconds"),
            Requirement(id="r-3", text="Every deploy is recorded in an audit log"),
        ],
        acceptance_criteria=[AcceptanceCriterion(id="ac-1", text="zero 5xx during rollout")],
        key_facts=["target platform is Kubernetes", "availability SLA is 99.95%"],
        open_questions=["Is blue-green acceptable, or is canary required?"],
    )


def _adr(trace_ids, *, deferred=None) -> ADR:
    traces = [RequirementTrace(requirement_id=i, addressed=True, how=f"handled by design ({i})") for i in trace_ids]
    for i in deferred or []:
        traces.append(RequirementTrace(requirement_id=i, addressed=False, deferred_reason="out of scope for v1"))
    return ADR(
        id="adr-1",
        source_requirements_id="req-1",
        title="Blue-green deployment with versioned rollback",
        context="Requirements demand zero-downtime releases with fast rollback and auditability.",
        decision="Adopt blue-green deploys behind the load balancer; keep N-1 live for instant rollback.",
        rationale="Blue-green gives atomic cutover (no dropped requests) and trivial rollback by swapping back.",
        requirement_traces=traces,
    )


def _ba(store, *, responses):
    return BAAgent(FakeModelClient(responses), store)


def _sa(store, *, responses):
    return SAAgent(FakeModelClient(responses), store)


def _fsm(tmp_path, **kw):
    return FSM(EventLog(tmp_path / "events.jsonl"), **kw)


# --------------------------------------------------------------------------


def test_happy_path_roundtrip(tmp_path, capsys):
    store = InMemoryMemoryStore()
    ba = _ba(store, responses=[_artifact().model_dump_json()])
    sa_decide = SAResponse(adr=_adr(["r-1", "r-2", "r-3"])).model_dump_json()
    sa = _sa(store, responses=[sa_decide])
    fsm = _fsm(tmp_path)

    result = run_loop(TICKET, ba=ba, sa=sa, fsm=fsm)

    # --- assertions ---
    assert result.final_state is DLCState.DECISION
    assert result.adr is not None
    assert result.clarify_rounds == 0
    omitted = store.omitted_requirement_ids("JIRA-42", "adr-1")
    assert omitted == set()
    assert store.get_node("adr-1").canonical is True  # orchestrator-promoted

    # --- print a readable trace so the result is visible ---
    with capsys.disabled():
        _print_run("HAPPY PATH", TICKET, result, store, fsm)


def test_clarification_then_decision(tmp_path, capsys):
    store = InMemoryMemoryStore()
    ba = _ba(store, responses=[_artifact().model_dump_json(), "Canary is required, not blue-green."])
    sa_clarify = SAResponse(
        clarifications=[ClarificationRequest(requirement_id="r-2", question="Is canary required?")]
    ).model_dump_json()
    sa_decide = SAResponse(adr=_adr(["r-1", "r-2", "r-3"])).model_dump_json()
    sa = _sa(store, responses=[sa_clarify, sa_decide])
    fsm = _fsm(tmp_path)

    result = run_loop(TICKET, ba=ba, sa=sa, fsm=fsm)

    assert result.final_state is DLCState.DECISION
    assert result.clarify_rounds == 1
    assert result.adr is not None
    with capsys.disabled():
        _print_run("CLARIFICATION → DECISION", TICKET, result, store, fsm)


def test_omission_is_detected(tmp_path):
    store = InMemoryMemoryStore()
    ba = _ba(store, responses=[_artifact().model_dump_json()])
    # SA addresses r-1, r-2 but silently drops r-3 (no trace at all)
    sa = _sa(store, responses=[SAResponse(adr=_adr(["r-1", "r-2"])).model_dump_json()])
    fsm = _fsm(tmp_path)

    run_loop(TICKET, ba=ba, sa=sa, fsm=fsm)

    assert store.omitted_requirement_ids("JIRA-42", "adr-1") == {"r-3"}


def test_deferred_requirement_is_not_omission(tmp_path):
    store = InMemoryMemoryStore()
    ba = _ba(store, responses=[_artifact().model_dump_json()])
    sa = _sa(store, responses=[SAResponse(adr=_adr(["r-1", "r-2"], deferred=["r-3"])).model_dump_json()])
    fsm = _fsm(tmp_path)

    run_loop(TICKET, ba=ba, sa=sa, fsm=fsm)

    assert store.omitted_requirement_ids("JIRA-42", "adr-1") == set()


def test_clarify_cap_forces_escalation(tmp_path):
    store = InMemoryMemoryStore()
    # BA answers each round; SA never stops clarifying.
    ba = _ba(store, responses=[_artifact().model_dump_json()] + ["answer"] * 10)
    clarify = SAResponse(
        clarifications=[ClarificationRequest(requirement_id="r-2", question="still unclear?")]
    ).model_dump_json()
    sa = _sa(store, responses=[clarify] * 10)
    fsm = _fsm(tmp_path, max_clarify_rounds=2)

    result = run_loop(TICKET, ba=ba, sa=sa, fsm=fsm)

    assert result.escalated is True
    assert result.final_state is DLCState.ESCALATION
    assert result.adr is None


def test_run_replays_to_identical_state(tmp_path):
    from agentic_memory import replay_final_state

    store = InMemoryMemoryStore()
    ba = _ba(store, responses=[_artifact().model_dump_json()])
    sa = _sa(store, responses=[SAResponse(adr=_adr(["r-1", "r-2", "r-3"])).model_dump_json()])
    path = tmp_path / "events.jsonl"
    fsm = FSM(EventLog(path))

    result = run_loop(TICKET, ba=ba, sa=sa, fsm=fsm)
    assert replay_final_state(EventLog(path)) == result.final_state


# --------------------------------------------------------------------------


def _print_run(label, ticket, result, store, fsm, group_id="default"):
    line = "═" * 70
    print(f"\n{line}\n  {label}\n{line}")
    print(f"📥 TICKET {ticket.id}: {ticket.body}")

    print("\n📋 REQUIREMENTS (BA → shared memory):")
    for r in store.requirements_for(ticket.id, group_id=group_id):
        print(f"   • [{r.id}] {r.attrs['text']}")
    print("🔑 KEY FACTS:")
    for kf in store.key_facts(ticket.id, group_id=group_id):
        print(f"   • {kf.attrs['text']}")

    print("\n🔀 FSM PATH (from the event log):")
    for e in fsm.event_log.read_all():
        if e.state is not None:
            forced = "  ⚠️ forced" if e.payload.get("forced") else ""
            print(f"   {e.seq}: {e.state.from_state} → {e.state.to_state}  ({e.agent}: {e.payload.get('reason')}){forced}")
    print(f"   clarification rounds: {result.clarify_rounds}")

    if result.adr is not None:
        adr = result.adr
        print(f"\n🏛️  ADR [{adr.id}] {adr.title}   (canonical={store.get_node(adr.id, group_id=group_id).canonical})")
        print(f"   decision : {adr.decision}")
        print(f"   rationale: {adr.rationale}")
        print("   traces:")
        for t in adr.requirement_traces:
            mark = "✓ addressed" if t.addressed else f"↪ deferred ({t.deferred_reason})"
            print(f"     - {t.requirement_id}: {mark} {t.how or ''}")
        omitted = store.omitted_requirement_ids(ticket.id, adr.id, group_id=group_id)
        print(f"   ⚖️  omission check: {'NONE ✅' if not omitted else 'DROPPED ' + str(omitted) + ' ❌'}")
    else:
        print(f"\n🚨 ESCALATED — no ADR (final state: {result.final_state})")
    print(line)
