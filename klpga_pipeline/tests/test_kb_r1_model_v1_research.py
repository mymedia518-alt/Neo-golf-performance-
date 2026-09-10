"""NEO GOLF DATA -- R1 MODEL V1 RESEARCH & VALIDATION.

Locks in the decisive finding: the only leakage-safe historical R1
performance source (round-1 Strokes Gained records) is present for
100% of eventual cut-survivors and only ~2.2% of eventual cut-missers
across the full 82-tournament historical corpus -- a structural,
corpus-construction artifact, not a fixable sampling gap. This blocks
CUT-tier validation, which blocks the required probability coherence
stack (0<=WIN<=TOP5<=TOP10<=TOP20<=CUT<=1), so the publication decision
is DATA_BLOCKED. These tests guard against a future change silently
fabricating a NEO_R1_MODEL_V1 freeze or KB predictions without actually
resolving this gap, and guard the strict KB holdout.
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


def _research() -> dict:
    return _load(f"KB_{GAME_CODE}_R1_MODEL_V1_RESEARCH_V1.json")


def test_publication_decision_is_data_blocked():
    rec = _research()
    assert rec["section_16_publication_decision"] == "DATA_BLOCKED"


def test_kb_never_appears_in_historical_corpus():
    """Direct proof of the strict holdout required by task section 2,
    not merely a claim inside the evidence artifact."""
    tw = _load("NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json")
    wh = _load("historical_sg_warehouse.json")
    tw_game_codes = {r["game_code"] for r in tw["records"]}
    wh_game_codes = {r["game_code"] for r in wh["records"]}
    assert GAME_CODE not in tw_game_codes
    assert GAME_CODE not in wh_game_codes


def test_missingness_proof_matches_real_source_files():
    """Re-derive the contingency table from the real source files -- the
    evidence artifact's numbers must not be hand-typed/fabricated."""
    tw = _load("NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json")
    wh = _load("historical_sg_warehouse.json")
    r1 = [r for r in wh["records"] if r.get("scope") == "single_round" and r.get("round") == 1]
    r1_index = {(r["game_code"], r["player_id"]) for r in r1}

    tw_recs = tw["records"]
    cut_true = [r for r in tw_recs if r["outcome"]["made_cut"]]
    cut_false = [r for r in tw_recs if not r["outcome"]["made_cut"]]
    cut_true_matched = [r for r in cut_true if (r["game_code"], r["player_id"]) in r1_index]
    cut_false_matched = [r for r in cut_false if (r["game_code"], r["player_id"]) in r1_index]

    proof = _research()["section_3_5_missingness_analysis"]["contingency"]
    assert proof["made_cut_true_total"] == len(cut_true) == 4687
    assert proof["made_cut_true_matched_to_r1_sg"] == len(cut_true_matched) == 4687
    assert proof["made_cut_false_total"] == len(cut_false) == 3143
    assert proof["made_cut_false_matched_to_r1_sg"] == len(cut_false_matched) == 68

    # The decisive asymmetry itself, computed fresh, not read back from the artifact.
    assert len(cut_true_matched) / len(cut_true) == 1.0
    assert len(cut_false_matched) / len(cut_false) < 0.03


def test_historical_dataset_coverage_matches_real_source_files():
    tw = _load("NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json")
    coverage = _research()["section_3_historical_dataset"]["coverage"]
    assert coverage["tournament_count"] == len({r["game_code"] for r in tw["records"]}) == 82
    assert coverage["player_event_count_total_in_truth_warehouse"] == len(tw["records"]) == 7830


def test_no_neo_r1_model_v1_was_frozen():
    """The whole point of DATA_BLOCKED: no model freeze, no coefficients,
    no simulation parameters were ever written."""
    for pattern in ("NEO_R1_MODEL_V1*.json", "*R1_MODEL_V1_FROZEN*.json"):
        assert list(CONTENT.glob(pattern)) == [], f"unexpected frozen-model artifact matching {pattern}"


def test_no_kb_r1_five_tier_predictions_were_generated():
    """No CUT/TOP20/TOP10/TOP5/WIN numbers were fabricated for KB's 118
    R1-eligible players by this task."""
    for name in (
        f"{GAME_CODE}_R1_5PROB_FROZEN.json",
        f"{GAME_CODE}_R1_5PROB_V1_FROZEN.json",
        f"KB_{GAME_CODE}_R1_5PROB_FREEZE_V1.json",
    ):
        assert not (CONTENT / name).exists()


def test_pre_frozen_artifact_still_byte_identical():
    actual_sha = hashlib.sha256(
        (CONTENT / f"{GAME_CODE}_PRE_5PROB_V2_FROZEN.json").read_bytes()
    ).hexdigest()
    expected = "456d465e05f919c96ab827a68004aafb1ad971a7a128e6b44c461c9eb41fef36"
    assert actual_sha == expected
    integrity = _research()["pre_frozen_artifact_integrity"]
    assert integrity["sha256_before_this_task"] == integrity["sha256_after_this_task"] == expected


def test_round_update_module_was_not_modified_by_this_task():
    import subprocess

    result = subprocess.run(
        ["git", "diff", "--stat", "HEAD", "--", "src/klpga/neo_win/round_update.py"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == ""


def test_round_update_is_documented_as_legacy_per_task_wording():
    legacy = _research()["section_17_legacy_preservation"]["round_update.py"]
    assert legacy["classification"] == "LEGACY / BETA R1 MODEL, not compatible with KB 2026090003 production inputs"
    assert legacy["modified_by_this_task"] is False


def test_no_sqlite_corpus_exists_in_this_worktree():
    hits = list(ROOT.parent.rglob("*.sqlite")) + list(ROOT.parent.rglob("*.db"))
    assert hits == []


def test_r1_feature_recovery_and_model_blocker_artifacts_still_present_and_unaltered():
    """This task extends, never supersedes-by-deletion, the two prior
    blocker findings from the same investigation thread."""
    blocker = _load(f"KB_{GAME_CODE}_R1_MODEL_BLOCKER_V1.json")
    assert blocker["MODEL_BLOCKER"]["status"] == "BLOCKED_MODEL_INCOMPATIBLE"
    recovery = _load(f"KB_{GAME_CODE}_R1_FEATURE_RECOVERY_V1.json")
    assert recovery["FEATURE_RECOVERY_STATUS"] == "BLOCKED_DEFINITION_UNRECOVERABLE"


def test_production_branch_reference_unchanged():
    prod = _research()["production_untouched"]
    assert prod["branch"] == "neo-website-v2"
    assert prod["commit"] == "15d43a6a5a65f166d38fcf242453cba22f67af1d"
    assert prod["modified_by_this_task"] is False
