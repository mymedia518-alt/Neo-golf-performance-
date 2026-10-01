"""Build docs/tournaments/2026/2026100005/r2/index.html.

Thin wrapper: the actual page-build logic now lives in
klpga.neo_win.hitejinro_round_pipeline.build_round_page(), shared with
R1/R3/FR via scripts/run_round_pipeline.py -- never duplicated per
round. This script just calls it with round_number=2 so the original
standalone R2 entry point keeps working. Fails closed (via
render_round_page's own FileNotFoundError) if round 2 hasn't actually
been played/collected yet.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import json  # noqa: E402

from klpga.neo_win.hitejinro_round_pipeline import build_round_page  # noqa: E402


def main() -> None:
    out_path = build_round_page(2)
    print(json.dumps({"written": str(out_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
