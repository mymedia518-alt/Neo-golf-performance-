"""R2 HOUSE: the rendered-output gate.

BUGFIX (fix/kb-r2-official-cut-gate-20260911, real production visual QA
failure): scripts/112 already gated official-source/completeness/
duplicate/status/freeze/pre_binding/future_leakage/sg/forecast/
probability before ever calling klpga.neo_win.r2_real_page.
render_r2_real_page -- but nothing ever checked the ACTUAL RENDERED
HTML against the frozen evidence it was supposed to reflect. That is
exactly how a real R2 page shipped to production (commit 39ba15e) with
every rank fabricated as a tied "T1" (CUT players included) and every
TOTAL/2R cell empty, while every earlier gate correctly reported PASS
(the freeze/forecast/probability artifacts were all genuinely valid --
only the renderer's own field-name mismatch, see r2_real_page.py's
_total_to_par docstring, silently broke the public page built from
them).

This module is the missing check: it parses the ACTUAL generated HTML
(never a synthetic fixture) and cross-verifies rank/TOTAL/2R/status for
EVERY frozen player against the frozen R2 evidence directly -- not
"does the element exist", but "does the rendered value match the real
official value". Raises RenderedOutputGateError (write nothing, HARD_
STOP the cycle) on any divergence. Called from scripts/112's
_publish_and_close immediately after render_r2_real_page and BEFORE the
page is ever written to docs/ -- a failing render must never reach
production."""
from __future__ import annotations

import re

EMPTY_MARK = "—"


class RenderedOutputGateError(RuntimeError):
    """A generated R2 page diverges from the frozen evidence it was
    built from. The caller must never write this HTML to docs/ and
    must treat the cycle as HARD_STOP."""


def _real_total_to_par(record: dict):
    r1 = record.get("r1_score_to_par")
    r2 = record.get("r2_score_to_par")
    if r1 is None or r2 is None:
        return None
    try:
        return float(r1) + float(r2)
    except (TypeError, ValueError):
        return None


def _expected_to_par_display(v) -> str:
    if v is None:
        return EMPTY_MARK
    n = int(v)
    if n == 0:
        return "E"
    return f"+{n}" if n > 0 else str(n)


def parse_rendered_rows(html: str) -> dict[str, dict]:
    """Pure: {player_id: {"rank": str, "total": str, "round2": str,
    "status_badge": str | None}} parsed directly from the real
    generated HTML's own `<tr data-player-id='...'>` rows -- joined by
    the renderer's own stable player_id attribute, never by display
    name (see r2_real_page.py's own data-player-id docstring)."""
    if "<tbody>" not in html:
        raise RenderedOutputGateError("rendered HTML has no <tbody> -- not a real leaderboard page")
    body = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    rows = re.findall(r"<tr data-player-id='([^']+)'>((?:(?!</tr>).)*)</tr>", body)
    if not rows:
        return {}

    def cell(row: str, label: str) -> str:
        m = re.search(rf"data-label='{label}'[^>]*>([^<]*)<", row)
        if m is None:
            raise RenderedOutputGateError(f"rendered row missing required data-label='{label}' cell")
        return m.group(1)

    parsed = {}
    for pid, row in rows:
        badge = re.search(r"<span class='status-badge'>([^<]+)</span>", row)
        parsed[pid] = {
            "rank": cell(row, "순위"),
            "total": cell(row, "합계"),
            "round2": cell(row, "2R"),
            "status_badge": badge.group(1) if badge else None,
        }
    return parsed


def validate_r2_rendered_output(html: str, r2_freeze: dict) -> None:
    """The full rendered-output gate. Raises RenderedOutputGateError on
    the FIRST divergence found (message names the concrete player/field
    so the failure is immediately actionable), never silently accepts a
    partial mismatch.

    Checks, in order:
      1. Rendered population == frozen population exactly (by player_id).
      2. For EVERY frozen record: rendered TOTAL and 2R exactly equal
         the real, computed r1_score_to_par + r2_score_to_par / real
         r2_score_to_par -- not merely "present", the EXACT real value.
         A record with incomplete data must render EMPTY_MARK for both,
         never a fabricated number.
      3. For EVERY frozen record: rendered rank is EMPTY_MARK if and
         only if that record has no real, complete total -- never a
         fabricated numeric/tied rank for incomplete data, and never
         EMPTY_MARK for a player who DOES have a real, complete total.
      4. For every non-ACTIVE record: the rendered status badge matches
         the frozen status exactly.
      5. Population-scale sanity: if the frozen evidence has 2 or more
         DISTINCT real totals among players with complete data, the
         rendered page must show 2 or more DISTINCT rank values among
         those same players -- catches exactly the real production bug
         (every rank collapsing onto one fabricated shared value) even
         if some future defect produces a self-consistent-looking but
         still-wrong single wrong value per player."""
    records = r2_freeze["records"]
    rendered = parse_rendered_rows(html)

    freeze_ids = {str(r["player_id"]) for r in records}
    rendered_ids = set(rendered)
    if rendered_ids != freeze_ids:
        missing = freeze_ids - rendered_ids
        extra = rendered_ids - freeze_ids
        raise RenderedOutputGateError(
            f"rendered population diverges from frozen evidence: "
            f"{len(missing)} missing ({sorted(missing)[:5]}), {len(extra)} unexpected extra ({sorted(extra)[:5]})"
        )

    distinct_totals_seen = set()
    distinct_ranks_seen = set()
    complete_population_size = 0

    for record in records:
        pid = str(record["player_id"])
        name = record.get("player_name", pid)
        row = rendered[pid]
        real_total = _real_total_to_par(record)
        expected_total_display = _expected_to_par_display(real_total)
        expected_round2_display = _expected_to_par_display(record.get("r2_score_to_par"))

        if row["total"] != expected_total_display:
            raise RenderedOutputGateError(
                f"TOTAL diverges from frozen evidence for {name} ({pid}): "
                f"rendered {row['total']!r}, expected {expected_total_display!r}"
            )
        if row["round2"] != expected_round2_display:
            raise RenderedOutputGateError(
                f"2R diverges from frozen evidence for {name} ({pid}): "
                f"rendered {row['round2']!r}, expected {expected_round2_display!r}"
            )

        if real_total is None:
            if row["rank"] != EMPTY_MARK:
                raise RenderedOutputGateError(
                    f"fabricated rank for incomplete-data player {name} ({pid}): "
                    f"rendered {row['rank']!r}, real total is unknown -- must be {EMPTY_MARK!r}"
                )
        else:
            if row["rank"] == EMPTY_MARK:
                raise RenderedOutputGateError(
                    f"missing rank for {name} ({pid}) despite a real, complete total ({real_total})"
                )
            complete_population_size += 1
            distinct_totals_seen.add(real_total)
            distinct_ranks_seen.add(row["rank"])

        status = record.get("status", "ACTIVE")
        if status != "ACTIVE" and row["status_badge"] != status:
            raise RenderedOutputGateError(
                f"status badge diverges from frozen evidence for {name} ({pid}): "
                f"rendered {row['status_badge']!r}, expected {status!r}"
            )

    if complete_population_size >= 2 and len(distinct_totals_seen) >= 2 and len(distinct_ranks_seen) < 2:
        raise RenderedOutputGateError(
            f"rank population is invalid: {complete_population_size} players have real, DIFFERING totals "
            f"({len(distinct_totals_seen)} distinct) but only {len(distinct_ranks_seen)} distinct rank(s) "
            "were rendered -- the real production T1-for-everyone failure mode"
        )
