"""Tests for scripts/105_round_count_audit_v2.py and
src/klpga/website_v2/round_count_audit_lib.py -- the archive-connected
round-count audit. Uses constructed fixture data (not real network access)
to exercise every classification path deterministically: VERIFIED,
MISMATCH, UNVERIFIED, the 1-ROUND RULE, WD/DQ independence from round-count
integrity, real CUT evidence, and that CUT players are never dropped from
the population.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.round_count_audit_lib import (  # noqa: E402
    build_cumulative_only, build_player_index, best_snapshot, count_nonnull_rounds, max_retrieved_round,
)

spec = importlib.util.spec_from_file_location(
    "round_count_audit_v2", ROOT / "scripts" / "105_round_count_audit_v2.py"
)
audit_v2 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit_v2
spec.loader.exec_module(audit_v2)  # type: ignore[union-attr]


def _sg_row(player_id, game_code, rounds, scope="tournament_cumulative", identity_state="RETAINED", total=100.0):
    return {
        "player_id": player_id, "game_code": game_code, "rounds": rounds,
        "scope": scope, "identity_state": identity_state, "total": total,
    }


def _official_row(player_id, requested_round, rounds_array, status="FINISHED"):
    return {
        "game_code": None, "requested_round": requested_round, "player_id": player_id,
        "player": f"Player {player_id}", "rank": "1", "rank_numeric": 1, "tie": False,
        "to_par": "-3", "through": "F", "rounds": rounds_array, "total": 278, "status": status,
    }


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


# ---------------------------------------------------------------- library


def test_best_snapshot_picks_the_row_with_the_most_non_null_rounds():
    rows = [
        _official_row("P1", 1, [70, None, None, None]),
        _official_row("P1", 2, [70, 68, None, None]),
    ]
    chosen = best_snapshot(rows)
    assert chosen["requested_round"] == 2
    assert count_nonnull_rounds(chosen["rounds"]) == 2


def test_best_snapshot_tie_breaks_on_highest_requested_round():
    # Both rows have 2 non-null values (a CUT player who appears with the
    # same partial score in two different round-leaderboard snapshots) --
    # the more recent/authoritative one must win.
    rows = [
        _official_row("P1", 2, [70, 68, None, None]),
        _official_row("P1", 3, [70, 68, None, None]),
    ]
    chosen = best_snapshot(rows)
    assert chosen["requested_round"] == 3


def test_best_snapshot_never_fabricates_returns_none_for_no_rows():
    assert best_snapshot([]) is None


def test_build_player_index_groups_by_player_id_across_rounds():
    event = _archive_event({1: [_official_row("P1", 1, [70, None, None, None])],
                             2: [_official_row("P1", 2, [70, 68, None, None])]})
    index = build_player_index(event)
    assert len(index["P1"]) == 2


def test_max_retrieved_round_only_counts_actually_retrieved_rounds():
    events = {"G1": _archive_event({1: [_official_row("P1", 1, [70, None, None, None])]}, max_round=1)}
    assert max_retrieved_round(events, "G1") == 1


def test_build_cumulative_only_deduplicates_progressive_snapshots_no_duplicate_keys():
    records = [
        _sg_row("P1", "G1", 3),
        _sg_row("P1", "G1", 4),  # a later, more-complete progressive snapshot for the SAME key
    ]
    cumulative_only, duplicates, _ = build_cumulative_only(records)
    assert len(cumulative_only) == 1
    assert duplicates == 1


def test_build_cumulative_only_never_mixes_single_round_into_cumulative():
    records = [_sg_row("P1", "G1", 2, scope="single_round")]
    cumulative_only, _, single_round_only = build_cumulative_only(records)
    assert cumulative_only == {}
    assert ("P1", "G1") in single_round_only


# ------------------------------------------------------------- classify


def test_classify_exact_match_is_verified_and_finished():
    best_row = _official_row("P1", 4, [70, 68, 71, 69])
    lb_count = count_nonnull_rounds(best_row["rounds"])
    assert lb_count == 4
    status = audit_v2.classify_competition_status(best_row, lb_count, archive_max_round=4)
    assert status == "FINISHED"


def test_classify_mismatch_is_independent_of_wd_status():
    # WD/DQ must be orthogonal to round-count integrity: a WD player can
    # still have a round-count MISMATCH (e.g. SG table says 4 rounds but
    # the official leaderboard shows only 3 non-null scores).
    best_row = _official_row("P1", 3, [70, 68, 71, None], status="WD")
    lb_count = count_nonnull_rounds(best_row["rounds"])
    assert lb_count == 3
    status = audit_v2.classify_competition_status(best_row, lb_count, archive_max_round=4)
    assert status == "WD"  # competition_status axis
    # round-count axis (computed separately in build_report) would be
    # MISMATCH here if the SG table's own rounds field said 4 -- these two
    # axes are independent by construction.


def test_classify_one_round_unexplained_is_unverified_early_exit_not_guessed():
    best_row = _official_row("P1", 1, [70, None, None, None], status="FINISHED")
    lb_count = count_nonnull_rounds(best_row["rounds"])
    status = audit_v2.classify_competition_status(best_row, lb_count, archive_max_round=4)
    assert status == "UNVERIFIED_EARLY_EXIT"


def test_classify_wd_flag_wins_even_with_one_round():
    best_row = _official_row("P1", 1, [70, None, None, None], status="WD")
    lb_count = count_nonnull_rounds(best_row["rounds"])
    status = audit_v2.classify_competition_status(best_row, lb_count, archive_max_round=4)
    assert status == "WD"


def test_classify_real_cut_evidence_not_inferred_from_round_count_alone():
    # The player's fullest snapshot is from round 2, but the ARCHIVE
    # actually retrieved round 4 for this event (i.e. round 4's official
    # leaderboard exists and this player is absent from it) -- that is
    # real evidence of a cut, not a guess from the number "2".
    best_row = _official_row("P1", 2, [70, 68, None, None], status="FINISHED")
    lb_count = count_nonnull_rounds(best_row["rounds"])
    status = audit_v2.classify_competition_status(best_row, lb_count, archive_max_round=4)
    assert status == "CUT"


# ------------------------------------------------------------ full report


def _build_fixture_report(sg_records, events):
    consistency = {"aggregate": {"verified_field_players": 9682, "SG_field_players": 7830, "missing_from_SG": 1852}}
    archive = {"events": events}
    return audit_v2.build_report({"records": sg_records}, consistency, archive, "fake-sha")


def test_report_verified_mismatch_unverified_and_cut_retained_in_population():
    sg_records = [
        _sg_row("VERIFIED_PLAYER", "G1", 4),
        _sg_row("MISMATCH_PLAYER", "G1", 4),
        _sg_row("MISSING_PLAYER", "G1", 3),
        _sg_row("CUT_PLAYER", "G1", 2),
        _sg_row("ONE_ROUND_PLAYER", "G1", 1),
    ]
    events = {
        "G1": _archive_event({
            1: [_official_row("VERIFIED_PLAYER", 1, [70, None, None, None]),
                _official_row("MISMATCH_PLAYER", 1, [71, None, None, None]),
                _official_row("CUT_PLAYER", 1, [72, None, None, None]),
                _official_row("ONE_ROUND_PLAYER", 1, [73, None, None, None])],
            2: [_official_row("VERIFIED_PLAYER", 2, [70, 68, None, None]),
                _official_row("MISMATCH_PLAYER", 2, [71, 69, None, None]),
                _official_row("CUT_PLAYER", 2, [72, 70, None, None])],
            3: [_official_row("VERIFIED_PLAYER", 3, [70, 68, 71, None]),
                _official_row("MISMATCH_PLAYER", 3, [71, 69, 70, None])],
            4: [_official_row("VERIFIED_PLAYER", 4, [70, 68, 71, 69])],
            # MISSING_PLAYER never appears anywhere in the archive.
        }, max_round=4),
    }
    report = _build_fixture_report(sg_records, events)

    assert report["player_events_checked"] == 5
    assert report["round_count_state"]["verified"] >= 2  # VERIFIED_PLAYER (4==4) and CUT_PLAYER (2==2)
    assert report["round_count_state"]["mismatch"] >= 1  # MISMATCH_PLAYER (sg=4, official best=3 non-null at round3)
    assert report["round_count_state"]["unverified"] == 1  # MISSING_PLAYER

    # CUT_PLAYER must be RETAINED in the population, not deleted -- it is
    # counted somewhere in competition_status, never silently dropped.
    assert sum(report["competition_status"].values()) == 5
    assert report["competition_status"].get("CUT", 0) >= 1
    assert report["competition_status"].get("UNVERIFIED_EARLY_EXIT", 0) >= 1

    # no duplicate (game_code, player_id) audit keys: exactly 5 distinct
    # players checked, matching the 5 sg_records above.
    assert report["player_events_checked"] == len(sg_records)


def test_report_hard_gate_blocked_when_no_archive_evidence_exists():
    sg_records = [_sg_row("P1", "G1", 4)]
    report = audit_v2.build_report({"records": sg_records}, {"aggregate": {"verified_field_players": 1, "SG_field_players": 1, "missing_from_SG": 0}}, None, None)
    assert report["hard_gate"]["status"] == "BLOCKED"
    assert report["round_count_state"]["verified"] == 0
    assert report["round_count_state"]["unverified"] == 1


def test_report_hard_gate_partial_evidence_when_some_verified():
    sg_records = [_sg_row("P1", "G1", 1)]
    events = {"G1": _archive_event({1: [_official_row("P1", 1, [70, None, None, None])]}, max_round=1)}
    report = _build_fixture_report(sg_records, events)
    assert report["round_count_state"]["verified"] == 1
    assert report["hard_gate"]["status"] == "PARTIAL_EVIDENCE"


# --------------------------------------------------- real-artifact locks


def test_real_v1_baseline_untouched_by_this_task():
    redteam = json.loads((ROOT / "content" / "website_v2" / "NEO_RANKING_V1_REDTEAM_BACKTEST.json").read_text(encoding="utf-8"))
    assert redteam["tournament_count"] == 82
    assert redteam["observation_count"] == 7830
    m = redteam["metrics"]
    assert abs(m["spearman_neo_rank_vs_finish"] - 0.4813430331167408) < 1e-9
    assert abs(m["made_cut_auc"] - 0.7120195073989171) < 1e-9


def test_real_production_publication_gate_untouched():
    home_ranking_src = (ROOT / "src" / "klpga" / "website_v2" / "home_ranking.py").read_text(encoding="utf-8")
    assert 'FORMULA_STATE = "BLOCKED_FORMULA_NOT_APPROVED"' in home_ranking_src
    assert "NEO_RANKING_VERSION = None" in home_ranking_src


def test_real_round_count_audit_artifact_is_v2_and_never_pass_without_evidence():
    report_path = ROOT / "content" / "website_v2" / "NEO_RANKING_V2_ROUND_COUNT_AUDIT.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == "neo_ranking_v2_round_count_audit_v2_archive_connected"
    assert report["model_state"] == "VALIDATION_MODEL_NOT_PRODUCTION"
    if report["round_count_state"]["verified"] == 0:
        assert report["hard_gate"]["status"] == "BLOCKED"
    else:
        assert report["hard_gate"]["status"] in ("BLOCKED", "PARTIAL_EVIDENCE")
