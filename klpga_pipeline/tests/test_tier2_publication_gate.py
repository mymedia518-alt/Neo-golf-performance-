import json
from pathlib import Path
from klpga.neo_win.tier2_publication_gate import detect_survivor_bias, evaluate
from klpga.tournament_context import load_active_tournament_context

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "content" / "website_v2"
CONTEXT = load_active_tournament_context()


def test_legacy_survivor_signature_detected_but_legitimate_equal_early_cumulative_not():
    assert detect_survivor_bias(100, 100, 100) is True
    assert detect_survivor_bias(100, 100, 80) is False


def test_current_gate_passes_all_domains_after_accepted_sg_evidence():
    gate = evaluate(CONTEXT)
    states = {d["domain"]: d["state"] for d in gate["domains"]}
    assert states["IDENTITY"] == "PASS"
    assert states["TEAM_SPONSOR"] == "PASS"
    # K-RANK PROVENANCE (Phase 2, fix/phase5-generic-pipeline-hardening):
    # the real, already-committed OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json
    # was collected before this hardening existed and genuinely carries
    # no returned_rank_week/raw_response_sha256/week_match evidence --
    # under the new fail-closed contract this MUST legitimately BLOCK,
    # not silently keep passing on the old "at least one PASS row"
    # standard alone. This is the correct, intended consequence of the
    # fix, not a regression to route around.
    assert states["K_RANKING"] == "BLOCK"
    assert states["WIN_PROBABILITY"] == "PASS"
    assert states["SG_DERIVED"] == "PASS"


def test_k_ranking_blocks_on_unproven_week_for_the_real_committed_artifact():
    gate = evaluate(CONTEXT)
    rank = next(d for d in gate["domains"] if d["domain"] == "K_RANKING")
    assert rank["state"] == "BLOCK"
    assert "raw_response_sha256" in rank["reason"] or "unproven" in rank["reason"]


def test_accepted_corrected_sg_fixture_passes_sg_domain():
    gate = evaluate(CONTEXT, sg_accepted=True)
    assert {d["domain"]: d["state"] for d in gate["domains"]}["SG_DERIVED"] == "PASS"
