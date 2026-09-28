"""MISSION V12 (2026-09-27), playerCode=10097 only.

"Forget the database. Forget provenance. Forget governance. Open the
page. Watch a golfer read it. Every place where the eye stops, fix the
design. Every place where the eye hesitates, simplify. Every place
where the user must think, replace with a visual. Do not add
information. Only improve understanding."

This mission touched CSS and small presentational markup only -- no new
data, no new sections, no changed calculations:

1. Every collapsed `<details class="evidence-detail">` (and its nested
   "more" toggle) previously gave no visual sign it could be opened --
   `display:flex` on `<summary>` silently kills the browser's native
   disclosure triangle, with nothing replacing it. A `::after` chevron
   (▸ collapsed, ▾ open) now covers every one of them via one shared,
   `.ph-page`-scoped rule.
2. `.label-chip` only ever rendered in one visual style (green), so a
   "worst"/"slump" chip looked identical to a "best"/"peak" chip even
   when the underlying number was genuinely negative. `_chip()` now
   takes a `negative` flag, applied at the 4 call sites that show a
   worst/slump value, keyed strictly off the real numeric sign of that
   value -- never off the "worst"/"slump" label alone, since a
   player's weakest season can still be a positive number.
3. The Round Analysis cards (`_round_card`) had the same problem: 최고
   라운드 and 최악 라운드 rendered with an identical neutral gray left
   border. They now carry `piq-brief--positive`/`piq-brief--negative`,
   keyed off the real sign of the round's sg_total or delta.

Every real number, section, and id from prior missions is unchanged;
these tests confirm the new visual hooks exist and are keyed off real
signs, not labels.
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

from klpga.website_v2 import player_history_report as report  # noqa: E402


def _doc_and_html():
    doc = build_script.build()
    return doc, report.render_player_history_html(doc)


def test_chevron_css_rule_is_scoped_to_ph_page_only():
    css = (ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.css").read_text()
    assert ".ph-page .evidence-detail summary::after" in css
    assert ".ph-page .evidence-detail[open]>summary::after" in css
    # comment/brace balance -- the exact bug class caught in Mission V8
    assert css.count("{") == css.count("}")
    assert css.count("/*") == css.count("*/")


def test_negative_chip_css_class_exists_and_differs_from_positive():
    css = (ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.css").read_text()
    assert ".label-chip--negative{" in css
    assert ".label-chip--positive{" in css


def test_chip_helper_supports_a_real_negative_flag():
    html = report._chip("SG PUTT -0.12", negative=True)
    assert "label-chip--negative" in html
    assert "label-chip--positive" not in html

    html_pos = report._chip("SG APP +0.57", positive=True)
    assert "label-chip--positive" in html_pos
    assert "label-chip--negative" not in html_pos


def test_worst_component_chip_in_career_form_story_is_colored_by_real_sign():
    doc = _doc_and_html()[0]
    html = report._career_form_story_html(doc["career_form_story"])
    for stage in doc["career_form_story"]:
        worst_text = f'{stage["worst_component"]} {stage["worst_delta"]:+.2f}'
        chip_start = html.index(worst_text)
        tag_start = html.rindex("<span", 0, chip_start)
        tag_end = html.index(">", tag_start)
        chip_tag = html[tag_start:tag_end]
        if stage["worst_delta"] < 0:
            assert "label-chip--negative" in chip_tag, f"worst_delta {stage['worst_delta']} is negative but chip is not red"
        else:
            assert "label-chip--negative" not in chip_tag, f"worst_delta {stage['worst_delta']} is non-negative but chip is red"


def test_worst_season_chip_in_career_evolution_never_colored_red_when_value_is_positive():
    """The exact scenario this mission's fix targets: a player's weakest
    season can still be a genuinely positive SG Total, and must not be
    painted red merely because it is labeled '최저 시즌'.

    MISSION "PLAYER HISTORY V20" (2026-09-28) moved this fact from a
    <span class="label-chip"> to a mark drawn directly on the season
    evolution chart (_marked_trend_svg) -- the same real-sign rule now
    applies to that mark's `fill` color instead of a chip class.

    MISSION V60 (2026-09-28): the mark's real value moved from a
    visible <text> label into a <title> tooltip on its <circle>; the
    fill color check now targets the circle instead of the old text."""
    import re
    doc, html = _doc_and_html()
    for metric in doc["career_evolution"].values():
        worst_raw = metric["worst_season"]["value"]
        # scope the search to this metric's own block -- several metrics
        # can share the same worst_season year, so a page-wide find()
        # would match the wrong metric's chip
        label_idx = html.index(f'>{report.escape(metric["label"])}</p>')
        block_end = html.index("</div></div>", label_idx)
        block = html[label_idx:block_end]
        m = re.search(r'<circle[^>]*fill="(#[0-9a-f]{6})"[^>]*>\s*<title>([^<]*최저[^<]*)</title>', block)
        assert m, f"no '최저' mark found for {metric['label']}"
        mark_color = m.group(1)
        if worst_raw < 0:
            assert mark_color == "#9b493f", f"{metric['label']}'s worst season {worst_raw} is negative but mark color is {mark_color}, not red"
        else:
            assert mark_color != "#9b493f", f"{metric['label']}'s worst season {worst_raw} is non-negative but mark color is red"


def test_slump_chip_in_season_replay_is_colored_by_real_sign():
    """MISSION V40 (2026-09-28): the slump tournament's name is now a
    real drill-down link (_tournament_link) to its own row in the full
    tournament table, so the needle allows for an optional wrapping
    <a href="#t-..."> tag between the label and the (possibly escaped)
    tournament name.

    MISSION V73 (2026-09-28): the Season Replay chart now also draws a
    real slump ring whose <title> tooltip starts with the same real
    "슬럼프: {tournament}..." text, earlier in the page than the chip
    -- the pattern is anchored to the chip's own <span class="label-
    chip..."> opening tag so it can never match that tooltip instead."""
    import re
    doc, html = _doc_and_html()
    for row in doc["season_replay"]:
        slump = row.get("slump")
        if not slump:
            continue
        escaped_name = report.escape(slump["tournament"])
        pattern = (
            r'<span class="(label-chip[^"]*)">' + re.escape("슬럼프: ")
            + r'(?:<a [^>]*>)?' + re.escape(escaped_name)
        )
        m = re.search(pattern, html)
        assert m, f"no slump chip found for {slump['tournament']}"
        chip_class = m.group(1)
        if slump["sg_total"] < 0:
            assert "label-chip--negative" in chip_class
        else:
            assert "label-chip--negative" not in chip_class, f"{slump['tournament']} sg_total={slump['sg_total']} is non-negative but rendered red"


def test_round_history_cards_are_colored_by_real_sign_not_by_label():
    """MISSION NEO PLAYER PROFILE V2 (2026-09-27) reduced #ph-round-
    history to the best/worst pair only (see _round_history_html) and
    relocated 가장 안정적인 대회/최다 향상 라운드/최대 붕괴 to #8 Raw
    Data via _round_history_detail_html -- both locations must still
    color strictly by the real numeric sign, never by the label.

    MISSION "30초 스캔" (2026-09-27), approved wireframe
    (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7) replaced the
    visible #6 pair's sentence cards (<strong>label</strong>, via
    _round_card) with big-number stat cards (via the new
    _round_big_stat, .ph-round-big-lbl instead of <strong>) -- #8's
    relocated three facts still use the original _round_card markup
    unchanged."""
    doc, html = _doc_and_html()
    rh = doc["round_history"]

    def _big_stat_class(section_html: str, label: str) -> str:
        idx = section_html.index(f'<div class="ph-round-big-lbl">{label}</div>')
        div_start = section_html.rindex('<div class="ph-round-big', 0, idx)
        div_end = section_html.index(">", div_start)
        return section_html[div_start:div_end]

    def _card_class(section_html: str, label: str) -> str:
        idx = section_html.index(f"<strong>{label}</strong>")
        div_start = section_html.rindex("<div", 0, idx)
        div_end = section_html.index(">", div_start)
        return section_html[div_start:div_end]

    section_start = html.index('id="ph-round-history"')
    section_end = html.index("</details>", section_start)
    section_html = html[section_start:section_end]

    best_class = _big_stat_class(section_html, "최고 라운드")
    worst_class = _big_stat_class(section_html, "최악 라운드")
    assert "ph-round-big--positive" in best_class if rh["best_round"]["sg_total"] >= 0 else "ph-round-big--negative" in best_class
    assert "ph-round-big--negative" in worst_class if rh["worst_round"]["sg_total"] < 0 else "ph-round-big--positive" in worst_class

    detail_start = html.index('id="ph-round-history-detail"')
    detail_end = html.index("</div></details>", detail_start)
    detail_html = html[detail_start:detail_end]
    collapse_class = _card_class(detail_html, "최대 붕괴")
    if rh["largest_collapse"]["delta"] < 0:
        assert "piq-brief--negative" in collapse_class
    else:
        assert "piq-brief--positive" in collapse_class


def test_round_card_css_variants_are_scoped_to_ph_page():
    css = (ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.css").read_text()
    assert ".ph-page .piq-brief--positive{" in css
    assert ".ph-page .piq-brief--negative{" in css


def test_no_golf_statistic_changed_between_consecutive_builds():
    """Purely visual mission -- no calculation may have become
    nondeterministic as a side effect."""
    doc1 = build_script.build()
    doc2 = build_script.build()
    for key in ("current_vs_career", "tournament_history", "career_overview", "round_history", "career_evolution", "season_replay"):
        assert doc1[key] == doc2[key], f"{key} changed between builds -- a calculation became nondeterministic"


def test_no_new_numbered_section_ids_were_added():
    _, html = _doc_and_html()
    known_ids = {
        "ph-current-form", "ph-snapshot", "ph-why-now", "ph-recent-form", "ph-in-progress",
        "ph-player-identity", "ph-career-story", "ph-career-evolution", "ph-player-evolution",
        "ph-season-replay", "ph-career-rolling-trend", "ph-career-heartbeat", "ph-technical-stats-2025",
        "ph-tournament-trend", "ph-tournament-history", "ph-round-history", "ph-hole-history",
        "ph-course-profile", "ph-player-dna-radar", "ph-career-dna", "ph-reconciliation", "ph-not-available",
    }
    found_ids = set(re.findall(r'<details class="[^"]*pi-section[^"]*" id="(ph-[a-z0-9-]+)"', html))
    assert found_ids <= known_ids, f"new top-level section id(s) introduced: {found_ids - known_ids}"
