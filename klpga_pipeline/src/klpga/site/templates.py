"""HTML rendering + all page copy. Every derived Korean label used
here is documented, with its exact wording rationale, in
`docs/PREDICTIONS_SITE.md` — nothing here is guessed inline without a
paper trail. No probability, rank, or feature value is computed in
this module; every value rendered comes directly from an already
rank-ordered `PredictionSnapshot`/`EntrantSnapshot`
(`klpga.archive.prediction_archive`) or `build.ordered_entrants`.

Display-only rounding: `_format_pct` and `_bar_width_pct` are the ONLY
places a probability is rounded, and they are called only at render
time — the value embedded in `<script type="application/json">` per
page, and every `data-*` attribute used for search/filter, still
carries the archive's full-precision float. Ranking is never
recomputed from probability anywhere in this file; display order is
always `build.ordered_entrants`, i.e. the archive's own `rank` field.
"""
from __future__ import annotations

import json
from html import escape as h

from klpga.archive.prediction_archive import EntrantSnapshot, PredictionSnapshot
from klpga.models.walk_forward_eval import ROOKIE_SLICES
from klpga.site.build import ordered_entrants

SITE_TITLE = "NEO GOLF PREDICTIONS"
SITE_TAGLINE = "data-driven golf intelligence"

# Korean labels for klpga.models.walk_forward_eval.ROOKIE_SLICES — kept
# in lockstep with the frozen slice names via the assertion below, so
# a future slice added upstream fails this module loudly rather than
# silently rendering an unlabeled bucket.
HISTORY_SLICE_LABELS_KO: dict[str, str] = {
    "cold_0": "출전 이력 없음",
    "very_sparse_1_4": "출전 이력 매우 적음 (1~4회)",
    "sparse_5_9": "출전 이력 적음 (5~9회)",
    "moderate_10_19": "출전 이력 보통 (10~19회)",
    "established_20plus": "출전 이력 풍부 (20회 이상)",
}
_slice_names = {name for name, _, _ in ROOKIE_SLICES}
assert set(HISTORY_SLICE_LABELS_KO) == _slice_names, (
    f"HISTORY_SLICE_LABELS_KO is out of sync with ROOKIE_SLICES: "
    f"missing={_slice_names - set(HISTORY_SLICE_LABELS_KO)}, "
    f"extra={set(HISTORY_SLICE_LABELS_KO) - _slice_names}"
)

PROBABILITY_EXPLANATION_KO = (
    "우승확률 10%는 이 선수가 반드시 우승한다는 뜻이 아닙니다. "
    "현재 출전선수와 대회 시작 전까지 확인된 과거 데이터를 기준으로, "
    "이 필드에서 우승할 상대적 가능성을 확률로 표현한 값입니다."
)
PROBABILITY_SUM_NOTE_KO = "모든 선수의 우승확률 합은 100%입니다."
PROBABILITY_NOT_GUARANTEE_KO = "이는 확률 추정치이며, 우승을 보장하는 예측이 아닙니다."

### v1.1 PUBLIC MODEL EXPLANATION ###
# Reader-facing copy only — see docs/PREDICTIONS_SITE.md "Public copy
# — model explanation, v1.1" for the reviewed wording log. No model
# name, version, or calibration-limitation disclosure is rendered
# anywhere in normal reader-facing UI (the underlying archive JSON's
# model_id/model_version/known_limitations fields are untouched — see
# `_embedded_data_json`'s docstring for where model_id still legitimately
# appears, as a transparency artifact, not visible prose).
#
# CORPUS_PLAYER_TOURNAMENT_ROWS_APPROX is FIXED editorial copy sourced
# from the real production coverage audit run 2026-08-26 (100 usable
# historical tournaments, 11,850 (target tournament, player) rows) —
# it is NOT recomputed at build time (the archive schema has no
# player-target-row-count field, and the site build never queries the
# database). Must be re-verified before reuse for a prediction built
# against a materially different historical corpus.
CORPUS_PLAYER_TOURNAMENT_ROWS_APPROX = "11,850"

MODEL_EXPLANATION_INTRO_TEMPLATE_KO = (
    "NEO는 과거 {tournament_count}개 KLPGA 대회의 약 {rows}개 선수-대회 기록을 분석합니다."
)
MODEL_EXPLANATION_METHOD_TEMPLATE_KO = (
    "Prediction #{prediction_id}은 대회 시작 전까지 확인된 정보만 사용해 "
    "선수의 장기적인 스코어 경기력과 최근 10개 대회의 경기 흐름을 평가하고, "
    "이번 대회 출전선수 {field_size}명을 서로 비교해 우승 가능성을 계산했습니다."
)
MODEL_EXPLANATION_SUM_KO = "모든 출전선수의 우승확률 합은 100%입니다."

METHODOLOGY_EXCLUSION_KO = (
    "NEO는 현재 스트로크게인드(Strokes Gained), 그린적중률(GIR), 드라이빙 거리/정확도, "
    "퍼팅 데이터를 사용하지 않습니다."
)


def _model_explanation_paragraphs(snapshot: PredictionSnapshot) -> tuple[str, str, str]:
    return (
        MODEL_EXPLANATION_INTRO_TEMPLATE_KO.format(
            tournament_count=snapshot.training_tournament_count,
            rows=CORPUS_PLAYER_TOURNAMENT_ROWS_APPROX,
        ),
        MODEL_EXPLANATION_METHOD_TEMPLATE_KO.format(
            prediction_id=snapshot.prediction_id,
            field_size=snapshot.field_size,
        ),
        MODEL_EXPLANATION_SUM_KO,
    )

RECENT_FORM_LABEL_KO = "최근 폼 데이터"
RECENT_FORM_AVAILABLE_KO = "있음 (최근 최대 10개 대회 기준, {n}개 대회 반영)"
RECENT_FORM_UNAVAILABLE_KO = "없음 (직전 대회 기록 없음)"
# See docs/PREDICTIONS_SITE.md "Reviewed Korean wording" — this label
# is deliberately NOT "평균 스코어" alone: prior_recent_form_10 is the
# mean of each tournament's TOTAL score-to-par (not a per-round
# average, not a raw strokes count) across up to the player's 10 most
# recent PRIOR tournaments (never padded — see
# klpga.backtest.point_in_time_features's module docstring). This
# wording is flagged for confirmation before being treated as final.
RECENT_FORM_VALUE_LABEL_KO = "최근 최대 10개 대회의 대회 합계 스코어(파 대비) 평균"

PLAYER_MATCHED_KO = "선수 데이터베이스 매칭됨"
PLAYER_UNMATCHED_KO = "선수 데이터베이스 미매칭"
PLAYER_UNMATCHED_NOTE_KO = (
    "출전자 명단에는 있으나 기존 선수 데이터베이스와 자동으로 매칭되지 않은 경우입니다. "
    "예측 대상에서 제외되지 않으며, 과거 기록이 없는 선수와 동일한 방식으로 처리됩니다."
)

### v1.1 SUMMARY STRIP (near the top of every prediction page) ###
SUMMARY_TOURNAMENTS_LABEL_KO = "분석"
SUMMARY_ROWS_LABEL_KO = "선수-대회 기록"
SUMMARY_FIELD_LABEL_KO = "비교"
SUMMARY_PROB_SUM_LABEL_KO = "전체 우승확률 합"

### v1.1 "WHY" SECTION (rank-1 entrant only, shown near the leaderboard) ###
WHY_TITLE_KO = "왜 이 선수의 우승확률이 높을까요?"
WHY_INTRO_TEMPLATE_KO = (
    "{name} 선수의 우승확률은 대회 시작 전까지 확인된 장기적인 스코어 경기력과 "
    "최근 경기 흐름을 이번 대회 출전선수 {field_size}명과 비교해 계산한 값입니다."
)
WHY_PARTICIPATION_LABEL_KO = "참가 이력"
# prior_avg_round_score_to_par IS a genuine per-round rate
# (sum(score_to_par)/sum(rounds_played) — see
# point_in_time_features.py's module docstring) — safe to call
# "per round."
WHY_LONG_TERM_LABEL_KO = "라운드당 평균 스코어"
# prior_recent_form_10 is the mean of each TOURNAMENT's total
# score-to-par across up to the 10 most recent prior tournaments — a
# per-EVENT average, NOT a per-round figure (see
# point_in_time_features.py's module docstring and
# player_stats.py's `_event_`/`_round_` naming-convention section).
# Must never be described as "per round" or "per round X strokes
# better" — that would misstate its unit.
WHY_RECENT_FORM_LABEL_KO = "최근 10개 대회 흐름"
WHY_RECENT_FORM_NOTE_KO = "라운드 평균이 아닌 대회 전체 합산 스코어 기준입니다."
WHY_NO_DATA_KO = "데이터 없음"


def _signed_strokes_ko(value: float) -> str:
    """'-0.66' -> '파 대비 약 0.66타 언더'. Renders a signed to-par
    float as plain Korean — never states a per-round/per-event unit
    itself; callers pair this with the correct unit label."""
    if value < 0:
        direction = "언더"
    elif value > 0:
        direction = "오버"
    else:
        direction = "이븐"
    return f"파 대비 약 {abs(value):.2f}타 {direction}"


HISTORY_STUB_NOTE_KO = (
    "대회 종료 후 결과 평가 기능은 아직 준비 중입니다. 예측 기록은 대회 시작 전 "
    "상태 그대로 보관되어 있으며, 결과와 비교한 평가는 별도 기록으로 추가될 예정입니다."
)


def _format_pct(probability: float) -> str:
    return f"{probability * 100:.2f}%"


def _bar_width_pct(probability: float, maximum_probability: float) -> float:
    """Relative to the FIELD's own top probability, not an absolute
    0-100% domain — with 100+ entrants, an absolute scale would render
    almost every bar as an invisible sliver. The rank-1 player (whose
    own probability equals `maximum_probability` by construction)
    always renders a full-width bar; every other bar is scaled
    relative to it. The exact percentage text next to the bar is
    always the ground truth — the bar communicates relative strength
    only, never a second number."""
    width = (probability / maximum_probability) * 100
    return min(100.0, round(width, 2))


def _history_slice_label(slice_name: str) -> str:
    return HISTORY_SLICE_LABELS_KO.get(slice_name, slice_name)


def _recent_form_value_html(entrant: EntrantSnapshot) -> str:
    if entrant.prior_recent_form_10_n == 0 or entrant.prior_recent_form_10 is None:
        return h(RECENT_FORM_UNAVAILABLE_KO)
    return (
        f"{h(RECENT_FORM_AVAILABLE_KO.format(n=entrant.prior_recent_form_10_n))}"
        f'<br><span class="detail-subvalue">{h(RECENT_FORM_VALUE_LABEL_KO)}: '
        f"{_signed_strokes_ko(entrant.prior_recent_form_10)}</span>"
    )


def _entrant_row_html(entrant: EntrantSnapshot, maximum_probability: float) -> str:
    pct = _format_pct(entrant.win_probability)
    bar_pct = _bar_width_pct(entrant.win_probability, maximum_probability)
    search_key = f"{entrant.player_name_display} {entrant.player_code}".lower()
    unmatched_badge = "" if entrant.player_master_matched else '<span class="badge badge-unmatched">미매칭</span>'

    main_row = (
        f'<tr class="pred-row" data-rank="{entrant.rank}" data-code="{h(entrant.player_code)}" '
        f'data-search="{h(search_key)}" tabindex="0" role="button" aria-expanded="false">'
        f'<td class="col-rank">{entrant.rank}</td>'
        f'<td class="col-player">{h(entrant.player_name_display)}{unmatched_badge}</td>'
        f'<td class="col-prob">'
        f'<div class="prob-bar-wrap"><div class="prob-bar" style="width:{bar_pct}%"></div></div>'
        f'<span class="prob-value">{pct}</span>'
        f'</td></tr>'
    )

    matched_label = PLAYER_MATCHED_KO if entrant.player_master_matched else PLAYER_UNMATCHED_KO
    matched_note = "" if entrant.player_master_matched else f'<p class="detail-note">{h(PLAYER_UNMATCHED_NOTE_KO)}</p>'

    detail_row = (
        f'<tr class="pred-detail" hidden><td colspan="3">'
        f'<dl class="detail-grid">'
        f'<dt>우승확률</dt><dd>{pct}</dd>'
        f'<dt>예측 순위</dt><dd>{entrant.rank}위</dd>'
        f'<dt>출전 이력 구간</dt><dd>{h(_history_slice_label(entrant.history_slice))}</dd>'
        f'<dt>참가 이력</dt><dd>{entrant.prior_events_n}회</dd>'
        f'<dt>{h(RECENT_FORM_LABEL_KO)}</dt><dd>{_recent_form_value_html(entrant)}</dd>'
        f'<dt>선수 데이터베이스</dt><dd>{h(matched_label)}</dd>'
        f'</dl>{matched_note}'
        f'</td></tr>'
    )
    return main_row + detail_row


def _embedded_data_json(snapshot: PredictionSnapshot) -> str:
    """A transparency artifact, not a runtime data source — the
    interactive JS operates on the rendered DOM's data-* attributes.
    Anyone can view-source this block and confirm it matches the
    visible table exactly, and that it is the archive's own data
    verbatim (see docs/PREDICTIONS_SITE.md). `model_id`/`model_version`
    are included here deliberately even though v1.1 removed them from
    visible prose (per the public-copy decision) — this block is
    internal/archive-provenance metadata, not "normal reader-facing
    UI," and that metadata must stay intact and inspectable."""
    payload = {
        "prediction_id": snapshot.prediction_id,
        "game_code": snapshot.game_code,
        "cutoff_date": snapshot.cutoff_date,
        "model_id": snapshot.model_id,
        "model_version": snapshot.model_version,
        "field_size": snapshot.field_size,
        "probability_sum": snapshot.probability_sum,
        "predictions": [
            {
                "rank": e.rank,
                "player_code": e.player_code,
                "player_name_display": e.player_name_display,
                "win_probability": e.win_probability,
            }
            for e in ordered_entrants(snapshot)
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def _table_html(snapshot: PredictionSnapshot) -> str:
    entrants = ordered_entrants(snapshot)
    rows = "".join(_entrant_row_html(e, snapshot.maximum_probability) for e in entrants)
    return (
        '<div data-neo-predictions-root>'
        '<div class="controls">'
        '<input type="search" id="player-search" class="search-input" '
        'placeholder="선수 검색 (이름 또는 선수코드)" aria-label="선수 검색">'
        '<div class="filter-pills" role="group" aria-label="순위 필터">'
        '<button type="button" class="filter-pill active" data-filter="all" aria-pressed="true">전체</button>'
        '<button type="button" class="filter-pill" data-filter="top10" aria-pressed="false">TOP 10</button>'
        '<button type="button" class="filter-pill" data-filter="top20" aria-pressed="false">TOP 20</button>'
        '</div></div>'
        '<table id="predictions-table" class="pred-table">'
        '<thead><tr><th class="col-rank">순위</th><th class="col-player">선수</th>'
        '<th class="col-prob">우승확률</th></tr></thead>'
        f'<tbody>{rows}</tbody>'
        '</table>'
        f'<script type="application/json" id="prediction-data">{_embedded_data_json(snapshot)}</script>'
        '</div>'
    )


def _summary_strip_html(snapshot: PredictionSnapshot) -> str:
    items = (
        (f"과거 {snapshot.training_tournament_count}개 대회", SUMMARY_TOURNAMENTS_LABEL_KO),
        (f"약 {CORPUS_PLAYER_TOURNAMENT_ROWS_APPROX}개", SUMMARY_ROWS_LABEL_KO),
        (f"출전선수 {snapshot.field_size}명", SUMMARY_FIELD_LABEL_KO),
        ("100%", SUMMARY_PROB_SUM_LABEL_KO),
    )
    tiles = "".join(
        f'<div class="summary-item"><span class="summary-value">{h(value)}</span>'
        f'<span class="summary-label">{h(label)}</span></div>'
        for value, label in items
    )
    return f'<div class="summary-strip">{tiles}</div>'


def _why_section_html(snapshot: PredictionSnapshot) -> str:
    entrants = ordered_entrants(snapshot)
    if not entrants:
        return ""
    top = entrants[0]
    pct = _format_pct(top.win_probability)

    long_term_html = (
        h(_signed_strokes_ko(top.prior_avg_round_score_to_par))
        if top.prior_avg_round_score_to_par is not None
        else h(WHY_NO_DATA_KO)
    )
    if top.prior_recent_form_10 is not None and top.prior_recent_form_10_n:
        recent_form_html = (
            f"{h(_signed_strokes_ko(top.prior_recent_form_10))}"
            f'<br><span class="detail-subvalue">{h(WHY_RECENT_FORM_NOTE_KO)}</span>'
        )
    else:
        recent_form_html = h(WHY_NO_DATA_KO)

    return (
        '<section class="why-panel" aria-label="왜 이 선수의 우승확률이 높을까요?">'
        f'<h2>{h(WHY_TITLE_KO)}</h2>'
        '<div class="why-player">'
        f'<span class="why-player-name">{h(top.player_name_display)}</span>'
        f'<span class="why-player-prob">우승확률 {pct}</span>'
        f'<span class="why-player-rank">예측순위 {top.rank}위</span>'
        '</div>'
        f'<p>{h(WHY_INTRO_TEMPLATE_KO.format(name=top.player_name_display, field_size=snapshot.field_size))}</p>'
        '<dl class="why-stats">'
        f'<dt>{h(WHY_PARTICIPATION_LABEL_KO)}</dt><dd>{top.prior_events_n}회</dd>'
        f'<dt>{h(WHY_LONG_TERM_LABEL_KO)}</dt><dd>{long_term_html}</dd>'
        f'<dt>{h(WHY_RECENT_FORM_LABEL_KO)}</dt><dd>{recent_form_html}</dd>'
        '</dl>'
        '</section>'
    )


def _explanation_block_html() -> str:
    return (
        '<section class="explanation" aria-label="우승확률이란?">'
        '<h2>우승확률이란?</h2>'
        f'<p>{h(PROBABILITY_EXPLANATION_KO)}</p>'
        f'<p class="explanation-note">{h(PROBABILITY_SUM_NOTE_KO)} {h(PROBABILITY_NOT_GUARANTEE_KO)}</p>'
        '</section>'
    )


def _methodology_content_html(snapshot: PredictionSnapshot) -> str:
    """Reader-facing explanation only. Deliberately does NOT render
    `snapshot.known_limitations` (the archived JSON's calibration-
    limitation text, which also names an internal docs file) — that
    field stays fully intact in the archive (see
    `klpga.archive.prediction_archive`), it is simply not surfaced in
    normal reader-facing UI. See docs/PREDICTIONS_SITE.md."""
    paragraphs = "".join(f"<p>{h(p)}</p>" for p in _model_explanation_paragraphs(snapshot))
    return f'{paragraphs}<p class="methodology-exclusion">{h(METHODOLOGY_EXCLUSION_KO)}</p>'


def _methodology_block_html(snapshot: PredictionSnapshot) -> str:
    return (
        '<details class="panel">'
        '<summary>모델은 어떻게 계산하나요?</summary>'
        f'<div class="panel-body">{_methodology_content_html(snapshot)}</div>'
        '</details>'
    )


def _prediction_record_block_html(snapshot: PredictionSnapshot) -> str:
    """The simplified v1.1 public Prediction Record: exactly four
    facts (prediction number, cutoff, PRE-TOURNAMENT status, LOCKED
    archive status) — no model name/version, no provenance/
    reconstruction detail. Full provenance (including
    `provenance.source`, the rerun_reconstruction verification
    fields, etc.) stays completely intact in the archived JSON —
    see `klpga.archive.prediction_archive` — this panel simply does
    not surface it publicly (per the v1.1 public-copy decision)."""
    return (
        '<details class="panel">'
        '<summary>Prediction Record</summary>'
        '<div class="panel-body">'
        '<dl class="record-grid">'
        f'<dt>예측 번호</dt><dd>Prediction #{h(snapshot.prediction_id)}</dd>'
        f'<dt>기준일</dt><dd>{h(snapshot.cutoff_date)}</dd>'
        '<dt>상태</dt><dd><span class="badge badge-status">PRE-TOURNAMENT</span></dd>'
        '<dt>보관 상태</dt><dd><span class="badge badge-locked">LOCKED</span></dd>'
        '</dl>'
        '</div></details>'
    )


def _nav_html(active: str) -> str:
    links = (
        ("/", "홈", "home"),
        ("/predictions/", "예측 기록", "predictions"),
        ("/methodology/", "방법론", "methodology"),
    )
    items = "".join(
        f'<a href="{href}" class="nav-link{" nav-active" if key == active else ""}">{label}</a>'
        for href, label, key in links
    )
    return f'<nav class="site-nav">{items}</nav>'


def _shell(*, page_title: str, active_nav: str, body_html: str) -> str:
    return (
        "<!doctype html>"
        '<html lang="ko">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{h(page_title)}</title>"
        '<link rel="stylesheet" href="/static/styles.css">'
        "</head>"
        "<body>"
        '<header class="site-header">'
        f'<a href="/" class="brand"><span class="brand-mark">{h(SITE_TITLE)}</span>'
        f'<span class="brand-tagline">{h(SITE_TAGLINE)}</span></a>'
        f"{_nav_html(active_nav)}"
        "</header>"
        f'<main class="site-main">{body_html}</main>'
        '<footer class="site-footer">'
        f'<p>{h(SITE_TITLE)} — {h(SITE_TAGLINE)}</p>'
        "</footer>"
        '<script src="/static/app.js"></script>'
        "</body></html>"
    )


def render_prediction_page(snapshot: PredictionSnapshot, *, is_home: bool) -> str:
    """The main per-prediction page (also written to `/` for the
    latest prediction, and to `/predictions/<id>/` as its permalink —
    identical content either way)."""
    tournament_name = snapshot.tournament_name or "(대회명 미확인)"
    body = (
        '<article class="prediction-page">'
        '<div class="tournament-header">'
        f'<h1 class="tournament-name">{h(tournament_name)}</h1>'
        '<span class="badge badge-status">PRE-TOURNAMENT</span>'
        "</div>"
        f"{_summary_strip_html(snapshot)}"
        f"{_why_section_html(snapshot)}"
        f"{_table_html(snapshot)}"
        f"{_explanation_block_html()}"
        f"{_methodology_block_html(snapshot)}"
        f"{_prediction_record_block_html(snapshot)}"
        "</article>"
    )
    title = f"{SITE_TITLE} — {tournament_name}" if is_home else f"{SITE_TITLE} — 예측 #{snapshot.prediction_id}"
    return _shell(page_title=title, active_nav="home" if is_home else "predictions", body_html=body)


def render_predictions_index(snapshots: list[PredictionSnapshot]) -> str:
    items = "".join(
        '<li class="prediction-list-item">'
        f'<a href="/predictions/{h(s.prediction_id)}/">'
        f'<span class="prediction-list-name">{h(s.tournament_name or "(대회명 미확인)")}</span>'
        f'<span class="prediction-list-meta">예측 #{h(s.prediction_id)} · 기준일 {h(s.cutoff_date)} · '
        f'{s.field_size}명</span>'
        "</a></li>"
        for s in reversed(snapshots)
    )
    body = (
        '<section class="predictions-index">'
        "<h1>예측 기록</h1>"
        f'<ul class="prediction-list">{items}</ul>'
        "</section>"
    )
    return _shell(page_title=f"{SITE_TITLE} — 예측 기록", active_nav="predictions", body_html=body)


def render_history_page(snapshots: list[PredictionSnapshot]) -> str:
    items = "".join(
        '<li class="prediction-list-item">'
        f'<a href="/predictions/{h(s.prediction_id)}/">'
        f'<span class="prediction-list-name">{h(s.tournament_name or "(대회명 미확인)")}</span>'
        f'<span class="prediction-list-meta">예측 #{h(s.prediction_id)} · 기준일 {h(s.cutoff_date)} · '
        f'결과: 대회 진행 전</span>'
        "</a></li>"
        for s in reversed(snapshots)
    )
    body = (
        '<section class="predictions-history">'
        "<h1>예측 기록</h1>"
        f'<p class="history-note">{h(HISTORY_STUB_NOTE_KO)}</p>'
        f'<ul class="prediction-list">{items}</ul>'
        "</section>"
    )
    return _shell(page_title=f"{SITE_TITLE} — 예측 기록 (결과 평가)", active_nav="predictions", body_html=body)


def render_methodology_page(snapshot: PredictionSnapshot) -> str:
    """`snapshot` supplies the explanation's concrete numbers (corpus
    size, field size, prediction id) — usually the latest prediction,
    same as `build_site()` picks for `/`."""
    body = (
        '<section class="methodology-page">'
        "<h1>모델은 어떻게 계산하나요?</h1>"
        f"{_methodology_content_html(snapshot)}"
        f'<h2>우승확률이란?</h2>'
        f'<p>{h(PROBABILITY_EXPLANATION_KO)}</p>'
        f'<p class="explanation-note">{h(PROBABILITY_SUM_NOTE_KO)} {h(PROBABILITY_NOT_GUARANTEE_KO)}</p>'
        "</section>"
    )
    return _shell(page_title=f"{SITE_TITLE} — 방법론", active_nav="methodology", body_html=body)

