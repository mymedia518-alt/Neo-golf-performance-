"""NEO derived shot-analysis layer for HiteJinro 2026100005.

READ-ONLY against the immutable RAW/normalized Shot Tracker data
(klpga_shots_RAW_READONLY.sqlite, a verbatim copy of the collected
table). Never writes back to that table. Produces a separate derived
layer only.

The 6 confirmed SOURCE_GAP (player, round) pairs (real absence at the
source, verified via both the group and per-player endpoints -- see
diagnose_result.json) are emitted as explicit NULL/SOURCE_GAP rows,
never interpolated or estimated.

GIR definition (explicit, literal): the first shot whose state_code is
exactly "3" (GREEN) must occur by shot number <= par-2. state_code
"12" (FRINGE) never counts as reaching the green for this purpose.
"""
from __future__ import annotations
import csv, json, sqlite3, statistics
from pathlib import Path

HERE = Path(__file__).parent
DB_PATH = HERE / "klpga_shots_RAW_READONLY.sqlite"
PLAYERS_JSON = HERE / "players_RAW_READONLY.json"
GAME_CODE = "2026100005"

# Confirmed real par per hole (holeInfo.stdScore, identical across all
# 4 rounds across 72 real raw files -- see par consistency check).
PAR_BY_HOLE = {1: 4, 2: 3, 3: 4, 4: 5, 5: 3, 6: 4, 7: 5, 8: 4, 9: 4,
               10: 5, 11: 3, 12: 4, 13: 4, 14: 4, 15: 4, 16: 3, 17: 4, 18: 5}

# Confirmed real SOURCE_GAP pairs (diagnose_result.json: zero shots via
# BOTH the group and per-player endpoints, for every one of 18 holes).
SOURCE_GAPS = [
    ("8240", 2), ("10112", 2), ("11076", 2), ("11978", 2), ("8246", 2),
    ("9401", 1),
]

LOW_SAMPLE_THRESHOLD = 5

TEE_MISS_MAP = {"2": "ROUGH", "6": "BUNKER", "5": "PENALTY", "4": "OB"}


def load_players():
    data = json.loads(PLAYERS_JSON.read_text(encoding="utf-8"))
    out = {}
    for pc, info in data["players"].items():
        out[pc] = {"player_name": info.get("player_name"), "rounds": sorted(set(info.get("rounds") or []))}
    return out


def fetch_all_shots(con):
    rows = con.execute(
        "SELECT player_code, player_name, round, hole, shot, state_code "
        "FROM klpga_player_shot WHERE game_code=? ORDER BY player_code, round, hole, shot",
        (GAME_CODE,),
    ).fetchall()
    grouped = {}
    for pc, name, rnd, hole, shot, state_code in rows:
        grouped.setdefault((pc, rnd, hole), []).append((shot, state_code, name))
    return grouped


def compute_hole_record(par, shots):
    """shots: list of (shot_number, state_code, player_name), sorted by shot_number."""
    strokes = len(shots)
    score_to_par = strokes - par

    first_shot_state = shots[0][1] if shots else None

    fw_hit = None
    tee_miss_state = None
    if par in (4, 5) and shots:
        if first_shot_state == "1":
            fw_hit = True
        else:
            fw_hit = False
            tee_miss_state = TEE_MISS_MAP.get(first_shot_state, "OTHER")

    gir_shot_number = None
    for shot_no, state_code, _ in shots:
        if state_code == "3":
            gir_shot_number = shot_no
            break
    gir = gir_shot_number is not None and gir_shot_number <= (par - 2)
    gir_miss = not gir

    final_score = strokes
    par_or_better = score_to_par <= 0

    return {
        "par": par,
        "strokes": strokes,
        "score_to_par": score_to_par,
        "first_shot_state": first_shot_state,
        "fw_hit": fw_hit,
        "tee_miss_state": tee_miss_state,
        "gir": gir,
        "gir_shot_number": gir_shot_number,
        "gir_miss": gir_miss,
        "final_score": final_score,
        "par_or_better": par_or_better,
    }


def build_derived_rows():
    con = sqlite3.connect(DB_PATH)
    grouped = fetch_all_shots(con)
    players = load_players()

    source_gap_set = set(SOURCE_GAPS)
    rows = []

    for (pc, rnd, hole), shots in sorted(grouped.items()):
        shots_sorted = sorted(shots, key=lambda s: s[0])
        par = PAR_BY_HOLE[hole]
        rec = compute_hole_record(par, shots_sorted)
        player_name = shots_sorted[0][2] if shots_sorted else players.get(pc, {}).get("player_name")
        rows.append({
            "game_code": GAME_CODE, "player_code": pc, "player_name": player_name,
            "round": rnd, "hole": hole, "source_gap": False, **rec,
        })

    # Explicit SOURCE_GAP rows -- never estimated, never interpolated.
    for pc, rnd in SOURCE_GAPS:
        player_name = players.get(pc, {}).get("player_name")
        for hole in range(1, 19):
            par = PAR_BY_HOLE[hole]
            rows.append({
                "game_code": GAME_CODE, "player_code": pc, "player_name": player_name,
                "round": rnd, "hole": hole, "source_gap": True,
                "par": par, "strokes": None, "score_to_par": None,
                "first_shot_state": None, "fw_hit": None, "tee_miss_state": None,
                "gir": None, "gir_shot_number": None, "gir_miss": None,
                "final_score": None, "par_or_better": None,
            })

    rows.sort(key=lambda r: (r["player_code"], r["round"], r["hole"]))
    return rows, players


def write_player_hole_csv(rows, out_path):
    cols = ["game_code", "player_code", "player_name", "round", "hole", "par", "strokes",
            "score_to_par", "first_shot_state", "fw_hit", "tee_miss_state", "gir",
            "gir_shot_number", "gir_miss", "final_score", "par_or_better", "source_gap"]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c) for c in cols})


def real_rows(rows):
    return [r for r in rows if not r["source_gap"]]


def rate(numer_rows, denom_rows):
    n = len(denom_rows)
    if n == 0:
        return None, 0
    k = sum(1 for r in numer_rows)
    return k / n, n


def mean_or_none(values):
    values = [v for v in values if v is not None]
    if not values:
        return None, 0
    return statistics.mean(values), len(values)


# ---------------------------------------------------------------------------
# Transition metrics (shared helper -- used at ALL/per-player/per-hole scope)
# ---------------------------------------------------------------------------

def transition_metrics(subset):
    """subset: list of real (non-source-gap) hole records (dicts) to
    compute transitions over. Returns dict of {metric_name: (rate, n)}."""
    par45 = [r for r in subset if r["par"] in (4, 5)]
    fw_hit_holes = [r for r in par45 if r["fw_hit"] is True]
    fw_miss_holes = [r for r in par45 if r["fw_hit"] is False]
    rough_holes = [r for r in fw_miss_holes if r["tee_miss_state"] == "ROUGH"]
    bunker_holes = [r for r in fw_miss_holes if r["tee_miss_state"] == "BUNKER"]
    other_miss_holes = [r for r in fw_miss_holes if r["tee_miss_state"] not in ("ROUGH", "BUNKER")]
    gir_miss_holes_all = [r for r in subset if r["gir"] is False]

    def gir_rate(group):
        n = len(group)
        if n == 0:
            return None, 0
        k = sum(1 for r in group if r["gir"])
        return k / n, n

    def par_or_better_rate(group):
        n = len(group)
        if n == 0:
            return None, 0
        k = sum(1 for r in group if r["par_or_better"])
        return k / n, n

    m = {}
    m["FW_to_GIR"] = gir_rate(fw_hit_holes)
    m["FW_to_GIR_Miss"] = (1 - gir_rate(fw_hit_holes)[0], gir_rate(fw_hit_holes)[1]) if gir_rate(fw_hit_holes)[0] is not None else (None, 0)
    m["Rough_to_GIR"] = gir_rate(rough_holes)
    m["Rough_to_GIR_Miss"] = (1 - gir_rate(rough_holes)[0], gir_rate(rough_holes)[1]) if gir_rate(rough_holes)[0] is not None else (None, 0)
    m["Bunker_to_GIR"] = gir_rate(bunker_holes)
    m["OtherTeeMiss_to_GIR"] = gir_rate(other_miss_holes)
    m["FWMiss_to_GIR"] = gir_rate(fw_miss_holes)
    m["FWHit_to_ParOrBetter"] = par_or_better_rate(fw_hit_holes)
    m["FWMiss_to_ParOrBetter"] = par_or_better_rate(fw_miss_holes)
    m["GIRMiss_to_ParSave"] = par_or_better_rate(gir_miss_holes_all)
    m["Rough_to_ParSave"] = par_or_better_rate(rough_holes)
    m["Bunker_to_ParSave"] = par_or_better_rate(bunker_holes)
    return m


# ---------------------------------------------------------------------------
# neo_player_event_shot_metrics.csv
# ---------------------------------------------------------------------------

def build_player_event_metrics(rows):
    rr = real_rows(rows)
    by_player = {}
    for r in rr:
        by_player.setdefault(r["player_code"], []).append(r)

    out = []
    for pc, subset in sorted(by_player.items()):
        name = subset[0]["player_name"]
        holes_analyzed = len(subset)
        avg_score_to_par, _ = mean_or_none([r["score_to_par"] for r in subset])
        par45 = [r for r in subset if r["par"] in (4, 5)]
        fw_hit_rate, fw_hit_n = rate((r for r in par45 if r["fw_hit"] is True), par45)
        gir_rate_val, gir_n = rate((r for r in subset if r["gir"]), subset)
        trans = transition_metrics(subset)
        row = {
            "player_code": pc, "player_name": name,
            "holes_analyzed": holes_analyzed,
            "avg_score_to_par": avg_score_to_par,
            "fw_hit_rate": fw_hit_rate, "fw_hit_rate_n": fw_hit_n,
            "gir_rate": gir_rate_val, "gir_rate_n": gir_n,
        }
        for k, (val, n) in trans.items():
            row[f"{k}_rate"] = val
            row[f"{k}_n"] = n
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# neo_hole_shot_metrics.csv
# ---------------------------------------------------------------------------

def build_hole_metrics(rows):
    rr = real_rows(rows)
    by_hole = {}
    for r in rr:
        by_hole.setdefault(r["hole"], []).append(r)

    out = []
    for hole in range(1, 19):
        subset = by_hole.get(hole, [])
        par = PAR_BY_HOLE[hole]
        n = len(subset)
        score_to_pars = [r["score_to_par"] for r in subset]
        avg_score_to_par, _ = mean_or_none(score_to_pars)
        stdev_score_to_par = statistics.pstdev(score_to_pars) if len(score_to_pars) > 1 else 0.0
        birdie_or_better_rate = sum(1 for s in score_to_pars if s <= -1) / n if n else None
        bogey_or_worse_rate = sum(1 for s in score_to_pars if s >= 1) / n if n else None
        par_rate = sum(1 for s in score_to_pars if s == 0) / n if n else None
        gir_rate_val = sum(1 for r in subset if r["gir"]) / n if n else None
        trans = transition_metrics(subset)
        row = {
            "hole": hole, "par": par, "n_player_rounds": n,
            "avg_score_to_par": avg_score_to_par,
            "stdev_score_to_par": stdev_score_to_par,
            "birdie_or_better_rate": birdie_or_better_rate,
            "bogey_or_worse_rate": bogey_or_worse_rate,
            "par_rate": par_rate,
            "gir_rate": gir_rate_val,
        }
        for k, (val, tn) in trans.items():
            row[f"{k}_rate"] = val
            row[f"{k}_n"] = tn
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# neo_miss_penalty.csv
# ---------------------------------------------------------------------------

def build_miss_penalty(rows):
    rr = real_rows(rows)
    by_hole = {}
    for r in rr:
        by_hole.setdefault(r["hole"], []).append(r)

    out = []
    for hole in range(1, 19):
        subset = by_hole.get(hole, [])
        par = PAR_BY_HOLE[hole]
        fw_hit = [r for r in subset if r["fw_hit"] is True]
        fw_miss = [r for r in subset if r["fw_hit"] is False]
        rough = [r for r in fw_miss if r["tee_miss_state"] == "ROUGH"]
        bunker = [r for r in fw_miss if r["tee_miss_state"] == "BUNKER"]
        penalty_ob = [r for r in fw_miss if r["tee_miss_state"] in ("PENALTY", "OB", "OTHER")]

        fw_hit_avg, fw_hit_n = mean_or_none([r["score_to_par"] for r in fw_hit])
        fw_miss_avg, fw_miss_n = mean_or_none([r["score_to_par"] for r in fw_miss])
        rough_avg, rough_n = mean_or_none([r["score_to_par"] for r in rough])
        bunker_avg, bunker_n = mean_or_none([r["score_to_par"] for r in bunker])
        penalty_ob_avg, penalty_ob_n = mean_or_none([r["score_to_par"] for r in penalty_ob])

        def cost_vs_fw_hit(avg, n):
            if avg is None or fw_hit_avg is None:
                return None
            return avg - fw_hit_avg

        row = {
            "hole": hole, "par": par,
            "fw_hit_avg_score_to_par": fw_hit_avg, "fw_hit_n": fw_hit_n,
            "fw_miss_avg_score_to_par": fw_miss_avg, "fw_miss_n": fw_miss_n,
            "fw_miss_cost_vs_fw_hit": cost_vs_fw_hit(fw_miss_avg, fw_miss_n),
            "fw_miss_LOW_SAMPLE": fw_miss_n < LOW_SAMPLE_THRESHOLD,
            "rough_avg_score_to_par": rough_avg, "rough_n": rough_n,
            "rough_cost_vs_fw_hit": cost_vs_fw_hit(rough_avg, rough_n),
            "rough_LOW_SAMPLE": rough_n < LOW_SAMPLE_THRESHOLD,
            "bunker_avg_score_to_par": bunker_avg, "bunker_n": bunker_n,
            "bunker_cost_vs_fw_hit": cost_vs_fw_hit(bunker_avg, bunker_n),
            "bunker_LOW_SAMPLE": bunker_n < LOW_SAMPLE_THRESHOLD,
            "penalty_ob_avg_score_to_par": penalty_ob_avg, "penalty_ob_n": penalty_ob_n,
            "penalty_ob_cost_vs_fw_hit": cost_vs_fw_hit(penalty_ob_avg, penalty_ob_n),
            "penalty_ob_LOW_SAMPLE": penalty_ob_n < LOW_SAMPLE_THRESHOLD,
            "fw_hit_LOW_SAMPLE": fw_hit_n < LOW_SAMPLE_THRESHOLD,
        }
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# neo_course_strategy.csv -- classification thresholds defined BEFORE
# looking at per-hole results; never adjusted after seeing them.
# ---------------------------------------------------------------------------

def build_course_strategy(hole_metrics, miss_penalty_rows):
    mp_by_hole = {r["hole"]: r for r in miss_penalty_rows}

    # miss_penalty per hole: fw_miss_cost_vs_fw_hit when FW concept
    # applies (par 4/5); for par-3 holes (no fairway target), fall back
    # to the GIR-based analogue already present in hole_metrics
    # (bogey_or_worse_rate - birdie_or_better_rate is not a cost in
    # strokes, so for par-3 holes we use the hole's own avg_score_to_par
    # as the risk proxy instead, documented explicitly in the report).
    def misspenalty_for(h):
        mp = mp_by_hole[h["hole"]]
        if h["par"] in (4, 5) and mp["fw_miss_cost_vs_fw_hit"] is not None:
            return mp["fw_miss_cost_vs_fw_hit"]
        return None  # par-3: no FW-based miss penalty defined

    birdie_rates = [h["birdie_or_better_rate"] for h in hole_metrics if h["birdie_or_better_rate"] is not None]
    bogey_rates = [h["bogey_or_worse_rate"] for h in hole_metrics if h["bogey_or_worse_rate"] is not None]
    miss_penalties = [misspenalty_for(h) for h in hole_metrics]
    miss_penalties_defined = [m for m in miss_penalties if m is not None]

    median_birdie = statistics.median(birdie_rates)
    median_bogey = statistics.median(bogey_rates)
    median_misspenalty = statistics.median(miss_penalties_defined) if miss_penalties_defined else 0.0

    out = []
    for h in hole_metrics:
        mp_val = misspenalty_for(h)
        birdie = h["birdie_or_better_rate"]
        bogey = h["bogey_or_worse_rate"]

        is_attack = (birdie is not None and birdie > median_birdie) and (mp_val is not None and mp_val <= median_misspenalty)
        is_defend = (bogey is not None and bogey > median_bogey) and (mp_val is not None and mp_val > median_misspenalty)

        if mp_val is None:
            # Par-3: no FW-based miss penalty exists -- classify on
            # birdie/bogey rate alone against the same medians.
            is_attack = birdie is not None and birdie > median_birdie and (bogey is None or bogey <= median_bogey)
            is_defend = bogey is not None and bogey > median_bogey and (birdie is None or birdie <= median_birdie)

        if is_attack and not is_defend:
            classification = "ATTACK"
        elif is_defend and not is_attack:
            classification = "DEFEND"
        else:
            classification = "CONTROL"

        out.append({
            "hole": h["hole"], "par": h["par"],
            "birdie_or_better_rate": birdie, "bogey_or_worse_rate": bogey,
            "miss_penalty_strokes": mp_val,
            "median_birdie_rate_threshold": median_birdie,
            "median_bogey_rate_threshold": median_bogey,
            "median_miss_penalty_threshold": median_misspenalty,
            "classification": classification,
        })
    return out, {"median_birdie": median_birdie, "median_bogey": median_bogey, "median_misspenalty": median_misspenalty}


# ---------------------------------------------------------------------------
# Hypothesis test: does FW-miss -> GIR survival explain score beyond the
# simpler FW-hit-rate / GIR-rate stats? Pre-defined eligibility: a player
# needs >=10 par4/5 holes analyzed (for fw_hit_rate/GIR-related stats to
# be minimally meaningful) and >=3 FW-miss holes to compute a FWMiss_to_GIR
# rate at all -- otherwise excluded, and N is reported either way.
# ---------------------------------------------------------------------------

MIN_PAR45_HOLES = 10
MIN_FW_MISS_HOLES = 3
CORR_MEANINGFUL_R = 0.30  # pre-defined threshold, not chosen post-hoc


def pearson(xs, ys):
    import numpy as np
    if len(xs) < 3:
        return None
    arr = np.corrcoef(xs, ys)
    r = arr[0, 1]
    if r != r:  # NaN (zero-variance input)
        return None
    return float(r)


def build_hypothesis_report(rows, player_metrics_rows):
    rr = real_rows(rows)
    by_player = {}
    for r in rr:
        by_player.setdefault(r["player_code"], []).append(r)

    eligible = []
    for pm in player_metrics_rows:
        pc = pm["player_code"]
        subset = by_player.get(pc, [])
        par45 = [r for r in subset if r["par"] in (4, 5)]
        fw_miss = [r for r in par45 if r["fw_hit"] is False]
        if len(par45) >= MIN_PAR45_HOLES and len(fw_miss) >= MIN_FW_MISS_HOLES:
            eligible.append(pm)

    def series(key):
        return [pm[key] for pm in eligible if pm[key] is not None and pm["avg_score_to_par"] is not None]

    def paired(key):
        pairs = [(pm[key], pm["avg_score_to_par"]) for pm in eligible if pm[key] is not None and pm["avg_score_to_par"] is not None]
        if not pairs:
            return [], []
        xs, ys = zip(*pairs)
        return list(xs), list(ys)

    correlations = {}
    for label, key in [
        ("fw_hit_rate_vs_score", "fw_hit_rate"),
        ("gir_rate_vs_score", "gir_rate"),
        ("fw_miss_to_gir_vs_score", "FWMiss_to_GIR_rate"),
        ("fw_hit_to_gir_vs_score", "FW_to_GIR_rate"),
        ("rough_to_gir_vs_score", "Rough_to_GIR_rate"),
        ("gir_miss_to_par_save_vs_score", "GIRMiss_to_ParSave_rate"),
    ]:
        xs, ys = paired(key)
        r = pearson(xs, ys)
        correlations[label] = {"r": r, "n": len(xs)}

    # Group comparison: split eligible players into top/bottom half by
    # FWMiss_to_GIR_rate (survival ability), compare avg_score_to_par.
    with_fwmg = [pm for pm in eligible if pm.get("FWMiss_to_GIR_rate") is not None]
    with_fwmg_sorted = sorted(with_fwmg, key=lambda pm: pm["FWMiss_to_GIR_rate"])
    group_comparison = None
    if len(with_fwmg_sorted) >= 6:
        half = len(with_fwmg_sorted) // 2
        low_group = with_fwmg_sorted[:half]
        high_group = with_fwmg_sorted[-half:]
        low_avg, low_n = mean_or_none([pm["avg_score_to_par"] for pm in low_group])
        high_avg, high_n = mean_or_none([pm["avg_score_to_par"] for pm in high_group])
        group_comparison = {
            "low_FWMiss_to_GIR_group": {"n": low_n, "avg_score_to_par": low_avg},
            "high_FWMiss_to_GIR_group": {"n": high_n, "avg_score_to_par": high_avg},
            "difference_strokes": (high_avg - low_avg) if (low_avg is not None and high_avg is not None) else None,
        }

    # Verdict: does fw_miss_to_gir correlate with score AT LEAST as
    # strongly as plain fw_hit_rate/gir_rate, with the expected sign
    # (higher survival -> lower/more-negative score_to_par)?
    r_fwmg = correlations["fw_miss_to_gir_vs_score"]["r"]
    r_fwhit = correlations["fw_hit_rate_vs_score"]["r"]
    r_gir = correlations["gir_rate_vs_score"]["r"]
    n_fwmg = correlations["fw_miss_to_gir_vs_score"]["n"]

    if r_fwmg is None or n_fwmg < 10:
        verdict = "REJECTED"
        verdict_reason = f"insufficient eligible players (n={n_fwmg}) to evaluate fw_miss_to_gir_vs_score"
    elif abs(r_fwmg) >= CORR_MEANINGFUL_R and r_fwmg < 0 and (r_fwhit is None or abs(r_fwmg) >= abs(r_fwhit) * 0.8):
        verdict = "CONFIRMED"
        verdict_reason = f"fw_miss_to_gir_vs_score r={r_fwmg:.3f} (n={n_fwmg}) meets |r|>={CORR_MEANINGFUL_R} with expected sign, comparable to or stronger than fw_hit_rate alone (r={r_fwhit})"
    elif r_fwmg < 0 and abs(r_fwmg) > 0.15:
        verdict = "PARTIAL"
        verdict_reason = f"fw_miss_to_gir_vs_score r={r_fwmg:.3f} (n={n_fwmg}) has the expected sign but does not clear the pre-defined |r|>={CORR_MEANINGFUL_R} threshold"
    else:
        verdict = "REJECTED"
        verdict_reason = f"fw_miss_to_gir_vs_score r={r_fwmg} (n={n_fwmg}) does not support the hypothesis"

    return {
        "eligible_player_count": len(eligible),
        "eligibility_rule": f">= {MIN_PAR45_HOLES} par4/5 holes analyzed AND >= {MIN_FW_MISS_HOLES} FW-miss holes",
        "correlations": correlations,
        "group_comparison_by_FWMiss_to_GIR": group_comparison,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
    }


def write_csv(rows, out_path, cols=None):
    if not rows:
        Path(out_path).write_text("", encoding="utf-8")
        return
    cols = cols or list(rows[0].keys())
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c) for c in cols})


if __name__ == "__main__":
    rows, players = build_derived_rows()
    out_dir = HERE
    write_player_hole_csv(rows, out_dir / "neo_player_hole_shot_derived.csv")
    print(f"wrote {len(rows)} rows ({sum(1 for r in rows if r['source_gap'])} SOURCE_GAP) to neo_player_hole_shot_derived.csv")

    player_metrics = build_player_event_metrics(rows)
    write_csv(player_metrics, out_dir / "neo_player_event_shot_metrics.csv")
    print(f"wrote {len(player_metrics)} rows to neo_player_event_shot_metrics.csv")

    hole_metrics = build_hole_metrics(rows)
    write_csv(hole_metrics, out_dir / "neo_hole_shot_metrics.csv")
    print(f"wrote {len(hole_metrics)} rows to neo_hole_shot_metrics.csv")

    miss_penalty = build_miss_penalty(rows)
    write_csv(miss_penalty, out_dir / "neo_miss_penalty.csv")
    print(f"wrote {len(miss_penalty)} rows to neo_miss_penalty.csv")

    strategy, thresholds = build_course_strategy(hole_metrics, miss_penalty)
    write_csv(strategy, out_dir / "neo_course_strategy.csv")
    print(f"wrote {len(strategy)} rows to neo_course_strategy.csv, thresholds={thresholds}")

    hyp = build_hypothesis_report(rows, player_metrics)
    (out_dir / "hypothesis_report.json").write_text(json.dumps(hyp, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(hyp, ensure_ascii=False, indent=2))
