"""NEO GOLF DATA — Korean-first mobile player card MVP.

Reuses `klpga.neo_win.cut_evaluation`'s CUT_OUTCOME_* vocabulary for
decided cut states (MADE/MISSED/WD/DQ/UNRESOLVED) rather than
inventing a second set of status strings — this module adds only
CUT_STATUS_PENDING, the one state cut_evaluation has no concept of
(R1, before the cut is officially known, when a CUT % probability is
still meaningful to show).

======================================================================
NEVER SHOW A FUTURE CUT PROBABILITY AFTER THE CUT IS DECIDED
======================================================================
`render_player_card_html` enforces this defensively: `cut_pct` is
rendered ONLY when `cut_status == CUT_STATUS_PENDING`, regardless of
what the caller passed — once a real decided status exists there is no
"probability" left, only a fact.

======================================================================
NEVER FABRICATE MISSING PROBABILITY-HISTORY STAGES
======================================================================
`probability_history` renders exactly the stages it is given, in
STAGE_DISPLAY_LABELS order — a stage that hasn't happened yet (or was
never supplied) is simply absent from the row, never interpolated or
guessed. `sample_size_rounds`/`expected_round_score`/
`consistency_stddev`/`total_score_to_par` each render only when not
None — a missing metric is omitted, never shown as 0 or blank text.

======================================================================
WHY_TEXT — only the two stages this task's spec actually gives wording
for
======================================================================
`build_why_text` supports exactly "R1" and "R2" (the task's own
verbatim example sentences) and raises ValueError for any other stage
— this module never invents an explanatory sentence for a stage the
task didn't specify wording for.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from klpga.neo_win.cut_evaluation import (
    CUT_OUTCOME_DQ,
    CUT_OUTCOME_MADE,
    CUT_OUTCOME_MISSED,
    CUT_OUTCOME_UNRESOLVED,
    CUT_OUTCOME_WD,
)
from klpga.neo_win.korean_ui_labels import BRAND_NAME, KOREAN_LABELS, STAGE_DISPLAY_LABELS

CUT_STATUS_PENDING = "PENDING"

_WHY_TEXT_BY_STAGE = {
    "R1": "대회 이전 경기력과 1라운드 실제 결과를 바탕으로\n남은 라운드를 시뮬레이션한 우승 확률입니다.",
    "R2": "대회 이전 경기력과 1·2라운드 실제 결과를 바탕으로\n남은 라운드를 시뮬레이션한 우승 확률입니다.",
}


def build_why_text(stage: str) -> str:
    if stage not in _WHY_TEXT_BY_STAGE:
        raise ValueError(
            f"No approved WHY-explanation wording exists for stage={stage!r} — only "
            f"{sorted(_WHY_TEXT_BY_STAGE)} are specified. Never invent explanatory text for a "
            "stage the task didn't give wording for."
        )
    return _WHY_TEXT_BY_STAGE[stage]


@dataclass(frozen=True)
class ProbabilityHistoryPoint:
    stage: str
    """One of STAGE_DISPLAY_LABELS' keys: 'PRE'/'R1'/'R2'/'R3'."""
    win_pct: float


@dataclass(frozen=True)
class RoundScoreRow:
    round_number: int
    round_score: int
    score_to_par: int


@dataclass(frozen=True)
class PlayerCardData:
    player_code: str
    player_name: str
    tournament_name: str
    stage_display: str
    """Already-Korean display text for the current stage, e.g. '2라운드'
    or '대회 전' — the card header shows "{tournament_name} · {stage_display}"."""
    win_pct: Optional[float] = None
    current_position: Optional[str] = None
    current_score_to_par: Optional[int] = None
    cut_status: str = CUT_STATUS_PENDING
    """CUT_STATUS_PENDING or one of cut_evaluation.CUT_OUTCOME_*."""
    cut_pct: Optional[float] = None
    """Only ever rendered when cut_status == CUT_STATUS_PENDING; see
    module docstring."""
    probability_history: tuple[ProbabilityHistoryPoint, ...] = field(default_factory=tuple)
    round_scores: tuple[RoundScoreRow, ...] = field(default_factory=tuple)
    total_score_to_par: Optional[int] = None
    sample_size_rounds: Optional[int] = None
    expected_round_score: Optional[float] = None
    consistency_stddev: Optional[float] = None
    why_text: Optional[str] = None
    tournament_id: str = ""
    """GA4 `player_card_open` event parameter (task section 12) —
    rendered as a data attribute on the card itself (this fragment has
    no literal `<body>` tag to attach it to, same convention as the
    rest of the R1/R2 page templates), read by render_player_card_js
    from the specific card being opened."""
    stage: str = ""
    """Raw stage code for the GA4 event, e.g. 'R1'/'R2' — distinct
    from `stage_display` (already-Korean text for the card header)."""


def _fmt_pct(value: Optional[float]) -> str:
    return "" if value is None else f"{value:.2f}%"


def _fmt_signed_pct_points(delta: float) -> str:
    arrow = "▲" if delta >= 0 else "▼"
    return f"{arrow} {delta:+.2f}%p"


def _fmt_score_to_par(value: Optional[int]) -> str:
    if value is None:
        return ""
    if value == 0:
        return "E"
    return f"+{value}" if value > 0 else str(value)


def _render_current_position_block(data: PlayerCardData) -> str:
    if data.current_position is None and data.current_score_to_par is None:
        return ""
    return (
        f'<div class="pc-row-2col">'
        f'<div><span class="pc-label">{KOREAN_LABELS["current_position"]}</span>'
        f'<span class="pc-value">{data.current_position or ""}</span></div>'
        f'<div><span class="pc-label">{KOREAN_LABELS["score"]}</span>'
        f'<span class="pc-value">{_fmt_score_to_par(data.current_score_to_par)}</span></div>'
        f"</div>"
    )


def _render_win_probability_block(data: PlayerCardData) -> str:
    cut_line = _render_cut_status_line(data)
    if data.win_pct is None:
        if not cut_line:
            return ""
        return f'<div class="pc-section pc-win-probability">{cut_line}</div>'
    parts = [
        f'<div class="pc-section pc-win-probability">',
        f'<div class="pc-label">{KOREAN_LABELS["win_probability"]}</div>',
        f'<div class="pc-win-pct">{_fmt_pct(data.win_pct)}</div>',
    ]
    if len(data.probability_history) >= 2:
        previous = data.probability_history[-2]
        delta = data.win_pct - previous.win_pct
        prev_label = STAGE_DISPLAY_LABELS.get(previous.stage, previous.stage)
        parts.append(f'<div class="pc-delta">{_fmt_signed_pct_points(delta)}</div>')
        parts.append(f'<div class="pc-delta-caption">{prev_label} 종료 후 {_fmt_pct(previous.win_pct)}</div>')
    if cut_line:
        parts.append(cut_line)
    parts.append("</div>")
    return "".join(parts)


def _render_cut_status_line(data: PlayerCardData) -> str:
    if data.cut_status == CUT_STATUS_PENDING:
        if data.cut_pct is None:
            return ""
        return f'<div class="pc-cut-line">{KOREAN_LABELS["make_cut"]} {_fmt_pct(data.cut_pct)}</div>'
    if data.cut_status == CUT_OUTCOME_MADE:
        return f'<div class="pc-cut-line pc-cut-made">{KOREAN_LABELS["cut_passed"]} ✓</div>'
    if data.cut_status == CUT_OUTCOME_MISSED:
        return f'<div class="pc-cut-line pc-cut-missed">{KOREAN_LABELS["cut_missed"]}</div>'
    if data.cut_status == CUT_OUTCOME_WD:
        return f'<div class="pc-cut-line pc-cut-wd">{KOREAN_LABELS["withdrawn"]}</div>'
    if data.cut_status == CUT_OUTCOME_DQ:
        return f'<div class="pc-cut-line pc-cut-dq">{KOREAN_LABELS["disqualified"]}</div>'
    if data.cut_status == CUT_OUTCOME_UNRESOLVED:
        return ""  # genuinely unknown — never guessed, never rendered as a claim
    raise ValueError(f"Unrecognized cut_status={data.cut_status!r}")


def _render_probability_history_block(data: PlayerCardData) -> str:
    if not data.probability_history:
        return ""
    stage_labels = " → ".join(STAGE_DISPLAY_LABELS.get(p.stage, p.stage) for p in data.probability_history)
    values = " → ".join(_fmt_pct(p.win_pct) for p in data.probability_history)
    return (
        f'<div class="pc-section pc-history">'
        f'<div class="pc-section-title">{KOREAN_LABELS["prediction_history"]}</div>'
        f'<div class="pc-history-stages">{stage_labels}</div>'
        f'<div class="pc-history-values">{values}</div>'
        f"</div>"
    )


def _render_tournament_result_block(data: PlayerCardData) -> str:
    if not data.round_scores:
        return ""
    rows = "".join(
        f'<tr><td>{r.round_number}R</td><td>{r.round_score}</td><td>{_fmt_score_to_par(r.score_to_par)}</td></tr>'
        for r in data.round_scores
    )
    total_row = ""
    if data.total_score_to_par is not None:
        total_row = f'<tr class="pc-total"><td>합계</td><td></td><td>{_fmt_score_to_par(data.total_score_to_par)}</td></tr>'
    return (
        f'<div class="pc-section">'
        f'<div class="pc-section-title">{KOREAN_LABELS["tournament_result"]}</div>'
        f'<table class="pc-round-table"><tbody>{rows}{total_row}</tbody></table>'
        f"</div>"
    )


def _render_player_data_block(data: PlayerCardData) -> str:
    rows = []
    if data.sample_size_rounds is not None:
        rows.append(f'<tr><td>{KOREAN_LABELS["historical_rounds"]}</td><td>{data.sample_size_rounds}라운드</td></tr>')
    if data.expected_round_score is not None:
        rows.append(f'<tr><td>{KOREAN_LABELS["expected_round"]}</td><td>{data.expected_round_score:+.2f}</td></tr>')
    if data.consistency_stddev is not None:
        rows.append(f'<tr><td>{KOREAN_LABELS["consistency"]}</td><td>{data.consistency_stddev:.2f}</td></tr>')
    if not rows:
        return ""
    return (
        f'<div class="pc-section">'
        f'<div class="pc-section-title">{KOREAN_LABELS["player_data"]}</div>'
        f'<table class="pc-kv-table"><tbody>{"".join(rows)}</tbody></table>'
        f"</div>"
    )


def _render_data_sample_block(data: PlayerCardData) -> str:
    if data.sample_size_rounds is None:
        return ""
    return (
        f'<div class="pc-section">'
        f'<div class="pc-section-title">{KOREAN_LABELS["data_sample"]}</div>'
        f'<div class="pc-sample-size">{data.sample_size_rounds}라운드</div>'
        f"</div>"
    )


def _render_why_block(data: PlayerCardData) -> str:
    if not data.why_text:
        return ""
    why_html = data.why_text.replace("\n", "<br>")
    return (
        f'<div class="pc-section pc-why">'
        f'<div class="pc-section-title">{KOREAN_LABELS["why_probability"]}</div>'
        f'<p>{why_html}</p>'
        f"</div>"
    )


def render_player_card_html(data: PlayerCardData) -> str:
    """A hidden-by-default bottom-sheet panel, `id="player-card-<code>"`.
    Semantic, readable as plain text even with JavaScript disabled
    (see module docstring / task section 11) — this is not a `<dialog>`
    that requires JS to render its content, only to become visible."""
    return (
        f'<div class="player-card" id="player-card-{data.player_code}" data-player-code="{data.player_code}" '
        f'data-tournament-id="{data.tournament_id}" data-stage="{data.stage}" '
        f'role="dialog" aria-modal="true" aria-labelledby="player-card-{data.player_code}-name" hidden>'
        f'<div class="pc-header">'
        f'<h2 id="player-card-{data.player_code}-name" class="pc-player-name">{data.player_name}</h2>'
        f'<button type="button" class="pc-close" aria-label="닫기" data-player-card-close>&times;</button>'
        f"</div>"
        f'<div class="pc-meta">{data.tournament_name} · {data.stage_display}</div>'
        f"{_render_current_position_block(data)}"
        f"{_render_win_probability_block(data)}"
        f"{_render_probability_history_block(data)}"
        f"{_render_tournament_result_block(data)}"
        f"{_render_player_data_block(data)}"
        f"{_render_data_sample_block(data)}"
        f"{_render_why_block(data)}"
        f'<div class="pc-brand">{BRAND_NAME}</div>'
        f"</div>"
    )


def render_player_name_cell(player_code: str, player_name: str) -> str:
    """The clickable/tappable name cell — a real `<button>` inside the
    existing `td.c-name` cell (task section 11: readable without JS,
    a semantic control). Works as a drop-in replacement for any
    existing `<td class="c-name">{name}</td>` cell — the table's other
    columns (c-pos/c-score/c-pct) are untouched by this function."""
    return (
        f'<td class="c-name"><button type="button" class="player-name-btn" '
        f'data-player-card-trigger data-player-code="{player_code}">{player_name}</button></td>'
    )


PLAYER_CARD_CSS = """
  .player-card {
    position: fixed;
    left: 0; right: 0; bottom: 0;
    max-width: 480px;
    margin: 0 auto;
    background: var(--bg-alt, #14171c);
    color: var(--text, #f2f4f6);
    border-top: 1px solid var(--border, #22262d);
    border-radius: 16px 16px 0 0;
    padding: 20px 20px calc(20px + env(safe-area-inset-bottom, 0px));
    max-height: 85vh;
    overflow-y: auto;
    z-index: 1001;
    transform: translateY(100%);
    transition: transform 0.2s ease-out;
  }
  .player-card[data-open="true"] { transform: translateY(0); }
  .player-card[hidden] { display: none; }
  @media (min-width: 600px) {
    .player-card { left: 50%; right: auto; bottom: auto; top: 50%; transform: translate(-50%, -45%); border-radius: 16px; }
    .player-card[data-open="true"] { transform: translate(-50%, -50%); }
  }
  .pc-backdrop {
    position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 1000;
    opacity: 0; pointer-events: none; transition: opacity 0.2s ease-out;
  }
  .pc-backdrop[data-open="true"] { opacity: 1; pointer-events: auto; }
  .pc-header { display: flex; align-items: center; justify-content: space-between; }
  .pc-player-name { font-size: 20px; margin: 0; }
  .pc-close { background: none; border: none; color: var(--text-dim, #8b93a1); font-size: 28px; line-height: 1; padding: 8px; min-width: 44px; min-height: 44px; cursor: pointer; }
  .pc-meta { color: var(--text-dim, #8b93a1); font-size: 13px; margin: 4px 0 16px; }
  .pc-row-2col { display: flex; gap: 24px; margin-bottom: 16px; }
  .pc-label { display: block; font-size: 12px; color: var(--text-dim, #8b93a1); }
  .pc-value { display: block; font-size: 18px; font-weight: 700; }
  .pc-section { margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border, #22262d); }
  .pc-section-title { font-size: 13px; color: var(--text-dim, #8b93a1); margin-bottom: 8px; }
  .pc-win-pct { font-size: 32px; font-weight: 800; }
  .pc-delta { font-size: 14px; }
  .pc-delta-caption { font-size: 12px; color: var(--text-dim, #8b93a1); }
  .pc-cut-line { margin-top: 8px; font-size: 14px; }
  .pc-history-stages, .pc-round-table, .pc-kv-table { width: 100%; font-size: 14px; }
  .pc-round-table td, .pc-kv-table td { padding: 4px 0; }
  .pc-sample-size { font-size: 16px; font-weight: 700; }
  .pc-why p { font-size: 13px; line-height: 1.6; color: var(--text-dim, #8b93a1); white-space: pre-line; }
  .pc-brand { margin-top: 16px; font-size: 11px; color: var(--text-dim, #8b93a1); text-align: right; }
  .player-name-btn {
    background: none; border: none; color: inherit; font: inherit; text-align: left;
    cursor: pointer; padding: 6px 2px; min-height: 44px; text-decoration: underline;
    text-decoration-color: transparent;
  }
  .player-name-btn:hover, .player-name-btn:focus-visible { text-decoration-color: currentColor; }
"""


def render_player_card_js(*, ga4_enabled: bool = True) -> str:
    """Event-delegation JS: works for any number of `[data-player-card-
    trigger]` buttons added to the page (no per-row listener wiring
    needed). Opens `#player-card-<code>`, locks body scroll, closes via
    close-button/backdrop/Escape. Dispatches the GA4 `player_card_open`
    event ONLY with the parameters the task specifies (player_code,
    player_name, tournament_id, stage) — never the win probability —
    and only if `gtag` actually exists on the page (never assumes GA4
    is installed)."""
    ga4_snippet = (
        """
      if (typeof gtag === 'function') {
        gtag('event', 'player_card_open', {
          player_code: code,
          player_name: name,
          tournament_id: card.getAttribute('data-tournament-id') || '',
          stage: card.getAttribute('data-stage') || ''
        });
      }
    """
        if ga4_enabled
        else ""
    )
    return f"""
(function() {{
  var backdrop = document.createElement('div');
  backdrop.className = 'pc-backdrop';
  document.body.appendChild(backdrop);

  function openCard(code) {{
    var card = document.getElementById('player-card-' + code);
    if (!card) return;
    var name = card.querySelector('.pc-player-name') ? card.querySelector('.pc-player-name').textContent : '';
    card.hidden = false;
    backdrop.setAttribute('data-open', 'true');
    requestAnimationFrame(function() {{ card.setAttribute('data-open', 'true'); }});
    document.body.style.overflow = 'hidden';
    {ga4_snippet}
  }}

  function closeCard(card) {{
    card.removeAttribute('data-open');
    backdrop.removeAttribute('data-open');
    document.body.style.overflow = '';
    setTimeout(function() {{ card.hidden = true; }}, 200);
  }}

  document.addEventListener('click', function(e) {{
    var trigger = e.target.closest('[data-player-card-trigger]');
    if (trigger) {{
      openCard(trigger.getAttribute('data-player-code'));
      return;
    }}
    var closeBtn = e.target.closest('[data-player-card-close]');
    if (closeBtn) {{
      closeCard(closeBtn.closest('.player-card'));
      return;
    }}
    if (e.target === backdrop) {{
      var openCardEl = document.querySelector('.player-card[data-open="true"]');
      if (openCardEl) closeCard(openCardEl);
    }}
  }});

  document.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape') {{
      var openCardEl = document.querySelector('.player-card[data-open="true"]');
      if (openCardEl) closeCard(openCardEl);
    }}
  }});
}})();
"""
