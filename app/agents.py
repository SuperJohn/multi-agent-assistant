"""The agent team and the worker that turns a task into agent output."""
from __future__ import annotations

import re

from .llm import LLM
from .orchestrator import Agent, Task

ROSTER = [
    ("Planner", "Breaks the request into a task graph and writes the final brief", ["plan", "summarize"], "#6366f1"),
    ("Researcher", "Searches the (fictional) knowledge base and CRM notes", ["research"], "#0ea5e9"),
    ("Scheduler", "Finds open slots across participants' calendars", ["schedule"], "#14b8a6"),
    ("Scribe", "Drafts agendas, notes and outbound messages", ["draft"], "#f59e0b"),
    ("Guardian", "Security & policy review: PII, secrets, external-sharing rules", ["review"], "#ef4444"),
    ("Dispatcher", "Performs outbound actions, only after human approval", ["send"], "#22c55e"),
]


def make_team() -> list[Agent]:
    return [Agent(n, r, s, c) for n, r, s, c in ROSTER]


# Guardrail patterns the Guardian applies on top of the model's opinion.
GUARDRAILS = {
    "phone number": re.compile(r"\b\d{3}[-.]\d{3}[-.]\d{4}\b"),
    "api key": re.compile(r"\b(sk|key)[-_][A-Za-z0-9]{8,}\b"),
    "internal-only marker": re.compile(r"\[internal\]", re.I),
}


def guardrail_findings(text: str) -> list[str]:
    return [name for name, rx in GUARDRAILS.items() if rx.search(text)]


def redact(text: str) -> str:
    for rx in GUARDRAILS.values():
        text = rx.sub("[REDACTED]", text)
    return text


def make_worker(llm: LLM):
    async def worker(agent: Agent, task: Task, context: dict[str, str]) -> str:
        system = f"You are {agent.name}, an agent whose role is: {agent.role}. Be concise (<=80 words)."
        upstream = "\n".join(f"- {k}: {v}" for k, v in context.items())
        prompt = f"Task: {task.title}\n{task.prompt}\nUpstream results:\n{upstream or '(none)'}"
        out = await llm.complete(system, prompt, task.script)
        if task.skill == "review":
            joined = "\n".join(context.values())
            hits = guardrail_findings(joined)
            if hits:
                out += f"\nGuardrail scan flagged: {', '.join(hits)} -> redacted in outbound copy."
            else:
                out += "\nGuardrail scan: clean."
        if task.skill == "send":
            out = redact(out)
        return out
    return worker
