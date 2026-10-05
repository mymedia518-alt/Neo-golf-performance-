from __future__ import annotations
import csv, json
from pathlib import Path

HERE = Path(__file__).parent

rows = []

# 1. Lower-ranked player beats the winner outright (from existing counterexamples CSV)
for r in csv.DictReader(open(HERE / "three_player_counterexamples.csv", encoding="utf-8")):
    rows.append({"category": "LOWER_PLAYER_BEATS_RYU", "round": r["round"], "hole": r["hole"], "par": r["par"],
                 "detail": f"Ryu={r['ryu_score']}({r['ryu_bucket']}) vs {r['opponent']}={r['opponent_score']}({r['opponent_bucket']}) margin={r['margin']}"})

# 2. FW hit -> Bogey+ and FW miss -> good (from fairway paradox cases, 3 focal players)
fwp = list(csv.DictReader(open(HERE / "neo_fairway_paradox_cases.csv", encoding="utf-8")))
for r in fwp:
    if r["category"] == "FW_HIT_BAD":
        rows.append({"category": "FW_HIT_BOGEY_PLUS", "round": r["round"], "hole": r["hole"], "par": r["par"],
                     "detail": f"{r['player']} tee=FAIRWAY -> {r['final_bucket']} ({r['final_score']})"})
    elif r["category"] == "FW_MISS_GOOD" and r["final_bucket"] == "Birdie+":
        rows.append({"category": "FW_MISS_BIRDIE", "round": r["round"], "hole": r["hole"], "par": r["par"],
                     "detail": f"{r['player']} tee={r['tee_lie']} -> {r['final_bucket']} ({r['final_score']})"})

# 3. GIR -> Bogey+ and GIR miss -> Par (from gir paradox cases)
girp = list(csv.DictReader(open(HERE / "neo_gir_paradox_cases.csv", encoding="utf-8")))
for r in girp:
    if r["category"] in ("GIR_TO_Bogey", "GIR_TO_DoublePLUS"):
        rows.append({"category": "GIR_BOGEY_PLUS", "round": r["round"], "hole": r["hole"], "par": r["par"],
                     "detail": f"{r['player']} GIR achieved, putts={r['putts_fixed']} -> {r['final_bucket']} ({r['final_score']})"})
    elif r["category"] == "GIRMISS_TO_Par" :
        pass  # too many (45) to list individually; summarized in report text instead

# 4. Same-start / same-miss divergence (already-validated cases)
for r in csv.DictReader(open(HERE / "three_player_same_start_different_end.csv", encoding="utf-8")):
    rows.append({"category": "SAME_START_DIFFERENT_END", "round": r["round"], "hole": r["hole"], "par": r["par"],
                 "detail": f"{r['player_a']}({r['a_remaining_after_tee_yd']}yd)={r['a_score']}({r['a_bucket']}) vs "
                           f"{r['player_b']}({r['b_remaining_after_tee_yd']}yd)={r['b_score']}({r['b_bucket']}) tol={r['tolerance_yd']}yd"})
for r in csv.DictReader(open(HERE / "three_player_same_miss_different_recovery.csv", encoding="utf-8")):
    rows.append({"category": "SAME_MISS_DIFFERENT_RECOVERY", "round": r["round"], "hole": r["hole"], "par": r["par"],
                 "detail": f"miss={r['miss_lie']} {r['player_a']}({r['a_miss_dist_yd']}yd)={r['a_score']}({r['a_bucket']}) vs "
                           f"{r['player_b']}({r['b_miss_dist_yd']}yd)={r['b_score']}({r['b_bucket']})"})

with open(HERE / "blue_heron_counterexamples.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["category", "round", "hole", "par", "detail"])
    w.writeheader()
    w.writerows(rows)

from collections import Counter
cat_n = Counter(r["category"] for r in rows)
print(f"blue_heron_counterexamples.csv: {len(rows)} rows")
for cat, n in cat_n.items():
    print(f"  {cat}: n={n}")
print(f"\n(for reference, not individually listed: GIRMISS_to_Par n={sum(1 for r in girp if r['category']=='GIRMISS_TO_Par')})")
