"""Build the official, final FR (Final Round = round 4 of 4) result for
제20회 S-OIL 챔피언십 (game_code 2026100001) -- the tournament's real,
final leaderboard, not a forecast.

Confirmed 4-round event (never assumed): the normalized LEADERBOARD.json
itself carries final_round=4, and before this run round_leaderboard_r4.html
held every player's own round4score as a placeholder "0" (pre-round field
listing); after re-dispatching neo-sync.yml stage=results on 2026-11-01,
the same 68 real R2/R3 cutmakers now show real, non-zero round4score
values on the freshly re-collected reader/2026100001 raw page -- cross-
checked against the normalized leaderboard's own rounds_played==4 flag,
never assumed from one source alone.

WHO PLAYED FR: exactly the same 68 real cutmakers who played R3
(scripts/278/282's cut determination) -- LEADERBOARD.json now shows
rounds_played=4 for those 68 and rounds_played=2 (unchanged) for the 28
cut-missed players. Cross-checked two ways, in exact agreement:
  - normalized LEADERBOARD.json: 68 records with rounds_played==4
  - raw round_leaderboard_r4.html: 68 distinct player codes, identical
    set to the 68 above, none with a "0" (unplayed) round4score

WD/DQ: never assumed zero. withdrawn/disqualified flags are read per
player from the official normalized leaderboard and recorded as-is; the
raw page's own 기권/실격/WD/DQ legend-text occurrence count is also
checked (expected exactly 1 each -- the page's fixed legend -- if this
is ever greater than 1 a real WD/DQ exists in the free text and this
script hard-stops rather than silently assume none).

final_rank is the KLPGA site's OWN finish_position -- including any
real scorecard-countback tie resolution -- never recomputed or guessed
by this script. total_score arithmetic (r1+r2+r3+r4) is verified to
match for all 68, and rank is verified monotonic non-decreasing with
score_to_par.

NOTE on tie_flag: the normalized leaderboard's own `tie_flag` field was
found to be unreliable (0 for every player, even within a group that
shares an identical finish_position AND identical score_to_par/total --
an unambiguous real tie by the official numbers themselves). This
script therefore never reads `tie_flag`; final_tie is derived directly
from whether more than one player shares the same finish_position_numeric
with identical score_to_par/total_score, which this script verifies for
internal consistency (every such group must agree on to_par and total,
or the build hard-stops).
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
OUT_PATH = CONTENT / f"SOIL_{GAME_CODE}_FR_OFFICIAL_V1.json"


def _git_show(ref: str) -> str:
    return subprocess.run(
        ["git", "show", ref], cwd=REPO_ROOT, capture_output=True, check=True, text=True, encoding="utf-8",
    ).stdout


def to_par_num(tp):
    if tp in ("E", "", None):
        return 0
    try:
        return int(tp)
    except (TypeError, ValueError):
        return None


def main() -> None:
    lb = json.loads(_git_show(f"origin/reader/{GAME_CODE}:klpga_pipeline/normalized/{GAME_CODE}/LEADERBOARD.json"))
    assert lb["final_round"] == 4, f"expected a 4-round tournament (final_round=4), found {lb['final_round']}"
    records = lb["records"]
    assert len(records) == 96, f"expected 96 official entrants, found {len(records)}"
    for r in records:
        assert r["rounds_played"] in (2, 4), f"{r['player_id']}: unexpected rounds_played {r['rounds_played']} (expected 2=cut or 4=finished)"

    fr_players = [r for r in records if r["rounds_played"] == 4]
    cut_players = [r for r in records if r["rounds_played"] == 2]
    assert len(fr_players) == 68, f"expected 68 real FR finishers, found {len(fr_players)}"
    assert len(cut_players) == 28, f"expected 28 cut-missed players, found {len(cut_players)}"

    # WD/DQ -- read as-is, never assumed. Real WD/DQ players would show up
    # here with rounds_played < 4 (likely 2, grouped with cut_players above
    # unless they withdrew mid-FR) and withdrawn/disqualified != 0.
    wd_dq = [r for r in records if r["withdrawn"] or r["disqualified"]]

    for r in fr_players:
        assert r["r1_score"] is not None and r["r2_score"] is not None and r["r3_score"] is not None and r["r4_score"] is not None
        assert r["total_score"] == r["r1_score"] + r["r2_score"] + r["r3_score"] + r["r4_score"], (
            f"{r['player_id']}: total_score does not equal r1+r2+r3+r4"
        )

    r4_html = _git_show(f"origin/reader/{GAME_CODE}:klpga_pipeline/raw/{GAME_CODE}/round_leaderboard_r4.html")

    codes_r4 = set(re.findall(r'_playerCode="(\d+)"', r4_html))
    fr_ids = {r["player_id"] for r in fr_players}
    assert codes_r4 == fr_ids, "R4 raw page player codes != 68 real FR finishers from LEADERBOARD.json"

    zero_scores = set(re.findall(r'data-round4score="0"', r4_html))
    assert len(zero_scores) == 0, "at least one player still shows an unplayed (0) round4score -- FR may not be fully complete"

    for term in ("기권", "실격", "WD", "DQ"):
        count = len(re.findall(re.escape(term), r4_html))
        assert count == 1, (
            f"unexpected '{term}' occurrence count in R4 raw page: {count} (expected exactly 1, the legend) "
            f"-- a real WD/DQ may be present in free text; refusing to assume none"
        )

    # Rank/tie self-consistency against the official finish_position fields.
    ordered = sorted(fr_players, key=lambda r: r["finish_position_numeric"])
    rank_monotonic_errors = []
    prev_tp = None
    for r in ordered:
        tp = to_par_num(r["score_to_par"])
        if prev_tp is not None and tp is not None and tp < prev_tp:
            rank_monotonic_errors.append({"player_id": r["player_id"], "rank": r["finish_position"], "score_to_par": r["score_to_par"], "prev_seen": prev_tp})
        if tp is not None:
            prev_tp = tp

    by_rank: dict[int, list[dict]] = {}
    for r in ordered:
        by_rank.setdefault(r["finish_position_numeric"], []).append(r)
    tie_group_errors = []
    for rank_num, group in by_rank.items():
        if len(group) > 1:
            tps = {g["score_to_par"] for g in group}
            totals = {g["total_score"] for g in group}
            if len(tps) > 1 or len(totals) > 1:
                tie_group_errors.append({"rank": rank_num, "players": [g["player_id"] for g in group], "to_pars": sorted(tps), "totals": sorted(totals)})

    verification_errors = {
        "rank_monotonic_errors": rank_monotonic_errors,
        "tie_group_errors": tie_group_errors,
    }
    total_errors = sum(len(v) for v in verification_errors.values())
    if total_errors:
        raise SystemExit(f"FR arithmetic/consistency verification failed ({total_errors} errors): {json.dumps(verification_errors, ensure_ascii=False, indent=2)}")

    winner = ordered[0]
    if len(by_rank[1]) > 1:
        raise SystemExit(f"official rank 1 is a tie ({by_rank[1]}) -- refusing to report a single winner; needs operator review")

    out_records = []
    for r in sorted(fr_players, key=lambda x: x["finish_position_numeric"]):
        out_records.append({
            "player_id": r["player_id"],
            "player_name": r["player_name"],
            "final_rank": r["finish_position"],
            "final_rank_numeric": r["finish_position_numeric"],
            "final_tie": len(by_rank[r["finish_position_numeric"]]) > 1,
            "r1_score": r["r1_score"],
            "r2_score": r["r2_score"],
            "r3_score": r["r3_score"],
            "r4_score": r["r4_score"],
            "total_score": r["total_score"],
            "score_to_par": r["score_to_par"],
            "status": "FINISHED",
            "withdrawn": bool(r["withdrawn"]),
            "disqualified": bool(r["disqualified"]),
        })

    out = {
        "schema_version": "SOIL_2026100001_FR_OFFICIAL_V1",
        "game_code": GAME_CODE,
        "round": 4,
        "stage_label": "FR",
        "source": {
            "leaderboard": f"origin/reader/{GAME_CODE}:klpga_pipeline/normalized/{GAME_CODE}/LEADERBOARD.json",
            "r4_raw_page": f"origin/reader/{GAME_CODE}:klpga_pipeline/raw/{GAME_CODE}/round_leaderboard_r4.html",
            "neo_sync_run": "neo-sync.yml stage=results, 2026-11-01 (run #25 on ref neo-website-v2), PASS",
        },
        "field_determination_method": (
            "68 players with rounds_played==4 in the normalized leaderboard -- the same real cutmakers from "
            "scripts/278/282 -- cross-checked against the R4 raw leaderboard page (68 distinct player codes, "
            "none with an unplayed/0 round4score)."
        ),
        "field_count": len(out_records),
        "cut_missed_count": len(cut_players),
        "roster_total": len(records),
        "withdrawals": len(wd_dq),
        "withdrawals_detail": [{"player_id": r["player_id"], "player_name": r["player_name"], "withdrawn": bool(r["withdrawn"]), "disqualified": bool(r["disqualified"])} for r in wd_dq],
        "winner_player_id": winner["player_id"],
        "winner_player_name": winner["player_name"],
        "winner_total_strokes": winner["total_score"],
        "winner_score_to_par": winner["score_to_par"],
        "verification_errors": verification_errors,
        "verification_pass": total_errors == 0,
        "records": out_records,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": str(OUT_PATH),
        "field_count": len(out_records),
        "withdrawals": len(wd_dq),
        "winner": winner["player_name"],
        "winner_score_to_par": winner["score_to_par"],
        "verification_pass": out["verification_pass"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
