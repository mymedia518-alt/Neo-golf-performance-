"""KB 2026090003 R1 -- feature recovery investigation (owner decision:
attempt option (b) before designing any new model).

Locks in the finding: no source in this sandbox holds a leakage-safe,
correctly-defined prior_avg_round_score_to_par / neo_consistency_stddev
for KB's field. The one candidate adapter that DOES have real data
available (tournament_pre_state.py, backed by KB's own real Strokes
Gained profile) computes a different, sign-inverted quantity under the
historical field name -- proven here by a concrete real-player example,
not merely asserted. This must never be silently "fixed" by negating
the SG value without real historical calibration -- that would still be
inventing an unvalidated definition.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
GAME_CODE = "2026090003"


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def test_feature_recovery_status_is_blocked_definition_unrecoverable():
    rec = _load(f"KB_{GAME_CODE}_R1_FEATURE_RECOVERY_V1.json")
    assert rec["FEATURE_RECOVERY_STATUS"] == "BLOCKED_DEFINITION_UNRECOVERABLE"


def test_no_sqlite_database_anywhere_in_sandbox():
    hits = list(ROOT.parent.rglob("*.sqlite")) + list(ROOT.parent.rglob("*.db"))
    assert hits == []


def test_historical_sg_warehouse_never_carries_a_score_to_par_field():
    """The real, leakage-safe alternative dataset exists, but is
    genuinely a different metric -- proven by field inspection, not
    assumed from the file's name."""
    wh = _load("historical_sg_warehouse.json")
    cumulative = [r for r in wh["records"] if r.get("scope") == "tournament_cumulative"]
    assert len(cumulative) > 0
    sample = cumulative[0]
    assert "score_to_par" not in sample
    assert {"total", "tee_to_green", "off_the_tee", "approach", "around_green", "putting"}.issubset(sample.keys())


def test_tournament_pre_state_adapter_source_field_is_sg_not_score_to_par():
    """Direct proof the existing adapter reads an SG mean under the
    prior_avg_round_score_to_par name, not inference from the name."""
    source = (ROOT / "src" / "klpga" / "tournament_pre_state.py").read_text(encoding="utf-8")
    assert 'prior_avg_round_score_to_par=multi.get("mean")' in source
    assert '(windows.get("multi_season") or {}).get("components", {}).get("total", {})' in source


def test_round_update_simulation_has_no_sign_normalization_step():
    """Direct proof round_update.py adds expected_round_score_to_par to
    a real r1_score_to_par with no rebasing -- confirms the two values
    must already share the same lower-is-better convention."""
    source = (ROOT / "src" / "klpga" / "neo_win" / "round_update.py").read_text(encoding="utf-8")
    assert "p.r1_score_to_par + r2[p.player_code]" in source
    for forbidden in ("* -1", "-expected", "negate", "sign_flip", "invert"):
        assert forbidden not in source.lower()


def test_sign_inversion_proof_uses_real_kb_players_not_synthetic_data():
    rec = _load(f"KB_{GAME_CODE}_R1_FEATURE_RECOVERY_V1.json")
    proof = rec["sign_inversion_proof"]
    perf = _load(f"{GAME_CODE}_PRE_PERFORMANCE_SNAPSHOT.json")
    profiles = {p["player_id"]: p for p in perf["profiles"]}
    rank = _load(f"{GAME_CODE}_OFFICIAL_KLPGA_RANKING.json")
    rank_by_id = {r["player_id"]: r["official_rank"] for r in rank["records"] if r.get("official_rank") is not None}

    for row in proof["real_kb_evidence"]:
        pid = row["player_id"]
        assert profiles[pid]["player_name"] == row["player_name"]
        assert rank_by_id[pid] == row["official_k_rank"]
        actual_mean = profiles[pid]["windows"]["multi_season"]["components"]["total"]["mean"]
        assert actual_mean == row["sg_multi_season_total_mean"]

    best, worst = proof["real_kb_evidence"]
    assert best["official_k_rank"] < worst["official_k_rank"]
    # the whole point: the BETTER-ranked real player has the HIGHER (SG) mean,
    # which round_update.py would treat as a WORSE expected score-to-par
    assert best["sg_multi_season_total_mean"] > worst["sg_multi_season_total_mean"]


def test_no_frozen_beta_prediction_archive_exists_to_validate_against():
    hits = list(ROOT.rglob("neo_win_predictions/**/*.json"))
    assert hits == []


def test_pre_frozen_artifact_still_byte_identical():
    actual_sha = hashlib.sha256((CONTENT / f"{GAME_CODE}_PRE_5PROB_V2_FROZEN.json").read_bytes()).hexdigest()
    assert actual_sha == "456d465e05f919c96ab827a68004aafb1ad971a7a128e6b44c461c9eb41fef36"


def test_round_update_module_itself_was_not_modified_by_this_investigation():
    """This task must never change round_update.py's coefficients/formula."""
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--stat", "HEAD", "--", "src/klpga/neo_win/round_update.py"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == ""


def test_no_new_r1_probability_model_was_created():
    for pattern in ("pre_v3.py", "r1_prob_model.py", "round_update_v2.py"):
        assert not (ROOT / "src" / "klpga" / "neo_win" / pattern).exists()
