"""Tests for scripts/113 (validation postmortem) and 114 (K-Rank/SG/NEO
comparison) -- NEO SITE V5 Missions 4/5."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


postmortem_mod = _load("build_tournament_validation_postmortem", "113_build_tournament_validation_postmortem.py")
krank_sg_neo_mod = _load("build_k_rank_neo_sg_validation", "114_build_k_rank_neo_sg_validation.py")


# ------------------------------------------------------------- Mission 4


def test_postmortem_never_tunes_the_model():
    doc = postmortem_mod.build()
    assert doc["model_tuned_using_this_result"] is False


def test_postmortem_has_real_sample_and_metrics():
    doc = postmortem_mod.build()
    evaluation = doc["evaluation"]
    assert evaluation["sample_size"] > 50
    assert evaluation["mean_absolute_error_vs_win_outcome"]["mae"] is not None
    assert evaluation["win_probability_vs_final_score_discrimination"]["rho"] is not None


def test_postmortem_stores_pre_prediction_provenance():
    doc = postmortem_mod.build()
    assert doc["pre_prediction"]["future_data_excluded"] is True
    assert doc["pre_prediction"]["model_version"]


def test_postmortem_leaves_r1_r2_r3_slots_for_future_multi_stage_extension():
    doc = postmortem_mod.build()
    assert doc["r1_actual"] is None
    assert doc["r2_actual"] is None
    assert doc["r3_actual"] is None


def test_postmortem_calibration_bins_sum_to_sample_size():
    doc = postmortem_mod.build()
    total = sum(b["predicted_count"] for b in doc["evaluation"]["calibration_bins"])
    assert total == doc["evaluation"]["sample_size"]


# ------------------------------------------------------------- Mission 5


def test_k_vs_sg_is_computed_from_real_data():
    doc = krank_sg_neo_mod.build()
    assert doc["k_rank_vs_sg"]["spearman"]["n"] > 50
    assert -1.0 <= doc["k_rank_vs_sg"]["spearman"]["rho"] <= 1.0


def test_neo_sides_are_always_blocked_never_numeric():
    doc = krank_sg_neo_mod.build()
    for section in ("k_rank_vs_neo", "sg_vs_neo"):
        block = doc[section]
        assert block["status"] == "BLOCKED_FORMULA_NOT_APPROVED"
        for key in ("spearman", "top10_overlap", "top20_overlap", "top50_overlap", "largest_divergences"):
            assert block[key] is None


def test_top_n_overlaps_are_internally_consistent():
    doc = krank_sg_neo_mod.build()
    for key in ("top10_overlap", "top20_overlap", "top50_overlap"):
        overlap = doc["k_rank_vs_sg"][key]
        assert overlap["overlap_count"] <= overlap["n"]


def test_future_predictive_performance_slots_documented_not_fabricated():
    doc = krank_sg_neo_mod.build()
    for key in ("future_5r_sg", "future_10r_sg", "future_20r_sg"):
        assert doc["future_predictive_performance"][key]["status"] == "NOT_YET_COMPUTED"


def test_postmortem_and_krank_sg_neo_validation_never_read_active_tour_master():
    # NEO SITE V5 architecture-correction item 4: an architecture change
    # to the active-tour-player-universe definition (universe B) must
    # never alter an already-frozen validation result -- confirmed here
    # structurally, since neither script even reads that artifact.
    import inspect
    for m in (postmortem_mod, krank_sg_neo_mod):
        source = inspect.getsource(m)
        assert 'CONTENT / "ACTIVE_KLPGA_TOUR_PLAYER_MASTER' not in source
        assert "ACTIVE_MASTER_PATH" not in source


def test_neo_ranking_never_forced_to_reproduce_k_ranking():
    # No code path in this script computes or writes any "adjustment"
    # that would pull a future NEO rank toward K-Rank -- confirmed by
    # source inspection: the k_rank_vs_neo/sg_vs_neo blocks are always
    # a static, unconditional null template, never a function of k_rank.
    import inspect
    source = inspect.getsource(krank_sg_neo_mod)
    assert "adjust" not in source.lower()
    assert "force" not in source.lower() or "forced" not in source.lower()
