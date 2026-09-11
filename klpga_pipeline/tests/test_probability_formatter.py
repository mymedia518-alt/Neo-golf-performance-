"""FINAL HOTFIX BEFORE DEPLOYMENT (base fb4f165): ONE shared public
probability formatter.

    p == 0       -> "0%"
    0 < p < 0.1  -> "<0.1%"
    p >= 0.1     -> one decimal place, e.g. "0.2%", "8.8%", "53.1%"

klpga.website_v2.probability_format.format_public_probability is the
ONE function behind every displayed probability cell in klpga.neo_win.
r2_real_page -- desktop and mobile render from the SAME markup (CSS
alone reflows it for narrow viewports; there is no separate mobile
template), so "PC and mobile use exactly the same formatter" holds by
construction. Nothing here touches raw stored probability values,
resimulates anything, or changes CSS/column widths/font sizes/player-
sponsor layout -- see this module's own docstring and the R2 renderer's
_pct_display, which now just delegates to format_public_probability."""
from __future__ import annotations

import re

import pytest

from klpga.neo_win.r2_real_page import render_r2_real_page
from klpga.website_v2.probability_format import format_public_probability

GAME_CODE = "TEST0001"
TOURNAMENT_NAME = "SYNTHETIC FORMATTER TEST OPEN"


# ---------------------------------------------------------------------
# 1-3: the formatter's own exact contract.
# ---------------------------------------------------------------------

def test_1_exact_zero_renders_0_percent():
    assert format_public_probability(0) == "0%"
    assert format_public_probability(0.0) == "0%"


@pytest.mark.parametrize("p", [0.01, 0.02, 0.05, 0.08, 0.09, 0.099999])
def test_2_near_zero_below_point_one_renders_lt_0_1_percent(p):
    assert format_public_probability(p) == "<0.1%"


@pytest.mark.parametrize("p, expected", [
    (0.1, "0.1%"), (0.2, "0.2%"), (8.8, "8.8%"), (53.1, "53.1%"),
    (53.11, "53.1%"), (100.0, "100.0%"), (36.28, "36.3%"),
])
def test_3_at_or_above_point_one_renders_one_decimal(p, expected):
    assert format_public_probability(p) == expected


# ---------------------------------------------------------------------
# 4: raw probability values are unchanged (display-only transform).
# ---------------------------------------------------------------------

def test_4_formatter_is_display_only_never_mutates_the_input():
    raw = 0.08
    format_public_probability(raw)
    assert raw == 0.08  # a float is immutable anyway, but this locks the contract in


def test_4_forecast_dict_passed_to_the_renderer_is_never_mutated():
    forecast_records = [{"player_id": "p1", "win_pct": 0.08, "top5_pct": 0.0, "top10_pct": 53.11, "top20_pct": 99.8}]
    snapshot = [dict(r) for r in forecast_records]
    records = [{"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0}]
    render_r2_real_page(
        tournament_name=TOURNAMENT_NAME, game_code=GAME_CODE, date_range="2026.01.01 — 01.04",
        r2_freeze={"records": records}, forecast={"records": forecast_records},
        sg_ingest={}, sponsor_by_id={},
    )
    assert forecast_records == snapshot


# ---------------------------------------------------------------------
# Shared markup fixture -- desktop and mobile checks both read THIS
# SAME rendered HTML, proving there is only one markup to check.
# ---------------------------------------------------------------------

def _render(records, forecast_records):
    return render_r2_real_page(
        tournament_name=TOURNAMENT_NAME, game_code=GAME_CODE, date_range="2026.01.01 — 01.04",
        r2_freeze={"records": records}, forecast={"records": forecast_records},
        sg_ingest={}, sponsor_by_id={"p1": "테스트스폰서"},
    )


_RECORDS = [
    {"player_id": "p1", "player_name": "선수일", "status": "ACTIVE", "r1_score_to_par": -3, "r2_score_to_par": -4},
    {"player_id": "p2", "player_name": "선수이", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0},
]
_FORECAST = [
    {"player_id": "p1", "win_pct": 53.11, "top5_pct": 99.8, "top10_pct": 100.0, "top20_pct": 100.0},
    {"player_id": "p2", "win_pct": 0.02, "top5_pct": 0.0, "top10_pct": 0.08, "top20_pct": 8.8},
]


# ---------------------------------------------------------------------
# 5/6: desktop and mobile markup/layout contract unchanged. The R2
# leaderboard is ONE responsive table (CSS media queries reflow
# leaderboard-table--r2-full for narrow viewports via each cell's own
# data-label attribute) -- there is no second, mobile-specific markup
# path to diverge, so both checks read the same render() output.
# ---------------------------------------------------------------------

def test_5_desktop_markup_contract_unchanged():
    html = _render(_RECORDS, _FORECAST)
    assert "leaderboard-table--r2-full" in html
    header = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL).group(1)
    labels = re.findall(r"<th>([^<]*)</th>", header)
    assert labels == ["순위", "선수", "합계", "2R", "Top5", "Top10", "Top20", "우승"]
    assert "<span class='player-name'>선수일</span>" in html
    assert "<span class='player-sponsor'>테스트스폰서</span>" in html


def test_6_mobile_markup_contract_unchanged_same_table_same_data_labels():
    html = _render(_RECORDS, _FORECAST)
    # every leaderboard cell still carries the data-label attribute the
    # mobile CSS reflow depends on -- nothing here is desktop-only markup.
    for label in ("순위", "선수", "합계", "2R", "Top5", "Top10", "Top20", "우승"):
        assert f"data-label='{label}'" in html
    # the near-zero cell renders as a single unbroken token -- no space,
    # so it can never wrap onto two lines under normal text flow.
    assert "<0.1%</td>" in html
    lt_cell = re.search(r"<td class='win' data-label='우승'>([^<]*<0\.1%)</td>", html)
    assert lt_cell is not None
    assert " " not in lt_cell.group(1)


def test_win_is_still_the_last_column_and_population_still_8_columns():
    html = _render(_RECORDS, _FORECAST)
    row = re.search(r"<tr data-player-id='p1'>((?:(?!</tr>).)*)</tr>", html).group(1)
    cells = re.findall(r"<t[dh][^>]*>", row)
    assert len(cells) == 8
    last_cell = re.search(r"<td[^>]*data-label='우승'>([^<]*)</td>\s*$", row.rstrip())
    assert last_cell is not None


# ---------------------------------------------------------------------
# Real, current-production regression: the formatter applied to the
# real forecast produces exactly the documented near-zero/exact-zero/
# one-decimal outputs, never anything else.
# ---------------------------------------------------------------------

def test_real_r2_forecast_every_win_pct_formats_per_contract():
    import json
    from pathlib import Path

    forecast = json.loads(
        (Path(__file__).resolve().parents[1] / "content" / "website_v2" / "2026090003_POST_R2_FINAL_FORECAST.json")
        .read_text(encoding="utf-8")
    )
    for row in forecast["records"]:
        p = row["win_pct"]
        display = format_public_probability(p)
        if p == 0:
            assert display == "0%"
        elif p < 0.1:
            assert display == "<0.1%"
        else:
            assert display == f"{p:.1f}%"


# ---------------------------------------------------------------------
# 7/8: HOME still resolves to R2; R3 WAIT does not promote it. Reuses
# the real, currently-committed generated site -- proves the formatter
# change didn't disturb the fb4f165 HOME routing contract.
# ---------------------------------------------------------------------

def test_7_home_still_resolves_to_r2():
    from klpga.tournament_context import load_tournament_context
    from klpga.website_v2.kb_home_stage_router import kb_current_stage

    context = load_tournament_context("2026090003")
    assert kb_current_stage(context) == "r2"

    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[2]
    home_html = (repo_root / "docs" / "index.html").read_text(encoding="utf-8")
    assert '"status">R2<' in home_html
    r2_html = (repo_root / "docs" / "tournaments" / "2026" / "2026090003" / "r2" / "index.html").read_text(encoding="utf-8")
    home_body = home_html.split("<main>", 1)[1].rsplit("</main>", 1)[0]
    r2_body = r2_html.split("<main>", 1)[1].rsplit("</main>", 1)[0]
    assert home_body == r2_body


def test_8_r3_wait_does_not_promote_home():
    from pathlib import Path

    from klpga.neo_win.r3_freeze import r3_freeze_exists
    from klpga.tournament_context import load_tournament_context

    context = load_tournament_context("2026090003")
    repo_root = Path(__file__).resolve().parents[2]
    r3_wait_page = repo_root / "docs" / "tournaments" / "2026" / "2026090003" / "r3" / "index.html"
    assert r3_wait_page.is_file()
    assert r3_freeze_exists(context) is False
    home_html = (repo_root / "docs" / "index.html").read_text(encoding="utf-8")
    assert '"status">R3<' not in home_html
