"""Parsers and validators for public KLPGA tournament analytics responses."""
from __future__ import annotations

import math
import re
from bs4 import BeautifulSoup

SG_KEYS = ("total", "tee_to_green", "off_the_tee", "approach", "around_green", "putting")


def _number(text: str) -> float | None:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text.strip())
    return float(match.group()) if match else None


def parse_sg_html(html: str, *, scope: str, round_number: int | None) -> list[dict]:
    """Parse the official ``strokesGained_detail`` response."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#record-one table") or soup.find("table")
    if table is None:
        raise ValueError("official SG table missing")
    records = []
    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 9:
            continue
        values = []
        for cell in cells[2:8]:
            rank = cell.select_one(".rank")
            if rank:
                rank.extract()
            values.append(_number(cell.get_text(" ", strip=True)))
        if any(value is None for value in values):
            continue
        records.append({
            "rank": int(_number(cells[0].get_text(strip=True)) or 0),
            "player": cells[1].get_text(" ", strip=True),
            **dict(zip(SG_KEYS, values)),
            "rounds": int(_number(cells[8].get_text(strip=True)) or 0),
            "scope": scope,
            "round": round_number,
        })
    return records


def validate_sg_record(record: dict, tolerance: float = 0.06) -> dict:
    component_total = sum(float(record[key]) for key in ("off_the_tee", "approach", "around_green", "putting"))
    component_t2g = sum(float(record[key]) for key in ("off_the_tee", "approach", "around_green"))
    total_delta = round(float(record["total"]) - component_total, 3)
    t2g_delta = round(float(record["tee_to_green"]) - component_t2g, 3)
    return {
        "total_delta": total_delta, "t2g_delta": t2g_delta,
        "total_within_tolerance": math.isclose(total_delta, 0.0, abs_tol=tolerance),
        "t2g_within_tolerance": math.isclose(t2g_delta, 0.0, abs_tol=tolerance),
    }


def parse_leaderboard_html(html: str) -> list[dict]:
    """Parse one official roundLeaderboard response, preserving ties/statuses."""
    soup = BeautifulSoup(html, "html.parser")
    output = []
    seen: set[str] = set()
    for button in soup.select("[id=btnDetail]"):
        table = button.find("table")
        cells = table.find_all("td") if table else []
        texts = [cell.get_text(" ", strip=True) for cell in cells]
        if len(texts) < 13:
            continue
        player_id = button.get("_playercode")
        if not player_id or player_id in seen:
            continue
        seen.add(player_id)
        rank = texts[1]
        scores = [int(x) if x.isdigit() else None for x in texts[8:12]]
        output.append({
            "rank": rank, "rank_numeric": int(_number(rank) or 0) or None,
            "tie": rank.startswith("T"), "player": texts[4],
            "player_id": player_id, "to_par": texts[5],
            "through": texts[6], "rounds": scores,
            "total": int(texts[12]) if texts[12].isdigit() else None,
            "status": "WD" if "WD" in rank else "DQ" if "DQ" in rank else "FINISHED",
        })
    return output


def parse_player_holes(html: str, *, player: str, player_id: str) -> list[dict]:
    """Parse exact strokes/par from official scorecard tables (one table per round)."""
    soup = BeautifulSoup(html, "html.parser")
    output = []
    round_number = 0
    for table in soup.find_all("table"):
        rows = [[c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])] for tr in table.find_all("tr")]
        if len(rows) < 3 or not rows[0] or rows[0][0] != "HOLE" or rows[1][0] != "PAR" or rows[2][0] != "Score":
            continue
        round_number += 1
        hole_positions = [i for i, label in enumerate(rows[0]) if label.isdigit() and 1 <= int(label) <= 18]
        for i in hole_positions:
            if i >= len(rows[1]) or i >= len(rows[2]) or not rows[1][i].isdigit() or not rows[2][i].isdigit():
                continue
            par, strokes = int(rows[1][i]), int(rows[2][i])
            output.append({"player": player, "player_id": player_id, "round": round_number,
                           "hole": int(rows[0][i]), "par": par, "strokes": strokes,
                           "relative_to_par": strokes - par})
    return output
