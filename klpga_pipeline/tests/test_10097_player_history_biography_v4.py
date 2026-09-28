"""NEO PLAYER BIOGRAPHY V4 (2026-09-25), playerCode=10097 only.

"Stop thinking about Player History. Start thinking about Player
Biography. The page must answer one question: 'Who is this golfer, and
how is she playing RIGHT NOW?' Current form comes first. History exists
only to explain the current player."

These tests pin down the new 11-section structure and the five new
derived features (current_form_indicator, why_now, player_identity,
career_story, course_profile) -- every one traceable to values already
computed elsewhere in this builder, never a new raw measurement.
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


# ---------------------------------------------------------------------------
# STRICT ORDER
# ---------------------------------------------------------------------------

def test_nothing_database_related_appears_before_section_11():
    """'Nothing database-related may appear before section 12 [11].'
    Warehouse/SQLite/script/builder/branch names and internal enum
    values must never appear before the final Database section."""
    _, html = _doc_and_html()
    recon_idx = html.index('id="ph-reconciliation"')
    before = html[:recon_idx]
    for banned in (
        "historical_sg_warehouse", ".json", ".sqlite", "build_10097_player_history.py",
        "reconcile_10097_player_history", "AVAILABLE_BUT_NOT_COLLECTED", "RECONCILED_OK",
    ):
        assert banned not in before, f"database-internal string leaked before section 11: {banned!r}"


def test_current_form_hero_is_tight_not_overloaded():
    """'Do NOT overload the hero.' Section 1's own <details> body (up to
    the next section's id) must not contain a <table> -- the hero is
    chips and a short note only; detail tables live in subordinate
    blocks or later sections."""
    _, html = _doc_and_html()
    start = html.index('id="ph-current-form"')
    end = html.index("</details>", start)
    hero_only = html[start:end]
    assert "<table" not in hero_only


def test_why_now_leads_with_one_sentence_before_the_arrow_chips():
    """V5 mission briefly replaced the current/career/diff TABLE with a
    dot-plot chart; V6 mission (2026-09-25) removed that chart too --
    it said the same four numbers the arrow chips already state, just
    slower to read ('if removing this does not make the user
    understand her less, delete it'). The sentence still leads.

    MISSION "30초 스캔" (2026-09-27), approved wireframe
    (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7): the arrow
    CHIPS ('APP ▲ OTT ▲ PUTT ▼' text) became a 4-card icon grid
    (.ph-arrow-grid) -- still no table, no chart, sentence still
    leads.

    MISSION V72 (2026-09-28): 'Remove duplicated narrative. If the
    Story layer already tells the conclusion, the detailed section
    below becomes evidence only.' The Story layer at the top of the
    page now states this exact same real conclusion (why_now's own
    "sentence" field) as its own headline -- that specific sentence no
    longer leads THIS section, since restating it here would be the
    exact duplication V72 bans. The skill chain's own, different,
    real closing sentence (which real scoring/score/result numbers
    this lead skill produced) is not a duplicate of anything above it
    and stays."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-why-now"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert "<table" not in section
    assert "<svg" not in section
    assert doc["why_now"]["sentence"] not in section, "MISSION V72: this exact sentence now lives only in the Story layer"
    assert "ph-arrow-grid" in section
    # the same real conclusion (lead component) still leads the page,
    # in the Story layer's own headline card
    lead = doc["why_now"]["lead_component"].removeprefix("SG ")
    story_start = html.index('id="ph-story-layer"')
    story_end = html.index("</section>", story_start)
    assert lead in html[story_start:story_end]


def test_why_now_sentence_names_exactly_one_lead_component():
    doc = build_script.build()
    why_now = doc["why_now"]
    assert why_now is not None
    assert why_now["lead_component"] in ("SG OTT", "SG APP", "SG ARG", "SG PUTT")
    assert why_now["lead_component"] in why_now["sentence"]
    # the lead component must be the real largest-magnitude delta among the four
    real = [a for a in why_now["arrows"] if a["delta"] is not None]
    biggest = max(real, key=lambda a: abs(a["delta"]))
    assert biggest["component"] == why_now["lead_component"]


def test_recent_results_has_last_5_10_and_20_nothing_else():
    """MISSION V7 (2026-09-25) redesigned the layout: the old three full
    tables (5, then 10, then 20) made the reader scroll past the same
    most-recent rows three times over -- only the last-5 table stayed
    open; rows 6-20 nested behind one 더보기 toggle, never repeated.

    MISSION "30초 스캔" (2026-09-27), approved wireframe
    (https://claude.ai/artifact/BZBJhzA36ZvskuKPkDjyv7) superseded that
    table layout entirely: all 20 completed tournaments now render as
    one flat, unnested dot in a single "form strip" -- no partial-5
    table, no 6-20th toggle, and (structurally) no way for a row to
    print twice, since there is exactly one dot per row."""
    doc, html = _doc_and_html()
    assert len(doc["recent_form_20"]) == 20
    start = html.index('id="ph-recent-form"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert "최근 5개 완료 대회" not in section
    assert "6~20번째" not in section
    assert section.count('class="ph-form-dot') == 20


# ---------------------------------------------------------------------------
# PLAYER IDENTITY
# ---------------------------------------------------------------------------

def test_player_identity_type_matches_the_real_career_foundation():
    """Every identity label traces to career_dna's already-computed
    career_foundation -- never invented independently."""
    doc = build_script.build()
    identity = doc["player_identity"]
    career_dna = doc["career_dna"]
    assert identity["primary_component"] == career_dna["career_foundation"]
    assert identity["primary_share_pct"] == career_dna["career_foundation_share_pct"]
    label_map = {
        "SG OTT": "볼 스트라이커", "SG APP": "어프로치 플레이어",
        "SG ARG": "리커버리 플레이어", "SG PUTT": "퍼팅으로 승부하는 유형",
    }
    assert identity["primary_type"] == label_map[career_dna["career_foundation"]]


def test_player_identity_renders_before_career_story():
    _, html = _doc_and_html()
    assert html.index('id="ph-player-identity"') < html.index('id="ph-career-story"')


# ---------------------------------------------------------------------------
# CAREER STORY (told backwards)
# ---------------------------------------------------------------------------

def test_career_story_current_chapter_is_the_latest_real_season():
    doc = build_script.build()
    story = doc["career_story"]
    latest_row = doc["career_overview"]["season_rows"][-1]
    assert story["current"]["season"] == latest_row["season"]
    assert story["current"]["sg_total"] == latest_row["sg_total"]


def test_career_story_chapters_are_backwards_not_chronological():
    """Winning Stage -> Breakthrough -> Development -> Adaptation, each
    naming a REAL, earlier-computed milestone -- never chronological
    (earliest-to-latest) order.

    MISSION (2026-09-28): 'The timeline should describe measurable
    career events, not narrative phases.' Chapter names renamed to
    name a real, measurable event (최고 경기력/경기력 도약/첫 우승/
    기준점) instead of a subjective life-stage word -- the backwards
    ordering itself is unchanged.

    MISSION (2026-09-28) follow-up: the earliest chapter renamed again
    to 기준점 (Baseline) -- 'the earliest reliable performance
    reference point... not their debut.'"""
    doc = build_script.build()
    chapters = [c["chapter"] for c in doc["career_story"]["chapters"]]
    assert chapters == sorted(chapters, key=lambda c: ["최고 경기력", "경기력 도약", "첫 우승", "기준점"].index(c))
    # every chapter's milestone is a real one from _player_story, never fabricated
    real_labels = {m["label"] for m in doc["player_story"]}
    for c in doc["career_story"]["chapters"]:
        for m in c["milestones"]:
            assert m["label"] in real_labels
            assert m in doc["player_story"]


def test_career_story_reveals_real_chronological_seasons_only_at_the_end():
    """'Only afterwards reveal seasons... Tell the story backwards.'
    In the rendered HTML, the current-first narrative chapters must
    appear before the season-by-season table.

    MISSION (2026-09-28): the '지금' (Current) stage label was renamed
    to '현재 경기력' (Current Performance) -- a measurable-event label
    instead of a bare narrative word -- per 'avoid subjective words.'"""
    _, html = _doc_and_html()
    start = html.index('id="ph-career-story"')
    end = html.index("</details>", start)
    section = html[start:end]
    chapters_idx = section.index("현재 경기력")
    season_table_idx = section.index("시즌별 기록")
    assert chapters_idx < season_table_idx


def test_career_story_never_starts_the_visible_narrative_with_a_bare_season():
    """The FIRST thing inside the Career Story body must be '현재 경기력'
    (Current Performance), never a literal season year like '2023'.

    MISSION (2026-09-28): renamed from '지금' -- see the mission note
    on test_career_story_reveals_real_chronological_seasons_only_at_the_end."""
    _, html = _doc_and_html()
    start = html.index('id="ph-career-story"')
    body_start = html.index('class="pi-section__body"', start)
    first_stage = html.index('class="ph-bio-stage"', body_start)
    first_label = html.index("piq-step-label", first_stage)
    snippet = html[first_label:first_label + 60]
    assert "현재 경기력" in snippet


# ---------------------------------------------------------------------------
# COURSE PROFILE
# ---------------------------------------------------------------------------

def test_course_profile_only_includes_real_repeated_tournaments():
    """'Nothing speculative.' Every profile must be a tournament she
    played at least twice -- a single appearance is excluded, never
    guessed at as a 'course.'"""
    doc = build_script.build()
    profiles = doc["course_profile"]
    assert profiles
    for p in profiles:
        assert p["appearances"] >= 2
    # sorted strongest-first
    avgs = [p["avg_sg_total"] for p in profiles]
    assert avgs == sorted(avgs, reverse=True)


def test_course_profile_discloses_the_real_data_limitation():
    """Course names are not reliably on file (see NOT_AVAILABLE) -- the
    section must disclose that it uses repeated tournament name as a
    proxy, never silently imply verified venue-level matching."""
    _, html = _doc_and_html()
    start = html.index('id="ph-course-profile"')
    end = html.index("</details>", start)
    section = html[start:end]
    assert "코스명" in section
    assert "반복 개최" in section


# ---------------------------------------------------------------------------
# CHART/JARGON RULES (biography-wide)
# ---------------------------------------------------------------------------

def test_no_duplicate_season_summary_sections():
    """'If two sections answer the same question, delete one.' The old
    standalone Career Overview ('선수 요약') and forward Player Story
    ('선수 스토리') sections are gone -- Career Story supersedes both."""
    _, html = _doc_and_html()
    assert 'id="ph-career-overview"' not in html
    assert 'id="ph-player-story"' not in html
