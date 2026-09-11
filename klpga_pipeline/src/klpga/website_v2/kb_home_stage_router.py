"""HOTFIX -- PRODUCTION HOME -> KB CURRENT STAGE ROUTING FAILURE.

ROOT CAUSE this module fixes: `docs/index.html` (root HOME) was written
exactly once, by `scripts/109_build_kb_r1_page.py`'s `write_root_home()`,
as a frozen snapshot of KB's R1 page. When R2 (`scripts/112`) and later
R3 (`scripts/114`) went live, nothing ever re-synced root HOME -- its
own embedded stage-nav still showed R2 as a disabled placeholder
(predating the PRE/R1 stage-nav-activation fix), and its "대회" top-nav
override still pointed at `/r1/`. A visitor landing on HOME was
therefore always shown R1 with no way forward -- exactly the reported
"HOME -> current tournament -> R1 -> stuck" failure. (`scripts/112`'s
own `_publish_and_close` comment even says "HOME STATE ROUTER will pick
this page up ... this script itself never rebuilds root HOME" --
referring to the SEPARATE, generic TOP120 HOME-state-router
(`klpga.website_v2.tournament_state` + `scripts/86/88/94`), which never
applied to KB's hand-built R1/R2/R3 page scripts at all: KB's pipeline
never writes `tournament_state`'s `STAGE_STATE_PATH`, so that router
could never have picked R2 up either. This module is KB's own,
equally-real equivalent -- driven by KB's actual freeze/forecast
evidence, not by that unrelated file.)

`kb_current_stage()` decides KB's real current stage from REAL
PUBLICATION EVIDENCE only -- never from whether a stage's HTML file
merely exists on disk (the R3 WAIT page, for example, always exists
once `klpga.neo_win.r3_wait_page` has run, long before R3 has actually
concluded -- its existence must NEVER promote HOME to R3). Evidence
checked, most-advanced stage first:

  r3: `klpga.neo_win.r3_freeze`'s real, hash-verified freeze exists --
      the round has genuinely concluded with real official evidence
      bound to it (`build_r3_frozen_evidence` requires every record's
      status to be a real evidence-backed ACTIVE/WD/DQ/DNS, never a
      guess). Never merely "the WAIT page file exists".
  r2: `klpga.neo_win.post_r2_forecast`'s canonical forecast artifact
      exists (`post_r2_forecast_status() == STAGE_CREATED`) -- that
      file is ONLY ever written by `run_post_r2_forecast()` after it
      has itself verified the R2 freeze hash and passed the R2 leakage
      gate, so its existence is strong, already-gated real evidence.
  r1: the frozen R1 prediction artifact
      (`<game_code>_R1_5PROB_FROZEN_V1.json`) exists.
  pre: always available (ships with the repo).

`sync_root_home_to_current_stage()` then does the one thing this
hotfix is scoped to do: copy the CURRENT stage's own already-published,
already-gated real page body (never rebuilt, never resimulated) into
root HOME, re-injecting the shared global nav with `active_section=
"home"` and a "대회" override that points at that SAME current stage
(never a hardcoded round). PRE/R1/R2's own real per-stage pages are
never modified by this module -- only `docs/index.html`. This is a
real, generic router, not a KB-R2-specific hardcode: once a real R3
freeze exists and R3 genuinely publishes, calling this same function
again advances HOME to R3 with no code change here."""
from __future__ import annotations

from pathlib import Path

from klpga.neo_win.post_r2_forecast import STAGE_CREATED as _R2_STAGE_CREATED, post_r2_forecast_status
from klpga.neo_win.r2_freeze import r2_freeze_exists, verify_r2_freeze_hash
from klpga.neo_win.r3_freeze import r3_freeze_exists, verify_r3_freeze_hash
from klpga.tournament_context import TournamentContext
from klpga.website_v2.global_navigation import inject_global_navigation
from klpga.website_v2.home_ownership_guard import (
    CURRENT_TOURNAMENT_OWNER,
    TOP120_OWNER,
    assert_home_write_allowed,
    embed_owner,
    extract_owner,
)


class KbHomeStageRouterError(RuntimeError):
    """Raised when the current stage's real published page can't be
    found where the evidence says it must be -- never silently falls
    back to a stale/wrong stage."""


def _r1_frozen_prediction_path(context: TournamentContext) -> Path:
    # Uses the SAME generic artifact_path() contract every other real
    # freeze/forecast path uses (see module docstring) -- resolves to
    # exactly "<game_code>_R1_5PROB_FROZEN_V1.json" for KB (no registry
    # override exists for it), and stays correctly redirected under a
    # test's own isolated CONTENT_DIR, unlike a module-level constant
    # imported once at import time would.
    return context.artifact_path("r1_5prob_frozen_v1")


def kb_current_stage(context: TournamentContext) -> str:
    """The most-advanced KB stage with REAL publication evidence behind
    it -- see module docstring. Never inferred from HTML file existence
    alone."""
    if r3_freeze_exists(context) and verify_r3_freeze_hash(context):
        return "r3"
    if (
        post_r2_forecast_status(context) == _R2_STAGE_CREATED
        and r2_freeze_exists(context)
        and verify_r2_freeze_hash(context)
    ):
        return "r2"
    if _r1_frozen_prediction_path(context).is_file():
        return "r1"
    return "pre"


def sync_root_home_to_current_stage(context: TournamentContext, *, repo_root: Path) -> dict:
    """Rewrites `docs/index.html` to mirror the CURRENT stage's own
    already-published real page body -- never rebuilds/resimulates
    anything, only reads the already-gated HTML that stage's own
    publish path already wrote. Idempotent: re-running while the
    current stage hasn't changed rewrites the same content."""
    stage = kb_current_stage(context)
    stage_page = repo_root / "docs" / context.url_base.strip("/") / stage / "index.html"
    if not stage_page.is_file():
        raise KbHomeStageRouterError(
            f"kb_current_stage() resolved to {stage!r} but its real page does not exist at {stage_page} "
            "-- refusing to sync HOME to a stage with no real published content."
        )
    stage_html = stage_page.read_text(encoding="utf-8")
    if "<main>" not in stage_html or "</main>" not in stage_html:
        raise KbHomeStageRouterError(f"{stage_page} has no <main>...</main> body to mirror onto HOME")

    header_prefix = stage_html.split("<main>", 1)[0] + "<main>"
    body = stage_html.split("<main>", 1)[1].rsplit("</main>", 1)[0]
    footer_suffix = "</main>" + stage_html.rsplit("</main>", 1)[1]

    nav_overrides = {"tournaments": f"{context.url_base}{stage}/"}
    home_header = inject_global_navigation(header_prefix, active_section="home", nav_overrides=nav_overrides)

    root_html = home_header + body + footer_suffix

    docs_index = repo_root / "docs" / "index.html"
    archive_index = repo_root / "docs_internal_archive" / "index.html"
    if docs_index.is_file():
        existing = docs_index.read_text(encoding="utf-8")
        if extract_owner(existing) != CURRENT_TOURNAMENT_OWNER and not archive_index.is_file():
            archive_index.parent.mkdir(parents=True, exist_ok=True)
            archive_index.write_text(existing, encoding="utf-8", newline="\n")

    assert_home_write_allowed(docs_index, CURRENT_TOURNAMENT_OWNER, repo_root=repo_root, allow_transfer_from=TOP120_OWNER)
    docs_index.write_text(embed_owner(root_html, CURRENT_TOURNAMENT_OWNER), encoding="utf-8", newline="\n")

    return {"current_stage": stage, "source_page": str(stage_page), "root_home": str(docs_index)}
