from __future__ import annotations
import argparse, json
from collector import fetch, load_json, PLAYER_ENDPOINT, GROUP_ENDPOINT

def verify_official_score(game, player, rnd, hole, official_par, official_strokes, cookie=None):
    """① Cross-check shotTrackerList row count for one hole against the
    REAL official per-hole score (from the player-detail page's own
    server-rendered scorecard, not assumed). Confirms the relationship:
    row count == official strokes, final row's pp_state should be '10'
    (HOLED) whenever the hole was completed."""
    status, raw = fetch(PLAYER_ENDPOINT, game, rnd, hole, player=player, cookie=cookie)
    obj = load_json(raw)
    shots = obj.get("shotTrackerList") or []
    shot_numbers = sorted(int(s["shot"]) for s in shots)
    last = max(shots, key=lambda s: int(s["shot"])) if shots else None
    result = {
        "check": "official_score_cross_check",
        "game": game, "player": player, "round": rnd, "hole": hole,
        "official_par": official_par,
        "official_strokes": official_strokes,
        "shotTrackerList_row_count": len(shots),
        "shot_numbers": shot_numbers,
        "shot_numbers_sequential_from_1": shot_numbers == list(range(1, len(shots) + 1)),
        "last_shot_pp_state": last["pp_state"] if last else None,
        "last_shot_is_holed": (last["pp_state"] == "10") if last else False,
        "row_count_matches_official_strokes": len(shots) == official_strokes,
    }
    result["PASS"] = bool(
        result["row_count_matches_official_strokes"]
        and result["shot_numbers_sequential_from_1"]
        and result["last_shot_is_holed"]
    )
    return result


def verify_group_vs_player(game, rnd, hole, group_no, player_codes=None, cookie=None):
    """② Cross-validate getGroupShotTracker against getShotTracker for the
    SAME group and hole: for every player in the group, the group
    endpoint's shots for that player must match the per-player
    endpoint's shots exactly on shot count, shot numbers, pp_state,
    coordinates, and distance. Never assumes equivalence -- compares
    real responses field by field. If player_codes is not given, the
    real group's full membership is discovered from groupPlayerList
    rather than assumed."""
    gstatus, graw = fetch(GROUP_ENDPOINT, game, rnd, hole, group_no=group_no, cookie=cookie)
    gobj = load_json(graw)
    group_player_list = gobj.get("groupPlayerList") or []
    group_shots = gobj.get("groupShotTrackerList") or []
    group_by_player = {}
    for s in group_shots:
        group_by_player.setdefault(str(s.get("playerCode")), []).append(s)

    if not player_codes:
        discovered = []
        for entry in group_player_list:
            pc = entry.get("playerCode") or entry.get("player_code")
            if pc is not None:
                discovered.append(str(pc))
        player_codes = discovered or sorted(group_by_player.keys())

    FIELDS = ["shot", "pp_state", "pp_x", "pp_y", "pp_greenx", "pp_greeny", "pp_distance", "pp_distanceLen", "pp_altitude"]

    per_player_results = {}
    all_pass = True
    for pc in player_codes:
        pstatus, praw = fetch(PLAYER_ENDPOINT, game, rnd, hole, player=pc, cookie=cookie)
        pobj = load_json(praw)
        player_shots = sorted((pobj.get("shotTrackerList") or []), key=lambda s: int(s["shot"]))
        g_shots_for_player = sorted(group_by_player.get(str(pc), []), key=lambda s: int(s["shot"]))

        mismatches = []
        if len(player_shots) != len(g_shots_for_player):
            mismatches.append(f"shot_count player={len(player_shots)} group={len(g_shots_for_player)}")
        else:
            for ps, gs in zip(player_shots, g_shots_for_player):
                for f in FIELDS:
                    pv, gv = ps.get(f), gs.get(f)
                    if str(pv) != str(gv):
                        mismatches.append(f"shot={ps.get('shot')} field={f} player={pv!r} group={gv!r}")

        per_player_results[pc] = {
            "player_shot_count": len(player_shots),
            "group_shot_count_for_player": len(g_shots_for_player),
            "player_in_group_response": str(pc) in group_by_player,
            "mismatches": mismatches,
            "PASS": not mismatches and str(pc) in group_by_player,
        }
        if not per_player_results[pc]["PASS"]:
            all_pass = False

    return {
        "check": "group_vs_player_cross_validation",
        "game": game, "round": rnd, "hole": hole, "group_no": group_no,
        "group_player_list_raw": group_player_list,
        "group_response_player_codes": sorted(group_by_player.keys()),
        "players_checked": list(player_codes),
        "per_player": per_player_results,
        "PASS": all_pass,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--player", required=True)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--hole", type=int, required=True)
    ap.add_argument("--official-par", type=int, required=True)
    ap.add_argument("--official-strokes", type=int, required=True)
    ap.add_argument("--group-no", required=True)
    ap.add_argument("--group-player-codes", default="", help="comma-separated playerCodes to check (optional -- auto-discovered from groupPlayerList if omitted)")
    ap.add_argument("--cookie")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    check1 = verify_official_score(a.game, a.player, a.round, a.hole, a.official_par, a.official_strokes, a.cookie)
    explicit_codes = [c for c in a.group_player_codes.split(",") if c] or None
    check2 = verify_group_vs_player(a.game, a.round, a.hole, a.group_no, explicit_codes, a.cookie)

    overall = {
        "official_score_cross_check": check1,
        "group_vs_player_cross_validation": check2,
        "OVERALL_PASS": bool(check1["PASS"] and check2["PASS"]),
    }
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(overall, fh, ensure_ascii=False, indent=2)
    print(json.dumps(overall, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
