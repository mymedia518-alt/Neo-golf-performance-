from __future__ import annotations
import argparse, datetime as dt, hashlib, json, sqlite3, time, uuid
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://klpga.co.kr"
PLAYER_ENDPOINT = "/ajax/leaderboard/getShotTracker"
GROUP_ENDPOINT = "/ajax/leaderboard/getGroupShotTracker"

# Official KLPGA pp_state mapping, as confirmed from KLPGA's own JS by the operator.
# Any code not in this table must NEVER be guessed/interpreted: it is preserved as
# UNKNOWN_<code> and logged, per explicit operating instruction.
STATE = {
    "1": ("페어웨이", "FAIRWAY"), "2": ("러프", "ROUGH"),
    "3": ("그린", "GREEN"), "4": ("OB", "OB"),
    "5": ("페널티구역", "PENALTY_AREA"), "6": ("벙커", "BUNKER"),
    "7": ("분실구", "LOST_BALL"), "8": ("벌타", "PENALTY_STROKE"),
    "9": ("그린주변벙커", "GREENSIDE_BUNKER"), "10": ("홀인", "HOLED"),
    "12": ("프린지", "FRINGE"),
}

def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat()
def f(v):
    try: return float(v) if v not in (None, "") else None
    except (TypeError, ValueError): return None

def map_state(sc, unknown_log_path):
    """Map a pp_state code to (ko, en). Unknown codes are preserved as
    UNKNOWN_<code> (never guessed) and appended to an unknown-code log."""
    if sc is None:
        return None, None
    if sc in STATE:
        return STATE[sc]
    unknown_log_path.parent.mkdir(parents=True, exist_ok=True)
    with unknown_log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": now_iso(), "unknown_pp_state": sc}, ensure_ascii=False) + "\n")
    label = f"UNKNOWN_{sc}"
    return label, label

def fetch(endpoint, game, rnd, hole, player=None, group_no=None, cookie=None):
    params = {"gameCode": game, "round": rnd, "hole": hole}
    if player is not None:
        params["playerCode"] = player
    if group_no is not None:
        params["groupNo"] = group_no
    body = urlencode(params).encode()
    headers = {
        "Accept": "*/*", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE}/web/leaderboard/leaderboard?gameCode={game}",
        "User-Agent": "Mozilla/5.0 NEO-Golf-Data/1.0",
    }
    if cookie: headers["Cookie"] = cookie
    req = Request(BASE + endpoint, data=body, headers=headers, method="POST")
    with urlopen(req, timeout=30) as r:
        raw = r.read(); status = r.status
    return status, raw

def save_raw(root, game, kind, key, rnd, hole, status, raw):
    """kind: 'player_shot' or 'group_shot'. key: player_code or group_no.
    Never overwrites: a differing response at the same path is saved under a
    sha-suffixed filename instead."""
    digest = hashlib.sha256(raw).hexdigest()
    p = root / "raw" / game / kind / str(key) / f"R{rnd}" / f"H{hole:02d}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        old = p.read_bytes()
        if hashlib.sha256(old).hexdigest() != digest:
            p = p.with_name(f"H{hole:02d}_{digest[:12]}.json")
    if not p.exists():
        p.write_bytes(raw)
    return p, digest

def load_json(raw):
    txt = raw.decode("utf-8-sig").strip()
    return json.loads(txt)

def normalize_player(db, root, game, player, rnd, hole, status, raw_path, digest, obj):
    source_id = str(uuid.uuid4())
    unknown_log = root / "logs" / game / "unknown_pp_state.jsonl"
    con = sqlite3.connect(db)
    con.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
    con.execute("INSERT OR IGNORE INTO klpga_shot_raw_manifest VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (source_id, game, PLAYER_ENDPOINT, player, None, rnd, hole, now_iso(), status, digest, str(raw_path)))
    row = con.execute("SELECT source_id FROM klpga_shot_raw_manifest WHERE game_code=? AND endpoint=? AND player_code=? AND round=? AND hole=? AND sha256=?",
        (game, PLAYER_ENDPOINT, player, rnd, hole, digest)).fetchone()
    source_id = row[0]
    shots = obj.get("shotTrackerList") or []
    known_fields = {"playerCode", "gameCode", "round", "hole", "shot", "pp_state", "pp_distance",
                    "pp_distanceLen", "pp_altitude", "pp_x", "pp_y", "pp_greenx", "pp_greeny",
                    "playerName", "shotVideoYN"}
    extra_fields_seen = set()
    for v in shots:
        extra_fields_seen |= (set(v.keys()) - known_fields)
        sc = str(v.get("pp_state")) if v.get("pp_state") is not None else None
        ko, en = map_state(sc, unknown_log)
        vals = (game, str(v.get("playerCode") or player), v.get("playerName"), int(v.get("round") or rnd),
                int(v.get("hole") or hole), int(v["shot"]), sc, ko, en, f(v.get("pp_distance")),
                f(v.get("pp_distanceLen")), f(v.get("pp_altitude")), f(v.get("pp_x")), f(v.get("pp_y")),
                f(v.get("pp_greenx")), f(v.get("pp_greeny")), v.get("shotVideoYN"), source_id,
                json.dumps(v, ensure_ascii=False, separators=(",", ":")))
        con.execute("INSERT OR REPLACE INTO klpga_player_shot VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", vals)
    con.commit(); con.close()
    if extra_fields_seen:
        extra_log = root / "logs" / game / "extra_fields_seen.jsonl"
        extra_log.parent.mkdir(parents=True, exist_ok=True)
        with extra_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": now_iso(), "round": rnd, "hole": hole, "player": player,
                                  "extra_fields": sorted(extra_fields_seen)}, ensure_ascii=False) + "\n")
    return len(shots)

def collect_player(game, player, rounds, holes, root, db, cookie=None, sleep=0.35):
    total = 0
    results = []
    for rnd in rounds:
        for hole in holes:
            try:
                status, raw = fetch(PLAYER_ENDPOINT, game, rnd, hole, player=player, cookie=cookie)
                path, digest = save_raw(root, game, "player_shot", player, rnd, hole, status, raw)
                n = normalize_player(db, root, game, player, rnd, hole, status, path, digest, load_json(raw))
                total += n
                results.append({"round": rnd, "hole": hole, "status": "PASS", "shots": n})
                print(f"PASS {game} player={player} R{rnd} H{hole:02d} shots={n}")
            except Exception as e:
                results.append({"round": rnd, "hole": hole, "status": "FAIL", "error": str(e)})
                print(f"FAIL {game} player={player} R{rnd} H{hole:02d}: {e}")
            time.sleep(sleep)
    return total, results

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True); ap.add_argument("--player", required=True)
    ap.add_argument("--rounds", default="1,2,3,4"); ap.add_argument("--holes", default="1-18")
    ap.add_argument("--root", default="./NEO_DATA_ROOT_LOCAL"); ap.add_argument("--cookie")
    ap.add_argument("--sleep", type=float, default=0.35)
    a = ap.parse_args()
    root = Path(a.root); db = root / "normalized" / "klpga_shots.sqlite"; db.parent.mkdir(parents=True, exist_ok=True)
    rounds = [int(x) for x in a.rounds.split(",")]
    holes = list(range(1, 19)) if a.holes == "1-18" else [int(x) for x in a.holes.split(",")]
    total, _ = collect_player(a.game, a.player, rounds, holes, root, db, a.cookie, a.sleep)
    print(f"DONE shots={total} db={db}")

if __name__ == "__main__":
    main()
