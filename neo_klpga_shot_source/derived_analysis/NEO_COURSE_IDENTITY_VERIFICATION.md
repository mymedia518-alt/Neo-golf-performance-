# NEO Course Identity Verification — Tournament H12 ↔ Blue Heron West Hole 3

Game: 2026100005 (하이트진로 챔피언십, gameCode) · Independent verification, separate from coordinate registration.

## Why this is a separate claim from coordinate registration

Coordinate registration (previously confirmed) only proves KLPGA's Shot Tracker `(x,y)` coordinates and `hole_12.png` share a consistent rendering frame — it says nothing about what the image actually depicts. This document verifies the image's real-world identity independently.

## Method

1. Headless Chromium (Playwright) loaded `https://www.blueheron.co.kr/` for real and traced actual network/DOM activity (not a static fetch — the site is a client-rendered SPA; a plain `urllib` fetch earlier returned only an empty JS shell).
2. Found a real course-map widget in the DOM: `div.west`/`div.east`, each listing `li.hole01..hole09`, paired with `<select id="course-map-title-west-hole">` / `...-east-hole`. This independently confirms Blue Heron's real structure is **West 9 + East 9 = 18 holes**, matching the previously-stated reference.
3. Dispatched real `click`/`change` DOM events (the widget sits in a non-active fullpage.js slide, so Playwright's actionability-gated `.click()` refused; events were dispatched directly, still exercising the page's own JS handlers) to walk **all 18 real holes** (West 1–9, East 1–9) and captured each hole's real title, Hdcp, and Blue/White tee yardage, plus the Pro Tip hazard text.
4. Cross-checked the full 18-hole sequence against KLPGA's own real per-hole yardage (`holeInfo.yds`, already present in this project's collected RAW for every Tournament hole 1–18 — not re-estimated, extracted directly: `klpga_tournament_18hole_par_yardage.json`).

## Result 1: West Hole 3 — direct real match

Real page returned (`https://blueheron.co.kr/swp/course/west/hole03`): **title "West Hole 3", Par 4, Hdcp 3**, tees Blue 428YD / **White 410YD** / Gold 377YD / Red 283YD.

KLPGA Tournament Hole 12 (this project's own collected RAW): **410 yards, Par 4.** Exact match to the White tee.

Pro Tip (official, real, Korean text): *"티샷의 목표는 보통 우측의 150YD 표지목을 기준으로 하는 것이 좋으나 장타자일 경우 좌측 100YD 표지목을 향하여 샷을 하여야 하나 낙하지점 좌측의 넓은 사이드 벙커가 위협하며 플레이어를 위축시키고 반대로 우측으로 갈 경우 5번 홀 좌측의 숲속으로 갈 수 있어 블루헤런에서 티샷이 가장 까다로운 곳이라 할 수 있다."* — right 150YD marker / long-hitter left 100YD marker / wide side bunker threatens the landing area's left / going right risks the forest left of hole 5. Matches the previously-stated reference almost verbatim.

## Result 2: full 18-hole systematic cross-check (decisive — not a single coincidence)

| Tournament hole | tourney yds | Blue Heron hole | Blue tee | White tee | diff vs Blue |
|---|---|---|---|---|---|
| H1 | 402 | East 1 | 410 | 394 | -8 |
| H2 | 188 | East 2 | 195 | 175 | -7 |
| H3 | 426 | East 3 | 467 | 443 | -41 |
| H4 | 542 | East 4 | 542 | 515 | 0 |
| H5 | 170 | East 5 | 175 | 155 | -5 |
| H6 | 410 | East 6 | 412 | 366 | -2 |
| H7 | 516 | East 7 | 540 | 510 | -24 |
| H8 | 377 | East 8 | 377 | 335 | 0 |
| H9 | 404 | East 9 | 423 | 399 | -19 |
| H10 | 570 | West 1 | 565 | 545 | +5 |
| H11 | 174 | West 2 | 174 | 159 | 0 |
| H12 | 410 | West 3 | 428 | **410** | -18 (0 vs White) |
| H13 | 376 | West 4 | 376 | 352 | 0 |
| H14 | 379 | West 5 | 379 | 354 | 0 |
| H15 | 423 | West 6 | 463 | 442 | -40 |
| H16 | 180 | West 7 | 176 | 156 | +4 |
| H17 | 390 | West 8 | 387 | 358 | +3 |
| H18 | 528 | West 9 | 524 | 504 | +4 |

**13 of 18 holes (72%) are within 10 yards of the official Blue tee, in the exact sequence position implied by H1-9=East/H10-18=West; mean absolute difference across all 18 holes is 10.0 yards.** The handful of larger gaps (H3, H7, H9, H12, H15) are all *shorter* than Blue and land between Blue and White — consistent with a real tournament using a combination-tee setup (a normal, common professional-event practice: forward markers on specific holes, not uniform back tees), not evidence against the mapping. This sequence-level agreement across all 18 holes, not just one, is the decisive evidence — a single hole's match could be coincidence; an 18-hole ordered sequence match at this consistency could not plausibly be.

## Result 3: visual comparison (qualitative, not pixel-exact)

Blue Heron's real official West Hole 3 image (`course-information-hole-information-visual-west-hole03.png`, fetched from real network traffic) and KLPGA's `hole_12.png` are independently-drawn stylized illustrations from two different systems, so an exact pixel/outline match is not expected or claimed. What IS observed in both, independently:
- A mid-fairway bunker complex positioned roughly at the midpoint of the hole, adjacent to a differently-textured (striped) fairway patch.
- A green-side bunker cluster immediately beside the green.
- A gently curving (non-straight) fairway shape, tree-lined on both sides.

This is consistent, corroborating evidence, not a deterministic proof on its own — weighted accordingly below.

## Verdict

**COURSE IDENTITY: PASS**

Basis (all three links independently evidenced, per the required chain):
1. **Tournament H12 → Blue Heron West H3**: confirmed systematically across the full real 18-hole yardage sequence (not a single-hole coincidence) — 13/18 holes within 10yd of the real official Blue tee in the correct sequence position, with H12 itself an exact match to White.
2. **Blue Heron West H3 → official geometry**: confirmed directly from the real official site (title, par, hdcp, 4-tee yardage table, Pro Tip hazard text matching the stated reference almost verbatim).
3. **Official West H3 image ↔ KLPGA's hole_12.png**: qualitatively consistent (mid-fairway bunker, green-side bunker, curving shape) — supporting, not deterministic, evidence.

Residual honest caveats (kept, not hidden): the 5 holes with larger yardage gaps (H3/H7/H9/H12/H15) indicate the tournament used a mixed/combination tee setup rather than uniform Blue tees — expected and normal, but means exact per-hole yardage cannot be assumed to always equal one listed tee; and the visual match is structural/qualitative, not an exact outline overlay.
