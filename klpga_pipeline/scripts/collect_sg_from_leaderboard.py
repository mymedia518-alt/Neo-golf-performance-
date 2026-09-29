"""Generic Strokes Gained collector, triggered by discovering a real
/web/leaderboard/strokesGained?gameCode=... link inside ANY captured
leaderboard page -- not a script written for one tournament.

MISSION (2026-09-28): "Whenever a leaderboard page contains
/web/leaderboard/strokesGained?gameCode=..., the Reader must discover
the SG URL automatically, download it, parse it, and save SG Total /
OTT / APP / ARG / PUTT into the warehouse. No gameCode-specific logic.
Must work for every future KLPGA tournament."

Root cause this replaces: 2026090003 (KB금융 골든라이프 챔피언십) was
invisible to scripts/63_collect_historical_sg_warehouse.py because that
collector only ever processes tournaments returned by
klpga.collectors.tournaments.fetch_game_list() for a season -- and KB
does not appear in that official season listing (see
scripts/104_evaluate_pre_v2.py's own "kb_excluded" note). Its SG data
was never "filtered out" downstream; the season-sweep collector never
even attempted it. This module adds a second, independent discovery
path that does not depend on the season game list at all: whenever the
Reader captures ANY leaderboard page (the normal season sweep's own
roundLeaderboard responses, or a special one-off per-tournament capture
like KB's), scanning that page's own HTML for a real strokesGained link
is enough to find and collect a tournament's SG data on its own.

Every function below takes game_code as DATA, discovered from the page
itself via discover_sg_game_code() -- never a hardcoded string, never a
per-tournament branch. The same four functions run for every
tournament this collector is ever pointed at.

Reuses, unchanged, the exact parser and HTTP client already proven
correct for every other tournament in the warehouse:
  - klpga.website_v2.official_data.parse_sg_html / validate_sg_record
  - klpga.analytics.sg_performance.standardize_player_name
  - klpga.http_client.PoliteHttpClient (rate-limited, cached, retrying)
Output rows are written in the exact schema
historical_sg_warehouse_corrected_v2.json already uses, so
reconcile_10097_player_history.py and everything downstream of it picks
up a newly-collected tournament with zero code changes -- the only
thing this module contributes is discovery + fetch + parse + merge.

NETWORK NOTE: live fetches require real network access to klpga.co.kr,
which this repository's own history shows has never been available
inside a Claude sandbox -- see scripts/154_ingest_hana_r1_sg_raw.py,
whose own docstring records that even the Hana strokesGained page had
to be saved by a human in a real browser and uploaded, never fetched
live. --sg-html-file below runs this collector fully offline against
such an already-saved page (the same proven pattern); --live attempts
a real fetch via PoliteHttpClient for an environment that does have
network access. Both paths call the exact same parse/build/merge
functions -- there is no separate "offline version" of this collector.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.http_client import PoliteHttpClient  # noqa: E402
from klpga.website_v2.official_data import parse_sg_html, validate_sg_record  # noqa: E402
from klpga.analytics.sg_performance import standardize_player_name  # noqa: E402

BASE_URL = "https://klpga.co.kr"
SG_WEB_PAGE_PATH = "/web/leaderboard/strokesGained"
SG_DETAIL_POST_PATH = "/load/leaderboard/strokesGained_detail"
DEFAULT_WAREHOUSE_PATH = ROOT / "content" / "website_v2" / "historical_sg_warehouse_corrected_v2.json"

# The one trigger this whole module runs on: a real strokesGained web
# page link, naming its own real gameCode. No other pattern is ever
# treated as a signal that SG data exists for a tournament.
_SG_LINK_RE = re.compile(re.escape(SG_WEB_PAGE_PATH) + r"\?gameCode=(\d+)")

_ROUND_SCOPES: list[tuple[str, Optional[int]]] = [
    ("tournament_cumulative", None),
    ("single_round", 1),
    ("single_round", 2),
    ("single_round", 3),
    ("single_round", 4),
]


def discover_sg_game_code(leaderboard_html: str) -> Optional[str]:
    """Scan ANY leaderboard page's real HTML for a real
    /web/leaderboard/strokesGained?gameCode=... link and return the
    real gameCode it names. Returns None (never a guess, never a
    fallback game_code) when no such link is present -- most
    leaderboard pages legitimately will not have one, because not
    every KLPGA tournament publishes an SG page."""
    m = _SG_LINK_RE.search(leaderboard_html)
    return m.group(1) if m else None


def fetch_sg_detail_html(client: PoliteHttpClient, game_code: str, round_number: Optional[int]) -> str:
    """Live fetch of the strokesGained_detail response for ANY real
    game_code -- the exact endpoint and payload shape
    63_collect_historical_sg_warehouse.py already proves correct for
    every tournament currently in the warehouse. Requires a live
    network path to klpga.co.kr (see module docstring)."""
    return client.post_text(
        BASE_URL + SG_DETAIL_POST_PATH,
        data={"gameCode": game_code, "round": "" if round_number is None else str(round_number)},
        headers={"X-Requested-With": "XMLHttpRequest", "Referer": BASE_URL},
    )


def build_warehouse_rows(
    sg_html: str, *, game_code: str, season: int, tournament: str,
    scope: str, round_number: Optional[int], id_lookup: dict, source_note: str,
) -> list[dict]:
    """Parse one real strokesGained_detail (or an operator-saved SG web
    page) response into rows in the exact schema
    historical_sg_warehouse_corrected_v2.json already uses. Raises
    ValueError (from parse_sg_html) when the given page has no SG
    table at all -- the caller decides whether that means 'this round
    was never played' or a genuine parser problem, this function never
    guesses. player_id is never invented: an unresolved name is kept
    as UNRESOLVED_IDENTITY, exactly like every other warehouse row."""
    parsed = parse_sg_html(sg_html, scope=scope, round_number=round_number)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = []
    for row in parsed:
        row = dict(row)
        row["validation"] = validate_sg_record(row)
        identity = standardize_player_name(row.get("player"), id_lookup.get(str(row.get("player"))))
        row.update(identity)
        row.update({
            "identity_state": "RETAINED" if identity["player_id"] else "UNRESOLVED_IDENTITY",
            "season": season,
            "game_code": game_code,
            "tournament": tournament,
            "source": source_note,
            "retrieved_at": now,
        })
        rows.append(row)
    return rows


def merge_into_warehouse(rows: list[dict], warehouse_path: Path = DEFAULT_WAREHOUSE_PATH) -> dict:
    """Append newly-discovered rows into the real warehouse file,
    de-duplicated on (player_id, game_code, scope, round) so re-running
    this collector on the same tournament twice is always safe and
    never overwrites a row already on disk. A genuine conflict between
    a re-collected row and the existing one is exactly what
    reconcile_10097_player_history.py's own ReconciliationError gate
    is designed to catch downstream -- this function never silently
    resolves one."""
    doc = json.loads(warehouse_path.read_text(encoding="utf-8")) if warehouse_path.exists() else {"records": []}
    existing_keys = {
        (r.get("player_id"), r.get("game_code"), r.get("scope"), r.get("round"))
        for r in doc.get("records", [])
    }
    added = 0
    for row in rows:
        key = (row.get("player_id"), row.get("game_code"), row.get("scope"), row.get("round"))
        if key in existing_keys:
            continue
        doc.setdefault("records", []).append(row)
        existing_keys.add(key)
        added += 1
    if added:
        warehouse_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"rows_added": added, "warehouse_total_records": len(doc.get("records", []))}


_DIFF_IGNORED_FIELDS = {"retrieved_at", "source"}


def merge_into_warehouse_with_diff(rows: list[dict], warehouse_path: Path = DEFAULT_WAREHOUSE_PATH) -> dict:
    """MISSION V82 extension: same de-duplication key as
    merge_into_warehouse() (never a duplicate row on disk), but where
    that function only ever appends brand-new keys, this one also
    detects when a re-collected row for an ALREADY-PRESENT key carries
    different real values (a genuine correction, e.g. a late official
    scoring fix) and updates that record in place -- while a
    re-collected row that is byte-identical to what is already on disk
    (apart from its own retrieved_at timestamp) is logged as skipped,
    never rewritten. This is additive: merge_into_warehouse() itself is
    untouched and still used by collect_live()/collect_from_saved_page()
    exactly as before; callers that want add/update/skip accounting
    (MISSION V82's Warehouse Update stage) call this function instead."""
    doc = json.loads(warehouse_path.read_text(encoding="utf-8")) if warehouse_path.exists() else {"records": []}
    records = doc.setdefault("records", [])
    index = {
        (r.get("player_id"), r.get("game_code"), r.get("scope"), r.get("round")): i
        for i, r in enumerate(records)
    }
    added = updated = skipped = 0
    for row in rows:
        key = (row.get("player_id"), row.get("game_code"), row.get("scope"), row.get("round"))
        if key not in index:
            records.append(row)
            index[key] = len(records) - 1
            added += 1
            continue
        existing = records[index[key]]
        comparable_existing = {k: v for k, v in existing.items() if k not in _DIFF_IGNORED_FIELDS}
        comparable_new = {k: v for k, v in row.items() if k not in _DIFF_IGNORED_FIELDS}
        if comparable_existing == comparable_new:
            skipped += 1
            continue
        records[index[key]] = row
        updated += 1
    if added or updated:
        warehouse_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "rows_added": added, "rows_updated": updated, "rows_skipped": skipped,
        "warehouse_total_records": len(records),
    }


def collect_live(
    client: PoliteHttpClient, leaderboard_html: str, *, season: int, tournament: str,
    id_lookup: Optional[dict] = None, warehouse_path: Path = DEFAULT_WAREHOUSE_PATH,
) -> dict:
    """The full discover -> download -> parse -> save cycle for
    whatever real game_code the given leaderboard page names -- tries
    the tournament-cumulative scope plus rounds 1-4, skipping any
    round this tournament genuinely has no SG table for (fewer than 4
    rounds played, or SG not published for every round)."""
    game_code = discover_sg_game_code(leaderboard_html)
    if not game_code:
        return {"status": "no_sg_link_found", "game_code": None}
    id_lookup = id_lookup or {}
    all_rows: list[dict] = []
    for scope, round_number in _ROUND_SCOPES:
        html = fetch_sg_detail_html(client, game_code, round_number)
        try:
            rows = build_warehouse_rows(
                html, game_code=game_code, season=season, tournament=tournament,
                scope=scope, round_number=round_number, id_lookup=id_lookup,
                source_note=(
                    f"{BASE_URL}{SG_DETAIL_POST_PATH} POST gameCode={game_code}, "
                    f"round={round_number if round_number else 'cumulative'} "
                    f"(discovered via {SG_WEB_PAGE_PATH}?gameCode={game_code})"
                ),
            )
        except ValueError:
            continue
        all_rows.extend(rows)
    merge_result = merge_into_warehouse(all_rows, warehouse_path)
    return {"status": "collected", "game_code": game_code, "rows_parsed": len(all_rows), **merge_result}


def collect_from_saved_page(
    leaderboard_html: str, sg_page_html: str, *, season: int, tournament: str,
    scope: str, round_number: Optional[int], id_lookup: Optional[dict] = None,
    warehouse_path: Path = DEFAULT_WAREHOUSE_PATH,
) -> dict:
    """Same discover -> parse -> save cycle, for an environment (like
    this one) with no live network path to klpga.co.kr. `sg_page_html`
    is an already-saved copy of the real
    /web/leaderboard/strokesGained?gameCode=... page (or its
    strokesGained_detail response) -- the exact ingestion pattern this
    repository already uses for Hana (scripts/154_ingest_hana_r1_sg_raw.py
    + scripts/155_build_hana_r1_sg_v1.py), generalized to any game_code
    instead of one hardcoded to it."""
    game_code = discover_sg_game_code(leaderboard_html)
    if not game_code:
        return {"status": "no_sg_link_found", "game_code": None}
    id_lookup = id_lookup or {}
    rows = build_warehouse_rows(
        sg_page_html, game_code=game_code, season=season, tournament=tournament,
        scope=scope, round_number=round_number, id_lookup=id_lookup,
        source_note=(
            f"operator-saved copy of {BASE_URL}{SG_WEB_PAGE_PATH}?gameCode={game_code} "
            f"(discovered via the same page's own link, no live network fetch)"
        ),
    )
    merge_result = merge_into_warehouse(rows, warehouse_path)
    return {"status": "collected", "game_code": game_code, "rows_parsed": len(rows), **merge_result}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--leaderboard-html-file", required=True, help="A captured leaderboard page to scan for a real strokesGained link.")
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--tournament", required=True)
    ap.add_argument("--live", action="store_true", help="Fetch live via PoliteHttpClient (requires real network access to klpga.co.kr).")
    ap.add_argument("--sg-html-file", help="An already-saved SG page/response, for offline collection (see module docstring's NETWORK NOTE).")
    ap.add_argument("--scope", default="tournament_cumulative", choices=["tournament_cumulative", "single_round"], help="Only used with --sg-html-file, which can only ever represent one scope per run.")
    ap.add_argument("--round", type=int, default=None, help="Only used with --sg-html-file when --scope=single_round.")
    ap.add_argument("--warehouse", default=str(DEFAULT_WAREHOUSE_PATH))
    args = ap.parse_args()

    leaderboard_html = Path(args.leaderboard_html_file).read_text(encoding="utf-8", errors="replace")
    warehouse_path = Path(args.warehouse)

    if args.live:
        client = PoliteHttpClient(cache_dir=ROOT / "data" / "raw_cache" / "http")
        result = collect_live(client, leaderboard_html, season=args.season, tournament=args.tournament, warehouse_path=warehouse_path)
    elif args.sg_html_file:
        sg_html = Path(args.sg_html_file).read_text(encoding="utf-8", errors="replace")
        result = collect_from_saved_page(
            leaderboard_html, sg_html, season=args.season, tournament=args.tournament,
            scope=args.scope, round_number=args.round, warehouse_path=warehouse_path,
        )
    else:
        ap.error("one of --live or --sg-html-file is required")
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
