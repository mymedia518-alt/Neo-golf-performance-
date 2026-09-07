"""Shared K-Rankings "PLAYER PROFILE" (k-rankings.klpga.co.kr/
playerprofile.jsp) fetch+parse, used by scripts 75 (full-field profile
audit) and 76 (bounded recheck of specific access failures) so both
share one parser and one retry policy instead of two copies."""
from __future__ import annotations

import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL = "https://k-rankings.klpga.co.kr/playerprofile.jsp"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(node):
    return node.get_text(" ", strip=True) if node else None


def collect_profile(pid: str, session: requests.Session, ranking_week_label: str, ranking_week_korean: str, *, attempts: int = 3) -> dict:
    u = URL + f"?player_code={pid}&top_player=김민솔&last_week={ranking_week_korean}"
    exc = None
    for attempt in range(attempts):
        try:
            r = session.get(u, timeout=30); r.raise_for_status(); break
        except requests.RequestException as err:
            exc = err; time.sleep(1.0 * (attempt + 1))
    else:
        return {"player_id": str(pid), "current_player_name": None, "current_k_ranking": None, "current_team": None,
                "ranking_points": None, "total_points": None, "events_played": None, "ranking_date": ranking_week_label,
                "official_source": u, "retrieved_at": now(), "parse_state": "ACCESS_FAILURE", "team_state": "ACCESS_FAILURE",
                "error": str(exc)}
    soup = BeautifulSoup(r.content.decode("utf-8", "replace"), "html.parser")
    rank = _text(soup.select_one("table.rank-table th.rank h1"))
    name = _text(soup.select_one("table.rank-table .player-info h4"))
    vals = [_text(x) for x in soup.select("table.point-table tbody td h4")]
    team = vals[0] if len(vals) > 0 else None
    rp = vals[1] if len(vals) > 1 else None
    total = vals[2] if len(vals) > 2 else None
    events = vals[3] if len(vals) > 3 else None

    def num(v):
        try:
            return float(v.replace(",", "")) if v is not None else None
        except ValueError:
            return None

    return {"player_id": str(pid), "current_player_name": name,
            "current_k_ranking": int(rank) if rank and rank.isdigit() else None,
            "current_team": team or None, "ranking_points": num(rp), "total_points": num(total),
            "events_played": int(events) if events and events.isdigit() else None,
            "ranking_date": ranking_week_label, "official_source": u, "retrieved_at": now(),
            "parse_state": "PASS" if name and rank else "FAIL",
            "team_state": "OFFICIAL_BLANK" if name and not team else ("PARSED" if team else "UNKNOWN")}
