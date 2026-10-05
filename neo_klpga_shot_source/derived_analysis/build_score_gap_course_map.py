from __future__ import annotations
import json, csv
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
mech_by_hole = {m["hole"]: m for m in json.loads((HERE / "blue_heron_hole_mechanism.json").read_text())}
chain = json.loads((HERE / "three_player_attribution_chain.json").read_text())["records"]
by_hole_key = {(r["player_code"], r["round"], r["hole"]): r for r in chain}
PLAYERS = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}
PAIRS = [("9115", "9708", "유해란", "이재윤"), ("9708", "9111", "이재윤", "박서현"), ("9115", "9111", "유해란", "박서현")]

# ============================================================
# three_player_score_gap_course_map.csv -- every hole-play x pair, with
# hole mechanism attached
# ============================================================
gap_rows = []
for a, b, an, bn in PAIRS:
    for rnd in (1, 2, 3, 4):
        for hole in range(1, 19):
            ra, rb = by_hole_key[(a, rnd, hole)], by_hole_key[(b, rnd, hole)]
            diff = ra["strokes"] - rb["strokes"]
            m = mech_by_hole[hole]
            gap_rows.append({
                "pair": f"{an}-{bn}", "round": rnd, "hole": hole, "par": ra["par"],
                "a_strokes": ra["strokes"], "b_strokes": rb["strokes"], "diff": diff,
                "hole_mechanism": m["dominant_failure_mode"], "field_avg_score_to_par": m["field_avg_score_to_par"],
            })
with open(HERE / "three_player_score_gap_course_map.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(gap_rows[0].keys()))
    w.writeheader()
    w.writerows(gap_rows)
print(f"three_player_score_gap_course_map.csv: {len(gap_rows)} rows")


# ============================================================
# three_player_top_gap_holes.csv -- top 10 per pair, with mechanism
# ============================================================
top_rows = []
for a, b, an, bn in PAIRS:
    nz = [r for r in gap_rows if r["pair"] == f"{an}-{bn}" and r["diff"] != 0]
    nz.sort(key=lambda r: -abs(r["diff"]))
    for rank, r in enumerate(nz[:10], 1):
        top_rows.append({**r, "rank": rank})
with open(HERE / "three_player_top_gap_holes.csv", "w", newline="", encoding="utf-8") as f:
    fieldnames = ["rank"] + [k for k in top_rows[0].keys() if k != "rank"]
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(top_rows)
print(f"three_player_top_gap_holes.csv: {len(top_rows)} rows")
print("\n=== Top gap holes, Ryu-Park, with hole mechanism ===")
for r in top_rows:
    if r["pair"] == "유해란-박서현":
        print(f"  #{r['rank']} R{r['round']}H{r['hole']} par{r['par']} [{r['hole_mechanism']}] diff={r['diff']:+d}")
