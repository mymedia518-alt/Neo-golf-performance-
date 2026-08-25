-- KLPGA Historical Database schema
-- Booleans are stored as INTEGER 0/1 (SQLite has no native BOOLEAN).
-- All dates are ISO-8601 TEXT ('YYYY-MM-DD').

PRAGMA foreign_keys = ON;

-- ============================================================
-- 1. tournament_master — exactly 100 most-recently-completed
--    KLPGA regular tour events, most recent first.
-- ============================================================
CREATE TABLE IF NOT EXISTS tournament_master (
    event_id            TEXT PRIMARY KEY,
    game_code           TEXT NOT NULL UNIQUE,
    event_name          TEXT NOT NULL,
    season              INTEGER NOT NULL,
    -- Nullable: no confirmed getGameList field for the tournament start
    -- date has been observed yet (only endDate) — not fabricated.
    -- See docs/SITE_STRUCTURE_TODO.md.
    start_date          TEXT,
    end_date            TEXT NOT NULL,
    course_name         TEXT,
    course_location     TEXT,
    par                 INTEGER,
    course_yards        INTEGER,
    rounds_scheduled    INTEGER,
    rounds_completed    INTEGER,
    field_size          INTEGER,
    winner              TEXT,
    winner_score        TEXT,
    -- Nullable: the tournament detail-page URL pattern has not been
    -- confirmed against a live response yet (see
    -- docs/SITE_STRUCTURE_TODO.md), so it is not fabricated.
    official_url        TEXT
);

-- ============================================================
-- 2. player_master — one row per official KLPGA player_id.
-- ============================================================
CREATE TABLE IF NOT EXISTS player_master (
    player_id           TEXT PRIMARY KEY,
    player_name         TEXT NOT NULL,
    birth_year          INTEGER,
    nationality         TEXT,
    team_or_sponsor     TEXT,
    official_player_url TEXT
);

-- ============================================================
-- 3. player_event — one row per (player, event).
-- ============================================================
CREATE TABLE IF NOT EXISTS player_event (
    event_id                TEXT NOT NULL REFERENCES tournament_master(event_id),
    game_code               TEXT NOT NULL,
    season                  INTEGER NOT NULL,
    player_id               TEXT NOT NULL REFERENCES player_master(player_id),
    player_name             TEXT NOT NULL,

    finish_position         TEXT,      -- e.g. 'T3', '1', 'CUT'
    finish_position_numeric INTEGER,   -- 3 for 'T3', NULL if not applicable
    tie_flag                INTEGER NOT NULL DEFAULT 0,

    made_cut                INTEGER NOT NULL DEFAULT 0,
    withdrawn               INTEGER NOT NULL DEFAULT 0,
    disqualified            INTEGER NOT NULL DEFAULT 0,

    rounds_played           INTEGER,

    r1_score                INTEGER,
    r2_score                INTEGER,
    r3_score                INTEGER,
    r4_score                INTEGER,

    total_score             INTEGER,
    score_to_par             INTEGER,

    prize_money             INTEGER,   -- KRW

    avg_score_event         REAL,

    official_url            TEXT,

    PRIMARY KEY (event_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_player_event_player ON player_event(player_id);
CREATE INDEX IF NOT EXISTS idx_player_event_event ON player_event(event_id);

-- ============================================================
-- 4. player_round — one row per (player, event, round_number).
-- ============================================================
CREATE TABLE IF NOT EXISTS player_round (
    event_id                    TEXT NOT NULL REFERENCES tournament_master(event_id),
    game_code                   TEXT NOT NULL,
    season                      INTEGER NOT NULL,
    round_number                INTEGER NOT NULL,

    player_id                   TEXT NOT NULL REFERENCES player_master(player_id),
    player_name                 TEXT NOT NULL,

    round_score                 INTEGER,
    round_to_par                INTEGER,
    finish_position_after_round TEXT,

    course_name                 TEXT,
    course_par                  INTEGER,

    front9_score                INTEGER,
    back9_score                 INTEGER,
    birdies                     INTEGER,
    eagles                      INTEGER,
    pars                        INTEGER,
    bogeys                      INTEGER,
    double_bogey_plus           INTEGER,

    official_url                TEXT,

    PRIMARY KEY (event_id, player_id, round_number)
);

CREATE INDEX IF NOT EXISTS idx_player_round_player ON player_round(player_id);
CREATE INDEX IF NOT EXISTS idx_player_round_event ON player_round(event_id);

-- ============================================================
-- 5. player_stats_snapshot — two DIFFERENT kinds of row, clearly
--    separated by column group below:
--
--    (a) OFFICIAL KLPGA Data Center performance statistics
--        (data.klpga.co.kr), captured AS OF a point in time to avoid
--        look-ahead bias when attached to a past event. Only columns
--        the official site actually publishes are filled; everything
--        else stays NULL. Nothing in this group is estimated/derived.
--        This host has never been reached from any environment this
--        project has run in — every column in this group is still
--        NULL in every row as of 2026-08-25 (see
--        docs/SITE_STRUCTURE_TODO.md section 3).
--
--    (b) DERIVED aggregates (`derived_*` columns, snapshot_type=
--        'derived_trailing100' only) computed by
--        src/klpga/analytics/player_stats.py straight from this
--        project's own validated tournament_master / player_event /
--        player_round dataset — NOT official KLPGA statistics, and
--        NOT a substitute for the official columns in (a). See that
--        module's docstring for the exact formula/provenance of each
--        one. True Strokes Gained and GIR are NOT derivable from this
--        dataset (no shot-level distance-to-hole/lie/hole-by-hole
--        green data was ever collected or is even collectible via the
--        confirmed roundLeaderboard endpoint) and deliberately have NO
--        derived_* equivalent — see docs/SITE_STRUCTURE_TODO.md
--        section 6. Never read a `derived_*` column as if it were
--        group (a)'s official equivalent, or vice versa.
--
--    snapshot_type:
--      'pre_event'          -> official stats as published immediately
--                               before related_event_id started
--                               (preferred, group (a) only).
--      'season_to_date'     -> official stats as of a mid-season
--                               snapshot date, group (a) only.
--      'season_final'       -> official season-end final stats (only
--                               ever used for events AFTER that season
--                               ended), group (a) only.
--      'derived_trailing100' -> this pipeline's own aggregate over the
--                               full validated tournament dataset as
--                               of `as_of_date`, group (b) only.
--                               related_event_id is always NULL for
--                               this type (not tied to one event) — a
--                               full recompute (DELETE + re-INSERT),
--                               not an incremental upsert; see
--                               scripts/09_build_player_stats_snapshot.py.
-- ============================================================
CREATE TABLE IF NOT EXISTS player_stats_snapshot (
    snapshot_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id             TEXT NOT NULL REFERENCES player_master(player_id),
    season                INTEGER NOT NULL,
    as_of_date            TEXT NOT NULL,
    snapshot_type         TEXT NOT NULL CHECK (snapshot_type IN ('pre_event', 'season_to_date', 'season_final', 'derived_trailing100')),
    related_event_id      TEXT REFERENCES tournament_master(event_id),

    -- ---------------- group (a): OFFICIAL Data Center columns -------
    scoring_average        REAL,
    scoring_average_rank   INTEGER,

    sg_total               REAL,
    sg_total_rank          INTEGER,
    sg_off_the_tee         REAL,
    sg_off_the_tee_rank    INTEGER,
    sg_approach            REAL,
    sg_approach_rank       INTEGER,
    sg_around_green        REAL,
    sg_around_green_rank   INTEGER,
    sg_putting             REAL,
    sg_putting_rank        INTEGER,

    gir                    REAL,
    gir_rank               INTEGER,

    driving_distance       REAL,
    driving_distance_rank  INTEGER,

    driving_accuracy       REAL,
    driving_accuracy_rank  INTEGER,

    putting_average        REAL,
    putting_average_rank   INTEGER,

    sixties_rate           REAL,
    sixties_rate_rank      INTEGER,

    top10_rate             REAL,
    top10_rate_rank        INTEGER,

    birdie_average         REAL,
    birdie_average_rank    INTEGER,

    par_breakers           REAL,
    par_breakers_rank      INTEGER,

    sand_save              REAL,
    sand_save_rank         INTEGER,

    scrambling             REAL,
    scrambling_rank        INTEGER,

    official_url           TEXT,

    -- ---------------- group (b): DERIVED columns ---------------------
    -- (this project's own aggregates — see module docstring above)
    --
    -- Naming convention, added 2026-08-25 after a red-team check found
    -- `derived_avg_score_to_par` (the old name) was ambiguous — it is
    -- a TOURNAMENT-TOTAL score-to-par average, not a per-round figure,
    -- and the old name didn't say so. Every column below now says
    -- `_event_` or `_round_` explicitly so a tournament-total metric
    -- can never be mistaken for a per-round one just from its name:
    --   `_round_*`  -> computed from real per-round data
    --                  (player_round.round_score), or a rate expressed
    --                  per round (sum of event totals / sum of rounds).
    --   `_event_*`  -> computed from per-EVENT totals
    --                  (player_event.score_to_par, the tournament-
    --                  cumulative `data-totunderpar` figure), averaged
    --                  one-event-one-vote — NOT scaled by how many
    --                  rounds each event represents.
    -- See src/klpga/analytics/player_stats.py's docstring for the full
    -- formula/provenance of each, and docs/SITE_STRUCTURE_TODO.md
    -- section 6 for the red-team writeup and mathematical verification
    -- of derived_avg_round_score_to_par against raw round_to_par data.
    derived_tournaments_played          INTEGER,
    derived_rounds_played                INTEGER,
    derived_made_cuts                    INTEGER,
    derived_cut_rate                     REAL,
    derived_wins                         INTEGER,
    derived_top5                         INTEGER,
    derived_top10                        INTEGER,
    derived_best_finish                  INTEGER,
    derived_avg_round_score              REAL,
    derived_round_scoring_stddev         REAL,
    derived_avg_event_score_to_par       REAL,
    derived_avg_event_score_to_par_n     INTEGER,
    derived_avg_round_score_to_par       REAL,
    derived_avg_round_score_to_par_n     INTEGER,
    derived_recent_event_form_5          REAL,
    derived_recent_event_form_5_n        INTEGER,
    derived_recent_event_form_10         REAL,
    derived_recent_event_form_10_n       INTEGER,
    derived_recent_event_form_20         REAL,
    derived_recent_event_form_20_n       INTEGER,
    derived_weighted_recent_event_form   REAL,
    derived_weighted_recent_event_form_n INTEGER,

    collected_at            TEXT NOT NULL,

    UNIQUE (player_id, season, as_of_date, snapshot_type, related_event_id)
);

CREATE INDEX IF NOT EXISTS idx_stats_snapshot_player ON player_stats_snapshot(player_id);
CREATE INDEX IF NOT EXISTS idx_stats_snapshot_event ON player_stats_snapshot(related_event_id);

-- ============================================================
-- 6. tournament_entry — one row per (game_code, player_code) confirmed
--    entrant on the live entry-list page (GET
--    /web/tourInfo/entry?gameCode=<code> — see
--    klpga.parsers.entry_list_parser / klpga.collectors.entry_list and
--    docs/SITE_STRUCTURE_TODO.md section 7 for the full confirmation
--    log). This is entry-list data (who is IN THE FIELD, confirmed live
--    2026-08-25 against gameCode=2026080001: 120/120 rows parsed, 0
--    unparseable, 0 duplicate player_codes) — NOT tournament RESULT
--    data (that stays in player_event/player_round) and NOT tied to
--    tournament_master.event_id, since an upcoming tournament may not
--    have played rounds yet.
--
--    No FK to player_master: a real, live-confirmed entrant can be a
--    rookie/unknown player not yet in player_master (confirmed
--    2026-08-25: player_code=13355, 배윤철, unmatched against the
--    existing 119/120-matched player_master — this row must still be
--    stored, never dropped, and is a real test case for a future
--    rookie/unknown-player fallback). Only genuinely confirmed fields
--    are stored — no entry_status/WD/DNS marker exists on this page
--    (investigated, not found; see section 7), and no
--    course/statistics field is invented here either.
-- ============================================================
CREATE TABLE IF NOT EXISTS tournament_entry (
    game_code               TEXT NOT NULL,   -- joins tournament_master.game_code (not enforced as FK:
                                              -- an upcoming tournament may not have a tournament_master
                                              -- row yet)
    player_code              TEXT NOT NULL,   -- confirmed real KLPGA playerCode; same identity space as
                                              -- player_master.player_id, but NOT enforced as an FK here
                                              -- (a legitimate entrant may not exist in player_master yet)
    player_name_display      TEXT NOT NULL,   -- display only, never used for matching
    nationality               TEXT,            -- confirmed from the tb-flag country code, e.g. 'KOR'
    qualification_category    TEXT,            -- confirmed: 자격자 / 추천자 / 초청자
    qualification_reason      TEXT,            -- confirmed free-text "참가 자격" column, NULL if empty
    source                    TEXT NOT NULL,   -- which confirmed endpoint/page this row came from
    collected_at              TEXT NOT NULL,   -- ISO-8601 UTC timestamp of this collection run

    PRIMARY KEY (game_code, player_code)
);

CREATE INDEX IF NOT EXISTS idx_tournament_entry_game ON tournament_entry(game_code);
CREATE INDEX IF NOT EXISTS idx_tournament_entry_player ON tournament_entry(player_code);

-- ============================================================
-- 7. collection_runs — audit log of each collection script
--    invocation, so re-runs/resumes and failures are traceable.
-- ============================================================
CREATE TABLE IF NOT EXISTS collection_runs (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    script_name   TEXT NOT NULL,
    target        TEXT,              -- e.g. a season or gameCode being collected
    started_at    TEXT NOT NULL,     -- ISO-8601 UTC timestamp
    finished_at   TEXT,
    status        TEXT NOT NULL CHECK (status IN ('running', 'success', 'error', 'blocked')),
    rows_written  INTEGER,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_collection_runs_script ON collection_runs(script_name);
