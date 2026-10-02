"""Regression for the 2026-10-02 'Set Difference 완전성 검증' mission:
before R2_CUT (or any later-round CUT state) may ever be computed as
Set Difference -- (prior round's real active player set) minus
(a later round's real captured player set) -- the later round's raw
capture must pass a 5-point PARTIAL HTML completeness gate.

Real incident this guards against: an operator-uploaded "3R 리더보드"
capture contained only 61 of this tournament's real ~102 active
players after R2, missing EXACTLY the lower half of the real R2
standings, with that capture's own <script> content showing it polls a
live 'getRoundLeaderboard("3")' AJAX endpoint inside a setTimeout
refresh loop rather than rendering completely in one shot. Computing
R2_CUT = (R2 active) - (that capture's players) would have silently
mislabeled 41 real, still-competing players as cut.

validate_round_html_completeness/parse_cut_by_set_difference take a
parsed {player_id: rank-or-None} dict, not raw HTML, so these tests
exercise them with small, explicitly-synthetic inputs built to mirror
that real incident's exact shape (short count, ranks stopping short,
the real lazy-load marker string, an unknown id, an internal rank
gap) -- never a claim about real tournament facts, purely proving the
gate's own logic. No real complete R3 capture exists yet in this
checkout to test the full parse_cut_by_set_difference() path against
real official-format raw evidence."""
from __future__ import annotations

import json

import pytest

from klpga.neo_win import hitejinro_round_pipeline as rp

pytestmark = pytest.mark.round_pipeline


def _complete_set(n: int) -> dict[str, int]:
    """n players, ranks 1..n, no ties, no gaps -- the cleanest possible
    'fully complete' capture."""
    return {str(i): i for i in range(1, n + 1)}


def test_passes_cleanly_when_the_capture_is_genuinely_complete():
    prior_active_ids = {str(i) for i in range(1, 103)}
    found = _complete_set(102)
    result = rp.validate_round_html_completeness(
        3, found, prior_active_ids=prior_active_ids, entrant_ids=set(prior_active_ids), lazy_load_detected=False,
    )
    assert result["r2_active_count"] == 102
    assert result["r3_player_count"] == 102
    assert result["r3_last_rank"] == 102
    assert result["rank_continuity_ok"] is True
    assert result["unknown_ids"] == []


def test_real_incident_shape_is_rejected_on_all_3_applicable_checks():
    """Mirrors the real operator-uploaded R3 capture's exact shape:
    102 real active players expected, only 61 found, ranks stopping at
    61, and the real confirmed lazy-load marker present."""
    prior_active_ids = {str(i) for i in range(1, 103)}
    found = _complete_set(61)
    with pytest.raises(rp.PartialHTMLError) as exc_info:
        rp.validate_round_html_completeness(
            3, found, prior_active_ids=prior_active_ids, entrant_ids=set(prior_active_ids), lazy_load_detected=True,
        )
    msg = str(exc_info.value)
    assert "fails 3/5" in msg
    assert "[1/2]" in msg and "41 real active player(s)" in msg
    assert "[3]" in msg
    assert "[4]" in msg and "getRoundLeaderboard" in msg


def test_check_2_short_player_count_alone_fails():
    prior_active_ids = {str(i) for i in range(1, 11)}
    found = _complete_set(9)  # one real active player missing, nothing else wrong
    with pytest.raises(rp.PartialHTMLError, match=r"\[1/2\].*1 real active player\(s\)"):
        rp.validate_round_html_completeness(
            3, found, prior_active_ids=prior_active_ids, entrant_ids=set(prior_active_ids), lazy_load_detected=False,
        )


def test_check_3_last_rank_short_of_active_count_fails():
    # 10 active expected, 10 players found (count matches!) but their
    # real ranks only reach 9 (e.g. two players tied at rank 9,
    # nothing reaches 10) -- count alone wouldn't catch this.
    prior_active_ids = {str(i) for i in range(1, 11)}
    found = {str(i): i for i in range(1, 9)}
    found["9a"] = 9
    found["9b"] = 9
    assert len(found) == 10
    with pytest.raises(rp.PartialHTMLError, match=r"\[3\] last real rank found \(9\)"):
        rp.validate_round_html_completeness(
            3, found, prior_active_ids=prior_active_ids, entrant_ids=set(prior_active_ids), lazy_load_detected=False,
        )


def test_check_4_lazy_load_detected_fails_unconditionally_even_if_counts_match():
    prior_active_ids = {str(i) for i in range(1, 11)}
    found = _complete_set(10)  # otherwise perfect
    with pytest.raises(rp.PartialHTMLError, match=r"\[4\]"):
        rp.validate_round_html_completeness(
            3, found, prior_active_ids=prior_active_ids, entrant_ids=set(prior_active_ids), lazy_load_detected=True,
        )


def test_check_5a_unknown_player_id_fails():
    prior_active_ids = {str(i) for i in range(1, 11)}
    found = _complete_set(10)
    found["999999"] = 11  # not a real entrant
    with pytest.raises(rp.PartialHTMLError, match=r"\[5a\] 1 player_id\(s\).*999999"):
        rp.validate_round_html_completeness(
            3, found, prior_active_ids=prior_active_ids, entrant_ids=set(prior_active_ids), lazy_load_detected=False,
        )


def test_check_5b_internal_rank_gap_fails_even_though_count_and_last_rank_are_fine():
    """A hole in the MIDDLE of the capture (e.g. ranks 1-5 and 9-13
    present, 6-8 entirely missing) -- distinct failure mode from
    checks 2/3, which only catch a capture that stops short at the
    END. Total count (10) and last rank (13 > 10) both look fine in
    isolation; only the gap check catches this."""
    prior_active_ids = {str(i) for i in range(1, 11)}
    found = {str(i): i for i in range(1, 6)}
    found.update({str(i): i for i in range(9, 14)})
    assert len(found) == 10
    with pytest.raises(rp.PartialHTMLError, match=r"\[5b\] rank sequence has 1 internal gap"):
        rp.validate_round_html_completeness(
            3, found, prior_active_ids=prior_active_ids, entrant_ids=set(prior_active_ids), lazy_load_detected=False,
        )


def test_check_5b_ties_never_count_as_a_gap():
    """A real 3-way tie at rank 5 legitimately means the next real
    rank is 8 (5,5,5,8,...) -- this must NOT be flagged as a gap."""
    prior_active_ids = {str(i) for i in range(1, 8)}
    found = {"1": 1, "2": 2, "3": 3, "4": 4, "5a": 5, "5b": 5, "5c": 5, "8": 8}
    assert len(found) == 8
    result = rp.validate_round_html_completeness(
        3, found, prior_active_ids=prior_active_ids, entrant_ids=set(found), lazy_load_detected=False,
    )
    assert result["rank_continuity_ok"] is True


def test_lazy_load_detected_matches_the_real_confirmed_marker():
    """2026-10-02: the real operator-uploaded R3 capture's own
    <script> content contains this exact literal call inside a
    setTimeout refresh loop -- confirmed by direct inspection of that
    file this session, not a guess."""
    real_snippet = (
        'if(autoRoundLeaderboardYn == "Y" && gameCurrentRound == "3"){\n'
        '\trefreshTimer = setTimeout(function(){\n'
        '\t\tvar height = $(document).scrollTop();\n'
        '\t\tgetRoundLeaderboard("3");\n'
        '\t},1000*autoSec);\n'
        '}\n'
    )
    assert rp._lazy_load_detected(real_snippet) is True
    assert rp._lazy_load_detected("<html><body>no such marker here</body></html>") is False


def test_player_ranks_from_leaderboard_html_reuses_the_real_row_regex():
    """_player_ranks_from_leaderboard_html must read rank==999 as
    "still in progress" (None), never a fabricated numeric rank --
    same real convention the rest of this module (parse_leaderboard)
    already uses for an incomplete row."""
    html = (
        '<li id="favoritItem_11076"[]data-rank="999" data-name="조하리" '
        'data-totunderpar="0" data-inghole="10" data-todayunderpar="0" data-score="0" '
        'data-round1score="88" data-round2score="" data-round3score="" data-round4score="" '
        'data-updown="999">'
        '<li id="favoritItem_1"[]data-rank="1" data-name="x" '
        'data-totunderpar="-4" data-inghole="" data-todayunderpar="" data-score="0" '
        'data-round1score="70" data-round2score="70" data-round3score="" data-round4score="" '
        'data-updown="0">'
    ).replace("[]", " ")
    ranks = rp._player_ranks_from_leaderboard_html(html)
    assert ranks == {"11076": None, "1": 1}


def test_parse_cut_by_set_difference_raises_cleanly_without_a_prior_leaderboard(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "LEADERBOARD_PATH", tmp_path / "LEADERBOARD.json")
    with pytest.raises(FileNotFoundError, match=r"parse_leaderboard\(2\) must run first"):
        rp.parse_cut_by_set_difference(3)


def test_parse_cut_by_set_difference_refuses_the_real_uploaded_r3_shape(tmp_path, monkeypatch):
    """End-to-end through parse_cut_by_set_difference() itself (not
    just the lower-level validator): given the real production R2
    LEADERBOARD.json (102 real active players) and a synthetic R3 raw
    HTML built to mirror the real uploaded capture's exact shape (61
    players found, real lazy-load marker present), this must raise
    PartialHTMLError and never return a Set Difference result."""
    from klpga.tournament_context import CONTENT_DIR

    monkeypatch.setattr(rp, "LEADERBOARD_PATH", tmp_path / "LEADERBOARD.json")
    real_board = json.loads((CONTENT_DIR / "2026100005_LEADERBOARD.json").read_text(encoding="utf-8"))
    (tmp_path / "LEADERBOARD.json").write_text(json.dumps(real_board, ensure_ascii=False), encoding="utf-8")
    active_ids = [r["player_id"] for r in real_board["records"] if r.get("status") is None]
    assert len(active_ids) == 102  # real production fact, re-confirmed here

    rows = "".join(
        f'<li id="favoritItem_{pid}" data-rank="{i + 1}" data-name="x" '
        f'data-totunderpar="0" data-inghole="" data-todayunderpar="" data-score="0" '
        f'data-round1score="70" data-round2score="70" data-round3score="" data-round4score="" '
        f'data-updown="0">'
        for i, pid in enumerate(active_ids[:61])
    )
    raw_html = rows + 'getRoundLeaderboard("3");'  # real confirmed lazy-load marker
    raw_path = tmp_path / "r3_raw.html"
    raw_path.write_text(raw_html, encoding="utf-8")

    with pytest.raises(rp.PartialHTMLError, match=r"fails 3/5"):
        rp.parse_cut_by_set_difference(3, raw_path=raw_path)
