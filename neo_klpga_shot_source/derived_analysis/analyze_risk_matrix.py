from __future__ import annotations
import json, csv, statistics
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
field = json.loads((HERE / "field_chain.json").read_text())
field_holes = field["hole_summaries"]
PLAYERS = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}

# field-wide per-hole stats, all 18 holes
field_by_hole = defaultdict(list)
for r in field_holes:
    field_by_hole[r["hole"]].append(r["score_to_par"])

field_all_par4 = [v for r in field_holes if r["par"] == 4 for v in [r["score_to_par"]]]
field_par4_avg = statistics.mean(field_all_par4)

player_by_hole = defaultdict(lambda: defaultdict(list))
for r in field_holes:
    if r["player_code"] in PLAYERS:
        player_by_hole[PLAYERS[r["player_code"]]][r["hole"]].append(r["score_to_par"])

rows = []
for hole in range(1, 19):
    fvals = field_by_hole[hole]
    par = next(r["par"] for r in field_holes if r["hole"] == hole)
    baseline = field_par4_avg if par == 4 else statistics.mean(v for r in field_holes if r["par"] == par for v in [r["score_to_par"]])
    f_avg = statistics.mean(fvals)
    course_risk = "높음(course risk)" if f_avg > baseline + 0.1 else ("낮음" if f_avg < baseline - 0.1 else "평균수준")
    for pname in PLAYERS.values():
        pvals = player_by_hole[pname][hole]
        n_p = len(pvals)
        if n_p < 3:
            rows.append({"hole": hole, "par": par, "field_n": len(fvals), "field_avg_score_to_par": round(f_avg, 3),
                         "course_risk_label": course_risk, "player": pname, "player_n": n_p,
                         "player_avg_score_to_par": None, "player_risk_label": "UNKNOWN(n<3)",
                         "quadrant": "UNKNOWN(n<3)"})
            continue
        p_avg = statistics.mean(pvals)
        p_dbl = sum(1 for v in pvals if v >= 2)
        player_risk = "높음" if p_avg > f_avg + 0.3 else ("낮음" if p_avg < f_avg - 0.3 else "평균수준")
        if course_risk == "낮음" and player_risk == "낮음":
            quad = "1.코스위험낮음/선수위험낮음"
        elif course_risk == "높음" and player_risk == "낮음":
            quad = "2.코스위험높음/선수위험낮음"
        elif course_risk == "낮음" and player_risk == "높음":
            quad = "3.코스위험낮음/선수위험높음"
        elif course_risk == "높음" and player_risk == "높음":
            quad = "4.코스위험높음/선수위험높음"
        else:
            quad = "경계(평균수준 포함)"
        rows.append({"hole": hole, "par": par, "field_n": len(fvals), "field_avg_score_to_par": round(f_avg, 3),
                     "course_risk_label": course_risk, "player": pname, "player_n": n_p,
                     "player_avg_score_to_par": round(p_avg, 3), "player_double_plus_n": p_dbl,
                     "player_risk_label": player_risk, "quadrant": quad})

with open(HERE / "course_player_risk_matrix.csv", "w", newline="", encoding="utf-8") as f:
    fieldnames = ["hole", "par", "field_n", "field_avg_score_to_par", "course_risk_label", "player", "player_n",
                  "player_avg_score_to_par", "player_double_plus_n", "player_risk_label", "quadrant"]
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k) for k in fieldnames})

print("=== Course x Player risk matrix, all 18 holes ===")
for hole in range(1, 19):
    hole_rows = [r for r in rows if r["hole"] == hole]
    print(f"Hole {hole} (par{hole_rows[0]['par']}) field_avg={hole_rows[0]['field_avg_score_to_par']:+.3f} [{hole_rows[0]['course_risk_label']}]: " +
          " | ".join(f"{r['player']}={r.get('player_avg_score_to_par')}[{r['player_risk_label']}]" for r in hole_rows))
print("\nWrote course_player_risk_matrix.csv")
