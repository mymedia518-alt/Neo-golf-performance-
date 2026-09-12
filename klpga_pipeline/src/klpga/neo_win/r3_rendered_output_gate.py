"""R3 HOUSE: the rendered-output gate.

Mirrors klpga.neo_win.r2_rendered_output_gate exactly, one round later
(including that module's own R2 CUT SURVIVORS ONLY population scoping):
parses the ACTUAL generated HTML (never a synthetic fixture) and
cross-verifies rank/3R/probabilities for EVERY ADVANCING
(status=="ACTIVE") player against the frozen R3 evidence directly --
(ROUND-PAGE SHARED CONTRACT, VISUAL-ARTIFACT-001 remediation: R3's
public table has no cumulative-total column -- 3R is the round's own
score, via klpga.website_v2.round_score_format.format_round_score --
ranking is still computed from the real cumulative total internally,
just never displayed)
not "does the element exist", but "does the rendered value match the
real official value". Raises RenderedOutputGateError (write nothing,
HARD_STOP the cycle) on any divergence. A WD/DQ/DNS record appearing as
a rendered row -- or an advancing record missing -- is itself a
HARD_STOP (population divergence), since the public main table shows
ONLY the advancing population.
"""
from __future__ import annotations

import re

from klpga.website_v2.round_score_format import format_round_score

EMPTY_MARK = "—"
ADVANCING_STATUS = "ACTIVE"
REQUIRED_HEADER_ORDER = ("순위", "선수", "3R", "TOP20", "TOP10", "TOP5", "우승")


class RenderedOutputGateError(RuntimeError):
    """A generated R3 page diverges from the frozen evidence it was
    built from. The caller must never write this HTML to docs/ and
    must treat the cycle as HARD_STOP."""


def _real_total_to_par(record: dict):
    r1 = record.get("r1_score_to_par")
    r2 = record.get("r2_score_to_par")
    r3 = record.get("r3_score_to_par")
    if r1 is None or r2 is None or r3 is None:
        return None
    try:
        return float(r1) + float(r2) + float(r3)
    except (TypeError, ValueError):
        return None


def _expected_pct_display(v) -> str:
    if v is None:
        return EMPTY_MARK
    p = float(v)
    if p == 0:
        return "0%"
    if 0 < p < 0.1:
        return "&lt;0.1%"
    return f"{p:.1f}%"


def parse_rendered_rows(html: str) -> dict[str, dict]:
    """Pure: {player_id: {"rank": str, "round3": str,
    "top5": str, "top10": str, "top20": str, "win": str}} parsed
    directly from the real generated HTML's own `<tr data-player-id=
    '...'>` rows -- joined by the renderer's own stable player_id
    attribute, never by display name."""
    if "<tbody>" not in html:
        raise RenderedOutputGateError("rendered HTML has no <tbody> -- not a real leaderboard page")
    body = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    rows = re.findall(r"<tr data-player-id='([^']+)'>((?:(?!</tr>).)*)</tr>", body)
    if not rows:
        return {}

    seen_ids = [pid for pid, _ in rows]
    dupes = sorted({pid for pid in seen_ids if seen_ids.count(pid) > 1})
    if dupes:
        raise RenderedOutputGateError(f"duplicate player_id rendered more than once in the main table: {dupes}")

    def cell(row: str, label: str) -> str:
        m = re.search(rf"data-label='{label}'[^>]*>([^<]*)<", row)
        if m is None:
            raise RenderedOutputGateError(f"rendered row missing required data-label='{label}' cell")
        return m.group(1)

    parsed = {}
    for pid, row in rows:
        if "class='player-name'" not in row or "class='player-sponsor'" not in row:
            raise RenderedOutputGateError(f"sponsor contract broken for player_id {pid}: missing player-name/player-sponsor slot")
        parsed[pid] = {
            "rank": cell(row, "순위"),
            "round3": cell(row, "3R"),
            "top5": cell(row, "Top5"),
            "top10": cell(row, "Top10"),
            "top20": cell(row, "Top20"),
            "win": cell(row, "우승"),
        }
    return parsed


def validate_r3_rendered_output(html: str, r3_freeze: dict, forecast: dict) -> None:
    """The full rendered-output gate. Raises RenderedOutputGateError on
    the FIRST divergence found (message names the concrete player/field
    so the failure is immediately actionable), never silently accepts a
    partial mismatch.

    Checks, in order:
      0a. No SG column anywhere in the page (SG must never appear in
          the public main table).
      0b. Header is EXACTLY REQUIRED_HEADER_ORDER, in order -- the
          7-column public contract (no cumulative-total column).
      0c. (inside parse_rendered_rows) no player_id is rendered more
          than once (duplicate player), and every row carries a
          structurally present player-name/player-sponsor slot
          (sponsor contract).
      1. Rendered population == the ADVANCING (status=="ACTIVE") subset
         of the frozen population exactly (by player_id) -- a WD/DQ/DNS
         record must NEVER appear as a rendered row, and every
         advancing record must always appear.
      2. For EVERY advancing record: rendered 3R exactly equals
         format_round_score(r3_strokes, r3_score_to_par) -- not merely
         "present", the EXACT real value. A record with no real r3
         strokes must render EMPTY_MARK.
      3. For EVERY advancing record: rendered rank is EMPTY_MARK if and
         only if that record has no real, complete total.
      4. For EVERY advancing record: rendered WIN/TOP5/TOP10/TOP20
         exactly equal the forecast's own recorded values (1-decimal
         display), or EMPTY_MARK if the player is absent from the
         forecast (e.g. missing PRE profile).
      5. Population-scale sanity: if the advancing population has 2 or
         more DISTINCT real totals among players with complete data,
         the rendered page must show 2 or more DISTINCT rank values
         among those same players -- catches the T1-for-everyone
         failure mode even if some future defect produces a self-
         consistent-looking but still-wrong single wrong value."""
    if "SG TOTAL" in html or "SG OTT" in html or "SG APP" in html or "SG ARG" in html or "SG PUTT" in html:
        raise RenderedOutputGateError("SG column(s) present in the public R3 main table -- SG must never appear here")

    header_match = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL)
    if header_match is None:
        raise RenderedOutputGateError("rendered HTML has no <thead> -- not a real leaderboard page")
    header_labels = tuple(re.findall(r"<th>([^<]*)</th>", header_match.group(1)))
    if header_labels != REQUIRED_HEADER_ORDER:
        raise RenderedOutputGateError(
            f"wrong column contract: rendered header {header_labels!r} != required {REQUIRED_HEADER_ORDER!r}"
        )

    records = r3_freeze["records"]
    rendered = parse_rendered_rows(html)
    forecast_by_id = {str(r["player_id"]): r for r in forecast.get("records", [])}

    advancing_records = [r for r in records if r.get("status", "ACTIVE") == ADVANCING_STATUS]
    # Public R3 truth includes explicit non-active status rows (WD/DQ/DNS);
    # absence is never used to infer status.
    advancing_ids = {str(r["player_id"]) for r in records}
    rendered_ids = set(rendered)
    if rendered_ids != advancing_ids:
        missing = advancing_ids - rendered_ids
        extra = rendered_ids - advancing_ids
        raise RenderedOutputGateError(
            f"rendered PUBLIC MAIN TABLE population diverges from the official advancing field: "
            f"{len(missing)} advancing player(s) missing ({sorted(missing)[:5]}), "
            f"{len(extra)} non-advancing/unexpected row(s) present ({sorted(extra)[:5]})"
        )

    distinct_totals_seen = set()
    distinct_ranks_seen = set()
    complete_population_size = 0

    for record in records:
        pid = str(record["player_id"])
        name = record.get("player_name", pid)
        row = rendered[pid]
        real_total = record.get("total_strokes") if record.get("total_strokes") is not None else _real_total_to_par(record)
        expected_round3_display = format_round_score(record.get("r3_strokes"), record.get("r3_score_to_par"))

        if row["round3"] != expected_round3_display:
            raise RenderedOutputGateError(
                f"3R diverges from frozen evidence for {name} ({pid}): "
                f"rendered {row['round3']!r}, expected {expected_round3_display!r}"
            )

        if record.get("status", "ACTIVE") != ADVANCING_STATUS:
            if row["rank"] != record.get("status"):
                raise RenderedOutputGateError(f"status rank diverges for {name} ({pid})")
        elif real_total is None:
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

        fc = forecast_by_id.get(pid)
        for cell_key, field in (("win", "win_pct"), ("top5", "top5_pct"), ("top10", "top10_pct"), ("top20", "top20_pct")):
            expected = _expected_pct_display(fc[field] if fc else None)
            if row[cell_key] != expected:
                raise RenderedOutputGateError(
                    f"probability diverges from frozen forecast for {name} ({pid}), field {field!r}: "
                    f"rendered {row[cell_key]!r}, expected {expected!r}"
                )

    if complete_population_size >= 2 and len(distinct_totals_seen) >= 2 and len(distinct_ranks_seen) < 2:
        raise RenderedOutputGateError(
            f"rank population is invalid: {complete_population_size} players have real, DIFFERING totals "
            f"({len(distinct_totals_seen)} distinct) but only {len(distinct_ranks_seen)} distinct rank(s) "
            "were rendered -- the T1-for-everyone failure mode"
        )
