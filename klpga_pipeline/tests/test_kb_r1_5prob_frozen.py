"""KB 2026090003 R1 5-tier frozen prediction -- regression coverage.

Locks in the freeze produced by scripts/108_apply_r1_model_to_kb.py:
118 = predicted + excluded reconciliation, coherence for every
predicted player, PRE artifact byte-identical, no refit, official
evidence/config provenance recorded.
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


def _freeze() -> dict:
    return _load(f"{GAME_CODE}_R1_5PROB_FROZEN_V1.json")


def test_reconciles_118_active_players():
    freeze = _freeze()
    assert freeze["r1_active_count"] == 118
    assert freeze["predicted_count"] + freeze["excluded_count"] == 118
    assert len(freeze["predictions"]) == freeze["predicted_count"]
    assert len(freeze["excluded_players"]) == freeze["excluded_count"]


def test_official_wd_count_and_no_overlap_with_predictions():
    freeze = _freeze()
    assert freeze["official_wd_count"] == 2
    wd_ids = {w["playerCode"] for w in freeze["official_wd"]}
    predicted_ids = {p["player_id"] for p in freeze["predictions"]}
    excluded_ids = {e["player_id"] for e in freeze["excluded_players"]}
    assert wd_ids.isdisjoint(predicted_ids)
    assert wd_ids.isdisjoint(excluded_ids)
    assert (predicted_ids | excluded_ids | wd_ids) == {
        e["player_id"] for e in _load(f"{GAME_CODE}_ENTRY_SNAPSHOT.json")["entries"]
    }


def test_no_duplicate_player_ids():
    freeze = _freeze()
    ids = [p["player_id"] for p in freeze["predictions"]]
    assert len(ids) == len(set(ids))


def test_every_prediction_is_coherent():
    freeze = _freeze()
    for p in freeze["predictions"]:
        vals = [p["win"], p["top5"], p["top10"], p["top20"], p["cut"]]
        assert all(0.0 <= v <= 1.0 for v in vals), p
        assert vals == sorted(vals), p


def test_excluded_players_reason_is_disclosed_not_fabricated():
    freeze = _freeze()
    for e in freeze["excluded_players"]:
        assert e["reason"] == "INSUFFICIENT_PRE_HISTORY_FOR_NEO_V1_SCORE"
    excluded_ids = {e["player_id"] for e in freeze["excluded_players"]}
    predicted_ids = {p["player_id"] for p in freeze["predictions"]}
    assert excluded_ids.isdisjoint(predicted_ids)


def test_no_refit_performed():
    freeze = _freeze()
    assert freeze["refit_performed"] is False
    assert freeze["future_data_excluded"] is True


def test_model_freeze_provenance_matches_real_files():
    freeze = _freeze()
    assert freeze["model_freeze_sha256"] == hashlib.sha256((CONTENT / "NEO_R1_MODEL_V1_FREEZE.json").read_bytes()).hexdigest()
    assert freeze["neo_v1_score_config_sha256"] == "0b33f7e4eb726079b163d4d6ec2cf8cfa4aec42218ee7609d8c538412a022643"
    assert freeze["tournament_master_dates_sha256"] == hashlib.sha256((CONTENT / "TOURNAMENT_MASTER_DATES_V1.json").read_bytes()).hexdigest()
    assert freeze["official_r1_evidence_sha256"] == hashlib.sha256(
        (CONTENT / f"NEO_KB_{GAME_CODE}_R1_OFFICIAL_RESULT_EVIDENCE_V1.json").read_bytes()
    ).hexdigest()


def test_prediction_values_sha256_matches_recomputation():
    freeze = _freeze()
    recomputed = hashlib.sha256(
        json.dumps(freeze["predictions"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert recomputed == freeze["prediction_values_sha256"]


def test_pre_frozen_artifact_still_byte_identical():
    actual_sha = hashlib.sha256((CONTENT / f"{GAME_CODE}_PRE_5PROB_V2_FROZEN.json").read_bytes()).hexdigest()
    assert actual_sha == "456d465e05f919c96ab827a68004aafb1ad971a7a128e6b44c461c9eb41fef36"


def test_round_update_and_pre_v2_not_modified():
    import subprocess

    for path in ("src/klpga/neo_win/round_update.py", "src/klpga/neo_win/pre_v2.py"):
        result = subprocess.run(
            ["git", "diff", "--stat", "HEAD", "--", path],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        assert result.stdout.strip() == ""
