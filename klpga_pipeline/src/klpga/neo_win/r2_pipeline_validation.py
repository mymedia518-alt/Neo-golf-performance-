"""BETA #001 R1 -> R2 evaluation pipeline, Section K: hard validation
gate. Every function here is a pure, independently-testable check that
returns {"check": name, "passed": bool, "detail": ...} — never raises,
never silently skips a check. `run_all_validations` is the single
gate the orchestrator (scripts/run_beta001_r2_update.py) must pass
before it is ever allowed to touch the real production docs/index.html
(Section J's STEP9).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

_SHA256_HEX_RE = re.compile(r"[0-9a-fA-F]{64}")
"""Matches a bare SHA-256 hex digest anywhere in a string. Real-world
fix: Windows' `certutil -hashfile <path> SHA256` prints the hash
surrounded by a "SHA256 hash of ..." header line and a "CertUtil:
... completed successfully." footer line — pasting that raw multi-line
output into --r1-html-expected-sha256 would otherwise make this check
report a false mismatch even when the file genuinely never changed.
Extracting the hex substring keeps the check's real guarantee (the
extracted 64 hex characters must still match exactly) while tolerating
that copy-paste noise."""


def check_r1_historical_html_unchanged(r1_html_path: Path, expected_sha256: str) -> dict:
    """The R1 historical snapshot (docs/tournaments/.../r1/index.html)
    must NEVER be modified by this pipeline. `expected_sha256` is the
    hash recorded BEFORE the pipeline ran; this re-hashes the file
    AFTER to prove nothing touched it. Only a real 64-hex-character
    SHA-256 digest found anywhere in `expected_sha256` is compared
    (see _SHA256_HEX_RE) — if none is found at all, that is reported
    as its own distinct failure, never silently treated as a match or
    folded into an ordinary hash-mismatch message."""
    path = Path(r1_html_path)
    if not path.exists():
        return {"check": "R1_HISTORICAL_HTML_UNCHANGED", "passed": False, "detail": f"{path} does not exist"}
    actual = hashlib.sha256(path.read_bytes()).hexdigest()

    match = _SHA256_HEX_RE.search(expected_sha256 or "")
    if match is None:
        return {
            "check": "R1_HISTORICAL_HTML_UNCHANGED",
            "passed": False,
            "detail": (
                f"--r1-html-expected-sha256={expected_sha256!r} contains no real 64-character SHA-256 hex "
                f"value — pass ONLY the hash itself (e.g. from `certutil -hashfile <path> SHA256`, not its "
                f"header/footer lines). actual sha256={actual}"
            ),
        }
    expected_hex = match.group(0).lower()
    return {
        "check": "R1_HISTORICAL_HTML_UNCHANGED",
        "passed": actual == expected_hex,
        "detail": f"expected sha256={expected_hex} actual sha256={actual}",
    }


def check_frozen_r1_values_unchanged(before_rows, after_rows) -> dict:
    """`before_rows`/`after_rows`: list[PlayerR1Frozen] loaded from the
    same frozen source at two different points in the pipeline run —
    must be identical (rank/WIN%/MAKE CUT% never mutate mid-run)."""
    key = lambda r: (r.player_code, r.r1_actual_rank, r.r1_win_probability_pct, r.r1_make_cut_probability_pct)  # noqa: E731
    before = {key(r) for r in before_rows}
    after = {key(r) for r in after_rows}
    return {
        "check": "FROZEN_R1_VALUES_UNCHANGED",
        "passed": before == after,
        "detail": f"{len(before ^ after)} differing (player_code, rank, win_pct, make_cut_pct) tuples",
    }


def check_player_codes_unique(rows) -> dict:
    codes = [r.player_code for r in rows]
    dupes = sorted({c for c in codes if codes.count(c) > 1})
    return {"check": "PLAYER_CODES_UNIQUE", "passed": len(dupes) == 0, "detail": f"duplicates={dupes}"}


def check_no_null_cut_probability_among_evaluated(rows) -> dict:
    evaluated = [r for r in rows if r.actual_cut is not None]
    bad = [r.player_code for r in evaluated if r.r1_make_cut_pct is None]
    return {"check": "NO_NULL_CUT_PROBABILITY_AMONG_EVALUATED", "passed": len(bad) == 0, "detail": f"bad={bad}"}


def check_cut_probability_in_0_100_range(rows) -> dict:
    bad = [r.player_code for r in rows if not (0.0 <= r.r1_make_cut_pct <= 100.0)]
    return {"check": "CUT_PROBABILITY_IN_0_100_RANGE", "passed": len(bad) == 0, "detail": f"bad={bad}"}


def check_win_probability_in_0_100_range(entrants: list[dict]) -> dict:
    bad = [e.get("player_code") for e in entrants if e.get("win_pct") is not None and not (0.0 <= e["win_pct"] <= 100.0)]
    return {"check": "WIN_PROBABILITY_IN_0_100_RANGE", "passed": len(bad) == 0, "detail": f"bad={bad}"}


def check_win_sums_to_100_among_cutmakers(entrants: list[dict], tolerance: float = 0.5) -> dict:
    """WIN% only sums to ~100 across players who made the cut (a
    non-cutmaker's win_pct is a real, known 0.0 — see round_update_r2's
    own docstring — and never contributes to the pool)."""
    values = [e["win_pct"] for e in entrants if e.get("win_pct") is not None and e.get("make_cut_pct") == 100.0]
    total = sum(values)
    passed = (not values) or abs(total - 100.0) <= tolerance
    return {"check": "WIN_SUMS_TO_100_AMONG_CUTMAKERS", "passed": passed, "detail": f"sum={total} over {len(values)} cutmakers"}


def check_missed_cut_count_plausible_after_completed_cut(cut_summary: dict) -> dict:
    """BETA #001's tournament format has exactly one real cut, after
    Round 2 (klpga.neo_win.round_update_r2's own docstring). Once real,
    completed official R2 data has actually been evaluated
    (`n_evaluated > 0`), a real field that shows ZERO missed-cut
    players is an impossible outcome — it means the CUT classification
    itself failed to find real missed-cut evidence (see klpga.neo_win.
    r1_to_r2_reconciliation's "A PLAYER WITH NO ROUND 2 ROW AT ALL"
    section), never that literally every evaluated player advanced.
    Real, confirmed regression: a live Windows run reported
    actual_missed_cut_count=0 with n_evaluated=110 and STEP10 wrongly
    passed it — this check exists specifically so that can never
    happen silently again."""
    n_evaluated = cut_summary.get("n_evaluated", 0)
    actual_missed = cut_summary.get("actual_missed_cut_count", 0)
    passed = n_evaluated == 0 or actual_missed > 0
    return {
        "check": "MISSED_CUT_COUNT_PLAUSIBLE_AFTER_COMPLETED_CUT",
        "passed": passed,
        "detail": f"n_evaluated={n_evaluated} actual_missed_cut_count={actual_missed}",
    }


def check_wd_dq_explicitly_handled(reconciliation_summary: dict) -> dict:
    required_keys = {"new_wd", "new_dq", "cut", "made_cut", "missing"}
    missing_keys = required_keys - set(reconciliation_summary)
    return {
        "check": "WD_DQ_EXPLICITLY_HANDLED",
        "passed": len(missing_keys) == 0,
        "detail": f"missing_keys={sorted(missing_keys)}" if missing_keys else str(reconciliation_summary),
    }


def check_unavailable_players_explicitly_handled(excluded_missing_r1_probability: list[str], reconciliation_summary: dict) -> dict:
    """Both "excluded from evaluation" (Section D) and "no real R2
    data yet" (Section B's `missing` count) must be real, reported
    numbers — never silently absorbed into the evaluated set."""
    passed = isinstance(excluded_missing_r1_probability, list) and "missing" in reconciliation_summary
    return {
        "check": "UNAVAILABLE_PLAYERS_EXPLICITLY_HANDLED",
        "passed": passed,
        "detail": f"excluded_missing_r1_probability={len(excluded_missing_r1_probability)} reconciliation_missing={reconciliation_summary.get('missing')}",
    }


def check_calibration_buckets_sum_to_evaluated(calibration_rows: list[dict], n_evaluated: int) -> dict:
    total = sum(b["n"] for b in calibration_rows)
    return {
        "check": "CALIBRATION_BUCKETS_SUM_TO_EVALUATED",
        "passed": total == n_evaluated,
        "detail": f"bucket_total={total} n_evaluated={n_evaluated}",
    }


def check_r2_path_never_overwrites_r1(r1_path: Path, r2_path: Path) -> dict:
    r1_resolved, r2_resolved = Path(r1_path).resolve(), Path(r2_path).resolve()
    passed = r1_resolved != r2_resolved
    return {
        "check": "R2_PATH_NEVER_OVERWRITES_R1",
        "passed": passed,
        "detail": f"r1_path={r1_resolved} r2_path={r2_resolved}",
    }


def run_all_validations(checks: list[dict]) -> dict:
    """Aggregates already-run checks (never runs them itself — the
    caller decides which checks apply, since not every check has
    inputs available in every mode, e.g. a dry run has no real
    docs/index.html production path to compare)."""
    failed = [c["check"] for c in checks if not c["passed"]]
    return {"all_passed": len(failed) == 0, "checks": checks, "failed": failed}
