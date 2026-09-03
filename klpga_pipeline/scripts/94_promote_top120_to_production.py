"""P0-5 production promotion path.

The single, explicit path from the TOP120 canonical candidate to
production `docs/`. Before this script existed, `docs/` was updated by
hand (confirmed in the Phase 0 audit: commit 1bd9eda copied files in
with zero corresponding script change). That is no longer the
workflow: this script is now the only sanctioned way to promote.

The source is hardcoded -- `candidate/neo-data-home-top120/` -- not a
CLI argument, so an arbitrary candidate tree can never be promoted by
mistake or by passing a different path.

Before promotion:
  1. DATA validation    -- re-run validate_top120_population on the
                            candidate's own written evaluation dataset.
  2. HOME ownership      -- the candidate's index.html must already
                            carry the top120-v1 owner marker.
  3. Route validation    -- every required production route must exist
                            in the candidate tree (home, tournaments
                            hub, deep-dive, about, all KG stages, all
                            OK Open stages).

After promotion (mirrored into docs/, CNAME preserved, nothing else
touched):
  4. Production validation -- the same three checks, re-run against
                               what is now actually sitting in docs/.

Any failure at any stage is a hard stop: non-zero exit, and nothing is
written to docs/ if a pre-check fails.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.home_ownership_guard import TOP120_OWNER, extract_owner, validate_top120_population  # noqa: E402

SOURCE = ROOT / "candidate" / "neo-data-home-top120"
DEST = REPO_ROOT / "docs"

REQUIRED_ROUTES = [
    "index.html",
    "tournaments/index.html",
    "deep-dive/index.html",
    "about/index.html",
    "tournaments/2026/kg-ladies-open/index.html",
    "tournaments/2026/kg-ladies-open/pre/index.html",
    "tournaments/2026/kg-ladies-open/r1/index.html",
    "tournaments/2026/kg-ladies-open/r2/index.html",
    "tournaments/2026/kg-ladies-open/r3/index.html",
    "tournaments/2026/kg-ladies-open/final/index.html",
    "protected/beta001/r1.html",
    "protected/beta001/r2.html",
    "protected/beta001/r3.html",
    "tournaments/2026/ok-savings-bank-open/pre/index.html",
    "tournaments/2026/ok-savings-bank-open/r1/index.html",
    "tournaments/2026/ok-savings-bank-open/r2/index.html",
    "tournaments/2026/ok-savings-bank-open/final/index.html",
]

# Only the candidate's own content routes are mirrored -- pure hosting
# config that has no equivalent inside the candidate tree (the GitHub
# Pages custom-domain CNAME) is left alone.
MIRRORED_TOP_LEVEL = ["index.html", "about", "assets", "data", "deep-dive", "tournaments", "protected"]


class PromotionError(Exception):
    pass


def _validate_tree(root: Path, label: str) -> None:
    missing = [route for route in REQUIRED_ROUTES if not (root / route).is_file()]
    if missing:
        raise PromotionError(f"{label}: missing required route(s): {missing}")

    dataset_path = root / "data" / "neo-top120-evaluation.json"
    if not dataset_path.is_file():
        raise PromotionError(f"{label}: missing TOP120 dataset at {dataset_path}")
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    validate_top120_population(dataset)

    home_html = (root / "index.html").read_text(encoding="utf-8")
    owner = extract_owner(home_html)
    if owner != TOP120_OWNER:
        raise PromotionError(f"{label}: HOME ownership check failed -- owner is {owner!r}, expected {TOP120_OWNER!r}")


def promote() -> None:
    if not SOURCE.is_dir():
        raise PromotionError(f"promotion source does not exist: {SOURCE}")

    print(f"=== P0-5 PRODUCTION PROMOTION: {SOURCE} -> {DEST} ===")
    print()
    print("[1/4] DATA + [2/4] HOME ownership + [3/4] route validation (pre-promotion, candidate)")
    _validate_tree(SOURCE, "PRE-PROMOTION (candidate)")
    print("  PASS")
    print()

    print("[promoting] mirroring candidate content into docs/ (CNAME preserved)")
    for name in MIRRORED_TOP_LEVEL:
        src_path = SOURCE / name
        dest_path = DEST / name
        if not src_path.exists():
            raise PromotionError(f"candidate is missing top-level route {name!r}, refusing partial promotion")
        if dest_path.exists():
            if dest_path.is_dir():
                shutil.rmtree(dest_path)
            else:
                dest_path.unlink()
        if src_path.is_dir():
            shutil.copytree(src_path, dest_path)
        else:
            shutil.copyfile(src_path, dest_path)
    print("  DONE")
    print()

    print("[4/4] production validation (post-promotion, docs/)")
    _validate_tree(DEST, "POST-PROMOTION (docs/)")
    print("  PASS")
    print()
    print("PROMOTION COMPLETE.")


def main() -> int:
    try:
        promote()
    except PromotionError as exc:
        print(f"FATAL: {exc}")
        print("Aborting -- promotion refused, docs/ left untouched (or only partially written -- re-run after fixing the source).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
