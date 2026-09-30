"""Build docs/tournaments/2026/2026100005/r2/index.html -- READY TO
RUN, fails closed right now (no round has been played yet). See
klpga.neo_win.hitejinro_round_page's own module docstring for the full
data contract and why every probability column stays 데이터 부족."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

import json  # noqa: E402

from klpga.neo_win.hitejinro_round_page import render_round_page  # noqa: E402

GAME_CODE = "2026100005"
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r2" / "index.html"


def main() -> None:
    tourney = json.loads((ROOT / "content" / "website_v2" / f"{GAME_CODE}_TOURNAMENT_INFO.json").read_text(encoding="utf-8"))
    start, end = tourney["start_date"], tourney["end_date"]
    date_range = f"{start[:4]}.{start[4:6]}.{start[6:8]} — {end[4:6]}.{end[6:8]}"
    html = render_round_page(2, tournament_name=tourney["event_name"], date_range=date_range, content_root=ROOT / "content" / "website_v2")
    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({"written": str(OUT_PAGE)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
