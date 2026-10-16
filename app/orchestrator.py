"""Core orchestration primitives: task graph, message bus, router, approval gate.

Everything here is framework-free so it can be unit-tested without a server.
"""
from __future__ import annotations

import asyncio
import itertools
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Awaitable, Callable

# Task lifecycle -------------------------------------------------------------
BLOCKED = "blocked"            # waiting on upstream tasks
QUEUED = "queued"              # dependencies met, waiting for an agent
RUNNING = "running"
AWAITING = "awaiting_approval" # human-in-the-loop gate
DONE = "done"
REJECTED = "rejected"          # human said no
CANCELLED = "cancelled"        # upstream was rejected / failed
TERMINAL = {DONE, REJECTED, CANCELLED}


@dataclass
class Task:
    id: str
    title: str
    skill: str
    deps: list[str] = field(default_factory=list)
    requires_approval: bool = False
    prompt: str = ""
    script: str = ""              # deterministic output used in simulated mode
    status: str = BLOCKED
    agent: str | None = None
    output: str = ""
    started: float | None = None
    finished: float | None = None

    def view(self) -> dict[str, Any]:
        return asdict(self)


class GraphError(ValueError):
    pass


class TaskGraph:
    """A DAG of tasks. Validates references and cycles up front."""

    def __init__(self, tasks: list[Task]):
        self.tasks: dict[str, Task] = {}
        for t in tasks:
            if t.id in self.tasks:
                raise GraphError(f"duplicate task id {t.id!r}")
            self.tasks[t.id] = t
        for t in tasks:
            for d in t.deps:
                if d not in self.tasks:
                    raise GraphError(f"task {t.id!r} depends on unknown {d!r}")
        self.order = self._topo()
        self.refresh()

    def _topo(self) -> list[str]:
        seen: dict[str, int] = {}
        out: list[str] = []

        def visit(n: str) -> None:
            state = seen.get(n, 0)
            if state == 1:
                raise GraphError(f"cycle detected at {n!r}")
            if state == 2:
                return
            seen[n] = 1
            for d in self.tasks[n].deps:
                visit(d)
            seen[n] = 2
            out.append(n)

        for n in self.tasks:
            visit(n)
        return out

    def dependents(self, tid: str) -> list[Task]:
        return [t for t in self.tasks.values() if tid in t.deps]

    def refresh(self) -> list[Task]:
        """Promote blocked->queued and propagate cancellations. Returns changed tasks."""
        changed = []
        for tid in self.order:
            t = self.tasks[tid]
            if t.status in TERMINAL or t.status in (RUNNING, AWAITING, "dispatching"):
                continue
            dep_states = [self.tasks[d].status for d in t.deps]
            if any(s in (REJECTED, CANCELLED) for s in dep_states):
                new = CANCELLED
            elif all(s == DONE for s in dep_states):
                new = QUEUED
            else:
                new = BLOCKED
            if new != t.status:
                t.status = new
                changed.append(t)
        return changed

    def ready(self) -> list[Task]:
        return [self.tasks[t] for t in self.order if self.tasks[t].status == QUEUED]

    def finished(self) -> bool:
        return all(t.status in TERMINAL for t in self.tasks.values())


# Message bus ----------------------------------------------------------------
class MessageBus:
    """Append-only event log with async fan-out to subscribers (SSE clients)."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._cond = asyncio.Condition()
        self._seq = itertools.count(1)
        self.t0 = time.time()

    async def publish(self, event_type: str, /, **data: Any) -> dict[str, Any]:
        ev = {"seq": next(self._seq), "t": round(time.time() - self.t0, 2), "type": event_type, **data}
        async with self._cond:
            self.events.append(ev)
            self._cond.notify_all()
        return ev

    async def wait_after(self, seq: int, timeout: float = 15.0) -> list[dict[str, Any]]:
        async with self._cond:
            if not any(e["seq"] > seq for e in self.events):
                try:
                    await asyncio.wait_for(self._cond.wait(), timeout)
                except asyncio.TimeoutError:
                    return []
            return [e for e in self.events if e["seq"] > seq]

    def messages(self) -> list[dict[str, Any]]:
        return [e for e in self.events if e["type"] == "message"]


# Agents & routing -----------------------------------------------------------
@dataclass
class Agent:
    name: str
    role: str
    skills: list[str]
    color: str = "#64748b"
    status: str = "idle"
    busy_with: str | None = None

    def view(self) -> dict[str, Any]:
        return asdict(self)


class Router:
    """Routes a task to the first agent advertising the task's skill."""

    def __init__(self, agents: list[Agent]):
        self.agents = {a.name: a for a in agents}

    def route(self, task: Task) -> Agent:
        for a in self.agents.values():
            if task.skill in a.skills:
                return a
        raise LookupError(f"no agent can handle skill {task.skill!r}")


# Orchestrator ---------------------------------------------------------------
Worker = Callable[[Agent, Task, dict[str, str]], Awaitable[str]]


class Orchestrator:
    NAME = "Orchestrator"

    def __init__(self, graph: TaskGraph, agents: list[Agent], worker: Worker,
                 bus: MessageBus | None = None, max_parallel: int = 3):
        self.graph = graph
        self.router = Router(agents)
        self.worker = worker
        self.bus = bus or MessageBus()
        self.max_parallel = max_parallel
        self._decisions: dict[str, asyncio.Future] = {}
        self.state = "idle"

    # --- human-in-the-loop ---
    def pending_approvals(self) -> list[str]:
        return [k for k, f in self._decisions.items() if not f.done()]

    def decide(self, task_id: str, approved: bool, note: str = "") -> bool:
        fut = self._decisions.get(task_id)
        if fut is None or fut.done():
            return False
        fut.set_result((approved, note))
        return True

    async def _emit_task(self, t: Task) -> None:
        await self.bus.publish("task", task=t.view())

    async def _emit_agent(self, a: Agent) -> None:
        await self.bus.publish("agent", agent=a.view())

    async def say(self, sender: str, to: str, content: str, kind: str = "info", task: str | None = None):
        await self.bus.publish("message", sender=sender, to=to, content=content, kind=kind, task=task)

    async def _run_task(self, t: Task) -> None:
        agent = self.router.route(t)
        t.agent = agent.name
        context = {d: self.graph.tasks[d].output for d in t.deps}

        if t.requires_approval:
            t.status = AWAITING
            await self._emit_task(t)
            loop = asyncio.get_running_loop()
            self._decisions[t.id] = loop.create_future()
            await self.say(self.NAME, "Human", f"Approval required before: {t.title}", "approval", t.id)
            approved, note = await self._decisions[t.id]
            if not approved:
                t.status, t.output = REJECTED, note or "Rejected by human reviewer."
                t.finished = time.time() - self.bus.t0
                await self.say("Human", self.NAME, f"Rejected: {t.output}", "reject", t.id)
                await self._emit_task(t)
                return
            await self.say("Human", self.NAME, f"Approved{': ' + note if note else ''}", "approve", t.id)

        while agent.status == "busy":   # one task per agent at a time
            await asyncio.sleep(0.05)
        t.status, t.started = RUNNING, time.time() - self.bus.t0
        agent.status, agent.busy_with = "busy", t.id
        await self._emit_task(t)
        await self._emit_agent(agent)
        await self.say(self.NAME, agent.name, f"Assigned: {t.title}", "assign", t.id)
        for d, out in context.items():
            src = self.graph.tasks[d].agent
            if src and src != agent.name:
                await self.say(src, agent.name, f"Handoff from '{self.graph.tasks[d].title}'", "handoff", t.id)
        try:
            t.output = await self.worker(agent, t, context)
            t.status = DONE
        except Exception as exc:  # a failed task cancels its dependents
            t.output, t.status = f"error: {exc}", CANCELLED
        t.finished = time.time() - self.bus.t0
        agent.status, agent.busy_with = "idle", None
        await self.say(agent.name, self.NAME, t.output, "result" if t.status == DONE else "error", t.id)
        await self._emit_task(t)
        await self._emit_agent(agent)

    async def run(self) -> dict[str, str]:
        self.state = "running"
        await self.bus.publish("run", state="running")
        for a in self.router.agents.values():
            await self._emit_agent(a)
        for t in self.graph.tasks.values():
            await self._emit_task(t)
        running: dict[str, asyncio.Task] = {}
        while not self.graph.finished():
            for t in self.graph.refresh():
                await self._emit_task(t)
            for t in self.graph.ready():
                if len(running) >= self.max_parallel:
                    break
                t.status = "dispatching"
                running[t.id] = asyncio.create_task(self._run_task(t))
            if not running:
                if self.graph.finished():
                    break
                raise RuntimeError("deadlock: nothing runnable")
            done, _ = await asyncio.wait(running.values(), return_when=asyncio.FIRST_COMPLETED)
            for tid in [k for k, v in running.items() if v in done]:
                running.pop(tid).result()
        for t in self.graph.refresh():
            await self._emit_task(t)
        self.state = "finished"
        summary = {t.id: t.status for t in self.graph.tasks.values()}
        await self.bus.publish("run", state="finished", summary=summary)
        return summary
