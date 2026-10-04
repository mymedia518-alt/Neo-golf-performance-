from __future__ import annotations
import argparse, json, re, time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://klpga.co.kr"
# Confirmed real endpoint (POST, HTML fragment response, not JSON) --
# same contract already proven in this repo's production leaderboard
# collector (klpga_pipeline/src/klpga/collectors/leaderboard.py), not
# guessed. This tool re-implements only player/round discovery
# independently, to keep neo_klpga_shot_source self-contained.
ENDPOINT = "/load/leaderboard/roundLeaderboard"

# Confirmed real row/detail attributes (see leaderboard_parser.py):
# each player row carries data-rank, and a _playerCode/_playerName
# detail attribute either on the row itself or a descendant.
ROW_RE = re.compile(r"<[^>]*data-rank\s*=", re.IGNORECASE)
TAG_RE = re.compile(r"<[a-zA-Z][^>]*>")
ATTR_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_-]*)\s*=\s*"([^"]*)"')


def fetch_round_html(game, rnd, cookie=None):
    body = urlencode({"gameCode": game, "round": rnd}).encode()
    headers = {
        "Accept": "*/*", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE}/web/leaderboard/leaderboard?gameCode={game}",
        "User-Agent": "Mozilla/5.0 NEO-Golf-Data/1.0",
    }
    if cookie: headers["Cookie"] = cookie
    req = Request(BASE + ENDPOINT, data=body, headers=headers, method="POST")
    with urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def _attrs(tag_text):
    return {k.lower(): v for k, v in ATTR_RE.findall(tag_text)}


def parse_player_rows(html):
    """Minimal, independent re-implementation of the confirmed real
    contract: every element carrying data-rank is one player's row; the
    _playerCode/_playerName detail attributes live on that same tag or
    a nearby descendant tag within the row's markup chunk. Never
    guesses a player identity it can't find attributes for -- such a
    row is skipped, not fabricated."""
    out = []
    # Split the fragment at each data-rank-bearing tag, searching a
    # bounded window after it for the matching _playerCode/_playerName
    # attributes (handles both "same tag" and "nested descendant" real
    # cases seen in production).
    for m in ROW_RE.finditer(html):
        window = html[m.start(): m.start() + 4000]
        tags = TAG_RE.findall(window)
        merged = {}
        for t in tags[:12]:
            merged.update(_attrs(t))
            if "_playercode" in merged:
                break
        player_code = merged.get("_playercode")
        if not player_code:
            continue
        out.append({
            "player_code": player_code.strip(),
            "player_name": (merged.get("_playername") or "").strip() or None,
            "rank_display": (merged.get("data-rank") or "").strip() or None,
        })
    return out


def discover(game, rounds, cookie=None, sleep=0.5):
    """Fetch each requested round's real leaderboard and record, per
    player_code, every round in which they actually appear (present in
    the field that round) -- never assumed from another round."""
    players = {}
    per_round_counts = {}
    for rnd in rounds:
        html = fetch_round_html(game, rnd, cookie)
        rows = parse_player_rows(html)
        per_round_counts[rnd] = len(rows)
        for row in rows:
            pc = row["player_code"]
            entry = players.setdefault(pc, {"player_name": row["player_name"], "rounds": []})
            if row["player_name"] and not entry["player_name"]:
                entry["player_name"] = row["player_name"]
            entry["rounds"].append(rnd)
        time.sleep(sleep)
    return players, per_round_counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--rounds", default="1,2,3,4")
    ap.add_argument("--cookie")
    ap.add_argument("--sleep", type=float, default=0.5)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rounds = [int(x) for x in a.rounds.split(",")]
    players, per_round_counts = discover(a.game, rounds, a.cookie, a.sleep)
    result = {
        "game_code": a.game,
        "rounds_queried": rounds,
        "per_round_row_counts": per_round_counts,
        "player_count": len(players),
        "players": players,
    }
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "players"}, ensure_ascii=False, indent=2))
    print(f"DONE players={len(players)} -> {a.out}")


if __name__ == "__main__":
    main()
