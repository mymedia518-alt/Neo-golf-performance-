"""HARD VALIDATION tests for the team/sponsor display applied to the
real production docs/index.html by
scripts/57_apply_team_sponsor_to_homepage.py, sourced ONLY from
data/sponsor/2026080001_team_sponsor_snapshot.csv (see that file's
sibling .PROVENANCE.md for how it was produced).

These tests read the real, currently-committed docs/index.html at the
repo root -- not a copy or a template render -- so a regression here
means the live page itself regressed."""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE_HTML_PATH = ROOT.parent / "docs" / "index.html"
SPONSOR_CSV_PATH = ROOT / "data" / "sponsor" / "2026080001_team_sponsor_snapshot.csv"

PLACEHOLDER_VALUES = {"-", "없음", "무소속", "확인중"}
HERO_CODES = {"9788", "11134"}


@pytest.fixture(scope="module")
def sponsor_rows() -> list[dict]:
    return list(csv.DictReader(SPONSOR_CSV_PATH.open(encoding="utf-8")))


@pytest.fixture(scope="module")
def html() -> str:
    return SITE_HTML_PATH.read_text(encoding="utf-8")


def test_sponsor_snapshot_has_62_rows(sponsor_rows):
    assert len(sponsor_rows) == 62


def test_sponsor_snapshot_no_duplicate_player_code_or_name(sponsor_rows):
    codes = [r["player_code"] for r in sponsor_rows]
    names = [r["player_name"] for r in sponsor_rows]
    assert len(set(codes)) == 62
    assert len(set(names)) == 62


def test_sponsor_snapshot_present_49_empty_13(sponsor_rows):
    present = [r for r in sponsor_rows if r["team_or_sponsor"]]
    empty = [r for r in sponsor_rows if not r["team_or_sponsor"]]
    assert len(present) == 49
    assert len(empty) == 13
    assert len(present) + len(empty) == 62


def test_no_placeholder_text_used_for_empty_sponsors(sponsor_rows):
    for row in sponsor_rows:
        assert row["team_or_sponsor"] not in PLACEHOLDER_VALUES, row


def test_homepage_roster_still_62(html):
    codes = re.findall(r'data-player-journey-trigger[^>]*data-player-code="(\d+)"', html)
    assert len(codes) == 62
    assert len(set(codes)) == 62


def test_leaderboard_sponsor_present_only_for_the_49(sponsor_rows, html):
    for row in sponsor_rows:
        name, sponsor = row["player_name"], row["team_or_sponsor"]
        has_span = f'<td class="c-name">{name}<span class="c-sponsor">' in html
        if sponsor:
            assert has_span, f"missing leaderboard sponsor for {name}"
            assert f'<span class="c-sponsor">{sponsor}</span>' in html
        else:
            assert not has_span, f"unexpected leaderboard sponsor for empty-sponsor player {name}"


def test_leaderboard_sponsor_span_count_is_49(html):
    assert html.count('class="c-sponsor"') == 49


def test_player_journey_sponsor_matches_leaderboard_for_every_present_player(sponsor_rows, html):
    for row in sponsor_rows:
        code, sponsor = row["player_code"], row["team_or_sponsor"]
        anchor = f'data-player-journey-panel data-player-code="{code}" hidden>'
        idx = html.find(anchor)
        assert idx != -1, f"missing journey panel for player_code={code}"
        window = html[idx : idx + 400]
        if sponsor:
            assert f'<span class="pj-sponsor">{sponsor}</span>' in window, code
        else:
            assert "pj-sponsor" not in window, code


def test_player_journey_sponsor_span_count_is_49(html):
    assert html.count('class="pj-sponsor"') == 49


def test_deep_dive_sponsor_consistent_with_leaderboard(sponsor_rows, html):
    """Every dd-name occurrence (a player may have more than one, e.g.
    a comparison card) must carry the SAME sponsor value as that
    player's leaderboard entry."""
    for row in sponsor_rows:
        code, name, sponsor = row["player_code"], row["player_name"], row["team_or_sponsor"]
        dd_name_tag = f'<div class="dd-name">{name}</div>'
        occurrences = html.count(dd_name_tag)
        if occurrences == 0:
            continue  # not every player has a Deep Dive card
        if sponsor:
            expected = f'{dd_name_tag}<div class="dd-sponsor">{sponsor}</div>'
            assert html.count(expected) == occurrences, (
                f"{name} ({code}): dd-name occurs {occurrences}x but matching "
                f"dd-sponsor {sponsor!r} doesn't follow every occurrence"
            )
        else:
            for m in re.finditer(re.escape(dd_name_tag) + r"(.{0,60})", html):
                assert "dd-sponsor" not in m.group(1), f"unexpected dd-sponsor for empty-sponsor player {name}"


def test_hero_sponsor_matches_leaderboard_for_hero_players(sponsor_rows, html):
    by_code = {r["player_code"]: r for r in sponsor_rows}
    for code in HERO_CODES:
        row = by_code[code]
        name, sponsor = row["player_name"], row["team_or_sponsor"]
        assert sponsor, f"hero player {name} ({code}) unexpectedly has no sponsor in the snapshot"
        assert f'<p class="hm-name">{name}</p><p class="hm-sponsor">{sponsor}</p>' in html


def test_hero_sponsor_span_count_is_2(html):
    assert html.count('class="hm-sponsor"') == 2


def test_no_placeholder_text_inside_any_rendered_sponsor_element(html):
    for m in re.finditer(r'class="(?:c|pj|dd|hm)-sponsor">([^<]*)<', html):
        assert m.group(1) not in PLACEHOLDER_VALUES, m.group(0)
        assert m.group(1) != "", "an empty-sponsor element should never have been inserted at all"


def test_stripping_sponsor_elements_and_css_reproduces_a_stable_document(html):
    """A structural proxy for 'nothing else changed': removing exactly
    the sponsor insertions must leave a document whose player/score/
    rank counts are the same known-good values from before this
    feature -- this doesn't replay the full pre-change file (not kept
    in the repo), but it pins the counts that matter."""
    stripped = html
    stripped = re.sub(r'<span class="c-sponsor">[^<]*</span>', "", stripped)
    stripped = re.sub(r'<span class="pj-sponsor">[^<]*</span>', "", stripped)
    stripped = re.sub(r'<div class="dd-sponsor">[^<]*</div>', "", stripped)
    stripped = re.sub(r'<p class="hm-sponsor">[^<]*</p>', "", stripped)

    trigger_codes = re.findall(r'data-player-journey-trigger[^>]*data-player-code="(\d+)"', stripped)
    assert len(trigger_codes) == 62
    assert stripped.count('class="rank-group-header"') == 13
    # a handful of known-frozen values must still be present verbatim
    for frozen_marker in ("15.04%", "11.56%", "8.40%", "-12.22%p"):
        assert frozen_marker in stripped
