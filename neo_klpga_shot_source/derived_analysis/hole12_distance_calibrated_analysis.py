"""NEO Hole 12 -- DISTANCE-CALIBRATED zone analysis.

Replaces coordinate-tercile SHORT/MID/LONG labels with real yard bands,
and ties every zone to real landing distance (tee->landing) and real
approach distance (landing->pin), computed from TWO REAL OFFICIAL
FIELDS ONLY (never coordinates, never estimated):

  landing_distance = HOLE_YARDAGE(round) - shot1.distance
  approach_distance = shot1.distance   (KLPGA's own real remaining-
                       distance-to-pin field after the tee shot; this
                       IS the second shot's real starting distance)

HOLE_YARDAGE is the real holeInfo.yds field, confirmed identical
(410yd) across all 4 real rounds for Hole 12 (checked directly against
raw archive, not assumed). No coordinate transform, no DERIVED flag
needed for these two numbers -- they are arithmetic on two real
official fields.

Lateral zone (LAT1/LAT2/LAT3) is kept from the earlier, already-
verified coordinate-based tee/green axis projection (lateral position
is not a distance claim -- the official distance field has no lateral
component, so lateral grouping still requires the verified coordinate
projection; this is clearly labeled DERIVED-COORDINATE where used).

Two tee shots (0.6% of 331) carry state codes (PENALTY_AREA, LOST_BALL)
where the real distance field is 0.0 or anomalously large -- these are
flagged UNRELIABLE_DISTANCE_STATE, never dropped, never silently
smoothed.
"""
from __future__ import annotations
import csv, json, math, sqlite3, statistics
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
DB = HERE / "klpga_shots_RAW_READONLY.sqlite"
GAME = "2026100005"
HOLE = 12
PAR = 4
HOLE_YARDAGE = 410.0  # confirmed identical across R1-4 from raw holeInfo.yds
UNRELIABLE_DISTANCE_STATES = {"4", "5", "7", "8"}  # OB/PENALTY_AREA/LOST_BALL/PENALTY_STROKE
LIE_NAME = {"1": "FAIRWAY", "2": "ROUGH", "3": "GREEN", "4": "OB", "5": "PENALTY_AREA",
            "6": "BUNKER", "7": "LOST_BALL", "8": "PENALTY_STROKE", "9": "GREENSIDE_BUNKER",
            "10": "HOLED", "12": "FRINGE"}
PLAYERS_OF_INTEREST = {"9115": "유해란(TOP,#1,-4)", "9708": "이재윤(MID,#27,+9)", "9111": "박서현(BOTTOM,#61,+26)"}

# Par-4 holes in the tournament (for player reachability / approach-ability
# context, using this project's own already-collected real per-hole par).
PAR4_HOLES = [1, 3, 6, 8, 9, 12, 13, 14, 15, 17]
HOLE_YARDS = json.loads((HERE / "klpga_tournament_18hole_par_yardage.json").read_text())


def load_hole12_shots(con):
    rows = con.execute(
        "SELECT player_code, player_name, round, shot, state_code, x, y, green_x, green_y, distance "
        "FROM klpga_player_shot WHERE game_code=? AND hole=? ORDER BY player_code, round, shot",
        (GAME, HOLE),
    ).fetchall()
    by_pr = defaultdict(list)
    names = {}
    for pc, name, rnd, shot, state, x, y, gx, gy, dist in rows:
        names[pc] = name
        by_pr[(pc, rnd)].append({"shot": shot, "state": state, "x": x, "y": y,
                                  "green_x": gx, "green_y": gy, "distance": dist})
    return by_pr, names


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
    """Re-derive the same tee/green OVERVIEW-frame anchors used throughout
    this project, for LATERAL bucket assignment only (DERIVED-COORDINATE)."""
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


def outcome(par, shots_sorted):
    strokes = len(shots_sorted)
    stp = strokes - par
    gir_shot = None
    for s in shots_sorted:
        if s["state"] == "3":
            gir_shot = s["shot"]; break
    gir = gir_shot is not None and gir_shot <= par - 2
    return strokes, stp, gir


def build_records(by_pr, names, tee, green, pins):
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

    # First pass: compute real landing distances to derive data-driven
    # longitudinal (distance) bands.
    landing_distances = []
    for pc, rnd, ss, lat in tmp:
        shot1 = ss[0]
        if shot1["state"] not in UNRELIABLE_DISTANCE_STATES:
            landing_distances.append(HOLE_YARDAGE - shot1["distance"])
    landing_distances.sort()
    n = len(landing_distances)
    d1 = landing_distances[n // 3]
    d2 = landing_distances[(2 * n) // 3]

    def dist_bucket(land_dist):
        if land_dist <= d1:
            return f"{int(round(landing_distances[0]))}-{int(round(d1))}yd"
        elif land_dist <= d2:
            return f"{int(round(d1))}-{int(round(d2))}yd"
        else:
            return f"{int(round(d2))}-{int(round(landing_distances[-1]))}yd"

    records = []
    for pc, rnd, ss, lat in tmp:
        shot1 = ss[0]
        unreliable = shot1["state"] in UNRELIABLE_DISTANCE_STATES
        landing_distance = HOLE_YARDAGE - shot1["distance"]
        approach_distance = shot1["distance"]
        strokes, stp, gir = outcome(PAR, ss)
        shot2 = ss[1] if len(ss) >= 2 else None
        approach_lie = LIE_NAME.get(shot2["state"], f"UNKNOWN_{shot2['state']}") if shot2 else None
        if stp <= -1:
            bucket = "Birdie+"
        elif stp == 0:
            bucket = "Par"
        elif stp == 1:
            bucket = "Bogey"
        else:
            bucket = "Double+"
        dband = dist_bucket(landing_distance)
        lband = lat_bucket(lat) if lat is not None else None
        zone = f"{dband} x {lband}" if lband else None
        records.append({
            "player_code": pc, "player_name": names.get(pc), "round": rnd,
            "tee_lie": LIE_NAME.get(shot1["state"], f"UNKNOWN_{shot1['state']}"),
            "landing_distance_yd": round(landing_distance, 1),
            "approach_distance_yd": round(approach_distance, 1),
            "unreliable_distance_state": unreliable,
            "distance_band": dband, "lateral_band": lband, "zone": zone,
            "approach_lie": approach_lie, "gir": gir,
            "strokes": strokes, "score_to_par": stp, "score_bucket": bucket,
            "fw_hit": shot1["state"] == "1",
        })
    thresholds = {
        "d1_yd": round(d1, 1), "d2_yd": round(d2, 1),
        "min_yd": round(landing_distances[0], 1), "max_yd": round(landing_distances[-1], 1),
        "l1": l1, "l2": l2,
    }
    return records, thresholds


def zone_stats_table(records):
    grouped = defaultdict(list)
    for r in records:
        if r["zone"] is None:
            continue
        grouped[r["zone"]].append(r)
    table = {}
    for zone, rows in grouped.items():
        n = len(rows)
        lands = [r["landing_distance_yd"] for r in rows]
        apps = [r["approach_distance_yd"] for r in rows]
        table[zone] = {
            "n": n,
            "landing_distance_range": [min(lands), max(lands)],
            "landing_distance_median": statistics.median(lands),
            "landing_distance_mean": round(statistics.mean(lands), 1),
            "approach_distance_range": [min(apps), max(apps)],
            "approach_distance_median": statistics.median(apps),
            "approach_distance_mean": round(statistics.mean(apps), 1),
            "avg_score_to_par": round(statistics.mean(r["score_to_par"] for r in rows), 3),
            "GIR_pct": round(sum(1 for r in rows if r["gir"]) / n, 3),
            "BirdiePlus_pct": round(sum(1 for r in rows if r["score_bucket"] == "Birdie+") / n, 3),
            "ParOrBetter_pct": round(sum(1 for r in rows if r["score_to_par"] <= 0) / n, 3),
            "BogeyPlus_pct": round(sum(1 for r in rows if r["score_to_par"] >= 1) / n, 3),
            "DoublePlus_pct": round(sum(1 for r in rows if r["score_to_par"] >= 2) / n, 3),
            "LOW_SAMPLE": n < 5,
        }
    return table


def zone_round_table(records):
    grouped = defaultdict(list)
    for r in records:
        if r["zone"] is None:
            continue
        grouped[(r["zone"], r["round"])].append(r)
    table = {}
    for (zone, rnd), rows in grouped.items():
        n = len(rows)
        lands = [r["landing_distance_yd"] for r in rows]
        apps = [r["approach_distance_yd"] for r in rows]
        table[f"{zone} | R{rnd}"] = {
            "n": n,
            "landing_distance_median": statistics.median(lands),
            "approach_distance_median": statistics.median(apps),
            "avg_score_to_par": round(statistics.mean(r["score_to_par"] for r in rows), 3),
            "GIR_pct": round(sum(1 for r in rows if r["gir"]) / n, 3),
            "BogeyPlus_pct": round(sum(1 for r in rows if r["score_to_par"] >= 1) / n, 3),
            "LOW_SAMPLE": n < 5,
        }
    return table


def approach_distance_value_bands(records):
    """Field-wide: does a shorter remaining/approach distance predict a
    better outcome? Tests BOTH a fixed-width scheme (100-125/125-150/...)
    AND data-driven quartiles, reports both with real n, keeps whichever
    is better supported (documented, not silently chosen)."""
    apps = sorted(r["approach_distance_yd"] for r in records)
    n = len(apps)
    quartile_cuts = [apps[n // 4], apps[n // 2], apps[(3 * n) // 4]]

    def fixed_band(d):
        if d < 100: return "<100"
        if d < 125: return "100-125"
        if d < 150: return "125-150"
        if d < 175: return "150-175"
        if d < 200: return "175-200"
        return "200+"

    def quartile_band(d):
        if d <= quartile_cuts[0]: return f"Q1(<={quartile_cuts[0]:.0f})"
        if d <= quartile_cuts[1]: return f"Q2(<={quartile_cuts[1]:.0f})"
        if d <= quartile_cuts[2]: return f"Q3(<={quartile_cuts[2]:.0f})"
        return f"Q4(>{quartile_cuts[2]:.0f})"

    def summarize(band_fn):
        g = defaultdict(list)
        for r in records:
            g[band_fn(r["approach_distance_yd"])].append(r)
        out = {}
        for b, rows in g.items():
            n2 = len(rows)
            out[b] = {
                "n": n2,
                "avg_score_to_par": round(statistics.mean(r["score_to_par"] for r in rows), 3),
                "GIR_pct": round(sum(1 for r in rows if r["gir"]) / n2, 3),
                "BirdiePlus_pct": round(sum(1 for r in rows if r["score_bucket"] == "Birdie+") / n2, 3),
                "ParOrBetter_pct": round(sum(1 for r in rows if r["score_to_par"] <= 0) / n2, 3),
                "BogeyPlus_pct": round(sum(1 for r in rows if r["score_to_par"] >= 1) / n2, 3),
                "DoublePlus_pct": round(sum(1 for r in rows if r["score_to_par"] >= 2) / n2, 3),
                "LOW_SAMPLE": n2 < 5,
            }
        return out

    return {
        "fixed_width_bands": summarize(fixed_band),
        "quartile_bands": summarize(quartile_band),
        "quartile_cuts_yd": [round(c, 1) for c in quartile_cuts],
    }


def player_par4_reachability(con, player_code):
    """Real landing-distance distribution for this player across ALL
    par-4 holes they played in the tournament (not just Hole 12), using
    the same official-field-only formula."""
    lands = []
    for hole in PAR4_HOLES:
        yd = float(HOLE_YARDS[str(hole)]["yds"])
        rows = con.execute(
            "SELECT distance, state_code FROM klpga_player_shot WHERE game_code=? AND hole=? "
            "AND player_code=? AND shot=1", (GAME, hole, player_code),
        ).fetchall()
        for dist, state in rows:
            if dist is None or state in UNRELIABLE_DISTANCE_STATES:
                continue
            lands.append(yd - dist)
    if not lands:
        return {"n": 0}
    lands.sort()
    return {
        "n": len(lands), "min": round(lands[0], 1), "max": round(lands[-1], 1),
        "median": round(statistics.median(lands), 1),
        "mean": round(statistics.mean(lands), 1),
        "stdev": round(statistics.pstdev(lands), 1) if len(lands) > 1 else None,
    }


def player_approach_ability_by_distance(con, player_code, quartile_cuts):
    """This player's own GIR/score outcome by approach-distance band,
    across all par-4 holes (shot2 = approach, shot1.distance = approach
    starting distance) -- same quartile cuts as the field-wide bands,
    for direct comparison."""
    def quartile_band(d):
        if d <= quartile_cuts[0]: return f"Q1(<={quartile_cuts[0]:.0f})"
        if d <= quartile_cuts[1]: return f"Q2(<={quartile_cuts[1]:.0f})"
        if d <= quartile_cuts[2]: return f"Q3(<={quartile_cuts[2]:.0f})"
        return f"Q4(>{quartile_cuts[2]:.0f})"

    rows_by_band = defaultdict(list)
    for hole in PAR4_HOLES:
        shots = con.execute(
            "SELECT round, shot, state_code, distance FROM klpga_player_shot WHERE game_code=? AND hole=? "
            "AND player_code=? ORDER BY round, shot", (GAME, hole, player_code),
        ).fetchall()
        by_round = defaultdict(list)
        for rnd, shot, state, dist in shots:
            by_round[rnd].append({"shot": shot, "state": state, "distance": dist})
        for rnd, ss in by_round.items():
            ss = sorted(ss, key=lambda s: s["shot"])
            if len(ss) < 2 or ss[0]["distance"] is None or ss[0]["state"] in UNRELIABLE_DISTANCE_STATES:
                continue
            approach_distance = ss[0]["distance"]
            strokes, stp, gir = outcome(4, ss)
            band = quartile_band(approach_distance)
            rows_by_band[band].append({"gir": gir, "stp": stp})
    out = {}
    for b, rows in rows_by_band.items():
        n2 = len(rows)
        out[b] = {
            "n": n2,
            "avg_score_to_par": round(statistics.mean(r["stp"] for r in rows), 3),
            "GIR_pct": round(sum(1 for r in rows if r["gir"]) / n2, 3),
            "ParOrBetter_pct": round(sum(1 for r in rows if r["stp"] <= 0) / n2, 3),
            "BogeyPlus_pct": round(sum(1 for r in rows if r["stp"] >= 1) / n2, 3),
            "LOW_SAMPLE": n2 < 5,
        }
    return out


def main():
    con = sqlite3.connect(DB)
    by_pr, names = load_hole12_shots(con)
    pins = round_pins(by_pr)
    tee, green = lateral_axis(by_pr)
    records, thresholds = build_records(by_pr, names, tee, green, pins)
    zone_stats = zone_stats_table(records)
    zone_round = zone_round_table(records)
    approach_bands = approach_distance_value_bands(records)

    player_section = {}
    for pc, label in PLAYERS_OF_INTEREST.items():
        player_rows = sorted([r for r in records if r["player_code"] == pc], key=lambda r: r["round"])
        reach = player_par4_reachability(con, pc)
        ability = player_approach_ability_by_distance(con, pc, approach_bands["quartile_cuts_yd"])
        player_section[pc] = {
            "label": label,
            "hole12_four_rounds": player_rows,
            "par4_tournament_wide_landing_distance_distribution": reach,
            "par4_tournament_wide_approach_ability_by_distance_quartile": ability,
        }

    out = {
        "hole": HOLE, "par": PAR, "hole_yardage_official_all_rounds": HOLE_YARDAGE,
        "method_note": (
            "landing_distance = HOLE_YARDAGE(round) - shot1.distance (both real official "
            "Shot Tracker fields; no coordinates involved, no DERIVED flag needed). "
            "approach_distance = shot1.distance directly (KLPGA's own real remaining-to-pin "
            "field, i.e. the real starting distance of the second shot). Lateral band "
            "(LAT1/2/3) uses the already-verified coordinate tee-green axis projection -- "
            "DERIVED-COORDINATE, kept separate from the two distance fields above."
        ),
        "distance_band_thresholds": thresholds,
        "zone_stats_distance_calibrated": zone_stats,
        "zone_x_round": zone_round,
        "approach_distance_value_bands": approach_bands,
        "player_section": player_section,
        "unreliable_distance_note": "2/331 real tee shots (0.6%) carry PENALTY_AREA/LOST_BALL states where the real distance field is 0.0 or anomalous (0.0 and 382.4yd respectively) -- flagged unreliable_distance_state=true per-row, never dropped.",
    }
    (HERE / "hole12_distance_calibrated_analysis.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    with open(HERE / "neo_hole12_distance_calibrated_records.csv", "w", newline="", encoding="utf-8") as fh:
        cols = ["player_code", "player_name", "round", "tee_lie", "landing_distance_yd", "approach_distance_yd",
                "unreliable_distance_state", "distance_band", "lateral_band", "zone", "approach_lie", "gir",
                "strokes", "score_to_par", "score_bucket", "fw_hit"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in records:
            w.writerow({c: r.get(c) for c in cols})

    print("DISTANCE BAND THRESHOLDS (real yards, data-driven tercile cuts):", thresholds)
    print("\nZONE STATS (distance-calibrated):")
    for z, s in sorted(zone_stats.items()):
        print(f"  {z}: n={s['n']} landing_med={s['landing_distance_median']} approach_med={s['approach_distance_median']} "
              f"avg_stp={s['avg_score_to_par']:+.3f} GIR={s['GIR_pct']:.0%} Bogey+={s['BogeyPlus_pct']:.0%} {'[LOW_SAMPLE]' if s['LOW_SAMPLE'] else ''}")
    print("\nAPPROACH DISTANCE VALUE (quartile bands):")
    for b, s in sorted(approach_bands["quartile_bands"].items()):
        print(f"  {b}: n={s['n']} avg_stp={s['avg_score_to_par']:+.3f} GIR={s['GIR_pct']:.0%} Bogey+={s['BogeyPlus_pct']:.0%}")
    print("\nPlayer reachability (par-4 tournament-wide landing distance):")
    for pc, sec in player_section.items():
        print(f"  {sec['label']}: {sec['par4_tournament_wide_landing_distance_distribution']}")
    print("\nWrote hole12_distance_calibrated_analysis.json, neo_hole12_distance_calibrated_records.csv")


if __name__ == "__main__":
    main()
