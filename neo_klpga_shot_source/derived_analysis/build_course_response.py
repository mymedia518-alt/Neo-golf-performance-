from __future__ import annotations
import json, csv, statistics
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent
mech = json.loads((HERE / "blue_heron_hole_mechanism.json").read_text())
mech_by_hole = {m["hole"]: m for m in mech}
chain = json.loads((HERE / "three_player_attribution_chain.json").read_text())["records"]
PLAYERS = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}

# ============================================================
# three_player_course_response_comparison.csv
# ============================================================
rows = []
for pc, pname in PLAYERS.items():
    by_mode = defaultdict(list)
    for r in chain:
        if r["player_code"] != pc:
            continue
        mode = mech_by_hole[r["hole"]]["dominant_failure_mode"]
        by_mode[mode].append(r)
    for mode, recs in by_mode.items():
        n = len(recs)
        rows.append({
            "player": pname, "hole_mechanism": mode, "n_hole_plays": n,
            "avg_score_to_par": round(statistics.mean(r["score_to_par"] for r in recs), 3),
            "birdie_pct": round(sum(1 for r in recs if r["score_bucket"] == "Birdie+") / n, 3),
            "par_pct": round(sum(1 for r in recs if r["score_bucket"] == "Par") / n, 3),
            "bogey_plus_pct": round(sum(1 for r in recs if r["score_bucket"] in ("Bogey", "Double", "TriplePlus")) / n, 3),
            "double_plus_pct": round(sum(1 for r in recs if r["score_bucket"] in ("Double", "TriplePlus")) / n, 3),
        })
with open(HERE / "three_player_course_response_comparison.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print("=== Course response by hole-mechanism type ===")
for r in sorted(rows, key=lambda x: (x["hole_mechanism"], x["player"])):
    print(f"  {r['hole_mechanism']:22s} {r['player']}: n={r['n_hole_plays']:3d} avg={r['avg_score_to_par']:+.3f} "
          f"birdie={r['birdie_pct']:.0%} par={r['par_pct']:.0%} bogey+={r['bogey_plus_pct']:.0%} dbl+={r['double_plus_pct']:.0%}")


# ============================================================
# Hierarchy test: GIR -> (miss) ParSave -> (tee miss) recover to GIR ->
# (adverse) contain at Bogey -> (good approach) convert to Birdie
# ============================================================
print("\n=== Hierarchy test (5 layers), all 3 players, all 72 holes each ===")
for pc, pname in PLAYERS.items():
    recs = [r for r in chain if r["player_code"] == pc]
    nonpar3 = [r for r in recs if r["par"] != 3]
    gir_n = sum(1 for r in recs if r["gir"])
    girmiss = [r for r in recs if not r["gir"]]
    girmiss_parsave = sum(1 for r in girmiss if r["score_bucket"] in ("Birdie+", "Par"))
    teemiss = [r for r in nonpar3 if not r["fw_hit"]]
    teemiss_recover_gir = sum(1 for r in teemiss if r["gir"])
    doubleplus = sum(1 for r in recs if r["score_bucket"] in ("Double", "TriplePlus"))
    adverse = [r for r in recs if (r["par"] != 3 and not r["fw_hit"]) or not r["gir"] or r["first_failure_stage"] == "PENALTY"]
    adverse_contained = sum(1 for r in adverse if r["score_bucket"] in ("Par", "Bogey", "Birdie+"))
    birdiefromgir = sum(1 for r in recs if r["gir"] and r["score_bucket"] == "Birdie+")
    print(f"  {pname}: 1.GIR%={gir_n/len(recs):.1%} | 2.GIRmiss->ParSave%={girmiss_parsave/len(girmiss):.1%}(n={len(girmiss)}) "
          f"| 3.TeeMiss->GIR%={teemiss_recover_gir/len(teemiss):.1%}(n={len(teemiss)}) "
          f"| 4.Adverse->NotDouble+%={adverse_contained/len(adverse):.1%}(n={len(adverse)}, Double+ total={doubleplus}) "
          f"| 5.GIR->Birdie%={birdiefromgir/gir_n:.1%}")
