"""Build the official, confirmed R1+R2 result record for 제20회 S-OIL
챔피언십 (game_code 2026100001), including the REAL 36-hole cut
determination -- not a simulated/assumed cut rule.

WHY NOT THE normalized LEADERBOARD.json `made_cut` FIELD: that field is
computed by klpga.collectors.aggregate as `1 if final_round in
round_scores else 0` -- i.e. "did this player play the tournament's
LAST round", not "did this player survive the 36-hole cut". Since R3/R4
have not been played yet, this field is 0 for all 96 entrants right
now; it will only become meaningful once the whole event is over. It
is not usable for a mid-tournament cut determination and was not used
here.

HOW THE REAL CUT WAS DETERMINED: cross-referencing two real, officially
served pages collected via neo-sync.yml (stage=results) on
reader/2026100001 -- raw/2026100001/round_leaderboard_r2.html (the
completed R2 leaderboard, 96 real player rows with real r1_score/
r2_score, source of truth for "who played what") against
raw/2026100001/round_leaderboard_r3.html (KLPGA's own round-3 leaderboard
view, already PRE-POPULATED with only the cut-surviving field before a
single R3 shot has been struck -- round3score=0/empty for everyone,
confirming R3 itself has not started). The player codes present in the
R3 page are a strict subset of R2's 96 (68 of 96, 0 new codes) -- this
is KLPGA's own, real, already-applied cut, read off its own site
structure, not inferred from a score threshold or a generic "top 60
and ties" assumption. (The "+16 컷오프 = CUT" text appearing on these
pages is a fixed template legend, not a per-event computed value --
confirmed by checking 2026100005's own R2 raw capture, which carries
the exact same literal "+16" text while that event's real cut fell
far from +16 strokes.)

No WD/DQ: searched both raw captures for 기권/WD/실격/DQ outside the
page's own fixed legend block -- zero real occurrences. All 96 entrants
played both rounds; 28 missed the cut, 0 withdrew or were disqualified.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
GAME_CODE = "2026100001"
OUT_PATH = CONTENT / f"SOIL_{GAME_CODE}_R2_OFFICIAL_V1.json"


def _git_show(ref: str) -> str:
    return subprocess.run(
        ["git", "show", ref], cwd=REPO_ROOT, capture_output=True, check=True, text=True, encoding="utf-8",
    ).stdout


def main() -> None:
    lb = json.loads(_git_show(f"origin/reader/{GAME_CODE}:klpga_pipeline/normalized/{GAME_CODE}/LEADERBOARD.json"))
    records = lb["records"]
    assert len(records) == 96, f"expected 96 official entrants, found {len(records)}"
    for r in records:
        assert r["rounds_played"] == 2, f"{r['player_id']}: expected rounds_played=2, got {r['rounds_played']}"
        assert r["r1_score"] is not None and r["r2_score"] is not None, f"{r['player_id']}: missing R1/R2 score"
        assert r["r3_score"] is None and r["r4_score"] is None, f"{r['player_id']}: unexpected R3/R4 score already present"
        assert r["withdrawn"] == 0 and r["disqualified"] == 0, f"{r['player_id']}: unexpected WD/DQ flag"

    r2_html = _git_show(f"origin/reader/{GAME_CODE}:klpga_pipeline/raw/{GAME_CODE}/round_leaderboard_r2.html")
    r3_html = _git_show(f"origin/reader/{GAME_CODE}:klpga_pipeline/raw/{GAME_CODE}/round_leaderboard_r3.html")

    codes_r2 = set(re.findall(r'_playerCode="(\d+)"', r2_html))
    codes_r3 = set(re.findall(r'_playerCode="(\d+)"', r3_html))
    assert codes_r2 == {r["player_id"] for r in records}, "R2 raw page player codes != normalized leaderboard player ids"
    assert codes_r3 <= codes_r2, "R3 field page lists a player not present in R2 -- cannot be a pure cut-trim"

    # Independent WD/DQ check directly on the raw page text (outside the
    # fixed legend block, which always contains exactly one of each term).
    for term in ("기권", "실격", "WD", "DQ"):
        count = len(re.findall(re.escape(term), r2_html))
        assert count == 1, f"unexpected '{term}' occurrence count in R2 raw page: {count} (expected exactly 1, the legend)"

    cut_survivors = codes_r3
    cut_missed = codes_r2 - codes_r3
    assert len(cut_survivors) + len(cut_missed) == 96

    out_records = []
    for r in sorted(records, key=lambda x: x["total_score"]):
        pid = r["player_id"]
        made_cut = pid in cut_survivors
        out_records.append({
            "player_id": pid,
            "player_name": r["player_name"],
            "r1_score": r["r1_score"],
            "r2_score": r["r2_score"],
            "total_score": r["total_score"],
            "score_to_par": r["score_to_par"],
            "made_cut": made_cut,
            "made_cut_source": "r3_field_listing_subset" if made_cut else "absent_from_r3_field_listing",
        })

    # Sanity: the cut boundary must be clean (no player on one side of
    # the line scores better than a player on the other side).
    worst_survivor = max(r["total_score"] for r in out_records if r["made_cut"])
    best_missed = min(r["total_score"] for r in out_records if not r["made_cut"])
    assert worst_survivor < best_missed, (
        f"cut boundary is not clean: worst survivor total={worst_survivor}, "
        f"best missed total={best_missed}"
    )

    out = {
        "schema_version": "SOIL_2026100001_R2_OFFICIAL_V1",
        "game_code": GAME_CODE,
        "source": {
            "leaderboard": "origin/reader/2026100001:klpga_pipeline/normalized/2026100001/LEADERBOARD.json",
            "r2_raw_page": "origin/reader/2026100001:klpga_pipeline/raw/2026100001/round_leaderboard_r2.html",
            "r3_raw_page": "origin/reader/2026100001:klpga_pipeline/raw/2026100001/round_leaderboard_r3.html",
            "neo_sync_run": "neo-sync.yml stage=results, 2026-10-30T09:30 UTC, PASS (see reports/2026100001/REVIEW_REPORT_V1.md)",
        },
        "cut_determination_method": (
            "Player codes present in the R3 (next-round) leaderboard page are the real, "
            "already-applied cut survivors -- a strict subset of R2's 96 entrants, "
            "cross-checked for a clean score boundary (no overlap) and zero WD/DQ."
        ),
        "made_cut_counts": {"made_cut_true": len(cut_survivors), "made_cut_false": len(cut_missed)},
        "cut_boundary": {"worst_survivor_total_score": worst_survivor, "best_missed_total_score": best_missed},
        "withdrawals": 0,
        "disqualifications": 0,
        "records": out_records,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": str(OUT_PATH),
        "field_count": len(out_records),
        "made_cut_true": len(cut_survivors),
        "made_cut_false": len(cut_missed),
        "cut_boundary": out["cut_boundary"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
