# Demo data (Multi-Agent Assistant)

Fictional scenario metadata and recorded replays for the static Cloudflare Pages showcase and offline demos.

| File | What it is | Events / tasks |
|---|---|---|
| `scenarios.json` | Titles/requests for all five scenarios (the three live-app presets + two demo-only ones, marked `demo_only`). | 5 scenarios |
| `replay-kickoff.json` | Client kickoff, recorded from the live app (unchanged). | 69 / 8 |
| `replay-incident.json` | Production-incident triage: metrics + deploy log in parallel, RCA, status-page draft, Guardian strips an internal key, human approves publish. | 83 / 8 |
| `replay-offsite.json` | Team offsite under $3k: venues + dates in parallel, budget/agenda, policy review, approved booking. | 75 / 7 |
| `replay-vendor.json` | *Demo-only.* Vendor contract renewal: usage, terms and calendar in parallel, savings model, negotiation email; Guardian flags a test key, phone and internal marker; **the human rejects the send**, so the brief is cancelled. | 85 / 9 |
| `replay-hiring.json` | *Demo-only.* Interview loop: candidate profile + panel availability, loop schedule, candidate packet; Guardian redacts an internal comp note and phone; approved send. | 83 / 8 |
| `manifest.json` | Event/task counts, byte sizes and sha256. | |

Every replay uses the same event schema as `replay-kickoff.json` (`request`, `agent`, `task`, `message` with kinds
`request/assign/handoff/result/approval/approve/reject`, and a final `run`). They are recorded by
`python3 demo/generate_data.py`, which drives the app's real task graph, skill routing and Guardian guardrails on a
virtual clock (seeded, byte-identical output). Kickoff is left as recorded.

Pages-served copies live under `site/data/` (root directory = `site`); those copies are not updated by the generator.

**Local override.** Point a local run at another dataset with `HL_DATASET_URI` (e.g. `HL_DATASET_URI=file://…/demo/data`).

All people, companies, phone numbers (reserved 555-01xx range), keys and credentials in these files are fictional.
