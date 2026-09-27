"""PLAYER OBSERVATION WAREHOUSE V1 -- playerCode=10097 (김민선7) ONLY.

Not a summary warehouse. The OBSERVATION LAYER (Layer 0-1: `observation_
hole`, `observation_shot`, `observation_round`) is the whole reason this
database exists -- every row in those three tables is one real,
independently-identifiable measurable event (one hole played, one shot
played, one round played). No column in any of the three is an average,
a percentage, or a cross-event summary -- a round's own `total_strokes`
is that round's own scorecard total (18 numbers added once, the same
arithmetic a human marker does, not a statistic over many rounds), and
a round's own `sg_total` is that one round's own reported Strokes
Gained figure, not something averaged across rounds by this script.

Every layer ABOVE the Observation Layer is COMPUTED via real SQL
aggregation over the layer directly below it -- never hand-copied from
a pre-aggregated source. If a fact cannot be reproduced from a lower
layer (because no lower-layer data exists for it), it is stored at its
own layer and explicitly marked as layer-anchored, never disguised as
an aggregate.

Layer 0  OBSERVATION  `observation_hole` / `observation_shot` -- one row
                       = one hole played / one shot played. The finest
                       grain this repository has ever captured.
Layer 1  OBSERVATION  `observation_round` -- one row = one round played.
                       Computed (SQL SUM of strokes) from `observation_
                       hole` wherever hole-level rows exist for that
                       round; otherwise sourced directly (no finer grain
                       reachable) and marked grain='DIRECT_NO_LOWER_LAYER'.
                       Still an observation, not a summary: a round
                       total is one event's own final number, not a
                       statistic over multiple rounds.
Layer 2  TOURNAMENT   one row = one tournament -- SG/strokes columns are
                       SQL-aggregated from Layer 1 (AVG/SUM ... GROUP BY
                       game_code); rank/tournament_name/win/top10 are
                       native Layer-2 facts (no lower layer can produce
                       a finish rank), stored alongside and never
                       confused with the aggregated columns
Layer 3  SEASON       one row = one season -- SQL-aggregated from Layer 2
Layer 4  CAREER       one row = the whole career -- SQL-aggregated from
                       Layer 3

This script proves reproducibility rather than asserting it: after
building Layer 2 from Layer 1, it cross-checks the aggregated SG Total
against reconcile_10097_player_history.py's own independently-reported
tournament sg_total (itself sourced from the SG Warehouse, a category-1
source never touched by this script's Layer 1 build) and records the
real match/mismatch count -- not a hardcoded claim.
"""
from __future__ import annotations

import datetime
import importlib.util
import re
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

CONTENT = ROOT / "content" / "website_v2"
PI_DIR = CONTENT / "knowledge_engine" / "player_intelligence" / "10097"
OUT_DIR = CONTENT / "knowledge_engine" / "player_data_warehouse" / "10097"
OUT_PATH = OUT_DIR / "PLAYER_DATA_WAREHOUSE_V1.sqlite"

PLAYER_ID = "10097"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _source_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        return "unknown"


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


SCHEMA = """
CREATE TABLE meta(
    player_id TEXT PRIMARY KEY, player_name TEXT, generated_at TEXT,
    source_commit TEXT, schema_version TEXT
);

-- LAYER 0 -- OBSERVATION (hole/shot). One row = one real observation at the finest grain
-- this repository has ever captured.
CREATE TABLE observation_hole(
    game_code TEXT, round_number INTEGER, hole INTEGER,
    course TEXT, par INTEGER, strokes INTEGER, relative_to_par INTEGER,
    layer INTEGER DEFAULT 0, grain TEXT DEFAULT 'DIRECT_MEASUREMENT',
    PRIMARY KEY(game_code, round_number, hole)
);

CREATE TABLE observation_shot(
    game_code TEXT, round_number INTEGER, hole INTEGER, shot_no INTEGER,
    distance_yd REAL, club TEXT, start_lie TEXT, end_lie TEXT,
    pin_distance_yd REAL, result TEXT, sg REAL,
    layer INTEGER DEFAULT 0, grain TEXT DEFAULT 'DIRECT_MEASUREMENT',
    PRIMARY KEY(game_code, round_number, hole, shot_no)
);

-- LAYER 1 -- OBSERVATION (round). One row = one round actually played.
CREATE TABLE observation_round(
    game_code TEXT, season INTEGER, round_number INTEGER, status TEXT,
    sg_total REAL, total_strokes INTEGER,
    layer INTEGER DEFAULT 1, grain TEXT, source TEXT,
    PRIMARY KEY(game_code, round_number)
);

-- LAYER 2 -- TOURNAMENT. sg_total_computed/total_strokes_computed/
-- rounds_aggregated are SQL-aggregated from observation_round. rank/
-- tournament_name/is_win/is_top10 are native Layer-2 facts (a finish
-- rank cannot be derived from round-level data) and are never confused
-- with the computed columns.
CREATE TABLE tournament_observation(
    game_code TEXT PRIMARY KEY, season INTEGER, tournament_name TEXT,
    status TEXT, finish_rank INTEGER, is_win INTEGER, is_top10 INTEGER,
    sg_total_computed REAL, total_strokes_computed INTEGER,
    rounds_aggregated INTEGER,
    layer INTEGER DEFAULT 2, grain TEXT, anchored_source TEXT
);

-- LAYER 3 -- SEASON. Every column SQL-aggregated from
-- tournament_observation (status='FINISHED' only).
CREATE TABLE season_observation(
    season INTEGER PRIMARY KEY,
    events INTEGER, wins INTEGER, top5 INTEGER, top10 INTEGER, top20 INTEGER,
    sg_total_computed REAL, rounds_aggregated INTEGER,
    layer INTEGER DEFAULT 3, grain TEXT DEFAULT 'COMPUTED_FROM_LAYER2'
);

-- LAYER 4 -- CAREER. Aggregated from season_observation.
CREATE TABLE career_observation(
    player_id TEXT PRIMARY KEY,
    events INTEGER, wins INTEGER, top5 INTEGER, top10 INTEGER, top20 INTEGER,
    seasons_aggregated INTEGER,
    layer INTEGER DEFAULT 4, grain TEXT DEFAULT 'COMPUTED_FROM_LAYER3'
);

-- Reproducibility proof: Layer 2's SQL-computed sg_total vs. the
-- independently-sourced tournament sg_total already reported by
-- reconcile_10097_player_history.py (an SG-Warehouse-category-1 fact,
-- never touched when building observation_round from round_rows in
-- the first place -- so this is a real, non-circular cross-check).
CREATE TABLE layer_reproducibility_check(
    game_code TEXT PRIMARY KEY,
    layer1_aggregated_sg_total REAL, layer2_reference_sg_total REAL,
    delta REAL, within_tolerance INTEGER
);

-- Independent, non-round-up categorical facts. Not part of the
-- Round -> Tournament -> Season -> Career reproducibility chain above
-- (they describe technical/skill readings, not scoring aggregates) --
-- kept as flat MEASURED/DERIVED atomic rows, never season-averaged by
-- this script.
CREATE TABLE player_profile(
    player_id TEXT PRIMARY KEY, official_name TEXT, english_name TEXT,
    current_ranking INTEGER, k_ranking INTEGER, k_ranking_asof TEXT
);

CREATE TABLE technical_reading(
    season INTEGER, category TEXT, metric_label TEXT,
    value REAL, unit TEXT, rank INTEGER,
    numerator REAL, denominator REAL, measured_rounds INTEGER,
    PRIMARY KEY(season, metric_label)
);

CREATE TABLE field_verification(
    table_name TEXT, field_note TEXT, status TEXT,
    source TEXT, repo_path TEXT, sample_size INTEGER,
    verification_date TEXT, confidence TEXT
);
"""

M, D, NC, BL = "MEASURED", "DERIVED", "NOT_COLLECTED", "BLOCKED"


def _verify(cur, table, field_note, status, *, source=None, repo_path=None, sample_size=None, confidence=None):
    cur.execute(
        "INSERT INTO field_verification VALUES (?,?,?,?,?,?,?,?)",
        (table, field_note, status, source, repo_path, sample_size, _utcnow(), confidence),
    )


def build() -> Path:
    build_mod = _load_module("build_10097_player_history", ROOT / "scripts" / "build_10097_player_history.py")
    recon_mod = _load_module("reconcile_10097_player_history", ROOT / "scripts" / "reconcile_10097_player_history.py")

    doc = build_mod.build()
    recon = recon_mod.reconcile()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUT_PATH.exists():
        OUT_PATH.unlink()
    conn = sqlite3.connect(OUT_PATH)
    conn.executescript(SCHEMA)
    cur = conn.cursor()

    cur.execute("INSERT INTO meta VALUES (?,?,?,?,?)",
                (PLAYER_ID, doc["player_name"], _utcnow(), _source_git_sha(), "player_data_warehouse_v1"))

    # ===================================================================
    # LAYER 0 -- OBSERVATION (hole/shot)
    # ===================================================================
    hh = doc.get("hole_history")
    if hh:
        for rnd in hh["rounds"]:
            for h in rnd["holes"]:
                cur.execute(
                    "INSERT INTO observation_hole(game_code, round_number, hole, course, par, strokes, relative_to_par) VALUES (?,?,?,?,?,?,?)",
                    (hh["game_code"], rnd["round"], h["hole"], hh["course"], h["par"], h["strokes"], h["relative_to_par"]),
                )
    n_holes = cur.execute("SELECT COUNT(*) FROM observation_hole").fetchone()[0]
    _verify(cur, "observation_hole", "par/strokes/relative_to_par (Layer 0)", M if n_holes else NC,
            source="OK Open (2026120001) real captured scorecard" if n_holes else None,
            repo_path=str(PI_DIR / "PLAYER_HISTORY.json"), sample_size=n_holes,
            confidence="HIGH" if n_holes else None)
    _verify(cur, "observation_shot", "all columns (Layer 0)", BL, source=None,
            repo_path="klpga.collectors.cmpro_shots (branch feat/cmpro-shot-data-v0) + /ajax/leaderboard/getShotTracker (undiscovered endpoint, both unreachable from this sandbox)",
            sample_size=0, confidence=None)

    # ===================================================================
    # LAYER 1 -- OBSERVATION (round)
    # ===================================================================
    # 1a. Rounds WITH Layer-0 hole data: total_strokes computed by real
    # SQL aggregation over observation_hole, never hand-summed in Python.
    cur.execute("""
        INSERT INTO observation_round(game_code, season, round_number, status, sg_total, total_strokes, grain, source)
        SELECT game_code, 2026, round_number,
               CASE WHEN round_number < (SELECT MAX(round_number) FROM observation_hole r2 WHERE r2.game_code = observation_hole.game_code)
                    THEN 'FINISHED' ELSE 'IN_PROGRESS_PARTIAL' END,
               NULL, SUM(strokes), 'COMPUTED_FROM_LAYER0', 'SQL SUM(strokes) over observation_hole'
        FROM observation_hole
        GROUP BY game_code, round_number
    """)
    # Real partial-round SG for OK Open R3 exists as an independently
    # captured live snapshot (not derivable from hole strokes alone) --
    # merged onto the Layer-0-derived row, never silently invented.
    ip = doc.get("current_tournament_in_progress")
    if ip and ip.get("partial_round_sg"):
        cur.execute(
            "UPDATE observation_round SET sg_total=?, source = source || ' + OK_OPEN_2026_R3_LIVE_SNAPSHOT.json (partial round SG)' WHERE game_code=? AND round_number=?",
            (ip["partial_round_sg"]["total"], ip["game_code"], ip["partial_round_sg"]["round"]),
        )

    # 1b. Rounds with NO Layer-0 data: sourced directly at Layer 1 (SG
    # per round from the SG Warehouse's own round_rows -- category-1
    # source, no hole breakdown ever captured for these).
    for r in recon["round_rows"]:
        cur.execute(
            "INSERT OR IGNORE INTO observation_round(game_code, season, round_number, status, sg_total, total_strokes, grain, source) VALUES (?,?,?,?,?,?,?,?)",
            (r["game_code"], r["season"], r["round"], "FINISHED", r["sg_total"], None,
             "DIRECT_NO_LOWER_LAYER", r.get("source", "sg_warehouse")),
        )

    # 1c. KB (2026090003): real per-round raw strokes from the Reader
    # source (R1-R4), no SG anywhere -- also DIRECT, no Layer-0 exists.
    kb = next((t for t in recon["finished_tournaments"] if t["game_code"] == "2026090003"), None)
    if kb and kb.get("round_scores"):
        for rs in kb["round_scores"]:
            cur.execute(
                "INSERT OR IGNORE INTO observation_round(game_code, season, round_number, status, sg_total, total_strokes, grain, source) VALUES (?,?,?,?,?,?,?,?)",
                (kb["game_code"], kb["season"], rs["round"], "FINISHED", None, rs["strokes"],
                 "DIRECT_NO_LOWER_LAYER", "reader (KB_2026090003_FR_OFFICIAL_LEADERBOARD_RECOVERY_V1.json)"),
            )

    # 1d. A second real per-round raw-strokes supplement the Tournament
    # Warehouse independently captured for one more SG-Warehouse
    # tournament -- enriches (never overwrites) its existing SG row.
    for t in recon["finished_tournaments"]:
        for supp in t.get("raw_round_supplement", []):
            cur.execute(
                "UPDATE observation_round SET total_strokes=?, source = source || ' + tournament_warehouse (raw strokes)' WHERE game_code=? AND round_number=?",
                (supp["strokes"], t["game_code"], supp["round"]),
            )

    n_rounds = cur.execute("SELECT COUNT(*) FROM observation_round").fetchone()[0]
    _verify(cur, "observation_round", "sg_total/total_strokes (Layer 1)", M, source="reconcile_10097_player_history.reconcile() round_rows + round_scores + raw_round_supplement, and SQL SUM over observation_hole where available", repo_path="scripts/reconcile_10097_player_history.py", sample_size=n_rounds, confidence="HIGH")

    # ===================================================================
    # LAYER 2 -- TOURNAMENT. Computed columns via real SQL aggregation.
    # ===================================================================
    # Excludes the in-progress tournament's game_code entirely, even
    # though 2 of its 3 rounds are themselves individually FINISHED --
    # a round finishing is not the same fact as the tournament
    # finishing, and this table's row-per-game_code must not be built
    # from a partial round set for a still-open tournament (handled in
    # its own branch below instead).
    in_progress_game_code = ip["game_code"] if ip else None
    cur.execute("""
        INSERT INTO tournament_observation(game_code, season, sg_total_computed, total_strokes_computed, rounds_aggregated, grain)
        SELECT game_code, season, AVG(sg_total), SUM(total_strokes), COUNT(*), 'COMPUTED_FROM_LAYER1'
        FROM observation_round
        WHERE status='FINISHED' AND game_code != COALESCE(?, '')
        GROUP BY game_code, season
    """, (in_progress_game_code,))
    # Native Layer-2 facts (rank/name/win/top10) -- cannot be derived
    # from round data, attached alongside the computed columns.
    for t in doc["tournament_history"]:
        cur.execute(
            "UPDATE tournament_observation SET tournament_name=?, status='FINISHED', finish_rank=?, is_win=?, is_top10=?, anchored_source='reconcile_10097_player_history (rank/name; not derivable from round data)' WHERE game_code=?",
            (t["tournament"], t["rank"], int(t["is_win"]), int(t["is_top10"]), t["game_code"]),
        )
    if ip:
        cur.execute(
            "INSERT OR IGNORE INTO tournament_observation(game_code, season, sg_total_computed, total_strokes_computed, rounds_aggregated, grain) SELECT game_code, season, AVG(sg_total), SUM(total_strokes), COUNT(*), 'COMPUTED_FROM_LAYER1' FROM observation_round WHERE game_code=? GROUP BY game_code, season",
            (ip["game_code"],),
        )
        cur.execute(
            "UPDATE tournament_observation SET tournament_name=?, status='IN_PROGRESS', is_win=0, is_top10=0, anchored_source='current tournament, excluded from FINISHED aggregates' WHERE game_code=?",
            (ip["tournament"], ip["game_code"]),
        )
    n_tournaments = cur.execute("SELECT COUNT(*) FROM tournament_observation").fetchone()[0]
    _verify(cur, "tournament_observation", "sg_total_computed/total_strokes_computed (Layer 2, SQL AVG/SUM over Layer 1)", D, source="SQL aggregation over observation_round", sample_size=n_tournaments, confidence="HIGH")
    _verify(cur, "tournament_observation", "finish_rank/tournament_name/is_win/is_top10 (Layer-2-native, not derivable)", M, source="reconcile_10097_player_history.reconcile()", repo_path="scripts/reconcile_10097_player_history.py", sample_size=n_tournaments, confidence="HIGH")

    # -- Reproducibility proof: Layer-2 SQL aggregate vs. the
    # independently-reported tournament sg_total already in
    # reconcile()'s own finished_tournaments (a category-1 fact never
    # used to build observation_round's SG rows in the first place --
    # round_rows and finished_tournaments are both read from the SG
    # Warehouse but at different granularity, so this is a real,
    # non-circular internal-consistency check).
    n_match, n_mismatch = 0, 0
    for t in recon["finished_tournaments"]:
        ref = t.get("sg_total")
        if ref is None:
            continue
        computed = cur.execute("SELECT sg_total_computed FROM tournament_observation WHERE game_code=?", (t["game_code"],)).fetchone()
        if not computed or computed[0] is None:
            continue
        delta = round(computed[0] - ref, 3)
        within = abs(delta) <= 0.02
        n_match += within
        n_mismatch += (not within)
        cur.execute("INSERT INTO layer_reproducibility_check VALUES (?,?,?,?,?)",
                    (t["game_code"], computed[0], ref, delta, int(within)))
    _verify(cur, "layer_reproducibility_check", "Layer2-computed vs. independently-reported tournament SG Total", D,
            source=f"real SQL cross-check: {n_match} matched within 0.02, {n_mismatch} mismatched, out of {n_match + n_mismatch} tournaments with both values",
            sample_size=n_match + n_mismatch, confidence="HIGH")

    # ===================================================================
    # LAYER 3 -- SEASON. SQL-aggregated from Layer 2 (FINISHED only).
    # ===================================================================
    cur.execute("""
        INSERT INTO season_observation(season, events, wins, top5, top10, top20, sg_total_computed, rounds_aggregated)
        SELECT t.season, COUNT(*), SUM(t.is_win),
               SUM(CASE WHEN t.finish_rank<=5 THEN 1 ELSE 0 END),
               SUM(CASE WHEN t.finish_rank<=10 THEN 1 ELSE 0 END),
               SUM(CASE WHEN t.finish_rank<=20 THEN 1 ELSE 0 END),
               AVG(t.sg_total_computed),
               SUM(t.rounds_aggregated)
        FROM tournament_observation t
        WHERE t.status='FINISHED'
        GROUP BY t.season
    """)
    n_seasons = cur.execute("SELECT COUNT(*) FROM season_observation").fetchone()[0]
    _verify(cur, "season_observation", "all columns (Layer 3, SQL aggregation over Layer 2)", D, source="SQL aggregation over tournament_observation", sample_size=n_seasons, confidence="HIGH")

    # ===================================================================
    # LAYER 4 -- CAREER. SQL-aggregated from Layer 3.
    # ===================================================================
    cur.execute("""
        INSERT INTO career_observation(player_id, events, wins, top5, top10, top20, seasons_aggregated)
        SELECT ?, SUM(events), SUM(wins), SUM(top5), SUM(top10), SUM(top20), COUNT(*)
        FROM season_observation
    """, (PLAYER_ID,))
    _verify(cur, "career_observation", "all columns (Layer 4, SQL aggregation over Layer 3)", D, source="SQL aggregation over season_observation", sample_size=n_seasons, confidence="HIGH")

    # ===================================================================
    # Independent categorical facts (not part of the layer chain)
    # ===================================================================
    english_name = None
    zip_path = ROOT / "evidence" / "current_round_2026120001_r3_20260906" / "official_sources.zip"
    if zip_path.exists():
        with zipfile.ZipFile(zip_path) as z:
            if "card-10097.html" in z.namelist():
                card_html = z.read("card-10097.html").decode("utf-8", errors="replace")
                m = re.search(r'playerEngName\s*=\s*"([^"]+)"', card_html)
                if m:
                    english_name = m.group(1)
    k_rank, k_rank_asof = None, None
    k_rank_path = CONTENT / "2026090003_OFFICIAL_KLPGA_RANKING.json"
    if k_rank_path.exists():
        import json as _json
        kr = _json.loads(k_rank_path.read_text(encoding="utf-8"))
        row = next((r for r in kr["records"] if str(r.get("player_id")) == PLAYER_ID), None)
        if row:
            k_rank, k_rank_asof = row.get("official_rank"), kr.get("ranking_date")
    snap = doc.get("current_snapshot")
    cur.execute("INSERT INTO player_profile VALUES (?,?,?,?,?,?)",
                (PLAYER_ID, doc["player_name"], english_name,
                 snap.get("official_rank") if snap else None, k_rank, k_rank_asof))
    _verify(cur, "player_profile", "official_name/english_name/current_ranking/k_ranking", M, source="PLAYER_HISTORY.json + card-10097.html + K-RANKING snapshot", sample_size=1, confidence="HIGH")

    ts = doc.get("technical_stats_2025")
    if ts:
        for m_ in ts["metrics"]:
            cur.execute(
                "INSERT OR IGNORE INTO technical_reading VALUES (?,?,?,?,?,?,?,?,?)",
                (ts["season"], "technical_stats_2025", m_["label"], m_["value"], m_.get("value_label"),
                 m_["rank"], m_.get("numerator"), m_.get("denominator"), m_.get("measured_rounds")),
            )
    n_tech = cur.execute("SELECT COUNT(*) FROM technical_reading").fetchone()[0]
    _verify(cur, "technical_reading", "14 real season-2025 metrics, one atomic row each", M, source="loadLocationRecord season-2025 capture", repo_path=str(PI_DIR / "TECHNICAL_STATS_2025.json"), sample_size=n_tech, confidence="HIGH")

    conn.commit()
    conn.close()
    return OUT_PATH


if __name__ == "__main__":
    path = build()
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    print(f"wrote {path}")
    for t in ("observation_hole", "observation_shot", "observation_round", "tournament_observation",
              "season_observation", "career_observation", "layer_reproducibility_check",
              "player_profile", "technical_reading", "field_verification"):
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n} rows")
    match, total = cur.execute("SELECT SUM(within_tolerance), COUNT(*) FROM layer_reproducibility_check").fetchone()
    print(f"Layer2<-Layer1 reproducibility: {match}/{total} tournaments matched within 0.02 SG")
    conn.close()
