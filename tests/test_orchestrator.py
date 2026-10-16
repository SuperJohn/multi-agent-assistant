import asyncio

import pytest

from app.agents import guardrail_findings, make_team, make_worker
from app.llm import LLM
from app.orchestrator import (AWAITING, BLOCKED, CANCELLED, DONE, QUEUED, REJECTED,
                              GraphError, Orchestrator, Router, Task, TaskGraph)
from app.scenarios import SCENARIOS


def graph(name="kickoff"):
    return TaskGraph(SCENARIOS[name]["tasks"]())


def test_topological_order_respects_deps():
    g = graph()
    pos = {t: i for i, t in enumerate(g.order)}
    for t in g.tasks.values():
        assert all(pos[d] < pos[t.id] for d in t.deps)


def test_initial_states():
    g = graph()
    assert g.tasks["plan"].status == QUEUED
    assert g.tasks["research"].status == BLOCKED


def test_cycle_and_unknown_dep_rejected():
    with pytest.raises(GraphError):
        TaskGraph([Task("a", "A", "plan", ["b"]), Task("b", "B", "plan", ["a"])])
    with pytest.raises(GraphError):
        TaskGraph([Task("a", "A", "plan", ["zzz"])])


def test_router_by_skill():
    r = Router(make_team())
    assert r.route(Task("x", "x", "schedule")).name == "Scheduler"
    assert r.route(Task("x", "x", "review")).name == "Guardian"
    with pytest.raises(LookupError):
        r.route(Task("x", "x", "juggle"))


def orch(name):
    return Orchestrator(graph(name), make_team(), make_worker(LLM("simulated", speed=0)))


async def drive(o, approve: bool):
    run = asyncio.create_task(o.run())
    for _ in range(500):
        await asyncio.sleep(0.01)
        if o.pending_approvals():
            break
    pending = o.pending_approvals()
    assert pending, "run should pause at the approval gate"
    assert o.graph.tasks[pending[0]].status == AWAITING
    # nothing downstream of the gate may run before a decision
    assert o.graph.tasks["brief"].status == BLOCKED
    o.decide(pending[0], approve)
    return await asyncio.wait_for(run, 5)


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_full_run_with_approval(name):
    summary = asyncio.run(drive(orch(name), True))
    assert set(summary.values()) == {DONE}


def test_rejection_cancels_downstream():
    o = orch("kickoff")
    summary = asyncio.run(drive(o, False))
    assert summary["send"] == REJECTED
    assert summary["brief"] == CANCELLED
    assert summary["review"] == DONE


def test_guardian_redacts_outbound():
    o = orch("kickoff")
    asyncio.run(drive(o, True))
    assert "flagged" in o.graph.tasks["review"].output
    sent = o.graph.tasks["send"].output
    assert "555-014-2231" not in sent and "[REDACTED]" in sent


def test_parallel_branches_and_message_bus():
    o = orch("kickoff")
    asyncio.run(drive(o, True))
    t = o.graph.tasks
    # research and slots both only depend on plan -> both start before either's dependents
    assert t["slots"].started < t["invite"].started and t["research"].started < t["agenda"].started
    kinds = {m["kind"] for m in o.bus.messages()}
    assert {"assign", "result", "handoff", "approval", "approve"} <= kinds


def test_guardrail_patterns():
    assert guardrail_findings("call 555-123-4567") == ["phone number"]
    assert guardrail_findings("nothing here") == []
