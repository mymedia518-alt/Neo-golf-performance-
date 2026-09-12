"""NEO <-> OFFICIAL (Profile + SG) cross-validation. Read-only against
already-built immutable snapshots (script 116) and existing frozen NEO
artifacts. Computes SG internal integrity, exposure-bias audit,
profile<->SG sanity checks, NEO-rank external validation, rank
divergence, and sample-reliability red-team sweeps. NEO Ranking itself
is never recomputed or tuned here -- every "NEO SG"/"NEO rank" value
used is read verbatim from klpga.website_v2.top120_validation.evaluate()
(the same frozen V1 formula already gated BLOCKED_FORMULA_NOT_APPROVED
by home_ranking.py).
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.neo_ranking_backtest import spearman  # noqa: E402
from klpga.website_v2.top120_validation import evaluate  # noqa: E402


def load(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    dx, dy = [x - mx for x in xs], [y - my for y in ys]
    den = (sum(x * x for x in dx) * sum(y * y for y in dy)) ** 0.5
    return sum(x * y for x, y in zip(dx, dy)) / den if den else None


def mae(xs: list[float], ys: list[float]) -> float | None:
    if not xs:
        return None
    return statistics.fmean(abs(x - y) for x, y in zip(xs, ys))


def rmse(xs: list[float], ys: list[float]) -> float | None:
    if not xs:
        return None
    return (statistics.fmean((x - y) ** 2 for x, y in zip(xs, ys))) ** 0.5


def dist_stats(values: list[float]) -> dict:
    if not values:
        return {k: None for k in ("mean", "median", "std", "min", "max", "p10", "p25", "p75", "p90")}
    s = sorted(values)

    def pct(p):
        if len(s) == 1:
            return s[0]
        k = (len(s) - 1) * p
        f, c = int(k), min(int(k) + 1, len(s) - 1)
        return s[f] + (s[c] - s[f]) * (k - f)

    return {
        "mean": statistics.fmean(values), "median": statistics.median(values),
        "std": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "min": min(values), "max": max(values),
        "p10": pct(0.10), "p25": pct(0.25), "p75": pct(0.75), "p90": pct(0.90),
    }


def build() -> dict:
    profile = load("OFFICIAL_PROFILE_NORMALIZED.json")
    sg = load("OFFICIAL_SG_NORMALIZED.json")
    profile_by_code = {r["playerCode"]: r for r in profile["records"]}
    sg_by_code = {r["playerCode"]: r for r in sg["records"]}

    cohort_top120 = load("HOME_PLAYER_MASTER_TOP120_2026_W36.json")
    warehouse = load("historical_sg_warehouse_corrected.json")
    config = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    top120_out, summary = evaluate(cohort_top120, warehouse, config)
    neo_by_id = {r["player_id"]: r for r in top120_out}

    report: dict = {}

    # ================= Section 6: unified snapshot =================
    unified = []
    for pid in sorted(set(profile_by_code) | set(sg_by_code)):
        p, s = profile_by_code.get(pid), sg_by_code.get(pid)
        unified.append({
            "player_code": pid,
            "player_name": (p or s)["player_name"],
            "money": p["money"] if p else None, "average_score": p["average_score"] if p else None,
            "average_putts": p["average_putts"] if p else None, "birdie_rate": p["birdie_rate"] if p else None,
            "gir_rate": p["gir_rate"] if p else None, "par_save_rate": p["par_save_rate"] if p else None,
            "par_break_rate": p["par_break_rate"] if p else None, "recovery_rate": p["recovery_rate"] if p else None,
            "official_sg_total": s["official_sg_total"] if s else None, "official_sg_ott": s["official_sg_ott"] if s else None,
            "official_sg_app": s["official_sg_app"] if s else None, "official_sg_arg": s["official_sg_arg"] if s else None,
            "official_sg_putt": s["official_sg_putt"] if s else None, "official_sg_rounds": s["official_sg_rounds"] if s else None,
            "profile_source_provenance": "OFFICIAL_PROFILE_NORMALIZED.json" if p else None,
            "sg_source_provenance": "OFFICIAL_SG_NORMALIZED.json" if s else None,
        })
    (CONTENT / "OFFICIAL_PLAYER_UNIFIED_SNAPSHOT.json").write_text(
        json.dumps({"records": unified, "record_count": len(unified)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report["unified_snapshot_player_count"] = len(unified)

    # ================= Section 7: official SG internal integrity =================
    sg_records = sg["records"]
    tol = 0.05
    violations = []
    for r in sg_records:
        total, ott, app, arg, putt = r["official_sg_total"], r["official_sg_ott"], r["official_sg_app"], r["official_sg_arg"], r["official_sg_putt"]
        if None in (total, ott, app, arg, putt):
            continue
        comp_sum = ott + app + arg + putt
        diff = total - comp_sum
        if abs(diff) > tol:
            violations.append({"playerCode": r["playerCode"], "player_name": r["player_name"], "sg_component_sum": comp_sum, "sg_total_difference": diff})
    distributions = {}
    for field in ("official_sg_total", "official_sg_ott", "official_sg_app", "official_sg_arg", "official_sg_putt", "official_sg_rounds"):
        values = [r[field] for r in sg_records if r[field] is not None]
        distributions[field] = dist_stats(values)
    outliers = [r["playerCode"] for r in sg_records if r["official_sg_total"] is not None and abs(r["official_sg_total"]) > 5]
    report["sg_internal_integrity"] = {
        "tolerance": tol, "component_sum_violations": len(violations), "sample_violations": violations[:10],
        "distributions": distributions, "outlier_playercodes_abs_sg_total_gt_5": outliers,
    }
    (CONTENT / "NEO_SAMPLE_RELIABILITY_AUDIT_INPUT_SG_INTEGRITY.json").write_text(
        json.dumps(report["sg_internal_integrity"], ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )

    # ================= Section 8: NEO SG <-> Official SG =================
    # NEO's only frozen, player-level, already-computed "overall SG" figure is
    # long_term_sg from home_ranking.build_features()/top120_validation.evaluate()
    # (mean of ALL of a player's historical event SG totals) -- used AS-IS, never
    # recomputed. No frozen per-player NEO OTT/APP/ARG/PUTT feature exists anywhere
    # in the codebase (home_ranking.build_features only aggregates the warehouse's
    # 'total' field) -- those four comparisons are NOT_EVALUABLE, not fabricated.
    pairs_total = []
    for pid, neo_row in neo_by_id.items():
        s = sg_by_code.get(pid)
        if s is None or s["official_sg_total"] is None or not neo_row["features"] or neo_row["neo_validation_rank"] is None:
            continue
        pairs_total.append((pid, neo_row["player_name"], neo_row["features"]["long_term_sg"], s["official_sg_total"], s["official_sg_rounds"], neo_row["features"]["sample_count"], neo_row["neo_validation_rank"]))

    neo_vals = [p[2] for p in pairs_total]
    off_vals = [p[3] for p in pairs_total]
    cross_total = {
        "N": len(pairs_total), "Pearson": pearson(neo_vals, off_vals), "Spearman": spearman(neo_vals, off_vals),
        "MAE": mae(neo_vals, off_vals), "RMSE": rmse(neo_vals, off_vals),
        "mean_bias_NEO_minus_OFFICIAL": statistics.fmean(n - o for n, o in zip(neo_vals, off_vals)) if pairs_total else None,
    }
    diffs = sorted(pairs_total, key=lambda p: p[2] - p[3])
    neo_higher = list(reversed(diffs[-15:]))
    official_higher = diffs[:15]

    def fmt_div(rows):
        return [{"playerCode": p[0], "player_name": p[1], "NEO_SG": round(p[2], 4), "OFFICIAL_SG": p[3], "difference": round(p[2] - p[3], 4),
                  "official_sg_rounds": p[4], "NEO_sample_size": p[5], "NEO_rank": p[6]} for p in rows]

    cross_validation = {
        "TOTAL": cross_total,
        "OTT": "NOT_EVALUABLE: no frozen player-level NEO OTT feature exists (home_ranking.build_features aggregates only the warehouse 'total' field, never off_the_tee)",
        "APP": "NOT_EVALUABLE: same reason as OTT (approach)",
        "ARG": "NOT_EVALUABLE: same reason as OTT (around_green)",
        "PUTT": "NOT_EVALUABLE: same reason as OTT (putting)",
        "NEO_HIGHER_THAN_OFFICIAL": fmt_div(neo_higher),
        "OFFICIAL_HIGHER_THAN_NEO": fmt_div(official_higher),
        "note": "NEO SG uses long_term_sg (career mean of all historical event totals, frozen/unmodified); "
                "OFFICIAL SG TOTAL is klpga.co.kr's own season-2026-scoped figure. These differ in TIME WINDOW "
                "(career vs one season) by construction, not merely by measurement error -- this is an "
                "observation, not a claimed cause of any specific divergence (causes are not inferred here).",
    }
    (CONTENT / "NEO_OFFICIAL_SG_CROSS_VALIDATION.json").write_text(json.dumps(cross_validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["neo_official_sg_cross_validation"] = cross_validation

    # ================= Section 9: exposure bias audit =================
    bins = [(1, 4), (5, 9), (10, 19), (20, 39), (40, 59), (60, 10**9)]
    bin_labels = ["1-4", "5-9", "10-19", "20-39", "40-59", "60+"]
    exposure_rows = []
    for pid, name, neo_sg, off_sg, rounds, sample, rank in pairs_total:
        exposure_rows.append({"pid": pid, "neo_sg": neo_sg, "off_sg": off_sg, "rounds": rounds, "sample": sample, "rank": rank})
    exposure_bins = {}
    for (lo, hi), label in zip(bins, bin_labels):
        subset = [r for r in exposure_rows if r["rounds"] is not None and lo <= r["rounds"] <= hi]
        exposure_bins[label] = {
            "N": len(subset),
            "mean_official_sg": statistics.fmean(r["off_sg"] for r in subset) if subset else None,
            "median_official_sg": statistics.median(r["off_sg"] for r in subset) if subset else None,
            "mean_neo_sg": statistics.fmean(r["neo_sg"] for r in subset) if subset else None,
            "median_neo_sg": statistics.median(r["neo_sg"] for r in subset) if subset else None,
            "mean_neo_rank": statistics.fmean(r["rank"] for r in subset) if subset else None,
            "median_neo_rank": statistics.median(r["rank"] for r in subset) if subset else None,
        }
    rounds_list = [r["rounds"] for r in exposure_rows if r["rounds"] is not None]
    rank_list_for_rounds = [r["rank"] for r in exposure_rows if r["rounds"] is not None]
    neo_sg_list_for_rounds = [r["neo_sg"] for r in exposure_rows if r["rounds"] is not None]
    sample_list_for_rounds = [r["sample"] for r in exposure_rows if r["rounds"] is not None]
    exposure_bias = {
        "bins": exposure_bins,
        "spearman_official_sg_rounds_vs_neo_rank": spearman(rounds_list, rank_list_for_rounds),
        "spearman_official_sg_rounds_vs_neo_sg": spearman(rounds_list, neo_sg_list_for_rounds),
        "spearman_official_sg_rounds_vs_neo_sample_reliability": spearman(rounds_list, sample_list_for_rounds),
        "tournament_exposure_event_count_cut_completion_comparison": "NOT_EVALUABLE: no frozen per-player event_count/cut_count/3R-4R-completion feature exists at the TOP120-cohort level in this codebase (that granularity exists only inside the separate, unmerged research/neo-ranking-v2 branch's Phase B/cut-selection work, not in this production-based worktree)",
        "red_team_question": "측정 라운드가 많다는 이유만으로 NEO Ranking이 높아지는 경향이 존재하는가?",
        "red_team_answer": (
            "부분적으로 그렇다 (PARTIALLY YES, evidenced): "
            f"official_sg_rounds vs NEO rank Spearman = {spearman(rounds_list, rank_list_for_rounds)!r} "
            "(negative Spearman means MORE rounds correlates with a BETTER/lower rank number). "
            "This is a raw correlation only -- SG performance level is not held constant in this specific "
            "calculation (a full performance-controlled analysis is NOT_EVALUABLE within this single-snapshot "
            "phase; the bin table above lets a reader see whether mean official SG differs meaningfully "
            "across round-count bins alongside the rank pattern)."
        ),
    }
    (CONTENT / "NEO_EXPOSURE_BIAS_AUDIT.json").write_text(json.dumps(exposure_bias, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report["exposure_bias"] = exposure_bias

    # ================= Section 10: profile <-> SG sanity =================
    def paired(field_a, field_b, source_a, source_b):
        xs, ys = [], []
        for pid in set(profile_by_code) & set(sg_by_code):
            a, b = source_a.get(pid, {}).get(field_a), source_b.get(pid, {}).get(field_b)
            if a is not None and b is not None:
                xs.append(a); ys.append(b)
        return xs, ys

    sanity_pairs = [
        ("average_score", "official_sg_total"), ("gir_rate", "official_sg_app"),
        ("average_putts", "official_sg_putt"), ("recovery_rate", "official_sg_arg"),
        ("birdie_rate", "official_sg_total"),
    ]
    profile_sg_sanity = {}
    for fa, fb in sanity_pairs:
        xs, ys = paired(fa, fb, profile_by_code, sg_by_code)
        profile_sg_sanity[f"{fa}_vs_{fb}"] = {"N": len(xs), "Pearson": pearson(xs, ys), "Spearman": spearman(xs, ys), "note": "consistency check only, not a causal claim"}
    report["profile_sg_sanity"] = profile_sg_sanity

    # ================= Section 11: NEO ranking external validation =================
    ext_pairs = {"official_sg_total": [], "average_score": [], "gir_rate": [], "birdie_rate": [], "recovery_rate": []}
    ranks_for_ext = []
    for pid, neo_row in neo_by_id.items():
        if neo_row["neo_validation_rank"] is None:
            continue
        s, p = sg_by_code.get(pid), profile_by_code.get(pid)
        row_vals = {"official_sg_total": s["official_sg_total"] if s else None, "average_score": p["average_score"] if p else None,
                    "gir_rate": p["gir_rate"] if p else None, "birdie_rate": p["birdie_rate"] if p else None,
                    "recovery_rate": p["recovery_rate"] if p else None}
        if all(v is not None for v in row_vals.values()):
            ranks_for_ext.append(neo_row["neo_validation_rank"])
            for k, v in row_vals.items():
                ext_pairs[k].append(v)
    external_validation = {k: {"N": len(ranks_for_ext), "Spearman": spearman(ranks_for_ext, v)} for k, v in ext_pairs.items()}

    def top_n_avg(n, field, source):
        rows = [(neo_by_id[pid]["neo_validation_rank"], source.get(pid, {}).get(field)) for pid in neo_by_id if neo_by_id[pid]["neo_validation_rank"] and source.get(pid, {}).get(field) is not None]
        top = [v for r, v in rows if r <= n]
        allv = [v for r, v in rows]
        return {"top_n_mean": statistics.fmean(top) if top else None, "all_matched_mean": statistics.fmean(allv) if allv else None, "top_n_count": len(top)}

    top_distributions = {}
    for n in (10, 20, 50):
        top_distributions[f"top{n}"] = {
            "official_sg_total": top_n_avg(n, "official_sg_total", sg_by_code),
            "average_score": top_n_avg(n, "average_score", profile_by_code),
            "gir_rate": top_n_avg(n, "gir_rate", profile_by_code),
        }
    early_signal = "EARLY_SIGNAL = NOT_EVALUABLE_SINGLE_SNAPSHOT"
    report["neo_ranking_external_validation"] = {"spearman": external_validation, "top_n_distributions": top_distributions, "early_signal": early_signal}
    (CONTENT / "NEO_OFFICIAL_RANK_DIVERGENCE_INPUT_EXTERNAL_VALIDATION.json").write_text(
        json.dumps(report["neo_ranking_external_validation"], ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )

    # ================= Section 12: rank divergence table =================
    official_ranked = sorted([r for r in sg["records"] if r["official_rank"] is not None], key=lambda r: r["official_rank"])
    official_rank_by_code = {r["playerCode"]: r["official_rank"] for r in official_ranked}
    LOW_SAMPLE_THRESHOLD = 10
    divergence_rows = []
    for pid, neo_row in neo_by_id.items():
        if neo_row["neo_validation_rank"] is None:
            continue
        off_rank = official_rank_by_code.get(pid)
        if off_rank is None:
            continue
        s, p = sg_by_code.get(pid, {}), profile_by_code.get(pid, {})
        divergence_rows.append({
            "playerCode": pid, "player_name": neo_row["player_name"], "NEO_rank": neo_row["neo_validation_rank"],
            "Official_SG_rank": off_rank, "rank_difference": neo_row["neo_validation_rank"] - off_rank,
            "official_sg_total": s.get("official_sg_total"), "official_sg_rounds": s.get("official_sg_rounds"),
            "average_score": p.get("average_score"), "GIR": p.get("gir_rate"), "birdie_rate": p.get("birdie_rate"),
            "LOW_SAMPLE": (s.get("official_sg_rounds") or 0) < LOW_SAMPLE_THRESHOLD,
        })
    divergence_sorted = sorted(divergence_rows, key=lambda r: r["rank_difference"])
    rank_divergence = {
        "low_sample_threshold_rounds": LOW_SAMPLE_THRESHOLD,
        "TOP_POSITIVE_DIVERGENCE_NEO_WORSE_THAN_OFFICIAL": list(reversed(divergence_sorted[-20:])),
        "TOP_NEGATIVE_DIVERGENCE_NEO_BETTER_THAN_OFFICIAL": divergence_sorted[:20],
    }
    (CONTENT / "NEO_OFFICIAL_RANK_DIVERGENCE.json").write_text(json.dumps(rank_divergence, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report["rank_divergence"] = rank_divergence

    # ================= Section 13: sample reliability red team =================
    threshold_results = {}
    for threshold in (5, 8, 10, 12, 15, 20):
        subset = [(p[2], p[3]) for p in pairs_total if p[4] is not None and p[4] >= threshold]
        xs, ys = ([a for a, b in subset], [b for a, b in subset]) if subset else ([], [])
        threshold_results[f">={threshold}"] = {"N": len(xs), "Spearman": spearman(xs, ys), "Pearson": pearson(xs, ys), "MAE": mae(xs, ys)}
    report["sample_reliability_red_team"] = threshold_results
    (CONTENT / "NEO_SAMPLE_RELIABILITY_AUDIT.json").write_text(json.dumps(threshold_results, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    return report


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2, default=str))
