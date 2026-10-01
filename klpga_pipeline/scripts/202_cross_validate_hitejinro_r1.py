"""RED TEAM: independently cross-check 2026100005_LEADERBOARD.json
against the separate R1 scorecard raw capture.

Thin wrapper: the actual round-agnostic comparison logic now lives in
klpga.neo_win.hitejinro_round_pipeline.cross_validate(), shared with
R2/R3/FR via scripts/run_round_pipeline.py -- never duplicated per
round. This script just calls it with round_number=1 so the original
standalone R1 entry point keeps working.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import json  # noqa: E402

from klpga.neo_win.hitejinro_round_pipeline import cross_validate  # noqa: E402


def main() -> None:
    result = cross_validate(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
