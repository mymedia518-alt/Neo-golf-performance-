"""NEO WEBSITE V3 PHASE 1 -- P0-6 negative regression tests.

Every test here is a FAIL condition per the P0-6 spec: each currently
passes (the defect is fixed), and each must go red if that specific
regression reappears. These are deliberately negative assertions
("this bad thing is absent"), not just positive feature checks -- the
Phase 0 audit's core finding was that the existing suite only ever
asserted presence/counts and so never caught a mojibake fragment that
was visibly live in production HTML.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from klpga.website_v2.home_ownership_guard import (
    HomeOwnershipError,
    TOP120_OWNER,
    assert_home_write_allowed,
    validate_top120_population,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "candidate" / "neo-data-home-top120"

# The exact, known mojibake byte pattern found live in production during
# the Phase 0 audit: CP949 bytes saved into a UTF-8-declared file,
# producing dangling href="..." fragments outside any opening <a> tag.
KNOWN_MOJIBAKE_FRAGMENTS = ["�ֱ�", "Ȩ</a>", "��ȸ</a>", "�Ұ�</a>", "�����̺�</a>"]

STALE_STATUS_PATTERNS = ["진행중", "다음 업데이트 예정", "NEXT UPDATE", "3라운드 진행중", "R3 진행중"]

KG_STAGES = ("pre", "r1", "r2", "r3", "final")


@pytest.fixture(scope="module")
def built():
    path = ROOT / "scripts" / "88_build_neo_top120_candidate.py"
    spec = importlib.util.spec_from_file_location("top120_builder_negreg", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build()


@pytest.fixture(scope="module")
def html_files(built):
    return list(OUTPUT.rglob("*.html"))


# 1. known mojibake fragment present in production HTML
def test_no_known_mojibake_fragment_in_any_production_html(html_files):
    offenders = []
    for f in html_files:
        text = f.read_text(encoding="utf-8")
        if any(frag in text for frag in KNOWN_MOJIBAKE_FRAGMENTS):
            offenders.append(str(f.relative_to(ROOT)))
    assert offenders == [], f"known mojibake fragment found in: {offenders}"


# 2. U+FFFD replacement character present
def test_no_replacement_character_in_any_production_html(html_files):
    offenders = [str(f.relative_to(ROOT)) for f in html_files if "�" in f.read_text(encoding="utf-8")]
    assert offenders == [], f"U+FFFD found in: {offenders}"


# 3. "진행중"-class stale in-progress text on a closed KG page
def test_no_in_progress_text_on_closed_kg_pages(built):
    kg_root = OUTPUT / "tournaments" / "2026" / "kg-ladies-open"
    offenders = []
    for stage in KG_STAGES:
        path = kg_root / stage / "index.html"
        text = path.read_text(encoding="utf-8")
        if "진행중" in text:
            offenders.append(f"{stage}: 진행중")
    hub_text = (OUTPUT / "tournaments" / "index.html").read_text(encoding="utf-8")
    if "진행중" in hub_text:
        offenders.append("hub: 진행중")
    assert offenders == [], f"in-progress text on closed KG pages: {offenders}"


# 4. stale "next update" text on a closed KG page
def test_no_stale_next_update_text_on_closed_kg_pages(built):
    kg_root = OUTPUT / "tournaments" / "2026" / "kg-ladies-open"
    offenders = []
    for stage in KG_STAGES:
        text = (kg_root / stage / "index.html").read_text(encoding="utf-8")
        hits = [p for p in STALE_STATUS_PATTERNS if p in text]
        if hits:
            offenders.append((stage, hits))
    assert offenders == [], f"stale next-update text on closed KG pages: {offenders}"


# 5. any KG PRE/R1/R2/R3/FINAL verified stage link missing from the hub
def test_all_five_kg_stage_links_present_in_hub(built):
    hub_text = (OUTPUT / "tournaments" / "index.html").read_text(encoding="utf-8")
    missing = [
        stage for stage in KG_STAGES
        if f'href="/tournaments/2026/kg-ladies-open/{stage}/"' not in hub_text
    ]
    assert missing == [], f"KG hub is missing stage link(s): {missing}"
    for stage in KG_STAGES:
        assert (OUTPUT / "tournaments" / "2026" / "kg-ladies-open" / stage / "index.html").is_file(), (
            f"KG {stage} link is present in the hub but the page itself does not exist"
        )


# 6. an internal production href pointing at a nonexistent route
def test_no_internal_href_points_at_a_nonexistent_route(html_files):
    broken = []
    for f in html_files:
        text = f.read_text(encoding="utf-8")
        for href in re.findall(r'href="(/[^"]*)"', text):
            path = urlsplit(href).path
            if not path.startswith("/") or path.startswith("//"):
                continue
            if path in ("/",):
                continue
            candidate = OUTPUT / path.lstrip("/")
            resolved = candidate if candidate.suffix else candidate / "index.html"
            if not resolved.is_file() and not (OUTPUT / path.lstrip("/")).is_file():
                broken.append((str(f.relative_to(ROOT)), href))
    assert broken == [], f"internal href(s) pointing at a nonexistent route: {broken}"


# 7. a tournament builder must never be able to overwrite canonical HOME
def test_tournament_builder_cannot_overwrite_canonical_home(tmp_path):
    (tmp_path / "docs").mkdir()
    target = tmp_path / "docs" / "index.html"
    with pytest.raises(HomeOwnershipError):
        assert_home_write_allowed(target, "kg-tournament-builder", repo_root=tmp_path)
    with pytest.raises(HomeOwnershipError):
        assert_home_write_allowed(target, "legacy-r2-deploy-script", repo_root=tmp_path)


# 8. HOME population != 120
def test_home_population_not_120_hard_fails():
    dataset = {"records": [{"official_k_rank": i} for i in range(1, 120)]}  # 119 records
    with pytest.raises(ValueError):
        validate_top120_population(dataset)


# 9. K-Rank != 1..120 (gap/duplicate)
def test_home_k_rank_not_contiguous_1_to_120_hard_fails():
    records = [{"official_k_rank": i} for i in range(1, 121)]
    records[0] = {"official_k_rank": 2}  # duplicate rank 2, missing rank 1
    dataset = {"records": records}
    with pytest.raises(ValueError):
        validate_top120_population(dataset)


# 10. HOME provenance/ownership mismatch
def test_home_ownership_mismatch_hard_fails(tmp_path):
    (tmp_path / "docs").mkdir()
    target = tmp_path / "docs" / "index.html"
    target.write_text('<head><meta name="neo-home-owner" content="top120-v1"></head>', encoding="utf-8")
    with pytest.raises(HomeOwnershipError):
        assert_home_write_allowed(target, "some-other-owner", repo_root=tmp_path)
    # the rightful owner re-writing its own claimed HOME must still be allowed
    assert_home_write_allowed(target, TOP120_OWNER, repo_root=tmp_path)


# Kept alongside the negative tests as a positive sanity check that the
# built candidate this whole module exercises really is the real TOP120
# population -- if this ever drifts, every negative test above is
# silently exercising the wrong artifact.
def test_built_candidate_is_the_real_120_player_top120_population(built):
    dataset = json.loads((OUTPUT / "data" / "neo-top120-evaluation.json").read_text(encoding="utf-8"))
    assert len(dataset["records"]) == 120
    assert sorted(r["official_k_rank"] for r in dataset["records"]) == list(range(1, 121))


# NEO WEBSITE V3 PHASE 3 -- P0-2 (broken links) and P1-8 (one canonical
# header, no page recreates its own) regression coverage.

# 11. an internal href with no matching route anywhere in the tree
def test_no_internal_href_targets_a_missing_route_v3(html_files):
    # protected/beta001/*.html are raw sha256-verified evidence fragments
    # (not real navigable pages -- no header/nav at all), out of scope here.
    pages = [f for f in html_files if "protected" not in f.parts]
    broken = []
    for f in pages:
        text = f.read_text(encoding="utf-8")
        for href in re.findall(r'href="(/[^"]*)"', text):
            path = urlsplit(href).path
            if not path.startswith("/") or path.startswith("//") or path == "/":
                continue
            candidate = OUTPUT / path.lstrip("/")
            resolved = candidate if candidate.suffix else candidate / "index.html"
            if not resolved.is_file() and not candidate.is_file():
                broken.append((str(f.relative_to(ROOT)), href))
    assert broken == [], f"internal href(s) with no matching route: {broken}"


# 12. exactly one canonical site-nav header per page -- no page (KG R1/R2,
# OK Open, or any future addition) may recreate or duplicate the header.
def test_every_page_has_exactly_one_canonical_header(html_files):
    pages = [f for f in html_files if "protected" not in f.parts]
    offenders = {}
    for f in pages:
        text = f.read_text(encoding="utf-8")
        count = len(re.findall(r'<header class="neo-global-header"', text))
        if count != 1:
            offenders[str(f.relative_to(ROOT))] = count
    assert offenders == {}, f"expected exactly 1 canonical header per page: {offenders}"


# 13. the canonical brand text/markup is what every header actually shows
# -- not a stale copy frozen from an earlier version of NAVIGATION_HTML,
# and never a mix of the old one-line ".neo-brand-sub" variant with the
# v3 UI/UX rebuild's stacked NEO + N/E/O legend lockup (spec: "Number ·
# Evidence · Oracle 한 줄 버전 혼재" is a P0 FAIL).
def test_every_header_shows_canonical_brand_text(html_files):
    pages = [f for f in html_files if "protected" not in f.parts]
    missing = []
    mixed_legacy = []
    for f in pages:
        text = f.read_text(encoding="utf-8")
        if '<span class="neo-brand-mark">NEO</span>' not in text or '<span class="neo-brand-legend"' not in text:
            missing.append(str(f.relative_to(ROOT)))
        if 'class="neo-brand-sub"' in text:
            mixed_legacy.append(str(f.relative_to(ROOT)))
    assert missing == [], f"page(s) missing the canonical brand lockup in their header: {missing}"
    assert mixed_legacy == [], f"page(s) still carrying the retired one-line .neo-brand-sub variant: {mixed_legacy}"


# 14. P0-3 build provenance: every page carries both non-visible
# provenance markers (source-commit + build-id -- see
# global_navigation.py for why these are two separate, honestly-scoped
# fields rather than one self-referential commit SHA).
def test_every_page_has_build_provenance_markers(html_files):
    pages = [f for f in html_files if "protected" not in f.parts]
    missing_commit = []
    missing_id = []
    for f in pages:
        text = f.read_text(encoding="utf-8")
        if 'meta name="neo-build-source-commit"' not in text:
            missing_commit.append(str(f.relative_to(ROOT)))
        if 'meta name="neo-build-id"' not in text:
            missing_id.append(str(f.relative_to(ROOT)))
    assert missing_commit == [], f"page(s) missing the neo-build-source-commit <meta> tag: {missing_commit}"
    assert missing_id == [], f"page(s) missing the neo-build-id <meta> tag: {missing_id}"


# 15. LIVE VISUAL HOTFIX P0: every real page in a built tree must carry
# the SAME neo-build-id -- a stale/mismatched value means the tree is a
# mix of two different builds, exactly the defect a red-team GitHub QA
# found (docs/deep-dive stuck on a provenance stamp from an earlier
# commit than the rest of the site).
def test_every_page_has_identical_build_id(html_files):
    pages = [f for f in html_files if "protected" not in f.parts]
    ids: dict[str, list[str]] = {}
    for f in pages:
        match = re.search(r'meta name="neo-build-id" content="([^"]*)"', f.read_text(encoding="utf-8"))
        build_id = match.group(1) if match else "<MISSING>"
        ids.setdefault(build_id, []).append(str(f.relative_to(ROOT)))
    assert len(ids) == 1, f"inconsistent neo-build-id across the built tree: {ids}"


# GLOBAL UI/UX REBUILD -- P0/P1 regression coverage.

# 15. every page's global nav marks exactly one item "here" -- UX spec 2
# ("현재 페이지 active state 표시"). Zero means the active-state wiring
# silently broke; more than one is nonsensical and just as wrong.
def test_every_header_has_exactly_one_active_nav_item(html_files):
    pages = [f for f in html_files if "protected" not in f.parts]
    offenders = {}
    for f in pages:
        text = f.read_text(encoding="utf-8")
        nav_start = text.find('<nav class="neo-global-nav"')
        nav_end = text.find("</nav>", nav_start)
        nav_html = text[nav_start:nav_end] if nav_start != -1 else ""
        count = nav_html.count('aria-current="page"')
        if count != 1:
            offenders[str(f.relative_to(ROOT))] = count
    assert offenders == {}, f"expected exactly one active nav item per page: {offenders}"


# 16. every real tournament page has the shared breadcrumb component --
# UX spec 3/16 ("각 generator가 자기 UI를 만들지 않는다").
def test_every_tournament_page_has_breadcrumb(html_files):
    pages = [
        f for f in html_files
        if "protected" not in f.parts and "/tournaments/2026/" in f.as_posix()
    ]
    offenders = [str(f.relative_to(ROOT)) for f in pages if '<nav class="breadcrumb"' not in f.read_text(encoding="utf-8")]
    assert offenders == [], f"tournament page(s) missing the shared breadcrumb: {offenders}"
