from __future__ import annotations
import json, csv, statistics
from pathlib import Path
from collections import defaultdict, Counter

HERE = Path(__file__).parent
field = json.loads((HERE / "field_chain.json").read_text())
field_shots = field["shot_records"]
field_holes = field["hole_summaries"]
field_hole_by_key = {(r["player_code"], r["round"], r["hole"]): r for r in field_holes}

three_rows = list(csv.DictReader(open(HERE / "three_player_spatial_chain_master.csv", encoding="utf-8")))
PLAYERS = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}
NAME2CODE = {v: k for k, v in PLAYERS.items()}

OFF_GREEN_LIES = {"FAIRWAY", "ROUGH", "BUNKER", "GREENSIDE_BUNKER"}
GREEN_LIES = {"GREEN", "FRINGE"}


def off_green_band(d):
    if d <= 50: return "0-50yd"
    if d <= 100: return "50-100yd"
    if d <= 150: return "100-150yd"
    if d <= 200: return "150-200yd"
    return "200yd+"


def green_band(d):
    if d <= 3: return "0-3yd"
    if d <= 6: return "3-6yd"
    if d <= 9: return "6-9yd"
    if d <= 12: return "9-12yd"
    if d <= 20: return "12-20yd"
    return "20yd+"


# ============================================================
# 1. neo_shot_chain_states.csv -- the 5-state structure, for the
#    three focal players (qualifying shots: every shot that creates
#    a next-shot condition, i.e. not the final holed shot)
# ============================================================
by_prh3 = defaultdict(list)
for r in three_rows:
    by_prh3[(r["player_code"], int(r["round"]), int(r["hole"]))].append(r)
for k in by_prh3:
    by_prh3[k].sort(key=lambda r: int(r["shot_number"]))

state_rows = []
for (pc, rnd, hole), shots in by_prh3.items():
    par = int(shots[0]["par"])
    final_stp = int(shots[0]["final_score_to_par"])
    if final_stp <= -1: final_bucket = "Birdie+"
    elif final_stp == 0: final_bucket = "Par"
    elif final_stp == 1: final_bucket = "Bogey"
    else: final_bucket = "Double+"
    for i, s in enumerate(shots[:-1]):  # exclude the holing shot (no "next shot")
        nxt = shots[i + 1]
        lie_after = s["lie_after"]
        rem_after = s["remaining_distance_after_yd"]
        next_lie = nxt["lie_after"]
        next_penalty = next_lie in ("OB", "PENALTY_AREA", "LOST_BALL", "PENALTY_STROKE")
        recovery_needed = lie_after in ("ROUGH", "BUNKER", "GREENSIDE_BUNKER", "FRINGE")
        state_rows.append({
            "player": PLAYERS[pc], "round": rnd, "hole": hole, "par": par, "shot_number": s["shot_number"],
            "state0_lie_before": s["lie_before"], "state0_remaining_before_yd": s["remaining_distance_before_yd"],
            "state1_end_coord": f"({s['end_x']},{s['end_y']})", "state1_lie_after": lie_after,
            "state1_remaining_after_yd": rem_after,
            "state2_next_shot_lie_hint": next_lie, "state2_recovery_needed": recovery_needed,
            "state2_penalty_next": next_penalty,
            "state3_next_shot_outcome_lie": nxt["lie_after"], "state3_next_shot_remaining_after_yd": nxt["remaining_distance_after_yd"],
            "state4_final_score": shots[0]["n_shots_this_hole"], "state4_score_bucket": final_bucket,
        })

with open(HERE / "neo_shot_chain_states.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(state_rows[0].keys()))
    w.writeheader()
    w.writerows(state_rows)
print(f"neo_shot_chain_states.csv: {len(state_rows)} qualifying shot-transition rows")


# ============================================================
# 2. neo_next_shot_quality.csv -- field-wide (n=107 players) outcome
#    by (lie_after, distance band), terciles define 유리/중립/위험
# ============================================================
field_bins = defaultdict(list)
for s in field_shots:
    lie = s["lie_after"]
    rem = s["remaining_after_yd"]
    if rem is None or s["shot_number"] == 1:  # exclude tee shots here; handled separately
        continue
    if lie in OFF_GREEN_LIES:
        band = off_green_band(rem)
    elif lie in GREEN_LIES:
        band = green_band(rem)
    else:
        continue
    key = (lie, band)
    final = field_hole_by_key[(s["player_code"], s["round"], s["hole"])]
    field_bins[key].append(final["score_to_par"])

quality_rows = []
for (lie, band), vals in field_bins.items():
    n = len(vals)
    if n < 5:
        continue
    avg = statistics.mean(vals)
    quality_rows.append({"lie": lie, "distance_band": band, "n": n, "avg_final_score_to_par": round(avg, 3),
                          "par_or_better_pct": round(sum(1 for v in vals if v <= 0) / n, 3),
                          "bogey_plus_pct": round(sum(1 for v in vals if v >= 1) / n, 3),
                          "double_plus_pct": round(sum(1 for v in vals if v >= 2) / n, 3)})

avgs = sorted(r["avg_final_score_to_par"] for r in quality_rows)
n_bins = len(avgs)
t1 = avgs[n_bins // 3]
t2 = avgs[(2 * n_bins) // 3]
for r in quality_rows:
    if r["avg_final_score_to_par"] <= t1:
        r["classification"] = "유리(favorable)"
    elif r["avg_final_score_to_par"] <= t2:
        r["classification"] = "중립(neutral)"
    else:
        r["classification"] = "위험(risky)"
    r["classification_rule"] = f"tercile of avg_final_score_to_par across {n_bins} (lie,band) bins, n>=5 each"

quality_rows.sort(key=lambda r: r["avg_final_score_to_par"])
with open(HERE / "neo_next_shot_quality.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(quality_rows[0].keys()))
    w.writeheader()
    w.writerows(quality_rows)
print(f"neo_next_shot_quality.csv: {len(quality_rows)} (lie,band) bins, field-wide, n>=5 each")
for r in quality_rows:
    print(f"  {r['lie']:18s} {r['distance_band']:10s} n={r['n']:4d} avg={r['avg_final_score_to_par']:+.3f} "
          f"par+={r['par_or_better_pct']:.0%} bogey+={r['bogey_plus_pct']:.0%} dbl+={r['double_plus_pct']:.0%} [{r['classification']}]")


# ============================================================
# 3. neo_fairway_paradox_cases.csv
# ============================================================
paradox_fw = []
for (pc, rnd, hole), shots in by_prh3.items():
    par = int(shots[0]["par"])
    if par == 3:
        continue
    tee = shots[0]
    final_stp = int(shots[0]["final_score_to_par"])
    bucket_ = "Birdie+" if final_stp <= -1 else ("Par" if final_stp == 0 else ("Bogey" if final_stp == 1 else "Double+"))
    next_shot = shots[1] if len(shots) > 1 else None
    paradox_fw.append({
        "player": PLAYERS[pc], "round": rnd, "hole": hole, "par": par,
        "tee_lie": tee["lie_after"], "tee_remaining_after_yd": tee["remaining_distance_after_yd"],
        "next_shot_lie": next_shot["lie_after"] if next_shot else None,
        "final_score": shots[0]["n_shots_this_hole"], "final_bucket": bucket_,
        "category": ("FW_HIT_BAD" if tee["lie_after"] == "FAIRWAY" and bucket_ in ("Bogey", "Double+") else
                     "FW_MISS_GOOD" if tee["lie_after"] != "FAIRWAY" and bucket_ in ("Par", "Birdie+") else
                     "FW_HIT_GOOD" if tee["lie_after"] == "FAIRWAY" else "FW_MISS_BAD"),
    })
with open(HERE / "neo_fairway_paradox_cases.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(paradox_fw[0].keys()))
    w.writeheader()
    w.writerows(paradox_fw)
cat_counts = Counter(r["category"] for r in paradox_fw)
print(f"\nneo_fairway_paradox_cases.csv: {len(paradox_fw)} rows (all non-par3 hole-plays, 3 players). category counts: {dict(cat_counts)}")


# ============================================================
# 4. neo_gir_paradox_cases.csv
# ============================================================
paradox_gir = []
for (pc, rnd, hole), shots in by_prh3.items():
    par = int(shots[0]["par"])
    final_stp = int(shots[0]["final_score_to_par"])
    bucket_ = "Birdie+" if final_stp <= -1 else ("Par" if final_stp == 0 else ("Bogey" if final_stp == 1 else "Double+"))
    gir = shots[0]["gir_hole"] == "True"
    # find the GIR-achieving shot's remaining distance (first-putt distance) or the miss lie+distance
    gir_shot = next((s for s in shots if s["lie_after"] == "GREEN"), None)
    first_putt_dist = gir_shot["remaining_distance_after_yd"] if gir and gir_shot else None
    miss_shot = next((s for s in shots[1:] if s["lie_after"] in ("ROUGH", "BUNKER", "GREENSIDE_BUNKER", "FRINGE")), None) if not gir else None
    paradox_gir.append({
        "player": PLAYERS[pc], "round": rnd, "hole": hole, "par": par, "gir": gir,
        "first_putt_distance_yd": first_putt_dist,
        "miss_lie": miss_shot["lie_after"] if miss_shot else None,
        "miss_remaining_yd": miss_shot["remaining_distance_after_yd"] if miss_shot else None,
        "putts_fixed": shots[0]["final_putts_fixed"], "final_score": shots[0]["n_shots_this_hole"], "final_bucket": bucket_,
        "category": f"{'GIR' if gir else 'GIRMISS'}_TO_{bucket_.replace('+','PLUS')}",
    })
with open(HERE / "neo_gir_paradox_cases.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(paradox_gir[0].keys()))
    w.writeheader()
    w.writerows(paradox_gir)
cat_counts2 = Counter(r["category"] for r in paradox_gir)
print(f"neo_gir_paradox_cases.csv: {len(paradox_gir)} rows. category counts: {dict(cat_counts2)}")


# ============================================================
# 5. approach_proximity_conversion.csv -- distance bands x
#    (3 players + field), birdie conversion from GIR
# ============================================================
prox_rows = []
bands = [(0, 3), (3, 6), (6, 9), (9, 12), (12, 999)]
def band_label(lo, hi):
    return f"{lo}-{hi}yd" if hi < 999 else f"{lo}yd+"

# field distribution
field_gir_fp = defaultdict(list)
for s in field_shots:
    if s["lie_after"] != "GREEN":
        continue
    final = field_hole_by_key[(s["player_code"], s["round"], s["hole"])]
    if not final["gir"]:
        continue
    # is this the FIRST green-arrival shot (i.e. the GIR shot)?
    pass
# recompute properly: first GREEN-state shot per player-hole among GIR holes
field_first_putt = {}
by_prh_field = defaultdict(list)
for s in field_shots:
    by_prh_field[(s["player_code"], s["round"], s["hole"])].append(s)
for key, shots in by_prh_field.items():
    shots.sort(key=lambda s: s["shot_number"])
    final = field_hole_by_key[key]
    if not final["gir"]:
        continue
    g = next((s for s in shots if s["lie_after"] == "GREEN"), None)
    if g and g["remaining_after_yd"] is not None:
        field_first_putt[key] = (g["remaining_after_yd"], final["score_to_par"])

for lo, hi in bands:
    label = band_label(lo, hi)
    for pc, pname in [*PLAYERS.items(), (None, "FIELD(107)")]:
        if pc is None:
            vals = [(d, stp) for d, stp in field_first_putt.values() if lo < d <= hi or (hi == 999 and d > lo)]
        else:
            vals = []
            for (ppc, rnd, hole), shots in by_prh3.items():
                if ppc != pc:
                    continue
                if shots[0]["gir_hole"] != "True":
                    continue
                g = next((s for s in shots if s["lie_after"] == "GREEN"), None)
                if g is None or g["remaining_distance_after_yd"] in (None, ""):
                    continue
                d = float(g["remaining_distance_after_yd"])
                if lo < d <= hi or (hi == 999 and d > lo):
                    vals.append((d, int(shots[0]["final_score_to_par"])))
        n = len(vals)
        if n == 0:
            prox_rows.append({"distance_band": label, "player": pname, "n": 0, "birdie_pct": None, "par_pct": None, "bogey_plus_pct": None})
            continue
        birdie = sum(1 for d, stp in vals if stp <= -1)
        par = sum(1 for d, stp in vals if stp == 0)
        bogeyplus = sum(1 for d, stp in vals if stp >= 1)
        prox_rows.append({"distance_band": label, "player": pname, "n": n,
                           "birdie_pct": round(birdie / n, 3), "par_pct": round(par / n, 3),
                           "bogey_plus_pct": round(bogeyplus / n, 3)})

with open(HERE / "approach_proximity_conversion.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(prox_rows[0].keys()))
    w.writeheader()
    w.writerows(prox_rows)
print(f"\napproach_proximity_conversion.csv: {len(prox_rows)} rows")
for r in prox_rows:
    print(f"  {r['distance_band']:8s} {r['player']:14s} n={r['n']:4d} birdie%={r['birdie_pct']} par%={r['par_pct']} bogey+%={r['bogey_plus_pct']}")

print("\nDone: states, next-shot-quality, fw-paradox, gir-paradox, proximity-conversion")
