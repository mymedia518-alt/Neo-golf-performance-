"""READ-ONLY R2<->R3 recovery/compare tool — for the confirmed real
incident: `scripts/run_beta001_r2_update.py`'s real-mode pipeline never
freezes STAGE_R2 into `neo_tournament_history/` (that pipeline's own
docstring scopes STAGE_R2-freezing OUT entirely; only
`scripts/44_predict_neo_win_post_r2.py --freeze` does that). When R2
production only ever ran via the orchestrator, no STAGE_R2 record
exists, so `scripts/run_beta001_r3_update.py`'s R2->R3 delta column
reads "unavailable" for every player — not a bug in that lookup (see
the investigation this script's docstring documents), just a missing
upstream artifact.

======================================================================
WHY THIS SCRIPT NEVER WRITES A STAGE_R2 HISTORY RECORD
======================================================================
`klpga.neo_win.tournament_history.HistoryStageSnapshot` / `HistoryEntrant`
have NO generic metadata field (confirmed by reading both dataclasses in
full) — there is nowhere to record `source_type="recovered_from_frozen_
r2_forecast"` / `source_path` / `recovered_after_stage` / `recalculated`
without either overloading an existing field's meaning (e.g. stuffing a
provenance string into `source_model_version`, which every other reader
of tournament_history expects to be a real model id) or changing that
module's schema. Neither is acceptable here: this module is shared,
already-tested, append-only infrastructure other frozen stages depend
on, and its schema is deliberately NOT modified by this script.

Rather than force a recovered CSV into a schema that has no honest place
to record how it got there, this script instead does the ONE thing that
is actually needed -- compare a real, already-computed R2 forecast
against the real, already-frozen R3 stage -- entirely OUTSIDE
tournament_history, by joining the two source files directly on
player_code. Nothing existing is touched:
  - the recovered R2 CSV (`--r2-csv`) is opened read-only, never modified.
  - the frozen STAGE_R3 record is read via `read_effective_history_stage`
    (read-only), never re-written, re-frozen, or superseded.
  - every output of this script lives under a NEW directory
    (`--output-dir`, never neo_tournament_history/, never the real
    BETA_R3_FULL.csv path) -- a comparison report CSV plus a provenance
    JSON that explicitly documents source_type/source_path/source_sha256/
    recovered_after_stage/recalculated=false, i.e. exactly the audit
    trail the schema itself has no field for.

If a real STAGE_R2 history record is ever wanted later (e.g. so
`run_beta001_r3_update.py`'s own BETA_R3_FULL.csv shows real r2_win_pct
values instead of "unavailable"), that is a SEPARATE, larger decision
requiring its own explicit sign-off -- this script deliberately does not
attempt it, and prints `R2.JSON REQUIRED: NO` when a plain comparison is
all that was asked for.

Usage (read-only; produces new files only under --output-dir):
    python scripts/recover_r2_frozen_forecast_and_compare_r3.py \\
        --r2-csv outputs/r2_frozen_forecast/2026080001/BETA001_R2_FORECAST_2026080001.csv \\
        --game-code 2026080001 --history-dir neo_tournament_history \\
        --output-dir outputs/r2_r3_recovery_compare
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.tournament_history import STAGE_R3, read_effective_history_stage  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY_DIR = ROOT / "neo_tournament_history"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "r2_r3_recovery_compare"

_R2_CSV_FIELDNAMES = (
    "player_code", "player_name", "r2_rank", "r2_total_score",
    "top20_pct", "top10_pct", "top5_pct", "win_pct",
)

_PCT_FIELDS = ("win_pct", "top5_pct", "top10_pct", "top20_pct")

_COMPARISON_CSV_FIELDNAMES = (
    "player_code", "player_name", "match_status",
    "r2_rank", "r2_total_score",
    "r2_win_pct", "r2_top5_pct", "r2_top10_pct", "r2_top20_pct",
    "r3_win_pct", "r3_top5_pct", "r3_top10_pct", "r3_top20_pct",
    "r2_to_r3_win_change_pct",
)

MATCH_BOTH = "BOTH"
MATCH_R2_ONLY = "R2_ONLY"
MATCH_R3_ONLY = "R3_ONLY"


class R2Row(NamedTuple):
    player_code: str
    player_name: str
    r2_rank: Optional[int]
    r2_total_score: Optional[float]
    win_pct: Optional[float]
    top5_pct: Optional[float]
    top10_pct: Optional[float]
    top20_pct: Optional[float]


def _parse_optional_float(raw: str) -> Optional[float]:
    raw = (raw or "").strip()
    return None if raw == "" else float(raw)


def _parse_optional_int(raw: str) -> Optional[int]:
    raw = (raw or "").strip()
    return None if raw == "" else int(raw)


def read_r2_csv(path: Path) -> tuple[list[R2Row], list[str]]:
    """Read-only. Returns (rows, header_problems) -- header_problems is
    non-empty if the file's columns don't match the confirmed real
    schema (never silently coerced/renamed)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header_problems = []
        if reader.fieldnames is None or set(reader.fieldnames) != set(_R2_CSV_FIELDNAMES):
            header_problems.append(
                f"expected columns {_R2_CSV_FIELDNAMES}, found {tuple(reader.fieldnames or ())}"
            )
            return [], header_problems
        rows = [
            R2Row(
                player_code=row["player_code"], player_name=row["player_name"],
                r2_rank=_parse_optional_int(row["r2_rank"]), r2_total_score=_parse_optional_float(row["r2_total_score"]),
                win_pct=_parse_optional_float(row["win_pct"]), top5_pct=_parse_optional_float(row["top5_pct"]),
                top10_pct=_parse_optional_float(row["top10_pct"]), top20_pct=_parse_optional_float(row["top20_pct"]),
            )
            for row in reader
        ]
    return rows, header_problems


def sha256_of_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_player_code_uniqueness(rows: list[R2Row]) -> list[str]:
    seen: dict[str, int] = {}
    for r in rows:
        seen[r.player_code] = seen.get(r.player_code, 0) + 1
    return sorted(code for code, n in seen.items() if n > 1)


def check_probability_invariants(rows: list[R2Row], *, label: str) -> list[str]:
    """0 <= WIN <= TOP5 <= TOP10 <= TOP20 <= 100 for every row with real
    values -- reports violations, never silently clamps/corrects them."""
    violations = []
    for r in rows:
        values = (r.win_pct, r.top5_pct, r.top10_pct, r.top20_pct)
        if any(v is None for v in values):
            continue
        win, top5, top10, top20 = values
        if not (0.0 <= win <= top5 <= top10 <= top20 <= 100.0):
            violations.append(
                f"{label} {r.player_code}: win={win} top5={top5} top10={top10} top20={top20} "
                "violates 0<=WIN<=TOP5<=TOP10<=TOP20<=100"
            )
    return violations


def check_r2_rank_score_monotonic(rows: list[R2Row]) -> list[str]:
    """A convention-agnostic sanity check: whether r2_total_score is
    "raw total strokes" (lower = better) or "score to par" (more
    negative = better), a BETTER rank must always carry a numerically
    LOWER (or equal, for ties) r2_total_score under either convention.
    Reports out-of-order pairs, never guesses which convention it is."""
    ranked = sorted((r for r in rows if r.r2_rank is not None and r.r2_total_score is not None), key=lambda r: r.r2_rank)
    problems = []
    for prev, cur in zip(ranked, ranked[1:]):
        if cur.r2_total_score < prev.r2_total_score:
            problems.append(
                f"rank {prev.r2_rank} ({prev.player_code}, score={prev.r2_total_score}) is better-ranked than "
                f"rank {cur.r2_rank} ({cur.player_code}, score={cur.r2_total_score}) but has a HIGHER score value"
            )
    return problems


def build_comparison(r2_rows: list[R2Row], r3_entrants) -> list[dict]:
    """Pure function -- no I/O. Joins by player_code; a code present on
    only one side still appears, with the other side's fields None
    (never dropped, never fabricated)."""
    r2_by_code = {r.player_code: r for r in r2_rows}
    r3_by_code = {e.player_code: e for e in r3_entrants}
    all_codes = sorted(set(r2_by_code) | set(r3_by_code))

    out = []
    for code in all_codes:
        r2 = r2_by_code.get(code)
        r3 = r3_by_code.get(code)
        if r2 is not None and r3 is not None:
            status = MATCH_BOTH
        elif r2 is not None:
            status = MATCH_R2_ONLY
        else:
            status = MATCH_R3_ONLY
        r2_win = r2.win_pct if r2 else None
        r3_win = r3.win_pct if r3 else None
        change = (r3_win - r2_win) if (r2_win is not None and r3_win is not None) else None
        out.append({
            "player_code": code,
            "player_name": (r2.player_name if r2 else None) or (r3.player_name if r3 else None),
            "match_status": status,
            "r2_rank": r2.r2_rank if r2 else None,
            "r2_total_score": r2.r2_total_score if r2 else None,
            "r2_win_pct": r2_win, "r2_top5_pct": r2.top5_pct if r2 else None,
            "r2_top10_pct": r2.top10_pct if r2 else None, "r2_top20_pct": r2.top20_pct if r2 else None,
            "r3_win_pct": r3_win, "r3_top5_pct": r3.top5_pct if r3 else None,
            "r3_top10_pct": r3.top10_pct if r3 else None, "r3_top20_pct": r3.top20_pct if r3 else None,
            "r2_to_r3_win_change_pct": change,
        })
    return out


def write_comparison_csv(comparison: list[dict], out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_COMPARISON_CSV_FIELDNAMES)
        writer.writeheader()
        for row in comparison:
            writer.writerow({k: (row[k] if row[k] is not None else "unavailable") for k in _COMPARISON_CSV_FIELDNAMES})
    return out_path


def write_provenance_json(
    *, game_code: str, r2_csv_path: Path, r2_csv_sha256: str, r3_stage_found: bool,
    r3_recorded_at_utc: Optional[str], validation: dict, out_path: Path,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "record_kind": "r2_r3_recovery_compare_provenance_v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "game_code": game_code,
        "source_type": "recovered_from_frozen_r2_forecast",
        "source_path": str(r2_csv_path),
        "source_sha256": r2_csv_sha256,
        "recovered_after_stage": "R3",
        "recalculated": False,
        "r3_stage_found": r3_stage_found,
        "r3_recorded_at_utc": r3_recorded_at_utc,
        "validation": validation,
        "note": (
            "This record documents a READ-ONLY comparison between an already-computed, already-frozen R2 "
            "forecast CSV (found locally, never regenerated) and the existing STAGE_R3 tournament_history "
            "record. No STAGE_R2 history record was written -- klpga.neo_win.tournament_history's schema has "
            "no generic metadata field to carry this provenance, so it is kept here instead, entirely outside "
            "that module."
        ),
    }
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--r2-csv", required=True, help="Path to the recovered frozen R2 forecast CSV.")
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--history-dir", default=str(DEFAULT_HISTORY_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    r2_csv_path = Path(args.r2_csv)
    if not r2_csv_path.exists():
        print(f"ERROR: {r2_csv_path} does not exist.")
        return 3

    r2_rows, header_problems = read_r2_csv(r2_csv_path)
    r2_csv_sha256 = sha256_of_file(r2_csv_path)

    r3_stage = read_effective_history_stage(Path(args.history_dir), args.game_code, STAGE_R3)
    r3_entrants = r3_stage.entrants if r3_stage is not None else ()

    duplicates = check_player_code_uniqueness(r2_rows)
    r2_invariant_violations = check_probability_invariants(r2_rows, label="R2")
    rank_score_problems = check_r2_rank_score_monotonic(r2_rows)

    r3_pseudo_rows = [
        R2Row(player_code=e.player_code, player_name=e.player_name, r2_rank=None, r2_total_score=None,
              win_pct=e.win_pct, top5_pct=e.top5_pct, top10_pct=e.top10_pct, top20_pct=e.top20_pct)
        for e in r3_entrants
    ]
    r3_invariant_violations = check_probability_invariants(r3_pseudo_rows, label="R3")

    r2_win_sum = round(sum(r.win_pct for r in r2_rows if r.win_pct is not None), 4)
    r3_win_sum = round(sum(e.win_pct for e in r3_entrants if e.win_pct is not None), 4)

    comparison = build_comparison(r2_rows, r3_entrants)
    matched = [c for c in comparison if c["match_status"] == MATCH_BOTH]
    r2_only = [c for c in comparison if c["match_status"] == MATCH_R2_ONLY]
    r3_only = [c for c in comparison if c["match_status"] == MATCH_R3_ONLY]

    source_valid = not header_problems and not duplicates

    validation = {
        "header_problems": header_problems,
        "duplicate_player_codes": duplicates,
        "r2_probability_invariant_violations": r2_invariant_violations,
        "r3_probability_invariant_violations": r3_invariant_violations,
        "r2_rank_score_monotonicity_problems": rank_score_problems,
        "r2_player_count": len(r2_rows),
        "r3_player_count": len(r3_entrants),
        "matched_player_count": len(matched),
        "r2_only_player_count": len(r2_only),
        "r3_only_player_count": len(r3_only),
        "r2_win_sum_pct": r2_win_sum,
        "r3_win_sum_pct": r3_win_sum,
    }

    output_dir = Path(args.output_dir) / args.game_code
    csv_path = None
    provenance_path = None
    if source_valid:
        csv_path = write_comparison_csv(comparison, output_dir / "R2_R3_RECOVERY_COMPARISON.csv")
    provenance_path = write_provenance_json(
        game_code=args.game_code, r2_csv_path=r2_csv_path, r2_csv_sha256=r2_csv_sha256,
        r3_stage_found=r3_stage is not None,
        r3_recorded_at_utc=(r3_stage.recorded_at_utc if r3_stage is not None else None),
        validation=validation, out_path=output_dir / "R2_R3_RECOVERY_PROVENANCE.json",
    )

    print("=== R2<->R3 RECOVERY / COMPARE (READ-ONLY) ===")
    print()
    print(f"RECOVERY SOURCE VALID: {'YES' if source_valid else 'NO'}")
    if header_problems:
        print(f"  header problems: {header_problems}")
    print(f"SOURCE HASH: {r2_csv_sha256}")
    print(f"R2 PLAYER COUNT: {len(r2_rows)}")
    print(f"R3 PLAYER COUNT: {len(r3_entrants)} ({'STAGE_R3 found' if r3_stage is not None else 'STAGE_R3 NOT FOUND -- comparison has no R3 side'})")
    print(f"MATCHED PLAYERS: {len(matched)}")
    print(f"DUPLICATES: {len(duplicates)} {duplicates}")
    print(f"PROBABILITY INVARIANTS: R2 violations={len(r2_invariant_violations)} R3 violations={len(r3_invariant_violations)} "
          f"rank/score monotonicity problems={len(rank_score_problems)}")
    print(f"R2 WIN SUM: {r2_win_sum}%")
    print(f"R3 WIN SUM: {r3_win_sum}%")
    print()
    print("RECOMMENDED RECOVERY METHOD: direct read-only JOIN of the recovered R2 CSV against the existing "
          "STAGE_R3 tournament_history record, by player_code -- never constructing a STAGE_R2 history file.")
    print("R2.JSON REQUIRED: NO")
    print("RECALCULATION REQUIRED: NO")
    print("FROZEN ARTIFACT MODIFICATION REQUIRED: NO")
    print(f"READY FOR R2->R3 COMPARISON: {'YES' if (source_valid and r3_stage is not None) else 'NO'}")
    print()
    if csv_path:
        print(f"Wrote: {csv_path}")
    print(f"Wrote: {provenance_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
