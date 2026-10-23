"""Build the published NEO Ranking player SG hexagon data.

The current profile sample is restricted to official single-round SG records
retained in the repository: 10 tournament RECORDS.json files plus R1/R2/R3
for the Iceberg Seoul Newspaper Open. It is intentionally labeled as a
recorded subset in the public page, not as complete season coverage.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
RANKING_PATH = CONTENT / "research" / "NEO_RANKING_2026_SEASON_ONLY_V2.json"
ENTRY_PATH = CONTENT / "2026100003_ENTRY_KRANKING_JOIN.json"
R3_PATH = CONTENT / "raw_capture" / "2026100003_fr" / "sg_r3.html"
OUT = REPO_ROOT / "docs" / "assets" / "neo-ranking-sg-profiles-2026.json"

COMPONENTS = (
    "total",
    "tee_to_green",
    "off_the_tee",
    "approach",
    "around_green",
    "putting",
)
RANKING_TO_ROUND_FIELD = {
    "total": "total",
    "tee_to_green": "tee_to_green",
    "off_the_tee": "off_the_tee",
    "approach": "approach",
    "around_green": "around_green",
    "putting": "putting",
}


class RoundThreeRows(HTMLParser):
    """Read the visible cells from the official round-three SG table."""

    def __init__(self) -> None:
        super().__init__()
        self.context_depth = 0
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.rows: list[list[str]] = []
        self.row: list[str] = []
        self.cell = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "div" and attr.get("id") == "record-one" and self.context_depth == 0:
            self.context_depth = 1
            return
        if self.context_depth:
            if tag == "div":
                self.context_depth += 1
            elif tag == "table":
                self.in_table = True
            elif tag == "tr" and self.in_table:
                self.in_row = True
                self.row = []
            elif tag == "td" and self.in_row:
                self.in_cell = True
                self.cell = ""

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_cell:
            self.row.append(" ".join(self.cell.split()))
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.row:
                self.rows.append(self.row)
            self.in_row = False
        elif tag == "table" and self.in_table:
            self.in_table = False
        elif tag == "div" and self.context_depth:
            self.context_depth -= 1


def _number(value: str) -> float:
    match = re.match(r"\s*(-?\d+(?:\.\d+)?)", value)
    if not match:
        raise ValueError(f"Could not parse official SG value: {value!r}")
    return float(match.group(1))


def _single_round_records() -> list[dict]:
    rows: list[dict] = []
    for path in sorted((CONTENT / "sg_official_history").glob("*/RECORDS.json")):
        records = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(
            row for row in records
            if row.get("scope") == "single_round"
            and row.get("season") == 2026
            and row.get("player_id")
            and row.get("date", "") <= "2026-10-18"
        )

    for round_number in (1, 2):
        path = CONTENT / f"ICEBERG_2026100003_R{round_number}_SG_OFFICIAL_V1.json"
        artifact = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(row for row in artifact["records"] if row.get("player_id"))

    entry = json.loads(ENTRY_PATH.read_text(encoding="utf-8"))
    player_ids = {
        row["player_name"]: str(row["player_code"])
        for row in entry["records"]
        if row.get("player_name") and row.get("player_code")
    }
    parser = RoundThreeRows()
    parser.feed(R3_PATH.read_text(encoding="utf-8", errors="replace"))
    if len(parser.rows) != 61:
        raise ValueError(f"Expected 61 official R3 SG rows, got {len(parser.rows)}")
    for row in parser.rows:
        if len(row) != 9:
            raise ValueError(f"Unexpected R3 SG row shape: {row!r}")
        _, name, total, tee_to_green, off_the_tee, approach, around_green, putting, _ = row
        player_id = player_ids.get(name)
        if not player_id:
            raise ValueError(f"Could not connect official R3 name to player ID: {name}")
        rows.append({
            "player_id": player_id,
            "player_name": name,
            "total": _number(total),
            "tee_to_green": _number(tee_to_green),
            "off_the_tee": _number(off_the_tee),
            "approach": _number(approach),
            "around_green": _number(around_green),
            "putting": _number(putting),
            "game_code": "2026100003",
            "round": 3,
            "scope": "single_round",
            "date": "2026-10-18",
        })
    return rows


def main() -> None:
    ranking = json.loads(RANKING_PATH.read_text(encoding="utf-8"))["ranking"]
    if len(ranking) != 120:
        raise ValueError(f"Expected 120 ranking players, got {len(ranking)}")
    ranking_ids = {str(row["player_id"]) for row in ranking}

    records = _single_round_records()
    keys = [(str(row["player_id"]), row["game_code"], row["round"]) for row in records]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate player/event/round records found")

    by_player: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        if str(row["player_id"]) in ranking_ids:
            by_player[str(row["player_id"])].append(row)

    profiles = {}
    for player in ranking:
        player_id = str(player["player_id"])
        player_records = by_player[player_id]
        if not player_records:
            raise ValueError(f"No official component SG records for {player['player_name']}")
        profiles[player_id] = {
            "rounds": len(player_records),
            "events": len({row["game_code"] for row in player_records}),
            "means": {
                key: round(sum(float(row[RANKING_TO_ROUND_FIELD[key]]) for row in player_records) / len(player_records), 6)
                for key in COMPONENTS
            },
        }

    event_count = len({row["game_code"] for row in records})
    if len(records) != 3882 or event_count != 11:
        raise ValueError(f"Unexpected source coverage: {len(records)} records, {event_count} tournaments")

    payload = {
        "season": 2026,
        "ranking_cutoff": "2026-10-18",
        "source_window": {"from": "2026-07-05", "through": "2026-10-18"},
        "source_tournaments": event_count,
        "source_round_records": len(records),
        "profile_method": "Equal-weight average of official single-round SG records retained in the repository for each player.",
        "coverage_note": "This chart uses the recorded official SG component rounds from 11 tournaments between July 5 and October 18. It is a confirmed subset of the 2026 season records, not a complete season component total.",
        "scale": {"min": -6, "max": 6},
        "components": [
            {"key": "off_the_tee", "label": "티샷"},
            {"key": "approach", "label": "어프로치"},
            {"key": "around_green", "label": "그린 주변"},
            {"key": "putting", "label": "퍼팅"},
            {"key": "tee_to_green", "label": "티샷부터 그린"},
            {"key": "total", "label": "전체"},
        ],
        "players": profiles,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": str(OUT),
        "players": len(profiles),
        "round_records": len(records),
        "tournaments": event_count,
        "minimum_player_rounds": min(row["rounds"] for row in profiles.values()),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
