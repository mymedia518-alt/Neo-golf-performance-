"""Generic top-level entry point: build one player's real Player History
report end to end, from reconciliation through the two production HTML
pages under docs/.

    python scripts/build_player_report.py --player-id 8243
    python scripts/build_player_report.py --player-id 10097

This is a thin orchestrator, not a second implementation: every real
step below is a direct call into the one existing implementation of
that step --

  1. scripts/reconcile_10097_player_history.reconcile(player_id, player_name)
     (called indirectly, via step 2, exactly the way it always was)
  2. scripts/build_10097_player_history.main(player_id, player_name)
     -- the now-generic PLAYER_HISTORY.json builder (writes
     content/website_v2/knowledge_engine/player_intelligence/<id>/
     PLAYER_HISTORY.json + its reconciliation report)
  3. scripts/188_build_player_intelligence_production_page.build_one(player_id)
     -- writes docs/player/<id>/index.html, routed by
     player_intelligence_v2.build_or_placeholder() through
     player_history_report.render_player_history_html() (see that
     module's routing docstring: any player_id with a real, built
     PLAYER_HISTORY.json takes this path automatically)
  4. scripts/189_build_player_data_quality_production_page.build_one(player_id)
     -- writes docs/player/<id>/data-quality/index.html

Despite the "10097" in two of those filenames, they are no longer
scope restrictions -- both scripts were parametrized in this same
refactor and now build a real, generic report for any player_id with
real evidence in the repository's warehouses. The "10097" in their
names is legacy naming only; renaming those files was judged out of
scope for this pass (it would require updating every existing import
site: build_10097_player_data_warehouse.py, build_10097_player_
database.py, validate_sg_integration.py, generate_provenance_reports_
v10.py, and this file), so this script imports them by their real,
current filenames instead.

The player's official name is resolved from the same real population
file scripts/188 and scripts/189 already use
(content/website_v2/HOME_REGULAR_TOUR_PLAYER_MASTER.json) unless
--player-name overrides it -- needed only by reconcile()'s
tournament-specific, name-matched evidence loaders (KB Reader,
special-game-code discovery); every other step is player_id-driven.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

POPULATION_FILE = ROOT / "content" / "website_v2" / "HOME_REGULAR_TOUR_PLAYER_MASTER.json"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_player_name(player_id: str) -> str | None:
    """Real player name from the same population file the production
    page builders (188/189) already trust -- None (not a fabricated
    fallback) if this player_id genuinely is not in it, so the caller
    can decide whether that is fatal."""
    if not POPULATION_FILE.exists():
        return None
    records = json.loads(POPULATION_FILE.read_text(encoding="utf-8")).get("records", [])
    row = next((r for r in records if str(r.get("player_id")) == str(player_id)), None)
    return row.get("player_name") if row else None


def build_player_report(player_id: str, player_name: str | None = None) -> dict:
    player_id = str(player_id)
    if player_name is None:
        player_name = _resolve_player_name(player_id)

    build_history = _load_module("build_10097_player_history", ROOT / "scripts" / "build_10097_player_history.py")
    page_188 = _load_module("page_188_build_player_intelligence_production_page", ROOT / "scripts" / "188_build_player_intelligence_production_page.py")
    page_189 = _load_module("page_189_build_player_data_quality_production_page", ROOT / "scripts" / "189_build_player_data_quality_production_page.py")

    print(f"=== [1/3] reconciling + building PLAYER_HISTORY.json for player_id={player_id} (player_name={player_name!r}) ===")
    history_doc = build_history.main(player_id=player_id, player_name=player_name)

    print(f"=== [2/3] building docs/player/{player_id}/index.html ===")
    intelligence_result = page_188.build_one(player_id)
    print(f"wrote {intelligence_result['path']}")

    print(f"=== [3/3] building docs/player/{player_id}/data-quality/index.html ===")
    data_quality_result = page_189.build_one(player_id)
    print(f"wrote {data_quality_result['path']}")

    return {
        "player_id": player_id,
        "player_name": player_name,
        "player_history": history_doc,
        "index_html_path": intelligence_result["path"],
        "data_quality_html_path": data_quality_result["path"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--player-id", required=True, help="playerCode to build the full report for, e.g. 8243")
    parser.add_argument("--player-name", default=None, help="Override the player's official name (default: looked up from HOME_REGULAR_TOUR_PLAYER_MASTER.json)")
    args = parser.parse_args()
    build_player_report(player_id=args.player_id, player_name=args.player_name)
