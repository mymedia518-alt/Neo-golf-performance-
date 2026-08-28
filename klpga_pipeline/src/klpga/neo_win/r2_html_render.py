"""BETA #001 R1 -> R2 evaluation pipeline, Sections H & I: the R2
production HTML page (reusing the exact dark-theme/wordmark visual
design already published at docs/index.html / docs/tournaments/2026/
kg-ladies-open/r1/index.html) plus the auto-generated "R1 MODEL CHECK"
scorecard section.

======================================================================
NEVER READS OR WRITES THE REAL PRODUCTION FILES
======================================================================
This module has ZERO code coupling to docs/index.html or docs/
tournaments/2026/kg-ladies-open/r1/index.html — the CSS/header/footer
markup below is a plain string constant, copied once from the already-
committed, real R1 page's own `<style>`/`<header>`/`<footer>` markup,
never parsed or imported from those files. Nothing here ever opens
docs/index.html or the R1 historical snapshot for writing; the caller
(scripts/run_beta001_r2_update.py) decides where output goes, and per
Section H/L that is NEVER a real production path during a dry run.

======================================================================
NO FABRICATED PLACEHOLDER VALUES
======================================================================
Every function here renders EXACTLY the data it is handed — a caller
with no real R2 evaluation yet (dry run, or a real R2 that hasn't
happened) must not call `render_r1_model_scorecard_section` with
invented numbers; there is no default/example data baked in here.
"""
from __future__ import annotations

from typing import Optional

R1_FROZEN_DISCLOSURE_SENTENCE = "R1 predictions were frozen before Round 2 results were known."

_CSS = """
  :root {
    --bg: #0b0d10;
    --bg-alt: #14171c;
    --border: #22262d;
    --text: #f2f4f6;
    --text-dim: #8b93a1;
    --accent: #4fd1c5;
    --pill-bg: #163a2e;
    --pill-text: #4ade80;
    --row-alt: #101317;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 24px 16px 60px;
    background: var(--bg);
    color: var(--text);
    font-family: "Noto Sans KR", sans-serif;
  }
  header { max-width: 960px; margin: 0 auto 20px; }
  main { max-width: 960px; margin: 0 auto; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { padding: 8px 10px; border-bottom: 1px solid var(--border); text-align: left; }
  .c-pos, .c-score, .c-pct { text-align: right; font-family: "Roboto Mono", monospace; }
  .row-alt { background: var(--row-alt); }
  .status-pill { background: var(--pill-bg); color: var(--pill-text); padding: 2px 10px; border-radius: 999px; font-size: 12px; }
  .meta { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
  .tournament-name { font-weight: 700; }
  section.scorecard { max-width: 960px; margin: 40px auto 0; border-top: 1px solid var(--border); padding-top: 24px; }
  section.scorecard h2 { font-size: 16px; }
  section.scorecard h3 { font-size: 13px; color: var(--text-dim); margin-top: 20px; }
  section.scorecard .disclosure { color: var(--text-dim); font-size: 12px; margin-top: 16px; }
  section.scorecard table { font-size: 13px; }
  footer {
    max-width: 960px;
    margin: 48px auto 0;
    padding-bottom: 8px;
    text-align: center;
    color: var(--text-dim);
    font-size: 11px;
    line-height: 1.7;
  }
  .footer-line { margin: 0; }
"""


def _fmt_score(score_to_par: Optional[float]) -> str:
    if score_to_par is None:
        return "unavailable"
    if score_to_par == 0:
        return "E"
    return f"+{int(score_to_par)}" if score_to_par > 0 else str(int(score_to_par))


def _fmt_pct(value: Optional[float]) -> str:
    return "unavailable" if value is None else f"{value:.2f}%"


def render_r2_table_rows(entrants: list[dict], *, clickable: bool = False) -> str:
    """`entrants`: [{"position", "player_name", "score_to_par",
    "win_pct", "make_cut_pct"}, ...] already sorted by the caller —
    this function never re-sorts or re-derives ranking.

    `clickable=False` (default) preserves the exact original output —
    a plain `<td class="c-name">`. `clickable=True` (Korean UI + player
    card task) requires `"player_code"` on every entrant and renders
    the name cell via klpga.neo_win.player_card.render_player_name_cell
    instead — a real `<button>`, readable as plain text with no
    JavaScript, wrapping the SAME `td.c-name` cell so table layout is
    unaffected."""
    rows = []
    for e in entrants:
        if clickable:
            from klpga.neo_win.player_card import render_player_name_cell

            name_cell = render_player_name_cell(e["player_code"], e["player_name"])
        else:
            name_cell = f'<td class="c-name">{e["player_name"]}</td>'
        rows.append(
            f'<tr><td class="c-pos">{e["position"]}</td>{name_cell}'
            f'<td class="c-score">{_fmt_score(e.get("score_to_par"))}</td>'
            f'<td class="c-pct">{_fmt_pct(e.get("win_pct"))}</td>'
            f'<td class="c-pct">{_fmt_pct(e.get("make_cut_pct"))}</td></tr>'
        )
    return "".join(rows)


def render_r1_model_scorecard_section(
    cut_summary: dict,
    calibration_rows: list[dict],
    top5: dict,
    win_interim: dict,
    round_condition: dict,
) -> str:
    """Section I's exact required structure: NEO GOLF DATA / BETA #001
    — R1 MODEL CHECK / CUT PREDICTION stats / CALIBRATION per-bucket /
    BEST PREDICTIONS / BIGGEST MISSES / R1 WIN% INTERIM CHECK / ROUND
    CONDITION / the fixed disclosure sentence. Every value comes
    straight from the caller's already-computed summary dicts (cut_
    evaluation.summarize_cut_evaluation / calibration_report, r1_r2_
    evaluation_report.top5_best_and_biggest_misses, win_interim_check.
    win_interim_summary, round_condition_metadata) — nothing is
    recomputed or invented here."""
    def _bucket_pct(value: Optional[float], *, signed: bool = False) -> str:
        if value is None:
            return "unavailable"
        return f"{value:+.2f}%" if signed else f"{value:.2f}%"

    calibration_html = "".join(
        f'<tr><td>{b["bucket"]}</td><td>{b["n"]}</td>'
        f'<td>{_bucket_pct(b["avg_predicted_pct"])}</td>'
        f'<td>{_bucket_pct(b["actual_made_cut_rate_pct"])}</td>'
        f'<td>{_bucket_pct(b["calibration_gap_pct"], signed=True)}</td></tr>'
        for b in calibration_rows
    )
    best_html = "".join(
        f'<li>{p["player_name"]} ({p["player_code"]}) — error {p["absolute_probability_error"]:.4f}</li>'
        for p in top5["top5_best"]
    )
    misses_html = "".join(
        f'<li>{p["player_name"]} ({p["player_code"]}) — error {p["absolute_probability_error"]:.4f}</li>'
        for p in top5["top5_biggest_misses"]
    )

    spearman = win_interim.get("spearman_rank_correlation")
    spearman_text = "N/A (fewer than 2 resolved players)" if spearman is None else f"{spearman:.4f}"

    return f"""<section class="scorecard">
  <h2>NEO GOLF DATA — BETA #001 — R1 MODEL CHECK</h2>

  <h3>CUT PREDICTION</h3>
  <ul>
    <li>Evaluated players: {cut_summary["n_evaluated"]} / {cut_summary["n_r1_players"]}</li>
    <li>Actual made cut: {cut_summary["actual_made_cut_count"]}</li>
    <li>Actual missed cut: {cut_summary["actual_missed_cut_count"]}</li>
    <li>Threshold (50%) accuracy: {"unavailable" if cut_summary["threshold_accuracy_pct"] is None else f'{cut_summary["threshold_accuracy_pct"]:.2f}%'}</li>
    <li>Brier score: {"unavailable" if cut_summary["brier_score"] is None else cut_summary["brier_score"]}</li>
    <li>Log loss: {"unavailable" if cut_summary["log_loss"] is None else cut_summary["log_loss"]}</li>
    <li>WD: {cut_summary["wd_count"]}, DQ: {cut_summary["dq_count"]}, unresolved: {cut_summary["unresolved_count"]}</li>
  </ul>

  <h3>CALIBRATION</h3>
  <table>
    <thead><tr><th>Bucket</th><th>n</th><th>Avg predicted</th><th>Actual rate</th><th>Gap</th></tr></thead>
    <tbody>{calibration_html}</tbody>
  </table>

  <h3>BEST PREDICTIONS</h3>
  <ul>{best_html}</ul>

  <h3>BIGGEST MISSES</h3>
  <ul>{misses_html}</ul>

  <h3>R1 WIN% INTERIM CHECK</h3>
  <p>{win_interim["label"]}</p>
  <ul>
    <li>Spearman rank correlation (R1 WIN% rank vs. R2 leaderboard position): {spearman_text}</li>
    <li>Resolved players: {win_interim["n_with_resolved_r2_position"]} / {win_interim["n_r1_players"]}</li>
  </ul>

  <h3>ROUND CONDITION</h3>
  <ul>
    <li>Date: {round_condition["date"]}</li>
    <li>Weather: {round_condition["weather"]}</li>
    <li>Green condition: {round_condition["green_condition"]}</li>
    <li>Play status at observation: {round_condition["play_status_at_observation"]}</li>
    <li>Source: {round_condition["source_type"]}</li>
  </ul>

  <p class="disclosure">{R1_FROZEN_DISCLOSURE_SENTENCE}</p>
</section>"""


def render_r2_page(
    *,
    tournament_name: str,
    status_pill_text: str,
    table_rows_html: str,
    scorecard_html: str,
    player_cards_html: str = "",
    include_player_card_assets: bool = False,
) -> str:
    """Full R2 HTML page — same wordmark/header/footer shell as the
    real, already-published R1 page, GA4 snippet included (project-
    wide requirement, same install as the committed R1/production
    pages).

    `player_cards_html`/`include_player_card_assets` are additive,
    opt-in (Korean UI + player card task): when
    `include_player_card_assets=True`, the player card CSS and event-
    delegation JS (klpga.neo_win.player_card) are injected once;
    `player_cards_html` is the concatenation of each entrant's already-
    rendered hidden card panel (klpga.neo_win.player_card.
    render_player_card_html). Both default to off/empty, so existing
    callers (and existing tests) get byte-identical output."""
    player_card_assets = ""
    if include_player_card_assets:
        from klpga.neo_win.player_card import PLAYER_CARD_CSS, render_player_card_js

        player_card_assets = f"<style>{PLAYER_CARD_CSS}</style><script>{render_player_card_js()}</script>"

    return f"""<script async src="https://www.googletagmanager.com/gtag/js?id=G-WVX07966WS"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-WVX07966WS');
</script>
<title>NEO R2 Tournament Prediction</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;800&amp;family=Noto+Sans+KR:wght@400;500;700&amp;family=Roboto+Mono:wght@400;600&amp;display=swap" rel="stylesheet">
<style>{_CSS}</style>
{player_card_assets}

<header>
  <div class="header-top">
    <div class="wordmark">
      <div class="wordmark-letters">
        <div class="letter-row"><span class="letter">N</span><span class="letter-word">NUMBER</span></div>
        <div class="letter-row"><span class="letter">E</span><span class="letter-word">EVIDENCE</span></div>
        <div class="letter-row"><span class="letter">O</span><span class="letter-word">ORACLE</span></div>
      </div>
      <div class="wordmark-name">TOURNAMENT PREDICTION</div>
    </div>
  </div>
  <div class="meta">
    <span class="tournament-name">{tournament_name}</span>
    <span class="status-pill">{status_pill_text}</span>
  </div>
</header>

<main>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>순위</th>
          <th>선수</th>
          <th>스코어</th>
          <th>우승확률</th>
          <th>컷 통과확률</th>
        </tr>
      </thead>
      <tbody>{table_rows_html}</tbody>
    </table>
  </div>
</main>

{scorecard_html}

{player_cards_html}

<footer>
  <div class="footer-line">&copy; 2026 NEO GOLF DATA. All Rights Reserved.</div>
  <div class="footer-line">Predictions and probability models are proprietary to NEO GOLF DATA.</div>
  <div class="footer-line">Tournament results and player information are based on publicly available data.</div>
</footer>
"""
