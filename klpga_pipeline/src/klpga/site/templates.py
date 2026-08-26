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
from typing import Optional

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

METHODOLOGY_INTRO_KO = "NEO의 우승확률은 다음 원칙에 따라 계산됩니다."
METHODOLOGY_POINTS_KO = (
    "대회 시작 전(strictly pre-tournament)까지 확인된 정보만 사용합니다.",
    "선수의 과거 대회 성적(스코어의 파 대비 기록)을 활용합니다.",
    "선수의 최근 출전 흐름(최근 폼)을 반영합니다.",
    "이번 대회 출전 선수 전체를 하나의 필드로 두고, 그 안에서의 상대적 우승 가능성을 계산합니다.",
    "전체 출전 선수의 확률 합이 100%가 되도록 정규화합니다.",
)
METHODOLOGY_EXCLUSION_KO = (
    "현재 M4 모델은 스트로크게인드(Strokes Gained), 그린적중률(GIR), 드라이빙 거리/정확도, "
    "퍼팅, 코스 적합도 데이터를 사용하지 않습니다."
)
METHODOLOGY_LIMITATION_KO = (
    "M4는 알려진 보정(calibration) 한계가 있습니다: 특히 약 10~20% 구간의 확률이 "
    "실제보다 다소 과신되어 있을 수 있습니다. 이 한계는 현재 보정하지 않고 그대로 공개합니다."
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

RECONSTRUCTION_NOTE_KO = (
    "이 예측 기록은 최초로 성공한 대회 시작 전 운영(production) 실행 결과의 "
    "결정론적(deterministic) 재구성본입니다. 최초 실행의 전체 원본 CMD 출력이 "
    "자동으로 저장되지 않았기 때문입니다. 기록되어 있던 최초 실행 결과 값들과 "
    "교차 검증을 거친 뒤에만 보관되었습니다."
)

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
        f"<br><span class=\"detail-subvalue\">{h(RECENT_FORM_VALUE_LABEL_KO)}: "
        f"{entrant.prior_recent_form_10:.2f}</span>"
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
    verbatim (see docs/PREDICTIONS_SITE.md)."""
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


def _metadata_block_html(snapshot: PredictionSnapshot) -> str:
    return (
        '<dl class="metadata">'
        f'<dt>예측 번호</dt><dd>예측 #{h(snapshot.prediction_id)}</dd>'
        f'<dt>모델</dt><dd>{h(snapshot.model_id)} Production {h(snapshot.model_version)}</dd>'
        f'<dt>기준일</dt><dd>{h(snapshot.cutoff_date)}</dd>'
        f'<dt>출전 선수</dt><dd>{snapshot.field_size}명</dd>'
        f'<dt>참고 과거 대회 수</dt><dd>{snapshot.training_tournament_count}개</dd>'
        '</dl>'
    )


def _explanation_block_html() -> str:
    return (
        '<section class="explanation" aria-label="우승확률이란?">'
        '<h2>우승확률이란?</h2>'
        f'<p>{h(PROBABILITY_EXPLANATION_KO)}</p>'
        f'<p class="explanation-note">{h(PROBABILITY_SUM_NOTE_KO)} {h(PROBABILITY_NOT_GUARANTEE_KO)}</p>'
        '</section>'
    )


def _methodology_content_html(snapshot: Optional[PredictionSnapshot]) -> str:
    points = "".join(f"<li>{h(p)}</li>" for p in METHODOLOGY_POINTS_KO)
    limitation = h(METHODOLOGY_LIMITATION_KO)
    if snapshot is not None:
        for note in snapshot.known_limitations:
            if note not in METHODOLOGY_LIMITATION_KO:
                limitation += f'<br>{h(note)}'
    return (
        f'<p>{h(METHODOLOGY_INTRO_KO)}</p>'
        f'<ul class="methodology-points">{points}</ul>'
        f'<p class="methodology-exclusion">{h(METHODOLOGY_EXCLUSION_KO)}</p>'
        f'<p class="methodology-limitation">{limitation}</p>'
    )


def _methodology_block_html(snapshot: PredictionSnapshot) -> str:
    return (
        '<details class="panel">'
        '<summary>모델은 어떻게 계산하나요?</summary>'
        f'<div class="panel-body">{_methodology_content_html(snapshot)}</div>'
        '</details>'
    )


def _prediction_record_block_html(snapshot: PredictionSnapshot) -> str:
    reconstruction_html = ""
    if snapshot.provenance.get("source") == "rerun_reconstruction":
        reconstruction_html = f'<p class="record-note">{h(RECONSTRUCTION_NOTE_KO)}</p>'
    return (
        '<details class="panel">'
        '<summary>Prediction Record</summary>'
        '<div class="panel-body">'
        '<dl class="record-grid">'
        f'<dt>Prediction ID</dt><dd>{h(snapshot.prediction_id)}</dd>'
        f'<dt>Model version</dt><dd>{h(snapshot.model_id)} Production {h(snapshot.model_version)}</dd>'
        f'<dt>Cutoff</dt><dd>{h(snapshot.cutoff_date)}</dd>'
        '<dt>Archive status</dt><dd><span class="badge badge-locked">LOCKED</span> (수정 불가)</dd>'
        '</dl>'
        f'{reconstruction_html}'
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
        f"{_metadata_block_html(snapshot)}"
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


def render_methodology_page() -> str:
    body = (
        '<section class="methodology-page">'
        "<h1>모델은 어떻게 계산하나요?</h1>"
        f"{_methodology_content_html(None)}"
        f'<h2>우승확률이란?</h2>'
        f'<p>{h(PROBABILITY_EXPLANATION_KO)}</p>'
        f'<p class="explanation-note">{h(PROBABILITY_SUM_NOTE_KO)} {h(PROBABILITY_NOT_GUARANTEE_KO)}</p>'
        "</section>"
    )
    return _shell(page_title=f"{SITE_TITLE} — 방법론", active_nav="methodology", body_html=body)

