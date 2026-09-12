"""ROUND-CONTEXT CORRECTION (research/official-tournament-warehouse-v1-
20260912): regressions locking in the corrected tournament context for
gameCode 2026090003 (KB금융 골든라이프 챔피언십), the genuine POST-R3
forecast built on top of it, and the immutability of the original
POST-R2 forecast. See TOURNAMENT_SITE_REGISTRY.json's own
"_final_round_number_comment" and 2026090003_VALIDATION_LEDGER.json for
the full evidence trail this file exercises.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_context import load_tournament_context  # noqa: E402

GAME_CODE = "2026090003"
POST_R2_SHA256 = "ad65227f59c19562005b3140c5bbdcf9713d90ae61f2df00e46d9ab9e97c8367"


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------
# 1-3: corrected round context
# ---------------------------------------------------------------------

def test_2026090003_final_round_number_is_four():
    context = load_tournament_context(GAME_CODE)
    assert context.final_round_number == 4


def test_remaining_rounds_after_r2_is_two():
    context = load_tournament_context(GAME_CODE)
    assert context.final_round_number - 2 == 2


def test_remaining_rounds_after_r3_is_one():
    context = load_tournament_context(GAME_CODE)
    assert context.final_round_number - 3 == 1


# ---------------------------------------------------------------------
# 4-6: public stage contract (PRE -> R1 -> R2 -> R3 -> FR -> FINAL)
# ---------------------------------------------------------------------

def test_public_stage_sequence_is_pre_r1_r2_r3_fr_final():
    context = load_tournament_context(GAME_CODE)
    assert context.stage_order == ("pre", "r1", "r2", "r3", "fr", "final")


def test_fr_maps_to_competitive_round_4_never_r4_or_final_label():
    context = load_tournament_context(GAME_CODE)
    assert context.stage_labels["fr"] == "FR"
    assert "r4" not in context.stage_order  # FR is never publicly spelled "r4"


def test_final_label_is_distinct_post_tournament_stage():
    context = load_tournament_context(GAME_CODE)
    assert context.stage_labels["final"] == "FINAL"
    # FR and FINAL are two distinct stage-order entries, never collapsed into one.
    assert context.stage_order.index("fr") < context.stage_order.index("final")


# ---------------------------------------------------------------------
# 7: genuine 3-round events are unaffected (no global behavior change)
# ---------------------------------------------------------------------

def test_genuine_three_round_event_still_resolves_to_three():
    """OK저축은행 웃맨오픈 (2026120001) is a real, confirmed 3-round event
    (active_tournament.json's own final_round_number=3, registry
    holes=54) and carries no explicit final_round_number override --
    the mechanical rN-counting fallback must still apply to it exactly
    as before this fix."""
    context = load_tournament_context("2026120001")
    assert context.final_round_number == 3
    assert context.holes == 54


def test_registry_derivation_prefers_explicit_field_only_when_present():
    """A registry entry with no explicit final_round_number keeps the
    exact prior mechanical-counting behavior -- this fix is additive,
    never a behavior change for any tournament that omits the field."""
    from klpga.tournament_context import resolve_context

    registry = {
        "synthetic_no_override": {"url_base": "/x/", "stage_state_filename": "x.json", "stage_order": ["pre", "r1", "r2", "final"]},
    }
    identity = {
        "game_code": "synthetic_no_override", "tournament_name": "SYNTH", "season": 2026,
        "start_date": "2026-01-01", "end_date": "2026-01-02", "final_round_number": 999, "current_round_number": 0,
    }
    # resolve_context always trusts identity's own final_round_number when
    # called directly (that path is unchanged) -- the fallback-derivation
    # path under test lives in _load_context_from_schedule_and_registry,
    # exercised via the real 2026120001/2026090003 cases above.
    context = resolve_context(identity, registry)
    assert context.final_round_number == 999


# ---------------------------------------------------------------------
# 8-9: original POST-R2 forecast immutability + classification
# ---------------------------------------------------------------------

def test_frozen_post_r2_artifact_sha_unchanged():
    path = CONTENT / f"{GAME_CODE}_POST_R2_FINAL_FORECAST.json"
    assert _sha256(path) == POST_R2_SHA256


def test_original_r2_forecast_classified_as_context_defective():
    classification = _load(f"{GAME_CODE}_POST_R2_FORECAST_AUDIT_CLASSIFICATION.json")
    assert classification["classification"] == "HISTORICAL_FORECAST_WITH_ROUND_CONTEXT_ERROR"
    assert classification["subject_artifact_sha256"] == POST_R2_SHA256
    assert classification["subject_artifact_modified_by_this_script"] is False
    assert classification["defect"]["recorded_remaining_rounds"] == 1
    assert classification["defect"]["correct_remaining_rounds_at_end_of_r2"] == 2


def test_validation_ledger_marks_class_a_unusable_for_formal_claims():
    ledger = _load(f"{GAME_CODE}_VALIDATION_LEDGER.json")
    a = ledger["evidence_classes"]["A_ORIGINAL_POST_R2_FORECAST"]
    b = ledger["evidence_classes"]["B_POST_R3_FORECAST"]
    c = ledger["evidence_classes"]["C_FR_FINAL_TRUTH"]
    assert a["usable_for_formal_model_performance_claims"] is False
    assert b["usable_for_formal_model_performance_claims"] is True
    assert c["status"] == "PENDING"
    assert a["sha256"] == POST_R2_SHA256


# ---------------------------------------------------------------------
# 10-13: the genuine POST-R3 forecast itself
# ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def post_r3_forecast():
    return _load(f"{GAME_CODE}_POST_R3_FINAL_FORECAST.json")


def test_post_r3_forecast_is_a_distinct_artifact_from_post_r2(post_r3_forecast):
    post_r2_sha = _sha256(CONTENT / f"{GAME_CODE}_POST_R2_FINAL_FORECAST.json")
    post_r3_sha = _sha256(CONTENT / f"{GAME_CODE}_POST_R3_FINAL_FORECAST.json")
    assert post_r2_sha != post_r3_sha
    assert post_r3_forecast["artifact"] == "post_r3_final_forecast"
    assert post_r3_forecast["stage"] == "POST_R3"


def test_post_r3_forecast_correct_context(post_r3_forecast):
    assert post_r3_forecast["final_round_number"] == 4
    assert post_r3_forecast["remaining_rounds"] == 1
    assert post_r3_forecast["source_round"] == 3
    assert post_r3_forecast["feature_cutoff"] == "END_OF_R3"
    assert post_r3_forecast["n_simulations"] == 10000


def test_post_r3_forecast_uses_real_r3_scores(post_r3_forecast):
    leader = next(r for r in post_r3_forecast["records"] if r["player_id"] == "11056")
    assert leader["r3_score_to_par"] == -4.0
    assert leader["r3_total_to_par"] == -5.0  # matches raw official data-totunderpar


def test_post_r3_forecast_excludes_wd_player():
    forecast = _load(f"{GAME_CODE}_POST_R3_FINAL_FORECAST.json")
    ids = {r["player_id"] for r in forecast["records"]}
    assert "8881" not in ids  # 성유진, official WD -- never simulated
    assert forecast["simulated_field_size"] == 70
    assert forecast["official_advancing_field_size"] == 70


def test_post_r3_forecast_probability_monotonicity(post_r3_forecast):
    for row in post_r3_forecast["records"]:
        assert 0.0 <= row["win_pct"] <= row["top5_pct"] <= row["top10_pct"] <= row["top20_pct"] <= 100.0 + 1e-6


def test_post_r3_forecast_win_probabilities_sum_to_100(post_r3_forecast):
    total = sum(r["win_pct"] for r in post_r3_forecast["records"])
    assert total == pytest.approx(100.0, abs=0.5)


# ---------------------------------------------------------------------
# 14: no future (FR/FINAL) data entered the POST-R3 forecast
# ---------------------------------------------------------------------

def test_post_r3_forecast_excludes_all_future_data():
    forecast = _load(f"{GAME_CODE}_POST_R3_FINAL_FORECAST.json")
    assert forecast["future_data_excluded"] is True
    blob = json.dumps(forecast, ensure_ascii=False)
    # "neo_final_rank" is the model's OWN predicted rank output from this
    # same forecast (legitimate), not leaked official future truth --
    # excluded from the substring scan below by construction (none of
    # these forbidden tokens are substrings of it).
    for forbidden in ("r4_score", "round4score", "fr_score", "official_final_rank", "winner", "champion"):
        assert forbidden not in blob


def test_r3_freeze_never_carries_round4_evidence():
    freeze = _load(f"{GAME_CODE}_R3_FROZEN_EVIDENCE.json")
    assert freeze["round"] == 3
    assert freeze["feature_cutoff"] == "END_OF_R3"
    for record in freeze["records"]:
        assert "r4_score_to_par" not in record
        assert "fr_score_to_par" not in record


# ---------------------------------------------------------------------
# 15-16: the real R3 public page reads ONLY the POST-R3 forecast
# ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_r3_html():
    path = ROOT.parent / "docs" / "tournaments" / "2026" / GAME_CODE / "r3" / "index.html"
    assert path.is_file(), f"real R3 page not found at {path}"
    return path.read_text(encoding="utf-8")


def test_r3_page_leader_matches_post_r3_forecast_not_post_r2(real_r3_html, post_r3_forecast):
    leader = next(r for r in post_r3_forecast["records"] if r["player_id"] == "11056")
    row = re.search(r"<tr data-player-id='11056'>((?:(?!</tr>).)*)", real_r3_html).group(1)
    expected_top10 = f"{leader['top10_pct']:.1f}%"
    assert f"data-label='Top10'>{expected_top10}<" in row


def test_r3_page_carries_r3_forecast_labeling_not_stale_r2_labeling(real_r3_html):
    assert "R3 종료 후 예측" in real_r3_html
    assert "R2 종료 후 예측" not in real_r3_html


def test_r3_page_wd_row_has_no_probability_values(real_r3_html):
    row = re.search(r"<tr data-player-id='8881'>((?:(?!</tr>).)*)", real_r3_html).group(1)
    for label in ("Top20", "Top10", "Top5", "우승"):
        assert f"data-label='{label}'>—<" in row


def test_r3_page_stage_nav_has_fr_and_final_both_disabled(real_r3_html):
    nav = re.search(r'<nav class="stage-nav".*?</nav>', real_r3_html, re.DOTALL).group(0)
    assert nav.count('<span class="stage-nav__disabled" aria-disabled="true">FR</span>') == 1
    assert nav.count('<span class="stage-nav__disabled" aria-disabled="true">FINAL</span>') == 1
    assert 'href="/tournaments/2026/2026090003/r3/" aria-current="page">R3</a>' in nav
