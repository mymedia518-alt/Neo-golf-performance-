"""Stage 5: review report. A human-readable summary of exactly what
stages 1-4 did for one gameCode -- what was collected, what was
skipped/blocked and why, and the validation verdict -- written for a
human (the operator) to read before stage 6 ever pushes anything.
Mirrors this project's established Review Report discipline (see the
automation pipeline's own review-report stage): explicit PASS/FAIL/
SKIP per item, every NOT_COLLECTED fact named, never a bare "done"."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from klpga.neo_reader.sync import SyncResult
from klpga.neo_reader.validate import ValidationReport


def render_review_report(sync_result: SyncResult, validation: ValidationReport) -> str:
    lines = []
    lines.append(f"# NEO Sync Review Report — gameCode {sync_result.game_code}")
    lines.append("")
    lines.append(f"- Season: {sync_result.season}")
    lines.append(f"- Sync stage requested: {sync_result.stage}")
    lines.append(f"- Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Overall sync result: {'SUCCESS' if sync_result.ok else 'FAILED'}")
    lines.append(f"- Overall validation result: {validation.overall}")
    lines.append("")
    lines.append("## Collection stages")
    lines.append("")
    lines.append("| Stage | Status | Detail |")
    lines.append("|---|---|---|")
    for s in sync_result.stages:
        detail = s.error_message if s.error_message else ", ".join(f"{k}={v}" for k, v in s.detail.items())
        lines.append(f"| {s.name} | {s.status.upper()} | {detail} |")
    lines.append("")
    lines.append("## Validation checks")
    lines.append("")
    lines.append("| Check | Status | Detail |")
    lines.append("|---|---|---|")
    for c in validation.checks:
        lines.append(f"| {c.name} | {c.status} | {c.detail} |")
    lines.append("")

    blocked_or_error = [s for s in sync_result.stages if s.status in ("blocked", "error")]
    skipped = [s for s in sync_result.stages if s.status == "skipped"]
    if blocked_or_error:
        lines.append("## Not collected")
        lines.append("")
        for s in blocked_or_error:
            lines.append(f"- **{s.name}**: {s.status.upper()} — {s.error_message}")
        lines.append("")
    if skipped:
        lines.append("## Skipped (already archived from a prior run)")
        lines.append("")
        for s in skipped:
            lines.append(f"- **{s.name}**: {s.error_message}")
        lines.append("")

    lines.append("## Recommendation")
    lines.append("")
    if sync_result.ok and validation.overall == "PASS":
        lines.append(
            "All required stages collected and validated. Safe to publish "
            "(stage 6) and, once reviewed, merge into the production branch "
            "for downstream PRE build."
        )
    else:
        lines.append(
            "Do NOT publish or build PRE from this sync run. Resolve the "
            "FAILED/BLOCKED item(s) above and re-run `neo sync` for this "
            "gameCode first."
        )
    return "\n".join(lines) + "\n"


def write_review_report(reports_root: Path, sync_result: SyncResult, validation: ValidationReport) -> Path:
    game_dir = reports_root / sync_result.game_code
    game_dir.mkdir(parents=True, exist_ok=True)
    report_path = game_dir / "REVIEW_REPORT_V1.md"
    report_path.write_text(render_review_report(sync_result, validation), encoding="utf-8")

    import json
    validation_path = game_dir / "VALIDATION_REPORT_V1.json"
    validation_path.write_text(json.dumps(validation.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    return report_path
