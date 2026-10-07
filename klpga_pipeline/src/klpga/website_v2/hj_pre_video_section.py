"""Single source of truth for the HJ 2026100004 NEO GOLF DATA pre-event
video <section> markup -- used by BOTH scripts/225_build_hj_2026100004_
pre_page.py (PRE) and scripts/build_tournament_archive_and_hj_scaffold.py
(HOME).

PRE->HOME PARITY FIX (2026-10-07, operator instruction): while the
tournament has not started, root HOME *is* the current tournament's PRE
screen -- so whatever PRE shows, HOME must show identically, including
this video. Before this fix, HOME's own build_home() never rendered this
section at all (it was only ever written inline inside 225's build()),
so every HOME rebuild silently regenerated a page missing the video --
not a one-off clobber, a structural gap in the generator itself. Moving
the markup here, with both builders calling this same function, makes
that gap impossible to reopen on a future rebuild: there is only one
place this HTML is defined, so PRE and HOME can never drift apart on it
again by construction, not by convention."""
from __future__ import annotations

GAME_CODE = "2026100004"
VIDEO_FILENAME = "neo-golf-data-pre.mp4"


def hj_pre_video_section_html(game_code: str = GAME_CODE, *, filename: str = VIDEO_FILENAME) -> str:
    return (
        "<section class='panel' id='final-video'><p class='note'>NEO GOLF DATA</p>"
        "<video controls playsinline style='display:block;width:100%;max-width:100%;height:auto' "
        f"src='/assets/tournaments/{game_code}/{filename}'></video></section>"
    )
