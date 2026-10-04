"""NEO Course Management -- ELIMINATION methodology for DEFEND holes
6, 8, 10, 12. No strategy is assumed correct up front; candidates are
generated, then eliminated by real outcome data.

COORDINATE SYSTEM NOTE (verified empirically, not assumed):
pp_x/pp_y (per-shot landing coordinates) form a real, internally
consistent hole-local coordinate system -- every player's shot
sequence for a given (round, hole) converges toward the same
hole-out point regardless of path (verified by inspecting raw shot
sequences directly). baseHoleInfo's bi_sx/sy/gx/gy are in a visibly
different numeric range/scale and are NOT used here as geometry --
they are a separate map-UI coordinate system (OBSERVED fact, not
compatible with pp_x/pp_y; using them together would be exactly the
"근거 없는 임의 생성" this analysis must avoid).

Tee and green/hole anchors are therefore derived empirically:
  TEE anchor  = centroid of all real shot-1 (x,y) for that hole
  GREEN anchor = centroid of all real final-shot (state_code=="10",
                 i.e. HOLED) (x,y) for that hole
Both are OBSERVED, not geometry-assumed.

Shot-shape (DRAW/FADE/STRAIGHT) is never asserted as what a player
actually played -- Shot Tracker carries no ball-flight-shape field.
Only which geometric zone a landing falls into is OBSERVED; which
shot shapes COULD reach that zone is a candidate hypothesis, kept
separate and labeled INFERRED/UNKNOWN as appropriate.
"""
from __future__ import annotations
import csv, json, sqlite3, statistics
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
DB = HERE / "klpga_shots_RAW_READONLY.sqlite"
GAME = "2026100005"
DEFEND_HOLES = [6, 8, 10, 12]
PAR_BY_HOLE = {6: 4, 8: 4, 10: 5, 12: 4}
PLAYERS = {"9115": "유해란(TOP,#1)", "9708": "이재윤(MID,#27)", "9111": "박서현(BOTTOM,#61)"}
LOW_SAMPLE_N = 5


def load_all_shots(con, hole):
    rows = con.execute(
        "SELECT player_code, round, shot, state_code, x, y, distance FROM klpga_player_shot "
        "WHERE game_code=? AND hole=? ORDER BY player_code, round, shot",
        (GAME, hole),
    ).fetchall()
    by_player_round = defaultdict(list)
    for pc, rnd, shot, state, x, y, dist in rows:
        by_player_round[(pc, rnd)].append({"shot": shot, "state": state, "x": x, "y": y, "distance": dist})
    return by_player_round


def hole_outcome(par, shots):
    shots_sorted = sorted(shots, key=lambda s: s["shot"])
    strokes = len(shots_sorted)
    score_to_par = strokes - par
    gir_shot = None
    for s in shots_sorted:
        if s["state"] == "3":
            gir_shot = s["shot"]
            break
    gir = gir_shot is not None and gir_shot <= par - 2
    return {"strokes": strokes, "score_to_par": score_to_par, "gir": gir, "par_or_better": score_to_par <= 0}


def derive_anchors(by_player_round, hole):
    tee_pts = []
    hole_pts = []
    for key, shots in by_player_round.items():
        shots_sorted = sorted(shots, key=lambda s: s["shot"])
        if shots_sorted and shots_sorted[0]["x"] is not None:
            tee_pts.append((shots_sorted[0]["x"], shots_sorted[0]["y"]))
        for s in shots_sorted:
            if s["state"] == "10" and s["x"] is not None:
                hole_pts.append((s["x"], s["y"]))
                break
    tee = (statistics.mean(p[0] for p in tee_pts), statistics.mean(p[1] for p in tee_pts))
    green = (statistics.mean(p[0] for p in hole_pts), statistics.mean(p[1] for p in hole_pts))
    return tee, green, len(tee_pts), len(hole_pts)


def project(tee, green, pt):
    """Project pt onto the tee->green line (derived from real data).
    Returns (frac_down_line, lateral_offset). frac_down_line in [~0,~1]
    roughly spans tee(0) to green(1) -- NOT clamped, can exceed range.
    lateral_offset sign is NOT assigned a left/right meaning (UNKNOWN
    without a verified compass/course-orientation reference)."""
    import math
    vx, vy = green[0] - tee[0], green[1] - tee[1]
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return None, None
    px, py = pt[0] - tee[0], pt[1] - tee[1]
    frac = (px * vx + py * vy) / L2
    # lateral = perpendicular distance, signed (sign is a neutral axis convention only)
    cross = px * vy - py * vx
    lateral = cross / math.sqrt(L2)
    return frac, lateral


def analyze_tee_shots(hole, by_player_round, par):
    tee, green, n_tee, n_hole = derive_anchors(by_player_round, hole)

    tee_shot_records = []
    for (pc, rnd), shots in by_player_round.items():
        shots_sorted = sorted(shots, key=lambda s: s["shot"])
        if not shots_sorted or shots_sorted[0]["x"] is None:
            continue
        t1 = shots_sorted[0]
        frac, lateral = project(tee, green, (t1["x"], t1["y"]))
        outcome = hole_outcome(par, shots_sorted)
        tee_shot_records.append({
            "player_code": pc, "round": rnd, "frac_down_line": frac, "lateral_offset": lateral,
            "tee_state": t1["state"], "tee_distance": t1["distance"], **outcome,
        })

    # Candidate zones: longitudinal thirds (SHORT/MID/LONG -- unambiguous,
    # not a left/right claim) x lateral thirds (L1/L2/L3 -- neutral labels,
    # direction not asserted).
    fracs = sorted(r["frac_down_line"] for r in tee_shot_records if r["frac_down_line"] is not None)
    laterals = sorted(r["lateral_offset"] for r in tee_shot_records if r["lateral_offset"] is not None)
    if not fracs or not laterals:
        return {"hole": hole, "error": "insufficient coordinate data"}
    f1, f2 = fracs[len(fracs) // 3], fracs[(2 * len(fracs)) // 3]
    l1, l2 = laterals[len(laterals) // 3], laterals[(2 * len(laterals)) // 3]

    def longitudinal_bucket(frac):
        return "SHORT" if frac <= f1 else ("MID" if frac <= f2 else "LONG")

    def lateral_bucket(lat):
        return "LAT1" if lat <= l1 else ("LAT2" if lat <= l2 else "LAT3")

    zones = defaultdict(list)
    for r in tee_shot_records:
        if r["frac_down_line"] is None:
            continue
        zone = f"{longitudinal_bucket(r['frac_down_line'])}-{lateral_bucket(r['lateral_offset'])}"
        zones[zone].append(r)

    zone_stats = []
    for zone, records in sorted(zones.items()):
        n = len(records)
        fw_n = sum(1 for r in records if r["tee_state"] == "1")
        rough_n = sum(1 for r in records if r["tee_state"] == "2")
        bunker_n = sum(1 for r in records if r["tee_state"] == "6")
        penalty_n = sum(1 for r in records if r["tee_state"] in ("4", "5", "7", "8"))
        gir_n = sum(1 for r in records if r["gir"])
        par_or_better_n = sum(1 for r in records if r["par_or_better"])
        bogey_plus_n = sum(1 for r in records if r["score_to_par"] >= 1)
        avg_stp = statistics.mean(r["score_to_par"] for r in records)
        zone_stats.append({
            "hole": hole, "zone": zone, "n": n,
            "FW_pct": fw_n / n, "Rough_pct": rough_n / n, "Bunker_pct": bunker_n / n, "Penalty_pct": penalty_n / n,
            "GIR_pct": gir_n / n, "ParOrBetter_pct": par_or_better_n / n, "BogeyPlus_pct": bogey_plus_n / n,
            "avg_score_to_par": avg_stp, "LOW_SAMPLE": n < LOW_SAMPLE_N,
        })

    # ELIMINATION: start with all zones with n>=LOW_SAMPLE_N as candidates.
    candidates = [z for z in zone_stats if not z["LOW_SAMPLE"]]
    eliminated = []
    survivors = list(candidates)

    # Elimination rule 1: BogeyPlus_pct meaningfully worse than the best
    # (>10pp above the minimum observed) -- documented, not post-hoc tuned
    # per hole (same rule applied to all holes).
    if survivors:
        min_bogey = min(z["BogeyPlus_pct"] for z in survivors)
        still = []
        for z in survivors:
            if z["BogeyPlus_pct"] > min_bogey + 0.10:
                eliminated.append({**z, "reason": f"BogeyPlus_pct {z['BogeyPlus_pct']:.1%} exceeds best zone's {min_bogey:.1%} by >10pp"})
            else:
                still.append(z)
        survivors = still

    # Elimination rule 2: avg_score_to_par meaningfully worse than the best
    if survivors:
        min_avg = min(z["avg_score_to_par"] for z in survivors)
        still = []
        for z in survivors:
            if z["avg_score_to_par"] > min_avg + 0.15:
                eliminated.append({**z, "reason": f"avg_score_to_par {z['avg_score_to_par']:+.3f} exceeds best zone's {min_avg:+.3f} by >0.15 strokes"})
            else:
                still.append(z)
        survivors = still

    recommended = min(survivors, key=lambda z: z["avg_score_to_par"]) if survivors else None
    low_sample_zones = [z for z in zone_stats if z["LOW_SAMPLE"]]

    return {
        "hole": hole, "par": par,
        "tee_anchor_observed": tee, "green_anchor_observed": green,
        "tee_anchor_n": n_tee, "green_anchor_n": n_hole,
        "all_zone_stats": zone_stats,
        "candidates_considered": [z["zone"] for z in candidates],
        "eliminated": eliminated,
        "low_sample_excluded": [z["zone"] for z in low_sample_zones],
        "survivors": [z["zone"] for z in survivors],
        "recommended_zone": recommended,
        "tee_shot_records": tee_shot_records,
    }


def main():
    con = sqlite3.connect(DB)
    all_results = {}
    for hole in DEFEND_HOLES:
        by_player_round = load_all_shots(con, hole)
        result = analyze_tee_shots(hole, by_player_round, PAR_BY_HOLE[hole])
        all_results[hole] = result
        print(f"\n{'='*80}\nHOLE {hole} (par {PAR_BY_HOLE[hole]})\n{'='*80}")
        print(f"TEE anchor (observed, n={result['tee_anchor_n']}): {result['tee_anchor_observed']}")
        print(f"GREEN/HOLE anchor (observed, n={result['green_anchor_n']}): {result['green_anchor_observed']}")
        print("Zone stats:")
        for z in result["all_zone_stats"]:
            print(f"  {z['zone']:16s} n={z['n']:3d} FW={z['FW_pct']:.0%} Rough={z['Rough_pct']:.0%} Bunker={z['Bunker_pct']:.0%} "
                  f"Penalty={z['Penalty_pct']:.0%} GIR={z['GIR_pct']:.0%} ParOrBetter={z['ParOrBetter_pct']:.0%} "
                  f"Bogey+={z['BogeyPlus_pct']:.0%} avg_stp={z['avg_score_to_par']:+.3f} {'[LOW_SAMPLE]' if z['LOW_SAMPLE'] else ''}")
        print(f"Eliminated: {[(e['zone'], e['reason']) for e in result['eliminated']]}")
        print(f"Survivors: {result['survivors']}")
        print(f"RECOMMENDED: {result['recommended_zone']['zone'] if result['recommended_zone'] else None}")

    # Save full detail (excluding raw per-shot records from the printed
    # summary file to keep it readable; full per-shot kept in a separate CSV)
    summary_for_json = {}
    tee_shot_rows = []
    for hole, r in all_results.items():
        summary_for_json[hole] = {k: v for k, v in r.items() if k != "tee_shot_records"}
        for rec in r["tee_shot_records"]:
            tee_shot_rows.append({"hole": hole, **rec})

    (HERE / "course_management_elimination.json").write_text(
        json.dumps(summary_for_json, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    with open(HERE / "neo_tee_shot_zone_records.csv", "w", newline="", encoding="utf-8") as fh:
        cols = ["hole", "player_code", "round", "frac_down_line", "lateral_offset", "tee_state",
                "tee_distance", "strokes", "score_to_par", "gir", "par_or_better"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in tee_shot_rows:
            w.writerow({c: r.get(c) for c in cols})

    with open(HERE / "neo_tee_zone_elimination_summary.csv", "w", newline="", encoding="utf-8") as fh:
        cols = ["hole", "zone", "n", "FW_pct", "Rough_pct", "Bunker_pct", "Penalty_pct", "GIR_pct",
                "ParOrBetter_pct", "BogeyPlus_pct", "avg_score_to_par", "LOW_SAMPLE"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for hole, r in all_results.items():
            for z in r["all_zone_stats"]:
                w.writerow({c: z.get(c) for c in cols})

    print("\nWrote course_management_elimination.json, neo_tee_shot_zone_records.csv, neo_tee_zone_elimination_summary.csv")


if __name__ == "__main__":
    main()
