"""BETA #001 R2 PRODUCTION HOMEPAGE — Section O. Renders the public
production page (root `docs/index.html` and the immutable
`docs/tournaments/2026/kg-ladies-open/r2/index.html`) from ALREADY
FROZEN, real CSV data only. This module never computes a probability,
never re-runs the simulation, and never touches the R1 historical
page — see scripts/deploy_r2_production_homepage.py for the real,
gated read-write orchestration.

======================================================================
VISUAL DIRECTION — deliberately distinct from the R1 page's theme
======================================================================
The real, immutable R1 page (docs/tournaments/2026/kg-ladies-open/r1/
index.html) uses a near-black theme (`--bg: #0b0d10`). This module
defines a SEPARATE, brighter palette (deep navy/charcoal, brighter
card surfaces, more whitespace) for the R2 production page only — the
R1 page's own markup/CSS is never read or modified by this module.
Same NEO wordmark identity, same font stack, same GA4 install
convention (script src + one gtag config call).

======================================================================
NO FABRICATED FIELDS ON THE PLAYER CARD
======================================================================
Only real fields present in the frozen R2 forecast CSV + the frozen
R1 CUT evaluation CSV + the frozen R1/PRE prediction sources are ever
rendered: player_name, real R2 rank/total score, real TOP20/TOP10/
TOP5/WIN, real R1 score-to-par, and the real PRE -> R1 -> R2 win%
history (each point only when its real source is available — never
interpolated). No SG, no course-fit score, no subjective rating.
"""
from __future__ import annotations

from klpga.neo_win.r2_html_render import render_r2_forecast_table_rows  # noqa: F401 (re-exported for callers)

PRODUCTION_CSS = """
  :root {
    --bg: #101a2c;
    --bg-alt: #16233c;
    --card-bg: #17253f;
    --border: #2b3a5a;
    --text: #f7f9fc;
    --text-dim: #aab6ce;
    --accent: #5fe0c7;
    --accent-blue: #6fa8ff;
    --pill-bg: #17394f;
    --pill-text: #6ee7b7;
    --row-alt: #14203a;
    --warn-bg: #3a2a17;
    --warn-text: #f2b866;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 32px 18px 72px;
    background: var(--bg);
    color: var(--text);
    font-family: "Noto Sans KR", sans-serif;
  }
  header, main, section.hero, section.calibration, section.forecast, footer { max-width: 980px; margin-left: auto; margin-right: auto; }
  header { margin-bottom: 28px; }

  .wordmark { --row: clamp(12px, 3vw, 16px); display: flex; align-items: center; gap: clamp(12px, 3.2vw, 20px); margin-bottom: 10px; }
  .wordmark-letters { display: flex; flex-direction: column; gap: calc(var(--row) * 0.15); flex-shrink: 0; }
  .letter-row { display: flex; align-items: baseline; gap: calc(var(--row) * 0.42); white-space: nowrap; }
  .letter { font-family: "Big Shoulders Display", sans-serif; font-weight: 800; font-size: calc(var(--row) * 1.15); line-height: 1; color: var(--accent); }
  .letter-word { font-family: "Big Shoulders Display", sans-serif; font-weight: 600; font-size: calc(var(--row) * 0.72); line-height: 1; letter-spacing: 0.04em; color: var(--text-dim); white-space: nowrap; }
  .wordmark-name { font-family: "Big Shoulders Display", sans-serif; font-weight: 800; font-size: calc(var(--row) * 3.75); line-height: 1; letter-spacing: 0.015em; color: var(--text); white-space: nowrap; }

  .meta { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 14px; }
  .meta .tournament-name { font-size: clamp(14px, 3.5vw, 18px); color: var(--text-dim); }
  .status-pill { background: var(--pill-bg); color: var(--pill-text); font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 999px; }

  section.hero { background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; padding: 28px 24px; margin-bottom: 24px; }
  section.hero h1 { font-family: "Big Shoulders Display", sans-serif; font-size: clamp(22px, 5vw, 30px); margin: 0 0 4px; }
  .hero-sub { color: var(--text-dim); font-size: 14px; margin: 0 0 20px; }
  .hero-primary-stat { background: var(--bg-alt); border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 18px; }
  .hero-primary-stat .big { font-family: "Roboto Mono", monospace; font-weight: 700; font-size: clamp(28px, 8vw, 40px); color: var(--accent); line-height: 1.15; }
  .hero-primary-stat .small { color: var(--text-dim); font-size: 13px; margin-top: 4px; }
  .hero-metrics { list-style: none; margin: 0 0 16px; padding: 0; display: flex; flex-wrap: wrap; gap: 10px; }
  .hero-metrics li { background: var(--pill-bg); color: var(--pill-text); padding: 6px 14px; border-radius: 999px; font-size: 13px; font-family: "Roboto Mono", monospace; }
  .hero-compare { font-size: 15px; margin: 0 0 14px; color: var(--text); }
  .hero-note { color: var(--text-dim); font-size: 13px; line-height: 1.7; margin: 0; border-top: 1px solid var(--border); padding-top: 14px; }

  section.calibration { margin-bottom: 24px; }
  section.calibration h2, section.forecast h2 { font-family: "Big Shoulders Display", sans-serif; font-size: clamp(18px, 4.5vw, 22px); margin: 0 0 4px; }
  section.forecast .forecast-sub { color: var(--text-dim); font-size: 13px; margin: 0 0 16px; }

  .table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 12px; background: var(--card-bg); }
  table { width: 100%; border-collapse: collapse; font-size: 14px; min-width: 480px; }
  thead th { text-align: left; font-weight: 600; color: var(--text-dim); background: var(--bg-alt); padding: 12px; border-bottom: 1px solid var(--border); white-space: nowrap; }
  tbody td { padding: 10px 12px; border-bottom: 1px solid var(--border); font-family: "Roboto Mono", monospace; white-space: nowrap; }
  tbody td.c-name { font-family: "Noto Sans KR", sans-serif; }
  tbody tr:nth-child(even) { background: var(--row-alt); }
  tbody td.c-pct { color: var(--accent-blue); font-weight: 600; }
  .cal-bucket-highlight td { color: var(--accent) !important; font-weight: 700; }

  footer { margin-top: 56px; padding-bottom: 8px; text-align: center; color: var(--text-dim); font-size: 11px; line-height: 1.7; }
  .footer-line { margin: 0; }

  @media (max-width: 480px) {
    body { padding: 20px 12px 48px; }
    table { font-size: 13px; }
    section.hero { padding: 20px 16px; }
    .wordmark { --row: 8px; }
    .wordmark-name { white-space: normal; line-height: 1.05; }
  }
"""


def _fmt_pct1(value) -> str:
    return "unavailable" if value is None else f"{value:.1f}%"


def render_production_hero_section(cut_summary: dict, threshold_survival: dict, calibration_rows: list[dict]) -> str:
    """Section 1 — "NEO 첫 실전 검증". Every number comes straight from
    the caller's already-real cut_summary/threshold_survival dicts
    (read from the frozen CUT evaluation CSV, never recomputed here).
    The explanation sentence is the fixed, real wording the task
    specified — never conditional on how good the numbers are."""
    n, m = threshold_survival["n_at_or_above"], threshold_survival["n_made_cut"]
    threshold_pct = threshold_survival["threshold_pct"]
    primary_stat_big = f"{threshold_pct:.0f}% 이상으로 예측한 {n}명"
    primary_stat_small = f"{m}명 전원 컷 통과" if m == n else f"{m}명 컷 통과"

    acc_text = _fmt_pct1(cut_summary.get("threshold_accuracy_pct"))
    brier = cut_summary.get("brier_score")
    brier_text = "unavailable" if brier is None else f"{brier:.4f}"
    mean_pred, actual_rate = cut_summary.get("mean_predicted_cut_pct"), cut_summary.get("actual_cut_rate_pct")
    compare_text = (
        "unavailable"
        if mean_pred is None or actual_rate is None
        else f"평균 예측 {mean_pred:.1f}% | 실제 컷 통과율 {actual_rate:.1f}%"
    )

    return f"""<section class="hero">
  <h1>NEO 첫 실전 검증</h1>
  <p class="hero-sub">1R 종료 후 공개한 컷 통과 확률, 실제 결과는?</p>
  <div class="hero-primary-stat">
    <div class="big">{primary_stat_big}</div>
    <div class="small">{primary_stat_small}</div>
  </div>
  <ul class="hero-metrics">
    <li>평가 대상 {cut_summary.get("n_evaluated", "unavailable")}명</li>
    <li>50% 기준 분류 정확도 {acc_text}</li>
    <li>Brier Score {brier_text}</li>
  </ul>
  <p class="hero-compare">{compare_text}</p>
  <p class="hero-note">높은 확률을 부여한 선수들의 생존은 잘 포착했지만, 전체적으로 컷 통과 가능성을 낮게 평가했다.
    BETA #001에서 확인된 첫 번째 개선 과제다.</p>
</section>"""


def render_calibration_section(calibration_rows: list[dict], highlight_threshold_pct: float = 40.0) -> str:
    """Section 2 — 예측 확률별 실제 컷 통과율. Renders the real,
    already-computed calibration buckets; the bucket(s) at/above
    `highlight_threshold_pct` are visually marked (never claims future
    certainty — purely a factual real-result table)."""
    rows_html = []
    for b in calibration_rows:
        try:
            bucket_lo = float(b["bucket"].split("-")[0])
        except (KeyError, ValueError, IndexError):
            bucket_lo = None
        row_class = " class=\"cal-bucket-highlight\"" if bucket_lo is not None and bucket_lo >= highlight_threshold_pct else ""
        avg_pred = "unavailable" if b.get("avg_predicted_pct") is None else f"{b['avg_predicted_pct']:.1f}%"
        actual = "unavailable" if b.get("actual_made_cut_rate_pct") is None else f"{b['actual_made_cut_rate_pct']:.1f}%"
        made = "-" if b.get("made_cut_count") is None else b["made_cut_count"]
        rows_html.append(
            f'<tr{row_class}><td>{b["bucket"]}</td><td>{b["n"]}</td><td>{made}</td><td>{avg_pred}</td><td>{actual}</td></tr>'
        )
    return f"""<section class="calibration">
  <h2>예측 확률별 실제 컷 통과율</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>예측 구간</th><th>인원</th><th>실제 통과</th><th>평균 예측</th><th>실제 통과율</th></tr></thead>
      <tbody>{"".join(rows_html)}</tbody>
    </table>
  </div>
</section>"""


def render_r2_forecast_section(table_rows_html: str) -> str:
    """Section 3 — 2R 종료 후 우승 경쟁 예측. `table_rows_html` is
    klpga.neo_win.r2_html_render.render_r2_forecast_table_rows's own
    output (reused unmodified) — this function only wraps it with the
    required title/subtitle and the production table shell."""
    return f"""<section class="forecast">
  <h2>2R 종료 후 우승 경쟁 예측</h2>
  <p class="forecast-sub">3R 시작 전 동결된 예측입니다. 이후 결과에 따라 수정하지 않습니다.</p>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>현재 순위</th>
          <th>선수</th>
          <th>스코어</th>
          <th>TOP20</th>
          <th>TOP10</th>
          <th>TOP5</th>
          <th>WIN</th>
        </tr>
      </thead>
      <tbody>{table_rows_html}</tbody>
    </table>
  </div>
</section>"""


def render_production_page(
    *,
    tournament_name: str,
    status_pill_text: str,
    hero_html: str,
    calibration_html: str,
    forecast_section_html: str,
    player_cards_html: str = "",
    include_player_card_assets: bool = True,
) -> str:
    """The full production homepage — SAME GA4 install convention as
    every other page this project publishes (script src + exactly one
    gtag config call), same NEO wordmark identity, brighter theme (see
    PRODUCTION_CSS)."""
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
<style>{PRODUCTION_CSS}</style>
{player_card_assets}

<header>
  <div class="wordmark">
    <div class="wordmark-letters">
      <div class="letter-row"><span class="letter">N</span><span class="letter-word">NUMBER</span></div>
      <div class="letter-row"><span class="letter">E</span><span class="letter-word">EVIDENCE</span></div>
      <div class="letter-row"><span class="letter">O</span><span class="letter-word">ORACLE</span></div>
    </div>
    <div class="wordmark-name">TOURNAMENT PREDICTION</div>
  </div>
  <div class="meta">
    <span class="tournament-name">{tournament_name}</span>
    <span class="status-pill">{status_pill_text}</span>
  </div>
</header>

<main>
  {hero_html}
  {calibration_html}
  {forecast_section_html}
</main>

{player_cards_html}

<footer>
  <div class="footer-line">&copy; 2026 NEO GOLF DATA. All Rights Reserved.</div>
  <div class="footer-line">Predictions and probability models are proprietary to NEO GOLF DATA.</div>
  <div class="footer-line">Tournament results and player information are based on publicly available data.</div>
</footer>
"""
