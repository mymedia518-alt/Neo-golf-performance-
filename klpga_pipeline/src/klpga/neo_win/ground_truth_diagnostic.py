"""BETA #001 R1 -> R2 ground-truth CUT-status diagnostic (double-
verification phase). Builds a per-player comparison table from real,
already-collected official Round 1 / Round 2 leaderboard rows plus —
when available — a real official Round 3 grouping/tee-time list.

This module NEVER infers a MISSED_CUT status from a player being
absent from a round's response, or from rank/position, taken alone. A
real Windows run already disproved that inference on its own (see
klpga.neo_win.r1_to_r2_reconciliation's own docstring): it produced an
implausibly high made-cut rate, meaning "absent from Round 2" is not,
by itself, reliable evidence of a missed cut on the real site. This
module instead combines TWO independent real signals — Round 3's real
grouping/tee-time list (a "this player was assigned a tee time to
continue playing" fact) plus a self-consistency check against the
Round 2 scores of players who ARE confirmed in Round 3 — before ever
proposing MISSED_CUT, and even then only as a CANDIDATE, gated by
cut-line consistency.

======================================================================
GROUP-PAGE ENDPOINT — URL CONFIRMED, DOM STRUCTURE NOT YET CONFIRMED
======================================================================
A real, human-captured browser Network request confirmed:
    GET https://klpga.co.kr/web/tourInfo/group?gameCode=<code>
    response: HTTP 200, text/html; charset=UTF-8
(see klpga.config.GROUP_PAGE_ENDPOINT and
klpga.collectors.group_page.fetch_group_page_html). Only the URL,
method, and response type are confirmed — the page's DOM structure,
including how the 1R/2R/3R tabs are represented, has NOT been
confirmed against real markup, so no parser exists yet. `r3_grouping_rows`
is therefore a plain parameter this module accepts from an ALREADY
structured real source (see scripts/diagnose_r2_r3_ground_truth.py's
--r3-grouping-json) — an empty list is the real, honest "not collected
/ not parseable yet" state, never treated as "confirmed no groupings
exist."

======================================================================
final_ground_truth_status — evidence tiers
======================================================================
  1. Explicit WD/DQ status text (Round 2 preferred, else Round 1) AND
     the player is ALSO found in the real Round 3 grouping list ->
     REVIEW_REQUIRED (a direct evidence conflict: official status says
     withdrawn/disqualified but Round 3 grouping says still playing).
  2. Explicit WD/DQ status text (Round 2 preferred, else Round 1),
     no conflict with Round 3 -> that status (WD or DQ).
  3. Found in the real Round 3 grouping/tee-time list, no explicit
     WD/DQ conflict -> MADE_CUT_CONFIRMED (the strongest, most direct
     real signal: they were assigned a tee time to keep playing).
  4. Absent from Round 3, but a valid completed Round 2 score exists
     (real total score, no explicit WD/DQ text, not the ambiguous
     999/INCOMPLETE sentinel) -> MISSED_CUT_CANDIDATE, subject to the
     cut-line consistency check below.
  5. Anything else (no Round 2 row, an incomplete/ambiguous Round 2
     row, or Round 3 data not collected at all yet) ->
     REVIEW_REQUIRED, with a `reason` naming exactly what evidence is
     missing.

======================================================================
Cut-line consistency check (second pass)
======================================================================
The derived cut line is the WORST (highest) `r2_total_score` among all
MADE_CUT_CONFIRMED players (i.e. the real Round 3 field) — a purely
empirical value, not an assumed field size or an assumed "top N and
ties" rule. Any MISSED_CUT_CANDIDATE whose own `r2_total_score` is AS
GOOD AS OR BETTER THAN (<=) that derived cut line directly conflicts
with the real Round 3 field (they scored well enough to belong, yet
are absent from it) and is reclassified to REVIEW_REQUIRED rather than
silently left as a missed-cut candidate. This is the HARD GATE: real
R2/R3 evidence conflicts always resolve to REVIEW_REQUIRED, never to a
guessed classification.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

STATUS_WD = "WD"
STATUS_DQ = "DQ"
STATUS_MADE_CUT = "MADE_CUT_CONFIRMED"
STATUS_MISSED_CUT_CANDIDATE = "MISSED_CUT_CANDIDATE"
STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"

_KNOWN_EXCEPTIONAL_STATUS = {"WD": STATUS_WD, "DQ": STATUS_DQ}


@dataclass(frozen=True)
class R3GroupingRow:
    """One player's real Round 3 grouping/tee-time entry — from an
    ALREADY-collected/structured real source (see module docstring);
    this dataclass never fetches or parses anything itself."""

    player_code: str
    player_name: Optional[str]
    group: Optional[str]
    tee_time: Optional[str]
    starting_tee: Optional[str] = None


@dataclass(frozen=True)
class GroundTruthRow:
    player_code: str
    official_name: str
    r1_present: bool
    r2_present: bool
    r2_raw_rank: Optional[str]
    r2_raw_status: Optional[str]
    r2_round_score: Optional[int]
    r2_total_score: Optional[int]
    r3_grouping_present: bool
    r3_group: Optional[str]
    r3_tee_time: Optional[str]
    r3_starting_tee: Optional[str]
    final_ground_truth_status: str
    reason: str


def _explicit_status(r1, r2) -> tuple[Optional[str], Optional[str]]:
    """Returns (status, source_round_label) for an explicit WD/DQ
    status only — Round 2 preferred, Round 1 only consulted when
    Round 2 has no row at all. Never derived from anything else."""
    r2_status = r2.status if r2 else None
    if r2_status in _KNOWN_EXCEPTIONAL_STATUS:
        return _KNOWN_EXCEPTIONAL_STATUS[r2_status], "Round 2"
    if r2 is None and r1 is not None and r1.status in _KNOWN_EXCEPTIONAL_STATUS:
        return _KNOWN_EXCEPTIONAL_STATUS[r1.status], "Round 1"
    return None, None


def build_ground_truth_table(
    r1_rows: list, r2_rows: list, r3_grouping_rows: list[R3GroupingRow]
) -> tuple[list[GroundTruthRow], dict]:
    """Pure function — no I/O, no fabrication. `r1_rows`/`r2_rows` are
    real klpga.parsers.leaderboard_parser.PlayerRoundRow lists (from an
    already-completed live fetch, e.g. klpga.collectors.leaderboard.
    collect_all_rounds_for_game). `player_code` is the ONLY join key
    across all three sources."""
    r1_by_code = {r.player_code: r for r in r1_rows if r.player_code}
    r2_by_code = {r.player_code: r for r in r2_rows if r.player_code}
    r3_by_code = {r.player_code: r for r in r3_grouping_rows if r.player_code}

    all_codes = set(r1_by_code) | set(r2_by_code) | set(r3_by_code)
    r3_available = len(r3_grouping_rows) > 0

    rows: list[GroundTruthRow] = []
    for code in sorted(all_codes):
        r1 = r1_by_code.get(code)
        r2 = r2_by_code.get(code)
        r3 = r3_by_code.get(code)
        r3_present = r3 is not None

        official_name = (
            (r2.player_name if r2 else None)
            or (r1.player_name if r1 else None)
            or (r3.player_name if r3 else None)
            or ""
        )

        explicit_status, status_source = _explicit_status(r1, r2)
        r2_status = r2.status if r2 else None
        r2_total_score = r2.total_strokes if r2 else None
        valid_r2_score = r2 is not None and r2_total_score is not None and explicit_status is None

        if explicit_status is not None and r3_present:
            status = STATUS_REVIEW_REQUIRED
            reason = (
                f"evidence conflict: official {status_source} status text = {explicit_status!r} "
                "but this player is ALSO found in the real official Round 3 grouping/tee-time list"
            )
        elif explicit_status is not None:
            status = explicit_status
            reason = f"official {status_source} status text = {explicit_status!r}"
        elif r3_present:
            status = STATUS_MADE_CUT
            reason = "found in the real official Round 3 grouping/tee-time list"
        elif valid_r2_score:
            status = STATUS_MISSED_CUT_CANDIDATE
            if r3_available:
                reason = (
                    "absent from the real Round 3 grouping/tee-time list with a valid completed "
                    "Round 2 score — missed-cut candidate, pending cut-line consistency validation"
                )
            else:
                reason = (
                    "Round 3 grouping/tee-time data not collected yet, but a valid completed Round 2 "
                    "score exists — tentative missed-cut candidate, cannot be validated against a cut "
                    "line until Round 3 data is available"
                )
        elif r3_available:
            status = STATUS_REVIEW_REQUIRED
            reason = (
                "no valid completed Round 2 score (missing or ambiguous/incomplete Round 2 evidence) "
                "and no explicit WD/DQ status — insufficient evidence to classify"
            )
        else:
            status = STATUS_REVIEW_REQUIRED
            reason = "Round 3 grouping/tee-time data not collected yet — cannot determine status"

        rows.append(
            GroundTruthRow(
                player_code=code,
                official_name=official_name,
                r1_present=r1 is not None,
                r2_present=r2 is not None,
                r2_raw_rank=r2.rank_display if r2 else None,
                r2_raw_status=r2_status,
                r2_round_score=r2.round2_score if r2 else None,
                r2_total_score=r2_total_score,
                r3_grouping_present=r3_present,
                r3_group=r3.group if r3 else None,
                r3_tee_time=r3.tee_time if r3 else None,
                r3_starting_tee=r3.starting_tee if r3 else None,
                final_ground_truth_status=status,
                reason=reason,
            )
        )

    # --- second pass: derive the empirical cut line from confirmed
    # Round 3 continuers, then flag any MISSED_CUT_CANDIDATE that
    # conflicts with it (scored as well as or better than the worst
    # confirmed continuer) as REVIEW_REQUIRED instead. ---
    made_cut_scores = [
        r.r2_total_score for r in rows if r.final_ground_truth_status == STATUS_MADE_CUT and r.r2_total_score is not None
    ]
    derived_cut_line = max(made_cut_scores) if made_cut_scores else None
    cut_line_exceptions: list[str] = []

    if derived_cut_line is not None:
        for i, row in enumerate(rows):
            if row.final_ground_truth_status != STATUS_MISSED_CUT_CANDIDATE:
                continue
            if row.r2_total_score is not None and row.r2_total_score <= derived_cut_line:
                cut_line_exceptions.append(row.player_code)
                rows[i] = GroundTruthRow(
                    **{
                        **row.__dict__,
                        "final_ground_truth_status": STATUS_REVIEW_REQUIRED,
                        "reason": (
                            f"cut-line conflict: Round 2 total score {row.r2_total_score} is <= the derived "
                            f"cut line {derived_cut_line} from confirmed Round 3 continuers, yet this player "
                            "is absent from the real Round 3 grouping/tee-time list"
                        ),
                    }
                )

    summary = {
        "total_tournament_players": len(all_codes),
        "r3_grouping_player_count": len(r3_by_code),
        "r3_absent_count": sum(1 for r in rows if not r.r3_grouping_present),
        "explicit_wd_count": sum(1 for r in rows if r.final_ground_truth_status == STATUS_WD),
        "explicit_dq_count": sum(1 for r in rows if r.final_ground_truth_status == STATUS_DQ),
        "made_cut_confirmed_count": sum(1 for r in rows if r.final_ground_truth_status == STATUS_MADE_CUT),
        "missed_cut_candidate_count": sum(1 for r in rows if r.final_ground_truth_status == STATUS_MISSED_CUT_CANDIDATE),
        "review_required_count": sum(1 for r in rows if r.final_ground_truth_status == STATUS_REVIEW_REQUIRED),
        "derived_cut_line": derived_cut_line,
        "cut_line_exceptions": cut_line_exceptions,
        # retained for backward-compat with earlier diagnostic output
        "unexplained_count": sum(1 for r in rows if r.final_ground_truth_status == STATUS_REVIEW_REQUIRED),
    }
    return rows, summary


_RAW_ROUND_ROW_FIELDNAMES: tuple[str, ...] = (
    "game_code", "player_code", "player_name", "player_eng_name", "round_number",
    "rank_display", "rank", "tie_flag", "status",
    "total_under_par_display", "total_under_par",
    "today_under_par_display", "today_under_par",
    "total_strokes", "holes_completed",
    "round1_score", "round2_score", "round3_score", "round4_score",
)


def raw_round_row_to_dict(row) -> dict:
    """Every real PlayerRoundRow field, preserved as-is — the "every
    raw status/rank field available from the endpoint" requirement
    (GROUND TRUTH CHECK A) — never a trimmed subset."""
    return {name: getattr(row, name) for name in _RAW_ROUND_ROW_FIELDNAMES}
