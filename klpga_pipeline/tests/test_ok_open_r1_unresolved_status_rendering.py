"""NEO P0 -- unresolved-round ("999" rank sentinel) row rendering.

klpga.parsers.leaderboard_parser's confirmed data-rank="999" sentinel
(a player whose round did not resolve to a real rank -- the source
data cannot distinguish WD/DQ/other, and this project never guesses)
is parsed as status="INCOMPLETE". Before this fix, scripts/84 rendered
that raw internal value literally: "999" as if it were a real rank,
and three separately repeated "산출 불가" placeholders across 오늘스코어
/선두와 타수차 (with the raw English word "INCOMPLETE" as the 상태
cell). This must instead show a single honest, translated status
("결과 미확인") with "—" everywhere a real value cannot exist -- never
a fabricated rank, never a misleading repeated "computation failed"
message for what is really just "no score available"."""
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
    assert "<td>—</td>" in html


def test_unresolved_row_never_shows_the_raw_english_status_string():
    row = _row("9277", "김아현", status="INCOMPLETE", holes="1", rank="999", total=None)
    html = builder._r1_row_html(row, {}, lambda r: "")
    assert "INCOMPLETE" not in html
    assert "결과 미확인" in html


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
        assert "결과 미확인" in row
        assert row.count("산출 불가") == 0


def test_real_build_has_no_literal_999_or_INCOMPLETE_anywhere_on_the_page():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert "INCOMPLETE" not in html
    assert "<td>999</td>" not in html
