"""GAP DECOMPOSITION RED TEAM AUDIT
Rebuilds an enriched 216-record chain fresh from RAW (reconciled against
official round scores), fixes a real off-by-one bug found in the previously
reused putts_count() (it counted the GIR-achieving approach shot itself as
a putt -- confirmed against a known 2-putt par, R1H12 Ryu: old formula said
3, actual is 2), and implements two independent, non-summed accounting
layers:
  LAYER A: causal / shot-stage attribution (TEE/APPROACH/RECOVERY/
           PUTTING/PENALTY/UNRESOLVED), DIRECT vs ESCALATION split so one
           stroke never gets attributed to two stages.
  LAYER B: event-severity decomposition (BIRDIE/PAR/BOGEY/DOUBLE+), a
           completely separate axis, not added to Layer A.
Does NOT touch or delete any Steps 1-25 file. Does NOT start a Hole-8
standalone analysis -- hole-level aggregation here is limited to what's
needed to quantify the R3-R4 deterioration question.
"""
from __future__ import annotations
import json, sqlite3, statistics
from pathlib import Path
from collections import defaultdict, Counter

HERE = Path(__file__).parent
DB = HERE / "klpga_shots_RAW_READONLY.sqlite"
GAME = "2026100005"
PLAYERS = {"9115": "유해란", "9708": "이재윤", "9111": "박서현"}
PAR_YDS = json.loads((HERE / "klpga_tournament_18hole_par_yardage.json").read_text())
PIN_AUDIT = json.loads((HERE / "pin_placement_72hole_audit.json").read_text())
PINS = {(e["round"], e["hole"]): e for e in PIN_AUDIT["per_round_hole_table"]}
LIE_NAME = {"1": "FAIRWAY", "2": "ROUGH", "3": "GREEN", "4": "OB", "5": "PENALTY_AREA",
            "6": "BUNKER", "7": "LOST_BALL", "8": "PENALTY_STROKE", "9": "GREENSIDE_BUNKER",
            "10": "HOLED", "12": "FRINGE"}
PENALTY_STATES = {"4", "5", "7", "8"}
UNRELIABLE_DISTANCE_STATES = {"4", "5", "7", "8"}
OFFICIAL_ROUND_SCORES = {
    "유해란": {1: 73, 2: 69, 3: 73, 4: 69},
    "이재윤": {1: 76, 2: 75, 3: 74, 4: 72},
    "박서현": {1: 75, 2: 78, 3: 81, 4: 80},
}


def putts_count_fixed(ss):
    """A putt = a shot whose STARTING lie is already on the green. The shot
    that FIRST brings the ball onto the green (approach/recovery) is not a
    putt even though its resulting state is '3'. Old formula (reused from
    hole1_full_analysis.py across this whole project) counted that shot as
    a putt -- verified wrong against R1H12 Ryu (known 2-putt par: old=3)."""
    last_off_green = -1
    for i, s in enumerate(ss):
        if s["state"] not in ("3", "10"):
            last_off_green = i
    g = last_off_green + 1
    if g >= len(ss):
        return 0
    if ss[g]["state"] == "10":
        return 0  # holed directly from off the green (chip-in), 0 putts
    return len(ss) - 1 - g


def first_putt_distance(ss):
    """Distance-to-pin value logged on the shot that FIRST reaches the
    green (state '3') -- this is the real, RAW-sourced first-putt length
    in yards (the 'distance' column = remaining distance AFTER a shot,
    confirmed via R1H12 Ryu: tee dist=114.3 -> approach dist=6.4 -> that
    6.4 is exactly the first putt's starting distance)."""
    for s in ss:
        if s["state"] == "3":
            return s["distance"]
    return None


def classify_stage(ss, par, fw_hit, gir):
    """Returns (first_failure_stage, escalation_stage_or_None,
    direct_cost, excess_cost, notes). Stages: TEE/APPROACH/RECOVERY/
    PUTTING/PENALTY/UNRESOLVED/NONE (no failure)."""
    # find index of first green/holed arrival
    green_idx = None
    for i, s in enumerate(ss):
        if s["state"] in ("3", "10"):
            green_idx = i
            break
    pre_green = ss[:green_idx] if green_idx is not None else ss[:]
    penalty_pre_green = any(s["state"] in PENALTY_STATES for s in pre_green)
    putts = putts_count_fixed(ss)

    if penalty_pre_green:
        first_failure = "PENALTY"
    elif par != 3 and not fw_hit:
        first_failure = "TEE"
    elif not gir:
        first_failure = "APPROACH"
    elif putts >= 3:
        first_failure = "PUTTING"
    else:
        first_failure = "NONE"

    if first_failure == "NONE":
        return "NONE", None, 0, 0, "par-or-better, no failure stage"

    # Determine escalation: what happens AFTER the first-failure point
    escalation = None
    if first_failure == "TEE":
        if penalty_pre_green:
            escalation = "PENALTY"
        elif not gir:
            escalation = "APPROACH"  # missed green too, after an already-bad tee shot
        elif putts >= 3:
            escalation = "PUTTING"
        else:
            escalation = None  # clean single tee-cost bogey
    elif first_failure == "APPROACH":
        # how many shots between approach-miss and reaching green?
        shots_to_reach_green = green_idx - 1 if green_idx is not None else None
        if penalty_pre_green:
            escalation = "PENALTY"
        elif shots_to_reach_green is not None and shots_to_reach_green >= 2:
            escalation = "RECOVERY"
        elif putts >= 3:
            escalation = "PUTTING"
        else:
            escalation = None  # clean single approach-miss bogey (up-and-down just missed)
    elif first_failure == "PENALTY":
        n_pen = sum(1 for s in ss if s["state"] in PENALTY_STATES)
        if n_pen >= 2:
            escalation = "PENALTY"  # repeat/compounding penalty
        elif not gir:
            escalation = "RECOVERY"
        elif putts >= 3:
            escalation = "PUTTING"
        else:
            escalation = None
    elif first_failure == "PUTTING":
        escalation = None  # putting IS the first and only failure

    strokes_over_par = len(ss) - par
    direct = min(strokes_over_par, 1) if strokes_over_par >= 1 else 0
    excess = max(strokes_over_par - 1, 0)
    return first_failure, escalation, direct, excess, ""


def main():
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT player_code, round, hole, shot, state_code, x, y, green_x, green_y, distance "
        "FROM klpga_player_shot WHERE game_code=? AND player_code IN (?,?,?) "
        "ORDER BY player_code, round, hole, shot",
        (GAME, *PLAYERS.keys()),
    ).fetchall()
    by_prh = defaultdict(list)
    for pc, rnd, hole, shot, state, x, y, gx, gy, dist in rows:
        by_prh[(pc, rnd, hole)].append({"shot": shot, "state": state, "x": x, "y": y,
                                         "green_x": gx, "green_y": gy, "distance": dist})

    records = []
    for pc, pname in PLAYERS.items():
        for rnd in (1, 2, 3, 4):
            for hole in range(1, 19):
                ss = sorted(by_prh[(pc, rnd, hole)], key=lambda s: s["shot"])
                par = PAR_YDS[str(hole)]["par"]
                strokes = len(ss)
                stp = strokes - par
                fw_hit = ss[0]["state"] == "1"
                gir_shot = next((s["shot"] for s in ss if s["state"] == "3"), None)
                gir = gir_shot is not None and gir_shot <= par - 2
                putts = putts_count_fixed(ss)
                fp_dist = first_putt_distance(ss)
                first_failure, escalation, direct, excess, notes = classify_stage(ss, par, fw_hit, gir)
                if stp <= -1: bucket = "Birdie+"
                elif stp == 0: bucket = "Par"
                elif stp == 1: bucket = "Bogey"
                elif stp == 2: bucket = "Double"
                else: bucket = "TriplePlus"
                records.append({
                    "player_code": pc, "player_name": pname, "round": rnd, "hole": hole, "par": par,
                    "strokes": strokes, "score_to_par": stp, "score_bucket": bucket,
                    "fw_hit": fw_hit, "gir": gir, "putts_fixed": putts, "first_putt_distance_yd": fp_dist,
                    "first_failure_stage": first_failure, "escalation_stage": escalation,
                    "direct_cost": direct, "excess_cost": excess,
                    "state_sequence": [s["state"] for s in ss],
                    "distance_sequence": [s["distance"] for s in ss],
                })

    # ---- RAW reconciliation (zero tolerance) ----
    by_pr_tot = defaultdict(int)
    for r in records:
        by_pr_tot[(r["player_name"], r["round"])] += r["strokes"]
    recon_ok = True
    recon_rows = []
    for (name, rnd), tot in sorted(by_pr_tot.items()):
        exp = OFFICIAL_ROUND_SCORES[name][rnd]
        ok = tot == exp
        recon_ok = recon_ok and ok
        recon_rows.append({"player": name, "round": rnd, "computed": tot, "official": exp, "match": ok})
    print(f"RAW reconciliation (216/216 required): n_records={len(records)}, all_match={recon_ok}")
    for r in recon_rows:
        if not r["match"]:
            print("  MISMATCH:", r)

    out = {"game_code": GAME, "n_records": len(records), "raw_reconciliation_pass": recon_ok and len(records) == 216,
           "raw_reconciliation_detail": recon_rows, "records": records}
    (HERE / "three_player_attribution_chain.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("Wrote three_player_attribution_chain.json")


if __name__ == "__main__":
    main()
