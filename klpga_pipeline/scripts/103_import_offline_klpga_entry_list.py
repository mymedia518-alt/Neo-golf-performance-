"""Sanctioned offline import path for a tournament's official entry
list when this session has no live klpga.co.kr access (proxy-blocked,
confirmed repeatedly) but a real, official page was captured elsewhere
by someone with real network access.

This never fabricates a field: it runs the exact same, already-
confirmed HTML parser (klpga.parsers.entry_list_parser) and identity-
match logic (klpga.tournament_entry_bootstrap) as the live collection
path -- see that module's collect_entry_list_snapshot_from_offline_html
-- against real, externally-captured HTML bytes handed to it via
--html-file, and records honest provenance (collection_method=
"offline_import", the file's own sha256, and the human-supplied
--source-description / --captured-at) rather than ever claiming this
session fetched the page.

For a game_code with no TOURNAMENT_SITE_REGISTRY.json entry yet, adds
one via klpga.tournament_context.ensure_site_registry_entry -- a
purely-structural, non-fabricated registry entry (internal naming
derived mechanically from game_code/season/final_round_number), never
a source edit and never a guessed human-readable route slug.

Usage:
    python scripts/103_import_offline_klpga_entry_list.py \\
        --game-code 2026090003 \\
        --tournament-name "KB금융 골든라이프 챔피언십" \\
        --season 2026 --start-date 2026-09-10 --end-date 2026-09-13 \\
        --final-round-number 3 \\
        --html-file /path/to/captured_entry_page.html \\
        --source-description "saved via browser view-source from
            https://klpga.co.kr/web/tourInfo/entry?gameCode=2026090003,
            operator-provided" \\
        --captured-at 2026-09-09T00:00:00Z

Prints exactly one JSON summary line to stdout as its last line.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_context import ensure_site_registry_entry, resolve_context  # noqa: E402
from klpga.tournament_entry_bootstrap import (  # noqa: E402
    EntryListBootstrapBlocked,
    collect_entry_list_snapshot_from_offline_html,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--tournament-name", required=True)
    parser.add_argument("--season", required=True, type=int)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--final-round-number", required=True, type=int)
    parser.add_argument("--current-round-number", type=int, default=0)
    parser.add_argument("--html-file", required=True, help="path to the real, externally-captured entry-list page HTML")
    parser.add_argument("--source-description", required=True, help="how/where the page was actually captured, by whom")
    parser.add_argument("--captured-at", required=True, help="ISO8601 timestamp of the real capture, as reported by whoever captured it")
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"), help="player_master DB for identity-match; skipped if missing")
    args = parser.parse_args()

    html_path = Path(args.html_file)
    if not html_path.is_file():
        print(json.dumps({"action": "ERROR", "reason": f"--html-file not found: {html_path}"}))
        return 2
    html = html_path.read_text(encoding="utf-8")

    identity = {
        "game_code": args.game_code,
        "tournament_name": args.tournament_name,
        "season": args.season,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "final_round_number": args.final_round_number,
        "current_round_number": args.current_round_number,
    }
    registry = ensure_site_registry_entry(identity)
    context = resolve_context(identity, registry)

    db_path = Path(args.db)
    try:
        out_path = collect_entry_list_snapshot_from_offline_html(
            context, html,
            source_description=args.source_description,
            captured_at=args.captured_at,
            db_path=db_path if db_path.is_file() else None,
        )
    except EntryListBootstrapBlocked as exc:
        print(json.dumps({"action": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 1

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    result = {
        "action": "IMPORTED",
        "game_code": args.game_code,
        "entry_snapshot_path": str(out_path.relative_to(ROOT)),
        "player_count": payload["player_count"],
        "duplicate_player_ids": payload["duplicate_player_ids"],
        "unresolved_player_ids": payload["unresolved_player_ids"],
        "identity_matched": payload["identity_matched"],
        "source_sha256": payload["source_sha256"],
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
