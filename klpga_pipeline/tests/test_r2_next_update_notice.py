"""R2 PUBLIC PAGE -- RESTORE NEXT UPDATE NOTICE (base f52d0a6).

klpga.neo_win.r2_real_page carries a static "R3 종료 후 업데이트" notice
below the leaderboard so a visitor knows when to expect the next
update -- correct regardless of round count, since R2's own next
public transition genuinely is R3.

ROUND-CONTEXT CORRECTION (research/official-tournament-warehouse-v1-
20260912): this file previously asserted KB 2026090003's
final_round_number is 3 (R3 being its last competitive round) as an
already-"confirmed" fact. Official evidence (the R3 leaderboard's own
4R column/round4score attributes + the official 4-day Thu-Sun
schedule) proves this is a genuine FOUR competitive-round event -- see
TOURNAMENT_SITE_REGISTRY.json's "_final_round_number_comment". A
genuine POST-R3 forecast (targeting FR, competitive round 4) is now
built via post_r3_forecast.py once R3 concludes.

Desktop and mobile are the SAME markup (no separate mobile template),
so proving the notice is present in the real generated HTML covers
both. This test file is the regression hook: it must fail loudly if
the notice is ever silently dropped from the public R2 page again."""
from __future__ import annotations

import re
from pathlib import Path

from klpga.neo_win.r2_real_page import NEXT_UPDATE_NOTICE, render_r2_real_page

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
REAL_PAGE_PATH = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090003" / "r2" / "index.html"
REAL_HOME_PATH = REPO_ROOT / "docs" / "index.html"


def _real_r2_html() -> str:
    assert REAL_PAGE_PATH.is_file(), f"real R2 page not found at {REAL_PAGE_PATH}"
    return REAL_PAGE_PATH.read_text(encoding="utf-8")


def test_notice_text_is_exactly_r3_jongryo_hu_update():
    assert NEXT_UPDATE_NOTICE == "R3 종료 후 업데이트"


def test_real_r2_page_carries_the_notice_below_the_leaderboard():
    html = _real_r2_html()
    leaderboard_section = re.search(r'<section class="panel leaderboard-panel" id="r2">(.*?)</section>', html, re.DOTALL).group(1)
    assert f'<p class="note next-update-note">{NEXT_UPDATE_NOTICE}</p>' in leaderboard_section
    # "below" the leaderboard: appears after the closing </table>, not before it.
    table_end = leaderboard_section.index("</table>")
    notice_pos = leaderboard_section.index(NEXT_UPDATE_NOTICE)
    assert notice_pos > table_end


def test_real_home_mirrors_the_same_notice_desktop_and_mobile():
    """HOME mirrors R2's real page body verbatim (klpga.website_v2.
    kb_home_stage_router) -- the SAME markup renders for both desktop
    and mobile (CSS alone reflows it), so this one assertion covers
    both surfaces at once."""
    if not REAL_HOME_PATH.is_file():
        return
    home_html = REAL_HOME_PATH.read_text(encoding="utf-8")
    if '"status">R2<' not in home_html:
        return  # HOME is not currently mirroring R2 -- not this test's concern
    assert f'<p class="note next-update-note">{NEXT_UPDATE_NOTICE}</p>' in home_html


def test_notice_reuses_the_existing_subtle_note_style_no_new_css_needed():
    """Reuses the already-styled `.note` class (neo.css:
    `.meta,.note{color:var(--muted);font-size:14px}`) -- `next-update-
    note` is purely a semantic/test hook, never a new visual rule."""
    html = _real_r2_html()
    assert 'class="note next-update-note"' in html


def test_notice_does_not_disturb_the_probability_column_order_or_win_last():
    html = _real_r2_html()
    header = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL).group(1)
    labels = re.findall(r"<th>([^<]*)</th>", header)
    assert labels == ["순위", "선수", "합계", "2R", "Top20", "Top10", "Top5", "우승"]


def test_notice_does_not_disturb_population_or_formatter():
    html = _real_r2_html()
    body = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    rows = re.findall(r"<tr data-player-id='[^']+'>", body)
    assert len(rows) == 71
    win_cells = re.findall(r"<td class='win' data-label='우승'>(.*?)</td>", body)
    assert win_cells
    for cell_text in win_cells:
        if cell_text == "—":
            continue
        assert re.fullmatch(r"0%|<0\.1%|[+-]?\d+\.\d%", cell_text)


def test_final_round_number_is_four_with_one_remaining_round_after_r3():
    """ROUND-CONTEXT CORRECTION: this tournament's final_round_number
    is 4 (a genuine four-round event, corrected from an earlier
    session's incorrect final_round_number=3 belief -- see
    TOURNAMENT_SITE_REGISTRY.json's own evidence trail). One
    competitive round (FR, round 4) remains after R3, so a genuine
    POST-R3 forecast IS buildable via post_r3_forecast.py -- see
    tests/test_post_r3_forecast.py and
    tests/test_2026090003_round_context.py for the forecast-artifact
    and context-correction regressions themselves."""
    from klpga.tournament_context import load_tournament_context

    context = load_tournament_context("2026090003")
    assert context.final_round_number == 4
    assert context.final_round_number - 3 == 1


def test_synthetic_render_always_includes_the_notice():
    html = render_r2_real_page(
        tournament_name="SYNTHETIC NOTICE TEST OPEN", game_code="TEST0001", date_range="2026.01.01 — 01.04",
        r2_freeze={"records": []}, forecast={"records": []}, sg_ingest={}, sponsor_by_id={},
    )
    assert NEXT_UPDATE_NOTICE in html
    assert 'class="note next-update-note"' in html
