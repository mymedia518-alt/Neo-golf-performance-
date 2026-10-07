"""Tests for build_home() in scripts/build_tournament_archive_and_hj_scaffold.py
-- the root docs/index.html for the current tournament (HJ 2026100004).
Covers the operator's "homepage completion" instructions: main message,
short Stableford explanation, dynamic (never hardcoded) Top-5 preview,
no internal jargon, no fabricated 0-100 score."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "build_tournament_archive_and_hj_scaffold.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("archive_hj_home", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["archive_hj_home"] = module
    spec.loader.exec_module(module)
    return module


def test_main_message_present():
    mod = _load_module()
    html = mod.build_home()
    assert "같은 경기력도 Stableford에서는 가치가 달라진다" in html


def test_short_stableford_scoring_explanation_present():
    mod = _load_module()
    html = mod.build_home()
    for term in ("알바트로스 +8", "이글 +5", "버디 +2", "파 0", "보기 -1", "더블보기 이상 -3"):
        assert term in html
    positions = [html.find(t) for t in ("알바트로스 +8", "이글 +5", "버디 +2", "파 0", "보기 -1", "더블보기 이상 -3")]
    assert positions == sorted(positions), "scores must render +8 -> +5 -> +2 -> 0 -> -1 -> -3"


def test_top5_preview_matches_frozen_snapshot_order_and_links_to_pre():
    mod = _load_module()
    html = mod.build_home()
    expected_top5 = ["서교림", "김민솔", "유현조", "박현경", "김민선7"]
    positions = [html.find(name) for name in expected_top5]
    assert all(p != -1 for p in positions)
    assert positions == sorted(positions)
    assert "/tournaments/2026/2026100004/pre/" in html


def test_no_internal_jargon_or_fabricated_score_on_home():
    mod = _load_module()
    html = mod.build_home()
    for forbidden in ("sha256", "CORE", "SUPPORTING", "REJECTED", "Stableford Fit", "parser", "cutoff"):
        assert forbidden not in html
    import re
    assert not re.search(r"#\d+\.\d", html)


def test_home_still_has_neo_home_owner_marker_and_global_nav():
    mod = _load_module()
    html = mod.build_home()
    assert 'name="neo-home-owner" content="current-tournament-v1"' in html
    assert 'class="neo-global-header"' in html


def _row_html_for(html: str, player_name: str) -> str:
    import re
    for row in re.findall(r"<tr>.*?</tr>", html):
        if player_name in row:
            return row
    raise AssertionError(f"row for {player_name!r} not found")


def test_thin_sample_players_rank_and_probabilities_masked_as_data_limited():
    """LIVE HOTFIX: same rounds < 10 masking policy as PRE -- 성아진 (6R)
    and 박조은 0806(A) (2R) must never show a public rank or probability."""
    mod = _load_module()
    html = mod.build_home()
    for name in ("성아진", "박조은 0806(A)", "김민서3", "이지유 0901(A)"):
        row = _row_html_for(html, name)
        assert row.count("데이터 부족") == 4, f"{name} must show 데이터 부족 in all 4 columns, got: {row}"
        assert "#94" not in row and "#106" not in row


def test_frozen_v1_raw_rank_value_unchanged_on_disk():
    mod = _load_module()
    import json
    snapshot_path = mod.CONTENT / "STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    by_name = {r["player_name"]: r for r in snapshot["records"]}
    assert by_name["성아진"]["pre_event_rank"] == 94
    assert by_name["박조은 0806(A)"]["pre_event_rank"] == 106


def test_eligible_players_ranks_unchanged():
    mod = _load_module()
    html = mod.build_home()
    for name, expected_rank in (("서교림", 1), ("김민솔", 2)):
        row = _row_html_for(html, name)
        rank_cell = row.split("Stableford 사전평가'>", 1)[1].split("</td>", 1)[0]
        assert rank_cell.startswith(f"#{expected_rank}")


def test_home_and_pre_enforce_identical_masking_rule():
    """HOME and PRE must mask the exact same set of players identically."""
    import importlib.util
    import sys as _sys
    home_mod = _load_module()
    pre_spec = importlib.util.spec_from_file_location(
        "pre_225_from_home_test", Path(__file__).parent.parent / "scripts" / "225_build_hj_2026100004_pre_page.py"
    )
    pre_mod = importlib.util.module_from_spec(pre_spec)
    _sys.modules["pre_225_from_home_test"] = pre_mod
    pre_spec.loader.exec_module(pre_mod)

    home_html = home_mod.build_home()
    pre_html = pre_mod.build()["html"]
    for name in ("성아진", "박조은 0806(A)", "김민서3", "이지유 0901(A)", "서교림", "김민솔"):
        home_row = _row_html_for(home_html, name)
        pre_row = _row_html_for(pre_html, name)
        assert home_row.count("데이터 부족") == pre_row.count("데이터 부족"), (
            f"{name}: HOME and PRE must apply the identical masking rule"
        )
