"""BETA #001 R2 PRODUCTION DEPLOYMENT — Section O's hard-validation
gate. Every function here is a pure, independently-testable check
against ALREADY-FROZEN real data (the CUT evaluation CSV, the R2
forecast CSV, the rendered HTML) — none of them recompute a
probability or touch the model. Mirrors the {"check", "passed",
"detail"} shape klpga.neo_win.r2_pipeline_validation already
established, reusable with the same run_all_validations aggregator.
"""
from __future__ import annotations

import re

_GA4_ID = "G-WVX07966WS"
_WD_LIKE_STATUSES = frozenset({"WD", "WD_AFTER_R1_START", "DQ"})


def check_forecast_population_matches_expected(forecast_rows: list[dict], expected_population: int | None) -> dict:
    """`expected_population` is a real number the CALLER supplies (from
    the real Round 3 grouping count they already confirmed) — never a
    number this function assumes or hardcodes. Passes trivially (with
    the real count reported) if the caller doesn't supply one."""
    n = len(forecast_rows)
    passed = expected_population is None or n == expected_population
    return {
        "check": "FORECAST_POPULATION_MATCHES_EXPECTED",
        "passed": passed,
        "detail": f"forecast_row_count={n} expected_population={expected_population}",
    }


def check_win_sum_from_source(forecast_rows: list[dict], tolerance: float = 1.0) -> dict:
    total = sum(r["win_pct"] for r in forecast_rows)
    passed = (not forecast_rows) or abs(total - 100.0) <= tolerance
    return {"check": "WIN_SUM_FROM_SOURCE_APPROXIMATELY_100", "passed": passed, "detail": f"sum={total}"}


def check_monotonicity_from_source(forecast_rows: list[dict]) -> dict:
    bad = [r["player_code"] for r in forecast_rows if not (r["win_pct"] <= r["top5_pct"] <= r["top10_pct"] <= r["top20_pct"])]
    return {
        "check": "MONOTONICITY_FROM_SOURCE_WIN_LE_TOP5_LE_TOP10_LE_TOP20",
        "passed": len(bad) == 0,
        "detail": f"bad={bad}",
    }


def check_no_excluded_status_players_in_forecast(forecast_rows: list[dict], cut_eval_rows: list[dict]) -> dict:
    """No player whose real CUT-evaluation status is WD / WD_AFTER_R1_START
    / DQ / MISSED_CUT may appear in the R2 forecast — cross-referenced
    by player_code (never by name) against the real CUT evaluation
    CSV's own actual_r2_status column."""
    excluded_codes = {
        row["player_code"] for row in cut_eval_rows
        if row.get("actual_r2_status") in _WD_LIKE_STATUSES or row.get("actual_r2_status") == "MISSED_CUT"
    }
    forecast_codes = {r["player_code"] for r in forecast_rows}
    leaked = sorted(forecast_codes & excluded_codes)
    return {
        "check": "NO_WD_OR_MISSED_CUT_PLAYERS_IN_FORECAST",
        "passed": len(leaked) == 0,
        "detail": f"leaked_player_codes={leaked}",
    }


def check_probabilities_render_exactly(forecast_rows: list[dict], rendered_html: str) -> dict:
    """Round-trips every forecast row's 4 percentages through the
    rendered HTML and confirms the exact same 2dp value appears —
    catches any accidental transformation between the source CSV and
    the published page."""
    bad = []
    for r in forecast_rows:
        for field in ("top20_pct", "top10_pct", "top5_pct", "win_pct"):
            needle = f"{r[field]:.2f}%"
            if needle not in rendered_html:
                bad.append(f"{r['player_code']}:{field}={needle}")
    return {"check": "PROBABILITIES_RENDER_EXACTLY_AS_IN_SOURCE_CSV", "passed": len(bad) == 0, "detail": f"missing={bad}"}


def check_ga4_present_exactly_once(rendered_html: str) -> dict:
    """"Exactly once" means one <script src> tag plus one gtag('config', ...)
    call for the SAME measurement ID — 2 literal occurrences of the ID
    string, matching this project's own established GA4 install
    convention (see every other rendered page)."""
    count = rendered_html.count(_GA4_ID)
    return {"check": "GA4_PRESENT_EXACTLY_ONCE", "passed": count == 2, "detail": f"occurrences={count} (expected 2)"}


def check_player_card_present_for_every_row(forecast_rows: list[dict], rendered_html: str) -> dict:
    missing = [r["player_code"] for r in forecast_rows if f'data-player-code="{r["player_code"]}"' not in rendered_html]
    return {"check": "PLAYER_CARD_PRESENT_FOR_EVERY_ROW", "passed": len(missing) == 0, "detail": f"missing={missing}"}


_ROW_PCT_RE = re.compile(r'<td class="c-pct">([\d.]+)%</td>')


def check_no_fabricated_extra_rows(forecast_rows: list[dict], rendered_html: str) -> dict:
    """The rendered table must contain EXACTLY the CSV's own row count
    of percentage cells (4 per row: TOP20/TOP10/TOP5/WIN) — never more
    (an invented row) and never fewer (a silently dropped row)."""
    expected = len(forecast_rows) * 4
    actual = len(_ROW_PCT_RE.findall(rendered_html))
    return {
        "check": "NO_FABRICATED_OR_DROPPED_FORECAST_ROWS",
        "passed": actual == expected,
        "detail": f"expected_pct_cells={expected} actual_pct_cells={actual}",
    }


def _fmt_score_to_par_for_check(value: int) -> str:
    if value == 0:
        return "E"
    return f"+{value}" if value > 0 else str(value)


def check_score_to_par_matches_par_arithmetic(forecast_rows: list[dict], par_total: int, rendered_html: str) -> dict:
    """스코어 (to-par) is never a separately estimated value -- it must
    equal the already-official cumulative r2_total_score (합계타수) minus
    par_total, for every real row, and that exact E/-N/+N string must
    appear verbatim in the rendered page. Also confirms 0 always renders
    as 'E', never '+0'."""
    bad = []
    for r in forecast_rows:
        total = r["r2_total_score"]
        if total is None:
            continue
        expected_score_to_par = total - par_total
        expected_str = _fmt_score_to_par_for_check(expected_score_to_par)
        needle = f'<td class="c-topar">{expected_str}</td>'
        if needle not in rendered_html:
            bad.append(f"{r['player_code']}:total={total}:expected_score_to_par={expected_str}")
    return {
        "check": "SCORE_TO_PAR_MATCHES_PAR_ARITHMETIC",
        "passed": len(bad) == 0,
        "detail": f"par_total={par_total} mismatches={bad}",
    }
