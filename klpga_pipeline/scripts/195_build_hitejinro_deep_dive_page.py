"""Build the public Deep Dive route for game_code 2026100005.

LAYOUT MOCKUP COMMIT (explicit operator instruction, 2026-10-01): renders
klpga.neo_win.hitejinro_deep_dive_mock_page.render_deep_dive_mock_page()
-- the full 11-section Deep Dive layout (코스 한눈에 보기 / 한 줄 분석 /
18홀 난이도 / 홀별 상세 분석 / 티샷 분포 / TOP5 x4 / NEO 코스 분석 /
DATA QUALITY) driven by that module's own hand-built, internally-
consistent MOCK dataset -- never real data. This deliberately bypasses
klpga.neo_win.final_course_deep_dive.connect_course_deep_dive()'s real
BLOCKED/CONNECTED gate for this one commit; see that mock module's own
docstring.

NEXT COMMIT wires this same layout to real data (course_statistics.json
/ playerInfo / shotGroupList from the Reader) -- at that point this
script goes back to calling connect_course_deep_dive() for real and
rendering hitejinro_deep_dive_wait_page's honest BLOCKED page whenever
that real artifact doesn't exist yet, exactly as it did before this
commit (see git history for that version if reverting is ever needed).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

import json  # noqa: E402

from klpga.neo_win.hitejinro_deep_dive_mock_page import render_deep_dive_mock_page  # noqa: E402

GAME_CODE = "2026100005"
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "deep-dive" / "index.html"


def main() -> None:
    tourney = json.loads((ROOT / "content" / "website_v2" / f"{GAME_CODE}_TOURNAMENT_INFO.json").read_text(encoding="utf-8"))
    html = render_deep_dive_mock_page(tournament_name=tourney["event_name"], game_code=GAME_CODE)
    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({"status": "MOCK_LAYOUT", "written": str(OUT_PAGE)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
