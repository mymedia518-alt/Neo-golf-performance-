"""ROOT HOME PROMOTION: promote ONLY the candidate's own index.html
(whichever HOME state scripts/88's build() decided -- TOP120_OWNER's
player-first fallback, or CURRENT_TOURNAMENT_OWNER's active-tournament
stage page, see that script's HOME STATE ROUTER), plus the ONE shared
CSS asset its markup depends on (assets/neo-site.css), to production
docs/. Supports ownership transfer in EITHER direction between the two
recognized owners -- home_ownership_guard.py's OWNER SUPERSESSION note
anticipated exactly this: "TOP120_OWNER's own build/promotion path
... still the sole legitimate writer for CURRENT_TOURNAMENT_OWNER to
itself supersede, if a future owner decision reverses this one" applies
symmetrically the other way once a tournament becomes active again.
Script 88 already decided WHICH state candidate/.../index.html carries;
this script only promotes whatever that decision was -- it makes no
state decision of its own.

Deliberately narrower than scripts/94_promote_top120_to_production.py.
That script mirrors the ENTIRE candidate tree (index.html, about,
archive, assets, data, deep-dive, neo-lab, ranking, tournaments) into
docs/. Running it now would silently violate two separate, still-active
site policies this task must not touch:

  1. apply_public_site_lockdown.py's approved-routes-only lockdown --
     docs/ranking, /about, /deep-dive, /neo-lab and every tournament
     route except KB's own released PRE/R1 pages are DELIBERATELY held
     at a "공사중" placeholder (verify_lockdown() hard-fails otherwise).
     The candidate tree carries the REAL content for all of those
     (confirmed by diff), so a full mirror would publish them all
     without any of this task's authorization covering that.
  2. the live KB PRE/R1 tournament pages -- the candidate's own copy of
     tournaments/2026/2026090003/{pre,r1} is a stale, differently-built
     snapshot (different active-nav target, different CSS href scheme,
     confirmed by diff against the real, currently-live pages), so
     mirroring it would regress the one thing this task's tournament-
     route-safety step explicitly protects.

WHY assets/neo-site.css IS promoted here, unlike everything else under
assets/: it is the ONE file docs/index.html's new markup cannot render
correctly without (.home-table mobile grid, .metric-sg/.k-rank-cell/
.metric-pos/.metric-neg color classes) -- and it was found to be stale
in docs/ (last promoted at commit 1c3506d, predating even the KB mobile
hotfix), a real, pre-existing gap in the promotion pipeline, not
something this task introduced. It is the SAME shared stylesheet every
other page (including KB PRE/R1) already links -- confirmed
additive-only relative to what was live before (no rule removed, only
new selectors added), and the full KB mobile QA suite
(tests/test_kb_current_mobile_ui_qa.py) is re-run against the real
docs/ tree after this promotion specifically to prove that empirically,
not just by diff review. assets/neo.css, assets/neo-site.js, and
assets/top120.js are confirmed already in sync (byte-identical, or
differing only by a leading blank line) and are left untouched.

This script writes exactly two files under docs/: index.html and
assets/neo-site.css. Nothing else is touched.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.home_ownership_guard import (  # noqa: E402
    CURRENT_TOURNAMENT_OWNER,
    TOP120_OWNER,
    assert_home_write_allowed,
    extract_owner,
)

CANDIDATE = ROOT / "candidate" / "neo-data-home-top120"
SOURCE = CANDIDATE / "index.html"
DEST = REPO_ROOT / "docs" / "index.html"
CSS_SOURCE = CANDIDATE / "assets" / "neo-site.css"
CSS_DEST = REPO_ROOT / "docs" / "assets" / "neo-site.css"

RECOGNIZED_OWNERS = (TOP120_OWNER, CURRENT_TOURNAMENT_OWNER)

# The shared stylesheet always needs the base nav/header classes (every
# HOME state links it) plus the TOP120-page classes -- checked
# unconditionally, not only when the candidate is currently in the
# TOP120 fallback state, because this same file must still be correct
# and complete for whichever state HOME is in NEXT time this script
# runs, not just the state it happens to be promoting right now.
REQUIRED_HOME_CSS_MARKERS = (
    ".neo-global-nav{display:flex",
    "@media(max-width:760px)",
    ".home-table tbody tr{",
    ".metric-sg",
    ".k-rank-cell",
    ".metric-pos",
    ".metric-neg",
    ".metric-empty",
)


class RootHomePromotionError(Exception):
    pass


def promote_root_home_only() -> tuple[str, str]:
    """Writes DEST from SOURCE and CSS_DEST from CSS_SOURCE. Returns
    (previous_owner, new_owner) (for logging/reporting) on success.
    Raises RootHomePromotionError and writes nothing on any failure."""
    if not SOURCE.is_file():
        raise RootHomePromotionError(f"candidate root HOME not found: {SOURCE}")
    if not CSS_SOURCE.is_file():
        raise RootHomePromotionError(f"candidate shared CSS not found: {CSS_SOURCE}")

    html = SOURCE.read_text(encoding="utf-8")
    owner = extract_owner(html)
    if owner not in RECOGNIZED_OWNERS:
        raise RootHomePromotionError(f"candidate root HOME owner is {owner!r}, expected one of {RECOGNIZED_OWNERS!r} -- refusing to promote")

    css = CSS_SOURCE.read_text(encoding="utf-8")
    missing = [marker for marker in REQUIRED_HOME_CSS_MARKERS if marker not in css]
    if missing:
        raise RootHomePromotionError(f"candidate CSS is missing required HOME rule(s), refusing to promote a broken stylesheet: {missing}")

    previous_owner = extract_owner(DEST.read_text(encoding="utf-8")) if DEST.is_file() else None
    allow_transfer_from = CURRENT_TOURNAMENT_OWNER if owner == TOP120_OWNER else TOP120_OWNER
    try:
        assert_home_write_allowed(DEST, owner, repo_root=REPO_ROOT, allow_transfer_from=allow_transfer_from)
    except Exception as exc:  # HomeOwnershipError
        raise RootHomePromotionError(str(exc)) from exc

    DEST.write_text(html, encoding="utf-8", newline="\n")
    CSS_DEST.write_text(css, encoding="utf-8", newline="\n")
    return previous_owner or "<none>", owner


def main() -> int:
    try:
        previous_owner, new_owner = promote_root_home_only()
    except RootHomePromotionError as exc:
        print(f"FATAL: {exc}")
        print("Aborting -- docs/ left untouched.")
        return 1
    print(f"promoted {SOURCE} -> {DEST}")
    print(f"promoted {CSS_SOURCE} -> {CSS_DEST}")
    print(f"owner transfer: {previous_owner!r} -> {new_owner!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
