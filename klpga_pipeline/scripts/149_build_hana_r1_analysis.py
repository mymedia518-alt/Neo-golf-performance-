"""HANA R1 -- per-player analysis layer, built from the real R1-
conditioned NEO_R1_MODEL_V1 output (2026090002_R1_5PROB_FROZEN_V1.json,
produced by 152_apply_r1_model_to_hana.py) -- NEVER from PRE's frozen
pre-tournament probabilities.

Per explicit operator instruction (2026-09-17), ALL 105 active
(non-WD) R1-completed players now carry a win/cut/top20/top10/top5
probability -- 96 from the full NEO_R1_MODEL_V1 application
(probability_basis=FULL_NEO_R1, real prior SG history), 9 from the
same frozen model applied with a neutral prior
(probability_basis=R1_SCORE_ONLY, driven purely by R1 field-relative
performance) -- win is normalized to sum to 1.0 across all 105 (see
152's own normalization_note). NEO 경기력 (the band) is NOT computed
for the 9 R1_SCORE_ONLY players -- it stays "데이터 부족", per explicit
instruction, even though their probabilities are now real numbers.

3 WD players (김리안 9702, 조혜림 9136, 권은 12706): no completed round,
no probability, no band -- reason "WD".
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

R1_RESULT_PATH = CONTENT / "HANA_2026090002_R1_PLAYER_RESULT_V1.json"
R1_5PROB_PATH = CONTENT / "2026090002_R1_5PROB_FROZEN_V1.json"

DATA_INSUFFICIENT = "데이터 부족"
CUT_POSSIBILITY_PLACEHOLDER = "데이터 부족(공식 컷 규칙 미확인)"

_BAND_LABELS = ["최상위", "상위", "중위", "하위", "최하위"]


def _pct(p: float) -> str:
    return f"{p * 100:.1f}%"


def main() -> None:
    r1_result = json.loads(R1_RESULT_PATH.read_text(encoding="utf-8"))
    records = r1_result["records"]
    assert len(records) == 108

    frozen = json.loads(R1_5PROB_PATH.read_text(encoding="utf-8"))
    assert frozen["game_code"] == "2026090002"
    assert frozen["refit_performed"] is False
    pred_by_id = {p["player_id"]: p for p in frozen["predictions"]}
    assert len(pred_by_id) == 105
    assert abs(sum(p["win"] for p in pred_by_id.values()) - 1.0) < 1e-6

    # NEO 경기력 band, computed over the FULL_NEO_R1 96 only (they alone
    # are eligible for a band -- see module docstring), ranked by
    # their own win probability among that 96, never mixed with the
    # 9 R1_SCORE_ONLY players' probabilities.
    full_neo_r1 = [p for p in pred_by_id.values() if p["probability_basis"] == "FULL_NEO_R1"]
    assert len(full_neo_r1) == 96
    ranked = sorted(full_neo_r1, key=lambda p: -p["win"])
    n = len(ranked)
    band_by_id: dict[str, str] = {}
    for i, p in enumerate(ranked):
        band_by_id[p["player_id"]] = _BAND_LABELS[min(4, i * 5 // n)]

    analysis_records = []
    for rec in records:
        pid = rec["player_id"]
        is_wd = rec["status"] == "WD"
        pred = pred_by_id.get(pid)

        if is_wd:
            reason = "WD"
        else:
            reason = pred["probability_basis"]

        row = {
            "player_id": pid,
            "official_display_name": rec["official_display_name"],
            "in_pre_population": rec["in_pre_population"],
            "status": rec["status"],
            "rank_display": rec["rank_display"],
            "rank": rec["rank"],
            "total_strokes": rec["total_strokes"],
            "total_under_par_display": rec["total_under_par_display"],
            "probability_basis": reason,
            "cut_possibility": CUT_POSSIBILITY_PLACEHOLDER,
        }
        if pred is not None:
            row.update({
                "neo_performance_band": band_by_id.get(pid, DATA_INSUFFICIENT),
                "cut_probability": _pct(pred["cut"]),
                "top20_probability": _pct(pred["top20"]),
                "top10_probability": _pct(pred["top10"]),
                "top5_probability": _pct(pred["top5"]),
                "win_probability": _pct(pred["win"]),
            })
        else:
            row.update({
                "neo_performance_band": DATA_INSUFFICIENT,
                "cut_probability": DATA_INSUFFICIENT,
                "top20_probability": DATA_INSUFFICIENT,
                "top10_probability": DATA_INSUFFICIENT,
                "top5_probability": DATA_INSUFFICIENT,
                "win_probability": DATA_INSUFFICIENT,
            })
        analysis_records.append(row)

    basis_counts: dict[str, int] = {}
    for r in analysis_records:
        basis_counts[r["probability_basis"]] = basis_counts.get(r["probability_basis"], 0) + 1
    assert basis_counts.get("WD") == 3
    assert basis_counts.get("FULL_NEO_R1") == 96
    assert basis_counts.get("R1_SCORE_ONLY") == 9
    assert sum(basis_counts.values()) == 108

    band_insufficient_count = sum(1 for r in analysis_records if r["neo_performance_band"] == DATA_INSUFFICIENT)
    assert band_insufficient_count == 12  # 3 WD + 9 R1_SCORE_ONLY

    out = {
        "schema_version": "neo_hana_r1_analysis_v3",
        "game_code": "2026090002",
        "round_number": 1,
        "as_of": "2026-09-17",
        "source_r1_player_result": str(R1_RESULT_PATH.relative_to(ROOT.parent)),
        "source_r1_5prob_frozen": str(R1_5PROB_PATH.relative_to(ROOT.parent)),
        "model_id": "NEO_R1_MODEL_V1",
        "model_freeze_sha256": frozen["model_freeze_sha256"],
        "policy": (
            "cut/top20/top10/top5/win 확률은 NEO_R1_MODEL_V1(동결된 walk-forward "
            "검증 모델)을 이 대회의 실제 R1 결과에 적용해 새로 계산한 값이다. PRE의 "
            "확률은 이 파일에 절대 복사되지 않는다. WD 3명은 확률이 없다. 나머지 "
            "105명은 전원 확률이 계산되며, probability_basis로 FULL_NEO_R1(사전 "
            "공식 SG 이력 기반, 96명)과 R1_SCORE_ONLY(R1 필드 상대 성적만 반영, "
            "중립 사전강도 가정, 9명)를 구분한다. NEO 경기력 배지는 FULL_NEO_R1 "
            "96명에만 부여되며, R1_SCORE_ONLY 9명은 확률이 있어도 배지는 '데이터 "
            "부족'으로 유지된다."
        ),
        "probability_basis_counts": basis_counts,
        "win_probability_sum_over_active_105": frozen["win_probability_sum_over_active_105"],
        "normalization_note": frozen["normalization_note"],
        "calibration_note": frozen["calibration_note"],
        "cut_possibility_note": (
            "위 5개 확률과 별개로, '공식 컷 순위 기준'은 R1 원자료에 없음(컷은 "
            "통상 R2 종료 후 확정) -- 모든 선수에 대해 '데이터 부족(공식 컷 규칙 "
            "미확인)'으로 고정."
        ),
        "records": analysis_records,
    }

    out_path = CONTENT / "HANA_2026090002_R1_ANALYSIS_V1.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out_path)
    print("basis_counts:", basis_counts)
    print("win_probability_sum:", frozen["win_probability_sum_over_active_105"])


if __name__ == "__main__":
    main()
