"""HOTFIX -- PRODUCTION HOME -> KB CURRENT STAGE ROUTING FAILURE.

Standalone, idempotent CLI entry point for
`klpga.website_v2.kb_home_stage_router.sync_root_home_to_current_stage`.
`scripts/112`/`scripts/114` already call this same function themselves
on every real PUBLISH_AND_CLOSE, so a normal live run never needs this
script -- it exists only to (re)sync root HOME on demand, e.g. right
after this hotfix ships, when the currently-live `docs/index.html` was
never synced past the one-time R1 snapshot `scripts/109` wrote.

Never rebuilds/resimulates anything: it only copies whichever stage
`klpga.website_v2.kb_home_stage_router.kb_current_stage` resolves as
real-evidence-current into root HOME."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_context import load_tournament_context  # noqa: E402
from klpga.website_v2.kb_home_stage_router import sync_root_home_to_current_stage  # noqa: E402


def main() -> int:
    context = load_tournament_context("2026090003")
    result = sync_root_home_to_current_stage(context, repo_root=REPO_ROOT)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
