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


def test_desktop_and_mobile_both_carry_the_identity_block_for_every_top150_row():
    html = _built_html()
    top150 = mod._load_top150()
    n = top150["confirmed_rank_count"]
    # one desktop row + one mobile row per confirmed Top150 player.
    assert n > 0
    assert html.count('class="neo-player-identity__name"') == n * 2


def test_verified_sponsor_renders_for_a_known_active_confirmed_player():
    html = _built_html()
    idx = html.index('neo-player-identity__name">강가율<')
    window = html[idx : idx + 200]
    assert 'class="neo-player-identity__sponsor">세기P&amp;C<' in window


def test_no_placeholder_sponsor_values_anywhere_on_the_page():
    html = _built_html()
    for placeholder in ("unknown", "Unknown", "미확인", "확인불가", "N/A", "TBD"):
        assert f'class="neo-player-identity__sponsor">{placeholder}<' not in html


def test_sponsor_source_is_real_top150_data_not_fabricated():
    top150 = mod._load_top150()
    sponsors = [p["official_sponsor"] for p in top150["players"] if p.get("official_sponsor")]
    assert sponsors, "expected at least some real sponsor evidence among the Top150"
    for sponsor in sponsors:
        assert isinstance(sponsor, str) and sponsor


def test_board_population_is_k_rank_top150_only():
    """NEO SITE V5 2026-09-07 simplification: no evidence-based
    classification, no 546-player historical population -- only current
    official K-Ranking, ranks 1-150."""
    import inspect
    source = inspect.getsource(mod)
    assert "ACTIVE_KLPGA_TOUR_PLAYER_MASTER" not in source
    assert "join_home_rows(" not in source  # the call itself, not incidental prose
    top150 = mod._load_top150()
    for p in top150["players"]:
        assert p["rank"] <= 150
