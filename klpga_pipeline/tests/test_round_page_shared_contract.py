"""VISUAL-ARTIFACT-001 remediation (research/official-tournament-
warehouse-v1-20260912): regression tests for the shared round-page
presentation contract (klpga.website_v2.round_score_format) and its
executable companion contract PUBLIC_ROUND_PAGE_001 (klpga.website_v2.
round_page_contract), so this same class of defect -- a round page
substituting a raw cumulative stroke count for 합계, using a stale/
prior-round forecast, leaking internal simulation copy, or losing the
relative-to-par presentation -- cannot silently reappear on R1/R2/R3/FR
without a test failing first.

Provenance/source assertions are used wherever possible (does the
rendered value trace back to the real frozen artifact) rather than
hardcoded player probability values -- representative-value checks are
an additional sanity layer only, never the sole proof."""
from __future__ import annotations

import re

import pytest

from klpga.neo_win.r3_real_page import render_r3_real_page
from klpga.neo_win.r3_rendered_output_gate import RenderedOutputGateError, validate_r3_rendered_output
from klpga.website_v2.round_score_format import EMPTY_MARK, format_round_score, format_to_par


# ---------------------------------------------------------------------
# The shared formatter itself.
# ---------------------------------------------------------------------

def test_format_to_par_notation():
    assert format_to_par(0) == "E"
    assert format_to_par(-4) == "-4"
    assert format_to_par(3) == "+3"
    assert format_to_par(None) == EMPTY_MARK


def test_format_round_score_combines_strokes_and_to_par():
    assert format_round_score(68, -4) == "68 (-4)"
    assert format_round_score(72, 0) == "72 (E)"
    assert format_round_score(75, 3) == "75 (+3)"


def test_format_round_score_never_fabricates_a_to_par_it_does_not_have():
    """A round's real official strokes render alone, never paired with
    an invented to-par value."""
    assert format_round_score(68, None) == "68"


def test_format_round_score_empty_when_no_real_strokes():
    """No real official strokes for this round (e.g. a WD player) ->
    EMPTY_MARK, never a fabricated placeholder."""
    assert format_round_score(None, None) == EMPTY_MARK
    assert format_round_score(None, -4) == EMPTY_MARK


# ---------------------------------------------------------------------
# R3's real renderer: never reintroduces a cumulative-total column,
# never loses the relative-to-par presentation, never leaks internal
# copy. (R1/R2 are covered by their own existing test suites; this
# file's job is the SHARED invariant, proven here via R3's real
# renderer and reusable for FR once that renderer exists.)
# ---------------------------------------------------------------------

GAME_CODE = "TEST0003"


def _active(pid="p1", **kw):
    return {"player_id": pid, "player_name": pid, "status": "ACTIVE",
            "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0, **kw}


def _render(records, forecast=None):
    return render_r3_real_page(
        tournament_name="TEST", game_code=GAME_CODE, date_range="2026.01.01",
        r3_freeze={"records": records}, forecast={"records": forecast or []}, sponsor_by_id={},
    )


def test_round_page_displays_cumulative_total_as_relative_to_par_never_raw_strokes():
    """PUBLIC_ROUND_PAGE_001 (klpga.website_v2.round_page_contract):
    R1/R2/R3/FR MAY display 합계 -- and R3's real renderer does -- but
    its VALUE must always be the cumulative score relative to par
    through that round, never a raw cumulative stroke count, even when
    a bogus 'total_strokes'-shaped field is present on the record."""
    html = _render([_active("p1", r1_score_to_par=0, r2_score_to_par=-1, r3_strokes=68, r3_score_to_par=-4, total_strokes=211)])
    header = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL).group(1)
    assert "합계" in header
    assert "data-label='합계'>-5<" in html
    assert "211" not in html


def test_round_page_cumulative_total_semantics_hard_stop_on_raw_strokes():
    """Negative-mutation, end-to-end via the real rendered-output gate:
    VALID 합계 (-5, relative to par) passes; INVALID 합계 (211, a raw
    cumulative stroke count substituted in) must HARD STOP with
    ROUND_PAGE_CUMULATIVE_SCORE_SEMANTICS_INVALID. The contract detects
    semantics, not merely the column's presence/name."""
    records = [_active("p1", r1_score_to_par=0, r2_score_to_par=-1, r3_strokes=68, r3_score_to_par=-4)]
    forecast = {"records": []}
    html = _render(records, forecast["records"])

    # VALID: the real rendered page, as-is, must pass the gate.
    validate_r3_rendered_output(html, {"records": records}, forecast)
    assert "data-label='합계'>-5<" in html

    # INVALID: tamper 합계's own cell to a raw-stroke-shaped value.
    tampered = html.replace("data-label='합계'>-5<", "data-label='합계'>211<", 1)
    with pytest.raises(RenderedOutputGateError, match="ROUND_PAGE_CUMULATIVE_SCORE_SEMANTICS_INVALID"):
        validate_r3_rendered_output(tampered, {"records": records}, forecast)


def test_round_page_score_keeps_relative_to_par_presentation():
    html = _render([_active("p1", r3_strokes=68, r3_score_to_par=-4)])
    assert "data-label='3R'>68 (-4)<" in html


def test_round_page_uses_only_the_forecast_it_was_given_never_a_different_rounds_values():
    """Provenance check: every rendered probability traces back to the
    forecast dict passed in, by player_id -- the renderer has no other
    source of probability data (no stale prior-round forecast could
    leak in even if one existed on disk, since this module never reads
    any file itself -- see its own docstring)."""
    forecast = [{"player_id": "p1", "win_pct": 24.84, "top5_pct": 77.72, "top10_pct": 96.89, "top20_pct": 99.99}]
    html = _render([_active("p1", r3_strokes=68, r3_score_to_par=-4)], forecast)
    assert "24.8%" in html and "77.7%" in html and "96.9%" in html

    other_forecast = [{"player_id": "p1", "win_pct": 53.11, "top5_pct": 99.8, "top10_pct": 100.0, "top20_pct": 100.0}]
    html2 = _render([_active("p1", r3_strokes=68, r3_score_to_par=-4)], other_forecast)
    assert "53.1%" in html2 and "24.8%" not in html2


def test_wd_never_receives_forecast_probabilities_even_if_present_in_the_forecast_dict():
    """A WD player must show EMPTY_MARK on every probability cell no
    matter what the forecast dict contains for that player_id -- the
    renderer filters WD out of the advancing population entirely."""
    forecast = [{"player_id": "wd1", "win_pct": 99.0, "top5_pct": 99.0, "top10_pct": 99.0, "top20_pct": 99.0}]
    html = _render([_active("wd1", status="WD", r3_score_to_par=None)], forecast)
    row = re.search(r"<tr data-player-id='wd1'>((?:(?!</tr>).)*)</tr>", html).group(1)
    assert "99.0%" not in row
    for label in ("Top20", "Top10", "Top5", "우승"):
        assert f"data-label='{label}'>—<" in row


def test_no_internal_simulation_or_provenance_copy_leaks_into_the_public_page():
    html = _render([_active("p1", r3_strokes=68, r3_score_to_par=-4)])
    for forbidden in ("시뮬레이션", "10,000회", "10000회", "고정된", "freeze", "provenance",
                      "build_id", "seed", "code_commit", "n_simulations"):
        assert forbidden not in html, f"internal copy leaked: {forbidden!r}"


def test_fr_and_final_both_disabled_r3_current_no_r4_label():
    html = _render([_active("p1", r3_strokes=68, r3_score_to_par=-4)])
    assert 'aria-current="page">R3' in html
    assert '<span class="stage-nav__disabled" aria-disabled="true">FR</span>' in html
    assert '<span class="stage-nav__disabled" aria-disabled="true">FINAL</span>' in html
    assert ">R4<" not in html and "/r4/" not in html
