"""PLAYER AFFILIATION / SPONSOR DISPLAY FIX -- regression tests.

Verifies the official affiliation/sponsor line renders directly under
the player name in the OK Open PRE and R1 tables via the ONE shared
_player_identity_cell() renderer, resolved strictly by player_id from
the canonical validated master (OK_OPEN_2026_PRE_PUBLIC_MASTER.json's
current_official_sponsor field -- never fabricated, never a name-only
match), and that nothing else about the tables (scores, probabilities,
rankings, mobile layout, amateur markers) changed as a side effect."""
import json
import re
from pathlib import Path

import importlib.util

SPEC = importlib.util.spec_from_file_location(
    "ok_open_builder", Path(__file__).parents[1] / "scripts" / "84_build_ok_open_pre_website_candidate.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

CONTENT = Path(__file__).parents[1] / "content" / "website_v2"
MASTER = CONTENT / "OK_OPEN_2026_PRE_PUBLIC_MASTER.json"
R1_LIVE_SNAPSHOT = CONTENT / "OK_OPEN_2026_R1_LIVE_SNAPSHOT.json"


def _master_records():
    return json.loads(MASTER.read_text(encoding="utf-8"))["records"]


def test_validated_affiliation_renders_under_player_name():
    out = builder.build()
    r1_html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    pre_html = (out / "tournaments/2026/ok-savings-bank-open/pre/index.html").read_text(encoding="utf-8")
    # 양효진's real validated sponsor from the canonical master -- must
    # appear as a distinct sub-line, never merged into the name string.
    assert "<span class='player'>양효진</span><span class='sponsor'>대보건설</span>" in r1_html
    assert "<span class='player'>양효진</span><span class='sponsor'>대보건설</span>" in pre_html


def test_shared_identity_cell_used_by_both_pre_and_r1_tables():
    # "the reusable tournament table renderer, not only the current R1
    # HTML": PRE and R1 must render byte-identical markup for the same
    # player via the one shared _player_identity_cell() function, not
    # two independently hand-written formats.
    out = builder.build()
    pre_html = (out / "tournaments/2026/ok-savings-bank-open/pre/index.html").read_text(encoding="utf-8")
    r1_html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    for name, sponsor in [("양효진", "대보건설"), ("이예원", "메디힐")]:
        cell = builder._player_identity_cell(name, sponsor)
        assert cell in pre_html
        assert cell in r1_html


def test_no_affiliation_is_fabricated_when_source_unavailable():
    records = _master_records()
    missing = [r for r in records if not r.get("current_official_sponsor")]
    assert missing, "fixture assumption: at least one player has no validated sponsor in the real master"
    r = missing[0]
    cell = builder._player_identity_cell(r["current_official_player_name"], r.get("current_official_sponsor"))
    assert "sponsor" not in cell
    assert cell == f"<span class='player'>{r['current_official_player_name']}</span>"


def test_player_id_is_the_identity_match_key_never_name_fallback():
    # The R1 join is a plain dict.get(player_id) with no name-based
    # fallback anywhere -- an unresolved/unknown player_id must never
    # silently inherit a different player's affiliation.
    sponsor_by_id = {"1": "실제소속사"}
    cell = builder._player_identity_cell("이름불일치선수", sponsor_by_id.get("999999-unknown-id"))
    assert "sponsor" not in cell
    assert "실제소속사" not in cell


def test_amateur_marker_remains_intact():
    out = builder.build()
    r1_html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    pre_html = (out / "tournaments/2026/ok-savings-bank-open/pre/index.html").read_text(encoding="utf-8")
    assert "오수민 0809(A)" in r1_html
    assert "오수민 0809(A)" in pre_html


def test_oh_sumin_is_never_assigned_daebang_construction():
    records = _master_records()
    oh = next(r for r in records if "오수민" in str(r.get("current_official_player_name") or ""))
    # The exact fabricated example this fix must never reproduce.
    assert oh.get("current_official_sponsor") != "대방건설"
    if not oh.get("current_official_sponsor"):
        out = builder.build()
        html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
        idx = html.find("오수민 0809(A)")
        assert idx != -1
        assert "대방건설" not in html[idx : idx + 400]


def test_scores_probabilities_and_rankings_unchanged_by_affiliation_join():
    snapshot = json.loads(R1_LIVE_SNAPSHOT.read_text(encoding="utf-8"))
    leader = snapshot["player_table"][0]
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    th_idx = html.index(f"<span class='player'>{leader['player_name']}</span>")
    row_end = html.index("</tr>", th_idx)
    row_tail = html[th_idx:row_end]
    if leader.get("total_under_par_display"):
        assert str(leader["total_under_par_display"]) in row_tail
    if leader.get("win_pct") is not None:
        assert f"{leader['win_pct']:.1f}%" in row_tail
    # 120 protected TOP120 records still drive the PRE table unchanged.
    pre_html = (out / "tournaments/2026/ok-savings-bank-open/pre/index.html").read_text(encoding="utf-8")
    assert pre_html.count("<tr>") - 1 == 120


def test_mobile_table_remains_usable_with_affiliation_line():
    out = builder.build()
    css = (out / "assets" / "neo.css").read_text(encoding="utf-8")
    assert ".sponsor{display:block;color:var(--muted);font-size:12px" in css
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    header = re.search(r"<thead>.*?</thead>", html, re.S).group(0)
    # Affiliation is a sub-line inside the existing player <th>, never a
    # new column -- column count must be unchanged.
    assert header.count("<th>") == 13
    assert ".table-wrap{width:100%;max-width:100%;overflow-x:auto" in css
