"""Additional REAL spot-checks of groupShotTrackerList's shape across
different rounds/holes/group sizes, before trusting the shape
confirmed at (round=4, hole=18, group=21) for the whole tournament.
Dumps every raw response fetched (unmodified) and cross-validates
against the real per-player endpoint for the same round/hole -- never
guesses, never treats a single sample as general.
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
from collector import fetch, load_json, PLAYER_ENDPOINT, GROUP_ENDPOINT
from inspect_real_shape import describe_value, contains_nested_json_string


def find_first_nonempty_group(game, rnd, hole, max_probe, cookie, sleep, dump_dir):
    for group_no in range(1, max_probe + 1):
        status, raw = fetch(GROUP_ENDPOINT, game, rnd, hole, group_no=str(group_no), cookie=cookie)
        obj = load_json(raw)
        if obj.get("groupPlayerList"):
            Path(dump_dir, f"group_{group_no}_R{rnd}_H{hole:02d}.json").write_bytes(raw)
            return group_no, obj
        time.sleep(sleep)
    return None, None


def spotcheck_one(game, rnd, hole, max_probe, cookie, sleep, dump_dir):
    print(f"\n{'#'*80}\nSPOT-CHECK round={rnd} hole={hole}\n{'#'*80}")
    group_no, gobj = find_first_nonempty_group(game, rnd, hole, max_probe, cookie, sleep, dump_dir)
    if group_no is None:
        print(f"NO real non-empty group found in range 1..{max_probe} for round={rnd} hole={hole} -- cannot spot-check here.")
        return {"round": rnd, "hole": hole, "found_group": None, "PASS": False, "reason": "no_group_found"}

    gst = gobj.get("groupShotTrackerList")
    gpl = gobj.get("groupPlayerList")
    print(f"found real groupNo={group_no}, groupPlayerList len={len(gpl)}")
    print(f"groupShotTrackerList top-level type: {type(gst).__name__}")
    if isinstance(gst, dict):
        print(f"  keys: {list(gst.keys())}")
    elif isinstance(gst, list):
        print(f"  len: {len(gst)}")
    nested = contains_nested_json_string(gobj)
    print(f"nested JSON-encoded strings found: {nested if nested else 'none'}")

    # Flatten defensively without assuming dict-vs-list.
    flat_shots = []
    if isinstance(gst, dict):
        for v in gst.values():
            if isinstance(v, list):
                flat_shots.extend(v)
    elif isinstance(gst, list):
        for v in gst:
            if isinstance(v, list):
                flat_shots.extend(v)
            elif isinstance(v, dict):
                flat_shots.append(v)
    group_by_player = {}
    for s in flat_shots:
        if isinstance(s, dict):
            group_by_player.setdefault(str(s.get("playerCode")), []).append(s)

    FIELDS = ["shot", "pp_state", "pp_x", "pp_y", "pp_greenx", "pp_greeny", "pp_distance", "pp_distanceLen", "pp_altitude"]
    per_player = {}
    all_pass = True
    for p in gpl:
        pc = str(p.get("playerCode"))
        status, praw = fetch(PLAYER_ENDPOINT, game, rnd, hole, player=pc, cookie=cookie)
        Path(dump_dir, f"player_{pc}_R{rnd}_H{hole:02d}.json").write_bytes(praw)
        pobj = load_json(praw)
        pshots = sorted(pobj.get("shotTrackerList") or [], key=lambda s: int(s["shot"]))
        gshots = sorted(group_by_player.get(pc, []), key=lambda s: int(s["shot"]))
        mismatches = []
        if len(pshots) != len(gshots):
            mismatches.append(f"shot_count player={len(pshots)} group={len(gshots)}")
        else:
            for ps, gs in zip(pshots, gshots):
                for f in FIELDS:
                    if str(ps.get(f)) != str(gs.get(f)):
                        mismatches.append(f"shot={ps.get('shot')} field={f} player={ps.get(f)!r} group={gs.get(f)!r}")
        per_player[pc] = {"player_shots": len(pshots), "group_shots": len(gshots), "mismatches": mismatches}
        if mismatches:
            all_pass = False
        print(f"  player {pc}: player_shots={len(pshots)} group_shots={len(gshots)} mismatches={len(mismatches)}")
        time.sleep(sleep)

    return {
        "round": rnd, "hole": hole, "found_group": group_no,
        "groupShotTrackerList_type": type(gst).__name__,
        "nested_json_strings": nested,
        "per_player": per_player,
        "PASS": all_pass,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--cases", required=True, help="semicolon-separated round:hole pairs, e.g. '1:1;3:9'")
    ap.add_argument("--max-probe", type=int, default=10)
    ap.add_argument("--cookie")
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--dump-dir", default="spotcheck_raw_dump")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    Path(a.dump_dir).mkdir(parents=True, exist_ok=True)

    results = []
    for case in a.cases.split(";"):
        rnd_s, hole_s = case.split(":")
        results.append(spotcheck_one(a.game, int(rnd_s), int(hole_s), a.max_probe, a.cookie, a.sleep, a.dump_dir))

    overall = {"game_code": a.game, "cases": results, "ALL_PASS": all(r["PASS"] for r in results)}
    Path(a.out).write_text(json.dumps(overall, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + json.dumps(overall, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
