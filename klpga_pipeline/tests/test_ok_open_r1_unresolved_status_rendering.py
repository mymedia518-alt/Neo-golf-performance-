"""NEO P0 -- unresolved-round ("999" rank sentinel) / generic WD-DQ
status-aware row rendering.

klpga.parsers.leaderboard_parser's confirmed data-rank="999" sentinel
(a player whose round did not resolve to a real rank -- the source
data cannot distinguish WD/DQ/other, and this project never guesses)
is parsed as status="INCOMPLETE". Before this fix, scripts/84 rendered
that raw internal value literally: "999" as if it were a real rank,
and three separately repeated "산출 불가" placeholders across 오늘스코어
/선두와 타수차 (with the raw English word "INCOMPLETE" as the 상태
cell). 순위/현재스코어/오늘스코어/선두와 타수차 must instead render as a
plain EMPTY cell wherever a real value cannot exist -- never a
fabricated rank, never "—", never a repeated "computation failed"
message for what is really just "no value here". 완료홀 (holes
completed) and 선수/소속 stay untouched -- they are real, officially
collected facts, not part of the sentinel.

The 상태 cell itself is empty too when all the source gives us is the
bare 999 sentinel (status="INCOMPLETE"): the source never actually
says WD or DQ, so printing either word there would be a guess dressed
up as a fact, and printing a Korean sentence like "결과 미확인" is the
same guess with extra words. The SAME blank-cell treatment generically
applies to a literal "WD" or "DQ" status value for every OTHER cell in
the row -- but for THOSE, the 상태 cell shows that exact literal word,
because in that case (unlike bare INCOMPLETE) the source really did
say so. Never hardcoded to any specific player name, and never applied
to CUT (a cut player has a real, valid completed score/rank)."""
from pathlib import Path

import importlib.util

SPEC = importlib.util.spec_from_file_location(
    "ok_open_builder", Path(__file__).parents[1] / "scripts" / "84_build_ok_open_pre_website_candidate.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def _row(pid, name, status=None, holes="9", rank="1", total=-2):
    return {
        "player_id": pid,
        "player_name": name,
        "rank_display": rank,
        "total_under_par": total,
        "total_under_par_display": str(total) if total is not None else None,
        "holes_completed": holes,
        "today_under_par": total,
        "gap_to_leader": 0,
        "status": status,
    }


def test_unresolved_row_never_shows_the_raw_999_sentinel():
    row = _row("9183", "박결", status="INCOMPLETE", holes="10", rank="999", total=None)
    html = builder._r1_row_html(row, {}, lambda r: "")
    assert "999" not in html
    assert "—" not in html
    assert "<td></td>" in html


def test_unresolved_row_never_shows_the_raw_english_status_string():
    row = _row("9277", "김아현", status="INCOMPLETE", holes="1", rank="999", total=None)
    html = builder._r1_row_html(row, {}, lambda r: "")
    assert "INCOMPLETE" not in html
    # No Korean status label is fabricated for a bare 999 sentinel either
    # -- the 상태 cell is empty like the row's other unknown cells, not
    # a guessed "결과 미확인" sentence dressing up an unknown as a fact.
    assert "결과 미확인" not in html
    assert html.endswith("<td></td></tr>")


def test_unresolved_row_does_not_repeat_computation_failed_three_times():
    row = _row("9183", "박결", status="INCOMPLETE", holes="10", rank="999", total=None)
    html = builder._r1_row_html(row, {}, lambda r: "")
    assert html.count("산출 불가") == 0


def test_unresolved_row_still_shows_real_holes_completed():
    # holes_completed is factual (a real collected value), not part of
    # the sentinel -- it must never be blanked out.
    row = _row("9183", "박결", status="INCOMPLETE", holes="10", rank="999", total=None)
    html = builder._r1_row_html(row, {}, lambda r: "")
    assert "<td>10</td>" in html


def test_normal_in_progress_row_is_unaffected():
    row = _row("1", "선수A", status=None, holes="9", rank="1", total=-2)
    html = builder._r1_row_html(row, {}, lambda r: "")
    assert "<td>1</td>" in html
    assert "<td>-2.0</td>" in html or "<td>-2</td>" in html
    assert "진행중" in html
    assert "결과 미확인" not in html


def test_real_build_박결_and_김아현_are_never_shown_with_999_or_repeated_placeholder():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    for name in ("박결", "김아현"):
        idx = html.find(f"<span class='player'>{name}</span>")
        assert idx != -1, f"fixture assumption: {name} present in the real R1 snapshot"
        row_start = html.rfind("<tr>", 0, idx)
        row_end = html.find("</tr>", idx)
        row = html[row_start : row_end + 5]
        assert "999" not in row
        assert "INCOMPLETE" not in row
        assert "결과 미확인" not in row
        assert "—" not in row
        assert row.endswith("<td></td></tr>")  # 상태 cell: honest empty, no guessed label
        assert row.count("산출 불가") == 0


def test_real_build_has_no_literal_999_or_INCOMPLETE_anywhere_on_the_page():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert "INCOMPLETE" not in html
    assert "<td>999</td>" not in html


def test_generic_wd_status_gets_the_same_blank_cell_treatment():
    # Defensive coverage: WD is a defined (never yet observed live)
    # status value in the parser -- never hardcoded to a specific
    # player name, and must never leak "999" as if it were a rank.
    row = _row("1", "선수W", status="WD", holes="7", rank="999", total=None)
    html = builder._r1_row_html(row, {}, lambda r: "")
    assert "999" not in html
    assert html.count("산출 불가") == 0
    assert "—" not in html
    assert "<td></td>" in html  # rank/현재스코어/오늘스코어/선두차 -- all empty
    assert "<td>7</td>" in html  # 완료홀: real factual data, kept
    assert "WD" in html.split("</th>")[-1]  # 상태 cell clearly shows WD -- the source literally says so here


def test_generic_dq_status_gets_the_same_blank_cell_treatment():
    row = _row("2", "선수D", status="DQ", holes="3", rank="999", total=None)
    html = builder._r1_row_html(row, {}, lambda r: "")
    assert "999" not in html
    assert html.count("산출 불가") == 0
    assert "—" not in html
    assert "<td></td>" in html
    assert "<td>3</td>" in html
    assert "DQ" in html.split("</th>")[-1]


def test_cut_status_is_never_blanked_it_has_a_real_completed_score():
    # A cut player DID complete their round(s) with a real score/rank --
    # never apply the did-not-complete blank-cell treatment to CUT.
    row = _row("3", "선수C", status="CUT", holes="18", rank="55", total=3)
    html = builder._r1_row_html(row, {}, lambda r: "")
    assert "<td>55</td>" in html
    assert "<td>+3.0</td>" in html
    assert "CUT" in html.split("</th>")[-1]


def test_wd_dq_status_is_never_hardcoded_to_a_specific_player_name():
    # Same status, two arbitrary different names -- both get identical
    # generic treatment, proving this is not a per-name special case.
    for name in ("아무개1", "아무개2"):
        row = _row("9", name, status="WD", holes="5", rank="999", total=None)
        html = builder._r1_row_html(row, {}, lambda r: "")
        assert "999" not in html
        assert html.count("산출 불가") == 0


def test_incomplete_row_exact_markup_all_unresolved_cells_truly_empty():
    # Locks the full contract down precisely: every cell that cannot be
    # known (순위/현재스코어/오늘스코어/선두와 타수차/상태) is a bare
    # <td></td> -- not "—", not a guessed WD/DQ -- while 완료홀 and the
    # player name are the row's only real content.
    row = _row("9183", "박결", status="INCOMPLETE", holes="10", rank="999", total=None)
    html = builder._r1_row_html(row, {}, lambda r: "")
    assert html == (
        "<tr><td></td>"
        "<th scope='row'><span class='player'>박결</span></th>"
        "<td></td><td>10</td><td></td><td></td><td></td></tr>"
    )


def test_wd_row_exact_markup_status_cell_shows_wd_everything_else_empty():
    # Same lock-down for a row whose status IS literally "WD" -- the
    # only cell that differs from the INCOMPLETE case is 상태 itself.
    row = _row("1", "선수W", status="WD", holes="7", rank="999", total=None)
    html = builder._r1_row_html(row, {}, lambda r: "")
    assert html == (
        "<tr><td></td>"
        "<th scope='row'><span class='player'>선수W</span></th>"
        "<td></td><td>7</td><td></td><td></td><td>WD</td></tr>"
    )
