import json
from pathlib import Path
from klpga.neo_win.tier2_publication_gate import detect_survivor_bias, evaluate

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "content" / "website_v2"


def test_legacy_survivor_signature_detected_but_legitimate_equal_early_cumulative_not():
    assert detect_survivor_bias(100, 100, 100) is True
    assert detect_survivor_bias(100, 100, 80) is False


def test_current_gate_passes_all_domains_after_accepted_sg_evidence():
    gate = evaluate(BASE)
    states = {d["domain"]: d["state"] for d in gate["domains"]}
    assert states["IDENTITY"] == "PASS"
    assert states["TEAM_SPONSOR"] == "PASS"
    assert states["K_RANKING"] == "PASS"
    assert states["WIN_PROBABILITY"] == "PASS"
    assert states["SG_DERIVED"] == "PASS"


def test_accepted_corrected_sg_fixture_passes_sg_domain():
    gate = evaluate(BASE, sg_accepted=True)
    assert {d["domain"]: d["state"] for d in gate["domains"]}["SG_DERIVED"] == "PASS"
