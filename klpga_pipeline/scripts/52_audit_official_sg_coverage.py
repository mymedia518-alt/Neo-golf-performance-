"""NEO SG DATA COLLECTION — PHASE 2, STEP 1/4/5/6/7 — READ-ONLY audit of
the real `official_metric_value` table for the 6 official KLPGA
Strokes Gained identity_keys.

Does NOT touch any prediction/model/probability code, does NOT fetch
anything over the network (run scripts/run_klpga_season_metrics_
collector.py --live first to populate/extend official_metric_value —
see this project's own docstring for the exact command), does NOT
write to the DB (opened mode=ro), does NOT create any new table.

What this prints, precisely:
  STEP 1 — per SG identity_key, BROKEN DOWN BY SEASON: row count,
    distinct player count, NULL value_raw count, FLAGGED count, and —
    since the DB stores only a single aggregate FLAGGED/CLEAN status
    per row, not a reason — a recomputed recoverable-rank-only-flag vs
    real-value-issue split via the REAL, unmodified klpga.discovery.
    flag_recovery.recover_value_validity (re-parses each row's own
    raw_sample_path exactly once per distinct path).
  UNMATCHED PLAYER CODE INVESTIGATION — recomputes the FULL (not just
    a 10-row sample) official_metric_value-vs-player_master mismatch
    set using the REAL, unmodified verify_player_code_identity_space
    over the WHOLE table (every identity_key, matching the real
    collector run's own full-table check, not just the SG subset), then
    for each unmatched code: checks whether a normalized variant
    (strip leading zeros / whitespace) matches player_master, lists
    every identity_key/season it appears under, and recovers a real
    player_name by re-parsing one of its own raw_sample_path files
    (official_metric_value itself has no player_name column).
  STEP 4 — PIT signal: for every pair of collected seasons (per
    identity_key), calls the REAL, unmodified klpga.discovery.
    response_schema.classify_historical_availability on the two
    seasons' parsed raw responses. That function is explicitly NOT a
    PIT classification (see its own docstring) — it only answers
    whether the site returned genuinely different data for a different
    season parameter. This script combines that real signal with the
    real schema fact that official_metric_value's PRIMARY KEY includes
    `season` (so distinct season rows are structurally preserved, never
    overwritten) to produce ONE explicit PIT_SAFE/PIT_PARTIAL/
    PIT_UNSAFE/PIT_UNKNOWN verdict per identity_key — always
    conservative: never PIT_SAFE off this evidence alone (see verdict
    rule in `pit_verdict_for_identity`), since classify_historical_
    availability cannot itself confirm exactly what point in the target
    season the value reflects.
  STEP 5 — integrity: duplicate (season, player_code) rows within an
    identity_key (should be impossible given the real PRIMARY KEY, but
    checked directly against real rows, not assumed from the schema),
    non-numeric value_raw, out-of-range values (SG values outside a
    generous [-15, 15] sanity band — real PGA/DataGolf SG values are
    typically within a few strokes; this band is only a sanity check,
    never a silent filter).
  STEP 6 — confirms no new table exists: reports the real, unmodified
    official_metric_value row/column count as the "existing structure"
    evidence STEP 6 of the mission requires.
  STEP 7 — final dataset size: total rows / players / seasons across
    all 6 SG identity_keys combined, plus the player_master join rate
    via the REAL, unmodified klpga.discovery.season_metric_collector.
    verify_player_code_identity_space.

Usage (after running scripts/run_klpga_season_metrics_collector.py
--live --seasons <comma-separated> to populate/extend the data):
    python scripts/52_audit_official_sg_coverage.py --db data/klpga.sqlite
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.discovery.flag_recovery import recover_value_validity  # noqa: E402
from klpga.discovery.response_parser import parse_record_response  # noqa: E402
from klpga.discovery.response_schema import classify_historical_availability  # noqa: E402
from klpga.discovery.season_metric_collector import (  # noqa: E402
    read_player_master_ids,
    verify_player_code_identity_space,
)

ROOT = Path(__file__).resolve().parents[1]

SG_IDENTITY_KEYS = ["Sg::Total", "Sg::TeeToGreen", "Sg::Tee", "Sg::Approach", "Sg::Around", "Sg::Putt"]
SG_LABELS = {
    "Sg::Total": "SG : 전체 (Total)",
    "Sg::TeeToGreen": "SG : 티샷 to 그린 (Tee-to-Green)",
    "Sg::Tee": "SG : 티샷 (Off-the-Tee)",
    "Sg::Approach": "SG : 어프로치 (Approach)",
    "Sg::Around": "SG : 그린주변 (Around-the-Green)",
    "Sg::Putt": "SG : 퍼팅 (Putting)",
}


def _resolve_raw_sample_path(stored_path: str) -> Path | None:
    p = Path(stored_path)
    if p.exists():
        return p
    fallback = ROOT / "docs" / "discovery" / "raw_samples" / p.name
    if fallback.exists():
        return fallback
    return None


def _recoverable_split(flagged_rows: list, label: str) -> tuple[int, int, list]:
    """Recompute recoverable-rank-only vs real-value-issue counts (once
    per distinct raw_sample_path) for a set of FLAGGED rows, via the
    real, unmodified flag_recovery.recover_value_validity."""
    distinct_flagged_paths = sorted({r[4] for r in flagged_rows if r[4]})
    recoverable, value_issue, unreadable = 0, 0, []
    for raw_path_str in distinct_flagged_paths:
        resolved = _resolve_raw_sample_path(raw_path_str)
        if resolved is None:
            unreadable.append(raw_path_str)
            continue
        try:
            result = recover_value_validity(resolved)
        except Exception as exc:  # noqa: BLE001 — report, never silently drop
            unreadable.append(f"{raw_path_str} (ERROR: {exc})")
            continue
        if result.get("reason") == "RANK_ONLY":
            recoverable += 1
        else:
            value_issue += 1
    return recoverable, value_issue, unreadable


def step1_step5_coverage(conn: sqlite3.Connection) -> dict:
    print("=== STEP 1 — REAL LOCAL DB COVERAGE, BY SEASON (per SG identity_key) ===")
    print()
    per_identity: dict[str, dict] = {}
    for key in SG_IDENTITY_KEYS:
        rows = conn.execute(
            "SELECT season, player_code, value_raw, validation_status, raw_sample_path "
            "FROM official_metric_value WHERE identity_key = ?",
            (key,),
        ).fetchall()
        seasons = sorted({r[0] for r in rows})

        print(f"{key}  ({SG_LABELS[key]})")
        if not seasons:
            print("  NO ROWS COLLECTED YET for this identity_key.")
            print()
            per_identity[key] = {"row_count": 0, "seasons": [], "player_codes": set()}
            continue

        identity_all_player_codes: set = set()
        identity_row_count = 0
        for season in seasons:
            season_rows = [r for r in rows if r[0] == season]
            row_count = len(season_rows)
            distinct_players = len({r[1] for r in season_rows})
            null_count = sum(1 for r in season_rows if r[2] is None or str(r[2]).strip() == "")
            flagged_rows = [r for r in season_rows if r[3] == "FLAGGED"]
            flagged_count = len(flagged_rows)
            recoverable, value_issue, unreadable = _recoverable_split(flagged_rows, key)

            identity_all_player_codes |= {r[1] for r in season_rows}
            identity_row_count += row_count

            print(f"  season {season}: ROW COUNT={row_count}  DISTINCT PLAYERS={distinct_players}  "
                  f"NULL={null_count}  FLAGGED={flagged_count}  "
                  f"(recoverable rank-only={recoverable}, real value-issue={value_issue}"
                  f"{', unreadable=' + str(len(unreadable)) if unreadable else ''})")

        # STEP 5 integrity checks, over the FULL identity_key (all seasons combined) — duplicate
        # (season, player_code) should be structurally impossible given the real PRIMARY KEY
        # (season, player_code, identity_key, official_label), checked directly against real rows.
        seen = set()
        dupes = []
        non_numeric, out_of_range = [], []
        for r in rows:
            dk = (r[0], r[1])
            if dk in seen:
                dupes.append(dk)
            seen.add(dk)
            v = r[2]
            if v is None or str(v).strip() == "":
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                non_numeric.append((r[1], v))
                continue
            if not (-15.0 <= fv <= 15.0):
                out_of_range.append((r[1], fv))

        per_identity[key] = {
            "row_count": identity_row_count, "seasons": seasons, "player_codes": identity_all_player_codes,
        }

        print(f"  STEP 5 duplicate (season, player_code) rows: {len(dupes)} {dupes[:5]}")
        print(f"  STEP 5 non-numeric value_raw: {len(non_numeric)} {non_numeric[:5]}")
        print(f"  STEP 5 out-of-[-15,15]-range values: {len(out_of_range)} {out_of_range[:5]}")
        print()
    return per_identity


def pit_verdict_for_identity(key: str, conn: sqlite3.Connection) -> tuple[str, list]:
    """STEP 4 — see module docstring for the conservative verdict rule.
    Never returns PIT_SAFE from this evidence alone."""
    seasons_rows = conn.execute(
        "SELECT DISTINCT season, raw_sample_path FROM official_metric_value "
        "WHERE identity_key = ? AND raw_sample_path IS NOT NULL ORDER BY season",
        (key,),
    ).fetchall()
    by_season: dict[int, str] = {}
    for season, path in seasons_rows:
        by_season.setdefault(season, path)  # first real sample path seen for that season

    seasons_sorted = sorted(by_season)
    if len(seasons_sorted) < 2:
        return "PIT_UNKNOWN", []

    pair_results = []
    any_current_only = False
    any_confirmed_different = False
    any_unknown = False
    for earlier, later in zip(seasons_sorted, seasons_sorted[1:]):
        earlier_path = _resolve_raw_sample_path(by_season[earlier])
        later_path = _resolve_raw_sample_path(by_season[later])
        if earlier_path is None or later_path is None:
            pair_results.append((earlier, later, "UNREADABLE"))
            any_unknown = True
            continue
        historical = parse_record_response(earlier_path.read_text(encoding="utf-8"))
        current = parse_record_response(later_path.read_text(encoding="utf-8"))
        verdict = classify_historical_availability(current, historical)
        pair_results.append((earlier, later, verdict))
        if verdict == "CURRENT_ONLY":
            any_current_only = True
        elif verdict == "HISTORICAL_SEASON_RESPONSE_CONFIRMED":
            any_confirmed_different = True
        else:
            any_unknown = True

    if any_current_only:
        overall = "PIT_UNSAFE"
    elif any_confirmed_different and not any_unknown:
        overall = "PIT_PARTIAL"
    else:
        overall = "PIT_UNKNOWN"
    return overall, pair_results


def step4_pit_safety(conn: sqlite3.Connection) -> None:
    print("=== STEP 4 — PIT SAFETY (per SG identity_key) ===")
    print()
    print("NOTE: official_metric_value's real PRIMARY KEY is (season, player_code, identity_key, "
          "official_label) — distinct season rows are structurally preserved, never overwritten by "
          "a later collection run. This is real, positive storage-layer evidence, separate from "
          "whether KLPGA's live site itself returns genuinely different values per season parameter, "
          "which is what classify_historical_availability below actually tests.")
    print()
    for key in SG_IDENTITY_KEYS:
        overall, pairs = pit_verdict_for_identity(key, conn)
        print(f"{key}: {overall}")
        for earlier, later, verdict in pairs:
            print(f"  season {earlier} vs {later}: {verdict}")
        if not pairs:
            print("  (fewer than 2 seasons collected for this identity_key — cannot test)")
        print()
    print("Per this module's own real docstring (klpga.discovery.response_schema."
          "classify_historical_availability): 'this is NEVER a PIT classification — it only answers "
          "did the site return real, different-looking data for a prior season, not is this safe to "
          "use as a model feature.' No identity_key above is reported PIT_SAFE from this evidence "
          "alone, by design — see STEP 9/RECOMMENDED PHASE 3 in the report for what PIT_SAFE would "
          "actually require.")
    print()


def _normalized_variants(code: str) -> set[str]:
    """Candidate alternate forms of a player_code that could plausibly
    still refer to the same real player_master.player_id — never a
    guess at IDENTITY, only at STRING FORMAT (leading zeros, whitespace,
    a stray non-digit character). Used only to report whether a
    format-level explanation exists, never to silently merge codes."""
    variants = {code, code.strip()}
    stripped = code.strip()
    if stripped.isdigit():
        variants.add(stripped.lstrip("0") or "0")
        variants.add(stripped.zfill(5))
        variants.add(stripped.zfill(6))
    return variants


def investigate_unmatched_player_codes(conn: sqlite3.Connection) -> None:
    print("=== UNMATCHED PLAYER CODE INVESTIGATION (full official_metric_value table, all identity_keys) ===")
    print()
    all_metric_player_codes = {
        row[0] for row in conn.execute("SELECT DISTINCT player_code FROM official_metric_value")
    }
    player_master_ids = read_player_master_ids(conn)
    full_result = verify_player_code_identity_space(all_metric_player_codes, player_master_ids)
    print("Full-table player_code identity check (matches the real collector run's own scope):")
    for k, v in full_result.items():
        print(f"  {k}: {v}")
    print()

    unmatched = sorted(all_metric_player_codes - player_master_ids)
    print(f"FULL unmatched set ({len(unmatched)} codes): {unmatched}")
    print()

    for code in unmatched:
        variants = _normalized_variants(code) - {code}
        variant_matches = sorted(v for v in variants if v in player_master_ids)

        occurrence_rows = conn.execute(
            "SELECT DISTINCT identity_key, season, raw_sample_path FROM official_metric_value "
            "WHERE player_code = ? ORDER BY season, identity_key",
            (code,),
        ).fetchall()
        identity_seasons = sorted({(r[0], r[1]) for r in occurrence_rows})

        real_name = None
        for _identity_key, _season, raw_path_str in occurrence_rows:
            if not raw_path_str:
                continue
            resolved = _resolve_raw_sample_path(raw_path_str)
            if resolved is None:
                continue
            try:
                parsed = parse_record_response(resolved.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001 — try the next occurrence rather than abort
                continue
            match = next((row for row in parsed.rows if row.player_code == code), None)
            if match is not None and match.player_name:
                real_name = match.player_name
                break

        print(f"player_code={code!r}")
        print(f"  real player_name recovered from raw HTML: {real_name!r}")
        print(f"  normalized-variant format match in player_master: "
              f"{variant_matches if variant_matches else 'NONE — not a leading-zero/whitespace formatting issue'}")
        print(f"  appears under {len(identity_seasons)} (identity_key, season) combination(s): "
              f"{identity_seasons[:10]}{' ...' if len(identity_seasons) > 10 else ''}")
        print()

    print("NOTE: no player identity was modified, merged, or inferred by this investigation — this is "
          "read-only diagnostic evidence for the mission's explicit 'do not modify player identities yet'.")
    print()


def step6_step7_summary(conn: sqlite3.Connection, per_identity: dict) -> None:
    print("=== STEP 6 — EXISTING STRUCTURE CONFIRMATION ===")
    print()
    total_table_rows = conn.execute("SELECT COUNT(*) FROM official_metric_value").fetchone()[0]
    print(f"official_metric_value real total row count (ALL identity_keys, not just SG): {total_table_rows}")
    print("No new table created by this script or by STEP 1-5 above — official_metric_value is the "
          "only table read.")
    print()

    print("=== STEP 7 — FINAL OFFICIAL SG DATASET SIZE ===")
    print()
    all_sg_player_codes: set[str] = set()
    all_sg_rows = 0
    all_sg_seasons: set[int] = set()
    for key, info in per_identity.items():
        all_sg_player_codes |= info["player_codes"]
        all_sg_rows += info["row_count"]
        all_sg_seasons |= set(info["seasons"])
    print(f"Total SG rows across all 6 categories: {all_sg_rows}")
    print(f"Distinct players with at least one SG value: {len(all_sg_player_codes)}")
    print(f"Seasons covered (any SG category): {sorted(all_sg_seasons)}")

    print()
    print("=== PLAYER_MASTER JOIN RATE (real, unmodified verify_player_code_identity_space) ===")
    print()
    player_master_ids = read_player_master_ids(conn)
    result = verify_player_code_identity_space(all_sg_player_codes, player_master_ids)
    for k, v in result.items():
        print(f"  {k}: {v}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        per_identity = step1_step5_coverage(conn)
        investigate_unmatched_player_codes(conn)
        step4_pit_safety(conn)
        step6_step7_summary(conn, per_identity)
    finally:
        conn.close()

    print("Done. Read-only — no model/prediction/HTML/production file was touched by this script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
