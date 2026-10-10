"""Tests for build_home() in scripts/build_tournament_archive_and_hj_scaffold.py
-- the root docs/index.html for the current tournament (HJ 2026100004).
Covers the operator's "homepage completion" instructions: main message,
short Stableford explanation, dynamic (never hardcoded) Top-5 preview,
no internal jargon, no fabricated 0-100 score."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

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
    """This PRE-era content only renders via build_home_pre_fallback()
    now -- build_home() itself has moved on to mirroring the real
    current stage (R2/R3) now that that evidence exists; see
    test_home_stage_mirror.py for that path's own coverage."""
    mod = _load_module()
    html = mod.build_home_pre_fallback()
    for term in ("알바트로스 +8", "이글 +5", "버디 +2", "파 0", "보기 -1", "더블보기 이상 -3"):
        assert term in html
    positions = [html.find(t) for t in ("알바트로스 +8", "이글 +5", "버디 +2", "파 0", "보기 -1", "더블보기 이상 -3")]
    assert positions == sorted(positions), "scores must render +8 -> +5 -> +2 -> 0 -> -1 -> -3"


def test_top5_preview_matches_frozen_snapshot_order_and_links_to_pre():
    mod = _load_module()
    html = mod.build_home_pre_fallback()
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
    and 박조은 0806(A) (2R) must never show a public rank or probability.
    (PRE-fallback path -- see module docstring on test_short_stableford_
    scoring_explanation_present for why this no longer goes through
    build_home() directly.)"""
    mod = _load_module()
    html = mod.build_home_pre_fallback()
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
    html = mod.build_home_pre_fallback()
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

    home_html = home_mod.build_home_pre_fallback()
    pre_html = pre_mod.build()["html"]
    for name in ("성아진", "박조은 0806(A)", "김민서3", "이지유 0901(A)", "서교림", "김민솔"):
        home_row = _row_html_for(home_html, name)
        pre_row = _row_html_for(pre_html, name)
        assert home_row.count("데이터 부족") == pre_row.count("데이터 부족"), (
            f"{name}: HOME and PRE must apply the identical masking rule"
        )


def _load_pre_module():
    import importlib.util
    import sys as _sys

    spec = importlib.util.spec_from_file_location(
        "pre_225_from_home_video_test", Path(__file__).parent.parent / "scripts" / "225_build_hj_2026100004_pre_page.py"
    )
    module = importlib.util.module_from_spec(spec)
    _sys.modules["pre_225_from_home_video_test"] = module
    spec.loader.exec_module(module)
    return module


def test_home_video_section_present_with_same_source_as_pre():
    """PRE->HOME PARITY FIX: while the tournament hasn't started, HOME
    *is* the current PRE screen, so it must carry the identical video
    section PRE does -- same src, reusing the same shared generator
    (klpga.website_v2.hj_pre_video_section), not a separately-authored
    HOME-only component."""
    home_mod = _load_module()
    pre_mod = _load_pre_module()

    home_html = home_mod.build_home_pre_fallback()
    pre_html = pre_mod.build()["html"]

    assert home_html.count("<video") == 1
    assert "id='final-video'" in home_html
    assert "/assets/tournaments/2026100004/neo-golf-data-pre.mp4" in home_html
    assert "controls" in home_html

    import re

    home_src = re.search(r"<video[^>]*src='([^']+)'", home_html).group(1)
    pre_src = re.search(r"<video[^>]*src='([^']+)'", pre_html).group(1)
    assert home_src == pre_src, "HOME and PRE must point at the exact same video asset"


def test_home_video_section_positioned_between_stableford_explanation_and_neo_verification():
    mod = _load_module()
    html = mod.build_home_pre_fallback()
    stableford_idx = html.find("알바트로스 +8")
    video_idx = html.find("<video")
    neo_verification_idx = html.find('id="neo-verification"')
    assert stableford_idx != -1 and video_idx != -1 and neo_verification_idx != -1
    assert stableford_idx < video_idx < neo_verification_idx, (
        "HOME order must be: Stableford 설명 -> NEO GOLF DATA 영상 -> NEO 검증 table, matching PRE"
    )


def test_home_stableford_and_neo_verification_content_unaffected_by_video_addition():
    """Adding the video section must not change the existing Stableford
    explanation or NEO 검증/player data content -- only insert between them."""
    mod = _load_module()
    html = mod.build_home_pre_fallback()
    for term in ("알바트로스 +8", "이글 +5", "버디 +2", "파 0", "보기 -1", "더블보기 이상 -3"):
        assert term in html
    assert html.count("데이터 부족") > 0
    assert "서교림" in html and "#1" in html


def test_home_video_asset_file_exists_on_disk():
    mod = _load_module()
    video_path = mod.ROOT / "docs" / "assets" / "tournaments" / "2026100004" / "neo-golf-data-pre.mp4"
    assert video_path.is_file(), f"missing video asset: {video_path}"
    assert video_path.stat().st_size > 0


def test_home_video_survives_a_fresh_rebuild():
    """Regression lock for the structural gap this fix closes: a fresh,
    independent build_home() call (not reusing any cached/previous
    output) must always include the video -- it is generated inline by
    the shared hj_pre_video_section_html(), not patched onto a specific
    file after the fact, so it cannot be silently dropped by a future
    rebuild the way it was before this fix."""
    mod = _load_module()
    html_first = mod.build_home_pre_fallback()
    html_second = mod.build_home_pre_fallback()
    assert html_first == html_second
    assert html_first.count("<video") == 1


def test_stale_hana_builder_still_cannot_clobber_home_after_video_parity_fix():
    """Ensures the daa8a85 HOME clobber guard (game-code-aware
    ownership check) still holds after this change -- the video parity
    fix must never weaken it."""
    import importlib.util

    from klpga.website_v2.home_ownership_guard import HomeOwnershipError

    repo_root = Path(__file__).resolve().parents[2]
    real_docs_index = repo_root / "docs" / "index.html"

    import hashlib

    sha_before = hashlib.sha256(real_docs_index.read_text(encoding="utf-8").encode("utf-8")).hexdigest()

    scripts_dir = Path(__file__).parent.parent / "scripts"
    spec = importlib.util.spec_from_file_location("_build_home_page_video_parity_test", scripts_dir / "156_build_home_page.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with pytest.raises(HomeOwnershipError, match="game_code"):
        module.build()

    sha_after = hashlib.sha256(real_docs_index.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    assert sha_after == sha_before


# ---------------------------------------------------------------------------
# HOME STAGE SYNC (R2/R3 mirroring): once real R2/R3 evidence exists, HOME
# must mirror that stage's own already-published page verbatim -- the
# operator's "2R 페이지가 홈화면이 아닌데? 영상도 없고" report that HOME had
# stayed frozen on hand-edited R1-era content with no video, long after R2
# concluded and R3 (with its own video) was published.
# ---------------------------------------------------------------------------

def test_hj_current_stage_resolves_to_fr_once_r3_official_and_fr_forecast_evidence_exist():
    mod = _load_module()
    assert (mod.CONTENT / "HJ_2026100004_R3_OFFICIAL_RESULTS_V1.json").is_file()
    assert (mod.CONTENT / "HJ_2026100004_POST_R3_STABLEFORD_MONTE_CARLO_V1_RESULTS.json").is_file()
    assert mod.hj_current_stage() == "fr"


def test_hj_current_stage_resolves_to_r3_when_only_r2_and_r3_forecast_evidence_exists(tmp_path, monkeypatch):
    """Isolated regression check for the earlier stage transition (R2
    official + pre-R3 forecast, no R3-official/FR-forecast evidence
    yet): must still resolve to 'r3', proving that code path still
    works even though the real repo has since advanced past it."""
    mod = _load_module()
    import shutil
    for name in (
        "HJ_2026100004_R2_OFFICIAL_RESULTS_AND_CUT_V1.json",
        "HJ_2026100004_POST_R2_STABLEFORD_MONTE_CARLO_V1_RESULTS.json",
    ):
        shutil.copy(mod.CONTENT / name, tmp_path / name)
    monkeypatch.setattr(mod, "CONTENT", tmp_path)
    assert mod.hj_current_stage() == "r3"


def test_build_home_mirrors_the_real_fr_page_verbatim():
    mod = _load_module()
    home_html = mod.build_home()
    fr_path = mod.TOURNAMENTS_DIR / mod.HJ_GAME_CODE / "fr" / "index.html"
    fr_html = fr_path.read_text(encoding="utf-8")
    fr_main = fr_html.split("<main>", 1)[1].rsplit("</main>", 1)[0]
    assert fr_main in home_html, "HOME must embed FR's own <main> body verbatim, not a re-derived copy"


def test_build_home_mirror_has_no_video_at_fr_stage():
    """The FR forecast page carries no video (only R3's page does) --
    HOME mirroring FR must not fabricate one either."""
    mod = _load_module()
    html = mod.build_home()
    assert "<video" not in html


def test_build_home_mirror_uses_homes_own_global_nav_not_r3s():
    """The embedded main body's own header/nav must be discarded --
    HOME keeps its own <head> and global nav with '홈' marked active,
    never R3's '대회 기록'-active header stacked on top."""
    mod = _load_module()
    html = mod.build_home()
    assert html.count("<header") == 1
    assert html.count('<nav class="neo-global-nav"') == 1
    nav = re.search(r"<nav class=\"neo-global-nav\".*?</nav>", html).group(0)
    assert '<a href="/" class="is-active" aria-current="page">홈</a>' in nav


def test_build_home_mirror_preserves_ownership_markers():
    mod = _load_module()
    html = mod.build_home()
    assert 'name="neo-home-owner" content="current-tournament-v1"' in html
    assert f'name="neo-home-game-code" content="{mod.HJ_GAME_CODE}"' in html


def test_build_home_mirror_never_exposes_sg_or_top5():
    mod = _load_module()
    html = mod.build_home()
    for forbidden in ("top5", "top5_pct", "strokes_gained", "sg_total", "SG_RAW"):
        assert forbidden not in html


def test_build_home_mirror_covers_all_61_fr_rows():
    mod = _load_module()
    html = mod.build_home()
    assert html.count("<tr>") == 62  # 1 header row + 61 forecast rows


def test_hj_current_stage_falls_back_to_pre_when_no_r2_evidence(tmp_path, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "CONTENT", tmp_path)
    monkeypatch.setattr(mod, "TOURNAMENTS_DIR", tmp_path)
    assert mod.hj_current_stage() == "pre"


def test_hj_stage_main_body_raises_if_resolved_stage_page_is_missing(tmp_path, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "TOURNAMENTS_DIR", tmp_path)
    with pytest.raises(mod.HjHomeStageError):
        mod._hj_stage_main_body("r3")
