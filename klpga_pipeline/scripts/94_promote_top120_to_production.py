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

import datetime
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.r1_live_probability import LIVE_PROBABILITY_MODEL_STATUS  # noqa: E402
from klpga.website_v2.freshness_gate import (  # noqa: E402
    FreshnessGateError,
    assert_completed_round_has_no_incomplete_holes,
    assert_no_silent_staleness,
)
from klpga.website_v2.home_ownership_guard import TOP120_OWNER, extract_owner, validate_top120_population  # noqa: E402
from klpga.website_v2.model_publication_gate import ModelPublicationGateError, assert_no_blocked_probability_output  # noqa: E402
from klpga.website_v2.tournament_state import home_mode, ok_open_latest_available_stage  # noqa: E402

MODEL_VALIDATED_FOR_PUBLICATION = LIVE_PROBABILITY_MODEL_STATUS == "VALIDATED"

SOURCE = ROOT / "candidate" / "neo-data-home-top120"
DEST = REPO_ROOT / "docs"
CONTENT = ROOT / "content" / "website_v2"
STAGE_STATE_PATH = CONTENT / "OK_OPEN_STAGE_STATE.json"
R1_LIVE_SNAPSHOT_PATH = CONTENT / "OK_OPEN_2026_R1_LIVE_SNAPSHOT.json"

REQUIRED_ROUTES = [
    "index.html",
    "ranking/index.html",
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
MIRRORED_TOP_LEVEL = ["index.html", "about", "assets", "data", "deep-dive", "ranking", "tournaments", "protected"]


class PromotionError(Exception):
    pass


BUILD_ID_RE = re.compile(r'<meta name="neo-build-id" content="([^"]*)">')


def _validate_build_id_consistency(root: Path, label: str) -> None:
    # HARD FAIL: every real page in this tree must carry the identical
    # neo-build-id -- a page with a different (stale) value means this
    # tree is a mix of two different builds, not one atomic promotion.
    # protected/beta001/*.html are raw sha256-verified evidence
    # fragments with no <head>/meta at all, not navigable pages.
    pages = [p for p in root.rglob("index.html") if "protected" not in p.parts]
    if not pages:
        raise PromotionError(f"{label}: no pages found to check build-id consistency")
    ids: dict[str, list[str]] = {}
    for page in pages:
        match = BUILD_ID_RE.search(page.read_text(encoding="utf-8"))
        build_id = match.group(1) if match else "<MISSING>"
        ids.setdefault(build_id, []).append(str(page.relative_to(root)))
    if len(ids) != 1:
        raise PromotionError(f"{label}: stale/inconsistent neo-build-id across the tree (HARD FAIL) -- {ids}")


def _validate_r1_freshness(root: Path, label: str) -> None:
    """P0 STALE-DATA INCIDENT HARD GATE: during an active tournament,
    refuse to promote a build whose R1 live page(s) silently present a
    stale snapshot as current, or whose data state claims R1 is
    complete while individual player rows still show incomplete
    holes. This inspects DATA STATE -- the snapshot's own collected_at
    timestamp and each player's holes_completed -- never merely
    whether the HTML/CSS is well-formed (a Playwright PASS alone is
    not sufficient). See klpga.website_v2.freshness_gate for the root
    cause this guards against."""
    if home_mode() != "TOURNAMENT_ACTIVE":
        return
    if not STAGE_STATE_PATH.is_file() or not R1_LIVE_SNAPSHOT_PATH.is_file():
        return
    state = json.loads(STAGE_STATE_PATH.read_text(encoding="utf-8"))
    r1_state = (state.get("stages") or {}).get("r1") or {}
    if not r1_state.get("validated"):
        return
    snapshot = json.loads(R1_LIVE_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    now = datetime.datetime.now(datetime.timezone.utc)
    collected_at_iso = snapshot.get("collected_at")
    player_table = snapshot.get("player_table") or []
    round_complete = bool(state.get("r1_complete"))
    try:
        assert_completed_round_has_no_incomplete_holes(player_table, round_complete=round_complete, label=label)
        routes = ["tournaments/2026/ok-savings-bank-open/r1/index.html"]
        stage_key, _ = ok_open_latest_available_stage()
        if stage_key == "r1":
            routes.append("index.html")
        for route in routes:
            page_path = root / route
            if not page_path.is_file():
                continue
            assert_no_silent_staleness(page_path.read_text(encoding="utf-8"), collected_at_iso=collected_at_iso, now=now, label=f"{label} ({route})")
    except FreshnessGateError as exc:
        raise PromotionError(str(exc)) from exc


def _validate_model_publication_gate(root: Path, label: str) -> None:
    """P0 MODEL SAFETY PATCH hard gate: while LIVE_PROBABILITY_MODEL_STATUS
    is not "VALIDATED", the R1 page(s) actually being promoted must not
    contain any output derived from the blocked simulation. Checked
    against every route that could carry it (the dedicated R1 route,
    plus root when TOURNAMENT_ACTIVE has root == the R1 stage page)."""
    routes = ["tournaments/2026/ok-savings-bank-open/r1/index.html"]
    if home_mode() == "TOURNAMENT_ACTIVE":
        stage_key, _ = ok_open_latest_available_stage()
        if stage_key == "r1":
            routes.append("index.html")
    for route in routes:
        page_path = root / route
        if not page_path.is_file():
            continue
        try:
            assert_no_blocked_probability_output(
                page_path.read_text(encoding="utf-8"), model_validated=MODEL_VALIDATED_FOR_PUBLICATION, label=f"{label} ({route})"
            )
        except ModelPublicationGateError as exc:
            raise PromotionError(str(exc)) from exc


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

    _validate_build_id_consistency(root, label)
    _validate_r1_freshness(root, label)
    _validate_model_publication_gate(root, label)


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
