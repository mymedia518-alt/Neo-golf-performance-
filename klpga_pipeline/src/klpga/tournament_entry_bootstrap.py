"""NEO TOURNAMENT PIPELINE Phase 3 item 2: the generic ENTRY LIST /
IDENTITY prerequisite -- the step run_tournament.py must complete
between DISCOVERY and PRE FREEZE, for any game_code, with no
tournament-specific script.

Deliberately scoped to what is genuinely tournament-independent today:
fetching and parsing the official entry list (klpga.collectors.entry_list
/ klpga.parsers.entry_list_parser, both already confirmed generic).
Cross-referencing player_master for identity_match/canonical_name (what
scripts/15_collect_entry_list.py does against a populated
data/klpga.sqlite) is NOT attempted here -- that DB and the historical
pipeline that populates player_master are a separate, not-yet-generic
prerequisite. Never fabricated: entries are written with
identity_match=None (unresolved), not a guessed True/False.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
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


def collect_entry_list_snapshot(context: TournamentContext, *, cache_dir: Path, client=None) -> Path:
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
    entries = [
        {**asdict(row), "identity_match": None, "canonical_name": None}
        for row in result.rows
    ]
    payload = {
        "schema_version": "neo_tournament_entry_bootstrap_v1",
        "game_code": context.game_code,
        "retrieved_at": retrieved_at,
        "source_url": f"{config.ENTRY_LIST_ENDPOINT}?gameCode={context.game_code}",
        "player_count": len(entries),
        "parser_unparsed_rows": result.unparsed_row_count,
        "identity_matched": "not attempted (no player_master DB in this run)",
        "entries": entries,
    }

    out_path = context.artifact_path("entry_snapshot")
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path
