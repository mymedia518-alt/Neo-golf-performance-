"""Tests for klpga.collectors.score_record -- fetch-only against the
real, URL-confirmed /web/tourRecord/scoreRecord endpoint. No parsing
logic exists yet (the page's DOM structure has not been confirmed
against real markup), so this only verifies the fetch call itself:
correct URL, correct (and ONLY) gameCode parameter, always-live (never
cached) fetch, real HTTP status + raw text returned unmodified, that a
real fetch failure propagates rather than being swallowed here, and
that the not-yet-implemented parser fails loudly and specifically
rather than silently guessing at markup it has never seen."""
from __future__ import annotations

import pytest

from klpga import config
from klpga.collectors.score_record import (
    fetch_score_record_html,
    parse_score_record_hole_by_hole,
    parse_score_record_html,
)


class FakeClient:
    """Duck-typed stand-in for PoliteHttpClient.get_text_with_status."""

    def __init__(self, responses_by_key: dict[tuple, tuple[int, str]], error_keys: frozenset = frozenset()):
        self.responses_by_key = responses_by_key
        self.error_keys = error_keys
        self.calls: list[tuple] = []

    def get_text_with_status(self, url, params=None, **kwargs):
        key = (url, tuple(sorted((params or {}).items())))
        self.calls.append(key)
        if key in self.error_keys:
            raise ConnectionError(f"simulated real network failure for {key}")
        return self.responses_by_key[key]


def test_fetch_score_record_html_calls_confirmed_endpoint_with_only_game_code():
    key = (config.SCORE_RECORD_ENDPOINT, (("gameCode", "2026120001"),))
    client = FakeClient({key: (200, "<html>raw score record page</html>")})

    status, html = fetch_score_record_html(client, "2026120001")

    assert status == 200
    assert html == "<html>raw score record page</html>"
    assert client.calls == [key]


def test_fetch_score_record_html_returns_raw_text_unparsed():
    raw = "<html><body>whatever real markup the site sends</body></html>"
    key = (config.SCORE_RECORD_ENDPOINT, (("gameCode", "9999999999"),))
    client = FakeClient({key: (200, raw)})

    status, html = fetch_score_record_html(client, "9999999999")

    assert status == 200
    assert html == raw


def test_fetch_score_record_html_propagates_real_fetch_failures():
    key = (config.SCORE_RECORD_ENDPOINT, (("gameCode", "2026120001"),))
    client = FakeClient({}, error_keys=frozenset({key}))

    with pytest.raises(ConnectionError):
        fetch_score_record_html(client, "2026120001")


def test_parse_score_record_html_rejects_unseen_markup():
    # This project never writes a parser against DOM structure it has
    # not actually seen -- see scripts/97_fetch_score_record_sample.py.
    # Any input, including well-formed-looking HTML, must raise the
    # same explicit NotImplementedError rather than silently returning
    # a plausible-looking but fabricated result.
    with pytest.raises(ValueError):
        parse_score_record_html("<html><table><tr><td>박결</td><td>WD</td></tr></table></html>")
def test_parse_score_record_html_real_fixture_extracts_r1_statuses_and_scores():
    from pathlib import Path
    fixture = Path(__file__).parent / "fixtures" / "score_record_2026120001_r1.html"
    rows = parse_score_record_html(fixture.read_text(encoding="utf-8"))
    assert len(rows) == 120
    assert sum(r["official_status"] == "WD" for r in rows) == 2
    assert sum(r["official_status"] is None and r["final_score"] is not None for r in rows) == 118


# ---------------------------------------------------------------------
# Hole-by-hole extraction (NEO CMPRO FULL COLLECTION score cross-check,
# 2026-09-21) -- tested against a real, byte-faithful trimmed excerpt
# of the same confirmed scoreRecord capture used above (game_code
# 2026120001, round-one: <thead> + its first 6 real <tbody> rows kept
# verbatim). NOT the 2026090002 tournament this cross-check is
# ultimately for -- that game was never captured -- this only proves
# the parser is correct against real, confirmed markup.
# ---------------------------------------------------------------------

def _hole_by_hole_fixture_html():
    from pathlib import Path
    fixture = Path(__file__).parent / "fixtures" / "score_record_2026120001_round_one_trimmed_real_excerpt.html"
    return fixture.read_text(encoding="utf-8")


def test_parse_score_record_hole_by_hole_real_fixture_row_count_and_names():
    rows = parse_score_record_hole_by_hole(_hole_by_hole_fixture_html(), round_tab_id="round-one")
    assert len(rows) == 6
    assert [r["player_name"] for r in rows] == ["양효진", "이예원", "신다인", "오수민 0809(A)", "고지우", "한지원"]


def test_parse_score_record_hole_by_hole_real_fixture_first_row_holes_match_out_in():
    rows = parse_score_record_hole_by_hole(_hole_by_hole_fixture_html(), round_tab_id="round-one")
    yang = rows[0]
    assert yang["player_name"] == "양효진"
    assert yang["rank_display"] == "T1"
    assert yang["official_status"] is None
    assert [yang["holes"][h] for h in range(1, 10)] == [5, 5, 2, 4, 4, 4, 4, 2, 5]
    assert [yang["holes"][h] for h in range(10, 19)] == [4, 4, 3, 4, 4, 5, 3, 3, 3]
    assert sum(yang["holes"][h] for h in range(1, 10)) == 35  # real OUT cell
    assert sum(yang["holes"][h] for h in range(10, 19)) == 33  # real IN cell


def test_parse_score_record_hole_by_hole_missing_round_tab_raises():
    with pytest.raises(ValueError):
        parse_score_record_hole_by_hole(_hole_by_hole_fixture_html(), round_tab_id="round-four")


def test_parse_score_record_hole_by_hole_skips_rows_missing_expected_cells():
    # A row lacking rank/name/out/in entirely (e.g. a divider row) is
    # skipped, not treated as a player -- never guessed.
    rows = parse_score_record_hole_by_hole(
        '<div id="round-one"><table><tbody><tr><td colspan="31">divider</td></tr></tbody></table></div>',
        round_tab_id="round-one",
    )
    assert rows == []


def test_parse_score_record_hole_by_hole_rejects_wrong_hole_cell_count():
    # rank/name/out/in are all present, but only 2 cells sit between
    # name and out (never confirmed as 9) -- refuses to guess mapping.
    html = (
        '<div id="round-one"><table><tbody><tr>'
        '<td class="rank">T1</td><td class="name">테스트</td>'
        '<td class="h1">4</td><td class="h2">4</td>'
        '<td class="out">8</td><td class="in">36</td>'
        '</tr></tbody></table></div>'
    )
    with pytest.raises(ValueError):
        parse_score_record_hole_by_hole(html, round_tab_id="round-one")
