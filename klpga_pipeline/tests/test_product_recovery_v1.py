"""NEO GOLF DATA -- KB PRE / HOME PUBLIC PRODUCT RECOVERY V1.

Regression coverage for the corrected contract:
  - the tournament outcome probability distribution (CUT/TOP20/TOP10/
    TOP5/WIN) stays structurally defined in the canonical schema but
    is never rendered publicly while the model publication gate is
    BLOCKED -- WIN has no exception;
  - the NEO recent-5-round SG metric is never publicly labelled as if
    it were the official KLPGA SG Total ranking;
  - HOME never composes a tournament stage's own page body;
  - internal validation/hash/tier2 metadata never leaks into the
    public PRE summary copy.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

_SPEC84 = importlib.util.spec_from_file_location(
    "product_recovery_s84", ROOT / "scripts" / "84_build_ok_open_pre_website_candidate.py"
)
builder84 = importlib.util.module_from_spec(_SPEC84)
_SPEC84.loader.exec_module(builder84)


def _kb_pre_html():
    out = builder84.build("2026090003")
    return (out / "tournaments/2026/2026090003/pre/index.html").read_text(encoding="utf-8")


def test_probability_distribution_is_structurally_defined_in_the_canonical_schema():
    """Contract correction: the recovered probability distribution
    must not be deleted from the schema merely because it is withheld
    from the public renderer."""
    master = json.loads((CONTENT / "2026090003_PRE_PUBLIC_MASTER.json").read_text(encoding="utf-8"))
    contract = master["probability_distribution_contract"]
    assert contract["schema"] == ["cut_probability", "top20_probability", "top10_probability", "top5_probability", "win_probability"]
    assert contract["checkpoint"] == "PRE"
    assert contract["model_status"] == builder84.LIVE_PROBABILITY_MODEL_STATUS
    expected_publication_status = "APPROVED" if builder84.LIVE_PROBABILITY_MODEL_STATUS == "VALIDATED" else "BLOCKED"
    assert contract["publication_status"] == expected_publication_status
    for record in master["records"]:
        assert "cut_probability" in record and "win_probability" in record


def test_blocked_probability_distribution_is_never_rendered_publicly_win_included():
    """No exception for WIN: while MODEL_VALIDATED_FOR_PUBLICATION is
    False, none of CUT/TOP20/TOP10/TOP5/WIN may appear as a PRE table
    column, even though win_probability is the one member with a real
    computed value today."""
    html = _kb_pre_html()
    if builder84.MODEL_VALIDATED_FOR_PUBLICATION:
        return  # nothing to assert once genuinely approved -- see the companion presence test below
    for forbidden in ("우승확률", "TOP20", "TOP10", "TOP5", "컷 통과확률"):
        assert forbidden not in html, f"blocked probability marker leaked into PRE: {forbidden!r}"
    assert "class='win'" not in html


def test_approved_probability_distribution_would_render_all_five_members():
    """Forward-compatibility check on the renderer's own logic (not a
    live assertion against today's BLOCKED state): if the gate were
    VALIDATED, every one of the five columns must render together --
    partial exposure is not a supported state."""
    assert builder84._PROBABILITY_COLUMNS == (
        ("cut_probability", "컷 통과확률"),
        ("top20_probability", "TOP20"),
        ("top10_probability", "TOP10"),
        ("top5_probability", "TOP5"),
        ("win_probability", "우승확률"),
    )


def test_neo_recent_sg_is_never_labelled_as_official_sg_total():
    """SG LABEL DECISION: the NEO recent-5-tournament-event SG ranking
    must never render under a label that reads as the official KLPGA
    statistic, and (NEO PRODUCT CONTRACT RECOVERY item 2) must never
    claim to be a per-round figure either -- it is the mean of the
    last 5 retained tournament-level SG observations, not 5 rounds."""
    html = _kb_pre_html()
    for forbidden_label in ("SG Total", "SG 전체", "KLPGA SG", "5R SG", "10R SG"):
        assert forbidden_label not in html
    assert "최근 5개 대회 SG" in html


def test_home_becomes_the_current_tournament_stage_body_by_owner_design():
    """KB TOURNAMENT-ONLY PUBLIC HOME -- PRIORITY MODE (Project Owner
    redesign decision) explicitly SUPERSEDES the prior "HOME/PRE ROLE
    AUDIT" gate this test used to enforce (HOME must never compose a
    tournament stage's own page body): while a current tournament has a
    validated, publication-gate-approved stage, / now literally IS that
    page (see tests/test_neo_top120_validation.py's
    test_home_becomes_the_current_tournament_stage_page_while_one_is_active
    for the fuller HOME-contract coverage). The permanent, player-centric
    K-Ranking x NEO 경기력 table keeps its own stable home at /ranking/,
    completely unaffected by this."""
    spec88 = importlib.util.spec_from_file_location("product_recovery_s88", ROOT / "scripts" / "88_build_neo_top120_candidate.py")
    builder88 = importlib.util.module_from_spec(spec88)
    spec88.loader.exec_module(builder88)
    builder88.build()
    home_html = (builder88.OUTPUT / "index.html").read_text(encoding="utf-8")
    assert "class='player-name'" in home_html
    assert "PRE 참가 선수" in home_html
    assert "data-player-row" not in home_html
    ranking_html = (builder88.OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    assert "data-player-row" in ranking_html


def test_public_pre_summary_omits_internal_validation_metadata():
    """PUBLIC PRE SUMMARY MUST REMAIN PUBLIC-FACING: hashes, tier2 gate
    filenames, internal artifact names, and raw ISO cutoff timestamps
    must never appear in the rendered public copy -- they stay in the
    audit artifact only."""
    html = _kb_pre_html()
    master = json.loads((CONTENT / "2026090003_PRE_PUBLIC_MASTER.json").read_text(encoding="utf-8"))
    assert master["tier2_gate"] not in html
    assert "tier2_gate" not in html
    for artifact_name in master["source_artifacts"]:
        assert artifact_name not in html
    assert master["cutoff"] not in html  # raw ISO cutoff timestamp is internal, not public copy
    assert "validation_state" not in html and "field_provenance" not in html


def test_pre_summary_line_is_concise_and_uses_real_field_count_and_k_ranking_week():
    html = _kb_pre_html()
    assert "참가 120 · K-Ranking 2026-W36 · PRE" in html
