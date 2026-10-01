"""HITE JINRO R1 -- parse the official Round 1 leaderboard raw capture
into klpga.neo_win.hitejinro_round_page's LEADERBOARD.json contract.

Thin wrapper: the actual round-agnostic parsing logic now lives in
klpga.neo_win.hitejinro_round_pipeline.parse_leaderboard(), shared with
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

from klpga.neo_win.hitejinro_round_pipeline import parse_leaderboard  # noqa: E402


def main() -> None:
    out_path = parse_leaderboard(1)
    doc = json.loads(out_path.read_text(encoding="utf-8"))
    print("wrote", out_path)
    print("coverage:", json.dumps(doc["coverage"], ensure_ascii=False))
    print("raw sha256:", doc["source_raw"]["sha256"])


if __name__ == "__main__":
    main()
