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
