# KLPGA site structure — confirmation log

This tracks exactly what has been confirmed against the live site (via a
real browser DevTools Network capture, or a real collection run against
klpga.co.kr — this dev environment's own egress to the site is still
blocked, so real runs so far have come from a Windows PC with actual
internet access) versus what is still an open question. Nothing in the
codebase should claim a field/endpoint is "confirmed" unless it's listed
as DONE here with a source.

Status legend: `[x]` confirmed · `[ ]` not yet confirmed.

## 1. Tournament list — `getGameList`

- [x] Endpoint: `POST https://klpga.co.kr/ajax/tourInfo/getGameList`
      (browser Network capture 2026-08-24; **live-confirmed by an actual
      successful call from a Windows PC, 2026-08-24**, season=2026,
      gameCode=2026080002)
- [x] Request is `application/x-www-form-urlencoded` with
      `season`, `tourType`, `year` form fields
- [x] `tourType=RE` == KLPGA regular tour (live-confirmed:
      gameCode=2026080002 returned with `tourType: "RE"`)
- [x] `gameFinish="F"` == completed (live-confirmed: gameCode=2026080002
      matched under the RE list and its round data was fully collectible)
- [x] Response is `application/json` with a top-level `gameList` array
- [x] Confirmed `gameList` entry fields, **live-confirmed 2026-08-24**
      (gameCode=2026080002, "BC카드 · 한경 제48회 KLPGA 챔피언십"):
      `gameCode`, `gameTitle`, `gameEngTitle`, `tourType`, `courseText`
      ("포천힐스"), `courseEngText`, `outCourseText` ("가든"),
      `inCourseText` ("팰리스"), `startDate` ("20260820"), `endDate`
      ("20260823") — both `YYYYMMDD` — `prizeMoney` (integer KRW total
      purse, `1500000000`), `winnerCode` (`"11134"`), `winnerName`
      (`"서교림"`)
- [x] `startDate` field exists and uses the same `YYYYMMDD` format as
      `endDate` — previously unconfirmed, now mapped to
      `tournament_master.start_date`
- [x] `winnerCode`/`winnerName` exist and are the site's own
      authoritative winner designation — mapped to
      `tournament_master.winner`. `winner_score` is deliberately **not**
      read from any getGameList field (none confirmed) — it's derived
      from the real collected `player_event.total_score` for that
      `winnerCode` (see `klpga.collectors.aggregate.resolve_winner_score`)
- [x] `prizeMoney` (total tournament purse) confirmed — **not yet mapped
      to a `tournament_master` column**, since the original 16-column
      spec has no slot for it; `04_collect_single_tournament.py` prints
      it for visibility but does not persist it. Revisit if the schema
      is intentionally extended.
- [x] `outCourseText`/`inCourseText` (nine-hole course names) confirmed
      — also not mapped to a column for the same reason (only
      `courseText` -> `course_name` is in the fixed spec)
- [ ] What other `tourType` values exist (Dream Tour / Jump Tour /
      Champions Tour / event) and their exact codes — **do not assume**
      `DR`/`JP`/`CH` etc. until seen in a real response
- [ ] What non-`"F"` `gameFinish` values mean (in-progress? cancelled?
      upcoming?) — only `"F"` is confirmed
- [ ] `par`, `course_yards`/course length, `field_size` — not observed
      in any confirmed capture or live run yet; `tournament_master`
      leaves these NULL
- [ ] Per-player `prize_money` breakdown (only the tournament TOTAL
      `prizeMoney` is confirmed so far) — `player_event.prize_money`
      stays NULL until a per-player figure is actually observed
- [ ] Full response schema for a live `year=` value (empty in every
      capture/run so far — behavior when set is unknown)
- [ ] Tournament detail-page URL pattern (`official_url`) — not
      confirmed, so `tournament_master.official_url` is left NULL and
      the column was made nullable (previously incorrectly NOT NULL)

## 2. Full leaderboard, per round — `roundLeaderboard`

- [x] Endpoint: `POST https://klpga.co.kr/load/leaderboard/roundLeaderboard`
      (browser Network capture 2026-08-24; **live-confirmed by an actual
      successful call from a Windows PC, 2026-08-24**,
      gameCode=2026080002, round=4)
- [x] Request is `application/x-www-form-urlencoded` with `gameCode`,
      `round` form fields
- [x] Response is an **HTML fragment**, not JSON — live-confirmed
- [x] Confirmed row-level attributes: `data-rank`, `data-name`,
      `data-totunderpar`, `data-inghole`, `data-todayunderpar`,
      `data-score`, `data-round1score`..`data-round4score` —
      live-confirmed; sample verified against real round=4 data:
      서교림 (playerCode 11134) 70-67-69-74=280 (-8), rank 1;
      김민솔 68-70-71-71=280 (-8), rank 2; 박민지 73-69-70-69=281 (-7),
      rank 3; 문정민 72-67-75-68=282 (-6), rank T4; 고지우
      71-69-70-72=282 (-6), rank T4
- [x] Confirmed detail-level attributes: `_gameCode`, `_playerCode`,
      `_playerName`, `_playerEngName`, `_round`, `_hole`
- [x] Empty string in any of the above == no value, parsed to `NULL`
      (never coerced to 0 or a guessed value)
- [x] `CUT` / `WD` / `DQ` / tied rank (`T1` etc.) are real `data-rank`
      string values — preserved raw in `rank_display`, with a
      best-effort normalized `rank` (int) alongside. The live run's
      T4 case above confirms the tied-rank format.
- [x] **NEW, live-confirmed 2026-08-24**: the `round=4` response for
      gameCode=2026080002 contained **144 raw parsed player rows that
      merged down to 72 unique `player_code` values** — i.e. the site's
      HTML contains roughly 2 DOM entries per player (likely a
      compact-row + detail-panel pair, or similar). The parser's
      "select every element with `data-rank`, then merge by
      `player_code`" design already handles this correctly (verified:
      final `player_master` count == 72, matching the real field size),
      but the *exact* duplicate markup itself hasn't been inspected
      directly — only inferred from the row-count discrepancy.
- [ ] Exact surrounding HTML tag/class structure (table vs list, real
      class names, and specifically what the "other" duplicate row per
      player actually is) — the parser deliberately does NOT depend on
      exact tag/class names, only on the attributes above, so it's
      expected to be robust to this either way
- [ ] Whether a CUT/WD/DQ player's **own earlier-round scores**
      (`data-round1score` etc.) are actually present in the *final*
      round's response, or only in that specific round's own response —
      **still genuinely open**: the live run collected 72 players ×
      4 rounds = 288 `player_round` rows with no partial-round players
      surfacing, so it did not exercise a real CUT case (this
      tournament's field may simply have had no 36-hole cut, or all 72
      recorded players happen to have played all 4 rounds).
      `klpga.collectors.leaderboard.collect_all_rounds_for_game` still
      implements the defensive per-round "missing check" for this, but
      it needs a tournament with an actual CUT to fully confirm.
- [x] How many rounds a given tournament was scheduled for: for
      gameCode=2026080002, `discover_final_round`'s probe from
      `config.PROBE_MAX_ROUNDS` (4) found round 4 immediately (144 raw
      rows), confirming this event had (at least) 4 rounds. Still not a
      general confirmed *field* — the probe strategy remains necessary
      for tournaments with fewer rounds.
- [x] **Section-5 minimal-request strategy validated on real data**: the
      reported run shows only a single `round=4` fetch (144 raw rows ->
      72 unique players, `player_round` ending up at 288 = 72×4 — i.e.
      every collected player already had all 4 rounds' scores present
      in that ONE response). No earlier-round (`round=1/2/3`) requests
      were needed for this tournament — the "fetch final round only,
      re-fetch earlier rounds only if something's missing" logic worked
      as designed on real data, not just the synthetic test.
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

## 5. Bugs found on real data (fixed)

- **`winner_score` patch crashed with `sqlite3.IntegrityError: NOT NULL
  constraint failed: tournament_master.game_code`**, discovered on the
  live 5-tournament run, 2026-08-24. Root cause: patching just
  `{event_id, winner_score}` through the generic
  `INSERT ... ON CONFLICT DO UPDATE` upsert helper — SQLite validates
  NOT NULL constraints on the constructed INSERT candidate row (other
  NOT NULL columns, omitted from that partial dict) *before* it checks
  whether ON CONFLICT even applies, so this failed even though the row
  already existed and only an UPDATE was intended. This also crashed
  `02_collect_leaderboards.py`'s whole per-tournament loop outright
  (the patch call was outside the try/except), silently abandoning
  every tournament after the first.
  Fixed: `db/upsert.update_tournament_winner_score()` is now a plain
  `UPDATE`, not an upsert; the entire per-tournament pipeline in
  `02_collect_leaderboards.py` is now inside one try/except so a
  failure on one tournament doesn't kill the batch. Regression tests
  added (`tests/test_upsert.py`, `tests/test_validate.py`).
- **`03_validate.py` didn't detect the above failure** — it only
  checked row counts / duplicates / FK integrity, none of which notice
  a `tournament_master` row with zero `player_event` rows (exactly what
  the crash above left behind). Fixed: added a coverage check requiring
  every `tournament_master` row to have ≥1 `player_event` row.

## Next steps

1. ~~Run `scripts/04_collect_single_tournament.py --season 2026
   --game-code 2026080002`~~ — **DONE, 2026-08-24.** 1 tournament, 72
   players, 72 player_event rows, 288 player_round rows, winner
   confirmed (서교림/11134, 280/-8). Results folded into sections 1-2.
2. ~~Run `scripts/01_collect_tournaments.py --target 5` (small
   multi-tournament run)~~ — **DONE, 2026-08-24.** 5 tournaments, 336
   player_event rows total, `03_validate.py --target 5` ->
   `VALIDATION PASSED`. Also surfaced and confirmed the fix for the bug
   in section 5 above. This run's report didn't include new
   field-level detail (tourType/gameFinish variety, a real CUT case,
   etc.) beyond aggregate counts — the open items below are still open.
3. **Still open / not yet run:** `scripts/00_discover_site.py` —
   `robots.txt` for both hosts has not actually been fetched yet in any
   run so far.
4. **Current goal: the full 100-tournament run**
   (`scripts/01_collect_tournaments.py --target 100`, the default). See
   README.md "Running the full pipeline". This is also the run most
   likely to surface the still-open items below (a real CUT case,
   other tourType/gameFinish values, older-season quirks), since it
   spans more tournaments and likely more than one season.
5. Use that run's output to fill in the remaining `[ ]` items above
   (other tourType codes, non-F gameFinish values, a real CUT case for
   the round-history question, exact duplicate-row markup, `par`/
   `course_yards`/`field_size`, per-player prize money, `official_url`
   pattern).
6. Update this file's checkboxes based on what's actually observed —
   never mark something done from inference alone.
7. `player_stats_snapshot` (data.klpga.co.kr) collection has not
   started — nothing there is confirmed yet. That's the next data
   source after tournament/leaderboard collection is solid at 100.
