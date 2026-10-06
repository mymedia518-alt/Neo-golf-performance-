"""Proves klpga.website_v2.stableford_blind_backtest (the generalized,
parameterized module built for 2024/2023 replication) produces the
EXACT same result as the frozen, untouched 2025-specific module --
i.e. generalizing it for replication did not alter the frozen V1
methodology in any way. This is the regression gate that must pass
before the generic module is trusted for a new target year."""
from __future__ import annotations

from pathlib import Path

import klpga.website_v2.stableford_2025_blind_backtest as frozen_2025
import klpga.website_v2.stableford_blind_backtest as generic

MANIFEST_2025 = Path("klpga_pipeline/content/website_v2/STABLEFORD_2025_PRIOR_TOURNAMENT_MANIFEST_V1.json").resolve()
PRIOR_DIR_2025 = Path("klpga_pipeline/evidence/stableford_prior_2025").resolve()


def test_generic_snapshot_matches_frozen_2025_hash_exactly():
    frozen_records = frozen_2025.build_preevent_snapshot()
    frozen_digest, frozen_payload = frozen_2025.freeze_and_hash(frozen_records)
    assert frozen_digest == "232aee3f8e3ac368d5924ceef8b676b2543da8edcd42ec860cd73e38061a26d4"

    generic_records = generic.build_preevent_snapshot("2025100001", MANIFEST_2025, PRIOR_DIR_2025)
    generic_digest, generic_payload = generic.freeze_and_hash(generic_records)

    assert generic_digest == frozen_digest
    assert generic_payload == frozen_payload


def test_generic_join_actual_results_matches_frozen_2025_evaluation():
    import json

    recon = json.loads(
        Path("klpga_pipeline/evidence/stableford_source_probe_2025100001/RECONSTRUCTION_2025100001.json")
        .read_text(encoding="utf-8")
    )
    actual = {a["player_name"]: a["total_points"] for a in recon["full_field_reconstruction_made_cut_players"]}

    frozen_records = frozen_2025.build_preevent_snapshot()
    frozen_result = frozen_2025.join_actual_results(frozen_records, actual, "김민솔")

    generic_records = generic.build_preevent_snapshot("2025100001", MANIFEST_2025, PRIOR_DIR_2025)
    generic_result = generic.join_actual_results(generic_records, actual, "김민솔")

    # Different dataclasses (frozen_2025.BlindEvaluationResult vs
    # generic.BlindEvaluationResult) -> dataclass __eq__ requires the
    # SAME class, so compare field-by-field via asdict() instead.
    from dataclasses import asdict
    assert asdict(generic_result) == asdict(frozen_result)
    assert generic_result.winner_pre_event_rank == 9
    assert generic_result.spearman_correlation == 0.5905
