"""FINAL R2 EVIDENCE-GATE TASK: synthetic precedence-rule unit tests
for klpga.collectors.score_record.parse_score_record_round_table --
edge cases the one real captured fixture doesn't happen to exercise
(explicit DQ, explicit literal "CUT" text, no boundary at all).
Isolated, fabricated markup only -- structurally matches the real
confirmed td.rank/td.name classes and tr.table-cut/"Missed Cut"
contract, never claimed as itself real evidence (see
test_score_record_round_table.py for the real-fixture coverage)."""
from __future__ import annotations

from klpga.collectors.score_record import parse_score_record_round_table


def _row(rank: str, name: str) -> str:
    return f'<tr><td class="rank">{rank}</td><td class="name">{name}</td></tr>'


def _boundary_row() -> str:
    return '<tr class="table-cut"><td colspan="31"><div class="bartitle-green">Missed Cut</div></td></tr>'


def _page(rows_html: str) -> str:
    return f'<html><body><div id="round-two"><table><tbody>{rows_html}</tbody></table></div></body></html>'


def test_no_boundary_means_cut_known_false_and_nobody_is_cut():
    html = _page(_row("1", "선수A") + _row("2", "선수B"))
    result = parse_score_record_round_table(html, round_tab_id="round-two")
    assert result["cut_boundary_published"] is False
    assert all(r["official_status"] is None for r in result["rows"])


def test_boundary_present_cut_known_true_rows_after_are_cut():
    html = _page(_row("1", "선수A") + _boundary_row() + _row("2", "선수B"))
    result = parse_score_record_round_table(html, round_tab_id="round-two")
    assert result["cut_boundary_published"] is True
    rows = {r["player_name"]: r["official_status"] for r in result["rows"]}
    assert rows["선수A"] is None
    assert rows["선수B"] == "CUT"


def test_explicit_dq_after_boundary_stays_dq_never_becomes_cut():
    html = _page(_row("1", "선수A") + _boundary_row() + _row("DQ", "선수C"))
    result = parse_score_record_round_table(html, round_tab_id="round-two")
    rows = {r["player_name"]: r["official_status"] for r in result["rows"]}
    assert rows["선수C"] == "DQ"


def test_explicit_dns_after_boundary_stays_dns_never_becomes_cut():
    html = _page(_boundary_row() + _row("DNS", "선수D"))
    result = parse_score_record_round_table(html, round_tab_id="round-two")
    rows = {r["player_name"]: r["official_status"] for r in result["rows"]}
    assert rows["선수D"] == "DNS"


def test_explicit_literal_cut_text_before_any_boundary_still_recognized():
    """Preserves the literal-CUT-text signal as another explicit
    official channel, matching a7a2a24's own convention for the
    sibling roundLeaderboard format -- never observed live on this
    page either, but handled the same way if it ever appears."""
    html = _page(_row("CUT", "선수E") + _row("1", "선수F"))
    result = parse_score_record_round_table(html, round_tab_id="round-two")
    rows = {r["player_name"]: r["official_status"] for r in result["rows"]}
    assert rows["선수E"] == "CUT"
    assert result["cut_boundary_published"] is False  # no real divider row -- a different signal


def test_explicit_wd_before_boundary_stays_wd():
    """WD anywhere in the document -- not just after the boundary --
    is always the row's own real status, never touched."""
    html = _page(_row("WD", "선수G") + _boundary_row() + _row("2", "선수H"))
    result = parse_score_record_round_table(html, round_tab_id="round-two")
    rows = {r["player_name"]: r["official_status"] for r in result["rows"]}
    assert rows["선수G"] == "WD"
    assert rows["선수H"] == "CUT"


def test_missing_player_contributes_no_row_never_a_cut_signal():
    """A player simply not present in this table's rows at all --
    absence is never evidence, in either direction."""
    html = _page(_row("1", "선수A") + _boundary_row() + _row("2", "선수B"))
    result = parse_score_record_round_table(html, round_tab_id="round-two")
    names = {r["player_name"] for r in result["rows"]}
    assert "선수Z" not in names  # never fabricated into existence, cut or otherwise
    assert len(result["rows"]) == 2


def test_multiple_boundary_rows_all_recognized_still_past_boundary_after_first():
    """Defensive: even if a real page ever emitted more than one
    divider (never observed), everything after the FIRST one is
    correctly treated as past-boundary, and the flag stays True."""
    html = _page(_row("1", "선수A") + _boundary_row() + _row("2", "선수B") + _boundary_row() + _row("3", "선수C"))
    result = parse_score_record_round_table(html, round_tab_id="round-two")
    assert result["cut_boundary_published"] is True
    rows = {r["player_name"]: r["official_status"] for r in result["rows"]}
    assert rows["선수A"] is None
    assert rows["선수B"] == "CUT"
    assert rows["선수C"] == "CUT"


def test_table_cut_class_without_missed_cut_text_is_not_a_boundary():
    """Requires BOTH the confirmed class AND the confirmed text --
    class alone (e.g. some unrelated styling reuse) must never
    false-positive as the real official boundary."""
    html = _page(_row("1", "선수A") + '<tr class="table-cut"><td>단순 스타일</td></tr>' + _row("2", "선수B"))
    result = parse_score_record_round_table(html, round_tab_id="round-two")
    assert result["cut_boundary_published"] is False
    rows = {r["player_name"]: r["official_status"] for r in result["rows"]}
    assert rows["선수B"] is None


def test_missed_cut_text_without_table_cut_class_is_not_a_boundary():
    """The inverse: real confirmed text alone, on some unrelated row,
    must never false-positive either -- both signals are required."""
    html = _page(_row("1", "선수A") + '<tr><td>Missed Cut somewhere unrelated</td></tr>' + _row("2", "선수B"))
    result = parse_score_record_round_table(html, round_tab_id="round-two")
    assert result["cut_boundary_published"] is False
