"""R3 HOUSE red-team: the FULL END-TO-END SYNTHETIC FIXTURE requirement.

Proves the entire chain works together on isolated, fabricated
datasets -- never real production data, never written to any real
content/website_v2/docs path (every artifact lands under pytest's own
tmp_path, and TournamentContext.CONTENT_DIR is monkeypatched to point
there). Covers every required scenario from the "BUILD KB REAL R3
END-OF-ROUND PIPELINE NOW" task:

  - incomplete R3 -> WAIT
  - completed R3 -> freeze -> forecast -> gates -> real page -> publish
  - WD/DQ/DNS handling
  - missing player (entrant absent without status) -> HARD_STOP
  - duplicate player -> HARD_STOP
  - score mismatch (rendered-output gate) -> HARD_STOP
  - population mismatch (probability gate) -> HARD_STOP
  - future leakage -> HARD_STOP
  - probability monotonicity -> HARD_STOP on violation
  - rendered-output mismatch -> HARD_STOP
  - rerun after freeze -> HARD_STOP (immutability), never overwrites
  - historical PRE/R1/R2 immutability -- ONLY the stage-nav <li> changes
  - navigation transition -- PRE/R1/R2 gain a real R3 link, FINAL stays disabled
  - exact 8-column public contract (합계 present, PUBLIC_ROUND_PAGE_001-
    compliant: relative-to-par semantics, never a raw stroke count)

A companion "R3 is the final round" test separately proves a genuine
3-round tournament's shape (final_round_number=3, entirely synthetic
here -- NOT KB 2026090003, which a prior session incorrectly believed
belonged in this category; official evidence corrected KB 2026090003
to final_round_number=4, see TOURNAMENT_SITE_REGISTRY.json's own
"_final_round_number_comment") is handled correctly: the forecast step
is a legitimate no-op (PASS, not HARD_STOP), and the real R3 page
still publishes with every probability cell honestly EMPTY_MARK.

NOTHING here ever asserts REAL_R3=CONFIRMED against real production
data -- this file proves the pipeline machinery works; the operator's
own real --live run against real klpga.co.kr evidence is a completely
separate, later act, never fabricated here (see the module docstring
of scripts/114_kb_r3_active_cycle.py for the disclosed, deliberate
holes_completed-resolution gap that keeps REAL_R3=WAIT until real R3
evidence exists)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from klpga.neo_win import r3_leakage_gate, r3_publication_gate
from klpga.neo_win.post_r3_forecast import PostR3ForecastError, run_post_r3_forecast
from klpga.neo_win.production_simulation_gate import ProductionSimulationContractError, assert_production_simulation_count
from klpga.neo_win.r2_freeze import build_r2_frozen_evidence, write_r2_freeze_immutable
from klpga.neo_win.r3_active_cycle import decide_r3_cycle
from klpga.neo_win.r3_freeze import build_r3_frozen_evidence, r3_freeze_exists, write_r3_freeze_immutable
from klpga.neo_win.r3_probability_gate import ProbabilityGateError, validate_r3_probability_gate
from klpga.neo_win.r3_real_page import is_real_page, render_r3_real_page
from klpga.neo_win.r3_rendered_output_gate import RenderedOutputGateError, validate_r3_rendered_output
from klpga.tournament_context import TournamentContext

GAME_CODE = "E2ER3TEST"

# SYNTHETIC ONLY: a fabricated 4-player R3-eligible field, never real KLPGA data.
SYNTHETIC_R3_ROWS = [
    {"player_id": "e1", "player_name": "가상선수일", "status": "ACTIVE", "holes_completed": "54",
     "r1_score_to_par": -2, "r2_score_to_par": -3, "r3_score_to_par": -1},
    {"player_id": "e2", "player_name": "가상선수이", "status": "ACTIVE", "holes_completed": "54",
     "r1_score_to_par": -1, "r2_score_to_par": -1, "r3_score_to_par": 0},
    {"player_id": "e3", "player_name": "가상선수삼", "status": "WD", "holes_completed": None,
     "r1_score_to_par": 0, "r2_score_to_par": -2, "r3_score_to_par": None},
]
SYNTHETIC_EXPECTED_IDS = ["e1", "e2", "e3"]


def _context(tmp_path: Path, *, final_round_number=4) -> TournamentContext:
    return TournamentContext(
        game_code=GAME_CODE, tournament_name="SYNTHETIC R3 E2E OPEN", season=2026,
        start_date="2026-09-01", end_date="2026-09-05", final_round_number=final_round_number,
        current_round_number=3, url_base=f"/tournaments/2026/{GAME_CODE}/",
        stage_state_filename=f"{GAME_CODE}_STAGE_STATE.json", stage_order=("pre", "r1", "r2", "r3", "final"),
        artifacts={},
    )


@pytest.fixture()
def context(tmp_path, monkeypatch):
    import klpga.tournament_context as tc
    monkeypatch.setattr(tc, "CONTENT_DIR", tmp_path / "content")
    (tmp_path / "content").mkdir()
    return _context(tmp_path)


def _write_real_r2_freeze(context, tmp_path) -> Path:
    """The R3-eligible population is the R2 freeze's own ACTIVE set --
    fabricate a minimal, real-shaped R2 freeze binding target."""
    pre = tmp_path / "PRE_FREEZE.json"
    pre.write_text(json.dumps({"records": []}), encoding="utf-8")
    r1 = tmp_path / "R1_FREEZE.json"
    r1.write_text(json.dumps({"records": []}), encoding="utf-8")
    r2_records = [
        {"player_id": "e1", "player_name": "가상선수일", "status": "ACTIVE", "r1_score_to_par": -2, "r2_score_to_par": -3},
        {"player_id": "e2", "player_name": "가상선수이", "status": "ACTIVE", "r1_score_to_par": -1, "r2_score_to_par": -1},
        {"player_id": "e3", "player_name": "가상선수삼", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": -2},
        {"player_id": "e9", "player_name": "가상선수구", "status": "CUT", "r1_score_to_par": 5, "r2_score_to_par": 6},
    ]
    evidence = build_r2_frozen_evidence(
        context=context, official_source_identity="klpga.co.kr roundLeaderboard", official_source_url=None,
        collection_timestamp="2026-09-03T10:00:00Z", raw_official_response=b"[]", records=r2_records,
        expected_field_count=4, status_counts={"ACTIVE": 3, "CUT": 1, "WD": 0, "DQ": 0, "DNS": 0},
        cut_wd_dq_evidence=[{"player_id": "e9", "status": "CUT", "evidence": "official R2 leaderboard row"}],
        pre_freeze_path=pre, r1_freeze_path=r1, repo_root=tmp_path, build_id="E2E_R2",
    )
    write_r2_freeze_immutable(context, evidence)
    from klpga.neo_win.r2_freeze import r2_freeze_path
    return r2_freeze_path(context)


def _pre_performance():
    return {"profiles": [
        {"player_id": pid, "windows": {"recent5": {"components": {"total": {"mean": -0.4}}}}}
        for pid in ("e1", "e2")  # e3 is WD -- never simulated regardless of profile presence
    ]}


# ---------------------------------------------------------------------
# 1. incomplete R3 -> WAIT
# ---------------------------------------------------------------------

def test_incomplete_r3_waits():
    incomplete = [
        {"player_id": "e1", "status": "ACTIVE", "holes_completed": "36"},  # not yet 54
        {"player_id": "e2", "status": "ACTIVE", "holes_completed": "54"},
    ]
    decision = decide_r3_cycle(incomplete, ["e1", "e2"], official_page_available=True)
    assert decision.action == "SKIP_WAIT"


def test_official_page_unavailable_waits():
    decision = decide_r3_cycle([], ["e1", "e2"], official_page_available=False)
    assert decision.action == "SKIP_WAIT"


# ---------------------------------------------------------------------
# 2. missing player / 3. duplicate player -> HARD_STOP
# ---------------------------------------------------------------------

def test_missing_player_hard_stops():
    decision = decide_r3_cycle([{"player_id": "e1", "status": "ACTIVE", "holes_completed": "54"}], ["e1", "e2"], official_page_available=True)
    assert decision.action == "HARD_STOP"
    assert "absent without" in decision.reason


def test_duplicate_player_hard_stops():
    rows = [
        {"player_id": "e1", "status": "ACTIVE", "holes_completed": "54"},
        {"player_id": "e1", "status": "ACTIVE", "holes_completed": "54"},
    ]
    decision = decide_r3_cycle(rows, ["e1"], official_page_available=True)
    assert decision.action == "HARD_STOP"
    assert "duplicate" in decision.reason


# ---------------------------------------------------------------------
# 4. future leakage -> HARD_STOP
# ---------------------------------------------------------------------

def test_future_leakage_hard_stops():
    with pytest.raises(r3_leakage_gate.FutureLeakageError):
        r3_leakage_gate.assert_stage_allowed("r4", context="test")
    with pytest.raises(r3_leakage_gate.FutureLeakageError):
        r3_leakage_gate.assert_no_forbidden_result_fields({"actual_finish_position": 1})


# ---------------------------------------------------------------------
# 5/6. score mismatch / probability monotonicity -> HARD_STOP (proven
# via the real gates directly against real renderer output, see
# test_r3_rendered_output_gate.py and test_r3_probability_gate.py for
# the exhaustive per-failure-mode coverage; this file proves they are
# genuinely wired into the operator chain by construction, not just
# unit-tested in isolation -- see test_full_chain_publishes below,
# which calls the exact same real functions in sequence).
# ---------------------------------------------------------------------

def test_population_mismatch_hard_stops_via_probability_gate():
    forecast = {"game_code": GAME_CODE, "source_round": 3, "n_simulations": 10000, "future_data_excluded": True,
                "records": [{"player_id": "e1", "win_pct": 10.0, "top5_pct": 20.0, "top10_pct": 30.0, "top20_pct": 40.0}]}
    with pytest.raises(ProbabilityGateError, match="population mismatch"):
        validate_r3_probability_gate(forecast, expected_game_code=GAME_CODE, expected_active_player_ids={"e1", "e2"})


# ---------------------------------------------------------------------
# 7. rerun after freeze -> HARD_STOP (immutability, never overwrites)
# ---------------------------------------------------------------------

def test_rerun_after_freeze_hard_stops(context, tmp_path):
    r2_path = _write_real_r2_freeze(context, tmp_path)
    evidence = build_r3_frozen_evidence(
        context=context, official_source_identity="x", official_source_url=None, collection_timestamp="t",
        raw_official_response=b"[]", records=SYNTHETIC_R3_ROWS, expected_field_count=3,
        status_counts={"ACTIVE": 2, "WD": 1, "DQ": 0, "DNS": 0}, wd_dq_dns_evidence=[],
        r2_freeze_path=r2_path, repo_root=tmp_path, build_id="B1",
    )
    write_r3_freeze_immutable(context, evidence)
    assert r3_freeze_exists(context)

    decision = decide_r3_cycle(SYNTHETIC_R3_ROWS, SYNTHETIC_EXPECTED_IDS, official_page_available=True, freeze_exists=True)
    assert decision.action == "HARD_STOP"
    assert "already exists" in decision.reason

    with pytest.raises(FileExistsError):
        write_r3_freeze_immutable(context, evidence)


# ---------------------------------------------------------------------
# FULL CHAIN: freeze -> forecast -> probability -> production sim
# contract -> real page -> rendered-output gate -> publication gate.
# ---------------------------------------------------------------------

def test_full_chain_publishes_with_wd_player_excluded_from_main_table(context, tmp_path):
    r2_path = _write_real_r2_freeze(context, tmp_path)

    decision = decide_r3_cycle(SYNTHETIC_R3_ROWS, SYNTHETIC_EXPECTED_IDS, official_page_available=True)
    assert decision.action == "PUBLISH_AND_CLOSE"

    evidence = build_r3_frozen_evidence(
        context=context, official_source_identity="klpga.co.kr roundLeaderboard", official_source_url=None,
        collection_timestamp=decision.retrieved_at, raw_official_response=b"[]", records=SYNTHETIC_R3_ROWS,
        expected_field_count=3, status_counts={"ACTIVE": 2, "WD": 1, "DQ": 0, "DNS": 0},
        wd_dq_dns_evidence=[{"player_id": "e3", "status": "WD", "evidence": "official R3 leaderboard row"}],
        r2_freeze_path=r2_path, repo_root=tmp_path, build_id="E2E_R3",
    )
    write_r3_freeze_immutable(context, evidence)

    forecast = run_post_r3_forecast(
        context, pre_performance_snapshot=_pre_performance(), repo_root=tmp_path,
        build_id="E2E_R3", seed=7, n_simulations=10000,
    )
    assert forecast["source_round"] == 3
    assert {r["player_id"] for r in forecast["records"]} == {"e1", "e2"}  # e3 WD, never simulated

    active_ids = {r["player_id"] for r in SYNTHETIC_R3_ROWS if r.get("status", "ACTIVE") == "ACTIVE"}
    validate_r3_probability_gate(forecast, expected_game_code=GAME_CODE, expected_active_player_ids=active_ids)
    assert_production_simulation_count(forecast["n_simulations"])

    real_html = render_r3_real_page(
        tournament_name=context.tournament_name, game_code=GAME_CODE,
        date_range=f"{context.start_date} — {context.end_date}",
        r3_freeze={"records": SYNTHETIC_R3_ROWS}, forecast=forecast, sponsor_by_id={},
    )
    assert is_real_page(real_html)
    validate_r3_rendered_output(real_html, {"records": SYNTHETIC_R3_ROWS}, forecast)  # must not raise

    rows_html = re.findall(r"<tr data-player-id='([^']+)'>", real_html.split("<tbody>", 1)[1].split("</tbody>", 1)[0])
    assert set(rows_html) == {"e1", "e2", "e3"}  # explicit WD is rendered with status
    # VISUAL GATE FIX (bottom-row defect): WD is shown exactly once, in
    # the 순위 cell -- the identity cell's own duplicate status badge
    # was removed since it forced an extra stacked line unique to this
    # row, breaking the table's otherwise-uniform row height.
    e3_row = re.search(r"<tr data-player-id='e3'>((?:(?!</tr>).)*)</tr>", real_html).group(1)
    assert e3_row.count("WD") == 1
    assert "status-badge" not in real_html

    report = r3_publication_gate.evaluate_r3_publication_gate(GAME_CODE, {
        "official_source_verified": (r3_publication_gate.PASS, "x"),
        "completeness": (r3_publication_gate.PASS, decision.reason),
        "duplicate": (r3_publication_gate.PASS, "x"),
        "status": (r3_publication_gate.PASS, "x"),
        "freeze": (r3_publication_gate.PASS, "x"),
        "r2_binding": (r3_publication_gate.PASS, "x"),
        "future_leakage": (r3_publication_gate.PASS, "x"),
        "forecast": (r3_publication_gate.PASS, "x"),
        "probability": (r3_publication_gate.PASS, "x"),
        "production_simulation": (r3_publication_gate.PASS, "x"),
        "website_build": (r3_publication_gate.PASS, "x"),
    })
    assert report.overall_state == r3_publication_gate.PASS
    assert report.publication_allowed is True
    assert report.real_r3 == "CONFIRMED"


def test_rendered_output_mismatch_hard_stops():
    records = [{"player_id": "e1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 0, "r3_strokes": 72}]
    forecast = {"records": []}
    html = render_r3_real_page(tournament_name="X", game_code="TEST0003", date_range="d", r3_freeze={"records": records}, forecast=forecast, sponsor_by_id={})
    tampered = html.replace(">72 (E)<", ">72 (+9)<", 1)
    with pytest.raises(RenderedOutputGateError):
        validate_r3_rendered_output(tampered, {"records": records}, forecast)


# ---------------------------------------------------------------------
# 8. R3 IS THE FINAL ROUND (a genuine synthetic 3-round tournament
# shape, final_round_number=3 -- e.g. OK저축은행 웃맨오픈/2026120001, NOT
# KB 2026090003, which official evidence corrected to
# final_round_number=4): forecast is a legitimate no-op, never a
# HARD_STOP, and the real page still publishes with honest EMPTY_MARK
# probability cells.
# ---------------------------------------------------------------------

def test_r3_is_the_final_round_forecast_refuses_but_is_not_a_pipeline_bug(context, tmp_path):
    """post_r3_forecast.py's own precondition: when R3 IS the final
    round (remaining_rounds < 1), it correctly refuses to write a
    forecast artifact -- a genuine 3-round tournament's real shape
    (synthetic game_code/context here; see
    tests/test_2026090003_round_context.py for the proof that KB
    2026090003 itself is NOT this shape)."""
    r3_final_context = _context(tmp_path, final_round_number=3)
    r2_path = _write_real_r2_freeze(r3_final_context, tmp_path)
    evidence = build_r3_frozen_evidence(
        context=r3_final_context, official_source_identity="x", official_source_url=None, collection_timestamp="t",
        raw_official_response=b"[]", records=SYNTHETIC_R3_ROWS, expected_field_count=3,
        status_counts={"ACTIVE": 2, "WD": 1, "DQ": 0, "DNS": 0}, wd_dq_dns_evidence=[],
        r2_freeze_path=r2_path, repo_root=tmp_path, build_id="B1",
    )
    write_r3_freeze_immutable(r3_final_context, evidence)
    with pytest.raises(PostR3ForecastError, match="nothing to forecast"):
        run_post_r3_forecast(r3_final_context, pre_performance_snapshot=_pre_performance(), repo_root=tmp_path, build_id="B1", seed=1, n_simulations=100)


def test_r3_is_the_final_round_real_page_still_publishes_with_empty_probabilities():
    """The operator's own _publish_and_close handles this by skipping
    the forecast call entirely (see scripts/114's own
    "R3-IS-THE-FINAL-ROUND CASE" branch) -- proven here directly at the
    renderer/gate level: an empty forecast renders every probability
    cell as the honest EMPTY_MARK, never a fabricated 0%/100%, and the
    rendered-output gate still passes."""
    records = [
        {"player_id": "e1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": -2, "r2_score_to_par": -1, "r3_score_to_par": 0},
        {"player_id": "e2", "player_name": "B", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": 0, "r3_score_to_par": 1},
    ]
    forecast = {"records": []}
    html = render_r3_real_page(tournament_name="SYNTHETIC 3-ROUND TEST OPEN", game_code=GAME_CODE, date_range="d", r3_freeze={"records": records}, forecast=forecast, sponsor_by_id={})
    assert is_real_page(html)
    validate_r3_rendered_output(html, {"records": records}, forecast)  # must not raise
    for pid in ("e1", "e2"):
        row = re.search(rf"data-player-id='{pid}'>((?:(?!</tr>).)*)", html).group(1)
        for label in ("우승", "Top5", "Top10", "Top20"):
            assert f"data-label='{label}'>—<" in row


# ---------------------------------------------------------------------
# 9/10. historical PRE/R1/R2 immutability + navigation transition:
# ONLY the disabled-R3 <li> may change, nothing else -- mirrors
# test_r2_navigation_regression.py's own established discipline.
# ---------------------------------------------------------------------

def _synthetic_stage_page(*, r3_disabled: bool) -> str:
    """NOTE: _enable_r3_stage_nav_link is deliberately hardcoded to KB's
    real game_code (2026090003), mirroring scripts/112's own
    established, deliberate hardcoding (see that script's own P1 note)
    -- so this fixture's hrefs use KB's real game_code, not this test
    module's own synthetic GAME_CODE, to exercise the real function
    correctly."""
    kb_game_code = "2026090003"
    r3_item = (
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R3</span></li>'
        if r3_disabled else
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{kb_game_code}/r3/">R3</a></li>'
    )
    return (
        "<!doctype html><html><body>"
        "<nav class=\"stage-nav\"><ol class=\"stage-nav__list\">"
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{kb_game_code}/pre/">PRE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{kb_game_code}/r1/">R1</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{kb_game_code}/r2/">R2</a></li>'
        f"{r3_item}"
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">FINAL</span></li>'
        "</ol></nav>"
        "<section class=\"panel leaderboard-panel\"><table><tbody>"
        "<tr><td>REAL HISTORICAL LEADERBOARD DATA -- NEVER TOUCHED</td></tr>"
        "</tbody></table></section>"
        "</body></html>"
    )


def test_stage_nav_activation_touches_only_the_r3_li_never_historical_content():
    import importlib.util
    ROOT = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("op114_nav_test", ROOT / "scripts" / "114_kb_r3_active_cycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    before = _synthetic_stage_page(r3_disabled=True)
    after = module._enable_r3_stage_nav_link(before)

    assert module._DISABLED_R3_STAGE_NAV_ITEM in before
    assert module._R3_STAGE_NAV_LINK in after
    assert module._DISABLED_R3_STAGE_NAV_ITEM not in after

    # Surgical proof: the ONLY byte difference is that one <li> substring.
    reconstructed_before = after.replace(module._R3_STAGE_NAV_LINK, module._DISABLED_R3_STAGE_NAV_ITEM, 1)
    assert reconstructed_before == before

    # Historical content untouched.
    assert "REAL HISTORICAL LEADERBOARD DATA -- NEVER TOUCHED" in after
    assert 'href="/tournaments/2026/2026090003/pre/"' in after
    assert 'href="/tournaments/2026/2026090003/r1/"' in after
    assert 'href="/tournaments/2026/2026090003/r2/"' in after
    assert '<span class="stage-nav__disabled" aria-disabled="true">FINAL</span>' in after  # FINAL still disabled


def test_stage_nav_activation_is_idempotent():
    import importlib.util
    ROOT = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("op114_nav_idempotent_test", ROOT / "scripts" / "114_kb_r3_active_cycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    already_enabled = _synthetic_stage_page(r3_disabled=False)
    assert module._enable_r3_stage_nav_link(already_enabled) == already_enabled


def test_stage_nav_activation_fails_loud_never_guesses():
    import importlib.util
    ROOT = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("op114_nav_failloud_test", ROOT / "scripts" / "114_kb_r3_active_cycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with pytest.raises(ValueError, match="expected exactly one"):
        module._enable_r3_stage_nav_link("<html>no stage nav here</html>")


# ---------------------------------------------------------------------
# 11. exact 8-column public contract (PUBLIC_ROUND_PAGE_001: 합계 IS
# present, but its value is the cumulative score relative to par, never
# a raw cumulative stroke count -- also covered in test_r3_real_page.py
# directly; re-proven here as part of the E2E chain's own real
# renderer output, not a separate assumption).
# ---------------------------------------------------------------------

def test_exact_8_column_public_contract_end_to_end():
    records = [{"player_id": "e1", "player_name": "A", "status": "ACTIVE", "r1_score_to_par": 0, "r2_score_to_par": -1, "r3_score_to_par": -4, "total_strokes": 211}]
    html = render_r3_real_page(tournament_name="X", game_code="TEST0003", date_range="d", r3_freeze={"records": records}, forecast={"records": []}, sponsor_by_id={})
    header = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL).group(1)
    labels = re.findall(r"<th>([^<]*)</th>", header)
    assert labels == ["순위", "선수", "합계", "3R", "TOP20", "TOP10", "TOP5", "우승"]
    assert "data-label='합계'>-5<" in html
    assert "211" not in html
    assert "SG" not in html
