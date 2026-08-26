"""Round 10 continued — the bounded missing-evidence request-plan and
live-fire acquisition logic, extracted from
`scripts/32_bounded_missing_evidence_request_plan.py` (Round 11) so
`scripts/run_klpga_collector.py`'s local-collector orchestrator can
reuse the EXACT same, already-tested request/parse/skip/hard-stop
logic instead of duplicating it — the same "extract shared logic into
`src/klpga/discovery/`, keep the script a thin CLI wrapper" pattern
this project already used for `record_fetch.py` (extracted from
scripts/27 for scripts/29's reuse). Behavior is UNCHANGED from the
original script-local version; `scripts/32` re-exports every name
below so its own existing tests continue to pass without modification.

Scope, unchanged from Round 10: ONLY the `identity_key` groups
`klpga.discovery.identity_key_audit.audit_identity_key_collisions`
classifies as `UNRESOLVED_INSUFFICIENT_EVIDENCE` right now — derived
fresh from the audit every call, never hardcoded, never assumed.
Every `PARTIAL_MATCH_NEEDS_REVIEW`/`D_UNRESOLVED`/already-resolved
group is excluded by construction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from klpga import config
from klpga.discovery.canonical_plan import build_canonical_plan
from klpga.discovery.identity_key_audit import (
    CATEGORY_INSUFFICIENT_EVIDENCE,
    CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW,
    CATEGORY_UNRESOLVED,
    audit_identity_key_collisions,
)
from klpga.discovery.record_fetch import fetch_and_analyze, request_form, sanitize_identity_key_for_filename
from klpga.discovery.sampler import _canonical_entry_to_leaf_dict, _leaf_from_dict
from klpga.http_client import RateLimitBlockedError

EXIT_HARD_STOP = 4
"""Mirrors scripts/29's EXIT_BLOCKED=4 — a 401/403/429 hard stop is not
a script bug, but it is not a clean completion either: the caller
should notice."""

_UNRESOLVED_AUDIT_CATEGORIES = frozenset(
    {CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW, CATEGORY_UNRESOLVED, CATEGORY_INSUFFICIENT_EVIDENCE}
)


def build_missing_evidence_request_plan(
    taxonomy: dict, *, season: str, raw_samples_dir: Path
) -> list[dict]:
    """Returns one row per `UNRESOLVED_INSUFFICIENT_EVIDENCE`
    `request_identity_key`, sorted for determinism. Every field is
    derived from evidence/logic that already exists elsewhere in this
    project (`build_canonical_plan`, `audit_identity_key_collisions`,
    `request_form`, `sanitize_identity_key_for_filename`) — nothing
    new is invented here."""
    counts, plan = build_canonical_plan(taxonomy)
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=raw_samples_dir, season=season)
    missing = [a for a in audits if a.category == CATEGORY_INSUFFICIENT_EVIDENCE]
    missing_keys = sorted(a.request_identity_key for a in missing)

    by_key: dict[str, dict] = {}
    for entry in plan:
        by_key.setdefault(entry["identity_key"], entry)

    rows: list[dict] = []
    for key in missing_keys:
        entry = by_key.get(key)
        if entry is None:
            # Should not happen — every audited identity_key comes
            # directly from this same canonical plan — but never
            # silently skip a real inconsistency.
            rows.append(
                {
                    "identity_key": key,
                    "menu1": None,
                    "menu2": None,
                    "menu3": None,
                    "season": season,
                    "expected_raw_sample_path": None,
                    "raw_sample_exists": None,
                    "warning": "No matching canonical plan entry found for this identity_key.",
                }
            )
            continue
        leaf = _leaf_from_dict(_canonical_entry_to_leaf_dict(entry))
        form = request_form(leaf, season)
        raw_path = raw_samples_dir / f"{sanitize_identity_key_for_filename(key)}__{season}.html"
        rows.append(
            {
                "identity_key": key,
                "menu1": form.get("menu1"),
                "menu2": form.get("menu2"),
                "menu3": form.get("menu3"),
                "season": form.get("season"),
                "expected_raw_sample_path": str(raw_path),
                "raw_sample_exists": raw_path.exists(),
                "warning": None,
            }
        )
    return rows


def _category_counts(audits: list) -> dict:
    """Tallies one audit run's `GroupAudit.category` values, plus a
    `total_unresolved` (PARTIAL + D_UNRESOLVED + INSUFFICIENT_EVIDENCE
    — matching scripts/31's own SUMMARY definition exactly, so a
    BEFORE/AFTER comparison here means the same thing it does there)
    and `total_groups`. Never forces any count to zero — this is a
    plain tally of whatever the audit actually returned."""
    counts: dict[str, int] = {}
    for a in audits:
        counts[a.category] = counts.get(a.category, 0) + 1
    counts["total_unresolved"] = sum(counts.get(c, 0) for c in _UNRESOLVED_AUDIT_CATEGORIES)
    counts["total_groups"] = len(audits)
    return counts


_CACHE_LIVE_SHORT_LABELS = {"CACHE_HIT": "CACHE", "LIVE_FETCH": "LIVE", "NOT_AVAILABLE": "N/A"}


def _progress_line(
    i: int, total: int, identity_key: str, cache_live: str, http_status: str, parse_status: str, saved_status: str
) -> str:
    """One line per identity, in the exact column order this project's
    local-collector observability requirement specifies: `PROGRESS
    [completed/expected] | identity_key | CACHE/LIVE | HTTP status |
    PARSE status | SAVED/SKIPPED`. Pure formatting over values already
    computed by the caller — never a new lookup, never a behavior
    change to what gets requested or how."""
    cache_live_short = _CACHE_LIVE_SHORT_LABELS.get(cache_live, cache_live)
    return (
        f"PROGRESS [{i}/{total}] | {identity_key} | {cache_live_short} | {http_status} | "
        f"{parse_status} | {saved_status}"
    )


def _cache_live_distinction(client, leaf, season: str) -> str:
    """Best-effort, NEVER guessed: "CACHE_HIT" if `PoliteHttpClient`'s
    own disk cache already held this exact request's response before
    this run touched it, "LIVE_FETCH" if not, "NOT_AVAILABLE" if this
    cannot be determined at all (e.g. a test double that doesn't
    expose the same cache internals, or any other lookup failure) —
    per explicit instruction, an undeterminable distinction is reported
    honestly rather than guessed either way."""
    try:
        form = request_form(leaf, season)
        cache_path = client._cache_path(config.RECORD_TAXONOMY_ENDPOINT, {"data": form})
        return "CACHE_HIT" if cache_path.exists() else "LIVE_FETCH"
    except Exception:  # noqa: BLE001 — genuinely any lookup failure means "cannot determine", not a bug.
        return "NOT_AVAILABLE"


def acquire_missing_evidence(
    client, taxonomy: dict, season: str, raw_samples_dir: Path, *, log: Callable[[str], None] = print
) -> dict:
    """Live-fire acquisition. Makes a real HTTP request (via `client` —
    a `PoliteHttpClient` or, in tests, a compatible fake) for EVERY
    identity_key `build_missing_evidence_request_plan` currently lists
    — i.e. every `UNRESOLVED_INSUFFICIENT_EVIDENCE` group, derived
    fresh right now — and only those. Never touches a `PARTIAL_MATCH_
    NEEDS_REVIEW`/`D_UNRESOLVED`/already-resolved group; never fires a
    request for an identity whose expected raw-sample file already
    exists (re-checked immediately before each request, not just once
    at plan-build time).

    A per-item HTTP failure (exhausted retries on a 5xx/timeout, etc.)
    is a LOCAL blocker: recorded in `items` with `http_outcome=
    "HTTP_FAILURE"`, and acquisition continues to the next identity. A
    `RateLimitBlockedError` (401/403/429) is a HARD safety blocker: it
    halts every further live request for the REMAINDER of this run
    (never retried, never bypassed) — every identity not yet attempted
    is recorded in `skipped` with a reason naming the hard stop, and
    this function still returns a full, valid report of whatever was
    collected before it. Never raises.

    Reruns `audit_identity_key_collisions` twice — once before any
    request (to capture the true BEFORE baseline) and once after
    acquisition (or the hard stop) completes — and returns both as
    plain category-count dicts, never forcing a category to zero."""
    audits_before = audit_identity_key_collisions(taxonomy, raw_samples_dir=raw_samples_dir, season=season)
    before_counts = _category_counts(audits_before)

    rows = build_missing_evidence_request_plan(taxonomy, season=season, raw_samples_dir=raw_samples_dir)
    core = acquire_canonical_rows(client, taxonomy, rows, season, raw_samples_dir, log=log)

    audits_after = audit_identity_key_collisions(taxonomy, raw_samples_dir=raw_samples_dir, season=season)
    after_counts = _category_counts(audits_after)

    return {
        "expected_missing_evidence_identities": len(rows),
        "processed": len(core["items"]) + len(core["skipped"]),
        "items": core["items"],
        "skipped": core["skipped"],
        "hard_stop": core["hard_stop"],
        "before_counts": before_counts,
        "after_counts": after_counts,
    }


def acquire_canonical_rows(
    client, taxonomy: dict, rows: list[dict], season: str, raw_samples_dir: Path, *, log: Callable[[str], None] = print
) -> dict:
    """The shared acquisition CORE `acquire_missing_evidence` (above)
    and `season_metric_collector.acquire_season_metrics` both call —
    fires one request per row in `rows` (any list matching `build_
    missing_evidence_request_plan`'s row shape: `identity_key`/`menu1`/
    `menu2`/`menu3`/`season`/`expected_raw_sample_path`/`raw_sample_
    exists`/`warning`) not already evidenced on disk, with the EXACT
    same hard-stop/per-item-failure/skip/PROGRESS-line behavior
    documented on `acquire_missing_evidence` above — this function IS
    that behavior; `acquire_missing_evidence` only adds the before/
    after collision-audit wrapping and its own `UNRESOLVED_
    INSUFFICIENT_EVIDENCE`-only row source on top of it. Returns
    `{"items": [...], "skipped": [...], "hard_stop": dict|None}` —
    never raises."""
    _counts, plan = build_canonical_plan(taxonomy)
    by_key: dict[str, dict] = {}
    for entry in plan:
        by_key.setdefault(entry["identity_key"], entry)

    items: list[dict] = []
    skipped: list[dict] = []
    hard_stop: dict | None = None

    for i, row in enumerate(rows, start=1):
        identity_key = row["identity_key"]
        expected_path = Path(row["expected_raw_sample_path"]) if row["expected_raw_sample_path"] else None

        if hard_stop is not None:
            skipped.append(
                {
                    "identity_key": identity_key,
                    "stage": "acquisition",
                    "reason": (
                        f"not attempted — a hard safety stop already occurred this run on "
                        f"{hard_stop['identity_key']}"
                    ),
                }
            )
            log(_progress_line(i, len(rows), identity_key, "NOT_AVAILABLE", "NOT_ATTEMPTED", "N/A", "SKIPPED"))
            continue

        entry = by_key.get(identity_key)
        if entry is None:
            skipped.append(
                {
                    "identity_key": identity_key,
                    "stage": "plan_lookup",
                    "reason": row.get("warning") or "no matching canonical plan entry found",
                }
            )
            log(_progress_line(i, len(rows), identity_key, "NOT_AVAILABLE", "NOT_ATTEMPTED", "N/A", "SKIPPED"))
            continue

        if expected_path is not None and expected_path.exists():
            skipped.append(
                {
                    "identity_key": identity_key,
                    "stage": "pre_request_check",
                    "reason": (
                        "a raw sample already exists at the expected path — outside this run's "
                        "scope, never overwritten, never requested"
                    ),
                }
            )
            log(_progress_line(i, len(rows), identity_key, "NOT_AVAILABLE", "NOT_ATTEMPTED", "N/A", "SKIPPED"))
            continue

        leaf = _leaf_from_dict(_canonical_entry_to_leaf_dict(entry))
        cache_live = _cache_live_distinction(client, leaf, season)
        attempt_timestamp = datetime.now(timezone.utc).isoformat()

        try:
            parsed, analysis, _log_entry = fetch_and_analyze(
                client, leaf, season, tag=f"{i}/{len(rows)}", raw_dir=raw_samples_dir, log=log
            )
        except RateLimitBlockedError as exc:
            hard_stop = {"identity_key": identity_key, "error": str(exc), "timestamp": attempt_timestamp}
            log(f"HARD STOP on {identity_key}: {exc} — not retrying, not bypassing, halting further live requests this run.")
            skipped.append(
                {"identity_key": identity_key, "stage": "acquisition", "reason": f"hard safety stop: {exc}"}
            )
            log(_progress_line(i, len(rows), identity_key, cache_live, "BLOCKED", "N/A", "SKIPPED"))
            continue
        except Exception as exc:  # noqa: BLE001 — a per-item HTTP failure must not abort the whole run.
            log(f"HTTP_FAILURE for {identity_key}: {exc}")
            log(_progress_line(i, len(rows), identity_key, cache_live, "FAILURE", "N/A", "SKIPPED"))
            items.append(
                {
                    "identity_key": identity_key,
                    "menu1": entry.get("menu1"),
                    "menu2": entry.get("menu2"),
                    "menu3": entry.get("menu3"),
                    "season": season,
                    "cache_live_distinction": cache_live,
                    "http_outcome": "HTTP_FAILURE",
                    "error": str(exc),
                    "raw_sample_path": None,
                    "response_size": None,
                    "timestamp": attempt_timestamp,
                    "parse_status": None,
                    "player_row_count": None,
                    "schema_fingerprint": None,
                    "missing_player_code": None,
                    "missing_player_name": None,
                    "blank_values": None,
                    "non_numeric_numeric_fields": None,
                    "duplicate_player_rows": None,
                    "data_quality_any_flagged": None,
                }
            )
            continue

        dq = analysis.data_quality
        response_size = expected_path.stat().st_size if expected_path is not None and expected_path.exists() else None
        items.append(
            {
                "identity_key": identity_key,
                "menu1": entry.get("menu1"),
                "menu2": entry.get("menu2"),
                "menu3": entry.get("menu3"),
                "season": season,
                "cache_live_distinction": cache_live,
                "http_outcome": "HTTP_SUCCESS",
                "error": None,
                "raw_sample_path": str(expected_path) if expected_path is not None else None,
                "response_size": response_size,
                "timestamp": attempt_timestamp,
                "parse_status": parsed.parse_status,
                "player_row_count": len(parsed.rows),
                "schema_fingerprint": analysis.schema_fingerprint,
                "missing_player_code": dq.missing_player_code,
                "missing_player_name": dq.missing_player_name,
                "blank_values": dq.blank_values,
                "non_numeric_numeric_fields": dq.non_numeric_numeric_fields,
                "duplicate_player_rows": dq.duplicate_player_rows,
                "data_quality_any_flagged": dq.any_flagged,
            }
        )
        log(_progress_line(i, len(rows), identity_key, cache_live, "SUCCESS", parsed.parse_status, "SAVED"))

    return {"items": items, "skipped": skipped, "hard_stop": hard_stop}
