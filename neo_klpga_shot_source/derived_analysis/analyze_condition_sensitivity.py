"""Tests whether 'same-start-different-end' and 'same-miss-different-
recovery' case counts survive under multiple explicit tolerance levels,
instead of committing to one arbitrary threshold."""
from __future__ import annotations
import json, csv
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
rows = list(csv.DictReader(open(HERE / "three_player_spatial_chain_master.csv", encoding="utf-8")))
PLAYERS = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}

by_prh = defaultdict(list)
for r in rows:
    key = (r["player_code"], int(r["round"]), int(r["hole"]))
    by_prh[key].append(r)
for k in by_prh:
    by_prh[k].sort(key=lambda r: int(r["shot_number"]))

hole_final = {}
for (pc, rnd, hole), shots in by_prh.items():
    last = shots[-1]
    hole_final[(pc, rnd, hole)] = {
        "par": int(last["par"]), "strokes": int(last["n_shots_this_hole"]),
        "score_to_par": int(last["n_shots_this_hole"]) - int(last["par"]),
    }

def bucket(stp):
    if stp <= -1: return "Birdie+"
    if stp == 0: return "Par"
    if stp == 1: return "Bogey"
    return "Double+"

# ---- same-start-different-end sensitivity: tee shots both FAIRWAY, par!=3 ----
tee_shots = defaultdict(dict)
for (pc, rnd, hole), shots in by_prh.items():
    s1 = shots[0]
    if s1["lie_after"] != "FAIRWAY":
        continue
    rem = s1["remaining_distance_after_yd"]
    if rem in (None, ""):
        continue
    tee_shots[(rnd, hole)][pc] = float(rem)

sens_rows = []
for tol in (3, 5, 10):
    n_found = 0
    for (rnd, hole), by_pc in tee_shots.items():
        par = hole_final[(list(by_pc.keys())[0], rnd, hole)]["par"]
        if par == 3:
            continue
        codes = list(by_pc.keys())
        for i in range(len(codes)):
            for j in range(i + 1, len(codes)):
                a, b = codes[i], codes[j]
                if abs(by_pc[a] - by_pc[b]) > tol:
                    continue
                fa = hole_final[(a, rnd, hole)]
                fb = hole_final[(b, rnd, hole)]
                if bucket(fa["score_to_par"]) == bucket(fb["score_to_par"]):
                    continue
                n_found += 1
    sens_rows.append({"test": "same_start_different_end", "tolerance_yd": tol, "n_cases_found": n_found})

# ---- same-miss-different-recovery sensitivity: first non-green/fairway miss lie, pin proximity tolerance ----
miss_pos = defaultdict(dict)
for (pc, rnd, hole), shots in by_prh.items():
    m = next((s for s in shots if s["lie_after"] in ("ROUGH", "BUNKER", "GREENSIDE_BUNKER", "FRINGE") and int(s["shot_number"]) > 1), None)
    if m is None:
        continue
    rem = m["remaining_distance_after_yd"]
    if rem in (None, ""):
        continue
    miss_pos[(rnd, hole)][pc] = (m["lie_after"], float(rem))

for tol in (1, 2, 3, 5):
    n_found = 0
    for (rnd, hole), by_pc in miss_pos.items():
        codes = list(by_pc.keys())
        for i in range(len(codes)):
            for j in range(i + 1, len(codes)):
                a, b = codes[i], codes[j]
                lie_a, d_a = by_pc[a]
                lie_b, d_b = by_pc[b]
                if lie_a != lie_b:
                    continue
                if abs(d_a - d_b) > tol:
                    continue
                fa = hole_final[(a, rnd, hole)]
                fb = hole_final[(b, rnd, hole)]
                if bucket(fa["score_to_par"]) == bucket(fb["score_to_par"]):
                    continue
                n_found += 1
    sens_rows.append({"test": "same_miss_different_recovery", "tolerance_yd": tol, "n_cases_found": n_found})

print("=== Comparable-condition sensitivity ===")
for r in sens_rows:
    print(f"  {r['test']}: tol=±{r['tolerance_yd']}yd -> n={r['n_cases_found']}")

with open(HERE / "comparable_condition_sensitivity.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["test", "tolerance_yd", "n_cases_found"])
    for r in sens_rows:
        w.writerow([r["test"], r["tolerance_yd"], r["n_cases_found"]])
print("\nWrote comparable_condition_sensitivity.csv")
