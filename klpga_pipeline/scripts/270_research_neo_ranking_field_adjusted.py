"""RESEARCH ONLY (operator instruction, 2026-10-23): explore a DataGolf-
style "sum/average round-level SG, don't accumulate tournament points"
ranking approach for KLPGA, scaled to what this repository's data
actually supports.

Scope discipline:
  - Does NOT touch, read for writing, or regenerate any production
    ranking artifact (NEO_RANKING_V1_FROZEN.json,
    NEO_RANKING_PUBLICATION_GATE_DECISION.json, docs/ranking/, the
    260_build_neo_ranking_page.py pipeline, or anything under docs/).
  - Writes only new files under klpga_pipeline/content/website_v2/research/.
  - Read-only against every existing data file.

IMPORTANT DISCREPANCY WITH THE OPERATOR'S BRIEF (documented here and in
the report, not silently corrected): the operator described reusing an
existing exploratory backtest -- scripts/250_experiment_neo_ranking_v3.py,
NEO_RANKING_V3_EXPLORATORY_BACKTEST.{md,json} -- with 34,982 single-round
SG rows across 105 tournaments, 516 players, and 53 weeks of historical
K-Ranking snapshots. None of those three files exist anywhere in this
repository's history (checked across all branches). The only committed
raw single-round SG source is `content/website_v2/sg_official_history/
<game_code>/RECORDS.json`, which covers 10 tournaments (2026-07-05 to
2026-10-04) and ~3,630 single-round rows -- roughly a tenth of the
described sample. The 53-week K-Ranking snapshot index
(HISTORICAL_KRANKING_SNAPSHOT_INDEX_V1.json) does genuinely exist and
does contain exactly 53 verified weeks, so that part of the brief is
real; the SG side is not. The operator was shown this discrepancy and
asked this script to build baseline/candidates fresh rather than
reproduce unverifiable numbers. Every "0.391 vs 0.386"-style figure in
this script's own output is a FRESH computation on the smaller real
dataset, not a reproduction of the cited numbers.

DATA SOURCES (all pre-existing, read-only):
  - content/website_v2/sg_official_history/*/RECORDS.json -- single_round
    scope rows: player_id, round, total/tee_to_green/off_the_tee/
    approach/around_green/putting SG, date, identity_state.
  - content/website_v2/HISTORICAL_KRANKING_SNAPSHOT_INDEX_V1.json --
    53 weekly official K-Ranking snapshots (rank, player_id per player).

LEAKAGE DISCIPLINE: every score computed "as of" a tournament's start
date uses strictly earlier single-round rows only (date < cutoff), and
every K-Ranking comparison uses the most recent snapshot whose week
started strictly before that same cutoff. Field-strength adjustment
(candidate B) uses only players' own pre-cutoff scores, never the
target tournament's own rows, and the "reference field level" used to
compute the adjustment direction is itself computed only from
strictly-earlier tournaments (so it does not drift using tournaments
that haven't happened yet relative to a given cutoff).
"""
from __future__ import annotations

import json
import math
import random
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
SG_DIR = CONTENT / "sg_official_history"
KRANKING_INDEX = CONTENT / "HISTORICAL_KRANKING_SNAPSHOT_INDEX_V1.json"
OUT_DIR = CONTENT / "research"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HALF_LIFE_DAYS = 365.0
PRIOR_ROUNDS = 32.0
MIN_VALID_ROUNDS = 8.0
FIELD_MIN_PRIOR_ROUNDS = 1.0  # a player needs >=1 weighted prior round to help estimate field strength
BOOTSTRAP_ITERS = 4000
RNG_SEED = 20261023

SG_COMPONENTS = ["total", "tee_to_green", "off_the_tee", "approach", "around_green", "putting"]


# --------------------------------------------------------------------------
# 1. Load + clean single-round SG data
# --------------------------------------------------------------------------

def load_single_round_rows() -> tuple[list[dict], dict]:
    """Returns (rows, integrity_report). rows are single_round-scope,
    identity-resolved, de-duplicated. integrity_report documents every
    exclusion so the final report can state exact counts."""
    all_rows_raw = []
    cumulative_rows = []
    tournament_meta = {}
    for f in sorted(SG_DIR.glob("*/RECORDS.json")):
        game_code = f.parent.name
        recs = json.loads(f.read_text(encoding="utf-8"))
        for r in recs:
            if r.get("game_code") != game_code:
                r = dict(r)
                r["game_code"] = game_code
            if r["scope"] == "single_round":
                all_rows_raw.append(r)
            elif r["scope"] == "tournament_cumulative":
                cumulative_rows.append(r)
        if recs:
            tournament_meta[game_code] = {
                "tournament": recs[0].get("tournament"),
                "date": recs[0].get("date"),
            }

    n_raw = len(all_rows_raw)
    unresolved = [r for r in all_rows_raw if r.get("identity_state") != "RETAINED"]
    resolved = [r for r in all_rows_raw if r.get("identity_state") == "RETAINED"]

    # exact-duplicate rows: same player_id + game_code + round
    seen = {}
    deduped = []
    dup_count = 0
    for r in resolved:
        key = (r["player_id"], r["game_code"], r["round"])
        if key in seen:
            dup_count += 1
            continue
        seen[key] = r
        deduped.append(r)

    # data-quality cross-check: does tournament_cumulative total match the
    # sum of this player's own single_round totals for that tournament?
    cumulative_check = {"checked": 0, "within_tolerance": 0, "mismatches": []}
    by_player_tournament = defaultdict(list)
    for r in deduped:
        by_player_tournament[(r["player_id"], r["game_code"])].append(r)
    for r in cumulative_rows:
        key = (r["player_id"], r["game_code"])
        rounds = by_player_tournament.get(key)
        if not rounds:
            continue
        # DISCOVERY (2026-10-23, found while writing this check): the
        # tournament_cumulative row's `total` is the player's PER-ROUND
        # AVERAGE SG across the tournament, not the sum of round SG --
        # confirmed by sum_of_rounds / cumulative_total landing on
        # exactly the player's round count (within rounding) for every
        # row before this fix. Comparing against the mean, not the sum.
        mean_of_rounds = sum(x["total"] for x in rounds) / len(rounds)
        cumulative_check["checked"] += 1
        if abs(mean_of_rounds - r["total"]) <= 0.02:
            cumulative_check["within_tolerance"] += 1
        else:
            cumulative_check["mismatches"].append({
                "player_id": r["player_id"], "game_code": r["game_code"],
                "cumulative_total_reported": r["total"],
                "mean_of_single_round_rows": round(mean_of_rounds, 4),
                "n_rounds_found": len(rounds),
            })

    integrity_report = {
        "raw_single_round_rows": n_raw,
        "unresolved_identity_excluded": len(unresolved),
        "resolved_rows": len(resolved),
        "exact_duplicate_rows_removed": dup_count,
        "final_single_round_rows": len(deduped),
        "tournaments_covered": len(tournament_meta),
        "distinct_players": len(set(r["player_id"] for r in deduped)),
        "cumulative_vs_sum_of_rounds_check": cumulative_check,
        "tournament_meta": tournament_meta,
    }
    return deduped, integrity_report


# --------------------------------------------------------------------------
# 2. Load K-Ranking snapshot index
# --------------------------------------------------------------------------

def load_kranking_snapshots() -> list[dict]:
    idx = json.loads(KRANKING_INDEX.read_text(encoding="utf-8"))
    snaps = []
    for s in idx["snapshots"]:
        week = s.get("returned_week") or s.get("requested_week")
        if not week or len(week) != 6:
            continue
        iso_year, iso_week = int(week[:4]), int(week[4:])
        try:
            week_start = date.fromisocalendar(iso_year, iso_week, 1)
        except ValueError:
            continue
        snaps.append({
            "week": week,
            "week_start": week_start.isoformat(),
            "records": s.get("records", []),
        })
    snaps.sort(key=lambda s: s["week_start"])
    return snaps


def most_recent_snapshot_before(snaps: list[dict], cutoff_date: str) -> dict | None:
    candidates = [s for s in snaps if s["week_start"] < cutoff_date]
    return candidates[-1] if candidates else None


# --------------------------------------------------------------------------
# 3. Scoring formulas
# --------------------------------------------------------------------------

def days_between(d1: str, d2: str) -> float:
    y1, m1, dd1 = (int(x) for x in d1.split("-"))
    y2, m2, dd2 = (int(x) for x in d2.split("-"))
    return (date(y1, m1, dd1) - date(y2, m2, dd2)).days


def weighted_recency_score(
    rows_before_cutoff: list[dict], cutoff_date: str, component: str,
    half_life_days: float = HALF_LIFE_DAYS, prior_rounds: float = PRIOR_ROUNDS,
    min_valid_rounds: float = MIN_VALID_ROUNDS, prior_mean: float = 0.0,
) -> dict[str, dict]:
    """Candidate A/C core formula: score = (sum(w_i * sg_i) + prior_rounds*prior_mean)
    / (sum(w_i) + prior_rounds), eligible only if sum(w_i) >= min_valid_rounds.
    w_i = 0.5 ** (days_ago / half_life_days). Returns {player_id: {score, eff_n, n_raw}}."""
    by_player = defaultdict(list)
    for r in rows_before_cutoff:
        by_player[r["player_id"]].append(r)
    out = {}
    for pid, rows in by_player.items():
        wsum, wn = 0.0, 0.0
        for r in rows:
            age = days_between(cutoff_date, r["date"])
            if age <= 0:
                continue  # safety: never use same-day-or-after rows
            w = 0.5 ** (age / half_life_days)
            wsum += w * r[component]
            wn += w
        if wn <= 0:
            continue
        score = (wsum + prior_rounds * prior_mean) / (wn + prior_rounds)
        out[pid] = {"score": score, "eff_n": wn, "n_raw": len(rows), "eligible": wn >= min_valid_rounds}
    return out


def field_level_for_tournament(game_code_rows: list[dict], player_prior_scores: dict[str, dict]) -> tuple[float | None, int]:
    """Weighted average of the field's own pre-cutoff `total` scores,
    weighted by each player's effective prior round count. Players with
    no prior rounds (eff_n == 0, i.e. not in player_prior_scores) are
    excluded from this estimate -- never assigned an assumed skill."""
    field_player_ids = set(r["player_id"] for r in game_code_rows)
    wsum, wn, n_contributing = 0.0, 0.0, 0
    for pid in field_player_ids:
        prior = player_prior_scores.get(pid)
        if prior is None or prior["eff_n"] < FIELD_MIN_PRIOR_ROUNDS:
            continue
        wsum += prior["score"] * prior["eff_n"]
        wn += prior["eff_n"]
        n_contributing += 1
    if wn <= 0:
        return None, 0
    return wsum / wn, n_contributing


# --------------------------------------------------------------------------
# 4. Stats helpers (pure python -- no numpy/scipy available in this env)
# --------------------------------------------------------------------------

def spearman(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 3:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    rx = _rank(xs)
    ry = _rank(ys)
    n = len(pairs)
    mean_rx = sum(rx) / n
    mean_ry = sum(ry) / n
    cov = sum((a - mean_rx) * (b - mean_ry) for a, b in zip(rx, ry))
    varx = sum((a - mean_rx) ** 2 for a in rx)
    vary = sum((b - mean_ry) ** 2 for b in ry)
    if varx <= 0 or vary <= 0:
        return None
    return cov / math.sqrt(varx * vary)


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def top20_hit_rate(pairs: list[tuple[float, float]]) -> float | None:
    """|predicted-top-20% intersect actual-top-20%| / |actual-top-20%|."""
    n = len(pairs)
    if n < 5:
        return None
    k = max(1, round(n * 0.2))
    pred_idx = set(sorted(range(n), key=lambda i: -pairs[i][0])[:k])
    actual_idx = set(sorted(range(n), key=lambda i: -pairs[i][1])[:k])
    return len(pred_idx & actual_idx) / len(actual_idx)


def bootstrap_ci(per_tournament_values: list[float], iters: int = BOOTSTRAP_ITERS, seed: int = RNG_SEED) -> dict:
    vals = [v for v in per_tournament_values if v is not None]
    if len(vals) < 2:
        return {"mean": (statistics.mean(vals) if vals else None), "n_tournaments": len(vals),
                "ci_low": None, "ci_high": None, "note": "fewer than 2 tournament-level values; CI not computable"}
    rng = random.Random(seed)
    means = []
    n = len(vals)
    for _ in range(iters):
        sample = [vals[rng.randrange(n)] for _ in range(n)]
        means.append(statistics.mean(sample))
    means.sort()
    lo = means[int(0.025 * iters)]
    hi = means[int(0.975 * iters) - 1]
    return {"mean": statistics.mean(vals), "n_tournaments": n, "ci_low": lo, "ci_high": hi}


# --------------------------------------------------------------------------
# 4b. Fixed 2025-regulars cohort + cohort-restricted A/B validation
#     (operator instruction, 2026-10-23 follow-up)
# --------------------------------------------------------------------------

R1_FULL_FIELD_PATH = CONTENT / "NEO_HISTORICAL_R1_FULL_FIELD_V1.json"
MIN_2025_STARTS = 20


def load_2025_cohort(min_starts: int = MIN_2025_STARTS) -> dict:
    """Fixed evaluation cohort: players with >=min_starts confirmed R1
    starts in the 2025 season, counted from the FULL FIELD (not the
    6-player PLAYER_HISTORY subset) so coverage isn't limited to a
    handful of players. Source: NEO_HISTORICAL_R1_FULL_FIELD_V1.json,
    a roundLeaderboard-sourced full-field R1 capture (CUT/incomplete
    included -- a player who withdrew before teeing off never appears
    on a posted round leaderboard, so presence in this list already
    means "started"). Determined ONLY from season-2025 rows -- this
    function takes no 2026 information whatsoever, so cohort membership
    can never be re-selected using how many times a player ends up
    playing in 2026 (see report section 13 for why that would leak)."""
    data = json.loads(R1_FULL_FIELD_PATH.read_text(encoding="utf-8"))
    starts = defaultdict(int)
    names = {}
    tournaments_2025 = set()
    for rec in data["records"]:
        if int(rec["event_date"][:4]) != 2025:
            continue
        tournaments_2025.add(rec["game_code"])
        for p in rec["players"]:
            pid = p["player_code"]
            starts[pid] += 1
            names[pid] = p["player_name"]
    cohort = {pid for pid, c in starts.items() if c >= min_starts}
    return {
        "cohort_player_ids": cohort,
        "starts_2025_all_players": dict(starts),
        "names": names,
        "n_tournaments_2025_in_source": len(tournaments_2025),
        "n_distinct_players_2025": len(starts),
        "min_starts_threshold": min_starts,
    }


def _rmse_mae(pairs: list[tuple[float, float]]) -> tuple[float | None, float | None]:
    if not pairs:
        return None, None
    errs = [pred - actual for pred, actual in pairs]
    rmse = math.sqrt(sum(e * e for e in errs) / len(errs))
    mae = sum(abs(e) for e in errs) / len(errs)
    return rmse, mae


def leave_one_tournament_out(per_tournament_values: list[tuple[str, float | None]]) -> list[dict]:
    """Deterministic jackknife: for each tournament, the mean of the
    OTHER tournaments' values, so a single dominant tournament shows up
    as a visible swing rather than being averaged away silently."""
    vals = [(gc, v) for gc, v in per_tournament_values if v is not None]
    out = []
    for i, (excluded_gc, _) in enumerate(vals):
        rest = [v for j, (gc, v) in enumerate(vals) if j != i]
        out.append({
            "excluded_tournament": excluded_gc,
            "mean_of_remaining": statistics.mean(rest) if rest else None,
            "n_remaining": len(rest),
        })
    return out


def run_cohort_restricted_analysis(rows, tournaments, rows_by_tournament, snaps, cohort: set) -> dict:
    """Baseline A vs field-adjusted B, on `total` SG only, restricted to
    the fixed 2025-regulars cohort. K-Ranking is computed and reported
    ONLY as a reference column -- never used to decide pass/fail here.
    Fixed config (365-day half-life / 32 prior rounds / min 8 valid
    rounds) -- no parameter search in this pass."""
    per_tournament = []
    for game_code, t_date in tournaments:
        rows_before = [r for r in rows if r["date"] < t_date]
        if not rows_before:
            continue  # first tournament: no finished history yet at all

        scores_A = weighted_recency_score(rows_before, t_date, "total")

        earlier_tournaments = [(gc, d) for gc, d in tournaments if d < t_date]
        field_levels = {}
        for gc, d in earlier_tournaments:
            rows_before_that = [r for r in rows if r["date"] < d]
            if not rows_before_that:
                continue
            prior_scores_at_that_time = weighted_recency_score(rows_before_that, d, "total")
            lvl, _n = field_level_for_tournament(rows_by_tournament[gc], prior_scores_at_that_time)
            if lvl is not None:
                field_levels[gc] = lvl
        reference_level = statistics.mean(field_levels.values()) if field_levels else None
        this_field_level, this_field_n = field_level_for_tournament(rows_by_tournament[game_code], scores_A)
        candidate_B_usable = reference_level is not None and this_field_level is not None and len(field_levels) >= 3
        field_adjustment = (this_field_level - reference_level) if candidate_B_usable else None

        scores_B = {}
        if candidate_B_usable:
            adjusted_rows_before = []
            for r in rows_before:
                lvl_r = field_levels.get(r["game_code"])
                if lvl_r is None:
                    continue
                rr = dict(r)
                rr["total"] = r["total"] + (lvl_r - reference_level)
                adjusted_rows_before.append(rr)
            scores_B = weighted_recency_score(adjusted_rows_before, t_date, "total")

        snap = most_recent_snapshot_before(snaps, t_date)
        kr_rank = {}
        if snap:
            for rec in snap["records"]:
                pid, rk = rec.get("player_id"), rec.get("rank")
                if pid and rk is not None:
                    try:
                        kr_rank[pid] = -float(rk)
                    except (TypeError, ValueError):
                        pass

        outcome_by_player = defaultdict(list)
        for r in rows_by_tournament[game_code]:
            if r["round"] in (1, 2):
                outcome_by_player[r["player_id"]].append(r["total"])
        outcomes = {pid: statistics.mean(vals) for pid, vals in outcome_by_player.items() if vals}

        eligible_A = {pid for pid, s in scores_A.items() if s["eligible"]} & cohort
        eligible_B = (set(scores_B.keys()) if candidate_B_usable else set()) & cohort
        eligible_outcome = set(outcomes.keys()) & cohort

        common_A = eligible_A & eligible_outcome
        common_B = eligible_B & eligible_outcome
        common_AB_fair = eligible_A & eligible_B & eligible_outcome
        common_K_ref = eligible_A & set(kr_rank.keys()) & eligible_outcome

        pairs_A = [(scores_A[p]["score"], outcomes[p]) for p in common_A]
        pairs_B = [(scores_B[p]["score"], outcomes[p]) for p in common_B]
        pairs_A_fair = [(scores_A[p]["score"], outcomes[p]) for p in common_AB_fair]
        pairs_B_fair = [(scores_B[p]["score"], outcomes[p]) for p in common_AB_fair]
        pairs_K_ref = [(kr_rank[p], outcomes[p]) for p in common_K_ref]

        rmse_A, mae_A = _rmse_mae(pairs_A)
        rmse_B, mae_B = _rmse_mae(pairs_B)

        per_tournament.append({
            "game_code": game_code,
            "date": t_date,
            "n_cohort_eligible_A": len(common_A),
            "n_cohort_eligible_B": len(common_B),
            "n_cohort_fair_AB": len(common_AB_fair),
            "n_cohort_K_reference": len(common_K_ref),
            "candidate_B_usable": candidate_B_usable,
            "field_adjustment": field_adjustment,
            "spearman_A": spearman(pairs_A),
            "spearman_B": spearman(pairs_B) if pairs_B else None,
            "spearman_A_fair_vs_B": spearman(pairs_A_fair) if pairs_A_fair else None,
            "spearman_B_fair_vs_A": spearman(pairs_B_fair) if pairs_B_fair else None,
            "spearman_K_reference_only": spearman(pairs_K_ref) if pairs_K_ref else None,
            "top20_hit_A": top20_hit_rate(pairs_A),
            "top20_hit_B": top20_hit_rate(pairs_B) if pairs_B else None,
            "rmse_A": rmse_A, "mae_A": mae_A,
            "rmse_B": rmse_B, "mae_B": mae_B,
        })

    def ci(key):
        return bootstrap_ci([r[key] for r in per_tournament if r.get(key) is not None])

    def loo(key):
        return leave_one_tournament_out([(r["game_code"], r.get(key)) for r in per_tournament])

    diff_spearman_B_minus_A = []
    for r in per_tournament:
        a, b = r["spearman_A_fair_vs_B"], r["spearman_B_fair_vs_A"]
        diff_spearman_B_minus_A.append((r["game_code"], (b - a) if (a is not None and b is not None) else None))

    return {
        "per_tournament": per_tournament,
        "summary": {
            "spearman_A": ci("spearman_A"),
            "spearman_B": ci("spearman_B"),
            "top20_hit_A": ci("top20_hit_A"),
            "top20_hit_B": ci("top20_hit_B"),
            "rmse_A": ci("rmse_A"), "mae_A": ci("mae_A"),
            "rmse_B": ci("rmse_B"), "mae_B": ci("mae_B"),
            "diff_spearman_B_minus_A_fair_cohort": bootstrap_ci([d for _gc, d in diff_spearman_B_minus_A if d is not None]),
            "spearman_K_reference_only": ci("spearman_K_reference_only"),
            "n_tournaments_evaluated": len(per_tournament),
            "n_tournaments_with_B_usable": sum(1 for r in per_tournament if r["candidate_B_usable"]),
        },
        "leave_one_tournament_out": {
            "spearman_A": loo("spearman_A"),
            "spearman_B": loo("spearman_B"),
            "rmse_A": loo("rmse_A"),
            "rmse_B": loo("rmse_B"),
            "diff_spearman_B_minus_A": [
                {"excluded_tournament": gc, "mean_of_remaining": (
                    statistics.mean([d for g2, d in diff_spearman_B_minus_A if g2 != gc and d is not None])
                    if any(g2 != gc and d is not None for g2, d in diff_spearman_B_minus_A) else None
                )}
                for gc, _d in diff_spearman_B_minus_A if _d is not None
            ],
        },
        "note": (
            "K-Ranking numbers in this block (spearman_K_reference_only) are "
            "REFERENCE ONLY per explicit instruction -- not used for any "
            "pass/fail or better/worse judgment here. Cohort fixed from "
            "2025-season data only (load_2025_cohort); never re-filtered by "
            "2026 participation counts."
        ),
    }


# --------------------------------------------------------------------------
# 5. Main walk-forward evaluation
# --------------------------------------------------------------------------

def main() -> None:
    rows, integrity = load_single_round_rows()
    snaps = load_kranking_snapshots()

    tournaments = sorted(
        {(r["game_code"], r["date"]) for r in rows}, key=lambda t: t[1]
    )
    rows_by_tournament = defaultdict(list)
    for r in rows:
        rows_by_tournament[r["game_code"]].append(r)

    results = {
        "method_display_names": {
            "A": "기준선 (고정 365일/32라운드/최소8라운드 가중평균+수축)",
            "C": "최근성적+적은표본조정 (동일 산식, 탐색용 출발점)",
            "B": "필드수준 보정 후보",
            "K": "공식 K-Ranking",
        },
        "per_tournament": [],
        "component_breakdown": {},
    }

    # main evaluation loop, per SG component
    for component in SG_COMPONENTS:
        per_tournament_records = []
        for idx_t, (game_code, t_date) in enumerate(tournaments):
            rows_before = [r for r in rows if r["date"] < t_date]
            if not rows_before:
                continue  # first tournament(s): no history at all, cannot score

            scores_AC = weighted_recency_score(rows_before, t_date, component)

            # Candidate B: field-adjustment, using TOTAL for field-level estimation
            # (field strength is a single tournament-level quantity, estimated
            # from players' own pre-cutoff `total` SG regardless of which
            # component we're scoring this pass -- a field is strong/weak as
            # a whole, not per SG sub-component).
            prior_total_scores = weighted_recency_score(rows_before, t_date, "total")
            earlier_tournaments = [(gc, d) for gc, d in tournaments if d < t_date]
            # field level for each earlier tournament, using ITS OWN pre-cutoff prior scores
            field_levels = {}
            for gc, d in earlier_tournaments:
                rows_before_that = [r for r in rows if r["date"] < d]
                if not rows_before_that:
                    continue
                prior_scores_at_that_time = weighted_recency_score(rows_before_that, d, "total")
                lvl, n_c = field_level_for_tournament(rows_by_tournament[gc], prior_scores_at_that_time)
                if lvl is not None:
                    field_levels[gc] = lvl
            reference_level = statistics.mean(field_levels.values()) if field_levels else None
            this_field_level, this_field_n = field_level_for_tournament(rows_by_tournament[game_code], prior_total_scores)

            candidate_B_usable = reference_level is not None and this_field_level is not None and len(field_levels) >= 3
            field_adjustment = (this_field_level - reference_level) if candidate_B_usable else None

            scores_B = {}
            if candidate_B_usable:
                # each historical row is adjusted by ITS OWN tournament's field
                # adjustment (relative to the same reference_level) -- never by
                # this target tournament's adjustment.
                adjusted_rows_before = []
                for r in rows_before:
                    gc_r = r["game_code"]
                    lvl_r = field_levels.get(gc_r)
                    if lvl_r is None:
                        continue  # skip rows whose own tournament's field level isn't estimable
                    adj_r = lvl_r - reference_level
                    rr = dict(r)
                    rr[component] = r[component] + adj_r
                    adjusted_rows_before.append(rr)
                scores_B = weighted_recency_score(adjusted_rows_before, t_date, component)

            # K-Ranking snapshot as of cutoff
            snap = most_recent_snapshot_before(snaps, t_date)
            kr_rank = {}
            if snap:
                for rec in snap["records"]:
                    pid = rec.get("player_id")
                    rk = rec.get("rank")
                    if pid and rk is not None:
                        try:
                            kr_rank[pid] = -float(rk)  # higher = better, for consistent orientation
                        except (TypeError, ValueError):
                            pass

            # outcome: this tournament's own R1/R2 mean (component), from the
            # ORIGINAL (unadjusted) rows -- never the adjusted ones, and never
            # mixed with rows_before.
            this_tournament_rows = rows_by_tournament[game_code]
            outcome_by_player = defaultdict(list)
            for r in this_tournament_rows:
                if r["round"] in (1, 2):
                    outcome_by_player[r["player_id"]].append(r[component])
            outcomes = {pid: statistics.mean(vals) for pid, vals in outcome_by_player.items() if vals}

            eligible_A = {pid for pid, s in scores_AC.items() if s["eligible"]}
            eligible_B = set(scores_B.keys()) if candidate_B_usable else set()
            eligible_K = set(kr_rank.keys())
            eligible_outcome = set(outcomes.keys())

            common_ABK = eligible_A & eligible_K & eligible_outcome
            common_B = (eligible_B & eligible_K & eligible_outcome) if candidate_B_usable else set()
            # for a FAIR, same-cohort B-vs-baseline comparison: both methods'
            # scores evaluated on the exact same player set (must be eligible
            # under BOTH A and B, plus present in K-Ranking and have an
            # outcome) -- NOT the same set common_ABK (A-only) uses.
            common_AB_fair = (eligible_A & eligible_B & eligible_K & eligible_outcome) if candidate_B_usable else set()

            pairs_A = [(scores_AC[p]["score"], outcomes[p]) for p in common_ABK]
            pairs_K = [(kr_rank[p], outcomes[p]) for p in common_ABK]
            pairs_C = pairs_A  # identical formula in this implementation; see report
            pairs_B = [(scores_B[p]["score"], outcomes[p]) for p in common_B]
            pairs_K_for_B = [(kr_rank[p], outcomes[p]) for p in common_B]
            # same-cohort pairs for the direct B-vs-A paired difference
            pairs_A_fair = [(scores_AC[p]["score"], outcomes[p]) for p in common_AB_fair]
            pairs_B_fair = [(scores_B[p]["score"], outcomes[p]) for p in common_AB_fair]

            spearman_B_val = spearman(pairs_B) if pairs_B else None
            spearman_K_for_B_val = spearman(pairs_K_for_B) if pairs_K_for_B else None
            top20_B_val = top20_hit_rate(pairs_B) if pairs_B else None
            top20_K_for_B_val = top20_hit_rate(pairs_K_for_B) if pairs_K_for_B else None

            spearman_A_fair_val = spearman(pairs_A_fair) if pairs_A_fair else None
            spearman_B_fair_val = spearman(pairs_B_fair) if pairs_B_fair else None
            top20_A_fair_val = top20_hit_rate(pairs_A_fair) if pairs_A_fair else None
            top20_B_fair_val = top20_hit_rate(pairs_B_fair) if pairs_B_fair else None

            # paired per-tournament differences (same cohort both sides) --
            # these are what get bootstrapped for the B-vs-K and B-vs-A
            # confidence intervals, NOT separate marginal CIs compared
            # informally.
            diff_spearman_B_minus_K = (
                spearman_B_val - spearman_K_for_B_val
                if spearman_B_val is not None and spearman_K_for_B_val is not None else None
            )
            diff_top20_B_minus_K = (
                top20_B_val - top20_K_for_B_val
                if top20_B_val is not None and top20_K_for_B_val is not None else None
            )
            diff_spearman_B_minus_A = (
                spearman_B_fair_val - spearman_A_fair_val
                if spearman_B_fair_val is not None and spearman_A_fair_val is not None else None
            )
            diff_top20_B_minus_A = (
                top20_B_fair_val - top20_A_fair_val
                if top20_B_fair_val is not None and top20_A_fair_val is not None else None
            )

            rec = {
                "game_code": game_code,
                "date": t_date,
                "component": component,
                "n_common_A_K_outcome": len(common_ABK),
                "n_common_B_K_outcome": len(common_B),
                "n_common_AB_fair": len(common_AB_fair),
                "candidate_B_usable": candidate_B_usable,
                "field_adjustment_this_tournament": field_adjustment,
                "field_level_n_contributing_players": this_field_n,
                "reference_level_n_prior_tournaments": len(field_levels),
                "spearman_A": spearman(pairs_A),
                "spearman_K_matched_to_A": spearman(pairs_K),
                "top20_hit_A": top20_hit_rate(pairs_A),
                "top20_hit_K_matched_to_A": top20_hit_rate(pairs_K),
                "spearman_B": spearman_B_val,
                "spearman_K_matched_to_B": spearman_K_for_B_val,
                "top20_hit_B": top20_B_val,
                "top20_hit_K_matched_to_B": top20_K_for_B_val,
                "spearman_A_fair_vs_B": spearman_A_fair_val,
                "spearman_B_fair_vs_A": spearman_B_fair_val,
                "top20_hit_A_fair_vs_B": top20_A_fair_val,
                "top20_hit_B_fair_vs_A": top20_B_fair_val,
                "diff_spearman_B_minus_K": diff_spearman_B_minus_K,
                "diff_top20_B_minus_K": diff_top20_B_minus_K,
                "diff_spearman_B_minus_A": diff_spearman_B_minus_A,
                "diff_top20_B_minus_A": diff_top20_B_minus_A,
            }
            per_tournament_records.append(rec)

        results["component_breakdown"][component] = {
            "per_tournament": per_tournament_records,
            "summary": {
                "spearman_A": bootstrap_ci([r["spearman_A"] for r in per_tournament_records]),
                "spearman_K_matched_to_A": bootstrap_ci([r["spearman_K_matched_to_A"] for r in per_tournament_records]),
                "top20_hit_A": bootstrap_ci([r["top20_hit_A"] for r in per_tournament_records]),
                "top20_hit_K_matched_to_A": bootstrap_ci([r["top20_hit_K_matched_to_A"] for r in per_tournament_records]),
                "spearman_B": bootstrap_ci([r["spearman_B"] for r in per_tournament_records if r["spearman_B"] is not None]),
                "spearman_K_matched_to_B": bootstrap_ci([r["spearman_K_matched_to_B"] for r in per_tournament_records if r["spearman_K_matched_to_B"] is not None]),
                "top20_hit_B": bootstrap_ci([r["top20_hit_B"] for r in per_tournament_records if r["top20_hit_B"] is not None]),
                "top20_hit_K_matched_to_B": bootstrap_ci([r["top20_hit_K_matched_to_B"] for r in per_tournament_records if r["top20_hit_K_matched_to_B"] is not None]),
                "n_tournaments_with_B_usable": sum(1 for r in per_tournament_records if r["candidate_B_usable"]),
                "n_tournaments_total": len(per_tournament_records),
            },
            "paired_comparison": {
                "diff_spearman_B_minus_K": bootstrap_ci([r["diff_spearman_B_minus_K"] for r in per_tournament_records if r["diff_spearman_B_minus_K"] is not None]),
                "diff_top20_B_minus_K": bootstrap_ci([r["diff_top20_B_minus_K"] for r in per_tournament_records if r["diff_top20_B_minus_K"] is not None]),
                "diff_spearman_B_minus_A": bootstrap_ci([r["diff_spearman_B_minus_A"] for r in per_tournament_records if r["diff_spearman_B_minus_A"] is not None]),
                "diff_top20_B_minus_A": bootstrap_ci([r["diff_top20_B_minus_A"] for r in per_tournament_records if r["diff_top20_B_minus_A"] is not None]),
                "n_tournaments_diff_B_minus_K": sum(1 for r in per_tournament_records if r["diff_spearman_B_minus_K"] is not None),
                "n_tournaments_diff_B_minus_A": sum(1 for r in per_tournament_records if r["diff_spearman_B_minus_A"] is not None),
                "note": "Paired tournament-level bootstrap: each tournament contributes ONE already-matched-cohort difference value (B minus K, or B minus A, same players both sides); resampling tournaments (not players) preserves the pairing. 95% CI from 2000-4000 resamples' percentiles.",
            },
        }

    cohort_info = load_2025_cohort()
    cohort_restricted = run_cohort_restricted_analysis(
        rows, tournaments, rows_by_tournament, snaps, cohort_info["cohort_player_ids"]
    )
    results["cohort_restricted_2025_regulars_analysis"] = {
        "cohort_definition": {
            "min_2025_starts": cohort_info["min_starts_threshold"],
            "n_players_in_cohort": len(cohort_info["cohort_player_ids"]),
            "n_distinct_players_seen_2025": cohort_info["n_distinct_players_2025"],
            "n_tournaments_2025_in_source": cohort_info["n_tournaments_2025_in_source"],
            "cohort_player_ids": sorted(cohort_info["cohort_player_ids"]),
        },
        **cohort_restricted,
    }

    results["integrity_report"] = integrity
    results["config"] = {
        "half_life_days": HALF_LIFE_DAYS, "prior_rounds": PRIOR_ROUNDS,
        "min_valid_rounds": MIN_VALID_ROUNDS, "field_min_prior_rounds": FIELD_MIN_PRIOR_ROUNDS,
        "bootstrap_iters": BOOTSTRAP_ITERS, "rng_seed": RNG_SEED,
        "tournaments_in_order": [{"game_code": gc, "date": d} for gc, d in tournaments],
        "kranking_snapshots_loaded": len(snaps),
    }

    out_path = OUT_DIR / "NEO_RANKING_FIELD_ADJUSTED_V1_EXPLORATORY.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": str(out_path),
        "integrity_report": integrity,
        "total_summary_example_component": results["component_breakdown"]["total"]["summary"],
        "total_paired_comparison": results["component_breakdown"]["total"]["paired_comparison"],
        "cohort_restricted_summary": results["cohort_restricted_2025_regulars_analysis"]["summary"],
        "cohort_definition": results["cohort_restricted_2025_regulars_analysis"]["cohort_definition"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
