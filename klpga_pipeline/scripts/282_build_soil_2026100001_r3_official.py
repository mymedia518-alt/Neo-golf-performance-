"""Build the official, confirmed R1+R2+R3 result record for 제20회
S-OIL 챔피언십 (game_code 2026100001) -- real R3 scores, not a forecast.

R3 has now actually been played (confirmed by re-dispatching neo-sync.yml
stage=results on 2026-10-31 and finding real, non-zero round3score values
on the freshly re-collected reader/2026100001 raw page -- not assumed).

WHO PLAYED R3: exactly the 68 real cutmakers from scripts/278's R2 cut
determination -- LEADERBOARD.json now shows rounds_played=3 for those 68
and rounds_played=2 (unchanged) for the 28 cut-missed players. Cross-
checked three ways, all in exact agreement:
  - normalized LEADERBOARD.json: 68 records with rounds_played==3
  - raw round_leaderboard_r3.html (this round's real player field):
    68 distinct player codes, identical set to the 68 above
  - raw round_leaderboard_r4.html (KLPGA's own next-round field
    listing, pre-populated before R4 starts): 68 distinct player
    codes, identical set to the 68 above -- confirms no second cut
    between R3 and R4, the same 68 advance.
No WD/DQ: 기권/실격/WD/DQ each occur exactly once in the raw R3 page
(the page's own fixed legend), zero real occurrences, matching
LEADERBOARD.json's withdrawn=0/disqualified=0 for all 96 records.
total_score arithmetic (r1+r2+r3) verified to match for all 68.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
GAME_CODE = "2026100001"
OUT_PATH = CONTENT / f"SOIL_{GAME_CODE}_R3_OFFICIAL_V1.json"


def _git_show(ref: str) -> str:
    return subprocess.run(
        ["git", "show", ref], cwd=REPO_ROOT, capture_output=True, check=True, text=True, encoding="utf-8",
    ).stdout


def main() -> None:
    lb = json.loads(_git_show(f"origin/reader/{GAME_CODE}:klpga_pipeline/normalized/{GAME_CODE}/LEADERBOARD.json"))
    records = lb["records"]
    assert len(records) == 96, f"expected 96 official entrants, found {len(records)}"
    for r in records:
        assert r["withdrawn"] == 0 and r["disqualified"] == 0, f"{r['player_id']}: unexpected WD/DQ flag"
        assert r["rounds_played"] in (2, 3), f"{r['player_id']}: unexpected rounds_played {r['rounds_played']}"

    r3_players = [r for r in records if r["rounds_played"] == 3]
    assert len(r3_players) == 68, f"expected 68 real R3 players, found {len(r3_players)}"
    for r in r3_players:
        assert r["r1_score"] is not None and r["r2_score"] is not None and r["r3_score"] is not None
        assert r["total_score"] == r["r1_score"] + r["r2_score"] + r["r3_score"], (
            f"{r['player_id']}: total_score does not equal r1+r2+r3"
        )

    r3_html = _git_show(f"origin/reader/{GAME_CODE}:klpga_pipeline/raw/{GAME_CODE}/round_leaderboard_r3.html")
    r4_html = _git_show(f"origin/reader/{GAME_CODE}:klpga_pipeline/raw/{GAME_CODE}/round_leaderboard_r4.html")

    codes_r3 = set(re.findall(r'_playerCode="(\d+)"', r3_html))
    codes_r4 = set(re.findall(r'_playerCode="(\d+)"', r4_html))
    r3_ids = {r["player_id"] for r in r3_players}
    assert codes_r3 == r3_ids, "R3 raw page player codes != 68 real R3 players from LEADERBOARD.json"
    assert codes_r4 == r3_ids, "R4 field-listing page codes != the same 68 -- a second cut would break this"

    for term in ("기권", "실격", "WD", "DQ"):
        count = len(re.findall(re.escape(term), r3_html))
        assert count == 1, f"unexpected '{term}' occurrence count in R3 raw page: {count} (expected exactly 1, the legend)"

    out_records = []
    for r in sorted(r3_players, key=lambda x: x["total_score"]):
        out_records.append({
            "player_id": r["player_id"],
            "player_name": r["player_name"],
            "r1_score": r["r1_score"],
            "r2_score": r["r2_score"],
            "r3_score": r["r3_score"],
            "total_score": r["total_score"],
            "score_to_par": r["score_to_par"],
        })

    out = {
        "schema_version": "SOIL_2026100001_R3_OFFICIAL_V1",
        "game_code": GAME_CODE,
        "source": {
            "leaderboard": "origin/reader/2026100001:klpga_pipeline/normalized/2026100001/LEADERBOARD.json",
            "r3_raw_page": "origin/reader/2026100001:klpga_pipeline/raw/2026100001/round_leaderboard_r3.html",
            "r4_raw_page": "origin/reader/2026100001:klpga_pipeline/raw/2026100001/round_leaderboard_r4.html",
            "neo_sync_run": "neo-sync.yml stage=results, 2026-10-31 (run #24 on ref neo-website-v2), PASS",
        },
        "field_determination_method": (
            "68 players with rounds_played==3 in the normalized leaderboard -- the same real cutmakers from "
            "scripts/278, now with a real R3 score -- cross-checked against both the R3 raw field page and the "
            "R4 next-round field-listing page (confirms no second cut)."
        ),
        "field_count": len(out_records),
        "withdrawals": 0,
        "disqualifications": 0,
        "records": out_records,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": str(OUT_PATH),
        "field_count": len(out_records),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
