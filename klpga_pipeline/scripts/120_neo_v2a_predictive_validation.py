"""V1 vs V2A predictive validation on the SAME leakage-safe walk-forward
dataset (reconstructed from NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json, same
method used for the 2026-09-12 NEO Ranking Publication Validation
report -- no live DB/network needed). Tolerance was pre-declared in
NEO_V2A_PREDECLARED_TOLERANCE.json BEFORE this script was ever run.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.neo_ranking_backtest import run_backtest, spearman  # noqa: E402
from klpga.website_v2.neo_ranking_v2a import estimate_shrinkage_prior, run_backtest_v2a  # noqa: E402


def load(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def build() -> dict:
    warehouse = load("historical_sg_warehouse_corrected.json")
    truth = load("NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json")
    config_v1 = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    tolerance = load("NEO_V2A_PREDECLARED_TOLERANCE.json")
    prior = estimate_shrinkage_prior(warehouse)

    start_dates, outcomes = {}, {}
    for r in truth["records"]:
        gc = str(r["game_code"])
        start_dates[gc] = r["tournament_start_date"]
        outcomes[(gc, str(r["player_id"]))] = {
            "finish_position_numeric": r["outcome"]["finish_position"], "made_cut": r["outcome"]["made_cut"],
            "withdrawn": r["outcome"]["withdrawn"], "disqualified": r["outcome"]["disqualified"],
        }

    v1 = run_backtest(warehouse, start_dates, outcomes, config_v1)
    v2a = run_backtest_v2a(warehouse, start_dates, outcomes, prior)

    def next_n_spearman(result, horizon):
        by_player = {}
        for row in result["observations"]:
            by_player.setdefault(row["player_id"], []).append(row)
        for pid in by_player:
            by_player[pid].sort(key=lambda r: r["target_start_date"])
        xs, ys = [], []
        for pid, seq in by_player.items():
            for i in range(len(seq)):
                future = seq[i + 1: i + 1 + horizon]
                if len(future) == horizon:
                    xs.append(seq[i]["neo_score"])
                    ys.append(statistics.fmean(f["target_sg_total"] for f in future))
        return spearman(xs, ys), len(xs)

    v1_next3, v1_next3_n = next_n_spearman(v1, 3)
    v1_next5, v1_next5_n = next_n_spearman(v1, 5)
    v2a_next3, v2a_next3_n = next_n_spearman(v2a, 3)
    v2a_next5, v2a_next5_n = next_n_spearman(v2a, 5)

    comparison = {
        "tournament_count": {"V1": v1["tournament_count"], "V2A": v2a["tournament_count"]},
        "observation_count": {"V1": v1["observation_count"], "V2A": v2a["observation_count"]},
        "spearman_neo_rank_vs_finish": {"V1": v1["metrics"]["spearman_neo_rank_vs_finish"], "V2A": v2a["metrics"]["spearman_neo_rank_vs_finish"]},
        "spearman_neo_score_vs_subsequent_sg_next1": {"V1": v1["metrics"]["spearman_neo_score_vs_subsequent_sg"], "V2A": v2a["metrics"]["spearman_neo_score_vs_subsequent_sg"]},
        "spearman_neo_score_vs_subsequent_sg_next3": {"V1": v1_next3, "V2A": v2a_next3, "n": {"V1": v1_next3_n, "V2A": v2a_next3_n}},
        "spearman_neo_score_vs_subsequent_sg_next5": {"V1": v1_next5, "V2A": v2a_next5, "n": {"V1": v1_next5_n, "V2A": v2a_next5_n}},
        "made_cut_auc": {"V1": v1["metrics"]["made_cut_auc"], "V2A": v2a["metrics"]["made_cut_auc"]},
        "top10_precision": {"V1": v1["metrics"]["top10_precision"], "V2A": v2a["metrics"]["top10_precision"]},
        "top20_precision": {"V1": v1["metrics"]["top20_precision"], "V2A": v2a["metrics"]["top20_precision"]},
    }

    core_map = {
        "spearman_neo_rank_vs_finish": comparison["spearman_neo_rank_vs_finish"],
        "spearman_neo_score_vs_subsequent_sg_next1": comparison["spearman_neo_score_vs_subsequent_sg_next1"],
        "spearman_neo_score_vs_subsequent_sg_next3": {"V1": v1_next3, "V2A": v2a_next3},
        "spearman_neo_score_vs_subsequent_sg_next5": {"V1": v1_next5, "V2A": v2a_next5},
        "made_cut_auc": comparison["made_cut_auc"],
    }
    core_decline = tolerance["rule"]["core_metric_max_tolerated_decline"]
    secondary_decline = tolerance["rule"]["secondary_metric_max_tolerated_decline"]
    failures = []
    for name, vals in core_map.items():
        # spearman_neo_rank_vs_finish is signed such that MORE POSITIVE = better agreement with finish rank
        decline = vals["V1"] - vals["V2A"]
        if decline > core_decline:
            failures.append({"metric": name, "V1": vals["V1"], "V2A": vals["V2A"], "decline": decline, "tolerated": core_decline})
    for name in ("top10_precision", "top20_precision"):
        vals = comparison[name]
        decline = vals["V1"] - vals["V2A"]
        if decline > secondary_decline:
            failures.append({"metric": name, "V1": vals["V1"], "V2A": vals["V2A"], "decline": decline, "tolerated": secondary_decline})

    predictive_validation = {
        "predeclared_tolerance": tolerance["rule"], "comparison": comparison,
        "failures_exceeding_predeclared_tolerance": failures,
        "PREDICTIVE_VALIDATION_GATE": "FAIL" if failures else "PASS",
    }
    (CONTENT / "NEO_V2A_PREDICTIVE_VALIDATION.json").write_text(json.dumps(predictive_validation, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return predictive_validation


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2, default=str))
