"""NEO STANDARD ARTIFACT (operator instruction, 2026-09-19): every
tournament from Hana (2026090002) forward gets exactly one
POST_TOURNAMENT_REPORT.md, generated once FR/POSTMORTEM is valid, in
the fixed 10-section order + NEO SCORECARD, committed as a git
Evidence Artifact under content/website_v2/ and never published to
docs/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import klpga.tournament_context as tournament_context  # noqa: E402
from klpga.neo_win.post_tournament_report import (  # noqa: E402
    AppendixFiles,
    DeploymentInfo,
    LessonsLearned,
    MonteCarloSection,
    NeoScorecard,
    OosValidationSection,
    PostTournamentReportInputs,
    PredictionPerformance,
    ProbabilityTimeline,
    SgAnalysis,
    TournamentSummary,
    build_post_tournament_report_inputs,
    render_post_tournament_report_markdown,
    write_post_tournament_report_if_absent,
)
from klpga.neo_win.probability_movers import compute_probability_movers  # noqa: E402
from klpga.tournament_context import resolve_context  # noqa: E402
from klpga.tournament_postmortem import PostmortemResult, build_postmortem_result, run_postmortem  # noqa: E402

REQUIRED_SECTION_HEADERS = [
    "# 1. Tournament Summary",
    "# 2. Prediction Performance",
    "# 3. Monte Carlo Summary",
    "# 4. SG Analysis",
    "# 5. Biggest Movers",
    "# 6. Probability Timeline",
    "# 7. OOS Validation",
    "# 8. Lessons Learned",
    "# 9. Deployment",
    "# 10. Appendix",
]

IDENTITY = {
    "game_code": "FIXTUREPTR01",
    "tournament_name": "Fixture Post Tournament Report Open",
    "season": 2027,
    "start_date": "2027-09-01",
    "end_date": "2027-09-04",
    "final_round_number": 4,
    "current_round_number": 4,
}
REGISTRY = {
    "FIXTUREPTR01": {
        "url_base": "/tournaments/2027/fixture-ptr-open/",
        "stage_state_filename": "FIXTURE_PTR_STAGE_STATE.json",
        "stage_order": ["pre", "r1", "r2", "r3", "final"],
    }
}
FIELD = [f"P{i}" for i in range(1, 6)]


def _context():
    return resolve_context(IDENTITY, REGISTRY)


def _write(tmp_path, name, payload):
    (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")


def _write_complete_final_snapshot(tmp_path, winner="P1"):
    _write(tmp_path, "FIXTUREPTR01_R4_LIVE_SNAPSHOT.json", {"player_table": [
        {"player_id": p, "holes_completed": 18, "status": None, "rank_display": ("1" if p == winner else "2")}
        for p in FIELD
    ]})


def _write_pre_forecast(tmp_path):
    _write(tmp_path, "FIXTUREPTR01_PRE_WIN_FORECAST.json", {
        "records": [{"player_id": p, "win_probability": 1 / len(FIELD)} for p in FIELD],
    })


def _minimal_inputs(tournament_name="Fixture Open") -> PostTournamentReportInputs:
    return PostTournamentReportInputs(
        tournament_summary=TournamentSummary(tournament_name=tournament_name),
        prediction_performance=PredictionPerformance(),
        monte_carlo=MonteCarloSection(),
        sg_analysis=SgAnalysis(),
        movers=None,
        probability_timeline=ProbabilityTimeline(stages=(), rows=()),
        oos_validation=OosValidationSection(),
        lessons_learned=LessonsLearned(),
        deployment=DeploymentInfo(),
        appendix=AppendixFiles(),
        scorecard=NeoScorecard(),
    )


def test_render_contains_all_ten_sections_in_order():
    markdown = render_post_tournament_report_markdown("G123", _minimal_inputs())
    positions = [markdown.index(header) for header in REQUIRED_SECTION_HEADERS]
    assert positions == sorted(positions), "sections must appear in the fixed 1-10 order"


def test_render_contains_neo_scorecard_with_stars_and_gates():
    scorecard = NeoScorecard(
        forecast_accuracy_stars=4, validation_stars=5,
        identity_gate="PASS", probability_gate="PASS", qa_gate="PASS", deployment_gate="PASS",
        overall_grade="A",
    )
    inputs = _minimal_inputs()
    inputs = PostTournamentReportInputs(**{**inputs.__dict__, "scorecard": scorecard})
    markdown = render_post_tournament_report_markdown("G123", inputs)
    assert "NEO SCORECARD" in markdown
    assert "Forecast Accuracy ★★★★☆" in markdown
    assert "Validation ★★★★★" in markdown
    assert "Identity Gate PASS" in markdown
    assert "Probability PASS" in markdown
    assert "QA PASS" in markdown
    assert "Deployment PASS" in markdown
    assert "Overall Grade: A" in markdown


def test_render_missing_sections_show_not_available_never_fabricated():
    markdown = render_post_tournament_report_markdown("G123", _minimal_inputs())
    assert "Evidence not available for this tournament" in markdown
    assert markdown.count("N/A") > 0


def test_movers_section_renders_risers_and_fallers():
    movers = compute_probability_movers(
        {"P1": 10.0, "P2": 50.0}, {"P1": 30.0, "P2": 20.0}, {"P1": "Alice", "P2": "Bob"},
        before_label="PRE", after_label="FINAL",
    )
    inputs = _minimal_inputs()
    inputs = PostTournamentReportInputs(**{**inputs.__dict__, "movers": movers})
    markdown = render_post_tournament_report_markdown("G123", inputs)
    assert "▲ 상승 TOP10" in markdown
    assert "▼ 하락 TOP10" in markdown
    assert "Alice" in markdown and "Bob" in markdown


def test_write_post_tournament_report_is_write_once(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    context = _context()
    inputs = _minimal_inputs(tournament_name="First Version")
    path, written = write_post_tournament_report_if_absent("FIXTUREPTR01", inputs, context)
    assert written is True
    assert path.name == "FIXTUREPTR01_POST_TOURNAMENT_REPORT.md"
    first_bytes = path.read_bytes()

    different_inputs = _minimal_inputs(tournament_name="Should Never Be Written")
    path2, written2 = write_post_tournament_report_if_absent("FIXTUREPTR01", different_inputs, context)
    assert written2 is False
    assert path2 == path
    assert path.read_bytes() == first_bytes
    assert b"Should Never Be Written" not in path.read_bytes()


def test_build_inputs_from_real_postmortem_result_populates_prediction_performance(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_complete_final_snapshot(tmp_path)
    _write_pre_forecast(tmp_path)
    context = _context()
    postmortem = run_postmortem(context)

    inputs = build_post_tournament_report_inputs(context, postmortem)
    assert inputs.prediction_performance.win_hit is True
    assert inputs.prediction_performance.top5_hit is True
    assert inputs.prediction_performance.top10_hit is True
    assert inputs.prediction_performance.top20_hit is True
    assert inputs.prediction_performance.calibration_bins is not None
    assert inputs.prediction_performance.brier_norm is not None
    assert inputs.prediction_performance.log_loss is not None
    # Generic assembler cannot honestly derive these without richer,
    # tournament-specific evidence -- must stay explicit, never guessed.
    assert inputs.monte_carlo.summary is None
    assert inputs.movers is None
    assert inputs.scorecard.qa_gate == "PENDING"
    assert inputs.scorecard.deployment_gate == "PENDING"
    assert inputs.scorecard.identity_gate == "PASS"


def test_build_inputs_appendix_lists_real_on_disk_evidence_files(tmp_path, monkeypatch):
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_complete_final_snapshot(tmp_path)
    _write_pre_forecast(tmp_path)
    _write(tmp_path, "FIXTUREPTR01_R3_FROZEN_EVIDENCE.json", {})
    _write(tmp_path, "FIXTUREPTR01_R1_SG_V1.json", {})
    _write(tmp_path, "FIXTUREPTR01_VALIDATION_REPORT_V1.json", {})
    context = _context()
    postmortem = run_postmortem(context)

    inputs = build_post_tournament_report_inputs(context, postmortem)
    all_appendix_files = (
        inputs.appendix.evidence_files + inputs.appendix.freeze_files
        + inputs.appendix.sg_files + inputs.appendix.validation_files
    )
    assert "FIXTUREPTR01_R3_FROZEN_EVIDENCE.json" in inputs.appendix.freeze_files
    assert "FIXTUREPTR01_R1_SG_V1.json" in inputs.appendix.sg_files
    assert "FIXTUREPTR01_VALIDATION_REPORT_V1.json" in inputs.appendix.validation_files
    assert "FIXTUREPTR01_POSTMORTEM_REPORT.json" in inputs.appendix.evidence_files
    assert "FIXTUREPTR01_POST_TOURNAMENT_REPORT.md" not in all_appendix_files


def test_never_recomputes_the_persisted_postmortem_artifact(tmp_path, monkeypatch):
    """build_postmortem_result (used when the report generator needs a
    fresh in-memory result on an already-valid cycle) must never touch
    the persisted postmortem_report file on disk."""
    monkeypatch.setattr(tournament_context, "CONTENT_DIR", tmp_path)
    _write_complete_final_snapshot(tmp_path)
    _write_pre_forecast(tmp_path)
    context = _context()
    run_postmortem(context)
    report_path = context.artifact_path("postmortem_report")
    before = report_path.read_bytes()

    result = build_postmortem_result(context)
    assert isinstance(result, PostmortemResult)
    assert report_path.read_bytes() == before


def test_post_tournament_report_never_appears_under_docs():
    """Operator rule 5: internal validation document only -- never
    published to the public site. Scans the REAL repo docs/ tree (not
    a fixture) for any leaked POST_TOURNAMENT_REPORT artifact."""
    repo_root = Path(__file__).resolve().parents[2]
    docs_dir = repo_root / "docs"
    if not docs_dir.is_dir():
        return
    leaked = list(docs_dir.rglob("*POST_TOURNAMENT_REPORT*"))
    assert leaked == [], f"POST_TOURNAMENT_REPORT must never be published to docs/: {leaked}"
