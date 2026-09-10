"""KB 2026090003 R1 -- KB application blocker regression coverage.

NEO_R1_MODEL_V1 passed validation (see test_r1_model_v1.py /
NEO_R1_MODEL_V1_FREEZE.json) but cannot be applied to KB because its
pre_score feature (NEO Ranking V1's NEO_V1_score) has no computable
value for KB's players -- proven here by direct inspection of the only
source that ever produces NEO_V1_score, not merely asserted. These
tests guard against a future change silently fabricating a KB
application by substituting an unvalidated feature or refitting the
frozen coefficients.
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


def _blocker() -> dict:
    return _load(f"KB_{GAME_CODE}_R1_KB_APPLICATION_BLOCKER_V1.json")


def test_status_is_kb_application_blocked():
    assert _blocker()["status"] == "KB_APPLICATION_BLOCKED"


def test_kb_absent_from_the_only_source_of_neo_v1_score():
    backtest = _load("NEO_RANKING_V1_REDTEAM_BACKTEST.json")
    event_ids = {ev["event"] for ev in backtest["events"]}
    assert GAME_CODE not in event_ids
    assert GAME_CODE not in json.dumps(backtest)


def test_script_92_reads_neo_score_from_backtest_not_computing_it():
    source = (ROOT / "scripts" / "92_build_historical_truth_warehouse.py").read_text(encoding="utf-8")
    assert 'r["neo_score"]' in source
    assert 'r["neo_rank"]' in source


def test_no_kb_r1_five_tier_predictions_were_generated():
    for name in (
        f"{GAME_CODE}_R1_5PROB_FROZEN.json",
        f"{GAME_CODE}_R1_5PROB_V1_FROZEN.json",
        f"KB_{GAME_CODE}_R1_5PROB_FREEZE_V1.json",
    ):
        assert not (CONTENT / name).exists()
    assert _blocker()["no_probabilities_generated_for_kb"] is True


def test_pre_frozen_artifact_still_byte_identical():
    actual_sha = hashlib.sha256((CONTENT / f"{GAME_CODE}_PRE_5PROB_V2_FROZEN.json").read_bytes()).hexdigest()
    expected = "456d465e05f919c96ab827a68004aafb1ad971a7a128e6b44c461c9eb41fef36"
    assert actual_sha == expected
    integrity = _blocker()["pre_frozen_artifact_integrity"]
    assert integrity["sha256_before_this_task"] == integrity["sha256_after_this_task"] == expected


def test_pre_v2_and_round_update_modules_not_modified():
    import subprocess

    for path in ("src/klpga/neo_win/pre_v2.py", "src/klpga/neo_win/round_update.py"):
        result = subprocess.run(
            ["git", "diff", "--stat", "HEAD", "--", path],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        assert result.stdout.strip() == "", f"{path} was modified"


def test_production_reference_unchanged():
    prod = _blocker()["production_untouched"]
    assert prod["branch"] == "neo-website-v2"
    assert prod["commit"] == "15d43a6a5a65f166d38fcf242453cba22f67af1d"
    assert prod["modified_by_this_task"] is False


def test_model_freeze_and_blocker_are_consistent():
    freeze = _load("NEO_R1_MODEL_V1_FREEZE.json")
    assert freeze["model_id"] == _blocker()["model_id"] == "NEO_R1_MODEL_V1"
    assert freeze["publication_decision_for_model_itself"] == "MODEL_VALIDATION_PASS"
