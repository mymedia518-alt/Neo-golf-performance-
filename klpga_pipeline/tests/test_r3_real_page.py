"""R3 renderer contract: complete official field, explicit statuses, no fabrication."""
import re
import pytest
from klpga.neo_win.r3_real_page import is_real_page, render_r3_real_page

def render(records, forecast=None, sponsors=None):
    return render_r3_real_page(tournament_name="TEST R3", game_code="TEST0003", date_range="2026.01.01", r3_freeze={"records": records}, forecast={"records": forecast or []}, sponsor_by_id=sponsors or {})

def rows(html):
    return re.findall(r"<tr data-player-id='[^']+'>(?:(?!</tr>).)*</tr>", html)

def active(pid="p1", **kw):
    return {"player_id": pid, "player_name": pid, "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0, **kw}

def test_full_freeze_population_includes_explicit_wd():
    html=render([active(), active("p2", status="WD", r3_score_to_par=None)])
    assert len(rows(html)) == 2 and ">WD<" in html and "INCOMPLETE" not in html

@pytest.mark.parametrize("status", ["WD", "DQ", "DNS"])
def test_non_active_status_has_no_finishing_rank_or_score(status):
    html=render([active("p1", status=status, r3_score_to_par=None)])
    row=rows(html)[0]
    assert f">{status}<" in row and "data-label='3R'>—<" in row

def test_no_cumulative_total_column():
    """ROUND-PAGE SHARED CONTRACT (VISUAL-ARTIFACT-001 remediation):
    R3's public table never shows a cumulative tournament stroke total
    -- that belongs on FINAL only."""
    html=render([active("p1", r3_strokes=68, r3_score_to_par=-4, total_strokes=211)])
    assert "data-label='합계'" not in html
    assert "211" not in html

def test_official_stroke_fields_render_without_under_par_inference():
    html=render([active("p1", r3_score_to_par=None, r3_strokes=68, total_strokes=211)])
    assert "data-label='3R'>68<" in html

def test_3r_score_combines_official_strokes_with_relative_to_par():
    """ROUND-PAGE SHARED CONTRACT: 3R must show the round's real
    official strokes together with its score relative to par, reusing
    the shared klpga.website_v2.round_score_format notation -- never a
    new, R3-only formatter."""
    html=render([active("p1", r3_strokes=68, r3_score_to_par=-4)])
    assert "data-label='3R'>68 (-4)<" in html

def test_probability_formatter_contract():
    html=render([active()], [{"player_id":"p1","win_pct":0,"top5_pct":0.05,"top10_pct":12.5,"top20_pct":100}])
    assert "data-label='우승'>0%<" in html and "data-label='Top5'>&lt;0.1%<" in html and "12.5%" in html

def test_sponsor_slot_and_navigation_contract():
    html=render([active()], sponsors={"p1":"OFFICIAL SPONSOR"})
    assert "OFFICIAL SPONSOR" in html and "class='player-sponsor'" in html
    assert 'aria-current="page">R3' in html and 'aria-disabled="true">FR' in html and 'aria-disabled="true">FINAL' in html

def test_next_update_copy_and_real_page_marker():
    """ROUND-CONTEXT CORRECTION: next-update copy now points at FR (the
    actual next stage in PRE/R1/R2/R3/FR/FINAL), not FINAL directly."""
    html=render([active()])
    assert "FR 종료 후 업데이트" in html and is_real_page(html)

def test_no_internal_operational_copy_in_public_page():
    """VISUAL-ARTIFACT-001 remediation: the public page must never
    expose simulation counts, freeze/provenance/build state, or
    internal audit terminology -- that belongs in evidence/validation
    ledger/internal reports only."""
    html=render([active()])
    for forbidden in ("10,000회", "10000회", "시뮬레이션", "고정된", "미래 데이터",
                      "freeze", "provenance", "build_id", "seed"):
        assert forbidden not in html, f"internal-facing copy leaked into public page: {forbidden!r}"
