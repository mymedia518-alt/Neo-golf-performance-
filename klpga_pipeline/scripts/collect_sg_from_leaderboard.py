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

Every function below takes game_code as DATA -- never a hardcoded
string, never a per-tournament branch. Two ways to supply it, both
generic (see resolve_game_code()): Mode A discovers it from a real
leaderboard page via discover_sg_game_code(); Mode B accepts an
already-known real gameCode directly via --game-code, skipping
discovery when there is nothing left to discover. The same functions
run for every tournament this collector is ever pointed at, in either
mode.

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
import time
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


def resolve_game_code(leaderboard_html: Optional[str], game_code: Optional[str]) -> Optional[str]:
    """Two ways to name the real tournament this collector runs
    against -- exactly one must be given, this function never guesses
    which the caller meant and never silently prefers one:

    Mode A (leaderboard_html): discover_sg_game_code() scans a real
    captured leaderboard page. This is the only mode that also proves,
    before any network call, that the tournament's own real page links
    to an SG page at all -- valuable when you do not already know
    whether one exists.

    Mode B (game_code): an already-known real gameCode, given
    directly -- skips discovery because there is nothing left to
    discover. The trade-off, made explicit rather than silently
    dropped: this mode has no equivalent up-front proof that an SG
    page exists for this gameCode. It does not need one to stay
    honest, though -- build_warehouse_rows() below still raises a real
    ValueError (caught and reported, never papered over) whenever the
    fetched page turns out to have no SG table, exactly as it always
    has for Mode A. A tournament that genuinely has no SG data
    produces an honest 'no rows parsed' result in either mode; Mode A
    just finds that out one HTTP round-trip earlier."""
    if leaderboard_html and game_code:
        raise ValueError("pass exactly one of leaderboard_html or game_code, not both")
    if game_code:
        return game_code
    if leaderboard_html:
        return discover_sg_game_code(leaderboard_html)
    raise ValueError("one of leaderboard_html or game_code is required")


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


def fetch_sg_detail_html_instrumented(client: PoliteHttpClient, game_code: str, round_number: Optional[int]) -> tuple[str, float]:
    """MISSION V91: the exact same request fetch_sg_detail_html() has
    always made -- reused unchanged, not duplicated -- timed with
    time.monotonic() so callers can report real per-request latency
    instead of a guess."""
    start = time.monotonic()
    html = fetch_sg_detail_html(client, game_code, round_number)
    return html, time.monotonic() - start


def collect_native_ajax(
    client: PoliteHttpClient, game_code: str, *, season: int, tournament: str,
    scope: Optional[str] = None, round_number: Optional[int] = None,
    id_lookup: Optional[dict] = None, warehouse_path: Path = DEFAULT_WAREHOUSE_PATH,
) -> dict:
    """MISSION V91 ("Native AJAX Collector"): collects directly from
    POST /load/leaderboard/strokesGained_detail using only gameCode and
    round -- no leaderboard/wrapper page is ever fetched, requested, or
    accepted as a parameter here; there is structurally nothing for
    one to do in this function's signature. The wrapper page was never
    actually a runtime dependency of the *live* path either (see
    fetch_sg_detail_html(), already POST-only, already gameCode+round
    only, since MISSION V81) -- what this function adds is the two
    things that genuinely did not exist before: (1) a clean, dedicated
    entry point whose signature makes the no-wrapper-page fact
    structural rather than incidental, and (2) real instrumentation
    (request count, per-request and total latency, rows parsed).

    Reuses, unchanged: fetch_sg_detail_html() for the request itself,
    build_warehouse_rows() -> parse_sg_html() for parsing (MISSION
    V91's own rule: "keep the existing parser, only replace the
    acquisition layer" -- nothing about parsing changes here), and
    merge_into_warehouse() for the write. Only the acquisition
    call-site gains a clock.

    scope=None (the default) collects every scope this collector has
    always tried -- tournament_cumulative plus rounds 1-4 (MISSION
    V91 item 3, "support both Tournament Total and Single Round" --
    both, not a choice between them, unless the caller narrows it).
    scope="tournament_cumulative" or scope="single_round" (with
    round_number) narrows to exactly one real request."""
    if scope is None:
        requested_scopes = list(_ROUND_SCOPES)
    elif scope == "tournament_cumulative":
        requested_scopes = [("tournament_cumulative", None)]
    elif scope == "single_round":
        if round_number is None:
            raise ValueError("scope='single_round' requires round_number")
        requested_scopes = [("single_round", round_number)]
    else:
        raise ValueError(f"unknown scope={scope!r} -- expected None, 'tournament_cumulative', or 'single_round'")

    id_lookup = id_lookup or {}
    all_rows: list[dict] = []
    latencies: list[float] = []
    for req_scope, req_round in requested_scopes:
        html, latency = fetch_sg_detail_html_instrumented(client, game_code, req_round)
        latencies.append(latency)
        try:
            rows = build_warehouse_rows(
                html, game_code=game_code, season=season, tournament=tournament,
                scope=req_scope, round_number=req_round, id_lookup=id_lookup,
                source_note=(
                    f"{BASE_URL}{SG_DETAIL_POST_PATH} POST gameCode={game_code}, round={req_round if req_round else 'cumulative'} "
                    f"(native AJAX acquisition, no wrapper page fetched)"
                ),
            )
        except ValueError:
            continue  # this scope genuinely has no SG table (e.g. round not played) -- never a fabricated row
        all_rows.extend(rows)

    merge_result = merge_into_warehouse(all_rows, warehouse_path)
    return {
        "status": "collected" if all_rows else "no_rows_parsed", "game_code": game_code, "rows_parsed": len(all_rows),
        "requests_made": len(requested_scopes), "total_latency_seconds": round(sum(latencies), 4),
        "avg_latency_seconds": round(sum(latencies) / len(latencies), 4) if latencies else None,
        "per_request_latency_seconds": [round(x, 4) for x in latencies],
        "acquisition": "native_ajax",
        **merge_result,
    }


def collect_native_ajax_from_saved_response(
    sg_response_html: str, game_code: str, *, season: int, tournament: str,
    scope: str = "tournament_cumulative", round_number: Optional[int] = None,
    id_lookup: Optional[dict] = None, warehouse_path: Path = DEFAULT_WAREHOUSE_PATH,
) -> dict:
    """MISSION V91's offline counterpart to collect_native_ajax(), for
    an environment (like this one) with no live network path -- the
    exact same acquisition contract (gameCode + round only, no wrapper
    page, no leaderboard_html parameter at all), given an already-saved
    copy of the real strokesGained_detail response instead of fetching
    it live. Used to prove Old-vs-Native equivalence offline in
    MISSION V91's own comparison (see the mission's item 7)."""
    id_lookup = id_lookup or {}
    rows = build_warehouse_rows(
        sg_response_html, game_code=game_code, season=season, tournament=tournament,
        scope=scope, round_number=round_number, id_lookup=id_lookup,
        source_note=f"operator-saved copy of {BASE_URL}{SG_DETAIL_POST_PATH} POST gameCode={game_code}, round={round_number or 'cumulative'} (native AJAX acquisition, no wrapper page)",
    )
    merge_result = merge_into_warehouse(rows, warehouse_path)
    return {"status": "collected" if rows else "no_rows_parsed", "game_code": game_code, "rows_parsed": len(rows), "acquisition": "native_ajax", **merge_result}


def _load_script_63():
    """scripts/63_collect_historical_sg_warehouse.py is MISSION V94's
    designated canonical SG collector -- imported by number-prefixed
    filename via importlib, since '63_...' is not a legal Python
    module name to import by name."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("script_63_canonical_collector", Path(__file__).resolve().parent / "63_collect_historical_sg_warehouse.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def collect_live(
    client: PoliteHttpClient, leaderboard_html: Optional[str] = None, *, season: int, tournament: str,
    id_lookup: Optional[dict] = None, warehouse_path: Path = DEFAULT_WAREHOUSE_PATH, game_code: Optional[str] = None,
) -> dict:
    """MISSION V94: wraps scripts/63_collect_historical_sg_warehouse.py's
    _collect_one() -- the repository's one canonical SG collector --
    instead of re-implementing the fetch. This function's own
    discovery contract is unchanged (Mode A via leaderboard_html, Mode
    B via game_code, resolve_game_code() decides which -- exactly one
    must be given) and its return shape is unchanged, so every caller
    built against it since MISSION V81 keeps working with zero changes
    on their end. What changed underneath: script 63's _collect_one()
    also fetches roundLeaderboard for rounds 4..1 to resolve a real
    player_id per round before parsing SG -- richer identity resolution
    than this function used to do on its own (which relied entirely on
    an externally-supplied id_lookup, usually empty in practice -- the
    exact identity-collision gap this session's own testing flagged
    repeatedly in MISSION V82/V83). merge_into_warehouse() is still
    this function's own, unchanged merge step."""
    resolved_game_code = resolve_game_code(leaderboard_html, game_code)
    if not resolved_game_code:
        return {"status": "no_sg_link_found", "game_code": None}
    script_63 = _load_script_63()
    result = script_63._collect_one(resolved_game_code, season, tournament)
    if result["status"] != "success":
        return {"status": "no_rows_parsed", "game_code": resolved_game_code, "rows_parsed": 0, "error": result.get("error")}
    rows = [dict(r, **script_63.standardize_player_name(r.get("player"), r.get("player_id"))) for r in result.get("records", [])]
    if id_lookup:  # an explicitly-supplied id_lookup, when given, still gets a chance to resolve any row script 63's own roundLeaderboard lookup left UNRESOLVED_IDENTITY -- never overwrites a real RETAINED id.
        for row in rows:
            if row.get("identity_state") == "UNRESOLVED_IDENTITY" and id_lookup.get(str(row.get("player"))):
                row.update({"player_id": id_lookup[str(row["player"])], "identity_state": "RETAINED"})
    merge_result = merge_into_warehouse(rows, warehouse_path)
    return {"status": "collected", "game_code": resolved_game_code, "rows_parsed": len(rows), **merge_result}


def collect_from_saved_page(
    leaderboard_html: Optional[str] = None, sg_page_html: str = "", *, season: int, tournament: str,
    scope: str, round_number: Optional[int], id_lookup: Optional[dict] = None,
    warehouse_path: Path = DEFAULT_WAREHOUSE_PATH, game_code: Optional[str] = None,
) -> dict:
    """Same discover-or-accept -> parse -> save cycle, for an
    environment (like this one) with no live network path to
    klpga.co.kr. `sg_page_html` is an already-saved copy of the real
    /web/leaderboard/strokesGained?gameCode=... page (or its
    strokesGained_detail response) -- the exact ingestion pattern this
    repository already uses for Hana (scripts/154_ingest_hana_r1_sg_raw.py
    + scripts/155_build_hana_r1_sg_v1.py), generalized to any game_code
    instead of one hardcoded to it. Accepts either Mode A
    (leaderboard_html) or Mode B (game_code) -- see
    resolve_game_code()'s own docstring. Exactly one must be given."""
    resolved_game_code = resolve_game_code(leaderboard_html, game_code)
    if not resolved_game_code:
        return {"status": "no_sg_link_found", "game_code": None}
    discovery_note = "discovered via the same page's own link, no live network fetch" if leaderboard_html else "game_code given directly by the operator, no leaderboard page discovery"
    id_lookup = id_lookup or {}
    rows = build_warehouse_rows(
        sg_page_html, game_code=resolved_game_code, season=season, tournament=tournament,
        scope=scope, round_number=round_number, id_lookup=id_lookup,
        source_note=(
            f"operator-saved copy of {BASE_URL}{SG_WEB_PAGE_PATH}?gameCode={resolved_game_code} ({discovery_note})"
        ),
    )
    merge_result = merge_into_warehouse(rows, warehouse_path)
    return {"status": "collected", "game_code": resolved_game_code, "rows_parsed": len(rows), **merge_result}


def _ensure_utf8_console() -> None:
    """MISSION V88: Windows' default console codepage (cp1252/cp949,
    never UTF-8) makes `print()` raise UnicodeEncodeError the moment a
    real Korean player name reaches stdout -- this collector's output
    always contains one. Reconfiguring stdout/stderr to UTF-8 is a
    no-op on Linux/macOS (already UTF-8) and the real fix on Windows;
    guarded because Python <3.7 lacks TextIOWrapper.reconfigure()."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def main() -> None:
    _ensure_utf8_console()
    ap = argparse.ArgumentParser(description=__doc__)
    discovery = ap.add_mutually_exclusive_group(required=True)
    discovery.add_argument("--leaderboard-html-file", help="Mode A: a captured leaderboard page to scan for a real strokesGained link.")
    discovery.add_argument("--game-code", help="Mode B: an already-known real gameCode, given directly -- skips leaderboard discovery. See resolve_game_code()'s docstring for the trade-off.")
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--tournament", required=True)
    ap.add_argument("--live", action="store_true", help="Fetch live via PoliteHttpClient (requires real network access to klpga.co.kr).")
    ap.add_argument("--sg-html-file", help="An already-saved SG page/response, for offline collection (see module docstring's NETWORK NOTE).")
    ap.add_argument("--scope", default="tournament_cumulative", choices=["tournament_cumulative", "single_round"], help="Only used with --sg-html-file, which can only ever represent one scope per run.")
    ap.add_argument("--round", type=int, default=None, help="Only used with --sg-html-file when --scope=single_round.")
    ap.add_argument("--warehouse", default=str(DEFAULT_WAREHOUSE_PATH))
    args = ap.parse_args()

    leaderboard_html = Path(args.leaderboard_html_file).read_text(encoding="utf-8", errors="replace") if args.leaderboard_html_file else None
    warehouse_path = Path(args.warehouse)

    # MISSION V91 item 8: Native AJAX is the default for Mode B (a
    # known game_code -- there is nothing to discover, so there is no
    # reason to run the discovery-oriented Old path). Mode A
    # (--leaderboard-html-file) still runs the Old collect_live() /
    # collect_from_saved_page() path -- kept, unmodified, as the real
    # fallback for when game_code is not already known.
    if args.live:
        client = PoliteHttpClient(cache_dir=ROOT / "data" / "raw_cache" / "http")
        if args.game_code:
            result = collect_native_ajax(client, args.game_code, season=args.season, tournament=args.tournament, warehouse_path=warehouse_path)
        else:
            result = collect_live(client, leaderboard_html, season=args.season, tournament=args.tournament, warehouse_path=warehouse_path)
    elif args.sg_html_file:
        sg_html = Path(args.sg_html_file).read_text(encoding="utf-8", errors="replace")
        if args.game_code:
            result = collect_native_ajax_from_saved_response(
                sg_html, args.game_code, season=args.season, tournament=args.tournament,
                scope=args.scope, round_number=args.round, warehouse_path=warehouse_path,
            )
        else:
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
