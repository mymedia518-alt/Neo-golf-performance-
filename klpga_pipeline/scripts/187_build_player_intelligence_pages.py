"""Build the Player Intelligence candidate pages (Sprint 3 integration).

Integration only, never redesign: reads the frozen Knowledge Engine's
already-generated content/website_v2/knowledge_engine/player_intelligence/
documents through klpga.website_v2.player_intelligence_v2 and writes one
static HTML page per player under candidate/neo-data-home-top120/player/
<player_id>/index.html -- the non-production candidate tree every other
NEO DATA HOME build already writes into (see scripts/86, scripts/88).

Never touches docs/ (the locked-down production tree) directly.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.global_navigation import inject_global_navigation  # noqa: E402
from klpga.website_v2.player_intelligence_v2 import build_or_placeholder  # noqa: E402
from klpga.tournament_context import candidate_dir  # noqa: E402

OUTPUT = candidate_dir("neo-data-home-top120")
POPULATION_FILE = ROOT / "content" / "website_v2" / "HOME_REGULAR_TOUR_PLAYER_MASTER.json"


def _load_population() -> list:
    doc = json.loads(POPULATION_FILE.read_text(encoding="utf-8"))
    return [r for r in doc.get("records", []) if r.get("player_id")]


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


def _sync_shared_assets() -> None:
    (OUTPUT / "assets").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        ROOT / "src" / "klpga" / "website_v2" / "static" / "neo-site.css",
        OUTPUT / "assets" / "neo-site.css",
    )


def build() -> dict:
    population = _load_population()

    generated = 0
    placeholder = 0

    for i, row in enumerate(population):
        player_id = str(row["player_id"])
        player_name = row.get("player_name") or player_id

        prev_row = population[i - 1] if i > 0 else None
        next_row = population[i + 1] if i + 1 < len(population) else None
        prev_link = {"href": f"/player/{prev_row['player_id']}/", "name": prev_row.get("player_name") or prev_row["player_id"]} if prev_row else None
        next_link = {"href": f"/player/{next_row['player_id']}/", "name": next_row.get("player_name") or next_row["player_id"]} if next_row else None

        body_html = build_or_placeholder(player_id, player_name=player_name, prev_link=prev_link, next_link=next_link)
        if 'class="pi-generating"' in body_html:
            placeholder += 1
        else:
            generated += 1

        page_html = _page_shell(player_id, player_name, body_html)
        page_html = inject_global_navigation(page_html)

        out_dir = OUTPUT / "player" / player_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(page_html, encoding="utf-8")

    _sync_shared_assets()

    return {"total": len(population), "generated": generated, "placeholder": placeholder}


if __name__ == "__main__":
    result = build()
    print(f"total={result['total']} generated={result['generated']} placeholder={result['placeholder']}")
