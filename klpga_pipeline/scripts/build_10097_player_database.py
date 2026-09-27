"""PLAYER DATABASE GOLD STANDARD V1 -- playerCode=10097 (김민선7) ONLY.

Builds ONE structured SQLite database consolidating every real,
independently-verifiable fact about this player already reconciled
elsewhere in this repository. This script does NOT re-derive facts from
raw sources -- it reads (read-only) from the already-tested, already-
reconciled data layer (reconcile_10097_player_history.reconcile() and
build_10097_player_history.build()), plus a small number of additional
already-committed real sources (K-ranking snapshot, the OK Open R3
official_sources.zip card page's embedded English name), and writes them
into typed tables.

Nothing here touches Player History's or Player Intelligence's HTML,
CSS, charts, or rendering. This is data-layer only, per the mission's
explicit scope: "Player History, Player Intelligence, Prediction,
Dashboard and Homepage will ALL consume this database" -- the direction
is database -> product, not the reverse; this script only builds the
database.

Every table has a matching set of rows in `field_verification`
documenting exactly where each field's value came from, or explicitly
marking it NOT_COLLECTED / BLOCKED / CONFIRMED_UNAVAILABLE when no real
value exists anywhere in this repository. Nothing is guessed or
estimated -- a field with no real backing value is written as NULL, not
a placeholder, and its verification row explains why.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
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
OUT_DIR = CONTENT / "knowledge_engine" / "player_database" / "10097"
OUT_PATH = OUT_DIR / "PLAYER_DATABASE_V1.sqlite"

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


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE meta(
    player_id TEXT PRIMARY KEY, player_name TEXT, generated_at TEXT,
    source_commit TEXT, schema_version TEXT
);

CREATE TABLE player_profile(
    player_id TEXT PRIMARY KEY, official_name TEXT, english_name TEXT,
    birth TEXT, nationality TEXT, turn_pro TEXT, sponsor TEXT, team TEXT,
    height TEXT, weight TEXT, handedness TEXT,
    current_ranking INTEGER, current_ranking_asof TEXT,
    world_ranking INTEGER,
    k_ranking INTEGER, k_ranking_asof TEXT
);

CREATE TABLE career_summary(
    player_id TEXT PRIMARY KEY,
    career_events INTEGER, career_rounds INTEGER,
    wins INTEGER, runner_up INTEGER, top3 INTEGER, top5 INTEGER,
    top10 INTEGER, top20 INTEGER, cuts INTEGER, earnings INTEGER,
    average_score REAL, best_finish INTEGER,
    best_round_tournament TEXT, best_round_sg_total REAL,
    worst_round_tournament TEXT, worst_round_sg_total REAL
);

CREATE TABLE season_stats(
    season INTEGER PRIMARY KEY,
    events INTEGER, cuts INTEGER, wins INTEGER, top5 INTEGER,
    top10 INTEGER, top20 INTEGER, earnings INTEGER,
    average_score REAL, average_finish REAL, scoring_average REAL,
    ranking INTEGER
);

CREATE TABLE season_sg(
    season INTEGER PRIMARY KEY,
    sg_total REAL, sg_ott REAL, sg_app REAL, sg_arg REAL, sg_putt REAL,
    t2g REAL, sample_size INTEGER
);

CREATE TABLE tournament(
    game_code TEXT PRIMARY KEY, season INTEGER, tournament_name TEXT,
    status TEXT, finish_rank INTEGER, rounds_played INTEGER,
    sg_total REAL, sg_ott REAL, sg_app REAL, sg_arg REAL, sg_putt REAL,
    is_win INTEGER, is_top10 INTEGER, source TEXT
);

CREATE TABLE round(
    game_code TEXT, season INTEGER, round_number INTEGER,
    sg_total REAL, source TEXT,
    PRIMARY KEY(game_code, round_number)
);

CREATE TABLE hole(
    game_code TEXT, round_number INTEGER, hole INTEGER,
    course TEXT, par INTEGER, strokes INTEGER, relative_to_par INTEGER,
    PRIMARY KEY(game_code, round_number, hole)
);

CREATE TABLE shot(
    game_code TEXT, round_number INTEGER, hole INTEGER, shot_no INTEGER,
    distance_yd REAL, club TEXT, start_lie TEXT, end_lie TEXT,
    pin_distance_yd REAL, result TEXT, sg REAL,
    PRIMARY KEY(game_code, round_number, hole, shot_no)
);

CREATE TABLE distance_bucket(
    bucket_label TEXT, season INTEGER,
    attempts INTEGER, gir_count INTEGER, birdie_count INTEGER,
    avg_proximity_yd REAL, avg_sg REAL,
    PRIMARY KEY(bucket_label, season)
);

CREATE TABLE driving(
    season INTEGER, par_scope TEXT,
    avg_distance_yd REAL, fairway_pct REAL,
    rank_distance INTEGER, rank_fairway INTEGER,
    left_miss_pct REAL, right_miss_pct REAL, rough_pct REAL, ob_pct REAL,
    next_shot_sg REAL,
    PRIMARY KEY(season, par_scope)
);

CREATE TABLE approach(
    season INTEGER, metric_label TEXT,
    distance_bucket TEXT, value REAL, unit TEXT, rank INTEGER,
    miss_direction TEXT, avg_proximity_yd REAL, avg_sg REAL,
    numerator REAL, denominator REAL, measured_rounds INTEGER,
    PRIMARY KEY(season, metric_label)
);

CREATE TABLE putting(
    season INTEGER, metric_label TEXT, distance_bucket TEXT,
    value REAL, unit TEXT, rank INTEGER,
    make_pct REAL, three_putt_pct REAL, average_putts REAL,
    numerator REAL, denominator REAL, measured_rounds INTEGER,
    PRIMARY KEY(season, metric_label)
);

CREATE TABLE short_game(
    season INTEGER, metric_label TEXT,
    value REAL, unit TEXT, rank INTEGER,
    numerator REAL, denominator REAL, measured_rounds INTEGER,
    PRIMARY KEY(season, metric_label)
);

CREATE TABLE scoring(
    scope TEXT PRIMARY KEY,
    eagle_or_better INTEGER, birdie INTEGER, par INTEGER, bogey INTEGER,
    double_or_worse INTEGER, sample_holes INTEGER,
    birdie_conversion_pct REAL, bogey_avoidance_pct REAL
);

CREATE TABLE course(
    game_code TEXT PRIMARY KEY, course_name TEXT,
    course_history_events INTEGER, course_average_score REAL,
    course_sg_total REAL, course_ranking INTEGER,
    course_wins INTEGER, course_top10 INTEGER
);

CREATE TABLE weather(
    game_code TEXT, round_number INTEGER,
    temperature REAL, wind TEXT, rain TEXT, humidity REAL,
    PRIMARY KEY(game_code, round_number)
);

CREATE TABLE momentum(
    scope TEXT, response_to TEXT,
    sample_size INTEGER, avg_next_hole_relative_to_par REAL,
    PRIMARY KEY(scope, response_to)
);

CREATE TABLE player_identity(
    player_id TEXT PRIMARY KEY,
    most_consistent_component TEXT, fastest_growing_component TEXT,
    most_volatile_component TEXT,
    career_foundation TEXT, career_foundation_share_pct REAL,
    winning_foundation TEXT, winning_foundation_share_pct REAL
);

CREATE TABLE growth(
    component TEXT, from_season INTEGER, to_season INTEGER,
    delta REAL, direction TEXT,
    PRIMARY KEY(component, from_season, to_season)
);

CREATE TABLE player_history_timeline(
    season INTEGER, label TEXT, detail TEXT
);

CREATE TABLE training_targets(
    target_label TEXT PRIMARY KEY,
    sample_size INTEGER, measured_weakness TEXT,
    career_trend TEXT, priority TEXT
);

CREATE TABLE field_verification(
    table_name TEXT, field_note TEXT, status TEXT,
    source TEXT, repo_path TEXT, parser TEXT, warehouse TEXT,
    reader TEXT, sample_size INTEGER, verification_date TEXT,
    confidence TEXT
);
"""

# Status vocabulary (RED TEAM mission's own three-state discipline,
# extended for this database): MEASURED (real, in this repo, used
# as-is) / DERIVED (computed from real measured inputs already in this
# repo) / PARTIAL (real but incomplete, e.g. one tournament only) /
# NOT_COLLECTED (KLPGA may publish it; this repo has never ingested it)
# / BLOCKED (network-blocked in this sandbox, existence unconfirmed) /
# CONFIRMED_UNAVAILABLE (verified nowhere on KLPGA's own site).
M, D, P, NC, BL, CU = "MEASURED", "DERIVED", "PARTIAL", "NOT_COLLECTED", "BLOCKED", "CONFIRMED_UNAVAILABLE"


def _verify(cur, table, field_note, status, *, source=None, repo_path=None, parser=None,
            warehouse=None, reader=None, sample_size=None, confidence=None):
    cur.execute(
        "INSERT INTO field_verification VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (table, field_note, status, source, repo_path, parser, warehouse, reader,
         sample_size, _utcnow(), confidence),
    )


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

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

    # -- meta --------------------------------------------------------
    cur.execute("INSERT INTO meta VALUES (?,?,?,?,?)",
                (PLAYER_ID, doc["player_name"], _utcnow(), _source_git_sha(), "player_database_v1"))

    # -- player_profile ------------------------------------------------
    k_rank_path = CONTENT / "2026090003_OFFICIAL_KLPGA_RANKING.json"
    k_rank, k_rank_asof = None, None
    if k_rank_path.exists():
        kr = json.loads(k_rank_path.read_text(encoding="utf-8"))
        row = next((r for r in kr["records"] if str(r.get("player_id")) == PLAYER_ID), None)
        if row:
            k_rank = row.get("official_rank")
            k_rank_asof = kr.get("ranking_date")

    english_name = None
    zip_path = ROOT / "evidence" / "current_round_2026120001_r3_20260906" / "official_sources.zip"
    if zip_path.exists():
        with zipfile.ZipFile(zip_path) as z:
            if "card-10097.html" in z.namelist():
                card_html = z.read("card-10097.html").decode("utf-8", errors="replace")
                import re
                m = re.search(r'playerEngName\s*=\s*"([^"]+)"', card_html)
                if m:
                    english_name = m.group(1)

    current_rank = None
    snap = doc.get("current_snapshot")
    if snap:
        current_rank = snap.get("official_rank")

    cur.execute(
        "INSERT INTO player_profile VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (PLAYER_ID, doc["player_name"], english_name,
         None, None, None, None, None, None, None, None,
         current_rank, "2026 시즌 스냅샷 1건",
         None,
         k_rank, k_rank_asof),
    )
    _verify(cur, "player_profile", "official_name/player_id", M, source="PLAYER_HISTORY.json", repo_path=str(PI_DIR / "PLAYER_HISTORY.json"), sample_size=1, confidence="HIGH")
    _verify(cur, "player_profile", "english_name", M if english_name else NC,
            source="OK Open R3 official_sources.zip card-10097.html embedded JS (playerEngName)" if english_name else None,
            repo_path=str(zip_path.relative_to(REPO_ROOT)), sample_size=1 if english_name else 0,
            confidence="HIGH" if english_name else None)
    _verify(cur, "player_profile", "current_ranking (money-list official_rank)", M if current_rank else NC,
            source="2026 season snapshot" if current_rank else None, repo_path=str(PI_DIR / "PLAYER_HISTORY.json"),
            sample_size=1 if current_rank else 0, confidence="HIGH" if current_rank else None)
    _verify(cur, "player_profile", "k_ranking", M if k_rank else NC,
            source="official K-RANKING weekly snapshot" if k_rank else None,
            repo_path=str(k_rank_path.relative_to(REPO_ROOT)) if k_rank_path.exists() else None,
            sample_size=1 if k_rank else 0, confidence="HIGH" if k_rank else None)
    _verify(cur, "player_profile", "birth/nationality/turn_pro/sponsor/team/height/weight/handedness", NC,
            source=None,
            repo_path="src/klpga/config.py (PLAYER_PROFILE_ENDPOINT, URL confirmed but never fetched)",
            parser="klpga.collectors.player_profile (fetch-only, no parser written -- no real sample captured)",
            sample_size=0, confidence=None)
    _verify(cur, "player_profile", "world_ranking (non-KLPGA e.g. Rolex world ranking)", CU,
            source=None, repo_path=None, sample_size=0, confidence=None)

    # -- career_summary ------------------------------------------------
    co = doc["career_overview"]
    rh = doc["round_history"]
    best = rh.get("best_round") or {}
    worst = rh.get("worst_round") or {}
    cur.execute(
        "INSERT INTO career_summary VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (PLAYER_ID, co["total_events"], rh["total_rounds"], co["total_wins"], None, None,
         co["total_top5"], co["total_top10"], co["total_top20"], None, None, None, None,
         best.get("tournament"), best.get("sg_total"),
         worst.get("tournament"), worst.get("sg_total")),
    )
    _verify(cur, "career_summary", "career_events/wins/top5/top10/top20", M, source="reconcile_10097_player_history.reconcile()", repo_path="scripts/reconcile_10097_player_history.py", sample_size=co["total_events"], confidence="HIGH")
    _verify(cur, "career_summary", "career_rounds", M, source="reconcile round_rows", repo_path="scripts/reconcile_10097_player_history.py", sample_size=rh["total_rounds"], confidence="HIGH")
    _verify(cur, "career_summary", "best_round/worst_round (by SG Total)", D, source="derived from round_rows", repo_path="scripts/build_10097_player_history.py::_round_history", sample_size=rh["total_rounds"], confidence="HIGH")
    _verify(cur, "career_summary", "runner_up/top3/cuts/career earnings/career average_score/best_finish (raw rank)", NC,
            source=None, repo_path=None, sample_size=0, confidence=None,
            reader="career-wide values not derivable: only a single 2026-season snapshot carries earnings/average_score; no cuts-made field is trusted (see coverage_matrix note on made_cut sample-size mismatch)")

    # -- season_stats / season_sg ----------------------------------------
    for row in co["season_rows"]:
        season = row["season"]
        is_current_snapshot_season = snap is not None and doc.get("career_overview", {}).get("latest_tournament", {}).get("season") == season
        cur.execute(
            "INSERT INTO season_stats VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (season, row["events"], None, row["wins"], row["top5"], row["top10"], row["top20"],
             snap["money"] if (snap and season == 2026) else None,
             snap["average_score"] if (snap and season == 2026) else None,
             None,
             snap["average_score"] if (snap and season == 2026) else None,
             k_rank if season == 2026 else None),
        )
        cur.execute(
            "INSERT INTO season_sg VALUES (?,?,?,?,?,?,?,?)",
            (season, row["sg_total"], row["sg_ott"], row["sg_app"], row["sg_arg"], row["sg_putt"],
             round(row["sg_ott"] + row["sg_app"] + row["sg_arg"], 4), row["sg_sample_size"]),
        )
    _verify(cur, "season_stats", "events/wins/top5/top10/top20 (per season)", M, source="reconcile", repo_path="scripts/reconcile_10097_player_history.py", sample_size=len(co["season_rows"]), confidence="HIGH")
    _verify(cur, "season_stats", "cuts (per season)", NC, source=None, repo_path=None, sample_size=0, confidence=None,
            reader="a made_cut field exists in NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json but its 2023 sample (7) does not match the 25 real tournaments other sources confirm -- excluded as unreliable, not silently used")
    _verify(cur, "season_stats", "earnings/average_score/scoring_average/ranking (per season)", P,
            source="2026 snapshot only", repo_path=str(PI_DIR / "PLAYER_HISTORY.json"), sample_size=1, confidence="HIGH",
            reader="real for season=2026 only; NULL for 2023-2025 -- no historical per-season snapshot has ever been captured")
    _verify(cur, "season_sg", "sg_total/ott/app/arg/putt/t2g (per season)", M, source="reconcile (SG Warehouse + Reader + Live snapshot merge)", repo_path="scripts/reconcile_10097_player_history.py", sample_size=sum(r["sg_sample_size"] for r in co["season_rows"]), confidence="HIGH")

    # -- tournament / round ----------------------------------------------
    for t in doc["tournament_history"]:
        comp = t.get("sg_components") or {}
        cur.execute(
            "INSERT INTO tournament VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (t["game_code"], t["season"], t["tournament"], "FINISHED", t["rank"], None,
             t["sg_total"], comp.get("ott"), comp.get("app"), comp.get("arg"), comp.get("putt"),
             int(t["is_win"]), int(t["is_top10"]), "reconcile_10097_player_history"),
        )
    ip = doc.get("current_tournament_in_progress")
    if ip:
        cur.execute(
            "INSERT INTO tournament VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ip["game_code"], ip["season"], ip["tournament"], "IN_PROGRESS", None, len(ip["rounds_completed"]),
             None, None, None, None, None, 0, 0, "reconcile_10097_player_history"),
        )
    for r in recon["round_rows"]:
        cur.execute(
            "INSERT OR IGNORE INTO round VALUES (?,?,?,?,?)",
            (r["game_code"], r["season"], r["round"], r["sg_total"], r.get("source")),
        )
    _verify(cur, "tournament", "all columns (96 finished + 1 in-progress)", M, source="reconcile_10097_player_history.reconcile()", repo_path="scripts/reconcile_10097_player_history.py", sample_size=len(doc["tournament_history"]) + (1 if ip else 0), confidence="HIGH")
    _verify(cur, "tournament", "field_size/course/date/earnings (per tournament)", NC, source=None, repo_path=None, sample_size=0, confidence=None)
    _verify(cur, "round", "sg_total (per round)", M, source="reconcile round_rows", repo_path="scripts/reconcile_10097_player_history.py", sample_size=len(recon["round_rows"]), confidence="HIGH")
    _verify(cur, "round", "score/birdie/bogey/double/putts/GIR/fairway/driving_distance (per round)", NC, source=None, repo_path=None, sample_size=0, confidence=None,
            reader="only game_code=2026120001's rounds have hole-level detail to derive these from -- see `hole` table; every other round has SG Total only")

    # -- hole (single real captured tournament) --------------------------
    hh = doc.get("hole_history")
    if hh:
        for rnd in hh["rounds"]:
            for h in rnd["holes"]:
                cur.execute(
                    "INSERT INTO hole VALUES (?,?,?,?,?,?,?)",
                    (hh["game_code"], rnd["round"], h["hole"], hh["course"], h["par"], h["strokes"], h["relative_to_par"]),
                )
    n_holes = sum(len(rnd["holes"]) for rnd in hh["rounds"]) if hh else 0
    _verify(cur, "hole", "par/strokes/relative_to_par", P if hh else NC,
            source="OK Open (2026120001) real captured scorecard" if hh else None,
            repo_path="content/website_v2/knowledge_engine/player_intelligence/10097/PLAYER_HISTORY.json (hole_history)" if hh else None,
            sample_size=n_holes, confidence="HIGH" if hh else None,
            reader="covers exactly 1 of 97 tournaments -- not a career-wide hole-level record")
    _verify(cur, "hole", "hole_average/hole_ranking (field-wide difficulty)", BL, source=None,
            repo_path="/ajax/leaderboard/getShotTracker -> holeInfo.avgScore/holeInfo.rank (confirmed real via card-*.html embedded JS, never live-fetched in this sandbox)",
            sample_size=0, confidence=None)

    # -- shot / distance_bucket (schema only, no real data reachable here) --
    _verify(cur, "shot", "shot_no/distance/lie/pin_distance/result/sg (all columns)", BL, source=None,
            repo_path="klpga.collectors.cmpro_shots (branch feat/cmpro-shot-data-v0, unmerged) + /ajax/leaderboard/getShotTracker (undiscovered until this session's data-discovery mission)",
            parser="klpga.collectors.cmpro_shots.parse_cmpro_shots (built+tested on an unmerged branch)",
            warehouse="operator-local cmpro_<game>_full.sqlite -- confirmed real and QA-passed for game 2026090002 (108 players, 6012 holes) per reports/cmpro_2026090002_final_qa.md on branch qa/cmpro-full-collection-review, but that SQLite file itself is not reachable from this sandbox",
            sample_size=0, confidence=None)
    _verify(cur, "distance_bucket", "attempts/gir/birdie/proximity/sg (all buckets)", BL, source=None,
            repo_path="same as `shot` -- distance buckets are computed FROM shot-level data, which is not reachable here",
            sample_size=0, confidence=None,
            reader="a distance-band function (<100,100-120,120-130,130-140,140-150,150-175) already exists in scripts/experiment_best_next_state_01.py on branch experiment/player-value-metrics-01, and 10097's real 150-175yd fairway/rough numbers are reported (not re-verifiable here) in scripts/player_report_01_kim_minsun7.py on the same lineage")

    # -- driving / approach / putting / short_game (2025 season stats) -----
    ts = doc.get("technical_stats_2025")
    if ts:
        season = ts["season"]
        by_label = {m["label"]: m for m in ts["metrics"]}

        def m(label):
            return by_label.get(label)

        driving_rows = [
            ("Par4,5", "평균 티샷 거리 (Par4,5)", "페어웨이 안착률 (Par4,5)"),
            ("Par5", "평균 티샷 거리 (Par5)", "페어웨이 안착률 (Par5)"),
            ("Par4", "평균 티샷 거리 (Par4)", "페어웨이 안착률 (Par4)"),
        ]
        for scope, dist_label, fw_label in driving_rows:
            dm, fm = m(dist_label), m(fw_label)
            cur.execute(
                "INSERT INTO driving VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (season, scope, dm["value"] if dm else None, fm["value"] if fm else None,
                 dm["rank"] if dm else None, fm["rank"] if fm else None,
                 None, None, None, None, None),
            )
        for label in ("그린 적중률 (GIR)", "페어웨이 안착률 (세컨샷)"):
            mm = m(label)
            if mm:
                cur.execute(
                    "INSERT INTO approach VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (season, label, None, mm["value"], mm.get("value_label"), mm["rank"],
                     None, None, None, mm.get("numerator"), mm.get("denominator"), mm.get("measured_rounds")),
                )
        for label in ("1퍼트 성공률", "라운드당 평균 퍼트 수", "퍼팅 성공률"):
            mm = m(label)
            if mm:
                cur.execute(
                    "INSERT INTO putting VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (season, label, None, mm["value"], mm.get("value_label"), mm["rank"],
                     None, None, None, mm.get("numerator"), mm.get("denominator"), mm.get("measured_rounds")),
                )
        for label in ("샌드 세이브율", "스크램블링률"):
            mm = m(label)
            if mm:
                cur.execute(
                    "INSERT INTO short_game VALUES (?,?,?,?,?,?,?,?)",
                    (season, label, mm["value"], mm.get("value_label"), mm["rank"],
                     mm.get("numerator"), mm.get("denominator"), mm.get("measured_rounds")),
                )
    _verify(cur, "driving", "distance/fairway (2025 only)", P, source="loadLocationRecord (season 2025 capture)",
            repo_path="docs/discovery/raw_samples/*.html -> TECHNICAL_STATS_2025.json", sample_size=1, confidence="HIGH",
            reader="season 2025 only -- 2023/2024/2026 BLOCKED (network required to check loadLocationRecord for those seasons)")
    _verify(cur, "driving", "left/right miss %, rough %, OB %, next_shot_sg", NC, source=None, repo_path=None, sample_size=0, confidence=None)
    _verify(cur, "approach", "GIR / second-shot fairway (2025 only)", P, source="TECHNICAL_STATS_2025.json", repo_path=str(PI_DIR / "TECHNICAL_STATS_2025.json"), sample_size=1, confidence="HIGH")
    _verify(cur, "approach", "distance-bucketed GIR / miss_direction / proximity / SG", BL, source=None, repo_path=None, sample_size=0, confidence=None)
    _verify(cur, "putting", "1-putt%/putts-per-round/putting success% (2025 only)", P, source="TECHNICAL_STATS_2025.json", repo_path=str(PI_DIR / "TECHNICAL_STATS_2025.json"), sample_size=1, confidence="HIGH")
    _verify(cur, "putting", "distance-bucketed (1m/2m/3m/5m/8m/10m/15m+) make%/3-putt%", BL, source=None, repo_path=None, sample_size=0, confidence=None)
    _verify(cur, "short_game", "sand save % / scrambling % (2025 only)", P, source="TECHNICAL_STATS_2025.json", repo_path=str(PI_DIR / "TECHNICAL_STATS_2025.json"), sample_size=1, confidence="HIGH")
    _verify(cur, "short_game", "rough save / fringe / chip / pitch (separated)", NC, source=None, repo_path=None, sample_size=0, confidence=None)

    # -- scoring (derived from the one real hole-level capture) -----------
    if hh:
        counts = {"eagle_or_better": 0, "birdie": 0, "par": 0, "bogey": 0, "double_or_worse": 0}
        for rnd in hh["rounds"]:
            for h in rnd["holes"]:
                rtp = h["relative_to_par"]
                if rtp <= -2:
                    counts["eagle_or_better"] += 1
                elif rtp == -1:
                    counts["birdie"] += 1
                elif rtp == 0:
                    counts["par"] += 1
                elif rtp == 1:
                    counts["bogey"] += 1
                else:
                    counts["double_or_worse"] += 1
        birdie_conv = round(100 * counts["birdie"] / n_holes, 2) if n_holes else None
        bogey_avoid = round(100 * (1 - (counts["bogey"] + counts["double_or_worse"]) / n_holes), 2) if n_holes else None
        cur.execute(
            "INSERT INTO scoring VALUES (?,?,?,?,?,?,?,?,?)",
            (f"{hh['game_code']}_all_rounds", counts["eagle_or_better"], counts["birdie"], counts["par"],
             counts["bogey"], counts["double_or_worse"], n_holes, birdie_conv, bogey_avoid),
        )
    cur.execute(
        "INSERT INTO scoring VALUES (?,?,?,?,?,?,?,?,?)",
        ("2026_season_snapshot_rate_only", None, None, None, None, None, None,
         snap.get("birdie_rate") if snap else None, snap.get("par_break_rate") if snap else None),
    )
    _verify(cur, "scoring", "eagle/birdie/par/bogey/double counts", P if hh else NC,
            source="derived from hole_history (1 tournament)" if hh else None, repo_path=str(PI_DIR / "PLAYER_HISTORY.json"),
            sample_size=n_holes, confidence="HIGH" if hh else None,
            reader="career-wide birdie/bogey counts do not exist; only a season-level birdie_rate/par_break_rate percentage exists (2026 snapshot)")

    # -- course (only the one real captured course name) -------------------
    if hh:
        cur.execute("INSERT INTO course VALUES (?,?,?,?,?,?,?,?)",
                    (hh["game_code"], hh["course"], None, None, None, None, None, None))
    _verify(cur, "course", "course_name", P if hh else NC, source="hole_history capture_note" if hh else None,
            repo_path=str(PI_DIR / "PLAYER_HISTORY.json") if hh else None, sample_size=1 if hh else 0,
            confidence="HIGH" if hh else None,
            reader="tournament names (e.g. '하나금융그룹 챔피언십') are NOT golf course names -- no course-name mapping exists for the other 96 tournaments")
    _verify(cur, "course", "course_history_events/course_average_score/course_sg_total/course_ranking/course_wins/course_top10", NC, source=None, repo_path=None, sample_size=0, confidence=None)

    # -- weather -------------------------------------------------------
    _verify(cur, "weather", "temperature/wind/rain/humidity (all rows)", NC, source=None, repo_path=None, sample_size=0, confidence=None,
            reader="never collected anywhere in this repository or any known branch")

    # -- momentum (derived from the one real hole-level capture) -----------
    if hh:
        holes_flat = [h for rnd in hh["rounds"] for h in rnd["holes"]]
        buckets = {"birdie_or_better": [], "bogey": [], "double_or_worse": []}
        for i in range(len(holes_flat) - 1):
            rtp = holes_flat[i]["relative_to_par"]
            nxt = holes_flat[i + 1]["relative_to_par"]
            if rtp <= -1:
                buckets["birdie_or_better"].append(nxt)
            elif rtp == 1:
                buckets["bogey"].append(nxt)
            elif rtp >= 2:
                buckets["double_or_worse"].append(nxt)
        for response_to, values in buckets.items():
            avg = round(sum(values) / len(values), 3) if values else None
            cur.execute("INSERT INTO momentum VALUES (?,?,?,?)",
                        (hh["game_code"], response_to, len(values), avg))
    _verify(cur, "momentum", "avg_next_hole_relative_to_par (birdie/bogey/double response)", P if hh else NC,
            source="derived from the one real hole-level capture" if hh else None,
            repo_path=str(PI_DIR / "PLAYER_HISTORY.json") if hh else None,
            sample_size=n_holes if hh else 0, confidence="LOW" if hh else None,
            reader="single-tournament, small-n sample -- not a defensible career-wide momentum profile")

    # -- player_identity / growth / timeline -------------------------------
    dna = doc.get("career_dna") or {}
    cur.execute(
        "INSERT INTO player_identity VALUES (?,?,?,?,?,?,?,?)",
        (PLAYER_ID, dna.get("most_consistent_component"), dna.get("fastest_growing_component"),
         dna.get("most_volatile_component"), dna.get("career_foundation"), dna.get("career_foundation_share_pct"),
         dna.get("winning_foundation"), dna.get("winning_foundation_share_pct")),
    )
    _verify(cur, "player_identity", "all columns", D, source="build_10097_player_history._career_dna()", repo_path="scripts/build_10097_player_history.py", sample_size=len(co["season_rows"]), confidence="HIGH")

    evo = doc["career_evolution"]
    for component, data in evo.items():
        for delta in data["deltas"]:
            cur.execute(
                "INSERT INTO growth VALUES (?,?,?,?,?)",
                (data["label"], delta["from_season"], delta["to_season"], delta["delta"],
                 "IMPROVED" if delta["delta"] > 0 else ("DECLINED" if delta["delta"] < 0 else "FLAT")),
            )
    _verify(cur, "growth", "component season-to-season deltas", D, source="build_10097_player_history._career_evolution()", repo_path="scripts/build_10097_player_history.py", sample_size=sum(len(d["deltas"]) for d in evo.values()), confidence="HIGH")

    for m_ in doc.get("player_story", []):
        cur.execute("INSERT INTO player_history_timeline VALUES (?,?,?)", (m_["season"], m_["label"], m_["detail"]))
    _verify(cur, "player_history_timeline", "season/label/detail", D, source="build_10097_player_history._player_story()", repo_path="scripts/build_10097_player_history.py", sample_size=len(doc.get("player_story", [])), confidence="HIGH")

    # -- training_targets: intentionally empty in this sandbox -------------
    _verify(cur, "training_targets", "all rows", BL, source=None,
            repo_path="scripts/experiment_best_next_state_01.py / player_report_01_kim_minsun7.py (branch experiment/player-value-metrics-01) already computes a real, cross-checked 150-175yd fairway/rough breakdown for this exact player, but its backing SQLite is not reachable from this sandbox",
            sample_size=0, confidence=None,
            reader="no row is written here rather than re-transcribing a number this build cannot itself re-verify against a live queryable source -- see the mission's own 'nothing may be guessed' rule")

    conn.commit()
    conn.close()
    return OUT_PATH


if __name__ == "__main__":
    path = build()
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    print(f"wrote {path}")
    for t in tables:
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n} rows")
    conn.close()
