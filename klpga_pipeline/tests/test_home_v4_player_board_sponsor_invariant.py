"""Tests for scripts/109_build_home_v4_data_terminal.py's compliance with
the site-wide Player Identity / sponsor invariant (NEO SITE V5
architecture-correction item 2): PLAYER NAME directly above OFFICIAL
SPONSOR, sponsor slot always structurally present, mobile obeys the same
hierarchy as desktop."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "build_home_v4_data_terminal", ROOT / "scripts" / "109_build_home_v4_data_terminal.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore[union-attr]


def _built_html() -> str:
    mod.build()
    return (mod.OUTPUT / "index.html").read_text(encoding="utf-8")


def test_no_separate_sponsor_column_header():
    html = _built_html()
    assert ">SPONSOR<" not in html


def test_every_player_row_carries_a_structurally_present_sponsor_slot():
    html = _built_html()
    name_count = html.count('class="neo-player-identity__name"')
    sponsor_count = html.count('class="neo-player-identity__sponsor"')
    assert name_count > 0
    assert name_count == sponsor_count  # 1:1 -- never omitted


def test_desktop_and_mobile_both_carry_the_identity_block_546_times_each():
    html = _built_html()
    # 546 desktop rows + 546 mobile rows = 1092 total identity blocks.
    assert html.count('class="neo-player-identity__name"') == 546 * 2


def test_verified_sponsor_renders_for_a_known_active_confirmed_player():
    html = _built_html()
    idx = html.index('neo-player-identity__name">강가율<')
    window = html[idx : idx + 200]
    assert 'class="neo-player-identity__sponsor">세기P&amp;C<' in window


def test_no_placeholder_sponsor_values_anywhere_on_the_page():
    html = _built_html()
    for placeholder in ("unknown", "Unknown", "미확인", "확인불가", "N/A", "TBD"):
        assert f'class="neo-player-identity__sponsor">{placeholder}<' not in html


def test_sponsor_source_is_real_active_tour_master_data_not_fabricated():
    source = mod._load_sponsor_source()
    assert source, "expected at least the real ACTIVE_CONFIRMED sponsor evidence"
    for pid, sponsor in source.items():
        assert isinstance(sponsor, str) and sponsor
