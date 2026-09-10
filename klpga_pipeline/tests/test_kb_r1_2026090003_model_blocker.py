"""KB 2026090003 R1 LOCAL TAKEOVER -- regression coverage for the
Step-3 STOP decision.

The official R1 result reconciles perfectly against the frozen PRE
field (120 = 118 competitive + 2 WD, 0 duplicates, exact identity
match), but no approved code path exists to turn it into updated
CUT/TOP20/TOP10/TOP5/WIN: the model that actually produced KB's frozen
PRE (pre_v2.py / NEO_PRE_5PROB_V2) is closed-form and PRE-only by
design, and the only R1-capable model (round_update.py) needs raw
features neither pre_v2.py nor this sandbox has for KB. These tests
lock in the reconciliation and the frozen-PRE-untouched proof, and
guard against a future change silently fabricating R1 probabilities
without actually closing this gap.
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


def test_r1_evidence_reconciles_exactly_against_official_entry():
    ev = _load(f"NEO_KB_{GAME_CODE}_R1_OFFICIAL_RESULT_EVIDENCE_V1.json")
    entry = _load(f"{GAME_CODE}_ENTRY_SNAPSHOT.json")
    entry_ids = {e["player_id"] for e in entry["entries"]}

    assert ev["pre_official_entry_count"] == 120
    assert ev["official_wd_count"] == 2
    assert ev["r1_competitive_count"] == 118
    assert ev["duplicate_playerCode_count"] == 0

    player_ids = [p["playerCode"] for p in ev["players"]]
    assert len(player_ids) == 118
    assert len(set(player_ids)) == 118

    wd_ids = {w["playerCode"] for w in ev["official_wd"]}
    assert wd_ids == {"11374", "9788"}

    assert (set(player_ids) | wd_ids) == entry_ids


def test_r1_evidence_leader_matches_owner_claim():
    ev = _load(f"NEO_KB_{GAME_CODE}_R1_OFFICIAL_RESULT_EVIDENCE_V1.json")
    leader = ev["players"][0]
    assert leader["playerCode"] == "10586"
    assert leader["name"] == "홍진영2"
    assert leader["r1Score"] == 67
    assert leader["toPar"] == "-5"


def test_pre_frozen_artifact_is_byte_identical_to_before_r1_work():
    blocker = _load(f"KB_{GAME_CODE}_R1_MODEL_BLOCKER_V1.json")
    integrity = blocker["pre_frozen_artifact_integrity"]
    actual_sha = hashlib.sha256(
        (CONTENT / f"{GAME_CODE}_PRE_5PROB_V2_FROZEN.json").read_bytes()
    ).hexdigest()
    assert actual_sha == integrity["sha256_before_r1_work"] == integrity["sha256_after_r1_work"]
    assert integrity["byte_identical"] is True
    assert integrity["modified_by_this_task"] is False


def test_no_r1_probabilities_were_fabricated():
    """No frozen R1 snapshot exists -- generation was correctly blocked,
    never worked around with invented numbers."""
    assert not (CONTENT / f"{GAME_CODE}_R1_5PROB_FROZEN.json").exists()
    assert not (CONTENT / f"{GAME_CODE}_R1_5PROB_V1_FROZEN.json").exists()


def test_model_blocker_is_explicit_and_evidence_based():
    blocker = _load(f"KB_{GAME_CODE}_R1_MODEL_BLOCKER_V1.json")
    mb = blocker["MODEL_BLOCKER"]
    assert mb["status"] == "BLOCKED_MODEL_INCOMPATIBLE"
    assert len(mb["evidence"]) >= 3


def test_pre_v2_model_has_no_round1_input_mechanism():
    """Direct proof, not just citation: pre_v2.py truly has no R1/round
    handling anywhere in its source."""
    source = (ROOT / "src" / "klpga" / "neo_win" / "pre_v2.py").read_text(encoding="utf-8")
    for forbidden in ("round1", "r1_score", "round_1", "post_round"):
        assert forbidden not in source.lower()


def test_round_update_requires_fields_absent_from_kb_frozen_v2_snapshot():
    """Direct proof the two model lineages are incompatible: the fields
    round_update.py's bridge function reads from pre_snapshot.predictions
    are not present in KB's actual frozen V2 predictions."""
    frozen = _load(f"{GAME_CODE}_PRE_5PROB_V2_FROZEN.json")
    v2_fields = set(frozen["predictions"][0].keys())
    required_by_round_update = {"prior_avg_round_score_to_par", "neo_consistency_stddev"}
    assert required_by_round_update.isdisjoint(v2_fields)

    round_update_source = (ROOT / "src" / "klpga" / "neo_win" / "round_update.py").read_text(encoding="utf-8")
    assert "prior_avg_round_score_to_par" in round_update_source
    assert "neo_consistency_stddev" in round_update_source


def test_no_existing_script_bridges_pre_v2_into_round_update():
    for script in ("104_evaluate_pre_v2.py", "105_build_pre_v2.py"):
        text = (ROOT / "scripts" / script).read_text(encoding="utf-8")
        assert "round_update" not in text
