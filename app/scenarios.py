"""Scenario presets. ALL people, companies and data here are fictional."""
from __future__ import annotations

from .orchestrator import Task

T = Task

SCENARIOS = {
    "kickoff": {
        "title": "Plan a client kickoff next week",
        "request": "Plan a kickoff with Lumen & Lark Robotics next week: brief me, pick a time, draft the agenda and send the invite.",
        "tasks": lambda: [
            T("plan", "Decompose request into a task graph", "plan",
              script="Plan: research account -> find slots (parallel) -> draft agenda & invite -> security review -> human approval -> send."),
            T("research", "Research Lumen & Lark Robotics account notes", "research", ["plan"],
              script="Lumen & Lark (fictional): 40-person warehouse-robotics startup. Champion: Priya Quasar (VP Ops). Goal: cut pick-time 20%. Open risk: data-retention questions from their legal team."),
            T("slots", "Find a 60-min slot next week for 4 attendees", "schedule", ["plan"],
              script="Free for all 4 attendees: Tue 10:00-11:00, Wed 14:00-15:00, Thu 09:30-10:30. Recommend Wed 14:00 (no adjacent conflicts)."),
            T("agenda", "Draft kickoff agenda", "draft", ["research"],
              script="Agenda: 1) Intros 2) Goals: -20% pick-time 3) Data-retention Q&A 4) Pilot scope & timeline 5) Next steps."),
            T("invite", "Draft calendar invite + email", "draft", ["agenda", "slots"],
              script="Subject: Kickoff, Lumen & Lark x Acme Demo Co, Wed 14:00. Hi Priya, looking forward to kicking off. Agenda attached. Dial-in: 555-014-2231 [internal]."),
            T("review", "Security & policy review of outbound invite", "review", ["invite"],
              script="Reviewed invite: recipients are on the approved external domain; no attachments with customer data."),
            T("send", "Send invite to external attendees", "send", ["review"], requires_approval=True,
              script="Invite sent to 3 external attendees for Wed 14:00. Dial-in: 555-014-2231 [internal]."),
            T("brief", "Write the final brief for the user", "summarize", ["send"],
              script="Done: kickoff booked Wed 14:00, agenda shared, legal's data-retention question is item 3. Guardian redacted an internal dial-in before sending."),
        ],
    },
    "incident": {
        "title": "Triage a production incident",
        "request": "Checkout latency spiked at 09:12. Figure out what happened, draft a status-page update and post it.",
        "tasks": lambda: [
            T("plan", "Decompose incident triage", "plan",
              script="Plan: pull fake metrics + deploy log in parallel -> root-cause note -> status update draft -> review -> approval -> publish."),
            T("metrics", "Pull checkout latency metrics", "research", ["plan"],
              script="p95 checkout latency 310ms -> 2.4s at 09:12; error rate flat; DB connection pool saturated at 100%."),
            T("deploys", "Check recent deploys", "schedule", ["plan"],
              script="Deploy #4821 (cart-service) at 09:07 raised pool timeout and halved max connections."),
            T("rca", "Draft root-cause note", "draft", ["metrics", "deploys"],
              script="Likely cause: deploy #4821 halved DB pool size. Mitigation: rollback; latency recovered 09:31 in staging replay."),
            T("status", "Draft public status-page update", "draft", ["rca"],
              script="We identified elevated checkout latency from 09:12 to 09:31 caused by a configuration change. It has been rolled back. Contact oncall key_9f8e7d6c5b4a for details."),
            T("review", "Review public update for leaks", "review", ["status"],
              script="Public copy reviewed: no customer names; tone OK."),
            T("publish", "Publish status-page update", "send", ["review"], requires_approval=True,
              script="Status page updated. Contact oncall key_9f8e7d6c5b4a for details."),
            T("brief", "Summarize for the user", "summarize", ["publish"],
              script="Resolved: rollback of #4821 restored latency. Status page posted after approval; Guardian stripped an internal credential from the public copy."),
        ],
    },
    "offsite": {
        "title": "Organize a team offsite",
        "request": "Organize a one-day offsite for the 8-person platform team next month under $3k.",
        "tasks": lambda: [
            T("plan", "Decompose offsite planning", "plan",
              script="Plan: venues + dates in parallel -> budget & agenda -> review -> approval -> book."),
            T("venues", "Research venues (fictional directory)", "research", ["plan"],
              script="Shortlist: The Copper Kettle Loft ($1,400/day), Harborlight Studio ($1,950/day), Greenwick Barn ($1,100/day, 40 min away)."),
            T("dates", "Find a date that works for 8 people", "schedule", ["plan"],
              script="Best dates: Fri 14th (8/8 free) or Thu 20th (7/8)."),
            T("budget", "Draft budget + agenda", "draft", ["venues", "dates"],
              script="Copper Kettle Loft, Fri 14th: venue $1,400 + catering $960 + activity $400 = $2,760 (under $3k). Agenda: roadmap AM, hack-sprint PM, dinner."),
            T("review", "Policy review: spend & vendor rules", "review", ["budget"],
              script="Within $3k cap; vendor not on blocklist; deposit is refundable."),
            T("book", "Book venue and send calendar holds", "send", ["review"], requires_approval=True,
              script="Venue booked for Fri 14th; holds sent to 8 teammates."),
            T("brief", "Summarize for the user", "summarize", ["book"],
              script="Offsite set: Copper Kettle Loft, Fri 14th, $2,760 total. Holds out to the team."),
        ],
    },
}
