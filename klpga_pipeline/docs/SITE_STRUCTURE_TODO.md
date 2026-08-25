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
      session notes). The OFFICIAL columns in `player_stats_snapshot`
      (`scoring_average`, `sg_*`, `gir`, `driving_distance`,
      `driving_accuracy`, `putting_average`, `sixties_rate`,
      `top10_rate`, `birdie_average`, `par_breakers`, `sand_save`,
      `scrambling`) are still all NULL in every row — this data source
      has not started. See section 6 below for the *derived* columns
      that ARE now populated from the already-validated tournament
      dataset — those are a different thing and do not fill this gap.

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

## 6. Analytics layer — derived `player_stats_snapshot` metrics (NOT official Data Center stats)

**Confirmed complete, 2026-08-25: the 100-tournament raw dataset is the
validated checkpoint.** Windows production DB: 100 distinct
tournaments, 0 excluded special-format gameCodes remaining, 0
zero-player tournaments, `03_validate.py --target 100` ->
`VALIDATION PASSED`. Row counts: `tournament_master` 100,
`player_master` 546, `player_event` 11,850, `player_round` 33,215, CSV
export 45,711 total rows. This raw dataset is NOT to be modified or
recollected unless a genuine data-integrity bug is found — everything
in this section reads from it, never writes to it.

**Whether true Strokes Gained and GIR are computable from this
dataset: NO, confirmed by inspection, not assumed.** Both require
shot-level data this project has never collected and the confirmed
`roundLeaderboard` endpoint does not expose:
  - **Strokes Gained** (Total or any component — off-the-tee, approach,
    around-the-green, putting) needs each shot's distance-to-hole and
    lie, compared against a field-relative baseline. Nothing at that
    granularity exists anywhere in `player_round` — only a whole
    round's final stroke count.
  - **GIR** (greens in regulation) needs to know, hole by hole, whether
    the green was reached in par-minus-2 strokes. The only
    hole-related field ever observed, `data-inghole`, was investigated
    in an earlier session (see section 2 above) and found to NOT behave
    consistently as "holes completed" — several rows showed
    `data-inghole` values inconsistent with an otherwise complete,
    valid round score. It was explicitly left uninterpreted then and
    still is; it is not usable as a GIR proxy.
  Per the project's explicit instruction, **no proxy metric was built
  for either and none is labeled "SG Total" or "GIR" anywhere** — the
  corresponding `player_stats_snapshot` columns (`sg_total`,
  `sg_off_the_tee`, `sg_approach`, `sg_around_green`, `sg_putting`,
  `gir`, and their `_rank` columns) are simply never written by the new
  analytics code and stay NULL, same as every other official Data
  Center column (driving distance/accuracy, putting average, sixties
  rate, birdie average, par breakers, sand save, scrambling).

**What IS derivable, and built**: `src/klpga/analytics/player_stats.py`
(`compute_player_stats`) computes 19 `derived_*` columns per
`player_id` (the confirmed real KLPGA playerCode — never player_name)
straight from `tournament_master` / `player_event` / `player_round`:
tournaments played, rounds played, made cuts + cut rate, wins, top 5,
top 10, best finish, a true per-round scoring average, average
score-to-par, scoring standard deviation, recent-form averages over the
5/10/20 most recent events (each with a companion `_n` column recording
how many events actually contributed, since most players have played
far fewer than 20 of the 100 tournaments), and a linearly-weighted
recent-form figure over up to the 10 most recent events. **Every
metric's exact source field, formula, sample size, and missing-data
treatment is documented in that module's docstring** — not repeated
here to avoid the two copies drifting apart.

One nuance worth flagging explicitly: "score relative to par" is
NOT computed by this pipeline from a course-par value — course/hole par
has never been confirmed in any live response
(`tournament_master.par` / `player_round.course_par` are always NULL,
see section 1). It is instead the average of the site's OWN published
to-par figure per tournament (`data-totunderpar`, confirmed live,
already stored as `player_event.score_to_par`) — official per-event
data, aggregated by this pipeline, not estimated by it.

**Schema change**: `player_stats_snapshot` now documents two clearly
separated column groups in `schema.sql` — the pre-existing OFFICIAL
Data Center columns (group (a), still all NULL) and the new `derived_*`
columns (group (b)). A new `snapshot_type='derived_trailing100'` value
was added to the `CHECK` constraint for this group; `related_event_id`
is always NULL for it (not tied to one event). `src/klpga/db/migrate.py`
(`ensure_player_stats_snapshot_schema`) safely adds the new columns to
an existing DB created under the old schema — but ONLY when
`player_stats_snapshot` is still empty (true on every validated DB so
far, since this data source had never been populated); it refuses and
raises instead of ever dropping a populated table under the old shape.
`scripts/09_build_player_stats_snapshot.py` runs the migration, then a
full DELETE + re-INSERT of every `derived_trailing100` row on each run
(a deliberate full recompute, not an incremental upsert — see that
script's docstring for why an upsert would be wrong here: SQLite never
treats two NULL `related_event_id` values as conflicting under the
table's `UNIQUE` constraint, so an upsert would silently accumulate
duplicate rows on every re-run instead of replacing them).

Regression tests: `tests/test_player_stats.py` (every formula
hand-computed against a synthetic scenario — see that file for the
worked example), `tests/test_migrate.py` (migrates a 0-row old-shape
table, is a no-op once current, refuses to drop a populated old-shape
table), `tests/test_build_player_stats_snapshot.py` (end-to-end:
snapshot metadata, official columns stay NULL, re-running replaces
rather than duplicates rows). 66/66 tests passing. Also run manually
against a synthetic multi-tournament test DB (5 players x 8
tournaments) — sane, non-degenerate values across all `derived_*`
columns, confirmed no duplicate rows after a second run, and confirmed
the old-shape-DB migration path against a hand-built pre-migration
table.

**Not yet decided or built**: the win-probability model itself. Per
explicit instruction, this is deferred until the `derived_*` feature
set above is reported back and reviewed.

**Red-team check, 2026-08-25: `derived_avg_score_to_par` looked
unrealistically low for real players (이예원 -4.69, 박지영 -4.91, 김민솔
-4.72) after the production snapshot build (546/546 populated).**
Traced the exact code path rather than assuming it was fine:
`derived_avg_score_to_par` = mean of `player_event.score_to_par`
(`src/klpga/analytics/player_stats.py`); `player_event.score_to_par` =
`entry["total_under_par"]` (`src/klpga/collectors/aggregate.py
build_rows()`), which is set ONLY in `merge_player_rows()`'s summary
section from `row.total_under_par` — parsed from `data-totunderpar`, a
per-TOURNAMENT cumulative field. The separate per-ROUND to-par field
(`data-todayunderpar` -> `PlayerRoundRow.today_under_par` ->
`player_round.round_to_par`) is written to an entirely different dict
key (`entry["round_to_par"]`, a per-round dict) and is never read by
`compute_player_stats()` anywhere — confirmed by grep across
`src/klpga/`, not just re-reading the two functions in isolation. So
`derived_avg_score_to_par` is "average TOURNAMENT-total score-to-par
across events," never a round-level figure, and there is no code path
that mixes the two. A -4 to -5 average across a real player's full mix
of made-cut (typically -5 to -15 as a 4-round total) and missed-cut
(commonly single-digit positive as a 2-round total) events is the
expected order of magnitude for this metric — it would only look wrong
if mistaken for a single round's to-par, which is exactly the
mislabeling risk this check exists to rule out.
Built `scripts/11_diagnose_avg_score_to_par.py` to verify this against
REAL production rows rather than stop at the code trace: for each of 5
representative players (defaults to the 3 flagged names + 2 more, or
falls back to the players with the most `derived_tournaments_played` if
a name doesn't match) it prints, per tournament: every raw
`player_round.round_score`, the sparse per-round `round_to_par` when
directly queried, `player_event.total_score` and `.score_to_par`, and
an independently reverse-engineered `implied_total_par = total_score -
score_to_par` (and per-round average) — which should land near a real
golf par (68-74) for every single event if `score_to_par` really is a
self-consistent tournament total, and won't if it's ever corrupted or
mixed with something else. Confirmed working end-to-end (including a
test that deliberately corrupts `score_to_par` and verifies the
implausible-par flag actually fires).

**Confirmed against the real Windows production DB, 2026-08-25:
`scripts/11` ran for 김민주 — `implied_avg_par/round = 72.00` for every
one of 97 valid events, mean across all 97 = 72.00, ZERO implausible
events.** This is the strongest possible confirmation short of an
official par field: `score_to_par` is a genuinely self-consistent
tournament-total figure, not corrupted or mixed with a round-level
value anywhere in the production dataset.

**Follow-up red-team round, 2026-08-25 (user-initiated, before any
modeling work): even though `derived_avg_score_to_par` was confirmed
NOT buggy, its OLD NAME didn't say it was a tournament-total average —
a real risk of being misread as a per-round figure by anyone building
on top of it later (exactly the original trigger for this whole
investigation).** Resolved by design, not just documentation:
  - `derived_avg_score_to_par` renamed to `derived_avg_event_score_to_par`
    (same formula, unchanged) with a new `_n` sample-size companion.
  - **New metric added**: `derived_avg_round_score_to_par` =
    sum(`score_to_par`) / sum(`rounds_played`) across a player's valid
    events — a rounds-WEIGHTED rate, comparable in magnitude to what a
    single round typically looks like (unlike the event-average, which
    treats a 2-round missed cut and a 4-round made cut as equally
    weighted data points). Also gets an `_n` companion storing the
    actual summed round count (the rate's true denominator).
  - **Every other tournament-total-based derived column renamed for the
    same reason**, so the naming CONVENTION itself now prevents this
    class of mistake rather than relying on any one column's docstring:
    `derived_avg_score` -> `derived_avg_round_score`, `derived_
    scoring_stddev` -> `derived_round_scoring_stddev` (both already
    genuinely per-round, renamed only for consistency),
    `derived_recent_form_{5,10,20}` -> `derived_recent_event_form_
    {5,10,20}`, `derived_weighted_recent_form` -> `derived_
    weighted_recent_event_form`. Going forward: any `derived_*` column
    built from `player_event.score_to_par` (a per-event total) MUST
    include `_event_` in its name; anything built from real per-round
    data or expressed as a per-round rate MUST include `_round_`. See
    `src/klpga/analytics/player_stats.py`'s docstring, which states this
    convention explicitly as a rule for any future column.
  - **`src/klpga/db/migrate.py`'s safety check was also tightened**:
    it used to refuse touching player_stats_snapshot if it had ANY rows
    under an outdated schema. Since a populated production DB (546
    rows) needed exactly this kind of rename applied, that check would
    have wrongly refused a perfectly safe migration — `derived_
    trailing100` rows are BY DESIGN always fully, mechanically
    reproducible by re-running `scripts/09`, so dropping and rebuilding
    them loses nothing. The check now only refuses if a row exists
    under a snapshot_type OTHER than `derived_trailing100` (i.e. real,
    non-reproducible official-stat data) — regression test added
    confirming a 50-row populated old-shape `derived_trailing100` table
    migrates cleanly, while a single `season_final` row still correctly
    blocks the migration.
  - **Mathematical verification, not just a formula choice**: added
    `scripts/12_verify_round_to_par_reliability.py` to check, against
    real production rows, whether `player_round.round_to_par`
    (`data-todayunderpar`) is reliable enough to use DIRECTLY instead of
    the sum-of-totals rate formula above — explicitly not assumed
    reliable just because the field exists.
      - CHECK A (no additivity assumption needed): for players with
        exactly one valid round, `round_to_par` for that round and
        `score_to_par` for the event must be identical — with only one
        round played, "today" and "the tournament total so far" are the
        same thing by definition.
      - CHECK B (tests additivity): for players whose event has
        `round_to_par` present on every round they played, the sum of
        those per-round values must equal `score_to_par` if the
        per-round figures are genuine independent daily deltas.
      - CROSS-CHECK: for the CHECK B subset,
        `derived_avg_round_score_to_par`'s formula
        (`sum(score_to_par)/sum(rounds_played)`) is compared against a
        direct reconstruction from the raw `round_to_par` field
        (`sum(round_to_par)/count(rounds)`) restricted to that same
        subset — these must converge, which is the actual proof (not
        just an assertion) that the chosen rate formula is
        mathematically consistent with real per-round data wherever
        there's enough of it to check.
    Confirmed working against synthetic data in both directions (a
    hand-built consistent case that passes, and a hand-built corrupted
    case that correctly gets flagged).

- **Confirmed against the real Windows production DB, 2026-08-25:
  `scripts/12_verify_round_to_par_reliability.py` result: `round_to_par`
  coverage 33,006/33,215 = 99.4%; CHECK B fully-covered multi-round
  events: 11,179; exact matches: 11,179/11,179 (zero mismatches);
  cross-check `sum(score_to_par)/sum(rounds_played)` vs.
  `sum(round_to_par)/count(rounds)` both = 0.51 -> AGREE.**
  `derived_avg_round_score_to_par` is now verified end-to-end: the
  formula, the raw field it could have used instead, and the real
  production data all agree. This closes both red-team rounds on the
  score-to-par metrics — see the win-probability model design report
  (approved direction: Model B's mechanism, fit Model C's
  walk-forward way) for how this feature is used next.

## 7. Upcoming-tournament entry list — CONFIRMED source, collection + storage layer DONE

**Status: fully closed, 2026-08-25.** Endpoint and HTML structure
CONFIRMED via manual browser capture, cross-checked against the full
raw HTML the user pasted verbatim. Parser, collector (fetch +
`player_master` matching + completed-tournament cross-check), a
read-only diagnostic script, and the `tournament_entry` storage layer
(idempotent UPSERT, additive migration, live-verified against the real
field) are all implemented, tested, and confirmed against a real
production run on the Windows PC (120/120 parsed, 119/120 matched — see
below). Full suite: 122/122 passing. This was a hard prerequisite for
the win-probability model (it must rank only the actual entered field)
and is tracked separately from the model design itself. **Next design
gate before the model: a point-in-time feature/backtest layer, to
guarantee no future information leaks into historical predictions —
not yet started.**

- [x] **CONFIRMED live, 2026-08-25 (manual browser capture, gameCode=
      2026080001, 제15회 KG 레이디스 오픈):**
      ```
      GET https://klpga.co.kr/web/tourInfo/entry?gameCode=<code>
      response: HTTP 200, text/html; charset=UTF-8 — a full rendered
      page, NOT JSON, NOT an AJAX fragment.
      ```
      Confirmed participant example: 문정민, whose KLPGA player detail
      page resolves to `mainRecord?playerCode=10296` — i.e. `playerCode`
      is the same identity space already used everywhere else in this
      project (`player_master.player_id`).
- [x] **Full raw HTML cross-check, 2026-08-25** — the user pasted the
      complete live page (not a summary). Saved verbatim as
      `tests/fixtures/entry_list_sample.html` (640KB, real captured
      data — same convention as `round_leaderboard_sample.html`).
      Confirmed structure from this real capture:
      - A summary box (`div.bg-light.boxshadow div.row.text-center`)
        with `div.col > h4 (label) + h1 (value)` pairs: 총 참가자=120,
        자격자=115, 추천자=5, 초청자=0.
      - **Two tables exist on the page.** `<h2>즐겨찾기 선수</h2>`
        ("favorites") is wrapped in `<div class="section-favorit"
        style="display:none">`, and — confirmed by inspecting the real
        markup — actually re-lists ALL 120 entrants again, with every
        individual `<tr>` also carrying its own `style="display:none;"`.
        This is a client-side favorite-toggle duplicate of the roster,
        NOT a second real list, and is excluded entirely by the parser.
        `<h2>전체 선수</h2>` ("all players") is the real, confirmed
        entry list — its row count (120) reconciles exactly with the
        summary box's 총 참가자 figure.
      - Real player rows carry `a.col-7[href*='playerCode=X']` (a
        second anchor around the avatar `<img>` carries the same code
        but no name text — only `a.col-7` is used). Interleaved in the
        same `<tbody>` are section-divider rows with no player link,
        e.g. `<td colspan="3">| 자격자 : 115명</td>`, which only update
        a running category context for the rows that follow. A category
        with 0 entrants (초청자 here) has no divider row at all.
      - The last `<td>` in a real player row is a free-text "참가 자격"
        (qualification/eligibility REASON) column, e.g. "시드순위자",
        "2025 정규투어 상금순위 60위 이내", "2024 일반대회 우승자", or
        empty.
      - **CONFIRMED cross-check:** 문정민's real row has
        `playerCode=10296`, category "자격자", reason "2024 일반대회
        우승자" — exactly matching the live browser confirmation. Five
        additional real players were cross-checked the same way
        (강가율/9174, 강지선/10623, 방신실/10095, 임진영/10138,
        정영화/10143 under 추천자 with an empty reason) — see
        `tests/test_entry_list_parser.py`.
- [x] **`entry_status` — investigated, NO confirmed source found.** The
      original schema sketch (STEP 5) proposed an `entry_status` column
      for withdrawal/DNS. No WD/DNS/cancellation marker of any kind
      (text, CSS class, or attribute) was found anywhere in the real
      captured HTML — the same finding this project already made for
      `roundLeaderboard`'s WD/DQ text (see section 5). The schema below
      is revised accordingly: `entry_status` is dropped in favor of the
      two genuinely confirmed fields, `qualification_category` (자격자/
      추천자/초청자, from the divider rows) and `qualification_reason`
      (the free-text "참가 자격" column). True attendance/withdrawal
      status remains an open, unconfirmed gap — not fabricated.
- [x] **Implemented, 2026-08-25:**
      - `src/klpga/parsers/entry_list_parser.py` —
        `parse_entry_summary()` / `parse_entry_list_html()`, excludes
        the favorites table, tracks category via divider rows, and
        explicitly surfaces (never silently drops) any row that looked
        like an entrant but had no extractable `playerCode`
        (`EntryListParseResult.unparsed_row_count` /
        `.unparsed_samples`).
      - `src/klpga/config.py` — `ENTRY_LIST_ENDPOINT`.
      - `src/klpga/collectors/entry_list.py` — `fetch_entry_list()`
        (uses the existing rate-limited/disk-cached `PoliteHttpClient`),
        `match_entries_to_player_master()` (matches by `player_code` ==
        `player_master.player_id` only, never by name; reports matched
        and unmatched counts explicitly, never discards silently;
        detects duplicate `player_code`s), `cross_check_against_
        player_event()` (compares an entry list's player_code set
        against an already-collected completed tournament's
        `player_event.player_id` set for the same `game_code` —
        reports the set difference without treating a mismatch as an
        error, per the explicit "do not assume the two lists must be
        identical" instruction).
      - `scripts/14_inspect_entry_list.py` — read-only Windows
        diagnostic (`--game-code`, optional `--db` opened
        read-only). Prints: gameCode, the page's own summary counts,
        parsed entrant total (cross-checked against 총 참가자, mismatch
        flagged not hidden), unparseable-row count/samples, duplicate
        `player_code`s, matched/unmatched vs. `player_master` when
        `--db` is given, and 10 sample entrants. Makes no DB writes.
      - Tests: `tests/test_entry_list_parser.py` (12 tests, against the
        real fixture), `tests/test_entry_list_collector.py` (5 tests,
        fake client + real `schema.sql`-built temp DB),
        `tests/test_inspect_entry_list.py` (3 tests, script report
        logic against the real fixture). Full suite: 106/106 passing
        as of this checkpoint.
- [x] **STEP 4's live-field run — DONE, 2026-08-25, on the Windows PC.
      CONFIRMED PRODUCTION RESULT for gameCode=2026080001:**
      - Page summary total entrants: 120
      - Parsed entrant rows: 120
      - `qualification_category`: 자격자=115, 추천자=5, 초청자=0
      - Unparseable entrant rows: 0
      - Duplicate `player_code`s: 0
      - Matched against existing `player_master`: 119
      - Unmatched: 1 — `player_code=13355`, name="배윤철 0908(A)"
        (99.17% match rate)

      **`player_code=13355` is treated as a legitimate unmatched/new
      entrant** (per explicit instruction) — never fuzzy-matched by
      name, never dropped. This is now a real (not hypothetical) test
      case for a future rookie/unknown-player fallback, and is exactly
      why `tournament_entry` below has no FK to `player_master`.
- [x] **`tournament_entry` storage layer — IMPLEMENTED, 2026-08-25**
      (revised from the original STEP 5 sketch — `entry_status` dropped,
      no confirmed source; see above):
      ```sql
      CREATE TABLE IF NOT EXISTS tournament_entry (
          game_code               TEXT NOT NULL,   -- joins tournament_master.game_code (not FK:
                                                     -- an upcoming tournament may have no
                                                     -- tournament_master row yet)
          player_code              TEXT NOT NULL,   -- confirmed real KLPGA playerCode; same identity
                                                     -- space as player_master.player_id, but NOT an FK
                                                     -- (a legitimate entrant may be unmatched — see
                                                     -- player_code=13355 above)
          player_name_display      TEXT NOT NULL,   -- display only, never used for matching
          nationality               TEXT,            -- confirmed from the tb-flag country code
          qualification_category    TEXT,            -- confirmed: 자격자 / 추천자 / 초청자
          qualification_reason      TEXT,            -- confirmed free-text "참가 자격" column
          source                    TEXT NOT NULL,   -- confirmed endpoint this row came from
          collected_at              TEXT NOT NULL,
          PRIMARY KEY (game_code, player_code)
      )
      ```
      - `src/klpga/db/schema.sql` section 6 (collection_runs renumbered
        to section 7). No `entry_status`/WD/DNS/SG/GIR/course-par or any
        other unconfirmed field — guarded by a dedicated test
        (`test_upsert_never_writes_an_entry_status_or_other_unconfirmed_column`).
      - `src/klpga/db/migrate.py` — `ensure_tournament_entry_schema()`:
        purely additive (the table is brand new, so unlike the
        `player_stats_snapshot` migration there is never an existing
        row to migrate or a drop-and-recreate decision) — creates the
        table on an already-populated production DB without touching
        `tournament_master`/`player_master`/`player_event`/
        `player_round`, confirmed by a dedicated regression test.
      - `src/klpga/db/upsert.py` — `upsert_tournament_entry()`: UPSERT
        keyed on `(game_code, player_code)`. Re-running collection for
        the same gameCode overwrites each row in place — confirmed
        idempotent by tests (3x re-collection of all 120 real entrants
        -> still 120 rows, not 360).
      - `src/klpga/collectors/entry_list.py` —
        `build_tournament_entry_rows()`: pure row-shaping (no DB
        access), only the genuinely confirmed fields.
      - `scripts/15_collect_entry_list.py` — the live collection
        command: fetch -> parse -> `ensure_tournament_entry_schema` ->
        UPSERT -> `collection_runs` audit log entry -> explicit
        matched/unmatched report against `player_master` (unmatched
        entrants are stored, never dropped). Never writes to
        `tournament_master`/`player_master`/`player_event`/
        `player_round` — confirmed by a dedicated regression test.
      - Tests: `tests/test_tournament_entry.py` (10 tests — migration
        safety, upsert idempotency, the unmatched-rookie-entrant case,
        pure row-shaping), `tests/test_collect_entry_list.py` (6
        tests — full collection against the real 120-row fixture,
        matched/unmatched reporting, idempotent re-collection,
        untouched validated tables, `collection_runs` audit log). Full
        suite: 122/122 passing.

**Earlier investigation history (superseded by the confirmation above,
kept for the record):** a full repo search (2026-08-25) found nothing
about an entry/participant roster anywhere in this codebase before this
investigation started. A live fetch attempt from this dev sandbox was
confirmed blocked at the proxy policy level (`curl` -> `CONNECT tunnel
failed, response 403`; `WebFetch` -> `EGRESS_BLOCKED`; the proxy's own
status endpoint showed `"gateway answered 403 to CONNECT (policy denial
or upstream failure)"` for both `klpga.co.kr:443` and
`www.klpga.co.kr:443`) — consistent with every other endpoint in this
project, all of which were confirmed from the user's Windows PC or, in
this case, a manual browser capture the user reported and then pasted in
full. `scripts/13_discover_entry_list.py` (read-only link-discovery
crawl, broadened entry/roster keyword list) was built as the automatable
half of the investigation and remains in the repo, though it was
superseded once the endpoint was confirmed directly.

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
7. ~~Re-run the full 100-tournament collection with the `gameMethod`
   fix~~ — **DONE and CONFIRMED, 2026-08-25.** Windows production DB:
   100 distinct tournaments, 0 excluded special-format gameCodes
   remaining, 0 zero-player tournaments, `03_validate.py --target 100`
   -> `VALIDATION PASSED`. `tournament_master` 100, `player_master`
   546, `player_event` 11,850, `player_round` 33,215, CSV export
   45,711 total rows. **This is now the validated raw-data checkpoint —
   do not modify or recollect it unless a genuine data-integrity bug is
   found.** See section 6 above.
8. Use that run's output to fill in the remaining `[ ]` items above
   (other tourType codes, non-F gameFinish values, exact duplicate-row
   markup, what `data-inghole` actually means, `par`/`course_yards`/
   `field_size`, per-player prize money, `official_url` pattern, and
   whether some OTHER endpoint — e.g. a default full-leaderboard view
   without a `round` param — distinguishes WD from DQ where this one
   doesn't). Not yet done — still open.
9. Update this file's checkboxes based on what's actually observed —
   never mark something done from inference alone.
10. ~~`player_stats_snapshot` (data.klpga.co.kr) collection~~ —
    **partially superseded, 2026-08-25**: the OFFICIAL Data Center
    columns in this table are still fully unpopulated (that endpoint is
    still unreached — nothing changed there), but the table itself now
    also carries a second, DERIVED set of columns computed from the
    validated tournament dataset. See section 6 above for exactly what
    was built and why the two are kept clearly separate.
11. **Current goal: design the win-probability model** using the
    `derived_*` feature set built in section 6, once that feature set
    has been reviewed. Deliberately not started yet — see section 6's
    "Not yet decided or built" note.
