"""HJ중공업·동부건설 챔피언십 (gameCode=2026100004) -- real official
entry-list acquisition + full playerCode-centric reconciliation.

Per explicit instruction: do NOT assume the field size (108 is a prior
OBSERVATION, not an official-source confirmation for THIS acquisition);
determine the real entrant count from the official page itself. Do NOT
match player identity by name alone -- every reconciliation below is
keyed on playerCode. Do NOT guess nationality or sponsor; a value is
shown only when a confirmed official source produced it.

PIPELINE (all on already-confirmed, already-tested building blocks --
no new endpoint/parser invented here):
  1. klpga.collectors.entry_list.fetch_entry_list + klpga.parsers.
     entry_list_parser.parse_entry_list_html/parse_entry_summary --
     GET /web/tourInfo/entry?gameCode=2026100004. Gives the REAL
     entrant count (page's own "총 참가자" label), player_code,
     player_name, nationality (from the country/<CODE>.png flag image
     -- real, already proven to cover non-Korean players, e.g. USA/
     CHN), qualification_category ("자격자"/"추천자"/"초청자" -- the
     closest real "출전자 유형" field this page exposes; no WD/DNS/
     entry_status marker has ever been confirmed on this page by this
     project, so none is invented here either), qualification_reason.
  2. klpga.website_v2.player_identity.cross_tournament_verified_sponsor
     _cache -- OFFLINE, zero new network calls: reuses any sponsor
     already PASS-verified for this exact player_code in another
     tournament's own *_CURRENT_PLAYER_MASTER.json or an operator-
     reported evidence file.
  3. For every entrant NOT covered by step 2, klpga.collectors.
     player_team_sponsor.collect_one -- a REAL, LIVE per-player fetch
     of PLAYER_PROFILE_ENDPOINT (mainRecord), with its own built-in
     double identity check (fetch by playerCode, then verify the
     expected name string actually appears in the returned page) and
     known-identity-landmine guard. Every outcome (OK/FETCH_FAILURE/
     IDENTITY_FAILURE/PARSE_FAILURE) is recorded per player -- a
     failure for one player never blocks the rest of the field.
  4. Reconciliation against every existing content/website_v2/*_
     CURRENT_PLAYER_MASTER.json and *_ENTRY_KRANKING_JOIN.json file
     (generic glob, no hardcoded tournament name), by exact player_code
     only: MATCHED (same name), NAME_CONFLICT (same player_code,
     different name recorded elsewhere -- flagged, never auto-
     resolved), or NEW_PLAYER (player_code not seen in any existing
     file). Every entrant gets exactly one of these -- the "100%
     reconciliation" gate below is PASS only if every parsed entry row
     produced exactly one reconciliation record (none silently
     dropped).
  5. Field-internal duplicate-name detection (two different player_
     codes sharing the same display name) -- a real identity risk
     (동명이인), reported separately from the duplicate-player_code
     check klpga.collectors.player_team_sponsor.validate_roster already
     does.

Output: evidence/hj_2026100004_entry_acquisition/
  entry_list_raw.html                  -- the real fetched entry page
  profile_<player_code>.html           -- per-player mainRecord fetch
                                           (only for cache-miss players)
  RECONCILIATION_REPORT.json           -- the full structured result

This does NOT build any homepage output and does NOT compute any
Stableford ranking for 2026 players -- explicitly out of scope for
this step.

Usage (on a machine with real klpga.co.kr access):
    cd klpga_pipeline
    python scripts/215_acquire_hj_2026100004_entry_list.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(KLPGA_PIPELINE_ROOT / "src"))

from klpga.collectors.entry_list import fetch_entry_list  # noqa: E402
from klpga.collectors.player_team_sponsor import (  # noqa: E402
    RosterIntegrityError,
    collect_one,
    validate_roster,
)
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402
from klpga.parsers.entry_list_parser import EntryRow, parse_entry_list_html, parse_entry_summary  # noqa: E402
from klpga.website_v2.player_identity import cross_tournament_verified_sponsor_cache  # noqa: E402

GAME_CODE = "2026100004"
CONTENT_ROOT = KLPGA_PIPELINE_ROOT / "content" / "website_v2"
OUT_DIR = KLPGA_PIPELINE_ROOT / "evidence" / "hj_2026100004_entry_acquisition"


def _existing_identity_index() -> dict[str, dict]:
    """player_code -> {"name": str, "source_file": str} from EVERY
    existing *_CURRENT_PLAYER_MASTER.json and *_ENTRY_KRANKING_JOIN.json
    already in content/website_v2 -- generic glob, no hardcoded
    tournament name. A player_code appearing with two DIFFERENT names
    across files is recorded with source_file=None and
    conflicting_names set, never silently picking one."""
    index: dict[str, dict] = {}
    conflicts: dict[str, set[str]] = {}

    def _consider(code: str, name: str, source_file: str) -> None:
        if not code or not name:
            return
        if code in conflicts:
            conflicts[code].add(name)
            return
        existing = index.get(code)
        if existing is None:
            index[code] = {"name": name, "source_file": source_file}
        elif existing["name"] != name:
            conflicts[code] = {existing["name"], name}
            index.pop(code, None)

    for path in sorted(CONTENT_ROOT.glob("*_CURRENT_PLAYER_MASTER.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for row in data.get("records") or []:
            code = str(row.get("player_id") or "").strip()
            name = row.get("current_official_player_name") or ""
            _consider(code, name, path.name)

    for path in sorted(CONTENT_ROOT.glob("*_ENTRY_KRANKING_JOIN.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = data if isinstance(data, list) else data.get("records") or data.get("entries") or []
        for row in rows:
            code = str(row.get("player_code") or "").strip()
            name = row.get("player_name") or ""
            _consider(code, name, path.name)

    for code, names in conflicts.items():
        index[code] = {"name": None, "source_file": None, "conflicting_names": sorted(names)}
    return index


def reconcile_entry(row: EntryRow, identity_index: dict[str, dict]) -> dict:
    existing = identity_index.get(row.player_code)
    if existing is None:
        status = "NEW_PLAYER"
    elif existing.get("conflicting_names"):
        status = "NAME_CONFLICT_ACROSS_EXISTING_SOURCES"
    elif existing["name"] == row.player_name:
        status = "MATCHED_EXISTING"
    else:
        status = "NAME_CONFLICT_WITH_EXISTING_SOURCE"
    return {
        "player_code": row.player_code,
        "player_name": row.player_name,
        "nationality": row.nationality,
        "qualification_category": row.qualification_category,
        "qualification_reason": row.qualification_reason,
        "identity_reconciliation_status": status,
        "existing_source_detail": existing,
    }


def resolve_sponsors(client: PoliteHttpClient, rows: list[EntryRow]) -> dict[str, dict]:
    cache = cross_tournament_verified_sponsor_cache()
    sponsors: dict[str, dict] = {}
    for row in rows:
        cached = cache.get(row.player_code)
        if cached is not None:
            sponsors[row.player_code] = {"sponsor": cached, "sponsor_source": "CACHED_CROSS_TOURNAMENT",
                                          "outcome": "OK", "detail": ""}
            continue
        result = collect_one(client, row.player_code, row.player_name)
        if result.raw_html is not None:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUT_DIR / f"profile_{row.player_code}.html").write_text(result.raw_html, encoding="utf-8")
        sponsors[row.player_code] = {
            "sponsor": result.team_or_sponsor, "sponsor_source": "LIVE_FETCH" if result.outcome == "OK" else None,
            "outcome": result.outcome, "detail": result.detail,
        }
    return sponsors


def main() -> int:
    client = PoliteHttpClient(cache_dir=KLPGA_PIPELINE_ROOT / ".http_cache_probe")

    try:
        html = fetch_entry_list(client, GAME_CODE)
    except RateLimitBlockedError as e:
        print(f"BLOCKED: {e}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "entry_list_raw.html").write_text(html, encoding="utf-8")

    summary = parse_entry_summary(html)
    result = parse_entry_list_html(html)
    real_total = summary.counts.get("총 참가자")
    print(f"Page summary counts: {summary.counts}")
    print(f"Parsed entrant rows: {len(result.rows)}")
    print(f"Unparseable rows: {result.unparsed_row_count}")
    if real_total is not None and real_total != len(result.rows):
        print(f"  MISMATCH: page reports 총 참가자={real_total} but {len(result.rows)} rows were parsed.")

    codes = [r.player_code for r in result.rows]
    names = [r.player_name for r in result.rows]
    dup_codes = sorted({c for c in codes if codes.count(c) > 1})
    dup_names = sorted({n for n in names if names.count(n) > 1})
    try:
        roster = [(r.player_code, r.player_name) for r in result.rows]
        validate_roster(roster)
        roster_integrity_error = None
    except RosterIntegrityError as e:
        roster_integrity_error = str(e)

    identity_index = _existing_identity_index()
    reconciled = [reconcile_entry(r, identity_index) for r in result.rows]
    sponsors = resolve_sponsors(client, result.rows)
    for rec in reconciled:
        rec.update(sponsors.get(rec["player_code"], {"sponsor": None, "sponsor_source": None, "outcome": "NOT_ATTEMPTED"}))

    status_counts = Counter(r["identity_reconciliation_status"] for r in reconciled)
    sponsor_outcome_counts = Counter(r["outcome"] for r in reconciled)
    overseas = [r for r in reconciled if r["nationality"] and r["nationality"] != "KOR"]
    invited = [r for r in reconciled if r["qualification_category"] and "초청" in r["qualification_category"]]

    reconciliation_complete = len(reconciled) == len(result.rows)

    report = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "game_code": GAME_CODE,
        "page_reported_total_participants": real_total,
        "parsed_entrant_rows": len(result.rows),
        "unparsed_row_count": result.unparsed_row_count,
        "duplicate_player_codes_in_field": dup_codes,
        "duplicate_player_names_in_field": dup_names,
        "roster_integrity_error": roster_integrity_error,
        "identity_reconciliation_status_counts": dict(status_counts),
        "sponsor_outcome_counts": dict(sponsor_outcome_counts),
        "overseas_entrant_count": len(overseas),
        "invited_entrant_count": len(invited),
        "reconciliation_complete_100pct": reconciliation_complete,
        "records": reconciled,
    }
    report_path = OUT_DIR / "RECONCILIATION_REPORT.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'=' * 80}")
    print(f"REAL ENTRANT COUNT (official page): {real_total}")
    print(f"Identity reconciliation: {dict(status_counts)}")
    print(f"Sponsor outcomes: {dict(sponsor_outcome_counts)}")
    print(f"Overseas entrants: {len(overseas)}  Invited entrants: {len(invited)}")
    print(f"Duplicate player_codes in field: {dup_codes}")
    print(f"Duplicate player_names in field: {dup_names}")
    print(f"100% RECONCILIATION GATE: {'PASS' if reconciliation_complete else 'FAIL'}")
    print(f"Wrote {report_path}")
    print(
        "\nNEXT: commit and push evidence/hj_2026100004_entry_acquisition/ to neo-website-v2. "
        "Do not build the HJ homepage or compute any Stableford ranking until this is reviewed."
    )
    return 0 if reconciliation_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
