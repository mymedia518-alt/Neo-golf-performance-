"""NEO TOURNAMENT PIPELINE Phase 3/4 item: the generic ENTRY LIST /
IDENTITY prerequisite -- the step run_tournament.py must complete
between DISCOVERY and PRE FREEZE, for any game_code, with no
tournament-specific script.

Fetches and parses the official entry list (klpga.collectors.entry_list
/ klpga.parsers.entry_list_parser, both already confirmed generic).
Cross-referencing player_master for identity_match/canonical_name (what
scripts/15_collect_entry_list.py, and formerly
scripts/67_build_ok_open_pre_performance.py's own inline copy, do
against a populated data/klpga.sqlite) is done here too when a
`db_path` is supplied and exists -- this is the single producer of the
`entry_snapshot` artifact for every caller (run_tournament.py's
DISCOVERY-time prerequisite AND script 67's PRE-freeze build), so
there is exactly one schema and one immutability guard, never two
competing writers of the same artifact_type. Never fabricated: with no
DB (or a player_id absent from it), identity_match is False/None, not
a guessed True.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path

from klpga import config
from klpga.collectors.entry_list import fetch_entry_list
from klpga.http_client import PoliteHttpClient
from klpga.parsers.entry_list_parser import parse_entry_list_html
from klpga.tournament_context import TournamentContext


class EntryListBootstrapBlocked(RuntimeError):
    """The official entry list is not usable yet (not published, or
    parsed to zero rows) -- the caller should treat this as WAIT, never
    fabricate a field."""


def collect_entry_list_snapshot(
    context: TournamentContext,
    *,
    cache_dir: Path,
    db_path: Path | None = None,
    client=None,
) -> Path:
    """Fetch, parse, and (when `db_path` is given and exists) identity-
    match the official entry list against `player_master`, then write
    the frozen `entry_snapshot` artifact. Raises EntryListBootstrapBlocked
    (never fabricates) if the page isn't usable yet. Does NOT check
    whether the artifact already exists -- callers that must be
    immutable-once-written (script 67's own historical contract) check
    `context.artifact_path("entry_snapshot").exists()` first."""
    client = client if client is not None else PoliteHttpClient(cache_dir=Path(cache_dir))
    html = fetch_entry_list(client, context.game_code)
    try:
        result = parse_entry_list_html(html)
    except ValueError as exc:
        raise EntryListBootstrapBlocked(
            f"official entry list page for game_code={context.game_code} did not match the "
            f"confirmed shape (not published yet, or the page changed): {exc}"
        ) from exc

    if not result.rows:
        raise EntryListBootstrapBlocked(
            f"official entry list for game_code={context.game_code} parsed to zero rows -- "
            "not published yet, or the page shape changed; refusing to write an empty snapshot"
        )

    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    known: dict[str, str] = {}
    if db_path is not None and Path(db_path).exists():
        conn = sqlite3.connect(db_path)
        try:
            known = {str(r[0]): str(r[1]) for r in conn.execute("SELECT player_id, player_name FROM player_master")}
        finally:
            conn.close()

    entries = []
    seen: set[str] = set()
    duplicates: list[str] = []
    for row in result.rows:
        code = str(row.player_code)
        if code in seen:
            duplicates.append(code)
        seen.add(code)
        entries.append({
            "player_id": code,
            "player_name": row.player_name,
            "entry_status": "listed",
            "nationality": row.nationality,
            "qualification_category": row.qualification_category,
            "qualification_reason": row.qualification_reason,
            "identity_match": (code in known) if known else None,
            "canonical_name": known.get(code),
        })
    unresolved = [e["player_id"] for e in entries if known and not e["identity_match"]]

    payload = {
        "schema_version": "neo_tournament_entry_v1",
        "game_code": context.game_code,
        "retrieved_at": retrieved_at,
        "source_url": f"{config.ENTRY_LIST_ENDPOINT}?gameCode={context.game_code}",
        "player_count": len(entries),
        "parser_unparsed_rows": result.unparsed_row_count,
        "duplicate_player_ids": duplicates,
        "unresolved_player_ids": unresolved,
        "withdrawals_marked_by_source": [],
        "identity_matched": "player_master identity match attempted" if known else "not attempted (no player_master DB in this run)",
        "entries": entries,
    }

    out_path = context.artifact_path("entry_snapshot")
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path
