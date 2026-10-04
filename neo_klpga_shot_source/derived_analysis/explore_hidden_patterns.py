"""NEO hidden-pattern exploration -- 10-angle investigation across the
3 case-study players and the full 107-player field. Read-only against
RAW/derived data. Goal is NOT to explain why the winner won; goal is
to find what a leaderboard-only view would miss: reversals, paradoxes,
asymmetries, counterexamples. Obvious confirmatory findings are
recorded as reference only, not treated as headline results.
"""
from __future__ import annotations
import csv, json, sqlite3, statistics
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
DB = HERE / "klpga_shots_RAW_READONLY.sqlite"
GAME = "2026100005"

PLAYERS = {"9115": "유해란(TOP,#1)", "9708": "이재윤(MID,#27)", "9111": "박서현(BOTTOM,#61)"}
CLASSIFICATION = {6: "DEFEND", 8: "DEFEND", 10: "DEFEND", 12: "DEFEND",
                  1: "CONTROL", 3: "CONTROL", 5: "CONTROL", 9: "CONTROL", 11: "CONTROL", 13: "CONTROL", 15: "CONTROL", 17: "CONTROL",
                  2: "ATTACK", 4: "ATTACK", 7: "ATTACK", 14: "ATTACK", 16: "ATTACK", 18: "ATTACK"}
PAR_BY_HOLE = {1: 4, 2: 3, 3: 4, 4: 5, 5: 3, 6: 4, 7: 5, 8: 4, 9: 4,
               10: 5, 11: 3, 12: 4, 13: 4, 14: 4, 15: 4, 16: 3, 17: 4, 18: 5}

LOW_SAMPLE_N = 5


def load_three_player_rows():
    rows = list(csv.DictReader(open(HERE / "neo_three_player_raw_reconstruction.csv", encoding="utf-8")))
    for r in rows:
        r["first_shot_state"] = r["shot_states"].split("|")[0] if r["shot_states"] else None
    return rows


def load_field_rows():
    return [r for r in csv.DictReader(open(HERE / "neo_player_hole_shot_derived.csv", encoding="utf-8")) if r["source_gap"] != "True"]


def load_player_event_metrics():
    return list(csv.DictReader(open(HERE / "neo_player_event_shot_metrics.csv", encoding="utf-8")))


def load_shot_level(con, player_codes=None):
    q = "SELECT player_code, round, hole, shot, state_code, x, y, green_x, green_y, distance FROM klpga_player_shot WHERE game_code=?"
    params = [GAME]
    if player_codes:
        q += f" AND player_code IN ({','.join('?' for _ in player_codes)})"
        params += list(player_codes)
    q += " ORDER BY player_code, round, hole, shot"
    return con.execute(q, params).fetchall()


# ===========================================================================
# ANGLE 1: Ranking reversal
# ===========================================================================

def angle1_ranking_reversal(three_rows):
    by_player_hole_round = {}
    for r in three_rows:
        key = (r["player_code"], int(r["round"]), int(r["hole"]))
        by_player_hole_round[key] = r

    reversals = []
    for rnd in range(1, 5):
        for hole in range(1, 19):
            top = by_player_hole_round[("9115", rnd, hole)]
            mid = by_player_hole_round[("9708", rnd, hole)]
            bot = by_player_hole_round[("9111", rnd, hole)]
            top_stp, mid_stp, bot_stp = int(top["score_to_par"]), int(mid["score_to_par"]), int(bot["score_to_par"])
            if bot_stp < top_stp:
                reversals.append({
                    "type": "bottom_beat_top", "round": rnd, "hole": hole, "par": PAR_BY_HOLE[hole],
                    "classification": CLASSIFICATION[hole],
                    "박서현_score_to_par": bot_stp, "박서현_states": bot["shot_states"],
                    "유해란_score_to_par": top_stp, "유해란_states": top["shot_states"],
                    "diff": top_stp - bot_stp,
                })
            if mid_stp <= top_stp:
                reversals.append({
                    "type": "mid_matched_or_beat_top", "round": rnd, "hole": hole, "par": PAR_BY_HOLE[hole],
                    "classification": CLASSIFICATION[hole],
                    "이재윤_score_to_par": mid_stp, "이재윤_states": mid["shot_states"],
                    "유해란_score_to_par": top_stp, "유해란_states": top["shot_states"],
                    "diff": top_stp - mid_stp,
                })
    return reversals


# ===========================================================================
# ANGLE 2: Same input, different output
# ===========================================================================

def angle2_same_input_different_output(three_rows):
    by_hole_round = defaultdict(dict)
    for r in three_rows:
        by_hole_round[(int(r["round"]), int(r["hole"]))][r["player_code"]] = r

    cases = []
    for (rnd, hole), players in by_hole_round.items():
        if len(players) != 3:
            continue
        states = {pc: r["first_shot_state"] for pc, r in players.items()}
        girs = {pc: r["gir"] for pc, r in players.items()}
        scores = {pc: int(r["score_to_par"]) for pc, r in players.items()}
        same_first_state = len(set(states.values())) == 1
        same_gir_outcome = len(set(girs.values())) == 1
        score_spread = max(scores.values()) - min(scores.values())
        if (same_first_state or same_gir_outcome) and score_spread >= 1:
            cases.append({
                "round": rnd, "hole": hole, "par": PAR_BY_HOLE[hole], "classification": CLASSIFICATION[hole],
                "same_first_shot_state": same_first_state, "first_shot_state": states if same_first_state else None,
                "same_gir_outcome": same_gir_outcome, "gir": girs if same_gir_outcome else None,
                "score_to_par": scores, "score_spread": score_spread,
                "full_sequences": {pc: players[pc]["shot_states"] for pc in players},
            })
    cases.sort(key=lambda c: -c["score_spread"])
    return cases


# ===========================================================================
# ANGLE 3: Good result -> bad score (3 players + full field counts)
# ===========================================================================

def angle3_good_start_bad_score(three_rows, field_rows):
    three_cases = []
    for r in three_rows:
        stp = int(r["score_to_par"])
        fw_hit = r["fw_hit"] == "True"
        gir = r["gir"] == "True"
        cls = CLASSIFICATION[int(r["hole"])]
        tags = []
        if fw_hit and stp >= 1:
            tags.append("FW_Hit_to_Bogey+")
        if fw_hit and stp >= 2:
            tags.append("FW_Hit_to_Double+")
        if gir and stp >= 1:
            tags.append("GIR_to_Bogey+")
        if cls == "ATTACK" and stp >= 1:
            tags.append("ATTACKhole_to_Bogey+")
        if tags:
            three_cases.append({"player_code": r["player_code"], "player_name": PLAYERS[r["player_code"]],
                                 "round": r["round"], "hole": r["hole"], "score_to_par": stp,
                                 "states": r["shot_states"], "tags": tags})

    field_counts = {"FW_Hit_to_Bogey+": 0, "FW_Hit_to_Double+": 0, "GIR_to_Bogey+": 0, "ATTACKhole_to_Bogey+": 0}
    field_n = {"FW_Hit_to_Bogey+": 0, "FW_Hit_to_Double+": 0, "GIR_to_Bogey+": 0, "ATTACKhole_to_Bogey+": 0}
    affected_players = defaultdict(set)
    for r in field_rows:
        stp = int(r["score_to_par"])
        fw_hit = r["fw_hit"] == "True"
        gir = r["gir"] == "True"
        cls = CLASSIFICATION[int(r["hole"])]
        if r["fw_hit"] in ("True", "False"):
            field_n["FW_Hit_to_Bogey+"] += 1 if fw_hit else 0
            field_n["FW_Hit_to_Double+"] += 1 if fw_hit else 0
        field_n["GIR_to_Bogey+"] += 1 if gir else 0
        field_n["ATTACKhole_to_Bogey+"] += 1 if cls == "ATTACK" else 0
        if fw_hit and stp >= 1:
            field_counts["FW_Hit_to_Bogey+"] += 1
            affected_players["FW_Hit_to_Bogey+"].add(r["player_code"])
        if fw_hit and stp >= 2:
            field_counts["FW_Hit_to_Double+"] += 1
            affected_players["FW_Hit_to_Double+"].add(r["player_code"])
        if gir and stp >= 1:
            field_counts["GIR_to_Bogey+"] += 1
            affected_players["GIR_to_Bogey+"].add(r["player_code"])
        if cls == "ATTACK" and stp >= 1:
            field_counts["ATTACKhole_to_Bogey+"] += 1
            affected_players["ATTACKhole_to_Bogey+"].add(r["player_code"])

    field_summary = {k: {"occurrences": field_counts[k], "n_eligible_holes": field_n[k],
                          "rate": field_counts[k] / field_n[k] if field_n[k] else None,
                          "distinct_players_affected": len(affected_players[k])} for k in field_counts}
    return three_cases, field_summary


# ===========================================================================
# ANGLE 4: Bad result -> good score
# ===========================================================================

def angle4_bad_start_good_score(three_rows, field_rows):
    three_cases = []
    for r in three_rows:
        stp = int(r["score_to_par"])
        fw_hit = r["fw_hit"]
        gir = r["gir"] == "True"
        tms = r["tee_miss_state"]
        tags = []
        if fw_hit == "False" and stp <= -1:
            tags.append("FWMiss_to_Birdie")
        if tms == "ROUGH" and stp <= -1:
            tags.append("Rough_to_Birdie")
        if tms == "BUNKER" and stp <= 0:
            tags.append("Bunker_to_ParOrBetter")
        if (not gir) and stp <= 0:
            tags.append("GIRMiss_to_Par")
        if tags:
            three_cases.append({"player_code": r["player_code"], "player_name": PLAYERS[r["player_code"]],
                                 "round": r["round"], "hole": r["hole"], "score_to_par": stp,
                                 "states": r["shot_states"], "tags": tags})

    per_player_recovery_rate = defaultdict(lambda: {"GIRMiss_to_Par_n": 0, "GIRMiss_to_Par_k": 0})
    field_counts = defaultdict(int)
    field_n = defaultdict(int)
    for r in field_rows:
        stp = int(r["score_to_par"])
        fw_hit = r["fw_hit"]
        gir = r["gir"] == "True"
        tms = r["tee_miss_state"]
        pc = r["player_code"]
        if fw_hit == "False":
            field_n["FWMiss_to_Birdie"] += 1
            if stp <= -1:
                field_counts["FWMiss_to_Birdie"] += 1
        if tms == "ROUGH":
            field_n["Rough_to_Birdie"] += 1
            if stp <= -1:
                field_counts["Rough_to_Birdie"] += 1
        if tms == "BUNKER":
            field_n["Bunker_to_ParOrBetter"] += 1
            if stp <= 0:
                field_counts["Bunker_to_ParOrBetter"] += 1
        if not gir:
            field_n["GIRMiss_to_Par"] += 1
            per_player_recovery_rate[pc]["GIRMiss_to_Par_n"] += 1
            if stp <= 0:
                field_counts["GIRMiss_to_Par"] += 1
                per_player_recovery_rate[pc]["GIRMiss_to_Par_k"] += 1

    field_summary = {k: {"occurrences": field_counts[k], "n_eligible": field_n[k],
                          "rate": field_counts[k] / field_n[k] if field_n[k] else None} for k in field_n}

    # Does 유해란 repeat GIRMiss->Par more than typical field?
    recovery_rates = []
    for pc, d in per_player_recovery_rate.items():
        if d["GIRMiss_to_Par_n"] >= LOW_SAMPLE_N:
            recovery_rates.append((pc, d["GIRMiss_to_Par_k"] / d["GIRMiss_to_Par_n"], d["GIRMiss_to_Par_n"]))
    recovery_rates.sort(key=lambda x: -x[1])
    rank_of = {pc: i + 1 for i, (pc, _, _) in enumerate(recovery_rates)}

    return three_cases, field_summary, {pc: {"rate": r, "n": n, "field_rank_of_%d_players" % len(recovery_rates): rank_of[pc]}
                                          for pc, r, n in recovery_rates if pc in PLAYERS}


# ===========================================================================
# ANGLE 5: Fairway paradox
# ===========================================================================

def angle5_fairway_paradox(field_rows):
    by_hole = defaultdict(lambda: {"fw_hit": [], "fw_miss": []})
    for r in field_rows:
        if r["fw_hit"] not in ("True", "False"):
            continue
        hole = int(r["hole"])
        stp = int(r["score_to_par"])
        if r["fw_hit"] == "True":
            by_hole[hole]["fw_hit"].append(stp)
        else:
            by_hole[hole]["fw_miss"].append(stp)

    paradoxes = []
    for hole, d in sorted(by_hole.items()):
        if len(d["fw_hit"]) < LOW_SAMPLE_N or len(d["fw_miss"]) < LOW_SAMPLE_N:
            continue
        fw_hit_avg = statistics.mean(d["fw_hit"])
        fw_miss_avg = statistics.mean(d["fw_miss"])
        fw_hit_bogey_rate = sum(1 for s in d["fw_hit"] if s >= 1) / len(d["fw_hit"])
        paradoxes.append({
            "hole": hole, "par": PAR_BY_HOLE[hole], "classification": CLASSIFICATION[hole],
            "fw_hit_avg_score": fw_hit_avg, "fw_hit_n": len(d["fw_hit"]),
            "fw_miss_avg_score": fw_miss_avg, "fw_miss_n": len(d["fw_miss"]),
            "fw_hit_bogey_or_worse_rate": fw_hit_bogey_rate,
            "gap_fw_hit_minus_fw_miss": fw_hit_avg - fw_miss_avg,
        })
    paradoxes.sort(key=lambda p: p["gap_fw_hit_minus_fw_miss"])
    return paradoxes


# ===========================================================================
# ANGLE 6: Miss location value (coordinates)
# ===========================================================================

def angle6_miss_location(con):
    rows = con.execute(
        "SELECT player_code, round, hole, shot, state_code, x, y FROM klpga_player_shot "
        "WHERE game_code=? AND shot=1 AND state_code='2'", (GAME,)
    ).fetchall()
    by_hole = defaultdict(list)
    for pc, rnd, hole, shot, state, x, y in rows:
        if x is None:
            continue
        by_hole[hole].append({"player_code": pc, "round": rnd, "x": x, "y": y})

    gir_lookup = {}
    for r in csv.DictReader(open(HERE / "neo_player_hole_shot_derived.csv", encoding="utf-8")):
        if r["source_gap"] == "True":
            continue
        gir_lookup[(r["player_code"], int(r["round"]), int(r["hole"]))] = r["gir"] == "True"

    results = []
    for hole, pts in sorted(by_hole.items()):
        if len(pts) < LOW_SAMPLE_N * 2:
            continue
        xs = sorted(p["x"] for p in pts)
        n = len(xs)
        t1, t2 = xs[n // 3], xs[(2 * n) // 3]

        def cluster_of(x):
            if x <= t1:
                return "A"
            if x <= t2:
                return "B"
            return "C"

        buckets = defaultdict(list)
        for p in pts:
            g = gir_lookup.get((p["player_code"], p["round"], hole))
            if g is not None:
                buckets[cluster_of(p["x"])].append(g)
        bucket_rates = {k: (sum(v) / len(v), len(v)) for k, v in buckets.items() if len(v) >= LOW_SAMPLE_N}
        if len(bucket_rates) >= 2:
            spread = max(r for r, n in bucket_rates.values()) - min(r for r, n in bucket_rates.values())
            results.append({"hole": hole, "par": PAR_BY_HOLE[hole], "rough_tee_shots_n": len(pts),
                             "cluster_gir_rates": bucket_rates, "spread": spread})
    results.sort(key=lambda r: -r["spread"])
    return results


# ===========================================================================
# ANGLE 7: Score gap concentration
# ===========================================================================

def angle7_gap_concentration(three_rows):
    by_player_hole_round = {}
    for r in three_rows:
        by_player_hole_round[(r["player_code"], int(r["round"]), int(r["hole"]))] = int(r["score_to_par"])

    events = []
    for rnd in range(1, 5):
        for hole in range(1, 19):
            top = by_player_hole_round[("9115", rnd, hole)]
            bot = by_player_hole_round[("9111", rnd, hole)]
            diff = bot - top
            if diff != 0:
                events.append({"round": rnd, "hole": hole, "classification": CLASSIFICATION[hole], "diff": diff})
    events.sort(key=lambda e: -e["diff"])
    total_gap = sum(e["diff"] for e in events)
    top5 = sum(e["diff"] for e in events[:5])
    top10 = sum(e["diff"] for e in events[:10])
    return {
        "total_events": len(events), "total_gap": total_gap,
        "top5_events": events[:5], "top5_sum": top5, "top5_share": top5 / total_gap if total_gap else None,
        "top10_events": events[:10], "top10_sum": top10, "top10_share": top10 / total_gap if total_gap else None,
        "all_events_sorted": events,
    }


# ===========================================================================
# ANGLE 8: Surprising similarity (TOP vs BOTTOM)
# ===========================================================================

def angle8_surprising_similarity(player_event_metrics):
    em = {r["player_code"]: r for r in player_event_metrics}
    top, bot = em["9115"], em["9111"]
    fields = ["fw_hit_rate", "FWMiss_to_GIR_rate", "Rough_to_GIR_rate", "Bunker_to_GIR_rate",
              "OtherTeeMiss_to_GIR_rate", "FWHit_to_ParOrBetter_rate"]
    out = []
    for f in fields:
        tv, bv = top.get(f), bot.get(f)
        if tv in (None, "") or bv in (None, ""):
            continue
        tv, bv = float(tv), float(bv)
        out.append({"metric": f, "유해란": tv, "박서현": bv, "abs_diff": abs(tv - bv)})
    out.sort(key=lambda r: r["abs_diff"])
    return out


# ===========================================================================
# ANGLE 9: Middle player (이재윤) decomposition
# ===========================================================================

def angle9_middle_player(player_event_metrics):
    em = {r["player_code"]: r for r in player_event_metrics}
    top, mid, bot = em["9115"], em["9708"], em["9111"]
    fields = ["fw_hit_rate", "gir_rate", "FW_to_GIR_rate", "FWMiss_to_GIR_rate", "Rough_to_GIR_rate",
              "GIRMiss_to_ParSave_rate", "FWHit_to_ParOrBetter_rate", "FWMiss_to_ParOrBetter_rate"]
    out = []
    for f in fields:
        tv, mv, bv = top.get(f), mid.get(f), bot.get(f)
        if tv in (None, "") or mv in (None, "") or bv in (None, ""):
            continue
        tv, mv, bv = float(tv), float(mv), float(bv)
        closer_to = "TOP" if abs(mv - tv) < abs(mv - bv) else "BOTTOM"
        out.append({"metric": f, "유해란": tv, "이재윤": mv, "박서현": bv, "이재윤_closer_to": closer_to,
                     "dist_to_top": abs(mv - tv), "dist_to_bottom": abs(mv - bv)})
    return out


# ===========================================================================
# ANGLE 10: Field-wide counterexamples to the FW-Miss->GIR hypothesis
# ===========================================================================

def angle10_counterexamples(player_event_metrics):
    rows = []
    for r in player_event_metrics:
        try:
            rows.append({
                "player_code": r["player_code"], "player_name": r["player_name"],
                "avg_score_to_par": float(r["avg_score_to_par"]),
                "fw_hit_rate": float(r["fw_hit_rate"]) if r["fw_hit_rate"] else None,
                "fw_hit_rate_n": int(r["fw_hit_rate_n"]),
                "gir_rate": float(r["gir_rate"]) if r["gir_rate"] else None,
                "gir_rate_n": int(r["gir_rate_n"]),
                "FWMiss_to_GIR_rate": float(r["FWMiss_to_GIR_rate"]) if r["FWMiss_to_GIR_rate"] else None,
                "FWMiss_to_GIR_n": int(r["FWMiss_to_GIR_n"]),
            })
        except (ValueError, TypeError):
            continue

    field_avg_score = statistics.mean(r["avg_score_to_par"] for r in rows)
    field_median_score = statistics.median(r["avg_score_to_par"] for r in rows)
    field_fw_hit = [r["fw_hit_rate"] for r in rows if r["fw_hit_rate"] is not None]
    field_gir = [r["gir_rate"] for r in rows if r["gir_rate"] is not None]
    field_fwmg = [r["FWMiss_to_GIR_rate"] for r in rows if r["FWMiss_to_GIR_rate"] is not None]
    median_fw_hit = statistics.median(field_fw_hit)
    median_gir = statistics.median(field_gir)
    median_fwmg = statistics.median(field_fwmg)

    low_fw_hit_good_score = sorted(
        [r for r in rows if r["fw_hit_rate"] is not None and r["fw_hit_rate_n"] >= LOW_SAMPLE_N
         and r["fw_hit_rate"] < median_fw_hit and r["avg_score_to_par"] < field_median_score],
        key=lambda r: r["avg_score_to_par"])

    low_gir_good_score = sorted(
        [r for r in rows if r["gir_rate"] is not None and r["gir_rate_n"] >= LOW_SAMPLE_N
         and r["gir_rate"] < median_gir and r["avg_score_to_par"] < field_median_score],
        key=lambda r: r["avg_score_to_par"])

    high_gir_bad_score = sorted(
        [r for r in rows if r["gir_rate"] is not None and r["gir_rate_n"] >= LOW_SAMPLE_N
         and r["gir_rate"] > median_gir and r["avg_score_to_par"] > field_median_score],
        key=lambda r: -r["avg_score_to_par"])

    low_fwmg_good_score = sorted(
        [r for r in rows if r["FWMiss_to_GIR_rate"] is not None and r["FWMiss_to_GIR_n"] >= LOW_SAMPLE_N
         and r["FWMiss_to_GIR_rate"] < median_fwmg and r["avg_score_to_par"] < field_median_score],
        key=lambda r: r["avg_score_to_par"])

    return {
        "field_n": len(rows), "field_avg_score": field_avg_score, "field_median_score": field_median_score,
        "median_fw_hit_rate": median_fw_hit, "median_gir_rate": median_gir, "median_FWMiss_to_GIR_rate": median_fwmg,
        "low_fw_hit_but_good_score": low_fw_hit_good_score[:10],
        "low_gir_but_good_score": low_gir_good_score[:10],
        "high_gir_but_bad_score": high_gir_bad_score[:10],
        "low_fw_miss_to_gir_but_good_score": low_fwmg_good_score[:10],
    }


def main():
    con = sqlite3.connect(DB)
    three_rows = load_three_player_rows()
    field_rows = load_field_rows()
    player_event_metrics = load_player_event_metrics()

    results = {}
    results["angle1_ranking_reversal"] = angle1_ranking_reversal(three_rows)
    results["angle2_same_input_different_output"] = angle2_same_input_different_output(three_rows)
    a3_three, a3_field = angle3_good_start_bad_score(three_rows, field_rows)
    results["angle3_good_start_bad_score"] = {"three_player_cases": a3_three, "field_summary": a3_field}
    a4_three, a4_field, a4_recovery = angle4_bad_start_good_score(three_rows, field_rows)
    results["angle4_bad_start_good_score"] = {"three_player_cases": a4_three, "field_summary": a4_field, "three_player_recovery_rank": a4_recovery}
    results["angle5_fairway_paradox"] = angle5_fairway_paradox(field_rows)
    results["angle6_miss_location"] = angle6_miss_location(con)
    results["angle7_gap_concentration"] = angle7_gap_concentration(three_rows)
    results["angle8_surprising_similarity"] = angle8_surprising_similarity(player_event_metrics)
    results["angle9_middle_player"] = angle9_middle_player(player_event_metrics)
    results["angle10_counterexamples"] = angle10_counterexamples(player_event_metrics)

    out_path = HERE / "hidden_patterns_exploration.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out_path}")

    # Print concise summaries for quick review
    print("\n--- ANGLE 1: reversals found ---", len(results["angle1_ranking_reversal"]))
    print("--- ANGLE 2: same-input-different-output cases ---", len(results["angle2_same_input_different_output"]))
    print("--- ANGLE 3: three-player good-start-bad-score cases ---", len(results["angle3_good_start_bad_score"]["three_player_cases"]))
    print("    field summary:", json.dumps(a3_field, ensure_ascii=False))
    print("--- ANGLE 4: three-player bad-start-good-score cases ---", len(results["angle4_bad_start_good_score"]["three_player_cases"]))
    print("    field summary:", json.dumps(a4_field, ensure_ascii=False))
    print("    recovery rank (3 players):", json.dumps(a4_recovery, ensure_ascii=False))
    print("--- ANGLE 5: fairway paradox candidates (most negative gap first) ---")
    for p in results["angle5_fairway_paradox"][:5]:
        print("   ", p)
    print("--- ANGLE 7: gap concentration ---")
    print("    top5_share:", results["angle7_gap_concentration"]["top5_share"], "top10_share:", results["angle7_gap_concentration"]["top10_share"])
    print("--- ANGLE 8: most similar metrics TOP vs BOTTOM ---")
    for s in results["angle8_surprising_similarity"][:3]:
        print("   ", s)
    print("--- ANGLE 10: field N and counterexample counts ---")
    print("    field_n:", results["angle10_counterexamples"]["field_n"])
    print("    low_fw_hit_but_good_score:", len(results["angle10_counterexamples"]["low_fw_hit_but_good_score"]))
    print("    low_gir_but_good_score:", len(results["angle10_counterexamples"]["low_gir_but_good_score"]))
    print("    high_gir_but_bad_score:", len(results["angle10_counterexamples"]["high_gir_but_bad_score"]))
    print("    low_fw_miss_to_gir_but_good_score:", len(results["angle10_counterexamples"]["low_fw_miss_to_gir_but_good_score"]))


if __name__ == "__main__":
    main()
