"""HOME STATE ROUTER (PRODUCTION HOME PRODUCT POLICY CORRECTION,
20260911): the 12 required regression cases.

RULE A: an active tournament (states PRE/R1/R2/R3/R4) makes ROOT HOME
(/) that tournament's own already-published stage page. RULE B: no
active tournament falls back to the permanent TOP120 player-first
ranking page. RULE C: a finished tournament must not stick to HOME.

CASE 1-5 and CASE 8-9 test the two pure decision functions in
scripts/88_build_neo_top120_candidate.py directly --
resolve_chronology_stages() (does "current" already have a real,
already-generated stage page?) and resolve_active_stage_page() (the
one Path/None root HOME's state comes from) -- so all 5 stages plus
the stale-cache/unknown-state edge cases can be exercised without
running the full, heavy build() pipeline 7 times.

CASE 6-7, 10-12 need the full build() pipeline (owner marker, sponsor
invariant, nav injection, single-writer discipline all only exist on
the actually-rendered page) and use the same
`module.OUTPUT = tmp_path / "candidate"` isolation pattern already
established by tests/test_neo_top120_validation.py.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.home_ownership_guard import (  # noqa: E402
    CURRENT_TOURNAMENT_OWNER,
    TOP120_OWNER,
    extract_owner,
)
from klpga.website_v2.tournament_chronology import TournamentCardFacts  # noqa: E402


def _load_builder_module(name: str):
    path = ROOT / "scripts" / "88_build_neo_top120_candidate.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture()
def builder():
    return _load_builder_module("home_state_router_builder")


def _facts(game_code: str = "9999990001", url_base: str = "/tournaments/2026/9999990001/") -> TournamentCardFacts:
    return TournamentCardFacts(
        game_code=game_code,
        tournament_name="TEST OPEN",
        date_range_display="2026.09.01-04",
        url_base=url_base,
        start_date="2026-09-01",
        end_date="2026-09-04",
    )


FULL_STAGE_ORDER = ["pre", "r1", "r2", "r3", "r4", "final"]


def _build_stage_tree(output: Path, url_base: str, stages_built: list[str]) -> None:
    """Writes a minimal but real index.html for each stage in
    `stages_built` under `output`, mirroring what script 84/etc leave
    behind for a real tournament route."""
    for stage in stages_built:
        page = output / url_base.strip("/") / stage / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(f"<html><body>{stage.upper()} content</body></html>", encoding="utf-8")


# ---------------------------------------------------------------------
# CASE 1-5: ACTIVE PRE/R1/R2/R3/R4 -> HOME = that tournament's own
# latest real, already-generated stage.
# ---------------------------------------------------------------------

@pytest.mark.parametrize("stage", ["pre", "r1", "r2", "r3", "r4"])
def test_case_1_to_5_active_stage_becomes_home(builder, tmp_path, stage):
    output = tmp_path / "output"
    url_base = "/tournaments/2026/9999990001/"
    built_so_far = FULL_STAGE_ORDER[: FULL_STAGE_ORDER.index(stage) + 1]
    _build_stage_tree(output, url_base, built_so_far)

    chronology = {"current": _facts(url_base=url_base), "last": None, "next": None}
    registry = {"9999990001": {"stage_order": FULL_STAGE_ORDER}}

    resolved = builder.resolve_chronology_stages(chronology, registry, output)
    assert resolved["current"].url_base == f"{url_base}{stage}/"

    active_page = builder.resolve_active_stage_page(resolved, output)
    assert active_page is not None
    assert active_page == output / "tournaments" / "2026" / "9999990001" / stage / "index.html"
    assert active_page.is_file()
    assert f"{stage.upper()} content" in active_page.read_text(encoding="utf-8")


# ---------------------------------------------------------------------
# CASE 6: NO ACTIVE TOURNAMENT -> HOME = ranking/player fallback
# (TOP120_OWNER), via the pure resolver directly.
# ---------------------------------------------------------------------

def test_case_6_no_active_tournament_resolves_to_none(builder, tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    chronology = {
        "current": None,
        "last": _facts(game_code="8888880001", url_base="/tournaments/2025/8888880001/"),
        "next": _facts(game_code="7777770001", url_base="/tournaments/2027/7777770001/"),
    }
    assert builder.resolve_active_stage_page(chronology, output) is None


def test_case_6_full_build_falls_back_to_top120_when_current_is_none(builder, tmp_path, monkeypatch):
    """Full-pipeline confirmation of CASE 6: when the chronology resolver
    genuinely reports no current tournament, build() must publish the
    TOP120_OWNER player-first fallback at root, never a blank/broken
    page and never a stale tournament page."""
    builder.OUTPUT = tmp_path / "candidate"
    monkeypatch.setattr(builder, "build_home_tournament_chronology", lambda registry, context: {"current": None, "last": None, "next": None})
    summary = builder.build()
    assert summary["home_mode"] == "RANKING_DEFAULT"
    html = (builder.OUTPUT / "index.html").read_text(encoding="utf-8")
    assert extract_owner(html) == TOP120_OWNER
    assert html.count("data-player-row") == 120


# ---------------------------------------------------------------------
# CASE 7: FINISHED tournament, no active tournament -- must not remain
# stuck on HOME just because its own old files still exist on disk. A
# finished tournament lives in "last", never "current" -- the resolver
# must consult only "current".
# ---------------------------------------------------------------------

def test_case_7_finished_tournament_with_stale_files_does_not_stick_to_home(builder, tmp_path):
    output = tmp_path / "output"
    finished_url_base = "/tournaments/2025/8888880001/"
    # The finished tournament's own real pages are still sitting on disk
    # (exactly as a completed tournament's archived route would be) --
    # this must NOT make it HOME merely because the files are present.
    _build_stage_tree(output, finished_url_base, FULL_STAGE_ORDER)

    chronology = {
        "current": None,
        "last": _facts(game_code="8888880001", url_base=finished_url_base),
        "next": None,
    }
    registry = {"8888880001": {"stage_order": FULL_STAGE_ORDER}}
    resolved = builder.resolve_chronology_stages(chronology, registry, output)
    assert builder.resolve_active_stage_page(resolved, output) is None


# ---------------------------------------------------------------------
# CASE 8: stale/optimistic registry cache -- the registry can claim a
# tournament has reached a late stage, but only real, already-generated
# files may ever be published; a stage name existing in the registry
# with no corresponding real file must never be fabricated as HOME.
# ---------------------------------------------------------------------

def test_case_8_stale_registry_never_publishes_an_unbuilt_stage(builder, tmp_path):
    output = tmp_path / "output"
    url_base = "/tournaments/2026/9999990001/"
    # Registry optimistically lists the full lifecycle, but reality
    # (what's actually been generated) stops at r1.
    _build_stage_tree(output, url_base, ["pre", "r1"])
    registry = {"9999990001": {"stage_order": FULL_STAGE_ORDER}}
    chronology = {"current": _facts(url_base=url_base), "last": None, "next": None}

    resolved = builder.resolve_chronology_stages(chronology, registry, output)
    assert resolved["current"].url_base == f"{url_base}r1/"
    active_page = builder.resolve_active_stage_page(resolved, output)
    assert active_page == output / "tournaments" / "2026" / "9999990001" / "r1" / "index.html"
    for phantom_stage in ("r2", "r3", "r4", "final"):
        assert phantom_stage not in resolved["current"].url_base


# ---------------------------------------------------------------------
# CASE 9: unknown/invalid tournament state -- a "current" tournament
# whose game_code has no (or a malformed) registry entry must resolve
# to the safe fallback, never crash and never fabricate a stage.
# ---------------------------------------------------------------------

def test_case_9_unknown_registry_entry_falls_back_safely(builder, tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    url_base = "/tournaments/2026/0000000000/"
    chronology = {"current": _facts(game_code="0000000000", url_base=url_base), "last": None, "next": None}

    # (a) game_code entirely absent from the registry
    resolved = builder.resolve_chronology_stages(chronology, {}, output)
    assert resolved["current"].url_base == ""
    assert builder.resolve_active_stage_page(resolved, output) is None

    # (b) game_code present but with a malformed/empty stage_order
    resolved2 = builder.resolve_chronology_stages(chronology, {"0000000000": {"stage_order": None}}, output)
    assert resolved2["current"].url_base == ""
    assert builder.resolve_active_stage_page(resolved2, output) is None


# ---------------------------------------------------------------------
# CASE 10: tournament HOME must preserve the sponsor invariant --
# exercised against today's REAL, non-mocked chronology (KB is
# genuinely the chronologically-current, in-window tournament with a
# real, already-published R1 page as of 2026-09-11).
# ---------------------------------------------------------------------

def test_case_10_active_tournament_home_preserves_sponsor_invariant(builder, tmp_path):
    builder.OUTPUT = tmp_path / "candidate"
    summary = builder.build()
    html = (builder.OUTPUT / "index.html").read_text(encoding="utf-8")

    assert summary["home_mode"] == "CURRENT_TOURNAMENT_HOME"
    assert extract_owner(html) == CURRENT_TOURNAMENT_OWNER
    # Both identity slots are always emitted together (render_player_identity's
    # "never omitted entirely" contract) -- a real DOM-pairing check, not a
    # single "sponsor" substring search. Stage pages (unlike the TOP120
    # ranking table) use single-quoted attributes -- count both quote
    # styles rather than assuming one.
    name_count = html.count('class="player-name"') + html.count("class='player-name'")
    sponsor_count = html.count('class="player-sponsor"') + html.count("class='player-sponsor'")
    assert name_count > 0
    assert name_count == sponsor_count


# ---------------------------------------------------------------------
# CASE 11: mobile HOME must remain usable -- structural DOM/CSS markers
# on the SAME real, currently-active-tournament HOME as CASE 10 (mobile
# usability must hold for whichever state root HOME is actually in).
# ---------------------------------------------------------------------

def test_case_11_active_tournament_home_is_mobile_usable(builder, tmp_path):
    builder.OUTPUT = tmp_path / "candidate"
    builder.build()
    html = (builder.OUTPUT / "index.html").read_text(encoding="utf-8")
    css = (builder.OUTPUT / "assets" / "neo-site.css").read_text(encoding="utf-8")

    assert 'name="viewport"' in html
    assert 'data-neo-global-navigation' in html
    assert 'class="neo-global-header"' in html
    assert 'class="neo-global-nav"' in html
    assert "@media(max-width:760px)" in css


# ---------------------------------------------------------------------
# CASE 12: root publication must have exactly one authorized
# writer/router -- the ownership guard structurally recognizes only
# TOP120_OWNER/CURRENT_TOURNAMENT_OWNER (any other declared owner is a
# hard stop regardless of which script attempts the write), the sole
# wired-into-production promoter (script 111) makes no state decision
# of its own, and every earlier state decision funnels through
# scripts/88's build() (exactly one decision point: active_stage_page).
# ---------------------------------------------------------------------

def test_case_12_exactly_one_authorized_home_writer(builder):
    from klpga.website_v2 import home_ownership_guard as guard

    assert guard._RECOGNIZED_OWNERS == (TOP120_OWNER, CURRENT_TOURNAMENT_OWNER)

    promotion_src = (ROOT / "scripts" / "111_promote_top120_root_home_only.py").read_text(encoding="utf-8")
    # The sole sanctioned promoter must make no state decision of its
    # own -- it only ever reads whatever owner scripts/88 already
    # embedded and mirrors that file verbatim.
    assert "active_stage_page" not in promotion_src
    assert "resolve_chronology_stages" not in promotion_src
    assert "build_home_tournament_chronology" not in promotion_src

    # Legacy, pre-router scripts that also know how to call the guard
    # (109/110, from an earlier task) are real, structurally-blocked-
    # from-drifting dead paths, not part of this router: neither
    # scripts/88 (the decision point) nor scripts/111 (the sanctioned
    # promoter) nor run_tournament.py (the pipeline entry point)
    # reference them.
    for orchestrator in ("88_build_neo_top120_candidate.py", "111_promote_top120_root_home_only.py", "run_tournament.py"):
        src = (ROOT / "scripts" / orchestrator).read_text(encoding="utf-8")
        assert "109_build_kb_r1_page" not in src
        assert "110_patch_home_current_tournament_card" not in src
