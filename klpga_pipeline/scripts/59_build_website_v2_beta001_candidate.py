"""Build the non-production NEO Website v2 BETA #001 candidate."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2 import build_beta001_candidate  # noqa: E402


def main() -> int:
    written = build_beta001_candidate(
        ROOT / "content" / "website_v2" / "beta001.json",
        ROOT / "evidence" / "beta001" / "manifest.json",
        REPO_ROOT,
        ROOT / "candidate" / "website-v2",
    )
    print(f"WROTE {len(written)} NON-PRODUCTION candidate files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
