"""Tests for the NEO SITE V5 Mission 1 shared design-system V2 API:
global_navigation.navigation_html_v2/inject_global_navigation_v2, and
shell.render_page(design_system=...).

Core contract: the existing V1 path (every currently-live page, six
existing test files) is byte-for-byte unaffected; the new V2 path
produces the HOME V4 ".t-bar" chrome while never altering body content.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2 import global_navigation as nav  # noqa: E402
from klpga.website_v2 import shell  # noqa: E402


# --------------------------------------------------------------- V1 intact


def test_v1_navigation_html_unchanged():
    html = nav.navigation_html("about")
    assert "neo-global-header" in html
    assert "t-bar" not in html


def test_v1_render_page_default_matches_pre_v5_output_shape():
    html = shell.render_page(title="NEO 소개", active_section="about", body_html="<p>hi</p>")
    assert '/assets/neo-site.css' in html
    assert '/assets/neo-design-system.css' not in html
    assert 'class="neo-global-header"' in html
    assert 't-bar' not in html
    assert 'class="home-v4"' not in html


# --------------------------------------------------------------- V2 header


def test_v2_nav_items_are_the_six_home_v4_routes():
    keys = [key for key, _label, _url in nav.DESIGN_SYSTEM_V2_NAV_ITEMS]
    assert keys == ["players", "tournaments", "ranking", "deep-dive", "neo-lab", "about"]


def test_v2_navigation_html_marks_active_section():
    html = nav.navigation_html_v2("about")
    assert '<a href="/about/" class="is-active" aria-current="page">ABOUT</a>' in html
    assert 't-bar' in html and 't-nav' in html


def test_v2_navigation_html_no_active_section_marks_nothing():
    html = nav.navigation_html_v2(None)
    assert "is-active" not in html


# ---------------------------------------------------- inject_global_navigation_v2


def _bare_page(body: str = "<p>content</p>") -> str:
    return f"<!doctype html><html><head><title>x</title></head><body>{body}</body></html>"


def test_inject_v2_adds_home_v4_body_class():
    html = nav.inject_global_navigation_v2(_bare_page())
    assert '<body class="home-v4">' in html


def test_inject_v2_preserves_existing_body_classes():
    html = nav.inject_global_navigation_v2('<html><body class="existing-class"><p>x</p></body></html>')
    assert 'class="existing-class home-v4"' in html


def test_inject_v2_adds_design_system_stylesheet_link():
    html = nav.inject_global_navigation_v2(_bare_page())
    assert '<link rel="stylesheet" href="/assets/neo-design-system.css">' in html


def test_inject_v2_does_not_duplicate_stylesheet_link_if_already_present():
    html = shell_html = (
        '<html><head><link rel="stylesheet" href="/assets/neo-design-system.css"></head>'
        '<body><p>x</p></body></html>'
    )
    result = nav.inject_global_navigation_v2(shell_html)
    assert result.count('href="/assets/neo-design-system.css"') == 1


def test_inject_v2_never_touches_body_content_text():
    body = "<p>정확한 사실 텍스트, 절대 바뀌면 안 됨</p>"
    html = nav.inject_global_navigation_v2(_bare_page(body))
    assert body in html


def test_inject_v2_is_idempotent_on_a_marked_header():
    once = nav.inject_global_navigation_v2(_bare_page(), active_section="about")
    twice = nav.inject_global_navigation_v2(once, active_section="about")
    assert once == twice


def test_inject_v2_refreshes_a_stale_marked_header_to_current_active_section():
    first = nav.inject_global_navigation_v2(_bare_page(), active_section="about")
    refreshed = nav.inject_global_navigation_v2(first, active_section="tournaments")
    assert 'href="/tournaments/" class="is-active"' in refreshed
    assert 'href="/about/" class="is-active"' not in refreshed


# --------------------------------------------------------- render_page v2


def test_render_page_v2_links_both_stylesheets():
    html = shell.render_page(title="NEO 소개", active_section="about", body_html="<p>x</p>", design_system="v2")
    assert '/assets/neo-site.css' in html  # legacy content-area styling preserved
    assert '/assets/neo-design-system.css' in html


def test_render_page_v2_uses_t_bar_header_not_old_header():
    html = shell.render_page(title="NEO 소개", active_section="about", body_html="<p>x</p>", design_system="v2")
    assert 'class="t-bar"' in html
    assert 'class="neo-global-header"' not in html


def test_render_page_v2_body_content_byte_identical_to_v1():
    body = "<section class='page-head'><h1>동일한 콘텐츠</h1></section>"
    v1 = shell.render_page(title="X", active_section="about", body_html=body, design_system="v1")
    v2 = shell.render_page(title="X", active_section="about", body_html=body, design_system="v2")

    def main_of(html: str) -> str:
        start = html.index('<main id="main-content">')
        end = html.index("</main>")
        return html[start:end]

    assert main_of(v1) == main_of(v2)


def test_render_page_rejects_unknown_design_system():
    import pytest
    with pytest.raises(ValueError):
        shell.render_page(title="X", active_section="about", body_html="<p/>", design_system="v3")


def test_render_page_v2_body_has_home_v4_class():
    html = shell.render_page(title="X", active_section="about", body_html="<p/>", design_system="v2")
    assert 'class="home-v4"' in html
