"""Full 18-hole DEFEND/CONTROL/ATTACK classification verification for
the 3 case-study players, extending (not replacing) the existing
7H/8H case study. Uses ONLY the already-independently-verified
per-hole reconstruction (neo_three_player_raw_reconstruction.csv,
itself re-derived from RAW with 0 mismatches against the derived CSV)
-- no RAW or derived-CSV modification, no re-fetching, no estimation.
"""
from __future__ import annotations
import csv, json
from pathlib import Path

HERE = Path(__file__).parent

CLASSIFICATION = {
    "DEFEND": [6, 8, 10, 12],
    "CONTROL": [1, 3, 5, 9, 11, 13, 15, 17],
    "ATTACK": [2, 4, 7, 14, 16, 18],
}
HOLE_TO_CLASS = {h: c for c, holes in CLASSIFICATION.items() for h in holes}

PLAYERS = {"9115": "유해란 (TOP, #1)", "9708": "이재윤 (MID, #27)", "9111": "박서현 (BOTTOM, #61)"}
OFFICIAL_TOTAL_UNDER_PAR = {"9115": -4, "9708": 9, "9111": 26}


def score_label(score_to_par):
    if score_to_par <= -1:
        return "birdie_or_better"
    if score_to_par == 0:
        return "par"
    if score_to_par == 1:
        return "bogey"
    return "double_or_worse"


def load_reconstruction():
    rows = list(csv.DictReader(open(HERE / "neo_three_player_raw_reconstruction.csv", encoding="utf-8")))
    return rows


def main():
    rows = load_reconstruction()
    by_player_hole = {}
    for r in rows:
        if r["NOTE"]:
            raise RuntimeError(f"unexpected gap in already-verified reconstruction: {r}")
        pc, hole = r["player_code"], int(r["hole"])
        by_player_hole.setdefault((pc, hole), []).append(r)

    per_player_hole_totals = {}  # (pc, hole) -> total score_to_par across 4 rounds
    per_player_class_totals = {}  # (pc, class) -> dict of aggregates

    for pc in PLAYERS:
        for hole in range(1, 19):
            instances = by_player_hole.get((pc, hole), [])
            if len(instances) != 4:
                raise RuntimeError(f"expected 4 rounds for {pc} hole {hole}, found {len(instances)}")
            total_stp = sum(int(r["score_to_par"]) for r in instances)
            per_player_hole_totals[(pc, hole)] = total_stp

    class_rows = []
    for pc in PLAYERS:
        for cls, holes in CLASSIFICATION.items():
            agg = {
                "total_score_to_par": 0, "birdie_or_better": 0, "par": 0, "bogey": 0,
                "double_or_worse": 0, "fw_hit": 0, "fw_miss": 0, "gir": 0,
                "fw_miss_to_gir": 0, "fw_miss_n": 0, "gir_miss_to_par_save": 0, "gir_miss_n": 0,
            }
            for hole in holes:
                for r in by_player_hole[(pc, hole)]:
                    stp = int(r["score_to_par"])
                    agg["total_score_to_par"] += stp
                    agg[score_label(stp)] += 1
                    if r["fw_hit"] == "True":
                        agg["fw_hit"] += 1
                    elif r["fw_hit"] == "False":
                        agg["fw_miss"] += 1
                        agg["fw_miss_n"] += 1
                        if r["gir"] == "True":
                            agg["fw_miss_to_gir"] += 1
                    if r["gir"] == "True":
                        agg["gir"] += 1
                    if r["gir"] == "False":
                        agg["gir_miss_n"] += 1
                        if stp <= 0:
                            agg["gir_miss_to_par_save"] += 1
            class_rows.append({"player_code": pc, "player_name": PLAYERS[pc], "classification": cls, **agg})
            per_player_class_totals[(pc, cls)] = agg

    # Per-hole output (all 18, for completeness/audit)
    hole_rows = []
    for pc in PLAYERS:
        for hole in range(1, 19):
            hole_rows.append({
                "player_code": pc, "player_name": PLAYERS[pc], "hole": hole,
                "classification": HOLE_TO_CLASS[hole],
                "total_score_to_par_4R": per_player_hole_totals[(pc, hole)],
            })

    with open(HERE / "neo_three_player_hole_classification.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["player_code", "player_name", "hole", "classification", "total_score_to_par_4R"])
        w.writeheader()
        for r in hole_rows:
            w.writerow(r)

    with open(HERE / "neo_three_player_classification_summary.csv", "w", newline="", encoding="utf-8") as fh:
        cols = ["player_code", "player_name", "classification", "total_score_to_par", "birdie_or_better",
                "par", "bogey", "double_or_worse", "fw_hit", "fw_miss", "gir", "fw_miss_to_gir", "fw_miss_n",
                "gir_miss_to_par_save", "gir_miss_n"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in class_rows:
            w.writerow(r)

    # --- Mandatory cross-check: sum of 3 classification totals == official total_under_par
    print("=" * 80)
    print("CROSS-CHECK: DEFEND + CONTROL + ATTACK total_score_to_par vs official total_under_par")
    print("=" * 80)
    all_pass = True
    summary = {}
    for pc, name in PLAYERS.items():
        defend = per_player_class_totals[(pc, "DEFEND")]["total_score_to_par"]
        control = per_player_class_totals[(pc, "CONTROL")]["total_score_to_par"]
        attack = per_player_class_totals[(pc, "ATTACK")]["total_score_to_par"]
        computed_total = defend + control + attack
        official = OFFICIAL_TOTAL_UNDER_PAR[pc]
        match = computed_total == official
        all_pass = all_pass and match
        summary[pc] = {"DEFEND": defend, "CONTROL": control, "ATTACK": attack, "computed_total": computed_total, "official": official, "MATCH": match}
        print(f"{name}: DEFEND={defend:+d} CONTROL={control:+d} ATTACK={attack:+d} => computed_total={computed_total:+d} official={official:+d} MATCH={match}")

    print()
    print("=" * 80)
    print("요구 1/2/3 -- 분류별 타수 손익")
    print("=" * 80)
    for pc, name in PLAYERS.items():
        s = summary[pc]
        print(f"{name}: DEFEND(4홀)={s['DEFEND']:+d}타, CONTROL(8홀)={s['CONTROL']:+d}타, ATTACK(6홀)={s['ATTACK']:+d}타")

    print()
    print("=" * 80)
    print("유해란 vs 박서현 30타 격차 분해 (박서현 - 유해란, 분류별)")
    print("=" * 80)
    top = summary["9115"]
    bottom = summary["9111"]
    gap_total = bottom["computed_total"] - top["computed_total"]
    gap_defend = bottom["DEFEND"] - top["DEFEND"]
    gap_control = bottom["CONTROL"] - top["CONTROL"]
    gap_attack = bottom["ATTACK"] - top["ATTACK"]
    print(f"전체 격차: {bottom['official']:+d} - ({top['official']:+d}) = {bottom['official'] - top['official']:+d}타")
    print(f"계산된 격차(검증용): {gap_total:+d}타 (DEFEND {gap_defend:+d} + CONTROL {gap_control:+d} + ATTACK {gap_attack:+d} = {gap_defend+gap_control+gap_attack:+d})")
    print(f"  DEFEND 격차: {gap_defend:+d}타")
    print(f"  CONTROL 격차: {gap_control:+d}타")
    print(f"  ATTACK 격차: {gap_attack:+d}타")

    decomposition = {
        "gap_total_official": bottom["official"] - top["official"],
        "gap_total_computed": gap_total,
        "gap_DEFEND": gap_defend,
        "gap_CONTROL": gap_control,
        "gap_ATTACK": gap_attack,
    }
    with open(HERE / "neo_three_player_classification_crosscheck.json", "w", encoding="utf-8") as fh:
        json.dump({"per_player": summary, "ALL_MATCH": all_pass, "top_vs_bottom_gap_decomposition": decomposition}, fh, ensure_ascii=False, indent=2)

    print()
    if not all_pass:
        print("VERDICT: FAIL -- a player's classification-sum does not equal their official total_under_par")
        raise SystemExit(1)
    print("VERDICT: PASS -- all 3 players' DEFEND+CONTROL+ATTACK exactly equals their official total_under_par")


if __name__ == "__main__":
    main()
