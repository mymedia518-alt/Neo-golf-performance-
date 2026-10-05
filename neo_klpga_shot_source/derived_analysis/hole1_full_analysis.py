"""NEO Hole 1 -- full analysis, same METHODOLOGY as Hole 12's MASTER
TEMPLATE, computed entirely fresh: no distance bands, zone boundaries,
or conclusions are copied from Hole 12. Only the procedure is reused.

Hole 1 = Blue Heron East Hole 1 (independently re-verified below, not
assumed from the Hole-12-era course-identity work beyond the already-
committed systematic 18-hole cross-check, which already covered H1).
Par 4, 402yd official (confirmed identical across all 4 real rounds).
"""
from __future__ import annotations
import csv, json, math, sqlite3, statistics
from pathlib import Path
from collections import defaultdict, Counter

HERE = Path(__file__).parent
DB = HERE / "klpga_shots_RAW_READONLY.sqlite"
GAME = "2026100005"
HOLE = 1
PAR = 4
HOLE_YARDAGE = 402.0  # confirmed identical R1-4 from raw holeInfo.yds -- real, not assumed
UNRELIABLE_DISTANCE_STATES = {"4", "5", "7", "8"}
LIE_NAME = {"1": "FAIRWAY", "2": "ROUGH", "3": "GREEN", "4": "OB", "5": "PENALTY_AREA",
            "6": "BUNKER", "7": "LOST_BALL", "8": "PENALTY_STROKE", "9": "GREENSIDE_BUNKER",
            "10": "HOLED", "12": "FRINGE"}
PLAYERS_OF_INTEREST = {"9115": "유해란(TOP,#1,-4)", "9708": "이재윤(MID,#27,+9)", "9111": "박서현(BOTTOM,#61,+26)"}
PAR4_HOLES = [1, 3, 6, 8, 9, 12, 13, 14, 15, 17]
players_meta = json.loads((HERE / "players_RAW_READONLY.json").read_text())["players"]
KNOWN_SOURCE_GAPS = {("8240", 2), ("10112", 2), ("11076", 2), ("11978", 2), ("8246", 2), ("9401", 1)}


# ---------- STEP 2: raw shot population / data integrity ----------
def step2_population(con):
    present = con.execute(
        "SELECT DISTINCT player_code, round FROM klpga_player_shot WHERE game_code=? AND hole=?", (GAME, HOLE)
    ).fetchall()
    present_set = {(pc, r) for pc, r in present}
    by_round = Counter(r for _, r in present)
    gaps = []
    for pc, info in players_meta.items():
        for r in info["rounds"]:
            if (pc, r) not in present_set:
                gaps.append({"player_code": pc, "player_name": info["player_name"], "round": r,
                             "matches_known_tournament_wide_gap": (pc, r) in KNOWN_SOURCE_GAPS})
    tee_shots = con.execute(
        "SELECT round, count(*) FROM klpga_player_shot WHERE game_code=? AND hole=? AND shot=1 GROUP BY round", (GAME, HOLE)
    ).fetchall()
    total_rows = con.execute("SELECT count(*) FROM klpga_player_shot WHERE game_code=? AND hole=?", (GAME, HOLE)).fetchone()[0]
    return {
        "player_rounds_by_round": dict(by_round), "total_tee_shots": sum(by_round.values()),
        "total_shot_rows": total_rows, "tee_shots_by_round": dict(tee_shots),
        "source_gaps_found": gaps,
        "all_gaps_match_known_tournament_pattern": all(g["matches_known_tournament_wide_gap"] for g in gaps),
    }


# ---------- STEP 2b: real pins (reuse the already-verified 72-hole audit) ----------
def step2_pins():
    audit = json.loads((HERE / "pin_placement_72hole_audit.json").read_text())
    pins = {}
    for r in (1, 2, 3, 4):
        key = f"R{r}H{HOLE}"
        entry = next((e for e in audit["per_round_hole_table"] if e["round"] == r and e["hole"] == HOLE), None)
        pins[r] = entry
    return pins


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


def round_pins_from_holed(by_pr):
    by_round = defaultdict(list)
    for (pc, rnd), shots in by_pr.items():
        for s in shots:
            if s["state"] == "10" and s["green_x"] is not None:
                by_round[rnd].append((s["green_x"], s["green_y"]))
    pins = {}
    for rnd, pts in sorted(by_round.items()):
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        pins[rnd] = {"pin_x": statistics.mean(xs), "pin_y": statistics.mean(ys),
                     "n": len(pts), "stdev_x": statistics.pstdev(xs), "stdev_y": statistics.pstdev(ys)}
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
    return tee, green, len(tee_pts), len(hole_pts)


def project_lateral(tee, green, pt):
    vx, vy = green[0] - tee[0], green[1] - tee[1]
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return None
    px, py = pt[0] - tee[0], pt[1] - tee[1]
    cross = px * vy - py * vx
    return cross / math.sqrt(L2)


def putts_count(ss):
    last_off_green = -1
    for i, s in enumerate(ss):
        if s["state"] not in ("3", "10"):
            last_off_green = i
    return len(ss) - (last_off_green + 1)


# ---------- STEP 3+4: real tee-shot distance distribution + landing location x distance ----------
def build_records(by_pr, pins, tee, green):
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

    reliable = sorted(HOLE_YARDAGE - ss[0]["distance"] for _, _, ss, _ in tmp if ss[0]["state"] not in UNRELIABLE_DISTANCE_STATES)
    n = len(reliable)
    # Hole-1-specific quantiles -- computed fresh, compared below against
    # natural breaks before committing to tercile cuts (STEP 3 requirement).
    deciles = [reliable[int(n * q)] for q in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)]
    d1, d2 = reliable[n // 3], reliable[(2 * n) // 3]

    def dist_band(land):
        if land <= d1: return f"{int(round(reliable[0]))}-{int(round(d1))}yd"
        if land <= d2: return f"{int(round(d1))}-{int(round(d2))}yd"
        return f"{int(round(d2))}-{int(round(reliable[-1]))}yd"

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
        records.append({
            "player_code": pc, "player_name": players_meta.get(pc, {}).get("player_name", pc), "round": rnd,
            "tee_lie": LIE_NAME.get(shot1["state"], f"UNKNOWN_{shot1['state']}"),
            "landing_distance_yd": round(landing_distance, 1),
            "landing_zone": f"{dist_band(landing_distance)} x {lat_bucket(lat)}" if lat is not None else None,
            "distance_band": dist_band(landing_distance) if lat is not None else None,
            "lateral_band": lat_bucket(lat) if lat is not None else None,
            "approach_distance_yd": round(approach_distance, 1),
            "unreliable_distance_state": unreliable,
            "round_pin_x": pin["pin_x"] if pin else None, "round_pin_y": pin["pin_y"] if pin else None,
            "approach_endpoint_green_x": shot2["green_x"] if shot2 else None,
            "approach_endpoint_green_y": shot2["green_y"] if shot2 else None,
            "approach_lie": approach_lie, "gir": gir,
            "pin_dx_map": pin_dx, "pin_dy_map": pin_dy, "pin_distance_map": pin_dist_map,
            "fw_hit": shot1["state"] == "1",
            "putts": putts, "strokes": strokes, "score_to_par": stp, "score_bucket": bucket,
            "penalty_involved": penalty,
            "shot_state_sequence": [s["state"] for s in ss],
            "shot_distance_sequence": [s["distance"] for s in ss],
        })
    thresholds = {"d1": d1, "d2": d2, "l1": l1, "l2": l2, "deciles": deciles, "min": reliable[0], "max": reliable[-1]}
    return records, thresholds


def zone_stats_table(records):
    grouped = defaultdict(list)
    for r in records:
        if r["landing_zone"] is None:
            continue
        grouped[r["landing_zone"]].append(r)
    table = {}
    for zone, rows in grouped.items():
        n = len(rows)
        reliable = [r for r in rows if not r["unreliable_distance_state"]]
        n_unreliable = n - len(reliable)
        lands = [r["landing_distance_yd"] for r in reliable] or [r["landing_distance_yd"] for r in rows]
        apps = [r["approach_distance_yd"] for r in reliable] or [r["approach_distance_yd"] for r in rows]
        table[zone] = {
            "n": n, "n_unreliable_excluded_from_range": n_unreliable,
            "landing_distance_range": [min(lands), max(lands)], "landing_distance_median": statistics.median(lands),
            "approach_distance_range": [min(apps), max(apps)], "approach_distance_median": statistics.median(apps),
            "FW_pct": round(sum(1 for r in rows if r["tee_lie"] == "FAIRWAY") / n, 3),
            "Rough_pct": round(sum(1 for r in rows if r["tee_lie"] == "ROUGH") / n, 3),
            "Bunker_pct": round(sum(1 for r in rows if r["tee_lie"] == "BUNKER") / n, 3),
            "Penalty_pct": round(sum(1 for r in rows if r["tee_lie"] in ("OB", "PENALTY_AREA", "LOST_BALL", "PENALTY_STROKE")) / n, 3),
            "GIR_pct": round(sum(1 for r in rows if r["gir"]) / n, 3),
            "BirdiePlus_pct": round(sum(1 for r in rows if r["score_bucket"] == "Birdie+") / n, 3),
            "Par_pct": round(sum(1 for r in rows if r["score_bucket"] == "Par") / n, 3),
            "BogeyPlus_pct": round(sum(1 for r in rows if r["score_to_par"] >= 1) / n, 3),
            "DoublePlus_pct": round(sum(1 for r in rows if r["score_to_par"] >= 2) / n, 3),
            "avg_score_to_par": round(statistics.mean(r["score_to_par"] for r in rows), 3),
            "LOW_SAMPLE": n < 5,
        }
    return table


# ---------- STEP 5: fairway confounding test ----------
def fairway_confound_test(records):
    out = {}
    for lat in ("LAT1", "LAT2", "LAT3"):
        fw_rows = [r for r in records if r["lateral_band"] == lat and r["fw_hit"]]
        miss_rows = [r for r in records if r["lateral_band"] == lat and not r["fw_hit"]]
        def summarize(rows):
            if not rows: return {"n": 0}
            n = len(rows)
            return {"n": n, "avg_score_to_par": round(statistics.mean(r["score_to_par"] for r in rows), 3),
                    "GIR_pct": round(sum(1 for r in rows if r["gir"]) / n, 3), "LOW_SAMPLE": n < 5}
        out[lat] = {"FW_hit_only": summarize(fw_rows), "FW_miss_only": summarize(miss_rows)}
    return out


# ---------- STEP 7: approach distance value (own thresholds) ----------
def approach_distance_value(records):
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
            "n": n2, "GIR_pct": round(sum(1 for r in rows if r["gir"]) / n2, 3),
            "BirdiePlus_pct": round(sum(1 for r in rows if r["score_bucket"] == "Birdie+") / n2, 3),
            "Par_pct": round(sum(1 for r in rows if r["score_bucket"] == "Par") / n2, 3),
            "Bogey_pct": round(sum(1 for r in rows if r["score_bucket"] == "Bogey") / n2, 3),
            "DoublePlus_pct": round(sum(1 for r in rows if r["score_bucket"] == "Double+") / n2, 3),
            "Penalty_pct": round(sum(1 for r in rows if r["penalty_involved"]) / n2, 3),
            "avg_score_to_par": round(statistics.mean(r["score_to_par"] for r in rows), 3),
            "fw_hit_pct_of_tee_shot": round(sum(1 for r in rows if r["fw_hit"]) / n2, 3),
            "round_mix": dict(Counter(r["round"] for r in rows)),
        }
    return {"quartile_cuts": [round(c, 1) for c in cuts], "bands": out}


# ---------- STEP 8: pin-centered map ----------
def pin_centered(records):
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
            "n": n2, "rounds_present": sorted(set(r["round"] for r in rows)),
            "GIR_pct": round(sum(1 for r in rows if r["gir"]) / n2, 3),
            "avg_score_to_par": round(statistics.mean(r["score_to_par"] for r in rows), 3),
            "DoublePlus_pct": round(sum(1 for r in rows if r["score_to_par"] >= 2) / n2, 3),
            "LOW_SAMPLE": n2 < 5,
        }
    points = [{"pc": r["player_code"], "round": r["round"], "dx": r["pin_dx_map"], "dy": r["pin_dy_map"],
               "ring": ring(r["pin_distance_map"]), "quad": quad(r["pin_dx_map"], r["pin_dy_map"]),
               "score_bucket": r["score_bucket"], "gir": r["gir"]} for r in pts]
    return {"ring_thresholds_map_units": {"t1": t1, "t2": t2}, "cell_summary": summary, "points": points}


# ---------- STEP 9: same condition, different outcome ----------
def same_condition_census(records):
    cats = defaultdict(list)
    for r in records:
        prefix = "FW HIT" if r["fw_hit"] else "FW MISS"
        cats[f"{prefix} -> {r['score_bucket']}"].append(r)
    out = {}
    for label, rows in sorted(cats.items()):
        rep = rows[0]
        out[label] = {"n": len(rows), "representative": {
            "player": rep["player_name"], "round": rep["round"], "landing_distance": rep["landing_distance_yd"],
            "approach_distance": rep["approach_distance_yd"], "approach_lie": rep["approach_lie"],
            "shot_state_sequence": rep["shot_state_sequence"], "strokes": rep["strokes"], "score_to_par": rep["score_to_par"]}}
    return out


# ---------- STEP 10: big-number mechanism elimination ----------
def big_number_mechanism(records):
    bad = [r for r in records if r["score_to_par"] >= 1]
    stages = {
        "tee_lie_mix": dict(Counter(r["tee_lie"] for r in bad)),
        "approach_lie_mix": dict(Counter(r["approach_lie"] for r in bad)),
        "gir_rate_among_bad": round(sum(1 for r in bad if r["gir"]) / len(bad), 3),
        "penalty_rate_among_bad": round(sum(1 for r in bad if r["penalty_involved"]) / len(bad), 3),
        "avg_putts_among_bad": round(statistics.mean(r["putts"] for r in bad), 2),
    }
    double_plus = [r for r in records if r["score_to_par"] >= 2]
    stages["double_plus_n"] = len(double_plus)
    stages["double_plus_tee_lie_mix"] = dict(Counter(r["tee_lie"] for r in double_plus))
    stages["double_plus_approach_lie_mix"] = dict(Counter(r["approach_lie"] for r in double_plus))
    stages["double_plus_penalty_rate"] = round(sum(1 for r in double_plus if r["penalty_involved"]) / len(double_plus), 3) if double_plus else None
    stages["double_plus_chains"] = [{"player": r["player_name"], "round": r["round"], "tee_lie": r["tee_lie"],
                                      "landing_distance": r["landing_distance_yd"], "approach_lie": r["approach_lie"],
                                      "shot_state_sequence": r["shot_state_sequence"], "strokes": r["strokes"]} for r in double_plus]
    return stages


# ---------- STEP 12/13: imperfect golf per player ----------
def imperfect_golf(records, apps_cuts):
    out = {}
    threshold = apps_cuts[2]  # Q3 upper bound -- Hole-1-specific, not borrowed from Hole 12's 170yd
    for pc, label in PLAYERS_OF_INTEREST.items():
        rows = [r for r in records if r["player_code"] == pc]
        cases = {"favorable_good": [], "favorable_bad": [], "unfavorable_saved": [], "unfavorable_damage": []}
        for r in rows:
            favorable = r["fw_hit"] and r["approach_distance_yd"] <= threshold
            good = r["score_to_par"] <= 0
            if favorable and good: cases["favorable_good"].append(r)
            elif favorable and not good: cases["favorable_bad"].append(r)
            elif not favorable and good: cases["unfavorable_saved"].append(r)
            elif not favorable and r["score_to_par"] >= 2: cases["unfavorable_damage"].append(r)
        out[pc] = {"label": label, "favorable_threshold_approach_yd": threshold, "cases": {
            k: [{"round": r["round"], "tee_lie": r["tee_lie"], "landing_distance": r["landing_distance_yd"],
                 "approach_distance": r["approach_distance_yd"], "approach_lie": r["approach_lie"],
                 "putts": r["putts"], "strokes": r["strokes"], "score_to_par": r["score_to_par"],
                 "shot_state_sequence": r["shot_state_sequence"]} for r in v] for k, v in cases.items()}}
    return out


def player_par4_reachability(con, player_code):
    lands = []
    for hole in PAR4_HOLES:
        yd = float(json.loads((HERE / "klpga_tournament_18hole_par_yardage.json").read_text())[str(hole)]["yds"])
        rows = con.execute(
            "SELECT distance, state_code FROM klpga_player_shot WHERE game_code=? AND hole=? AND player_code=? AND shot=1",
            (GAME, hole, player_code)).fetchall()
        for dist, state in rows:
            if dist is None or state in UNRELIABLE_DISTANCE_STATES: continue
            lands.append(yd - dist)
    if not lands: return {"n": 0}
    lands.sort()
    return {"n": len(lands), "min": round(lands[0], 1), "max": round(lands[-1], 1),
            "median": round(statistics.median(lands), 1), "mean": round(statistics.mean(lands), 1),
            "stdev": round(statistics.pstdev(lands), 1) if len(lands) > 1 else None}


def player_approach_ability(con, pc, cuts):
    def qband(d):
        if d <= cuts[0]: return f"Q1(<={cuts[0]:.0f})"
        if d <= cuts[1]: return f"Q2(<={cuts[1]:.0f})"
        if d <= cuts[2]: return f"Q3(<={cuts[2]:.0f})"
        return f"Q4(>{cuts[2]:.0f})"
    bands = defaultdict(list)
    for hole in PAR4_HOLES:
        shots = con.execute("SELECT round, shot, state_code, distance FROM klpga_player_shot WHERE game_code=? AND hole=? AND player_code=? ORDER BY round, shot", (GAME, hole, pc)).fetchall()
        by_round = defaultdict(list)
        for rnd, shot, state, dist in shots:
            by_round[rnd].append({"shot": shot, "state": state, "distance": dist})
        for rnd, ss in by_round.items():
            ss = sorted(ss, key=lambda s: s["shot"])
            if len(ss) < 2 or ss[0]["distance"] is None or ss[0]["state"] in UNRELIABLE_DISTANCE_STATES: continue
            ad = ss[0]["distance"]
            gir_shot = None
            for s in ss:
                if s["state"] == "3": gir_shot = s["shot"]; break
            gir = gir_shot is not None and gir_shot <= 2
            stp = len(ss) - 4
            bands[qband(ad)].append({"gir": gir, "stp": stp})
    out = {}
    for b, rows in bands.items():
        n2 = len(rows)
        out[b] = {"n": n2, "avg_score_to_par": round(statistics.mean(r["stp"] for r in rows), 3),
                   "GIR_pct": round(sum(1 for r in rows if r["gir"]) / n2, 3), "LOW_SAMPLE": n2 < 5}
    return out


def main():
    con = sqlite3.connect(DB)
    pop = step2_population(con)
    pins_audit = step2_pins()
    by_pr = load_all(con)
    pins = round_pins_from_holed(by_pr)
    tee, green, n_tee, n_hole = lateral_axis(by_pr)
    records, thresholds = build_records(by_pr, pins, tee, green)

    zone_stats = zone_stats_table(records)
    confound = fairway_confound_test(records)
    approach_value = approach_distance_value(records)
    pin_map = pin_centered(records)
    same_cond = same_condition_census(records)
    big_number = big_number_mechanism(records)
    imperfect = imperfect_golf(records, approach_value["quartile_cuts"])
    player_reach = {pc: player_par4_reachability(con, pc) for pc in PLAYERS_OF_INTEREST}
    player_ability = {pc: player_approach_ability(con, pc, approach_value["quartile_cuts"]) for pc in PLAYERS_OF_INTEREST}

    out = {
        "hole": HOLE, "par": PAR, "hole_yardage_official_all_rounds": HOLE_YARDAGE,
        "step2_population": pop, "step2_pins_72hole_audit_subset": pins_audit,
        "step3_thresholds": thresholds, "tee_green_anchor_n": {"tee": n_tee, "green": n_hole},
        "step4_zone_stats": zone_stats,
        "step5_fairway_confound_test": confound,
        "step7_approach_distance_value": approach_value,
        "step8_pin_centered": pin_map,
        "step9_same_condition_census": same_cond,
        "step10_big_number_mechanism": big_number,
        "step12_player_reachability": player_reach,
        "step12_player_approach_ability": player_ability,
        "step13_imperfect_golf": imperfect,
    }
    (HERE / "hole1_full_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    with open(HERE / "neo_hole1_records.csv", "w", newline="", encoding="utf-8") as fh:
        cols = ["player_code", "player_name", "round", "tee_lie", "landing_distance_yd", "landing_zone",
                "approach_distance_yd", "approach_lie", "pin_distance_map", "gir", "putts", "strokes",
                "score_to_par", "score_bucket", "penalty_involved", "fw_hit", "unreliable_distance_state"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in records:
            w.writerow({c: r.get(c) for c in cols})

    print("=== STEP 2: population ===", pop)
    print("\n=== STEP 2b: pins ===")
    for r, p in pins.items():
        print(f"  R{r}: ({p['pin_x']:.1f},{p['pin_y']:.1f}) n={p['n']} stdev=({p['stdev_x']:.3f},{p['stdev_y']:.3f})")
    print("\n=== STEP 3: distance thresholds (real yards) ===", thresholds)
    print("\n=== STEP 4: zone stats ===")
    for z, s in sorted(zone_stats.items()):
        print(f"  {z}: n={s['n']} FW={s['FW_pct']:.0%} avg_stp={s['avg_score_to_par']:+.3f} GIR={s['GIR_pct']:.0%} Bogey+={s['BogeyPlus_pct']:.0%}")
    print("\n=== STEP 5: fairway confound ===")
    for lat, v in confound.items():
        print(f"  {lat}: FW_hit={v['FW_hit_only']} FW_miss={v['FW_miss_only']}")
    print("\n=== STEP 7: approach distance value ===")
    for b, v in sorted(approach_value["bands"].items()):
        print(f"  {b}: n={v['n']} GIR={v['GIR_pct']:.0%} avg_stp={v['avg_score_to_par']:+.3f} FW%={v['fw_hit_pct_of_tee_shot']:.0%} round_mix={v['round_mix']}")
    print("\n=== STEP 8: pin-centered cells ===")
    for c, v in sorted(pin_map["cell_summary"].items()):
        print(f"  {c}: n={v['n']} rounds={v['rounds_present']} avg_stp={v['avg_score_to_par']:+.3f} GIR={v['GIR_pct']:.0%}")
    print("\n=== STEP 9: same condition census ===")
    for label, v in same_cond.items():
        print(f"  {label}: n={v['n']}")
    print("\n=== STEP 10: big number mechanism ===", {k: v for k, v in big_number.items() if k != "double_plus_chains"})
    print("\n=== STEP 12: player reachability ===")
    for pc, v in player_reach.items():
        print(f"  {PLAYERS_OF_INTEREST[pc]}: {v}")
    print("\n=== STEP 13: imperfect golf counts ===")
    for pc, v in imperfect.items():
        print(f"  {v['label']}: " + ", ".join(f"{k}={len(vv)}" for k, vv in v['cases'].items()))
    print("\nWrote hole1_full_analysis.json, neo_hole1_records.csv")


if __name__ == "__main__":
    main()
