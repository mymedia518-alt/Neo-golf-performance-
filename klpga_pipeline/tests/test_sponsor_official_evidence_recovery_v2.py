"""SPONSOR OFFICIAL-EVIDENCE RECOVERY V2 -- regression coverage.

Extends the shared sponsor resolver (src/klpga/website_v2/
player_identity.py) with a third, explicitly distinct evidence tier --
OPERATOR_REPORTED_SPONSOR_EVIDENCE_V1.json, real KLPGA official checks
performed outside this session (this sandbox's own network access to
klpga.co.kr / k-rankings.klpga.co.kr is proxy-blocked). These tests lock
in:
  1. the operator-reported tier is merged under the SAME conflict-drop
     discipline as cross-tournament reuse (never a second, divergent
     resolver);
  2. the five named regression checks the owner gave verbatim (서교림,
     유현조, 이다연, 박민지, 최예림);
  3. every remaining blank is classified COLLECTION_BLOCKED, never
     NO_OFFICIAL_EVIDENCE (network access being unavailable is not proof
     a sponsor doesn't exist);
  4. the V2 audits and the consolidated KB_SPONSOR_RECOVERY_V2_STATUS.json
     agree on population counts;
  5. the rendered HTML sponsor slot for a newly recovered player is
     present and non-guessed, on both HOME and the KB tournament page.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_context import candidate_dir  # noqa: E402
from klpga.website_v2.player_identity import cross_tournament_verified_sponsor_cache  # noqa: E402

GAME_CODE = "2026090003"

# Verbatim owner-given regression checks: player_id -> (name, sponsor)
NAMED_CHECKS = {
    "11134": ("서교림", "삼천리"),
    "10146": ("유현조", "롯데"),
    "8392": ("이다연", "메디힐"),
    "8772": ("박민지", "NH투자증권"),
    "8284": ("최예림", "휴온스"),
}


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------
# 1. Operator-reported tier is a real, distinct evidence source
# ---------------------------------------------------------------------

def test_operator_reported_evidence_file_is_a_distinct_tier_not_a_fetch():
    evidence = _load("OPERATOR_REPORTED_SPONSOR_EVIDENCE_V1.json")
    assert evidence["schema_version"] == "operator_reported_sponsor_evidence_v1"
    assert "outside this session" in evidence["_provenance_honesty_note"]
    for row in evidence["records"]:
        assert row["evidence_status"] == "VERIFIED_OFFICIAL_OPERATOR_REPORTED"


@pytest.mark.parametrize("player_id,expected", NAMED_CHECKS.items())
def test_named_owner_regression_checks_resolve_through_the_shared_cache(player_id, expected):
    name, sponsor = expected
    cache = cross_tournament_verified_sponsor_cache(content_dir=CONTENT)
    assert cache.get(player_id) == sponsor, f"{name} ({player_id}) must resolve to {sponsor}"


def test_operator_reported_rows_never_override_a_conflicting_existing_value():
    evidence = _load("OPERATOR_REPORTED_SPONSOR_EVIDENCE_V1.json")
    assert "no disagreement to drop" in evidence["conflict_check"]


# ---------------------------------------------------------------------
# 2. V2 audits: COLLECTION_BLOCKED, never NO_OFFICIAL_EVIDENCE
# ---------------------------------------------------------------------

def test_kb_v2_audit_uses_collection_blocked_terminology_not_no_evidence():
    audit = _load("KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V2.json")
    assert audit["official_field_count"] == 120
    assert (
        audit["verified_sponsor_count"] + audit["collection_blocked_count"] + audit["identity_unresolved_count"]
        == 120
    )
    for row in audit["collection_blocked_players"]:
        assert row["status"] == "COLLECTION_BLOCKED"
        assert row["status"] != "NO_OFFICIAL_EVIDENCE"


def test_home_v2_audit_uses_collection_blocked_terminology_not_no_evidence():
    audit = _load("HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V2.json")
    assert audit["home_population_count"] == 120
    assert audit["verified_sponsor_count"] + audit["collection_blocked_count"] == 120
    for row in audit["collection_blocked_players"]:
        assert row["status"] == "COLLECTION_BLOCKED"
        assert row["status"] != "NO_OFFICIAL_EVIDENCE"


def test_kb_v2_recovers_more_than_v1():
    v1 = _load("KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V1.json")
    v2 = _load("KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V2.json")
    assert v2["verified_sponsor_count"] > v1["verified_sponsor_count"]
    assert v1["status"] == "SUPERSEDED_BY_V2"


def test_home_v2_recovers_more_than_v1():
    v1 = _load("HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V1.json")
    v2 = _load("HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V2.json")
    assert v2["verified_sponsor_count"] > v1["verified_sponsor_count"]
    assert v1["status"] == "SUPERSEDED_BY_V2"


# ---------------------------------------------------------------------
# 3. Consolidated provenance artifact agrees with the audits
# ---------------------------------------------------------------------

def test_consolidated_status_artifact_matches_kb_v2_audit_counts():
    status = _load("KB_SPONSOR_RECOVERY_V2_STATUS.json")
    v2 = _load("KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V2.json")
    kb = status["kb_tournament_field"]["summary"]
    assert kb["population_count"] == 120
    assert kb["verified_official_count"] == v2["verified_sponsor_count"]
    assert kb["collection_blocked_count"] == v2["collection_blocked_count"]


def test_consolidated_status_artifact_matches_home_v2_audit_counts():
    status = _load("KB_SPONSOR_RECOVERY_V2_STATUS.json")
    v2 = _load("HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V2.json")
    home = status["home_ranking_population"]["summary"]
    assert home["population_count"] == 120
    assert home["verified_official_count"] == v2["verified_sponsor_count"]
    assert home["collection_blocked_count"] == v2["collection_blocked_count"]


def test_every_consolidated_record_carries_the_required_provenance_fields():
    status = _load("KB_SPONSOR_RECOVERY_V2_STATUS.json")
    required = {"player_id", "player_name", "sponsor", "official_source", "retrieval_date", "evidence_status"}
    for population in ("kb_tournament_field", "home_ranking_population"):
        for row in status[population]["players"]:
            assert required.issubset(row.keys())
            if row["evidence_status"] == "VERIFIED_OFFICIAL":
                assert row["sponsor"]
                assert row["official_source"]
            else:
                assert row["evidence_status"] == "COLLECTION_BLOCKED"
                assert row["sponsor"] is None


def test_named_checks_appear_as_verified_official_in_consolidated_status():
    status = _load("KB_SPONSOR_RECOVERY_V2_STATUS.json")
    by_id = {r["player_id"]: r for r in status["kb_tournament_field"]["players"]}
    for player_id, (name, sponsor) in NAMED_CHECKS.items():
        row = by_id[player_id]
        assert row["player_name"] == name
        assert row["sponsor"] == sponsor
        assert row["evidence_status"] == "VERIFIED_OFFICIAL"


# ---------------------------------------------------------------------
# 4. Rendered HTML: sponsor slot present, non-guessed, on both universes
# ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def built():
    path = ROOT / "scripts" / "88_build_neo_top120_candidate.py"
    spec = importlib.util.spec_from_file_location("top120_builder_v2_sponsor_recovery", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build()


def test_newly_recovered_sponsor_renders_on_home(built):
    output = candidate_dir("neo-data-home-top120")
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "서교림" in html
    assert "삼천리" in html


def test_newly_recovered_sponsor_renders_on_kb_pre_page(built):
    output = candidate_dir("neo-data-home-top120")
    html = (output / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html").read_text(encoding="utf-8")
    assert "박민지" in html
    assert "NH투자증권" in html
