"""Build the real, public Deep Dive route for game_code 2026100005.

Calls the real klpga.neo_win.final_course_deep_dive.connect_course_deep_dive()
connector (never re-implements its BLOCKED/CONNECTED decision) and
renders whichever is true right now: the honest WAIT page
(hitejinro_deep_dive_wait_page.render_deep_dive_wait_page) while
BLOCKED, or -- once a real content_root/2026100005_COURSE_DEEP_DIVE.json
artifact exists and the connector reports CONNECTED -- a real content
render (not implemented here yet, since it cannot be honestly written
until real data exists to shape it against; this script will need one
more real section once that day comes, same as r2_wait_page.py was
superseded the day R2 actually published).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

import json  # noqa: E402

from klpga.neo_win.final_course_deep_dive import connect_course_deep_dive  # noqa: E402
from klpga.neo_win.hitejinro_deep_dive_wait_page import render_deep_dive_wait_page  # noqa: E402
from klpga.tournament_context import resolve_context  # noqa: E402

GAME_CODE = "2026100005"
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "deep-dive" / "index.html"


def main() -> None:
    tourney = json.loads((ROOT / "content" / "website_v2" / f"{GAME_CODE}_TOURNAMENT_INFO.json").read_text(encoding="utf-8"))
    identity = {
        "game_code": GAME_CODE, "tournament_name": tourney["event_name"], "season": tourney["season"],
        "start_date": "2026-10-01", "end_date": "2026-10-04", "final_round_number": 3, "current_round_number": 0,
    }
    registry = json.loads((ROOT / "content" / "website_v2" / "TOURNAMENT_SITE_REGISTRY.json").read_text(encoding="utf-8"))["tournaments"]
    context = resolve_context(identity, registry)

    connection = connect_course_deep_dive(context)
    if connection.status == "BLOCKED":
        # connection.reason is a developer-facing diagnostic (includes an
        # absolute filesystem path) -- never shown verbatim on the public
        # page; the real, full reason is still in this script's own
        # stdout/the build log for anyone investigating.
        public_reason = "홀별 경기 데이터가 아직 수집되지 않았습니다"
        html = render_deep_dive_wait_page(
            tournament_name=tourney["event_name"], game_code=GAME_CODE, reason=public_reason,
        )
        OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
        OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")
        print(json.dumps({"status": "BLOCKED", "written_wait_page": str(OUT_PAGE), "reason": connection.reason}, ensure_ascii=False, indent=2))
        return

    raise SystemExit(
        f"connect_course_deep_dive() reports CONNECTED for {GAME_CODE} -- real data now exists at "
        f"{connection.expected_artifact_path}, but this script has no real-content renderer yet. "
        "Do not fabricate one from connection.data without writing that renderer first."
    )


if __name__ == "__main__":
    main()
