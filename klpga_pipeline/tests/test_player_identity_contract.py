"""Tests for src/klpga/website_v2/player_identity.py -- the shared,
site-wide Player Identity / sponsor rendering contract (NEO SITE V5
architecture correction #2)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2 import player_identity as pi  # noqa: E402


def test_verified_sponsor_renders_directly_below_name():
    html = pi.render_player_identity("김선수", "테스트스폰서")
    name_idx = html.index(f'class="{pi.PLAYER_IDENTITY_NAME_CLASS}"')
    sponsor_idx = html.index(f'class="{pi.PLAYER_IDENTITY_SPONSOR_CLASS}"')
    assert name_idx < sponsor_idx  # name slot precedes sponsor slot in DOM order
    assert "테스트스폰서" in html
    assert "김선수" in html


def test_missing_sponsor_renders_blank_but_slot_present():
    html = pi.render_player_identity("김선수", None)
    assert f'class="{pi.PLAYER_IDENTITY_SPONSOR_CLASS}"' in html  # structurally present
    assert f'<span class="{pi.PLAYER_IDENTITY_SPONSOR_CLASS}"></span>' in html  # blank content


def test_empty_string_sponsor_renders_blank_but_slot_present():
    html = pi.render_player_identity("김선수", "")
    assert f'<span class="{pi.PLAYER_IDENTITY_SPONSOR_CLASS}"></span>' in html


def test_whitespace_only_sponsor_renders_blank():
    assert pi.resolve_sponsor_text("   ") == ""


def test_no_placeholder_strings_ever_rendered():
    for placeholder in ("unknown", "Unknown", "UNKNOWN", "미확인", "확인불가", "N/A", "n/a",
                        "-", "--", "—", "None", "null", "TBD"):
        html = pi.render_player_identity("김선수", placeholder)
        assert f'<span class="{pi.PLAYER_IDENTITY_SPONSOR_CLASS}"></span>' in html, (
            f"placeholder {placeholder!r} leaked into rendered sponsor slot"
        )


def test_never_guesses_a_company_name_for_unresolved_identity():
    html = pi.render_player_identity(None, None)
    assert "—" in html  # unresolved name renders an em dash, not a guessed name
    assert f'<span class="{pi.PLAYER_IDENTITY_SPONSOR_CLASS}"></span>' in html


def test_html_escaping_applied_to_both_slots():
    html = pi.render_player_identity("<script>alert(1)</script>", "<b>Evil</b>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<b>Evil</b>" not in html


def test_container_wraps_both_slots_by_default():
    html = pi.render_player_identity("김선수", "테스트스폰서")
    assert html.startswith(f'<span class="{pi.PLAYER_IDENTITY_CONTAINER_CLASS}">')
    assert html.endswith("</span>")


def test_container_can_be_omitted_for_callers_with_their_own_wrapper():
    html = pi.render_player_identity("김선수", "테스트스폰서", container_class=None)
    assert f'class="{pi.PLAYER_IDENTITY_CONTAINER_CLASS}"' not in html
    assert f'class="{pi.PLAYER_IDENTITY_NAME_CLASS}"' in html
    assert f'class="{pi.PLAYER_IDENTITY_SPONSOR_CLASS}"' in html


def test_custom_tag_and_class_names_still_produce_two_present_slots():
    html = pi.render_player_identity(
        "김선수", None, tag="div", name_class="player", sponsor_class="sponsor", container_class=None,
    )
    assert '<div class="player">김선수</div>' in html
    assert '<div class="sponsor"></div>' in html


def test_resolve_sponsor_text_is_idempotent_on_real_values():
    assert pi.resolve_sponsor_text("세기P&C") == "세기P&C"
    assert pi.resolve_sponsor_text(None) == ""
    assert pi.resolve_sponsor_text("") == ""
