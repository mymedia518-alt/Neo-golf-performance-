"""HOTFIX -- PRODUCTION HOME -> HANA CURRENT STAGE ROUTING FAILURE (LIVE
RED TEAM finding).

ROOT CAUSE: scripts/156_build_home_page.py's `build()` never read "what
is Hana's current stage" from any evidence at all -- it hardcoded
`_CURRENT_STAGE = "r1"` and duplicated R1's own row-rendering logic
inline. When R2 (scripts/157-161) went live, nothing ever told HOME a
newer stage existed; a visitor landing on HOME kept seeing R1 forever,
exactly the same "HOME -> current tournament -> stuck on an old stage"
failure `klpga.website_v2.kb_home_stage_router` was already written to
fix for KB. This module is Hana's own equivalent (a separate module,
never imported by KB's, per this project's established
self-contained-per-tournament-builder convention) -- same philosophy,
same shape: decide the current stage from REAL evidence, then mirror
that stage's own already-published real page body onto root HOME,
never rebuilding or resimulating anything.

`hana_current_stage()` checks REAL PUBLICATION EVIDENCE only, most
advanced first:
  r3: the real, official R3 frozen evidence (2026090002_R3_FROZEN_
      EVIDENCE.json, built from operator-supplied official R3 evidence)
      AND its own FINAL-stage forecast preview (2026090002_POST_R4_
      FINAL_PREVIEW.json, built from the already-validated/promoted
      R1SG_R2SG model -- no retraining) both exist.
  r2: Hana's real, generic `post_r2_final_forecast` artifact exists
      (`klpga.neo_win.post_r2_forecast.post_r2_forecast_status() ==
      STAGE_CREATED`) -- that file is ONLY ever written after
      `run_post_r2_forecast()` has itself verified the R2 freeze hash
      and passed the leakage gate (scripts/158+159), so its existence
      is strong, already-gated real evidence -- never merely "the R2
      HTML file exists on disk".
  r1: the real, already-published R1 analysis artifact
      (HANA_2026090002_R1_ANALYSIS_V1.json) exists.
  pre: always available (ships with the repo).

This is a real, generic router for THIS tournament, not an R2-specific
hardcode: once a real FR/FINAL stage genuinely publishes for Hana with
its own equivalent evidence artifact, extending the check below (one
more `if`) advances HOME past R3 with no other code change.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from klpga.neo_win.post_r2_forecast import STAGE_CREATED as _R2_STAGE_CREATED, post_r2_forecast_status  # noqa: E402
from klpga.tournament_context import load_tournament_context  # noqa: E402

GAME_CODE = "2026090002"
CONTENT = _ROOT / "content" / "website_v2"
R1_ANALYSIS_PATH = CONTENT / "HANA_2026090002_R1_ANALYSIS_V1.json"
R3_FREEZE_PATH = CONTENT / "2026090002_R3_FROZEN_EVIDENCE.json"
R4_FINAL_PREVIEW_PATH = CONTENT / "2026090002_POST_R4_FINAL_PREVIEW.json"


class HanaHomeStageRouterError(RuntimeError):
    """Raised when hana_current_stage() resolves to a stage whose real
    page does not exist -- never silently falls back to a stale stage."""


def hana_current_stage() -> str:
    context = load_tournament_context(GAME_CODE)
    if R3_FREEZE_PATH.is_file() and R4_FINAL_PREVIEW_PATH.is_file():
        return "r3"
    if post_r2_forecast_status(context) == _R2_STAGE_CREATED:
        return "r2"
    if R1_ANALYSIS_PATH.is_file():
        return "r1"
    return "pre"


def current_stage_main_html(*, repo_root: Path) -> tuple[str, str]:
    """Returns (stage, main_html): the CURRENT Hana stage's own
    already-published real `<main>...</main>` content, read verbatim
    from that stage's own real page file -- never rebuilt/resimulated.
    HOME's own `<head>`/`<header>`/`<footer>` shell (with its own,
    deliberately homepage-generic OG tags -- see scripts/156's module
    docstring) is left for the caller to build exactly as before; this
    function only supplies the one thing that must now track the real
    current stage instead of a hardcoded R1 duplicate: the leaderboard
    body itself."""
    stage = hana_current_stage()
    stage_page = repo_root / "docs" / "tournaments" / "2026" / GAME_CODE / stage / "index.html"
    if not stage_page.is_file():
        raise HanaHomeStageRouterError(
            f"hana_current_stage() resolved to {stage!r} but its real page does not exist at {stage_page} "
            "-- refusing to sync HOME to a stage with no real published content."
        )
    stage_html = stage_page.read_text(encoding="utf-8")
    if "<main>" not in stage_html or "</main>" not in stage_html:
        raise HanaHomeStageRouterError(f"{stage_page} has no <main>...</main> body to mirror onto HOME")
    main_html = "<main>" + stage_html.split("<main>", 1)[1].rsplit("</main>", 1)[0] + "</main>"
    return stage, main_html
