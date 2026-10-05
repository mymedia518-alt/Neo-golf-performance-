"""NEO 72-hole score-gap deep analysis -- Steps 5+ on top of the already
locked NEO_72HOLE_SCORE_GAP_ROOT_CAUSE.md (Steps 1-4).
Reads only three_player_master_chain.json (built fresh from RAW this task).
"""
from __future__ import annotations
import json, statistics
from pathlib import Path
from collections import defaultdict, Counter

HERE = Path(__file__).parent
chain = json.loads((HERE / "three_player_master_chain.json").read_text())["records"]
PLAYERS = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}
NAME2CODE = {v: k for k, v in PLAYERS.items()}
by_prh = {(r["player_code"], r["round"], r["hole"]): r for r in chain}
PAIRS = [("9115", "9708", "유해란", "이재윤"), ("9708", "9111", "이재윤", "박서현"), ("9115", "9111", "유해란", "박서현")]
DEFEND = {6, 8, 10, 12}
ATTACK = {2, 4, 7, 14, 16, 18}
CONTROL = {1, 3, 5, 9, 11, 13, 15, 17}

def hole_type(h):
    return "DEFEND" if h in DEFEND else ("ATTACK" if h in ATTACK else "CONTROL")


# ---------------- Step 5-6: pairwise hole-play diff + hotspot classification ----------------
def pair_matrix(a, b):
    rows = []
    for rnd in (1, 2, 3, 4):
        for hole in range(1, 19):
            ra, rb = by_prh[(a, rnd, hole)], by_prh[(b, rnd, hole)]
            rows.append({"round": rnd, "hole": hole, "par": ra["par"],
                         "a_strokes": ra["strokes"], "b_strokes": rb["strokes"],
                         "diff": ra["strokes"] - rb["strokes"]})
    return rows


def hotspots(rows, top_n=10):
    nz = [r for r in rows if r["diff"] != 0]
    nz.sort(key=lambda r: abs(r["diff"]), reverse=True)
    top = nz[:top_n]
    hole_counts = Counter(r["hole"] for r in top)
    repeating_holes = {h: c for h, c in hole_counts.items() if c >= 2}
    return top, repeating_holes


def classify_hotspot_type(top, rows):
    # same hole number appearing >=2x in a player's full-72 gap list at all (not just top10) => repeating hole weakness
    hole_all_diff = defaultdict(list)
    for r in rows:
        if r["diff"] != 0:
            hole_all_diff[r["hole"]].append(r["diff"])
    out = []
    for t in top:
        h = t["hole"]
        occurrences = len(hole_all_diff[h])
        same_sign = len([d for d in hole_all_diff[h] if (d > 0) == (t["diff"] > 0)])
        if occurrences >= 2 and same_sign >= 2:
            label = "REPEATING_HOLE_WEAKNESS"
        else:
            label = "ONE_OFF_EVENT"
        out.append({**t, "label": label, "hole_occurrences_nonzero": occurrences, "same_direction_occurrences": same_sign})
    return out


pair_results = {}
for a, b, aname, bname in PAIRS:
    rows = pair_matrix(a, b)
    top, rep = hotspots(rows)
    labeled = classify_hotspot_type(top, rows)
    net = sum(r["diff"] for r in rows)
    pair_results[f"{aname}-{bname}"] = {"a": aname, "b": bname, "net_gap_a_minus_b": net, "rows": rows,
                                         "top10": labeled, "repeating_holes_in_top10": rep}

print("=== STEP 5-6: Hotspot top-10 per pair + classification ===")
for k, v in pair_results.items():
    print(f"\n-- {k} (net {v['a']}-{v['b']} = {v['net_gap_a_minus_b']}) --")
    for t in v["top10"]:
        print(f"  R{t['round']}H{t['hole']} par{t['par']}: {v['a']}={t['a_strokes']} {v['b']}={t['b_strokes']} diff={t['diff']:+d} [{t['label']}]")
    print("  repeating holes in top10:", v["repeating_holes_in_top10"])


# ---------------- Step 7: shot-by-shot autopsy of Ryu-Park top10 ----------------
def autopsy(pc_a, pc_b, name_a, name_b, top10):
    out = []
    for t in top10:
        ra, rb = by_prh[(pc_a, t["round"], t["hole"])], by_prh[(pc_b, t["round"], t["hole"])]
        worse_r = rb if t["diff"] < 0 else ra  # player with MORE strokes on this hole
        worse_name = name_b if t["diff"] < 0 else name_a
        better_r = ra if t["diff"] < 0 else rb
        better_name = name_a if t["diff"] < 0 else name_b
        seq = worse_r["state_sequence"]
        first_fail = None
        if not worse_r["fw_hit"] and worse_r["par"] != 3:
            first_fail = f"shot1 tee={worse_r['tee_lie']}"
        elif worse_r["approach_lie"] not in (None, "GREEN", "FRINGE"):
            first_fail = f"shot2 approach={worse_r['approach_lie']}"
        elif worse_r["gir"] is False:
            first_fail = "missed green on regulation approach"
        else:
            first_fail = "on track through approach -- failure is on/after green"
        escalation = "none"
        if worse_r["penalty_count"] >= 1:
            escalation = f"penalty/OB/lost-ball x{worse_r['penalty_count']}"
        elif worse_r["bunker_count"] >= 2:
            escalation = "bunker-to-bunker"
        elif worse_r["putts"] >= 3:
            escalation = f"{worse_r['putts']}-putt"
        out.append({"round": t["round"], "hole": t["hole"], "par": t["par"],
                     "worse_player": worse_name, "worse_strokes": worse_r["strokes"],
                     "better_player": better_name, "better_strokes": better_r["strokes"],
                     "diff": abs(t["diff"]), "state_sequence": seq,
                     "first_failure": first_fail, "escalation_point": escalation,
                     "final_damage_strokes_over_par": worse_r["score_to_par"]})
    return out

ryu_park_autopsy = autopsy("9115", "9111", "유해란", "박서현", pair_results["유해란-박서현"]["top10"])
print("\n=== STEP 7: 유해란-박서현 top10 shot-chain autopsy ===")
for a in ryu_park_autopsy:
    print(f"R{a['round']}H{a['hole']} par{a['par']}: {a['worse_player']} {a['worse_strokes']} vs {a['better_player']} {a['better_strokes']} | seq={a['state_sequence']} | FIRST_FAILURE={a['first_failure']} | ESCALATION={a['escalation_point']} | final stp={a['final_damage_strokes_over_par']:+d}")


# ---------------- Step 8-9: same-condition different-result ----------------
def cond_bucket(r):
    if r["par"] == 3:
        return ("PAR3", None, None)
    fw = "FW" if r["fw_hit"] else "MISS"
    ad = r["approach_remaining_yd"]
    if ad is None:
        band = "UNK"
    elif ad <= 50:
        band = "0-50"
    elif ad <= 100:
        band = "50-100"
    elif ad <= 150:
        band = "100-150"
    else:
        band = "150+"
    return ("P45", fw, band)

same_cond_flags = []
for rnd in (1, 2, 3, 4):
    for hole in range(1, 19):
        trio = {pc: by_prh[(pc, rnd, hole)] for pc in PLAYERS}
        par = trio["9115"]["par"]
        for pa, pb in [("9115", "9708"), ("9115", "9111"), ("9708", "9111")]:
            ra, rb = trio[pa], trio[pb]
            if par == 3:
                cond_match = ra["tee_lie"] == rb["tee_lie"]
            else:
                same_fw = (ra["fw_hit"] == rb["fw_hit"])
                same_app_lie = (ra["approach_lie"] == rb["approach_lie"])
                cond_match = same_fw and same_app_lie
            if cond_match and abs(ra["strokes"] - rb["strokes"]) >= 2:
                same_cond_flags.append({
                    "round": rnd, "hole": hole, "par": par,
                    "player_a": PLAYERS[pa], "a_tee": ra["tee_lie"], "a_fw_hit": ra["fw_hit"],
                    "a_approach_lie": ra["approach_lie"], "a_strokes": ra["strokes"], "a_bucket": ra["score_bucket"],
                    "player_b": PLAYERS[pb], "b_tee": rb["tee_lie"], "b_fw_hit": rb["fw_hit"],
                    "b_approach_lie": rb["approach_lie"], "b_strokes": rb["strokes"], "b_bucket": rb["score_bucket"],
                    "stroke_diff": abs(ra["strokes"] - rb["strokes"]),
                })

print(f"\n=== STEP 8-9: SAME tee/approach condition, cross-player result diverges >=2 strokes: n={len(same_cond_flags)} ===")
for f in sorted(same_cond_flags, key=lambda x: -x["stroke_diff"]):
    print(f"  R{f['round']}H{f['hole']} par{f['par']} both_fw_hit={f['a_fw_hit']} both_approach={f['a_approach_lie']}: "
          f"{f['player_a']}={f['a_strokes']}({f['a_bucket']}) vs {f['player_b']}={f['b_strokes']}({f['b_bucket']}) diff={f['stroke_diff']}")


# ---------------- Step 10-11: FW hit/miss -> GIR, GIR miss -> outcome, per player all 72 holes ----------------
def player_rates(pc):
    rs = [r for r in chain if r["player_code"] == pc]
    nonpar3 = [r for r in rs if r["par"] != 3]
    fw = [r for r in nonpar3 if r["fw_hit"]]
    miss = [r for r in nonpar3 if not r["fw_hit"]]
    def gir_pct(group):
        return round(sum(1 for r in group if r["gir"]) / len(group), 3) if group else None
    gir_miss = [r for r in rs if not r["gir"]]
    def outcome_rate(group, bucket_set):
        n = len(group)
        return round(sum(1 for r in group if r["score_bucket"] in bucket_set) / n, 3) if n else None
    tee_penalty = sum(1 for r in nonpar3 if r["penalty_count"] >= 1 and r["first_miss_shot"] == 1)
    return {
        "player": PLAYERS[pc], "n_nonpar3": len(nonpar3),
        "fw_hit_pct": round(len(fw) / len(nonpar3), 3),
        "FWHit_to_GIR": gir_pct(fw), "FWMiss_to_GIR": gir_pct(miss), "n_fw": len(fw), "n_miss": len(miss),
        "GIRMiss_n": len(gir_miss),
        "GIRMiss_to_ParSave": outcome_rate(gir_miss, {"Birdie+", "Par"}),
        "GIRMiss_to_Bogey": outcome_rate(gir_miss, {"Bogey"}),
        "GIRMiss_to_DoublePlus": outcome_rate(gir_miss, {"Double", "TriplePlus"}),
        "tee_penalty_events": tee_penalty,
        "avg_score_to_par_all72": round(statistics.mean(r["score_to_par"] for r in rs), 3),
        "BogeyPlus_pct_all72": round(sum(1 for r in rs if r["score_bucket"] in ("Bogey","Double","TriplePlus"))/len(rs),3),
        "DoublePlus_pct_all72": round(sum(1 for r in rs if r["score_bucket"] in ("Double","TriplePlus"))/len(rs),3),
        "Birdie_pct_all72": round(sum(1 for r in rs if r["score_bucket"]=="Birdie+")/len(rs),3),
    }

rates = {pc: player_rates(pc) for pc in PLAYERS}
print("\n=== STEP 10-11: FW/GIR/outcome rates, all 72 holes per player ===")
for pc, v in rates.items():
    print(f"  {v['player']}: FW%={v['fw_hit_pct']:.0%} FWHit->GIR={v['FWHit_to_GIR']} FWMiss->GIR={v['FWMiss_to_GIR']} | GIRmiss n={v['GIRMiss_n']} ParSave={v['GIRMiss_to_ParSave']} Bogey={v['GIRMiss_to_Bogey']} Double+={v['GIRMiss_to_DoublePlus']} | avg_stp={v['avg_score_to_par_all72']:+.3f} Birdie%={v['Birdie_pct_all72']:.0%} Bogey+%={v['BogeyPlus_pct_all72']:.0%} Double+%={v['DoublePlus_pct_all72']:.0%}")


# ---------------- Step 12-13: big number (Double+) full autopsy, all players ----------------
big_events = []
for r in chain:
    if r["score_bucket"] in ("Double", "TriplePlus"):
        seq = r["state_sequence"]
        first_fail = None
        if r["par"] != 3 and not r["fw_hit"]:
            first_fail = f"tee={r['tee_lie']}"
        elif r["approach_lie"] not in (None, "GREEN", "FRINGE"):
            first_fail = f"approach={r['approach_lie']}"
        elif not r["gir"]:
            first_fail = "missed green in regulation"
        else:
            first_fail = "GIR hit, damage came after green (3+ putt or later)"
        escalation = "none"
        if r["penalty_count"] >= 1:
            escalation = f"penalty/OB/lost x{r['penalty_count']}"
        elif r["bunker_count"] >= 2:
            escalation = "bunker-to-bunker"
        elif r["putts"] >= 3:
            escalation = f"{r['putts']}-putt"
        big_events.append({"player": r["player_name"], "round": r["round"], "hole": r["hole"], "par": r["par"],
                            "strokes": r["strokes"], "score_to_par": r["score_to_par"], "state_sequence": seq,
                            "first_failure": first_fail, "escalation_point": escalation})

print(f"\n=== STEP 12-13: Big-number (Double+) events, all players, n={len(big_events)} ===")
by_player_big = defaultdict(list)
for e in big_events:
    by_player_big[e["player"]].append(e)
for p, evs in by_player_big.items():
    total_dmg = sum(e["score_to_par"] for e in evs)
    print(f"  {p}: n={len(evs)} total_strokes_over_par_from_doubles={total_dmg} avg={total_dmg/len(evs):.2f}")
    esc_counter = Counter(e["escalation_point"] for e in evs)
    print(f"    escalation breakdown: {dict(esc_counter)}")


# ---------------- Step 14: bogey origin classification, all players ----------------
def bogey_origin(r):
    if r["par"] != 3 and not r["fw_hit"]:
        if r["penalty_count"] >= 1:
            return "TEE_PENALTY"
        return "TEE_MISS"
    if r["approach_lie"] not in (None, "GREEN", "FRINGE"):
        if r["penalty_count"] >= 1:
            return "APPROACH_PENALTY"
        return "APPROACH_MISS"
    if not r["gir"]:
        return "GREEN_MISS_RECOVERY_FAIL"
    if r["putts"] >= 3:
        return "THREE_PUTT"
    return "UNRESOLVED"

bogey_rows = [r for r in chain if r["score_bucket"] == "Bogey"]
origin_by_player = defaultdict(Counter)
for r in bogey_rows:
    origin_by_player[r["player_name"]][bogey_origin(r)] += 1

print(f"\n=== STEP 14: Bogey origin classification, n_bogeys={len(bogey_rows)} ===")
for p, c in origin_by_player.items():
    print(f"  {p} (n={sum(c.values())}): {dict(c)}")


# ---------------- Step 16: par3/4/5 pairwise contribution ----------------
def par_breakdown(rows, label):
    out = {}
    for par in (3, 4, 5):
        sub = [r for r in rows if r["par"] == par]
        out[f"par{par}"] = {"n": len(sub), "net_diff": sum(r["diff"] for r in sub)}
    return out

print("\n=== STEP 16: par3/4/5 contribution to each pair's net gap ===")
for k, v in pair_results.items():
    pb = par_breakdown(v["rows"], k)
    print(f"  {k}: {pb}")

# attack/control/defend
def act_breakdown(rows):
    out = {}
    for label, hs in (("DEFEND", DEFEND), ("CONTROL", CONTROL), ("ATTACK", ATTACK)):
        sub = [r for r in rows if r["hole"] in hs]
        out[label] = {"n": len(sub), "net_diff": sum(r["diff"] for r in sub)}
    return out

print("\n=== STEP 16b: DEFEND/CONTROL/ATTACK contribution to each pair's net gap ===")
for k, v in pair_results.items():
    print(f"  {k}: {act_breakdown(v['rows'])}")


# ---------------- Step 17: hole 1-18 repeating pattern across pairs ----------------
print("\n=== STEP 17: per-hole net diff summed across rounds, each pair ===")
for k, v in pair_results.items():
    by_hole = defaultdict(int)
    for r in v["rows"]:
        by_hole[r["hole"]] += r["diff"]
    worst = sorted(by_hole.items(), key=lambda x: x[1])[:5]
    best = sorted(by_hole.items(), key=lambda x: -x[1])[:3]
    print(f"  {k}: most-negative(a worse) holes={worst} | most-positive(a better) holes={best}")


# save everything
# ---------------- Step 20-21: no-double-count gap decomposition per pair ----------------
def failure_category(r):
    if r["score_bucket"] in ("Double", "TriplePlus"):
        return "BIG_NUMBER_COMPOUND"
    if r["par"] != 3 and not r["fw_hit"]:
        return "TEE_PENALTY" if r["penalty_count"] >= 1 else "TEE_MISS"
    if r["approach_lie"] not in (None, "GREEN", "FRINGE"):
        return "APPROACH_PENALTY" if r["penalty_count"] >= 1 else "APPROACH_MISS"
    if not r["gir"]:
        return "GREEN_MISS_RECOVERY_FAIL"
    if r["putts"] >= 3:
        return "THREE_PUTT_PLUS"
    return "UNRESOLVED"

decomposition = {}
decomposition_net = {}
for a, b, aname, bname in PAIRS:
    key = f"{aname}-{bname}"
    cat_totals = Counter()
    cat_net = Counter()
    for rnd in (1, 2, 3, 4):
        for hole in range(1, 19):
            ra, rb = by_prh[(a, rnd, hole)], by_prh[(b, rnd, hole)]
            diff = ra["strokes"] - rb["strokes"]
            if diff == 0:
                continue
            worse, better = (rb, ra) if diff < 0 else (ra, rb)  # worse = more strokes
            mag = abs(diff)
            if worse["score_bucket"] in ("Par", "Birdie+"):
                cat = "BETTER_PLAYER_BIRDIE"
            else:
                cat = failure_category(worse)
            cat_totals[cat] += mag
            cat_net[cat] += diff  # preserves sign so sum(cat_net) == net gap exactly
    decomposition[key] = dict(cat_totals)
    decomposition_net[key] = dict(cat_net)

print("\n=== STEP 20-21: Score-gap decomposition per pair ===")
for k in decomposition:
    print(f"  {k}: GROSS(both directions)={decomposition[k]} sum={sum(decomposition[k].values())}")
    print(f"       NET(signed, reconciles to actual net gap)={decomposition_net[k]} sum={sum(decomposition_net[k].values())}")


dump = {
    "pair_hotspots": {k: v["top10"] for k, v in pair_results.items()},
    "pair_net_gap": {k: v["net_gap_a_minus_b"] for k, v in pair_results.items()},
    "ryu_park_autopsy": ryu_park_autopsy,
    "same_condition_flags_n": len(same_cond_flags),
    "same_condition_flags": same_cond_flags,
    "player_rates": rates,
    "big_events_n": len(big_events),
    "big_events": big_events,
    "bogey_origin_by_player": {p: dict(c) for p, c in origin_by_player.items()},
    "par_breakdown_by_pair": {k: par_breakdown(v["rows"], k) for k, v in pair_results.items()},
    "act_breakdown_by_pair": {k: act_breakdown(v["rows"]) for k, v in pair_results.items()},
    "gap_decomposition_gross_by_pair": decomposition,
    "gap_decomposition_net_by_pair": decomposition_net,
}
(HERE / "three_player_gap_deep_analysis.json").write_text(json.dumps(dump, ensure_ascii=False, indent=1))
print("\nWrote three_player_gap_deep_analysis.json")
