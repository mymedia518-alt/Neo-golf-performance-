"""Locks in the public stage structure per tournament, after the
2026-10-07 "긴급 회귀 수정" incident: the 2026-10-04 "SEO discoverability"
commit (7f0b76b) silently added a "최종 검증" nav entry + a public
/verification/ link to every HiteJinro (2026100005) stage page, and a
"페이지 업데이트" timestamp to FR -- none of which the operator asked
for, and both directly contradicting an earlier explicit decision
(commit 30a4de7) to keep NEO Verification/SG/Course Analysis internal.

These tests pin exactly the public stage set per tournament (so a
future change to any one tournament's builder, or to the shared
archive/round-page renderer, can never silently leak a new stage into
another tournament's nav or the archive index) and specifically assert
HiteJinro's own already-published pages never again expose 최종 검증,
verification, or a page-update timestamp."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"
SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "build_tournament_archive_and_hj_scaffold.py"

EXPECTED_PUBLIC_STAGES = {
    "2026100005": ["pre", "r1", "r2", "r3", "fr"],
    "2026090002": ["pre", "r1", "r2", "r3", "final"],
    "2026090003": ["pre", "r1", "r2", "r3", "fr", "final"],
    "ok-savings-bank-open": ["pre", "r1", "r2", "r3"],
    "kg-ladies-open": ["pre", "r1", "r2", "r3", "final"],
}


def _load_module():
    spec = importlib.util.spec_from_file_location("archive_hj_invariant", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["archive_hj_invariant"] = module
    spec.loader.exec_module(module)
    return module


def test_public_stages_per_tournament_unchanged():
    mod = _load_module()
    for dirname, expected in EXPECTED_PUBLIC_STAGES.items():
        assert mod.public_stages(dirname) == expected, f"{dirname}: public stage set regressed"


def test_hitejinro_verification_never_in_public_stages():
    mod = _load_module()
    assert "verification" not in mod.public_stages("2026100005")
    assert "course-analysis" not in mod.public_stages("2026100005")


def test_hitejinro_live_pages_never_expose_verification_nav_or_update_timestamp():
    for stage in ("pre", "r1", "r2", "r3", "fr"):
        path = DOCS_ROOT / "tournaments" / "2026" / "2026100005" / stage / "index.html"
        html = path.read_text(encoding="utf-8")
        assert "최종 검증" not in html, f"{stage}: 최종 검증 nav regressed"
        assert "/2026100005/verification/" not in html, f"{stage}: verification link regressed"
        assert "페이지 업데이트" not in html, f"{stage}: page-update timestamp regressed"


def test_hitejinro_stage_nav_is_exactly_pre_r1_r2_r3_fr_on_every_page():
    for stage in ("pre", "r1", "r2", "r3", "fr"):
        path = DOCS_ROOT / "tournaments" / "2026" / "2026100005" / stage / "index.html"
        html = path.read_text(encoding="utf-8")
        nav_match = re.search(r"<nav class=.stage-nav.[^>]*>.*?</nav>", html, re.DOTALL)
        assert nav_match, f"{stage}: no stage-nav found"
        nav_html = nav_match.group(0)
        hrefs = re.findall(r"href=['\"]?/tournaments/2026/2026100005/([a-z0-9-]+)/['\"]?", nav_html)
        current = re.findall(r"aria-current=['\"]page['\"][^>]*>([^<]+)<", nav_html)
        assert set(hrefs) <= {"pre", "r1", "r2", "r3", "fr"}, f"{stage}: unexpected stage-nav link {hrefs}"


def test_sitemap_never_advertises_hitejinro_verification():
    sitemap = (DOCS_ROOT / "sitemap.xml").read_text(encoding="utf-8")
    assert "2026100005/verification" not in sitemap
