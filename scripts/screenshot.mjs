// Headless screenshots of the dashboard on fictional data. Needs: npx playwright (chromium).
// Usage: server running on PORT (default 8790), then `node scripts/screenshot.mjs`.
import { chromium } from "playwright";
const base = `http://localhost:${process.env.PORT || 8790}`;
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 860 }, deviceScaleFactor: 2 });
await p.goto(`${base}/?scenario=kickoff&autorun=1`);
await p.waitForSelector("#gate.show", { timeout: 60000 });
await p.screenshot({ path: "docs/dashboard-approval.png" });
await p.click("#ok");
await p.waitForFunction(() => document.querySelector("#state").textContent === "finished", null, { timeout: 60000 });
await p.waitForTimeout(400);
await p.screenshot({ path: "docs/dashboard-finished.png" });
await b.close();
