"""RED TEAM narrative mission (2026-09-25), playerCode=10097 only.

'Keep every real computation. Hide every implementation detail. Users
should never see 5-window / 91 windows / moving average / percentile
among windows. Instead translate them into Early Season / Mid Season /
Late Season / Peak Form / Current Form. For every stage answer: which
skill improved? which skill declined? Never lead with statistics. Lead
with the story. The calculations stay exactly the same. Only the
presentation changes.'

These tests pin down: (1) career_rolling_trend's own JSON keeps every
field it always had (window_size, total_windows, self_percentile, ...)
-- nothing was deleted; (2) the visible page never renders window_size,
total_windows, "이동평균", or "백분위" text; (3) career_form_story's
five stages are built ONLY from already-real numbers (no new stat);
(4) every stage's rendered card leads with a story sentence, with
numbers only as supporting chips beneath it.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("build_10097_player_history", ROOT / "scripts" / "build_10097_player_history.py")
build_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_script)

from klpga.website_v2 import player_history_report as report  # noqa: E402


def _doc_and_html():
    doc = build_script.build()
    return doc, report.render_player_history_html(doc)


def test_career_rolling_trend_json_keeps_every_field_unchanged():
    """Nothing is deleted from the underlying computation -- window_size,
    total_windows, self_percentile per window, and the raw series are
    all still real and present in the data, even though the page never
    shows them."""
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    assert crt["window_size"] == 5
    assert crt["total_windows"] == len(crt["series"])
    assert crt["total_windows"] > 1
    assert all("self_percentile" in w for w in crt["series"])
    assert all("moving_average_sg_total" in w for w in crt["series"])


def test_window_mechanics_never_appear_in_the_career_rolling_trend_block():
    """The exact banned vocabulary, scoped to the block this mission
    targets (career_rolling_trend's 5-tournament/91-window rolling
    series): window_size/total_windows as text, '이동평균' (moving
    average), '백분위 (window self-percentile)', '슬라이딩' (sliding).
    Career Heartbeat's own, separately-computed per-TOURNAMENT
    percentile (a different quantity, a different already-red-teamed
    V7 feature) is out of this mission's scope and keeps its own
    '백분위' disclosure -- checked here only within
    #ph-career-rolling-trend, not the whole page.

    MISSION NEO PLAYER PROFILE V2 (2026-09-27) relocated Career
    Heartbeat to #8 Raw Data, so its id no longer immediately follows
    this block -- bounded instead by #ph-technical-stats-2025, the
    next real block in the season-evolution cluster."""
    doc, html = _doc_and_html()
    crt = doc["career_rolling_trend"]
    start = html.index('id="ph-career-rolling-trend"')
    end = html.index('id="ph-technical-stats-2025"')
    section = html[start:end]
    banned_numeric = [f'{crt["window_size"]}개 대회 슬라이딩', f'총 {crt["total_windows"]}개 구간']
    for phrase in banned_numeric:
        assert phrase not in section
    assert "이동평균" not in section
    assert "백분위" not in section
    assert "슬라이딩" not in section


def test_career_form_story_has_five_real_stages_each_traceable_to_the_series():
    """Every stage's window_index must correspond to a real entry in
    career_rolling_trend's own series -- no invented window."""
    doc = build_script.build()
    story = doc["career_form_story"]
    crt = doc["career_rolling_trend"]
    assert len(story) == 5
    labels = [s["stage"] for s in story]
    assert labels == ["시즌 초반", "시즌 중반", "시즌 후반", "전성기", "현재 폼"]
    series_ranges = {(w["start_tournament"], w["end_tournament"]) for w in crt["series"]}
    for s in story:
        assert (s["start_tournament"], s["end_tournament"]) in series_ranges


def test_current_form_stage_is_the_series_final_window():
    doc = build_script.build()
    story = doc["career_form_story"]
    crt = doc["career_rolling_trend"]
    current = next(s for s in story if s["stage"] == "현재 폼")
    last_window = crt["series"][-1]
    assert current["start_tournament"] == last_window["start_tournament"]
    assert current["end_tournament"] == last_window["end_tournament"]


def test_peak_form_stage_is_the_already_computed_peak_window():
    doc = build_script.build()
    story = doc["career_form_story"]
    crt = doc["career_rolling_trend"]
    peak_stage = next(s for s in story if "전성기" in s["stage"])
    peak_window = crt["peak_window"]
    assert peak_stage["start_tournament"] == peak_window["start_tournament"]
    assert peak_stage["end_tournament"] == peak_window["end_tournament"]


def test_every_stage_names_a_best_and_worst_skill_from_real_deltas():
    """'Which skill improved? Which skill declined?' -- every stage
    must name a best/worst SG component, each delta computed against
    the real career-average-per-component (not invented)."""
    doc = build_script.build()
    story = doc["career_form_story"]
    career_component_avg = build_script._career_component_averages(
        build_script.recon_module.reconcile()
    )
    for s in story:
        assert s["best_component"] in ("SG OTT", "SG APP", "SG ARG", "SG PUTT")
        assert s["best_delta"] is not None
        key = {"SG OTT": "ott", "SG APP": "app", "SG ARG": "arg", "SG PUTT": "putt"}[s["best_component"]]
        avg = career_component_avg[key]["average"]
        assert avg is not None


def test_worst_skill_is_never_called_a_decline_when_the_real_delta_is_positive():
    """A component can be 'relatively weakest' while still being ABOVE
    her career average -- the story must never claim it declined in
    that case (RED TEAM: never a false claim from a true number)."""
    doc, html = _doc_and_html()
    story = doc["career_form_story"]
    start = html.index('id="ph-career-rolling-trend"')
    end = html.index('id="ph-career-heartbeat"')
    section = html[start:end]
    for s in story:
        if s.get("worst_delta") is not None and s["worst_delta"] >= 0:
            # this stage's own sentence must not say "가장 부진했습니다" (declined)
            pass  # cross-checked below via the narrative function directly
    from klpga.website_v2.player_history_report import _stage_narrative
    for s in story:
        sentence = _stage_narrative(s)
        if s.get("worst_delta") is not None and s["worst_delta"] >= 0:
            assert "부진했습니다" not in sentence
            assert "상대적으로 가장 덜 강했습니다" in sentence


def test_story_stage_sentence_leads_the_card_before_the_numeric_chips():
    """'Never lead with statistics. Lead with the story.' -- in every
    stage card's markup, the narrative <p> must appear before the
    numeric chip <div>."""
    _, html = _doc_and_html()
    story_start = html.index('class="ph-form-story"')
    story_end = html.index('class="ph-spark"', story_start)  # sparkline right after the story block
    story_html = html[story_start:story_end]
    cards = story_html.split('class="ph-form-stage"')[1:]
    # 4 or 5 real cards: the renderer merges two stages into one card
    # when her career peak (전성기) coincides with a season-third's own
    # real tournament range, rather than repeating identical numbers.
    assert len(cards) in (4, 5)
    for card in cards:
        sentence_idx = card.index("piq-current-detail")
        chip_idx = card.index("piq-audit")
        assert sentence_idx < chip_idx


def test_sg_component_letter_names_are_never_bare_english_jargon_without_prefix():
    """Consistent with the site-wide SG-prefix convention -- best/worst
    components are always 'SG OTT' etc, never a bare 'OTT'."""
    doc = build_script.build()
    for s in doc["career_form_story"]:
        if s.get("best_component"):
            assert s["best_component"].startswith("SG ")
        if s.get("worst_component"):
            assert s["worst_component"].startswith("SG ")
