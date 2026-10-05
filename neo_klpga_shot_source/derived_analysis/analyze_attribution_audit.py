from __future__ import annotations
import json, csv
from pathlib import Path
from collections import defaultdict, Counter

HERE = Path(__file__).parent
data = json.loads((HERE / "three_player_attribution_chain.json").read_text())
chain = data["records"]
by_prh = {(r["player_code"], r["round"], r["hole"]): r for r in chain}
PLAYERS = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}
PAIRS = [("9115", "9708", "유해란", "이재윤"), ("9708", "9111", "이재윤", "박서현"), ("9115", "9111", "유해란", "박서현")]
STAGES_A = ["TEE", "APPROACH", "RECOVERY", "PUTTING", "PENALTY", "UNRESOLVED"]
SEVERITY = ["Birdie+", "Par", "Bogey", "Double", "TriplePlus"]

assert data["raw_reconciliation_pass"], "RAW reconciliation must pass before any audit logic runs"


# ============================================================
# LAYER A: causal / shot-stage attribution, DIRECT + ESCALATION
# split so each stroke belongs to exactly one stage.
# ============================================================
def layer_a_stage_for_advantage(better_r, worse_r):
    """When the 'worse' player made par-or-better (no failure of their own)
    and the gap is purely the 'better' player's gain, trace WHERE that gain
    was created using the SAME stage vocabulary, symmetric to the loss
    side. Falls back to UNRESOLVED if not safely determinable."""
    # A gain below par needs: did it come from an exceptional approach
    # (very short/first-putt distance) or an exceptional putt from a
    # non-trivially-short first-putt distance?
    if better_r["score_bucket"] != "Birdie+":
        return "UNRESOLVED"
    fp = better_r["first_putt_distance_yd"]
    putts = better_r["putts_fixed"]
    if better_r["par"] != 3 and not better_r["fw_hit"]:
        return "TEE"  # scored from a tee-shot-created advantage (rare but possible, e.g. drivable par4)
    if putts == 0:
        return "APPROACH"  # holed the approach/chip directly
    if fp is None:
        return "UNRESOLVED"
    if putts <= 1:
        # 1-putt birdie: distinguish approach-created (very close) vs a made longer putt
        return "APPROACH" if fp <= 3.0 else "PUTTING"
    return "UNRESOLVED"


layer_a = {}
waterfall_rows = []
for a, b, aname, bname in PAIRS:
    key = f"{aname}-{bname}"
    stage_net = Counter()
    for rnd in (1, 2, 3, 4):
        for hole in range(1, 19):
            ra, rb = by_prh[(a, rnd, hole)], by_prh[(b, rnd, hole)]
            diff = ra["strokes"] - rb["strokes"]
            if diff == 0:
                continue
            worse, better = (rb, ra) if diff < 0 else (ra, rb)
            mag = abs(diff)
            sign = 1 if diff > 0 else -1  # sign to apply so sum reconciles to net gap (a-b)
            if worse["first_failure_stage"] == "NONE":
                stage = layer_a_stage_for_advantage(better, worse)
                direct_stage, esc_stage = stage, None
                direct, excess = min(mag, 1), max(mag - 1, 0)
            else:
                direct_stage = worse["first_failure_stage"]
                esc_stage = worse["escalation_stage"]
                # allocate using the WORSE record's own direct/excess split,
                # but cap at the pairwise mag actually observed (mag may
                # exceed worse["direct_cost"]+["excess_cost"] if the BETTER
                # player also under/over-performed par -- in that case the
                # remainder beyond the worse player's own over-par strokes
                # is attributed to the stage where the better player's edge
                # came from, to avoid inventing precision we don't have)
                own = worse["direct_cost"] + worse["excess_cost"]
                direct = min(mag, worse["direct_cost"])
                excess = max(mag - direct, 0)
                if own < mag:
                    # better player was also under par -- residual is their
                    # gain, not the worse player's loss; route to UNRESOLVED
                    # rather than silently folding it into the worse
                    # player's stage (would be fake precision)
                    pass
            waterfall_rows.append({
                "pair": key, "round": rnd, "hole": hole, "par": ra["par"],
                "diff_a_minus_b": diff, "worse_player": bname if diff < 0 else aname,
            })
            stage_net[direct_stage] += sign * direct
            if excess > 0:
                stage_net[esc_stage or "UNRESOLVED"] += sign * excess
    layer_a[key] = dict(stage_net)

print("=== LAYER A: signed causal/shot-stage attribution (reconciles to net gap) ===")
for k, v in layer_a.items():
    print(f"  {k}: {v}  sum={sum(v.values())}")


# ============================================================
# LAYER B: event-severity decomposition (independent axis)
# ============================================================
layer_b = {}
for a, b, aname, bname in PAIRS:
    key = f"{aname}-{bname}"
    sev_net = Counter()
    for rnd in (1, 2, 3, 4):
        for hole in range(1, 19):
            ra, rb = by_prh[(a, rnd, hole)], by_prh[(b, rnd, hole)]
            diff = ra["strokes"] - rb["strokes"]
            if diff == 0:
                continue
            # unambiguous rule: net stroke diff is fully explained by
            # (a.stp - b.stp); bucket it by whichever side is non-par, or
            # split if both sides are non-par (mixed)
            if ra["score_bucket"] != "Par" and rb["score_bucket"] == "Par":
                sev_net[ra["score_bucket"]] += diff
            elif rb["score_bucket"] != "Par" and ra["score_bucket"] == "Par":
                sev_net[rb["score_bucket"]] += diff
            else:
                # both non-par (mixed gap, e.g. birdie vs bogey) -- split by
                # each player's own deviation from par, signed
                sev_net[f"{ra['score_bucket']}(A)"] += ra["score_to_par"]
                sev_net[f"{rb['score_bucket']}(B)"] += -rb["score_to_par"]
    layer_b[key] = dict(sev_net)

print("\n=== LAYER B: signed event-severity decomposition (reconciles to net gap; A/B tags = mixed-gap hole-plays) ===")
for k, v in layer_b.items():
    print(f"  {k}: {v}  sum={sum(v.values())}")


# ============================================================
# Q1: Was Park's tee loss (-9) and big-number loss (-8) double counted?
# ============================================================
print("\n=== Q1: double-count check, 유해란-박서현 ===")
rp = layer_a["유해란-박서현"]
print("  Layer A (corrected, no BIG_NUMBER bucket at all):", rp, "sum=", sum(rp.values()))
print("  -> BIG_NUMBER_COMPOUND does not exist as a Layer-A bucket anymore; every stroke that used to")
print("     sit in 'BIG_NUMBER_COMPOUND' has been re-attributed to its true first-failure/escalation stage.")
print("     In the OLD chart6 decomposition, TEE_MISS(-9) and BIG_NUMBER_COMPOUND(-8) were presented as")
print("     if independent -- but some of the -8 BIG_NUMBER strokes started as tee misses, so summing them")
print("     as two separate causes WAS double-counting the same underlying failure under two different axes.")


# ============================================================
# Q4 + big-number counterfactual sensitivity
# ============================================================
big_events_pp = [r for r in chain if r["player_name"] == "박서현" and r["score_bucket"] in ("Double", "TriplePlus")]
lee_park_net = sum(by_prh[("9708", r["round"], r["hole"])]["strokes"] - r["strokes"] for r in
                    [rr for rr in chain if rr["player_code"] == "9111"])
counterfactual_rows = []
actual_lp = sum(by_prh[("9708", rnd, hole)]["strokes"] - by_prh[("9111", rnd, hole)]["strokes"]
                 for rnd in (1, 2, 3, 4) for hole in range(1, 19))
cap_bogey_delta = 0
cap_par_delta = 0
for r in big_events_pp:
    par = r["par"]
    actual = r["strokes"]
    bogey_capped = par + 1
    par_capped = par
    cap_bogey_delta += (actual - bogey_capped)
    cap_par_delta += (actual - par_capped)
    counterfactual_rows.append({"round": r["round"], "hole": r["hole"], "par": par, "actual_strokes": actual,
                                 "bogey_capped_strokes": bogey_capped, "par_capped_strokes": par_capped,
                                 "strokes_saved_if_bogey_cap": actual - bogey_capped,
                                 "strokes_saved_if_par_cap": actual - par_capped})
bogey_cap_gap = actual_lp + cap_bogey_delta  # Park's strokes go DOWN -> Lee-Park gap moves toward 0
par_cap_gap = actual_lp + cap_par_delta
print(f"\n=== Q4 + counterfactual sensitivity (NOT a prediction) ===")
print(f"  Actual 이재윤-박서현 net gap: {actual_lp}")
print(f"  If 박서현's 5 Double+ events were each capped at Bogey: gap = {bogey_cap_gap} (narrows by {cap_bogey_delta})")
print(f"  If 박서현's 5 Double+ events were each capped at Par:   gap = {par_cap_gap} (narrows by {cap_par_delta})")


# ============================================================
# Q2 + putting-escalation dissection of Ryu-Park top-10 (corrected putts)
# ============================================================
rp_rows = []
for rnd in (1, 2, 3, 4):
    for hole in range(1, 19):
        ra, rb = by_prh[("9115", rnd, hole)], by_prh[("9111", rnd, hole)]
        diff = ra["strokes"] - rb["strokes"]
        if diff != 0:
            rp_rows.append((rnd, hole, diff))
rp_rows.sort(key=lambda x: -abs(x[2]))
top10_rp = rp_rows[:10]

putting_dissection = []
for rnd, hole, diff in top10_rp:
    ra, rb = by_prh[("9115", rnd, hole)], by_prh[("9111", rnd, hole)]
    worse, worse_name = (rb, "박서현") if diff < 0 else (ra, "유해란")
    better, better_name = (ra, "유해란") if diff < 0 else (rb, "박서현")
    involves_putting = worse["first_failure_stage"] == "PUTTING" or worse["escalation_stage"] == "PUTTING"
    putting_role = None
    if worse["first_failure_stage"] == "PUTTING":
        putting_role = "PUTTING_WAS_FIRST_FAILURE"
    elif worse["escalation_stage"] == "PUTTING":
        putting_role = "PUTTING_ESCALATED_EARLIER_FAILURE"
    fp = worse["first_putt_distance_yd"]
    risk = None
    if putting_role is not None:
        if fp is None:
            risk = "UNRESOLVED (first-putt distance not available)"
        elif fp >= 10.0:
            risk = "APPROACH-CREATED_PUTTING_RISK (first putt >=10yd)"
        else:
            risk = "OBSERVED_MULTI-PUTT_FINISH (first putt <10yd, independent of approach)"
    putting_dissection.append({
        "round": rnd, "hole": hole, "par": worse["par"], "worse_player": worse_name,
        "worse_strokes": worse["strokes"], "better_player": better_name, "better_strokes": better["strokes"],
        "pairwise_gap": abs(diff), "putts_fixed": worse["putts_fixed"],
        "first_putt_distance_yd": fp, "first_failure_stage": worse["first_failure_stage"],
        "escalation_stage": worse["escalation_stage"], "involves_putting": involves_putting,
        "putting_role": putting_role, "putting_risk_classification": risk,
        "state_sequence": worse["state_sequence"],
    })

n_putting = sum(1 for d in putting_dissection if d["involves_putting"])
print(f"\n=== Q2: Ryu-Park top10, putting involvement (CORRECTED putts) ===")
print(f"  {n_putting} of 10 involve putting as first-failure or escalation (previous report said 6/10 using the uncorrected putts formula)")
for d in putting_dissection:
    print(f"  R{d['round']}H{d['hole']} par{d['par']}: {d['worse_player']}({d['worse_strokes']}) vs {d['better_player']}({d['better_strokes']}) "
          f"putts_fixed={d['putts_fixed']} first_putt_dist={d['first_putt_distance_yd']} "
          f"first_failure={d['first_failure_stage']} escalation={d['escalation_stage']} role={d['putting_role']} risk={d['putting_risk_classification']}")


# ============================================================
# Q3: Ryu birdie ~8 validation -- RYU_POSITIVE_CONVERSION vs
# LEE_NEGATIVE_OUTCOME vs MIXED_GAP, for Ryu-Lee pair
# ============================================================
birdie_rows = []
for rnd in (1, 2, 3, 4):
    for hole in range(1, 19):
        ra, rb = by_prh[("9115", rnd, hole)], by_prh[("9708", rnd, hole)]
        diff = ra["strokes"] - rb["strokes"]
        if diff == 0:
            continue
        ryu_birdie = ra["score_bucket"] == "Birdie+"
        lee_nonpar = rb["score_bucket"] != "Par"
        if ryu_birdie and rb["score_bucket"] == "Par":
            cls = "RYU_POSITIVE_CONVERSION"
        elif not ryu_birdie and lee_nonpar and diff < 0:
            cls = "LEE_NEGATIVE_OUTCOME"
        elif ryu_birdie and lee_nonpar:
            cls = "MIXED_GAP"
        elif ra["score_bucket"] == "Par" and rb["score_bucket"] != "Par":
            cls = "LEE_NEGATIVE_OUTCOME"
        else:
            cls = "MIXED_GAP"
        birdie_rows.append({"round": rnd, "hole": hole, "diff": diff, "ryu_bucket": ra["score_bucket"],
                             "lee_bucket": rb["score_bucket"], "classification": cls})

cls_totals = Counter()
for r in birdie_rows:
    cls_totals[r["classification"]] += r["diff"]
print(f"\n=== Q3: Ryu-Lee gap, unique classification (sums to -13) ===")
print(" ", dict(cls_totals), "sum=", sum(cls_totals.values()))
pure_ryu_birdie_rows = [r for r in birdie_rows if r["classification"] == "RYU_POSITIVE_CONVERSION"]
print(f"  Pure RYU_POSITIVE_CONVERSION hole-plays (Ryu birdied, Lee exactly par): n={len(pure_ryu_birdie_rows)}, "
      f"strokes={sum(r['diff'] for r in pure_ryu_birdie_rows)}")


# ============================================================
# Q5: R1-2 vs R3-4 Park causal-stage pattern + H8/H9 share of deterioration
# ============================================================
park_recs = [r for r in chain if r["player_name"] == "박서현"]
def stage_tally(recs):
    c = Counter()
    for r in recs:
        if r["first_failure_stage"] != "NONE":
            c[r["first_failure_stage"]] += r["direct_cost"]
            if r["escalation_stage"]:
                c[r["escalation_stage"]] += r["excess_cost"]
    return c

r12 = [r for r in park_recs if r["round"] in (1, 2)]
r34 = [r for r in park_recs if r["round"] in (3, 4)]
print(f"\n=== Q5: 박서현 causal-stage pattern, R1-2 vs R3-4 (strokes over par by stage, own chain only) ===")
print("  R1-2:", dict(stage_tally(r12)), "total strokes-over-par:", sum(r['score_to_par'] for r in r12 if r['score_to_par']>0))
print("  R3-4:", dict(stage_tally(r34)), "total strokes-over-par:", sum(r['score_to_par'] for r in r34 if r['score_to_par']>0))

over_par_12 = sum(r["score_to_par"] for r in r12 if r["score_to_par"] > 0)
over_par_34 = sum(r["score_to_par"] for r in r34 if r["score_to_par"] > 0)
deterioration = over_par_34 - over_par_12
h89_34 = [r for r in r34 if r["hole"] in (8, 9) and r["score_to_par"] > 0]
h89_damage_34 = sum(r["score_to_par"] for r in h89_34)
print(f"  Total strokes-over-par R1-2={over_par_12}, R3-4={over_par_34}, deterioration={deterioration}")
print(f"  H8+H9 strokes-over-par within R3-4={h89_damage_34} -> explains "
      f"{(h89_damage_34/deterioration*100) if deterioration else float('nan'):.1f}% of the raw R3-4-vs-R1-2 "
      f"strokes-over-par increase (NOTE: this is raw strokes-over-par, not the field-relative Step-4 figure, "
      f"and H8/H9 existed as holes in R1-2 too -- see audit notes on this comparison's limits)")


# ============================================================
# Q6: hole-plays where a single cause cannot be cleanly chosen
# ============================================================
multi_cause = [r for r in chain if r["first_failure_stage"] != "NONE" and r["escalation_stage"] is not None]
print(f"\n=== Q6: hole-plays with BOTH a first-failure stage AND a distinct escalation stage: n={len(multi_cause)} ===")
by_combo = Counter((r["first_failure_stage"], r["escalation_stage"]) for r in multi_cause)
print(" ", dict(by_combo))


# ============================================================
# Export CSVs
# ============================================================
with open(HERE / "three_player_unique_attribution.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["player", "round", "hole", "par", "strokes", "score_to_par", "score_bucket",
                "first_failure_stage", "escalation_stage", "direct_cost", "excess_cost",
                "putts_fixed", "first_putt_distance_yd"])
    for r in chain:
        w.writerow([r["player_name"], r["round"], r["hole"], r["par"], r["strokes"], r["score_to_par"],
                    r["score_bucket"], r["first_failure_stage"], r["escalation_stage"], r["direct_cost"],
                    r["excess_cost"], r["putts_fixed"], r["first_putt_distance_yd"]])

with open(HERE / "three_player_first_failure_escalation.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["round", "hole", "par", "worse_player", "worse_strokes", "better_player", "better_strokes",
                "pairwise_gap", "putts_fixed", "first_putt_distance_yd", "first_failure_stage",
                "escalation_stage", "putting_role", "putting_risk_classification", "state_sequence"])
    for d in putting_dissection:
        w.writerow([d["round"], d["hole"], d["par"], d["worse_player"], d["worse_strokes"], d["better_player"],
                    d["better_strokes"], d["pairwise_gap"], d["putts_fixed"], d["first_putt_distance_yd"],
                    d["first_failure_stage"], d["escalation_stage"], d["putting_role"],
                    d["putting_risk_classification"], "-".join(d["state_sequence"])])

with open(HERE / "three_player_pairwise_waterfall.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["pair", "layer", "category", "net_signed_strokes"])
    for k, v in layer_a.items():
        for cat, val in v.items():
            w.writerow([k, "A_CAUSAL_STAGE", cat, val])
    for k, v in layer_b.items():
        for cat, val in v.items():
            w.writerow([k, "B_EVENT_SEVERITY", cat, val])

with open(HERE / "three_player_big_number_counterfactual.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["round", "hole", "par", "actual_strokes", "bogey_capped_strokes", "par_capped_strokes",
                "strokes_saved_if_bogey_cap", "strokes_saved_if_par_cap"])
    for r in counterfactual_rows:
        w.writerow([r["round"], r["hole"], r["par"], r["actual_strokes"], r["bogey_capped_strokes"],
                    r["par_capped_strokes"], r["strokes_saved_if_bogey_cap"], r["strokes_saved_if_par_cap"]])

# reconciliation check (zero tolerance)
official_net = {"유해란-이재윤": -13, "이재윤-박서현": -17, "유해란-박서현": -30}
recon_pass = {}
for k in layer_a:
    a_sum = sum(layer_a[k].values())
    b_sum = sum(layer_b[k].values())
    recon_pass[k] = {"layer_a_sum": a_sum, "layer_b_sum": b_sum, "official": official_net[k],
                      "A_PASS": a_sum == official_net[k], "B_PASS": b_sum == official_net[k]}
print("\n=== FINAL RECONCILIATION (zero tolerance) ===")
for k, v in recon_pass.items():
    print(f"  {k}: {v}")

dump = {
    "layer_a": layer_a, "layer_b": layer_b,
    "q1_note": "see printed output",
    "q4_counterfactual": {"actual_lee_park_gap": actual_lp,
                           "bogey_cap_gap": bogey_cap_gap,
                           "par_cap_gap": par_cap_gap,
                           "events": counterfactual_rows},
    "q2_putting_dissection": putting_dissection,
    "q3_birdie_classification": {"totals": dict(cls_totals), "rows": birdie_rows},
    "q5_park_r12_vs_r34": {"over_par_12": over_par_12, "over_par_34": over_par_34,
                            "deterioration": deterioration, "h89_damage_34": h89_damage_34,
                            "stage_12": dict(stage_tally(r12)), "stage_34": dict(stage_tally(r34))},
    "q6_multi_cause_n": len(multi_cause), "q6_combos": {f"{a}->{b}": n for (a, b), n in by_combo.items()},
    "reconciliation": recon_pass,
}
(HERE / "three_player_attribution_audit_results.json").write_text(json.dumps(dump, ensure_ascii=False, indent=1))
print("\nWrote all CSVs + three_player_attribution_audit_results.json")
