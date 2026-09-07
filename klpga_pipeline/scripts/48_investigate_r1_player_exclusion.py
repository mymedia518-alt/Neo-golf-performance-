"""INVESTIGATION — scripts/48_investigate_r1_player_exclusion.py

READ-ONLY. A narrow, single-player deep dive: for one player_code that
has a real round_number=1 row in the DB but is entirely absent from
the frozen BETA #001-C PRE (and therefore R1) snapshot, this answers
ONE question only — WHY was this player excluded from the frozen
PRE field?

Never writes to the DB (opened `mode=ro`), never modifies or
regenerates any prediction/history artifact. Reuses the exact same
read-only evidence functions as scripts/45_audit_beta001c_r1.py (see
klpga.neo_win.r1_provenance) — never a second, independently
maintained copy of the same evidence-gathering logic.

======================================================================
EVIDENCE GATHERED (all real, all disclosed with their own caveats)
======================================================================
1. player_name (player_master), current player_event detail.
2. Every real round_number=1 player_round row for this player_code.
3. Whether this player_code is in the frozen PRE snapshot's own
   120-player field (direct membership check against the frozen JSON).
4. The REAL entry-list HTML cached for this exact game_code (the same
   raw response klpga.collectors.entry_list.fetch_entry_list would
   have fetched), re-parsed with the SAME parser the production
   collector uses (klpga.parsers.entry_list_parser.parse_entry_list_html)
   — giving a real, code-verified player_code set from that cached
   page, compared against the frozen PRE's own 120 codes. The cache
   file's own filesystem mtime is reported as "most recent real fetch
   time for the content on disk today" — see klpga.neo_win.
   r1_provenance.find_entry_list_cache_file's own caveat: it is NOT
   proof of a first-ever-seen timestamp, because a cache HIT never
   rewrites the file.
5. tournament_entry.collected_at for this player_code — also disclosed
   with its own caveat: klpga.db.upsert._upsert uses
   ON CONFLICT DO UPDATE SET col=excluded.col for EVERY column
   including collected_at, and scripts/15_collect_entry_list.py always
   writes the CURRENT wall-clock time on every run regardless of
   whether the underlying HTTP fetch was a real fetch or a cache hit —
   so this column reflects "the last time any collection run touched
   this row", not "when this player first appeared in the real field".
6. raw HTTP cache hits anywhere referencing this game_code (broad
   scan, not just the entry-list endpoint) and whether this
   player_code's text appears in them.
7. The set of player_codes present in the frozen PRE's 120-player
   field but ABSENT from the real cached entry-list's own parsed set
   (if that cache file exists) — candidate "replaced" player(s). And
   the reverse: codes in the real cached field but not in PRE (should
   include this investigation's own player_code).

======================================================================
ROOT CAUSE CLASSIFICATION (evidence-only, never guessed)
======================================================================
Requires the entry-list cache file (item 4) to exist, since that is
the only source giving a REAL, parseable player_code set with a real
filesystem mtime to compare against the PRE freeze timestamp:
  - LATE_ENTRY: the cached entry-list content (which includes this
    player_code) has an mtime AFTER the PRE snapshot's own
    created_at_utc — consistent with a real late field addition
    captured by a later real fetch. Still not fully conclusive (see
    output caveat), but the only positive, non-defect explanation this
    script can support.
  - COLLECTOR_OMISSION: the cached entry-list content's mtime is AT OR
    BEFORE PRE's created_at_utc, yet this player_code is absent from
    the frozen PRE's own 120 — meaning the real field data available
    to the system before/at PRE generation already included this
    player, and PRE's own field-selection code failed to include them.
    A real code defect candidate, not a data-timing explanation.
  - UNRESOLVED: no entry-list cache file found for this exact
    (endpoint, game_code) key — real field content at any specific
    time cannot be determined from this evidence; classification
    withheld rather than guessed.

Usage:
    python scripts/48_investigate_r1_player_exclusion.py --db data/klpga.sqlite \\
        --game-code 2026080001 --pre-cutoff-date 2026-08-27 --player-code 9384 \\
        --raw-cache-dir data/raw_cache/http
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga import config  # noqa: E402
from klpga.neo_win.beta001c_archive import archive_paths as c_archive_paths, read_neo_win_c_snapshot  # noqa: E402
from klpga.neo_win.r1_provenance import (  # noqa: E402
    all_round_rows_for_player,
    find_entry_list_cache_file,
    real_entry_field_codes_from_cached_html,
)

ROOT = Path(__file__).resolve().parents[1]

ROOT_CAUSE_LATE_ENTRY = "LATE_ENTRY"
ROOT_CAUSE_COLLECTOR_OMISSION = "COLLECTOR_OMISSION"
ROOT_CAUSE_UNRESOLVED = "UNRESOLVED"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--pre-cutoff-date", required=True)
    parser.add_argument("--c-predictions-dir", default=str(ROOT / "neo_win_c_predictions"))
    parser.add_argument("--pre-prediction-id", default="001-C-FINAL")
    parser.add_argument("--player-code", required=True)
    parser.add_argument("--raw-cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3

    pre_json_path, _ = c_archive_paths(
        Path(args.c_predictions_dir), args.pre_prediction_id, args.game_code, args.pre_cutoff_date
    )
    if not pre_json_path.exists():
        print(f"ERROR: frozen BETA #001-C PRE snapshot not found at {pre_json_path}.")
        return 5
    pre_snapshot = read_neo_win_c_snapshot(pre_json_path)
    pre_field_codes = {e.player_code for e in pre_snapshot.predictions}
    pre_names_by_code = {e.player_code: e.player_name for e in pre_snapshot.predictions}

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        master_row = conn.execute(
            "SELECT player_name FROM player_master WHERE player_id = ?", (args.player_code,)
        ).fetchone()
        player_name = master_row[0] if master_row else None

        event_row = conn.execute(
            "SELECT player_name, finish_position, finish_position_numeric, made_cut, withdrawn, disqualified, "
            "rounds_played, score_to_par FROM player_event WHERE game_code = ? AND player_id = ?",
            (args.game_code, args.player_code),
        ).fetchone()

        entry_row = conn.execute(
            "SELECT collected_at FROM tournament_entry WHERE game_code = ? AND player_code = ?",
            (args.game_code, args.player_code),
        ).fetchone()
        in_entry_field_today = entry_row is not None
        entry_collected_at = entry_row[0] if entry_row is not None else None

        all_rounds = all_round_rows_for_player(conn, args.game_code, args.player_code)
    finally:
        conn.close()

    r1_rows = [r for r in all_rounds if r["round_number"] == 1]

    in_pre_field = args.player_code in pre_field_codes

    cache_dir = Path(args.raw_cache_dir)
    entry_cache = find_entry_list_cache_file(cache_dir, config.ENTRY_LIST_ENDPOINT, args.game_code)
    real_field_codes = None
    if entry_cache is not None and entry_cache.get("body_text"):
        real_field_codes = real_entry_field_codes_from_cached_html(entry_cache["body_text"])

    print(f"=== {args.player_code} PRE-FIELD-EXCLUSION INVESTIGATION (READ-ONLY) ===")
    print()
    print(f"1. player_name (player_master): {player_name!r}")
    if event_row is not None:
        (ev_name, finish_position, finish_position_numeric, made_cut, withdrawn, disqualified,
         rounds_played, score_to_par) = event_row
        print(
            f"   player_event: player_name={ev_name!r} finish_position={finish_position!r} "
            f"finish_position_numeric={finish_position_numeric!r} made_cut={bool(made_cut)} "
            f"withdrawn={bool(withdrawn)} disqualified={bool(disqualified)} "
            f"rounds_played={rounds_played!r} score_to_par={score_to_par!r}"
        )
    else:
        print("   player_event: no row exists")
    print()
    print(f"2. round_number=1 player_round row(s) for {args.player_code}:")
    if r1_rows:
        for r in r1_rows:
            print(
                f"   - round_score={r['round_score']!r} round_to_par={r['round_to_par']!r} "
                f"finish_position_after_round={r['finish_position_after_round']!r} "
                f"is_completed_score={r['is_completed_score']}"
            )
    else:
        print("   (none)")
    print()
    print(f"3. In frozen PRE snapshot's own 120-player field ({pre_json_path.name}): {in_pre_field}")
    print()
    print("4. Real entry-list cache evidence (klpga.config.ENTRY_LIST_ENDPOINT, this game_code):")
    if entry_cache is None:
        print(
            "   No cache file found for this exact (endpoint, gameCode) key under "
            f"{cache_dir} — real field content at any specific time cannot be determined from this "
            "evidence source. (Cleared, never fetched under this cache dir, or fetched with different params.)"
        )
    else:
        print(f"   cache file: {entry_cache['path']}")
        print(
            f"   file mtime (UTC): {entry_cache['mtime_utc']} — most recent REAL fetch time for the "
            "content currently on disk (a cache hit never rewrites this file, so this is not necessarily "
            "the very first-ever fetch — see module docstring caveat)."
        )
        print(f"   PRE snapshot created_at_utc: {pre_snapshot.created_at_utc!r}")
        if real_field_codes is not None:
            print(f"   real parsed player_code count in this cached page: {len(real_field_codes)}")
            print(f"   {args.player_code} present in this real cached field: {args.player_code in real_field_codes}")
        else:
            print("   cached body_text missing/empty — could not parse a real player_code set from it.")
    print()
    print(f"5. tournament_entry (ENTRY_FIELD) TODAY: in_field={in_entry_field_today}, "
          f"collected_at={entry_collected_at!r}")
    print(
        "   CAVEAT (confirmed by reading klpga.db.upsert._upsert + scripts/15_collect_entry_list.py): "
        "collected_at is OVERWRITTEN with the current wall-clock time on every collection run regardless "
        "of whether the underlying HTTP fetch was a real fetch or a cache hit — it reflects 'last touched "
        "by any run', NOT 'first seen in the real field'. Not used alone to time this player's real "
        "first appearance; see item 4 for the more reliable real-fetch-mtime evidence."
    )
    print()

    replaced_candidates = sorted(pre_field_codes - real_field_codes) if real_field_codes is not None else None
    newly_in_real_field = sorted(real_field_codes - pre_field_codes) if real_field_codes is not None else None
    print("6. PRE field (120) vs real cached entry-list field — set differences:")
    if real_field_codes is None:
        print("   UNKNOWN — no real cached entry-list field set available (see item 4).")
    else:
        print(f"   in PRE but NOT in real cached field (candidate replaced/removed players): {replaced_candidates}")
        print(f"   in real cached field but NOT in PRE: {newly_in_real_field}")
        for code in (replaced_candidates or []):
            print(f"     - {code}: PRE field player_name={pre_names_by_code.get(code)!r}")
    print()

    # --- root cause, evidence-only ---
    root_cause = ROOT_CAUSE_UNRESOLVED
    root_cause_detail = "No entry-list cache file found — real field content at PRE-generation time is undetermined."
    if entry_cache is not None:
        if entry_cache["mtime_utc"] > pre_snapshot.created_at_utc:
            root_cause = ROOT_CAUSE_LATE_ENTRY
            root_cause_detail = (
                f"Cached entry-list content (mtime {entry_cache['mtime_utc']}) is NEWER than PRE's "
                f"created_at_utc ({pre_snapshot.created_at_utc!r}) — consistent with a real late field "
                "addition captured by a later real fetch, not a code defect. Cannot fully rule out that "
                "an EARLIER real fetch (now overwritten in cache) already had this player, since a cache "
                "HIT never rewrites the file and no earlier fetch's content survives to check."
            )
        else:
            root_cause = ROOT_CAUSE_COLLECTOR_OMISSION
            root_cause_detail = (
                f"Cached entry-list content (mtime {entry_cache['mtime_utc']}) is AT/BEFORE PRE's "
                f"created_at_utc ({pre_snapshot.created_at_utc!r}) — the real field data available to the "
                "system before/at PRE generation already included this player, yet PRE's own 120-player "
                "field excluded them. This is a real code-defect candidate in PRE's own field-selection "
                "logic, not a data-timing explanation."
            )

    arithmetic_note = (
        "This investigation does not by itself confirm the 115->116 arithmetic total — see "
        "scripts/45_audit_beta001c_r1.py's own ARITHMETIC CHECK section for that separate computation."
    )

    print("=== VERDICT ===")
    print()
    print(f"{args.player_code} ROOT CAUSE: {root_cause} — {root_cause_detail}")
    if replaced_candidates is None:
        print("PLAYER REPLACED/DIFFERENCE: UNKNOWN — no real cached entry-list field set available.")
    elif len(replaced_candidates) == 1:
        code = replaced_candidates[0]
        print(
            f"PLAYER REPLACED/DIFFERENCE: {code} ({pre_names_by_code.get(code)!r}) is in PRE's 120 but "
            f"NOT in the real cached entry-list field — a 1-for-1 candidate substitution with "
            f"{args.player_code}, though this does not by itself prove causation, only co-occurrence."
        )
    elif len(replaced_candidates) == 0:
        print(
            "PLAYER REPLACED/DIFFERENCE: NONE — every PRE-field code is also present in the real cached "
            f"entry-list field; {args.player_code}'s addition does not correspond to any single removed "
            "player (field size may have simply grown, or PRE's own selection independently omitted them)."
        )
    else:
        print(
            f"PLAYER REPLACED/DIFFERENCE: {len(replaced_candidates)} candidates ({replaced_candidates}) — "
            "NOT a single unambiguous replacement; more than one PRE-field code is absent from the real "
            "cached field."
        )
    print(
        "EVIDENCE TIMELINE: PRE created_at_utc="
        f"{pre_snapshot.created_at_utc!r}"
        + (f" -> entry-list cache mtime_utc={entry_cache['mtime_utc']!r}" if entry_cache is not None else " -> entry-list cache: not found")
        + f" -> tournament_entry.collected_at (unreliable, see item 5 caveat)={entry_collected_at!r}."
    )
    print(f"({arithmetic_note})")
    safe_to_close = root_cause == ROOT_CAUSE_LATE_ENTRY and (replaced_candidates is not None)
    print(f"R1 AUDIT SAFE TO CLOSE: {'YES' if safe_to_close else 'NO'}")
    if not safe_to_close:
        print(
            "  (NO unless root cause is LATE_ENTRY with a real cached-field comparison available — arithmetic "
            "consistency alone is never sufficient to close a FAIL verdict.)"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
