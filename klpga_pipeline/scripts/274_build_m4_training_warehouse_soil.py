"""Rebuild the real, cross-tournament player_event/player_round
training warehouse (same schema/engine as scripts/241_build_m4_
training_warehouse.py) for the NEXT target tournament, 제20회 S-OIL
챔피언십 (game_code 2026100001, starts 2026-10-29).

Identical HISTORICAL_GAME_CODES to scripts/241 (the same 10 distinct,
completed KLPGA regular-tour gameCodes, collected via the same
registered neo-sync.yml route, stage="results") -- not extended, not
reduced. Every one of those 10 tournaments ended by 2026-10-04, so the
leakage check below (all historical start_dates strictly before this
target's 2026-10-29 start) passes with an even wider margin than it did
for 2026100003's own 2026-10-16 target. Re-running against a new
TARGET_GAME_CODE/TARGET_START_DATE is necessary because scripts/242's
own build() hard-refuses (InsufficientWarehouseError via the "target
game's own rows already exist" guard is not the issue here; rather,
klpga.ops.paths.db_path() is a single shared file, and PRE temporal
isolation must be re-verified against the CURRENT target, not an old
one) -- see this script's own `main()` leakage block, line-for-line
unchanged from 241 except GAME_CODE/TARGET_START_DATE.

Other completed tournaments since 241 was first run (2026100004 HJ중공업,
2026100003 아이스버그) are NOT added here: 2026100004 was never synced
via neo-sync (built by a separate bespoke pipeline, no reader/<gc>
branch with normalized/LEADERBOARD.json), and 2026100003's own
reader/2026100003 branch only carries PRE-stage artifacts (entry/
k-ranking), not a results-stage LEADERBOARD.json -- its real round
results were collected via a different, non-neo-sync route. Adding
either would require a fresh stage="results" neo-sync dispatch and is
out of scope for this task; the existing, already-validated 10-
tournament corpus (same one 2026100003's own PRE M4 build used, see
ICEBERG_2026100003_PRE_M4_CANDIDATE_V1.json) is reused unchanged.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.ops.paths import db_path  # noqa: E402

TARGET_GAME_CODE = "2026100001"
TARGET_START_DATE = date(2026, 10, 29)

HISTORICAL_GAME_CODES = [
    "2026090002", "2026090003", "2026100005",
    "2026080001", "2026080002", "2026080003", "2026080004",
    "2026070001", "2026070002", "2026070003",
]


def _git_show(ref: str) -> str:
    return subprocess.run(
        ["git", "show", ref], cwd=REPO_ROOT, capture_output=True, check=True, text=True, encoding="utf-8",
    ).stdout


def _iso(yyyymmdd: str) -> str:
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def main() -> None:
    db = db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.is_file():
        db.unlink()

    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE tournament_master(event_id TEXT PRIMARY KEY, game_code TEXT, event_name TEXT, start_date TEXT, end_date TEXT)")
    conn.execute(
        "CREATE TABLE player_event(player_id TEXT, event_id TEXT, player_name TEXT, "
        "finish_position TEXT, made_cut INTEGER, "
        "finish_position_numeric INTEGER, score_to_par INTEGER, rounds_played INTEGER, "
        "PRIMARY KEY (player_id, event_id))"
    )
    conn.execute(
        "CREATE TABLE player_round(player_id TEXT, event_id TEXT, round_number INTEGER, "
        "round_score INTEGER, round_to_par INTEGER, PRIMARY KEY (player_id, event_id, round_number))"
    )

    report = {"tournaments": [], "validation": {}}
    total_events = 0
    total_rounds = 0
    arithmetic_problems = []
    leakage_problems = []
    dup_event_problems = []
    dup_round_problems = []

    for gc in HISTORICAL_GAME_CODES:
        tinfo = json.loads(_git_show(f"origin/reader/{gc}:klpga_pipeline/normalized/{gc}/TOURNAMENT_INFO.json"))
        lb = json.loads(_git_show(f"origin/reader/{gc}:klpga_pipeline/normalized/{gc}/LEADERBOARD.json"))
        game_list = json.loads(_git_show(f"origin/reader/{gc}:klpga_pipeline/raw/{gc}/game_list.json"))
        total_par = game_list.get("totalPar")
        assert total_par, f"{gc}: no official totalPar in game_list.json -- refusing to guess a par"

        start_iso = _iso(tinfo["start_date"])
        end_iso = _iso(tinfo["end_date"])
        start_d = date.fromisoformat(start_iso)
        if not (start_d < TARGET_START_DATE):
            leakage_problems.append(f"{gc}: start_date {start_iso} is not strictly before target start {TARGET_START_DATE.isoformat()}")

        conn.execute("INSERT INTO tournament_master VALUES (?,?,?,?,?)", (gc, gc, tinfo["event_name"], start_iso, end_iso))

        records = lb["records"]
        seen_players = set()
        for r in records:
            pid = r["player_id"]
            if pid in seen_players:
                dup_event_problems.append(f"{gc}: duplicate player_id {pid} in player_event")
                continue
            seen_players.add(pid)
            conn.execute(
                "INSERT INTO player_event VALUES (?,?,?,?,?,?,?,?)",
                (pid, gc, r["player_name"], r["finish_position"], r["made_cut"],
                 r["finish_position_numeric"], r["score_to_par"], r["rounds_played"]),
            )
            total_events += 1

            round_scores = []
            seen_rounds = set()
            for rn in (1, 2, 3, 4):
                score = r.get(f"r{rn}_score")
                if score is None:
                    continue
                if rn in seen_rounds:
                    dup_round_problems.append(f"{gc}/{pid}: duplicate round {rn}")
                    continue
                seen_rounds.add(rn)
                round_to_par = score - total_par
                conn.execute(
                    "INSERT INTO player_round VALUES (?,?,?,?,?)",
                    (pid, gc, rn, score, round_to_par),
                )
                total_rounds += 1
                round_scores.append(score)

            declared_total = r.get("total_score")
            if declared_total is not None and round_scores and sum(round_scores) != declared_total:
                arithmetic_problems.append(
                    f"{gc}/{pid}: sum(round_scores)={sum(round_scores)} != declared total_score={declared_total}"
                )

        report["tournaments"].append({
            "game_code": gc,
            "tournament_name": tinfo["event_name"],
            "start_date": start_iso,
            "end_date": end_iso,
            "total_par": total_par,
            "player_event_rows": len(records),
            "player_round_rows": sum(1 for r in records for rn in (1, 2, 3, 4) if r.get(f"r{rn}_score") is not None),
        })

    conn.commit()

    (n_tournaments,) = conn.execute("SELECT COUNT(DISTINCT event_id) FROM player_event").fetchone()
    (n_events,) = conn.execute("SELECT COUNT(*) FROM player_event").fetchone()
    (n_rounds,) = conn.execute("SELECT COUNT(*) FROM player_round").fetchone()
    conn.close()

    report["validation"] = {
        "target_game_code": TARGET_GAME_CODE,
        "target_start_date": TARGET_START_DATE.isoformat(),
        "distinct_training_tournaments": n_tournaments,
        "player_event_rows": n_events,
        "player_round_rows": n_rounds,
        "duplicate_player_event_problems": dup_event_problems,
        "duplicate_player_round_problems": dup_round_problems,
        "arithmetic_mismatch_problems": arithmetic_problems,
        "future_leakage_problems": leakage_problems,
        "all_checks_pass": not (dup_event_problems or dup_round_problems or arithmetic_problems or leakage_problems),
    }
    report["db_path"] = str(db)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
