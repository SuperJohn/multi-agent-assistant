#!/usr/bin/env python3
"""Record the Multi-Agent Assistant demo replays under demo/data (seeded, deterministic).

Runs each scenario through the real task graph (app.orchestrator.TaskGraph), router skills and Guardian guardrails
(app.agents) on a virtual clock, and writes timed events in the same shape as replay-kickoff.json. Adds two demo-only
scenarios (vendor renewal with a human REJECT at the approval gate; interview loop). All fictional.

    python3 demo/generate_data.py      # rewrites replay-{incident,offsite,vendor,hiring}.json + scenarios.json + manifest.json
"""
import hashlib, json
from pathlib import Path


def _enc(o, level=0):
    """Pretty JSON where arrays of objects/arrays put one compact record per line (small, diff-friendly)."""
    pad, pad1 = " " * level, " " * (level + 1)
    if isinstance(o, dict):
        if not o:
            return "{}"
        items = [f'{pad1}{json.dumps(k, ensure_ascii=False)}: {_enc(v, level + 1)}' for k, v in o.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(o, list) and o and all(isinstance(x, (dict, list)) for x in o):
        rows = [pad1 + json.dumps(x, ensure_ascii=False, separators=(", ", ": ")) for x in o]
        return "[\n" + ",\n".join(rows) + "\n" + pad + "]"
    return json.dumps(o, ensure_ascii=False)


def write(path: Path, obj) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = _enc(obj) + "\n"
    json.loads(text)  # must round-trip
    path.write_text(text, encoding="utf-8")
    b = text.encode()
    return {"name": path.name, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
# ---------------------------------------------------------------------------------------------------------------
import argparse
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.agents import ROSTER, guardrail_findings, redact  # noqa: E402
from app.orchestrator import DONE, REJECTED, Task, TaskGraph  # noqa: E402
from app.scenarios import SCENARIOS  # noqa: E402

SEED = 42
T = Task
SKILL_AGENT = {s: name for name, _, skills, _ in ROSTER for s in skills}
ROSTER_OUT = [{"name": n, "role": r, "color": c} for n, r, _, c in ROSTER] + [
    {"name": "Orchestrator", "role": "Routes tasks and messages", "color": "#5eead4"},
    {"name": "Human", "role": "Approves gated outbound actions", "color": "#e5e9f2"}]

# Extra demo scenarios (ALL people, companies, numbers and keys are fictional; phones use the reserved 555-01xx range).
EXTRA = {
    "vendor": {
        "title": "Review a vendor contract renewal",
        "request": "Our Brightpath Analytics contract auto-renews on the 30th. Compare usage against the price, draft a negotiation email to their account manager and send it.",
        "decision": ("reject", "Hold off: legal wants to review the auto-renew clause first. Don't send yet."),
        "tasks": lambda: [
            T("plan", "Decompose contract review", "plan",
              script="Plan: pull usage + contract terms in parallel -> savings analysis -> negotiation email -> policy review -> approval -> send -> brief."),
            T("usage", "Pull 12 months of seat and API usage", "research", ["plan"],
              script="Brightpath (fictional): 40 seats licensed, 23 active in the last 90 days (58%). API calls avg 410k/mo against a 1M/mo tier."),
            T("terms", "Read current contract terms", "research", ["plan"],
              script="Contract BP-2291: $48,000/yr, auto-renews Nov 30 for 12 months, 5% uplift, 30-day notice window, downgrade allowed at renewal."),
            T("calendar", "Find a 30-min slot with their account manager", "schedule", ["plan"],
              script="Overlap with Dana Whitlock (Brightpath AM, fictional): Tue 11:00 or Thu 15:30. Recommend Tue 11:00, before the notice window closes."),
            T("analysis", "Model savings options", "draft", ["usage", "terms"],
              script="Option A: 25 seats + 500k API tier = $29,400/yr (-39%). Option B: 30 seats, same tier = $38,100/yr (-21%). Recommend A with a 2-year price lock."),
            T("email", "Draft negotiation email", "draft", ["analysis", "calendar"],
              script="Hi Dana, ahead of our Nov 30 renewal we'd like to right-size to 25 seats and the 500k API tier, with a 2-year price lock. Free Tue 11:00? Our test key key_demo4a7c9e21 is attached for the usage export. Call me at 555-555-0134 [internal]."),
            T("review", "Policy review of outbound email", "review", ["email"],
              script="Commercial terms OK to share; recipient is on the vendor's domain. No customer data in the body."),
            T("send", "Send negotiation email to vendor", "send", ["review"], requires_approval=True,
              script="Email sent to Dana Whitlock with the right-sizing proposal. Key key_demo4a7c9e21; call-back 555-555-0134 [internal]."),
            T("brief", "Summarize for the user", "summarize", ["send"],
              script="Proposal ready: right-size to 25 seats + 500k tier saves ~$18.6k/yr. Email drafted and reviewed; Guardian removed a test API key and an internal phone number."),
        ],
    },
    "hiring": {
        "title": "Run an interview loop",
        "request": "Set up the onsite loop for the senior data engineer candidate next week: pull the scorecard, book four interviewers, draft the candidate packet and send the invites.",
        "tasks": lambda: [
            T("plan", "Decompose interview loop", "plan",
              script="Plan: candidate profile + interviewer availability in parallel -> loop schedule -> packet + invites -> privacy review -> approval -> send -> brief."),
            T("profile", "Summarize the candidate profile and scorecard", "research", ["plan"],
              script="Morgan Vale (fictional): 7 yrs data engineering, dbt + Airflow, led a warehouse migration at Kestrel Freight (fictional). Scorecard focus: SQL modelling, pipeline reliability, stakeholder comms."),
            T("avail", "Find a half-day with 4 interviewers", "schedule", ["plan"],
              script="All four free Thu 13:00-17:00: Ana Ruiz (hiring manager), Theo Park (SQL), Lena Ito (systems design), Omar Haddad (values). Fri morning has 3 of 4."),
            T("loop", "Build the loop schedule", "draft", ["profile", "avail"],
              script="Thu: 13:00 Ana (intro + role), 13:45 Theo (SQL modelling), 14:45 break, 15:00 Lena (pipeline design), 16:00 Omar (values), 16:45 wrap-up."),
            T("packet", "Draft candidate packet + invites", "draft", ["loop"],
              script="Hi Morgan, here's your Thursday loop at Acme Demo Co. Parking at the north entrance; reception number 555-555-0161. Recruiter notes: comp target $185k [internal]."),
            T("review", "Privacy review of candidate-facing packet", "review", ["packet"],
              script="Candidate-facing copy checked against the hiring policy: no other candidates named; internal comp notes must not be shared."),
            T("send", "Send loop invites to candidate and panel", "send", ["review"], requires_approval=True,
              script="Invites sent to Morgan Vale and 4 interviewers for Thu 13:00-17:00. Reception 555-555-0161; comp target [internal]."),
            T("brief", "Summarize for the user", "summarize", ["send"],
              script="Loop booked Thu 13:00-17:00 with all four interviewers; packet sent. Guardian stripped the internal comp note and a phone number from the candidate copy."),
        ],
    },
}
SPEED = {"plan": 0.7, "research": 1.2, "schedule": 0.9, "draft": 0.9, "review": 0.8, "send": 0.6, "summarize": 0.6}


def record(key, title, request, tasks, rng, decision=("approve", "")):
    graph = TaskGraph(tasks)
    ev = []
    add = lambda t, typ, **kw: ev.append({"t": round(t, 2), "type": typ, **kw})
    view = lambda task: {"id": task.id, "title": task.title, "skill": task.skill, "deps": list(task.deps),
                         "requires_approval": task.requires_approval, "status": task.status, "agent": task.agent, "output": task.output}
    agent_ev = lambda t, name, status, busy: add(t, "agent", agent={"name": name, "role": "", "color": "#888", "status": status, "busy_with": busy})

    add(0.0, "request", title=title, text=request, mode="simulated")
    add(0.1, "message", sender="Human", to="Orchestrator", kind="request", content=request)
    for i, a in enumerate(ROSTER_OUT[:-1]):
        add(0.2 + 0.05 * i, "agent", agent={**a, "status": "idle", "busy_with": None})
    for i, tid in enumerate(graph.order):
        add(1.0 + 0.15 * i, "task", task=view(graph.tasks[tid]))
    busy, running, now = {}, {}, 1.5          # busy: agent -> task id; running: task id -> finish time
    while True:
        for t in graph.ready():
            ag = SKILL_AGENT[t.skill]
            if ag in busy or len(running) >= 3:
                continue
            t.agent, t.status = ag, "running"
            busy[ag] = t.id
            agent_ev(now, ag, "busy", t.id)
            add(now, "task", task=view(t))
            add(now + 0.1, "message", sender="Orchestrator", to=ag, kind="assign", content=f"Assigned: {t.title}")
            for d in t.deps:
                src = graph.tasks[d].agent
                if src and src != ag:
                    add(now + 0.15, "message", sender=src, to=ag, kind="handoff", content=f"Handoff from '{graph.tasks[d].title}'")
            dur = SPEED[t.skill] * rng.uniform(0.8, 1.25)
            if t.requires_approval:
                t.status = "awaiting_approval"
                add(now + 0.65, "task", task=view(t))
                add(now + 0.85, "message", sender="Orchestrator", to="Human", kind="approval", content=f"Approval required before: {t.title}")
                dur += 1.4
            running[t.id] = now + dur
        if not running:
            break
        tid = min(running, key=running.get)
        now = running.pop(tid)
        t = graph.tasks[tid]
        ctx = "\n".join(graph.tasks[d].output for d in t.deps)
        if t.requires_approval and decision[0] == "reject":
            t.status, t.output = REJECTED, decision[1]
            add(now - 0.3, "message", sender="Human", to="Orchestrator", kind="reject", content=f"Rejected: {decision[1]}")
        else:
            if t.requires_approval:
                add(now - 0.3, "message", sender="Human", to="Orchestrator", kind="approve", content="Approved (static demo auto-approve).")
            out = t.script
            if t.skill == "review":
                hits = guardrail_findings(ctx)
                out += (f"\nGuardrail scan flagged: {', '.join(hits)} -> redacted in outbound copy." if hits else "\nGuardrail scan: clean.")
            if t.skill == "send":
                out = redact(out)
            t.status, t.output = DONE, out
        add(now, "task", task=view(t))
        busy.pop(t.agent, None)
        agent_ev(now, t.agent, "idle", None)
        if t.status == DONE:
            add(now, "message", sender=t.agent, to="Orchestrator", kind="result", content=t.output)
        for c in graph.refresh():
            add(now + 0.05, "task", task=view(c))
        now += 0.1
    summary = {t.id: t.status for t in graph.tasks.values()}
    add(now + 0.2, "run", state="done", summary=summary)
    ev.sort(key=lambda e: e["t"])
    return {"scenario": key, "title": title, "synthetic": True, "roster": ROSTER_OUT, "events": ev}


def main():
    ap = argparse.ArgumentParser(description="Record the Multi-Agent Assistant demo replays (seeded, deterministic).")
    ap.add_argument("--out", default=str(ROOT / "demo/data"))
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    out = Path(a.out)
    rng = random.Random(a.seed)
    files, counts, meta = [], {}, {}
    for key in ("incident", "offsite"):            # kickoff stays as recorded (it is the replay on the live Pages site)
        sc = SCENARIOS[key]
        files.append(write(out / f"replay-{key}.json", record(key, sc["title"], sc["request"], sc["tasks"](), rng)))
    for key, sc in EXTRA.items():
        files.append(write(out / f"replay-{key}.json", record(key, sc["title"], sc["request"], sc["tasks"](), rng,
                                                             sc.get("decision", ("approve", "")))))
    scen = {k: {"title": v["title"], "request": v["request"]} for k, v in SCENARIOS.items()}
    scen.update({k: {"title": v["title"], "request": v["request"], "demo_only": True} for k, v in EXTRA.items()})
    files.append(write(out / "scenarios.json", {"scenarios": scen, "modes": {"simulated": True},
                                                "note": "All companies, people and data are fictional."}))
    for k in scen:
        r = json.loads((out / f"replay-{k}.json").read_text())
        counts[k] = {"events": len(r["events"]), "tasks": len({e["task"]["id"] for e in r["events"] if e["type"] == "task"}),
                     "seconds": r["events"][-1]["t"]}
    write(out / "manifest.json", {"app": "multi-agent-assistant", "synthetic": True, "generator": "demo/generate_data.py", "seed": a.seed,
                                  "replays": counts, "files": files,
                                  "unchanged": ["replay-kickoff.json (recorded; also served from site/data/)"]})
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
