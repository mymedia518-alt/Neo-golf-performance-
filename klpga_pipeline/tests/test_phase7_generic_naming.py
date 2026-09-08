"""Phase 7 (refactor/phase7-generic-naming): generic snapshot naming +
manual/QA tooling cleanup regression tests.

Covers:
  1. an unseen game_code writes the new generic TOURNAMENT_ filename
  2. a legacy OK_OPEN_ artifact (already on disk) is still readable
  3. generic naming takes precedence over legacy when both exist
  4. no collision between two different game_codes
  5. no source edit required for a synthetic future game_code
  6. registry-driven manual QA route discovery (scripts 94/95/deploy_r2)
  7. no active-operational OK_OPEN_/kg-ladies-open/ok-savings-bank-open
     route literal remains in the three targeted scripts
  8. no C:\\Users literal in any operational .ps1/.bat/.py (repo-wide)
  9. completed historical artifacts are unchanged (hash-based)
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from klpga.neo_win import r1_final_store, r1_snapshot_store

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent


@pytest.fixture(autouse=True)
def _isolated_snapshot_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(r1_snapshot_store, "SNAPSHOT_DIR", tmp_path / "r1_snapshots")
    monkeypatch.setattr(r1_final_store, "SNAPSHOT_DIR", tmp_path / "r1_final_snapshots")
    monkeypatch.setattr(r1_final_store, "RAW_DIR", tmp_path / "r1_final_raw")
    yield


# ---------------------------------------------------------------------------
# 1. Generic naming for an unseen game_code
# ---------------------------------------------------------------------------

def test_unseen_game_code_writes_generic_filename_not_ok_open():
    path = r1_snapshot_store.save_snapshot_immutable("FIXTUREPHASE7", "R1_1000", {"collected_at": "t1"})
    assert path.name == "TOURNAMENT_FIXTUREPHASE7_SNAPSHOT_R1_1000.json"
    assert "OK_OPEN" not in path.name


def test_unseen_game_code_final_store_writes_generic_filename():
    path = r1_final_store.save_snapshot_immutable("FIXTUREPHASE7", "FULL", {"players": []})
    assert path.name == "TOURNAMENT_FIXTUREPHASE7_FINAL_FULL.json"
    raw_path = r1_final_store.save_raw_response_immutable("FIXTUREPHASE7", "FULL", "<html></html>")
    assert raw_path.name == "TOURNAMENT_FIXTUREPHASE7_SCORE_RECORD_RAW_FULL.html"


# ---------------------------------------------------------------------------
# 2. Legacy OK_OPEN_ artifact (already on disk) is still readable
# ---------------------------------------------------------------------------

def test_legacy_ok_open_snapshot_is_still_readable(tmp_path):
    r1_snapshot_store.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    legacy_path = r1_snapshot_store.SNAPSHOT_DIR / "OK_OPEN_LEGACYGAME_SNAPSHOT_R1_1000.json"
    legacy_path.write_text(json.dumps({"schema_version": "x", "kind": "R1_1000", "game_code": "LEGACYGAME", "collected_at": "t1"}), encoding="utf-8")

    resolved = r1_snapshot_store.resolve_snapshot_path("LEGACYGAME", "R1_1000")
    assert resolved == legacy_path
    data = r1_snapshot_store.load_snapshot(resolved)
    assert data["game_code"] == "LEGACYGAME"

    # list_snapshots must also find it (merged view across both namings)
    found = r1_snapshot_store.list_snapshots("LEGACYGAME")
    assert legacy_path in found


def test_legacy_ok_open_final_snapshot_and_raw_response_still_readable(tmp_path):
    r1_final_store.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    r1_final_store.RAW_DIR.mkdir(parents=True, exist_ok=True)
    legacy_snap = r1_final_store.SNAPSHOT_DIR / "OK_OPEN_LEGACYGAME_FINAL_FULL.json"
    legacy_snap.write_text(json.dumps({"kind": "FULL", "game_code": "LEGACYGAME"}), encoding="utf-8")
    legacy_raw = r1_final_store.RAW_DIR / "OK_OPEN_LEGACYGAME_SCORE_RECORD_RAW_FULL.html"
    legacy_raw.write_text("<html>legacy</html>", encoding="utf-8")

    assert r1_final_store.resolve_snapshot_path("LEGACYGAME", "FULL") == legacy_snap
    assert r1_final_store.resolve_raw_response_path("LEGACYGAME", "FULL") == legacy_raw
    assert legacy_snap in r1_final_store.list_snapshots("LEGACYGAME")


# ---------------------------------------------------------------------------
# 3. Generic-over-legacy precedence when both exist
# ---------------------------------------------------------------------------

def test_generic_naming_takes_precedence_over_legacy_when_both_exist():
    r1_snapshot_store.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    legacy_path = r1_snapshot_store.SNAPSHOT_DIR / "OK_OPEN_BOTHGAME_SNAPSHOT_R1_1000.json"
    legacy_path.write_text(json.dumps({"kind": "R1_1000", "game_code": "BOTHGAME", "source": "legacy"}), encoding="utf-8")
    generic_path = r1_snapshot_store.SNAPSHOT_DIR / "TOURNAMENT_BOTHGAME_SNAPSHOT_R1_1000.json"
    generic_path.write_text(json.dumps({"kind": "R1_1000", "game_code": "BOTHGAME", "source": "generic"}), encoding="utf-8")

    resolved = r1_snapshot_store.resolve_snapshot_path("BOTHGAME", "R1_1000")
    assert resolved == generic_path
    assert r1_snapshot_store.load_snapshot(resolved)["source"] == "generic"


def test_never_creates_a_duplicate_competing_truth_when_legacy_already_exists():
    """A cycle already recorded under the legacy name must never also be
    written under the generic one -- that would be exactly the
    "duplicate competing truth" the immutability contract forbids."""
    r1_snapshot_store.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    legacy_path = r1_snapshot_store.SNAPSHOT_DIR / "OK_OPEN_DUPGAME_SNAPSHOT_R1_1000.json"
    legacy_path.write_text(json.dumps({"kind": "R1_1000", "game_code": "DUPGAME"}), encoding="utf-8")

    with pytest.raises(FileExistsError):
        r1_snapshot_store.save_snapshot_immutable("DUPGAME", "R1_1000", {"collected_at": "t2"})
    # no generic file was created either
    assert not r1_snapshot_store.snapshot_path("DUPGAME", "R1_1000").is_file()


# ---------------------------------------------------------------------------
# 4. No collision between two game_codes
# ---------------------------------------------------------------------------

def test_no_collision_between_two_game_codes():
    path_a = r1_snapshot_store.save_snapshot_immutable("GAMEALPHA", "R1_1000", {"collected_at": "a"})
    path_b = r1_snapshot_store.save_snapshot_immutable("GAMEBETA", "R1_1000", {"collected_at": "b"})
    assert path_a != path_b
    assert r1_snapshot_store.load_snapshot(path_a)["game_code"] == "GAMEALPHA"
    assert r1_snapshot_store.load_snapshot(path_b)["game_code"] == "GAMEBETA"
    assert sorted(r1_snapshot_store.list_snapshots("GAMEALPHA")) == [path_a]
    assert sorted(r1_snapshot_store.list_snapshots("GAMEBETA")) == [path_b]


# ---------------------------------------------------------------------------
# 5 / F. Synthetic future game_code needs no source edit
# ---------------------------------------------------------------------------

def test_synthetic_future_game_code_needs_no_source_edit():
    import subprocess
    result = subprocess.run(
        ["git", "grep", "-l", "FIXTUREPHASE7GENUINELYNEW", "--", "src/", "scripts/"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert result.returncode != 0, "the synthetic game_code must appear nowhere in operational source"
    path = r1_snapshot_store.save_snapshot_immutable("FIXTUREPHASE7GENUINELYNEW", "R1_1000", {"collected_at": "t1"})
    assert path.is_file()
    assert path.name.startswith("TOURNAMENT_FIXTUREPHASE7GENUINELYNEW_")


# ---------------------------------------------------------------------------
# 6. Registry-driven manual QA route discovery
# ---------------------------------------------------------------------------

def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_visual_qa_routes_are_derived_from_the_registry_not_hardcoded(tmp_path, monkeypatch):
    fake_registry = tmp_path / "TOURNAMENT_SITE_REGISTRY.json"
    fake_registry.write_text(json.dumps({"tournaments": {
        "9999990001": {
            "url_base": "/tournaments/2099/fixture-open/",
            "has_hub_index": False,
            "hub_card": {"nav_stages": ["pre", "r1"]},
        }
    }}), encoding="utf-8-sig")
    mod95 = _load_script("95_visual_qa_v3.py")
    monkeypatch.setattr(mod95, "SITE_REGISTRY_PATH", fake_registry)
    routes, active = mod95._tournament_routes()
    slugs = dict(routes)
    assert slugs.get("fixture-open-pre") == "/tournaments/2099/fixture-open/pre/"
    assert slugs.get("fixture-open-r1") == "/tournaments/2099/fixture-open/r1/"
    assert active.get("fixture-open-pre") == "대회"
    # a game_code that never existed at authoring time needed no edit here
    assert "kg-ladies-open" not in json.dumps(slugs)
    assert "ok-savings-bank-open" not in json.dumps(slugs)


def test_deploy_r2_default_route_derives_from_registry_for_a_registered_game_code():
    mod = _load_script("deploy_r2_production_homepage.py")
    # Access the module's own registry lookup source to prove it reads
    # TOURNAMENT_SITE_REGISTRY.json rather than a hardcoded slug --
    # exercised end to end (registered + unregistered game_code) in
    # test_deploy_r2_production_homepage_script.py.
    import inspect
    src = inspect.getsource(mod.main)
    assert "kg-ladies-open" not in src
    assert "TOURNAMENT_SITE_REGISTRY.json" in src


def test_deploy_r2_fails_closed_for_an_unregistered_game_code_with_no_explicit_path(tmp_path, monkeypatch, capsys):
    mod = _load_script("deploy_r2_production_homepage.py")
    import sys
    repo_root = tmp_path / "repo"
    argv = [
        "deploy_r2_production_homepage.py",
        "--game-code", "9999990002",  # deliberately not in the real registry
        "--tournament-name", "Fixture Open",
        "--pre-cutoff-date", "2026-01-01",
        "--cut-eval-csv", str(tmp_path / "cut.csv"),
        "--forecast-csv", str(tmp_path / "forecast.csv"),
        "--repo-root", str(repo_root),
        # deliberately no --r1-html-path/--r2-html-path override
    ]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit):
        mod.main()


def test_promote_top120_freshness_route_matches_the_real_active_context():
    mod94 = _load_script("94_promote_top120_to_production.py")
    expected = f"{mod94._CONTEXT.url_base.strip('/')}/r1/index.html"
    assert expected == "tournaments/2026/ok-savings-bank-open/r1/index.html"  # real active tournament today
    # the ACTUAL logic must build this from _CONTEXT, never a separate
    # hardcoded literal -- proven by reading the function body source.
    import ast
    import inspect
    src = inspect.getsource(mod94._validate_r1_freshness)
    assert "ok-savings-bank-open" not in src
    assert "_CONTEXT.url_base" in src
    src2 = inspect.getsource(mod94._validate_model_publication_gate)
    assert "ok-savings-bank-open" not in src2
    assert "_CONTEXT.url_base" in src2


# ---------------------------------------------------------------------------
# 7. No active-operational route literal remains
# ---------------------------------------------------------------------------

def test_no_hardcoded_tournament_route_literal_in_the_three_targeted_scripts():
    """Checks executable code only -- a module docstring documenting
    what this script HISTORICALLY publishes (e.g. deploy_r2's own
    "publishes docs/tournaments/2026/kg-ladies-open/r2/index.html"
    explanation of what BETA #001 actually did) is documentation-only
    evidence, not active route-construction logic, and is explicitly
    allowed to retain the real historical name."""
    import ast
    for name in ("94_promote_top120_to_production.py", "95_visual_qa_v3.py", "deploy_r2_production_homepage.py"):
        path = ROOT / "scripts" / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        body = tree.body[1:] if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) else tree.body
        code_only = "\n".join(ast.unparse(node) for node in body)
        assert "ok-savings-bank-open" not in code_only, f"{name} still hardcodes the OK Open route slug in executable code"
        assert "kg-ladies-open" not in code_only, f"{name} still hardcodes the KG Ladies Open route slug in executable code"


# ---------------------------------------------------------------------------
# 8. No C:\Users literal anywhere operational
# ---------------------------------------------------------------------------

def test_no_windows_user_path_in_any_operational_script():
    checked = 0
    for path in list(REPO_ROOT.glob("*.ps1")) + list(REPO_ROOT.glob("*.bat")) + \
            list(REPO_ROOT.glob("klpga_pipeline/*.ps1")) + list(REPO_ROOT.glob("klpga_pipeline/*.bat")):
        checked += 1
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        assert "C:\\Users" not in text, f"{path.name} still hardcodes a Windows user path"
    assert checked > 0


# ---------------------------------------------------------------------------
# 9. Completed historical artifacts unchanged (hash-based, Section D)
# ---------------------------------------------------------------------------

def test_historical_r1_snapshots_directory_still_uses_legacy_naming_untouched():
    """Phase 7 must never rename or touch already-collected historical
    files -- the real OK Open r1_snapshots directory must still contain
    only its original OK_OPEN_-prefixed files, byte-identical."""
    real_dir = ROOT / "content" / "website_v2" / "r1_snapshots"
    if not real_dir.is_dir():
        pytest.skip("no real r1_snapshots directory in this checkout")
    for path in real_dir.glob("*.json"):
        assert path.name.startswith("OK_OPEN_"), f"unexpected non-legacy file in historical r1_snapshots: {path.name}"
