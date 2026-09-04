"""R1 LIVE SUMMARY COPY FIX -- regression tests.

1. The disclaimer sentence "공식 리더보드 + NEO 시뮬레이션 확률(30분
   주기 재계산, 확정된 사실 아님)" is replaced with either "라이브
   업데이트 주기 30분" (fresh snapshot) or, once the P0 STALE-DATA
   freshness gate fix landed, the honest STALE_NOTICE_MARKER when the
   real snapshot on disk is older than the staleness threshold -- the
   last-updated timestamp itself is untouched either way. Which one
   applies to the CURRENT real snapshot is derived the same way the
   generator itself derives it (never hardcoded), so this test does
   not go stale the moment a fresh collection lands.
2. The pinned top-summary "NEO 우승확률 1위" metric (player name +
   percentage) is removed entirely -- but Win% stays in the detailed
   player table, unchanged."""
import datetime
import json
import sys
from pathlib import Path

import importlib.util

SPEC = importlib.util.spec_from_file_location(
    "ok_open_builder", Path(__file__).parents[1] / "scripts" / "84_build_ok_open_pre_website_candidate.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from klpga.website_v2.freshness_gate import STALE_NOTICE_MARKER, is_snapshot_stale  # noqa: E402


def _current_live_cadence_note() -> str:
    snapshot = json.loads(
        (Path(__file__).parents[1] / "content" / "website_v2" / "OK_OPEN_2026_R1_LIVE_SNAPSHOT.json").read_text(encoding="utf-8")
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    if is_snapshot_stale(snapshot.get("collected_at"), now):
        return STALE_NOTICE_MARKER
    return "라이브 업데이트 주기 30분"


def test_disclaimer_sentence_replaced_with_exact_copy():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert _current_live_cadence_note() in html
    assert "공식 리더보드 + NEO 시뮬레이션 확률" not in html
    assert "확정된 사실 아님" not in html
    assert "30분 주기 재계산" not in html


def test_last_updated_timestamp_is_still_present_and_unmodified():
    snapshot = json.loads(
        (Path(__file__).parents[1] / "content" / "website_v2" / "OK_OPEN_2026_R1_LIVE_SNAPSHOT.json").read_text(encoding="utf-8")
    )
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert f"마지막 성공 업데이트(UTC): {snapshot['collected_at']} · {_current_live_cadence_note()}" in html


def test_top_summary_win_probability_metric_is_removed():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert "NEO 우승확률 1위" not in html
    # P0 MODEL SAFETY PATCH: "NEO 예상 컷" is itself a probability output
    # of the same blocked simulation and is now ALSO gated -- so the
    # summary grid has exactly one metric (현재 선두) while blocked, two
    # once LIVE_PROBABILITY_MODEL_STATUS == "VALIDATED".
    grid_start = html.index("r1-live-summary__grid")
    grid_end = html.index("</section>", grid_start)
    grid_html = html[grid_start:grid_end]
    assert "현재 선두" in grid_html
    if builder.MODEL_VALIDATED_FOR_PUBLICATION:
        assert grid_html.count("<div><span class='label'>") == 2
        assert "NEO 예상 컷" in grid_html
    else:
        assert grid_html.count("<div><span class='label'>") == 1
        assert "NEO 예상 컷" not in grid_html


def test_win_pct_column_presence_matches_model_publication_status():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    if builder.MODEL_VALIDATED_FOR_PUBLICATION:
        assert "<th>Win%</th>" in html
    else:
        assert "<th>Win%</th>" not in html


def test_scores_unchanged_and_win_probability_withheld_by_the_model_gate():
    import json

    snapshot = json.loads(
        (Path(__file__).parents[1] / "content" / "website_v2" / "OK_OPEN_2026_R1_LIVE_SNAPSHOT.json").read_text(encoding="utf-8")
    )
    leader = snapshot["player_table"][0]
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    th_idx = html.index(f"<span class='player'>{leader['player_name']}</span>")
    row_end = html.index("</tr>", th_idx)
    row_tail = html[th_idx:row_end]
    if leader.get("total_under_par_display"):
        assert str(leader["total_under_par_display"]) in row_tail  # factual score: always shown
    if leader.get("win_pct") is not None:
        # P0 MODEL SAFETY PATCH: win_pct is a blocked probability output
        # -- omitted, never rendered, while the model is not validated.
        if builder.MODEL_VALIDATED_FOR_PUBLICATION:
            assert f"{leader['win_pct']:.1f}%" in row_tail
        else:
            assert f"{leader['win_pct']:.1f}%" not in row_tail
