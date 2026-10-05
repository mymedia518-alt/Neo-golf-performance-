"""Blue Heron 18-hole field mechanism: for each hole, real field-wide
rates (FW/GIR/recovery/penalty/outcome) PLUS a Shot-Chain-based
classification of what kind of failure actually drove the Bogey+/Double+
outcomes there (not just "this hole has a high average"). Reuses
field_chain.json (already fixed-putts, 5958 hole-plays, 24993 shots,
107 players) -- no new RAW query.
"""
from __future__ import annotations
import json, csv, statistics
from pathlib import Path
from collections import defaultdict, Counter

HERE = Path(__file__).parent
field = json.loads((HERE / "field_chain.json").read_text())
holes = field["hole_summaries"]
shots = field["shot_records"]
PAR_YDS = json.loads((HERE / "klpga_tournament_18hole_par_yardage.json").read_text())
shots_by_key = defaultdict(list)
for s in shots:
    shots_by_key[(s["player_code"], s["round"], s["hole"])].append(s)
for k in shots_by_key:
    shots_by_key[k].sort(key=lambda s: s["shot_number"])

PENALTY_STATES = {"4", "5", "7", "8"}


def classify_record(ss, par):
    """Same stage logic as the attribution audit, applied here to field
    chain shot_records (which carry lie_before/lie_after/is_penalty/
    state via remaining_after_yd etc already)."""
    fw_hit = ss[0]["lie_after"] == "FAIRWAY"
    gir_shot = next((s["shot_number"] for s in ss if s["lie_after"] == "GREEN"), None)
    gir = gir_shot is not None and gir_shot <= par - 2
    green_idx = next((i for i, s in enumerate(ss) if s["lie_after"] in ("GREEN", "HOLED")), len(ss) - 1)
    pre_green = ss[: green_idx + 1]
    penalty_pre_green = any(s["is_penalty"] for s in pre_green)
    putts = ss[0]["putts_fixed"]
    if penalty_pre_green:
        return "PENALTY"
    if par != 3 and not fw_hit:
        return "TEE"
    if not gir:
        return "APPROACH"
    if putts >= 3:
        return "PUTTING"
    return "NONE"


rows = []
for hole in range(1, 19):
    hole_rows = [h for h in holes if h["hole"] == hole]
    par = hole_rows[0]["par"]
    n = len(hole_rows)
    vals = [h["score_to_par"] for h in hole_rows]
    fw_rows = [h for h in hole_rows if par != 3]
    fw_hit_n = sum(1 for h in fw_rows if h["tee_lie"] == "FAIRWAY")
    gir_n = sum(1 for h in hole_rows if h["gir"])
    girmiss_rows = [h for h in hole_rows if not h["gir"]]
    girmiss_parsave = sum(1 for h in girmiss_rows if h["score_to_par"] <= 0)
    fwmiss_rows = [h for h in fw_rows if h["tee_lie"] != "FAIRWAY"]
    fwmiss_gir = sum(1 for h in fwmiss_rows if h["gir"])
    fwhit_rows = [h for h in fw_rows if h["tee_lie"] == "FAIRWAY"]
    fwhit_gir = sum(1 for h in fwhit_rows if h["gir"])
    rough_tee_rows = [h for h in fw_rows if h["tee_lie"] == "ROUGH"]
    rough_gir = sum(1 for h in rough_tee_rows if h["gir"])
    penalty_n = sum(1 for h in hole_rows if any(s == str(c) for c in (4, 5, 7, 8) for s in h["state_sequence"]))

    # Shot-chain classification of the bad outcomes (Bogey+)
    bad_rows = [h for h in hole_rows if h["score_to_par"] >= 1]
    chain_cats = Counter()
    for h in bad_rows:
        ss = shots_by_key.get((h["player_code"], h["round"], hole))
        if not ss:
            continue
        cat = classify_record(ss, par)
        chain_cats[cat] += 1
    total_bad = sum(chain_cats.values())
    dominant = "N/A"
    dominant_pct = None
    if total_bad >= 10:
        top_cat, top_n = chain_cats.most_common(1)[0]
        dominant_pct = top_n / total_bad
        if dominant_pct >= 0.45:
            dominant = top_cat + "-DRIVEN"
        else:
            dominant = "MIXED"
    else:
        dominant = "UNRESOLVED(low n)"

    rows.append({
        "hole": hole, "par": par, "yds": PAR_YDS[str(hole)]["yds"], "field_n": n,
        "field_avg_score_to_par": round(statistics.mean(vals), 3),
        "birdie_pct": round(sum(1 for v in vals if v <= -1) / n, 3),
        "par_pct": round(sum(1 for v in vals if v == 0) / n, 3),
        "bogey_plus_pct": round(sum(1 for v in vals if v >= 1) / n, 3),
        "double_plus_pct": round(sum(1 for v in vals if v >= 2) / n, 3),
        "fw_hit_pct": round(fw_hit_n / len(fw_rows), 3) if par != 3 else None,
        "gir_pct": round(gir_n / n, 3),
        "fwmiss_to_gir_pct": round(fwmiss_gir / len(fwmiss_rows), 3) if fwmiss_rows else None,
        "fwhit_to_gir_pct": round(fwhit_gir / len(fwhit_rows), 3) if fwhit_rows else None,
        "rough_tee_to_gir_pct": round(rough_gir / len(rough_tee_rows), 3) if rough_tee_rows else None,
        "girmiss_to_parsave_pct": round(girmiss_parsave / len(girmiss_rows), 3) if girmiss_rows else None,
        "penalty_rate_pct": round(penalty_n / n, 3),
        "n_bad_outcomes": total_bad,
        "bad_outcome_chain_breakdown": dict(chain_cats),
        "dominant_failure_mode": dominant,
        "dominant_pct_of_bad": round(dominant_pct, 3) if dominant_pct else None,
    })

print("=== Blue Heron 18-hole field mechanism (n=331 player-rounds each) ===")
for r in rows:
    print(f"H{r['hole']:2d} par{r['par']} {r['yds']}yd: avg={r['field_avg_score_to_par']:+.3f} "
          f"birdie={r['birdie_pct']:.0%} bogey+={r['bogey_plus_pct']:.0%} dbl+={r['double_plus_pct']:.0%} "
          f"FW%={r['fw_hit_pct']} GIR%={r['gir_pct']:.0%} FWmiss->GIR={r['fwmiss_to_gir_pct']} "
          f"GIRmiss->ParSave={r['girmiss_to_parsave_pct']} | {r['dominant_failure_mode']} "
          f"({r['dominant_pct_of_bad']}, n_bad={r['n_bad_outcomes']}) {r['bad_outcome_chain_breakdown']}")

with open(HERE / "blue_heron_score_mechanism_by_hole.csv", "w", newline="", encoding="utf-8") as f:
    fieldnames = list(rows[0].keys())
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for r in rows:
        rr = dict(r)
        rr["bad_outcome_chain_breakdown"] = json.dumps(rr["bad_outcome_chain_breakdown"])
        w.writerow(rr)
print("\nWrote blue_heron_score_mechanism_by_hole.csv")

(HERE / "blue_heron_hole_mechanism.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
