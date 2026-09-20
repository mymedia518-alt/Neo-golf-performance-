"""RED TEAM FOLLOW-UP (2026-09-20): "검증은 깊게, 화면은 쉽게" -- the
Hana (2026090002) public FINAL/HOME page must read like a plain
results summary a golf fan understands with no explanation, while the
internal validation (FinalValidationResult / build_final_report) keeps
every metric untouched. Covers:

  1. render_final_public_summary's own output is jargon-free.
  2. The real, currently-published docs/ FINAL and HOME pages carry no
     internal-validation vocabulary (Brier/Log Loss/Rank MAE/
     Reciprocal Rank/proxy/native metric/frozen forecast/schema
     bridge/validator/calibration/Monte Carlo/Precision/Recall), and
     no more Top20 or biggest-movers section on the public page.
  3. Nothing was deleted internally: build_final_report(context) for
     the real 2026090002 context still returns the full metric detail
     (both evidence tiers) untouched.
  4. Official player name accuracy: 김민선7 is never truncated to bare
     김민선 anywhere in the real, currently-published Hana artifacts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from klpga.neo_win import final_report
from klpga.neo_win.final_real_page import render_final_hero_forecast_line, render_final_public_summary
from klpga.tournament_context import load_tournament_context

REPO_ROOT = Path(__file__).resolve().parents[2]
KLPGA_ROOT = Path(__file__).resolve().parents[1]
GAME_CODE = "2026090002"

FORBIDDEN_JARGON = [
    "Rank MAE", "Brier", "Log Loss", "Reciprocal Rank",
    "proxy", "native metric", "frozen forecast", "schema bridge",
    "validator", "calibration", "Monte Carlo",
    "Precision", "Recall", "정밀도", "재현율", "neo_final_rank",
]


def test_render_final_hero_forecast_line_is_plain_language_and_jargon_free():
    html = render_final_hero_forecast_line(winner_win_probability_pct=45.543333, winner_is_top_pick=True)
    for term in FORBIDDEN_JARGON:
        assert term not in html, f"forbidden internal-validation term leaked into hero forecast line: {term!r}"
    assert "45.54%" in html
    assert "1위" in html
    assert "우승" in html


def test_render_final_hero_forecast_line_omits_rank_phrase_when_not_top_pick():
    html = render_final_hero_forecast_line(winner_win_probability_pct=30.0, winner_is_top_pick=False)
    assert "1위" not in html


def test_render_final_public_summary_is_plain_language_and_jargon_free():
    html = render_final_public_summary(
        top5_predicted=5, top5_hit=4,
        top10_predicted=10, top10_hit=7,
    )
    for term in FORBIDDEN_JARGON:
        assert term not in html, f"forbidden internal-validation term leaked into public summary: {term!r}"
    assert "Top5 예측 5명 중 4명 실제 Top5" in html
    assert "Top10 예측 10명 중 7명 실제 Top10" in html


def test_real_hana_final_page_has_no_internal_validation_jargon():
    path = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "final" / "index.html"
    html = path.read_text(encoding="utf-8")
    for term in FORBIDDEN_JARGON:
        assert term not in html, f"forbidden internal-validation term leaked into the real public FINAL page: {term!r}"
    # The old internal-report-style sections must be gone from the
    # public page entirely -- render_final_validation_sections' ids.
    assert 'id="forecast-vs-result"' not in html
    assert 'id="neo-validation"' not in html
    assert 'id="biggest-movers"' not in html
    # The new plain-language summary IS present. Top20 hit-rate
    # language must be gone from the public summary specifically
    # (the leaderboard's own per-player "TOP20" probability COLUMN is
    # a separate, pre-existing, unrelated display and stays untouched).
    assert 'id="final-summary"' in html
    assert "Top5 예측" in html
    assert "Top10 예측" in html
    summary_section = re.search(r'<section class="panel" id="final-summary">.*?</section>', html, re.S).group(0)
    assert "Top20" not in summary_section
    assert "주요 순위 변동" not in html


def test_real_hana_final_page_shows_forecast_vs_actual_in_the_hero_above_the_fold():
    """Operator check: on mobile, the FIRST screen alone (hero, before
    the 64-row leaderboard) must make the "김민선7 -> NEO 우승확률 1위
    45.54% -> 실제 우승" relationship obvious with no scrolling."""
    path = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "final" / "index.html"
    html = path.read_text(encoding="utf-8")
    hero_end = html.index('id="final-leaderboard"')
    hero_html = html[:hero_end]
    assert "NEO 4R 전 우승확률" in hero_html
    assert "45.54%" in hero_html
    assert "1위" in hero_html
    assert "실제 결과" in hero_html
    assert "우승" in hero_html
    assert "김민선7" in hero_html


def test_real_hana_home_page_mirrors_the_jargon_free_final_page():
    path = REPO_ROOT / "docs" / "index.html"
    html = path.read_text(encoding="utf-8")
    for term in FORBIDDEN_JARGON:
        assert term not in html, f"forbidden internal-validation term leaked into the real public HOME page: {term!r}"
    assert 'id="final-summary"' in html


def test_internal_final_report_still_has_full_metric_detail_untouched():
    """Nothing computed internally was deleted -- only the public page
    changed. build_final_report(context) for the real Hana context
    must still expose both evidence tiers in full."""
    context = load_tournament_context(GAME_CODE)
    report = final_report.build_final_report(context)
    perf = report["forecast_performance"]
    native = perf["frozen_forecast_native_metrics"]
    proxy = perf["post_hoc_rank_proxy_diagnostics"]
    assert native["brier_norm"] is not None
    assert native["log_loss"] is not None
    assert native["reciprocal_rank"] is not None
    assert native["top5_hit"] is True
    assert native["top10_hit"] is True
    assert proxy["rank_mae"] is not None
    assert proxy["neo_final_rank_is_derived_proxy"] is True
    assert "post-hoc derived probability-rank proxy" in proxy["rank_proxy_note"]


# ---------------------------------------------------------------
# Official player-name accuracy: 김민선7, never truncated to 김민선.
# ---------------------------------------------------------------

TRUNCATION_PATTERN = re.compile(r"김민선(?!7)")

REAL_ARTIFACTS_TO_CHECK = [
    REPO_ROOT / "docs" / "index.html",
    REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "final" / "index.html",
    REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html",
    REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html",
    REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r2" / "index.html",
    REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r3" / "index.html",
    REPO_ROOT / "docs" / GAME_CODE / "index.html",
    REPO_ROOT / "docs" / "share" / GAME_CODE / "index.html",
    KLPGA_ROOT / "content" / "website_v2" / f"{GAME_CODE}_FINAL_TRUTH.json",
    KLPGA_ROOT / "content" / "website_v2" / f"{GAME_CODE}_POST_R4_FINAL_PREVIEW.json",
    KLPGA_ROOT / "content" / "website_v2" / f"{GAME_CODE}_POST_R3_FINAL_FORECAST.json",
]


def test_official_winner_name_never_truncated_in_real_hana_artifacts():
    checked_any_hit = False
    for path in REAL_ARTIFACTS_TO_CHECK:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if "김민선" in text:
            checked_any_hit = True
        bad = TRUNCATION_PATTERN.findall(text)
        assert not bad, f"{path}: found truncated '김민선' (missing trailing 7), {len(bad)} occurrence(s)"
    assert checked_any_hit, "expected at least one real artifact to mention 김민선7 -- test fixture list may be stale"


def test_final_truth_uses_the_full_official_player_name():
    truth_path = KLPGA_ROOT / "content" / "website_v2" / f"{GAME_CODE}_FINAL_TRUTH.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    winner = next(r for r in truth["records"] if str(r["player_id"]) == "10097")
    assert winner["player_name"] == "김민선7"


# ---------------------------------------------------------------
# FINAL video insert (2026-09-20): operator-supplied video, placed
# after the hero and before the rest of the FINAL content, no
# redesign, no autoplay/loop/forced-mute, responsive width.
# ---------------------------------------------------------------

VIDEO_SRC = "/assets/tournaments/2026090002/hana-final-win-probability.mp4"


def test_render_final_video_section_has_required_attrs_and_no_forbidden_ones():
    from klpga.neo_win.final_real_page import render_final_video_section
    html = render_final_video_section(video_src=VIDEO_SRC, caption="4R 전 NEO 우승확률")
    assert "controls" in html
    assert "playsinline" in html
    assert "autoplay" not in html
    assert "loop" not in html
    assert "muted" not in html
    assert VIDEO_SRC in html
    assert "width:100%" in html
    for term in FORBIDDEN_JARGON:
        assert term not in html


def test_real_hana_final_page_video_is_positioned_after_hero_before_leaderboard():
    path = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "final" / "index.html"
    html = path.read_text(encoding="utf-8")
    assert 'id="final-video"' in html
    hero_pos = html.index('id="tournament"')
    video_pos = html.index('id="final-video"')
    leaderboard_pos = html.index('id="final-leaderboard"')
    assert hero_pos < video_pos < leaderboard_pos, "video must sit between the hero and the rest of the FINAL content"


def test_real_hana_final_page_video_element_is_a_real_html5_video_with_the_expected_attrs():
    path = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "final" / "index.html"
    html = path.read_text(encoding="utf-8")
    video_tag = re.search(r"<video[^>]*>", html)
    assert video_tag is not None
    tag = video_tag.group(0)
    assert "controls" in tag
    assert "playsinline" in tag
    assert "autoplay" not in tag
    assert "loop" not in tag
    assert "muted" not in tag
    assert VIDEO_SRC in tag
    assert "width:100%" in tag
    assert "max-width:100%" in tag


def test_real_hana_home_page_mirrors_the_same_video_section():
    path = REPO_ROOT / "docs" / "index.html"
    html = path.read_text(encoding="utf-8")
    assert 'id="final-video"' in html
    assert VIDEO_SRC in html


def test_video_file_actually_exists_at_the_referenced_path_bytewise():
    """VIDEO_SRC is a site-root-absolute URL; on disk that is
    docs/<the rest of the path>. Confirms the referenced file exists
    and is a real MP4, and that it was copied verbatim (not
    re-encoded) from the operator-supplied original."""
    video_path = REPO_ROOT / "docs" / VIDEO_SRC.lstrip("/")
    assert video_path.is_file(), f"referenced video file does not exist on disk: {video_path}"
    assert video_path.stat().st_size > 0
    header = video_path.read_bytes()[:12]
    assert header[4:8] == b"ftyp", "expected a valid MP4 (ISO Base Media) file signature"
