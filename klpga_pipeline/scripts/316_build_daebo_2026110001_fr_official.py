"""Build the official, final FR (Final Round = round 3 of 3) result for
대보 하우스디 챔피언십 (game_code 2026110001) -- the tournament's real,
final leaderboard, not a forecast.

Source: __out/validated-current.json on the orphan branch
collector-output/2026110001-r3 (collected for real via
collect_current_round_evidence.py on a GitHub-hosted runner,
collected_at 2026-11-08T07:16:11Z) -- fetched via `git show` against
that branch, mirroring scripts/289's own `_git_show` pattern for
S-OIL's equivalent FR_OFFICIAL build, adapted to this tournament's own
collector pipeline (collect_current_round_evidence.py /
validated-current.json) rather than S-OIL's older
neo_klpga_shot_source/reader-branch pipeline -- the two tournaments
were collected through different pipelines; there is no
reader/2026110001 branch for this one.

Official round1_score/round2_score are populated by the source
collector; its own round3_score/round4_score fields are both null for
every row in this run (a quirk of that script's own official-field
mapping for a 3-round event, not a real missing value) -- this script
instead derives the final (3rd) round's score as
total_strokes - round1_score - round2_score, verified to be internally
consistent with the official rank ordering and total_under_par for
every one of the 59 real finishers.

WD: 방신실 withdrew during Round 2 (confirmed in scripts/313's own
build) and has no Round 3 row in this leaderboard at all -- the field
is 59, not 60, for the entire tournament from Round 2 onward. This
script's own field_size reflects that; it is not a 60-of-61 count.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
GAME_CODE = "2026110001"
SOURCE_PATH = CONTENT / "raw_capture" / f"{GAME_CODE}_r3" / "validated-current.json"
OUT_PATH = CONTENT / f"DAEBO_{GAME_CODE}_FR_OFFICIAL_V1.json"

EXPECTED_FIELD_SIZE = 59
WD_PLAYER_ID = "10095"
WD_PLAYER_NAME = "방신실"


def main() -> None:
    doc = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    records = doc["player_table"]
    if len(records) != EXPECTED_FIELD_SIZE:
        raise SystemExit(f"expected {EXPECTED_FIELD_SIZE} real FR finishers, found {len(records)}")

    ids = [str(r["player_code"]) for r in records]
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate player_code in official FR leaderboard")
    if WD_PLAYER_ID in ids:
        raise SystemExit(f"WD player {WD_PLAYER_NAME} ({WD_PLAYER_ID}) unexpectedly present in the FR field")

    for r in records:
        if r.get("holes_completed") != 18 or r.get("progress_display") != "F":
            raise SystemExit(f"{r['player_name']}: not finished (holes_completed={r.get('holes_completed')}, progress={r.get('progress_display')})")
        if r.get("round1_score") is None or r.get("round2_score") is None or r.get("total_strokes") is None:
            raise SystemExit(f"{r['player_name']}: missing round1/round2/total_strokes")

    out_records = []
    for r in sorted(records, key=lambda x: x["rank"]):
        r3_score = r["total_strokes"] - r["round1_score"] - r["round2_score"]
        out_records.append({
            "player_id": str(r["player_code"]),
            "player_name": r["player_name"],
            "final_rank": r["rank_display"],
            "final_rank_numeric": r["rank"],
            "final_tie": bool(r.get("tie_flag")),
            "r1_score": r["round1_score"],
            "r2_score": r["round2_score"],
            "r3_score": r3_score,
            "total_score": r["total_strokes"],
            "score_to_par": r["total_under_par"],
            "status": "FINISHED",
            "withdrawn": False,
            "disqualified": False,
        })

    # Internal consistency: rank must be monotonic non-decreasing with score_to_par.
    rank_errors = []
    prev = None
    for r in out_records:
        if prev is not None and r["score_to_par"] < prev:
            rank_errors.append(r["player_id"])
        prev = r["score_to_par"]
    if rank_errors:
        raise SystemExit(f"rank/score_to_par monotonicity violated for: {rank_errors}")

    by_rank: dict[int, list[dict]] = {}
    for r in out_records:
        by_rank.setdefault(r["final_rank_numeric"], []).append(r)
    tie_group_errors = [
        {"rank": k, "players": [x["player_id"] for x in v]}
        for k, v in by_rank.items()
        if len(v) > 1 and len({x["score_to_par"] for x in v}) > 1
    ]
    if tie_group_errors:
        raise SystemExit(f"tie-group inconsistency: {tie_group_errors}")

    winner = out_records[0]
    if len(by_rank[1]) > 1:
        raise SystemExit(f"official rank 1 is a tie ({by_rank[1]}) -- refusing to report a single winner; needs operator review")

    out = {
        "schema_version": "DAEBO_2026110001_FR_OFFICIAL_V1",
        "game_code": GAME_CODE,
        "round": 3,
        "stage_label": "FR",
        "source": {
            "validated_current": f"collector-output/{GAME_CODE}-r3:__out/validated-current.json",
            "collected_at": doc.get("collected_at"),
        },
        "field_determination_method": (
            "59 real finishers from the Round 3 collector's own official leaderboard reconciliation "
            "(collect_current_round_evidence.py, holes_completed==18 / progress_display=='F' for all); "
            "방신실 (WD during Round 2) is absent from this field entirely."
        ),
        "field_count": len(out_records),
        "roster_total": 60,
        "withdrawals": 1,
        "withdrawals_detail": [{"player_id": WD_PLAYER_ID, "player_name": WD_PLAYER_NAME, "withdrawn": True, "disqualified": False, "withdrew_during": "Round 2"}],
        "winner_player_id": winner["player_id"],
        "winner_player_name": winner["player_name"],
        "winner_total_strokes": winner["total_score"],
        "winner_score_to_par": winner["score_to_par"],
        "verification_errors": {"rank_monotonic_errors": rank_errors, "tie_group_errors": tie_group_errors},
        "verification_pass": not rank_errors and not tie_group_errors,
        "records": out_records,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": str(OUT_PATH),
        "field_count": len(out_records),
        "winner": winner["player_name"],
        "winner_score_to_par": winner["score_to_par"],
        "verification_pass": out["verification_pass"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
