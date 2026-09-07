"""NEO TOURNAMENT PIPELINE item 3: build_current_round_page.py must produce a
candidate that klpga.tournament_atomic_promotion's generic candidate ->
validate -> promote gate accepts -- the same gate every other stage uses,
not a page-specific docs/ bypass."""
from __future__ import annotations

import importlib.util
from hashlib import sha256
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klpga.tournament_atomic_promotion import validate_candidate_for_promotion  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "build_current_round_page", Path(__file__).parents[1] / "scripts" / "build_current_round_page.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

TEMPLATE = """<!doctype html>
<html><head><title>NEO GOLF DATA · R3 (FINAL) 예측</title>
<meta name="neo-build-id" content="old">
</head><body>
<!-- NEO CURRENT ROUND START -->
old block
<!-- NEO CURRENT ROUND END -->
<h1>R3 (FINAL) NEO 예측</h1>
<section class="panel">
rest
</section>
</body></html>"""


def _snapshot(round_number=3, stage="FINAL_LIVE"):
    return {
        "round": round_number,
        "stage": stage,
        "game_code": "2026120001",
        "collected_at": "2026-09-07T05:00:00+00:00",
        "sg_retrieved_at": "2026-09-07T05:00:00+00:00",
        "row_count": 1,
        "player_table": [
            {"player_code": "P1", "rank_display": "1", "player_name": "테스트선수",
             "total_under_par_display": "-10", "today_under_par_display": "-3",
             "holes_completed": 18, "progress_display": "F", "raw_inghole": 18,
             "starting_tee": 1}
        ],
        "sg": [
            {"player_id": "P1", "player": "테스트선수",
             "validation": {"total_within_tolerance": True, "t2g_within_tolerance": True},
             "total": 1.0, "tee_to_green": 0.5, "off_the_tee": 0.2, "approach": 0.1,
             "around_green": 0.1, "putting": 0.1}
        ],
    }


def test_final_round_uses_suffixed_label_only_in_heading_and_splice_targets():
    snapshot = _snapshot()
    html = module.build(snapshot, TEMPLATE, tournament_name="OK저축은행 읏맨 오픈", factual_sha256="deadbeef")
    assert "<h1>R3 (FINAL) 현재 리더보드</h1>" in html
    assert "<h2>R2 종료 기준 · R3 (FINAL) NEO 사전예측</h2>" in html
    assert "NEO GOLF DATA · R3 (FINAL) 현재 상황</title>" in html
    # Everywhere else stays plain "R3", matching the page's original copy.
    assert "공식 R3 현재 상황" in html
    assert "<caption>R3 공식 성적</caption>" in html
    assert "공식 R3 SG 경기력 보기" in html
    assert "R3 단일 라운드 공식 SG" in html
    assert "현재 R3 성적을 반영" in html
    assert "R3 (FINAL) 공식 성적" not in html
    assert "R3 (FINAL) SG 경기력" not in html


def test_non_final_round_never_gets_final_suffix_anywhere():
    snapshot = _snapshot(round_number=1, stage="R1_LIVE")
    template = TEMPLATE.replace("R3 (FINAL)", "R1")
    html = module.build(snapshot, template, tournament_name="OK저축은행 읏맨 오픈", factual_sha256="deadbeef")
    assert "(FINAL)" not in html
    assert "<h1>R1 현재 리더보드</h1>" in html


def test_candidate_passes_the_generic_atomic_promotion_gate(tmp_path):
    snapshot = _snapshot()
    snapshot_bytes = b'{"fixture": "official-round-evidence"}'
    factual_sha256 = sha256(snapshot_bytes).hexdigest()
    html = module.build(snapshot, TEMPLATE, tournament_name="OK저축은행 읏맨 오픈", factual_sha256=factual_sha256)
    candidate = tmp_path / "candidate.html"
    candidate.write_text(html, encoding="utf-8")

    # Must not raise PromotionBlocked -- this IS the shared gate, not a
    # look-alike reimplementation.
    sha = validate_candidate_for_promotion(
        candidate,
        expected_game_code="2026120001",
        expected_round_number=3,
        expected_factual_sha256=factual_sha256,
    )
    assert sha


def test_wrong_factual_sha256_is_rejected_by_the_gate(tmp_path):
    snapshot = _snapshot()
    html = module.build(snapshot, TEMPLATE, tournament_name="OK저축은행 읏맨 오픈", factual_sha256="correct-hash")
    candidate = tmp_path / "candidate.html"
    candidate.write_text(html, encoding="utf-8")

    import pytest
    from klpga.tournament_atomic_promotion import PromotionBlocked
    with pytest.raises(PromotionBlocked):
        validate_candidate_for_promotion(
            candidate,
            expected_game_code="2026120001",
            expected_round_number=3,
            expected_factual_sha256="a-different-hash",
        )
