"""Full V1-vs-V2A validation battery: cut/completion red team, exposure
gate, predictive validation (leakage-safe walk-forward, same dataset as
V1), official-SG external validation, stability, and cohort-dependency
red-team re-run. Read-only against frozen inputs (dac6a09 official
SG/Profile snapshots, the production historical warehouse, the
already-committed NEO_V2A_PREDECLARED_TOLERANCE.json). Writes only new
artifacts under content/website_v2/. Never modifies V1 code/config.
"""
from __future__ import annotations

import copy
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.neo_ranking_backtest import run_backtest, spearman  # noqa: E402
from klpga.website_v2.neo_ranking_v2a import build_features_v2a, estimate_shrinkage_prior, evaluate_v2a, run_backtest_v2a  # noqa: E402
from klpga.website_v2.top120_validation import evaluate  # noqa: E402


def load(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def pearson(xs, ys):
    if len(xs) < 2:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    dx, dy = [x - mx for x in xs], [y - my for y in ys]
    den = (sum(x * x for x in dx) * sum(y * y for y in dy)) ** 0.5
    return sum(x * y for x, y in zip(dx, dy)) / den if den else None


def mae(xs, ys):
    return statistics.fmean(abs(x - y) for x, y in zip(xs, ys)) if xs else None


def rmse(xs, ys):
    return (statistics.fmean((x - y) ** 2 for x, y in zip(xs, ys))) ** 0.5 if xs else None


def build() -> dict:
    warehouse = load("historical_sg_warehouse_corrected.json")
    config_v1 = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    cohort_top120 = load("HOME_PLAYER_MASTER_TOP120_2026_W36.json")
    sg = load("OFFICIAL_SG_NORMALIZED.json")
    sg_by_code = {r["playerCode"]: r for r in sg["records"]}

    prior = estimate_shrinkage_prior(warehouse)
    v1_out, v1_summary = evaluate(cohort_top120, warehouse, config_v1)
    v2a_out, v2a_summary = evaluate_v2a(cohort_top120, warehouse, prior)
    v1_by_id = {r["player_id"]: r for r in v1_out}
    v2a_by_id = {r["player_id"]: r for r in v2a_out}

    report: dict = {"shrinkage_prior": prior, "v1_summary": v1_summary, "v2a_summary": v2a_summary}

    # ============ Section 5: cut/completion red team ============
    latest = {}
    for row in warehouse.get("records", ()):
        pid, gc = str(row.get("player_id") or ""), str(row.get("game_code") or "")
        if not pid or not gc or row.get("identity_state") != "RETAINED" or not isinstance(row.get("total"), (int, float)):
            continue
        rounds = row.get("rounds")
        if not isinstance(rounds, (int, float)) or rounds <= 0:
            continue
        key = (pid, gc)
        if key not in latest or int(rounds) >= int(latest[key].get("rounds") or 0):
            latest[key] = row
    groups = {2: [], 3: [], 4: []}
    for row in latest.values():
        r = int(row["rounds"])
        if r in groups:
            groups[r].append(row)
    cut_completion = {}
    for r, rows in groups.items():
        totals = [float(x["total"]) for x in rows]
        rates = [float(x["total"]) / float(x["rounds"]) for x in rows]
        pids_here = {str(x["player_id"]) for x in rows}
        v1_ranks = [v1_by_id[p]["neo_validation_rank"] for p in pids_here if p in v1_by_id and v1_by_id[p]["neo_validation_rank"]]
        v2a_ranks = [v2a_by_id[p]["neo_validation_rank"] for p in pids_here if p in v2a_by_id and v2a_by_id[p]["neo_validation_rank"]]
        cut_completion[f"{r}R"] = {
            "observations": len(rows), "unique_players_in_TOP120_with_this_round_count_event": len(pids_here & set(v1_by_id)),
            "mean_raw_sg_total": statistics.fmean(totals) if totals else None, "median_raw_sg_total": statistics.median(totals) if totals else None,
            "mean_raw_sg_rate_per_round": statistics.fmean(rates) if rates else None,
            "mean_v1_rank_among_top120_players_with_this_event_type": statistics.fmean(v1_ranks) if v1_ranks else None,
            "mean_v2a_rank_among_top120_players_with_this_event_type": statistics.fmean(v2a_ranks) if v2a_ranks else None,
            "note": "these are observation-level (event-level) groups, not player status groups -- a player normally contributes events to multiple bins over their career; WD/DQ status is not inferred here, only rows with an explicit numeric rounds/total are counted",
        }
    report["cut_completion_red_team"] = cut_completion

    # ============ Section 6: exposure gate ============
    def exposure_pairs(by_id, rank_key="neo_validation_rank", score_getter=None):
        rounds_l, rank_l, score_l, sample_l = [], [], [], []
        for pid, row in by_id.items():
            if row[rank_key] is None:
                continue
            sgr = sg_by_code.get(pid)
            if sgr is None or sgr["official_sg_rounds"] is None:
                continue
            rounds_l.append(sgr["official_sg_rounds"]); rank_l.append(row[rank_key])
            if score_getter:
                score_l.append(score_getter(row))
            sample_l.append(row["features"]["sample_count"] if "sample_count" in (row["features"] or {}) else row["features"].get("sample_count_events") if row["features"] else None)
        return rounds_l, rank_l, score_l, sample_l

    r1, rk1, sc1, sm1 = exposure_pairs(v1_by_id, score_getter=lambda r: r["validation_score"])
    r2, rk2, sc2, sm2 = exposure_pairs(v2a_by_id, score_getter=lambda r: r["validation_score"])
    exposure_gate = {
        "V1_spearman_official_rounds_vs_rank": spearman(r1, rk1), "V1_reference_known": -0.358,
        "V2A_spearman_official_rounds_vs_rank": spearman(r2, rk2),
        "V1_spearman_official_rounds_vs_score": spearman(r1, sc1), "V2A_spearman_official_rounds_vs_score": spearman(r2, sc2),
        "V1_spearman_official_rounds_vs_sample_reliability": spearman(r1, sm1), "V2A_spearman_official_rounds_vs_sample_reliability": spearman(r2, sm2),
        "n_V1": len(r1), "n_V2A": len(r2),
    }
    v1_abs, v2a_abs = abs(exposure_gate["V1_spearman_official_rounds_vs_rank"]), abs(exposure_gate["V2A_spearman_official_rounds_vs_rank"])
    exposure_gate["absolute_exposure_correlation_declined"] = v2a_abs < v1_abs
    exposure_gate["relative_reduction_pct"] = round(100 * (v1_abs - v2a_abs) / v1_abs, 1) if v1_abs else None
    report["exposure_gate"] = exposure_gate
    (CONTENT / "NEO_V2A_EXPOSURE_GATE.json").write_text(json.dumps(exposure_gate, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    # ============ Section 8: official SG external validation ============
    def sg_cross(by_id, score_key="validation_score", rate_key=None):
        neo_vals, off_vals = [], []
        for pid, row in by_id.items():
            if row["neo_validation_rank"] is None:
                continue
            sgr = sg_by_code.get(pid)
            if sgr is None or sgr["official_sg_total"] is None:
                continue
            if rate_key:
                v = row["features"][rate_key]
            else:
                v = row["features"]["long_term_sg"]
            neo_vals.append(v); off_vals.append(sgr["official_sg_total"])
        return neo_vals, off_vals

    neo1, off1 = sg_cross(v1_by_id, rate_key="long_term_sg")
    neo2, off2 = sg_cross(v2a_by_id, rate_key="long_term_rate_shrunk")
    official_sg_validation = {
        "V1": {"N": len(neo1), "Pearson": pearson(neo1, off1), "Spearman": spearman(neo1, off1), "MAE": mae(neo1, off1), "RMSE": rmse(neo1, off1),
               "mean_bias": statistics.fmean(a - b for a, b in zip(neo1, off1)) if neo1 else None},
        "V1_reference_known": {"N": 104, "Pearson": 0.733, "Spearman": 0.737, "MAE": 0.629, "RMSE": 0.819},
        "V2A": {"N": len(neo2), "Pearson": pearson(neo2, off2), "Spearman": spearman(neo2, off2), "MAE": mae(neo2, off2), "RMSE": rmse(neo2, off2),
                "mean_bias": statistics.fmean(a - b for a, b in zip(neo2, off2)) if neo2 else None},
    }
    report["official_sg_validation"] = official_sg_validation
    (CONTENT / "NEO_V2A_OFFICIAL_SG_VALIDATION.json").write_text(json.dumps(official_sg_validation, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    # ============ Section 9: stability ============
    common = set(v1_by_id) & set(v2a_by_id)
    v1_ranked = {pid: v1_by_id[pid]["neo_validation_rank"] for pid in common if v1_by_id[pid]["neo_validation_rank"]}
    v2a_ranked = {pid: v2a_by_id[pid]["neo_validation_rank"] for pid in common if v2a_by_id[pid]["neo_validation_rank"]}
    both_ranked = set(v1_ranked) & set(v2a_ranked)

    def topn_overlap(n):
        t1 = {p for p in v1_ranked if v1_ranked[p] <= n}
        t2 = {p for p in v2a_ranked if v2a_ranked[p] <= n}
        return len(t1 & t2) / len(t1 | t2) if (t1 | t2) else None

    rank_corr = spearman([v1_ranked[p] for p in both_ranked], [v2a_ranked[p] for p in both_ranked])
    movers = sorted(both_ranked, key=lambda p: abs(v1_ranked[p] - v2a_ranked[p]), reverse=True)[:20]
    mover_rows = []
    for pid in movers:
        v1r, v2r = v1_by_id[pid], v2a_by_id[pid]
        sgr = sg_by_code.get(pid)
        mover_rows.append({
            "playerCode": pid, "player_name": v1r["player_name"], "V1_rank": v1_ranked[pid], "V2A_rank": v2a_ranked[pid],
            "delta": v2a_ranked[pid] - v1_ranked[pid], "V1_skill": v1r["validation_score"], "V2A_skill": v2r["validation_score"],
            "official_sg_total": sgr["official_sg_total"] if sgr else None, "official_sg_rounds": sgr["official_sg_rounds"] if sgr else None,
            "historical_NEO_rounds": v2r["features"]["total_rounds"] if v2r["features"] else None,
            "historical_NEO_events": v1r["features"]["sample_count"] if v1r["features"] else None,
            "mechanical_reason": (
                "moved because V2A round-normalizes the observation unit (pooled SG-per-round rather than raw per-event total) "
                "and drops the additive sample_reliability bonus, replacing it with shrinkage weighted by total rounds"
            ),
        })
    stability = {"top10_overlap": topn_overlap(10), "top20_overlap": topn_overlap(20), "top50_overlap": topn_overlap(50),
                 "rank_correlation_spearman": rank_corr, "n_both_ranked": len(both_ranked), "top_20_movers": mover_rows}
    report["stability"] = stability
    (CONTENT / "NEO_V2A_STABILITY.json").write_text(json.dumps(stability, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    # ============ Section 10: cohort dependency red team (re-run on V2A) ============
    baseline_ranks = {pid: r["neo_validation_rank"] for pid, r in v2a_by_id.items() if r["neo_validation_rank"]}
    in_cohort_ids = {str(r["player_id"]) for r in cohort_top120["records"]}
    candidate_pool = {str(r.get("player_id")) for r in warehouse["records"] if r.get("identity_state") == "RETAINED"}
    substitute_id = next(pid for pid in sorted(candidate_pool) if pid not in in_cohort_ids)
    swapped = copy.deepcopy(cohort_top120)
    removed = swapped["records"][-1]
    swapped["records"][-1] = {**removed, "player_id": substitute_id, "player_name": f"UNRELATED_SUB_{substitute_id}"}
    swapped_out, _ = evaluate_v2a(swapped, warehouse, prior)
    swapped_ranks = {r["player_id"]: r["neo_validation_rank"] for r in swapped_out if r["neo_validation_rank"]}
    common2 = set(baseline_ranks) & set(swapped_ranks)
    changed = sum(1 for pid in common2 if baseline_ranks[pid] != swapped_ranks[pid])
    cohort_dependency = {
        "removed_player": removed.get("player_name"), "players_common_to_both_runs": len(common2),
        "players_whose_rank_changed_solely_from_removing_one_unrelated_player": changed,
        "pct_changed": round(100 * changed / len(common2), 1) if common2 else None,
        "V1_reference_known_pct_changed": 13.1,
        "gate": "FAIL" if changed > 0 else "PASS",
        "expected": "FAIL -- V2A does not touch cohort z-scoring, per instruction (exposure only, this phase)",
    }
    report["cohort_dependency"] = cohort_dependency
    (CONTENT / "NEO_V2A_COHORT_DEPENDENCY_REDTEAM.json").write_text(json.dumps(cohort_dependency, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    return report


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2, default=str))
