"""FastAPI app: REST controls + Server-Sent Events stream of the message bus."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .agents import make_team, make_worker
from .llm import LLM, available_modes
from .orchestrator import MessageBus, Orchestrator, TaskGraph
from .scenarios import SCENARIOS

STATIC = Path(__file__).resolve().parent.parent / "static"
app = FastAPI(title="Multi-Agent Assistant")


class Run:
    orch: Orchestrator | None = None
    task: asyncio.Task | None = None
    scenario: str | None = None
    mode: str = "simulated"


RUN = Run()


class StartReq(BaseModel):
    scenario: str = "kickoff"
    mode: str = "simulated"
    speed: float = float(os.environ.get("MAA_SPEED", "1"))


class Decision(BaseModel):
    task_id: str
    approved: bool
    note: str = ""


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/scenarios")
def scenarios():
    return {"scenarios": {k: {"title": v["title"], "request": v["request"]} for k, v in SCENARIOS.items()},
            "modes": available_modes()}


@app.post("/api/run")
async def start(req: StartReq):
    if req.scenario not in SCENARIOS:
        raise HTTPException(404, "unknown scenario")
    if not available_modes().get(req.mode):
        raise HTTPException(400, f"mode {req.mode} not available")
    if RUN.task and not RUN.task.done():
        RUN.task.cancel()
    sc = SCENARIOS[req.scenario]
    bus = MessageBus()
    RUN.orch = Orchestrator(TaskGraph(sc["tasks"]()), make_team(), make_worker(LLM(req.mode, req.speed)), bus)
    RUN.scenario, RUN.mode = req.scenario, req.mode
    await bus.publish("request", scenario=req.scenario, title=sc["title"], text=sc["request"], mode=req.mode)
    await RUN.orch.say("Human", "Orchestrator", sc["request"], "request")
    RUN.task = asyncio.create_task(RUN.orch.run())
    return {"ok": True}


@app.post("/api/approve")
def approve(d: Decision):
    if not RUN.orch or not RUN.orch.decide(d.task_id, d.approved, d.note):
        raise HTTPException(409, "no pending approval for that task")
    return {"ok": True}


@app.get("/api/events")
async def events(after: int = 0):
    async def gen():
        seq, bus = after, None
        while True:
            if RUN.orch is None:
                await asyncio.sleep(0.3)
                continue
            if bus is not RUN.orch.bus:  # new run: restart the stream
                bus, seq = RUN.orch.bus, 0
                yield "event: reset\ndata: {}\n\n"
            for ev in await bus.wait_after(seq, timeout=10):
                seq = ev["seq"]
                yield f"data: {json.dumps(ev)}\n\n"
            yield ": keepalive\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")
