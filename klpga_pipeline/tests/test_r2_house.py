"""R2 HOUSE: focused production-path tests for every required scenario
(empty/partial/suspended/complete R2, wrong tournament/round, missing
player, conflicting duplicate, 1st/10th tee, CUT/WD/DQ, missing status
field, stale cache/hash mismatch, PRE hash mismatch, R3/R4/FINAL
leakage, SG/forecast before freeze, probability bounds/monotonicity,
simulation count zero, wrong source_round, website/HOME advance before
the publication gate)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from klpga.neo_win import r2_leakage_gate, r2_publication_gate, r2_sg_gate
from klpga.neo_win.post_r2_forecast import PostR2ForecastError, run_post_r2_forecast
from klpga.neo_win.r2_active_cycle import decide_r2_cycle
from klpga.neo_win.r2_freeze import (
    build_r2_frozen_evidence, load_r2_freeze, r2_freeze_exists, verify_r2_freeze_hash, write_r2_freeze_immutable,
)
from klpga.neo_win.r2_house_contract import expected_r2_field_from_r1_evidence
from klpga.neo_win.r2_probability_gate import ProbabilityGateError, validate_probability_gate
from klpga.neo_win.r2_readiness import assess_r2
from klpga.neo_win.r2_wait_page import is_wait_page, render_r2_wait_page
from klpga.parsers.round_progress import resolve_completed_holes
from klpga.tournament_context import TournamentContext

GAME_CODE = "TEST0001"


def _context(tmp_path: Path, *, final_round_number=3) -> TournamentContext:
    return TournamentContext(
        game_code=GAME_CODE, tournament_name="TEST OPEN", season=2026,
        start_date="2026-09-01", end_date="2026-09-04", final_round_number=final_round_number,
        current_round_number=2, url_base=f"/tournaments/2026/{GAME_CODE}/",
        stage_state_filename=f"{GAME_CODE}_STAGE_STATE.json", stage_order=("pre", "r1", "r2", "r3", "final"),
        artifacts={},
    )


@pytest.fixture()
def context(tmp_path, monkeypatch):
    import klpga.tournament_context as tc
    monkeypatch.setattr(tc, "CONTENT_DIR", tmp_path / "content")
    (tmp_path / "content").mkdir()
    return _context(tmp_path)


def _pre_and_r1_freeze_files(tmp_path: Path) -> tuple[Path, Path]:
    pre = tmp_path / "PRE_FREEZE.json"
    pre.write_text(json.dumps({"schema": "pre"}), encoding="utf-8")
    r1 = tmp_path / "R1_FREEZE.json"
    r1.write_text(json.dumps({"schema": "r1"}), encoding="utf-8")
    return pre, r1


def _freeze_evidence(context, tmp_path, *, records, status_counts, expected=3):
    pre, r1 = _pre_and_r1_freeze_files(tmp_path)
    return build_r2_frozen_evidence(
        context=context, official_source_identity="test", official_source_url=None,
        collection_timestamp="2026-09-03T00:00:00Z", raw_official_response=b"{}",
        records=records, expected_field_count=expected, status_counts=status_counts,
        cut_wd_dq_evidence=[], pre_freeze_path=pre, r1_freeze_path=r1, repo_root=tmp_path, build_id="TEST",
    )


# ---------------------------------------------------------------------
# CASE: empty / partial / suspended / complete R2 (r2_readiness.assess_r2)
# ---------------------------------------------------------------------

def test_empty_r2_waits():
    d = assess_r2([], ["p1", "p2"], official_page_available=False)
    assert d.decision == "WAIT"
    assert "unavailable" in d.reason


def test_partial_r2_waits_on_unresolved_holes():
    rows = [{"player_id": "p1", "status": "ACTIVE", "holes_completed": "12"}]
    d = assess_r2(rows, ["p1"], official_page_available=True, cut_known=True)
    assert d.decision == "WAIT"


def test_suspended_r2_waits():
    d = assess_r2([{"player_id": "p1"}], ["p1"], official_page_available=True, suspended=True)
    assert d.decision == "WAIT"
    assert "suspension" in d.reason


def test_complete_r2_is_r2_complete():
    rows = [
        {"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"},
        {"player_id": "p2", "status": "CUT", "holes_completed": "36"},
    ]
    d = assess_r2(rows, ["p1", "p2"], official_page_available=True, cut_known=True)
    assert d.decision == "R2_COMPLETE"
    assert d.cutmakers == 1
    assert d.cut_players == 1


# ---------------------------------------------------------------------
# CASE: missing player / conflicting duplicate
# ---------------------------------------------------------------------

def test_missing_player_hard_stops():
    rows = [{"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"}]
    d = assess_r2(rows, ["p1", "p2"], official_page_available=True, cut_known=True)
    assert d.decision == "HARD_STOP"
    assert "absent without official" in d.reason


def test_conflicting_duplicate_identity_hard_stops():
    rows = [
        {"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"},
        {"player_id": "p1", "status": "CUT", "holes_completed": "36"},
    ]
    d = assess_r2(rows, ["p1"], official_page_available=True, cut_known=True)
    assert d.decision == "HARD_STOP"
    assert "duplicate" in d.reason


# ---------------------------------------------------------------------
# CASE: 1st tee / 10th tee / round-tee regression (round_progress reuse)
# ---------------------------------------------------------------------

def test_1st_tee_completed_holes_is_raw_inghole():
    result = resolve_completed_holes(7, "1")
    assert result.completed == 7


def test_10th_tee_completed_holes_corrects_for_offset():
    # a 10th-tee starter at course hole 16 has played 7 holes, not 16
    result = resolve_completed_holes(16, "10")
    assert result.completed == 7


# ---------------------------------------------------------------------
# CASE: CUT / WD / DQ / missing status field (evidence-based, never inferred)
# ---------------------------------------------------------------------

def test_cut_wd_dq_status_counts_are_evidence_based():
    rows = [
        {"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"},
        {"player_id": "p2", "status": "CUT", "holes_completed": "36"},
        {"player_id": "p3", "status": "WD", "holes_completed": "36"},
        {"player_id": "p4", "status": "DQ", "holes_completed": "36"},
    ]
    d = assess_r2(rows, ["p1", "p2", "p3", "p4"], official_page_available=True, cut_known=True)
    assert d.decision == "R2_COMPLETE"


def test_missing_status_field_defaults_to_active_never_fabricates_wd():
    """A row with no status field at all is treated as ACTIVE (the
    round's default participation state) -- never silently upgraded to
    WD just because a field is absent. This is the direct test of the
    P0 rule 'missing R2 row != WD'."""
    rows = [{"player_id": "p1", "holes_completed": "36"}]
    d = assess_r2(rows, ["p1"], official_page_available=True, cut_known=True)
    assert d.decision == "R2_COMPLETE"
    assert d.cutmakers == 1  # counted as ACTIVE, not WD


def test_unrecognized_status_hard_stops():
    rows = [{"player_id": "p1", "status": "MADE_UP_STATUS", "holes_completed": "36"}]
    d = assess_r2(rows, ["p1"], official_page_available=True, cut_known=True)
    assert d.decision == "HARD_STOP"
    assert "unrecognized" in d.reason


# ---------------------------------------------------------------------
# CASE: stale cache / freeze already exists / hash mismatch / PRE hash mismatch
# ---------------------------------------------------------------------

def test_stale_cache_never_overwrites_an_existing_freeze():
    d = assess_r2([{"player_id": "p1"}], ["p1"], official_page_available=True, freeze_exists=True)
    assert d.decision == "HARD_STOP"
    assert "already exists" in d.reason


def test_r2_freeze_is_immutable_second_write_raises(context, tmp_path):
    evidence = _freeze_evidence(context, tmp_path, records=[{"player_id": "p1", "status": "ACTIVE"}], status_counts={"ACTIVE": 1})
    write_r2_freeze_immutable(context, evidence)
    assert r2_freeze_exists(context)
    with pytest.raises(FileExistsError):
        write_r2_freeze_immutable(context, evidence)


def test_hash_mismatch_detected_after_tampering(context, tmp_path):
    evidence = _freeze_evidence(context, tmp_path, records=[{"player_id": "p1", "status": "ACTIVE"}], status_counts={"ACTIVE": 1})
    path = write_r2_freeze_immutable(context, evidence)
    assert verify_r2_freeze_hash(context) is True
    # tamper: change a record without updating the recorded hash
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["records"][0]["status"] = "WD"
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert verify_r2_freeze_hash(context) is False


def test_pre_hash_mismatch_source_missing_raises(context, tmp_path):
    _, r1 = _pre_and_r1_freeze_files(tmp_path)
    missing_pre = tmp_path / "DOES_NOT_EXIST.json"
    with pytest.raises(FileNotFoundError):
        build_r2_frozen_evidence(
            context=context, official_source_identity="t", official_source_url=None,
            collection_timestamp="2026-09-03T00:00:00Z", raw_official_response=b"{}",
            records=[], expected_field_count=0, status_counts={}, cut_wd_dq_evidence=[],
            pre_freeze_path=missing_pre, r1_freeze_path=r1, repo_root=tmp_path, build_id="T",
        )


# ---------------------------------------------------------------------
# CASE: R3 / R4 / FINAL leakage
# ---------------------------------------------------------------------

@pytest.mark.parametrize("stage", ["r3", "r4", "final"])
def test_future_stage_leakage_hard_stops(stage):
    with pytest.raises(r2_leakage_gate.FutureLeakageError):
        r2_leakage_gate.assert_stage_allowed(stage)


@pytest.mark.parametrize("artifact_type", ["r3_live_snapshot", "r4_forecast", "final_result_archive"])
def test_future_artifact_type_leakage_hard_stops(artifact_type):
    with pytest.raises(r2_leakage_gate.FutureLeakageError):
        r2_leakage_gate.assert_artifact_type_allowed(artifact_type)


def test_forbidden_result_fields_hard_stop():
    with pytest.raises(r2_leakage_gate.FutureLeakageError):
        r2_leakage_gate.assert_no_forbidden_result_fields({"winner": "someone"})


def test_pre_r1_r2_stages_allowed():
    for stage in ("pre", "r1", "r2"):
        r2_leakage_gate.assert_stage_allowed(stage)  # must not raise


# ---------------------------------------------------------------------
# CASE: SG before freeze / forecast before freeze
# ---------------------------------------------------------------------

def test_sg_before_freeze_hard_stops(context):
    with pytest.raises(r2_sg_gate.SgPreconditionError):
        r2_sg_gate.require_verified_frozen_r2_for_sg(context)


def test_sg_after_verified_freeze_passes(context, tmp_path):
    evidence = _freeze_evidence(context, tmp_path, records=[{"player_id": "p1", "status": "ACTIVE"}], status_counts={"ACTIVE": 1})
    write_r2_freeze_immutable(context, evidence)
    freeze = r2_sg_gate.require_verified_frozen_r2_for_sg(context)
    assert freeze["game_code"] == GAME_CODE


def test_forecast_before_freeze_hard_stops(context):
    with pytest.raises(PostR2ForecastError):
        run_post_r2_forecast(context, pre_performance_snapshot={"profiles": []}, repo_root=Path("."), build_id="T", seed=1)


def test_forecast_zero_simulations_hard_stops(context, tmp_path):
    evidence = _freeze_evidence(
        context, tmp_path,
        records=[{"player_id": "p1", "player_name": "P1", "status": "ACTIVE", "r1_score_to_par": -2, "r2_score_to_par": -1}],
        status_counts={"ACTIVE": 1},
    )
    write_r2_freeze_immutable(context, evidence)
    with pytest.raises(PostR2ForecastError):
        run_post_r2_forecast(
            context, pre_performance_snapshot={"profiles": []}, repo_root=tmp_path, build_id="T", seed=1, n_simulations=0,
        )


def test_forecast_succeeds_and_writes_canonical_artifact_once_freeze_and_profile_exist(context, tmp_path):
    evidence = _freeze_evidence(
        context, tmp_path,
        records=[{"player_id": "p1", "player_name": "P1", "status": "ACTIVE", "r1_score_to_par": -2, "r2_score_to_par": -1}],
        status_counts={"ACTIVE": 1},
    )
    write_r2_freeze_immutable(context, evidence)
    profile = {"profiles": [{"player_id": "p1", "windows": {"recent5": {"components": {"total": {"mean": 0.3}}}}}]}
    payload = run_post_r2_forecast(context, pre_performance_snapshot=profile, repo_root=tmp_path, build_id="T", seed=1, n_simulations=200)
    assert payload["game_code"] == GAME_CODE
    assert payload["source_round"] == 2
    assert payload["remaining_rounds"] == context.final_round_number - 2
    assert payload["n_simulations"] == 200
    assert len(payload["records"]) == 1
    assert context.artifact_path("post_r2_final_forecast").is_file()


# ---------------------------------------------------------------------
# CASE: probability bounds / monotonicity / wrong tournament / wrong
# round / simulation count zero
# ---------------------------------------------------------------------

def _valid_forecast(**overrides) -> dict:
    base = {
        "game_code": GAME_CODE, "source_round": 2, "n_simulations": 100, "future_data_excluded": True,
        "records": [{"player_id": "p1", "win_pct": 10.0, "top5_pct": 20.0, "top10_pct": 30.0, "top20_pct": 40.0}],
    }
    base.update(overrides)
    return base


def test_probability_gate_passes_on_valid_forecast():
    validate_probability_gate(_valid_forecast(), expected_game_code=GAME_CODE, expected_active_player_ids={"p1"})


def test_probability_out_of_bounds_hard_stops():
    forecast = _valid_forecast(records=[{"player_id": "p1", "win_pct": 150.0, "top5_pct": 20, "top10_pct": 30, "top20_pct": 40}])
    with pytest.raises(ProbabilityGateError):
        validate_probability_gate(forecast, expected_game_code=GAME_CODE, expected_active_player_ids={"p1"})


def test_probability_monotonicity_violation_hard_stops():
    forecast = _valid_forecast(records=[{"player_id": "p1", "win_pct": 50.0, "top5_pct": 20.0, "top10_pct": 30.0, "top20_pct": 40.0}])
    with pytest.raises(ProbabilityGateError):
        validate_probability_gate(forecast, expected_game_code=GAME_CODE, expected_active_player_ids={"p1"})


def test_wrong_tournament_hard_stops():
    with pytest.raises(ProbabilityGateError):
        validate_probability_gate(_valid_forecast(game_code="OTHER"), expected_game_code=GAME_CODE, expected_active_player_ids={"p1"})


def test_wrong_source_round_hard_stops():
    with pytest.raises(ProbabilityGateError):
        validate_probability_gate(_valid_forecast(source_round=1), expected_game_code=GAME_CODE, expected_active_player_ids={"p1"})


def test_zero_simulation_count_hard_stops():
    with pytest.raises(ProbabilityGateError):
        validate_probability_gate(_valid_forecast(n_simulations=0), expected_game_code=GAME_CODE, expected_active_player_ids={"p1"})


def test_non_finite_probability_hard_stops():
    forecast = _valid_forecast(records=[{"player_id": "p1", "win_pct": float("nan"), "top5_pct": 20, "top10_pct": 30, "top20_pct": 40}])
    with pytest.raises(ProbabilityGateError):
        validate_probability_gate(forecast, expected_game_code=GAME_CODE, expected_active_player_ids={"p1"})


def test_wrong_population_hard_stops():
    with pytest.raises(ProbabilityGateError):
        validate_probability_gate(_valid_forecast(), expected_game_code=GAME_CODE, expected_active_player_ids={"p1", "p2"})


# ---------------------------------------------------------------------
# CASE: website before publication gate / HOME advance before publication gate
# ---------------------------------------------------------------------

def test_wait_page_always_carries_the_not_ready_marker():
    html = render_r2_wait_page(tournament_name="TEST OPEN", game_code=GAME_CODE)
    assert is_wait_page(html)
    assert "data-player-row" not in html
    assert "win_pct" not in html and "WIN" not in html


def test_publication_gate_reports_not_ready_for_the_empty_house():
    report = r2_publication_gate.empty_house_gate_report(GAME_CODE)
    assert report.publication_allowed is False
    assert report.real_r2 == "WAIT"
    assert report.overall_state != r2_publication_gate.PASS


def test_publication_gate_requires_every_named_gate():
    with pytest.raises(KeyError):
        r2_publication_gate.evaluate_r2_publication_gate(GAME_CODE, {"completeness": (r2_publication_gate.PASS, "x")})


def test_publication_gate_passes_only_when_every_gate_passes():
    gates = {name: (r2_publication_gate.PASS, "ok") for name in r2_publication_gate.GATE_NAMES}
    report = r2_publication_gate.evaluate_r2_publication_gate(GAME_CODE, gates)
    assert report.publication_allowed is True
    gates["sg"] = (r2_publication_gate.WAIT, "not ready")
    report2 = r2_publication_gate.evaluate_r2_publication_gate(GAME_CODE, gates)
    assert report2.publication_allowed is False


def test_home_router_never_advances_to_a_wait_state_r2_page(tmp_path):
    """The direct regression test for the HOME STATE ROUTER addendum:
    a real, on-disk r2/index.html that carries the WAIT marker must
    never be picked as the tournament's latest stage."""
    import importlib.util
    ROOT = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("r2_house_home_router", ROOT / "scripts" / "88_build_neo_top120_candidate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    output = tmp_path / "output"
    url_base = "/tournaments/2026/TEST0001/"
    r1_page = output / "tournaments" / "2026" / "TEST0001" / "r1" / "index.html"
    r1_page.parent.mkdir(parents=True, exist_ok=True)
    r1_page.write_text("<html><body>R1 real content</body></html>", encoding="utf-8")

    r2_page = output / "tournaments" / "2026" / "TEST0001" / "r2" / "index.html"
    r2_page.parent.mkdir(parents=True, exist_ok=True)
    r2_page.write_text(render_r2_wait_page(tournament_name="TEST OPEN", game_code="TEST0001"), encoding="utf-8")

    import klpga.website_v2.tournament_chronology as chron
    facts = chron.TournamentCardFacts(
        game_code="TEST0001", tournament_name="TEST OPEN", date_range_display="", url_base=url_base,
        start_date="2026-09-01", end_date="2026-09-04",
    )
    chronology = {"current": facts, "last": None, "next": None}
    registry = {"TEST0001": {"stage_order": ["pre", "r1", "r2", "r3", "final"]}}

    resolved = module.resolve_chronology_stages(chronology, registry, output)
    assert resolved["current"].url_base == f"{url_base}r1/"
    active = module.resolve_active_stage_page(resolved, output)
    assert active == r1_page


def test_home_router_advances_once_r2_is_a_real_ready_page(tmp_path):
    """The inverse: once the R2 page no longer carries the WAIT marker
    (a real, gate-passed publish), the router correctly advances."""
    import importlib.util
    ROOT = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("r2_house_home_router_ready", ROOT / "scripts" / "88_build_neo_top120_candidate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    output = tmp_path / "output"
    url_base = "/tournaments/2026/TEST0001/"
    for stage in ("pre", "r1", "r2"):
        page = output / "tournaments" / "2026" / "TEST0001" / stage / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(f"<html><body>{stage} real content</body></html>", encoding="utf-8")

    import klpga.website_v2.tournament_chronology as chron
    facts = chron.TournamentCardFacts(
        game_code="TEST0001", tournament_name="TEST OPEN", date_range_display="", url_base=url_base,
        start_date="2026-09-01", end_date="2026-09-04",
    )
    chronology = {"current": facts, "last": None, "next": None}
    registry = {"TEST0001": {"stage_order": ["pre", "r1", "r2", "r3", "final"]}}

    resolved = module.resolve_chronology_stages(chronology, registry, output)
    assert resolved["current"].url_base == f"{url_base}r2/"


# ---------------------------------------------------------------------
# CASE: independent expected population (never expected == observed)
# ---------------------------------------------------------------------

def test_expected_population_derived_from_r1_evidence_not_r2_observation():
    r1_evidence = {"gameCode": GAME_CODE, "players": [{"playerCode": "p1"}, {"playerCode": "p2"}, {"playerCode": "p3"}]}
    expected = expected_r2_field_from_r1_evidence(r1_evidence, source_artifact="x.json", source_sha256="abc")
    assert expected.player_ids == frozenset({"p1", "p2", "p3"})
    # an R2 collection that only observed 2 of the 3 must still fail --
    # this is what "never expected_count = observed_count" protects.
    rows = [{"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"}, {"player_id": "p2", "status": "ACTIVE", "holes_completed": "36"}]
    d = assess_r2(rows, sorted(expected.player_ids), official_page_available=True, cut_known=True)
    assert d.decision == "HARD_STOP"


def test_expected_population_refuses_empty_r1_evidence():
    with pytest.raises(ValueError):
        expected_r2_field_from_r1_evidence({"gameCode": GAME_CODE, "players": []}, source_artifact="x", source_sha256="y")


# ---------------------------------------------------------------------
# CASE: decide_r2_cycle action vocabulary
# ---------------------------------------------------------------------

def test_decide_r2_cycle_skip_wait_when_official_page_unavailable():
    decision = decide_r2_cycle([], ["p1"], official_page_available=False)
    assert decision.action == "SKIP_WAIT"


def test_decide_r2_cycle_hard_stop_on_existing_freeze():
    decision = decide_r2_cycle([{"player_id": "p1"}], ["p1"], official_page_available=True, freeze_exists=True)
    assert decision.action == "HARD_STOP"


def test_decide_r2_cycle_publish_and_close_on_complete():
    rows = [{"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"}]
    decision = decide_r2_cycle(rows, ["p1"], official_page_available=True, cut_known=True)
    assert decision.action == "PUBLISH_AND_CLOSE"
