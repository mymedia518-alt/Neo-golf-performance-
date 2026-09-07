"""Tests for scripts/106_round_count_mismatch_diagnostic.py and the fixed
hard-gate wording in scripts/105_round_count_audit_v2.py. Uses constructed
fixture data (deterministic, no real network/archive dependency) to
exercise the confusion matrix, delta distribution, event/year aggregation,
direction counts, population conservation, the CUT-classifier red-team
signal, and the corrected BLOCKED_ROUND_COUNT_SEMANTICS gate.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location(
    "round_count_mismatch_diagnostic", ROOT / "scripts" / "106_round_count_mismatch_diagnostic.py"
)
diag = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = diag
spec.loader.exec_module(diag)  # type: ignore[union-attr]

audit_v2 = diag._audit_v2  # the dynamically-loaded 105 module, reused (not reimplemented)


def _sg_row(player_id, game_code, rounds, scope="tournament_cumulative", identity_state="RETAINED"):
    return {"player_id": player_id, "game_code": game_code, "rounds": rounds,
            "scope": scope, "identity_state": identity_state, "total": 100.0}


def _official_row(player_id, requested_round, rounds_array, status="FINISHED"):
    return {"game_code": None, "requested_round": requested_round, "player_id": player_id,
            "player": f"Player {player_id}", "rank": "1", "rank_numeric": 1, "tie": False,
            "to_par": "-3", "through": "F", "rounds": rounds_array, "total": 278, "status": status}


def _archive_event(rounds_by_number: dict[int, list[dict]], max_round=4):
    rounds_out = {}
    for n in range(1, 5):
        rows = rounds_by_number.get(n)
        rounds_out[str(n)] = {
            "round_retrieval_state": "RETRIEVED" if rows is not None and n <= max_round else "NETWORK_EGRESS_DENIED",
            "retrieved_at": "2026-01-01T00:00:00Z",
            "row_count": len(rows) if rows else 0,
            "players": rows or [],
        }
    return {"event_retrieval_state": "RETRIEVED" if max_round == 4 else "PARTIAL", "rounds": rounds_out}


# ------------------------------------------------------- fixture scenario


def _mixed_fixture():
    """A population of 6, deliberately covering: exact match, SG<official,
    SG>official, unverified (no official row), and a phantom-later-round
    CUT-classifier red flag."""
    sg_records = [
        _sg_row("EQUAL_P", "G1", 4),
        _sg_row("LESS_P", "G1", 2),        # SG says 2, official will show 3 -> SG < official
        _sg_row("GREATER_P", "G1", 4),     # SG says 4, official will show 3 -> SG > official
        _sg_row("MISSING_P", "G1", 3),     # never appears in archive
        _sg_row("PHANTOM_P", "G1", 2),     # appears again in round 4 with stale data
        _sg_row("EQUAL_P2", "G2", 1),
    ]
    events = {
        "G1": _archive_event({
            1: [_official_row("EQUAL_P", 1, [70, None, None, None]),
                _official_row("LESS_P", 1, [71, None, None, None]),
                _official_row("GREATER_P", 1, [72, None, None, None]),
                _official_row("PHANTOM_P", 1, [73, None, None, None])],
            2: [_official_row("EQUAL_P", 2, [70, 68, None, None]),
                _official_row("LESS_P", 2, [71, 69, None, None]),
                _official_row("GREATER_P", 2, [72, 70, None, None]),
                _official_row("PHANTOM_P", 2, [73, 71, None, None])],
            3: [_official_row("EQUAL_P", 3, [70, 68, 71, None]),
                _official_row("LESS_P", 3, [71, 69, 70, None]),
                _official_row("GREATER_P", 3, [72, 70, 69, None])],
            4: [_official_row("EQUAL_P", 4, [70, 68, 71, 69]),
                # PHANTOM_P reappears in round 4 with the SAME (non-improving) 2-round data --
                # this is the "phantom later-round appearance" the red-team signal must catch.
                _official_row("PHANTOM_P", 4, [73, 71, None, None])],
        }, max_round=4),
        "G2": _archive_event({1: [_official_row("EQUAL_P2", 1, [65, None, None, None])]}, max_round=1),
    }
    return {"records": sg_records}, {"events": events}


def test_confusion_matrix_counts_and_percentages():
    sg, archive = _mixed_fixture()
    report = diag.build_diagnostic(sg, archive)
    cells = {(c["sg_rounds"], c["official_rounds"]): c["count"] for c in report["confusion_matrix"]}
    assert cells[(4, 4)] == 1   # EQUAL_P
    assert cells[(2, 3)] == 1   # LESS_P
    assert cells[(4, 3)] == 1   # GREATER_P
    assert cells[(2, 2)] == 1   # PHANTOM_P (best snapshot still 2 non-null despite phantom round4 row)
    assert cells[(1, 1)] == 1   # EQUAL_P2
    total_cells = sum(c["count"] for c in report["confusion_matrix"])
    assert total_cells == report["evidence_matched_count"] == 5  # MISSING_P excluded (unverified)


def test_delta_distribution_buckets_match_confusion_matrix():
    sg, archive = _mixed_fixture()
    report = diag.build_diagnostic(sg, archive)
    dist = report["delta_distribution"]
    # PHANTOM_P's max non-null count (2) is identical whichever tied round
    # is selected, so it lands as an EQUAL case (delta 0) alongside
    # EQUAL_P (4-4) and EQUAL_P2 (1-1) -- 3 total, not a separate mismatch.
    assert dist.get("0") == 3
    assert dist.get("1") == 1   # LESS_P: official(3) - sg(2) = +1
    assert dist.get("-1") == 1  # GREATER_P: official(3) - sg(4) = -1
    assert sum(dist.values()) == report["evidence_matched_count"]


def test_mismatch_direction_and_no_dropped_rows_population_conservation():
    sg, archive = _mixed_fixture()
    report = diag.build_diagnostic(sg, archive)
    direction = report["mismatch_direction"]
    assert direction["sg_equal_official"] == 3
    assert direction["sg_less_than_official"] == 1
    assert direction["sg_greater_than_official"] == 1
    assert direction["unverified_no_official_row"] == 1
    # population conservation: every one of the 6 sg_records must land in
    # exactly one bucket -- nothing silently dropped.
    assert sum(direction.values()) == 6 == report["population_checked"]


def test_event_diagnostics_aggregate_correctly_per_game_code():
    sg, archive = _mixed_fixture()
    report = diag.build_diagnostic(sg, archive)
    by_code = {e["game_code"]: e for e in report["event_diagnostics"]["worst_mismatch_events_top20"]}
    assert by_code["G1"]["population"] == 5
    assert by_code["G1"]["verified"] == 2  # EQUAL_P, PHANTOM_P (count-tie resolves to EQUAL either way)
    assert by_code["G1"]["mismatch"] == 2  # LESS_P, GREATER_P
    assert by_code["G1"]["unverified"] == 1  # MISSING_P
    assert by_code["G1"]["mismatch_rate"] == round(2 / 4, 4)


def test_year_diagnostics_extracted_from_game_code_prefix():
    sg, archive = _mixed_fixture()
    report = diag.build_diagnostic(sg, archive)
    years = {y["year"]: y for y in report["year_diagnostics"]}
    # fixture game codes "G1"/"G2" don't start with a 4-digit year -- must
    # classify UNKNOWN rather than fabricate a year, per year_of_game_code's
    # explicit contract.
    assert set(years.keys()) == {"UNKNOWN"}
    assert years["UNKNOWN"]["population"] == 6

    real_year = diag.year_of_game_code("2023040001")
    assert real_year == "2023"


def test_cut_redteam_phantom_signal_flags_stale_later_round_appearance():
    sg, archive = _mixed_fixture()
    report = diag.build_diagnostic(sg, archive)
    signal = report["cut_classifier_redteam"]["phantom_later_round_appearance_signal"]
    assert signal["phantom_count"] == 1
    assert signal["examples"][0]["player_id"] == "PHANTOM_P"


def test_cut_redteam_signal_is_zero_for_a_player_who_truly_disappears():
    sg = {"records": [_sg_row("REAL_CUT_P", "G1", 2)]}
    archive = {"events": {"G1": _archive_event({
        1: [_official_row("REAL_CUT_P", 1, [70, None, None, None])],
        2: [_official_row("REAL_CUT_P", 2, [70, 68, None, None])],
        3: [],  # truly absent from round 3 and round 4
        4: [],
    }, max_round=4)}}
    report = diag.build_diagnostic(sg, archive)
    assert report["cut_classifier_redteam"]["phantom_later_round_appearance_signal"]["phantom_count"] == 0


def test_no_official_evidence_still_conserves_population_and_reports_unverified():
    sg = {"records": [_sg_row("P1", "G1", 4)]}
    report = diag.build_diagnostic(sg, None)
    assert report["population_checked"] == 1
    assert report["evidence_matched_count"] == 0
    assert report["mismatch_direction"]["unverified_no_official_row"] == 1


def test_sg_rounds_semantics_provenance_cites_exact_code_paths_not_inference():
    sg, archive = _mixed_fixture()
    report = diag.build_diagnostic(sg, archive)
    prov = report["sg_rounds_semantics_provenance"]
    assert "scripts/77_repair_sg_row_retention.py" in prov["producer_script"]
    assert "official_data.py" in prov["rounds_field_source"]
    assert "cells[8]" in prov["rounds_field_source"]
    # the hypothesis must be explicitly labeled as unresolved, never asserted as settled fact
    assert "hypothesis" in prov["unresolved_hypothesis_not_asserted_as_fact"].lower()


# --------------------------------------------- fixed hard-gate wording (105)


def test_gate_blocked_round_count_semantics_when_high_mismatch_with_real_evidence():
    """The exact scenario the red-team surfaced: retrieval succeeded (real
    evidence exists for every player) but the mismatch rate is high -- the
    gate must say BLOCKED_ROUND_COUNT_SEMANTICS, never plain BLOCKED
    (which would misleadingly suggest a retrieval-coverage problem) and
    never PARTIAL_EVIDENCE/VERIFIED (which would misleadingly suggest the
    data is usable)."""
    sg_records = [_sg_row(f"P{i}", "G1", 4) for i in range(10)]
    # 6 of 10 mismatch (60% mismatch rate, comfortably over the 5% gate threshold)
    events = {"G1": _archive_event({
        1: [_official_row(f"P{i}", 1, [70, None, None, None]) for i in range(10)],
        2: [_official_row(f"P{i}", 2, [70, 68, None, None]) for i in range(10)],
        3: [_official_row(f"P{i}", 3, [70, 68, 71, None]) for i in range(10)],
        4: [_official_row(f"P{i}", 4, [70, 68, 71, 69] if i < 4 else [70, 68, 71, None]) for i in range(10)],
    }, max_round=4)}
    consistency = {"aggregate": {"verified_field_players": 1, "SG_field_players": 1, "missing_from_SG": 0}}
    report = audit_v2.build_report({"records": sg_records}, consistency, archive={"events": events}, archive_sha="fake")
    assert report["round_count_state"]["verified"] == 4
    assert report["round_count_state"]["mismatch"] == 6
    assert report["hard_gate"]["status"] == "BLOCKED_ROUND_COUNT_SEMANTICS"
    assert "not a retrieval-coverage problem" in report["hard_gate"]["reason"]


def test_gate_stays_plain_blocked_when_zero_evidence_at_all():
    sg_records = [_sg_row("P1", "G1", 4)]
    consistency = {"aggregate": {"verified_field_players": 1, "SG_field_players": 1, "missing_from_SG": 0}}
    report = audit_v2.build_report({"records": sg_records}, consistency, archive=None, archive_sha=None)
    assert report["hard_gate"]["status"] == "BLOCKED"
    assert "Zero player-events matched" in report["hard_gate"]["reason"]


def test_gate_partial_evidence_when_mismatch_rate_is_low():
    sg_records = [_sg_row(f"P{i}", "G1", 1) for i in range(20)]
    events = {"G1": _archive_event({
        1: [_official_row(f"P{i}", 1, [70, None, None, None] if i else [70, 68, None, None]) for i in range(20)],
    }, max_round=1)}
    consistency = {"aggregate": {"verified_field_players": 1, "SG_field_players": 1, "missing_from_SG": 0}}
    report = audit_v2.build_report({"records": sg_records}, consistency, archive={"events": events}, archive_sha="fake")
    # 1/20 = 5% exactly is not > 5%, stays under the gate threshold
    assert report["round_count_state"]["mismatch"] == 1
    assert report["hard_gate"]["status"] in ("PARTIAL_EVIDENCE", "VERIFIED")


# ------------------------------------------------------- real-artifact locks


def test_real_v1_baseline_untouched_by_this_diagnostic():
    redteam = json.loads((ROOT / "content" / "website_v2" / "NEO_RANKING_V1_REDTEAM_BACKTEST.json").read_text(encoding="utf-8"))
    assert redteam["tournament_count"] == 82
    assert redteam["observation_count"] == 7830


def test_real_production_gate_untouched():
    home_ranking_src = (ROOT / "src" / "klpga" / "website_v2" / "home_ranking.py").read_text(encoding="utf-8")
    assert 'FORMULA_STATE = "BLOCKED_FORMULA_NOT_APPROVED"' in home_ranking_src
    assert "NEO_RANKING_VERSION = None" in home_ranking_src


def test_real_sg_warehouse_file_never_modified_by_this_task():
    """This is a read-only diagnostic -- lock in that the SG warehouse's
    own scope/identity_state distribution (the thing 106 reads) still
    matches what the earlier round-count audit already established."""
    sg = json.loads((ROOT / "content" / "website_v2" / "historical_sg_warehouse_corrected.json").read_text(encoding="utf-8"))
    cumulative_retained = sum(
        1 for r in sg["records"] if r.get("identity_state") == "RETAINED" and r.get("scope") == "tournament_cumulative"
    )
    distinct_keys = {
        (r.get("player_id"), r.get("game_code"))
        for r in sg["records"] if r.get("identity_state") == "RETAINED" and r.get("scope") == "tournament_cumulative"
    }
    assert len(distinct_keys) == 6294


def test_real_mismatch_diagnostic_artifact_never_claims_evidence_it_does_not_have():
    report_path = ROOT / "content" / "website_v2" / "NEO_RANKING_V2_ROUND_COUNT_MISMATCH_DIAGNOSTIC.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["model_state"] == "VALIDATION_MODEL_NOT_PRODUCTION"
    assert report["population_checked"] == 6294
    # whatever the real evidence_matched_count is in this environment, the
    # confusion matrix's total count must never exceed it (no fabricated cells).
    total_confusion_count = sum(c["count"] for c in report["confusion_matrix"])
    assert total_confusion_count == report["evidence_matched_count"]
    assert report["evidence_matched_count"] + report["unverified_no_official_row_count"] == report["population_checked"]
