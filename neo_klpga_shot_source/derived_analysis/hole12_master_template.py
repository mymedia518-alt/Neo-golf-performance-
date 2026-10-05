"""NEO Hole 12 MASTER TEMPLATE -- final build.

Covers, from real data only (no estimation):
  TASK 1  Same-fairway, different-outcome: FW-hit-only subset, full chain
          per outcome bucket (Birdie+/Par/Bogey+/Double+), including putts.
  TASK 2  Approach-endpoint map data: every real approach (not just the 3
          case-study players), START(remaining distance)->PIN->ENDPOINT,
          per round, bucketed by outcome.
  TASK 3  Pin-centered map: every approach endpoint re-expressed as
          (dx,dy) from THAT ROUND'S real pin (already-verified HOLED-shot
          convergence), combined across all 4 rounds. Neutral QUAD id
          (orientation NOT verified -- never left/right) x NEAR/MID/FAR
          pin-distance tercile (map-pixel units, not yards -- flagged).
  TASK 4  Red-team of the "flat inside 170yd" finding: full outcome
          breakdown per distance band + confound checks (lie mix, round
          mix within each band).
  TASK 5  Player-specific second-shot chain for the 3 case-study players.
  TASK 6  "Imperfect golf" case finder: real favorable/unfavorable x
          good/bad outcome examples per player.
"""
from __future__ import annotations
import csv, json, math, sqlite3, statistics
from pathlib import Path
from collections import defaultdict, Counter

HERE = Path(__file__).parent
DB = HERE / "klpga_shots_RAW_READONLY.sqlite"
GAME = "2026100005"
HOLE = 12
PAR = 4
HOLE_YARDAGE = 410.0
UNRELIABLE_DISTANCE_STATES = {"4", "5", "7", "8"}
LIE_NAME = {"1": "FAIRWAY", "2": "ROUGH", "3": "GREEN", "4": "OB", "5": "PENALTY_AREA",
            "6": "BUNKER", "7": "LOST_BALL", "8": "PENALTY_STROKE", "9": "GREENSIDE_BUNKER",
            "10": "HOLED", "12": "FRINGE"}
PLAYERS_OF_INTEREST = {"9115": "유해란(TOP,#1,-4)", "9708": "이재윤(MID,#27,+9)", "9111": "박서현(BOTTOM,#61,+26)"}
PAR4_HOLES = [1, 3, 6, 8, 9, 12, 13, 14, 15, 17]
HOLE_YARDS = json.loads((HERE / "klpga_tournament_18hole_par_yardage.json").read_text())
players_meta = json.loads((HERE / "players_RAW_READONLY.json").read_text())["players"]


def load_all(con):
    rows = con.execute(
        "SELECT player_code, round, shot, state_code, x, y, green_x, green_y, distance "
        "FROM klpga_player_shot WHERE game_code=? AND hole=? ORDER BY player_code, round, shot",
        (GAME, HOLE),
    ).fetchall()
    by_pr = defaultdict(list)
    for pc, rnd, shot, state, x, y, gx, gy, dist in rows:
        by_pr[(pc, rnd)].append({"shot": shot, "state": state, "x": x, "y": y, "green_x": gx, "green_y": gy, "distance": dist})
    return by_pr


def round_pins(by_pr):
    by_round = defaultdict(list)
    for (pc, rnd), shots in by_pr.items():
        for s in shots:
            if s["state"] == "10" and s["green_x"] is not None:
                by_round[rnd].append((s["green_x"], s["green_y"]))
    pins = {}
    for rnd, pts in sorted(by_round.items()):
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        pins[rnd] = {"pin_x": statistics.mean(xs), "pin_y": statistics.mean(ys)}
    return pins


def lateral_axis(by_pr):
    tee_pts, hole_pts = [], []
    for key, shots in by_pr.items():
        ss = sorted(shots, key=lambda s: s["shot"])
        if ss and ss[0]["x"] is not None:
            tee_pts.append((ss[0]["x"], ss[0]["y"]))
        for s in ss:
            if s["state"] == "10" and s["x"] is not None:
                hole_pts.append((s["x"], s["y"])); break
    tee = (statistics.mean(p[0] for p in tee_pts), statistics.mean(p[1] for p in tee_pts))
    green = (statistics.mean(p[0] for p in hole_pts), statistics.mean(p[1] for p in hole_pts))
    return tee, green


def project_lateral(tee, green, pt):
    vx, vy = green[0] - tee[0], green[1] - tee[1]
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return None
    px, py = pt[0] - tee[0], pt[1] - tee[1]
    cross = px * vy - py * vx
    return cross / math.sqrt(L2)


def putts_count(ss):
    """Trailing shots with state in {GREEN,HOLED} starting right after the
    last non-green state -- standard real-golf putt count."""
    last_off_green = -1
    for i, s in enumerate(ss):
        if s["state"] not in ("3", "10"):
            last_off_green = i
    return len(ss) - (last_off_green + 1)


def build_full_chain(by_pr, pins, tee, green):
    laterals = []
    tmp = []
    for (pc, rnd), shots in by_pr.items():
        ss = sorted(shots, key=lambda s: s["shot"])
        if not ss or ss[0]["x"] is None or ss[0]["distance"] is None:
            continue
        lat = project_lateral(tee, green, (ss[0]["x"], ss[0]["y"]))
        tmp.append((pc, rnd, ss, lat))
        if lat is not None:
            laterals.append(lat)
    laterals.sort()
    l1, l2 = laterals[len(laterals) // 3], laterals[(2 * len(laterals)) // 3]

    def lat_bucket(lat):
        return "LAT1" if lat <= l1 else ("LAT2" if lat <= l2 else "LAT3")

    reliable_lands = sorted(HOLE_YARDAGE - ss[0]["distance"] for _, _, ss, _ in tmp if ss[0]["state"] not in UNRELIABLE_DISTANCE_STATES)
    n = len(reliable_lands)
    d1, d2 = reliable_lands[n // 3], reliable_lands[(2 * n) // 3]

    def dist_band(land):
        if land <= d1: return f"{int(round(reliable_lands[0]))}-{int(round(d1))}yd"
        if land <= d2: return f"{int(round(d1))}-{int(round(d2))}yd"
        return f"{int(round(d2))}-{int(round(reliable_lands[-1]))}yd"

    records = []
    for pc, rnd, ss, lat in tmp:
        shot1 = ss[0]
        unreliable = shot1["state"] in UNRELIABLE_DISTANCE_STATES
        landing_distance = HOLE_YARDAGE - shot1["distance"]
        approach_distance = shot1["distance"]
        strokes = len(ss)
        stp = strokes - PAR
        gir_shot = None
        for s in ss:
            if s["state"] == "3":
                gir_shot = s["shot"]; break
        gir = gir_shot is not None and gir_shot <= PAR - 2
        shot2 = ss[1] if len(ss) >= 2 else None
        pin = pins.get(rnd)
        pin_dx = pin_dy = pin_dist_map = None
        approach_lie = None
        if shot2 is not None:
            approach_lie = LIE_NAME.get(shot2["state"], f"UNKNOWN_{shot2['state']}")
            if pin is not None and shot2["green_x"] is not None:
                pin_dx = shot2["green_x"] - pin["pin_x"]
                pin_dy = shot2["green_y"] - pin["pin_y"]
                pin_dist_map = math.hypot(pin_dx, pin_dy)
        putts = putts_count(ss)
        if stp <= -1: bucket = "Birdie+"
        elif stp == 0: bucket = "Par"
        elif stp == 1: bucket = "Bogey"
        else: bucket = "Double+"
        penalty = any(s["state"] in ("4", "5", "7", "8") for s in ss)
        gir_miss_outcome = None
        if gir is False:
            gir_miss_outcome = "ParSave" if stp == 0 else ("Bogey" if stp == 1 else "Double+")
        records.append({
            "player_code": pc, "player_name": players_meta.get(pc, {}).get("player_name", pc), "round": rnd,
            "tee_lie": LIE_NAME.get(shot1["state"], f"UNKNOWN_{shot1['state']}"),
            "landing_distance_yd": round(landing_distance, 1),
            "landing_zone": f"{dist_band(landing_distance)} x {lat_bucket(lat)}" if lat is not None else None,
            "approach_distance_yd": round(approach_distance, 1),
            "unreliable_distance_state": unreliable,
            "round_pin_x": pin["pin_x"] if pin else None, "round_pin_y": pin["pin_y"] if pin else None,
            "approach_endpoint_green_x": shot2["green_x"] if shot2 else None,
            "approach_endpoint_green_y": shot2["green_y"] if shot2 else None,
            "approach_lie": approach_lie, "gir": gir, "gir_miss_outcome": gir_miss_outcome,
            "pin_dx_map": pin_dx, "pin_dy_map": pin_dy, "pin_distance_map": pin_dist_map,
            "fw_hit": shot1["state"] == "1",
            "putts": putts, "strokes": strokes, "score_to_par": stp, "score_bucket": bucket,
            "penalty_involved": penalty,
            "shot_state_sequence": [s["state"] for s in ss],
            "shot_distance_sequence": [s["distance"] for s in ss],
        })
    return records, {"d1": d1, "d2": d2, "l1": l1, "l2": l2}


# ---------- TASK 1: same fairway, different outcome ----------
def task1_same_fairway(records):
    fw = [r for r in records if r["fw_hit"]]
    by_bucket = defaultdict(list)
    for r in fw:
        by_bucket[r["score_bucket"]].append(r)
    out = {}
    for b, rows in sorted(by_bucket.items()):
        out[b] = {
            "n": len(rows),
            "avg_landing_distance": round(statistics.mean(r["landing_distance_yd"] for r in rows), 1),
            "avg_approach_distance": round(statistics.mean(r["approach_distance_yd"] for r in rows), 1),
            "GIR_pct": round(sum(1 for r in rows if r["gir"]) / len(rows), 3),
            "avg_putts": round(statistics.mean(r["putts"] for r in rows), 2),
            "penalty_pct": round(sum(1 for r in rows if r["penalty_involved"]) / len(rows), 3),
            "approach_lie_mix": dict(Counter(r["approach_lie"] for r in rows)),
            "full_chains": [{
                "player": r["player_name"], "round": r["round"], "landing_distance": r["landing_distance_yd"],
                "landing_zone": r["landing_zone"], "approach_distance": r["approach_distance_yd"],
                "approach_lie": r["approach_lie"], "pin_distance_map": r["pin_distance_map"],
                "gir": r["gir"], "putts": r["putts"], "strokes": r["strokes"], "score_to_par": r["score_to_par"],
                "shot_state_sequence": r["shot_state_sequence"], "shot_distance_sequence": r["shot_distance_sequence"],
            } for r in rows],
        }
    return out


# ---------- TASK 2: approach endpoint map (all real approaches) ----------
def task2_approach_map(records):
    out = defaultdict(list)
    for r in records:
        if r["approach_endpoint_green_x"] is None:
            continue
        out[r["round"]].append({
            "player": r["player_name"], "pc": r["player_code"],
            "start_remaining_distance": r["approach_distance_yd"],
            "endpoint_green_x": r["approach_endpoint_green_x"], "endpoint_green_y": r["approach_endpoint_green_y"],
            "pin_x": r["round_pin_x"], "pin_y": r["round_pin_y"],
            "approach_lie": r["approach_lie"], "score_bucket": r["score_bucket"],
        })
    return out


# ---------- TASK 3: pin-centered combined map ----------
def task3_pin_centered(records):
    pts = [r for r in records if r["pin_dx_map"] is not None]
    dists = sorted(r["pin_distance_map"] for r in pts)
    n = len(dists)
    t1, t2 = dists[n // 3], dists[(2 * n) // 3]

    def ring(d):
        return "NEAR" if d <= t1 else ("MID" if d <= t2 else "FAR")

    def quad(dx, dy):
        if dx >= 0 and dy >= 0: return "QUAD-A"
        if dx < 0 and dy >= 0: return "QUAD-B"
        if dx < 0 and dy < 0: return "QUAD-C"
        return "QUAD-D"

    cells = defaultdict(list)
    for r in pts:
        cell = f"{ring(r['pin_distance_map'])} {quad(r['pin_dx_map'], r['pin_dy_map'])}"
        cells[cell].append(r)
    summary = {}
    for cell, rows in cells.items():
        n2 = len(rows)
        summary[cell] = {
            "n": n2,
            "rounds_present": sorted(set(r["round"] for r in rows)),
            "GIR_pct": round(sum(1 for r in rows if r["gir"]) / n2, 3),
            "ParOrBetter_pct": round(sum(1 for r in rows if r["score_to_par"] <= 0) / n2, 3),
            "BogeyPlus_pct": round(sum(1 for r in rows if r["score_to_par"] >= 1) / n2, 3),
            "DoublePlus_pct": round(sum(1 for r in rows if r["score_to_par"] >= 2) / n2, 3),
            "avg_score_to_par": round(statistics.mean(r["score_to_par"] for r in rows), 3),
            "LOW_SAMPLE": n2 < 5,
        }
    points = [{"pc": r["player_code"], "round": r["round"], "dx": r["pin_dx_map"], "dy": r["pin_dy_map"],
               "ring": ring(r["pin_distance_map"]), "quad": quad(r["pin_dx_map"], r["pin_dy_map"]),
               "score_bucket": r["score_bucket"], "gir": r["gir"]} for r in pts]
    return {"ring_thresholds_map_units": {"t1": t1, "t2": t2}, "cell_summary": summary, "points": points,
            "orientation_note": "QUAD-A/B/C/D are neutral sign-of-(dx,dy) buckets. Real-world compass orientation (left/right, short/long) is NOT independently verified -- never relabeled as such."}


# ---------- TASK 4: red-team distance bands ----------
def task4_redteam_distance(records):
    apps = sorted(r["approach_distance_yd"] for r in records)
    n = len(apps)
    cuts = [apps[n // 4], apps[n // 2], apps[(3 * n) // 4]]

    def qband(d):
        if d <= cuts[0]: return f"Q1(<={cuts[0]:.0f})"
        if d <= cuts[1]: return f"Q2(<={cuts[1]:.0f})"
        if d <= cuts[2]: return f"Q3(<={cuts[2]:.0f})"
        return f"Q4(>{cuts[2]:.0f})"

    bands = defaultdict(list)
    for r in records:
        bands[qband(r["approach_distance_yd"])].append(r)
    out = {}
    for b, rows in bands.items():
        n2 = len(rows)
        out[b] = {
            "n": n2,
            "GIR_pct": round(sum(1 for r in rows if r["gir"]) / n2, 3),
            "BirdiePlus_pct": round(sum(1 for r in rows if r["score_bucket"] == "Birdie+") / n2, 3),
            "Par_pct": round(sum(1 for r in rows if r["score_bucket"] == "Par") / n2, 3),
            "Bogey_pct": round(sum(1 for r in rows if r["score_bucket"] == "Bogey") / n2, 3),
            "DoublePlus_pct": round(sum(1 for r in rows if r["score_bucket"] == "Double+") / n2, 3),
            "Penalty_pct": round(sum(1 for r in rows if r["penalty_involved"]) / n2, 3),
            "avg_score_to_par": round(statistics.mean(r["score_to_par"] for r in rows), 3),
            "lie_mix": dict(Counter(r["approach_lie"] for r in rows)),
            "round_mix": dict(Counter(r["round"] for r in rows)),
            "fw_hit_pct_of_tee_shot": round(sum(1 for r in rows if r["fw_hit"]) / n2, 3),
        }
    return {"quartile_cuts": [round(c, 1) for c in cuts], "bands": out}


# ---------- TASK 5: player-specific second-shot chain ----------
def task5_player_chain(con, pc, cuts):
    def qband(d):
        if d <= cuts[0]: return f"Q1(<={cuts[0]:.0f})"
        if d <= cuts[1]: return f"Q2(<={cuts[1]:.0f})"
        if d <= cuts[2]: return f"Q3(<={cuts[2]:.0f})"
        return f"Q4(>{cuts[2]:.0f})"

    miss_lies = defaultdict(int)
    recovery = defaultdict(list)
    for hole in PAR4_HOLES:
        shots = con.execute(
            "SELECT round, shot, state_code, distance FROM klpga_player_shot WHERE game_code=? AND hole=? "
            "AND player_code=? ORDER BY round, shot", (GAME, hole, pc),
        ).fetchall()
        by_round = defaultdict(list)
        for rnd, shot, state, dist in shots:
            by_round[rnd].append({"shot": shot, "state": state, "distance": dist})
        for rnd, ss in by_round.items():
            ss = sorted(ss, key=lambda s: s["shot"])
            if len(ss) < 2 or ss[0]["distance"] is None or ss[0]["state"] in UNRELIABLE_DISTANCE_STATES:
                continue
            approach_distance = ss[0]["distance"]
            band = qband(approach_distance)
            shot2 = ss[1]
            gir_shot = None
            for s in ss:
                if s["state"] == "3":
                    gir_shot = s["shot"]; break
            gir = gir_shot is not None and gir_shot <= 2
            if not gir:
                miss_lies[(band, LIE_NAME.get(shot2["state"], f"UNKNOWN_{shot2['state']}"))] += 1
                stp = len(ss) - 4
                recovery[band].append(stp <= 0)
    recovery_rate = {b: round(sum(v) / len(v), 3) if v else None for b, v in recovery.items()}
    miss_dist = defaultdict(dict)
    for (band, lie), cnt in miss_lies.items():
        miss_dist[band][lie] = cnt
    return {"miss_lie_distribution_by_band": dict(miss_dist), "scrambling_rate_by_band": recovery_rate}


# ---------- TASK 6: imperfect golf case finder ----------
def task6_imperfect_golf(records):
    out = {}
    for pc, label in PLAYERS_OF_INTEREST.items():
        rows = [r for r in records if r["player_code"] == pc]
        cases = {"favorable_good": [], "favorable_bad": [], "unfavorable_saved": [], "unfavorable_damage": []}
        for r in rows:
            favorable = r["fw_hit"] and r["approach_distance_yd"] <= 170
            good = r["score_to_par"] <= 0
            if favorable and good:
                cases["favorable_good"].append(r)
            elif favorable and not good:
                cases["favorable_bad"].append(r)
            elif not favorable and good:
                cases["unfavorable_saved"].append(r)
            elif not favorable and r["score_to_par"] >= 2:
                cases["unfavorable_damage"].append(r)
        out[pc] = {"label": label, "cases": {
            k: [{"round": r["round"], "tee_lie": r["tee_lie"], "landing_distance": r["landing_distance_yd"],
                 "approach_distance": r["approach_distance_yd"], "approach_lie": r["approach_lie"],
                 "putts": r["putts"], "strokes": r["strokes"], "score_to_par": r["score_to_par"],
                 "shot_state_sequence": r["shot_state_sequence"]} for r in v]
            for k, v in cases.items()
        }}
    return out


def main():
    con = sqlite3.connect(DB)
    by_pr = load_all(con)
    pins = round_pins(by_pr)
    tee, green = lateral_axis(by_pr)
    records, thresholds = build_full_chain(by_pr, pins, tee, green)

    t1 = task1_same_fairway(records)
    t2 = task2_approach_map(records)
    t3 = task3_pin_centered(records)
    t4 = task4_redteam_distance(records)
    t5 = {pc: task5_player_chain(con, pc, t4["quartile_cuts"]) for pc in PLAYERS_OF_INTEREST}
    t6 = task6_imperfect_golf(records)

    out = {
        "hole": HOLE, "par": PAR, "thresholds": thresholds,
        "task1_same_fairway_different_outcome": t1,
        "task2_approach_endpoint_map": t2,
        "task3_pin_centered": t3,
        "task4_redteam_distance_bands": t4,
        "task5_player_second_shot_chain": t5,
        "task6_imperfect_golf": t6,
    }
    (HERE / "hole12_master_template.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    with open(HERE / "neo_hole12_master_records.csv", "w", newline="", encoding="utf-8") as fh:
        cols = ["player_code", "player_name", "round", "tee_lie", "landing_distance_yd", "landing_zone",
                "approach_distance_yd", "approach_lie", "pin_distance_map", "gir", "putts", "strokes",
                "score_to_par", "score_bucket", "penalty_involved", "fw_hit", "unreliable_distance_state"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in records:
            w.writerow({c: r.get(c) for c in cols})

    print("=== TASK 1: same fairway, different outcome ===")
    for b, v in t1.items():
        print(f"  {b}: n={v['n']} avg_land={v['avg_landing_distance']} avg_app={v['avg_approach_distance']} GIR={v['GIR_pct']:.0%} avg_putts={v['avg_putts']} penalty%={v['penalty_pct']:.0%} lie_mix={v['approach_lie_mix']}")
    print("\n=== TASK 4: red-team distance bands ===")
    for b, v in sorted(t4["bands"].items()):
        print(f"  {b}: n={v['n']} GIR={v['GIR_pct']:.0%} Birdie+={v['BirdiePlus_pct']:.0%} Par={v['Par_pct']:.0%} Bogey={v['Bogey_pct']:.0%} Double+={v['DoublePlus_pct']:.0%} Penalty={v['Penalty_pct']:.0%} avg_stp={v['avg_score_to_par']:+.3f} FW%={v['fw_hit_pct_of_tee_shot']:.0%} round_mix={v['round_mix']}")
    print("\n=== TASK 3: pin-centered cells ===")
    for c, v in sorted(t3["cell_summary"].items()):
        print(f"  {c}: n={v['n']} rounds={v['rounds_present']} avg_stp={v['avg_score_to_par']:+.3f} GIR={v['GIR_pct']:.0%} Double+={v['DoublePlus_pct']:.0%} {'[LOW_SAMPLE]' if v['LOW_SAMPLE'] else ''}")
    print("\n=== TASK 6: imperfect golf case counts ===")
    for pc, v in t6.items():
        print(f"  {v['label']}: " + ", ".join(f"{k}={len(vv)}" for k, vv in v['cases'].items()))
    print("\nWrote hole12_master_template.json, neo_hole12_master_records.csv")


if __name__ == "__main__":
    main()
