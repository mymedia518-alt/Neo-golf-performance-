"""Tests for klpga.website_v2.previous_tournament_link -- the single,
shared "이전 대회" link resolver every stage page (PRE, R1/R2/R3/FR via
hitejinro_round_page.py; HOME inherits it for free by mirroring
whichever stage page is currently live) must call, never reimplement.

Real bug fixed 2026-10-01: the link used to hardcode f"{url_base}pre/",
so a visitor was always sent to the previous tournament's own PRE
(pre-tournament forecast) page even once that tournament had finished
and published a real FINAL page."""
from __future__ import annotations

from pathlib import Path

import pytest

from klpga.website_v2.previous_tournament_link import latest_published_stage_url

pytestmark = pytest.mark.round_pipeline


def test_links_to_final_when_a_real_final_page_exists(tmp_path: Path):
    docs = tmp_path / "docs"
    (docs / "tournaments" / "2026" / "9999990001" / "final").mkdir(parents=True)
    (docs / "tournaments" / "2026" / "9999990001" / "final" / "index.html").write_text("x", encoding="utf-8")
    (docs / "tournaments" / "2026" / "9999990001" / "pre").mkdir(parents=True)
    (docs / "tournaments" / "2026" / "9999990001" / "pre" / "index.html").write_text("x", encoding="utf-8")

    url = latest_published_stage_url("/tournaments/2026/9999990001/", repo_root=tmp_path)
    assert url == "/tournaments/2026/9999990001/final/"


def test_falls_back_to_the_most_advanced_real_round_page(tmp_path: Path):
    docs = tmp_path / "docs"
    for stage in ("pre", "r1", "r2"):
        d = docs / "tournaments" / "2026" / "9999990002" / stage
        d.mkdir(parents=True)
        (d / "index.html").write_text("x", encoding="utf-8")
    # no r3/final published yet

    url = latest_published_stage_url("/tournaments/2026/9999990002/", repo_root=tmp_path)
    assert url == "/tournaments/2026/9999990002/r2/"


def test_falls_back_to_pre_when_nothing_else_was_ever_published(tmp_path: Path):
    url = latest_published_stage_url("/tournaments/2026/9999990003/", repo_root=tmp_path)
    assert url == "/tournaments/2026/9999990003/pre/"


def test_real_hana_tournament_resolves_to_its_real_final_page():
    """Against the real, committed repo state (not a tmp fixture) --
    Hana (2026090002) really has completed and really has a real
    final/index.html on disk."""
    url = latest_published_stage_url("/tournaments/2026/2026090002/")
    assert url == "/tournaments/2026/2026090002/final/"


def test_hitejinro_r1_page_hero_includes_the_shared_previous_tournament_link(tmp_path: Path):
    """End-to-end proof that the shared resolver is actually wired into
    hitejinro_round_page.render_round_page (used by R1/R2/R3/FR) -- not
    just PRE. Uses an isolated, synthetic LEADERBOARD.json fixture
    (never written to the real repo) purely to get past the "has this
    round actually been played" fail-closed gate."""
    import json

    from klpga.neo_win.hitejinro_round_page import render_round_page

    content_root = tmp_path
    (content_root / "2026100005_LEADERBOARD.json").write_text(json.dumps({
        "game_code": "2026100005", "final_round": 1,
        "records": [{
            "player_id": "10725", "player_name": "김민솔", "finish_position": "1",
            "finish_position_numeric": 1, "score_to_par": -3,
            "r1_score": 69, "r2_score": None, "r3_score": None, "r4_score": None,
            "withdrawn": False, "disqualified": False,
        }],
    }, ensure_ascii=False), encoding="utf-8")

    html = render_round_page(
        1, tournament_name="제26회 하이트진로 챔피언십", date_range="2026.10.01 — 10.04",
        content_root=content_root,
    )
    assert "이전 대회" in html
    assert "/tournaments/2026/2026090002/final/" in html
