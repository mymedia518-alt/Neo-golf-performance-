from __future__ import annotations
import argparse, json, sqlite3, time
from pathlib import Path
from collector import collect_group

def load_groups(groups_path):
    data = json.loads(Path(groups_path).read_text(encoding="utf-8"))
    return data["game_code"], data["rounds"]  # {round_str: {group_no_str: [members]}}

def load_players(players_path):
    data = json.loads(Path(players_path).read_text(encoding="utf-8"))
    return data["players"]  # {player_code: {player_name, rounds: [..dup..]}}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--groups", required=True, help="path to discover_groups.py output")
    ap.add_argument("--players", required=True, help="path to discover_players.py output")
    ap.add_argument("--root", default="./NEO_DATA_ROOT_LOCAL")
    ap.add_argument("--cookie")
    ap.add_argument("--sleep", type=float, default=0.35)
    ap.add_argument("--rounds", default="1,2,3,4", help="restrict to these rounds (comma-separated)")
    ap.add_argument("--report-out", required=True)
    a = ap.parse_args()

    root = Path(a.root)
    db = root / "normalized" / "klpga_shots.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)

    game_code, groups_by_round = load_groups(a.groups)
    players = load_players(a.players)
    restrict_rounds = {int(x) for x in a.rounds.split(",")}

    total_shots = 0
    raw_requests = 0
    fails = []
    warns = []
    completed_groups = 0
    attempted_groups = 0

    for rnd_str, groups in groups_by_round.items():
        rnd = int(rnd_str)
        if rnd not in restrict_rounds:
            continue
        for group_no in sorted(groups.keys(), key=int):
            attempted_groups += 1
            n, results = collect_group(a.game, group_no, [rnd], list(range(1, 19)), root, db, a.cookie, a.sleep)
            total_shots += n
            raw_requests += len(results)
            hole_fails = [r for r in results if r["status"] == "FAIL"]
            if hole_fails:
                fails.append({"round": rnd, "group_no": group_no, "failed_holes": hole_fails})
            else:
                completed_groups += 1
            if n == 0:
                warns.append(f"round={rnd} group_no={group_no}: zero shots across all 18 holes")

    # Cross-check real player coverage against discovery (never assumed).
    con = sqlite3.connect(db)
    covered = {
        (row[0], row[1])
        for row in con.execute(
            "SELECT DISTINCT player_code, round FROM klpga_player_shot WHERE game_code=?", (a.game,)
        )
    }
    con.close()

    con = sqlite3.connect(db)
    total_player_round_holes = con.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT player_code, round, hole FROM klpga_player_shot WHERE game_code=?)",
        (a.game,),
    ).fetchone()[0]
    total_shot_rows = con.execute(
        "SELECT COUNT(*) FROM klpga_player_shot WHERE game_code=?", (a.game,)
    ).fetchone()[0]
    con.close()

    missing_player_rounds = []
    for pc, info in players.items():
        expected_rounds = sorted(set(info["rounds"])) if info.get("rounds") else []
        expected_rounds = [r for r in expected_rounds if r in restrict_rounds]
        for r in expected_rounds:
            if (pc, r) not in covered:
                missing_player_rounds.append({"player_code": pc, "player_name": info.get("player_name"), "round": r})

    report = {
        "game_code": a.game,
        "rounds_processed": sorted(restrict_rounds),
        "total_players_in_field": len(players),
        "completed_player_rounds": len(covered),
        "attempted_groups": attempted_groups,
        "completed_groups_no_hole_failures": completed_groups,
        "raw_requests": raw_requests,
        "total_player_round_hole_rows": total_player_round_holes,
        "total_shot_rows": total_shot_rows,
        "FAIL": fails,
        "WARN": warns,
        "missing_player_rounds": missing_player_rounds,
    }
    Path(a.report_out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
