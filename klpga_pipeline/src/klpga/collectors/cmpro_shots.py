"""KLPGA cmpro 3D Shot Tracker collector.

Confirmed public fragment contract:
  GET /load/map3d/leaderboard?gameCode=...
  GET /load/map3d/playerScore?gameCode=...&playerCode=...
  POST /load/map3d/playerInfo
       gameCode, playerCode, round, hole, lang, gameMethod, trueHole, arrayTrueHole

This module deliberately reuses PoliteHttpClient so cmpro collection inherits
NEO's cache, throttle, bounded retries and 401/403/429 stop policy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup
from klpga.http_client import PoliteHttpClient

CMPRO_BASE = "https://cmpro.klpga.co.kr"
LEADERBOARD_ENDPOINT = f"{CMPRO_BASE}/load/map3d/leaderboard"
PLAYER_SCORE_ENDPOINT = f"{CMPRO_BASE}/load/map3d/playerScore"
PLAYER_INFO_ENDPOINT = f"{CMPRO_BASE}/load/map3d/playerInfo"


@dataclass(frozen=True)
class CmproShot:
    shot_no: int
    shot_distance_yd: float
    end_distance_yd: float
    end_lie: str
    start_distance_yd: Optional[float] = None
    start_lie: Optional[str] = None

    @property
    def hole_out(self) -> bool:
        return self.end_lie == "홀인" or self.end_distance_yd == 0.0


def fetch_cmpro_leaderboard_html(client: PoliteHttpClient, game_code: str) -> str:
    return client.get_text(LEADERBOARD_ENDPOINT, params={"gameCode": game_code, "lang": "kr"})


def parse_cmpro_players(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    players: dict[str, str] = {}
    for tag in soup.find_all(True):
        attrs = {str(k).lower(): v for k, v in tag.attrs.items()}
        code = attrs.get("_playercode") or attrs.get("data-playercode")
        if code:
            name = attrs.get("_playername") or attrs.get("data-playername") or " ".join(tag.stripped_strings)
            players[str(code).strip()] = str(name).strip()
    return players


def fetch_player_score_html(client: PoliteHttpClient, game_code: str, player_code: str, *, use_cache: bool = True) -> str:
    return client.get_text(
        PLAYER_SCORE_ENDPOINT,
        params={"gameCode": game_code, "playerCode": player_code, "lang": "kr"},
        use_cache=use_cache,
    )



def parse_cmpro_played_holes(html: str) -> dict[int, list[int]]:
    """Return only round/hole pairs explicitly present in the official playerScore fragment."""
    soup = BeautifulSoup(html, "html.parser")
    played: dict[int, set[int]] = {}
    for node in soup.find_all(attrs={"_round": True}):
        try:
            rnd = int(str(node.get("_round")).strip())
        except (TypeError, ValueError):
            continue
        holes: set[int] = set()
        if node.has_attr("_hole"):
            try:
                hole = int(str(node.get("_hole")).strip())
                if 1 <= hole <= 18:
                    holes.add(hole)
            except (TypeError, ValueError):
                pass
        for child in node.find_all(attrs={"_hole": True}):
            try:
                hole = int(str(child.get("_hole")).strip())
            except (TypeError, ValueError):
                continue
            if 1 <= hole <= 18:
                holes.add(hole)
        if holes:
            played.setdefault(rnd, set()).update(holes)

    # Some fragments put _round and _hole on the same repeated score cells rather than a parent.
    for node in soup.find_all(attrs={"_round": True, "_hole": True}):
        try:
            rnd = int(str(node.get("_round")).strip())
            hole = int(str(node.get("_hole")).strip())
        except (TypeError, ValueError):
            continue
        if 1 <= hole <= 18:
            played.setdefault(rnd, set()).add(hole)

    return {rnd: sorted(holes) for rnd, holes in sorted(played.items())}


def fetch_player_info_html(
    client: PoliteHttpClient, game_code: str, player_code: str, round_number: int, hole: int,
    *, use_cache: bool = True,
) -> str:
    data = {
        "gameCode": game_code, "playerCode": player_code, "round": str(round_number),
        "hole": str(hole), "lang": "kr", "gameMethod": "0", "trueHole": "0",
        "arrayTrueHole": "",
    }
    return client.post_text(PLAYER_INFO_ENDPOINT, data=data, use_cache=use_cache)


def parse_cmpro_shots(html: str) -> list[CmproShot]:
    soup = BeautifulSoup(html, "html.parser")
    raw: list[tuple[int, float, float, str]] = []
    for node in soup.select(".map-playertext"):
        text = " ".join(node.stripped_strings)
        no = re.search(r"SHOT\s*(\d+)", text, re.I)
        dist = re.search(r"비거리\s*([0-9.]+)\s*yds", text)
        rem = re.search(r"남은거리\s*([0-9.]+)\s*yds", text)
        if not (no and dist and rem):
            continue
        lie = next((x for x in ("페어웨이", "러프", "그린", "벙커", "홀인") if x in text), "")
        raw.append((int(no.group(1)), float(dist.group(1)), float(rem.group(1)), lie))
    raw.sort()
    shots: list[CmproShot] = []
    previous: Optional[CmproShot] = None
    for no, dist, rem, lie in raw:
        shots.append(CmproShot(
            shot_no=no, shot_distance_yd=dist, end_distance_yd=rem, end_lie=lie,
            start_distance_yd=None if previous is None else previous.end_distance_yd,
            start_lie="티" if previous is None else previous.end_lie,
        ))
        previous = shots[-1]
    return shots


def validate_cmpro_hole(shots: list[CmproShot]) -> str:
    if not shots:
        return "EMPTY"
    numbers = [s.shot_no for s in shots]
    if numbers != list(range(1, len(shots) + 1)):
        return "FAIL_SHOT_SEQUENCE"
    for prev, cur in zip(shots, shots[1:]):
        if cur.start_distance_yd != prev.end_distance_yd or cur.start_lie != prev.end_lie:
            return "FAIL_STATE_LINK"
    if not shots[-1].hole_out:
        return "WARN_NOT_HOLED"
    return "PASS"
