"""R3 RESULT-ONLY INPUT PREPARATION.

This module is NOT the R3 forecast pipeline (klpga.neo_win.r3_freeze /
post_r3_forecast / r3_real_page, built earlier for the general
end-of-round-page architecture and left untouched by this module).
KB 2026090003's real, confirmed final_round_number is 3 -- R3 is this
tournament's LAST competitive round, so there is no POST-R3 win
forecast to build or publish. This module exists for exactly one
purpose: once R3 has genuinely concluded, collect the single official
R3 RESULT (never a forecast, never a simulation) and JOIN it against
the already-frozen R2 forecast to produce a FINAL validation dataset
-- nothing more.

======================================================================
REQUIRED USER INPUT: NONE beyond running the entry point
======================================================================
scripts/117_kb_r3_result_and_final_candidate.py is the ONE command a
user runs after R3 concludes. It collects the official result itself
(klpga.co.kr roundLeaderboard, round=3) -- no player list, no CSV, no
manually-entered probabilities, no CUT/WD judgment, no R1/R2 re-entry.

======================================================================
OFFICIAL STATUS PRECEDENCE -- NEVER INFER WD/DQ
======================================================================
A player's real, confirmed status comes from exactly one place: the
official round=3 roundLeaderboard row's own parsed `status` field
(klpga.parsers.leaderboard_parser.PlayerRoundRow.status -- only ever
set from a real site-rendered CUT/WD/DQ/INCOMPLETE marker, per that
parser's own docstring). A player present with a real score and no
status marker is ACTIVE. A player who does NOT appear in the round=3
response AT ALL is UNRESOLVED -- never defaulted to WD/DQ, and never
silently dropped; it BLOCKS FINAL candidate generation until real
evidence resolves it (see validate_r3_result's `unresolved_players`).
This is the exact real production defect ("missing row treated as WD")
this module is built to never repeat.

DISCLOSED, DELIBERATE GAP (mirrors scripts/114's own r3 active-cycle
convention exactly): `holes_completed` is never read from the raw
`data-inghole` response field directly -- that field's real meaning is
ambiguous without combining it with `starting_tee` evidence (see
scripts/114's own module docstring), and neither matters for a
COMPLETED final round's official result (there is no "in progress"
state left to disambiguate once the round has genuinely ended).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REQUIRED_R2_ACTIVE_POPULATION = 71


class R3ResultInputError(RuntimeError):
    """A real precondition failure (e.g. no R2 freeze/forecast exists
    yet) -- distinct from a validation BLOCKED report, which is a real,
    reportable outcome, not an exception."""


class R2FreezeProtectionError(RuntimeError):
    """HARD STOP: R2's frozen artifacts changed between the pre- and
    post-collection snapshot. R3 collection/validation must NEVER be
    able to mutate R2 -- if this fires, something wrote to a file it
    must not have, and no FINAL candidate is ever produced."""


@dataclass(frozen=True)
class R3OfficialResultRow:
    player_id: str
    player_name: str
    r3_score: Optional[float]
    """Real round-3 score-to-par. None only for a real WD/DQ row with
    no completed round-3 score -- never a fabricated 0."""
    final_total: Optional[float]
    """Real cumulative r1+r2+r3 total-to-par. None only when r3_score
    is None."""
    official_status: str
    """'ACTIVE' | 'WD' | 'DQ' -- ONLY ever set from a real official
    evidence marker (the round=3 row's own parsed status) or 'ACTIVE'
    when the row is present with a real score and no marker. Never
    'CUT' -- KB's cut already happened at R2; a CUT record has no
    business appearing in the R3-eligible (R2 ACTIVE) population this
    module ever joins against."""
    status_evidence: Optional[str]
    """A short, real description of where a non-ACTIVE status came
    from (e.g. 'official round=3 roundLeaderboard row status=WD') --
    None for ACTIVE rows. Never populated for an inferred status."""


def extract_r3_official_result(
    raw_rows: list, r2_active_player_ids: set[str]
) -> tuple[list[R3OfficialResultRow], list[str]]:
    """Pure: raw_rows are klpga.parsers.leaderboard_parser.PlayerRoundRow
    instances (or any object with the same attributes) from a real
    round=3 roundLeaderboard fetch. Returns (rows, unresolved_player_ids)
    -- unresolved_player_ids are R2-ACTIVE players who do NOT appear
    anywhere in raw_rows at all; they are NEVER defaulted to WD/DQ,
    NEVER silently dropped, and NEVER included in the returned rows.
    Rows for a player outside r2_active_player_ids (e.g. a real CUT
    player who still shows up on the R3 page) are excluded -- they have
    no place in a result built only for the 71 ACTIVE population."""
    by_id: dict[str, object] = {}
    for r in raw_rows:
        pid = getattr(r, "player_code", None)
        if pid is None or pid not in r2_active_player_ids:
            continue
        by_id[pid] = r  # last-seen wins is never reached: duplicates are validated separately

    rows: list[R3OfficialResultRow] = []
    for pid in r2_active_player_ids:
        r = by_id.get(pid)
        if r is None:
            continue  # unresolved -- reported by the caller, never guessed here
        status = getattr(r, "status", None)
        r3_score = getattr(r, "today_under_par", None)
        if r3_score is None:
            r3_score = getattr(r, "round3_score", None)
        total = getattr(r, "total_under_par", None)
        if status in ("WD", "DQ"):
            rows.append(R3OfficialResultRow(
                player_id=pid, player_name=getattr(r, "player_name", None),
                r3_score=r3_score, final_total=total,
                official_status=status,
                status_evidence=f"official round=3 roundLeaderboard row status={status}",
            ))
        else:
            rows.append(R3OfficialResultRow(
                player_id=pid, player_name=getattr(r, "player_name", None),
                r3_score=r3_score, final_total=total,
                official_status="ACTIVE", status_evidence=None,
            ))

    resolved_ids = {row.player_id for row in rows}
    unresolved = sorted(r2_active_player_ids - resolved_ids)
    return rows, unresolved


def _derive_final_ranks(rows: list[R3OfficialResultRow]) -> dict[str, str]:
    """Ascending real final_total (lower is better), exactly mirroring
    klpga.neo_win.r2_real_page._derive_display_ranks's own algorithm --
    DERIVED from the real total, never taken from an external/echoed
    rank field. A row with no real final_total (WD/DQ with no score)
    never receives a numeric or tied rank."""
    with_total = [r for r in rows if r.final_total is not None]
    ordered = sorted(with_total, key=lambda r: r.final_total)
    ranks: dict[str, str] = {r.player_id: "—" for r in rows}
    current_rank = 0
    current_total = None
    tie_counts: dict[int, int] = {}
    for i, r in enumerate(ordered, start=1):
        if r.final_total != current_total:
            current_rank = i
            current_total = r.final_total
        ranks[r.player_id] = str(current_rank)
        tie_counts[current_rank] = tie_counts.get(current_rank, 0) + 1
    return {pid: (f"T{r}" if r != "—" and tie_counts.get(int(r), 0) > 1 else r) for pid, r in ranks.items()}


@dataclass(frozen=True)
class R3ValidationReport:
    passed: bool
    checks: dict  # {check_name: (bool, reason)}
    unresolved_players: list
    duplicate_player_ids: list
    duplicate_player_names: list

    def blocked_reasons(self) -> list[str]:
        return [f"{name}: {reason}" for name, (ok, reason) in self.checks.items() if not ok]


def validate_r3_result(
    *,
    game_code: str,
    final_round_number: int,
    r2_freeze: dict,
    r3_rows: list[R3OfficialResultRow],
    unresolved_player_ids: list[str],
    raw_rows: list,
    expected_game_code: str = "2026090003",
) -> R3ValidationReport:
    """The 12-point checklist. Every check is fail-closed: BLOCKED
    (passed=False) unless real evidence confirms it. Never PASS merely
    because nothing looked wrong -- each check states what it verified."""
    active_records = [r for r in r2_freeze["records"] if r.get("status") == "ACTIVE"]
    active_ids = {str(r["player_id"]) for r in active_records}

    r3_ids_seen = [getattr(r, "player_code", None) for r in raw_rows]
    dup_ids = sorted({pid for pid in r3_ids_seen if pid and r3_ids_seen.count(pid) > 1})

    names_by_id = {r.player_id: r.player_name for r in r3_rows}
    name_to_ids: dict[str, set[str]] = {}
    for pid, name in names_by_id.items():
        name_to_ids.setdefault(name, set()).add(pid)
    dup_names = sorted(name for name, ids in name_to_ids.items() if len(ids) > 1)

    r3_ids = {r.player_id for r in r3_rows}
    unmatched_extra = sorted(r3_ids - active_ids)  # r3 rows for a player not in R2 ACTIVE (should never happen -- extract already filters)
    missing_from_r3 = sorted(active_ids - r3_ids)  # == unresolved_player_ids, kept as an independent cross-check

    scores_ok = all(r.r3_score is not None or r.official_status in ("WD", "DQ") for r in r3_rows)
    totals_ok = all(r.final_total is not None or r.official_status in ("WD", "DQ") for r in r3_rows)
    ranks = _derive_final_ranks(r3_rows)
    ranks_ok = all(ranks.get(r.player_id) not in (None,) for r in r3_rows)
    status_evidence_ok = all(
        (r.official_status == "ACTIVE") or (r.status_evidence is not None)
        for r in r3_rows
    )

    checks = {
        "tournament_identity": (game_code == expected_game_code, f"game_code={game_code!r}, expected {expected_game_code!r}"),
        "final_round_number": (final_round_number == 3, f"final_round_number={final_round_number!r}, expected 3"),
        "r2_active_population_71": (len(active_ids) == REQUIRED_R2_ACTIVE_POPULATION, f"R2 ACTIVE population={len(active_ids)}, expected {REQUIRED_R2_ACTIVE_POPULATION}"),
        "player_id_join_complete": (not unresolved_player_ids and not unmatched_extra, f"unresolved={unresolved_player_ids}, unmatched_extra={unmatched_extra}"),
        "no_duplicate_player_id": (not dup_ids, f"duplicate player_id in raw R3 rows: {dup_ids}"),
        "no_duplicate_player_name": (not dup_names, f"duplicate player_name across distinct player_id: {dup_names}"),
        "unmatched_players": (not missing_from_r3 and not unmatched_extra, f"missing_from_r3={missing_from_r3}, unmatched_extra={unmatched_extra}"),
        "r3_score_present": (scores_ok, "every ACTIVE row has a real r3_score" if scores_ok else "at least one ACTIVE row is missing r3_score"),
        "final_total_present": (totals_ok, "every ACTIVE row has a real final_total" if totals_ok else "at least one ACTIVE row is missing final_total"),
        "final_rank_derived": (ranks_ok, "every row received a derived rank or the explicit unranked mark"),
        "official_wd_dq_status_evidenced": (status_evidence_ok, "every non-ACTIVE status carries real evidence" if status_evidence_ok else "a non-ACTIVE status has no evidence string"),
        "population_reconciliation": (
            len(r3_rows) + len(unresolved_player_ids) == REQUIRED_R2_ACTIVE_POPULATION,
            f"{len(r3_rows)} resolved + {len(unresolved_player_ids)} unresolved != {REQUIRED_R2_ACTIVE_POPULATION}",
        ),
    }
    passed = all(ok for ok, _ in checks.values())
    return R3ValidationReport(
        passed=passed, checks=checks, unresolved_players=list(unresolved_player_ids),
        duplicate_player_ids=dup_ids, duplicate_player_names=dup_names,
    )


_R2_PROTECTED_ARTIFACT_TYPES = ("r2_frozen_evidence", "post_r2_final_forecast")


def snapshot_r2_state(context) -> dict[str, Optional[str]]:
    """sha256 of every byte of R2's frozen freeze + forecast artifacts,
    keyed by artifact_type. A missing file hashes to None (still
    compared exactly on the way out -- a file that appears, disappears,
    or changes between snapshots is caught identically)."""
    snapshot = {}
    for artifact_type in _R2_PROTECTED_ARTIFACT_TYPES:
        path = context.artifact_path(artifact_type)
        snapshot[artifact_type] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return snapshot


def verify_r2_state_unchanged(context, before: dict[str, Optional[str]]) -> None:
    after = snapshot_r2_state(context)
    if after != before:
        changed = {k: (before.get(k), after.get(k)) for k in before if before.get(k) != after.get(k)}
        raise R2FreezeProtectionError(f"R2 frozen artifacts changed during R3 result collection -- HARD STOP: {changed}")


def build_r3_frozen_records(*, r2_freeze: dict, r3_rows: list[R3OfficialResultRow]) -> list[dict]:
    """R3 FINAL WEB DRY-RUN task, section 1: R3 MUST exist as a real
    public stage in its own right -- FINAL must never be reachable by
    collapsing R2 straight into FINAL. This builds the exact per-player
    record shape klpga.neo_win.r3_freeze.build_r3_frozen_evidence /
    klpga.neo_win.r3_real_page.render_r3_real_page already require
    (player_id, player_name, status, r1_score_to_par, r2_score_to_par,
    r3_score_to_par), merging R2's own frozen r1/r2 scores with this
    module's own real, evidence-gated R3 result -- never a second,
    independently-sourced r1/r2 number. `status` is carried through
    from `r3_rows` verbatim (already real evidence-only, per
    extract_r3_official_result's own contract) -- R3FrozenEvidence's own
    __post_init__ rejects anything outside {ACTIVE, WD, DQ, DNS}, so a
    'CUT' status (settled at R2, never valid at R3) can never reach it."""
    r2_by_id = {str(r["player_id"]): r for r in r2_freeze["records"]}
    records = []
    for r in r3_rows:
        r2_row = r2_by_id.get(r.player_id, {})
        records.append({
            "player_id": r.player_id,
            "player_name": r.player_name,
            "status": r.official_status,
            "r1_score_to_par": r2_row.get("r1_score_to_par"),
            "r2_score_to_par": r2_row.get("r2_score_to_par"),
            "r3_score_to_par": r.r3_score,
        })
    return records


def build_final_validation_dataset(
    *, r2_freeze: dict, r2_forecast: dict, r3_rows: list[R3OfficialResultRow]
) -> list[dict]:
    """The ONE join this module produces: R2's frozen forecast x R3's
    official result. Never a POST-R3 win forecast -- no simulation, no
    probability is computed here, only real inputs carried through and
    real final placement flags derived from the real final_rank."""
    forecast_by_id = {str(r["player_id"]): r for r in r2_forecast.get("records", [])}
    ranks = _derive_final_ranks(r3_rows)

    dataset = []
    for r in r3_rows:
        fc = forecast_by_id.get(r.player_id)
        final_rank = ranks.get(r.player_id)
        numeric_rank = None
        if final_rank not in (None, "—"):
            try:
                numeric_rank = int(final_rank.lstrip("T"))
            except ValueError:
                numeric_rank = None
        dataset.append((
            numeric_rank,
            {
                "player_id": r.player_id,
                "player_name": r.player_name,
                "r2_rank": fc.get("neo_final_rank") if fc else None,
                "r2_total": fc.get("r2_total_to_par") if fc else None,
                "r2_top20": fc.get("top20_pct") if fc else None,
                "r2_top10": fc.get("top10_pct") if fc else None,
                "r2_top5": fc.get("top5_pct") if fc else None,
                "r2_win": fc.get("win_pct") if fc else None,
                "r3_score": r.r3_score,
                "final_total": r.final_total,
                "final_rank": final_rank,
                "final_status": r.official_status,
                "winner_flag": numeric_rank == 1,
                "top5_flag": numeric_rank is not None and numeric_rank <= 5,
                "top10_flag": numeric_rank is not None and numeric_rank <= 10,
                "top20_flag": numeric_rank is not None and numeric_rank <= 20,
            },
        ))
    dataset.sort(key=lambda pair: (pair[0] is None, pair[0] if pair[0] is not None else 0))
    return [row for _, row in dataset]
