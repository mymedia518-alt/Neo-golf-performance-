"""NEO Hole 12 PIN-CORRECTED analysis -- replaces green_side_miss_analysis.json
(DISCARDED, not fixed in place -- it assumed the pin sat at coordinate origin
(0,0), which real per-round HOLED-shot convergence disproves).

Real per-round pin = (green_x, green_y) of every player's HOLED (state_code
"10") shot for that (round, hole). Verified elsewhere (pin_placement_72hole_
audit.json) to have zero variance across all real players within a round --
this is definitional (ball-in-hole IS the pin), not an assumption.

green_x/green_y are populated on EVERY shot (not only approach shots) and
converge toward the round's pin as the ball approaches it -- confirmed by
inspecting real full shot sequences. This lets every shot's position be
expressed relative to the REAL round-specific pin, with no coordinate
assumption.

Chain built per player-round (Hole 12 is a flat par-4, so shot 1 = tee,
shot 2 = approach -- this is an observed sequence position, not an assumed
"intended" shot):
  TEE LANDING (shot1: x,y,state,remaining-distance)
  -> LIE (shot1 state_code)
  -> REMAINING DISTANCE (shot1's own real "distance" field -- KLPGA's own
     distance-to-pin value, not computed/estimated)
  -> ROUND PIN (real, round-specific, from HOLED convergence)
  -> APPROACH ENDPOINT (shot2: green_x,green_y,state,distance)
  -> PIN-RELATIVE VECTOR (dx,dy,distance -- computed from green_x/y minus
     the round pin, cross-checked against shot2's own real distance field)
  -> GIR/MISS (literal def: shot2 state=="3" at shot_number 2 <= par-2)
  -> RECOVERY (shots 3..N-1)
  -> FINAL SCORE (strokes - par)

left/right, front/back, short-side/long-side are NEVER assigned: the
coordinate axes' real-world compass meaning is not independently verified
(see COURSE IDENTITY: UNRESOLVED). Only neutral dx/dy/distance_from_pin
are reported.
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
PLAYERS_OF_INTEREST = {"9115": "유해란(TOP,#1,-4)", "9708": "이재윤(MID,#27,+9)", "9111": "박서현(BOTTOM,#61,+26)"}
LIE_NAME = {"1": "FAIRWAY", "2": "ROUGH", "3": "GREEN", "4": "OB", "5": "PENALTY_AREA",
            "6": "BUNKER", "7": "LOST_BALL", "8": "PENALTY_STROKE", "9": "GREENSIDE_BUNKER",
            "10": "HOLED", "12": "FRINGE"}


def load_shots(con):
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
    """Real per-round pin = (green_x,green_y) of every HOLED shot that round.
    Returns {round: (pin_x,pin_y,n,stdev_x,stdev_y)}."""
    by_round = defaultdict(list)
    for (pc, rnd), shots in by_pr.items():
        for s in shots:
            if s["state"] == "10" and s["green_x"] is not None:
                by_round[rnd].append((s["green_x"], s["green_y"]))
    pins = {}
    for rnd, pts in sorted(by_round.items()):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        pins[rnd] = {
            "pin_x": statistics.mean(xs), "pin_y": statistics.mean(ys), "n": len(pts),
            "stdev_x": statistics.pstdev(xs), "stdev_y": statistics.pstdev(ys),
        }
    return pins


def tee_zone_anchors(by_pr):
    """Re-derive the SAME tee/green(overview-frame) anchors and zone
    thresholds used in course_management_elimination.py, so tee-zone labels
    stay consistent with the already-published analysis."""
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
    return tee, green


def project(tee, green, pt):
    vx, vy = green[0] - tee[0], green[1] - tee[1]
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return None, None
    px, py = pt[0] - tee[0], pt[1] - tee[1]
    frac = (px * vx + py * vy) / L2
    cross = px * vy - py * vx
    lateral = cross / math.sqrt(L2)
    return frac, lateral


def build_chain_records(by_pr, names, tee, green, pins):
    fracs_all, laterals_all = [], []
    tmp = []
    for (pc, rnd), shots in by_pr.items():
        ss = sorted(shots, key=lambda s: s["shot"])
        if not ss or ss[0]["x"] is None:
            continue
        frac, lateral = project(tee, green, (ss[0]["x"], ss[0]["y"]))
        tmp.append((pc, rnd, ss, frac, lateral))
        if frac is not None:
            fracs_all.append(frac)
            laterals_all.append(lateral)
    fracs_all.sort(); laterals_all.sort()
    f1, f2 = fracs_all[len(fracs_all) // 3], fracs_all[(2 * len(fracs_all)) // 3]
    l1, l2 = laterals_all[len(laterals_all) // 3], laterals_all[(2 * len(laterals_all)) // 3]

    def lon_bucket(frac):
        return "SHORT" if frac <= f1 else ("MID" if frac <= f2 else "LONG")

    def lat_bucket(lat):
        return "LAT1" if lat <= l1 else ("LAT2" if lat <= l2 else "LAT3")

    records = []
    for pc, rnd, ss, frac, lateral in tmp:
        pin = pins.get(rnd)
        shot1 = ss[0]
        tee_zone = f"{lon_bucket(frac)}-{lat_bucket(lateral)}" if frac is not None else None
        strokes = len(ss)
        score_to_par = strokes - PAR

        shot2 = ss[1] if len(ss) >= 2 else None
        approach = None
        pin_dx = pin_dy = pin_dist = pin_dist_official = None
        gir = None
        miss_lie = None
        if shot2 is not None and pin is not None and shot2["green_x"] is not None:
            pin_dx = shot2["green_x"] - pin["pin_x"]
            pin_dy = shot2["green_y"] - pin["pin_y"]
            pin_dist = math.hypot(pin_dx, pin_dy)
            pin_dist_official = shot2["distance"]
            gir = (shot2["state"] == "3")
            if not gir:
                miss_lie = LIE_NAME.get(shot2["state"], f"UNKNOWN_{shot2['state']}")
        recovery_shots = ss[2:] if len(ss) > 2 else []
        recovery_strokes = len(recovery_shots)

        if score_to_par <= -1:
            bucket = "Birdie+"
        elif score_to_par == 0:
            bucket = "Par"
        elif score_to_par == 1:
            bucket = "Bogey"
        else:
            bucket = "Double+"

        gir_miss_outcome = None
        if gir is False:
            if score_to_par == 0:
                gir_miss_outcome = "ParSave"
            elif score_to_par == 1:
                gir_miss_outcome = "Bogey"
            else:
                gir_miss_outcome = "Double+"

        records.append({
            "player_code": pc, "player_name": names.get(pc), "round": rnd,
            "tee_zone": tee_zone, "frac_down_line": frac, "lateral_offset": lateral,
            "tee_x": shot1["x"], "tee_y": shot1["y"], "tee_lie": LIE_NAME.get(shot1["state"], f"UNKNOWN_{shot1['state']}"),
            "tee_remaining_distance_official": shot1["distance"],
            "round_pin_x": pin["pin_x"] if pin else None, "round_pin_y": pin["pin_y"] if pin else None,
            "approach_green_x": shot2["green_x"] if shot2 else None,
            "approach_green_y": shot2["green_y"] if shot2 else None,
            "approach_lie": LIE_NAME.get(shot2["state"], f"UNKNOWN_{shot2['state']}") if shot2 else None,
            "pin_dx": pin_dx, "pin_dy": pin_dy,
            "pin_distance_computed": pin_dist, "pin_distance_official": pin_dist_official,
            "gir": gir, "miss_lie": miss_lie, "gir_miss_outcome": gir_miss_outcome,
            "fw_hit": shot1["state"] == "1",
            "recovery_strokes": recovery_strokes,
            "strokes": strokes, "score_to_par": score_to_par, "score_bucket": bucket,
            "shot_state_sequence": [s["state"] for s in ss],
        })
    thresholds = {"f1": f1, "f2": f2, "l1": l1, "l2": l2}
    return records, thresholds


def counterexample_census(records):
    cats = defaultdict(list)
    for r in records:
        if r["fw_hit"]:
            cats[f"FW Hit -> {r['score_bucket']}"].append(r)
        else:
            if r["score_bucket"] != "Double+":
                cats[f"FW Miss -> {r['score_bucket']}"].append(r)
            else:
                cats["FW Miss -> Double+"].append(r)
        if r["gir"] is True:
            cats[f"GIR -> {r['score_bucket']}"].append(r)
        elif r["gir"] is False and r["gir_miss_outcome"]:
            label = {"ParSave": "GIR Miss -> Par Save", "Bogey": "GIR Miss -> Bogey", "Double+": "GIR Miss -> Double+"}[r["gir_miss_outcome"]]
            cats[label].append(r)
    out = {}
    for label, rows in sorted(cats.items()):
        rep = rows[0]
        out[label] = {
            "n": len(rows),
            "representative_chain": {
                "player": rep["player_name"], "player_code": rep["player_code"], "round": rep["round"],
                "tee_zone": rep["tee_zone"], "tee_lie": rep["tee_lie"],
                "tee_remaining_distance": rep["tee_remaining_distance_official"],
                "approach_lie": rep["approach_lie"], "pin_distance": rep["pin_distance_official"],
                "shot_state_sequence": rep["shot_state_sequence"], "strokes": rep["strokes"],
                "score_to_par": rep["score_to_par"],
            },
        }
    return out


def zone_round_table(records):
    grouped = defaultdict(list)
    for r in records:
        if r["tee_zone"] is None:
            continue
        grouped[(r["tee_zone"], r["round"])].append(r)
    table = []
    for (zone, rnd), rows in sorted(grouped.items()):
        n = len(rows)
        table.append({
            "zone": zone, "round": rnd, "n": n,
            "avg_score_to_par": statistics.mean(r["score_to_par"] for r in rows),
            "GIR_pct": sum(1 for r in rows if r["gir"]) / n,
            "BogeyPlus_pct": sum(1 for r in rows if r["score_to_par"] >= 1) / n,
            "LOW_SAMPLE": n < 5,
        })
    return table


def fairway_effect_control(records):
    """Compare LAT1 vs LAT2 vs LAT3 restricted to FW-hit tee shots only,
    to test whether lateral-zone advantage survives once lie is held fixed."""
    out = {}
    for lat in ("LAT1", "LAT2", "LAT3"):
        fw_rows = [r for r in records if r["tee_zone"] and r["tee_zone"].endswith(f"-{lat}") and r["fw_hit"]]
        rough_rows = [r for r in records if r["tee_zone"] and r["tee_zone"].endswith(f"-{lat}") and not r["fw_hit"]]
        def summarize(rows):
            if not rows:
                return {"n": 0}
            n = len(rows)
            return {"n": n, "avg_score_to_par": statistics.mean(r["score_to_par"] for r in rows),
                    "GIR_pct": sum(1 for r in rows if r["gir"]) / n, "LOW_SAMPLE": n < 5}
        out[lat] = {"FW_hit_only": summarize(fw_rows), "not_FW_only": summarize(rough_rows)}
    return out


def interaction_short_lat3_vs_long_lat3(records):
    out = {}
    for zone in ("SHORT-LAT3", "LONG-LAT3", "SHORT-LAT1", "LONG-LAT1", "SHORT-LAT2", "LONG-LAT2"):
        rows = [r for r in records if r["tee_zone"] == zone]
        if not rows:
            out[zone] = {"n": 0}
            continue
        n = len(rows)
        out[zone] = {
            "n": n, "avg_score_to_par": statistics.mean(r["score_to_par"] for r in rows),
            "BogeyPlus_pct": sum(1 for r in rows if r["score_to_par"] >= 1) / n,
            "FW_pct": sum(1 for r in rows if r["fw_hit"]) / n,
            "Bunker_approach_pct": sum(1 for r in rows if r["approach_lie"] in ("BUNKER", "GREENSIDE_BUNKER")) / n,
        }
    return out


def three_player_full_reconstruction(records):
    out = {}
    for pc, label in PLAYERS_OF_INTEREST.items():
        rows = sorted([r for r in records if r["player_code"] == pc], key=lambda r: r["round"])
        out[pc] = {"label": label, "rounds": rows}
    return out


def layer2_player_truth(by_pr, names):
    """Hole-12-specific player tendencies (n=4 per player -- explicitly
    LOW_SAMPLE) are reported separately from tournament-wide skill context
    (72 holes, already-computed, not re-derived here)."""
    import csv as _csv
    tourney = {}
    with open(HERE / "neo_player_event_shot_metrics.csv", encoding="utf-8") as fh:
        for row in _csv.DictReader(fh):
            tourney[row["player_code"]] = row
    out = {}
    for pc, label in PLAYERS_OF_INTEREST.items():
        t = tourney.get(pc, {})
        out[pc] = {
            "label": label,
            "hole12_sample_n": 4,
            "hole12_LOW_SAMPLE": True,
            "tournament_wide_72holes": {
                "fw_hit_rate": t.get("fw_hit_rate"), "fw_hit_rate_n": t.get("fw_hit_rate_n"),
                "gir_rate": t.get("gir_rate"), "gir_rate_n": t.get("gir_rate_n"),
                "FWMiss_to_GIR_rate": t.get("FWMiss_to_GIR_rate"), "FWMiss_to_GIR_n": t.get("FWMiss_to_GIR_n"),
                "GIRMiss_to_ParSave_rate": t.get("GIRMiss_to_ParSave_rate"), "GIRMiss_to_ParSave_n": t.get("GIRMiss_to_ParSave_n"),
            },
            "shot_shape": "UNKNOWN (Shot Tracker carries no ball-flight-shape field)",
        }
    return out


def layer3_player_x_course(records, zone_table, fairway_control):
    """Per player: FIELD EVIDENCE (zone_table) + PLAYER EVIDENCE (their own
    Hole12 zone usage/outcomes) + SAMPLE SIZE + COUNTER-EVIDENCE +
    UNCERTAINTY. Never forces one zone onto all three players."""
    field_zone_summary = defaultdict(lambda: {"n": 0, "score_sum": 0, "gir_n": 0, "bogey_n": 0})
    for r in records:
        if r["tee_zone"] is None:
            continue
        z = field_zone_summary[r["tee_zone"]]
        z["n"] += 1
        z["score_sum"] += r["score_to_par"]
        z["gir_n"] += 1 if r["gir"] else 0
        z["bogey_n"] += 1 if r["score_to_par"] >= 1 else 0
    field_summary = {
        z: {"n": v["n"], "avg_score_to_par": v["score_sum"] / v["n"], "GIR_pct": v["gir_n"] / v["n"],
            "BogeyPlus_pct": v["bogey_n"] / v["n"], "LOW_SAMPLE": v["n"] < 5}
        for z, v in field_zone_summary.items()
    }

    out = {}
    for pc, label in PLAYERS_OF_INTEREST.items():
        player_rows = [r for r in records if r["player_code"] == pc]
        zones_used = defaultdict(list)
        for r in player_rows:
            if r["tee_zone"]:
                zones_used[r["tee_zone"]].append(r)
        player_zone_evidence = {}
        for z, rows in zones_used.items():
            player_zone_evidence[z] = {
                "n": len(rows), "LOW_SAMPLE": True,
                "rounds_used": [r["round"] for r in rows],
                "scores_to_par": [r["score_to_par"] for r in rows],
                "avg_score_to_par": statistics.mean(r["score_to_par"] for r in rows),
            }
        out[pc] = {
            "label": label,
            "field_evidence_all_zones": field_summary,
            "player_evidence_hole12_zones_actually_used": player_zone_evidence,
            "sample_size_note": "player evidence n<=4 per zone on this single hole -- LOW_SAMPLE, not a field-level claim",
            "counter_evidence": None,
            "uncertainty": "player-specific target zone cannot be statistically confirmed from n<=4; "
                           "field_evidence shows population-level outcome distribution only, "
                           "not a guarantee for this specific player",
        }
    return out


def hunt_haeran_counterexample(records):
    """유해란 (winner, -4) never played the field's best-looking zones on
    Hole12 (per earlier elimination analysis); report her real 4 rounds
    without asserting the zone caused or didn't cause her result."""
    rows = sorted([r for r in records if r["player_code"] == "9115"], key=lambda r: r["round"])
    return rows


def main():
    con = sqlite3.connect(DB)
    by_pr, names = load_shots(con)
    pins = round_pins(by_pr)
    tee, green_overview_axis_only = tee_zone_anchors(by_pr)
    records, thresholds = build_chain_records(by_pr, names, tee, green_overview_axis_only, pins)

    census = counterexample_census(records)
    zrt = zone_round_table(records)
    fw_control = fairway_effect_control(records)
    interaction = interaction_short_lat3_vs_long_lat3(records)
    three_players = three_player_full_reconstruction(records)
    layer2 = layer2_player_truth(by_pr, names)
    layer3 = layer3_player_x_course(records, zrt, fw_control)
    haeran_rows = hunt_haeran_counterexample(records)

    # Cross-validate computed pin-distance against KLPGA's own official
    # distance field (real, not derived) -- report mean abs diff.
    diffs = [abs(r["pin_distance_computed"] - r["pin_distance_official"])
             for r in records if r["pin_distance_computed"] is not None and r["pin_distance_official"] is not None]
    pin_distance_crosscheck = {
        "n": len(diffs),
        "mean_abs_diff": statistics.mean(diffs) if diffs else None,
        "max_abs_diff": max(diffs) if diffs else None,
    }

    out = {
        "hole": HOLE, "par": PAR, "game_code": GAME,
        "round_pins_real": pins,
        "tee_zone_thresholds": thresholds,
        "pin_distance_crosscheck_computed_vs_official_field": pin_distance_crosscheck,
        "counterexample_census": census,
        "zone_x_round_table": zrt,
        "fairway_effect_control_by_lateral_zone": fw_control,
        "short_lat3_vs_long_lat3_interaction": interaction,
        "three_case_study_players_full_12case_reconstruction": three_players,
        "layer1_course_truth_note": "see zone_x_round_table + fairway_effect_control + interaction for field-wide observed outcome distribution",
        "layer2_player_truth": layer2,
        "layer3_player_x_course_recommendation": layer3,
        "haeran_counterexample_rows": haeran_rows,
        "old_green_side_miss_analysis_json": "DISCARDED -- assumed pin at origin (0,0), disproven by real per-round pin positions; do not use",
    }
    (HERE / "hole12_pin_corrected_analysis.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    with open(HERE / "neo_hole12_pin_corrected_records.csv", "w", newline="", encoding="utf-8") as fh:
        cols = ["player_code", "player_name", "round", "tee_zone", "tee_lie", "tee_remaining_distance_official",
                "round_pin_x", "round_pin_y", "approach_green_x", "approach_green_y", "approach_lie",
                "pin_dx", "pin_dy", "pin_distance_computed", "pin_distance_official", "gir", "miss_lie",
                "gir_miss_outcome", "fw_hit", "recovery_strokes", "strokes", "score_to_par", "score_bucket"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in records:
            w.writerow({c: r.get(c) for c in cols})

    print("ROUND PINS (real, from HOLED-shot convergence):")
    for rnd, p in pins.items():
        print(f"  R{rnd}: pin=({p['pin_x']:.1f},{p['pin_y']:.1f}) n={p['n']} stdev=({p['stdev_x']:.3f},{p['stdev_y']:.3f})")
    print(f"\nPin-distance cross-check (computed dx/dy magnitude vs KLPGA's own official distance field): {pin_distance_crosscheck}")
    print(f"\nTotal chain records: {len(records)}")
    print("\nCOUNTEREXAMPLE CENSUS:")
    for label, v in sorted(census.items()):
        print(f"  {label}: n={v['n']}")
    print("\nFAIRWAY EFFECT CONTROL (FW-hit only, by lateral zone):")
    for lat, v in fw_control.items():
        print(f"  {lat}: FW_hit_only={v['FW_hit_only']}  not_FW_only={v['not_FW_only']}")
    print("\nSHORT-LAT3 vs LONG-LAT3 interaction check:")
    for z, v in interaction.items():
        print(f"  {z}: {v}")
    print("\n유해란 (9115) Hole12 all 4 rounds, real zones actually used:")
    for r in haeran_rows:
        print(f"  R{r['round']}: tee_zone={r['tee_zone']} tee_lie={r['tee_lie']} approach_lie={r['approach_lie']} "
              f"pin_dist={r['pin_distance_official']} gir={r['gir']} strokes={r['strokes']} score={r['score_to_par']:+d}")
    print("\nWrote hole12_pin_corrected_analysis.json, neo_hole12_pin_corrected_records.csv")


if __name__ == "__main__":
    main()
