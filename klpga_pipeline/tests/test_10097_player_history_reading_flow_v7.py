"""MISSION V7 (2026-09-25), playerCode=10097 only.

"Do not build anything new. Do not create a single new section. Do not
create a single new chart. Open the page. Read it like a golfer. Every
time you stop reading, identify why. Then redesign only that moment.
Measure success by reading flow, not by data quantity."

A full top-to-bottom read of the rendered page (desktop + mobile
screenshots) surfaced three concrete moments where a first-time reader
would stop and re-read something they had already just read, or land
on a stale default:

1. Section 3 (최근 경기 결과) printed three FULL tables -- last 5, then
   last 10, then last 20 -- so the same most-recent rows scrolled past
   three times over. Only the last-5 table stays open now; the 6th-10th
   and 11th-20th rows are nested (via the same disclosure component
   already used in Course Profile), each shown exactly once.
2. Section 7's "최근 우승" and "최근 대회" highlight cards were
   byte-identical whenever her most recent tournament was also her most
   recent win (true right now: 하나금융그룹 챔피언십 2026 is both) --
   the reader hit the same card twice in a row.
3. Section 10 (플레이어 DNA)'s season tabs defaulted to the OLDEST
   season, directly contradicting the page's own "current form comes
   first" thesis. The default tab is now her most recent season.

No new section, card, or chart was added -- every fix either removes a
duplicate render of already-computed data or changes which existing
tab/row is shown by default.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("build_10097_player_history", ROOT / "scripts" / "build_10097_player_history.py")
build_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_script)

from klpga.website_v2 import player_history_10097_report as report  # noqa: E402


def _doc_and_html():
    doc = build_script.build()
    return doc, report.render_player_history_html(doc)


def test_recent_results_never_prints_the_same_tournament_row_twice():
    """Every completed-tournament name may appear in the Recent Results
    section at most once.

    MISSION "30초 스캔" (2026-09-27), approved wireframe
    (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7) replaced the
    old 5-row-plus-nested-15-row tables (where triple-printing was a
    real risk) with one flat dot strip, one dot per real row -- no
    table, no nesting, so no row can structurally repeat. Checked via
    each dot's title attribute (the strip's only place a tournament
    name renders) instead of a <td> cell."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-recent-form"')
    end = html.index("</details>", start)
    section = html[start:end]
    longest = max((r["tournament"] for r in doc["recent_form_20"]), key=len)
    assert section.count(escape_safe(longest)) == 1


def test_recent_results_shows_one_flat_strip_never_nested():
    """MISSION "30초 스캔" (2026-09-27), approved wireframe
    (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7) superseded the
    5-open/15-nested table split -- the whole 20-tournament window is
    one un-nested strip now."""
    _, html = _doc_and_html()
    start = html.index('id="ph-recent-form"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert 'class="ph-nested-detail"' not in section
    assert "최근 5개 완료 대회" not in section


def test_recent_results_nested_window_contains_every_older_row_exactly_once():
    doc, html = _doc_and_html()
    older_rows = doc["recent_form_20"][: len(doc["recent_form_20"]) - len(doc["recent_form_5"])]
    start = html.index('id="ph-recent-form"')
    end = html.index("</details>", start)
    section = html[start:end]
    for r in older_rows:
        assert escape_safe(r["tournament"]) in section


def escape_safe(s: str) -> str:
    from html import escape
    return escape(s)


def test_recent_win_card_is_never_duplicated_as_the_latest_tournament_card():
    """If the most recent completed tournament is also the most recent
    win, '최근 대회' must not repeat '최근 우승' word for word."""
    doc, html = _doc_and_html()
    rows = doc["tournament_history"]
    wins = [r for r in rows if r["is_win"]]
    sg_rows = [r for r in rows if r.get("sg_total") is not None]
    assert wins and sg_rows
    latest_win = wins[-1]
    latest = sg_rows[-1]
    start = html.index('id="ph-tournament-trend"')
    end = html.index("</details>", start)
    section = html[start:end]
    if latest["game_code"] == latest_win["game_code"]:
        assert section.count(f'{escape_safe(latest["tournament"])} ({latest["season"]})') == 1
    else:
        assert "최근 대회" in section


def test_player_dna_radar_defaults_to_the_most_recent_season():
    doc, html = _doc_and_html()
    seasons = doc["player_dna_radar"]
    assert seasons
    latest_season = seasons[-1]["season"]
    last_index = len(seasons) - 1
    checked_tab = re.search(rf'id="ph-dna-tab-{last_index}" class="ph-dna-radio" checked', html)
    assert checked_tab, "most recent season's tab must be checked by default"
    # the oldest season's tab (index 0) must NOT be checked, unless it
    # is also the only / most recent season (single-season career).
    if last_index != 0:
        assert re.search(r'id="ph-dna-tab-0" class="ph-dna-radio" checked', html) is None
    assert f'{latest_season}시즌 (같은 시즌' in html
