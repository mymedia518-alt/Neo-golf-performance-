/* Playwright capture — Desktop / Tablet / Mobile screenshots of the
   Player Intelligence page (and the leaderboard entry point).
   usage: node scripts/capture.mjs [baseUrl]  */
import { chromium } from "playwright";
import fs from "node:fs";

const BASE = process.argv[2] || "http://127.0.0.1:4173";
const OUT = "screenshots";
fs.mkdirSync(OUT, { recursive: true });

const VIEWS = [
  { name: "desktop", width: 1440, height: 1000, dsf: 2 },
  { name: "tablet", width: 900, height: 1200, dsf: 2 },
  { name: "mobile", width: 390, height: 844, dsf: 3, mobile: true }
];

const PAGES = [
  { slug: "player-intelligence", path: "/player/kim-minsun7", full: true },
  { slug: "player-intelligence-park", path: "/player/park-jiyoung2", full: true, only: ["desktop"] },
  { slug: "leaderboard", path: "/leaderboard.html", full: false }
];

const EXEC = ["/opt/pw-browsers/chromium-1194/chrome-linux/chrome", "/opt/pw-browsers/chromium/chrome-linux/chrome"]
  .find((p) => fs.existsSync(p));
const browser = await chromium.launch(EXEC ? { executablePath: EXEC } : {});
const errors = [];

for (const v of VIEWS) {
  const ctx = await browser.newContext({
    viewport: { width: v.width, height: v.height },
    deviceScaleFactor: v.dsf,
    isMobile: !!v.mobile,
    hasTouch: !!v.mobile
  });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(`${v.name}: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") errors.push(`${v.name} console: ${m.text()}`); });

  for (const p of PAGES) {
    if (p.only && !p.only.includes(v.name)) continue;
    await page.goto(BASE + p.path, { waitUntil: "networkidle" });
    await page.waitForTimeout(450);
    const file = `${OUT}/${p.slug}-${v.name}.png`;
    await page.screenshot({ path: file, fullPage: p.full });
    console.log("captured", file);
  }

  // Hole Library row → hole detail panel (structure for the hole-detail route)
  await page.goto(BASE + "/player/kim-minsun7", { waitUntil: "networkidle" });
  await page.locator(".hole-row").first().click();
  const detail = (await page.textContent("[data-hole-detail]")).trim();
  if (!/holeDetailRoute/.test(detail)) throw new Error("hole detail did not open");
  console.log(`[${v.name}] hole row click → ${detail.split("\n")[0].slice(0, 40)}…`);

  // Chart hover tooltip
  await page.locator('[data-chart="driver"] .mark').nth(3).hover();
  await page.waitForTimeout(150);
  const tipOn = await page.locator(".neo-tip.is-on").count();
  console.log(`[${v.name}] chart tooltip visible: ${tipOn > 0}`);

  // Leaderboard → player name click → Player Intelligence (route check)
  await page.goto(BASE + "/leaderboard.html", { waitUntil: "networkidle" });
  await page.click('a[data-player-code="kim-minsun7"]');
  await page.waitForURL("**/player/kim-minsun7");
  await page.waitForTimeout(350);
  const h1 = await page.textContent(".pi-hero__name");
  console.log(`[${v.name}] leaderboard click → ${new URL(page.url()).pathname} → ${h1.trim()}`);

  // → next player
  await page.click(".pager-btn--next");
  await page.waitForTimeout(350);
  console.log(`[${v.name}] next player → ${new URL(page.url()).pathname} → ${(await page.textContent(".pi-hero__name")).trim()}`);

  await ctx.close();
}

await browser.close();
if (errors.length) { console.error("PAGE ERRORS:\n" + errors.join("\n")); process.exit(1); }
console.log("no page errors");
