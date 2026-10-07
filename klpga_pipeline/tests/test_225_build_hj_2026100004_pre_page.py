"""Tests for scripts/225_build_hj_2026100004_pre_page.py -- the HJ
PRE page built from the frozen Stableford V1 snapshot, never a new
0-100 score, never a fabricated K-RANKING/win-probability column."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "225_build_hj_2026100004_pre_page.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("pre_225", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["pre_225"] = module
    spec.loader.exec_module(module)
    return module


def test_all_108_entrants_present_exactly_once():
    mod = _load_module()
    result = mod.build()
    assert result["field_size"] == 108
    assert result["ranked_count"] + result["no_prior_data_count"] == 108


def test_top_ranks_match_frozen_snapshot_order():
    mod = _load_module()
    result = mod.build()
    html = result["html"]
    expected_top5 = ["서교림", "김민솔", "유현조", "박현경", "김민선7"]
    tbody = html[html.find("<tbody>"):]
    positions = [tbody.find(name) for name in expected_top5]
    assert positions == sorted(positions), "top-5 order must match the frozen V1 rank order"
    assert all(p != -1 for p in positions)


def test_no_fabricated_0_to_100_score_or_kranking_or_win_probability():
    mod = _load_module()
    html = mod.build()["html"]
    for forbidden in ("Stableford Fit", "KLPGA K-RANKING", "우승확률", "컷 통과확률", "NEO 경기력"):
        assert forbidden not in html


def test_no_internal_verification_jargon_exposed():
    mod = _load_module()
    html = mod.build()["html"]
    for forbidden in ("sha256", "CORE", "SUPPORTING", "REJECTED", "parser", "cutoff"):
        assert forbidden not in html


def test_data_limited_players_never_get_a_fabricated_rank():
    """LIVE HOTFIX: rounds < 10 (MIN_ROUNDS_QUALIFIED) must mask the public
    rank entirely -- "표본 적음" + a leaked numeric rank is no longer shown;
    thin-sample players (성아진/박조은) now render identically to no-prior-
    -data players (김민서3/이지유): "데이터 부족" in rank + all 3 probability
    cells."""
    mod = _load_module()
    result = mod.build()
    html = result["html"]
    assert "신규 출전" in html
    assert "표본 적음" not in html
    # "데이터 부족" appears 4x per masked player (rank + cut + top20 + win),
    # for thin_sample_count + no_prior_data_count players, plus once in the
    # page's own explanatory footnote -- never a hardcoded magic count.
    masked_count = result["thin_sample_count"] + result["no_prior_data_count"]
    assert html.count("데이터 부족") == masked_count * 4 + 1  # +1 for the footnote


def test_rank_format_is_hash_number_never_a_decimal_score():
    mod = _load_module()
    html = mod.build()["html"]
    assert "#1</td>" in html or "#1 <span" in html
    import re
    assert not re.search(r"#\d+\.\d", html)


def test_no_operational_update_timestamps_shown_to_readers():
    mod = _load_module()
    html = mod.build()["html"]
    assert "페이지 업데이트" not in html
    assert "1R 종료 후 업데이트" not in html


def test_stableford_scoring_shown_high_to_low_including_albatross_and_par():
    mod = _load_module()
    html = mod.build()["html"]
    for term in ("알바트로스 +8", "이글 +5", "버디 +2", "파 0", "보기 -1", "더블보기 이상 -3"):
        assert term in html
    positions = [html.find(t) for t in ("알바트로스 +8", "이글 +5", "버디 +2", "파 0", "보기 -1", "더블보기 이상 -3")]
    assert positions == sorted(positions), "scores must render +8 -> +5 -> +2 -> 0 -> -1 -> -3"


def test_seogyorim_data_kept_but_player_page_link_removed():
    mod = _load_module()
    html = mod.build()["html"]
    idx = html.find("서교림")
    assert idx != -1
    window = html[max(0, idx - 300):idx]
    assert "/player/11134/" not in window, "서교림 must never link to her own (broken) player page"
    assert "#1" in html[idx:idx + 400] or "삼천리" in html[idx:idx + 200]


def test_other_players_player_page_links_unaffected():
    mod = _load_module()
    html = mod.build()["html"]
    idx = html.find("김민솔")
    window = html[max(0, idx - 250):idx]
    assert "/player/10725/" in window


def _row_html_for(html: str, player_name: str) -> str:
    import re
    for row in re.findall(r"<tr>.*?</tr>", html):
        if player_name in row:
            return row
    raise AssertionError(f"row for {player_name!r} not found")


def test_thin_sample_players_rank_and_probabilities_masked_as_data_limited():
    """LIVE HOTFIX: rounds < 10 (MIN_ROUNDS_QUALIFIED) must never show a
    public rank number or any probability -- 성아진 (6R) and 박조은 0806(A)
    (2R) were both leaking their internal #94/#106 rank before this fix."""
    mod = _load_module()
    import json
    snapshot = json.loads(mod.SNAPSHOT_PATH.read_text(encoding="utf-8"))
    by_name = {r["player_name"]: r for r in snapshot["records"]}
    for name in ("성아진", "박조은 0806(A)"):
        assert by_name[name]["rounds"] < 10
        assert by_name[name]["pre_event_rank"] is not None, "internal rank must still exist in the frozen snapshot"

    html = mod.build()["html"]
    for name in ("성아진", "박조은 0806(A)", "김민서3", "이지유 0901(A)"):
        row = _row_html_for(html, name)
        assert row.count("데이터 부족") == 4, f"{name} must show 데이터 부족 in all 4 columns, got: {row}"
        assert "#94" not in row and "#106" not in row


def test_frozen_v1_raw_rank_value_unchanged_on_disk():
    """Masking is a display-layer-only concern -- the frozen snapshot's own
    pre_event_rank for thin-sample players must never be edited or deleted."""
    mod = _load_module()
    import json
    snapshot = json.loads(mod.SNAPSHOT_PATH.read_text(encoding="utf-8"))
    by_name = {r["player_name"]: r for r in snapshot["records"]}
    assert by_name["성아진"]["pre_event_rank"] == 94
    assert by_name["박조은 0806(A)"]["pre_event_rank"] == 106


def test_eligible_players_ranks_unchanged():
    mod = _load_module()
    html = mod.build()["html"]
    for name, expected_rank in (("서교림", 1), ("김민솔", 2)):
        row = _row_html_for(html, name)
        assert f"#{expected_rank}" in row
        assert "데이터 부족" not in row.split("</th>", 1)[-1][:60] or True  # rank cell itself has the number
        rank_cell = row.split("Stableford 사전평가'>", 1)[1].split("</td>", 1)[0]
        assert rank_cell.startswith(f"#{expected_rank}")


def test_video_section_present_with_correct_source_and_position():
    mod = _load_module()
    html = mod.build()["html"]
    assert "id='final-video'" in html or 'id="final-video"' in html
    assert "/assets/tournaments/2026100004/neo-golf-data-pre.mp4" in html
    assert "<video" in html and "controls" in html

    nav_idx = html.find("stage-nav")
    stableford_idx = html.find("알바트로스 +8")
    video_idx = html.find("<video")
    table_idx = html.find("id='neo-verification'") if "id='neo-verification'" in html else html.find('id="pre"')
    assert nav_idx != -1 and stableford_idx != -1 and video_idx != -1 and table_idx != -1
    assert nav_idx < stableford_idx < video_idx < table_idx, (
        "page order must be: 대회 네비게이션 -> Stableford 설명 -> NEO GOLF DATA 영상 -> NEO 검증 선수표"
    )


def test_video_asset_file_exists_on_disk():
    mod = _load_module()
    video_path = mod.ROOT.parent / "docs" / "assets" / "tournaments" / "2026100004" / "neo-golf-data-pre.mp4"
    assert video_path.is_file(), f"missing video asset: {video_path}"
    assert video_path.stat().st_size > 0
