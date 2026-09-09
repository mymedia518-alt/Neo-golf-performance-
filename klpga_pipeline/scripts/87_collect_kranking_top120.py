"""Validate official K-Ranking evidence and build an ordered TOP 120.

The publication path deliberately needs two independent official captures:
the period page proves the literal official ranking period and supplies the
visible TOP 10, while the all-player page supplies the complete population.
The overlapping TOP 10 must agree on id, name, rank, rating, points and event
count. A filename, manifest, requested week, or operator statement is never
accepted as period evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
CANONICAL_URL = "https://k-rankings.klpga.co.kr/allplayer.jsp"
ACQUISITION_URL = "https://k-rankings.klpga.co.kr/index.jsp"


def clean_name(label: str) -> str:
    """Remove only an explicit KLPGA membership suffix from a name."""
    return re.sub(r"\s+\([^()]*(?:회원|대상자)[^()]*\)\s*$", "", label).strip()


def _week_from_html(html: str) -> str:
    match = re.search(r"(20\d{2})년\s*(\d+)주차", html)
    if not match:
        raise ValueError("official ranking period is absent from the captured response")
    return f"{match.group(1)}-W{int(match.group(2)):02d}"


def _player_id(link) -> str:
    if link is None or not link.get("href"):
        raise ValueError("official player profile link is missing")
    query = parse_qs(urlparse(link["href"]).query)
    values = query.get("player_code") or query.get("playerCode")
    if not values or not str(values[0]).isdigit():
        raise ValueError(f"official player id is missing from profile link: {link['href']!r}")
    return str(values[0])


def _number(text: str, field: str) -> Decimal:
    token = (text or "").replace(",", "").strip().split()[0]
    try:
        return Decimal(token)
    except (InvalidOperation, IndexError):
        raise ValueError(f"invalid {field}: {text!r}") from None


def _row(rank: int, player_id: str, name: str, rating: str, points: str, events: str) -> dict:
    try:
        event_count = int(events.replace(",", "").strip())
    except ValueError:
        raise ValueError(f"invalid event count: {events!r}") from None
    return {
        "official_k_rank": rank,
        "player_id": player_id,
        "player_name": clean_name(name),
        "rating": str(_number(rating, "rating")),
        "total_points": str(_number(points, "total points")),
        "event_count": event_count,
    }


def extract_period_top10(html: str) -> tuple[str, list[dict]]:
    """Read the literal official period and its visible TOP 10 table."""
    week = _week_from_html(html)
    soup = BeautifulSoup(html, "html.parser")
    tables = [t for t in soup.select("table.ranking-list.top10") if len(t.select("tbody tr")) >= 10]
    if len(tables) != 1:
        raise ValueError(f"expected one official TOP10 table, found {len(tables)}")
    records: list[dict] = []
    for tr in tables[0].select("tbody tr")[:10]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
        if len(cells) < 5:
            raise ValueError("official TOP10 row is incomplete")
        try:
            rank = int(cells[0])
        except ValueError:
            raise ValueError(f"invalid official TOP10 rank: {cells[0]!r}") from None
        records.append(_row(rank, _player_id(tr.find("a", href=True)), cells[1], cells[2], cells[3], cells[4]))
    if [r["official_k_rank"] for r in records] != list(range(1, 11)):
        raise ValueError("official TOP10 ordering is not contiguous 1..10")
    return week, records


def extract_full_table(html: str) -> list[dict]:
    """Read the official all-player ordered table without inferring a week."""
    soup = BeautifulSoup(html, "html.parser")
    candidates = [t for t in soup.select("table.recordTale") if len(t.select("tbody tr")) >= 120]
    if len(candidates) != 1:
        raise ValueError(f"expected one complete official all-player table, found {len(candidates)}")
    records: list[dict] = []
    for tr in candidates[0].select("tbody tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
        if len(cells) < 7:
            raise ValueError("official all-player row is incomplete")
        rank_text = next(tr.find_all("td")[1].stripped_strings, "")
        try:
            rank = int(rank_text)
        except ValueError:
            raise ValueError(f"invalid official all-player rank: {rank_text!r}") from None
        records.append(_row(rank, _player_id(tr.find("a", href=True)), cells[3], cells[4], cells[5], cells[6]))
    ranks = [r["official_k_rank"] for r in records]
    ids = [r["player_id"] for r in records]
    if not ranks or ranks[0] != 1 or any(b < a for a, b in zip(ranks, ranks[1:])):
        raise ValueError("official all-player ordering is not nondecreasing")
    if len(ids) != len(set(ids)):
        raise ValueError("official all-player table contains duplicate player ids")
    return records


def _top10_crosscheck(period_rows: list[dict], full_rows: list[dict]) -> list[dict]:
    by_rank = {row["official_k_rank"]: row for row in full_rows}
    fields = ("player_id", "player_name", "official_k_rank", "rating", "total_points", "event_count")
    checks = []
    mismatches = []
    for period in period_rows:
        complete = by_rank.get(period["official_k_rank"])
        if complete is None:
            mismatches.append({"rank": period["official_k_rank"], "reason": "missing from complete table"})
            continue
        unequal = {field: {"period": period[field], "full_table": complete[field]} for field in fields if period[field] != complete[field]}
        if unequal:
            mismatches.append({"rank": period["official_k_rank"], "fields": unequal})
        checks.append({"rank": period["official_k_rank"], "player_id": period["player_id"], "matched": not unequal})
    if len(checks) != 10 or mismatches:
        raise ValueError(f"official TOP10 evidence mismatch: {mismatches or 'overlap count is not 10'}")
    return checks


def combine_official_evidence(period_path: Path, full_table_path: Path, retrieved_at: str) -> dict:
    """Build publication-ready TOP120 only after the two-source check."""
    period_bytes = period_path.read_bytes()
    full_bytes = full_table_path.read_bytes()
    week, period_rows = extract_period_top10(period_bytes.decode("utf-8", "strict"))
    full_rows = extract_full_table(full_bytes.decode("utf-8", "strict"))
    overlap = _top10_crosscheck(period_rows, full_rows)
    records = [{
        **row,
        "retrieved_at": retrieved_at,
        "identity_validation_state": "PASS_OFFICIAL_PLAYER_ID",
        "official_source": CANONICAL_URL,
        "ranking_week": week,
    } for row in full_rows[:120]]
    return {
        "schema_version": "neo_home_kranking_top120_v2",
        "population_kind": "official_klpga_kranking_top120",
        "ranking_week": week,
        "official_source": CANONICAL_URL,
        "period_source": ACQUISITION_URL,
        "retrieved_at": retrieved_at,
        "population_selection": "official K-Ranking closed interval 1..120 only",
        "source_sha256": {
            "period": hashlib.sha256(period_bytes).hexdigest(),
            "full_table": hashlib.sha256(full_bytes).hexdigest(),
        },
        "source_bytes": {"period": len(period_bytes), "full_table": len(full_bytes)},
        "crosscheck": {
            "fields": ["player_id", "player_name", "official_k_rank", "rating", "total_points", "event_count"],
            "overlap_count": 10,
            "mismatched": 0,
            "records": overlap,
        },
        "full_population_count": len(full_rows),
        "records": records,
    }


def extract(html: str, retrieved_at: str) -> list[dict]:
    """Legacy single-capture extractor retained for historical imports."""
    week = _week_from_html(html)
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
        "ranking_week": week,
    } for rank, (player_id, label) in enumerate(pairs[:120], 1)]
    ids = [row["player_id"] for row in records]
    if len(ids) != len(set(ids)):
        raise ValueError("TOP120 player id integrity failure")
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period-html", type=Path)
    parser.add_argument("--full-table-html", type=Path)
    parser.add_argument("--html", type=Path, help="legacy single-capture import; not publication approved")
    parser.add_argument("--output", type=Path, default=CONTENT / "HOME_PLAYER_MASTER_TOP120.json")
    args = parser.parse_args()
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if args.period_html and args.full_table_html and not args.html:
        output = combine_official_evidence(args.period_html, args.full_table_html, retrieved_at)
    elif args.html and not args.period_html and not args.full_table_html:
        records = extract(args.html.read_text(encoding="utf-8"), retrieved_at)
        output = {
            "schema_version": "neo_home_kranking_top120_legacy_single_capture_v1",
            "population_kind": "official_klpga_kranking_top120",
            "ranking_week": records[0]["ranking_week"],
            "official_source": CANONICAL_URL,
            "retrieved_at": retrieved_at,
            "population_selection": "official K-Ranking closed interval 1..120 only",
            "source_sha256": hashlib.sha256(args.html.read_bytes()).hexdigest(),
            "publication_approved": False,
            "blocked_reason": "combined official period and complete-table evidence required",
            "records": records,
        }
    else:
        parser.error("provide both --period-html and --full-table-html")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"WROTE official K-Ranking TOP120 {output['ranking_week']}; combined={isinstance(output['source_sha256'], dict)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
