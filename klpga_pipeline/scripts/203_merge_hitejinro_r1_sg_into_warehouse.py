"""Merge the real, already-verified HITE JINRO R1 Strokes Gained
records into historical_sg_warehouse_corrected_v2.json as real
tournament_cumulative rows.

Thin wrapper: the actual round-agnostic merge logic now lives in
klpga.neo_win.hitejinro_round_pipeline.merge_sg_into_warehouse(),
shared with R2/R3/FR via scripts/run_round_pipeline.py -- never
duplicated per round. This script just calls it with round_number=1
so the original standalone R1 entry point keeps working. Idempotent:
re-running this is safe, see that function's own docstring.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import json  # noqa: E402

from klpga.neo_win.hitejinro_round_pipeline import merge_sg_into_warehouse  # noqa: E402


def main() -> None:
    result = merge_sg_into_warehouse(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
