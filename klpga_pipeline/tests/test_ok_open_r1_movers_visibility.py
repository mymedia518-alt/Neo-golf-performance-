"""NEO PRODUCTION UI PATCH -- "기대 이상/이하 (오늘 스코어)" temporary
hide regression tests.

The SG field-average -> score-to-par baseline conversion behind
vs_expected_strokes is still under Red Team audit, so the two
strokes-based mover lists are withheld from the public R1 page. This
must be a presentation-only change: the underlying computation
(compute_neo_movers) and the snapshot's own neo_movers.beat_expectation
/missed_expectation data must be completely unaffected -- only the
generated HTML omits them. Win% 상승/하락 (independently validated)
and the detailed table's Win% column must be unaffected."""
import json
from pathlib import Path

import importlib.util

SPEC = importlib.util.spec_from_file_location(
    "ok_open_builder", Path(__file__).parents[1] / "scripts" / "84_build_ok_open_pre_website_candidate.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

CONTENT = Path(__file__).parents[1] / "content" / "website_v2"
R1_LIVE_SNAPSHOT = CONTENT / "OK_OPEN_2026_R1_LIVE_SNAPSHOT.json"


def test_expected_vs_actual_movers_are_hidden_from_the_public_page():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert "기대 이상" not in html
    assert "기대 이하" not in html
    assert "beat_expectation" not in html
    assert "missed_expectation" not in html


def test_win_pct_movers_and_cut_risk_remain_visible():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert "Win% 상승" in html
    assert "Win% 하락" in html
    assert "컷 통과 위험" in html


def test_underlying_neo_movers_data_and_computation_are_unaffected():
    # The raw snapshot itself -- the actual computed
    # beat_expectation/missed_expectation values -- must still exist
    # untouched on disk; only the HTML rendering omits them.
    snapshot = json.loads(R1_LIVE_SNAPSHOT.read_text(encoding="utf-8"))
    movers = snapshot.get("neo_movers") or {}
    assert "beat_expectation" in movers
    assert "missed_expectation" in movers
    assert movers["beat_expectation"], "fixture assumption: real data has at least one beat_expectation entry"


def test_top_summary_win_probability_metric_still_removed():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert "NEO 우승확률 1위" not in html


def test_live_copy_still_replaced():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert "라이브 업데이트 주기 30분" in html
    assert "공식 리더보드 + NEO 시뮬레이션" not in html


def test_win_pct_column_and_win_delta_still_in_detailed_table():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert "<th>Win%</th>" in html
    assert "<th>PRE 대비 Win Δ</th>" in html


def test_affiliation_still_preserved_and_never_fabricated():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert "<span class='player'>양효진</span><span class='sponsor'>대보건설</span>" in html
    idx = html.find("오수민 0809(A)")
    assert idx != -1
    assert "대방건설" not in html[idx : idx + 400]
