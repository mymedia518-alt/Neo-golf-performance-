"""Master per-hole-play shot chain for 유해란(9115)/이재윤(9708)/박서현(9111),
all 18 holes x 4 rounds = 72 hole-plays per player, 216 total.
Same methodology as hole1_full_analysis.py / hole12_master_template.py
(LIE_NAME, GIR definition, putts_count), generalized across all holes,
using the already-verified pin_placement_72hole_audit.json for real pins.
"""
from __future__ import annotations
import json, math, sqlite3, statistics
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
DB = HERE / "klpga_shots_RAW_READONLY.sqlite"
GAME = "2026100005"
PLAYERS = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}
PAR_YDS = json.loads((HERE / "klpga_tournament_18hole_par_yardage.json").read_text())
PIN_AUDIT = json.loads((HERE / "pin_placement_72hole_audit.json").read_text())
PINS = {(e["round"], e["hole"]): e for e in PIN_AUDIT["per_round_hole_table"]}
UNRELIABLE_DISTANCE_STATES = {"4", "5", "7", "8"}
LIE_NAME = {"1": "FAIRWAY", "2": "ROUGH", "3": "GREEN", "4": "OB", "5": "PENALTY_AREA",
            "6": "BUNKER", "7": "LOST_BALL", "8": "PENALTY_STROKE", "9": "GREENSIDE_BUNKER",
            "10": "HOLED", "12": "FRINGE"}
PENALTY_STATES = {"4", "5", "7", "8"}


def putts_count(ss):
    last_off_green = -1
    for i, s in enumerate(ss):
        if s["state"] not in ("3", "10"):
            last_off_green = i
    return len(ss) - (last_off_green + 1)


def main():
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT player_code, round, hole, shot, state_code, x, y, green_x, green_y, distance "
        "FROM klpga_player_shot WHERE game_code=? AND player_code IN (?,?,?) "
        "ORDER BY player_code, round, hole, shot",
        (GAME, *PLAYERS.keys()),
    ).fetchall()
    by_prh = defaultdict(list)
    for pc, rnd, hole, shot, state, x, y, gx, gy, dist in rows:
        by_prh[(pc, rnd, hole)].append({"shot": shot, "state": state, "x": x, "y": y,
                                         "green_x": gx, "green_y": gy, "distance": dist})

    records = []
    missing = []
    for pc, pname in PLAYERS.items():
        for rnd in (1, 2, 3, 4):
            for hole in range(1, 19):
                ss = by_prh.get((pc, rnd, hole))
                if not ss:
                    missing.append((pc, pname, rnd, hole))
                    continue
                ss = sorted(ss, key=lambda s: s["shot"])
                par = PAR_YDS[str(hole)]["par"]
                yds = PAR_YDS[str(hole)]["yds"]
                shot1 = ss[0]
                strokes = len(ss)
                stp = strokes - par
                putts = putts_count(ss)
                gir_shot = None
                for s in ss:
                    if s["state"] == "3":
                        gir_shot = s["shot"]; break
                gir = gir_shot is not None and gir_shot <= par - 2
                pin = PINS.get((rnd, hole))
                fw_hit = shot1["state"] == "1"
                tee_lie = LIE_NAME.get(shot1["state"], f"UNKNOWN_{shot1['state']}")
                tee_land_dist = None
                if shot1["distance"] is not None and shot1["state"] not in UNRELIABLE_DISTANCE_STATES:
                    tee_land_dist = round(yds - shot1["distance"], 1)
                approach_lie = None
                approach_remaining = None
                if par != 3 and len(ss) >= 2:
                    shot2 = ss[1]
                    approach_lie = LIE_NAME.get(shot2["state"], f"UNKNOWN_{shot2['state']}")
                    approach_remaining = shot2["distance"]
                penalty_count = sum(1 for s in ss if s["state"] in PENALTY_STATES)
                bunker_count = sum(1 for s in ss if s["state"] in ("6", "9"))
                rough_count = sum(1 for s in ss if s["state"] == "2")
                first_miss_shot = None
                first_miss_lie = None
                for s in ss[:-1] if gir else ss:
                    if s["state"] in ("2", "4", "5", "6", "7", "8", "9"):
                        first_miss_shot = s["shot"]; first_miss_lie = LIE_NAME.get(s["state"]); break
                if stp <= -1: bucket = "Birdie+"
                elif stp == 0: bucket = "Par"
                elif stp == 1: bucket = "Bogey"
                elif stp == 2: bucket = "Double"
                else: bucket = "TriplePlus"
                pin_dist_last_approach = None
                if pin is not None and len(ss) >= 2:
                    s2 = ss[1]
                    if s2["green_x"] is not None:
                        pin_dist_last_approach = round(math.hypot(s2["green_x"] - pin["pin_x"],
                                                                   s2["green_y"] - pin["pin_y"]), 2)
                records.append({
                    "player_code": pc, "player_name": pname, "round": rnd, "hole": hole, "par": par,
                    "strokes": strokes, "score_to_par": stp, "score_bucket": bucket,
                    "tee_lie": tee_lie, "tee_land_dist_yd": tee_land_dist, "fw_hit": fw_hit,
                    "approach_lie": approach_lie, "approach_remaining_yd": approach_remaining,
                    "pin_distance_map_shot2": pin_dist_last_approach,
                    "gir": gir, "putts": putts,
                    "penalty_count": penalty_count, "bunker_count": bunker_count, "rough_count": rough_count,
                    "first_miss_shot": first_miss_shot, "first_miss_lie": first_miss_lie,
                    "n_shots": len(ss),
                    "state_sequence": [s["state"] for s in ss],
                    "distance_sequence": [s["distance"] for s in ss],
                })

    print(f"Total records: {len(records)} (expected 216). Missing: {len(missing)}")
    for m in missing:
        print(" MISSING:", m)

    out = {"game_code": GAME, "players": PLAYERS, "n_records": len(records), "missing": missing, "records": records}
    (HERE / "three_player_master_chain.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

    import csv
    with open(HERE / "three_player_master_chain.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["player_code", "player_name", "round", "hole", "par", "strokes", "score_to_par",
                    "score_bucket", "tee_lie", "tee_land_dist_yd", "fw_hit", "approach_lie",
                    "approach_remaining_yd", "pin_distance_map_shot2", "gir", "putts",
                    "penalty_count", "bunker_count", "rough_count", "first_miss_shot", "first_miss_lie", "n_shots"])
        for r in records:
            w.writerow([r["player_code"], r["player_name"], r["round"], r["hole"], r["par"], r["strokes"],
                        r["score_to_par"], r["score_bucket"], r["tee_lie"], r["tee_land_dist_yd"], r["fw_hit"],
                        r["approach_lie"], r["approach_remaining_yd"], r["pin_distance_map_shot2"], r["gir"],
                        r["putts"], r["penalty_count"], r["bunker_count"], r["rough_count"],
                        r["first_miss_shot"], r["first_miss_lie"], r["n_shots"]])
    print("Wrote three_player_master_chain.json / .csv")


if __name__ == "__main__":
    main()
