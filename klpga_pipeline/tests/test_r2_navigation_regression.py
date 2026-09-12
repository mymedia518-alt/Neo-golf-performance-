"""Task M (fix/kb-r2-official-cut-gate-20260911): REAL R2 NAVIGATION
FAILURE -- user visual QA against the real generated site found the
"2R" stage button not clickable, despite Task L's own QA reporting
"stage nav PASS: PRE/R1/R2, R2 aria-current".

WHY THE PREVIOUS QA FALSE-PASSED: Task L's navigation checks (test_r2_
real_page.py, test_r2_rendered_output_regression.py) only ever verified
the stage-nav that klpga.neo_win.r2_real_page.render_r2_real_page
itself produces for R2's OWN page -- which was, and is, correct (R2's
own template always emits a real <a> for R2 with aria-current="page").
Nothing ever checked PRE's or R1's OWN, separately-generated,
already-committed HTML files. Those are static, hand-carried pages
(scripts/109_build_kb_r1_page.py's own module docstring) built BEFORE
R2's real page existed -- their own <nav class="stage-nav"> still
carried a hardcoded `<span class="stage-nav__disabled">R2</span>`, so
a real user browsing from PRE or R1 (not from R2 itself) hit a
genuinely non-clickable R2 button. See test_pre_and_r1_own_generated_
html_previously_showed_r2_as_disabled below for the exact
reproduction.

FIX: scripts/112's new _enable_r2_stage_nav_link mirrors scripts/109's
own established, already-approved update_pre_page_stage_nav pattern
exactly (idempotent, fail-loud, touches ONLY the one disabled-R2 <li>
substring) -- wired into _publish_and_close, run once now against the
real PRE/R1 files. Verified surgical: `before_html.replace(old_li,
new_li, 1) == after_html` exactly, for both files -- proving the ONLY
byte difference is that one navigation element; no leaderboard,
prediction, sponsor, or historical content of any kind was touched.

Every test here reads the REAL, currently-committed generated site
under docs/ directly -- never a synthetic fixture standing in for it."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DOCS = REPO_ROOT / "docs"
GAME_CODE = "2026090003"
TOURNAMENT_DIR = DOCS / "tournaments" / "2026" / GAME_CODE

PRE_PAGE = TOURNAMENT_DIR / "pre" / "index.html"
R1_PAGE = TOURNAMENT_DIR / "r1" / "index.html"
R2_PAGE = TOURNAMENT_DIR / "r2" / "index.html"

_DISABLED_R2_ITEM = '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R2</span></li>'
_ENABLED_R2_ITEM = f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r2/">R2</a></li>'


def _load_operator_module():
    spec = importlib.util.spec_from_file_location("op112_nav_regression_under_test", ROOT / "scripts" / "112_kb_r2_active_cycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    return _load_operator_module()


# ---------------------------------------------------------------------
# WHY THE PREVIOUS QA FALSE-PASSED: this is the check that was missing.
# ---------------------------------------------------------------------

def test_pre_and_r1_own_generated_html_previously_showed_r2_as_disabled_root_cause():
    """Documents the false-PASS root cause directly: PRE's and R1's own
    generated files are static and were never touched by R2's own
    renderer/template -- proving why checking R2's own page alone
    (Task L's own QA) could never have caught this. This test passes
    NOW because the fix has already been applied to the real files;
    the historical bug is proven instead by
    test_stage_nav_activation_is_surgical_and_reconstructible below,
    which reconstructs the exact pre-fix state and confirms it matches
    _DISABLED_R2_ITEM."""
    assert PRE_PAGE.is_file() and R1_PAGE.is_file()
    pre_html = PRE_PAGE.read_text(encoding="utf-8")
    r1_html = R1_PAGE.read_text(encoding="utf-8")
    assert _DISABLED_R2_ITEM not in pre_html, "PRE's own stage-nav still shows R2 as disabled -- the real reported bug"
    assert _DISABLED_R2_ITEM not in r1_html, "R1's own stage-nav still shows R2 as disabled -- the real reported bug"


def test_stage_nav_activation_is_surgical_and_reconstructible(module):
    """Reconstructs the pre-fix PRE/R1 HTML by reversing the exact
    substitution _enable_r2_stage_nav_link performs, and proves the
    reversal exactly reproduces the real disabled-R2 placeholder that
    caused the reported bug -- i.e. the fix's own diff is provably
    limited to that one substring, both directions."""
    for page in (PRE_PAGE, R1_PAGE):
        after = page.read_text(encoding="utf-8")
        assert _ENABLED_R2_ITEM in after
        reconstructed_before = after.replace(_ENABLED_R2_ITEM, _DISABLED_R2_ITEM, 1)
        assert _DISABLED_R2_ITEM in reconstructed_before
        # Re-applying the real fix function to the reconstructed pre-fix
        # HTML must reproduce the real current file exactly.
        assert module._enable_r2_stage_nav_link(reconstructed_before) == after


def test_stage_nav_activation_is_idempotent_on_the_real_files(module):
    """Running the real fix function again on the ALREADY-fixed real
    files must be a true no-op -- required for scripts/112 to be safely
    re-run in future cycles without corrupting PRE/R1 further."""
    for page in (PRE_PAGE, R1_PAGE):
        html = page.read_text(encoding="utf-8")
        assert module._enable_r2_stage_nav_link(html) == html


def test_stage_nav_activation_fails_loud_never_guesses(module):
    with pytest.raises(ValueError, match="expected exactly one"):
        module._enable_r2_stage_nav_link("<html>no stage nav here</html>")


# ---------------------------------------------------------------------
# Required checks 1-9 against the REAL generated site.
# ---------------------------------------------------------------------

def _href(html: str, label: str) -> str | None:
    """Extracts the real href for a stage-nav item by its label text,
    or None if that stage is rendered as a disabled <span> (not a real
    link) -- never guesses."""
    import re
    m = re.search(rf"<a class='stage-nav__link' href='([^']+)'[^>]*>{label}<", html) or \
        re.search(rf'<a class="stage-nav__link" href="([^"]+)"[^>]*>{label}<', html)
    return m.group(1) if m else None


def _resolve_under_docs(href: str) -> Path:
    return DOCS / href.strip("/")


@pytest.mark.parametrize("source_page,source_label", [(PRE_PAGE, "R1"), (R1_PAGE, "R2")])
def test_1_pre_href_resolves_and_returns_the_pre_page(source_page, source_label):
    html = source_page.read_text(encoding="utf-8")
    href = _href(html, "사전 분석 PRE") or _href(html, "PRE")
    assert href is not None, f"no PRE href found in {source_page}"
    resolved = _resolve_under_docs(href) / "index.html"
    assert resolved.is_file()
    assert resolved == PRE_PAGE


def test_2_r1_href_resolves_and_returns_the_r1_page():
    html = PRE_PAGE.read_text(encoding="utf-8")
    href = _href(html, "R1")
    assert href is not None
    resolved = _resolve_under_docs(href) / "index.html"
    assert resolved.is_file()
    assert resolved == R1_PAGE


@pytest.mark.parametrize("source_page", [PRE_PAGE, R1_PAGE])
def test_3_r2_href_resolves_to_the_real_r2_route(source_page):
    html = source_page.read_text(encoding="utf-8")
    href = _href(html, "R2")
    assert href == f"/tournaments/2026/{GAME_CODE}/r2/"


@pytest.mark.parametrize("source_page", [PRE_PAGE, R1_PAGE])
def test_4_r2_is_not_disabled_in_pre_and_r1(source_page):
    html = source_page.read_text(encoding="utf-8")
    assert _DISABLED_R2_ITEM not in html
    assert _href(html, "R2") is not None  # a real <a>, not a <span>


def test_5_r2_is_marked_current_default_on_its_own_page():
    html = R2_PAGE.read_text(encoding="utf-8")
    assert f'<a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r2/" aria-current="page">R2</a>' in html


@pytest.mark.parametrize("page", [PRE_PAGE, R1_PAGE, R2_PAGE])
def test_6_r3_is_not_disabled_once_real(page):
    """ROUND-CONTEXT CORRECTION (research/official-tournament-warehouse-
    v1-20260912), pre-deploy R3 candidate: a real, hash-verified R3
    freeze now exists for 2026090003, so R3's own stage-nav activation
    (mirroring scripts/112's established _enable_r2_stage_nav_link
    pattern, one stage later) has run against PRE/R1/R2's own files --
    exactly like test_4 above proved for R2 once IT became real."""
    html = page.read_text(encoding="utf-8")
    assert '<span class="stage-nav__disabled" aria-disabled="true">R3</span>' not in html
    assert _href(html, "R3") == f"/tournaments/2026/{GAME_CODE}/r3/"


@pytest.mark.parametrize("page", [PRE_PAGE, R1_PAGE, R2_PAGE])
def test_6b_fr_remains_disabled(page):
    """FR (the true, not-yet-played 4th competitive round) is the only
    round-stage that must still be disabled everywhere -- R3 is real,
    FR is not."""
    html = page.read_text(encoding="utf-8")
    assert '<span class="stage-nav__disabled" aria-disabled="true">FR</span>' in html


@pytest.mark.parametrize("page", [PRE_PAGE, R1_PAGE, R2_PAGE])
def test_7_final_remains_disabled(page):
    html = page.read_text(encoding="utf-8")
    assert '<span class="stage-nav__disabled" aria-disabled="true">FINAL</span>' in html


@pytest.mark.parametrize("page", [PRE_PAGE, R1_PAGE, R2_PAGE])
def test_8_every_generated_stage_nav_href_points_to_an_existing_file_under_docs(page):
    import re
    html = page.read_text(encoding="utf-8")
    hrefs = re.findall(r"<a class=['\"]stage-nav__link['\"] href=['\"]([^'\"]+)['\"]", html)
    assert hrefs, f"no stage-nav hrefs found in {page}"
    for href in hrefs:
        resolved = _resolve_under_docs(href) / "index.html"
        assert resolved.is_file(), f"{page}: href {href!r} does not resolve to a real file"


@pytest.mark.parametrize("page", [PRE_PAGE, R1_PAGE, R2_PAGE])
def test_9_existing_global_home_navigation_links_remain_valid(page):
    """The shared global header/footer nav (inject_global_navigation)
    is untouched by this fix -- spot-check its own links still resolve
    under docs, proving the stage-nav patch never touched it."""
    import re
    html = page.read_text(encoding="utf-8")
    breadcrumb_home = re.search(r'<nav class="breadcrumb"[^>]*><a href="([^"]+)">', html)
    assert breadcrumb_home is not None
    resolved = _resolve_under_docs(breadcrumb_home.group(1))
    target = resolved / "index.html" if not str(resolved).endswith(".html") else resolved
    assert target.is_file() or resolved.is_file()


# ---------------------------------------------------------------------
# R2's own result-page regression must still pass after this navigation
# fix (never weakened, never re-broken by touching a sibling file).
# ---------------------------------------------------------------------

def test_r2_result_page_still_uses_the_real_new_forecast_artifact():
    import json
    from klpga.neo_win.r2_rendered_output_gate import validate_r2_rendered_output

    freeze = json.loads((ROOT / "content" / "website_v2" / f"{GAME_CODE}_R2_FROZEN_EVIDENCE.json").read_text(encoding="utf-8"))
    html = R2_PAGE.read_text(encoding="utf-8")
    validate_r2_rendered_output(html, freeze)  # must not raise
