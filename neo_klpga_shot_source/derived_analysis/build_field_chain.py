"""Full 107-player field chain, same methodology as build_spatial_chain_master.py
(fixed putts formula, real per-round pins, remaining-distance chaining with
UNKNOWN propagation through unreliable-distance states). This is the
foundation for all field-vs-player and next-shot-quality research below --
built once, queried many times, rather than re-querying RAW per analysis.
"""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
DB = HERE / "klpga_shots_RAW_READONLY.sqlite"
GAME = "2026100005"
PAR_YDS = json.loads((HERE / "klpga_tournament_18hole_par_yardage.json").read_text())
PIN_AUDIT = json.loads((HERE / "pin_placement_72hole_audit.json").read_text())
PINS = {(e["round"], e["hole"]): e for e in PIN_AUDIT["per_round_hole_table"]}
LIE_NAME = {"1": "FAIRWAY", "2": "ROUGH", "3": "GREEN", "4": "OB", "5": "PENALTY_AREA",
            "6": "BUNKER", "7": "LOST_BALL", "8": "PENALTY_STROKE", "9": "GREENSIDE_BUNKER",
            "10": "HOLED", "12": "FRINGE"}
PENALTY_STATES = {"4", "5", "7", "8"}
UNRELIABLE = {"4", "5", "7", "8"}


def putts_count_fixed(ss):
    last_off_green = -1
    for i, s in enumerate(ss):
        if s["state"] not in ("3", "10"):
            last_off_green = i
    g = last_off_green + 1
    if g >= len(ss):
        return 0
    if ss[g]["state"] == "10":
        return 0
    return len(ss) - 1 - g


def main():
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT player_code, round, hole, shot, state_code, x, y, green_x, green_y, distance "
        "FROM klpga_player_shot WHERE game_code=? ORDER BY player_code, round, hole, shot", (GAME,)
    ).fetchall()
    by_prh = defaultdict(list)
    for pc, rnd, hole, shot, state, x, y, gx, gy, dist in rows:
        by_prh[(pc, rnd, hole)].append({"shot": shot, "state": state, "x": x, "y": y, "gx": gx, "gy": gy, "distance": dist})

    shot_records = []
    hole_summaries = []
    for key, ss in by_prh.items():
        pc, rnd, hole = key
        ss = sorted(ss, key=lambda s: s["shot"])
        par = PAR_YDS[str(hole)]["par"]
        yds = PAR_YDS[str(hole)]["yds"]
        pin = PINS.get((rnd, hole))
        strokes = len(ss)
        stp = strokes - par
        gir_shot = next((s["shot"] for s in ss if s["state"] == "3"), None)
        gir = gir_shot is not None and gir_shot <= par - 2
        putts = putts_count_fixed(ss)

        remaining_before = float(yds)
        remaining_before_reliable = True
        for i, s in enumerate(ss):
            lie_before = "TEE" if i == 0 else LIE_NAME.get(ss[i - 1]["state"], f"UNKNOWN_{ss[i-1]['state']}")
            lie_after = LIE_NAME.get(s["state"], f"UNKNOWN_{s['state']}")
            unreliable = s["state"] in UNRELIABLE
            remaining_after = s["distance"]
            pin_dx = pin_dy = pin_dist = None
            if pin is not None and s["gx"] is not None:
                pin_dx = s["gx"] - pin["pin_x"]
                pin_dy = s["gy"] - pin["pin_y"]
                pin_dist = (pin_dx ** 2 + pin_dy ** 2) ** 0.5
            shot_records.append({
                "player_code": pc, "round": rnd, "hole": hole, "par": par, "shot_number": s["shot"],
                "lie_before": lie_before, "lie_after": lie_after,
                "remaining_before_yd": round(remaining_before, 1) if remaining_before_reliable else None,
                "remaining_after_yd": remaining_after if not unreliable else None,
                "is_penalty": s["state"] in PENALTY_STATES,
                "pin_space_dist": round(pin_dist, 1) if pin_dist is not None else None,
                "n_shots_this_hole": strokes, "final_score_to_par": stp, "gir": gir, "putts_fixed": putts,
            })
            if not unreliable and remaining_after is not None:
                remaining_before = remaining_after
                remaining_before_reliable = True
            else:
                remaining_before_reliable = False

        if stp <= -1: bucket = "Birdie+"
        elif stp == 0: bucket = "Par"
        elif stp == 1: bucket = "Bogey"
        elif stp == 2: bucket = "Double"
        else: bucket = "TriplePlus"
        hole_summaries.append({"player_code": pc, "round": rnd, "hole": hole, "par": par, "strokes": strokes,
                                "score_to_par": stp, "score_bucket": bucket, "gir": gir, "putts_fixed": putts,
                                "tee_lie": LIE_NAME.get(ss[0]["state"]), "state_sequence": [s["state"] for s in ss]})

    print(f"Field chain: {len(hole_summaries)} player-hole plays, {len(shot_records)} shot records, "
          f"{len(set((r['player_code'] for r in hole_summaries)))} players")
    out = {"game_code": GAME, "n_hole_plays": len(hole_summaries), "n_shot_records": len(shot_records),
           "hole_summaries": hole_summaries, "shot_records": shot_records}
    (HERE / "field_chain.json").write_text(json.dumps(out, ensure_ascii=False))
    print("Wrote field_chain.json")


if __name__ == "__main__":
    main()
