"""Field (107-player) validation for the specific spatial clusters that
matter to the three-player narrative. Separates PLAYER FAILURE from
COURSE LOCATION RISK by checking whether a cluster is risky for everyone
or just for one player. All claims carry n.
"""
from __future__ import annotations
import json, sqlite3, csv, statistics
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
DB = HERE / "klpga_shots_RAW_READONLY.sqlite"
GAME = "2026100005"
PAR_YDS = json.loads((HERE / "klpga_tournament_18hole_par_yardage.json").read_text())
LIE_NAME = {"1": "FAIRWAY", "2": "ROUGH", "3": "GREEN", "4": "OB", "5": "PENALTY_AREA",
            "6": "BUNKER", "7": "LOST_BALL", "8": "PENALTY_STROKE", "9": "GREENSIDE_BUNKER",
            "10": "HOLED", "12": "FRINGE"}


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
        "SELECT player_code, round, hole, shot, state_code, distance FROM klpga_player_shot "
        "WHERE game_code=? ORDER BY player_code, round, hole, shot", (GAME,)
    ).fetchall()
    by_prh = defaultdict(list)
    for pc, rnd, hole, shot, state, dist in rows:
        by_prh[(pc, rnd, hole)].append({"shot": shot, "state": state, "distance": dist})

    hole_scores = {}  # (pc, rnd, hole) -> dict
    for key, ss in by_prh.items():
        ss = sorted(ss, key=lambda s: s["shot"])
        pc, rnd, hole = key
        par = PAR_YDS[str(hole)]["par"]
        strokes = len(ss)
        hole_scores[key] = {"strokes": strokes, "par": par, "score_to_par": strokes - par,
                             "tee_lie": LIE_NAME.get(ss[0]["state"]), "state_seq": [s["state"] for s in ss]}

    results = {}

    # ---- Validation A: Holes 8 & 9 difficulty, field-wide ----
    for hole in (8, 9):
        vals = [v["score_to_par"] for k, v in hole_scores.items() if k[2] == hole]
        results[f"hole{hole}_field"] = {"n": len(vals), "avg_score_to_par": round(statistics.mean(vals), 3),
                                          "bogey_plus_pct": round(sum(1 for v in vals if v >= 1) / len(vals), 3),
                                          "double_plus_pct": round(sum(1 for v in vals if v >= 2) / len(vals), 3)}
    all_par4_vals = [v["score_to_par"] for k, v in hole_scores.items() if v["par"] == 4]
    results["all_par4_field"] = {"n": len(all_par4_vals), "avg_score_to_par": round(statistics.mean(all_par4_vals), 3),
                                   "double_plus_pct": round(sum(1 for v in all_par4_vals if v >= 2) / len(all_par4_vals), 3)}

    # ---- Validation B: R1H3 greenside-bunker-area outcome, field-wide ----
    # (any player whose shot sequence includes a GREENSIDE_BUNKER (state 9)
    # on R1H3, what score resulted)
    gsb_r1h3 = []
    for key, ss in by_prh.items():
        pc, rnd, hole = key
        if rnd == 1 and hole == 3:
            states = [s["state"] for s in sorted(ss, key=lambda s: s["shot"])]
            if "9" in states:
                gsb_r1h3.append(hole_scores[key]["score_to_par"])
    if gsb_r1h3:
        results["r1h3_greenside_bunker_field"] = {
            "n": len(gsb_r1h3), "avg_score_to_par": round(statistics.mean(gsb_r1h3), 3),
            "par_or_better_pct": round(sum(1 for v in gsb_r1h3 if v <= 0) / len(gsb_r1h3), 3),
            "double_plus_pct": round(sum(1 for v in gsb_r1h3 if v >= 2) / len(gsb_r1h3), 3)}

    # ---- Validation C: ROUGH first-miss, field-wide par-save rate ----
    rough_recoveries = []
    for key, ss in by_prh.items():
        pc, rnd, hole = key
        ss_sorted = sorted(ss, key=lambda s: s["shot"])
        states = [s["state"] for s in ss_sorted]
        gir_shot = next((i + 1 for i, s in enumerate(ss_sorted) if s["state"] == "3"), None)
        par = PAR_YDS[str(hole)]["par"]
        gir = gir_shot is not None and gir_shot <= par - 2
        if gir:
            continue
        first_miss = next((s["state"] for s in ss_sorted[1:] if s["state"] in ("2", "6", "9", "12")), None)
        if first_miss == "2":  # rough
            rough_recoveries.append(hole_scores[key]["score_to_par"])
    results["field_rough_miss_parsave"] = {
        "n": len(rough_recoveries),
        "par_or_better_pct": round(sum(1 for v in rough_recoveries if v <= 0) / len(rough_recoveries), 3),
        "double_plus_pct": round(sum(1 for v in rough_recoveries if v >= 2) / len(rough_recoveries), 3)}

    # ---- Validation D: field-wide putts distribution for sanity (fixed formula) ----
    putts_all = []
    for key, ss in by_prh.items():
        ss_sorted = sorted(ss, key=lambda s: s["shot"])
        putts_all.append(putts_count_fixed(ss_sorted))
    results["field_putts_distribution"] = {"n": len(putts_all), "mean": round(statistics.mean(putts_all), 3),
                                             "max": max(putts_all), "pct_3plus": round(sum(1 for p in putts_all if p >= 3) / len(putts_all), 3)}

    print(json.dumps(results, ensure_ascii=False, indent=1))
    (HERE / "field_spatial_validation_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))

    with open(HERE / "three_player_field_spatial_validation.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cluster", "n", "metric", "value"])
        for cluster, d in results.items():
            for metric, value in d.items():
                if metric == "n":
                    continue
                w.writerow([cluster, d["n"], metric, value])
    print("\nWrote field_spatial_validation_results.json + three_player_field_spatial_validation.csv")


if __name__ == "__main__":
    main()
