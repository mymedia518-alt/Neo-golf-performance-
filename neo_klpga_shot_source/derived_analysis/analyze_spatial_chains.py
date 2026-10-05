from __future__ import annotations
import json, csv, statistics, sqlite3
from pathlib import Path
from collections import defaultdict, Counter

HERE = Path(__file__).parent
DB = HERE / "klpga_shots_RAW_READONLY.sqlite"
GAME = "2026100005"
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
PAIRS = [("9115", "9708", "유해란", "이재윤"), ("9708", "9111", "이재윤", "박서현"), ("9115", "9111", "유해란", "박서현")]


def chain_narrative(pc, rnd, hole):
    shots = by_shot_key[(pc, rnd, hole)]
    lines = []
    for s in shots:
        lines.append(f"  shot{s['shot_number']}: {s['lie_before']} -> {s['lie_after']}"
                      f" | end=({s['end_x']},{s['end_y']})"
                      f" | shot_dist={s['shot_distance_yd']}yd" if s['shot_distance_yd'] is not None else
                      f"  shot{s['shot_number']}: {s['lie_before']} -> {s['lie_after']} | end=({s['end_x']},{s['end_y']}) | shot_dist=UNKNOWN"
                      )
    return lines


# ============================================================
# 1. Pairwise gap matrix, top events per pair (reconstruct fresh,
#    reusing the already-locked methodology, not copying old CSVs)
# ============================================================
pair_tops = {}
for a, b, aname, bname in PAIRS:
    rows = []
    for rnd in (1, 2, 3, 4):
        for hole in range(1, 19):
            ra, rb = by_hole_key[(a, rnd, hole)], by_hole_key[(b, rnd, hole)]
            diff = ra["strokes"] - rb["strokes"]
            rows.append({"round": rnd, "hole": hole, "par": ra["par"], "a": ra["strokes"], "b": rb["strokes"], "diff": diff})
    nz = [r for r in rows if r["diff"] != 0]
    nz.sort(key=lambda r: -abs(r["diff"]))
    pair_tops[f"{aname}-{bname}"] = nz[:10]

print("=== Top-10 gap events per pair (spatial-chain-ready) ===")
for k, v in pair_tops.items():
    print(f"-- {k} --")
    for r in v:
        print(f"  R{r['round']}H{r['hole']} par{r['par']}: a={r['a']} b={r['b']} diff={r['diff']:+d}")


# ============================================================
# 2. Full narrative reconstruction of Ryu-Park top10 with real
#    coordinates/distances (EXAMPLE FORMAT from the brief)
# ============================================================
def build_case(pc_a, pc_b, name_a, name_b, rnd, hole):
    ra, rb = by_hole_key[(pc_a, rnd, hole)], by_hole_key[(pc_b, rnd, hole)]
    sa, sb = by_shot_key[(pc_a, rnd, hole)], by_shot_key[(pc_b, rnd, hole)]
    def fmt_chain(shots):
        out = []
        for s in shots:
            sd = s["shot_distance_yd"]
            sd_s = f"{sd}yd" if sd is not None else "UNKNOWN"
            rem = s["remaining_distance_after_yd"]
            rem_s = f"{rem}yd to pin" if rem is not None else "UNKNOWN remaining"
            out.append({"shot": s["shot_number"], "lie_after": s["lie_after"], "shot_distance": sd_s,
                        "remaining_after": rem_s, "end_coord": [s["end_x"], s["end_y"]],
                        "pin_space_distance_mapunits": s["pin_space_distance_mapunits"]})
        return out
    return {
        "round": rnd, "hole": hole, "par": ra["par"],
        "player_a": name_a, "a_score": ra["strokes"], "a_score_to_par": ra["score_to_par"], "a_chain": fmt_chain(sa),
        "player_b": name_b, "b_score": rb["strokes"], "b_score_to_par": rb["score_to_par"], "b_chain": fmt_chain(sb),
        "diff": ra["strokes"] - rb["strokes"],
    }


ryu_park_cases = [build_case("9115", "9111", "유해란", "박서현", r["round"], r["hole"]) for r in pair_tops["유해란-박서현"]]
lee_park_big = [build_case("9708", "9111", "이재윤", "박서현", r["round"], r["hole"]) for r in pair_tops["이재윤-박서현"]
                if by_hole_key[("9111", r["round"], r["hole"])]["score_bucket"] in ("Double", "TriplePlus")]
ryu_lee_positive = []
for rnd in (1, 2, 3, 4):
    for hole in range(1, 19):
        ra, rb = by_hole_key[("9115", rnd, hole)], by_hole_key[("9708", rnd, hole)]
        if ra["score_bucket"] == "Birdie+" and rb["score_bucket"] == "Par":
            ryu_lee_positive.append(build_case("9115", "9708", "유해란", "이재윤", rnd, hole))

print(f"\nryu_park_cases={len(ryu_park_cases)}  lee_park_big={len(lee_park_big)}  ryu_lee_positive={len(ryu_lee_positive)}")


# ============================================================
# 3. Counterexamples: R1H16 (Park beats Ryu), R2H12 (Lee beats Ryu)
# ============================================================
counter_r1h16 = build_case("9115", "9111", "유해란", "박서현", 1, 16)
counter_r2h12 = build_case("9115", "9708", "유해란", "이재윤", 2, 12)
print("\n=== Counterexample 1: R1H16, Park beats Ryu ===")
print(json.dumps(counter_r1h16, ensure_ascii=False, indent=1))
print("\n=== Counterexample 2: R2H12, Lee beats Ryu ===")
print(json.dumps(counter_r2h12, ensure_ascii=False, indent=1))


# ============================================================
# 4. SAME-START, DIFFERENT-END (data-driven tolerance)
# ============================================================
# Tolerance definition: remaining-distance-after-tee-shot band width =
# one field-wide decile of that hole's remaining-distance distribution
# (computed from the full 107-player field, not just these 3), applied
# within the SAME (round, hole) so the pin is identical by construction.
# This replaces guessing a fixed yard window with a data-driven one.
con = sqlite3.connect(DB)

def hole_decile_width(hole):
    rows = con.execute(
        "SELECT distance, state_code FROM klpga_player_shot WHERE game_code=? AND hole=? AND shot=1",
        (GAME, hole)).fetchall()
    vals = sorted(d for d, st in rows if d is not None and st not in ("4", "5", "7", "8"))
    if len(vals) < 10:
        return None
    n = len(vals)
    return vals[int(n * 0.9)] - vals[int(n * 0.1)], (vals[int(n*0.9)]-vals[int(n*0.1)]) / 10.0

same_start_diff_end = []
for rnd in (1, 2, 3, 4):
    for hole in range(1, 19):
        par = by_hole_key[("9115", rnd, hole)]["par"]
        if par == 3:
            continue
        width = hole_decile_width(hole)
        if width is None:
            continue
        _, tol = width
        recs = {pc: by_hole_key[(pc, rnd, hole)] for pc in PLAYERS}
        sh = {pc: by_shot_key[(pc, rnd, hole)] for pc in PLAYERS}
        for pa, pb in [("9115", "9111"), ("9115", "9708"), ("9708", "9111")]:
            ra, rb = recs[pa], recs[pb]
            sa1, sb1 = sh[pa][0], sh[pb][0]
            if sa1["lie_after"] != "FAIRWAY" or sb1["lie_after"] != "FAIRWAY":
                continue
            da, db = sa1["remaining_distance_after_yd"], sb1["remaining_distance_after_yd"]
            if da is None or db is None:
                continue
            if abs(da - db) > tol:
                continue
            if ra["score_bucket"] == rb["score_bucket"]:
                continue
            same_start_diff_end.append({
                "round": rnd, "hole": hole, "par": par, "tolerance_yd": round(tol, 1),
                "player_a": PLAYERS[pa], "a_remaining_after_tee": da, "a_score": ra["strokes"], "a_bucket": ra["score_bucket"],
                "player_b": PLAYERS[pb], "b_remaining_after_tee": db, "b_score": rb["strokes"], "b_bucket": rb["score_bucket"],
                "score_diff": abs(ra["strokes"] - rb["strokes"]),
            })

print(f"\n=== SAME-START (FW, comparable remaining dist within field decile-tolerance), DIFFERENT-END: n={len(same_start_diff_end)} ===")
for r in sorted(same_start_diff_end, key=lambda x: -x["score_diff"]):
    print(f"  R{r['round']}H{r['hole']} par{r['par']} tol={r['tolerance_yd']}yd: {r['player_a']}({r['a_remaining_after_tee']}yd)={r['a_score']}({r['a_bucket']}) "
          f"vs {r['player_b']}({r['b_remaining_after_tee']}yd)={r['b_score']}({r['b_bucket']}) diff={r['score_diff']}")


# ============================================================
# 5. SAME MISS, DIFFERENT RECOVERY
# ============================================================
same_miss_diff_recovery = []
for rnd in (1, 2, 3, 4):
    for hole in range(1, 19):
        par = by_hole_key[("9115", rnd, hole)]["par"]
        sh = {pc: by_shot_key[(pc, rnd, hole)] for pc in PLAYERS}
        rec = {pc: by_hole_key[(pc, rnd, hole)] for pc in PLAYERS}
        # find each player's first non-green, non-fairway miss lie + its distance-to-pin
        miss = {}
        for pc in PLAYERS:
            for s in sh[pc]:
                if s["lie_after"] in ("ROUGH", "BUNKER", "GREENSIDE_BUNKER", "FRINGE") and s["shot_number"] > 1:
                    miss[pc] = s
                    break
        for pa, pb in [("9115", "9111"), ("9115", "9708"), ("9708", "9111")]:
            if pa not in miss or pb not in miss:
                continue
            ma, mb = miss[pa], miss[pb]
            if ma["lie_after"] != mb["lie_after"]:
                continue
            da, db = ma["remaining_distance_after_yd"], mb["remaining_distance_after_yd"]
            if da is None or db is None:
                continue
            if abs(da - db) > 5.0:  # tight, explicit 5yd tolerance for miss-location comparability
                continue
            ra, rb = rec[pa], rec[pb]
            if ra["score_bucket"] == rb["score_bucket"]:
                continue
            same_miss_diff_recovery.append({
                "round": rnd, "hole": hole, "par": par, "miss_lie": ma["lie_after"], "tolerance_yd": 5.0,
                "player_a": PLAYERS[pa], "a_miss_dist": da, "a_score": ra["strokes"], "a_bucket": ra["score_bucket"],
                "player_b": PLAYERS[pb], "b_miss_dist": db, "b_score": rb["strokes"], "b_bucket": rb["score_bucket"],
                "score_diff": abs(ra["strokes"] - rb["strokes"]),
            })

print(f"\n=== SAME MISS LIE + comparable distance-to-pin (+-5yd), DIFFERENT RECOVERY OUTCOME: n={len(same_miss_diff_recovery)} ===")
for r in sorted(same_miss_diff_recovery, key=lambda x: -x["score_diff"]):
    print(f"  R{r['round']}H{r['hole']} par{r['par']} miss={r['miss_lie']}: {r['player_a']}({r['a_miss_dist']}yd)={r['a_score']}({r['a_bucket']}) "
          f"vs {r['player_b']}({r['b_miss_dist']}yd)={r['b_score']}({r['b_bucket']}) diff={r['score_diff']}")


# ============================================================
# 6. FW HIT -> BOGEY+/DOUBLE+ and FW MISS -> PAR/BIRDIE, real cases
# ============================================================
fw_hit_bad = []
fw_miss_good = []
for r in hole_summaries:
    if r["par"] == 3:
        continue
    sh = by_shot_key[(r["player_code"], r["round"], r["hole"])]
    tee = sh[0]
    if tee["lie_after"] == "FAIRWAY" and r["score_bucket"] in ("Bogey", "Double", "TriplePlus"):
        fw_hit_bad.append({"player": r["player_name"], "round": r["round"], "hole": r["hole"], "par": r["par"],
                            "score": r["strokes"], "bucket": r["score_bucket"]})
    if tee["lie_after"] != "FAIRWAY" and r["score_bucket"] in ("Par", "Birdie+"):
        fw_miss_good.append({"player": r["player_name"], "round": r["round"], "hole": r["hole"], "par": r["par"],
                              "score": r["strokes"], "bucket": r["score_bucket"], "tee_lie": tee["lie_after"]})

print(f"\n=== FW HIT -> Bogey+: n={len(fw_hit_bad)} ===")
for r in fw_hit_bad:
    print(f"  {r['player']} R{r['round']}H{r['hole']} par{r['par']}: {r['score']} ({r['bucket']})")
print(f"\n=== FW MISS -> Par/Birdie: n={len(fw_miss_good)} ===")
for r in fw_miss_good[:20]:
    print(f"  {r['player']} R{r['round']}H{r['hole']} par{r['par']} tee={r['tee_lie']}: {r['score']} ({r['bucket']})")
print(f"  ... total {len(fw_miss_good)}")


# ============================================================
# Save everything
# ============================================================
out = {
    "pair_tops": pair_tops,
    "ryu_park_cases": ryu_park_cases, "lee_park_big_cases": lee_park_big, "ryu_lee_positive_cases": ryu_lee_positive,
    "counterexample_r1h16": counter_r1h16, "counterexample_r2h12": counter_r2h12,
    "same_start_diff_end": same_start_diff_end, "same_miss_diff_recovery": same_miss_diff_recovery,
    "fw_hit_bad": fw_hit_bad, "fw_miss_good": fw_miss_good,
}
(HERE / "spatial_analysis_intermediate.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

with open(HERE / "three_player_same_start_different_end.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["round", "hole", "par", "tolerance_yd", "player_a", "a_remaining_after_tee_yd", "a_score", "a_bucket",
                "player_b", "b_remaining_after_tee_yd", "b_score", "b_bucket", "score_diff"])
    for r in same_start_diff_end:
        w.writerow([r["round"], r["hole"], r["par"], r["tolerance_yd"], r["player_a"], r["a_remaining_after_tee"],
                    r["a_score"], r["a_bucket"], r["player_b"], r["b_remaining_after_tee"], r["b_score"], r["b_bucket"],
                    r["score_diff"]])

with open(HERE / "three_player_same_miss_different_recovery.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["round", "hole", "par", "miss_lie", "tolerance_yd", "player_a", "a_miss_dist_yd", "a_score", "a_bucket",
                "player_b", "b_miss_dist_yd", "b_score", "b_bucket", "score_diff"])
    for r in same_miss_diff_recovery:
        w.writerow([r["round"], r["hole"], r["par"], r["miss_lie"], r["tolerance_yd"], r["player_a"], r["a_miss_dist"],
                    r["a_score"], r["a_bucket"], r["player_b"], r["b_miss_dist"], r["b_score"], r["b_bucket"], r["score_diff"]])

print("\nWrote spatial_analysis_intermediate.json + 2 CSVs")
