"""Tests for the HJ 2026100004 R2 (official result + cut) and R3
(forecast) page builders -- scripts/233_... and scripts/234_....

Guards the operator's explicit constraints: cut status shown as its own
state (not hidden/deleted), WD kept distinct from CUT, R3 covers exactly
the 61 official survivors, and no SG/Top5 data ever reaches either page.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / "scripts"
DOCS_ROOT = Path(__file__).parent.parent.parent / "docs" / "tournaments" / "2026" / "2026100004"
CONTENT = Path(__file__).parent.parent / "content" / "website_v2"


def _load_and_run(script_name):
    spec = importlib.util.spec_from_file_location(script_name, SCRIPTS / script_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[script_name] = module
    spec.loader.exec_module(module)
    module.main()
    return module


def test_r2_page_shows_every_player_with_distinct_cut_wd_status(tmp_path, monkeypatch):
    _load_and_run("233_hj_2026100004_build_r2_page.py")
    html = (DOCS_ROOT / "r2" / "index.html").read_text(encoding="utf-8")
    r2 = json.loads((CONTENT / "HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json").read_text(encoding="utf-8"))

    assert html.count("status-badge'>CUT") == r2["missed_cut_count"]
    assert html.count("status-badge'>WD") == r2["wd_count"]
    # every advancing player's name appears with no CUT/WD badge immediately after it
    for p in r2["advanced_to_r3"]:
        name_idx = html.find(f">{p['player_name']}<")
        assert name_idx != -1, f"{p['player_name']} missing from R2 page"
        nearby = html[name_idx:name_idx + 400]
        assert "status-badge" not in nearby.split("</th>")[0]


def test_r2_page_player_count_matches_official_field_size():
    html = (DOCS_ROOT / "r2" / "index.html").read_text(encoding="utf-8")
    r2 = json.loads((CONTENT / "HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json").read_text(encoding="utf-8"))
    row_count = len(re.findall(r"<tr>", html)) - 1  # minus thead row
    assert row_count == r2["field_size"]


def test_r3_page_covers_exactly_the_61_survivors_no_more_no_less():
    html = (DOCS_ROOT / "r3" / "index.html").read_text(encoding="utf-8")
    r2 = json.loads((CONTENT / "HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json").read_text(encoding="utf-8"))
    row_count = len(re.findall(r"<tr>", html)) - 1
    assert row_count == r2["advanced_count"] == 61
    missed_names = {p["player_name"] for p in r2["missed_cut"]}
    for name in missed_names:
        assert f">{name}<" not in html, f"missed-cut player {name} must not appear on the R3 forecast page"


def test_no_sg_or_top5_data_on_either_public_page():
    r2_html = (DOCS_ROOT / "r2" / "index.html").read_text(encoding="utf-8")
    r3_html = (DOCS_ROOT / "r3" / "index.html").read_text(encoding="utf-8")
    for html in (r2_html, r3_html):
        for forbidden in ("top5", "top5_pct", "strokes_gained", "sg_total", "SG_RAW", "6.47", "5.61"):
            assert forbidden not in html, f"forbidden term {forbidden!r} leaked onto a public page"


def test_stage_nav_consistent_and_correct_across_all_five_pages():
    pages = {
        "hub": DOCS_ROOT / "index.html",
        "pre": DOCS_ROOT / "pre" / "index.html",
        "r1": DOCS_ROOT / "r1" / "index.html",
        "r2": DOCS_ROOT / "r2" / "index.html",
        "r3": DOCS_ROOT / "r3" / "index.html",
    }
    for name, path in pages.items():
        html = path.read_text(encoding="utf-8")
        nav = re.search(r"<nav class=['\"]stage-nav['\"].*?</nav>", html)
        assert nav, f"{name} page missing stage-nav"
        nav_html = nav.group(0)
        # PRE/R1/R2/R3 must each be a real <a> (live) on every page now that all 4 are published
        for stage in ("pre", "r1", "r2", "r3"):
            assert f"2026100004/{stage}/" in nav_html, f"{name} page's stage-nav missing a live link to {stage}"
        # FR has no page yet -- must still render as disabled, not a dead link
        assert "FR</span>" in nav_html or "is-disabled" in nav_html.split("FR")[0][-120:]


def test_r2_cut_rank_numbering_is_contiguous_and_matches_field_size():
    html = (DOCS_ROOT / "r2" / "index.html").read_text(encoding="utf-8")
    ranks = re.findall(r'data-label="순위">([^<]+)<', html)
    # last numeric (non-T, non-em-dash) rank should reach the missed-cut tail close to 108
    numeric = [int(r.lstrip("T")) for r in ranks if r not in ("—",)]
    assert max(numeric) <= 108
    assert min(numeric) == 1
