"""Build the non-production PHASE 1 NEO Website v2 shell preview."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2 import build_preview_site  # noqa: E402


def main() -> int:
    fixture = ROOT / "tests" / "fixtures" / "website_v2" / "beta002_shell.json"
    output = ROOT / "previews" / "website-v2-phase1"
    written = build_preview_site(fixture, output)
    print(f"WROTE {len(written)} PHASE 1 preview files to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
