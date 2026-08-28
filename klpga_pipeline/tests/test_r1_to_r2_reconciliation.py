"""Tests for klpga.neo_win.r1_to_r2_reconciliation — Section B of the
R1->R2 evaluation pipeline. Synthetic frozen-R1 + official-R2 fixtures
only (never live R2 data); pins the exact status->outcome mapping and
the R1_PLAYERS/R2_PLAYERS/NEW_WD/NEW_DQ/CUT/MADE_CUT/MISSING/
UNMATCHED_PLAYER_CODES summary fields the spec requires."""
from __future__ import annotations

from klpga.neo_win.cut_evaluation import (
    CUT_OUTCOME_DQ,
    CUT_OUTCOME_MADE,
    CUT_OUTCOME_MISSED,
    CUT_OUTCOME_UNRESOLVED,
    CUT_OUTCOME_WD,
)
from klpga.neo_win.r1_frozen_snapshot import PlayerR1Frozen
from klpga.neo_win.r1_to_r2_reconciliation import (
    outcome_from_official_r2,
    reconcile_r1_to_r2,
)
from klpga.neo_win.round_reconciliation import NormalizedPlayer


def _frozen(code, name="A", rank=1, score=-3.0, win=10.0, cut=80.0):
    return PlayerR1Frozen(
        tournament_id="2026080001", player_code=code, player_name=name, r1_actual_rank=rank,
        r1_actual_score_to_par=score, r1_win_probability_pct=win, r1_make_cut_probability_pct=cut,
        model_version="001-C-R1", prediction_generated_at="2026-08-27T00:00:00Z",
    )


def _official(code, name="A", position=10, round_score=70, score_to_par=-2, status=None):
    return NormalizedPlayer(
        player_code=code, player_name=name, position_display=str(position) if position else None,
        position=position, round_score=round_score, score_to_par=score_to_par, status=status,
    )


# ---------------------------------------------------------------
# outcome_from_official_r2 — the status -> outcome mapping
# ---------------------------------------------------------------


def test_status_cut_maps_to_missed_cut():
    assert outcome_from_official_r2(_official("p1", status="CUT")) == CUT_OUTCOME_MISSED


def test_status_wd_maps_to_wd():
    assert outcome_from_official_r2(_official("p1", status="WD")) == CUT_OUTCOME_WD


def test_status_dq_maps_to_dq():
    assert outcome_from_official_r2(_official("p1", status="DQ")) == CUT_OUTCOME_DQ


def test_status_incomplete_sentinel_maps_to_unresolved_never_wd_or_dq():
    assert outcome_from_official_r2(_official("p1", status="INCOMPLETE")) == CUT_OUTCOME_UNRESOLVED


def test_no_status_with_real_score_maps_to_made_cut():
    assert outcome_from_official_r2(_official("p1", status=None, round_score=68)) == CUT_OUTCOME_MADE


def test_no_status_and_no_score_maps_to_unresolved():
    o = _official("p1", status=None, round_score=None, score_to_par=None)
    assert outcome_from_official_r2(o) == CUT_OUTCOME_UNRESOLVED


def test_absent_from_official_r2_entirely_maps_to_unresolved_never_guessed():
    assert outcome_from_official_r2(None) == CUT_OUTCOME_UNRESOLVED


def test_unrecognized_status_text_maps_to_unresolved_never_crashes():
    assert outcome_from_official_r2(_official("p1", status="SOME_NEW_UNSEEN_STATUS")) == CUT_OUTCOME_UNRESOLVED


# ---------------------------------------------------------------
# outcome_from_official_r2 — real-site fix: no Round 2 row at all,
# fall back to Round 1 presence/absence evidence (never rank-based)
# ---------------------------------------------------------------


def test_absent_from_r2_but_completed_r1_stays_unresolved_never_guessed_missed():
    """R1-presence + R2-absence alone is NOT treated as sufficient
    evidence of a missed cut — this was tried and disproven against a
    real Windows run (see module docstring's "A PLAYER WITH NO ROUND 2
    ROW AT ALL" section)."""
    r1 = _official("p1", round_score=72, score_to_par=1, status=None)
    assert outcome_from_official_r2(None, r1) == CUT_OUTCOME_UNRESOLVED


def test_absent_from_r2_and_r1_shows_wd_maps_to_wd_not_missed():
    r1 = _official("p1", round_score=None, score_to_par=None, status="WD")
    assert outcome_from_official_r2(None, r1) == CUT_OUTCOME_WD


def test_absent_from_r2_and_r1_shows_dq_maps_to_dq_not_missed():
    r1 = _official("p1", round_score=None, score_to_par=None, status="DQ")
    assert outcome_from_official_r2(None, r1) == CUT_OUTCOME_DQ


def test_absent_from_r2_and_r1_also_has_no_score_stays_unresolved():
    r1 = _official("p1", round_score=None, score_to_par=None, status=None)
    assert outcome_from_official_r2(None, r1) == CUT_OUTCOME_UNRESOLVED


def test_absent_from_r2_with_no_r1_evidence_at_all_stays_unresolved():
    assert outcome_from_official_r2(None, None) == CUT_OUTCOME_UNRESOLVED


def test_r2_row_present_but_ambiguous_never_falls_back_to_r1():
    """A genuine (if ambiguous) Round 2 row always wins over Round 1
    fallback reasoning — the fallback is ONLY for a player missing
    from Round 2 entirely."""
    o = _official("p1", status="INCOMPLETE")
    r1 = _official("p1", round_score=70, score_to_par=-1, status=None)
    assert outcome_from_official_r2(o, r1) == CUT_OUTCOME_UNRESOLVED


def test_r2_made_cut_never_falls_back_to_r1_even_if_r1_looks_odd():
    o = _official("p1", status=None, round_score=68)
    r1 = _official("p1", round_score=None, score_to_par=None, status="WD")
    assert outcome_from_official_r2(o, r1) == CUT_OUTCOME_MADE


# ---------------------------------------------------------------
# reconcile_r1_to_r2 — full field reconciliation + summary
# ---------------------------------------------------------------


def test_reconcile_full_field_summary_counts():
    frozen = [_frozen("p1"), _frozen("p2"), _frozen("p3"), _frozen("p4"), _frozen("p5")]
    official = {
        "p1": _official("p1", status=None, round_score=68),   # made cut
        "p2": _official("p2", status="CUT"),                   # missed cut
        "p3": _official("p3", status="WD"),
        "p4": _official("p4", status="DQ"),
        # p5 absent from official entirely -> unresolved
    }
    rows, summary = reconcile_r1_to_r2(frozen, official)
    assert summary["r1_players"] == 5
    assert summary["r2_players"] == 4
    assert summary["made_cut"] == 1
    assert summary["cut"] == 1
    assert summary["new_wd"] == 1
    assert summary["new_dq"] == 1
    assert summary["missing"] == 1
    assert summary["unmatched_player_codes"]["only_in_frozen_r1"] == ["p5"]
    assert summary["unmatched_player_codes"]["only_in_official_r2"] == []


def test_reconcile_reports_official_only_players_as_unmatched():
    frozen = [_frozen("p1")]
    official = {"p1": _official("p1", round_score=68), "p9": _official("p9", round_score=70)}
    _rows, summary = reconcile_r1_to_r2(frozen, official)
    assert summary["unmatched_player_codes"]["only_in_official_r2"] == ["p9"]


def test_reconcile_never_merges_by_name_only_by_player_code():
    frozen = [_frozen("p1", name="Same Name")]
    official = {"p2": _official("p2", name="Same Name", round_score=68)}
    rows, summary = reconcile_r1_to_r2(frozen, official)
    codes = {r.player_code for r in rows}
    assert codes == {"p1", "p2"}  # never collapsed into one row by matching names
    assert summary["unmatched_player_codes"]["only_in_frozen_r1"] == ["p1"]
    assert summary["unmatched_player_codes"]["only_in_official_r2"] == ["p2"]


def test_reconcile_row_carries_real_r2_position_and_score():
    frozen = [_frozen("p1")]
    official = {"p1": _official("p1", position=7, round_score=69, score_to_par=-1)}
    rows, _summary = reconcile_r1_to_r2(frozen, official)
    row = rows[0]
    assert row.r2_position == 7
    assert row.r2_score_to_par == -1
    assert row.r2_outcome == CUT_OUTCOME_MADE
    assert row.in_frozen_r1 is True
    assert row.in_official_r2 is True


def test_reconcile_empty_official_r2_reports_all_frozen_players_unresolved():
    frozen = [_frozen("p1"), _frozen("p2")]
    rows, summary = reconcile_r1_to_r2(frozen, {})
    assert summary["r2_players"] == 0
    assert summary["missing"] == 2
    assert all(r.r2_outcome == CUT_OUTCOME_UNRESOLVED for r in rows)


def test_reconcile_with_official_r1_still_defers_r2_absent_players_to_unresolved():
    """R1-presence + R2-absence alone (p2, p3) stays UNRESOLVED — see
    module docstring's "A PLAYER WITH NO ROUND 2 ROW AT ALL" section
    for why this inference was tried and reverted. An explicit WD/DQ
    status in official_r1 (p4) is still real, direct evidence and is
    still honored. p5 has no evidence anywhere."""
    frozen = [_frozen("p1"), _frozen("p2"), _frozen("p3"), _frozen("p4"), _frozen("p5")]
    official_r1 = {
        "p1": _official("p1", round_score=70, score_to_par=-2, status=None),
        "p2": _official("p2", round_score=75, score_to_par=3, status=None),
        "p3": _official("p3", round_score=76, score_to_par=4, status=None),
        "p4": _official("p4", round_score=None, score_to_par=None, status="WD"),
        # p5 has no Round 1 evidence at all either.
    }
    official_r2 = {
        "p1": _official("p1", round_score=68, score_to_par=-4, status=None),
        # p2, p3, p4, p5 all absent from Round 2 entirely (the real, confirmed site behavior).
    }
    rows, summary = reconcile_r1_to_r2(frozen, official_r2, official_r1)

    assert summary["made_cut"] == 1  # p1
    assert summary["cut"] == 0  # never asserted without proven evidence
    assert summary["new_wd"] == 1  # p4
    assert summary["missing"] == 3  # p2, p3, p5 — real evidence still needed
    by_code = {r.player_code: r.r2_outcome for r in rows}
    assert by_code["p2"] == CUT_OUTCOME_UNRESOLVED
    assert by_code["p3"] == CUT_OUTCOME_UNRESOLVED
    assert by_code["p4"] == CUT_OUTCOME_WD
    assert by_code["p5"] == CUT_OUTCOME_UNRESOLVED


def test_reconcile_missing_player_diagnostics_shows_why_each_is_unresolved():
    """Real-world diagnostic requirement: a genuinely unresolved player
    (no evidence in official_r1 OR official_r2) must be individually
    explainable, not just a bare count."""
    frozen = [_frozen("p1"), _frozen("p2"), _frozen("p3")]
    official_r1 = {
        "p2": _official("p2", round_score=None, score_to_par=None, status=None),  # in R1 field but no real score
        # p3 has no Round 1 evidence at all either.
    }
    official_r2 = {}  # no one has a Round 2 row
    _rows, summary = reconcile_r1_to_r2(frozen, official_r2, official_r1)

    assert summary["missing"] == 3
    diag_by_code = {d["player_code"]: d for d in summary["missing_player_diagnostics"]}
    assert set(diag_by_code) == {"p1", "p2", "p3"}
    assert diag_by_code["p1"]["in_official_r1"] is False
    assert diag_by_code["p2"]["in_official_r1"] is True
    assert diag_by_code["p2"]["official_r1_round_score"] is None
    assert diag_by_code["p3"]["in_official_r1"] is False


def test_reconcile_missing_player_diagnostics_empty_when_nothing_unresolved():
    frozen = [_frozen("p1")]
    official_r2 = {"p1": _official("p1", round_score=68)}
    _rows, summary = reconcile_r1_to_r2(frozen, official_r2)
    assert summary["missing_player_diagnostics"] == []


def test_reconcile_omitting_official_r1_preserves_old_conservative_behavior():
    frozen = [_frozen("p1"), _frozen("p2")]
    official_r2 = {"p1": _official("p1", round_score=68)}
    rows, summary = reconcile_r1_to_r2(frozen, official_r2)  # no official_r1 passed
    assert summary["cut"] == 0
    assert summary["missing"] == 1
    p2 = next(r for r in rows if r.player_code == "p2")
    assert p2.r2_outcome == CUT_OUTCOME_UNRESOLVED
