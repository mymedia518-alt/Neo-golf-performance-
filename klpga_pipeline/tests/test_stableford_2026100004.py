"""Tests for the NEO HJ 2026 (gameCode 2026100004) Stableford build.

Covers the one piece that could actually be implemented and run for real
this turn (stableford_scoring.py, pure arithmetic over the official point
table) plus the guards on the blocked pieces (backtest, Monte Carlo) and
the Red Team checklist's own structural checks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "klpga_pipeline" / "src"))

from klpga.website_v2.stableford_scoring import (  # noqa: E402
    HoleOutcomeCounts, HoleOutcomeProbabilities, SCORING_TABLE, expected_round_points,
)
from klpga.website_v2.stableford_backtest import (  # noqa: E402
    BacktestBlockedError, BacktestInputs, run_blind_backtest,
)
from klpga.website_v2.stableford_monte_carlo import (  # noqa: E402
    MonteCarloBlockedError, MonteCarloInputs, run_monte_carlo,
)
from klpga.website_v2.stableford_redteam import run_redteam  # noqa: E402


def test_official_scoring_table_matches_relayed_values():
    assert SCORING_TABLE == {
        "albatross": 8, "eagle": 5, "birdie": 2, "par": 0, "bogey": -1, "double_or_worse": -3,
    }


def test_hole_outcome_counts_total_points_worked_example():
    # 1 eagle, 3 birdies, 12 pars, 2 bogeys -- 18 holes
    counts = HoleOutcomeCounts(eagle=1, birdie=3, par=12, bogey=2)
    assert counts.total_holes == 18
    assert counts.total_points() == 1 * 5 + 3 * 2 + 12 * 0 + 2 * -1
    assert counts.total_points() == 9


def test_hole_outcome_probabilities_must_sum_to_one():
    with pytest.raises(ValueError):
        HoleOutcomeProbabilities(birdie=0.5, par=0.3)  # sums to 0.8


def test_hole_outcome_probabilities_rejects_out_of_range():
    with pytest.raises(ValueError):
        HoleOutcomeProbabilities(birdie=1.5, par=-0.5)


def test_expected_points_official_formula():
    p = HoleOutcomeProbabilities(eagle=0.02, birdie=0.20, par=0.60, bogey=0.15, double_or_worse=0.03)
    expected = 8 * 0 + 5 * 0.02 + 2 * 0.20 - 1 * 0.15 - 3 * 0.03
    assert abs(p.expected_points() - expected) < 1e-9


def test_variance_includes_double_bogey_tail():
    # two distributions with the same mean, different tail risk
    safe = HoleOutcomeProbabilities(par=1.0)
    risky = HoleOutcomeProbabilities(eagle=0.1, par=0.8, double_or_worse=0.1)
    assert safe.expected_points() == 0.0
    # risky's mean: 5*0.1 + 0*0.8 - 3*0.1 = 0.2, not zero -- construct a
    # zero-mean-but-risky distribution instead for a clean variance comparison
    risky_zero_mean = HoleOutcomeProbabilities(par=0.968, double_or_worse=0.02, eagle=0.012)
    # (close enough to zero mean for the point of this test: variance > 0 while mean ~ safe's)
    assert risky_zero_mean.variance_points() > safe.variance_points()


def test_expected_round_points_sums_across_holes():
    holes = [HoleOutcomeProbabilities(par=1.0) for _ in range(18)]
    mean, var = expected_round_points(holes)
    assert mean == 0.0
    assert var == 0.0  # zero variance when every hole is 100% one outcome


def test_backtest_refuses_without_real_data():
    inputs = BacktestInputs(
        past_game_code="UNKNOWN", past_tournament_date=__import__("datetime").date(2020, 1, 1),
        past_course_name="익산CC", past_results=[], pre_cutoff_player_records=[],
        confirm_real_data=False,
    )
    with pytest.raises(BacktestBlockedError):
        run_blind_backtest(inputs)


def test_monte_carlo_refuses_without_real_data():
    inputs = MonteCarloInputs(
        entry_list=[], player_outcome_rates={}, course_hole_table=[],
        backtest_passed=False, confirm_real_data=False,
    )
    with pytest.raises(MonteCarloBlockedError):
        run_monte_carlo(inputs)


def test_monte_carlo_refuses_even_with_confirm_flag_but_no_real_data():
    """--confirm-real-data alone must never be sufficient -- the guard must
    also check actual field size / coverage, matching the established
    pattern from point_simulation_SCAFFOLD.py on the sibling branch."""
    inputs = MonteCarloInputs(
        entry_list=["a"] * 5, player_outcome_rates={"a": {}}, course_hole_table=[],
        backtest_passed=True, confirm_real_data=True,
    )
    with pytest.raises(MonteCarloBlockedError):
        run_monte_carlo(inputs)


def test_redteam_zero_fail_this_turn():
    """The 4 structurally-checkable items must all PASS (no stroke-play
    reuse, tail risk represented, no hardcoded 2025 winner, no course-effect
    leakage). The other 3 stay honestly BLOCKED -- never silently PASS."""
    items = run_redteam()
    by_item = {it.item: it for it in items}
    assert len(items) == 7
    structurally_checkable = [
        "기존 스트로크플레이 모델 재사용 여부",
        "Double+ 꼬리위험 반영 여부",
        "2025 우승자 사후인지 반영 여부",
        "익산CC 코스효과를 에이원CC로 이식했는지 여부",
    ]
    for name in structurally_checkable:
        assert by_item[name].status == "PASS", f"{name}: {by_item[name].status} -- {by_item[name].detail}"
    blocked = ["Birdie% 과대평가 여부", "파5 4개 홀 효과 과대평가 여부", "미래 데이터 leakage 여부"]
    for name in blocked:
        assert by_item[name].status == "BLOCKED", f"{name} should be honestly BLOCKED, not {by_item[name].status}"
    assert sum(1 for it in items if it.status == "FAIL") == 0


def test_no_win_probability_output_exists_anywhere_this_turn():
    """확률 검증 없으면 PUBLIC 금지 -- there must be no file anywhere in this
    build claiming a win/cut/Top-N probability number for 2026100004,
    since Monte Carlo has never run."""
    stableford_dir = REPO_ROOT / "klpga_pipeline" / "content" / "website_v2" / "stableford_2026100004"
    if stableford_dir.exists():
        for f in stableford_dir.rglob("*"):
            if f.is_file() and f.suffix in (".json", ".csv", ".html"):
                text = f.read_text(encoding="utf-8")
                assert "우승확률" not in text
                assert "win_probability" not in text.lower()


def test_tournament_info_json_has_required_official_fields_and_no_fabricated_hole_table():
    path = REPO_ROOT / "klpga_pipeline" / "content" / "website_v2" / "2026100004_TOURNAMENT_INFO.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["game_code"] == "2026100004"
    assert data["course_par"] == 72
    assert data["course_yardage"] == 6504
    assert data["prize_money_total"] == 1_000_000_000
    assert data["prize_money_winner"] == 180_000_000
    assert data["scoring_table"] == {
        "albatross": 8, "eagle": 5, "birdie": 2, "par": 0, "bogey": -1, "double_bogey_or_worse": -3,
    }
    assert data["is_stroke_play"] is False
    # must NOT contain a fabricated 18-hole table -- only the 5 named key holes
    assert "hole_by_hole_table" not in data
    assert set(data["official_key_holes_as_described"]["par5"]) == {3, 9, 13, 15}
    assert data["official_key_holes_as_described"]["par3"] == [17]


def test_official_schedule_has_2026100004_entry_sourced_correctly():
    path = REPO_ROOT / "klpga_pipeline" / "content" / "website_v2" / "OFFICIAL_KLPGA_SCHEDULE.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = [t for t in data["tournaments"] if t["game_code"] == "2026100004"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["tournament_name"] == "HJ중공업·동부건설 챔피언십"
    assert entry["start_date"] == "2026-10-08"
    assert entry["end_date"] == "2026-10-11"
    assert entry["venue"] == "에이원CC"
    assert entry["source_identity"] == "content/website_v2/2026100004_TOURNAMENT_INFO.json"
    import hashlib
    info_path = REPO_ROOT / "klpga_pipeline" / "content" / "website_v2" / "2026100004_TOURNAMENT_INFO.json"
    assert entry["source_hash"] == hashlib.sha256(info_path.read_bytes()).hexdigest()
