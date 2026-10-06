"""2023 BLIND BACKTEST REPLICATION tests -- real data only (19 committed
prior-tournament captures under evidence/stableford_prior_2023/ + the
already SOURCE-PASS-verified 2023100002 reconstruction). Uses the
generalized frozen pipeline (klpga.website_v2.stableford_blind_backtest),
unchanged from the 2024/2025 runs."""
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
MANIFEST_2023 = CONTENT_ROOT / "STABLEFORD_2023_PRIOR_TOURNAMENT_MANIFEST_V1.json"
PRIOR_DIR_2023 = EVIDENCE_ROOT / "stableford_prior_2023"
TARGET_2023 = "2023100002"


def _snapshot():
    return build_preevent_snapshot(TARGET_2023, MANIFEST_2023, PRIOR_DIR_2023)


def _actual_points():
    recon = json.loads((EVIDENCE_ROOT / f"stableford_source_probe_{TARGET_2023}" / f"RECONSTRUCTION_{TARGET_2023}.json").read_text(encoding="utf-8"))
    return {a["player_name"]: a["total_points"] for a in recon["full_field_reconstruction_made_cut_players"]}


def test_manifest_has_19_entries_target_excluded_all_strictly_prior():
    from datetime import date
    manifest = json.loads(MANIFEST_2023.read_text(encoding="utf-8"))
    assert manifest["target_game_code"] == TARGET_2023
    assert len(manifest["entries"]) == 19
    codes = [e["game_code"] for e in manifest["entries"]]
    assert len(set(codes)) == 19
    assert TARGET_2023 not in codes
    target = date(2023, 10, 12)
    for e in manifest["entries"]:
        y, m, d = map(int, e["start_date"].split("-"))
        assert date(y, m, d) < target


def test_manifest_dates_match_independently_sourced_tournament_master_dates():
    """The 2023 manifest was produced by a different process than the
    generic build_manifest() used for 2024/2025 (placeholder names for
    most entries, no before_target_event_start field) -- so its dates
    are cross-checked here against TOURNAMENT_MASTER_DATES_V1.json (the
    same real production-DB-sourced file 2024/2025 used) rather than
    trusted at face value. All 19 must match exactly."""
    master_dates = json.loads((CONTENT_ROOT / "TOURNAMENT_MASTER_DATES_V1.json").read_text(encoding="utf-8"))["dates"]
    manifest = json.loads(MANIFEST_2023.read_text(encoding="utf-8"))
    for e in manifest["entries"]:
        assert master_dates.get(e["game_code"]) == e["start_date"], (
            f"{e['game_code']}: manifest claims {e['start_date']}, "
            f"TOURNAMENT_MASTER_DATES_V1.json says {master_dates.get(e['game_code'])}"
        )


def test_preevent_snapshot_covers_106_of_108_real_field():
    records = _snapshot()
    assert len(records) == 106


def test_missing_players_are_the_real_two():
    records = _snapshot()
    covered = {r.player_name for r in records}
    from klpga.collectors.score_record import extract_hole_outcomes
    target_html = (EVIDENCE_ROOT / f"stableford_source_probe_{TARGET_2023}" / f"scoreRecord_{TARGET_2023}.html").read_text(encoding="utf-8")
    field = set(extract_hole_outcomes(target_html)["1R"].keys())
    assert field - covered == {"박조은 0806(A)", "신이솔"}


def test_every_record_has_correct_rate_and_outcome_arithmetic():
    records = _snapshot()
    for r in records:
        assert r.holes > 0 and r.holes % 18 == 0
        assert r.albatross + r.eagle + r.birdie + r.par + r.bogey + r.double_or_worse == r.holes
        rate_sum = r.albatross_rate + r.eagle_rate + r.birdie_rate + r.par_rate + r.bogey_rate + r.double_or_worse_rate
        assert abs(rate_sum - 1.0) < 1e-3
        assert r.albatross == 0 and r.albatross_rate == 0.0


def test_bang_sin_sil_blind_rank_reported_exactly_not_adjusted():
    records = _snapshot()
    bs = next(r for r in records if r.player_name == "방신실")
    assert bs.pre_event_rank == 14
    assert bs.percentile == 87.62
    assert bs.holes == 936
    assert (bs.eagle, bs.birdie, bs.par, bs.bogey, bs.double_or_worse) == (3, 183, 606, 115, 29)


def test_frozen_hash_matches_committed_value_and_is_immutable_after_join():
    records = _snapshot()
    digest_before, payload_before = freeze_and_hash(records)
    assert digest_before == "7d32813aab7a11faf2fb2571767638bb11b8bbdf0f60c7f0057d12fe829cf0f1"

    join_actual_results(records, _actual_points(), "방신실")

    digest_after, payload_after = freeze_and_hash(records)
    assert digest_after == digest_before
    assert payload_after == payload_before


def test_join_actual_results_covers_all_61_made_cut_finalists():
    records = _snapshot()
    result = join_actual_results(records, _actual_points(), "방신실")
    assert result.n_joined == 61


def test_winner_evaluation_matches_frozen_rank_exactly():
    records = _snapshot()
    result = join_actual_results(records, _actual_points(), "방신실")
    assert result.winner_pre_event_rank == 14
    assert result.winner_pre_event_percentile == 87.62
    assert result.winner_actual_points == 43


def test_spearman_and_topn_metrics_match_computed_real_values():
    records = _snapshot()
    result = join_actual_results(records, _actual_points(), "방신실")
    assert result.spearman_correlation == 0.2877
    assert result.top10_precision == 0.5
    assert result.top10_recall == 0.3571
    assert result.top20_precision == 0.5
    assert result.top20_recall == 0.4762


def test_small_sample_players_present_and_disclosed():
    records = _snapshot()
    thin = [r for r in records if r.holes < 180]
    names = {r.player_name for r in thin}
    assert names == {"임채리", "박희영", "이세영 0705(A)", "김지윤 0506(A)"}


def test_frozen_snapshot_artifact_matches_live_computation():
    artifact = json.loads((CONTENT_ROOT / "STABLEFORD_2023_FROZEN_PREEVENT_SNAPSHOT_V1.json").read_text(encoding="utf-8"))
    records = _snapshot()
    digest, payload = freeze_and_hash(records)
    assert artifact["sha256"] == digest
    assert artifact["records"] == json.loads(json.dumps(payload, ensure_ascii=False))
