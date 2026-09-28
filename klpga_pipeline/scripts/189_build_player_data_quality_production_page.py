"""Publish ONE player's Data Quality Report to docs/ (the locked-down
GitHub Pages production tree), player/<player_id>/data-quality/index.html.

MISSION V50 (2026-09-28): "Remove Developer Thinking from Player
History... Create a separate page... /player/10097/data-quality/...
Everything technical moves there." This is that page's production
build counterpart to scripts/188_build_player_intelligence_production_
page.py -- same shell, same provenance injection, same real
PLAYER_HISTORY.json, just rendered through player_data_quality_report.py
(which itself only calls functions player_history_report.py already
had -- no duplicate render logic).

Scope discipline: writes ONLY the one player_id passed on the command
line, only under player/<player_id>/data-quality/. No other path under
docs/ is touched.
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
from klpga.website_v2.player_data_quality_report import render_data_quality_html  # noqa: E402
from klpga.website_v2.player_provider import load_player_history  # noqa: E402

DOCS = REPO_ROOT / "docs"
POPULATION_FILE = ROOT / "content" / "website_v2" / "HOME_REGULAR_TOUR_PLAYER_MASTER.json"


def _source_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def _page_shell(player_id: str, player_name: str, body_html: str) -> str:
    title = f"{player_name} · 데이터 품질 보고서" if player_name else "데이터 품질 보고서"
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

    doc = load_player_history(player_id)
    if doc is None:
        raise RuntimeError(
            f"REFUSING TO PUBLISH: player_id={player_id} has no built PLAYER_HISTORY.json yet -- "
            "run the player's history builder first."
        )

    body_html = render_data_quality_html(doc, player_history_url=f"/player/{player_id}/")

    page_html = _page_shell(player_id, player_name, body_html)
    page_html = inject_global_navigation(page_html, active_section=None)
    page_html = inject_build_provenance(page_html, _source_git_sha(), datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))

    out_dir = DOCS / "player" / player_id / "data-quality"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(page_html, encoding="utf-8")

    return {"player_id": player_id, "path": str((out_dir / "index.html").relative_to(REPO_ROOT))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish one player's Data Quality Report to docs/ production.")
    parser.add_argument("--player-id", required=True)
    args = parser.parse_args()
    result = build_one(args.player_id)
    print(f"wrote {result['path']}")
