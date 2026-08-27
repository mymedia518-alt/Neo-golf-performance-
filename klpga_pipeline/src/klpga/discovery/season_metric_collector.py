"""Round 12 — the season-level official-metrics collector. Acquires
every canonical `(season, identity_key)` combination not yet
evidenced, then ingests the MAPPED subset (per `identity_mapping.py`)
into `official_metric_value` rows. Structurally the generalization of
`missing_evidence_acquisition.py` from "the audit's insufficient-
evidence subset" to "the FULL 248-identity canonical set", reusing its
`acquire_canonical_rows` core unchanged — same `PoliteHttpClient`
rate-limiting/retry/hard-stop, same PROGRESS-line/skip/log behavior.

See `docs/HISTORICAL_METRICS_COLLECTION_DESIGN.md` for the full
architecture rationale (why season-level, not per-tournament; why a
normalized fact table, not ~250 columns) and `docs/KLPGA_OFFICIAL_
DATA_MAP.md` for the evidence log this module builds on.
"""
from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from klpga import config
from klpga.discovery.canonical_plan import build_canonical_plan, check_sanity_invariants
from klpga.discovery.identity_key_audit import audit_identity_key_collisions
from klpga.discovery.identity_mapping import STATUS_MAPPED, build_identity_metric_mapping
from klpga.discovery.missing_evidence_acquisition import acquire_canonical_rows
from klpga.discovery.record_fetch import request_form, sanitize_identity_key_for_filename
from klpga.discovery.response_parser import parse_record_response
from klpga.discovery.response_schema import PIT_STATUS, analyze_response
from klpga.discovery.sampler import _canonical_entry_to_leaf_dict, _leaf_from_dict

_CONFIRMED_UNIT_TOKENS = {"yds", "%"}
"""Deliberately a small, real-evidence whitelist, not a guess: every
trailing-parenthetical annotation this project has directly observed
in a real response that IS a physical unit (`"평균 남은 거리(yds)"`,
`"성공률(%)"`, etc.) — case-folded. A parenthetical that doesn't match
this whitelist (e.g. `"그린 적중률(RTP)"` — RTP is a distinct concept
`response_schema.py` already tracks separately, not a unit) yields
`unit=None` rather than a guessed value."""


def build_season_metric_request_plan(taxonomy: dict, *, season: str, raw_samples_dir: Path) -> list[dict]:
    """One row per UNIQUE canonical identity_key not yet backed by a
    saved raw response for THIS season — the FULL canonical set (248
    unique identities as of the Round 11 rebuild), not just the
    identity-key-collision audit's `UNRESOLVED_INSUFFICIENT_EVIDENCE`
    subset (`missing_evidence_acquisition.build_missing_evidence_
    request_plan` stays scoped to that narrower set, unchanged).
    Same row shape as that function so both can feed `acquire_
    canonical_rows` interchangeably."""
    _counts, plan = build_canonical_plan(taxonomy)
    seen: set[str] = set()
    rows: list[dict] = []
    for entry in plan:
        key = entry["identity_key"]
        if key in seen:
            continue
        seen.add(key)
        leaf = _leaf_from_dict(_canonical_entry_to_leaf_dict(entry))
        form = request_form(leaf, season)
        raw_path = raw_samples_dir / f"{sanitize_identity_key_for_filename(key)}__{season}.html"
        exists = raw_path.exists()
        if exists:
            continue
        rows.append(
            {
                "identity_key": key,
                "menu1": form.get("menu1"),
                "menu2": form.get("menu2"),
                "menu3": form.get("menu3"),
                "season": form.get("season"),
                "expected_raw_sample_path": str(raw_path),
                "raw_sample_exists": exists,
                "warning": None,
            }
        )
    return rows


def acquire_season_metrics(
    client, taxonomy: dict, season: str, raw_samples_dir: Path, *, log: Callable[[str], None] = print
) -> dict:
    """Live-fire acquisition for the FULL canonical set, one season.
    Reuses `acquire_canonical_rows` — identical hard-stop/per-item-
    failure/skip/PROGRESS-line behavior to `missing_evidence_
    acquisition.acquire_missing_evidence`, just over the full 248-
    identity row source instead of the audit's narrower subset."""
    rows = build_season_metric_request_plan(taxonomy, season=season, raw_samples_dir=raw_samples_dir)
    core = acquire_canonical_rows(client, taxonomy, rows, season, raw_samples_dir, log=log)
    return {
        "season": season,
        "expected_identities": len(rows),
        "processed": len(core["items"]) + len(core["skipped"]),
        "items": core["items"],
        "skipped": core["skipped"],
        "hard_stop": core["hard_stop"],
    }


def build_official_metric_value_rows(
    taxonomy: dict, *, season: str, raw_samples_dir: Path
) -> tuple[list[dict], list]:
    """Ingestion step — pure, no DB connection. Reads every raw
    response already on disk (does NOT fire any request), resolves
    each canonical label to a value per player row via `identity_
    mapping.build_identity_metric_mapping`, and returns `(rows,
    mapping)`: `rows` are ready for `ingest_official_metric_value_
    rows`, `mapping` is the full mapping report (including every
    UNMAPPED_* record) so a caller can inspect what was skipped and
    why — never silently dropped.

    A player row with no `player_code` at all is skipped (cannot key
    an `official_metric_value` row without one) — never inserted with
    a fabricated identity."""
    mapping = build_identity_metric_mapping(taxonomy, raw_samples_dir=raw_samples_dir, season=season)
    mapped = [m for m in mapping if m.status == STATUS_MAPPED]

    by_identity: dict[str, list] = {}
    for m in mapped:
        by_identity.setdefault(m.identity_key, []).append(m)

    rows: list[dict] = []
    for identity_key, records in by_identity.items():
        raw_path = Path(records[0].raw_sample_path)
        html = raw_path.read_text(encoding="utf-8")
        parsed = parse_record_response(html)
        analysis = analyze_response(parsed)
        validation_status = "FLAGGED" if analysis.data_quality.any_flagged else "CLEAN"
        acquired_at = datetime.fromtimestamp(raw_path.stat().st_mtime, tz=timezone.utc).isoformat()

        for player_row in parsed.rows:
            if not player_row.player_code:
                continue
            for m in records:
                value_raw = player_row.values.get(m.field_name)
                rows.append(
                    {
                        "season": int(season),
                        "player_code": player_row.player_code,
                        "identity_key": m.identity_key,
                        "menu1": m.menu1,
                        "menu2": m.menu2,
                        "menu3": m.menu3,
                        "official_label": m.label,
                        "field_name": m.field_name,
                        "value_raw": value_raw,
                        "unit": _extract_confirmed_unit(m.response_column_label),
                        "response_column_label": m.response_column_label,
                        "schema_fingerprint": analysis.schema_fingerprint,
                        "parse_status": parsed.parse_status,
                        "validation_status": validation_status,
                        "pit_status": PIT_STATUS,
                        "source_url": config.RECORD_TAXONOMY_ENDPOINT,
                        "raw_sample_path": str(raw_path),
                        "acquired_at": acquired_at,
                    }
                )

    return rows, mapping


def _extract_confirmed_unit(response_column_label: Optional[str]) -> Optional[str]:
    if not response_column_label or "(" not in response_column_label or not response_column_label.endswith(")"):
        return None
    inside = response_column_label[response_column_label.rindex("(") + 1 : -1].strip()
    return inside if inside.lower() in _CONFIRMED_UNIT_TOKENS else None


def ingest_official_metric_value_rows(conn, rows: list[dict]) -> int:
    """Thin upsert loop — one `upsert_official_metric_value` call per
    row, one commit at the end. Returns the row count written."""
    from klpga.db.upsert import upsert_official_metric_value

    for row in rows:
        upsert_official_metric_value(conn, row)
    conn.commit()
    return len(rows)


# ---------------------------------------------------------------
# Player identity verification — schema.sql section 8's own comment is
# explicit that loadLocationRecord's player_code has NEVER been
# independently confirmed to share player_master.player_id's identity
# space. This is a PURE comparison function: it takes two already-
# real sets and reports overlap — it never fabricates either set
# itself. Running it against REAL production data requires a real,
# populated data/klpga.sqlite, which does not exist in this sandbox
# (no production database file has ever been present here) — see the
# LOCAL_EXECUTION_REQUIRED note in docs/HISTORICAL_METRICS_COLLECTION_
# DESIGN.md.
# ---------------------------------------------------------------

STATUS_MATCH_CONFIRMED = "PLAYER_CODE_IDENTITY_CONFIRMED"
STATUS_MATCH_PARTIAL = "PLAYER_CODE_IDENTITY_PARTIAL"
STATUS_MATCH_NONE = "PLAYER_CODE_IDENTITY_NOT_CONFIRMED"
STATUS_MATCH_NO_DATA = "PLAYER_CODE_IDENTITY_NO_DATA"


def verify_player_code_identity_space(
    loadlocationrecord_player_codes: set[str], player_master_player_ids: set[str]
) -> dict:
    """Pure set comparison — both arguments must already be REAL
    values the caller obtained from real evidence (e.g. `extract_
    player_codes_from_raw_samples` below for the first set, a real
    `SELECT player_id FROM player_master` for the second). Never
    infers, samples, or fabricates either set itself.

    `overall_status`:
      `PLAYER_CODE_IDENTITY_NO_DATA`   — either input set is empty;
                                          nothing to compare.
      `PLAYER_CODE_IDENTITY_CONFIRMED` — every loadLocationRecord code
                                          checked is present in
                                          player_master (100% match).
      `PLAYER_CODE_IDENTITY_PARTIAL`   — some, but not all, match.
      `PLAYER_CODE_IDENTITY_NOT_CONFIRMED` — none match at all."""
    if not loadlocationrecord_player_codes or not player_master_player_ids:
        return {
            "overall_status": STATUS_MATCH_NO_DATA,
            "total_loadlocationrecord_codes": len(loadlocationrecord_player_codes),
            "total_player_master_ids": len(player_master_player_ids),
            "matched": 0,
            "unmatched_loadlocationrecord_only": len(loadlocationrecord_player_codes),
            "match_rate": None,
            "sample_unmatched": sorted(loadlocationrecord_player_codes)[:10],
        }

    matched = loadlocationrecord_player_codes & player_master_player_ids
    unmatched = loadlocationrecord_player_codes - player_master_player_ids
    match_rate = len(matched) / len(loadlocationrecord_player_codes)

    if match_rate == 1.0:
        overall = STATUS_MATCH_CONFIRMED
    elif match_rate == 0.0:
        overall = STATUS_MATCH_NONE
    else:
        overall = STATUS_MATCH_PARTIAL

    return {
        "overall_status": overall,
        "total_loadlocationrecord_codes": len(loadlocationrecord_player_codes),
        "total_player_master_ids": len(player_master_player_ids),
        "matched": len(matched),
        "unmatched_loadlocationrecord_only": len(unmatched),
        "match_rate": round(match_rate, 4),
        "sample_unmatched": sorted(unmatched)[:10],
    }


def extract_player_codes_from_raw_samples(raw_samples_dir: Path) -> set[str]:
    """Real player_codes seen across every already-saved raw response
    in `raw_samples_dir` — parses each file with the same, unmodified
    `parse_record_response`. Empty set if the directory has no files
    (never an error)."""
    codes: set[str] = set()
    if not raw_samples_dir.exists():
        return codes
    for path in raw_samples_dir.glob("*.html"):
        parsed = parse_record_response(path.read_text(encoding="utf-8"))
        codes.update(row.player_code for row in parsed.rows if row.player_code)
    return codes


def read_player_master_ids(conn: sqlite3.Connection) -> set[str]:
    """Real `player_master.player_id` values from the production DB —
    a plain read, no join, no assumption that this identity space
    matches `loadLocationRecord`'s `player_code` (schema.sql section 8
    is explicit that this has never been confirmed; that is exactly
    what `verify_player_code_identity_space` checks)."""
    return {row[0] for row in conn.execute("SELECT DISTINCT player_id FROM player_master")}


# ---------------------------------------------------------------
# Season auto-derivation — removes any dependency on a human typing
# season values, and on the external `sqlite3` CLI: uses Python's
# built-in `sqlite3` module directly against the already-collected
# `tournament_master` table (the 100-tournament corpus this project's
# earlier phases already built).
# ---------------------------------------------------------------


def derive_seasons_from_tournament_master(db_path: Path) -> list[int]:
    """Real, distinct `season` values already present in `tournament_
    master` — read-only, stdlib `sqlite3` only (no external CLI
    dependency). Returns an empty list (never a fabricated default
    range) if the table has zero rows."""
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT DISTINCT season FROM tournament_master ORDER BY season").fetchall()
    finally:
        conn.close()
    return [row[0] for row in rows]


# ---------------------------------------------------------------
# Post-acquisition validation — re-runs the two READ-ONLY diagnostics
# this project already relies on (script 28's canonical-plan sanity
# invariants, script 31's identity-key collision audit) so a caller
# never has to shell out to those scripts separately. Pure, no live
# request, no DB write.
# ---------------------------------------------------------------


def build_post_acquisition_validation_report(taxonomy: dict, *, raw_samples_dir: Path, season: str) -> dict:
    """Re-derives the canonical plan and identity-key collision audit
    against whatever evidence is on disk for `season` right now.
    `collision_category_totals` mirrors script 31's own category
    tally — never a new, separately-invented classification."""
    counts, _plan = build_canonical_plan(taxonomy)
    invariant_warnings = check_sanity_invariants(counts)
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=raw_samples_dir, season=season)
    category_totals = Counter(a.category for a in audits)
    return {
        "season": season,
        "canonical_requestable_metric_count": counts.canonical_requestable_metric_count,
        "unique_identity_key_count": counts.unique_identity_key_count,
        "menu3_collision_count": counts.menu3_collision_count,
        "duplicate_identity_key_group_count": counts.duplicate_identity_key_group_count,
        "sanity_invariant_warnings": invariant_warnings,
        "collision_group_count": len(audits),
        "collision_category_totals": dict(sorted(category_totals.items())),
    }


# ---------------------------------------------------------------
# Database completeness check — a plain, read-only tally over
# `official_metric_value` itself (the table this collector writes
# to). Never a claim about coverage of the full 248-identity canonical
# set beyond what is literally counted here.
# ---------------------------------------------------------------


def build_official_metric_value_completeness_report(conn: sqlite3.Connection) -> dict:
    """Real counts from `official_metric_value` — total rows, seasons
    present, distinct identities/players covered, rows with a NULL
    `value_raw` (parsed but empty), and rows `validation_status =
    'FLAGGED'`. Read-only; never mutates the table."""
    total_rows = conn.execute("SELECT COUNT(*) FROM official_metric_value").fetchone()[0]
    seasons = [row[0] for row in conn.execute("SELECT DISTINCT season FROM official_metric_value ORDER BY season")]
    distinct_identities = conn.execute(
        "SELECT COUNT(DISTINCT identity_key) FROM official_metric_value"
    ).fetchone()[0]
    distinct_players = conn.execute("SELECT COUNT(DISTINCT player_code) FROM official_metric_value").fetchone()[0]
    null_value_rows = conn.execute(
        "SELECT COUNT(*) FROM official_metric_value WHERE value_raw IS NULL"
    ).fetchone()[0]
    flagged_rows = conn.execute(
        "SELECT COUNT(*) FROM official_metric_value WHERE validation_status = 'FLAGGED'"
    ).fetchone()[0]
    return {
        "total_rows": total_rows,
        "seasons_present": seasons,
        "distinct_identity_keys_present": distinct_identities,
        "distinct_players_present": distinct_players,
        "null_value_raw_rows": null_value_rows,
        "flagged_rows": flagged_rows,
    }
