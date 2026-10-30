-- Player-season extension tables for the KLPGA Shot Tracker player endpoint.
-- Additive only: schema.sql (klpga_shot_raw_manifest, klpga_player_shot) is
-- loaded first and is NOT modified. These tables hold the two non-shot parts
-- of every getShotTracker response (holeInfo, baseHoleInfo) and the official
-- per-round score used for reconciliation.

CREATE TABLE IF NOT EXISTS klpga_hole_info (
  game_code TEXT NOT NULL,
  round INTEGER NOT NULL,
  hole INTEGER NOT NULL,
  player_code TEXT NOT NULL,          -- the player whose request returned this block
  true_hole TEXT,                     -- baseHoleInfo.bi_trueHole (raw string)
  par INTEGER,                        -- holeInfo.stdScore
  yds REAL,                           -- holeInfo.yds  (unit as labelled by the field name)
  meter REAL,                         -- holeInfo.meter
  field_avg_score REAL,               -- holeInfo.avgScore
  difficulty_rank INTEGER,            -- holeInfo.rank
  holeinfo_count INTEGER,             -- holeInfo.count (meaning not confirmed; preserved)
  bi_sx REAL, bi_sy REAL,             -- baseHoleInfo UI fields: separate coordinate
  bi_gx REAL, bi_gy REAL,             -- system from pp_x/pp_y (see PLAYER_SEASON_ARCHIVE.md);
  bi_gpx REAL, bi_gpy REAL,           -- preserved, NOT interpreted
  source_id TEXT NOT NULL,
  hole_info_json TEXT NOT NULL,
  base_hole_info_json TEXT NOT NULL,
  PRIMARY KEY(game_code, round, hole, player_code),
  FOREIGN KEY(source_id) REFERENCES klpga_shot_raw_manifest(source_id)
);

CREATE TABLE IF NOT EXISTS klpga_player_round_official (
  season TEXT NOT NULL,
  game_code TEXT NOT NULL,
  player_code TEXT NOT NULL,
  round INTEGER NOT NULL,
  official_value TEXT,                -- reGameList.roundNScore exactly as published
  game_type TEXT,                     -- reGameList.gameType ("0" stroke play in this data; "2" = HJ match play)
  shot_rows INTEGER,                  -- rows in klpga_player_shot for this round
  comparison_status TEXT NOT NULL,    -- MATCH / MISMATCH / NOT_COMPARABLE_NON_STROKE_FORMAT / NO_SHOT_DATA
  PRIMARY KEY(season, game_code, player_code, round)
);

CREATE INDEX IF NOT EXISTS idx_klpga_hole_info_event ON klpga_hole_info(game_code, round, hole);
