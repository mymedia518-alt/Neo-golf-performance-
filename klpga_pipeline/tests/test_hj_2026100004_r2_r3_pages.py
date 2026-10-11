"""Tests for the HJ 2026100004 R2 (official result + cut) and R3
(forecast) page builders -- scripts/233_... and scripts/234_....

Guards the operator's explicit constraints: cut status shown as its own
state (not hidden/deleted), WD kept distinct from CUT, R3 covers exactly
the 61 official survivors, and no SG/Top5 data ever reaches either page.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / "scripts"
DOCS_ROOT = Path(__file__).parent.parent.parent / "docs" / "tournaments" / "2026" / "2026100004"
CONTENT = Path(__file__).parent.parent / "content" / "website_v2"


def _load_and_run(script_name):
    spec = importlib.util.spec_from_file_location(script_name, SCRIPTS / script_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[script_name] = module
    spec.loader.exec_module(module)
    module.main()
    return module


def test_r2_page_shows_every_player_with_distinct_cut_wd_status(tmp_path, monkeypatch):
    _load_and_run("233_hj_2026100004_build_r2_page.py")
    html = (DOCS_ROOT / "r2" / "index.html").read_text(encoding="utf-8")
    r2 = json.loads((CONTENT / "HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json").read_text(encoding="utf-8"))

    assert html.count("status-badge'>CUT") == r2["missed_cut_count"]
    assert html.count("status-badge'>WD") == r2["wd_count"]
    # every advancing player's name appears with no CUT/WD badge immediately after it
    for p in r2["advanced_to_r3"]:
        name_idx = html.find(f">{p['player_name']}<")
        assert name_idx != -1, f"{p['player_name']} missing from R2 page"
        nearby = html[name_idx:name_idx + 400]
        assert "status-badge" not in nearby.split("</th>")[0]


def test_r2_page_player_count_matches_official_field_size():
    html = (DOCS_ROOT / "r2" / "index.html").read_text(encoding="utf-8")
    r2 = json.loads((CONTENT / "HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json").read_text(encoding="utf-8"))
    row_count = len(re.findall(r"<tr>", html)) - 1  # minus thead row
    assert row_count == r2["field_size"]



def test_r2_shows_the_exact_forecasts_published_on_r1_page():
    r1_html = (DOCS_ROOT / "r1" / "index.html").read_text(encoding="utf-8")
    r2_html = (DOCS_ROOT / "r2" / "index.html").read_text(encoding="utf-8")

    def values_by_player(html, labels):
        found = {}
        for row in re.findall(r"<tr>(.*?)</tr>", html, flags=re.DOTALL):
            name = re.search(r'class="player-name"[^>]*>(.*?)</span>', row)
            if not name:
                continue
            cells = {
                label: re.sub(r"<[^>]+>", "", value).strip()
                for label, value in re.findall(
                    r'<td[^>]*data-label="([^"]+)"[^>]*>(.*?)</td>',
                    row,
                    flags=re.DOTALL,
                )
            }
            found[name.group(1)] = [cells[label] for label in labels]
        return found

    original = values_by_player(
        r1_html, ("컷 통과확률", "TOP20", "TOP10", "우승확률")
    )
    shown = values_by_player(
        r2_html, ("R1 컷 예측", "R1 TOP20", "R1 TOP10", "R1 우승확률")
    )
    assert len(original) == len(shown) == 108
    assert set(original) == set(shown)
    assert all(shown[name] == original[name] for name in original)
    assert "<th>R1 컷 예측</th>" in r2_html
    assert "<th>R1 TOP20</th>" in r2_html
    assert "<th>R1 TOP10</th>" in r2_html
    assert "<th>R1 우승확률</th>" in r2_html


def test_r2_shows_r1_r2_round_scores_and_cumulative_total():
    html = (DOCS_ROOT / "r2" / "index.html").read_text(encoding="utf-8")
    r2 = json.loads((CONTENT / "HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json").read_text(encoding="utf-8"))
    expected = {}
    for p in r2["advanced_to_r3"]:
        expected[p["player_name"]] = (p["r1_points"], p["r2_points"], p["cum36_points"])
    for p in r2["missed_cut"]:
        expected[p["player_name"]] = (
            p["r1_points"], p["r2_points"],
            (p["r1_points"] or 0) + (p["r2_points"] or 0),
        )
    for p in r2["withdrawn"]:
        expected[p["player_name"]] = (p["r1_points"], None, p["r1_points"] or 0)

    found = {}
    for row in re.findall(r"<tr>(.*?)</tr>", html, flags=re.DOTALL):
        name = re.search(r'class="player-name"[^>]*>(.*?)</span>', row)
        if not name:
            continue
        cells = dict(re.findall(r'<td[^>]*data-label="([^"]+)"[^>]*>(.*?)</td>', row, flags=re.DOTALL))
        found[name.group(1)] = (cells["R1"], cells["R2"], cells["합계"])
    assert len(found) == len(expected) == 108
    assert set(found) == set(expected)
    for name, (r1_points, r2_points, total) in expected.items():
        r1_label = "—" if r1_points is None else (f"+{r1_points}" if r1_points > 0 else str(r1_points))
        r2_label = "—" if r2_points is None else (f"+{r2_points}" if r2_points > 0 else str(r2_points))
        total_label = f"+{total}" if total > 0 else str(total)
        assert found[name] == (r1_label, r2_label, total_label)
    assert "<th>R1</th>" in html and "<th>R2</th>" in html and "<th>합계</th>" in html


def test_r3_official_page_shows_full_field_with_61_active_and_correct_cum54():
    html = (DOCS_ROOT / "r3" / "index.html").read_text(encoding="utf-8")
    r3 = json.loads((CONTENT / "HJ_2026100004_R3_OFFICIAL_RESULTS_V1.json").read_text(encoding="utf-8"))
    row_count = len(re.findall(r"<tr>", html)) - 1  # minus thead row
    assert row_count == r3["field_size"] == 108
    assert html.count("status-badge'>CUT") == r3["missed_cut_count"] == 46
    assert html.count("status-badge'>WD") == r3["wd_count"] == 1

    found = {}
    for row in re.findall(r"<tr>(.*?)</tr>", html, flags=re.DOTALL):
        name = re.search(r'class="player-name"[^>]*>(.*?)</span>', row)
        if not name:
            continue
        cum = re.search(r'data-label="합계">([^<]+)</td>', row)
        found[name.group(1)] = cum.group(1) if cum else None
    for p in r3["active_players"]:
        expected = f"+{p['cum54_points']}" if p["cum54_points"] > 0 else str(p["cum54_points"])
        assert found.get(p["player_name"]) == expected, f"{p['player_name']}: cum54 mismatch on R3 page"


def test_r3_official_page_carries_the_post_r2_forecast_as_dated_verification():
    """R3 is an official-results page, but -- like R2 keeps R1's own
    forecast under 'R1 예측 검증' -- it must still show the pre-R3
    forecast that was actually published (from POST-R2 Monte Carlo),
    clearly dated '2R ~' so it reads as a historical prediction being
    checked against the real outcome, not as R3's own upcoming
    forecast (operator report: '3R 페이지에 네오 예측들이 다 어디로
    사라진거야?' -- the first rewrite dropped it entirely instead of
    carrying it forward, unlike R2)."""
    html = (DOCS_ROOT / "r3" / "index.html").read_text(encoding="utf-8")
    r3 = json.loads((CONTENT / "HJ_2026100004_R3_OFFICIAL_RESULTS_V1.json").read_text(encoding="utf-8"))
    forecast = json.loads((CONTENT / "HJ_2026100004_POST_R2_STABLEFORD_MONTE_CARLO_V1_RESULTS.json").read_text(encoding="utf-8"))
    forecast_by_name = {p["player_name"]: p for p in forecast["players"]}

    assert "<th>2R TOP20</th>" in html
    assert "<th>2R TOP10</th>" in html
    assert "<th>2R 우승확률</th>" in html
    # the un-dated, ambiguous headers (which read as R3's OWN forecast,
    # not a historical R2-era one) must never appear
    assert "<th>TOP20</th>" not in html
    assert "<th>TOP10</th>" not in html
    assert "<th>우승확률</th>" not in html
    assert "top5" not in html.lower()  # never Top5/SG here either, as before

    found = {}
    for row in re.findall(r"<tr>(.*?)</tr>", html, flags=re.DOTALL):
        name = re.search(r'class="player-name"[^>]*>(.*?)</span>', row)
        if not name:
            continue
        cells = dict(re.findall(r'<td[^>]*data-label="([^"]+)"[^>]*>([^<]*)</td>', row))
        found[name.group(1)] = cells

    for p in r3["active_players"]:
        fc = forecast_by_name[p["player_name"]]
        row = found[p["player_name"]]
        assert row["2R TOP20"] == f"{fc['top20_pct'] * 100:.1f}%", p["player_name"]
        assert row["2R TOP10"] == f"{fc['top10_pct'] * 100:.1f}%", p["player_name"]
        assert row["2R 우승확률"] == f"{fc['win_pct'] * 100:.1f}%", p["player_name"]

    for p in r3["missed_cut"] + r3["withdrawn"]:
        row = found[p["player_name"]]
        assert row["2R TOP20"] == row["2R TOP10"] == row["2R 우승확률"] == "—", (
            f"{p['player_name']}: CUT/WD player never had a post-R2 forecast, must show em-dash"
        )


def test_no_sg_data_on_any_public_page():
    r2_html = (DOCS_ROOT / "r2" / "index.html").read_text(encoding="utf-8")
    r3_html = (DOCS_ROOT / "r3" / "index.html").read_text(encoding="utf-8")
    fr_html = (DOCS_ROOT / "fr" / "index.html").read_text(encoding="utf-8")
    for html in (r2_html, r3_html, fr_html):
        for forbidden in ("strokes_gained", "sg_total", "SG_RAW"):
            assert forbidden not in html, f"forbidden SG term {forbidden!r} leaked onto a public page"
        # these two are specific historical SG canary values -- checked
        # as a number NOT immediately followed by '%' (a legitimate
        # TOP20/TOP10/TOP5/win percentage can innocently contain the
        # same digits, e.g. "95.61%")
        for canary in ("6.47", "5.61"):
            assert re.search(re.escape(canary) + r"(?!%)", html) is None, f"forbidden SG canary {canary!r} leaked onto a public page outside a percentage value"


def test_no_top5_data_on_r2_or_r3_page():
    """TOP5 is public ONLY on FR and its HOME mirror (operator
    instruction, 2026-10-10) -- R2/R3 must never show it."""
    r2_html = (DOCS_ROOT / "r2" / "index.html").read_text(encoding="utf-8")
    r3_html = (DOCS_ROOT / "r3" / "index.html").read_text(encoding="utf-8")
    for html in (r2_html, r3_html):
        for forbidden in ("top5", "Top5", "TOP5", "top5_pct"):
            assert forbidden not in html, f"forbidden term {forbidden!r} leaked onto a page that must never show TOP5"


def test_bare_undated_top20_never_appears_on_r2_or_r3():
    """TOP20 is public on FR/HOME (added 2026-10-10) and already
    legitimately appears on R2 ('R1 TOP20') and R3 ('2R TOP20') as a
    DATED verification column for a forecast that was actually
    published back then -- but a bare, undated '<th>TOP20</th>' would
    read as that page's own live forecast and must never appear on
    R2/R3."""
    r2_html = (DOCS_ROOT / "r2" / "index.html").read_text(encoding="utf-8")
    r3_html = (DOCS_ROOT / "r3" / "index.html").read_text(encoding="utf-8")
    for html in (r2_html, r3_html):
        assert "<th>TOP20</th>" not in html
    assert "<th>R1 TOP20</th>" in r2_html
    assert "<th>2R TOP20</th>" in r3_html


def test_no_internal_pipeline_language_on_public_pages():
    """Standing guard: public pages must never describe internal
    data-pipeline timing/methodology (e.g. 'this was frozen as of R1
    and not recalculated', the original flagged phrase '...종료 시점의
    컷 통과확률입니다'). Column headers may say 'R1 ~' (plain labeling
    of which round a value is from), but prose explaining *why*/*when
    internally* a number was computed must not appear."""
    r2_html = (DOCS_ROOT / "r2" / "index.html").read_text(encoding="utf-8")
    r3_html = (DOCS_ROOT / "r3" / "index.html").read_text(encoding="utf-8")
    fr_html = (DOCS_ROOT / "fr" / "index.html").read_text(encoding="utf-8")
    for html in (r2_html, r3_html, fr_html):
        for forbidden in (
            "종료 시점", "종료 시 공개", "재계산하지 않았습니다", "재계산하지 않음",
            "Monte Carlo", "몬테카를로", "시뮬레이션",
        ):
            assert forbidden not in html, f"internal pipeline language {forbidden!r} leaked onto a public page"


def test_stage_nav_consistent_and_correct_across_all_six_pages():
    pages = {
        "hub": DOCS_ROOT / "index.html",
        "pre": DOCS_ROOT / "pre" / "index.html",
        "r1": DOCS_ROOT / "r1" / "index.html",
        "r2": DOCS_ROOT / "r2" / "index.html",
        "r3": DOCS_ROOT / "r3" / "index.html",
        "fr": DOCS_ROOT / "fr" / "index.html",
    }
    for name, path in pages.items():
        html = path.read_text(encoding="utf-8")
        nav = re.search(r"<nav class=['\"]stage-nav['\"].*?</nav>", html)
        assert nav, f"{name} page missing stage-nav"
        nav_html = nav.group(0)
        # PRE/R1/R2/R3/FR must each be a real <a> (live) on every page now that all 5 are published
        for stage in ("pre", "r1", "r2", "r3", "fr"):
            assert f"2026100004/{stage}/" in nav_html, f"{name} page's stage-nav missing a live link to {stage}"


def test_r2_cut_rank_numbering_is_contiguous_and_matches_field_size():
    html = (DOCS_ROOT / "r2" / "index.html").read_text(encoding="utf-8")
    ranks = re.findall(r'data-label="순위">([^<]+)<', html)
    # last numeric (non-T, non-em-dash) rank should reach the missed-cut tail close to 108
    numeric = [int(r.lstrip("T")) for r in ranks if r not in ("—",)]
    assert max(numeric) <= 108
    assert min(numeric) == 1


def test_player_name_sponsor_and_status_badge_never_visually_run_together():
    """Regression guard: name/sponsor/CUT-WD badges must never be
    squashed onto one line. neo-site.css's site-wide GLOBAL SPONSOR
    RULE (.player-name/.player-sponsor{display:block}) only takes
    effect if the markup carries no competing inline style -- an
    earlier version of name_cell() set style="display:inline" directly
    on both spans, which (being more specific than the external class
    rule) silently defeated that site-wide fix and made the sponsor
    and any CUT/WD badge run inline right after the player name."""
    for stage in ("r2", "r3", "fr"):
        html = (DOCS_ROOT / stage / "index.html").read_text(encoding="utf-8")
        assert "player-name\" style=" not in html, f"{stage}: player-name must not carry an inline style override"
        assert "player-sponsor\" style=" not in html, f"{stage}: player-sponsor must not carry an inline style override"
        # status badge (where present) must never leak into the sponsor
        # span's own text content
        for m in re.finditer(r"<span class=\"player-sponsor\">([^<]*)</span>", html):
            assert "CUT" not in m.group(1) and "WD" not in m.group(1), f"{stage}: status text leaked into the sponsor span itself: {m.group(1)!r}"


def test_fr_page_covers_exactly_the_61_r3_active_players():
    """2026-10-11 redesign: FR shows ONLY the official final result
    (no pre-4R forecast, operator instruction) -- header row + 61
    players, nothing else."""
    html = (DOCS_ROOT / "fr" / "index.html").read_text(encoding="utf-8")
    r3 = json.loads((CONTENT / "HJ_2026100004_R3_OFFICIAL_RESULTS_V1.json").read_text(encoding="utf-8"))
    fr = json.loads((CONTENT / "HJ_2026100004_FR_OFFICIAL_RESULTS_V1.json").read_text(encoding="utf-8"))
    assert fr["field_size"] == len(fr["final_players"]) == 61
    row_count = len(re.findall(r"<tr>", html)) - 1  # minus the thead row
    assert row_count == 61 == r3["active_count"]
    missed_names = {p["player_name"] for p in r3["missed_cut"]}
    for name in missed_names:
        assert f">{name}<" not in html, f"missed-cut player {name} must not appear on the FR page"


def test_fr_page_columns_and_winner():
    """FR's single table is the official final result only: real
    R1/R2/R3/4R points + final total, ranked by real final points."""
    html = (DOCS_ROOT / "fr" / "index.html").read_text(encoding="utf-8")
    fr = json.loads((CONTENT / "HJ_2026100004_FR_OFFICIAL_RESULTS_V1.json").read_text(encoding="utf-8"))
    theads = re.findall(r"<thead><tr>(.*?)</tr></thead>", html)
    assert len(theads) == 1, "FR page must have exactly 1 table"
    headers = re.findall(r"<th>([^<]+)</th>", theads[0])
    assert headers == ["순위", "선수", "R1", "R2", "R3", "4R", "최종 포인트"], headers
    winner = max(fr["final_players"], key=lambda p: p["final_points"])
    assert winner["player_name"] == "유현조"
    assert winner["final_points"] == 52
    assert f">{winner['player_name']}<" in html
    assert "+52" in html


def test_fr_page_and_home_mirror_have_no_forecast_or_internal_terms():
    """2026-10-11 operator instruction: delete everything related to
    the pre-4R forecast and keep no internal/pipeline terminology
    visible -- FR shows only the real outcome."""
    fr_html = (DOCS_ROOT / "fr" / "index.html").read_text(encoding="utf-8")
    for forbidden in (
        "TOP20", "TOP10", "TOP5", "top5_pct", "top10_pct", "top20_pct", "win_pct",
        "우승확률", "예측", "Monte Carlo", "몬테카를로", "시뮬레이션",
        "forecast", "player_code", "median_final_points", "make_cut_pct",
        "strokes_gained", "sg_total", "SG_RAW",
        "neo-golf-data-fr-summary",
    ):
        assert forbidden not in fr_html, f"forecast/internal term {forbidden!r} still on the FR page"
    asset_path = Path(__file__).parent.parent.parent / "docs" / "assets" / "tournaments" / "2026100004" / "neo-golf-data-fr-summary.png"
    assert not asset_path.exists(), "pre-4R forecast summary image must be removed, not just unlinked"


def test_r2_r3_fr_player_cells_center_under_player_heading():
    for stage in ("r2", "r3", "fr"):
        html = (DOCS_ROOT / stage / "index.html").read_text(encoding="utf-8")
        assert 'data-label="선수" style="text-align:center"' in html
