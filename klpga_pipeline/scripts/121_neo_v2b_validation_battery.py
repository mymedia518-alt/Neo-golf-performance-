"""V1 vs V2A vs V2B validation battery: exposure gate, official-SG
external validation, stability, and cohort-dependency red-team
(measuring BOTH the underlying score and the display-list rank label,
since V2B's fix targets the score). Mirrors scripts/119 exactly for
consistency but adds V2B and the score-vs-rank distinction.
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

from klpga.website_v2.neo_ranking_backtest import spearman  # noqa: E402
from klpga.website_v2.neo_ranking_v2a import estimate_shrinkage_prior, evaluate_v2a  # noqa: E402
from klpga.website_v2.neo_ranking_v2b import evaluate_v2b  # noqa: E402
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
    v2b_out, v2b_summary = evaluate_v2b(cohort_top120, warehouse, prior)
    v1_by_id = {r["player_id"]: r for r in v1_out}
    v2a_by_id = {r["player_id"]: r for r in v2a_out}
    v2b_by_id = {r["player_id"]: r for r in v2b_out}

    report: dict = {"v1_summary": v1_summary, "v2a_summary": v2a_summary, "v2b_summary": v2b_summary}

    # exposure gate
    def exposure_pairs(by_id):
        rounds_l, rank_l, score_l = [], [], []
        for pid, row in by_id.items():
            if row["neo_validation_rank"] is None:
                continue
            sgr = sg_by_code.get(pid)
            if sgr is None or sgr["official_sg_rounds"] is None:
                continue
            rounds_l.append(sgr["official_sg_rounds"]); rank_l.append(row["neo_validation_rank"]); score_l.append(row["validation_score"])
        return rounds_l, rank_l, score_l

    r1, rk1, sc1 = exposure_pairs(v1_by_id)
    r2, rk2, sc2 = exposure_pairs(v2a_by_id)
    r3, rk3, sc3 = exposure_pairs(v2b_by_id)
    exposure_gate = {
        "V1_spearman_rounds_vs_rank": spearman(r1, rk1), "V2A_spearman_rounds_vs_rank": spearman(r2, rk2), "V2B_spearman_rounds_vs_rank": spearman(r3, rk3),
        "n": {"V1": len(r1), "V2A": len(r2), "V2B": len(r3)},
    }
    report["exposure_gate"] = exposure_gate
    (CONTENT / "NEO_V2B_EXPOSURE_GATE.json").write_text(json.dumps(exposure_gate, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    # official SG external validation
    def sg_cross(by_id, rate_key):
        neo_vals, off_vals = [], []
        for pid, row in by_id.items():
            if row["neo_validation_rank"] is None:
                continue
            sgr = sg_by_code.get(pid)
            if sgr is None or sgr["official_sg_total"] is None:
                continue
            neo_vals.append(row["features"][rate_key]); off_vals.append(sgr["official_sg_total"])
        return neo_vals, off_vals

    neo1, off1 = sg_cross(v1_by_id, "long_term_sg")
    neo2, off2 = sg_cross(v2a_by_id, "long_term_rate_shrunk")
    neo3, off3 = sg_cross(v2b_by_id, "long_term")
    official_sg_validation = {
        "V1": {"N": len(neo1), "Pearson": pearson(neo1, off1), "Spearman": spearman(neo1, off1), "MAE": mae(neo1, off1), "RMSE": rmse(neo1, off1)},
        "V2A": {"N": len(neo2), "Pearson": pearson(neo2, off2), "Spearman": spearman(neo2, off2), "MAE": mae(neo2, off2), "RMSE": rmse(neo2, off2)},
        "V2B": {"N": len(neo3), "Pearson": pearson(neo3, off3), "Spearman": spearman(neo3, off3), "MAE": mae(neo3, off3), "RMSE": rmse(neo3, off3)},
    }
    report["official_sg_validation"] = official_sg_validation
    (CONTENT / "NEO_V2B_OFFICIAL_SG_VALIDATION.json").write_text(json.dumps(official_sg_validation, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    # stability V1 vs V2B
    common = set(v1_by_id) & set(v2b_by_id)
    v1_ranked = {pid: v1_by_id[pid]["neo_validation_rank"] for pid in common if v1_by_id[pid]["neo_validation_rank"]}
    v2b_ranked = {pid: v2b_by_id[pid]["neo_validation_rank"] for pid in common if v2b_by_id[pid]["neo_validation_rank"]}
    both_ranked = set(v1_ranked) & set(v2b_ranked)

    def topn_overlap(n):
        t1 = {p for p in v1_ranked if v1_ranked[p] <= n}
        t2 = {p for p in v2b_ranked if v2b_ranked[p] <= n}
        return len(t1 & t2) / len(t1 | t2) if (t1 | t2) else None

    rank_corr = spearman([v1_ranked[p] for p in both_ranked], [v2b_ranked[p] for p in both_ranked])
    movers = sorted(both_ranked, key=lambda p: abs(v1_ranked[p] - v2b_ranked[p]), reverse=True)[:20]
    mover_rows = []
    for pid in movers:
        v1r, v2r = v1_by_id[pid], v2b_by_id[pid]
        sgr = sg_by_code.get(pid)
        mover_rows.append({"playerCode": pid, "player_name": v1r["player_name"], "V1_rank": v1_ranked[pid], "V2B_rank": v2b_ranked[pid],
                            "delta": v2b_ranked[pid] - v1_ranked[pid], "V1_skill": v1r["validation_score"], "V2B_skill": v2r["validation_score"],
                            "official_sg_total": sgr["official_sg_total"] if sgr else None, "official_sg_rounds": sgr["official_sg_rounds"] if sgr else None,
                            "historical_NEO_rounds": v2r["features"]["total_rounds"] if v2r["features"] else None,
                            "mechanical_reason": "round-normalized pooled-rate + shrinkage observation unit AND population-frozen (not cohort-relative) z-score, replacing V1's raw-event-total cohort z-score"})
    stability = {"top10_overlap": topn_overlap(10), "top20_overlap": topn_overlap(20), "top50_overlap": topn_overlap(50),
                 "rank_correlation_spearman": rank_corr, "n_both_ranked": len(both_ranked), "top_20_movers": mover_rows}
    report["stability"] = stability
    (CONTENT / "NEO_V2B_STABILITY.json").write_text(json.dumps(stability, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    # cohort dependency red team -- SCORE (substantive) vs RANK LABEL (list-position artifact)
    def cohort_redteam(evaluate_fn):
        baseline_out, _ = evaluate_fn(cohort_top120, warehouse, prior)
        baseline_scores = {r["player_id"]: r["validation_score"] for r in baseline_out if r["neo_validation_rank"]}
        baseline_ranks = {r["player_id"]: r["neo_validation_rank"] for r in baseline_out if r["neo_validation_rank"]}
        in_cohort_ids = {str(r["player_id"]) for r in cohort_top120["records"]}
        candidate_pool = {str(r.get("player_id")) for r in warehouse["records"] if r.get("identity_state") == "RETAINED"}
        substitute_id = next(pid for pid in sorted(candidate_pool) if pid not in in_cohort_ids)
        swapped = copy.deepcopy(cohort_top120)
        swapped["records"][-1] = {**swapped["records"][-1], "player_id": substitute_id, "player_name": f"UNRELATED_SUB_{substitute_id}"}
        swapped_out, _ = evaluate_fn(swapped, warehouse, prior)
        swapped_scores = {r["player_id"]: r["validation_score"] for r in swapped_out if r["neo_validation_rank"]}
        swapped_ranks = {r["player_id"]: r["neo_validation_rank"] for r in swapped_out if r["neo_validation_rank"]}
        common2 = set(baseline_scores) & set(swapped_scores)
        score_changed = sum(1 for pid in common2 if abs(baseline_scores[pid] - swapped_scores[pid]) > 1e-9)
        rank_changed = sum(1 for pid in common2 if baseline_ranks[pid] != swapped_ranks[pid])
        return {"n": len(common2), "score_changed": score_changed, "rank_label_changed": rank_changed,
                "score_changed_pct": round(100 * score_changed / len(common2), 2) if common2 else None,
                "rank_label_changed_pct": round(100 * rank_changed / len(common2), 2) if common2 else None}

    def _v1_wrapper(cohort, warehouse, _prior):
        return evaluate(cohort, warehouse, config_v1)

    cohort_dependency = {
        "V1": cohort_redteam(_v1_wrapper),
        "V2A": cohort_redteam(evaluate_v2a),
        "V2B": cohort_redteam(evaluate_v2b),
        "note": "SCORE change is the substantive test (does a player's own assessed skill move when an unrelated player is swapped?); RANK_LABEL change is an unavoidable list-position artifact of re-sorting a finite displayed set whenever its membership changes, even when every score is invariant.",
        "V2B_gate": "PASS" if 0 == 0 else "FAIL",  # filled precisely below
    }
    cohort_dependency["V2B_gate"] = "PASS" if cohort_dependency["V2B"]["score_changed"] == 0 else "FAIL"
    cohort_dependency["V2A_gate"] = "FAIL" if cohort_dependency["V2A"]["score_changed"] > 0 else "PASS"
    cohort_dependency["V1_gate"] = "FAIL" if cohort_dependency["V1"]["score_changed"] > 0 else "PASS"
    report["cohort_dependency"] = cohort_dependency
    (CONTENT / "NEO_V2B_COHORT_DEPENDENCY_REDTEAM.json").write_text(json.dumps(cohort_dependency, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    return report


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2, default=str))
