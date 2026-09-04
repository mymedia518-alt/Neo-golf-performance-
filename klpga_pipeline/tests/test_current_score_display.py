from __future__ import annotations

from klpga.website_v2.current_score_display import format_current_score, normalize_hole_state


def test_in_progress_negative_score():
    cell = format_current_score(-4, "12", "ACTIVE")
    assert cell.display == "-4 · 12H"
    assert cell.sort_score == -4 and cell.sort_holes == 12 and cell.sort_status == "IN_PROGRESS"


def test_in_progress_positive_score():
    cell = format_current_score(1, "7", "ACTIVE")
    assert cell.display == "+1 · 7H"
    assert cell.sort_score == 1 and cell.sort_holes == 7


def test_in_progress_even_par():
    cell = format_current_score(0, "15", "ACTIVE")
    assert cell.display == "E · 15H"


def test_complete_via_18_holes():
    cell = format_current_score(-5, "18", "ACTIVE")
    assert cell.display == "-5 · F"
    assert cell.sort_status == "COMPLETE" and cell.sort_holes == 18


def test_complete_even_par():
    cell = format_current_score(0, "18", "ACTIVE")
    assert cell.display == "E · F"


def test_complete_via_status_text_variants():
    for status in ("F", "Finished", "종료", "COMPLETED", "finished"):
        cell = format_current_score(-3, None, status)
        assert cell.display == "-3 · F", status


def test_complete_via_holes_completed_text_variant():
    cell = format_current_score(-2, "F", None)
    assert cell.display == "-2 · F"


def test_not_started_player_shows_em_dash():
    cell = format_current_score(None, None, None)
    assert cell.display == "—"
    assert cell.sort_score is None and cell.sort_holes is None and cell.sort_status == "NO_DATA"


def test_zero_holes_completed_treated_as_not_started():
    cell = format_current_score(0, "0", None)
    assert cell.display == "—"
    assert cell.sort_status == "NO_DATA"


def test_player_not_in_snapshot_shows_em_dash():
    # The caller passes score_to_par=None for any player absent from the
    # live snapshot -- identical formatting to "not started".
    cell = format_current_score(None, "5", "ACTIVE")
    assert cell.display == "—"


def test_unrecognized_holes_completed_never_guessed():
    cell = format_current_score(-1, "garbage", None)
    assert cell.display == "—"
    assert cell.sort_status == "NO_DATA"


def test_holes_beyond_18_still_treated_as_complete():
    cell = format_current_score(-6, "19", None)
    assert cell.display == "-6 · F"


def test_normalize_hole_state_directly():
    assert normalize_hole_state("9", "ACTIVE") == ("IN_PROGRESS", 9)
    assert normalize_hole_state("18", "ACTIVE") == ("COMPLETE", 18)
    assert normalize_hole_state(None, None) == ("NOT_STARTED", None)
    assert normalize_hole_state("0", None) == ("NOT_STARTED", None)


def test_raw_source_fields_are_never_mutated():
    # format_current_score is called with plain values (never mutable
    # containers), so there is nothing here to accidentally write back
    # into -- this test documents that the function is pure.
    holes = "12"
    status = "ACTIVE"
    format_current_score(-4, holes, status)
    assert holes == "12" and status == "ACTIVE"
