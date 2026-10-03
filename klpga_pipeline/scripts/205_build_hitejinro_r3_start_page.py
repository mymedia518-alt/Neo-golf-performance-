"""Build docs/tournaments/2026/2026100005/r3/index.html from the real,
operator-saved confirmed R3 field capture (round 3 just started -- 0
real completed round-3 scores at capture time; same shape as scripts/
204's R2 START precedent). This same capture is also the one
hitejinro_round_pipeline.derive_r2_cut_from_confirmed_r3_field() reads
to derive R2_CUT status onto LEADERBOARD.json -- run that (and rebuild
the R2 page) BEFORE this script, so the 41 real R2_CUT players already
carry their real status when this script's roster/ranking runs.

show_hole_progress=False (2026-10-03, same reasoning as scripts/204's
R2 START page): this capture's inghole values (1-10) are ambiguous --
could be real in-progress hole numbers, could be a shotgun-start
starting-hole assignment -- too close to this round's own start to
treat confidently as live progress. Every still-active player's R3
cell shows "-" here regardless; a real completed score still renders
immediately the moment one appears in a future capture.

Thin wrapper: the actual parse/render logic lives in
klpga.neo_win.hitejinro_round_pipeline.build_in_progress_round_page().
Once round 3 genuinely finishes, run the real completed-round pipeline
(parse_leaderboard(3)/parse_sg(3)/cross_validate(3)/build_round_page(3))
against the real completed captures instead -- that replaces this page
with the real completed-round one, which this script never touches.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import json  # noqa: E402

from klpga.neo_win.hitejinro_round_pipeline import build_in_progress_round_page  # noqa: E402

RAW_PATH = ROOT / "content" / "website_v2" / "incoming_evidence" / "2026100005" / "HITEJINRO_2026100005_R3_LEADERBOARD_INPROGRESS_RAW.html"


def main() -> None:
    out_path = build_in_progress_round_page(3, raw_path=RAW_PATH, show_hole_progress=False)
    print(json.dumps({"written": str(out_path), "raw_evidence": str(RAW_PATH)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
