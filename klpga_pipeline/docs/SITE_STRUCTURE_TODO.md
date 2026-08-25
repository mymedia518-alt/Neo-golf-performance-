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
- [x] **`gameMethod` — tournament format field, live-confirmed
      2026-08-24 from the 100-tournament run.** `"0"` = standard stroke
      play (the baseline, `gameCode=2023060005`, "맥콜 · 모나 용평
      오픈 with SBS Golf", had `gameMethod: "0"` and collected
      normally). `"1"` = Match Play (all 3 "두산 매치플레이" /
      "Doosan Match Play" tournaments hit — `gameCode`s 2024050016,
      2025050002, 2026050002). `"2"` = Modified Stableford (all 3
      "동부건설 · 한국토지신탁 챔피언십" / "Dongbu Construction ·
      KOREIT Championship" tournaments hit — `gameCode`s 2023100002,
      2024100009, 2025100001). Both `"1"` and `"2"` were confirmed, by
      exhaustively probing `round=1..8` against the real
      `roundLeaderboard` endpoint for all of them, to return **zero
      player rows at every single round tried** — not a narrower round
      range than assumed, a genuinely different/unavailable data source
      for this endpoint. `filter_completed_regular_tour` now requires
      `gameMethod == config.GAME_METHOD_STROKE_PLAY` ("0") in addition
      to `tourType == "RE"` and `gameFinish == "F"`. Other `gameMethod`
      values may exist (Pro-Am format, etc.) and are unconfirmed —
      treated as unsupported until proven otherwise.
- [x] `leaderBoardYN` **ruled out** as a distinguishing field — it was
      `null` on the working baseline tournament too, not just the 6
      failures. Not used for anything.
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
- **CUT/WD/DQ players were silently dropped from collection entirely —
  a serious data-completeness bug**, discovered from the live
  5-tournament run's diagnostics, 2026-08-24: `player_round` was
  **exactly** `4 × player_event` across all 336 collected
  `player_event` rows (`SUM(1-made_cut)=0`, `SUM(withdrawn)=0`,
  `SUM(disqualified)=0`). That is not plausible as "none of 5 real
  KLPGA tournaments had a cut" — the real cause was that
  `collect_all_rounds_for_game`'s missing-round detection only scanned
  players **already present** in the final round's response for
  missing individual scores. A player who is cut/WD/DQ and therefore
  **entirely absent** from the final round's row list (not merely
  missing some fields on a present row) was never even seen, so they
  never triggered any earlier-round fetch and never appeared anywhere
  in the collected data — not with `made_cut=0`, just not present at
  all.
  Fixed (`src/klpga/collectors/leaderboard.py`): now always fetches
  round 1 too (the one round the full starting field is guaranteed to
  appear on) and diffs its `player_code` set against the final round's.
  Any discrepancy triggers fetching every intermediate round to locate
  where each dropped player's real last-played data (and CUT/WD/DQ
  marker) actually is. This costs more requests per tournament in the
  common case where cuts did happen (up to one request per round
  instead of one or two total), which is an intentional trade — data
  completeness over request-count minimization, per the project's own
  stated priority.
  **Consequence: both the earlier single-tournament (gameCode
  2026080002) and 5-tournament collected datasets are known-incomplete**
  and must be re-collected with the fixed code before being trusted —
  see "Next steps" below. This does NOT necessarily mean those specific
  tournaments actually had CUT players (gameCode 2026080002 in
  particular may be a genuinely small/no-cut field, as speculated
  earlier in this doc) — it means the pipeline could not have told us
  either way, which is the actual defect.
  Regression tests added: `tests/test_leaderboard_collector.py`
  (collector-level request-strategy tests) and
  `tests/test_cut_player_integration.py` (full collector -> merge ->
  build pipeline test asserting a CUT player ends up with
  `made_cut=0`, 2 rounds played, not dropped).
- **Follow-up after re-collecting the 5-tournament dataset with the
  fix above, 2026-08-24: player discovery now works (602 player_event
  rows, 1,862 player_round rows — no longer the suspicious exact-4x
  ratio), but `made_cut`/`withdrawn`/`disqualified` were STILL all
  zero.** Root cause: those three columns were only ever derived from
  `status` (set only when `data-rank` is the literal text `"CUT"` /
  `"WD"` / `"DQ"`) — never from `rounds_played` at all. The live data
  shows the real site does NOT use those literal strings in
  `data-rank`. The actual `rounds_played` distribution across the 5
  tournaments: `[(1, 14), (2, 252), (4, 336)]` — **zero 3-round
  players**, exactly the signature of a standard 36-hole cut (cut
  after round 2). Two distinct patterns for the non-4-round groups:
    - **252 players, 2 rounds, plain real numeric `finish_position`**
      (e.g. 62, 90, 101 — real ranks among the field, not a special
      marker). This is almost certainly the normal missed-cut group.
    - **14 players, 1 round, `finish_position == '999'`** — a sentinel
      value, not a real rank. This is NOT yet confirmed to mean WD
      specifically vs. DQ specifically vs. some other single "did not
      complete round 1" bucket — `999` could cover more than one real
      status. `scripts/07_inspect_status_markup.py` was added to
      inspect the raw cached HTML around these `999` rows (using the
      already-fetched disk cache, zero new requests) for any
      additional marker (class name, title attribute, different text)
      before writing classification logic — **not yet run**.
  **`made_cut`/`withdrawn`/`disqualified` derivation is being reworked
  to key off `rounds_played` vs. the tournament's actual final round
  (a real structural fact) instead of `data-rank` text matching** —
  see the fix entry that follows this one once the `999` markup
  inspection comes back. Not fixed yet as of this entry.
- **`scripts/07_inspect_status_markup.py` run, 2026-08-24 — raw markup
  for 5 real `999` rows (gameCode=2026080002) inspected.** Confirmed:
  - `data-rank="999"` is mirrored by a `data-updown="999"` attribute
    (not otherwise useful — just duplicates rank).
  - `data-score`, `data-totunderpar`, `data-todayunderpar` are ALL
    reset to the placeholder `"0"` alongside `data-rank="999"` — real
    zeros are never paired with a `999` rank in the sample.
  - 4 of 5 sampled players had a completely VALID round 1 (real rank
    like 84/109/113, real score like 75/78/79) and only became `999`
    starting round 2 — i.e. they legitimately played round 1, then
    something happened before/during round 2. The 5th player was
    already `999` at round 1 itself, with `data-round1score="0"`.
  - `class="table-drop"` appears on every sampled row (999 AND normal)
    — a generic UI class for the expandable detail panel, not a
    status-specific marker.
  - **No `"WD"`, `"DQ"`, or any other status text was found anywhere**
    in the surrounding markup (no distinguishing class name, no
    `title` attribute, nothing) — this endpoint's data genuinely does
    not appear to let WD be told apart from DQ.
  - `data-inghole` (e.g. "1", "9", "10" on `999` rows) does NOT behave
    consistently enough to be trusted yet: several players' round-1
    responses show `data-inghole` values less than 18 (e.g. "9") DESPITE
    those same rows having a complete, valid round-1 score — so
    `data-inghole` is NOT reliably "holes completed in the round being
    queried." Left uninterpreted; not used for any classification
    logic. Still an open question for a future investigation.
  **Fixed** (`src/klpga/parsers/leaderboard_parser.py`,
  `src/klpga/collectors/aggregate.py`):
  - `data-rank="999"` is now parsed as `status="INCOMPLETE"`,
    `rank=None` (previously incorrectly parsed as a literal numeric
    rank 999) — `rank_display="999"` is still preserved raw.
  - When a row's status is `INCOMPLETE`, its
    `total_strokes`/`total_under_par`/`today_under_par` are set to
    `None` instead of the placeholder `"0"` — but ONLY for this
    confirmed sentinel case; a normal row's genuine `"0"` (even par)
    is untouched.
  - A literal `"0"` in any `data-round{N}score` or `data-score` field
    is now always parsed as `None` — 0 strokes is never realistic for
    a round or a tournament total in golf, regardless of the row's
    rank, so this isn't limited to the `999` case.
  - `made_cut` is now derived structurally: 1 if the player has a real
    (non-sentinel, non-placeholder-zero) score for the tournament's
    actual final round, else 0 — no longer dependent on `data-rank`
    text matching at all, since the real site doesn't use `"CUT"` text.
  - `withdrawn`/`disqualified` are LEFT AT 0 for `INCOMPLETE` rows —
    genuinely unconfirmed which applies, and this is not guessed. They
    still fire if `status` is literally `"WD"`/`"DQ"` text (kept for
    forward-compatibility in case some response somewhere does use
    it — never actually observed). `finish_position` preserves the raw
    `"999"` so this group stays identifiable to downstream consumers
    despite the boolean columns not distinguishing it from a normal
    missed cut.
  Regression tests added: `tests/test_leaderboard_parser.py` (parser-
  level: the 999-sentinel row, literal-zero-score suppression, and a
  belt-and-suspenders check that genuine even-par `"0"` on a NORMAL row
  is preserved) and `tests/test_cut_player_integration.py` (full
  pipeline test using the exact real markup shape from playerCode 9777).
  **The earlier re-collected 5-tournament dataset is once again
  known-incomplete for made_cut/withdrawn/disqualified specifically
  (though its player/round discovery is correct) and needs another
  re-collection with this fix** — see "Next steps" below.
- **Re-collected live, 2026-08-24, on the fix above — CONFIRMED
  WORKING**: `made_cut` split `(0, 266), (1, 336)` across 602
  player_event rows (`03_validate.py --target 5` -> `VALIDATION
  PASSED`). `rounds_played` distribution shifted from the earlier
  (incorrect) `[(1,14),(2,252),(4,336)]` to `[(None,10),(1,15),(2,241),
  (4,336)]` — the `"0"`-score fix correctly reclassified some players
  who looked like they had 2 valid rounds as actually only having 1, or
  (10 players) 0. This 0-round group is the same real pattern as
  playerCode 9750: `data-rank="999"` already on round 1 itself, with
  `data-round1score="0"` — a player who registered in the field but has
  zero valid round scores anywhere.
  **Follow-up bug found from this**: `rounds_played` was stored as
  `NULL` for these 10 players (`len(round_scores) or None` collapses a
  real, confirmed `0` into `NULL`, which misreads as "unknown" rather
  than "verified zero"). Fixed — `rounds_played` now stores the literal
  int, including `0`. Regression test added
  (`tests/test_cut_player_integration.py`,
  `test_zero_valid_rounds_pattern_stores_real_zero_not_null`).
  **Decision on WD vs. DQ classification** (in response to a direct
  question about whether the 10 zero-round + 15 one-round players need
  further status classification): **no further classification is
  attempted.** The raw HTML inspection (see the entry above) confirmed
  no marker anywhere distinguishes WD from DQ at this endpoint — adding
  a specific split would mean guessing, which violates the project's
  own "don't fabricate" requirement. `withdrawn`/`disqualified` stay
  `0` for every non-completing player (whether a normal 2-round missed
  cut or an abnormal 0/1-round early exit). Downstream consumers can
  still distinguish "normal missed cut" from "abnormal early exit"
  using already-real, already-collected fields: `rounds_played == 2`
  with a plain numeric `finish_position` is the normal missed-cut
  pattern for a 36-hole-cut event; `rounds_played < 2` with
  `finish_position == '999'` is the abnormal-exit pattern. No new
  column was added for this — the existing fields already carry the
  signal.
- **First full 100-tournament run, 2026-08-24: 94/100 tournaments
  collected their leaderboard successfully (11,057 player rows), but 6
  failed with `discover_final_round` exhausting rounds 1..4 with zero
  player rows.** This was a genuinely different failure mode from
  anything seen at smaller scale — not a missing/incomplete round, but
  zero data on every round tried. The batch-processing and
  validation-coverage work from earlier entries in this section handled
  it exactly as designed: `02_collect_leaderboards.py` logged each of
  the 6 individually to `collection_runs` and kept processing the other
  94; `03_validate.py` correctly caught the resulting coverage gap.
  Root cause found via `scripts/08_inspect_failed_leaderboards.py`
  (raw `getGameList` comparison against a working baseline, plus an
  exhaustive `round=1..8` probe against the live endpoint for all 6) —
  see the `gameMethod` entry in section 1 above for the full finding.
  **Fixed**: `filter_completed_regular_tour` now excludes
  `gameMethod != "0"` tournaments (Match Play, Modified Stableford),
  so the season walk-back in `collect_most_recent_completed`
  automatically continues past them to find real stroke-play
  replacements — no manual exclusion list needed. Regression test
  added (`tests/test_tournaments_collector.py`,
  `test_filter_completed_regular_tour_excludes_match_play_and_stableford`).
  **The current 100-tournament dataset (94 usable + 6 unusable) must be
  re-collected from scratch with this fix** — see "Next steps" below.
- **`src/klpga/db/export_csv.py` exited with no error and no `data/csv`
  directory at all, on Windows, against a real, already-validated
  100-tournament DB (`03_validate.py --target 100` -> `VALIDATION
  PASSED`), 2026-08-25.** `export_all()`'s very first line is
  `out_dir.mkdir(parents=True, exist_ok=True)` — for the directory to
  never appear, execution must have stopped before `export_all` even
  ran, i.e. at module import time. The only import in that script not
  already proven to work on that machine (every other script — 01-04,
  07, 08, 03_validate.py — uses only sqlite3/argparse/stdlib and had
  already run successfully) was `import pandas as pd`, a C-extension
  package. This dev sandbox has no way to reach the user's Windows
  machine to capture the actual traceback, so rather than guess at the
  exact DLL/wheel mismatch, **the pandas/numpy dependency was removed
  from this script entirely** — a plain SQLite-rows-to-CSV export has no
  real need for it. Rewritten using only `csv` + `sqlite3` (stdlib).
  Also fixed two related, genuine (not just Windows-specific) gaps found
  while rewriting:
  - `sqlite3.connect(db_path)` silently creates a new, empty database
    file if `db_path` doesn't exist — so a wrong/mistyped `--db` path
    would previously not fail clearly, it would instead try to `SELECT
    *` from tables that don't exist in that brand-new empty file.
    `export_all` now explicitly checks `db_path.exists()` first and
    raises `FileNotFoundError` with a clear message (mirroring
    `03_validate.py`'s existing `--db` check) — matching exit code 2.
  - `main()` now wraps the whole export in try/except: any unexpected
    exception prints a full traceback to stderr and returns exit code 1
    — there is no code path left that can exit 0 (or exit with no
    printed output at all) without having actually written the CSVs.
  Per-table output was already printed (row count + full path); a
  final summary line (`Exported N table(s), M row(s) total -> <out_dir>`)
  was added so a real run's completion is unambiguous at a glance.
  `pandas` removed from `requirements.txt` (nothing else in the repo
  imports it — confirmed by grep).
  Regression tests added: `tests/test_export_csv.py` — CSV headers/row
  counts per table, boolean TRUE/FALSE mapping, NULL -> empty string
  (not the literal word "None"), the missing-`--db` FileNotFoundError
  path, and the specific reported symptom (every table empty must still
  produce a real `csv/` directory with header-only files, never a
  silent no-op).

## Next steps

1. ~~Run `scripts/04_collect_single_tournament.py --season 2026
   --game-code 2026080002`~~ — **DONE, 2026-08-24.** 1 tournament, 72
   players, 72 player_event rows, 288 player_round rows, winner
   confirmed (서교림/11134, 280/-8). Results folded into sections 1-2.
   **Superseded, 2026-08-24: known-incomplete** per the CUT/WD/DQ bug
   in section 5 — must be re-collected with the fixed code.
2. ~~Run `scripts/01_collect_tournaments.py --target 5` (small
   multi-tournament run)~~ — **DONE, 2026-08-24.** 5 tournaments, 336
   player_event rows total, `03_validate.py --target 5` ->
   `VALIDATION PASSED`. Also surfaced and confirmed the fix for the
   `winner_score` bug in section 5. **Superseded, 2026-08-24:
   known-incomplete** — this run's diagnostics (`SUM(1-made_cut)=0`
   across all 336 rows) is exactly what led to finding the CUT/WD/DQ
   drop bug in section 5. Re-collected.
3. ~~Re-run the 5-tournament checkpoint with the player-discovery
   fix~~ — **DONE, 2026-08-24.** 602 player_event rows, 1,862
   player_round rows — player discovery confirmed fixed (no longer the
   suspicious exact-4x ratio). **But `made_cut`/`withdrawn`/
   `disqualified` were STILL all zero** — see the follow-up entry in
   section 5. Do NOT treat this dataset's CUT/WD/DQ flags as correct
   yet; the `rounds_played`/`finish_position` data itself looks right.
4. ~~Run `scripts/07_inspect_status_markup.py`~~ — **DONE, 2026-08-24.**
   Raw markup for 5 real `999` rows inspected; no WD/DQ distinction
   found anywhere. Results and the made_cut/withdrawn/disqualified fix
   folded into section 5 above.
5. ~~Re-run the 5-tournament checkpoint with the made_cut/withdrawn/
   disqualified fix~~ — **DONE, 2026-08-24. CONFIRMED WORKING.**
   `made_cut` split (0, 266), (1, 336) across 602 player_event rows;
   `03_validate.py --target 5` -> `VALIDATION PASSED`. Found and fixed
   one more follow-up bug (`rounds_played` NULL instead of a confirmed
   0 — see section 5) and made the explicit decision NOT to attempt a
   WD/DQ split (no marker exists to support it; `rounds_played` +
   `finish_position` already carry the distinguishing signal). This
   dataset has NOT been re-collected again with the `rounds_played=0`
   display fix specifically — that fix is cosmetic (doesn't change
   made_cut or any other classification), so it doesn't block scaling.
6. ~~Scale up to the full 100-tournament run~~ — **DONE, 2026-08-24.**
   94/100 collected cleanly (11,057 player rows); 6 failed
   (`gameCode`s 2023100002, 2024050016, 2024100009, 2025050002,
   2025100001, 2026050002) — all confirmed Match Play or Modified
   Stableford via `scripts/08_inspect_failed_leaderboards.py`. See the
   entry in section 5 above. **Superseded, 2026-08-24: this dataset
   must be re-collected from scratch** now that
   `filter_completed_regular_tour` excludes `gameMethod != "0"`.
7. **Current goal: re-run the full 100-tournament collection with the
   `gameMethod` fix** (`scripts/01_collect_tournaments.py --target
   100` against a fresh `--reset` DB). This time the season walk-back
   should skip Match Play/Stableford tournaments automatically and
   walk back far enough to find 100 real replacements — expect it to
   reach further back in time than the previous run did, and possibly
   take a bit longer. `03_validate.py --target 100` should report
   `VALIDATION PASSED` with zero coverage-gap failures this time. See
   README.md "Running the full pipeline".
8. Use that run's output to fill in the remaining `[ ]` items above
   (other tourType codes, non-F gameFinish values, exact duplicate-row
   markup, what `data-inghole` actually means, `par`/`course_yards`/
   `field_size`, per-player prize money, `official_url` pattern, and
   whether some OTHER endpoint — e.g. a default full-leaderboard view
   without a `round` param — distinguishes WD from DQ where this one
   doesn't).
9. Update this file's checkboxes based on what's actually observed —
   never mark something done from inference alone.
10. `player_stats_snapshot` (data.klpga.co.kr) collection has not
    started — nothing there is confirmed yet. That's the next data
    source after tournament/leaderboard collection is solid at 100.
