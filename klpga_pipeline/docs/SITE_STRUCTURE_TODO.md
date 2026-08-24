# KLPGA site structure — confirmation log

This tracks exactly what has been confirmed against the live site (via a
real browser DevTools Network capture, or a real HTTP response fetched
from this environment) versus what is still an open question. Nothing in
the codebase should claim a field/endpoint is "confirmed" unless it's
listed as DONE here with a source.

Status legend: `[x]` confirmed · `[ ]` not yet confirmed.

## 1. Tournament list — `getGameList`

- [x] Endpoint: `POST https://klpga.co.kr/ajax/tourInfo/getGameList`
      (browser Network capture, 2026-08-24)
- [x] Request is `application/x-www-form-urlencoded` with
      `season`, `tourType`, `year` form fields
- [x] `tourType=RE` == KLPGA regular tour
- [x] Response is `application/json` with a top-level `gameList` array
- [x] Confirmed `gameList` entry fields: `gameCode`, `gameTitle`,
      `gameEngTitle`, `tourType`, `courseText`, `courseEngText`,
      `endDate` (format `YYYYMMDD`), `gameFinish` (`"F"` == completed)
- [ ] What other `tourType` values exist (Dream Tour / Jump Tour /
      Champions Tour / event) and their exact codes — **do not assume**
      `DR`/`JP`/`CH` etc. until seen in a real response
- [ ] What non-`"F"` `gameFinish` values mean (in-progress? cancelled?
      upcoming?) — only `"F"` is confirmed
- [ ] Tournament start date field (only `endDate` has been confirmed —
      no `startDate`-equivalent has been observed yet)
- [ ] `par`, `course_yards`/course length, `field_size`, `winner`,
      `winner_score`, `prize` fields — not observed in the confirmed
      capture; `tournament_master` leaves these NULL until confirmed
- [ ] Full response schema for a live `year=` value (empty in the
      confirmed example — behavior when set is unknown)
- [ ] Tournament detail-page URL pattern (`official_url`) — not
      confirmed, so `tournament_master.official_url` is left NULL and
      the column was made nullable (previously incorrectly NOT NULL)

## 2. Full leaderboard, per round — `roundLeaderboard`

- [x] Endpoint: `POST https://klpga.co.kr/load/leaderboard/roundLeaderboard`
      (browser Network capture, 2026-08-24 — triggered by clicking a
      round button on the FULL LEADERBOARD view)
- [x] Request is `application/x-www-form-urlencoded` with `gameCode`,
      `round` form fields
- [x] Response is an **HTML fragment**, not JSON
- [x] Confirmed row-level attributes: `data-rank`, `data-name`,
      `data-totunderpar`, `data-inghole`, `data-todayunderpar`,
      `data-score`, `data-round1score`..`data-round4score`
- [x] Confirmed detail-level attributes: `_gameCode`, `_playerCode`,
      `_playerName`, `_playerEngName`, `_round`, `_hole`
- [x] Empty string in any of the above == no value, parsed to `NULL`
      (never coerced to 0 or a guessed value)
- [x] `CUT` / `WD` / `DQ` / tied rank (`T1` etc.) are real `data-rank`
      string values — preserved raw in `rank_display`, with a
      best-effort normalized `rank` (int) alongside
- [ ] Exact surrounding HTML tag/class structure (table vs list, real
      class names) — the parser deliberately does NOT depend on this,
      only on the attributes above, so it should be robust to it, but
      it hasn't been directly observed
- [ ] Whether a CUT/WD/DQ player's **own earlier-round scores**
      (`data-round1score` etc.) are actually present in the *final*
      round's response, or only in that specific round's own response —
      `klpga.collectors.leaderboard.collect_all_rounds_for_game`
      implements a defensive per-round "missing check" for this, but
      the real behavior needs to be confirmed against a live cut player
- [ ] How many rounds a given tournament was scheduled for — no
      confirmed field carries this; `discover_final_round` probes
      downward from `config.PROBE_MAX_ROUNDS` (4) as a strategy, not a
      confirmed fact
- [ ] `round_to_par` for a round that was only ever seen via a *later*
      round's response (not directly queried) — left NULL rather than
      inferred, since `today_under_par` only applies to the round that
      was actually requested

## 3. Player Performance Statistics (data.klpga.co.kr data center)

- [ ] Nothing confirmed yet — `data.klpga.co.kr` has not been reachable
      from this environment (egress still blocked as of 2026-08-24; see
      session notes). `player_stats_snapshot` collection has not started.

## 4. robots.txt / terms of service

- [ ] Not yet fetched — network access to `klpga.co.kr` /
      `data.klpga.co.kr` has been blocked at the environment's egress
      proxy every time it's been attempted so far. `scripts/00_discover_site.py`
      is ready to run the moment access works, and will save
      `robots.txt` for both hosts before any other collection runs.

## Next steps once network access works

**Current goal is ONE real tournament (gameCode=2026080002), not the
full 100 — do not jump straight to `01_collect_tournaments.py`.**

1. Run `scripts/00_discover_site.py` and read `robots.txt` for both
   hosts before anything else.
2. Run `scripts/04_collect_single_tournament.py --season 2026
   --game-code 2026080002` and review its full printed output (the raw
   `getGameList` entry, round-fetch counts, sample player rows, raw HTML
   snippet). This is the single-tournament validation checkpoint.
3. Use that output to fill in the remaining `[ ]` items above (other
   tourType codes, gameFinish values, any startDate-equivalent field,
   the CUT/WD/DQ round-history question, real markup around the
   confirmed attributes).
4. Update this file's checkboxes based on what's actually observed —
   never mark something done from inference alone.
5. Only after step 2-4 look solid, scale up to
   `scripts/01_collect_tournaments.py` / `02_collect_leaderboards.py`
   for the full 100-tournament run.
