"""Real-capture-backed tests for klpga.website_v2.official_detail_enrichment.

Fixtures (tests/fixtures/official_detail/*.html) are real HTTP responses
captured 2026-10-03 from klpga.co.kr via a GitHub Actions runner (this
sandbox has no network access to klpga.co.kr -- see
klpga.config.PUBLIC_RECORD_SEASON_DETAIL_ENDPOINT / SCORE_DETAIL_ENDPOINT
for the full discovery trail), playerCode=8436 (유현주),
gameCode=2026080002 (BC카드 · 한경 제48회 KLPGA 챔피언십). Never
fabricated/hand-written HTML -- real server bytes.
"""
from __future__ import annotations

from pathlib import Path

from klpga.collectors.player_profile import (
    parse_public_record_season_detail_html,
    parse_score_detail_html,
)
from klpga.website_v2.official_detail_enrichment import (
    _SEASON_DETAIL_FIELD_MAP,
    compute_hole_distribution,
    compute_round_momentum,
    derive_course_fit_score,
    derive_player_dna,
    enrich_player_history_doc,
)

FIXTURES = Path(__file__).parent / "fixtures" / "official_detail"


def _season_detail():
    html = (FIXTURES / "8436_publicRecordSeasonDetail.html").read_text(encoding="utf-8")
    raw_sections = parse_public_record_season_detail_html(html)
    normalized = {}
    for section, label, field_name in _SEASON_DETAIL_FIELD_MAP:
        row = raw_sections.get(section, {}).get(label)
        normalized[field_name] = row["value"] if row else None
    return {"raw_sections": raw_sections, "normalized": normalized}


def _scorecards():
    html = (FIXTURES / "8436_scoreDetail.html").read_text(encoding="utf-8")
    return {"2026080002": parse_score_detail_html(html)}


def test_season_detail_field_map_extracts_real_confirmed_values():
    normalized = _season_detail()["normalized"]
    # Exact real values from the 2026-10-03 capture -- see module docstring.
    assert normalized["average_score"] == 77.625
    assert normalized["birdie_rate"] == 4.8611
    assert normalized["fairway_hit_rate"] == 60.0
    assert normalized["avg_driving_distance"] == 238.308
    assert normalized["gir_rate"] == 56.9444
    assert normalized["avg_putts"] == 32.25
    # Real-and-genuinely-absent, never fabricated as 0.
    assert normalized["eagle_count"] is None
    assert normalized["hole_in_one_count"] is None


def test_hole_distribution_matches_real_scorecard_counts():
    hd = compute_hole_distribution(_scorecards())
    assert hd["total_holes"] == 36  # 2 real rounds x 18 holes
    assert hd["counts"]["Birdie"] == 2
    assert hd["counts"]["Double Bogey"] == 2
    assert hd["counts"]["Par"] == 24
    assert hd["counts"]["Bogey"] == 8
    assert hd["double_bogey_avoidance_rate"] == 1 - 2 / 36


def test_round_momentum_matches_real_scorecard_totals():
    rm = compute_round_momentum(_scorecards())
    totals = {r["round"]: r["total_strokes"] for r in rm["rounds"]}
    assert totals == {1: 79.0, 2: 76.0}


def test_hole_distribution_never_fabricates_a_zero_for_an_uncollected_round():
    hd = compute_hole_distribution({"9999999999": {"error": "fetch failed"}})
    assert hd["total_holes"] == 0
    assert hd["double_bogey_avoidance_rate"] is None


def test_enrich_player_history_doc_preserves_every_existing_key():
    original = {
        "player_id": "8436", "player_name": "유현주",
        "career_dna": {"career_foundation": "SG APP", "career_foundation_share_pct": 30.4,
                        "most_consistent_component": "SG PUTT", "most_volatile_component": "SG OTT",
                        "fastest_growing_component": "SG OTT"},
        "course_profile": [{"tournament_family": "두산건설 We've 챔피언십", "appearances": 3,
                             "avg_sg_total": -2.523, "best_sg_total": -0.92, "worst_sg_total": -4.79}],
        "some_untouched_field": {"nested": ["value"]},
    }
    enriched = enrich_player_history_doc(original, _season_detail(), _scorecards())

    for key, value in original.items():
        assert enriched[key] == value, f"existing key {key!r} was altered"

    new_keys = set(enriched) - set(original)
    assert new_keys == {
        "official_detail_record", "hole_distribution", "round_momentum",
        "player_dna", "course_fit_score",
    }


def test_player_dna_is_a_thin_readthrough_of_existing_career_dna_never_a_new_classification():
    doc = {"career_dna": {"career_foundation": "SG APP", "career_foundation_share_pct": 30.4,
                           "most_consistent_component": "SG PUTT", "most_volatile_component": "SG OTT",
                           "fastest_growing_component": "SG OTT"}}
    dna = derive_player_dna(doc)
    assert dna["foundation"] == "SG APP"
    assert dna["foundation_share_pct"] == 30.4


def test_course_fit_score_never_invents_a_difficulty_weighting():
    doc = {"course_profile": [{"tournament_family": "X", "appearances": 1, "avg_sg_total": -1.0,
                                "best_sg_total": -1.0, "worst_sg_total": -1.0}]}
    fit = derive_course_fit_score(doc)
    assert fit[0]["difficulty_weighting"] is None
    assert fit[0]["avg_sg_total"] == -1.0


def test_generic_across_player_ids_no_special_casing():
    """The whole module must behave identically regardless of
    player_id/player_name -- no `if player_id == "8436"` branch
    anywhere in official_detail_enrichment.py."""
    import inspect
    import klpga.website_v2.official_detail_enrichment as mod
    source = inspect.getsource(mod)
    assert "8436" not in source
    assert "유현주" not in source
