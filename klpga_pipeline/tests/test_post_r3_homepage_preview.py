"""Tests for klpga.neo_win.post_r3_homepage_preview — pure join/
validation/render logic for the POST-R3 homepage preview builder."""
from __future__ import annotations

from klpga.neo_win.post_r3_homepage_preview import (
    STATUS_ACTIVE,
    DbPlayerRow,
    build_preview_rows,
    check_duplicate_player_codes,
    check_probability_invariants,
    check_win_sum,
    compute_current_ranks,
    format_win_change,
    reconcile_codes,
    render_preview_html,
    sort_active_rows_by_rank_then_win,
)


class _FakeEntrant:
    def __init__(self, player_code, player_name, win_pct, top5_pct, top10_pct, top20_pct):
        self.player_code = player_code
        self.player_name = player_name
        self.win_pct = win_pct
        self.top5_pct = top5_pct
        self.top10_pct = top10_pct
        self.top20_pct = top20_pct


def _db(code, name, status, cum=None):
    return DbPlayerRow(player_code=code, player_name=name, status=status, cumulative_score_to_par=cum)


# ---------------------------------------------------------------
# compute_current_ranks
# ---------------------------------------------------------------


def test_ranks_only_among_active_ascending_score():
    db_rows = [
        _db("p1", "A", STATUS_ACTIVE, -3.0),
        _db("p2", "B", STATUS_ACTIVE, -8.0),
        _db("p3", "C", "CUT", None),
    ]
    ranks = compute_current_ranks(db_rows)
    assert ranks == {"p2": 1, "p1": 2}  # p3 excluded entirely


def test_ranks_ties_share_rank_and_next_rank_skips():
    db_rows = [
        _db("p1", "A", STATUS_ACTIVE, -9.0),
        _db("p2", "B", STATUS_ACTIVE, -9.0),
        _db("p3", "C", STATUS_ACTIVE, -4.0),
    ]
    ranks = compute_current_ranks(db_rows)
    assert ranks == {"p1": 1, "p2": 1, "p3": 3}


# ---------------------------------------------------------------
# build_preview_rows
# ---------------------------------------------------------------


def test_active_player_joins_all_three_sources():
    db_rows = [_db("p1", "A", STATUS_ACTIVE, -6.0)]
    stage = {"p1": _FakeEntrant("p1", "A", 42.0, 78.0, 88.0, 94.0)}
    recovery = {"p1": -3.0}
    rows, warnings = build_preview_rows(db_rows, stage, recovery)
    assert warnings == []
    r = rows[0]
    assert r.win_pct == 42.0 and r.top20_pct == 94.0
    assert r.r2_to_r3_win_change_pct == -3.0
    assert r.current_rank == 1


def test_active_player_missing_from_stage_r3_warns_and_leaves_probabilities_none():
    db_rows = [_db("p1", "A", STATUS_ACTIVE, -6.0)]
    rows, warnings = build_preview_rows(db_rows, {}, {})
    assert len(warnings) >= 1
    assert "absent from STAGE_R3" in warnings[0]
    assert rows[0].win_pct is None


def test_non_advancing_player_never_gets_probabilities_even_if_present_in_stage_r3():
    """A CUT player's STAGE_R3 entry (win_pct=0.0, a real known fact) must
    never be surfaced through a non-ACTIVE DbPlayerRow -- status
    classification from the DB is authoritative for whether a player is
    even looked up in STAGE_R3 at all."""
    db_rows = [_db("p1", "A", "CUT", None)]
    stage = {"p1": _FakeEntrant("p1", "A", 0.0, 0.0, 0.0, 0.0)}
    rows, warnings = build_preview_rows(db_rows, stage, {})
    assert rows[0].win_pct is None
    assert rows[0].status == "CUT"
    assert warnings == []


def test_current_rank_display_tied_gets_t_prefix_untied_does_not():
    db_rows = [
        _db("p1", "A", STATUS_ACTIVE, -9.0),
        _db("p2", "B", STATUS_ACTIVE, -9.0),
        _db("p3", "C", STATUS_ACTIVE, -4.0),
    ]
    rows, _w = build_preview_rows(db_rows, {}, {})
    by_code = {r.player_code: r for r in rows}
    assert by_code["p1"].current_rank_display == "T1"
    assert by_code["p2"].current_rank_display == "T1"
    assert by_code["p3"].current_rank_display == "3"


def test_recovery_missing_for_active_player_is_warned_and_unavailable():
    db_rows = [_db("p1", "A", STATUS_ACTIVE, -6.0)]
    stage = {"p1": _FakeEntrant("p1", "A", 42.0, 78.0, 88.0, 94.0)}
    rows, warnings = build_preview_rows(db_rows, stage, {})
    assert rows[0].r2_to_r3_win_change_pct is None
    assert any("recovery" in w.lower() or "RECOVERY" in w for w in warnings)


# ---------------------------------------------------------------
# validation checks
# ---------------------------------------------------------------


def test_duplicate_player_codes_detected():
    assert check_duplicate_player_codes(["p1", "p2", "p1"]) == ["p1"]
    assert check_duplicate_player_codes(["p1", "p2"]) == []


def _row(code, win, top5, top10, top20, status=STATUS_ACTIVE):
    return build_preview_rows(
        [_db(code, code, status, -1.0)],
        {code: _FakeEntrant(code, code, win, top5, top10, top20)} if status == STATUS_ACTIVE else {},
        {},
    )[0][0]


def test_win_sum_passes_near_100():
    rows = [_row("p1", 60.0, 70, 80, 90), _row("p2", 40.0, 50, 60, 70)]
    total, ok = check_win_sum(rows)
    assert total == 100.0 and ok is True


def test_win_sum_fails_far_from_100():
    rows = [_row("p1", 1.0, 2, 3, 4)]
    total, ok = check_win_sum(rows)
    assert ok is False


def test_probability_invariants_flags_violation():
    rows = [_row("p1", 80.0, 70, 60, 50)]  # reversed -- WIN > TOP5
    violations = check_probability_invariants(rows)
    assert len(violations) == 1 and "p1" in violations[0]


def test_probability_invariants_ignores_non_active_rows():
    rows, _w = build_preview_rows([_db("p1", "A", "CUT", None)], {}, {})
    assert check_probability_invariants(rows) == []


def test_reconcile_codes_partitions_correctly():
    result = reconcile_codes("a", {"p1", "p2"}, "b", {"p2", "p3"})
    assert result == {"matched": ["p2"], "a_only": ["p1"], "b_only": ["p3"]}


# ---------------------------------------------------------------
# format_win_change
# ---------------------------------------------------------------


def test_format_win_change_signs_and_precision():
    assert format_win_change(9.723) == "+9.72%p"
    assert format_win_change(-12.225) == "-12.22%p" or format_win_change(-12.225) == "-12.23%p"  # banker's rounding edge
    assert format_win_change(0.0) == "+0.00%p"
    assert format_win_change(None) == "unavailable"


# ---------------------------------------------------------------
# render_preview_html
# ---------------------------------------------------------------


def test_render_html_separates_active_and_non_advancing():
    rows, _w = build_preview_rows(
        [_db("p1", "Active Player", STATUS_ACTIVE, -6.0), _db("p2", "Cut Player", "CUT", None)],
        {"p1": _FakeEntrant("p1", "Active Player", 42.0, 78.0, 88.0, 94.0)},
        {"p1": -3.0},
    )
    html = render_preview_html(rows, tournament_name="Test Open", game_code="2026080099")
    assert "Active Player" in html
    assert "Cut Player" in html
    assert "컷 탈락" in html
    assert "42.00%" in html
    assert "-3.00%p" in html
    assert "Probabilities represent NEO model estimates for the final tournament result after Round 4." in html
    assert "PREVIEW ONLY" in html
    # Cut Player's name must appear only in the non-advancing pill list, never inside a probability <td>.
    assert "<td class=\"c-pct\">42.00%</td>" in html


def test_render_html_sorts_by_current_rank_ascending():
    """Better (lower) 54-hole score -> better rank -> earlier in the
    table, even though WIN% alone would have ordered them the other way."""
    rows, _w = build_preview_rows(
        [_db("p1", "BetterRankLowerWin", STATUS_ACTIVE, -2.0), _db("p2", "WorseRankHigherWin", STATUS_ACTIVE, -1.0)],
        {
            "p1": _FakeEntrant("p1", "BetterRankLowerWin", 5.0, 10, 20, 30),
            "p2": _FakeEntrant("p2", "WorseRankHigherWin", 50.0, 60, 70, 80),
        },
        {},
    )
    html = render_preview_html(rows, tournament_name="Test Open", game_code="2026080099")
    assert html.index("BetterRankLowerWin") < html.index("WorseRankHigherWin")


def test_render_html_ties_broken_by_win_pct_descending_and_shows_t_prefix():
    rows, _w = build_preview_rows(
        [_db("p1", "TiedLowerWin", STATUS_ACTIVE, -5.0), _db("p2", "TiedHigherWin", STATUS_ACTIVE, -5.0)],
        {
            "p1": _FakeEntrant("p1", "TiedLowerWin", 20.0, 40, 60, 80),
            "p2": _FakeEntrant("p2", "TiedHigherWin", 30.0, 50, 70, 90),
        },
        {},
    )
    html = render_preview_html(rows, tournament_name="Test Open", game_code="2026080099")
    assert html.index("TiedHigherWin") < html.index("TiedLowerWin")
    assert html.count(">T1<") == 2  # both tied players show "T1"


def test_sort_active_rows_by_rank_then_win_orders_and_excludes_non_active():
    rows, _w = build_preview_rows(
        [
            _db("p1", "A", STATUS_ACTIVE, -5.0),
            _db("p2", "B", STATUS_ACTIVE, -5.0),
            _db("p3", "C", STATUS_ACTIVE, -1.0),
            _db("p4", "D", "CUT", None),
        ],
        {
            "p1": _FakeEntrant("p1", "A", 20.0, 40, 60, 80),
            "p2": _FakeEntrant("p2", "B", 30.0, 50, 70, 90),
            "p3": _FakeEntrant("p3", "C", 50.0, 60, 80, 95),
        },
        {},
    )
    ordered = sort_active_rows_by_rank_then_win(rows)
    assert [r.player_code for r in ordered] == ["p2", "p1", "p3"]
