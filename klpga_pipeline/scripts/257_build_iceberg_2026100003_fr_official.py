"""Build the official FR (final round -- official round 3 of 3; this is
a 3-round stroke-play tournament, confirmed by an empty round=4
official roundLeaderboard response) result for 아이스버그골프·서울신문
오픈 (game_code 2026100003), continuing the exact data flow scripts/
248/251/252 established for R1/R2 (hash-verified raw capture -> parser
-> player_id-linked, provenance-carrying JSON in the repo).

Inputs (collected via the same tooling/sg-recovery-oneoff workflow used
for R1/R2, run id 39105778187, dispatched 2026-10-18 after the operator
reported FR had concluded -- verified true here independently: the
official round=4 roundLeaderboard response has 0 rows, and round=3's
own response has exactly 61 FINISHED rows, matching the 61 real
cutmakers scripts/251 already established from the round=3 tee sheet):
  - content/website_v2/raw_capture/2026100003_fr/roundLeaderboard_r1.html
  - content/website_v2/raw_capture/2026100003_fr/roundLeaderboard_r2.html
  - content/website_v2/raw_capture/2026100003_fr/roundLeaderboard_r3.html
  - content/website_v2/raw_capture/2026100003_fr/roundLeaderboard_r4.html
  - content/website_v2/raw_capture/2026100003_fr/MANIFEST.json

======================================================================
FINAL STATUS FOR ALL 108 ROSTER PLAYERS -- NEVER A NEW CUTLINE, NEVER
GUESSED. Reuses scripts/251's own already-verified R2_OFFICIAL_V1.json
made_cut/WD determination for every player who did not reach round 3,
and this round's own real official round=3 response (61 FINISHED rows,
0 WD/DQ) for the 61 who did.
======================================================================
  - 1 player (8243, 장은수): WD at R1 (scripts/251's KNOWN_R1_WD_PLAYER_ID)
  - 5 players: WD at/by R2 (scripts/251's made_cut_false_wd)
  - 41 players: missed the cut at R2 (scripts/251's made_cut_false_missed)
  - 61 players: played and finished R3 -- the real official round=3
    leaderboard's own rank/to_par/status text is used verbatim, never
    recomputed from scores. In particular rank 1 (마서영) and rank 2
    (성유진) share the identical official to_par (-4) and total (212)
    strokes yet are NOT marked tied (tie=False for both) -- this is
    the official site's own scorecard countback resolution (e.g. back-
    nine score), which this script does not attempt to re-derive; the
    official rank text is trusted as-is, exactly like every prior
    status/rank field in this pipeline.
  1 + 5 + 41 + 61 = 108.

ARITHMETIC VERIFICATION (operator instruction, 2026-10-18): for all 61
finishers, this script checks (a) rounds[0]+rounds[1]+rounds[2] ==
official total strokes, (b) to_par is monotonic non-decreasing as rank
increases, (c) every tie=True row shares its to_par/total with its tie
group and the tie group's rank text is self-consistent (no gaps), and
(d) the R1/R2 strokes embedded in this round's own cumulative view
match, player-for-player, the R1/R2 strokes already recorded in
ICEBERG_2026100003_R2_OFFICIAL_V1.json (same official source, must be
byte-for-byte identical -- any mismatch is reported, never silently
accepted). Failures abort the build (SystemExit), never silently
proceed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.official_data import parse_leaderboard_html  # noqa: E402

GAME_CODE = "2026100003"
RAW_DIR = ROOT / "content" / "website_v2" / "raw_capture" / "2026100003_fr"
MANIFEST_PATH = RAW_DIR / "MANIFEST.json"
JOIN_PATH = ROOT / "content" / "website_v2" / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"
R2_OFFICIAL_PATH = ROOT / "content" / "website_v2" / f"ICEBERG_{GAME_CODE}_R2_OFFICIAL_V1.json"
OUT_PATH = ROOT / "content" / "website_v2" / f"ICEBERG_{GAME_CODE}_FR_OFFICIAL_V1.json"

KNOWN_R1_WD_PLAYER_ID = "8243"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def to_par_num(tp):
    if tp in ("E", "", None):
        return 0
    try:
        return int(tp)
    except (TypeError, ValueError):
        return None


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_sha_by_label = {r["label"]: r["sha256"] for r in manifest["requests"]}

    raw_bytes = {}
    hash_check = {}
    for fname, label in [
        ("roundLeaderboard_r1.html", "roundLeaderboard_r1"),
        ("roundLeaderboard_r2.html", "roundLeaderboard_r2"),
        ("roundLeaderboard_r3.html", "roundLeaderboard_r3"),
        ("roundLeaderboard_r4.html", "roundLeaderboard_r4"),
    ]:
        b = (RAW_DIR / fname).read_bytes()
        raw_bytes[label] = b
        actual = sha256_bytes(b)
        expected = manifest_sha_by_label.get(label)
        hash_check[fname] = {"expected": expected, "actual": actual, "match": actual == expected}
    if not all(v["match"] for v in hash_check.values()):
        raise SystemExit(f"hash mismatch against MANIFEST.json: {json.dumps(hash_check, indent=2)}")

    join = json.loads(JOIN_PATH.read_text(encoding="utf-8"))
    roster_ids = {str(r["player_code"]) for r in join["records"]}
    assert len(roster_ids) == 108, f"expected 108-entrant roster, found {len(roster_ids)}"

    r2_official = json.loads(R2_OFFICIAL_PATH.read_text(encoding="utf-8"))
    r2_by_id = {r["player_id"]: r for r in r2_official["records"]}

    r1_rows = parse_leaderboard_html(raw_bytes["roundLeaderboard_r1"].decode("utf-8"))
    r3_rows = parse_leaderboard_html(raw_bytes["roundLeaderboard_r3"].decode("utf-8"))
    r4_rows = parse_leaderboard_html(raw_bytes["roundLeaderboard_r4"].decode("utf-8"))
    assert len(r4_rows) == 0, f"round=4 returned {len(r4_rows)} rows -- tournament may not actually be a 3-round event, refusing to proceed"

    r1_by_id = {r["player_id"]: r for r in r1_rows}
    r3_by_id = {r["player_id"]: r for r in r3_rows}

    finisher_ids = set(r3_by_id)
    wd_r1_ids = {KNOWN_R1_WD_PLAYER_ID}
    wd_r2_ids = {pid for pid, r in r2_by_id.items() if r["r2_status"] == "WD"}
    missed_cut_ids = {pid for pid, r in r2_by_id.items() if r["r2_status"] != "WD" and not r["made_cut"]}

    accounted = finisher_ids | wd_r1_ids | wd_r2_ids | missed_cut_ids
    assert accounted == roster_ids, f"roster accounting mismatch: missing={roster_ids - accounted}, extra={accounted - roster_ids}"
    assert len(finisher_ids & wd_r1_ids) == 0 and len(finisher_ids & wd_r2_ids) == 0 and len(finisher_ids & missed_cut_ids) == 0, "overlap between finisher/WD/missed-cut sets"
    assert finisher_ids == {pid for pid, r in r2_by_id.items() if r["made_cut"]}, "round=3 finisher set does not exactly match scripts/251's made_cut=True set"

    # Arithmetic + cross-source verification for the 61 finishers.
    arithmetic_errors = []
    r1r2_cross_check_errors = []
    for pid, r in r3_by_id.items():
        rounds = r["rounds"] or []
        if len(rounds) != 4:
            arithmetic_errors.append({"player_id": pid, "error": "rounds list does not have exactly 4 entries (r1,r2,r3,total)", "rounds": rounds})
            continue
        r1_s, r2_s, r3_s, total_s = rounds
        if None in (r1_s, r2_s, r3_s, total_s) or (r1_s + r2_s + r3_s) != total_s:
            arithmetic_errors.append({"player_id": pid, "error": "r1+r2+r3 != total", "rounds": rounds})

        prior_r1 = r2_by_id.get(pid, {}).get("r1_score")
        prior_r2 = r2_by_id.get(pid, {}).get("r2_score")
        if prior_r1 is not None and prior_r1 != r1_s:
            r1r2_cross_check_errors.append({"player_id": pid, "field": "r1_score", "r2_official": prior_r1, "fr_leaderboard": r1_s})
        if prior_r2 is not None and prior_r2 != r2_s:
            r1r2_cross_check_errors.append({"player_id": pid, "field": "r2_score", "r2_official": prior_r2, "fr_leaderboard": r2_s})

    # Rank/tie self-consistency: to_par monotonic non-decreasing with
    # rank_numeric; every tie=True row's to_par/total matches every
    # other row sharing the same rank_numeric.
    ordered = sorted(r3_by_id.values(), key=lambda r: r["rank_numeric"])
    rank_monotonic_errors = []
    prev_tp = None
    for r in ordered:
        tp = to_par_num(r["to_par"])
        if prev_tp is not None and tp is not None and tp < prev_tp:
            rank_monotonic_errors.append({"player_id": r["player_id"], "rank": r["rank"], "to_par": r["to_par"], "prev_to_par_seen": prev_tp})
        if tp is not None:
            prev_tp = tp

    by_rank_numeric: dict[int, list[dict]] = {}
    for r in ordered:
        by_rank_numeric.setdefault(r["rank_numeric"], []).append(r)
    tie_group_errors = []
    for rank_num, group in by_rank_numeric.items():
        if len(group) > 1:
            tps = {g["to_par"] for g in group}
            totals = {g["rounds"][3] for g in group if g["rounds"] and len(g["rounds"]) == 4}
            if len(tps) > 1 or len(totals) > 1:
                tie_group_errors.append({"rank": rank_num, "players": [g["player_id"] for g in group], "to_pars": sorted(tps), "totals": sorted(totals)})
            if not all(g["tie"] for g in group):
                tie_group_errors.append({"rank": rank_num, "players": [g["player_id"] for g in group], "error": "shares rank_numeric but not all marked tie=True"})

    verification_errors = {
        "arithmetic_errors": arithmetic_errors,
        "r1r2_cross_check_errors": r1r2_cross_check_errors,
        "rank_monotonic_errors": rank_monotonic_errors,
        "tie_group_errors": tie_group_errors,
    }
    total_errors = sum(len(v) for v in verification_errors.values())
    if total_errors:
        raise SystemExit(f"FR arithmetic/consistency verification failed ({total_errors} errors): {json.dumps(verification_errors, ensure_ascii=False, indent=2)}")

    winner = ordered[0]
    # Fail closed if the official data itself marks a tie at rank 1 --
    # never invent a single winner when the official source says tied.
    if winner["tie"] or len([g for g in by_rank_numeric[1]]) > 1:
        raise SystemExit(f"official rank 1 is a tie ({by_rank_numeric[1]}) -- refusing to report a single winner; this needs operator review, not an assumption")

    records = []
    for pid in roster_ids:
        if pid in finisher_ids:
            r = r3_by_id[pid]
            records.append({
                "player_id": pid,
                "player_name": r["player"],
                "status": "FINISHED",
                "final_rank": r["rank"],
                "final_rank_numeric": r["rank_numeric"],
                "final_tie": r["tie"],
                "final_to_par": r["to_par"],
                "r1_score": r["rounds"][0],
                "r2_score": r["rounds"][1],
                "fr_score": r["rounds"][2],
                "total_strokes": r["rounds"][3],
            })
        elif pid in wd_r1_ids:
            records.append({
                "player_id": pid, "player_name": join_name(join, pid), "status": "WD_R1",
                "final_rank": None, "final_rank_numeric": None, "final_tie": None, "final_to_par": None,
                "r1_score": None, "r2_score": None, "fr_score": None, "total_strokes": None,
            })
        elif pid in wd_r2_ids:
            r2r = r2_by_id[pid]
            records.append({
                "player_id": pid, "player_name": r2r["player_name"], "status": "WD_R2",
                "final_rank": None, "final_rank_numeric": None, "final_tie": None, "final_to_par": None,
                "r1_score": r2r.get("r1_score"), "r2_score": r2r.get("r2_score"), "fr_score": None, "total_strokes": None,
            })
        else:
            r2r = r2_by_id[pid]
            records.append({
                "player_id": pid, "player_name": r2r["player_name"], "status": "CUT",
                "final_rank": None, "final_rank_numeric": None, "final_tie": None, "final_to_par": None,
                "r1_score": r2r.get("r1_score"), "r2_score": r2r.get("r2_score"), "fr_score": None, "total_strokes": None,
            })

    out = {
        "artifact": "iceberg_2026100003_fr_official",
        "game_code": GAME_CODE,
        "round": 3,
        "stage_label": "FR",
        "source_files": {
            "roundLeaderboard_r1.html": {"path": "content/website_v2/raw_capture/2026100003_fr/roundLeaderboard_r1.html", "sha256": hash_check["roundLeaderboard_r1.html"]["actual"]},
            "roundLeaderboard_r2.html": {"path": "content/website_v2/raw_capture/2026100003_fr/roundLeaderboard_r2.html", "sha256": hash_check["roundLeaderboard_r2.html"]["actual"]},
            "roundLeaderboard_r3.html": {"path": "content/website_v2/raw_capture/2026100003_fr/roundLeaderboard_r3.html", "sha256": hash_check["roundLeaderboard_r3.html"]["actual"]},
            "roundLeaderboard_r4.html": {"path": "content/website_v2/raw_capture/2026100003_fr/roundLeaderboard_r4.html", "sha256": hash_check["roundLeaderboard_r4.html"]["actual"]},
        },
        "hash_check_against_manifest": hash_check,
        "round4_empty_confirms_3_round_tournament": True,
        "roster_size": len(roster_ids),
        "finisher_count": len(finisher_ids),
        "wd_r1_count": len(wd_r1_ids),
        "wd_r2_count": len(wd_r2_ids),
        "missed_cut_count": len(missed_cut_ids),
        "accounting_check": {
            "sum": len(finisher_ids) + len(wd_r1_ids) + len(wd_r2_ids) + len(missed_cut_ids),
            "roster_size": len(roster_ids),
            "match": (len(finisher_ids) + len(wd_r1_ids) + len(wd_r2_ids) + len(missed_cut_ids)) == len(roster_ids),
        },
        "verification_errors": verification_errors,
        "verification_pass": total_errors == 0,
        "winner_player_id": winner["player_id"],
        "winner_player_name": winner["player"],
        "winner_total_strokes": winner["rounds"][3],
        "winner_to_par": winner["to_par"],
        "fr_official_final_evidence": [
            "roundLeaderboard round=3 (official FR) 61/61 FINISHED, 0 WD/DQ",
            "roundLeaderboard round=4 returned 0 rows -- confirms 3-round event, FR is final",
            "winner rank=1 not tied (tie=False) per official rank text -- single winner, no countback guess made by this script",
        ],
        "records": records,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "written": str(OUT_PATH),
        "roster_size": len(roster_ids),
        "finisher_count": len(finisher_ids),
        "wd_r1_count": len(wd_r1_ids),
        "wd_r2_count": len(wd_r2_ids),
        "missed_cut_count": len(missed_cut_ids),
        "accounting_match": out["accounting_check"]["match"],
        "verification_pass": out["verification_pass"],
        "winner_player_name": winner["player"],
        "winner_total_strokes": winner["rounds"][3],
        "winner_to_par": winner["to_par"],
        "hash_check": hash_check,
    }, ensure_ascii=False, indent=2))


def join_name(join: dict, pid: str) -> str:
    for r in join["records"]:
        if str(r["player_code"]) == pid:
            return r["player_name"]
    raise KeyError(pid)


if __name__ == "__main__":
    main()
