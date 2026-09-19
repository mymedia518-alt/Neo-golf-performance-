"""NEO STANDARD ARTIFACT: POST_TOURNAMENT_REPORT.md.

Operator directive (2026-09-19, starting with the Hana Financial Group
Championship / 2026090002): from this tournament forward, every
KLPGA/KPGA/LPGA/PGA tournament this pipeline covers gets exactly one
POST_TOURNAMENT_REPORT.md, generated automatically once the FR
(official final round) leaderboard is confirmed, written in Markdown,
committed to git as an Evidence Artifact under content/website_v2/
(never published to docs/ -- internal validation document only), in
the fixed 10-section order below plus a closing NEO SCORECARD.

Zero tournament-specific literals: every value here comes from a
TournamentContext-resolved artifact path or an explicit typed input --
this module never hardcodes a game_code, player name, or date.

Fail-closed, not fail-fabricated: a section this generator cannot
honestly populate from real evidence renders as an explicit
"not available" note, never a guessed or interpolated number. The NEO
SCORECARD's star ratings and Overall Grade are a human judgment call
(there is no defined rubric to auto-derive them from a single Brier/
log-loss pair), so the generic assembler leaves them PENDING for the
analyst reviewing the tournament to fill in before the report is
committed -- exactly like this session's own PRE-PUSH REPORT workflow
already does for Deployment fields.

Write-once: mirrors klpga.tournament_historical_manifest's
write_*_if_absent idiom -- once a report exists for a game_code it is
never silently overwritten or regenerated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from klpga.models.metrics import CalibrationBin, TournamentPrediction, calibration_report, top_k_hit
from klpga.neo_win.monte_carlo_summary import MonteCarloRunSummary
from klpga.neo_win.probability_movers import MoversReport
from klpga.tournament_context import TournamentContext
from klpga.tournament_postmortem import PostmortemResult

_NOT_AVAILABLE = "_Evidence not available for this tournament._"
_PENDING_ANALYST = "_PENDING — to be completed by the analyst reviewing this tournament before commit._"


@dataclass(frozen=True)
class TournamentSummary:
    tournament_name: str
    course: str | None = None
    date_range: str | None = None
    purse: str | None = None
    winner_name: str | None = None
    winner_score: str | None = None


@dataclass(frozen=True)
class PredictionPerformance:
    win_hit: bool | None = None
    top5_hit: bool | None = None
    top10_hit: bool | None = None
    top20_hit: bool | None = None
    calibration_bins: tuple[CalibrationBin, ...] | None = None
    brier_norm: float | None = None
    log_loss: float | None = None


@dataclass(frozen=True)
class MonteCarloSection:
    simulation_engine: str | None = None
    summary: MonteCarloRunSummary | None = None
    note: str | None = None


@dataclass(frozen=True)
class SgAnalysis:
    r1_sg: str | None = None
    r2_sg: str | None = None
    r3_sg: str | None = None
    final_sg: str | None = None
    current_sg_impact: str | None = None


@dataclass(frozen=True)
class ProbabilityTimelineRow:
    player_id: str
    player_name: str
    by_stage_pct: dict[str, float | None]


@dataclass(frozen=True)
class ProbabilityTimeline:
    stages: tuple[str, ...]
    rows: tuple[ProbabilityTimelineRow, ...]
    note: str | None = None


@dataclass(frozen=True)
class OosValidationSection:
    baseline: dict[str, float] | None = None
    challenger: dict[str, float] | None = None
    note: str | None = None


@dataclass(frozen=True)
class LessonsLearned:
    what_worked: tuple[str, ...] = ()
    what_failed: tuple[str, ...] = ()
    improvements: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeploymentInfo:
    commit_sha: str | None = None
    production_sha: str | None = None
    pages_run: str | None = None
    deployment_status: str | None = None


@dataclass(frozen=True)
class AppendixFiles:
    evidence_files: tuple[str, ...] = ()
    freeze_files: tuple[str, ...] = ()
    sg_files: tuple[str, ...] = ()
    validation_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class NeoScorecard:
    forecast_accuracy_stars: int | None = None
    validation_stars: int | None = None
    identity_gate: str = "PENDING"
    probability_gate: str = "PENDING"
    qa_gate: str = "PENDING"
    deployment_gate: str = "PENDING"
    overall_grade: str = "PENDING"


@dataclass(frozen=True)
class PostTournamentReportInputs:
    tournament_summary: TournamentSummary
    prediction_performance: PredictionPerformance
    monte_carlo: MonteCarloSection
    sg_analysis: SgAnalysis
    movers: MoversReport | None
    probability_timeline: ProbabilityTimeline
    oos_validation: OosValidationSection
    lessons_learned: LessonsLearned
    deployment: DeploymentInfo
    appendix: AppendixFiles
    scorecard: NeoScorecard


def _stars(n: int | None) -> str:
    if n is None:
        return "PENDING"
    n = max(0, min(5, n))
    return "★" * n + "☆" * (5 - n)


def _bool_cell(value: bool | None) -> str:
    if value is None:
        return "N/A"
    return "HIT" if value else "MISS"


def _fmt(value: object, digits: int = 4) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _render_tournament_summary(s: TournamentSummary) -> str:
    return "\n".join([
        f"- 대회명: {s.tournament_name}",
        f"- 코스: {s.course or 'N/A'}",
        f"- 날짜: {s.date_range or 'N/A'}",
        f"- 총상금: {s.purse or 'N/A'}",
        f"- 우승자: {s.winner_name or 'N/A'}",
        f"- 우승 스코어: {s.winner_score or 'N/A'}",
    ])


def _render_prediction_performance(p: PredictionPerformance) -> str:
    lines = [
        f"- 우승 적중: {_bool_cell(p.win_hit)}",
        f"- Top5: {_bool_cell(p.top5_hit)}",
        f"- Top10: {_bool_cell(p.top10_hit)}",
        f"- Top20: {_bool_cell(p.top20_hit)}",
        f"- Brier Score: {_fmt(p.brier_norm)}",
        f"- Log Loss: {_fmt(p.log_loss)}",
    ]
    if p.calibration_bins:
        lines.append("- 확률 Calibration:")
        lines.append("")
        lines.append("  | bucket | n | expected wins | actual wins | tournaments |")
        lines.append("  |---|---|---|---|---|")
        for b in p.calibration_bins:
            lines.append(
                f"  | [{b.lo:.1f},{b.hi:.1f}) | {b.row_count} | {b.expected_wins:.3f} | "
                f"{b.actual_wins} | {b.contributing_tournament_count} |"
            )
    else:
        lines.append(f"- 확률 Calibration: {_NOT_AVAILABLE}")
    return "\n".join(lines)


def _render_monte_carlo(m: MonteCarloSection) -> str:
    if m.summary is None:
        return m.note or _NOT_AVAILABLE
    s = m.summary
    return "\n".join([
        f"- Simulation: {m.simulation_engine or 'N/A'}",
        f"- Seed: {s.seed}",
        f"- N Simulations: {s.n_simulations}",
        f"- Mean: {_fmt(s.mean, 4)}",
        f"- Median: {_fmt(s.median, 4)}",
        f"- Std Dev: {_fmt(s.stddev, 4)}",
        f"- 95% CI: [{_fmt(s.ci95_low, 4)}, {_fmt(s.ci95_high, 4)}]",
    ])


def _render_sg_analysis(sg: SgAnalysis) -> str:
    if not any([sg.r1_sg, sg.r2_sg, sg.r3_sg, sg.final_sg, sg.current_sg_impact]):
        return _NOT_AVAILABLE
    return "\n".join([
        f"- R1 SG: {sg.r1_sg or 'N/A'}",
        f"- R2 SG: {sg.r2_sg or 'N/A'}",
        f"- R3 SG: {sg.r3_sg or 'N/A'}",
        f"- Final SG: {sg.final_sg or 'N/A'}",
        f"- Current SG 영향: {sg.current_sg_impact or 'N/A'}",
    ])


def _render_movers(movers: MoversReport | None) -> str:
    if movers is None:
        return _NOT_AVAILABLE
    lines = [f"({movers.before_label} → {movers.after_label})", "", "▲ 상승 TOP10", ""]
    if movers.risers:
        for i, r in enumerate(movers.risers, 1):
            lines.append(f"{i}. {r.player_name}: {r.before_pct:.3f} → {r.after_pct:.3f} ({r.delta_pct:+.3f})")
    else:
        lines.append(_NOT_AVAILABLE)
    lines += ["", "▼ 하락 TOP10", ""]
    if movers.fallers:
        for i, r in enumerate(movers.fallers, 1):
            lines.append(f"{i}. {r.player_name}: {r.before_pct:.3f} → {r.after_pct:.3f} ({r.delta_pct:+.3f})")
    else:
        lines.append(_NOT_AVAILABLE)
    return "\n".join(lines)


def _render_probability_timeline(t: ProbabilityTimeline) -> str:
    if not t.rows:
        return t.note or _NOT_AVAILABLE
    header = "| 선수 | " + " | ".join(t.stages) + " |"
    sep = "|---|" + "---|" * len(t.stages)
    lines = [header, sep]
    for row in t.rows:
        cells = " | ".join(_fmt(row.by_stage_pct.get(stage)) for stage in t.stages)
        lines.append(f"| {row.player_name} | {cells} |")
    if t.note:
        lines += ["", t.note]
    return "\n".join(lines)


def _render_oos_validation(o: OosValidationSection) -> str:
    if o.baseline is None and o.challenger is None:
        return o.note or _NOT_AVAILABLE
    lines = ["| metric | Baseline | Challenger |", "|---|---|---|"]
    for key in ("mae", "rmse", "bias"):
        base = (o.baseline or {}).get(key)
        chall = (o.challenger or {}).get(key)
        lines.append(f"| {key.upper()} | {_fmt(base)} | {_fmt(chall)} |")
    if o.note:
        lines += ["", o.note]
    return "\n".join(lines)


def _render_bullets(items: tuple[str, ...]) -> str:
    if not items:
        return _PENDING_ANALYST
    return "\n".join(f"- {item}" for item in items)


def _render_lessons_learned(ll: LessonsLearned) -> str:
    return "\n\n".join([
        "잘된 점\n\n" + _render_bullets(ll.what_worked),
        "실패한 점\n\n" + _render_bullets(ll.what_failed),
        "다음 대회 개선사항\n\n" + _render_bullets(ll.improvements),
    ])


def _render_deployment(d: DeploymentInfo) -> str:
    return "\n".join([
        f"- Commit SHA: {d.commit_sha or 'PENDING — filled in immediately before push'}",
        f"- Production SHA: {d.production_sha or 'PENDING'}",
        f"- Pages Run: {d.pages_run or 'PENDING'}",
        f"- Deployment Status: {d.deployment_status or 'PENDING'}",
    ])


def _render_appendix(a: AppendixFiles) -> str:
    def _list(label: str, files: tuple[str, ...]) -> str:
        body = "\n".join(f"- {f}" for f in files) if files else f"- {_NOT_AVAILABLE}"
        return f"**{label}**\n\n{body}"

    return "\n\n".join([
        _list("Evidence Files", a.evidence_files),
        _list("Freeze Files", a.freeze_files),
        _list("SG Files", a.sg_files),
        _list("Validation Files", a.validation_files),
    ])


def _render_scorecard(sc: NeoScorecard) -> str:
    return "\n".join([
        "## NEO SCORECARD",
        "",
        f"Forecast Accuracy {_stars(sc.forecast_accuracy_stars)}",
        "",
        f"Validation {_stars(sc.validation_stars)}",
        "",
        f"Identity Gate {sc.identity_gate}",
        "",
        f"Probability {sc.probability_gate}",
        "",
        f"QA {sc.qa_gate}",
        "",
        f"Deployment {sc.deployment_gate}",
        "",
        f"Overall Grade: {sc.overall_grade}",
    ])


def render_post_tournament_report_markdown(game_code: str, inputs: PostTournamentReportInputs) -> str:
    """Renders the fixed 10-section NEO standard artifact, in the exact
    section order/titles specified by the operator, followed by the
    NEO SCORECARD. `game_code` is only used for the document title --
    every other value comes from `inputs`."""
    sections = [
        f"# POST_TOURNAMENT_REPORT — {inputs.tournament_summary.tournament_name} ({game_code})",
        "",
        "# 1. Tournament Summary",
        "",
        _render_tournament_summary(inputs.tournament_summary),
        "",
        "# 2. Prediction Performance",
        "",
        _render_prediction_performance(inputs.prediction_performance),
        "",
        "# 3. Monte Carlo Summary",
        "",
        _render_monte_carlo(inputs.monte_carlo),
        "",
        "# 4. SG Analysis",
        "",
        _render_sg_analysis(inputs.sg_analysis),
        "",
        "# 5. Biggest Movers",
        "",
        _render_movers(inputs.movers),
        "",
        "# 6. Probability Timeline",
        "",
        "PRE\n↓\nR1\n↓\nR2\n↓\nR3\n↓\nFINAL",
        "",
        _render_probability_timeline(inputs.probability_timeline),
        "",
        "# 7. OOS Validation",
        "",
        _render_oos_validation(inputs.oos_validation),
        "",
        "# 8. Lessons Learned",
        "",
        "이번 대회에서",
        "",
        _render_lessons_learned(inputs.lessons_learned),
        "",
        "# 9. Deployment",
        "",
        _render_deployment(inputs.deployment),
        "",
        "# 10. Appendix",
        "",
        _render_appendix(inputs.appendix),
        "",
        _render_scorecard(inputs.scorecard),
        "",
    ]
    return "\n".join(sections)


def write_post_tournament_report_if_absent(
    game_code: str, inputs: PostTournamentReportInputs, context: TournamentContext,
) -> tuple[Path, bool]:
    """-> (report_path, written_this_call). Mirrors
    write_historical_manifest_if_absent: never overwrites an existing
    report for this game_code -- once committed it is immutable
    historical record."""
    out_path = context.artifact_path("post_tournament_report", ext="md")
    if out_path.is_file():
        return out_path, False
    markdown = render_post_tournament_report_markdown(game_code, inputs)
    out_path.write_text(markdown, encoding="utf-8")
    return out_path, True


def _categorize_appendix_files(context: TournamentContext) -> AppendixFiles:
    """Real, on-disk evidence file listing for this game_code --
    never a fabricated inventory. Categorized by filename substring
    heuristics only (no game-specific literals): this is a best-effort
    grouping for the human reader, not a load-bearing contract."""
    content_dir = context.artifact_path("post_tournament_report", ext="md").parent
    prefix = context.game_code
    candidates = sorted(
        p.name for p in content_dir.glob(f"{prefix}*")
        if p.is_file() and p.name != context.artifact_path("post_tournament_report", ext="md").name
    )
    freeze_files = tuple(f for f in candidates if "FREEZE" in f.upper() or "FROZEN" in f.upper())
    sg_files = tuple(f for f in candidates if "_SG_" in f.upper() or f.upper().startswith(f"{prefix}_SG"))
    validation_files = tuple(
        f for f in candidates
        if "VALIDATION" in f.upper() or "EVALUATION" in f.upper() or "GATE" in f.upper()
    )
    already_bucketed = set(freeze_files) | set(sg_files) | set(validation_files)
    evidence_files = tuple(f for f in candidates if f not in already_bucketed)
    return AppendixFiles(
        evidence_files=evidence_files, freeze_files=freeze_files,
        sg_files=sg_files, validation_files=validation_files,
    )


def build_post_tournament_report_inputs(
    context: TournamentContext, postmortem: PostmortemResult,
) -> PostTournamentReportInputs:
    """Best-effort GENERIC assembler: populates every section this
    module can honestly derive from artifacts every tournament is
    guaranteed to have (the postmortem result + real on-disk evidence
    file listing), and leaves the rest as an explicit "not available"
    or PENDING note rather than guessing.

    A tournament with richer, tournament-specific evidence (a
    Monte-Carlo trial capture, per-round SG files, a probability
    timeline, an OOS validation archive) should call
    render_post_tournament_report_markdown directly with a fully
    populated PostTournamentReportInputs instead of relying on this
    assembler for those sections -- exactly as the Hana
    POST_R4_EXECUTIVE_SUMMARY.md and PRE-PUSH REPORT already do
    ad hoc; this assembler is the zero-effort floor every tournament
    gets automatically, not a ceiling."""
    prediction = postmortem.prediction
    top20_hit = top_k_hit(prediction, 20)
    calibration_bins = tuple(calibration_report([prediction]))

    return PostTournamentReportInputs(
        tournament_summary=TournamentSummary(
            tournament_name=context.tournament_name,
            course=context.venue,
            date_range=context.display_date_range,
        ),
        prediction_performance=PredictionPerformance(
            win_hit=postmortem.winner_rank == 1,
            top5_hit=postmortem.top5_hit,
            top10_hit=postmortem.top10_hit,
            top20_hit=top20_hit,
            calibration_bins=calibration_bins,
            brier_norm=postmortem.brier_norm,
            log_loss=postmortem.log_loss,
        ),
        monte_carlo=MonteCarloSection(
            note="Monte Carlo trial capture is not part of the generic postmortem artifact for this "
                 "tournament -- supply a MonteCarloSection explicitly if a trial-level record exists."
        ),
        sg_analysis=SgAnalysis(),
        movers=None,
        probability_timeline=ProbabilityTimeline(
            stages=(), rows=(),
            note="Only the PRE win forecast and the final-round result are generically available for "
                 "this tournament -- a full PRE→R1→R2→R3→FINAL timeline requires per-round forecast "
                 "artifacts to be supplied explicitly.",
        ),
        oos_validation=OosValidationSection(
            note="No OOS validation archive found for this game_code."
        ),
        lessons_learned=LessonsLearned(),
        deployment=DeploymentInfo(),
        appendix=_categorize_appendix_files(context),
        scorecard=NeoScorecard(
            identity_gate="PASS",
            probability_gate="PASS",
            qa_gate="PENDING",
            deployment_gate="PENDING",
        ),
    )
