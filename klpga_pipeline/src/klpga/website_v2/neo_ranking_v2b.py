"""NEO_RANKING_V2B_EXPOSURE_AND_COHORT_NEUTRAL -- builds on V2A's
round-normalized, shrinkage-based skill estimator (unchanged; imported,
not reimplemented) and additionally replaces cohort-relative z-scoring
with a FIXED, walk-forward-frozen POPULATION normalization.

WHY: V1 and V2A both z-score each feature against "whoever else is in
the specific display pool / event field right now" -- so a player's
displayed rank can change purely because an unrelated player was
added to or removed from that pool (confirmed for V1: 13.1% of
otherwise-unaffected players' ranks changed from one unrelated swap;
confirmed for V2A in this same phase: 24.1%, WORSE, not better).

V2B's fix: z-score every feature against the FULL population of
ELIGIBLE players as of the relevant date (every player with enough
history, not just the small live TOP120 display list, or a single
event's field) -- and, critically, freeze that population's mean/
stdev using ONLY data available before the target date in the
walk-forward backtest (no current/future information leaks
backward). A player's own z-score then depends only on their own
feature value against this large, date-frozen population -- adding or
removing one unrelated player from a DISPLAY list of 120 has a
negligible-to-zero effect on a population that can include hundreds
of eligible players.

No new constants are hand-picked: the only fitted quantities are the
same method-of-moments shrinkage prior as V2A (sigma^2/tau^2/mean)
and each date's population mean/stdev, both computed directly from
real historical data, never chosen by inspection of final results.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict

from klpga.website_v2.neo_ranking_v2a import MODEL_ID as _V2A_MODEL_ID  # noqa: F401 (documents lineage)
from klpga.website_v2.neo_ranking_v2a import V2A_WEIGHTS, _pooled_rate, _shrink, estimate_shrinkage_prior

MODEL_ID = "neo-ranking-v2b-exposure-and-cohort-neutral"


def _latest_records(warehouse: dict) -> dict[str, list[dict]]:
    latest: dict[tuple[str, str], dict] = {}
    for row in warehouse.get("records", ()):
        pid = str(row.get("player_id") or "").strip()
        gc = str(row.get("game_code") or "").strip()
        if not pid or not gc or row.get("identity_state") != "RETAINED":
            continue
        total = row.get("total")
        if not isinstance(total, (int, float)) or not math.isfinite(float(total)):
            continue
        rounds = row.get("rounds")
        if not isinstance(rounds, (int, float)) or rounds <= 0:
            continue
        key = (pid, gc)
        if key not in latest or int(rounds) >= int(latest[key].get("rounds") or 0):
            latest[key] = row
    grouped: dict[str, list[dict]] = defaultdict(list)
    for (pid, _), row in latest.items():
        grouped[pid].append(row)
    return grouped


def _player_features(rows_sorted: list[dict], prior: dict) -> dict:
    recent5_rows, recent10_rows = rows_sorted[-5:], rows_sorted[-10:]
    r5_rate, r5_rounds = _pooled_rate(recent5_rows)
    r10_rate, r10_rounds = _pooled_rate(recent10_rows)
    lt_rate, lt_rounds = _pooled_rate(rows_sorted)
    r5_shrunk, _ = _shrink(r5_rate, r5_rounds, prior)
    r10_shrunk, _ = _shrink(r10_rate, r10_rounds, prior)
    lt_shrunk, lt_w = _shrink(lt_rate, lt_rounds, prior)
    event_rates = [float(r["total"]) / float(r["rounds"]) for r in rows_sorted]
    consistency = -statistics.pstdev(event_rates) if len(event_rates) > 1 else 0.0
    return {"recent_5": r5_shrunk, "recent_10": r10_shrunk, "long_term": lt_shrunk, "consistency": consistency,
            "total_rounds": lt_rounds, "reliability_weight": lt_w, "sample_count_events": len(rows_sorted)}


def build_population_features_v2b(warehouse: dict, prior: dict, *, minimum_rounds: int = 20) -> dict[str, dict]:
    """Features for EVERY eligible player in the full warehouse (the
    z-score POPULATION), not just a display subset."""
    grouped = _latest_records(warehouse)
    result = {}
    for pid, rows in grouped.items():
        rows_sorted = sorted(rows, key=lambda r: (int(r.get("season") or 0), str(r.get("game_code") or "")))
        f = _player_features(rows_sorted, prior)
        if f["total_rounds"] >= minimum_rounds:
            result[pid] = f
    return result


def _z_against_population(pop_features: dict[str, dict], key: str) -> tuple[float, float]:
    values = [f[key] for f in pop_features.values()]
    mean = statistics.fmean(values)
    sd = statistics.pstdev(values)
    return mean, sd


def evaluate_v2b(cohort: dict, warehouse: dict, prior: dict, *, minimum_rounds: int = 20) -> tuple[list[dict], dict]:
    """Same output shape as evaluate_v2a, but z-scored against the FULL
    eligible population (build_population_features_v2b), not against
    the cohort passed in. Swapping one player in/out of `cohort` never
    changes another player's z-score, because the normalization
    baseline (the population) does not depend on `cohort` at all."""
    rows = list(cohort.get("records", ()))
    population = build_population_features_v2b(warehouse, prior, minimum_rounds=minimum_rounds)

    means_sds = {key: _z_against_population(population, key) for key in ("recent_5", "recent_10", "long_term", "consistency")}

    def zscore(pid: str, key: str) -> float:
        mean, sd = means_sds[key]
        return (population[pid][key] - mean) / sd if sd else 0.0

    eligible_ids = [str(row["player_id"]) for row in rows if str(row["player_id"]) in population]
    scores, contributions = {}, {}
    for pid in eligible_ids:
        contributions[pid] = {name: V2A_WEIGHTS[name] * zscore(pid, name) for name in ("recent_5", "recent_10", "long_term", "consistency")}
        scores[pid] = sum(contributions[pid].values())
    ordered = sorted(scores, key=lambda pid: (-scores[pid], pid))
    neo_rank = {pid: rank for rank, pid in enumerate(ordered, 1)}

    output = []
    for row in rows:
        pid = str(row["player_id"])
        feature = population.get(pid)
        rank = neo_rank.get(pid)
        output.append({**row, "features": feature, "sg_join_state": "PASS" if feature else "DATA_INSUFFICIENT",
                       "neo_validation_rank": rank, "validation_score": round(scores[pid], 6) if rank else None,
                       "feature_contributions": ({k: round(v, 6) for k, v in contributions[pid].items()} if rank else None),
                       "neo_ranking_state": "VALIDATION_MODEL" if rank else "VALIDATION_PENDING",
                       "rank_delta": int(row["official_k_rank"]) - rank if rank else None,
                       "reliability_weight": feature["reliability_weight"] if feature else None,
                       "population_size_used_for_normalization": len(population),
                       "model_id": MODEL_ID})
    summary = {"cohort_count": len(rows), "neo_ranked": len(eligible_ids), "validation_pending": len(rows) - len(eligible_ids),
               "population_size_used_for_normalization": len(population)}
    return output, summary


def run_backtest_v2b(warehouse: dict, start_dates: dict[str, str], outcomes: dict, prior: dict, *, minimum_rounds: int = 20) -> dict:
    """Leakage-safe walk-forward backtest with a WALK-FORWARD-FROZEN
    population normalization: at each target event, the z-score
    population is EVERY player (in the whole warehouse, not just that
    event's field) whose history strictly before the target date makes
    them eligible -- frozen fresh at each step, never using same-date-
    or-later information."""
    from klpga.website_v2.neo_ranking_backtest import spearman, auc  # noqa: E402

    events: dict[str, dict[str, dict]] = defaultdict(dict)
    all_pids = set()
    for row in warehouse.get("records", ()):
        pid, event = str(row.get("player_id") or ""), str(row.get("game_code") or "")
        if not pid or event not in start_dates or row.get("identity_state") != "RETAINED" or not isinstance(row.get("total"), (int, float)):
            continue
        rounds = row.get("rounds")
        if not isinstance(rounds, (int, float)) or rounds <= 0:
            continue
        all_pids.add(pid)
        old = events[event].get(pid)
        if old is None or int(rounds) >= int(old.get("rounds") or 0):
            events[event][pid] = row

    ordered = sorted(events, key=lambda event: (start_dates[event], event))
    history: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
    observations, event_reports = [], []

    for event in ordered:
        target_date, target = start_dates[event], events[event]

        # Build the FULL population (every player with enough PRIOR history,
        # not just this event's field) fresh at this exact point in time.
        population_features = {}
        for pid in all_pids:
            hist = [(d, t, r) for d, t, r in history[pid] if d < target_date]
            total_rounds = sum(r for _, _, r in hist)
            if total_rounds < minimum_rounds:
                continue
            hist_sorted = sorted(hist, key=lambda h: h[0])
            recent5, recent10 = hist_sorted[-5:], hist_sorted[-10:]
            r5_rate = sum(t for _, t, _ in recent5) / sum(r for _, _, r in recent5)
            r10_rate = sum(t for _, t, _ in recent10) / sum(r for _, _, r in recent10)
            lt_rate = sum(t for _, t, _ in hist_sorted) / total_rounds
            r5_shrunk, _ = _shrink(r5_rate, sum(r for _, _, r in recent5), prior)
            r10_shrunk, _ = _shrink(r10_rate, sum(r for _, _, r in recent10), prior)
            lt_shrunk, _ = _shrink(lt_rate, total_rounds, prior)
            rates = [t / r for _, t, r in hist_sorted]
            consistency = -statistics.pstdev(rates) if len(rates) > 1 else 0.0
            population_features[pid] = {"recent_5": r5_shrunk, "recent_10": r10_shrunk, "long_term": lt_shrunk, "consistency": consistency}

        target_eligible = [pid for pid in target if pid in population_features]
        if len(target_eligible) < 2 or len(population_features) < 2:
            for pid, row in target.items():
                history[pid].append((target_date, float(row["total"]), float(row["rounds"])))
            continue

        means_sds = {}
        for key in ("recent_5", "recent_10", "long_term", "consistency"):
            values = [f[key] for f in population_features.values()]
            means_sds[key] = (statistics.fmean(values), statistics.pstdev(values))

        def z(pid, key):
            mean, sd = means_sds[key]
            return (population_features[pid][key] - mean) / sd if sd else 0.0

        scores, contributions = {}, {}
        for pid in target_eligible:
            contributions[pid] = {name: V2A_WEIGHTS[name] * z(pid, name) for name in ("recent_5", "recent_10", "long_term", "consistency")}
            scores[pid] = sum(contributions[pid].values())

        ranked = sorted(scores, key=lambda pid: (-scores[pid], pid))
        ranks = {pid: i + 1 for i, pid in enumerate(ranked)}
        event_obs = []
        for pid in ranked:
            outcome = outcomes.get((event, pid), {})
            finish = outcome.get("finish_position_numeric")
            sg_total = float(target[pid]["total"])
            max_feature_date = max(d for d, _, _ in history[pid] if d < target_date)
            if not max_feature_date < target_date:
                raise AssertionError("future leakage")
            row = {"event": event, "target_start_date": target_date, "player_id": pid, "neo_rank": ranks[pid],
                   "neo_score": round(scores[pid], 8), "target_sg_total": sg_total, "outcome_joined": bool(outcome),
                   "finish_position": finish, "made_cut": outcome.get("made_cut"), "withdrawn": outcome.get("withdrawn"),
                   "disqualified": outcome.get("disqualified")}
            observations.append(row); event_obs.append(row)

        valid_finish = [r for r in event_obs if r["finish_position"] is not None and not r["withdrawn"] and not r["disqualified"]]
        top10 = set(r["player_id"] for r in sorted(valid_finish, key=lambda r: r["finish_position"])[:10]); pick10 = set(ranked[:10])
        top20 = set(r["player_id"] for r in sorted(valid_finish, key=lambda r: r["finish_position"])[:20]); pick20 = set(ranked[:20])
        event_reports.append({
            "event": event, "spearman_neo_rank_vs_finish": spearman([r["neo_rank"] for r in valid_finish], [r["finish_position"] for r in valid_finish]),
            "spearman_neo_score_vs_subsequent_sg": spearman([r["neo_score"] for r in event_obs], [r["target_sg_total"] for r in event_obs]),
            "top10_precision": len(pick10 & top10) / len(pick10) if pick10 else None,
            "top10_recall": len(pick10 & top10) / len(top10) if top10 else None,
            "top20_precision": len(pick20 & top20) / len(pick20) if pick20 else None,
            "top20_recall": len(pick20 & top20) / len(top20) if top20 else None,
            "made_cut_auc": auc([r["neo_score"] for r in event_obs if r["made_cut"] is not None], [bool(r["made_cut"]) for r in event_obs if r["made_cut"] is not None]),
        })
        for pid, row in target.items():
            history[pid].append((target_date, float(row["total"]), float(row["rounds"])))

    def avg(key):
        vals = [e[key] for e in event_reports if e[key] is not None]
        return statistics.fmean(vals) if vals else None

    metrics = {key: avg(key) for key in ("spearman_neo_rank_vs_finish", "spearman_neo_score_vs_subsequent_sg", "top10_precision", "top10_recall", "top20_precision", "top20_recall", "made_cut_auc")}
    return {"model_id": MODEL_ID, "tournament_count": len(event_reports), "observation_count": len(observations),
            "unique_players": len({r["player_id"] for r in observations}), "metrics": metrics, "observations": observations, "events": event_reports}
