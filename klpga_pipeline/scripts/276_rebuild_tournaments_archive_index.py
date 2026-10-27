"""Rebuild ONLY docs/tournaments/index.html (the public 대회 기록
archive), reusing build_tournament_archive_and_hj_scaffold.py's own
real build_archive_index() function -- the actual generator for this
page (confirmed: .archive-card is used nowhere else in the repo).

Deliberately does NOT call that module's main() or import
build_hj_scaffold()/build_home(): main() also rewrites docs/tournaments/
2026/2026100004/index.html (HJ's own scaffold, a separate, out-of-scope
pipeline) and, far more importantly, OVERWRITES docs/index.html with a
stale HOME build from before this session's S-OIL hero card / seed
bubble zone / major-chart work -- that write would silently destroy
already-approved, already-reported HOME content. Importing just the one
function this task actually needs avoids all of that.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_tournament_archive_and_hj_scaffold import build_archive_index  # noqa: E402

OUT_PATH = REPO_ROOT / "docs" / "tournaments" / "index.html"


def main() -> None:
    html = build_archive_index()
    OUT_PATH.write_text(html, encoding="utf-8")
    print({"written": str(OUT_PATH), "bytes": len(html)})


if __name__ == "__main__":
    main()
