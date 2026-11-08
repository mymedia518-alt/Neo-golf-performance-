"""NEO ranking re-verification as of the 2026 season's last known
completed tournament, 대보 하우스디 챔피언십 (game_code 2026110001,
final round 2026-11-08, winner 유현조 at -14).

Reuses the FROZEN V1 formula unmodified
(klpga.website_v2.home_ranking.build_features,
klpga.website_v2.top120_validation's exact z-score/weight logic per
NEO_RANKING_V1_FROZEN.json) -- no weights or eligibility rules are
invented here. Two cohorts are evaluated side by side, NEVER merged:

  A. OFFICIAL_TOP120_COHORT -- calls top120_validation.evaluate()
     completely unchanged against the real official
     2026110001_KRANKING_TOP120.json (120 players, K-Ranking week
     2026-W43). This is the only invocation this frozen function was
     ever actually designed for.
  B. FULL_CANDIDATE_POOL -- the user explicitly required evaluating
     every player with any usable SG history, not a re-sort of the
     existing top120 list. top120_validation.evaluate() cannot do this
     (it hard-validates exactly a 120-row, population_kind ==
     "official_klpga_kranking_top120" cohort) -- so this script
     inlines the IDENTICAL z-score + weight formula
     (NEO_RANKING_V1_FROZEN.json's own `_z` transform and feature
     weights, byte-identical to top120_validation.py's `_z()`) over
     the full candidate pool instead. This is methodologically
     DIFFERENT exposure than the gate review ever tested -- the
     COHORT_DEPENDENCY failure this script's own gate table reproduces
     below is about exactly this kind of pool-membership sensitivity.

SG DATA COVERAGE (confirmed by direct repo inspection, not assumed):
only 13 of the 2026 season's at-least-28 known tournaments have any
official per-round or tournament-cumulative SG in this repository --
listed in full in TOURNAMENT_COVERAGE below. No SG value for any
missing round/player/tournament is estimated, interpolated, or
carried forward; a player's `sample_count` here is strictly "how many
of these 13 tournaments she has a real SG total for," not her true
season event count.
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
CONTENT = ROOT / "content" / "website_v2"

from klpga.website_v2.home_ranking import build_features  # noqa: E402
from klpga.website_v2 import top120_validation  # noqa: E402

FROZEN_CONFIG = json.loads((CONTENT / "NEO_RANKING_V1_FROZEN.json").read_text(encoding="utf-8"))
FORMULA = FROZEN_CONFIG["formula"]
MIN_SG_EVENTS = int(FORMULA["eligibility"]["minimum_sg_events"])
WEIGHTS = {name: float(spec["weight"]) for name, spec in FORMULA["features"].items()}

# (game_code, [(round, path, scope_of_source_file)], tournament_name, date) --
# the 3 tournaments that only have per-round files, no tournament_cumulative
# row anywhere; their cumulative total is the SUM of the rounds found.
SUMMED_TOURNAMENTS = [
    {
        "game_code": "2026100001", "name": "제20회 S-OIL 챔피언십", "date": "2026-11-01",
        "round_paths": [
            CONTENT / "SOIL_2026100001_R1_SG_OFFICIAL_V1.json",
            CONTENT / "SOIL_2026100001_R2_SG_OFFICIAL_V1.json",
            CONTENT / "SOIL_2026100001_R3_SG_OFFICIAL_V1.json",
            CONTENT / "SOIL_2026100001_FR_SG_OFFICIAL_V1.json",
        ],
    },
    {
        "game_code": "2026100003", "name": "아이스버그골프 · 서울신문 오픈", "date": "2026-10-18",
        "round_paths": [
            CONTENT / "ICEBERG_2026100003_R1_SG_OFFICIAL_V1.json",
            CONTENT / "ICEBERG_2026100003_R2_SG_OFFICIAL_V1.json",
        ],
        "note": "R3 SG was never normalized into its own JSON for Iceberg (only parsed inline by sg_pre_v1.load_2026_sg_round_history from raw HTML); R3 is therefore MISSING from this tournament's cumulative total below -- it reflects only 2 of 3 real rounds for every Iceberg player. Flagged, not filled.",
    },
    {
        "game_code": "2026110001", "name": "대보 하우스디 챔피언십", "date": "2026-11-08",
        "round_paths": [
            CONTENT / "DAEBO_2026110001_R1_SG_OFFICIAL_V1.json",
            CONTENT / "DAEBO_2026110001_R2_SG_OFFICIAL_V1.json",
            CONTENT / "DAEBO_2026110001_FR_SG_OFFICIAL_V1.json",
        ],
    },
]

KNOWN_SEASON_GAME_CODES_NO_SG = [
    "2026030001", "2026040001", "2026040002", "2026040003", "2026040004", "2026040005",
    "2026050001", "2026050003", "2026050004", "2026060001", "2026060002", "2026060003",
    "2026060004", "2026090001", "2026100004", "2026120001",
]


def load_history_cumulative_rows() -> tuple[list[dict], dict[str, dict]]:
    """Rows already present as scope=='tournament_cumulative' in
    sg_official_history/*/RECORDS.json -- these are KLPGA's own
    cumulative figures, not re-derived here."""
    rows = []
    coverage: dict[str, dict] = {}
    for path in sorted(CONTENT.glob("sg_official_history/*/RECORDS.json")):
        records = json.loads(path.read_text(encoding="utf-8"))
        cum = [r for r in records if r.get("scope") == "tournament_cumulative" and r.get("season") == 2026]
        if not cum:
            continue
        gc = str(cum[0]["game_code"])
        coverage[gc] = {
            "game_code": gc, "name": cum[0].get("tournament"), "date": cum[0].get("date"),
            "player_count": len(cum), "source": "sg_official_history (already-cumulative, official)",
        }
        rows.extend(cum)
    return rows, coverage


def build_summed_cumulative_rows() -> tuple[list[dict], dict[str, dict]]:
    rows = []
    coverage: dict[str, dict] = {}
    for spec in SUMMED_TOURNAMENTS:
        gc = spec["game_code"]
        per_player: dict[str, dict] = {}
        rounds_found = 0
        for p in spec["round_paths"]:
            if not p.exists():
                continue
            doc = json.loads(p.read_text(encoding="utf-8"))
            for rec in doc["records"]:
                pid = str(rec["player_id"])
                per_player.setdefault(pid, {"total": 0.0, "rounds": 0, "name": rec.get("player_name")})
                per_player[pid]["total"] += float(rec["total"])
                per_player[pid]["rounds"] += 1
            rounds_found += 1
        for pid, agg in per_player.items():
            rows.append({
                "player_id": pid, "player_name": agg["name"], "total": round(agg["total"], 3),
                "rounds": agg["rounds"], "game_code": gc, "season": 2026, "identity_state": "RETAINED",
                "scope": "tournament_cumulative_derived_sum", "date": spec["date"],
            })
        coverage[gc] = {
            "game_code": gc, "name": spec["name"], "date": spec["date"], "player_count": len(per_player),
            "source": f"summed from {rounds_found} per-round official SG file(s) (no pre-existing cumulative row)",
            "note": spec.get("note"),
        }
    return rows, coverage


def zscore(values: dict[str, float]) -> dict[str, float]:
    mean = statistics.fmean(values.values())
    sd = statistics.pstdev(values.values())
    return {k: (v - mean) / sd if sd else 0.0 for k, v in values.items()}


def score_full_pool(features: dict[str, dict]) -> tuple[dict[str, float], dict[str, dict], list[str]]:
    eligible = [pid for pid, f in features.items() if f["sample_count"] >= MIN_SG_EVENTS]
    components = {}
    for name in ("recent_5_sg", "recent_10_sg", "long_term_sg"):
        components[name] = zscore({pid: float(features[pid][name]) for pid in eligible})
    components["consistency"] = zscore({pid: -float(features[pid]["volatility"]) for pid in eligible})
    scores, contributions = {}, {}
    for pid in eligible:
        reliability = min(float(features[pid]["sample_count"]) / 20.0, 1.0)
        contributions[pid] = {name: WEIGHTS[name] * components[name][pid] for name in components}
        contributions[pid]["sample_reliability"] = WEIGHTS["sample_reliability"] * reliability
        scores[pid] = sum(contributions[pid].values())
    return scores, contributions, eligible


def spearman(xs: list[float], ys: list[float]) -> float:
    def rank(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        ranks = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks
    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = math_sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math_sqrt(sum((b - my) ** 2 for b in ry))
    return cov / (sx * sy) if sx and sy else 0.0


def math_sqrt(x: float) -> float:
    return x ** 0.5


def main() -> None:
    hist_rows, hist_cov = load_history_cumulative_rows()
    summed_rows, summed_cov = build_summed_cumulative_rows()
    all_rows = hist_rows + summed_rows
    warehouse = {"records": all_rows}

    coverage = {**hist_cov, **summed_cov}
    features = build_features(warehouse)

    # ---- Cohort A: official top120, unmodified evaluate() ----
    top120_doc = json.loads((CONTENT / "2026110001_KRANKING_TOP120.json").read_text(encoding="utf-8"))
    eval_config = {**FORMULA, "model_id": FROZEN_CONFIG["model_id"]}
    a_output, a_summary = top120_validation.evaluate(top120_doc, warehouse, eval_config)
    a_ranked = sorted((r for r in a_output if r["neo_validation_rank"]), key=lambda r: r["neo_validation_rank"])

    # ---- Cohort B: full candidate pool, same formula, inlined ----
    b_scores, b_contrib, b_eligible = score_full_pool(features)
    b_ordered = sorted(b_scores, key=lambda pid: (-b_scores[pid], pid))
    name_lookup = {}
    for r in all_rows:
        name_lookup.setdefault(str(r["player_id"]), r.get("player_name"))
    for r in top120_doc["records"]:
        name_lookup.setdefault(str(r["player_id"]), r.get("player_name"))

    b_rows = []
    for rank, pid in enumerate(b_ordered, 1):
        f = features[pid]
        b_rows.append({
            "rank": rank, "player_id": pid, "player_name": name_lookup.get(pid, "?"),
            "score": round(b_scores[pid], 6), "sample_count_tournaments": f["sample_count"],
            "recent_5_sg": f["recent_5_sg"], "recent_10_sg": f["recent_10_sg"], "long_term_sg": f["long_term_sg"],
            "volatility": f["volatility"], "feature_contributions": {k: round(v, 6) for k, v in b_contrib[pid].items()},
        })
    b_top100 = b_rows[:100]

    # ---- Verification gates (computed on TODAY's real data) ----
    gates = []
    # EXPOSURE_BIAS: Spearman(sample_count_tournaments, neo_rank) for cohort B
    xs = [float(r["sample_count_tournaments"]) for r in b_top100]
    ys = [float(r["rank"]) for r in b_top100]
    rho = spearman(xs, ys)
    gates.append({
        "gate": "EXPOSURE_BIAS", "metric": f"Spearman(event_count, neo_rank) over top100 pool B = {rho:.3f}",
        "pass": abs(rho) < 0.15, "note": "known 2026-09-12 finding was -0.358 on a different (120-player, different-era-data) cohort; this is the same diagnostic re-run on today's full-pool output, not a re-use of the old number.",
    })
    # COHORT_DEPENDENCY: swap one eligible-but-not-top100 player out, one in; measure rank churn in top100.
    # If the eligible pool B is <=100 (no one outside top100 to swap in from), there is no
    # meaningful swap to run; this is reported as its own finding rather than skipped silently.
    swappable = [pid for pid in b_eligible if pid not in {r["player_id"] for r in b_top100}]
    if swappable:
        drop_pid = b_top100[-1]["player_id"]
        add_pid = swappable[0]
        trial_pool = [pid for pid in b_eligible if pid != drop_pid] + [add_pid] if drop_pid != add_pid else b_eligible
    else:
        # Fall back to: drop the single lowest-scoring eligible player, no replacement,
        # and measure how much that alone perturbs everyone else's relative order --
        # the cohort pool here (eligible_count) is itself < 100, so there is no genuinely
        # "unrelated" outside player to swap in.
        drop_pid = b_ordered[len(b_eligible) - 1]
        add_pid = None
        trial_pool = [pid for pid in b_eligible if pid != drop_pid]
    comp2 = {}
    for name in ("recent_5_sg", "recent_10_sg", "long_term_sg"):
        comp2[name] = zscore({pid: float(features[pid][name]) for pid in trial_pool})
    comp2["consistency"] = zscore({pid: -float(features[pid]["volatility"]) for pid in trial_pool})
    scores2 = {}
    for pid in trial_pool:
        rel = min(float(features[pid]["sample_count"]) / 20.0, 1.0)
        contrib2 = {name: WEIGHTS[name] * comp2[name][pid] for name in comp2}
        contrib2["sample_reliability"] = WEIGHTS["sample_reliability"] * rel
        scores2[pid] = sum(contrib2.values())
    ordered2 = sorted(scores2, key=lambda pid: (-scores2[pid], pid))
    rank2 = {pid: i + 1 for i, pid in enumerate(ordered2)}
    common = [pid for pid in b_eligible if pid in rank2 and pid != drop_pid]
    rank1_map = {pid: i + 1 for i, pid in enumerate(b_ordered) if pid in rank2}
    changed = sum(1 for pid in common if rank1_map.get(pid) != rank2.get(pid))
    pct = changed / len(common) * 100 if common else 0.0
    swap_desc = f"swapping {drop_pid}->{add_pid}" if add_pid else f"dropping {drop_pid} (eligible pool is only {len(b_eligible)} < 100, no outside player available to swap in)"
    gates.append({
        "gate": "COHORT_DEPENDENCY", "metric": f"{pct:.1f}% of {len(common)} unaffected players' ranks changed when {swap_desc}",
        "pass": pct < 5.0, "note": "known 2026-09-12 finding was 13.1% on a different (120-player) cohort/era; re-run on today's full pool B, which has a smaller effective pool (99 eligible) than that original test assumed.",
    })
    gates.append({
        "gate": "PUBLICATION_APPROVAL", "metric": "NEO_RANKING_PUBLICATION_GATE_DECISION.json status",
        "pass": False, "note": "status remains BLOCKED as of this script's run; this script does not and cannot flip that decision -- no new approval evidence exists in this repo.",
    })

    # ---- Comparison vs last published state (2026-11-01) ----
    prev_doc = json.loads((Path(__file__).resolve().parents[2] / "docs" / "data" / "neo-ranking-2026-11-01.json").read_text(encoding="utf-8"))
    prev_rank = {str(r["player_id"]): r["rank"] for r in prev_doc["players"]}
    movers = []
    for r in b_top100:
        prev = prev_rank.get(r["player_id"])
        if prev is not None:
            movers.append({"player_id": r["player_id"], "player_name": r["player_name"], "prev_rank": prev, "new_rank": r["rank"], "delta": prev - r["rank"]})
    movers.sort(key=lambda m: -abs(m["delta"]))

    OUT_JSON = CONTENT / "NEO_RANKING_FULLPOOL_V2_2026_11_08.json"
    OUT_CSV = CONTENT / "NEO_RANKING_FULLPOOL_V2_2026_11_08.csv"
    out_doc = {
        "schema_version": "NEO_RANKING_FULLPOOL_V2",
        "as_of": "2026-11-08",
        "note": "대보 하우스디 챔피언십 (2026-11-08 종료, 유현조 우승 -14) 반영. 공개 승인되지 않은 FROZEN V1 공식을 그대로 재사용; 전체 후보군(top120 고정 명단이 아님) 평가.",
        "formula_source": "NEO_RANKING_V1_FROZEN.json (unmodified)",
        "publication_gate_status": "BLOCKED (see gates below) -- this is NOT a publication-approved ranking",
        "tournament_coverage": coverage,
        "known_season_game_codes_with_no_sg_data": KNOWN_SEASON_GAME_CODES_NO_SG,
        "eligibility_minimum_sg_events": MIN_SG_EVENTS,
        "full_pool_size": len(features),
        "eligible_count": len(b_eligible),
        "gates": gates,
        "top_movers_vs_2026_11_01": movers[:20],
        "players": b_top100,
    }
    OUT_JSON.write_text(json.dumps(out_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "player_id", "player_name", "score", "sample_count_tournaments", "recent_5_sg", "recent_10_sg", "long_term_sg", "volatility"])
        for r in b_top100:
            w.writerow([r["rank"], r["player_id"], r["player_name"], r["score"], r["sample_count_tournaments"], r["recent_5_sg"], r["recent_10_sg"], r["long_term_sg"], r["volatility"]])

    print(json.dumps({
        "cohort_A_official_top120_ranked": len(a_ranked),
        "cohort_A_summary": a_summary,
        "cohort_B_full_pool_size": len(features),
        "cohort_B_eligible": len(b_eligible),
        "cohort_B_top5": [(r["rank"], r["player_name"], r["score"]) for r in b_top100[:5]],
        "gates": gates,
        "written": [str(OUT_JSON), str(OUT_CSV)],
    }, ensure_ascii=False, indent=2))

    # Save cohort A too, for the report.
    (CONTENT / "NEO_RANKING_OFFICIAL_TOP120_COHORT_V1_2026_11_08.json").write_text(
        json.dumps({"schema_version": "NEO_RANKING_OFFICIAL_TOP120_COHORT_V1", "as_of": "2026-11-08",
                    "summary": a_summary, "records": a_ranked}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
