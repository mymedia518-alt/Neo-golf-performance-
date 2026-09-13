"""KB금융 골든라이프 챔피언십 FR BUILD (2026-09-13): tests for
klpga.neo_win.fr_real_page and scripts/132_build_kb_fr_page.py.

Uses the REAL KB 2026090003 pipeline (real V3 operator-supplied-
official-screenshot evidence, positions 1-39) -- the same inputs
scripts/132 itself uses -- so these are simultaneously unit tests of
the renderer AND a regression guard against the real production
output. Covers exactly what the FR BUILD mission required: winner,
leaderboard, round arithmetic, tie positions, sponsor invariant,
39-row scope, zero internal-state leakage, ZERO model-analysis
language (FR is a pure results page), navigation, mobile structure,
and R3 freeze integrity."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from klpga.neo_win.fr_real_page import is_fr_real_page, render_fr_real_page
from klpga.tournament_context import load_tournament_context

ROOT = Path(__file__).resolve().parents[1]
GAME_CODE = "2026090003"
EXPECTED_R3_FORECAST_SHA256 = "016d02966bd57f88f466a5acfb4da480d3895fa4f28181157472d5ef5622141f"


@pytest.fixture(scope="module")
def real_fr_html():
    context = load_tournament_context(GAME_CODE)
    evidence_path = ROOT / "content" / "website_v2" / "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V3.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert all(not r["review_required"] and r["player_id"] is not None for r in evidence["confirmed_records"])
    html = render_fr_real_page(
        tournament_name=context.tournament_name, game_code=context.game_code,
        date_range=context.display_date_range, evidence=evidence,
    )
    return html, evidence


def test_is_fr_real_page_recognizes_real_output(real_fr_html):
    html, _evidence = real_fr_html
    assert is_fr_real_page(html) is True


def test_is_fr_real_page_rejects_arbitrary_html():
    assert is_fr_real_page("<html><body>not an fr page</body></html>") is False


def test_winner_is_박보겸_with_correct_score(real_fr_html):
    html, evidence = real_fr_html
    winner = next(r for r in evidence["confirmed_records"] if str(r["final_rank"]) == "1")
    assert winner["player_name"] == "박보겸"
    assert winner["final_to_par"] == -5
    assert winner["final_total_strokes"] == 283
    assert winner["r4_strokes"] == 71
    assert "우승 <span class='player-name'>박보겸</span><span class='player-sponsor'>삼천리</span>" in html
    assert "<span class='metric'>-5</span>" in html
    assert "FR 71" in html


def test_leaderboard_has_exactly_39_rows_in_rank_order(real_fr_html):
    html, evidence = real_fr_html
    rows = re.findall(r"<tr data-player-id='(\d+)'>", html)
    assert len(rows) == 39
    assert len(evidence["confirmed_records"]) == 39


def test_round_arithmetic_is_correct_for_every_row(real_fr_html):
    _html, evidence = real_fr_html
    par_per_round = evidence["par_per_round"]
    for r in evidence["confirmed_records"]:
        rounds = [r["r1_strokes"], r["r2_strokes"], r["r3_strokes"], r["r4_strokes"]]
        assert sum(rounds) == r["final_total_strokes"]
        assert r["final_total_strokes"] - par_per_round * 4 == r["final_to_par"]


def test_tie_positions_render_with_t_prefix(real_fr_html):
    html, _evidence = real_fr_html
    for name in ("박예지", "방신실", "유서연2"):
        row = re.search(rf"<tr data-player-id='\d+'>(?:(?!</tr>).)*{name}.*?</tr>", html, re.DOTALL)
        assert row is not None
        assert "data-label='순위'>T2<" in row.group(0)


def test_leaderboard_columns_are_r1_r2_r3_fr_total_in_order(real_fr_html):
    html, evidence = real_fr_html
    winner = next(r for r in evidence["confirmed_records"] if str(r["final_rank"]) == "1")
    row = re.search(rf"<tr data-player-id='{winner['player_id']}'>((?:(?!</tr>).)*)", html).group(1)
    assert "data-label='R1'>70<" in row
    assert "data-label='R2'>69<" in row
    assert "data-label='R3'>73<" in row
    assert "data-label='FR'>71<" in row
    assert "data-label='합계'>-5<" in row


def test_sponsor_invariant_every_name_has_a_sponsor_span(real_fr_html):
    html, _evidence = real_fr_html
    name_count = html.count("class='player-name'")
    sponsor_count = html.count("class='player-sponsor'")
    assert name_count > 0
    assert name_count == sponsor_count


def test_sponsor_left_blank_when_unverified_never_guessed(real_fr_html):
    html, evidence = real_fr_html
    row = next(r for r in evidence["confirmed_records"] if r["player_name"] == "유서연2")
    assert row.get("sponsor") is None
    match = re.search(r"<tr data-player-id='11066'>((?:(?!</tr>).)*)", html)
    assert match is not None
    assert "class='player-sponsor'></span>" in match.group(0)


def test_scope_label_present_and_correct(real_fr_html):
    html, evidence = real_fr_html
    scope_through = evidence["positions_confirmed_gapless_through"]
    assert scope_through == 39
    assert f"FR 상위 {scope_through}명 공식 결과 기준" in html
    assert "70명" not in html


def test_no_internal_state_leak(real_fr_html):
    html, _evidence = real_fr_html
    forbidden = [
        "sha256", "evidence_tier", "OPERATOR_SUPPLIED", "OPERATOR_REPORTED",
        "review_required", "content/website_v2", "build_id", "code_commit",
        "fingerprint", "not_direct_klpga_automated_ingestion",
    ]
    for needle in forbidden:
        assert needle not in html
    for pattern in (r"\.py\b", r"[A-Za-z0-9_\-/]+\.json"):
        assert not re.search(pattern, html)


def test_zero_model_analysis_language(real_fr_html):
    """FR is a RESULT page, not an analysis page -- none of NEO's
    probability/validation/postmortem vocabulary may appear here."""
    html, _evidence = real_fr_html
    forbidden = [
        "우승확률", "win_pct", "NEO 우승", "NEO 예상", "NEO 랭킹", "NEO PICK",
        "Top5", "Top10", "Top20", "top5_pct", "top10_pct", "top20_pct",
        "확률", "Brier", "log_loss", "Monte Carlo", "몬테카를로",
        "SURPRISE", "MISS", "예측", "postmortem", "코스 분석", "모델",
    ]
    for needle in forbidden:
        assert needle not in html, f"forbidden model-analysis term leaked into FR: {needle!r}"


def test_stage_nav_fr_current_no_final_link(real_fr_html):
    """Desired sequence for THIS build: PRE -> R1 -> R2 -> R3 -> FR
    only -- FINAL is explicitly out of scope for FR's own nav."""
    html, _evidence = real_fr_html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/pre/">사전 분석 PRE</a>' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r1/">R1</a>' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r2/">R2</a>' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r3/">R3</a>' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/fr/" aria-current="page">FR</a>' in html
    assert "FINAL" not in html.split("<nav", 1)[1].split("</nav>", 1)[0]


def test_mobile_leaderboard_uses_fr_full_modifier(real_fr_html):
    html, _evidence = real_fr_html
    assert 'class="data leaderboard-table leaderboard-table--fr-full"' in html
    assert "data-label='순위'" in html
    assert "data-label='선수'" in html
    assert "data-label='FR'" in html
    assert "data-label='합계'" in html


def test_r3_frozen_forecast_fingerprint_unchanged():
    path = ROOT / "content" / "website_v2" / "2026090003_POST_R3_FINAL_FORECAST.json"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == EXPECTED_R3_FORECAST_SHA256
