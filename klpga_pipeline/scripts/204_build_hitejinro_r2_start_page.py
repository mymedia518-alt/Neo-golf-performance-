"""Build docs/tournaments/2026/2026100005/r2/index.html from the real,
operator-saved LIVE round-2 leaderboard capture (round 2 just started
-- 0 real completed round-2 scores at capture time; see
klpga.neo_win.hitejinro_round_pipeline.parse_in_progress_state's own
docstring for exactly how "excluded"/"playing"/"not yet started" are
each real, non-fabricated signals read from that capture, never a
hardcoded headcount or a guessed "진행 중" label).

show_hole_progress=False (operator call, 2026-10-01): this first
capture's "FU" (fairway, hit a shot) signal exists for most players,
but the operator judged it too close to this round's own start to
treat as the real moment to switch the 2R column to hole numbers --
every still-active player's cell shows "-" here regardless. A real
completed score (CUT/WD status, or an eventual real round-2 score)
still renders immediately in either mode -- only the hole-number
display is held back by this flag.

Thin wrapper: the actual parse/render logic lives in
klpga.neo_win.hitejinro_round_pipeline.build_in_progress_round_page().
Once round 2 genuinely finishes, run scripts/run_round_pipeline.py
2026100005 R2 against the real completed captures instead -- that
replaces this page with the real completed-round one via
build_round_page(2), which this script never touches.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import json  # noqa: E402

from klpga.neo_win.hitejinro_round_pipeline import (  # noqa: E402
    build_in_progress_round_page,
    raw_evidence_path,
)

RAW_PATH = ROOT / "content" / "website_v2" / "incoming_evidence" / "2026100005" / "HITEJINRO_2026100005_R2_LEADERBOARD_INPROGRESS_RAW.html"


def main() -> None:
    out_path = build_in_progress_round_page(2, raw_path=RAW_PATH, show_hole_progress=False)
    print(json.dumps({"written": str(out_path), "raw_evidence": str(RAW_PATH)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
