"""Diagnose the real reason behind a missing (player, round) gap: fetch
that player's own getShotTracker for all 18 holes directly (the
already-proven fallback path). If real shots exist there, the group-
discovery step missed a real group (a bug to fix, not a data gap). If
the per-player endpoint is also empty for every hole, that is itself
real evidence of a genuine absence for that round.
"""
from __future__ import annotations
import argparse, json, time
from collector import fetch, load_json, PLAYER_ENDPOINT

def check_player_round(game, player, rnd, cookie=None, sleep=0.3):
    per_hole = {}
    total_shots = 0
    for hole in range(1, 19):
        status, raw = fetch(PLAYER_ENDPOINT, game, rnd, hole, player=player, cookie=cookie)
        obj = load_json(raw)
        shots = obj.get("shotTrackerList") or []
        per_hole[hole] = len(shots)
        total_shots += len(shots)
        time.sleep(sleep)
    return total_shots, per_hole

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--pairs", required=True, help="semicolon-separated player:round pairs")
    ap.add_argument("--cookie")
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    results = {}
    for pair in a.pairs.split(";"):
        pc, rnd_s = pair.split(":")
        rnd = int(rnd_s)
        total, per_hole = check_player_round(a.game, pc, rnd, a.cookie, a.sleep)
        nonzero_holes = [h for h, n in per_hole.items() if n > 0]
        results[f"{pc}:{rnd}"] = {
            "player_code": pc, "round": rnd,
            "total_shots_via_player_endpoint": total,
            "holes_with_shots": nonzero_holes,
            "per_hole_counts": per_hole,
        }
        print(f"{pc} R{rnd}: total_shots={total} holes_with_shots={nonzero_holes}")

    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
