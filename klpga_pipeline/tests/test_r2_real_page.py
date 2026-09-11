"""R2 HOUSE red-team P0-1: the real-data R2 renderer.

Every fixture here is ISOLATED and SYNTHETIC -- fabricated player_ids,
names, and numbers invented only for this test file, never read from
or written into any real production artifact (content/website_v2/*.json,
docs/, candidate/). This is exactly the "isolated synthetic TEST
FIXTURES" the P0-1 spec requires, kept in its own file (not
test_r2_house.py) so a reader can never mistake these numbers for real
R2 evidence.

FIELD-NAME CORRECTION (fix/kb-r2-official-cut-gate-20260911, real
production visual QA failure): every fixture record here now uses the
REAL R2 freeze schema's own field names -- `r1_score_to_par` and
`r2_score_to_par` -- not the `round_to_par`/`total_to_par` names this
file previously fabricated. Those two names were NEVER what the real
freeze (klpga.neo_win.r2_freeze, written by scripts/112) actually
produces, so every test in the previous version of this file exercised
the renderer against a self-consistent but entirely fictional input
shape -- which is exactly how a real production run (every rank T1,
TOTAL/2R both "--" for all 118 real players) shipped with 168/168 green
tests. See tests/test_r2_rendered_output_regression.py for the
regression that checks the renderer against the REAL committed
artifacts directly, and r2_real_page.py's own _total_to_par docstring
for the full root-cause trace."""
from __future__ import annotations

import re

import pytest

from klpga.neo_win.r2_real_page import render_r2_real_page, is_real_page
from klpga.neo_win.r2_wait_page import is_wait_page, render_r2_wait_page

GAME_CODE = "TEST0001"
TOURNAMENT_NAME = "SYNTHETIC TEST OPEN"


def _freeze(records):
    return {"records": records}


def _forecast(records):
    return {"records": records}


def _sg(status, sg_by_player_id=None):
    return {"status": status, "sg_by_player_id": sg_by_player_id or {}}


def _fixture_html(*, records, forecast_records=None, sg_status="AVAILABLE", sg_by_id=None, sponsor_by_id=None):
    return render_r2_real_page(
        tournament_name=TOURNAMENT_NAME, game_code=GAME_CODE, date_range="2026.01.01 — 01.04",
        r2_freeze=_freeze(records), forecast=_forecast(forecast_records or []),
        sg_ingest=_sg(sg_status, sg_by_id), sponsor_by_id=sponsor_by_id or {},
    )


def _rows(html: str) -> list[str]:
    return re.findall(r"<tr[^>]*>(?:(?!</tr>).)*</tr>", html.split("<tbody>", 1)[1].split("</tbody>", 1)[0])


# ---------------------------------------------------------------------
# Required public column structure (13 columns, exact order)
# ---------------------------------------------------------------------

def test_header_carries_all_13_required_columns_in_order():
    html = _fixture_html(records=[])
    header = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL).group(1)
    labels = re.findall(r"<th>([^<]*)</th>", header)
    assert labels == ["순위", "선수", "합계", "2R", "SG TOTAL", "SG OTT", "SG APP", "SG ARG", "SG PUTT",
                       "우승", "Top5", "Top10", "Top20"]


def test_uses_the_r2_full_leaderboard_modifier_class():
    html = _fixture_html(records=[])
    assert "leaderboard-table leaderboard-table--r2-full" in html


# ---------------------------------------------------------------------
# Never fabricates a player row -- population must be exactly the
# frozen R2 evidence's own records, no more, no fewer.
# ---------------------------------------------------------------------

def test_row_count_matches_frozen_records_exactly_not_forecast_or_sg():
    records = [
        {"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": -1, "r2_score_to_par": -1},
        {"player_id": "p2", "player_name": "선수이", "status": "ACTIVE", "r1_score_to_par": 1, "r2_score_to_par": 0},
        {"player_id": "p3", "player_name": "선수삼", "status": "CUT", "r1_score_to_par": 3, "r2_score_to_par": 5},
    ]
    # forecast/SG only cover a SUBSET (p1) -- the real-world case of a
    # player excluded from simulation / SG join -- must not shrink the
    # rendered population, and an extra forecast/SG player (p9, not in
    # the freeze at all) must never leak a row that was never frozen.
    forecast_records = [
        {"player_id": "p1", "win_pct": 5.0, "top5_pct": 20.0, "top10_pct": 40.0, "top20_pct": 60.0},
        {"player_id": "p9", "win_pct": 99.0, "top5_pct": 99.0, "top10_pct": 99.0, "top20_pct": 99.0},
    ]
    sg_by_id = {"p1": {"total": 1.0, "off_the_tee": 0.4, "approach": 0.3, "around_green": 0.2, "putting": 0.1},
                "p9": {"total": 9.0, "off_the_tee": 9.0, "approach": 9.0, "around_green": 9.0, "putting": 9.0}}
    html = _fixture_html(records=records, forecast_records=forecast_records, sg_by_id=sg_by_id)
    rows = _rows(html)
    assert len(rows) == 3
    assert "선수일" in html and "선수이" in html and "선수삼" in html
    assert "9.0" not in html and "99.0" not in html  # p9 never rendered -- not a real frozen entrant


# ---------------------------------------------------------------------
# CUT/WD/DQ players are shown, never dropped, with a real status badge
# ---------------------------------------------------------------------

@pytest.mark.parametrize("status", ["CUT", "WD", "DQ"])
def test_non_active_status_is_shown_never_silently_dropped(status):
    records = [{"player_id": "p1", "player_name": "선수일", "status": status, "r1_score_to_par": 2, "r2_score_to_par": 4}]
    html = _fixture_html(records=records)
    assert "선수일" in html
    assert f"<span class='status-badge'>{status}</span>" in html


def test_active_status_shows_no_badge():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": -1}]
    html = _fixture_html(records=records)
    assert "status-badge" not in html


# ---------------------------------------------------------------------
# Sponsor invariant: identity + sponsor slot always present together,
# sponsor directly follows player name (render_player_identity), never
# fabricated when unknown.
# ---------------------------------------------------------------------

def test_sponsor_slot_present_for_every_row_even_when_unknown():
    records = [
        {"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0},
        {"player_id": "p2", "player_name": "선수이", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0},
    ]
    html = _fixture_html(records=records, sponsor_by_id={"p1": "SYNTH SPONSOR CO"})
    assert html.count("class='player-name'") == 2
    assert html.count("class='player-sponsor'") == 2
    assert "SYNTH SPONSOR CO" in html
    # p2 has no known sponsor -- the slot must still exist (structurally
    # present, empty content), never a guessed/placeholder sponsor name.
    for row in _rows(html):
        if "선수이" in row:
            assert re.search(r"class='player-sponsor'></span>", row)


def test_sponsor_immediately_follows_player_name_in_dom_order():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0}]
    html = _fixture_html(records=records, sponsor_by_id={"p1": "SPONSOR X"})
    name_idx = html.index("class='player-name'")
    sponsor_idx = html.index("class='player-sponsor'")
    assert name_idx < sponsor_idx < name_idx + 200  # same identity block, not scattered elsewhere


# ---------------------------------------------------------------------
# R2 score info: real r1_score_to_par/r2_score_to_par displayed -- 2R
# is the real r2_score_to_par, TOTAL is the real r1+r2 sum (see
# r2_real_page._total_to_par -- there is no "total_to_par" field on the
# real freeze; it is always COMPUTED here, never read off a nonexistent
# key). A missing value never renders as 0/E, always the explicit empty
# mark.
# ---------------------------------------------------------------------

def test_real_score_values_render_with_par_notation():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": 5, "r2_score_to_par": -3}]
    html = _fixture_html(records=records)
    row = _rows(html)[0]
    assert "data-label='2R'>-3<" in row
    assert "data-label='합계'>+2<" in row  # 5 + (-3) = 2


def test_total_is_the_real_sum_of_r1_and_r2_not_a_separately_read_field():
    """The exact bug this fix corrects: TOTAL must be COMPUTED from the
    real r1_score_to_par + r2_score_to_par, never read from a
    "total_to_par" key the real freeze schema never has."""
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": -2}]
    html = _fixture_html(records=records)
    row = _rows(html)[0]
    assert "data-label='합계'>-7<" in row  # -5 + -2 = -7, not "--"


def test_missing_score_renders_empty_mark_never_zero():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": None, "r2_score_to_par": None}]
    html = _fixture_html(records=records)
    row = _rows(html)[0]
    assert "data-label='2R'>—<" in row
    assert "data-label='합계'>—<" in row
    assert "data-label='2R'>0<" not in row


def test_total_missing_when_only_r1_present_never_half_computed():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": None}]
    html = _fixture_html(records=records)
    row = _rows(html)[0]
    assert "data-label='합계'>—<" in row  # never fabricated as just r1's value
    assert "data-label='2R'>—<" in row


# ---------------------------------------------------------------------
# SG TOTAL/OTT/APP/ARG/PUTT: real values when AVAILABLE, honest empty
# mark when NOT_AVAILABLE -- never fabricated/interpolated.
# ---------------------------------------------------------------------

def test_sg_available_renders_real_signed_values():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0}]
    sg_by_id = {"p1": {"total": 3.21, "off_the_tee": 1.0, "approach": 0.8, "around_green": 0.3, "putting": 1.11}}
    html = _fixture_html(records=records, sg_by_id=sg_by_id, sg_status="AVAILABLE")
    row = _rows(html)[0]
    assert "data-label='SG TOTAL'>+3.21<" in row
    assert "data-label='SG OTT'>+1.00<" in row
    assert "data-label='SG PUTT'>+1.11<" in row


def test_sg_not_available_renders_empty_mark_for_every_sg_cell_never_zero():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0}]
    html = _fixture_html(records=records, sg_status="NOT_AVAILABLE")
    row = _rows(html)[0]
    for label in ("SG TOTAL", "SG OTT", "SG APP", "SG ARG", "SG PUTT"):
        assert f"data-label='{label}' class='metric-empty'>—<" in row or f"class='metric-empty' data-label='{label}'>—<" in row
    assert "스트로크 게인드 데이터가 아직" in html  # honest disclosure note, only when unavailable


def test_sg_available_note_is_absent_when_sg_actually_shown():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0}]
    sg_by_id = {"p1": {"total": 1.0, "off_the_tee": 0.4, "approach": 0.3, "around_green": 0.2, "putting": 0.1}}
    html = _fixture_html(records=records, sg_by_id=sg_by_id, sg_status="AVAILABLE")
    assert "스트로크 게인드 데이터가 아직" not in html


# ---------------------------------------------------------------------
# WIN/TOP5/TOP10/TOP20: real forecast values, honest empty mark for a
# player excluded from simulation (e.g. CUT, or missing PRE profile).
# ---------------------------------------------------------------------

def test_forecast_probabilities_render_from_real_forecast_row():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0}]
    forecast_records = [{"player_id": "p1", "win_pct": 12.5, "top5_pct": 40.25, "top10_pct": 60.0, "top20_pct": 80.0}]
    html = _fixture_html(records=records, forecast_records=forecast_records)
    row = _rows(html)[0]
    assert "class='win' data-label='우승'>12.5%<" in row
    assert "class='win' data-label='Top5'>40.2%<" in row  # 1-decimal display boundary only


def test_player_missing_from_forecast_gets_empty_mark_never_fabricated_probability():
    records = [{"player_id": "p1", "player_name": "선수일", "status": "CUT", "r1_score_to_par": 0, "r2_score_to_par": 5}]
    html = _fixture_html(records=records, forecast_records=[])
    row = _rows(html)[0]
    for label in ("우승", "Top5", "Top10", "Top20"):
        assert f"data-label='{label}'>—<" in row


# ---------------------------------------------------------------------
# Ranking: DERIVED from the real cumulative total (r1+r2), ties share a
# rank. THIS IS THE EXACT PRODUCTION BUG: reading a nonexistent
# "total_to_par" field made every player's sort key identical, so
# real ACTIVE and CUT players alike all rendered as a tied "T1".
# ---------------------------------------------------------------------

def test_ranking_ascending_by_real_cumulative_total_ties_share_rank():
    records = [
        {"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": 0},
        {"player_id": "p2", "player_name": "B", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": 0},
        {"player_id": "p3", "player_name": "C", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0},
    ]
    html = _fixture_html(records=records)
    rows = _rows(html)
    assert "data-label='순위'>T1<" in rows[0]
    assert "data-label='순위'>T1<" in rows[1]
    assert "data-label='순위'>3<" in rows[2]


def test_cut_player_with_real_scores_gets_a_real_distinct_rank_never_fabricated_t1():
    """Reproduces the exact real production symptom: an ACTIVE leader,
    a mid-field ACTIVE player, and a real CUT player with a real, worse
    total -- none of them may all collapse onto a shared fake "T1"."""
    records = [
        {"player_id": "p1", "player_name": "리더", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": -2},
        {"player_id": "p2", "player_name": "중위권", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": -1},
        {"player_id": "p3", "player_name": "컷탈락", "status": "CUT", "r1_score_to_par": 3, "r2_score_to_par": 5},
    ]
    html = _fixture_html(records=records)
    by_name = {name: row for row in _rows(html) for name in ("리더", "중위권", "컷탈락") if name in row}
    assert "data-label='순위'>1<" in by_name["리더"]
    assert "data-label='순위'>2<" in by_name["중위권"]
    assert "data-label='순위'>3<" in by_name["컷탈락"]
    ranks_shown = [re.search(r"data-label='순위'>([^<]+)<", row).group(1) for row in _rows(html)]
    assert ranks_shown.count("T1") == 0
    assert ranks_shown.count("1") == 1  # exactly one real leader, never every row tied


def test_missing_total_sorts_last_and_renders_empty_rank_never_a_fabricated_number():
    records = [
        {"player_id": "p1", "player_name": "A", "status": "WD", "r1_score_to_par": None, "r2_score_to_par": None},
        {"player_id": "p2", "player_name": "B", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": -2},
    ]
    html = _fixture_html(records=records)
    rows = _rows(html)
    assert "B" in rows[0]
    assert "A" in rows[1]
    assert "data-label='순위'>—<" in rows[1]  # never a fabricated "2" or any other number
    assert "data-label='순위'>1<" in rows[0]


# ---------------------------------------------------------------------
# Real page vs WAIT page: mutually exclusive markers -- the HOME STATE
# ROUTER (scripts/88) must always be able to tell the two apart.
# ---------------------------------------------------------------------

def test_real_page_is_never_mistaken_for_the_wait_page():
    real_html = _fixture_html(records=[{"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0}])
    wait_html = render_r2_wait_page(tournament_name=TOURNAMENT_NAME, game_code=GAME_CODE)
    assert is_real_page(real_html) is True
    assert is_wait_page(real_html) is False
    assert is_real_page(wait_html) is False
    assert is_wait_page(wait_html) is True


def test_real_page_carries_publication_ready_meta_not_the_not_ready_marker():
    html = _fixture_html(records=[])
    assert 'content="true"' in html
    assert 'content="false"' not in html


# ---------------------------------------------------------------------
# Shared shell invariants: breadcrumb, stage-nav, real R1 link (not a
# disabled placeholder -- R2's own stage is complete, R1 already
# happened).
# ---------------------------------------------------------------------

def test_breadcrumb_present_with_r2_as_current_stage():
    html = _fixture_html(records=[])
    assert '<nav class="breadcrumb"' in html
    assert '<span aria-current="page">R2</span>' in html


def test_stage_nav_links_pre_and_r1_r2_current_r3_final_disabled():
    html = _fixture_html(records=[])
    assert f'href="/tournaments/2026/{GAME_CODE}/pre/"' in html
    assert f'href="/tournaments/2026/{GAME_CODE}/r1/"' in html
    assert f'href="/tournaments/2026/{GAME_CODE}/r2/" aria-current="page"' in html
    assert html.count('class="stage-nav__disabled"') == 2  # R3 + FINAL only
