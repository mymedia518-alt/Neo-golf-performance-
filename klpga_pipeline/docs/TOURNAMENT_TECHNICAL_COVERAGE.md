# TOURNAMENT TECHNICAL COVERAGE — playerCode=10097 (김민선7)

RED TEAM mission (2026-09-25), section B/C/K. 96 completed tournaments
checked (local repository audit only — this sandbox has no live
network access to klpga.co.kr; see `docs/KLPGA_OFFICIAL_DATA_MAP.md`
for 13+ prior confirmations of the same block, re-confirmed again for
this round with a direct `curl` returning `403 CONNECT tunnel failed`).

## What was investigated

The mission proposed `GET /web/tourRecord/mainRecord?gameCode=<code>`
as a possible per-tournament technical-record page. An exhaustive
repo-wide search (raw HTML captures under `docs/discovery/`,
`content/website_v2/`, `evidence/`, and every collector/config module)
found **no local trace of this exact path**. It appears to conflate two
already-confirmed, DIFFERENT real endpoints:

- `SCORE_RECORD_ENDPOINT` (`/web/tourRecord/scoreRecord?gameCode=`) —
  gameCode-scoped, real, but everything captured of it so far is
  rank/round-score/WD-DQ-CUT status, never driving distance / fairway /
  GIR / putting.
- `PLAYER_PROFILE_ENDPOINT` (`/web/profile/mainRecord?playerCode=`) —
  carries the "mainRecord" name, but is playerCode-scoped (not
  gameCode-scoped) and, per the user's own earlier report, only ever
  carried 소속/출생년도/회원번호/입회년도.

`klpga.config.TOURNAMENT_RECORD_ENDPOINT_UNCONFIRMED` and
`klpga.collectors.tournament_record` (fetch-only, generic over any
`gameCode` + `playerCode`, no parser written — matching this project's
own "never guess DOM structure" discipline) are ready for the next
session that has real network access to actually try the URL the
mission gave and see what comes back.

## Coverage table (96 eligible completed tournaments)

| Metric | Available events | Eligible events | Coverage % | Gap classification |
|---|---|---|---|---|
| SG (Total/OTT/APP/ARG/PUTT) | 95 | 96 | 99.0% | `NEO NOT YET COLLECTED` (KB 2026090003 — raw SG HTML was never supplied to this repo, though the strokesGained page URL is proven real via KB's own captured leaderboard nav link) |
| Driving Distance (per tournament) | 0 | 96 | 0.0% | `SOURCE BLOCKED` (network required to determine whether `mainRecord?gameCode=` — or any per-tournament page — exposes this at all) |
| Fairway Accuracy (per tournament) | 0 | 96 | 0.0% | `SOURCE BLOCKED` |
| GIR (per tournament) | 0 | 96 | 0.0% | `SOURCE BLOCKED` |
| Putting (per tournament) | 0 | 96 | 0.0% | `SOURCE BLOCKED` |
| Average Score (per tournament) | 0 | 96 | 0.0% | `SOURCE BLOCKED` for the official per-tournament metric itself; note per-round raw strokes already exist for most tournaments in this repo, which is a *different*, derivable data point, not the same as KLPGA's own official 평균타수 figure |
| Birdies (per tournament) | 0 | 96 | 0.0% | `SOURCE BLOCKED` |
| Prize Money (per tournament) | 0 | 96 | 0.0% | `SOURCE BLOCKED` |

Season-level (not tournament-level) technical stats for 2025 — Driving
Distance, Fairway Accuracy, GIR, Sand Save, Scrambling, Putting (14
metrics) — ARE real and already in the product
(`TECHNICAL_STATS_2025.json`, recovered from `docs/discovery/raw_samples/`
during the prior verification round). That recovery is a season
aggregate from the confirmed `loadLocationRecord` taxonomy endpoint, a
genuinely different source and granularity than the tournament-level
question this section investigates — it is not double-counted above.

## Why every 0.0% row reads SOURCE BLOCKED, not NEO NOT YET COLLECTED

`NEO NOT YET COLLECTED` implies the page is known to exist and simply
hasn't been fetched yet (true for KB's SG — the page URL is proven).
For the other seven per-tournament metrics, no real page is confirmed
to exist AT ALL at tournament granularity — the only way to find out is
a live fetch of the mission's proposed URL (or a real DevTools capture
of whatever page KLPGA actually serves). Until that happens, calling it
"NEO's fault" would overclaim certainty in the other direction; SOURCE
BLOCKED is the honest state.

No row in this table is `KLPGA PAGE DOES NOT PROVIDE` or
`TRUE NOT APPLICABLE` — this project has not been able to rule either
in or out for anything except SG, because ruling those in requires a
real page inspection this sandbox cannot perform.
