"""Publish ONE player's real Player Intelligence page to docs/ (the locked-
down GitHub Pages production tree), player/<player_id>/index.html.

This is the production counterpart of scripts/187_build_player_intelligence_pages.py
(which only ever writes to the non-production candidate/ tree). It writes
directly under docs/ and therefore -- unlike script 187 -- hard-stops
before writing anything if the report is not real (still a placeholder):
a placeholder must never reach the locked-down production tree.

Scope discipline: writes ONLY the one player_id passed on the command
line. No other player's page, and no other path under docs/, is touched.
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.global_navigation import inject_build_provenance, inject_global_navigation  # noqa: E402
from klpga.website_v2.player_intelligence_v2 import build_or_placeholder  # noqa: E402

DOCS = REPO_ROOT / "docs"
POPULATION_FILE = ROOT / "content" / "website_v2" / "HOME_REGULAR_TOUR_PLAYER_MASTER.json"


def _source_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def _page_shell(player_id: str, player_name: str, body_html: str) -> str:
    title = f"{player_name} · Player Intelligence" if player_name else "Player Intelligence"
    return (
        f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{title}</title>"
        f'<link rel="stylesheet" href="/assets/neo-site.css"></head>'
        f"<body><header data-neo-global-navigation></header><main>{body_html}</main>"
        f'<footer class="site-footer"><div class="site-footer__inner">'
        f'<p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p>'
        f"</div></footer></body></html>"
    )


def build_one(player_id: str) -> dict:
    player_id = str(player_id)
    population = json.loads(POPULATION_FILE.read_text(encoding="utf-8")).get("records", [])
    row = next((r for r in population if str(r.get("player_id")) == player_id), None)
    if row is None:
        raise ValueError(f"player_id {player_id!r} is not in the real population ({POPULATION_FILE.name})")
    player_name = row.get("player_name") or player_id

    body_html = build_or_placeholder(player_id, player_name=player_name, prev_link=None, next_link=None)
    if 'class="pi-generating"' in body_html:
        raise RuntimeError(
            f"REFUSING TO PUBLISH: player_id={player_id} report is still a placeholder "
            "(no Gold Standard report exists for this player yet). A placeholder must "
            "never be written into docs/ (the locked-down production tree)."
        )

    page_html = _page_shell(player_id, player_name, body_html)
    page_html = inject_global_navigation(page_html, active_section=None)
    page_html = inject_build_provenance(page_html, _source_git_sha(), datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))

    out_dir = DOCS / "player" / player_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(page_html, encoding="utf-8")

    return {"player_id": player_id, "path": str((out_dir / "index.html").relative_to(REPO_ROOT))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish one player's real Player Intelligence page to docs/ production.")
    parser.add_argument("--player-id", required=True)
    args = parser.parse_args()
    result = build_one(args.player_id)
    print(f"wrote {result['path']}")
