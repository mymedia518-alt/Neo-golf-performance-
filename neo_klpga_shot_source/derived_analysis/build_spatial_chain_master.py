"""NEO Three-Player Shot Tracker SPATIAL CHAIN master builder.

Builds a SHOT-LEVEL (not hole-level) chain for every shot by 유해란/이재윤/
박서현 across all 216 player-hole plays, fresh from RAW.

Coordinate spaces used (both are real RAW fields, not invented):
  - (x, y): whole-hole coordinate space (tee-to-green), used for tee-shot
    dispersion. Scale/orientation NOT verified against compass direction,
    so no LEFT/RIGHT labels are derived from it directly -- only a
    verified tee-green AXIS (reused from hole1_full_analysis.py's method,
    recomputed fresh per hole from the full field) gives a neutral LAT1/
    LAT2/LAT3 lateral bucket (which side is "LAT1" vs "LAT3" is NOT
    claimed to be left or right).
  - (green_x, green_y): green/pin-area coordinate space, present on every
    shot row. Real per-round pins (pin_placement_72hole_audit.json,
    already VERIFIED for all 72 round-holes) are in this same space, so
    pin_dx/pin_dy/pin-space-distance are computed directly here.
  - distance-to-pin in REAL YARDS does not need calibration: the RAW
    'distance' column is the authoritative real-world remaining distance
    to the hole after each shot (confirmed via the known 2-putt par
    R1H12 case in the attribution audit: tee dist=114.3 -> approach
    dist=6.4 -> that 6.4 IS the real first-putt distance in yards). This
    is used as distance_to_pin_yd for every shot, not just Hole 12.
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
LIE_NAME = {"1": "FAIRWAY", "2": "ROUGH", "3": "GREEN", "4": "OB", "5": "PENALTY_AREA",
            "6": "BUNKER", "7": "LOST_BALL", "8": "PENALTY_STROKE", "9": "GREENSIDE_BUNKER",
            "10": "HOLED", "12": "FRINGE"}
PENALTY_STATES = {"4", "5", "7", "8"}
UNRELIABLE_DISTANCE_STATES = {"4", "5", "7", "8"}


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


def tee_green_axis_per_hole(con):
    """Full-field (107 players), fresh from RAW, same method as
    hole1_full_analysis.py's lateral_axis(): mean tee-shot landing point
    and mean holed-out point define a hole-specific axis."""
    axes = {}
    for hole in range(1, 19):
        rows = con.execute(
            "SELECT player_code, round, shot, state_code, x, y FROM klpga_player_shot "
            "WHERE game_code=? AND hole=? ORDER BY player_code, round, shot", (GAME, hole)
        ).fetchall()
        by_pr = defaultdict(list)
        for pc, rnd, shot, state, x, y in rows:
            by_pr[(pc, rnd)].append({"shot": shot, "state": state, "x": x, "y": y})
        tee_pts, hole_pts = [], []
        for key, shots in by_pr.items():
            ss = sorted(shots, key=lambda s: s["shot"])
            if ss and ss[0]["x"] is not None:
                tee_pts.append((ss[0]["x"], ss[0]["y"]))
            for s in ss:
                if s["state"] == "10" and s["x"] is not None:
                    hole_pts.append((s["x"], s["y"]))
                    break
        tee = (statistics.mean(p[0] for p in tee_pts), statistics.mean(p[1] for p in tee_pts))
        green = (statistics.mean(p[0] for p in hole_pts), statistics.mean(p[1] for p in hole_pts))
        axes[hole] = {"tee": tee, "green": green, "n_tee": len(tee_pts), "n_green": len(hole_pts)}
    return axes


def project_lateral(tee, green, pt):
    vx, vy = green[0] - tee[0], green[1] - tee[1]
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return None
    px, py = pt[0] - tee[0], pt[1] - tee[1]
    cross = px * vy - py * vx
    return cross / math.sqrt(L2)


def main():
    con = sqlite3.connect(DB)
    print("Computing tee-green axis per hole from full field (107 players)...")
    axes = tee_green_axis_per_hole(con)
    for h, a in axes.items():
        print(f"  Hole {h}: n_tee={a['n_tee']} n_green={a['n_green']}")

    # field-wide lateral terciles per hole, for LAT1/2/3 bucket boundaries
    lat_thresholds = {}
    for hole in range(1, 19):
        rows = con.execute(
            "SELECT player_code, round, shot, x, y FROM klpga_player_shot "
            "WHERE game_code=? AND hole=? AND shot=1 ORDER BY player_code, round", (GAME, hole)
        ).fetchall()
        tee, green = axes[hole]["tee"], axes[hole]["green"]
        lats = []
        for pc, rnd, shot, x, y in rows:
            if x is None:
                continue
            lat = project_lateral(tee, green, (x, y))
            if lat is not None:
                lats.append(lat)
        lats.sort()
        n = len(lats)
        if n >= 3:
            l1, l2 = lats[n // 3], lats[(2 * n) // 3]
        else:
            l1 = l2 = 0
        lat_thresholds[hole] = {"l1": l1, "l2": l2, "n": n}

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

    shot_records = []
    hole_summaries = []
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
                pin = PINS.get((rnd, hole))
                tee, green = axes[hole]["tee"], axes[hole]["green"]
                l1, l2 = lat_thresholds[hole]["l1"], lat_thresholds[hole]["l2"]

                strokes = len(ss)
                stp = strokes - par
                gir_shot = next((s["shot"] for s in ss if s["state"] == "3"), None)
                gir = gir_shot is not None and gir_shot <= par - 2
                putts = putts_count_fixed(ss)

                prev = None  # previous shot dict, for start-coordinate chaining
                remaining_before = float(yds)
                remaining_before_reliable = True
                for i, s in enumerate(ss):
                    shot_no = s["shot"]
                    lie_before = "TEE" if i == 0 else LIE_NAME.get(ss[i - 1]["state"], f"UNKNOWN_{ss[i-1]['state']}")
                    lie_after = LIE_NAME.get(s["state"], f"UNKNOWN_{s['state']}")
                    start_x = prev["x"] if prev is not None else None
                    start_y = prev["y"] if prev is not None else None
                    start_provenance = "OBSERVED(previous shot landing)" if prev is not None else "UNKNOWN(tee box not separately logged in RAW)"
                    end_x, end_y = s["x"], s["y"]
                    unreliable_dist = s["state"] in UNRELIABLE_DISTANCE_STATES
                    remaining_after = s["distance"]
                    shot_dist_yd = None
                    if remaining_before_reliable and not unreliable_dist and remaining_after is not None:
                        shot_dist_yd = round(remaining_before - remaining_after, 1)
                    pin_dx = pin_dy = pin_space_dist = None
                    if pin is not None and s["green_x"] is not None:
                        pin_dx = round(s["green_x"] - pin["pin_x"], 1)
                        pin_dy = round(s["green_y"] - pin["pin_y"], 1)
                        pin_space_dist = round(math.hypot(pin_dx, pin_dy), 1)
                    lat = None
                    lat_bucket = None
                    if i == 0 and end_x is not None:
                        lat = project_lateral(tee, green, (end_x, end_y))
                        if lat is not None:
                            lat_bucket = "LAT1" if lat <= l1 else ("LAT2" if lat <= l2 else "LAT3")
                    is_penalty = s["state"] in PENALTY_STATES
                    is_putt_phase = (s["state"] in ("3", "10")) and i > 0 and ss[i - 1]["state"] in ("3", "10")

                    shot_records.append({
                        "player_code": pc, "player_name": pname, "round": rnd, "hole": hole, "par": par,
                        "shot_number": shot_no, "n_shots_this_hole": strokes,
                        "start_x": start_x, "start_y": start_y, "start_provenance": start_provenance,
                        "end_x": end_x, "end_y": end_y, "end_green_x": s["green_x"], "end_green_y": s["green_y"],
                        "lie_before": lie_before, "lie_after": lie_after,
                        "shot_distance_yd": shot_dist_yd,
                        "remaining_distance_before_yd": round(remaining_before, 1) if remaining_before_reliable else None,
                        "remaining_distance_after_yd": remaining_after if not unreliable_dist else None,
                        "remaining_distance_unreliable_state": unreliable_dist,
                        "round_pin_x": pin["pin_x"] if pin else None, "round_pin_y": pin["pin_y"] if pin else None,
                        "pin_dx_mapunits": pin_dx, "pin_dy_mapunits": pin_dy,
                        "pin_space_distance_mapunits": pin_space_dist,
                        "distance_to_pin_yd": remaining_after if not unreliable_dist else None,
                        "tee_lateral_value": round(lat, 2) if lat is not None else None,
                        "tee_lateral_bucket": lat_bucket,
                        "is_penalty_stroke": is_penalty, "is_putt_phase": is_putt_phase,
                        "gir_hole": gir, "final_putts_fixed": putts,
                        "final_score": strokes, "final_score_to_par": stp,
                        "source_provenance": "OBSERVED(RAW klpga_player_shot)",
                    })
                    prev = s
                    if not unreliable_dist and remaining_after is not None:
                        remaining_before = remaining_after
                        remaining_before_reliable = True
                    else:
                        remaining_before_reliable = False

                if stp <= -1: bucket = "Birdie+"
                elif stp == 0: bucket = "Par"
                elif stp == 1: bucket = "Bogey"
                elif stp == 2: bucket = "Double"
                else: bucket = "TriplePlus"
                hole_summaries.append({
                    "player_code": pc, "player_name": pname, "round": rnd, "hole": hole, "par": par,
                    "strokes": strokes, "score_to_par": stp, "score_bucket": bucket,
                    "n_shots": strokes, "gir": gir, "putts_fixed": putts,
                    "tee_lateral_bucket": next((r["tee_lateral_bucket"] for r in shot_records
                                                 if r["player_code"] == pc and r["round"] == rnd and r["hole"] == hole and r["shot_number"] == 1), None),
                    "state_sequence": [s["state"] for s in ss],
                })

    print(f"\nTotal hole-plays: {len(hole_summaries)} (expected 216). Missing: {len(missing)}")
    print(f"Total shot-level records: {len(shot_records)}")

    out = {"game_code": GAME, "n_hole_plays": len(hole_summaries), "n_shot_records": len(shot_records),
           "missing": missing, "tee_green_axes": {str(k): v for k, v in axes.items()},
           "lat_thresholds": {str(k): v for k, v in lat_thresholds.items()},
           "hole_summaries": hole_summaries, "shot_records": shot_records}
    (HERE / "neo_three_player_spatial_chain.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

    import csv
    with open(HERE / "three_player_spatial_chain_master.csv", "w", newline="", encoding="utf-8") as f:
        fields = list(shot_records[0].keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in shot_records:
            w.writerow(r)
    print("Wrote neo_three_player_spatial_chain.json / three_player_spatial_chain_master.csv")


if __name__ == "__main__":
    main()
