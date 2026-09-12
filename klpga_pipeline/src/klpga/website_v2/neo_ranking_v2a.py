"""NEO_RANKING_V2A_EXPOSURE_NEUTRAL -- an experimental candidate that
changes ONLY the observation unit and reliability treatment of frozen
V1, to test whether exposure bias (Spearman(official_sg_rounds,
NEO_rank) = -0.358 in V1) can be materially reduced while preserving
predictive skill. Cohort z-scoring is DELIBERATELY left unchanged
(cohort-independence is a separate, later phase -- V2B).

WHY THIS CHANGES ANYTHING (proven from the real warehouse, not
assumed): V1's home_ranking.build_features()/neo_ranking_backtest.
_latest_records() consume one scalar `total` per (player, game_code)
-- an ALREADY-AGGREGATED event total, never divided by that event's
own `rounds` (1-4). 43.6% of the 11,144 real consumed observations are
single-round-only totals, averaged identically alongside full 4-round
totals inside recent5/recent10/long_term_sg's plain arithmetic mean.

V2A's fix: use the ROUND-WEIGHTED pooled rate
    pooled_rate(events) = sum(total over events) / sum(rounds over events)
over the same recency windows (latest 5/10/all-prior events, same
recency definition as V1 -- only the WITHIN-window aggregation
changes), then apply empirical-Bayes shrinkage toward the population
mean, weighted by that window's own total rounds (not event count).
Sample size affects shrinkage weight (confidence) only -- it is never
added to the skill score itself, unlike V1's `sample_reliability`
feature (weight 0.05, added directly into the composite).

Shrinkage formula (classic empirical-Bayes, one prior fit once from
this worktree's own frozen warehouse -- a GLOBAL, not per-walk-forward-
fold, hyperparameter; this is disclosed as a modeling choice, not
hidden):
    shrunk = w * pooled_rate + (1 - w) * population_mean
    w = tau^2 / (tau^2 + sigma^2 / n_rounds)
  sigma^2 (within-player, round-level noise): mean over events with
    rounds>=1 of rounds * (event_rate - player's own pooled rate)^2,
    weighted by rounds, restricted to players with >=3 RETAINED events.
  tau^2 (between-player, true-skill spread): Var(player pooled rates)
    minus the mean per-player sigma^2/n_rounds correction (method of
    moments), floored at 0.
  population_mean: rounds-weighted mean of all event rates.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict

MODEL_ID = "neo-ranking-v2a-exposure-neutral"


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


def estimate_shrinkage_prior(warehouse: dict) -> dict:
    """Method-of-moments fit, run ONCE against the full frozen
    warehouse (a global hyperparameter, documented as such -- not
    refit per walk-forward fold in V2A; see module docstring)."""
    grouped = _latest_records(warehouse)

    all_events = []  # (rounds, rate) across every player/event
    player_pooled = {}  # pid -> (pooled_rate, total_rounds, n_events)
    for pid, rows in grouped.items():
        rounds_list = [float(r["rounds"]) for r in rows]
        rates = [float(r["total"]) / float(r["rounds"]) for r in rows]
        total_rounds = sum(rounds_list)
        pooled_rate = sum(float(r["total"]) for r in rows) / total_rounds
        player_pooled[pid] = (pooled_rate, total_rounds, len(rows))
        for rnd, rate in zip(rounds_list, rates):
            all_events.append((rnd, rate))

    total_rounds_all = sum(r for r, _ in all_events)
    population_mean = sum(r * v for r, v in all_events) / total_rounds_all

    # sigma^2: rounds-weighted mean squared deviation of each event's own
    # rate from ITS PLAYER's pooled rate, restricted to players with >=3
    # events (stability) -- this estimates the per-round noise variance.
    sigma_num, sigma_den = 0.0, 0.0
    for pid, rows in grouped.items():
        if len(rows) < 3:
            continue
        pooled_rate, _, _ = player_pooled[pid]
        for r in rows:
            rnd = float(r["rounds"])
            rate = float(r["total"]) / rnd
            sigma_num += rnd * (rate - pooled_rate) ** 2
            sigma_den += rnd
    sigma2 = sigma_num / sigma_den if sigma_den else 0.0

    # tau^2: between-player variance of pooled rates, minus the average
    # per-player sampling-noise correction (method of moments), floored at 0.
    stable_players = [p for p, (_, _, n) in player_pooled.items() if n >= 3]
    pooled_rates = [player_pooled[p][0] for p in stable_players]
    if len(pooled_rates) >= 2:
        var_pooled = statistics.pvariance(pooled_rates)
        mean_correction = statistics.fmean(sigma2 / player_pooled[p][1] for p in stable_players)
        tau2 = max(0.0, var_pooled - mean_correction)
    else:
        tau2 = 0.0

    return {"sigma2": sigma2, "tau2": tau2, "population_mean": population_mean, "fit_player_count": len(stable_players)}


def _shrink(pooled_rate: float, total_rounds: float, prior: dict) -> tuple[float, float]:
    tau2, sigma2, mean = prior["tau2"], prior["sigma2"], prior["population_mean"]
    if total_rounds <= 0:
        return mean, 0.0
    denom = tau2 + sigma2 / total_rounds
    w = tau2 / denom if denom > 0 else 0.0
    return w * pooled_rate + (1 - w) * mean, w


def _pooled_rate(rows: list[dict]) -> tuple[float, float]:
    total_sg = sum(float(r["total"]) for r in rows)
    total_rounds = sum(float(r["rounds"]) for r in rows)
    return (total_sg / total_rounds if total_rounds else 0.0), total_rounds


def build_features_v2a(warehouse: dict, prior: dict, *, minimum_rounds: int = 20) -> dict[str, dict]:
    """Player-level V2A features, mirroring home_ranking.build_features()'s
    shape but round-normalized + shrunk. Eligibility is by TOTAL ROUNDS
    (>=20, roughly 5 four-round events -- matching the exposure-neutral
    design goal), not event count -- a disclosed formula change from V1's
    event-count floor, not a hidden one."""
    grouped = _latest_records(warehouse)
    result = {}
    for pid, rows in grouped.items():
        rows_sorted = sorted(rows, key=lambda r: (int(r.get("season") or 0), str(r.get("game_code") or "")))
        recent5_rows, recent10_rows = rows_sorted[-5:], rows_sorted[-10:]

        r5_rate, r5_rounds = _pooled_rate(recent5_rows)
        r10_rate, r10_rounds = _pooled_rate(recent10_rows)
        lt_rate, lt_rounds = _pooled_rate(rows_sorted)

        r5_shrunk, r5_w = _shrink(r5_rate, r5_rounds, prior)
        r10_shrunk, r10_w = _shrink(r10_rate, r10_rounds, prior)
        lt_shrunk, lt_w = _shrink(lt_rate, lt_rounds, prior)

        event_rates = [float(r["total"]) / float(r["rounds"]) for r in rows_sorted]
        consistency = -statistics.pstdev(event_rates) if len(event_rates) > 1 else 0.0

        result[pid] = {
            "recent_5_rate_shrunk": r5_shrunk, "recent_10_rate_shrunk": r10_shrunk, "long_term_rate_shrunk": lt_shrunk,
            "consistency": consistency, "total_rounds": lt_rounds, "sample_count_events": len(rows_sorted),
            "reliability_weight": lt_w,  # CONFIDENCE metadata only -- never added into the score.
            "eligibility": "FEATURES_READY" if lt_rounds >= minimum_rounds else "INSUFFICIENT_SAMPLE",
        }
    return result


def _z(values: dict[str, float]) -> dict[str, float]:
    mean = statistics.fmean(values.values())
    sd = statistics.pstdev(values.values())
    return {k: (v - mean) / sd if sd else 0.0 for k, v in values.items()}


# Weights renormalized from V1's 0.35/0.25/0.25/0.10 (dropping the 0.05
# additive sample_reliability term entirely, per "do not reward sample
# count inside the skill estimate") so the remaining four sum to 1.0.
V2A_WEIGHTS = {"recent_5": 0.35 / 0.95, "recent_10": 0.25 / 0.95, "long_term": 0.25 / 0.95, "consistency": 0.10 / 0.95}


def evaluate_v2a(cohort: dict, warehouse: dict, prior: dict, *, minimum_rounds: int = 20) -> tuple[list[dict], dict]:
    """Same output shape as klpga.website_v2.top120_validation.evaluate()
    (rank/score/contributions per TOP120 row) so the exact same
    downstream cross-validation/stability code can consume either."""
    rows = list(cohort.get("records", ()))
    features = build_features_v2a(warehouse, prior, minimum_rounds=minimum_rounds)
    eligible_ids = [str(row["player_id"]) for row in rows if features.get(str(row["player_id"]), {}).get("total_rounds", 0) >= minimum_rounds]

    components = {}
    for name, key in (("recent_5", "recent_5_rate_shrunk"), ("recent_10", "recent_10_rate_shrunk"), ("long_term", "long_term_rate_shrunk")):
        components[name] = _z({pid: features[pid][key] for pid in eligible_ids}) if eligible_ids else {}
    components["consistency"] = _z({pid: features[pid]["consistency"] for pid in eligible_ids}) if eligible_ids else {}

    scores, contributions = {}, {}
    for pid in eligible_ids:
        contributions[pid] = {name: V2A_WEIGHTS[name] * components[name][pid] for name in components}
        scores[pid] = sum(contributions[pid].values())
    ordered = sorted(scores, key=lambda pid: (-scores[pid], pid))
    neo_rank = {pid: rank for rank, pid in enumerate(ordered, 1)}

    output = []
    for row in rows:
        pid = str(row["player_id"])
        feature = features.get(pid)
        rank = neo_rank.get(pid)
        output.append({**row, "features": feature, "sg_join_state": "PASS" if feature else "DATA_INSUFFICIENT",
                       "neo_validation_rank": rank, "validation_score": round(scores[pid], 6) if rank else None,
                       "feature_contributions": ({k: round(v, 6) for k, v in contributions[pid].items()} if rank else None),
                       "neo_ranking_state": "VALIDATION_MODEL" if rank else "VALIDATION_PENDING",
                       "rank_delta": int(row["official_k_rank"]) - rank if rank else None,
                       "reliability_weight": feature["reliability_weight"] if feature else None,
                       "model_id": MODEL_ID})
    summary = {"cohort_count": len(rows), "neo_ranked": len(eligible_ids), "validation_pending": len(rows) - len(eligible_ids)}
    return output, summary


def run_backtest_v2a(warehouse: dict, start_dates: dict[str, str], outcomes: dict, prior: dict, *, minimum_rounds: int = 20) -> dict:
    """Leakage-safe walk-forward backtest, same event-ordering/target
    structure as klpga.website_v2.neo_ranking_backtest.run_backtest(),
    so V1 and V2A can be scored on EXACTLY the same observations. Every
    feature is built only from events whose start date is strictly
    before the target event's start date -- same hard assertion as V1."""
    from klpga.website_v2.neo_ranking_backtest import spearman, auc  # noqa: E402 (reuse, not reimplement)

    events: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in warehouse.get("records", ()):
        pid, event = str(row.get("player_id") or ""), str(row.get("game_code") or "")
        if not pid or event not in start_dates or row.get("identity_state") != "RETAINED" or not isinstance(row.get("total"), (int, float)):
            continue
        rounds = row.get("rounds")
        if not isinstance(rounds, (int, float)) or rounds <= 0:
            continue
        old = events[event].get(pid)
        if old is None or int(rounds) >= int(old.get("rounds") or 0):
            events[event][pid] = row

    ordered = sorted(events, key=lambda event: (start_dates[event], event))
    history: dict[str, list[tuple[str, float, float]]] = defaultdict(list)  # pid -> [(date, total, rounds)]
    observations, event_reports = [], []

    for event in ordered:
        target_date, target = start_dates[event], events[event]
        eligible_hist = {pid: [(d, t, r) for d, t, r in history[pid] if d < target_date] for pid in target}
        eligible_hist = {pid: h for pid, h in eligible_hist.items() if sum(r for _, _, r in h) >= minimum_rounds}
        if len(eligible_hist) < 2:
            for pid, row in target.items():
                history[pid].append((target_date, float(row["total"]), float(row["rounds"])))
            continue

        raw_rates, raw_rounds, raw_consistency = {}, {}, {}
        for pid, hist in eligible_hist.items():
            recent5, recent10 = hist[-5:], hist[-10:]
            r5_rate, r5_rounds = (sum(t for _, t, _ in recent5) / sum(r for _, _, r in recent5)), sum(r for _, _, r in recent5)
            r10_rate, r10_rounds = (sum(t for _, t, _ in recent10) / sum(r for _, _, r in recent10)), sum(r for _, _, r in recent10)
            lt_rate, lt_rounds = (sum(t for _, t, _ in hist) / sum(r for _, _, r in hist)), sum(r for _, _, r in hist)
            r5_shrunk, _ = _shrink(r5_rate, r5_rounds, prior)
            r10_shrunk, _ = _shrink(r10_rate, r10_rounds, prior)
            lt_shrunk, lt_w = _shrink(lt_rate, lt_rounds, prior)
            event_rates = [t / r for _, t, r in hist]
            raw_rates[pid] = {"recent_5": r5_shrunk, "recent_10": r10_shrunk, "long_term": lt_shrunk}
            raw_consistency[pid] = -statistics.pstdev(event_rates) if len(event_rates) > 1 else 0.0
            raw_rounds[pid] = lt_w

        z = {name: _z({pid: raw_rates[pid][name] for pid in eligible_hist}) for name in ("recent_5", "recent_10", "long_term")}
        z["consistency"] = _z(raw_consistency)
        scores, contributions = {}, {}
        for pid in eligible_hist:
            contributions[pid] = {name: V2A_WEIGHTS[name] * z[name][pid] for name in z}
            scores[pid] = sum(contributions[pid].values())

        ranked = sorted(scores, key=lambda pid: (-scores[pid], pid))
        ranks = {pid: i + 1 for i, pid in enumerate(ranked)}
        event_obs = []
        for pid in ranked:
            outcome = outcomes.get((event, pid), {})
            finish = outcome.get("finish_position_numeric")
            sg_total = float(target[pid]["total"])
            max_feature_date = max(d for d, _, _ in eligible_hist[pid])
            if not max_feature_date < target_date:
                raise AssertionError("future leakage")
            row = {"event": event, "target_start_date": target_date, "player_id": pid, "neo_rank": ranks[pid],
                   "neo_score": round(scores[pid], 8), "prior_rounds": sum(r for _, _, r in eligible_hist[pid]),
                   "target_sg_total": sg_total, "outcome_joined": bool(outcome), "finish_position": finish,
                   "made_cut": outcome.get("made_cut"), "withdrawn": outcome.get("withdrawn"), "disqualified": outcome.get("disqualified")}
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
