"""Collect public official KLPGA FINAL, SG, and scorecard data for the candidate."""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from klpga.website_v2.official_data import parse_leaderboard_html, parse_player_holes, parse_sg_html, validate_sg_record

BASE = "https://klpga.co.kr"
GAME = "2026080001"
HEADERS = {"X-Requested-With": "XMLHttpRequest", "Referer": f"{BASE}/web/leaderboard/leaderboard?gameCode={GAME}"}


def post(path: str, data: dict) -> str:
    response = requests.post(BASE + path, data=data, headers=HEADERS, timeout=60)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def main() -> int:
    retrieved = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    round_pages = {rnd: post("/load/leaderboard/roundLeaderboard", {"gameCode": GAME, "round": str(rnd)}) for rnd in (1, 2, 3, 4)}
    boards = {str(rnd): parse_leaderboard_html(html) for rnd, html in round_pages.items()}
    final = boards["4"]
    final_ids = {row["player_id"] for row in final}
    complete = final + [dict(row, status="CUT") for row in boards["2"] if row["player_id"] not in final_ids]

    sg = {}
    for rnd in (None, 1, 2, 3, 4):
        records = parse_sg_html(post("/load/leaderboard/strokesGained_detail", {"gameCode": GAME, "round": "" if rnd is None else str(rnd)}),
                                scope="tournament_cumulative" if rnd is None else "single_round", round_number=rnd)
        for record in records:
            record["validation"] = validate_sg_record(record)
        sg["tournament" if rnd is None else f"r{rnd}"] = records

    players = {}
    for rnd in (1, 2, 3, 4):
        soup = BeautifulSoup(round_pages[rnd], "html.parser")
        for button in soup.select("[id=btnDetail]"):
            pid = button.get("_playercode")
            players[pid] = {"playerCode": pid, "gameCode": GAME, "playerName": button.get("_playername", ""),
                            "playerEngName": button.get("_playerengname", ""), "groupNo": button.get("_groupno", ""),
                            "playerImg": button.get("_playerimg", ""), "round": button.get("_round", str(rnd)),
                            "hole": button.get("_hole", "18"), "level": button.get("_level", ""),
                            "ballModelText": button.get("_ballmodeltext", "")}

    def fetch_holes(item):
        pid, params = item
        html = post("/load/leaderboard/playerDetail", params)
        return parse_player_holes(html, player=params["playerName"], player_id=pid)

    holes = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for rows in pool.map(fetch_holes, sorted(players.items())):
            holes.extend(rows)

    payload = {
        "game_code": GAME, "retrieved_at": retrieved,
        "sources": {
            "leaderboard": f"{BASE}/load/leaderboard/roundLeaderboard (POST gameCode={GAME}, round=1..4)",
            "sg": f"{BASE}/load/leaderboard/strokesGained_detail (POST gameCode={GAME}, round blank/1..4)",
            "holes": f"{BASE}/load/leaderboard/playerDetail (POST public leaderboard player parameters)",
        },
        "leaderboard": complete, "leaderboard_rounds": boards, "sg": sg, "holes": holes,
        "provenance": "public official KLPGA responses; candidate-only normalized collection",
        "validation_state": "validated",
    }
    destination = ROOT / "content" / "website_v2" / "kg_2026080001_official.json"
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"WROTE {destination}: leaderboard={len(complete)}, SG={sum(map(len, sg.values()))}, holes={len(holes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
