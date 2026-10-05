from __future__ import annotations
import json, csv
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
data = json.loads((HERE / "neo_three_player_spatial_chain.json").read_text())
hole_summaries = data["hole_summaries"]
shot_records = data["shot_records"]
by_hole_key = {(r["player_code"], r["round"], r["hole"]): r for r in hole_summaries}
by_shot_key = defaultdict(list)
for r in shot_records:
    by_shot_key[(r["player_code"], r["round"], r["hole"])].append(r)
for k in by_shot_key:
    by_shot_key[k].sort(key=lambda r: r["shot_number"])
PLAYERS = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}

# ============================================================
# Score-preservation cases: 유해란's own Bogey+ hole-plays where the
# chain shows a real miss that did NOT become worse than Bogey (i.e.
# damage was capped at exactly 1-over, with an identifiable moment
# where it could have gone further but didn't)
# ============================================================
preservation = []
for r in hole_summaries:
    if r["player_code"] != "9115" or r["score_bucket"] != "Bogey":
        continue
    sh = by_shot_key[(r["player_code"], r["round"], r["hole"])]
    tee = sh[0]
    had_miss = tee["lie_after"] != "FAIRWAY" and r["par"] != 3
    had_green_miss = not r["gir"]
    if not (had_miss or had_green_miss):
        continue
    last_approach_before_green = next((s for s in sh if s["lie_after"] in ("GREEN", "FRINGE")), None)
    preservation.append({
        "round": r["round"], "hole": r["hole"], "par": r["par"], "score": r["strokes"],
        "tee_lie": tee["lie_after"], "gir": r["gir"], "putts": r["putts_fixed"],
        "recovery_endpoint_dist_yd": last_approach_before_green["remaining_distance_after_yd"] if last_approach_before_green else None,
        "state_sequence": "-".join(r["state_sequence"]),
    })

with open(HERE / "three_player_score_preservation_cases.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["round", "hole", "par", "score", "tee_lie", "gir", "putts", "recovery_endpoint_dist_yd", "state_sequence"])
    for r in preservation:
        w.writerow([r["round"], r["hole"], r["par"], r["score"], r["tee_lie"], r["gir"], r["putts"],
                    r["recovery_endpoint_dist_yd"], r["state_sequence"]])
print(f"score_preservation_cases: n={len(preservation)}")

# ============================================================
# Big-number spatial autopsy: all 6 Double+/TriplePlus events (3
# players), full shot-by-shot spatial detail
# ============================================================
big_rows = []
for r in hole_summaries:
    if r["score_bucket"] not in ("Double", "TriplePlus"):
        continue
    sh = by_shot_key[(r["player_code"], r["round"], r["hole"])]
    for s in sh:
        big_rows.append({
            "player": r["player_name"], "round": r["round"], "hole": r["hole"], "par": r["par"],
            "final_score": r["strokes"], "final_bucket": r["score_bucket"],
            "shot_number": s["shot_number"], "lie_before": s["lie_before"], "lie_after": s["lie_after"],
            "shot_distance_yd": s["shot_distance_yd"], "remaining_after_yd": s["remaining_distance_after_yd"],
            "end_x": s["end_x"], "end_y": s["end_y"], "pin_space_distance_mapunits": s["pin_space_distance_mapunits"],
        })

with open(HERE / "three_player_big_number_spatial_autopsy.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["player", "round", "hole", "par", "final_score", "final_bucket", "shot_number", "lie_before",
                "lie_after", "shot_distance_yd", "remaining_after_yd", "end_x", "end_y", "pin_space_distance_mapunits"])
    for r in big_rows:
        w.writerow([r["player"], r["round"], r["hole"], r["par"], r["final_score"], r["final_bucket"],
                    r["shot_number"], r["lie_before"], r["lie_after"], r["shot_distance_yd"],
                    r["remaining_after_yd"], r["end_x"], r["end_y"], r["pin_space_distance_mapunits"]])
print(f"big_number_spatial_autopsy rows: n={len(big_rows)} (6 events)")

# ============================================================
# Counterexamples CSV: formal list of cases where Ryu did NOT win the
# hole against Lee or Park (lower-ranked player wins or ties favorably)
# ============================================================
counters = []
for a, b, aname, bname in [("9115", "9708", "유해란", "이재윤"), ("9115", "9111", "유해란", "박서현")]:
    for rnd in (1, 2, 3, 4):
        for hole in range(1, 19):
            ra, rb = by_hole_key[(a, rnd, hole)], by_hole_key[(b, rnd, hole)]
            if rb["strokes"] < ra["strokes"]:
                counters.append({"round": rnd, "hole": hole, "par": ra["par"],
                                  "ryu_score": ra["strokes"], "ryu_bucket": ra["score_bucket"],
                                  "opponent": bname, "opponent_score": rb["strokes"], "opponent_bucket": rb["score_bucket"],
                                  "margin": ra["strokes"] - rb["strokes"]})

with open(HERE / "three_player_counterexamples.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["round", "hole", "par", "ryu_score", "ryu_bucket", "opponent", "opponent_score", "opponent_bucket", "margin"])
    for r in sorted(counters, key=lambda x: -x["margin"]):
        w.writerow([r["round"], r["hole"], r["par"], r["ryu_score"], r["ryu_bucket"], r["opponent"],
                    r["opponent_score"], r["opponent_bucket"], r["margin"]])
print(f"counterexamples (Ryu lost the hole outright): n={len(counters)}")
for r in sorted(counters, key=lambda x: -x["margin"])[:8]:
    print(f"  R{r['round']}H{r['hole']} par{r['par']}: Ryu={r['ryu_score']}({r['ryu_bucket']}) vs {r['opponent']}={r['opponent_score']}({r['opponent_bucket']}) margin={r['margin']}")
