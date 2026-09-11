"""Task L (fix/kb-r2-official-cut-gate-20260911): the rendered-output
gate itself -- synthetic unit tests proving it HARD_STOPs on exactly
the real production failure mode (and its variants), and PASSES a
correctly rendered page.

Uses klpga.neo_win.r2_real_page.render_r2_real_page to build real HTML
from synthetic-but-correctly-shaped freeze records, so these tests
exercise the actual renderer + gate pairing end-to-end (never a
hand-typed HTML string standing in for what the renderer would really
produce) -- except where a test deliberately needs to inject a
divergence the current (fixed) renderer would never itself produce, to
prove the gate independently catches a REGRESSION even if some future
renderer change reintroduces one."""
from __future__ import annotations

import pytest

from klpga.neo_win.r2_real_page import render_r2_real_page
from klpga.neo_win.r2_rendered_output_gate import RenderedOutputGateError, validate_r2_rendered_output

GAME_CODE = "TEST0002"
TOURNAMENT_NAME = "SYNTHETIC GATE TEST OPEN"


def _render(records):
    html = render_r2_real_page(
        tournament_name=TOURNAMENT_NAME, game_code=GAME_CODE, date_range="2026.01.01 — 01.04",
        r2_freeze={"records": records}, forecast={"records": []},
        sg_ingest={"status": "NOT_AVAILABLE", "sg_by_player_id": {}}, sponsor_by_id={},
    )
    return html


def test_correctly_rendered_page_passes():
    records = [
        {"player_id": "p1", "player_name": "리더", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": -2},
        {"player_id": "p2", "player_name": "중위권", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": -1},
        {"player_id": "p3", "player_name": "컷탈락", "status": "CUT", "r1_score_to_par": 3, "r2_score_to_par": 5},
        {"player_id": "p4", "player_name": "기권", "status": "WD", "r1_score_to_par": 1, "r2_score_to_par": None},
    ]
    html = _render(records)
    validate_r2_rendered_output(html, {"records": records})  # must not raise


def test_catches_the_real_production_bug_reproduced_synthetically():
    """Reproduces the EXACT real production defect: a renderer reading
    a nonexistent field so every player's total is None -- simulated
    here by feeding _total_to_par-incompatible records directly into a
    hand-built HTML that mirrors what the OLD (buggy) renderer would
    have produced: every rank tied at T1, TOTAL/2R both empty, but with
    the data-player-id attribute the gate itself requires."""
    records = [
        {"player_id": "p1", "player_name": "리더", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": -2},
        {"player_id": "p2", "player_name": "컷탈락", "status": "CUT", "r1_score_to_par": 3, "r2_score_to_par": 5},
    ]
    broken_html = (
        "<table><tbody>"
        "<tr data-player-id='p1'><td data-label='순위'>T1</td>"
        "<td data-label='합계'>—</td><td data-label='2R'>—</td></tr>"
        "<tr data-player-id='p2'><td data-label='순위'>T1</td>"
        "<td data-label='합계'>—</td><td data-label='2R'>—</td>"
        "<span class='status-badge'>CUT</span></tr>"
        "</tbody></table>"
    )
    with pytest.raises(RenderedOutputGateError, match="TOTAL diverges"):
        validate_r2_rendered_output(broken_html, {"records": records})


def test_catches_fabricated_uniform_rank_even_if_total_2r_happen_to_be_right():
    """A narrower regression than the full field-name bug: TOTAL/2R are
    somehow correct but the rank computation itself is broken and
    fabricates the same rank for every player despite real, differing
    totals -- the population-scale sanity check (5) must catch this
    independently of checks (2)/(3)."""
    records = [
        {"player_id": "p1", "player_name": "리더", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": -2},
        {"player_id": "p2", "player_name": "중위권", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": -1},
        {"player_id": "p3", "player_name": "컷탈락", "status": "CUT", "r1_score_to_par": 3, "r2_score_to_par": 5},
    ]
    broken_html = (
        "<table><tbody>"
        "<tr data-player-id='p1'><td data-label='순위'>T1</td>"
        "<td data-label='합계'>-7</td><td data-label='2R'>-2</td></tr>"
        "<tr data-player-id='p2'><td data-label='순위'>T1</td>"
        "<td data-label='합계'>-1</td><td data-label='2R'>-1</td></tr>"
        "<tr data-player-id='p3'><td data-label='순위'>T1</td>"
        "<td data-label='합계'>+8</td><td data-label='2R'>+5</td>"
        "<span class='status-badge'>CUT</span></tr>"
        "</tbody></table>"
    )
    with pytest.raises(RenderedOutputGateError, match="rank population is invalid"):
        validate_r2_rendered_output(broken_html, {"records": records})


def test_catches_a_cut_player_fabricated_onto_the_leaders_rank():
    records = [
        {"player_id": "p1", "player_name": "리더", "status": "ACTIVE", "r1_score_to_par": -5, "r2_score_to_par": -2},
        {"player_id": "p2", "player_name": "컷탈락", "status": "CUT", "r1_score_to_par": 3, "r2_score_to_par": 5},
    ]
    broken_html = (
        "<table><tbody>"
        "<tr data-player-id='p1'><td data-label='순위'>1</td>"
        "<td data-label='합계'>-7</td><td data-label='2R'>-2</td></tr>"
        "<tr data-player-id='p2'><td data-label='순위'>1</td>"
        "<td data-label='합계'>+8</td><td data-label='2R'>+5</td>"
        "<span class='status-badge'>CUT</span></tr>"
        "</tbody></table>"
    )
    with pytest.raises(RenderedOutputGateError, match="rank population is invalid"):
        validate_r2_rendered_output(broken_html, {"records": records})


def test_catches_incomplete_data_player_given_a_fabricated_rank():
    records = [{"player_id": "p1", "player_name": "기권", "status": "WD", "r1_score_to_par": 1, "r2_score_to_par": None}]
    broken_html = (
        "<table><tbody>"
        "<tr data-player-id='p1'><td data-label='순위'>1</td>"
        "<td data-label='합계'>—</td><td data-label='2R'>—</td>"
        "<span class='status-badge'>WD</span></tr>"
        "</tbody></table>"
    )
    with pytest.raises(RenderedOutputGateError, match="fabricated rank"):
        validate_r2_rendered_output(broken_html, {"records": records})


def test_catches_population_divergence_missing_player():
    records = [
        {"player_id": "p1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0},
        {"player_id": "p2", "player_name": "B", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0},
    ]
    html = _render([records[0]])  # p2 never rendered
    with pytest.raises(RenderedOutputGateError, match="population diverges"):
        validate_r2_rendered_output(html, {"records": records})


def test_catches_status_badge_divergence():
    records = [{"player_id": "p1", "player_name": "A", "status": "WD", "r1_score_to_par": 0, "r2_score_to_par": None}]
    broken_html = (
        "<table><tbody>"
        "<tr data-player-id='p1'><td data-label='순위'>—</td>"
        "<td data-label='합계'>—</td><td data-label='2R'>—</td>"
        "<span class='status-badge'>DQ</span></tr>"
        "</tbody></table>"
    )
    with pytest.raises(RenderedOutputGateError, match="status badge diverges"):
        validate_r2_rendered_output(broken_html, {"records": records})


def test_the_real_regenerated_2026090003_r2_page_passes_the_gate():
    """The actual real artifacts, end-to-end: this is the live proof
    the fix works, not just a synthetic reproduction."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    repo_root = root.parent
    freeze = json.loads((root / "content" / "website_v2" / "2026090003_R2_FROZEN_EVIDENCE.json").read_text(encoding="utf-8"))
    html = (repo_root / "docs" / "tournaments" / "2026" / "2026090003" / "r2" / "index.html").read_text(encoding="utf-8")
    validate_r2_rendered_output(html, freeze)  # must not raise
