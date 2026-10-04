from __future__ import annotations
import argparse, json, time
from collector import fetch, load_json, GROUP_ENDPOINT

def discover_groups_for_round(game, rnd, hole, max_group_no, cookie=None, sleep=0.3):
    """Probe groupNo=1..max_group_no for one representative hole and
    record which group numbers are real (non-empty groupPlayerList),
    together with their real membership -- never assumes a group
    count, discovers it from real responses."""
    groups = {}
    for group_no in range(1, max_group_no + 1):
        try:
            status, raw = fetch(GROUP_ENDPOINT, game, rnd, hole, group_no=str(group_no), cookie=cookie)
            obj = load_json(raw)
            player_list = obj.get("groupPlayerList") or []
            if player_list:
                groups[str(group_no)] = [
                    {"playerCode": str(p.get("playerCode")), "playerName": p.get("playerName")}
                    for p in player_list if p.get("playerCode") is not None
                ]
                print(f"PASS round={rnd} groupNo={group_no} members={len(player_list)}")
            else:
                print(f"EMPTY round={rnd} groupNo={group_no}")
        except Exception as e:
            print(f"FAIL round={rnd} groupNo={group_no}: {e}")
        time.sleep(sleep)
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--rounds", default="1,2,3,4")
    ap.add_argument("--probe-hole", type=int, default=1)
    ap.add_argument("--max-group-no", type=int, default=45)
    ap.add_argument("--cookie")
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    result = {"game_code": a.game, "probe_hole": a.probe_hole, "rounds": {}}
    for rnd in [int(x) for x in a.rounds.split(",")]:
        groups = discover_groups_for_round(a.game, rnd, a.probe_hole, a.max_group_no, a.cookie, a.sleep)
        result["rounds"][str(rnd)] = groups
        total_players = sum(len(v) for v in groups.values())
        print(f"DONE round={rnd} groups={len(groups)} players_covered={total_players}")

    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(f"WROTE {a.out}")


if __name__ == "__main__":
    main()
