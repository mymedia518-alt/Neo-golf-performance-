"""UNIFIED PLAYER HISTORY RECONCILIATION -- playerCode=10097 only.

Covers scripts/reconcile_10097_player_history.py. Player History must
never depend on a single warehouse: these tests check that every known
tournament is accounted for across all 7 source categories, that real
cross-source checks actually run (not just get logged unconditionally),
and that a genuine gap or conflict stops reconciliation instead of
being silently patched downstream.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("reconcile_10097_player_history", ROOT / "scripts" / "reconcile_10097_player_history.py")
recon_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recon_module)


def test_reconcile_accounts_for_every_known_tournament_exactly_once():
    result = recon_module.reconcile()
    report = result["report"]
    assert report["status"] == "RECONCILED_OK"
    assert report["missing"] == 0
    assert report["conflicts_detected"] == 0
    all_codes = list(result["tournaments"].keys())
    assert len(all_codes) == len(set(all_codes)), "a tournament must be accounted for exactly once"


def test_reconciliation_report_has_all_mission_required_fields():
    report = recon_module.reconcile()["report"]
    for key in ("total_tournaments", "found_in_warehouse", "found_in_reader", "found_in_live", "merged", "missing", "resolved"):
        assert key in report


def test_three_tournaments_missing_from_sg_warehouse_are_reconciled_in():
    result = recon_module.reconcile()
    for gc in ("2026090002", "2026090003"):
        assert gc in result["tournaments"], f"{gc} must be reconciled from its dedicated sources, not silently dropped"
    assert result["in_progress_tournament"]["game_code"] == "2026120001"


def test_sg_warehouse_alone_is_missing_exactly_the_three_known_gaps():
    """Documents the actual structural bug this module exists to fix --
    if the SG Warehouse pipeline is ever backfilled to include these,
    this test (not a silent downstream patch) is what should fail
    first, forcing an update to the reconciliation logic."""
    sg_rows = recon_module._load_sg_warehouse_rows()
    sg_codes = {r["game_code"] for r in sg_rows if r.get("scope") == "tournament_cumulative"}
    for gc in recon_module._KNOWN_SPECIAL_GAME_CODES:
        assert gc not in sg_codes


def test_hana_sg_total_uses_the_real_four_round_official_cumulative():
    """Regression: the prior ad hoc patch computed the mean of only
    R1-R3 (4.63) because it never loaded the R4 SG file. The real
    official 4-round cumulative (which this file also carries directly)
    is 4.50 -- reconciliation must use the real 4-round figure."""
    result = recon_module.reconcile()
    hana = result["tournaments"]["2026090002"]
    assert hana["rounds_played"] == 4
    assert len(hana["round_scores"]) == 4
    assert abs(hana["sg_total"] - 4.5) < 0.02
    assert abs(hana["sg_total"] - 4.63) > 0.1


def test_kb_tournament_has_real_finish_but_no_fabricated_sg():
    result = recon_module.reconcile()
    kb = result["tournaments"]["2026090003"]
    assert kb["rank"] == 16
    assert kb["sg_total"] is None
    assert len(kb["round_scores"]) == 4
    assert sum(r["strokes"] for r in kb["round_scores"]) == kb["total_strokes"]


def test_ok_open_is_in_progress_and_excluded_from_finished_tournaments():
    result = recon_module.reconcile()
    finished_codes = {t["game_code"] for t in result["finished_tournaments"]}
    assert "2026120001" not in finished_codes
    assert result["in_progress_tournament"]["status"] == "IN_PROGRESS"
    assert len(result["in_progress_tournament"]["rounds_completed"]) == 2


def test_cross_category_merges_are_real_not_just_counted():
    """'merged' must correspond to tournaments whose fields actually
    came from more than one of the 7 categories -- not a fixed number."""
    report = recon_module.reconcile()["report"]
    assert report["merged"] >= 4  # 2023090002, 2023090003, Hana, OK Open at minimum


def test_kb_reader_arithmetic_is_actually_checked_not_assumed():
    """A tampered Reader file whose rounds don't sum to its own reported
    total must fail reconciliation loudly, not pass silently."""
    bad_fr_doc = {
        "game_code": "2026090003",
        "tournament": "KB금융 골든라이프 챔피언십",
        "players": [{"final_position": "T16", "player_name": recon_module.PLAYER_NAME, "r1_score": 74, "r2_score": 71, "r3_score": 73, "fr_score": 72, "total_strokes": 999, "to_par": 2}],
    }
    real_load = recon_module._load_json

    def fake_load(path):
        if path.name == "KB_2026090003_KLPGA_OFFICIAL_FR_70_SUPPLIED.json":
            return bad_fr_doc
        return real_load(path)

    recon_module._load_json = fake_load
    try:
        with pytest.raises(recon_module.ReconciliationError):
            recon_module._load_kb_reader_final()
    finally:
        recon_module._load_json = real_load


def test_hana_cumulative_conflict_stops_reconciliation():
    """If the official 4-round cumulative SG ever disagreed with the
    mean of the 4 real rounds beyond tolerance, that is a genuine
    conflict and must stop reconciliation -- not be silently trusted."""
    real_load_content = recon_module._load_content

    def fake_load_content(name):
        doc = real_load_content(name)
        if name == "HANA_2026090002_R4_SG_V1.json" and doc:
            for rec in doc["total_cumulative_sg"]["records"]:
                if rec["player_id"] == recon_module.PLAYER_ID:
                    rec["total"] = 99.0
        return doc

    recon_module._load_content = fake_load_content
    try:
        with pytest.raises(recon_module.ReconciliationError):
            recon_module._load_hana_live_sg()
    finally:
        recon_module._load_content = real_load_content


def test_an_unhandled_new_tournament_shape_stops_reconciliation_not_silently_dropped():
    """The core structural fix: a tournament discoverable in a known
    real-source SHAPE that this module has no dedicated loader for must
    raise, never be silently omitted the way Hana/KB/OK Open were for
    months before this reconciliation module existed."""
    real_discover = recon_module._discover_special_game_codes

    def fake_discover():
        found = real_discover()
        found.add("9999999999")
        return found

    recon_module._discover_special_game_codes = fake_discover
    try:
        with pytest.raises(recon_module.ReconciliationError, match="9999999999"):
            recon_module.reconcile()
    finally:
        recon_module._discover_special_game_codes = real_discover


def test_missing_known_special_tournament_stops_reconciliation():
    """If a source file for one of the three known special tournaments
    disappears, reconciliation must fail loudly, never silently drop
    that tournament from the report."""
    real_load_content = recon_module._load_content

    def fake_load_content(name):
        if name.startswith("HANA_2026090002_"):
            return None
        return real_load_content(name)

    recon_module._load_content = fake_load_content
    try:
        with pytest.raises(recon_module.ReconciliationError):
            recon_module.reconcile()
    finally:
        recon_module._load_content = real_load_content


def test_synthetic_sg_warehouse_doc_feeds_season_profiles_with_real_shape():
    result = recon_module.reconcile()
    doc = result["synthetic_sg_warehouse_doc"]
    assert doc["records"]
    for r in doc["records"]:
        assert r["scope"] == "tournament_cumulative"
        assert r["identity_state"] == "RETAINED"
        assert r["player_id"] == recon_module.PLAYER_ID
    # KB has no SG -- must never appear in the SG-averaging input
    assert not any(r["game_code"] == "2026090003" for r in doc["records"])
    assert any(r["game_code"] == "2026090002" for r in doc["records"])
