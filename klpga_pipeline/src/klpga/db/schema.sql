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
    start_date          TEXT NOT NULL,
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
    official_url        TEXT NOT NULL
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
-- 5. player_stats_snapshot — official KLPGA Data Center
--    performance statistics, captured AS OF a point in time to
--    avoid look-ahead bias when attached to a past event.
--
--    snapshot_type:
--      'pre_event'      -> stats as published immediately before
--                           related_event_id started (preferred).
--      'season_to_date' -> stats as of a mid-season snapshot date
--                           when a pre_event snapshot isn't available.
--      'season_final'   -> season-end final stats (only ever used
--                           for events AFTER that season ended —
--                           never attached to a prior event).
--
--    Only columns the official site actually publishes are filled;
--    everything else stays NULL. Nothing here is estimated/derived.
-- ============================================================
CREATE TABLE IF NOT EXISTS player_stats_snapshot (
    snapshot_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id             TEXT NOT NULL REFERENCES player_master(player_id),
    season                INTEGER NOT NULL,
    as_of_date            TEXT NOT NULL,
    snapshot_type         TEXT NOT NULL CHECK (snapshot_type IN ('pre_event', 'season_to_date', 'season_final')),
    related_event_id      TEXT REFERENCES tournament_master(event_id),

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
    collected_at            TEXT NOT NULL,

    UNIQUE (player_id, season, as_of_date, snapshot_type, related_event_id)
);

CREATE INDEX IF NOT EXISTS idx_stats_snapshot_player ON player_stats_snapshot(player_id);
CREATE INDEX IF NOT EXISTS idx_stats_snapshot_event ON player_stats_snapshot(related_event_id);
