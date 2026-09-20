"""KB FINAL BUILD: the real-data public FINAL page renderer.

Mirrors klpga.neo_win.r3_real_page's own conventions exactly -- same
design system (docs/assets/neo.css / neo-site.css, no new CSS classes),
same sponsor-invariant helper (render_player_identity), same shell/
breadcrumb/global-nav machinery. A pure renderer: it invents nothing
and computes nothing itself -- every number comes from one of the two
already-validated inputs (the OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT
evidence file and the ExtendedFinalComparison the caller already
computed via final_partial_evidence_validator.run_extended_comparison).

SCOPE, stated explicitly and repeatedly in the public copy itself (per
the operator's own instruction): this is NOT the complete 70-player
FINAL leaderboard. It covers exactly the positions the evidence file's
own `positions_confirmed_gapless_through` reports (39 for this
tournament) -- every heading that could be mistaken for "complete
results" is qualified with "상위 N명 공식 결과 기준".

Never exposes internal state in the public HTML: no SHA/hash, no
evidence-tier name, no file path, no "review_required"/QA-state word,
no build/commit id. See test_final_real_page.py's leakage test for the
enforced forbidden-string list.
"""
from __future__ import annotations

from klpga.website_v2.global_navigation import inject_global_navigation
from klpga.website_v2.player_identity import render_player_identity
from klpga.website_v2.shell import breadcrumb_html

EMPTY_MARK = "—"
STAGE_READY_META = '<meta name="neo-stage-publication-ready" content="true">'


def _to_par_display(v) -> str:
    if v is None:
        return EMPTY_MARK
    n = int(v)
    if n == 0:
        return "E"
    return f"+{n}" if n > 0 else str(n)


def _pct_display(v) -> str:
    if v is None:
        return EMPTY_MARK
    return f"{v * 100:.0f}%"


def _score_line(record: dict) -> str:
    total = record.get("final_total_strokes")
    to_par = _to_par_display(record.get("final_to_par"))
    if total is None:
        return to_par
    return f"{to_par} ({total})"


def _r4_display(record: dict) -> str:
    strokes = record.get("r4_strokes")
    if strokes is None:
        return EMPTY_MARK
    to_par = _to_par_display(record.get("r4_to_par"))
    return f"{strokes} ({to_par})" if to_par != EMPTY_MARK else str(strokes)


def render_final_real_page(
    *,
    tournament_name: str,
    game_code: str,
    date_range: str,
    evidence: dict,
    comparison,
    overestimated: list,
    underestimated: list,
) -> str:
    scope_through = evidence["positions_confirmed_gapless_through"]
    scope_label = f"FINAL 상위 {scope_through}명 공식 결과 기준"
    records = sorted(evidence["confirmed_records"], key=lambda r: r["position_from"])
    sponsor_by_id = {str(r["player_id"]): r.get("sponsor") for r in records if r.get("player_id")}

    winner_record = next(r for r in records if str(r["final_rank"]) == "1")
    winner_score_line = _score_line(winner_record)

    # ---------------- Leaderboard rows ----------------
    rows_html = []
    for row in records:
        identity = render_player_identity(row["player_name"], row.get("sponsor"), quote="'")
        rows_html.append(
            f"<tr data-player-id='{row['player_id']}'>"
            f"<td data-label='순위'>{row['final_rank']}</td>"
            f"<th scope='row' data-label='선수'>{identity}</th>"
            f"<td data-label='최종스코어'>{_score_line(row)}</td>"
            f"<td data-label='FR'>{_r4_display(row)}</td>"
            "</tr>"
        )

    # ---------------- Forecast vs result (headline players) ----------------
    forecast_rows = []
    highlight_ids = {comparison.winner_player_id} | {c.player_id for c in (overestimated + underestimated)}
    ordered_confirmed = sorted(comparison.confirmed_players, key=lambda c: c.neo_predicted_rank)
    for c in ordered_confirmed[:5] + [c for c in ordered_confirmed if c.player_id in highlight_ids and c.neo_predicted_rank > ordered_confirmed[4].neo_predicted_rank]:
        forecast_rows.append(
            "<tr>"
            f"<th scope='row' data-label='선수'>{render_player_identity(c.player_name, sponsor_by_id.get(c.player_id), quote=chr(39))}</th>"
            f"<td data-label='R3 종료 NEO 우승확률'>{c.neo_win_probability_pct:.1f}% (예상 {c.neo_predicted_rank}위)</td>"
            f"<td data-label='FINAL 결과'>{c.actual_final_rank}위</td>"
            "</tr>"
        )

    # ---------------- Validation stats ----------------
    def _stat_row(k: int) -> str:
        t = comparison.topk[k]
        return (
            "<tr>"
            f"<td data-label='구간'>Top{k}</td>"
            f"<td data-label='정밀도'>{_pct_display(t.precision)}</td>"
            f"<td data-label='재현율'>{_pct_display(t.recall)}</td>"
            "</tr>"
        )

    validation_rows = "".join(_stat_row(k) for k in (5, 10, 20))

    # ---------------- Movers ----------------
    def _mover_item(c) -> str:
        arrow = "▲" if c.rank_delta > 0 else "▼"
        return f"<li>{render_player_identity(c.player_name, sponsor_by_id.get(c.player_id), quote=chr(39))} <span class='win'>{arrow} NEO 예상 {c.neo_predicted_rank}위 → FINAL {c.actual_position_from}위</span></li>"

    rise_html = "".join(_mover_item(c) for c in underestimated)
    fall_html = "".join(_mover_item(c) for c in overestimated)

    # ---------------- Why the winner won (strictly data-backed) ----------------
    winner_comparison = next(c for c in comparison.confirmed_players if c.player_id == comparison.winner_player_id)
    why_points = [
        f"{winner_record['player_name']}는 R3 종료 시점 NEO 예상 우승확률 {winner_comparison.neo_win_probability_pct:.1f}%(예상 {winner_comparison.neo_predicted_rank}위)로 우승 후보 중 하나였다.",
        f"3라운드까지는 선두가 아니었으나(2위권), 최종 라운드 {_r4_display(winner_record)}로 마무리하며 우승을 확정했다.",
    ]
    why_html = "".join(f"<li>{p}</li>" for p in why_points)

    breadcrumb = breadcrumb_html(tournament_name, None, "FINAL")
    body = (
        f"{breadcrumb}"
        '<section class="hero" id="tournament"><div><p class="eyebrow">FINAL</p>'
        f"<h1>{tournament_name}</h1><p class=\"meta\">{date_range}</p>"
        f"<p class=\"meta\">우승 {render_player_identity(winner_record['player_name'], winner_record.get('sponsor'), quote=chr(39))} {winner_score_line}</p></div>"
        '<strong class="status">FINAL</strong></section>'
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/pre/">사전 분석 PRE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/r1/">R1</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/r2/">R2</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/r3/">R3</a></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">FR</span></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/final/" aria-current="page">FINAL</a></li>'
        '</ol></nav>'
        '<section class="panel leaderboard-panel" id="final-leaderboard">'
        f'<div class="leaderboard-head"><h2>FINAL 리더보드</h2><p class="note">{scope_label}</p></div>'
        '<div class="table-wrap"><table class="data leaderboard-table"><thead><tr>'
        "<th>순위</th><th>선수</th><th>최종스코어</th><th>FR</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div>"
        "</section>"
        '<section class="product-section" id="forecast-vs-result">'
        f'<h2>NEO R3 예측 vs FINAL 결과</h2><p class="note">{scope_label}</p>'
        '<div class="table-wrap"><table class="data"><thead><tr>'
        "<th>선수</th><th>R3 종료 NEO 우승확률</th><th>FINAL 결과</th>"
        "</tr></thead><tbody>" + "".join(forecast_rows) + "</tbody></table></div>"
        "</section>"
        '<section class="product-section" id="neo-validation">'
        f'<h2>NEO 검증</h2><p class="note">{scope_label}</p>'
        '<div class="table-wrap"><table class="data"><thead><tr>'
        "<th>구간</th><th>정밀도</th><th>재현율</th>"
        "</tr></thead><tbody>" + validation_rows + "</tbody></table></div>"
        "</section>"
        '<section class="product-section" id="biggest-movers">'
        "<h2>주요 순위 변동</h2>"
        f"<h3>상승</h3><ul>{rise_html}</ul>"
        f"<h3>하락</h3><ul>{fall_html}</ul>"
        "</section>"
        '<section class="product-section" id="why-the-winner-won">'
        "<h2>우승 포인트</h2>"
        f"<ul>{why_html}</ul>"
        "</section>"
    )

    shell = (
        "<!doctype html><html lang=\"ko\"><head>"
        f"{STAGE_READY_META}"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>NEO GOLF DATA · {tournament_name} FINAL</title>"
        "<link rel=\"stylesheet\" href=\"/assets/neo-site.css\">"
        "<link rel=\"stylesheet\" href=\"/assets/neo.css\">"
        "</head><body>"
        f"<main>{body}</main>"
        "<footer class=\"site-footer\"><div class=\"site-footer__inner\">"
        "<p class=\"site-footer__copyright\">© 2026 NEO GOLF DATA. All Rights Reserved.</p>"
        "</div></footer>"
        "</body></html>"
    )
    return inject_global_navigation(shell, active_section="tournaments")


def is_final_real_page(html: str) -> bool:
    return STAGE_READY_META in html and 'id="final-leaderboard"' in html


# ----------------------------------------------------------------
# GENERIC extension (Hana 2026090002 FINAL build, 2026-09-20): the
# forecast-vs-result / validation / movers sections, usable by ANY
# tournament that has a COMPLETE official FINAL truth (final_truth.py)
# rather than only a partial/screenshot-evidence tier -- unlike
# render_final_real_page above (built for KB's specific partial-field
# scenario), this takes already-computed, generic inputs (plain dicts,
# no ExtendedFinalComparison/evidence-file coupling) so a caller with a
# full 64-player (or any N-player) FinalTruth + FinalValidationResult
# can reuse the SAME design system (render_player_identity, the same
# CSS classes/table markup) without forking a new one-off page. The
# caller (e.g. scripts/181_build_hana_final_page.py) owns its own
# leaderboard shell/hero/stage-nav to match that tournament's own
# already-established visual convention exactly; this function only
# supplies the three FINAL-specific sections below it.
# ----------------------------------------------------------------


def render_final_validation_sections(
    *,
    scope_label: str,
    top_candidates: list,  # [{player_name, sponsor, neo_win_probability_pct, neo_predicted_rank, actual_final_rank}]
    topk_stats: dict,  # {5: {"precision":.., "recall":.., "predicted_population":.., "actual_population":..}, 10:.., 20:..}
    metrics: dict,  # {"brier_norm":.., "log_loss":.., "rank_mae":.., "reciprocal_rank":..}
    positive_surprises: list,  # [{player_name, sponsor, predicted_rank, final_rank}]
    negative_surprises: list,
) -> str:
    forecast_rows = "".join(
        "<tr>"
        f"<th scope='row' data-label='선수'>{render_player_identity(c['player_name'], c.get('sponsor'), quote=chr(39))}</th>"
        f"<td data-label='PRE-FINAL NEO 우승확률'>{c['neo_win_probability_pct']:.2f}% (예상 {c['neo_predicted_rank']}위)</td>"
        f"<td data-label='FINAL 결과'>{c['actual_final_rank']}위</td>"
        "</tr>"
        for c in top_candidates
    )

    def _topk_row(k: int) -> str:
        t = topk_stats[k]
        pop_note = f" ({t['actual_population']}명)" if t.get("actual_population") != k else ""
        return (
            "<tr>"
            f"<td data-label='구간'>Top{k}{pop_note}</td>"
            f"<td data-label='정밀도'>{t['precision'] * 100:.0f}%</td>"
            f"<td data-label='재현율'>{t['recall'] * 100:.0f}%</td>"
            "</tr>"
        )

    validation_rows = "".join(_topk_row(k) for k in (5, 10, 20))

    def _mover_item(m: dict, arrow: str) -> str:
        return (
            f"<li>{render_player_identity(m['player_name'], m.get('sponsor'), quote=chr(39))} "
            f"<span class='win'>{arrow} NEO 예상 {m['predicted_rank']}위 → FINAL {m['final_rank']}위</span></li>"
        )

    rise_html = "".join(_mover_item(m, "▲") for m in positive_surprises)
    fall_html = "".join(_mover_item(m, "▼") for m in negative_surprises)

    return (
        '<section class="product-section" id="forecast-vs-result">'
        f'<h2>NEO PRE-FINAL 예측 vs FINAL 결과</h2><p class="note">{scope_label}</p>'
        '<div class="table-wrap"><table class="data"><thead><tr>'
        "<th>선수</th><th>PRE-FINAL NEO 우승확률</th><th>FINAL 결과</th>"
        "</tr></thead><tbody>" + forecast_rows + "</tbody></table></div>"
        "</section>"
        '<section class="product-section" id="neo-validation">'
        f'<h2>NEO 검증</h2><p class="note">{scope_label} · Brier(norm) {metrics["brier_norm"]:.4f} · '
        f'Log Loss {metrics["log_loss"]:.4f} · Rank MAE {metrics["rank_mae"]:.2f} · '
        f'Reciprocal Rank {metrics["reciprocal_rank"]:.3f}</p>'
        '<div class="table-wrap"><table class="data"><thead><tr>'
        "<th>구간</th><th>정밀도</th><th>재현율</th>"
        "</tr></thead><tbody>" + validation_rows + "</tbody></table></div>"
        "</section>"
        '<section class="product-section" id="biggest-movers">'
        "<h2>주요 순위 변동</h2>"
        f"<h3>상승 (NEO 예상보다 선전)</h3><ul>{rise_html}</ul>"
        f"<h3>하락 (NEO 예상보다 부진)</h3><ul>{fall_html}</ul>"
        "</section>"
    )
