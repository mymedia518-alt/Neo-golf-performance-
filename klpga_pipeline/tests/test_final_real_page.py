"""FINAL PAGE GO (2026-09-13): tests for klpga.neo_win.final_real_page.

Uses the REAL KB 2026090003 pipeline (real frozen R3 forecast + real
V3 operator-supplied-official-screenshot evidence, positions 1-39) --
the same inputs scripts/131_build_kb_final_page.py itself uses -- so
these are simultaneously unit tests of the renderer AND a regression
guard against the real production output. Covers exactly what
FINAL PAGE GO's mission explicitly required: the sponsor invariant, a
zero-internal-state-leak public page, the explicit "상위 39명" scope
label (never claiming a complete 70-player field), and stage-nav
correctness (FINAL current, FR still disabled, FINAL PAGE GO's own
required V3 metrics rendered verbatim)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from klpga.neo_win.final_partial_evidence_validator import biggest_movers, run_extended_comparison
from klpga.neo_win.final_real_page import is_final_real_page, render_final_real_page
from klpga.tournament_context import load_tournament_context

ROOT = Path(__file__).resolve().parents[1]
GAME_CODE = "2026090003"


@pytest.fixture(scope="module")
def real_final_html():
    context = load_tournament_context(GAME_CODE)
    evidence_path = ROOT / "content" / "website_v2" / "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V3.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert all(not r["review_required"] and r["player_id"] is not None for r in evidence["confirmed_records"])

    comparison = run_extended_comparison(context, evidence)
    overestimated, underestimated = biggest_movers(comparison, n=5)
    html = render_final_real_page(
        tournament_name=context.tournament_name, game_code=context.game_code,
        date_range=context.display_date_range, evidence=evidence, comparison=comparison,
        overestimated=overestimated, underestimated=underestimated,
    )
    return html, evidence, comparison


def test_is_final_real_page_recognizes_real_output(real_final_html):
    html, _evidence, _comparison = real_final_html
    assert is_final_real_page(html) is True


def test_is_final_real_page_rejects_arbitrary_html():
    assert is_final_real_page("<html><body>not a final page</body></html>") is False


# ---------------------------------------------------------------------
# No internal-state leak: SHA/hash, evidence-tier name, file path,
# review_required/QA-state word, build/commit id -- none of it belongs
# in the public HTML.
# ---------------------------------------------------------------------

FORBIDDEN_SUBSTRINGS = [
    "sha256", "evidence_tier", "OPERATOR_SUPPLIED", "OPERATOR_REPORTED",
    "review_required", "content/website_v2", "build_id", "code_commit",
    "fingerprint", "not_direct_klpga_automated_ingestion",
]
FORBIDDEN_PATTERNS = [r"\.py\b", r"[A-Za-z0-9_\-/]+\.json"]


def test_no_internal_state_leak(real_final_html):
    html, _evidence, _comparison = real_final_html
    for needle in FORBIDDEN_SUBSTRINGS:
        assert needle not in html, f"forbidden internal-state string leaked into public HTML: {needle!r}"
    for pattern in FORBIDDEN_PATTERNS:
        assert not re.search(pattern, html), f"forbidden internal-state pattern leaked into public HTML: {pattern!r}"


# ---------------------------------------------------------------------
# Explicit Top-39 scope wording -- never represented as the complete
# 70-player field.
# ---------------------------------------------------------------------

def test_scope_label_present_and_correct(real_final_html):
    html, evidence, _comparison = real_final_html
    scope_through = evidence["positions_confirmed_gapless_through"]
    assert scope_through == 39
    assert f"FINAL 상위 {scope_through}명 공식 결과 기준" in html
    assert "70명" not in html
    assert "전체 결과" not in html


# ---------------------------------------------------------------------
# Sponsor invariant: every player-name span has a matching (possibly
# empty-text) sponsor span immediately after it -- never omitted.
# ---------------------------------------------------------------------

def test_sponsor_invariant_every_name_has_a_sponsor_span(real_final_html):
    html, _evidence, _comparison = real_final_html
    name_count = html.count("class='player-name'")
    sponsor_count = html.count("class='player-sponsor'")
    assert name_count > 0
    assert name_count == sponsor_count
    assert re.search(r"class='player-name'[^<]*</span><span class='player-sponsor'", html)


# ---------------------------------------------------------------------
# Stage nav correctness.
# ---------------------------------------------------------------------

def test_stage_nav_final_current_fr_disabled_others_plain_links(real_final_html):
    html, _evidence, _comparison = real_final_html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/pre/">사전 분석 PRE</a>' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r1/">R1</a>' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r2/">R2</a>' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r3/">R3</a>' in html
    assert '<span class="stage-nav__disabled" aria-disabled="true">FR</span>' in html
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/final/" aria-current="page">FINAL</a>' in html
    # R3 must NOT be aria-current on the FINAL page itself.
    assert 'href="/tournaments/2026/2026090003/r3/" aria-current="page"' not in html


# ---------------------------------------------------------------------
# FINAL PAGE GO's own required V3 metrics, rendered verbatim.
# ---------------------------------------------------------------------

def test_required_v3_metrics_rendered(real_final_html):
    html, _evidence, comparison = real_final_html
    assert comparison.topk[5].precision == pytest.approx(0.8)
    assert comparison.topk[5].recall == pytest.approx(0.8)
    assert comparison.topk[10].precision == pytest.approx(0.7)
    assert comparison.topk[10].recall == pytest.approx(0.7)
    assert comparison.topk[20].precision == pytest.approx(0.75)
    assert comparison.topk[20].recall == pytest.approx(0.75)
    assert "80%" in html and "70%" in html and "75%" in html
    assert comparison.winner_name == "박보겸"
    assert "우승 <span class='player-name'>박보겸</span>" in html
    assert "-5 (283)" in html
    assert comparison.winner_neo_win_probability_pct == pytest.approx(11.78, abs=0.01)
    assert comparison.winner_neo_probability_rank == 5


def test_biggest_movers_include_required_named_players(real_final_html):
    _html, _evidence, comparison = real_final_html
    overestimated, underestimated = biggest_movers(comparison, n=5)
    under_names = {c.player_name for c in underestimated}
    over_names = {c.player_name for c in overestimated}
    assert "송은아" in under_names
    assert "이채은2" in over_names
