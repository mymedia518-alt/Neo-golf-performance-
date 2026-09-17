"""HANA R1 -- internal PRE-vs-R1 comparison record.

This is an internal analysis artifact for later model evaluation (R2/
R3/FINAL) -- it is NOT rendered on the public R1 page. Per the
standing "PRE 예측과 실제 결과 혼합 금지" rule, PRE's frozen
pre-tournament prediction and R1's real observed result are kept in
two clearly separate, explicitly labeled column groups for the same
player row; they are never combined into one blended number anywhere
in this file.

Population: the 107 players present in BOTH the PRE 108-player entry
and the R1 108-player official field (i.e. everyone except 양서후,
10867, who has no PRE record to compare against). 박서현 (9111, PRE
-only, absent from R1) is recorded separately as a PRE-only row with
no R1 columns, for completeness.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

PRE_INPUT_PATH = CONTENT / "HANA_2026090002_PLAYER_ANALYSIS_INPUT_V4.json"
PRE_M4_PATH = CONTENT / "HANA_2026090002_PRE_M4_60000_CANDIDATE_V2.json"
R1_RESULT_PATH = CONTENT / "HANA_2026090002_R1_PLAYER_RESULT_V1.json"


def main() -> None:
    pre_input = json.loads(PRE_INPUT_PATH.read_text(encoding="utf-8"))
    pre_by_id = {r["player_id"]: r for r in pre_input["records"]}

    pre_m4 = json.loads(PRE_M4_PATH.read_text(encoding="utf-8"))
    m4_by_id = {r["playerCode"]: r for r in pre_m4["records"]}

    r1_result = json.loads(R1_RESULT_PATH.read_text(encoding="utf-8"))
    r1_by_id = {r["player_id"]: r for r in r1_result["records"]}

    common_ids = sorted(set(pre_by_id) & set(r1_by_id), key=int)
    assert len(common_ids) == 107, f"expected 107 players common to PRE and R1, got {len(common_ids)}"

    comparison_records = []
    for pid in common_ids:
        pre_rec = pre_by_id[pid]
        m4_rec = m4_by_id.get(pid)
        r1_rec = r1_by_id[pid]
        comparison_records.append({
            "player_id": pid,
            "official_display_name": pre_rec["official_display_name"],
            "pre": {
                "k_rank": pre_rec.get("k_rank"),
                "analysis_status": m4_rec["analysis_status"] if m4_rec else None,
                "win_probability": m4_rec["win_probability"] if m4_rec else None,
                "cut_probability": m4_rec["cut_probability"] if m4_rec else None,
                "top20_probability": m4_rec["top20_probability"] if m4_rec else None,
                "top10_probability": m4_rec["top10_probability"] if m4_rec else None,
                "top5_probability": m4_rec["top5_probability"] if m4_rec else None,
            },
            "r1": {
                "status": r1_rec["status"],
                "rank_display": r1_rec["rank_display"],
                "rank": r1_rec["rank"],
                "total_strokes": r1_rec["total_strokes"],
                "total_under_par_display": r1_rec["total_under_par_display"],
            },
        })

    pre_only = [
        {
            "player_id": "9111",
            "official_display_name": pre_by_id["9111"]["official_display_name"],
            "pre": {
                "k_rank": pre_by_id["9111"].get("k_rank"),
                "analysis_status": m4_by_id.get("9111", {}).get("analysis_status"),
                "win_probability": m4_by_id.get("9111", {}).get("win_probability"),
                "cut_probability": m4_by_id.get("9111", {}).get("cut_probability"),
                "top20_probability": m4_by_id.get("9111", {}).get("top20_probability"),
                "top10_probability": m4_by_id.get("9111", {}).get("top10_probability"),
                "top5_probability": m4_by_id.get("9111", {}).get("top5_probability"),
            },
            "r1": None,
            "note": "PRE 108명 엔트리에 있었으나 R1 공식 리더보드에 전혀 나타나지 않음 -- R1 값 없음",
        }
    ]

    out = {
        "schema_version": "neo_hana_r1_pre_comparison_v1",
        "game_code": "2026090002",
        "round_number": 1,
        "as_of": "2026-09-17",
        "internal_only": True,
        "purpose": (
            "R2/R3/FINAL 단계의 모델 검증을 위한 내부 기록. PRE(사전예측, "
            "고정값)와 R1(실제 결과)을 같은 선수 행에 나란히 보관하되 절대 "
            "하나의 값으로 합치지 않는다. 이 파일은 공개 R1 페이지에 렌더링 "
            "되지 않는다."
        ),
        "population": {
            "common_to_pre_and_r1": len(common_ids),
            "pre_only_not_in_r1": len(pre_only),
        },
        "records": comparison_records,
        "pre_only_records": pre_only,
    }

    out_path = CONTENT / "HANA_2026090002_R1_PRE_COMPARISON_V1.json"
    assert not out_path.exists(), f"refusing to overwrite existing file: {out_path}"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out_path)
    print("population:", out["population"])


if __name__ == "__main__":
    main()
