"""Extract the official, ordered K-Ranking TOP 120 player dataset.

The official all-player table and the official home page share the same weekly
ranking dataset.  The home page embeds the complete ordered player/id array;
this is used because the allplayer response currently terminates before its
tbody.  Cross-checking against 119 independently collected official ranks is
mandatory before publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
CANONICAL_URL = "https://k-rankings.klpga.co.kr/allplayer.jsp"
ACQUISITION_URL = "https://k-rankings.klpga.co.kr/index.jsp"


def clean_name(label: str) -> str:
    return re.sub(r"\s+\([^()]*(?:회원|대상자)[^()]*\)\s*$", "", label).strip()


def extract(html: str, retrieved_at: str) -> list[dict]:
    week = re.search(r"(20\d{2})년\s*(\d+)주차", html)
    if not week:
        raise ValueError("official ranking week not found")
    pairs = re.findall(r'\{"id":\s*(\d+),"text":\s*"([^"]+)', html)
    if len(pairs) < 120:
        raise ValueError(f"official ordered dataset has only {len(pairs)} players")
    records = [{
        "official_k_rank": rank,
        "player_id": player_id,
        "player_name": clean_name(label),
        "retrieved_at": retrieved_at,
        "identity_validation_state": "PASS_OFFICIAL_PLAYER_ID",
        "official_source": CANONICAL_URL,
        "acquisition_source": ACQUISITION_URL,
        "ranking_week": f"{week.group(1)}-W{int(week.group(2)):02d}",
    } for rank, (player_id, label) in enumerate(pairs[:120], 1)]
    ranks = [row["official_k_rank"] for row in records]
    ids = [row["player_id"] for row in records]
    names = [row["player_name"] for row in records]
    if ranks != list(range(1, 121)) or len(ids) != len(set(ids)) or len(names) != len(set(names)):
        raise ValueError("TOP120 rank/id integrity failure")
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--crosscheck", type=Path, default=CONTENT / "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json")
    parser.add_argument("--output", type=Path, default=CONTENT / "HOME_PLAYER_MASTER_TOP120.json")
    args = parser.parse_args()
    html = args.html.read_text(encoding="utf-8")
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    records = extract(html, retrieved_at)
    by_id = {row["player_id"]: row["official_k_rank"] for row in records}
    prior = json.loads(args.crosscheck.read_text(encoding="utf-8"))["records"]
    comparable = [row for row in prior if row.get("official_rank") is not None and 1 <= int(row["official_rank"]) <= 120]
    mismatches = [row for row in comparable if by_id.get(str(row["player_id"])) != row["official_rank"]]
    if mismatches:
        raise ValueError(f"official rank crosscheck failed: {mismatches[:3]}")
    output = {
        "schema_version": "neo_home_kranking_top120_v1",
        "population_kind": "official_klpga_kranking_top120",
        "ranking_week": records[0]["ranking_week"],
        "official_source": CANONICAL_URL,
        "acquisition_source": ACQUISITION_URL,
        "retrieved_at": retrieved_at,
        "population_selection": "official K-Ranking closed interval 1..120 only",
        "source_sha256": hashlib.sha256(args.html.read_bytes()).hexdigest(),
        "crosscheck": {"artifact": args.crosscheck.name, "matched": len(comparable), "mismatched": 0},
        "records": records,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE official K-Ranking TOP120; crosscheck={len(comparable)}/0 mismatches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
