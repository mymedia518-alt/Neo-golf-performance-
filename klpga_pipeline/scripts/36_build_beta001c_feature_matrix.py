"""BETA #001-C Phase 5 — writes outputs/beta001_c/BETA001C_FEATURE_MATRIX.csv:
one row per live-field player with the existing NEO WIN v0.1 base
features (unchanged — prior_avg_round_score_to_par, prior_recent_form_10,
neo_consistency_stddev) PLUS the new validated official-metric domain
scores (neo_driving, neo_approach, neo_short_game, neo_putting,
neo_scoring [always None — see klpga.neo_win.feature_matrix's module
docstring], neo_overall_skill), and a per-domain coverage summary.

Read-only (DB opened `mode=ro`); does not touch predictions/, the
frozen M0-M6 ladder, or klpga.neo_win.official_metrics/archive.py (BETA
#001's own pipeline — untouched by this Phase 5 step).

Usage:
    python scripts/36_build_beta001c_feature_matrix.py --db data/klpga.sqlite \\
        --game-code 2026080001 --cutoff-date 2026-08-27
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.feature_matrix import DOMAIN_FEATURE_NAMES, build_beta001c_feature_matrix  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "beta001_c"
DEFAULT_TAXONOMY_PATH = ROOT / "docs" / "discovery" / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json"
DEFAULT_RAW_SAMPLES_DIR = ROOT / "docs" / "discovery" / "raw_samples"

_BASE_FEATURE_COLUMNS = ("prior_avg_round_score_to_par", "prior_recent_form_10", "neo_consistency_stddev")


def _write_feature_matrix_csv(result: dict, output_path: Path) -> None:
    domain_columns = list(DOMAIN_FEATURE_NAMES.values())
    fieldnames = (
        ["player_code", "player_name", "in_player_master"]
        + list(_BASE_FEATURE_COLUMNS)
        + [c for name in domain_columns for c in (name, f"{name}_n")]
    )
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in result["field_rows"]:
            out = {"player_code": row["player_code"], "player_name": row.get("player_name"),
                   "in_player_master": row.get("in_player_master")}
            for col in _BASE_FEATURE_COLUMNS:
                out[col] = "" if row.get(col) is None else row.get(col)
            for name in domain_columns:
                out[name] = "" if row.get(name) is None else row.get(name)
                out[f"{name}_n"] = row.get(f"{name}_n", 0)
            writer.writerow(out)


def print_report(result: dict) -> None:
    print("=== BETA #001-C — FEATURE MATRIX (Phase 5) ===")
    print()
    print(f"Target season: {result['target_season']}  Prior season used: {result['prior_season']}")
    print(f"Field size: {len(result['field_rows'])}")
    print()
    print("=== DOMAIN COVERAGE ===")
    print()
    for domain, cov in result["coverage"].items():
        print(f"{domain} ({cov['feature_name']}): {cov['players_with_data']}/{cov['field_size']} players — "
              f"{len(cov['metrics_used'])} metric(s) used: {cov['metrics_used']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--cutoff-date", required=True)
    parser.add_argument("--taxonomy-path", default=str(DEFAULT_TAXONOMY_PATH))
    parser.add_argument("--raw-samples-dir", default=str(DEFAULT_RAW_SAMPLES_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3

    taxonomy_path = Path(args.taxonomy_path)
    if not taxonomy_path.exists():
        print(f"ERROR: {taxonomy_path} does not exist.")
        return 3
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        result = build_beta001c_feature_matrix(
            conn, args.game_code, date.fromisoformat(args.cutoff_date),
            taxonomy=taxonomy, raw_samples_dir=Path(args.raw_samples_dir),
        )
    finally:
        conn.close()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix_path = output_dir / "BETA001C_FEATURE_MATRIX.csv"
    _write_feature_matrix_csv(result, matrix_path)

    print_report(result)
    print()
    print(f"Wrote: {matrix_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
