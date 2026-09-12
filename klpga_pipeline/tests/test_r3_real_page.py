"""R3 renderer contract: complete official field, explicit statuses, no fabrication."""
import re
import pytest
from klpga.neo_win.r3_real_page import is_real_page, render_r3_real_page
from klpga.website_v2.round_page_contract import RoundPageContractError

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
    assert f">{status}<" in row and "data-label='합계'>—<" in row and "data-label='3R'>—<" in row

def test_cumulative_total_is_relative_to_par_not_raw_strokes():
    """PUBLIC_ROUND_PAGE_001: 합계 IS shown, but its value is the
    cumulative score relative to par through R3 -- never a raw
    cumulative stroke count, even if a bogus 'total_strokes'-shaped
    field is present on the record (it must be ignored entirely)."""
    html=render([active("p1", r1_score_to_par=0, r2_score_to_par=-1, r3_strokes=68, r3_score_to_par=-4, total_strokes=211)])
    assert "data-label='합계'>-5<" in html
    assert "211" not in html

def test_cumulative_total_empty_for_incomplete_wd_data():
    """A WD player with no real r3 result has no real cumulative total
    through R3 -- 합계 renders EMPTY_MARK, never a fabricated partial
    (e.g. r1+r2 only) or a raw stroke count."""
    html=render([active("p1", status="WD", r1_score_to_par=-3, r2_score_to_par=2, r3_score_to_par=None)])
    row=rows(html)[0]
    assert "data-label='합계'>—<" in row

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
    """Navigation is PRE/R1/R2/R3/FR only -- FINAL is deliberately
    omitted from R3's own nav (not even as a disabled placeholder)."""
    html=render([active()], sponsors={"p1":"OFFICIAL SPONSOR"})
    assert "OFFICIAL SPONSOR" in html and "class='player-sponsor'" in html
    assert 'aria-current="page">R3' in html and 'aria-disabled="true">FR' in html
    assert "FINAL" not in html

def test_real_page_marker_and_no_bottom_copy():
    """Public bottom copy (population count, next-update note,
    simulation/methodology/provenance text) is removed entirely -- the
    public content ends cleanly right after the table."""
    html=render([active()])
    assert is_real_page(html)
    assert "next-update" not in html
    assert not re.search(r"총\s*\d+\s*명", html)

def test_no_internal_operational_copy_in_public_page():
    """VISUAL-ARTIFACT-001 remediation: the public page must never
    expose simulation counts, freeze/provenance/build state, or
    internal audit terminology -- that belongs in evidence/validation
    ledger/internal reports only."""
    html=render([active()])
    for forbidden in ("10,000회", "10000회", "시뮬레이션", "고정된", "미래 데이터",
                      "freeze", "provenance", "build_id", "seed"):
        assert forbidden not in html, f"internal-facing copy leaked into public page: {forbidden!r}"

def test_no_r3_probability_explanation_copy():
    """VISUAL GATE remediation: no visible copy explaining that the
    probabilities are R3-specific/checkpoint-derived -- the public page
    shows the table with no probability/checkpoint explanatory note."""
    html=render([active()])
    assert "종료 후 예측값" not in html
    assert "<p class=\"note\">" not in html

def test_cumulative_score_semantics_hard_stop_is_reachable():
    """The executable contract's semantic check is real, not decorative
    -- confirm it actually raises on a raw-stroke-shaped value."""
    from klpga.website_v2.round_page_contract import assert_cumulative_score_is_relative_to_par
    with pytest.raises(RoundPageContractError, match="ROUND_PAGE_CUMULATIVE_SCORE_SEMANTICS_INVALID"):
        assert_cumulative_score_is_relative_to_par("211")
    assert_cumulative_score_is_relative_to_par("-5")  # must not raise
    assert_cumulative_score_is_relative_to_par("E")  # must not raise
    assert_cumulative_score_is_relative_to_par("—")  # EMPTY_MARK must not raise
