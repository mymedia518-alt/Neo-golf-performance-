"""2024 BLIND BACKTEST REPLICATION tests -- real data only (23 committed
prior-tournament captures under evidence/stableford_prior_2024/ +
the already SOURCE-PASS-verified 2024100009 reconstruction). Uses the
generalized frozen pipeline (klpga.website_v2.stableford_blind_backtest),
already proven byte-identical to the frozen 2025 module by
test_stableford_blind_backtest_matches_frozen_2025.py."""
from __future__ import annotations

import json
from pathlib import Path

from klpga.website_v2.stableford_blind_backtest import (
    build_preevent_snapshot,
    freeze_and_hash,
    join_actual_results,
)

CONTENT_ROOT = Path(__file__).parent.parent / "content" / "website_v2"
EVIDENCE_ROOT = Path(__file__).parent.parent / "evidence"
MANIFEST_2024 = CONTENT_ROOT / "STABLEFORD_2024_PRIOR_TOURNAMENT_MANIFEST_V1.json"
PRIOR_DIR_2024 = EVIDENCE_ROOT / "stableford_prior_2024"
TARGET_2024 = "2024100009"


def _snapshot():
    return build_preevent_snapshot(TARGET_2024, MANIFEST_2024, PRIOR_DIR_2024)


def _actual_points():
    recon = json.loads((EVIDENCE_ROOT / f"stableford_source_probe_{TARGET_2024}" / f"RECONSTRUCTION_{TARGET_2024}.json").read_text(encoding="utf-8"))
    return {a["player_name"]: a["total_points"] for a in recon["full_field_reconstruction_made_cut_players"]}


def test_preevent_snapshot_covers_105_of_108_real_field():
    records = _snapshot()
    assert len(records) == 105


def test_missing_players_are_the_real_three():
    records = _snapshot()
    covered = {r.player_name for r in records}
    from klpga.collectors.score_record import extract_hole_outcomes
    target_html = (EVIDENCE_ROOT / f"stableford_source_probe_{TARGET_2024}" / f"scoreRecord_{TARGET_2024}.html").read_text(encoding="utf-8")
    field = set(extract_hole_outcomes(target_html)["1R"].keys())
    assert field - covered == {"박조은 0806(A)", "배신영", "유다겸(I)"}


def test_every_record_has_correct_rate_and_outcome_arithmetic():
    records = _snapshot()
    for r in records:
        assert r.holes > 0 and r.holes % 18 == 0
        assert r.albatross + r.eagle + r.birdie + r.par + r.bogey + r.double_or_worse == r.holes
        rate_sum = r.albatross_rate + r.eagle_rate + r.birdie_rate + r.par_rate + r.bogey_rate + r.double_or_worse_rate
        assert abs(rate_sum - 1.0) < 1e-3
        assert r.albatross == 0 and r.albatross_rate == 0.0


def test_kim_min_byul_blind_rank_reported_exactly_not_adjusted():
    records = _snapshot()
    km = next(r for r in records if r.player_name == "김민별")
    assert km.pre_event_rank == 16
    assert km.percentile == 85.58
    assert km.holes == 1116
    assert (km.eagle, km.birdie, km.par, km.bogey, km.double_or_worse) == (2, 200, 767, 134, 13)


def test_frozen_hash_matches_committed_value_and_is_immutable_after_join():
    records = _snapshot()
    digest_before, payload_before = freeze_and_hash(records)
    assert digest_before == "e55a64403d75c4eb634b6632b7f4858ef73a4a8e64718d6f87cf65f88c788eb4"

    join_actual_results(records, _actual_points(), "김민별")

    digest_after, payload_after = freeze_and_hash(records)
    assert digest_after == digest_before
    assert payload_after == payload_before


def test_join_actual_results_covers_all_60_made_cut_finalists():
    records = _snapshot()
    result = join_actual_results(records, _actual_points(), "김민별")
    assert result.n_joined == 60


def test_winner_evaluation_matches_frozen_rank_exactly():
    records = _snapshot()
    result = join_actual_results(records, _actual_points(), "김민별")
    assert result.winner_pre_event_rank == 16
    assert result.winner_pre_event_percentile == 85.58
    assert result.winner_actual_points == 49


def test_spearman_and_topn_metrics_match_computed_real_values():
    records = _snapshot()
    result = join_actual_results(records, _actual_points(), "김민별")
    assert result.spearman_correlation == 0.4818
    assert result.top10_precision == 0.2
    assert result.top10_recall == 0.2
    assert result.top20_precision == 0.5
    assert result.top20_recall == 0.5


def test_small_sample_players_present_and_disclosed():
    records = _snapshot()
    thin = [r for r in records if r.holes < 180]
    assert len(thin) == 3
    names = {r.player_name for r in thin}
    assert names == {"김효문", "이지원 0810(A)", "임채리"}


def test_frozen_snapshot_artifact_matches_live_computation():
    artifact = json.loads((CONTENT_ROOT / "STABLEFORD_2024_FROZEN_PREEVENT_SNAPSHOT_V1.json").read_text(encoding="utf-8"))
    records = _snapshot()
    digest, payload = freeze_and_hash(records)
    assert artifact["sha256"] == digest
    assert artifact["records"] == json.loads(json.dumps(payload, ensure_ascii=False))
