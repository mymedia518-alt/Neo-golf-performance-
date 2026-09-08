"""NEO two-event validation and next-event readiness pipeline.

This script is deliberately model-agnostic. It audits the frozen forecast
artifacts and official result artifacts for the KG Ladies Open and OK Savings
Bank Utman Open before any model tuning is allowed.

It never edits a forecast, never converts a live snapshot into a final result,
and never manufactures a missing result. Missing official results are WAIT;
structural or leakage failures are HARD_STOP.

Examples:
    python scripts/run_two_event_validation_pipeline.py \
      --repo-root . \
      --manifest klpga_pipeline/config/NEO_TWO_EVENT_VALIDATION_MANIFEST_V1.json

    python scripts/run_two_event_validation_pipeline.py \
      --repo-root . \
      --manifest klpga_pipeline/config/NEO_TWO_EVENT_VALIDATION_MANIFEST_V1.json \
      --freeze
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PASS = "PASS"
WAIT = "WAIT"
HARD_STOP = "HARD_STOP"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def find_game_code(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("game_code", "gameCode"):
            if value.get(key) is not None:
                return str(value[key])
        for child in value.values():
            found = find_game_code(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_game_code(child)
            if found:
                return found
    return None


def find_records(value: Any) -> list[dict[str, Any]]:
    """Find a conventional player-record list without guessing values."""
    if isinstance(value, dict):
        for key in ("records", "predictions", "player_table", "players", "entrants", "leaderboard"):
            candidate = value.get(key)
            if isinstance(candidate, list) and all(isinstance(row, dict) for row in candidate):
                return candidate
        for child in value.values():
            found = find_records(child)
            if found:
                return found
    elif isinstance(value, list) and value and all(isinstance(row, dict) for row in value):
        return value
    return []


def player_key(row: dict[str, Any]) -> str | None:
    for key in ("player_id", "player_code", "playerId", "playerCode", "code"):
        if row.get(key) is not None:
            return str(row[key])
    return None


_EXPLICIT_PERCENT_KEYS = {
    "win_pct",
    "top5_pct",
    "top10_pct",
    "top20_pct",
    "win_probability_pct",
    "top5_probability_pct",
    "top10_probability_pct",
    "top20_probability_pct",
}


def probability_percent(value: Any, *, field_name: str | None = None) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    # Explicit *_pct fields are already percentages.  A value below 1.0
    # is still a valid percentage (e.g. 0.298 == 0.298%), so magnitude
    # must never be used to reinterpret these fields as fractions.
    if field_name in _EXPLICIT_PERCENT_KEYS or (field_name and field_name.endswith("_pct")):
        return number
    # Legacy probability fields without a *_pct suffix use fractions when
    # they are in [0, 1], and percentages otherwise.
    return number * 100.0 if 0.0 <= number <= 1.0 else number


def first_probability(row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key in row:
            return probability_percent(row[key], field_name=key)
    return None


def numeric_rank(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None


def row_rank(row: dict[str, Any], *, forecast: bool) -> int | None:
    keys = ("neo_final_rank", "rank", "rank_numeric") if forecast else ("rank_numeric", "rank")
    for key in keys:
        if key in row:
            rank = numeric_rank(row[key])
            if rank is not None:
                return rank
    return None


def score_forecast_against_result(forecast_path: Path, result_path: Path) -> dict[str, Any]:
    """Score a frozen forecast against an official result when both are ready.

    This is intentionally stage-local. PRE is never pooled with a POST_R2
    forecast, and one or two events never pretend to be a calibration sample.
    """
    try:
        forecast_payload = load_json(forecast_path)
        result_payload = load_json(result_path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": WAIT, "reason": f"score input unreadable: {exc}"}

    forecast_rows = find_records(forecast_payload)
    result_rows = find_records(result_payload)
    if not forecast_rows or not result_rows:
        return {"status": WAIT, "reason": "forecast/result record shape is not scoreable"}

    forecast_by_id: dict[str, dict[str, Any]] = {}
    for row in forecast_rows:
        pid = player_key(row)
        if pid:
            forecast_by_id[pid] = row
    result_by_id: dict[str, dict[str, Any]] = {}
    for row in result_rows:
        pid = player_key(row)
        if pid:
            result_by_id[pid] = row

    actual_ranked = [(pid, row_rank(row, forecast=False)) for pid, row in result_by_id.items()]
    actual_ranked = [(pid, rank) for pid, rank in actual_ranked if rank is not None]
    forecast_ranked = [(pid, row_rank(row, forecast=True)) for pid, row in forecast_by_id.items()]
    forecast_ranked = [(pid, rank) for pid, rank in forecast_ranked if rank is not None]
    if not actual_ranked or not forecast_ranked:
        return {"status": WAIT, "reason": "rank fields are not scoreable"}

    actual_ranked.sort(key=lambda item: item[1])
    forecast_ranked.sort(key=lambda item: item[1])
    actual_winner_id = next((pid for pid, rank in actual_ranked if rank == 1), None)
    if actual_winner_id is None:
        return {"status": WAIT, "reason": "official result has no unambiguous rank-1 winner"}

    actual_winner = result_by_id[actual_winner_id]
    predicted_top1_id = forecast_ranked[0][0]
    actual_winner_forecast = forecast_by_id.get(actual_winner_id, {})
    winner_probability_pct = first_probability(
        actual_winner_forecast,
        ("win_pct", "win_probability_pct", "win_probability"),
    )
    if winner_probability_pct is None:
        return {"status": WAIT, "reason": "actual winner has no forecast win probability"}

    probabilities: list[tuple[str, float]] = []
    missing_probability: list[str] = []
    for pid, row in forecast_by_id.items():
        value = first_probability(row, ("win_pct", "win_probability_pct", "win_probability"))
        if value is None:
            missing_probability.append(pid)
        else:
            probabilities.append((pid, value / 100.0))
    if missing_probability:
        return {"status": WAIT, "reason": f"missing win probability for {len(missing_probability)} forecast rows"}

    brier = sum((prob - (1.0 if pid == actual_winner_id else 0.0)) ** 2 for pid, prob in probabilities) / len(probabilities)
    epsilon = 1e-15
    log_loss = -math.log(max(epsilon, min(1.0 - epsilon, winner_probability_pct / 100.0)))
    forecast_top5 = {pid for pid, rank in forecast_ranked if rank <= 5}
    forecast_top10 = {pid for pid, rank in forecast_ranked if rank <= 10}
    actual_top5 = {pid for pid, rank in actual_ranked if rank <= 5}
    actual_top10 = {pid for pid, rank in actual_ranked if rank <= 10}
    matched = set(forecast_by_id) & set(result_by_id)
    rank_errors = [
        abs(row_rank(forecast_by_id[pid], forecast=True) - row_rank(result_by_id[pid], forecast=False))
        for pid in matched
        if row_rank(forecast_by_id[pid], forecast=True) is not None and row_rank(result_by_id[pid], forecast=False) is not None
    ]

    return {
        "status": "EVALUATED",
        "actual_winner_id": actual_winner_id,
        "actual_winner_name": actual_winner.get("player") or actual_winner.get("player_name") or actual_winner.get("player_name_display"),
        "predicted_top1_id": predicted_top1_id,
        "predicted_top1_name": forecast_by_id[predicted_top1_id].get("player_name") or forecast_by_id[predicted_top1_id].get("player_name_display"),
        "winner_hit": predicted_top1_id == actual_winner_id,
        "actual_winner_probability_pct": round(winner_probability_pct, 6),
        "brier_score": round(brier, 8),
        "log_loss": round(log_loss, 8),
        "winner_in_predicted_top5": actual_winner_id in forecast_top5,
        "winner_in_predicted_top10": actual_winner_id in forecast_top10,
        "actual_top5_coverage": round(len(actual_top5 & forecast_top5) / len(actual_top5), 6) if actual_top5 else None,
        "actual_top10_coverage": round(len(actual_top10 & forecast_top10) / len(actual_top10), 6) if actual_top10 else None,
        "matched_player_count": len(matched),
        "forecast_player_count": len(forecast_by_id),
        "result_player_count": len(result_by_id),
        "rank_mae": round(sum(rank_errors) / len(rank_errors), 6) if rank_errors else None,
        "calibration_status": "INSUFFICIENT_SAMPLE: stage-level calibration requires more tournaments",
    }


def audit_forecast(repo_root: Path, event: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    spec = event["forecast"]
    path = repo_root / spec["path"]
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    if not path.is_file():
        return {
            "status": HARD_STOP if spec.get("required", True) else WAIT,
            "path": spec["path"],
            "checks": [{"name": "FORECAST_FILE_EXISTS", "passed": False}],
            "errors": [f"forecast artifact missing: {spec['path']}"],
            "warnings": [],
        }

    checks.append({"name": "FORECAST_FILE_EXISTS", "passed": True})
    try:
        payload = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": HARD_STOP,
            "path": spec["path"],
            "checks": checks + [{"name": "FORECAST_JSON_READABLE", "passed": False}],
            "errors": [f"forecast JSON unreadable: {exc}"],
            "warnings": [],
        }
    checks.append({"name": "FORECAST_JSON_READABLE", "passed": True})

    actual_game_code = find_game_code(payload)
    expected_game_code = str(event["game_code"])
    game_ok = actual_game_code in (None, expected_game_code)
    checks.append({"name": "FORECAST_GAME_CODE_MATCH", "passed": game_ok, "actual": actual_game_code, "expected": expected_game_code})
    if not game_ok:
        errors.append(f"forecast game_code mismatch: expected {expected_game_code}, got {actual_game_code}")

    stage = str(spec["stage"])
    allowed_stages = set(policy["54_hole_forecast_stage_names"])
    stage_ok = int(event["format_holes"]) != 54 or stage in allowed_stages
    checks.append({"name": "STAGE_CONTRACT", "passed": stage_ok, "stage": stage})
    if not stage_ok:
        errors.append(f"invalid 54-hole forecast stage: {stage}; public R3 is a legacy alias only")

    future_flag = payload.get("future_data_excluded") if isinstance(payload, dict) else None
    if future_flag is False:
        checks.append({"name": "FUTURE_DATA_EXCLUDED", "passed": False, "value": False})
        errors.append("forecast explicitly includes future data")
    elif future_flag is True:
        checks.append({"name": "FUTURE_DATA_EXCLUDED", "passed": True, "value": True})
    elif spec.get("legacy_artifact"):
        checks.append({"name": "FUTURE_DATA_EXCLUDED", "passed": False, "value": "not_explicit_in_legacy_artifact"})
        warnings.append("legacy forecast lacks an explicit future_data_excluded field; keep review flag in freeze record")
    else:
        checks.append({"name": "FUTURE_DATA_EXCLUDED", "passed": False, "value": "missing"})
        errors.append("forecast has no explicit future_data_excluded=true field")

    records = find_records(payload)
    records_ok = bool(records)
    checks.append({"name": "FORECAST_RECORDS_PRESENT", "passed": records_ok, "record_count": len(records)})
    if not records_ok:
        errors.append("no player forecast records found")
    else:
        keys = [player_key(row) for row in records]
        duplicate_keys = sorted({key for key in keys if key and keys.count(key) > 1})
        unique_ok = not duplicate_keys and all(keys)
        checks.append({"name": "PLAYER_KEYS_UNIQUE", "passed": unique_ok, "duplicates": duplicate_keys})
        if not unique_ok:
            errors.append(f"player key problem: duplicates={duplicate_keys}, missing={keys.count(None)}")

        bad_probability_rows: list[str] = []
        monotonicity_rows: list[str] = []
        win_values: list[float] = []
        for row in records:
            code = player_key(row) or "<missing>"
            values = {
                "win": first_probability(row, ("win_pct", "win_probability", "win_probability_pct")),
                "top5": first_probability(row, ("top5_pct", "top5_probability", "top5_probability_pct")),
                "top10": first_probability(row, ("top10_pct", "top10_probability", "top10_probability_pct")),
                "top20": first_probability(row, ("top20_pct", "top20_probability", "top20_probability_pct")),
            }
            present = [v for v in values.values() if v is not None]
            if any(v < 0.0 or v > 100.0 for v in present):
                bad_probability_rows.append(code)
            ordered = [values[name] for name in ("win", "top5", "top10", "top20")]
            if all(v is not None for v in ordered) and not (ordered[0] <= ordered[1] <= ordered[2] <= ordered[3]):
                monotonicity_rows.append(code)
            if values["win"] is not None:
                win_values.append(values["win"])
        probability_ok = not bad_probability_rows
        checks.append({"name": "PROBABILITIES_IN_0_100", "passed": probability_ok, "bad_rows": bad_probability_rows})
        if not probability_ok:
            errors.append(f"probability out of range for players: {bad_probability_rows}")
        monotonicity_ok = not monotonicity_rows
        checks.append({"name": "PROBABILITY_MONOTONICITY", "passed": monotonicity_ok, "bad_rows": monotonicity_rows})
        if not monotonicity_ok:
            errors.append(f"WIN <= TOP5 <= TOP10 <= TOP20 violated for: {monotonicity_rows}")
        if win_values:
            win_sum = sum(win_values)
            sum_ok = abs(win_sum - 100.0) <= 0.5
            checks.append({"name": "WIN_PROBABILITY_SUM", "passed": sum_ok, "sum_pct": round(win_sum, 6)})
            if not sum_ok:
                errors.append(f"win probability sum is {win_sum:.6f}%, expected approximately 100%")

    status = HARD_STOP if errors else (WAIT if warnings else PASS)
    return {
        "status": status,
        "path": spec["path"],
        "sha256": sha256_file(path),
        "stage": stage,
        "record_count": len(records),
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


def audit_result(repo_root: Path, event: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    spec = event["result"]
    path = repo_root / spec["path"]
    if not path.is_file():
        return {
            "status": WAIT,
            "path": spec["path"],
            "checks": [{"name": "OFFICIAL_RESULT_FROZEN", "passed": False, "value": "missing"}],
            "errors": [],
            "warnings": ["official final result is not frozen yet; no scoring and no tuning allowed"],
        }
    checks: list[dict[str, Any]] = [{"name": "OFFICIAL_RESULT_FROZEN", "passed": True}]
    errors: list[str] = []
    warnings: list[str] = []
    try:
        payload = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": HARD_STOP,
            "path": spec["path"],
            "checks": [{"name": "RESULT_JSON_READABLE", "passed": False}],
            "errors": [f"official result JSON unreadable: {exc}"],
            "warnings": [],
        }
    checks.append({"name": "RESULT_JSON_READABLE", "passed": True})
    actual_game_code = find_game_code(payload)
    expected_game_code = str(event["game_code"])
    game_ok = actual_game_code in (None, expected_game_code)
    checks.append({"name": "RESULT_GAME_CODE_MATCH", "passed": game_ok, "actual": actual_game_code, "expected": expected_game_code})
    if not game_ok:
        errors.append(f"result game_code mismatch: expected {expected_game_code}, got {actual_game_code}")

    source_audit_path = spec.get("source_audit_path")
    if source_audit_path:
        audit_path = repo_root / source_audit_path
        audit_ok = audit_path.is_file()
        checks.append({"name": "OFFICIAL_SOURCE_AUDIT_PRESENT", "passed": audit_ok, "path": source_audit_path})
        if not audit_ok:
            warnings.append("official source audit manifest is missing; result can be frozen only after it is added")
    else:
        # Some unit fixtures and legacy result adapters do not have a
        # separate source-audit file. The production manifest supplies one;
        # do not turn a deliberately minimal adapter fixture into a false
        # blocker here.
        checks.append({"name": "OFFICIAL_SOURCE_AUDIT_PRESENT", "passed": True, "value": "not_required_by_manifest"})

    records = find_records(payload)
    checks.append({"name": "RESULT_RECORDS_PRESENT", "passed": bool(records), "record_count": len(records)})
    if not records:
        warnings.append("result record shape not recognized; use the event-specific official-result adapter before scoring")

    status = HARD_STOP if errors else (WAIT if warnings else PASS)
    return {
        "status": status,
        "path": spec["path"],
        "sha256": sha256_file(path),
        "record_count": len(records),
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


def audit_event(repo_root: Path, event: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    forecast = audit_forecast(repo_root, event, policy)
    result = audit_result(repo_root, event, policy)
    forecast_path = repo_root / event["forecast"]["path"]
    result_path = repo_root / event["result"]["path"]
    score = score_forecast_against_result(forecast_path, result_path) if forecast_path.is_file() and result_path.is_file() else {
        "status": WAIT,
        "reason": "scoring waits for both frozen forecast and official result artifacts",
    }
    statuses = {forecast["status"], result["status"]}
    status = HARD_STOP if HARD_STOP in statuses else (WAIT if WAIT in statuses else PASS)
    return {
        "game_code": event["game_code"],
        "name": event["name"],
        "status": status,
        "forecast": forecast,
        "result": result,
        "score": score,
        "tuning_allowed_for_event": status == PASS,
    }


def build_report(repo_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    event_reports = [audit_event(repo_root, event, manifest["policy"]) for event in manifest["events"]]
    statuses = {report["status"] for report in event_reports}
    global_status = HARD_STOP if HARD_STOP in statuses else (WAIT if WAIT in statuses else PASS)
    blockers = []
    for report in event_reports:
        if report["status"] != PASS:
            blockers.append({"game_code": report["game_code"], "status": report["status"]})
    evaluated_scores = [event["score"] for event in event_reports if event["score"].get("status") == "EVALUATED"]
    return {
        "schema_version": "neo_two_event_validation_report_v1",
        "generated_at_utc": utc_now(),
        "manifest_id": manifest["manifest_id"],
        "repository_root": str(repo_root),
        "policy": manifest["policy"],
        "events": event_reports,
        "global_status": global_status,
        "postmortem_freeze": "READY" if global_status == PASS else "BLOCKED",
        "model_tuning": "ALLOWED_ONLY_AFTER_FREEZE" if global_status == PASS else "BLOCKED",
        "next_event_mode": "PRODUCTION_CANDIDATE" if global_status == PASS else "SHADOW_ONLY",
        "blockers": blockers,
        "scoring": {
            "evaluated_event_count": len(evaluated_scores),
            "stage_local_only": True,
            "calibration_status": "INSUFFICIENT_SAMPLE: two events are not enough for production calibration; keep PRE and POST_R2_PRE_FINAL separate",
            "events": evaluated_scores,
        },
    }


def write_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "NEO_TWO_EVENT_VALIDATION_REPORT.json"
    md_path = output_dir / "NEO_TWO_EVENT_VALIDATION_REPORT.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# NEO Two-Event Validation Report",
        "",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Global status: **{report['global_status']}**",
        f"- Postmortem freeze: **{report['postmortem_freeze']}**",
        f"- Model tuning: **{report['model_tuning']}**",
        f"- Next event mode: **{report['next_event_mode']}**",
        "",
        "## Event status",
        "",
        "| Event | Status | Forecast | Result | Tuning |",
        "|---|---|---|---|---|",
    ]
    for event in report["events"]:
        lines.append(
            f"| {event['name']} ({event['game_code']}) | {event['status']} | "
            f"{event['forecast']['status']} | {event['result']['status']} | "
            f"{event['tuning_allowed_for_event']} |"
        )
        score = event.get("score", {})
        if score.get("status") == "EVALUATED":
            lines.append(
                f"| ↳ score | EVALUATED | winner hit={score['winner_hit']} | "
                f"Brier={score['brier_score']} / LogLoss={score['log_loss']} | "
                f"Top5 coverage={score['actual_top5_coverage']} |"
            )
    lines += ["", "## Blockers", ""]
    if report["blockers"]:
        lines.extend(f"- `{x['game_code']}`: **{x['status']}**" for x in report["blockers"])
    else:
        lines.append("- none")
    lines += [
        "",
        "## Operating rule",
        "",
        "Do not tune, overwrite, or recalibrate a model until every required official result is frozen and this report is PASS.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def freeze_report(repo_root: Path, manifest: dict[str, Any], report: dict[str, Any], output_dir: Path) -> Path:
    if report["global_status"] != PASS:
        raise RuntimeError(f"freeze blocked: global status is {report['global_status']}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    freeze_dir = output_dir / "frozen" / f"NEO_TWO_EVENT_POSTMORTEM_{stamp}"
    if freeze_dir.exists():
        raise RuntimeError(f"freeze directory already exists: {freeze_dir}")
    evidence_dir = freeze_dir / "evidence"
    evidence_dir.mkdir(parents=True)
    frozen_files: list[dict[str, Any]] = []
    for event in manifest["events"]:
        for role in ("forecast", "result"):
            relative = event[role]["path"]
            source = repo_root / relative
            target = evidence_dir / event["game_code"] / role / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            frozen_files.append({
                "game_code": event["game_code"],
                "role": role,
                "source_path": relative,
                "frozen_path": str(target.relative_to(freeze_dir)).replace("\\", "/"),
                "sha256": sha256_file(target),
            })
    (freeze_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (freeze_dir / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (freeze_dir / "FROZEN_EVIDENCE_INDEX.json").write_text(json.dumps({
        "schema_version": "neo_two_event_frozen_evidence_index_v1",
        "frozen_at_utc": utc_now(),
        "immutable_after_creation": True,
        "files": frozen_files,
        "note": "This bundle is the holdout evidence. Build challenger models from pre-event history only; never fit on these files.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return freeze_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=None, help="Repository root; defaults to two levels above this script.")
    parser.add_argument("--manifest", required=True, help="Path to NEO_TWO_EVENT_VALIDATION_MANIFEST_V1.json")
    parser.add_argument("--output-dir", default=None, help="Output directory for the audit report.")
    parser.add_argument("--freeze", action="store_true", help="Create an immutable postmortem bundle only when all gates pass.")
    args = parser.parse_args(argv)

    script_root = Path(__file__).resolve().parents[2]
    repo_root = Path(args.repo_root).resolve() if args.repo_root else script_root
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = repo_root / manifest_path
    manifest = load_json(manifest_path)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else repo_root / "outputs" / "two_event_validation_v1"

    report = build_report(repo_root, manifest)
    json_path, md_path = write_report(report, output_dir)
    print("=== NEO TWO-EVENT VALIDATION PIPELINE V1 ===")
    print(f"GLOBAL STATUS: {report['global_status']}")
    print(f"POSTMORTEM FREEZE: {report['postmortem_freeze']}")
    print(f"MODEL TUNING: {report['model_tuning']}")
    print(f"NEXT EVENT MODE: {report['next_event_mode']}")
    for event in report["events"]:
        print(f"{event['game_code']} {event['name']}: {event['status']} (forecast={event['forecast']['status']}, result={event['result']['status']})")
    print(f"JSON REPORT: {json_path}")
    print(f"MARKDOWN REPORT: {md_path}")

    if args.freeze:
        if report["global_status"] != PASS:
            print(f"HARD_STOP: freeze refused while status is {report['global_status']}")
            return 2
        freeze_dir = freeze_report(repo_root, manifest, report, output_dir)
        print(f"FROZEN POSTMORTEM: {freeze_dir}")
    return 0 if report["global_status"] in (PASS, WAIT) else 3


if __name__ == "__main__":
    raise SystemExit(main())
