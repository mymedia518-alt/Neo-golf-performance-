from __future__ import annotations
import json, csv, statistics
from pathlib import Path
from collections import defaultdict, Counter

HERE = Path(__file__).parent
field = json.loads((HERE / "field_chain.json").read_text())
field_shots = field["shot_records"]
field_hole_by_key = {(r["player_code"], r["round"], r["hole"]): r for r in field["hole_summaries"]}
three_rows = list(csv.DictReader(open(HERE / "three_player_spatial_chain_master.csv", encoding="utf-8")))
PLAYERS = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}

by_prh3 = defaultdict(list)
for r in three_rows:
    by_prh3[(r["player_code"], int(r["round"]), int(r["hole"]))].append(r)
for k in by_prh3:
    by_prh3[k].sort(key=lambda r: int(r["shot_number"]))

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


def band_of(lie, d):
    if lie in OFF_GREEN_LIES:
        return off_green_band(d)
    if lie in GREEN_LIES:
        return green_band(d)
    return None


# ============================================================
# 1. same_location_player_execution.csv -- "location" defined as
#    (lie_after, real-yard remaining distance within +-1yd), matched
#    across ANY two of the three players regardless of hole/round
#    (NOT raw coordinate matching across different holes, which would
#    be meaningless -- lie + real-yard proximity-to-pin is the
#    comparable quantity across holes).
# ============================================================
all_shots3 = []
for (pc, rnd, hole), shots in by_prh3.items():
    for i, s in enumerate(shots):
        rem = s["remaining_distance_after_yd"]
        if rem in (None, "") or s["lie_after"] not in (OFF_GREEN_LIES | GREEN_LIES):
            continue
        all_shots3.append({"player": PLAYERS[pc], "round": rnd, "hole": hole, "shot_number": int(s["shot_number"]),
                            "lie_after": s["lie_after"], "remaining_after_yd": float(rem),
                            "next_shot_idx": i + 1, "shots": shots})

same_loc = []
TOL = 1.0
for i in range(len(all_shots3)):
    for j in range(i + 1, len(all_shots3)):
        a, b = all_shots3[i], all_shots3[j]
        if a["player"] == b["player"]:
            continue
        if a["lie_after"] != b["lie_after"]:
            continue
        if abs(a["remaining_after_yd"] - b["remaining_after_yd"]) > TOL:
            continue
        final_a = int(a["shots"][0]["final_score_to_par"])
        final_b = int(b["shots"][0]["final_score_to_par"])
        # what happened NEXT for each (strokes-to-finish from this point)
        strokes_to_finish_a = len(a["shots"]) - a["next_shot_idx"] + 1
        strokes_to_finish_b = len(b["shots"]) - b["next_shot_idx"] + 1
        same_loc.append({
            "lie": a["lie_after"], "remaining_a_yd": a["remaining_after_yd"], "remaining_b_yd": b["remaining_after_yd"],
            "player_a": a["player"], "round_a": a["round"], "hole_a": a["hole"], "strokes_to_finish_a": strokes_to_finish_a,
            "final_score_to_par_a": final_a,
            "player_b": b["player"], "round_b": b["round"], "hole_b": b["hole"], "strokes_to_finish_b": strokes_to_finish_b,
            "final_score_to_par_b": final_b,
            "strokes_to_finish_diff": strokes_to_finish_a - strokes_to_finish_b,
        })

same_loc_diverging = [r for r in same_loc if r["strokes_to_finish_diff"] != 0]
with open(HERE / "same_location_player_execution.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(same_loc[0].keys()))
    w.writeheader()
    w.writerows(same_loc)
print(f"same_location_player_execution.csv: {len(same_loc)} matched pairs (tol=+-{TOL}yd), "
      f"{len(same_loc_diverging)} with a different strokes-to-finish")
for r in sorted(same_loc_diverging, key=lambda x: -abs(x["strokes_to_finish_diff"]))[:10]:
    print(f"  {r['lie']} ~{r['remaining_a_yd']}/{r['remaining_b_yd']}yd: "
          f"{r['player_a']} R{r['round_a']}H{r['hole_a']} finish_from_here={r['strokes_to_finish_a']} vs "
          f"{r['player_b']} R{r['round_b']}H{r['hole_b']} finish_from_here={r['strokes_to_finish_b']}")


# ============================================================
# 2. field_vs_player_location_value.csv -- two separate layers,
#    never mixed: field value per (lie,band), player value per
#    (lie,band), joined only for the final 4-quadrant label
# ============================================================
field_bins = defaultdict(list)
for s in field_shots:
    if s["shot_number"] == 1 or s["remaining_after_yd"] is None:
        continue
    band = band_of(s["lie_after"], s["remaining_after_yd"])
    if band is None:
        continue
    final = field_hole_by_key[(s["player_code"], s["round"], s["hole"])]
    field_bins[(s["lie_after"], band)].append(final["score_to_par"])

player_bins = defaultdict(lambda: defaultdict(list))
for (pc, rnd, hole), shots in by_prh3.items():
    final_stp = int(shots[0]["final_score_to_par"])
    for s in shots[1:]:
        rem = s["remaining_distance_after_yd"]
        if rem in (None, ""):
            continue
        band = band_of(s["lie_after"], float(rem))
        if band is None:
            continue
        player_bins[PLAYERS[pc]][(s["lie_after"], band)].append(final_stp)

field_avg_all = statistics.mean(v for vals in field_bins.values() for v in vals)
fvp_rows = []
for (lie, band), fvals in field_bins.items():
    if len(fvals) < 5:
        continue
    field_avg = statistics.mean(fvals)
    field_label = "유리" if field_avg < field_avg_all - 0.1 else ("위험" if field_avg > field_avg_all + 0.1 else "중립")
    for pname in PLAYERS.values():
        pvals = player_bins[pname].get((lie, band), [])
        if len(pvals) < 3:
            fvp_rows.append({"lie": lie, "distance_band": band, "field_n": len(fvals), "field_avg_score_to_par": round(field_avg, 3),
                              "field_label": field_label, "player": pname, "player_n": len(pvals),
                              "player_avg_score_to_par": None, "player_label": "UNKNOWN(n<3)", "quadrant": "UNKNOWN(player n<3)"})
            continue
        p_avg = statistics.mean(pvals)
        p_label = "유리" if p_avg < field_avg - 0.15 else ("불리" if p_avg > field_avg + 0.15 else "field수준")
        if field_label == "유리" and p_label != "불리":
            quad = "필드유리/선수유리"
        elif field_label == "유리" and p_label == "불리":
            quad = "필드유리/선수불리"
        elif field_label == "위험" and p_label == "유리":
            quad = "필드불리/선수유리"
        elif field_label == "위험":
            quad = "필드불리/선수불리"
        else:
            quad = "필드중립"
        fvp_rows.append({"lie": lie, "distance_band": band, "field_n": len(fvals), "field_avg_score_to_par": round(field_avg, 3),
                          "field_label": field_label, "player": pname, "player_n": len(pvals),
                          "player_avg_score_to_par": round(p_avg, 3), "player_label": p_label, "quadrant": quad})

with open(HERE / "field_vs_player_location_value.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(fvp_rows[0].keys()))
    w.writeheader()
    w.writerows(fvp_rows)
print(f"\nfield_vs_player_location_value.csv: {len(fvp_rows)} rows")
interesting = [r for r in fvp_rows if r["quadrant"] in ("필드유리/선수불리", "필드불리/선수유리")]
print(f"  interesting (field/player diverge): n={len(interesting)}")
for r in interesting:
    print(f"  {r['lie']} {r['distance_band']}: field_n={r['field_n']} field_avg={r['field_avg_score_to_par']} | "
          f"{r['player']} n={r['player_n']} avg={r['player_avg_score_to_par']} -> {r['quadrant']}")

print("\nDone: same-location-execution, field-vs-player location value")
