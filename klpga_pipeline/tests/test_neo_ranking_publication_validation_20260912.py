"""NEO RANKING PUBLICATION-LEVEL VALIDATION (2026-09-12).

Permanent regression guards for the findings of the full 19-section
publication-readiness audit (docs/NEO_RANKING_PUBLICATION_VALIDATION_
20260912.md). Two are CONFIRMED, currently-unfixed hard defects
(exposure bias from unnormalized round counts; cohort z-score
membership sensitivity) captured here as documenting regressions so a
future change to either is visible and deliberate, not silent. The
rest guard structural invariants (formula-approval block, population
block, no-sentinel-rank, SG arithmetic, reproducibility, no
K-Ranking/win-probability leakage) that this audit depends on.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

from klpga.website_v2 import home_ranking
from klpga.website_v2.neo_ranking_backtest import run_backtest
from klpga.website_v2.top120_validation import evaluate

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"


def load(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def test_home_ranking_formula_state_remains_blocked_pending_approval():
    """home_ranking.py's own hard gate must stay in place until a
    formula is explicitly approved -- this audit did not approve one."""
    assert home_ranking.FORMULA_STATE == "BLOCKED_FORMULA_NOT_APPROVED"
    assert home_ranking.NEO_RANKING_VERSION is None


def test_regular_tour_population_validation_remains_blocked():
    document = load("HOME_REGULAR_TOUR_PLAYER_MASTER.json")
    assert document["population_validation_state"] == "BLOCKED_CURRENT_REGISTRY_EQUIVALENCE_NOT_PROVEN"
    with __import__("pytest").raises(ValueError):
        home_ranking.validate_population({**document, "population_validation_state": "PASS"})


def test_no_neo_ranked_player_ever_receives_a_sentinel_rank():
    cohort = load("HOME_PLAYER_MASTER_TOP120_2026_W36.json")
    warehouse = load("historical_sg_warehouse_corrected.json")
    config = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    out, summary = evaluate(cohort, warehouse, config)
    ranks = [r["neo_validation_rank"] for r in out if r["neo_validation_rank"] is not None]
    assert ranks, "fixture must have at least one ranked player"
    assert max(ranks) < 999999
    assert max(ranks) == summary["neo_ranked"]
    assert min(ranks) == 1


def test_sg_component_math_is_within_tolerance_across_the_full_warehouse():
    """SG_INTEGRITY gate: SG_TOTAL ~= tee_to_green + putting and
    tee_to_green ~= off_the_tee + approach + around_green for every
    record that carries all five fields, tolerance 0.05."""
    warehouse = load("historical_sg_warehouse_corrected.json")
    violations = 0
    for r in warehouse["records"]:
        t2g, ott, app, arg, putt, total = (
            r.get("tee_to_green"), r.get("off_the_tee"), r.get("approach"),
            r.get("around_green"), r.get("putting"), r.get("total"),
        )
        if None in (t2g, ott, app, arg, putt, total):
            continue
        if abs(t2g - (ott + app + arg)) > 0.05 or abs(total - (t2g + putt)) > 0.05:
            violations += 1
    assert violations == 0


def test_no_duplicate_game_player_scope_round_among_retained_rows():
    """Duplicate (game_code, player_id, scope, round) keys only ever
    occur among UNRESOLVED_IDENTITY rows (player_id is legitimately
    null/shared there) -- there must be zero duplicates among RETAINED
    rows, which is what every consumer (build_features,
    _latest_records) actually joins on."""
    warehouse = load("historical_sg_warehouse_corrected.json")
    from collections import Counter
    retained = [r for r in warehouse["records"] if r.get("identity_state") == "RETAINED" and r.get("player_id")]
    keys = Counter((r["game_code"], r["player_id"], r.get("scope"), r.get("round")) for r in retained)
    assert all(count == 1 for count in keys.values())


def test_exposure_bias_majority_of_consumed_observations_lack_round_normalization():
    """CONFIRMED, UNFIXED DEFECT (publication gate: EXPOSURE_BIAS =
    BLOCKED). home_ranking.build_features() and
    neo_ranking_backtest._latest_records() both consume the raw event
    'total' field with zero division by 'rounds' -- a player who played
    only 1 of 4 rounds contributes that single round's SG identically
    to a player's full 4-round cumulative total. This test documents
    the CURRENT, real magnitude of that exposure so a future change
    (fix or regression) to this behavior is visible and deliberate,
    never silent. If this test's asserted percentage ever moves
    sharply, that is a real change to how much of the ranking's input
    is round-count-biased -- re-verify before updating the assertion,
    do not just bump the numbers to make it pass."""
    warehouse = load("historical_sg_warehouse_corrected.json")
    latest = {}
    for row in warehouse["records"]:
        pid, gc = str(row.get("player_id") or "").strip(), str(row.get("game_code") or "").strip()
        if not pid or not gc or row.get("identity_state") != "RETAINED":
            continue
        total = row.get("total")
        if not isinstance(total, (int, float)) or not math.isfinite(float(total)):
            continue
        key = (pid, gc)
        if key not in latest or int(row.get("rounds") or 0) >= int(latest[key].get("rounds") or 0):
            latest[key] = row
    rounds = [int(r.get("rounds") or 0) for r in latest.values()]
    single_round_pct = 100 * sum(1 for n in rounds if n == 1) / len(rounds)
    full_4round_pct = 100 * sum(1 for n in rounds if n == 4) / len(rounds)
    # Real, reproduced magnitude as of this audit: ~43.6% single-round-only, ~29.7% full 4-round.
    assert single_round_pct > 35, "single-round-only share dropped -- re-verify whether a fix landed before updating this test"
    assert full_4round_pct < 40, "full-4-round share rose sharply -- re-verify before updating this test"


def test_cohort_zscore_makes_unrelated_players_rank_shift_when_pool_membership_changes():
    """CONFIRMED, UNFIXED DEFECT (publication gate: RED TEAM = BLOCKED).
    Swapping ONE player in the TOP120 pool (for an unrelated real
    player with SG history, keeping the population structurally valid
    at exactly 120 entries) changes the NEO rank of some OTHER,
    completely unaffected players purely because they are re-z-scored
    against a different cohort -- their own performance did not
    change. This documents that the defect currently exists; if it
    ever stops reproducing, that is a real formula change worth
    investigating, not a reason to delete this test."""
    warehouse = load("historical_sg_warehouse_corrected.json")
    config = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    cohort = load("HOME_PLAYER_MASTER_TOP120_2026_W36.json")

    baseline, _ = evaluate(cohort, warehouse, config)
    baseline_ranks = {r["player_id"]: r["neo_validation_rank"] for r in baseline if r["neo_validation_rank"]}

    in_cohort_ids = {str(r["player_id"]) for r in cohort["records"]}
    candidate_pool = {str(r.get("player_id")) for r in warehouse["records"] if r.get("identity_state") == "RETAINED"}
    substitute_id = next(pid for pid in sorted(candidate_pool) if pid not in in_cohort_ids)

    swapped = copy.deepcopy(cohort)
    removed = swapped["records"][-1]
    swapped["records"][-1] = {**removed, "player_id": substitute_id, "player_name": f"UNRELATED_SUB_{substitute_id}"}

    swapped_out, _ = evaluate(swapped, warehouse, config)
    swapped_ranks = {r["player_id"]: r["neo_validation_rank"] for r in swapped_out if r["neo_validation_rank"]}

    common = set(baseline_ranks) & set(swapped_ranks)
    changed = sum(1 for pid in common if baseline_ranks[pid] != swapped_ranks[pid])
    assert changed > 0, "cohort membership sensitivity did not reproduce -- re-verify whether the formula changed"


def test_neo_ranking_backtest_is_bytewise_reproducible():
    warehouse = load("historical_sg_warehouse_corrected.json")
    config = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    cohort = load("HOME_PLAYER_MASTER_TOP120_2026_W36.json")
    out_a, _ = evaluate(cohort, warehouse, config)
    out_b, _ = evaluate(cohort, warehouse, config)
    assert out_a == out_b


def test_neo_score_never_incorporates_k_ranking_or_win_probability():
    config = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    source_backtest = (ROOT / "src" / "klpga" / "website_v2" / "neo_ranking_backtest.py").read_text(encoding="utf-8")
    source_top120 = (ROOT / "src" / "klpga" / "website_v2" / "top120_validation.py").read_text(encoding="utf-8")
    assert all(name in ("recent_5_sg", "recent_10_sg", "long_term_sg", "consistency", "sample_reliability") for name in config["features"])
    # official_k_rank legitimately appears in top120_validation.py, but only
    # as passthrough display data (validate_cohort/output rows) -- never as
    # an input to _z()/scores/contributions. The scoring function itself
    # (run_backtest) must never reference K-Ranking or win-probability at all.
    assert "official_k_rank" not in source_backtest
    assert "win_probability" not in source_backtest
    assert "win_probability" not in source_top120


def test_explainability_rank_order_is_reproducible_from_the_audit_record_alone():
    """Section 12 hard requirement: displayed rank must be exactly
    reproducible by independently recomputing the score from the
    per-player feature_contributions the model itself reports."""
    warehouse = load("historical_sg_warehouse_corrected.json")
    config = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    cohort = load("HOME_PLAYER_MASTER_TOP120_2026_W36.json")
    out, _ = evaluate(cohort, warehouse, config)
    ranked = [r for r in out if r["neo_validation_rank"]]
    recomputed = [(r["player_id"], round(sum(r["feature_contributions"].values()), 6), r["neo_validation_rank"]) for r in ranked]
    resorted = sorted(recomputed, key=lambda t: (-t[1], t[0]))
    assert all(resorted[i][2] == i + 1 for i in range(len(resorted)))
