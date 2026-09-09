"""Independently audit and sign a tournament's frozen PRE SG inputs.

This is an explicit reviewer action, not part of the automatic PRE chain.  It
does not calculate new SG definitions or tune a model.  It reproduces the
existing pre-cutoff recent-five rank and performance-band checks from the
accepted corrected warehouse, then binds the exact tournament artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_context import load_tournament_context  # noqa: E402

WAREHOUSE = CONTENT / "historical_sg_warehouse_corrected_v2.json"
WAREHOUSE_AUDIT = CONTENT / "historical_sg_warehouse_corrected_audit_v2.json"
EVENT_MAPPING = CONTENT / "TOURNAMENT_K_WEEK_MAPPING_V1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _close(a, b) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-12)


def _expected_band(profile: dict, field_median: float | None) -> str:
    recent = profile["windows"]["recent5"]["components"]["total"]
    multi = profile["windows"]["multi_season"]["components"]["total"]
    sample = recent["sample"]
    sd = multi.get("sample_sd")
    se = sd / math.sqrt(sample) if sd is not None and sample else None
    z = (recent["mean"] - field_median) / se if se and field_median is not None else None
    if z is None or sample < 5:
        return "INSUFFICIENT_EVIDENCE"
    if z >= 1.96:
        return "VERY_HIGH"
    if z > 1.0:
        return "HIGH"
    if z >= -1.0:
        return "TYPICAL"
    if z > -1.96:
        return "LOW"
    return "VERY_LOW"


def audit(game_code: str) -> tuple[dict, dict]:
    context = load_tournament_context(game_code)
    entry_path = context.artifact_path("entry_snapshot")
    rank_path = context.artifact_path("pre_sg_total_rank_corrected_v2")
    band_path = context.artifact_path("pre_performance_row_retention_corrected_v2")
    required = (WAREHOUSE, WAREHOUSE_AUDIT, EVENT_MAPPING, entry_path, rank_path, band_path)
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"required SG evidence missing: {missing}")

    warehouse_hash = sha256(WAREHOUSE)
    warehouse = json.loads(WAREHOUSE.read_text(encoding="utf-8"))
    warehouse_audit = json.loads(WAREHOUSE_AUDIT.read_text(encoding="utf-8"))
    if warehouse_audit.get("arithmetic_validation", {}).get("exceptions") != 0:
        raise ValueError("corrected SG warehouse arithmetic exceptions are non-zero")
    if warehouse_audit.get("corrected", {}).get("sha256") != warehouse_hash:
        raise ValueError("accepted corrected SG warehouse hash does not match the bytes under audit")

    mapping = json.loads(EVENT_MAPPING.read_text(encoding="utf-8"))
    event_dates = {str(row["game_code"]): row["start_date"] for row in mapping.get("records", []) if row.get("start_date")}
    cutoff = context.start_date
    eligible_rows = []
    unknown_date_rows = 0
    future_rows = 0
    for row in warehouse.get("records", []):
        if row.get("scope") != "tournament_cumulative" or not row.get("player_id"):
            continue
        code = str(row.get("game_code") or "")
        date = event_dates.get(code)
        if date is None:
            unknown_date_rows += 1
            continue
        if code == context.game_code or date >= cutoff:
            future_rows += 1
            continue
        eligible_rows.append(row)
    if any(event_dates[str(row["game_code"])] >= cutoff for row in eligible_rows):
        raise ValueError("post-cutoff SG row entered the PRE input set")

    entries = json.loads(entry_path.read_text(encoding="utf-8"))["entries"]
    entry_ids = [str(row["player_id"]) for row in entries]
    if len(entry_ids) != len(set(entry_ids)):
        raise ValueError("entry snapshot contains duplicate player ids")

    by_player: dict[str, list[dict]] = {}
    for row in eligible_rows:
        by_player.setdefault(str(row["player_id"]), []).append(row)
    expected = []
    for player_id in entry_ids:
        rows = sorted(by_player.get(player_id, []), key=lambda row: str(row.get("game_code") or ""))
        values = [row.get("total") for row in rows[-5:] if row.get("total") is not None]
        expected.append({
            "player_id": player_id,
            "sg_total_mean": sum(values) / len(values) if values else None,
            "sample_count": len(values),
        })
    ranked = sorted(
        (row for row in expected if row["sg_total_mean"] is not None),
        key=lambda row: (-row["sg_total_mean"], row["player_id"]),
    )
    previous = None
    rank = 0
    for position, row in enumerate(ranked, 1):
        if previous is None or row["sg_total_mean"] != previous:
            rank = position
            previous = row["sg_total_mean"]
        row["sg_total_rank"] = rank
    for row in expected:
        row.setdefault("sg_total_rank", None)

    rank_doc = json.loads(rank_path.read_text(encoding="utf-8"))
    if rank_doc.get("game_code") != context.game_code or rank_doc.get("cutoff") != f"{cutoff}T00:00:00+09:00":
        raise ValueError("SG rank tournament/cutoff mismatch")
    actual_by_id = {str(row["player_id"]): row for row in rank_doc.get("records", [])}
    if set(actual_by_id) != set(entry_ids):
        raise ValueError("SG rank player population differs from official entry snapshot")
    mismatches = []
    for expected_row in expected:
        actual = actual_by_id[expected_row["player_id"]]
        if (
            actual.get("sample_count") != expected_row["sample_count"]
            or actual.get("sg_total_rank") != expected_row["sg_total_rank"]
            or not _close(actual.get("sg_total_mean"), expected_row["sg_total_mean"])
        ):
            mismatches.append(expected_row["player_id"])
    if mismatches:
        raise ValueError(f"SG rank reproduction mismatch: {mismatches[:5]}")

    band_doc = json.loads(band_path.read_text(encoding="utf-8"))
    if (
        band_doc.get("game_code") != context.game_code
        or band_doc.get("cutoff") != f"{cutoff}T00:00:00+09:00"
        or band_doc.get("warehouse_sha256") != warehouse_hash
        or band_doc.get("future_data_excluded") is not True
    ):
        raise ValueError("SG band provenance does not bind the accepted pre-cutoff warehouse")
    profiles = band_doc.get("profiles", [])
    if {str(row["player_id"]) for row in profiles} != set(entry_ids):
        raise ValueError("SG band player population differs from official entry snapshot")
    eligible_values = [
        profile["windows"]["recent5"]["components"]["total"]["mean"]
        for profile in profiles
        if profile["windows"]["recent5"]["components"]["total"]["sample"] >= 5
    ]
    field_median = statistics.median(eligible_values) if eligible_values else None
    if not _close(field_median, band_doc.get("field_median")):
        raise ValueError("SG band field median is not reproducible")
    band_mismatches = [
        str(profile["player_id"])
        for profile in profiles
        if profile.get("neo_performance_band") != _expected_band(profile, field_median)
    ]
    if band_mismatches:
        raise ValueError(f"SG performance band reproduction mismatch: {band_mismatches[:5]}")

    controls = {
        "entry_count": len(entry_ids),
        "eligible_rank_count": len(ranked),
        "insufficient_rank_count": len(entry_ids) - len(ranked),
        "rank_reproduction_mismatches": 0,
        "band_reproduction_mismatches": 0,
        "field_median": field_median,
        "warehouse_arithmetic_exceptions": 0,
        "eligible_pre_cutoff_warehouse_rows": len(eligible_rows),
        "excluded_unknown_date_rows": unknown_date_rows,
        "excluded_target_or_post_cutoff_rows": future_rows,
        "future_data_excluded": True,
    }
    artifacts = {
        "entry_snapshot": {"file": entry_path.name, "sha256": sha256(entry_path)},
        "sg_total_rank": {"file": rank_path.name, "sha256": sha256(rank_path)},
        "performance_bands": {"file": band_path.name, "sha256": sha256(band_path)},
    }
    return controls, artifacts


def accept(game_code: str, accepted_by: str, accepted_at: str | None = None) -> Path:
    if not accepted_by.strip():
        raise ValueError("an independent reviewer identity is required")
    context = load_tournament_context(game_code)
    controls, artifacts = audit(game_code)
    output = context.artifact_path("sg_independent_acceptance")
    payload = {
        "schema_version": "neo_tournament_sg_independent_acceptance_v2",
        "state": "ACCEPTED",
        "game_code": context.game_code,
        "accepted_at": accepted_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "accepted_by": accepted_by.strip(),
        "basis": "independent reproduction of frozen pre-cutoff SG rank and performance-band inputs",
        "warehouse": WAREHOUSE.name,
        "warehouse_sha256": sha256(WAREHOUSE),
        "artifacts": artifacts,
        "controls": controls,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--accepted-by", required=True)
    parser.add_argument("--accepted-at")
    args = parser.parse_args()
    output = accept(args.game_code, args.accepted_by, args.accepted_at)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
