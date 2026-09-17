"""HANA R1 -- parse the official Round 1 leaderboard raw capture into
per-player results, cross-checked player_id-by-player_id against the
PRE 108-player population.

Uses the existing, already-tested klpga.parsers.leaderboard_parser
(built for exactly this `data-rank`/`_playerCode`-style markup) --
never a new ad hoc parser.

CONFIRMED field reconciliation (2026-09-17): the R1 official field is
NOT byte-identical to the PRE 108-player population. 박서현 (9111, in
PRE) does not appear anywhere in the R1 raw HTML at all -- no WD/기권
marker, simply absent. 양서후 (10867, not in PRE) appears in R1 with a
complete 18-hole round (76 strokes, rank 56T) -- i.e. a genuine
pre-tournament alternate substitution. Per explicit operator decision
(after this exact discrepancy was surfaced and confirmed reproducible
against the raw HTML), this script reflects the REAL official R1 field
of 108 players as-is: 박서현 is recorded separately as removed, 양서후
is included as a new entrant with no PRE record.

CONFIRMED 3 WD players (2026090002 R1): 김리안(9702), 조혜림(9136),
권은 0906(A)(12706) -- all three independently show status="WD" in the
parsed leaderboard (explicit "WD"/"기권" text in the row, not just the
rank=999 sentinel), each with holes_completed < 18. This matches the
operator's named WD list exactly -- an independent confirmation, not a
value taken on the operator's word alone.

Known parser artifact fixed here: for an explicit-status (WD/DQ/CUT)
row, the site still renders the placeholder total_under_par/
today_under_par as literal "0" (the same placeholder used alongside
the rank=999 sentinel) -- but only the "INCOMPLETE" (999-sentinel-only)
branch of the shared parser suppresses this to None. This script
suppresses it explicitly for every WD row too, since "0" is never a
real to-par value for a withdrawn player.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.parsers.leaderboard_parser import parse_round_leaderboard_html  # noqa: E402

RAW_PATH = CONTENT / "incoming_evidence" / "2026090002" / "HANA_2026090002_R1_LEADERBOARD_RAW_V1.html"
PRE_INPUT_PATH = CONTENT / "HANA_2026090002_PLAYER_ANALYSIS_INPUT_V4.json"

EXPECTED_WD_IDS = {"9702", "9136", "12706"}


def main() -> None:
    raw_html = RAW_PATH.read_text(encoding="utf-8")
    raw_sha256 = hashlib.sha256(RAW_PATH.read_bytes()).hexdigest()

    pre = json.loads(PRE_INPUT_PATH.read_text(encoding="utf-8"))
    pre_by_id = {r["player_id"]: r for r in pre["records"]}
    pre_ids = set(pre_by_id)
    assert len(pre_ids) == 108, f"expected 108 PRE players, got {len(pre_ids)}"

    rows = parse_round_leaderboard_html(raw_html, game_code="2026090002", round_number=1)
    r1_by_id = {r.player_code: r for r in rows}
    r1_ids = set(r1_by_id)
    assert len(r1_ids) == 108, f"expected 108 players in the R1 official field, got {len(r1_ids)}"

    removed_from_pre = sorted(pre_ids - r1_ids, key=int)
    added_not_in_pre = sorted(r1_ids - pre_ids, key=int)
    assert removed_from_pre == ["9111"], f"unexpected PRE-only players: {removed_from_pre}"
    assert added_not_in_pre == ["10867"], f"unexpected R1-only players: {added_not_in_pre}"

    wd_ids = {pid for pid, r in r1_by_id.items() if r.status == "WD"}
    assert wd_ids == EXPECTED_WD_IDS, f"WD set mismatch: got {sorted(wd_ids)}, expected {sorted(EXPECTED_WD_IDS)}"

    records = []
    for pid in sorted(r1_ids, key=int):
        r = r1_by_id[pid]
        pre_rec = pre_by_id.get(pid)
        is_wd = r.status == "WD"

        total_under_par = None if is_wd else r.total_under_par
        today_under_par = None if is_wd else r.today_under_par
        total_under_par_display = None if is_wd else r.total_under_par_display
        today_under_par_display = None if is_wd else r.today_under_par_display

        records.append({
            "player_id": pid,
            "official_display_name": pre_rec["official_display_name"] if pre_rec else r.player_name,
            "player_eng_name": r.player_eng_name,
            "in_pre_population": pre_rec is not None,
            "status": r.status,
            "rank_display": r.rank_display,
            "rank": r.rank,
            "tie_flag": r.tie_flag,
            "holes_completed": r.holes_completed,
            "round1_score": r.round1_score,
            "total_strokes": r.total_strokes,
            "total_under_par_display": total_under_par_display,
            "total_under_par": total_under_par,
            "today_under_par_display": today_under_par_display,
            "today_under_par": today_under_par,
        })

    out = {
        "schema_version": "neo_hana_r1_player_result_v1",
        "game_code": "2026090002",
        "round_number": 1,
        "as_of": "2026-09-17",
        "source_raw": {
            "path": str(RAW_PATH.relative_to(ROOT.parent)),
            "sha256": raw_sha256,
            "saved_from_url": "https://klpga.co.kr/web/leaderboard/leaderboard?gameCode=2026090002",
        },
        "parser": "klpga.parsers.leaderboard_parser.parse_round_leaderboard_html",
        "field_reconciliation": {
            "pre_population_count": len(pre_ids),
            "r1_official_field_count": len(r1_ids),
            "exact_match": False,
            "removed_from_pre_population": [
                {
                    "player_id": "9111",
                    "official_display_name": pre_by_id["9111"]["official_display_name"],
                    "note": (
                        "PRE 108명 엔트리에 포함되어 있었으나 R1 공식 리더보드에 전혀 "
                        "나타나지 않음 (WD/기권 표시 없이 완전 부재, 원자료 전수 검색 "
                        "결과 0건). 대회 시작 전 후보선수 교체로 추정되나 공식 사유는 "
                        "미확인 -- operator 확인 후 R1 페이지에 이 사실을 그대로 반영."
                    ),
                }
            ],
            "added_not_in_pre_population": [
                {
                    "player_id": "10867",
                    "official_display_name": r1_by_id["10867"].player_name,
                    "note": (
                        "PRE 108명 엔트리에 없었으나 R1 공식 리더보드에 신규 등장, "
                        "18홀 완주(76타, T56위) -- 대회 시작 전 알터네이트(후보선수) "
                        "출전으로 추정. PRE 예측 데이터가 존재하지 않으므로 NEO 경기력 "
                        "·확률은 데이터 부족으로 유지."
                    ),
                }
            ],
        },
        "wd_players": sorted(
            (
                {"player_id": pid, "official_display_name": pre_by_id[pid]["official_display_name"]}
                for pid in wd_ids
            ),
            key=lambda r: int(r["player_id"]),
        ),
        "records": records,
    }

    out_path = CONTENT / "HANA_2026090002_R1_PLAYER_RESULT_V1.json"
    assert not out_path.exists(), f"refusing to overwrite existing file: {out_path}"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out_path)
    print("field_reconciliation:", json.dumps(out["field_reconciliation"], ensure_ascii=False))
    print("wd_players:", out["wd_players"])


if __name__ == "__main__":
    main()
