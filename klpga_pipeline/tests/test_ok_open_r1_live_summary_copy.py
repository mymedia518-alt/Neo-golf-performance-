"""R1 LIVE SUMMARY COPY FIX -- regression tests.

1. The disclaimer sentence "공식 리더보드 + NEO 시뮬레이션 확률(30분
   주기 재계산, 확정된 사실 아님)" is replaced with exactly "라이브
   업데이트 주기 30분" -- the last-updated timestamp itself is
   untouched.
2. The pinned top-summary "NEO 우승확률 1위" metric (player name +
   percentage) is removed entirely -- but Win% stays in the detailed
   player table, unchanged."""
from pathlib import Path

import importlib.util

SPEC = importlib.util.spec_from_file_location(
    "ok_open_builder", Path(__file__).parents[1] / "scripts" / "84_build_ok_open_pre_website_candidate.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def test_disclaimer_sentence_replaced_with_exact_copy():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert "라이브 업데이트 주기 30분" in html
    assert "공식 리더보드 + NEO 시뮬레이션 확률" not in html
    assert "확정된 사실 아님" not in html
    assert "30분 주기 재계산" not in html


def test_last_updated_timestamp_is_still_present_and_unmodified():
    import json

    snapshot = __import__("json").loads(
        (Path(__file__).parents[1] / "content" / "website_v2" / "OK_OPEN_2026_R1_LIVE_SNAPSHOT.json").read_text(encoding="utf-8")
    )
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert f"마지막 성공 업데이트(UTC): {snapshot['collected_at']} · 라이브 업데이트 주기 30분" in html


def test_top_summary_win_probability_metric_is_removed():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert "NEO 우승확률 1위" not in html
    # the summary grid now has exactly two metrics: leader + expected cut
    grid_start = html.index("r1-live-summary__grid")
    grid_end = html.index("</section>", grid_start)
    grid_html = html[grid_start:grid_end]
    assert grid_html.count("<div><span class='label'>") == 2
    assert "현재 선두" in grid_html
    assert "NEO 예상 컷" in grid_html


def test_win_pct_column_remains_in_the_detailed_player_table():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert "<th>Win%</th>" in html
    table_start = html.index("<table class='data'>")
    table_html = html[table_start : html.index("</table>", table_start)]
    assert "%" in table_html


def test_scores_and_probabilities_unchanged_by_the_copy_fix():
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
        assert str(leader["total_under_par_display"]) in row_tail
    if leader.get("win_pct") is not None:
        assert f"{leader['win_pct']:.1f}%" in row_tail
