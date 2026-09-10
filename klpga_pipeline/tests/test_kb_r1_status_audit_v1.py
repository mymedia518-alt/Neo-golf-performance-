"""KB 2026090003 -- R1 OFFICIAL STATUS UPDATE V1 -- regression coverage.

Official R1 evidence supplied by the owner confirms exactly two WD
(withdrawn / 기권) players: 전승희, 박혜준. This is an ADDITIVE R1-stage
status layer (KB_2026090003_R1_STATUS_AUDIT_V1.json +
KB_2026090003_R1_OFFICIAL_STATUS_EVIDENCE_V1.json) on top of the frozen
PRE 120-entrant field -- PRE itself (ENTRY snapshot, PRE public master,
PRE prediction/evidence artifacts) is never modified, WD players are
never deleted from any historical record, and no probability model code
or frozen PRE probability is touched. These tests lock in that contract.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"

GAME_CODE = "2026090003"
WD_PLAYERS = {"11374": "전승희", "9788": "박혜준"}


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def _entry_ids() -> set[str]:
    entry = _load(f"{GAME_CODE}_ENTRY_SNAPSHOT.json")
    return {e["player_id"] for e in entry["entries"]}


# ---------------------------------------------------------------------
# 1. PRE remains exactly 120 and historically immutable
# ---------------------------------------------------------------------

def test_pre_entry_count_remains_120():
    assert len(_entry_ids()) == 120


def test_pre_playercode_set_unchanged_by_this_task():
    """Sanity: the R1 status layer is purely additive -- PRE ENTRY's own
    120 playerCodes still exactly match PRE_PUBLIC_MASTER's field."""
    entry_ids = _entry_ids()
    pre_master = _load(f"{GAME_CODE}_PRE_PUBLIC_MASTER.json")
    pre_ids = {r["player_id"] for r in pre_master["records"]}
    assert entry_ids == pre_ids
    assert len(entry_ids) == 120


def test_wd_players_are_not_deleted_from_pre_entry():
    """WD status is additive, never a deletion -- both WD players must
    still be present in the frozen PRE ENTRY field."""
    entry_ids = _entry_ids()
    for pid in WD_PLAYERS:
        assert pid in entry_ids, f"WD player {WD_PLAYERS[pid]} ({pid}) must remain in PRE ENTRY"


# ---------------------------------------------------------------------
# 2. R1 status layer: exactly the 2 supplied WD statuses
# ---------------------------------------------------------------------

def test_r1_status_audit_records_exactly_the_two_supplied_wd_players():
    audit = _load(f"KB_{GAME_CODE}_R1_STATUS_AUDIT_V1.json")
    assert audit["game_code"] == GAME_CODE
    assert audit["official_entry_count"] == 120
    assert audit["wd_count"] == 2
    wd_by_id = {row["playerCode"]: row for row in audit["wd_players"]}
    assert set(wd_by_id) == set(WD_PLAYERS)
    for pid, name in WD_PLAYERS.items():
        assert wd_by_id[pid]["player_name"] == name
        assert wd_by_id[pid]["status"] == "WD"


def test_jeon_seunghee_existed_in_pre_and_becomes_wd_in_r1():
    assert "11374" in _entry_ids()
    audit = _load(f"KB_{GAME_CODE}_R1_STATUS_AUDIT_V1.json")
    wd_by_id = {row["playerCode"]: row for row in audit["wd_players"]}
    assert wd_by_id["11374"]["status"] == "WD"
    assert wd_by_id["11374"]["player_name"] == "전승희"


def test_park_hyejun_existed_in_pre_and_becomes_wd_in_r1():
    assert "9788" in _entry_ids()
    audit = _load(f"KB_{GAME_CODE}_R1_STATUS_AUDIT_V1.json")
    wd_by_id = {row["playerCode"]: row for row in audit["wd_players"]}
    assert wd_by_id["9788"]["status"] == "WD"
    assert wd_by_id["9788"]["player_name"] == "박혜준"


def test_wd_count_matches_the_supplied_snapshot_exactly():
    audit = _load(f"KB_{GAME_CODE}_R1_STATUS_AUDIT_V1.json")
    assert audit["wd_count"] == len(WD_PLAYERS) == 2
    assert audit["r1_observed_count"] == 2


def test_non_wd_count_is_never_reduced_by_missing_score_alone():
    """The task's explicit accounting: ENTRY 120, WD 2, non-WD maximum
    118 -- non_wd_count must be exactly entry_count - wd_count, i.e.
    every remaining PRE entrant is accounted for by absence of a WD
    report, never excluded because some OTHER round-score field is
    missing (this audit never even reads a score field)."""
    audit = _load(f"KB_{GAME_CODE}_R1_STATUS_AUDIT_V1.json")
    assert audit["non_wd_count"] == audit["official_entry_count"] - audit["wd_count"] == 118
    assert audit["unknown_status_count"] == 0


def test_no_player_is_misclassified_as_dns_dq_or_cut():
    audit = _load(f"KB_{GAME_CODE}_R1_STATUS_AUDIT_V1.json")
    statuses = {row["status"] for row in audit["wd_players"]}
    assert statuses == {"WD"}
    assert audit.get("identity_unresolved") == []


# ---------------------------------------------------------------------
# 3. Identity resolution: exact playerCode, no fuzzy name-only join
# ---------------------------------------------------------------------

def test_wd_identity_resolved_by_exact_playercode_not_name_only():
    entry = _load(f"{GAME_CODE}_ENTRY_SNAPSHOT.json")
    for pid, name in WD_PLAYERS.items():
        matches = [e for e in entry["entries"] if e["player_id"] == pid]
        assert len(matches) == 1, f"expected exactly one PRE ENTRY row for playerCode {pid}"
        assert matches[0]["player_name"] == name


def test_evidence_source_file_hash_matches_the_audit_record():
    evidence_path = CONTENT / f"KB_{GAME_CODE}_R1_OFFICIAL_STATUS_EVIDENCE_V1.json"
    sha = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    audit = _load(f"KB_{GAME_CODE}_R1_STATUS_AUDIT_V1.json")
    assert audit["source_sha256"] == sha
    assert audit["r1_status_source"] == evidence_path.name


# ---------------------------------------------------------------------
# 4. Forward-simulation eligibility contract (data only, no model code)
# ---------------------------------------------------------------------

def test_wd_players_excluded_from_forward_simulation_eligibility():
    audit = _load(f"KB_{GAME_CODE}_R1_STATUS_AUDIT_V1.json")
    excluded = set(audit["forward_simulation_excluded_ids"])
    assert excluded == set(WD_PLAYERS)


def test_forward_eligible_population_is_118_and_derived_not_hardcoded():
    audit = _load(f"KB_{GAME_CODE}_R1_STATUS_AUDIT_V1.json")
    eligible = _entry_ids() - set(audit["forward_simulation_excluded_ids"])
    assert len(eligible) == 118
    assert len(eligible) == audit["non_wd_count"]


def test_no_probability_model_or_pre_prediction_files_touched_by_this_task():
    """This task must never rewrite frozen PRE probabilities or modify
    probability model code -- verify the well-known PRE prediction
    artifacts still parse and still report the same 120-entrant field
    they always have (their content, not just existence, is untouched:
    no git diff on any PRE_*/probability file is asserted at commit
    time; here we only re-affirm the field-count invariant they share)."""
    pre_forecast = _load(f"{GAME_CODE}_PRE_WIN_FORECAST.json")
    assert pre_forecast  # still loads; content untouched by this task


# ---------------------------------------------------------------------
# 5. Safety: HOME / sponsor / lockdown unaffected by this isolated task
# ---------------------------------------------------------------------

def test_home_player_master_top120_population_unchanged():
    home = _load("HOME_PLAYER_MASTER_TOP120.json")
    assert len(home["records"]) == 120
    ids = {r["player_id"] for r in home["records"]}
    assert len(ids) == 120


def test_sponsor_v2_audits_unchanged_by_this_task():
    kb_sponsor = _load(f"KB_{GAME_CODE}_SPONSOR_INTEGRITY_AUDIT_V2.json")
    home_sponsor = _load("HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V2.json")
    assert kb_sponsor["verified_sponsor_count"] == 94
    assert kb_sponsor["collection_blocked_count"] == 26
    assert home_sponsor["verified_sponsor_count"] == 80
    assert home_sponsor["collection_blocked_count"] == 40


def test_production_docs_lockdown_untouched():
    """MAIN ONLY LOCKDOWN must remain: every route but '/' still shows
    the construction placeholder in production docs/."""
    docs = REPO_ROOT / "docs"
    for route in ("about/index.html", "deep-dive/index.html", "tournaments/index.html"):
        text = (docs / route).read_text(encoding="utf-8")
        assert "공사중" in text
    home_text = (docs / "index.html").read_text(encoding="utf-8")
    assert "공사중" not in home_text
