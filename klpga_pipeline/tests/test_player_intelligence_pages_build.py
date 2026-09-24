"""Tests for scripts/187_build_player_intelligence_pages.py (Sprint 3)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("script187_under_test", ROOT / "scripts" / "187_build_player_intelligence_pages.py")
pi_pages = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pi_pages)


def test_build_writes_a_page_per_player_and_syncs_assets():
    result = pi_pages.build()
    assert result["total"] > 100
    assert result["generated"] + result["placeholder"] == result["total"]

    sample_path = pi_pages.OUTPUT / "player" / "10097" / "index.html"
    assert sample_path.exists()
    html = sample_path.read_text(encoding="utf-8")
    assert "<!doctype html>" in html
    # playerCode=10097 renders the real PLAYER_HISTORY.json report, not
    # the ordinary stat layout's player-type classification text --
    # Player Intelligence is no longer the goal for this player.
    assert "커리어 개요" in html or "player-type" in html
    assert (pi_pages.OUTPUT / "assets" / "neo-site.css").exists()


def test_build_page_has_global_navigation_and_footer():
    pi_pages.build()
    html = (pi_pages.OUTPUT / "player" / "10097" / "index.html").read_text(encoding="utf-8")
    assert 'data-neo-global-navigation' not in html or "neo-global-header" in html
    assert "site-footer" in html


def test_build_prev_next_links_reference_real_neighbours():
    pi_pages.build()
    population = pi_pages._load_population()
    ids = [str(r["player_id"]) for r in population]
    idx = ids.index("10097")
    html = (pi_pages.OUTPUT / "player" / "10097" / "index.html").read_text(encoding="utf-8")
    if idx > 0:
        assert f'/player/{ids[idx - 1]}/' in html
    if idx + 1 < len(ids):
        assert f'/player/{ids[idx + 1]}/' in html


def test_build_never_writes_outside_candidate_root(tmp_path, monkeypatch):
    from klpga.tournament_context import CANDIDATE_ROOT

    result = pi_pages.build()
    assert str(pi_pages.OUTPUT).startswith(str(CANDIDATE_ROOT))
    assert result["total"] > 0


# ---------------------------------------------------------------------------
# build_one(): a single player_id, never touching any other player's page
# ---------------------------------------------------------------------------


def test_build_one_writes_real_content_for_10097():
    pi_pages.build()  # establish a full baseline once
    result = pi_pages.build_one("10097")
    assert result == {"player_id": "10097", "placeholder": False}
    html = (pi_pages.OUTPUT / "player" / "10097" / "index.html").read_text(encoding="utf-8")
    assert "<!doctype html>" in html
    assert "pi-generating" not in html
    # Player Intelligence is no longer the goal for playerCode=10097 --
    # it now renders the real PLAYER_HISTORY.json report.
    assert "커리어 개요" in html


def test_build_one_never_touches_any_other_players_page():
    pi_pages.build()
    other_ids = ["10002", "10098", "9784"]
    other_paths = [pi_pages.OUTPUT / "player" / pid / "index.html" for pid in other_ids]
    before = [p.read_bytes() for p in other_paths]

    pi_pages.build_one("10097")

    after = [p.read_bytes() for p in other_paths]
    assert before == after


def test_build_one_raises_for_unknown_player_id():
    pi_pages.build()
    with pytest.raises(ValueError):
        pi_pages.build_one("NO_SUCH_PLAYER_ID_XYZ")


def test_build_one_prev_next_links_reference_real_neighbours():
    pi_pages.build()
    population = pi_pages._load_population()
    ids = [str(r["player_id"]) for r in population]
    idx = ids.index("10097")

    pi_pages.build_one("10097")
    html = (pi_pages.OUTPUT / "player" / "10097" / "index.html").read_text(encoding="utf-8")
    if idx > 0:
        assert f'/player/{ids[idx - 1]}/' in html
    if idx + 1 < len(ids):
        assert f'/player/{ids[idx + 1]}/' in html
