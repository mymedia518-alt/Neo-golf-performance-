CREATE TABLE IF NOT EXISTS klpga_shot_raw_manifest (
  source_id TEXT PRIMARY KEY,
  game_code TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  player_code TEXT,
  group_no TEXT,
  round INTEGER NOT NULL,
  hole INTEGER NOT NULL,
  collected_at TEXT NOT NULL,
  http_status INTEGER,
  sha256 TEXT NOT NULL,
  raw_path TEXT NOT NULL,
  UNIQUE(game_code, endpoint, player_code, group_no, round, hole, sha256)
);

CREATE TABLE IF NOT EXISTS klpga_player_shot (
  game_code TEXT NOT NULL,
  player_code TEXT NOT NULL,
  player_name TEXT,
  round INTEGER NOT NULL,
  hole INTEGER NOT NULL,
  shot INTEGER NOT NULL,
  state_code TEXT,
  state_name_ko TEXT,
  state_name_en TEXT,
  distance REAL,
  distance_len REAL,
  altitude REAL,
  x REAL,
  y REAL,
  green_x REAL,
  green_y REAL,
  shot_video_yn TEXT,
  source_id TEXT NOT NULL,
  raw_json TEXT NOT NULL,
  PRIMARY KEY(game_code, player_code, round, hole, shot),
  FOREIGN KEY(source_id) REFERENCES klpga_shot_raw_manifest(source_id)
);

CREATE INDEX IF NOT EXISTS idx_klpga_player_shot_event
ON klpga_player_shot(game_code, round, hole);
CREATE INDEX IF NOT EXISTS idx_klpga_player_shot_player
ON klpga_player_shot(game_code, player_code, round);
