"""Round Transition Engine tests, against the real Evidence Warehouse
for 2026100005 R1/R2 (never synthetic fixtures -- this project's
established convention of testing against real data wherever it
already exists)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from klpga.neo_win import round_transition_engine as engine

pytestmark = pytest.mark.round_pipeline

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONTENT = _REPO_ROOT / "klpga_pipeline" / "content" / "website_v2"
_WAREHOUSE = _CONTENT / "evidence_warehouse"

requires_warehouse = pytest.mark.skipif(
    not (_WAREHOUSE / "tournament" / "2026100005" / "R2" / "leaderboard_raw.html").is_file(),
    reason="Evidence Warehouse for 2026100005 R2 not present in this checkout",
)


def _entrant_ids() -> list[str]:
    entrants = json.loads((_CONTENT / "2026100005_ENTRY_KRANKING_JOIN.json").read_text(encoding="utf-8"))["records"]
    return [r["player_code"] for r in entrants]


@requires_warehouse
def test_real_r1_cut_players_are_classified_r1_cut_not_r2_cut():
    """조하리/이수민/이소영: real r1_score=88 (실제 raw evidence, 코스
    par 72 기준 +16 컷오프), real r2_score=None (R2 raw evidence에
    전혀 등장하지 않음 -- R2를 실제로 플레이한 적이 없음). 이들의 CUT
    텍스트는 klpga.co.kr 시스템상 R2 캡처에서야 처음 보이지만, 실제
    적용 라운드는 R1이어야 한다 (이번 미션의 핵심 요구사항)."""
    state = engine.compute_state(_entrant_ids(), as_of_round=2, warehouse_root=_WAREHOUSE)
    for pid, expected_name in [("11076", "조하리"), ("11978", "이수민"), ("8246", "이소영")]:
        s = state[pid]
        assert s["status"] == "R1_CUT", f"{expected_name} ({pid}): expected R1_CUT, got {s['status']}"
        assert s["status_round"] == 1, f"{expected_name} ({pid}): expected status_round=1, got {s['status_round']}"
        assert s["r1_score"] == 88
        assert s["r2_score"] is None


@requires_warehouse
def test_real_wd_players_classified_correctly():
    """고지우/황정미: 실제 R1 완료(real r1_score), R2는 전혀 플레이하지
    않음(r2_score=None) -- WD가 R1 이후에 적용됨. 마다솜: R1 자체도
    플레이하지 않음(real evidence: r1_score=None), R1 자신의 evidence
    안에 WD 텍스트가 바로 존재."""
    state = engine.compute_state(_entrant_ids(), as_of_round=2, warehouse_root=_WAREHOUSE)
    for pid, expected_name, expected_r1 in [("10112", "고지우", 81), ("8240", "황정미", 78)]:
        s = state[pid]
        assert s["status"] == "WD", f"{expected_name}: expected WD, got {s['status']}"
        assert s["status_round"] == 1
        assert s["r1_score"] == expected_r1
        assert s["r2_score"] is None

    mds = state["9401"]
    assert mds["status"] == "WD"
    assert mds["r1_score"] is None
    assert mds["r2_score"] is None


@requires_warehouse
def test_active_player_state_as_of_round_1_is_unaffected_by_round_2_evidence():
    """핵심 구조적 요구사항: as_of_round=1로 계산한 State는 R2 evidence를
    전혀 참조하지 않아야 한다 -- 이게 '스냅샷 오염' 위험을 구조적으로
    제거하는 지점이다."""
    state_r1 = engine.compute_state(_entrant_ids(), as_of_round=1, warehouse_root=_WAREHOUSE)
    # 조하리는 R1 자신의 evidence에는 아직 CUT 텍스트가 없음(이번 세션
    # 실측: R2 캡처에서야 처음 보임) -- 따라서 as_of_round=1 시점에는
    # 아직 ACTIVE여야 한다(R1_CUT으로 앞당겨 판정하면 안 됨).
    assert state_r1["11076"]["status"] == "ACTIVE"
    assert state_r1["11076"]["r1_score"] == 88


@requires_warehouse
def test_active_player_keeps_both_real_round_scores():
    state = engine.compute_state(_entrant_ids(), as_of_round=2, warehouse_root=_WAREHOUSE)
    kim = state["10725"]  # 김민솔, 실제 1위, R1=70 R2=70
    assert kim["status"] == "ACTIVE"
    assert kim["r1_score"] == 70
    assert kim["r2_score"] == 70
