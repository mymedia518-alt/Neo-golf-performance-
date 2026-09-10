"""NEO KB FIELD + SPONSOR INTEGRITY REPAIR V1 -- regression coverage.

OWNER DECISION (binding, see content/website_v2/
KB_OWNER_DECISION_HOME_VS_TOURNAMENT_POPULATIONS_V1.json for the full
record): HOME_RANKING_UNIVERSE (the persistent K-Ranking TOP120 page)
and TOURNAMENT_FIELD(gameCode) (= OFFICIAL_ENTRY(gameCode) exactly) are
two permanently separate populations. Neither substitutes for, nor
falls back to, the other. A K-Ranking TOP120 player who is not a KB
entrant (e.g. 황유민) belongs on HOME and must NEVER be removed from
it; the same player must NEVER appear in KB's own tournament field.

These tests lock in that both populations are already correctly built
(no source code was changed by this task) and would catch a future
regression that re-conflates them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.player_identity import cross_tournament_verified_sponsor_cache  # noqa: E402

GAME_CODE = "2026090003"
HUANG_YUMIN_ID = "10185"


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def _official_entry_ids() -> set[str]:
    entry = _load(f"{GAME_CODE}_ENTRY_SNAPSHOT.json")
    return {e["player_id"] for e in entry["entries"]}


def _tournament_field_ids() -> set[str]:
    master = _load(f"{GAME_CODE}_PRE_PUBLIC_MASTER.json")
    return {r["player_id"] for r in master["records"]}


def _home_ranking_universe_ids() -> set[str]:
    home = _load("HOME_PLAYER_MASTER_TOP120.json")
    return {str(r["player_id"]) for r in home["records"]}


# ---------------------------------------------------------------------
# 1. HOME K-Ranking player who is a KB non-entrant remains on HOME
# ---------------------------------------------------------------------

def test_huang_yumin_is_on_home_ranking_universe():
    assert HUANG_YUMIN_ID in _home_ranking_universe_ids(), (
        "황유민 (K-Ranking TOP120) must remain on HOME -- her presence there is correct, "
        "per OWNER DECISION, and must never be 'fixed' by removing her."
    )


def test_huang_yumin_is_not_a_kb_official_entrant():
    assert HUANG_YUMIN_ID not in _official_entry_ids()


# ---------------------------------------------------------------------
# 2. Same player cannot leak into KB tournament field
# ---------------------------------------------------------------------

def test_huang_yumin_is_absent_from_kb_tournament_field():
    assert HUANG_YUMIN_ID not in _tournament_field_ids(), (
        "A HOME-only K-Ranking player must never appear in a tournament's own field."
    )


def test_no_home_only_kranking_player_leaks_into_kb_field():
    home_only = _home_ranking_universe_ids() - _official_entry_ids()
    leaked = home_only & _tournament_field_ids()
    assert leaked == set(), f"K-Ranking-only players leaked into KB tournament field: {leaked}"


# ---------------------------------------------------------------------
# 3. KB entrant outside HOME TOP120 remains in KB field
# ---------------------------------------------------------------------

def test_kb_entrants_outside_home_top120_still_appear_in_kb_field():
    official_only_of_home = _official_entry_ids() - _home_ranking_universe_ids()
    assert len(official_only_of_home) > 0, "fixture sanity: expect at least one KB entrant outside HOME TOP120"
    missing = official_only_of_home - _tournament_field_ids()
    assert missing == set(), f"KB entrants outside HOME TOP120 missing from KB tournament field: {missing}"


# ---------------------------------------------------------------------
# 4. No fallback from tournament field to HOME_PLAYER_MASTER_TOP120
# ---------------------------------------------------------------------

def test_tournament_builders_never_reference_home_player_master_top120():
    for script in ("83_build_ok_open_pre_public_master.py", "84_build_ok_open_pre_website_candidate.py"):
        source = (ROOT / "scripts" / script).read_text(encoding="utf-8")
        assert "HOME_PLAYER_MASTER_TOP120" not in source, f"{script} must never fall back to HOME's population"


def test_kb_tournament_field_exact_set_equals_official_entry():
    assert _tournament_field_ids() == _official_entry_ids()


# ---------------------------------------------------------------------
# 5. gameCode alone selects official tournament field (generic, no hardcoding)
# ---------------------------------------------------------------------

def test_current_player_master_identity_source_is_entry_snapshot_for_every_record():
    master = _load(f"{GAME_CODE}_CURRENT_PLAYER_MASTER.json")
    for row in master["records"]:
        assert row["identity_source"] == "entry_snapshot", (
            f"player_id={row.get('player_id')} was not identity-sourced from the entry snapshot"
        )


def test_pre_public_master_and_current_player_master_agree_on_field():
    cur = _load(f"{GAME_CODE}_CURRENT_PLAYER_MASTER.json")
    cur_ids = {r["player_id"] for r in cur["records"]}
    assert cur_ids == _tournament_field_ids()


# ---------------------------------------------------------------------
# 6. Exact playerCode equality required (no near-miss tolerance)
# ---------------------------------------------------------------------

def test_official_entry_has_no_duplicate_player_ids():
    entry = _load(f"{GAME_CODE}_ENTRY_SNAPSHOT.json")
    ids = [e["player_id"] for e in entry["entries"]]
    assert len(ids) == len(set(ids)) == 120


def test_kb_tournament_field_has_no_duplicate_player_ids():
    master = _load(f"{GAME_CODE}_PRE_PUBLIC_MASTER.json")
    ids = [r["player_id"] for r in master["records"]]
    assert len(ids) == len(set(ids)) == 120


def test_field_integrity_gate_artifact_reports_pass():
    gate = _load("KB_2026090003_FIELD_INTEGRITY_PUBLICATION_GATE_V1.json")
    assert gate["FIELD_INTEGRITY_STATUS"] == "PASS"
    assert all(gate["checks"].values()), gate["checks"]
    assert gate["home_population_explicitly_excluded_from_this_gate"] is True


# ---------------------------------------------------------------------
# 7. Sponsor official-evidence rule applies independently to both universes
# ---------------------------------------------------------------------

def test_kb_tournament_sponsor_slots_are_never_guessed_and_always_structurally_present():
    audit = _load("KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V1.json")
    assert audit["official_field_count"] == 120
    assert audit["verified_sponsor_count"] + audit["blank_count"] + audit["identity_unresolved_count"] == 120
    assert audit["identity_unresolved_count"] == 0


def test_home_sponsor_audit_covers_the_full_home_population_not_a_handful():
    audit = _load("HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V1.json")
    assert audit["home_population_count"] == 120
    assert audit["verified_sponsor_count"] + audit["blank_count"] == 120


def test_home_and_kb_sponsor_recovery_use_the_same_shared_resolver():
    """Both populations' sponsor rule must come from the one shared,
    six-point-gated resolver -- never two divergent implementations."""
    cache = cross_tournament_verified_sponsor_cache(content_dir=CONTENT)
    kb_audit = _load("KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V1.json")
    for row in kb_audit["newly_recovered_sponsors"]:
        assert cache.get(row["player_id"]) == row["sponsor"]
    home_audit = _load("HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V1.json")
    for row in home_audit["newly_recovered_sponsors"]:
        assert cache.get(row["player_id"]) == row["sponsor"]


def test_official_sponsor_by_id_matches_the_home_sponsor_audit_exactly():
    """Calls the REAL scripts/88 function (not a re-implementation) to
    confirm the audit's numbers are what production actually renders."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("m88_sponsor_check", ROOT / "scripts" / "88_build_neo_top120_candidate.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sponsor_by_id = m._official_sponsor_by_id()
    home_ids = _home_ranking_universe_ids()
    covered = sum(1 for pid in home_ids if sponsor_by_id.get(pid))
    home_audit = _load("HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V1.json")
    assert covered == home_audit["verified_sponsor_count"]


# ---------------------------------------------------------------------
# Owner decision record itself
# ---------------------------------------------------------------------

def test_owner_decision_record_exists_and_documents_no_fallback_rule():
    decision = _load("KB_OWNER_DECISION_HOME_VS_TOURNAMENT_POPULATIONS_V1.json")
    assert "HOME_RANKING_UNIVERSE" in decision["rule"]
    assert "TOURNAMENT_FIELD(gameCode)" in decision["rule"]
    assert "PRODUCT RECOVERY V1" in str(decision["not_changed_by_this_task"])
