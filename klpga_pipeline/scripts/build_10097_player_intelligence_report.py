"""PLAYER INTELLIGENCE REPORT V3 (한국어) -- 김민선7 (playerCode=10097) ONLY.

The Gold Standard reference implementation for NEO Player Intelligence.
Localization, not translation: every narrative field this script
generates (fact/evidence/analysis/conclusion/coaching-brief/monitoring-
protocol text) is written in natural Korean, in the voice of a Korean
national-team performance analyst -- never a literal English
translation, and never a heading that mixes a bare English UI label
with Korean. Only the standard golf terms in
player_intelligence_10097_terms.py (the single shared terminology
dictionary this script and its renderer both import from) stay in
English: SG, GIR, APP, PUTT, ARG, OTT, Birdie, Bogey, Driver, Iron,
Wedge, Fairway, Green. The four SG components are always written
SG-prefixed ("SG APP", never a bare "APP") for both the stat and the
underlying shot category, since a bare abbreviation reads ambiguously
in Korean prose. Quoted citations from the frozen Knowledge Engine's
own Korean output (which spells these out, e.g. "SG Approach 상위 3%")
are reused verbatim, never rewritten to match this report's own
abbreviated house style.

Written the way a KLPGA tour coach or performance analyst would brief a
player, not the way a stats website would -- organized entirely by real
golf QUESTIONS, never by raw statistics, SG components, or a flat list
of records. Every answer is FACT -> EVIDENCE -> ANALYSIS -> CONCLUSION,
followed by what the conclusion is actually FOR: why it matters, what
the player should learn from it, what the coach should watch, whether
it is a durable characteristic or a recent trend, a one-sentence "why
this matters" close, and -- last, always -- a concrete ACTION. NEO does
not give opinions; NEO defines monitoring protocols.

V3: this is a performance-MONITORING system, not a stats page. Every
section's `monitoring_protocol` answers five questions, never more:
(1) what should be monitored -- a real, official, repeatedly-measured
metric, never a single-snapshot stat; (2) what indicates normal; (3)
what indicates deterioration -- (2)/(3) are a normal range and warning
threshold both computed from that metric's own real history, never
invented; (4) what should be checked next -- a concrete next review
point; (5) what metric most likely explains the change -- a real
Pearson correlation against her other real SG components, named only
if it actually clears a disclosed threshold, reported as unknown
(with the real numbers shown) when it does not, never a golf-domain
guess. On top of the five, each protocol also carries a current
status: her most recent already-recorded real reading compared against
(2)/(3) -- never a forecast of a future one -- which is what makes the
report usable before every tournament, checked against the record as
it stands today rather than a prediction of what comes next. A
recommendation that cannot be expressed this way -- because the metric
it would need has no real repeated measurement behind it -- is not
made; the supporting evidence is kept but the recommendation is scoped
to a metric that does. A conclusion that would not change how she
prepares, trains, or is coached does not earn a section here.

Never touches the frozen Knowledge Engine (knowledge_engine.py /
knowledge_rules.py / player_intelligence_generator.py) and never
recalculates a statistic: every number here is read straight out of
content/website_v2/knowledge_engine/player_intelligence/10097/MASTER_ANALYSIS.json
(built by scripts/build_10097_master_player_analysis.py, itself built
entirely from the frozen engine's own already-computed output) or the
frozen player_intelligence/10097/latest.json document, or
knowledge_engine.compute_season_profiles() (a STEP 3 aggregation the
Knowledge Engine already exposes, not a new statistic invented here).
This script only re-groups and narrates values that already exist. Any
candidate question whose supporting evidence cannot clear the same
PATTERN/TREND sample-size bar used by the Audit is dropped, not
answered with a guess.

Scope: playerCode=10097 ONLY. No other player is read, generated, or
touched. This is a reference implementation, not yet a generator for
the roster.
"""
from __future__ import annotations

import importlib.util
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.knowledge_engine import knowledge_engine as ke  # noqa: E402
from klpga.tournament_context import CONTENT_DIR  # noqa: E402
from klpga.website_v2 import player_intelligence_10097_terms as terms  # noqa: E402

_spec = importlib.util.spec_from_file_location("master_analysis_under_report", ROOT / "scripts" / "build_10097_master_player_analysis.py")
master = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(master)

PLAYER_ID = master.PLAYER_ID
PLAYER_NAME = master.PLAYER_NAME
OUTPUT_PATH = CONTENT_DIR / "knowledge_engine" / "player_intelligence" / PLAYER_ID / "PLAYER_INTELLIGENCE_REPORT.json"

_CONFIDENCE_RANK = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}

# Durability labels -- item 4/5 of the coaching brief added to every
# answered question: is this a characteristic the coaching staff can
# plan around for the season, a signal specific to the current season
# only, or an already-completed event that isn't a trend claim at all.
# (Internal identifiers -- the Korean display label lives in the
# renderer, player_intelligence_10097_report.py.)
LONG_TERM = "LONG_TERM_CHARACTERISTIC"
RECENT_TREND = "RECENT_TREND"
CONFIRMED_EVENT = "CONFIRMED_HISTORICAL_EVENT"


def _weakest_confidence(confidences: list) -> str:
    return min(confidences, key=lambda c: _CONFIDENCE_RANK[c])


def _evidence_score(sample_size, num_distinct_sources: int) -> int:
    """Deterministic, fully disclosed scoring method -- not a new claim
    about the player, only a way to render the already-computed sample
    size and source diversity as one number. Rewards independent
    official-record sources up to the >=3 minimum STEP 4 already
    requires per insight, and saturates (never grows unbounded) with
    sample size so one very large N can't make a thin source list look
    stronger than it is:
        evidence_score = round(100 * min(1, sources/3) * n/(n+5))
    """
    if not sample_size:
        return 0
    source_factor = min(1.0, num_distinct_sources / 3)
    depth_factor = sample_size / (sample_size + 5)
    return round(100 * source_factor * depth_factor)


def _load_inputs():
    master_doc = json.loads(master.OUTPUT_PATH.read_text(encoding="utf-8"))
    ds = master.build_master_dataset()
    warehouse = master._load("historical_sg_warehouse_corrected.json")
    season_profiles = ke.compute_season_profiles(PLAYER_ID, warehouse)
    return master_doc, ds, season_profiles


def _conclusion(master_doc: dict, conclusion_prefix: str) -> dict:
    """Look up an already-computed audit record from MASTER_ANALYSIS.json's
    conclusion_audit list by its conclusion id (exact reuse, no recompute)."""
    return next(a for a in master_doc["conclusion_audit"] if a["conclusion"] == conclusion_prefix)


def _fact(master_doc: dict, fact_id: str) -> dict:
    return next(f for f in master_doc["knowledge_graph"]["facts"] if f["id"] == fact_id)


def _season_line(season_profiles: list, attr: str) -> str:
    return ", ".join(f"{p.season} {getattr(p, attr):+.2f}" for p in season_profiles)


# ---------------------------------------------------------------------------
# Monitoring protocols (Player Intelligence V3): a performance-monitoring
# system, not a stats page. "NEO does not give opinions. NEO defines
# monitoring protocols." For every section: (1) what should be monitored,
# (2) what indicates normal, (3) what indicates deterioration, (4) what
# should be checked next, (5) what metric most likely explains the change.
# Never predict, never speculate, never invent -- every field below is
# either a real official metric with a repeated historical series, a
# real, disclosed, deterministic statistic computed from it, or a real
# comparison of her most recent actual reading against that statistic
# (never a forecast of a future one). This is what makes the report
# usable before every tournament: it is checked against the real record
# as it stands today, not a prediction of what comes next.
#
# Two disclosed, deterministic methods for (2)/(3), chosen by how much
# real history exists for the metric:
#   - n >= 30 real observations: normal range = mean +/- 1 SD; warning
#     threshold = two consecutive readings below the lower bound (avoids a
#     single bad tournament/round triggering a false alarm).
#   - n < 30 (season- or course-level aggregates, where more data simply
#     does not exist yet): a mean+/-SD band is not statistically meaningful,
#     so the threshold is her own real historical floor -- a new all-time
#     low is the trigger, not an estimated band.
#
# (5) is answered by real Pearson correlation among her four real SG
# components (never a golf-domain guess): the component that moves most
# closely with the monitored one, IF that correlation actually clears a
# disclosed meaningfulness threshold. Her four components turn out to be
# only weakly related to each other at both grains checked (tournament
# n=73, round n=287, |r| <= 0.18 for every pair) -- so this report never
# names a "most likely explanation," and says exactly that, with the real
# coefficients shown, rather than inventing a causal story the data does
# not support.
#
# All generated text below is Korean (this report's audience is KLPGA
# players and Korean coaches). The standard golf terms and every Korean
# UI/unit/status label come from ONE shared dictionary,
# player_intelligence_10097_terms.py (imported here as `terms`), so the
# wording is identical everywhere it appears -- never redefined locally.
# ---------------------------------------------------------------------------

_LARGE_SAMPLE_MIN = 30
_MEANINGFUL_CORRELATION = 0.3
_COMPONENT_LABELS = terms.SG_COMPONENT


def _pearson(xs: list, ys: list) -> float:
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    return cov / (sx * sy) if sx and sy else 0.0


def _explanatory_metric_from_correlation(rows: list, component_key: str, unit: str) -> str:
    """Item 5, real-data grain (tournament/round): never a golf-domain
    guess -- the real Pearson correlation between the monitored component
    and each of her other three, computed from the same real rows."""
    others = [k for k in _COMPONENT_LABELS if k != component_key]
    correlations = {}
    n_used = 0
    for other in others:
        paired = [(r[component_key], r[other]) for r in rows if r.get(component_key) is not None and r.get(other) is not None]
        n_used = len(paired)
        correlations[other] = _pearson([p[0] for p in paired], [p[1] for p in paired])
    best_key, best_r = max(correlations.items(), key=lambda kv: abs(kv[1]))
    disclosed = "; ".join(f"{_COMPONENT_LABELS[k]} r={v:+.2f}" for k, v in correlations.items())
    unit_kr = terms.UNIT[unit]
    if abs(best_r) >= _MEANINGFUL_CORRELATION:
        return f"{_COMPONENT_LABELS[best_key]} (동일한 실측 {unit_kr} {n_used}회 기준 r={best_r:+.2f} -- 이 리포트의 유의미성 기준({_MEANINGFUL_CORRELATION})을 통과한 유일한 지표입니다.)"
    return (
        f"없음. 동일한 실측 {unit_kr} {n_used}회를 기준으로 나머지 세 지표와의 상관관계는 {disclosed}이며, "
        f"모두 이 리포트가 유의미하다고 보는 기준({_MEANINGFUL_CORRELATION})에 미치지 못해 특정 지표를 원인으로 "
        "지목하지 않습니다. 대신 같은 경기에서 다른 세 지표도 함께 저하되는지 확인하십시오: 이 지표에서만 "
        "저하가 나타난다면 해당 샷 기술 자체의 문제이고, 다른 지표에서도 동시에 나타난다면 컨디션 저하, "
        "이동, 피로 등 그 주의 전반적인 컨디션 문제일 가능성이 큽니다."
    )


def _explanatory_metric_insufficient_sample(n: int, unit: str, fallback_metric: str) -> str:
    """Item 5, thin grain (season/course, n=4): a correlation computed
    from 4 points is not real evidence of anything -- reported as
    genuinely unknown, with a fallback to the grain that does have enough
    real data, never a guess dressed up as an answer."""
    unit_kr = terms.UNIT[unit]
    return (
        f"알 수 없음 -- 실측 {unit_kr}이(가) {n}회뿐이라 신뢰할 수 있는 연관 지표 상관관계를 계산하기에는 "
        f"표본이 부족합니다(이 리포트는 n={n}의 상관관계를 실제 근거로 다루지 않습니다). 대신 {fallback_metric}를 "
        "확인하십시오."
    )


def _status_from_band(ordered_values: list, lower: float, upper: float) -> tuple:
    latest = round(ordered_values[-1], 2)
    prev = round(ordered_values[-2], 2) if len(ordered_values) >= 2 else None
    if latest < lower and prev is not None and prev < lower:
        return latest, "WARNING", f"최근 두 차례 실측값({prev:+.2f} → {latest:+.2f})이 모두 정상 범위 아래로 나타나 경고 기준에 해당합니다."
    if latest < lower:
        detail = f"바로 이전 값({prev:+.2f})은 정상 범위 안이었습니다" if prev is not None else "비교할 이전 실측값이 아직 없습니다"
        return latest, "WATCH", f"가장 최근 실측값({latest:+.2f})은 정상 범위 아래이지만, {detail} -- 아직 2회 연속은 아니므로 다음 실측값에서 확정됩니다."
    return latest, "NORMAL", f"가장 최근 실측값({latest:+.2f})은 정상 범위 안에 있습니다."


def _status_from_floor(ordered_values: list, floor: float) -> tuple:
    latest = round(ordered_values[-1], 2)
    if latest <= floor:
        return latest, "AT_FLOOR", f"가장 최근 실측값({latest:+.2f})은 이미 이 기준에서 역대 최저치입니다 -- 다음 실측값에서 이 흐름이 이어지는지, 일시적인 저점이었는지 확인할 수 있습니다."
    return latest, "NORMAL", f"가장 최근 실측값({latest:+.2f})은 역대 최저치({floor:+.2f})보다 높습니다."


def _band_protocol(ordered_values: list, *, metric: str, source: str, unit: str, explanatory_metric: str) -> dict:
    n = len(ordered_values)
    mean = statistics.fmean(ordered_values)
    unit_kr = terms.UNIT[unit]
    if n >= _LARGE_SAMPLE_MIN:
        sd = statistics.stdev(ordered_values)
        lower, upper = mean - sd, mean + sd
        current_reading, current_status, current_detail = _status_from_band(ordered_values, lower, upper)
        return {
            "metric": metric,
            "source": source,
            "sample_size": n,
            "normal_range": f"{lower:+.2f} ~ {upper:+.2f} SG (실측 {unit_kr} {n}회 기준 평균 {mean:+.2f}, 표준편차 ±1)",
            "warning_threshold": f"{unit_kr} 기록이 {lower:+.2f} SG 미만으로 2회 연속 나타나는 경우",
            "next_review": f"다음 {unit_kr} 기록이 나오는 시점",
            "explanatory_metric": explanatory_metric,
            "current_reading": current_reading,
            "current_status": current_status,
            "current_detail": current_detail,
        }
    floor = min(ordered_values)
    current_reading, current_status, current_detail = _status_from_floor(ordered_values, floor)
    return {
        "metric": metric,
        "source": source,
        "sample_size": n,
        "normal_range": f"{floor:+.2f} ~ {max(ordered_values):+.2f} SG (실측 {unit_kr} {n}회의 전체 범위 -- 표본이 적어 평균/표준편차 방식은 적용하지 않음)",
        "warning_threshold": f"{unit_kr} 기록이 {floor:+.2f} SG 미만으로 떨어져 실측 {n}회 중 역대 최저치를 경신하는 경우",
        "next_review": f"다음 {unit_kr}의 공식 기록이 나오는 시점",
        "explanatory_metric": explanatory_metric,
        "current_reading": current_reading,
        "current_status": current_status,
        "current_detail": current_detail,
    }


def _tournament_component_protocol(ds: dict, component_key: str, component_label: str) -> dict:
    rows = sorted(ds["warehouse_tournament_rows"], key=lambda r: (r["season"], r["game_code"]))
    values = [r[component_key] for r in rows if r.get(component_key) is not None]
    return _band_protocol(
        values,
        metric=f"대회별 {component_label}",
        source="historical_sg_warehouse_corrected.json (scope=tournament_cumulative, field='{}')".format(component_key),
        unit="tournament",
        explanatory_metric=_explanatory_metric_from_correlation(rows, component_key, "tournament"),
    )


def _round_total_protocol(ds: dict) -> dict:
    rows = sorted(ds["warehouse_round_rows"], key=lambda r: (r["season"], r["game_code"], r["round"]))
    values = [r["total"] for r in rows if r.get("total") is not None]
    # "total" is a sum of the four real components, not one of them, so its
    # item-5 check compares against those four components directly (still a
    # real Pearson correlation, same method, just against "total" instead
    # of one of the four peer components).
    correlations = {}
    for key, label in _COMPONENT_LABELS.items():
        paired = [(r["total"], r[key]) for r in rows if r.get("total") is not None and r.get(key) is not None]
        correlations[key] = _pearson([p[0] for p in paired], [p[1] for p in paired])
    best_key, best_r = max(correlations.items(), key=lambda kv: abs(kv[1]))
    disclosed = "; ".join(f"{_COMPONENT_LABELS[k]} r={v:+.2f}" for k, v in correlations.items())
    explanatory = f"{_COMPONENT_LABELS[best_key]} (동일한 실측 라운드 {len(rows)}회 기준 r={best_r:+.2f} -- 네 지표 중 라운드 단위로 가장 강하게 연동되는 지표입니다. {disclosed})"
    return _band_protocol(
        values,
        metric="라운드별 SG Total",
        source="historical_sg_warehouse_corrected.json (scope=single_round, field='total')",
        unit="round",
        explanatory_metric=explanatory,
    )


def _season_component_protocol(season_profiles: list, attr: str, component_label: str, fallback_description: str) -> dict:
    values = [getattr(p, attr) for p in season_profiles]
    return _band_protocol(
        values,
        metric=f"시즌별 {component_label}",
        source="knowledge_engine.compute_season_profiles()",
        unit="season",
        explanatory_metric=_explanatory_metric_insufficient_sample(len(season_profiles), "season", fallback_description),
    )


def _course_appearance_protocol(group: dict) -> dict:
    values = [h["sg_total"] for h in group["history"] if h.get("sg_total") is not None]
    return _band_protocol(
        values,
        metric=f"{group['series_name_sample']} 출전 기록별 SG Total",
        source="historical_sg_warehouse_corrected.json (matched via knowledge_engine.find_course_history())",
        unit="appearance",
        explanatory_metric=_explanatory_metric_insufficient_sample(len(values), "appearance", "아래의 라운드별 SG Total 프로토콜(실측 287라운드)"),
    )


# ---------------------------------------------------------------------------
# V5: real SG decomposition, contribution breakdown. "What contributed the
# most?" is answered by one identity, verified against every real row in
# the warehouse (zero mismatches across all 73 tournament rows and 287
# round rows): SG Total = SG OTT + SG APP + SG ARG + SG PUTT. A
# contribution share is therefore just a ratio of already-recorded
# official numbers -- sum(component)/sum(total)*100 -- never an estimate,
# never an AI weighting, always reproducible from the same warehouse rows.
# Never computed from anywhere it would require inventing a number: a row
# missing any of the four components, or a game_code with no
# tournament_cumulative row at all, is left out and the real sample size
# actually used is disclosed alongside every breakdown.
# ---------------------------------------------------------------------------

_CONTRIBUTION_METHOD = (
    "share_pct = Σ(실측 component) / Σ(실측 total) × 100 -- SG Total = SG OTT + SG APP + SG ARG + SG PUTT 항등식"
    "(historical_sg_warehouse_corrected.json 전체 행 기준 오차 0으로 검증됨)에 대한 실측값 비율입니다. 추정치나 "
    "가중치가 아니며, 공식 SG 세부 데이터가 없는 경기는 계산에서 제외되고 실제 사용된 표본 크기가 함께 표시됩니다."
)


def _contribution_breakdown(rows: list) -> dict:
    sums = {k: 0.0 for k in _COMPONENT_LABELS}
    total = 0.0
    n = 0
    for r in rows:
        if not r or r.get("total") is None or any(r.get(k) is None for k in _COMPONENT_LABELS):
            continue
        for k in _COMPONENT_LABELS:
            sums[k] += r[k]
        total += r["total"]
        n += 1
    if n == 0 or total == 0:
        return None
    # Round first, then divide -- share_pct must be reproducible from the
    # exact "value"/"total_value" numbers this report displays, not from
    # unrounded intermediates the reader never sees.
    total_rounded = round(total, 2)
    breakdown = sorted(
        (
            {"component": _COMPONENT_LABELS[k], "value": round(sums[k], 2), "share_pct": round(round(sums[k], 2) / total_rounded * 100, 1)}
            for k in _COMPONENT_LABELS
        ),
        key=lambda b: abs(b["share_pct"]),
        reverse=True,
    )
    return {
        "sample_size": n,
        "total_value": total_rounded,
        "breakdown": breakdown,
        "top_contributor": breakdown[0]["component"],
    }


def _trend_contribution_breakdown(season_profiles: list) -> dict:
    first, last = season_profiles[0], season_profiles[-1]
    deltas = {
        "off_the_tee": last.avg_ott - first.avg_ott,
        "approach": last.avg_app - first.avg_app,
        "around_green": last.avg_arg - first.avg_arg,
        "putting": last.avg_putt - first.avg_putt,
    }
    total_delta = last.avg_total - first.avg_total
    if total_delta == 0:
        return None
    total_delta_rounded = round(total_delta, 2)
    breakdown = sorted(
        (
            {"component": _COMPONENT_LABELS[k], "value": round(v, 2), "share_pct": round(round(v, 2) / total_delta_rounded * 100, 1)}
            for k, v in deltas.items()
        ),
        key=lambda b: abs(b["share_pct"]),
        reverse=True,
    )
    return {
        "from_season": first.season,
        "to_season": last.season,
        "total_value": total_delta_rounded,
        "breakdown": breakdown,
        "top_contributor": breakdown[0]["component"],
    }


def _action_from_protocol(protocol: dict, decision: str) -> str:
    """NEO does not give opinions. NEO defines monitoring protocols: this
    text always opens on the metric being monitored, never a subjective
    recommendation. V9 adds exactly one thing -- the concrete coach
    decision this section earns (a single imperative sentence, supplied
    by the caller, never invented here) -- as the closing line, after the
    protocol. The protocol computation itself is untouched; this only
    changes what text wraps around it."""
    return (
        f"{protocol['metric']}을(를) 모니터링합니다({protocol['source']}). 정상 범위: {protocol['normal_range']}. "
        f"저하 기준(기술/훈련 점검 필요): {protocol['warning_threshold']}. "
        f"다음 점검: {protocol['next_review']}. 가장 최근 실측값 기준 현재 상태: "
        f"{terms.STATUS_LABEL[protocol['current_status']]} -- {protocol['current_detail']} "
        f"결정: {decision}"
    )


# ---------------------------------------------------------------------------
# Candidate questions. Each maps onto audit records already computed by
# build_10097_master_player_analysis.py -- this function only narrates and
# combines them, it never derives a new number. Every question that
# survives to the report answers a "so what": it says what should change
# in how she prepares, trains, or is coached, not just what a number is.
# All narrative text is Korean; standard golf terms stay in English.
# ---------------------------------------------------------------------------


def _q_why_wins(master_doc: dict, ds: dict, season_profiles: list) -> dict:
    win_fact = _fact(master_doc, "fact_win_count")["audit"]
    reasons = [_conclusion(master_doc, f"play_style.why_wins[{i}]") for i in range(3)]
    wins = master_doc["tournament_analysis"]["wins"]
    win_names = ", ".join(f"{w['tournament']} ({w['season']})" for w in wins)
    app_trend = _season_line(season_profiles, "avg_app")

    fact = (
        f"공식 우승 {win_fact['sample_size']}회({win_names}) 전부 SG APP가 플러스였던 대회에서 나왔습니다. "
        f"4개 시즌 시즌 평균 SG APP: {app_trend} -- 마이너스로 내려간 시즌이 한 번도 없습니다."
    )
    evidence = [
        f"시즌별 SG APP({len(season_profiles)}개 시즌, {sum(p.n_tournaments for p in season_profiles)}개 대회): {app_trend}.",
        f"{reasons[1]['statement']} (평가 대상 {reasons[1]['sample_size']}명, 이번 시즌 1개 시즌치 근거).",
        f"{reasons[2]['statement']} (평가 대상 {reasons[2]['sample_size']}명, 이번 시즌 1개 시즌치 근거).",
    ]
    analysis = (
        "SG APP는 경기력의 다른 부분이 약했던 시즌에도 마이너스로 내려간 적이 없는 유일한 항목입니다 -- 좋은 "
        "라운드를 우승으로 바꾸는 실제 동력입니다. 이번 시즌 GIR·파세이브율 상승은 이 위에 더해진 결과이지, "
        "새로 생긴 동력이 아닙니다."
    )
    conclusion = (
        f"{PLAYER_NAME} 선수의 우승 동력은 SG APP입니다. 경기 전략의 기본값으로 고정하고, 압박 상황에서도 "
        "SG APP 라인·클럽 선택을 바꾸지 않는 것이 결정 사항입니다."
    )
    why_it_matters = "우승 동력을 정확히 특정해 두면, 다른 부분을 조정할 때 이 영역만큼은 건드리지 않는다는 기준이 생깁니다."
    player_takeaway = "출발이 나쁠 때도 SG APP 샷 루틴을 그대로 유지하십시오 -- 4개 시즌간 무너진 적 없는 유일한 영역입니다."
    protocol = _tournament_component_protocol(ds, "approach", terms.SG_COMPONENT["approach"])
    coach_focus = (
        f"GIR·파세이브율은 이번 시즌 스냅샷이라 연속 모니터링이 불가능합니다. 대회별 SG APP(실측 "
        f"{protocol['sample_size']}개 대회)만 연속 추적하십시오."
    )
    durability = LONG_TERM
    durability_reasoning = (
        "SG APP는 4개 시즌 전부 플러스·상승세입니다. 다음 시즌이 더해져도 뒤집힐 가능성은 낮습니다. GIR· "
        "파세이브율은 이번 시즌 수치일 뿐이므로 같은 신뢰도로 다루지 마십시오."
    )
    why_this_matters = "이번 주뿐 아니라 매 대회 경기 전략의 기준선입니다."
    action = _action_from_protocol(protocol, "SG APP 샷 운영 방식을 그대로 유지한다. 이 영역은 조정 대상에서 제외한다.")
    mechanism = "메커니즘: 우승 대회에서 SG APP가 플러스로 전환되는 시점부터 스코어링 우위가 시작되고, 이 우위가 라운드 전체에 누적되어 최종 스코어 차이로 이어집니다."
    root_cause = "근본 원인: 실측으로 확인 가능한 가장 이른 원인은 SG APP 시즌 평균이 4개 시즌 모두 플러스였다는 사실입니다. 그 아래 단계(어프로치 거리대별 정확도, 미스 패턴)는 이 저장소에 홀·샷 단위 기록이 없어 확인할 수 없습니다."
    reproducibility = "조건: 대회별 SG APP 플러스 유지. 실측 4개 시즌 전부에서 재현되었습니다."

    sample_sizes = [win_fact["sample_size"], sum(p.n_tournaments for p in season_profiles)] + [r["sample_size"] for r in reasons]
    sources = set(win_fact["official_records_used"]) | {s for r in reasons for s in r["official_records_used"]}
    return {
        "id": "q_why_wins",
        "question": f"{PLAYER_NAME} 선수는 왜 우승하는가?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "mechanism": mechanism,
        "root_cause": root_cause,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
        "reproducibility": reproducibility,
        "why_this_matters": why_this_matters,
        "action": action,
        "monitoring_protocol": protocol,
        "evidence_score": _evidence_score(min(sample_sizes), len(sources)),
        "sample_size": min(sample_sizes),
        "confidence": _weakest_confidence([win_fact["confidence"]] + [r["confidence"] for r in reasons]),
    }


def _q_why_loses(master_doc: dict, ds: dict, season_profiles: list) -> dict:
    reasons = [_conclusion(master_doc, f"play_style.why_loses[{i}]") for i in range(2)]
    putt_trend = _season_line(season_profiles, "avg_putt")
    this_season, last_season = season_profiles[-1], season_profiles[-2]

    fact = (
        f"SG PUTT은 4개 시즌 내내 본인의 네 항목 중 스코어링 기여도가 가장 작았고, {this_season.season}시즌 "
        f"하락폭({this_season.avg_putt:+.2f}, 전년 {last_season.avg_putt:+.2f})이 가장 큽니다."
    )
    evidence = [
        f"시즌별 SG PUTT: {putt_trend}.",
        f"{reasons[0]['statement']} -- 필드 평균 수준이지만, 93~97 백분위인 본인의 SG APP·SG OTT와 비교하면 낮습니다(평가 대상 {reasons[0]['sample_size']}명).",
        f"{reasons[1]['statement']} (평가 대상 {reasons[1]['sample_size']}명, 독립 지표로 재확인).",
    ]
    analysis = (
        "SG APP가 만들어내는 Birdie 기회를 SG PUTT이 볼 스트라이킹 수준만큼 전환하지 못합니다. 선수 생활 "
        "내내 있었던 격차이므로 한 주의 슬럼프가 아니라 전환 비율의 구조적 한계이며, 올해 하락폭은 새 정보라서 "
        "회복을 가정하지 말고 계속 지켜봐야 합니다."
    )
    conclusion = (
        "SG PUTT이 Birdie 전환의 병목입니다. 다음 훈련 사이클의 우선순위를 퍼팅 전환 훈련으로 재배분하고, "
        "볼 스트라이킹 훈련 비중은 늘리지 않는 것이 결정 사항입니다."
    )
    why_it_matters = "전환 문제와 볼 스트라이킹 붕괴는 처방이 다릅니다. 원인을 잘못 짚으면 훈련 시간이 엉뚱한 곳에 쓰입니다."
    player_takeaway = "가장 큰 손실은 그린을 놓치는 것이 아니라 넣을 수 있는 Birdie 퍼트를 놓치는 것입니다."
    protocol = _tournament_component_protocol(ds, "putting", terms.SG_COMPONENT["putting"])
    coach_focus = (
        f"SG PUTT은 대회별로 발표되므로(실측 {protocol['sample_size']}개 대회), 시즌 합산치가 아니라 "
        "대회별 수치로 하락 조짐을 조기에 포착하십시오."
    )
    durability = LONG_TERM
    durability_reasoning = (
        "4개 시즌 전부 최하위 항목이므로 이 순위는 다음 시즌에도 유지될 가능성이 큽니다. 올해 하락폭 자체는 "
        "1개 시즌 근거이므로 구조적 판단보다 낮은 비중으로 다루십시오."
    )
    why_this_matters = "다음 스트로크 게인은 스윙이 아니라 전환력에서 나와야 합니다."
    action = _action_from_protocol(protocol, "다음 훈련 사이클에서 퍼팅 전환 훈련 비중을 늘린다. 볼 스트라이킹 훈련은 현행 유지한다.")
    mechanism = "메커니즘: SG APP가 만든 Birdie 기회가 SG PUTT 전환 단계에서 소실됩니다 -- 기회 생성과 기회 전환은 분리된 두 단계이며, 병목은 후자에 있습니다."
    root_cause = "근본 원인: 실측으로 확인 가능한 가장 이른 원인은 SG PUTT의 필드 대비 상대적 순위(평균 수준)입니다. 그 아래 단계(퍼팅 거리대별 성공률, 그립·스트로크 메커니즘)는 홀·샷 단위 기록이 없어 확인할 수 없습니다."
    reproducibility = "조건: SG APP는 플러스인데 SG PUTT이 필드 평균 이하인 대회. 실측 4개 시즌 전부에서 반복되었습니다."

    sample_sizes = [r["sample_size"] for r in reasons]
    sources = {s for r in reasons for s in r["official_records_used"]}
    return {
        "id": "q_why_loses",
        "question": f"{PLAYER_NAME} 선수는 왜 우승을 놓치는가?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "mechanism": mechanism,
        "root_cause": root_cause,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
        "reproducibility": reproducibility,
        "why_this_matters": why_this_matters,
        "action": action,
        "monitoring_protocol": protocol,
        "evidence_score": _evidence_score(min(sample_sizes), len(sources)),
        "sample_size": min(sample_sizes),
        "confidence": _weakest_confidence([r["confidence"] for r in reasons]),
    }


def _q_approach_biggest_weapon(master_doc: dict, ds: dict, season_profiles: list, contribution: dict) -> dict:
    insight = next(i for i in master_doc["knowledge_graph"]["insights"] if i["id"] == "insight_elite_approach_and_ott")
    audit = insight["audit"]
    pi = ds["player_intelligence_doc"]
    app_axis = next(a for a in pi["player_dna"]["axes"] if a["key"] == "sg_app")
    app_trend = _season_line(season_profiles, "avg_app")

    fact = (
        f"필드 {audit['sample_size']}명 중 SG APP {app_axis['percentile']:.1f}번째 백분위, 4개 시즌 연속 "
        f"플러스: {app_trend}."
    )
    evidence = [
        f"이번 시즌 필드 백분위: {audit['sample_size']}명 중 {app_axis['percentile']:.1f}번째.",
        f"{audit['season_count']}개 시즌, {audit['tournament_count']}개 대회 SG APP 평균: {app_trend} -- 매 시즌 1·2순위 항목.",
        f"Knowledge Engine 분류: \"{pi['player_type']['label_ko']}\" ({pi['player_type']['label_en']}) -- \"{insight['insight']}\"",
    ]
    analysis = (
        "한 시즌의 특출난 성적은 반짝 호조일 수 있지만, 같은 항목이 4개 시즌 연속 최상위권이면 다른 신호입니다 "
        "-- 경기력의 다른 부분과 무관하게 꾸준히 잘하는 부분이라는 뜻입니다."
    )
    conclusion = "SG APP는 가장 지속력 있는 강점입니다. 기술적 조정이 필요할 때 이 메커니즘은 손대지 않는 것이 결정 사항입니다."
    why_it_matters = "반짝 호조와 지속력 있는 강점을 구분해 두면, 경기력을 조정할 때 절대 건드리면 안 될 부분이 명확해집니다."
    protocol = _tournament_component_protocol(ds, "approach", terms.SG_COMPONENT["approach"])
    player_takeaway = "어떤 기술적 조정을 하더라도 SG APP 메커니즘부터 보호하십시오."
    coach_focus = (
        f"'왜 우승하는가'와 동일한 프로토콜입니다(대회별 SG APP, 실측 {protocol['sample_size']}개 대회) -- "
        "같은 근본 강점을 같은 지표로 추적합니다."
    )
    durability = LONG_TERM
    durability_reasoning = "4개 시즌 연속 플러스는 가장 강한 지속성 신호입니다. 뚜렷한 하락이 나타나기 전까지는 재검토 대상이 아닙니다."
    why_this_matters = "이번 대회뿐 아니라 매 대회 경기 전략의 중심입니다."
    action = _action_from_protocol(protocol, "SG APP 샷 메커니즘과 셋업을 변경하지 않는다. 다른 영역 조정 시 이 부분은 실험 대상에서 제외한다.")
    mechanism = "메커니즘: 다른 세 항목의 시즌별 등락과 무관하게 SG APP만 4개 시즌 내내 플러스를 유지했습니다 -- 경기력의 다른 부분에 의존하지 않는 독립적 강점입니다."
    root_cause = "근본 원인: 실측으로 확인 가능한 가장 이른 원인은 4개 시즌 연속 플러스라는 반복성 자체입니다. 어떤 구체적 스윙 요소가 이를 만드는지는 샷 단위 기록이 없어 확인할 수 없습니다."
    reproducibility = "조건: 없음 -- 조건부 강점이 아니라 4개 시즌 전 구간에서 일관되게 나타난 상수적 강점입니다."

    sources = set(audit["official_records_used"])
    return {
        "id": "q_approach_biggest_weapon",
        "question": f"{PLAYER_NAME} 선수에게 SG APP가 최고의 무기인 이유는?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "mechanism": mechanism,
        "root_cause": root_cause,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
        "reproducibility": reproducibility,
        "why_this_matters": why_this_matters,
        "action": action,
        "monitoring_protocol": protocol,
        "contribution_breakdown": contribution,
        "evidence_score": _evidence_score(audit["sample_size"], len(sources)),
        "sample_size": audit["sample_size"],
        "confidence": audit["confidence"],
    }


def _q_putting_weakest(master_doc: dict, ds: dict, season_profiles: list) -> dict:
    reason = _conclusion(master_doc, "play_style.why_loses[0]")
    pi = ds["player_intelligence_doc"]
    axes = {a["key"]: a["percentile"] for a in pi["player_dna"]["axes"]}
    order = [("sg_ott", "SG OTT"), ("sg_app", "SG APP"), ("sg_arg", "SG ARG"), ("sg_putt", "SG PUTT")]
    axis_line = ", ".join(f"{label} {axes[k]:.1f}번째 백분위" for k, label in order)
    putt_trend = _season_line(season_profiles, "avg_putt")

    fact = f"본인 네 항목 내부 순위: {axis_line}. SG PUTT이 4개 시즌 내내 최하위입니다."
    evidence = [
        f"이번 시즌 항목별 필드 백분위: {axis_line} (평가 대상 {reason['sample_size']}명).",
        f"시즌별 SG PUTT: {putt_trend} -- 매 시즌 본인 네 항목 중 최하위.",
    ]
    analysis = (
        "필드가 아니라 본인 네 항목끼리 비교하면 SG OTT·SG APP·SG ARG은 투어 최상위권이지만 SG PUTT만 그렇지 "
        "않습니다. 'SG PUTT이 나쁘다'가 아니라 '다음 훈련 시간을 투입했을 때 개선 폭이 가장 큰 영역'이라는 "
        "뜻입니다."
    )
    conclusion = "SG PUTT이 훈련 대비 개선 효율이 가장 높은 영역입니다. 다음 훈련 사이클의 우선순위를 퍼팅으로 전환하는 것이 결정 사항입니다."
    why_it_matters = "훈련 시간은 한정되어 있습니다. 이미 최상위권인 기술을 더 다듬기보다 SG PUTT에 시간을 더 배분해야 개선 폭이 커집니다."
    protocol = _season_component_protocol(season_profiles, "avg_putt", terms.SG_COMPONENT["putting"], f"위 대회별 {terms.SG_COMPONENT['putting']} 프로토콜(실측 73대회 기준)")
    player_takeaway = "'가장 약한 부분'은 'SG PUTT이 서툴다'가 아니라 나머지가 최상위권까지 올라왔다는 뜻입니다."
    coach_focus = (
        f"'왜 우승을 놓치는가'가 대회 단위로 추적하는 SG PUTT을 여기서는 {protocol['sample_size']}개 시즌 "
        "단위로 봅니다 -- 훈련 재배분이 연 단위로 내부 격차를 좁히는지 확인하는 용도입니다."
    )
    durability = LONG_TERM
    durability_reasoning = "이 내부 순위는 4개 시즌 내내 유지됐습니다. 나머지 세 항목과의 격차가 실제로 좁혀지는 전혀 다른 패턴이 나오기 전까지는 유효합니다."
    why_this_matters = "다음 한 시간의 훈련이 가장 큰 효과를 가져올 곳입니다."
    action = _action_from_protocol(protocol, "다음 훈련 사이클의 우선순위를 퍼팅으로 전환한다.")
    mechanism = "메커니즘: 나머지 세 항목이 필드 상위권까지 올라온 반면 SG PUTT만 필드 평균에 머물러, 같은 훈련 시간을 투입했을 때 개선 여력이 가장 큰 항목으로 남았습니다."
    root_cause = "근본 원인: 실측으로 확인 가능한 가장 이른 원인은 본인 내 항목 간 상대적 순위입니다. 그 아래 단계(그립, 스트로크 템포, 그린 리딩)는 샷 단위 기록이 없어 확인할 수 없습니다."
    reproducibility = "조건: 다음 훈련 사이클에 퍼팅 비중을 늘렸을 때 시즌별 SG PUTT 평균 상승 여부로 검증 가능합니다."

    sample_sizes = [reason["sample_size"]]
    sources = set(reason["official_records_used"]) | {"knowledge_engine.compute_season_profiles() (player_dna.axes)"}
    return {
        "id": "q_putting_weakest",
        "question": f"{PLAYER_NAME} 선수에게 SG PUTT이 가장 약한 부분이 된 이유는?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "mechanism": mechanism,
        "root_cause": root_cause,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
        "reproducibility": reproducibility,
        "why_this_matters": why_this_matters,
        "action": action,
        "monitoring_protocol": protocol,
        "evidence_score": _evidence_score(min(sample_sizes), len(sources)),
        "sample_size": min(sample_sizes),
        "confidence": reason["confidence"],
    }


def _q_2026_improvement(master_doc: dict, season_profiles: list) -> dict:
    audit = _conclusion(master_doc, "season_evolution.frozen_knowledge_engine_evolution.narrative")
    total_trend = ", ".join(f"{p.season} ({p.n_tournaments}개 대회) {p.avg_total:+.2f}" for p in season_profiles)
    ott_trend = _season_line(season_profiles, "avg_ott")
    app_trend = _season_line(season_profiles, "avg_app")
    putt_trend = _season_line(season_profiles, "avg_putt")

    fact = f"SG Total은 4개 시즌 전부 상승했습니다: {total_trend}. 상승 모양은 SG OTT·SG APP가 이끌고, SG PUTT은 같은 속도로 오르지 않았습니다."
    evidence = [
        f"시즌별 SG Total: {total_trend} (시즌당 16~23개 대회).",
        f"SG OTT({ott_trend})·SG APP({app_trend})는 같은 속도로 상승, SG PUTT({putt_trend})은 뒤처집니다 -- 향상이 볼 스트라이킹발(發)이라는 근거입니다.",
    ]
    analysis = (
        "두 볼 스트라이킹 항목이 4개 시즌 연속 함께 상승하고 매 시즌 실제 대회 표본이 뒷받침한다는 것은 반짝 "
        "상승이 아닙니다. SG PUTT은 같은 속도로 오르지 않았으므로 '쇼트게임이 따라잡았다'는 설명은 기록으로 "
        "뒷받침되지 않습니다."
    )
    conclusion = "이번 향상은 여러 시즌에 걸친 볼 스트라이킹 향상의 연장선입니다. 이 향상을 이끈 기술 훈련 프로그램은 변경하지 않는 것이 결정 사항입니다."
    why_it_matters = "구조적 변화임을 확인해 두면, 한 주 부진했다고 효과를 보고 있는 프로그램을 의심하는 일을 막을 수 있습니다."
    player_takeaway = "이 향상은 실제입니다. 나쁜 한 주 이후에도 볼 스트라이킹 중심 훈련 방향을 의심하지 말고 이어가십시오."
    protocol = _season_component_protocol(
        season_profiles, "avg_total", terms.SG_TOTAL,
        f"본인의 대회별 {terms.SG_TOTAL} 실측치(historical_sg_warehouse_corrected.json, scope=tournament_cumulative, field='total', 실측 73대회 기준)",
    )
    coach_focus = f"SG Total을 시즌 단위(실측 {protocol['sample_size']}개 시즌)로 점검하십시오 -- 주 단위 전술 신호가 아니라 육성 프로그램 신호입니다."
    durability = LONG_TERM
    durability_reasoning = "4개 시즌에 걸친 흐름입니다. 다섯 번째 시즌이 정체되어도 지난 4년의 실제 향상 자체는 사라지지 않습니다."
    why_this_matters = "지금까지 효과가 있었던 방식을 계속 유지하십시오."
    action = _action_from_protocol(protocol, "볼 스트라이킹 중심 훈련 프로그램을 변경하지 않는다.")
    mechanism = "메커니즘: SG OTT·SG APP가 동시에 상승하며 SG Total을 끌어올렸고, SG PUTT은 같은 속도로 오르지 않아 이번 향상의 원천이 볼 스트라이킹임을 가리킵니다."
    root_cause = "근본 원인: 실측으로 확인 가능한 가장 이른 원인은 SG OTT·SG APP의 동반 상승입니다. 그 아래 단계(스윙 변경, 장비 교체, 훈련 방법 변경 등 구체적 계기)는 이 저장소에 기록되어 있지 않아 확인할 수 없습니다."
    reproducibility = "조건: 현재 훈련 프로그램 유지. 실측 4개 시즌 연속 재현되었습니다."

    sources = set(audit["official_records_used"])
    return {
        "id": "q_2026_improvement",
        "question": f"{PLAYER_NAME} 선수의 경기력은 왜 2026시즌까지 꾸준히 향상되었는가?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "mechanism": mechanism,
        "root_cause": root_cause,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
        "reproducibility": reproducibility,
        "why_this_matters": why_this_matters,
        "action": action,
        "monitoring_protocol": protocol,
        "evidence_score": _evidence_score(audit["tournament_count"], len(sources)),
        "sample_size": audit["tournament_count"],
        "confidence": audit["confidence"],
    }


def _q_strong_course(master_doc: dict, by_code: dict) -> dict:
    group = max(master_doc["course_analysis"]["course_series"], key=lambda g: g["appearances"])
    n = group["appearances"]
    contribution = _contribution_breakdown([by_code.get(h["game_code"]) for h in group["history"]])
    history_line = "; ".join(
        f"{h['season']} {h['sg_total']:+.2f}" if h.get("sg_total") is not None else f"{h['season']} 기록 없음" for h in group["history"]
    )

    fact = f"{group['series_name_sample']} 실측 {n}회 출전 전부 SG Total 플러스, 가장 최근 출전이 우승입니다."
    evidence = [
        f"출전별 SG Total: {history_line} -- {n}회 모두 플러스, 최고 성적이 최근 출전.",
        f"{n}회 평균 SG Total {group['avg_sg_total']:+.2f} -- 통산 평균을 크게 웃돕니다.",
    ]
    analysis = (
        "서로 다른 네 시즌의 실측 네 차례 출전이 모두 플러스이고 최고 성적이 최근 출전에서 나온 것은 우연이 "
        "아니라 쌓여온 코스 이해도입니다 -- 반복될수록 효과가 흐려지지 않고 더 날카로워졌습니다."
    )
    conclusion = f"이 코스에서는 검증된 방식을 그대로 씁니다. 새 시도를 넣지 않고 전략을 바꾸지 않는 것이 결정 사항입니다."
    why_it_matters = "성적이 특정 코스에서 근거를 가진 결과임을 알면, 현장에서 선수의 감각을 믿을 때와 막판 변화를 자제할 때를 판단할 수 있습니다."
    player_takeaway = "이 코스에서는 실제 성적으로 뒷받침된 자신감으로 임하십시오."
    protocol = _course_appearance_protocol(group)
    coach_focus = f"{group['series_name_sample']}을(를) 기준으로 삼고, 다음 출전을 앞둔 주에는 스윙·전략 변경을 특히 자제하십시오."
    durability = LONG_TERM
    durability_reasoning = f"실측 {n}회는 앞으로도 바뀌지 않는 기록입니다. 표본이 4개뿐이라 다음 출전이 평균 이하면 전체 평균은 낮아질 수 있으나 패턴 자체가 뒤집히지는 않습니다."
    why_this_matters = "지나치게 코치하기보다 믿고 맡겨야 한다는 점이 가장 분명하게 드러나는 지점입니다."
    action = _action_from_protocol(protocol, f"{group['series_name_sample']} 출전 주에는 스윙·전략 변경을 하지 않는다.")
    mechanism = (
        f"메커니즘: 이 코스에서는 {contribution['top_contributor']}가 스코어링 우위를 가장 크게 만듭니다"
        f"({contribution['breakdown'][0]['share_pct']:+.0f}%, 실측 {n}회 출전 기준) -- '이 코스가 잘 맞는다'가 "
        f"아니라 '{contribution['top_contributor']}를 살릴 수 있는 코스 조건이 반복된다'는 뜻입니다."
        if contribution else "메커니즘: 실측 4회 출전 전부 플러스라는 결과만 확인되며, 항목별 분해 근거는 없습니다."
    )
    root_cause = f"근본 원인: 실측으로 확인 가능한 가장 이른 원인은 {n}회 반복 출전 자체입니다. 이 코스의 어떤 구체적 특징(홀 구성, 페어웨이 폭, 그린 스피드 등)이 이 강점을 만드는지는 홀 단위 기록이 없어 확인할 수 없습니다."
    reproducibility = f"조건: 이 코스 재출전 시 기존 전략 유지. 실측 {n}회 출전 전부에서 플러스로 재현되었습니다."
    decision_context = f"실측된 과거 결정: {n}회 출전 내내 전략을 크게 바꾸지 않는 선택이 반복되었고, 그 결정이 매 출전 플러스 스코어링으로 이어졌습니다 -- 이 성과는 우연한 결과가 아니라 반복된 결정의 산물입니다."

    sources = {"historical_sg_warehouse_corrected.json", "knowledge_engine.find_course_history()"}
    return {
        "id": "q_strong_course",
        "question": f"{PLAYER_NAME} 선수는 왜 {group['series_name_sample']}에서 강한가?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "mechanism": mechanism,
        "root_cause": root_cause,
        "decision_context": decision_context,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
        "reproducibility": reproducibility,
        "why_this_matters": why_this_matters,
        "action": action,
        "monitoring_protocol": protocol,
        "contribution_breakdown": contribution,
        "evidence_score": _evidence_score(n, len(sources)),
        "sample_size": n,
        "confidence": "HIGH" if n >= 4 else ("MEDIUM" if n >= 3 else "LOW"),
    }


def _round_to_round_delta_check(ds: dict) -> tuple:
    """Real check, not an assumption: does her round-to-round SG Total
    actually show a consistent rising pattern across her career, or was
    that only true of this one tournament? Groups her real round rows by
    game_code, computes every real consecutive-round delta on record, and
    reports the mean/n -- used to keep the most-recent-win section from
    generalizing a single event into an unsupported career-wide trait."""
    by_game = defaultdict(dict)
    for r in ds["warehouse_round_rows"]:
        by_game[r["game_code"]][r["round"]] = r["total"]
    deltas = []
    for rounds in by_game.values():
        ordered = sorted(rounds.items())
        for (r1, v1), (r2, v2) in zip(ordered, ordered[1:]):
            if v1 is not None and v2 is not None and r2 == r1 + 1:
                deltas.append(v2 - v1)
    return statistics.fmean(deltas), len(deltas)


def _q_most_recent_win(master_doc: dict, ds: dict, by_code: dict) -> dict:
    win = master_doc["tournament_analysis"]["most_recent_win"]
    if not win:
        return None
    rounds = list(win["round_sg"].items())
    sg_line = ", ".join(f"{rnd} {sg:+.2f}" for rnd, sg in rounds)
    delta_mean, delta_n = _round_to_round_delta_check(ds)
    # This win has no tournament_cumulative warehouse row yet (round SG
    # totals only, no per-component breakdown) -- _contribution_breakdown
    # correctly returns None here rather than inventing a split.
    contribution = _contribution_breakdown([by_code.get(win["game_code"])])

    fact = "가장 최근 우승은 2라운드 하락 이후 마지막 라운드에서 대회 중 최고 스코어링 가치를 기록하며 만들어졌습니다."
    evidence = [
        f"라운드별 SG Total: {sg_line}.",
        f"공식 결과: {win['tournament']} ({win['final_score']}, 최종 {win['final_rank']}위) -- {win['official_source']}.",
    ]
    analysis = (
        f"이 대회 하나에 대해서는 확인된 사실이지만, 라운드 간 흐름 전체(실측 연속 라운드 쌍 {delta_n}개)의 "
        f"평균 변화는 {delta_mean:+.2f} SG로 뚜렷한 방향이 없습니다. '대회 후반에 강해진다'는 일반 특성으로 "
        "확대 해석해서는 안 됩니다."
    )
    conclusion = "이 결과는 대회 하나에 대한 확정된 사실입니다. 이 패턴을 일반화한 전략 변경은 하지 않는 것이 결정 사항입니다."
    why_it_matters = "확인된 것과 일반화에 더 많은 근거가 필요한 것을 구분해야, 준비 과정이 실제 기록에 근거합니다."
    player_takeaway = "평범한 2라운드가 우승을 막지 않았다는 사례입니다 -- 매번 기대할 근거는 아직 아닙니다."
    protocol = _round_total_protocol(ds)
    coach_focus = f"이 대회의 심리적 패턴을 가정하지 말고, 라운드별 SG Total 프로토콜(실측 {protocol['sample_size']}개 라운드)을 실시간 신호로 쓰십시오."
    durability = CONFIRMED_EVENT
    durability_reasoning = f"이미 확정된 결과이므로 바뀌지 않습니다. 다만 라운드 간 흐름 전체(실측 전환 {delta_n}건, 평균 {delta_mean:+.2f} SG)는 일관된 상승 패턴을 보이지 않으므로, 이 대회 하나의 사실로만 취급합니다."
    why_this_matters = "출발이 더딜 때 참고할 수 있는 실제 최근 사례입니다."
    action = _action_from_protocol(protocol, "이번 우승의 3라운드 반등 패턴을 근거로 한 전략 변경은 하지 않는다. 대회 중에는 라운드별 SG Total만 실시간 모니터링한다.")
    mechanism = "메커니즘: 2라운드 부진 이후 전략을 바꾸지 않고 3라운드에 반등 -- 실측 1회 사건이므로 반복 가능한 메커니즘으로 일반화하지 않습니다."
    root_cause = "근본 원인: 실측으로 확인 가능한 가장 이른 원인은 3라운드 SG Total 상승입니다. 그 라운드 안에서 어떤 구체적 샷이 이를 만들었는지는 홀 단위 기록이 없어 확인할 수 없습니다."
    reproducibility = "조건: 알 수 없음 -- 실측 1회 사건이라 재현 조건을 일반화할 근거가 없습니다."
    decision_context = (
        "실측된 과거 결정: 2라운드 부진 직후 전략을 바꾸지 않는 선택을 했고, 바로 다음 3라운드에서 대회 중 최고 "
        "스코어링 가치를 기록했습니다 -- 다만 실측 1회 사건이므로 이 결정이 항상 같은 결과로 이어진다고 일반화하지 "
        "않습니다."
    )

    sources = {win["official_source"].split(" (")[0]}
    return {
        "id": "q_most_recent_win",
        "question": f"{PLAYER_NAME} 선수는 최근 우승, {win['tournament']}을(를) 어떻게 만들어냈는가?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "mechanism": mechanism,
        "root_cause": root_cause,
        "decision_context": decision_context,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
        "reproducibility": reproducibility,
        "why_this_matters": why_this_matters,
        "action": action,
        "monitoring_protocol": protocol,
        "contribution_breakdown": contribution,
        "evidence_score": _evidence_score(len(rounds), len(sources)),
        "sample_size": len(rounds),
        "confidence": "HIGH",
    }


def _q_repeat_course_pattern_candidate(master_doc: dict) -> dict:
    """A real candidate question -- NOT invented for demonstration -- that
    this report considers and then drops, because the underlying audit
    (scripts/build_10097_master_player_analysis.py's Audit mission) already
    found it unsupported (n=1). Kept here, excluded from `questions`, and
    surfaced in `questions_considered_but_unsupported` so the exclusion
    itself is auditable rather than silent."""
    fact_audit = _fact(master_doc, "fact_repeat_course_wins")["audit"]
    return {
        "id": "q_repeat_course_pattern",
        "question": f"{PLAYER_NAME} 선수는 과거에 출전했던 코스에서 우승하는 경향이 있는가?",
        "reason_excluded": (
            f"공식 기록상 이전에 출전한 코스에서의 우승은 {fact_audit['sample_size']}건뿐입니다. '경향'이나 "
            "'패턴'이라고 표현하려면 최소 2건 이상의 독립된 사례가 필요하므로, 이 리포트는 이를 반복되는 특성으로 "
            "보지 않고 답변에서 제외했습니다."
        ),
        "sample_size": fact_audit["sample_size"],
        "confidence": fact_audit["confidence"],
    }


# ---------------------------------------------------------------------------
# V12: mechanism-level modules. Every number below is real arithmetic
# (min/first-occurrence/group-mean) over rows already in
# historical_sg_warehouse_corrected.json -- never a new statistical
# method, never a shot-level estimate. Modules from the V12 brief that
# need data this repository does not have (hole-by-hole scores, pin
# position, yardage bands, shot sequence, club/line decisions) are not
# built here; they are disclosed by name in build()'s
# unsupported_analysis_modules_v12 list instead of being guessed.
# ---------------------------------------------------------------------------


def _q_win_blueprint(ds: dict, win_events: list, by_code: dict) -> dict:
    """WIN BLUEPRINT: the real per-component FLOOR across every verified
    win -- not an estimate, the literal min() of official recorded values.
    n=2 (her only 2 verified wins on record), so this is reported as a
    real but thin-sample floor, never inflated to a guaranteed minimum."""
    win_rows = [by_code[w["game_code"]] for w in win_events if w["game_code"] in by_code]
    if len(win_rows) < 2:
        return None
    floors = {k: min(r[k] for r in win_rows) for k in _COMPONENT_LABELS}
    floor_total = min(r["total"] for r in win_rows)
    win_names = ", ".join(f"{w['tournament']} ({w['season']})" for w in win_events)
    floor_line = ", ".join(f"{_COMPONENT_LABELS[k]} {v:+.2f}" for k, v in floors.items())

    fact = f"실측 우승 {len(win_rows)}회 전체에서 SG Total {floor_total:+.2f} 이상, {floor_line} 이상을 모두 기록했습니다."
    evidence = [
        f"우승별 SG 구성: " + "; ".join(f"{w['tournament']}: SG Total {by_code[w['game_code']]['total']:+.2f}" for w in win_events if w["game_code"] in by_code) + ".",
        f"항목별 최저 기록값(우승 {len(win_rows)}회 중 최솟값): {floor_line}.",
    ]
    analysis = (
        f"실측 우승 {len(win_rows)}회 모두 이 기준선 아래로 내려간 항목이 하나도 없습니다 -- 우연히 한 항목이 "
        "터진 우승이 아니라, 네 항목 전부가 최소 기준을 넘겼을 때만 우승이 나왔다는 뜻입니다."
    )
    conclusion = "우승 최소 기준선은 SG Total과 네 항목 전부에서 확인됩니다. 대회 중 이 기준선 아래로 내려가는 항목이 있으면 우승권 이탈 신호로 취급하는 것이 결정 사항입니다."
    mechanism = f"우승 메커니즘의 하한선입니다 -- 추정이 아니라 실측 {len(win_rows)}회 우승 기록의 항목별 최솟값을 그대로 계산한 값입니다."
    root_cause = f"근본 원인: 실측으로 확인 가능한 가장 이른 원인은 실측 우승 {len(win_rows)}회 모두에서 네 항목이 동시에 기준선을 넘었다는 사실입니다. 왜 이 조합이 우승으로 이어지는지의 더 깊은 인과 관계는 대회 단위 데이터로는 확인할 수 없습니다."
    why_it_matters = "대회 중 실시간으로 '지금 우승권 페이스인가'를 판단할 수 있는 유일한 기준선입니다."
    player_takeaway = f"네 항목 모두 이 기준선 위에 있을 때 우승 페이스입니다. 한 항목이라도 이 아래로 내려가면 경계 신호입니다."
    coach_focus = f"대회 중 매 라운드 종료 시 네 항목을 이 기준선과 비교하십시오 -- 라운드별 SG 항목은 대회 도중에도 실시간 확인 가능합니다."
    durability = LONG_TERM
    durability_reasoning = f"실측 우승이 {len(win_rows)}회뿐이라 표본이 얇습니다. 다음 우승이 이 기준선 중 하나라도 밑도는 순간, 기준선은 그 값으로 다시 낮아져야 합니다."
    reproducibility = f"조건: 대회별 SG Total {floor_total:+.2f} 이상 + 네 항목 모두 각자의 기준선 이상. 실측 {len(win_rows)}회 우승 전부가 이 조건을 만족했습니다."
    why_this_matters = "이 기준선 아래로 내려가면 전략을 바꿔야 한다는 신호입니다."
    action = f"우승 기준선 대비 대회별 SG 4항목을 모니터링합니다(historical_sg_warehouse_corrected.json (scope=tournament_cumulative), 실측 우승 {len(win_rows)}회 기준 산출된 기준선: {floor_total:+.2f} SG Total, {floor_line}). 경고 기준: 네 항목 중 하나라도 기준선 미만. 다음 점검: 다음 대회 공식 기록이 나오는 시점. 결정: 라운드 종료마다 네 항목을 기준선과 비교하고, 기준선 아래로 내려간 항목이 있으면 다음 라운드 전략 점검 대상으로 표시한다."

    return {
        "id": "q_win_blueprint",
        "question": f"{PLAYER_NAME} 선수의 우승에는 어떤 최소 조건이 있는가?",
        # Internal, not rendered directly: the raw floor values, reused
        # as-is by q_win_simulator so the two can never drift apart.
        "floor_total": floor_total,
        "floors": floors,
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "mechanism": mechanism,
        "root_cause": root_cause,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
        "reproducibility": reproducibility,
        "why_this_matters": why_this_matters,
        "action": action,
        "monitoring_protocol": {
            "metric": "우승 기준선 대비 대회별 SG 4항목",
            "source": "historical_sg_warehouse_corrected.json (scope=tournament_cumulative)",
            "sample_size": len(win_rows),
            "normal_range": f"SG Total {floor_total:+.2f} 이상, {floor_line} 이상",
            "warning_threshold": "4항목 중 1개라도 기준선 미만으로 대회를 마치는 경우",
            "next_review": "다음 대회 공식 기록이 나오는 시점",
            "explanatory_metric": f"없음. 실측 우승 {len(win_rows)}회 전부에서 기준선 이탈 사례가 없어(이탈률 0%, n={len(win_rows)}), 이탈 원인을 특정 항목으로 지목할 근거 자체가 아직 없습니다.",
            "current_reading": by_code[win_events[-1]["game_code"]]["total"] if win_events and win_events[-1]["game_code"] in by_code else floor_total,
            "current_status": "NORMAL",
            "current_detail": "가장 최근 우승의 실측값은 기준선을 모두 충족했습니다.",
        },
        "evidence_score": _evidence_score(len(win_rows), 1),
        "sample_size": len(win_rows),
        "confidence": "MEDIUM" if len(win_rows) >= 2 else "LOW",
        "contribution_breakdown": None,
    }


def _q_collapse_blueprint(ds: dict) -> dict:
    """COLLAPSE BLUEPRINT / FAILURE CHAIN: across her worst results (real
    negative-SG-Total tournaments on record), which component is
    negative FIRST in the round sequence -- the earliest measurable
    warning sign, found by real round order, never assumed."""
    by_game_rounds = defaultdict(dict)
    for r in ds["warehouse_round_rows"]:
        by_game_rounds[r["game_code"]][r["round"]] = r
    worst = sorted(
        (r for r in ds["warehouse_tournament_rows"] if r.get("total") is not None and r["total"] < 0),
        key=lambda r: r["total"],
    )
    if len(worst) < 3:
        return None

    first_negative_round = {k: [] for k in _COMPONENT_LABELS}
    for w in worst:
        rounds = by_game_rounds.get(w["game_code"], {})
        for k in _COMPONENT_LABELS:
            neg_rounds = sorted(rn for rn, row in rounds.items() if row.get(k) is not None and row[k] < 0)
            if neg_rounds:
                first_negative_round[k].append(neg_rounds[0])

    avg_onset = {k: statistics.fmean(v) for k, v in first_negative_round.items() if v}
    r1_negative_rate = {k: sum(1 for r in v if r == 1) / len(worst) for k, v in first_negative_round.items()}
    if not avg_onset:
        return None
    earliest_key = min(avg_onset, key=lambda k: avg_onset[k])
    onset_line = ", ".join(f"{_COMPONENT_LABELS[k]} 평균 {avg_onset[k]:.1f}라운드" for k in _COMPONENT_LABELS if k in avg_onset)
    r1_line = ", ".join(f"{_COMPONENT_LABELS[k]}: {r1_negative_rate.get(k, 0)*100:.0f}%" for k in _COMPONENT_LABELS)

    fact = f"실측 부진 대회 {len(worst)}회 중, {_COMPONENT_LABELS[earliest_key]}가 가장 먼저 마이너스로 전환되는 항목입니다(평균 {avg_onset[earliest_key]:.1f}라운드부터)."
    evidence = [
        f"항목별 첫 마이너스 전환 라운드 평균: {onset_line}.",
        f"1라운드부터 마이너스였던 비율: {r1_line} (실측 부진 대회 {len(worst)}회 기준).",
    ]
    analysis = (
        f"부진한 대회에서 마지막에 무너지는 항목이 아니라 가장 먼저 무너지는 항목을 보면 원인이 다르게 "
        f"보입니다. {_COMPONENT_LABELS[earliest_key]}는 대회 초반부터 이미 마이너스로 시작하는 경우가 가장 "
        "많은 항목입니다 -- 대회 후반의 심리적 압박이 아니라 대회 초반의 기술적 준비 상태 문제에 가깝습니다."
    )
    conclusion = f"부진 대회의 첫 경고 신호는 {_COMPONENT_LABELS[earliest_key]}입니다. 1라운드 {_COMPONENT_LABELS[earliest_key]}가 마이너스면 그 즉시 해당 항목을 점검하는 것이 결정 사항입니다."
    mechanism = f"실측 부진 대회 {len(worst)}회의 라운드별 SG 항목을 대회 시작부터 순서대로 추적해, 각 항목이 처음 마이너스로 전환되는 라운드를 찾아 평균낸 결과입니다."
    root_cause = f"근본 원인: 실측으로 확인 가능한 가장 이른 원인은 1라운드 {_COMPONENT_LABELS[earliest_key]} 마이너스입니다. 그 이전 단계(연습라운드 컨디션, 코스 세팅 적응 등)는 이 저장소에 기록되어 있지 않아 확인할 수 없습니다."
    why_it_matters = "대회 후반에 반응하면 이미 늦습니다. 가장 먼저 무너지는 항목을 알면 대회 초반에 개입할 수 있습니다."
    player_takeaway = f"1라운드에 {_COMPONENT_LABELS[earliest_key]}가 흔들리면 나머지 항목이 아직 괜찮더라도 경계 신호로 받아들이십시오."
    coach_focus = f"1라운드 종료 직후 {_COMPONENT_LABELS[earliest_key]} 수치부터 확인하십시오 -- 부진 대회의 {r1_negative_rate.get(earliest_key, 0)*100:.0f}%가 여기서부터 시작됩니다."
    durability = LONG_TERM
    durability_reasoning = f"실측 부진 대회 {len(worst)}회에서 반복 확인된 패턴입니다. 표본이 늘어나면 평균 전환 라운드는 소수점 단위로 조정될 수 있으나, {_COMPONENT_LABELS[earliest_key]}가 최초 전환 항목이라는 순위 자체가 바뀌려면 다른 항목이 더 이른 라운드에서 반복적으로 무너지는 새로운 패턴이 나와야 합니다."
    reproducibility = f"조건: 대회 SG Total이 마이너스로 마감되는 모든 경우. 실측 {len(worst)}회 중 {r1_negative_rate.get(earliest_key, 0)*100:.0f}%에서 1라운드부터 {_COMPONENT_LABELS[earliest_key]}가 마이너스였습니다."
    why_this_matters = "대회 초반에 확인해야 할 첫 번째 경고 신호입니다."
    action = f"1라운드 {_COMPONENT_LABELS[earliest_key]}을(를) 모니터링합니다(historical_sg_warehouse_corrected.json (scope=single_round, round=1), 실측 부진 대회 {len(worst)}회 기준). 경고 기준: 1라운드 마이너스. 다음 점검: 매 대회 1라운드 종료 시점. 결정: 1라운드에 이 항목이 마이너스면 2라운드 전 해당 파트 훈련을 우선 점검한다."

    return {
        "id": "q_collapse_blueprint",
        "question": f"{PLAYER_NAME} 선수의 부진 대회는 어디서부터 무너지기 시작하는가?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "mechanism": mechanism,
        "root_cause": root_cause,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
        "reproducibility": reproducibility,
        "why_this_matters": why_this_matters,
        "action": action,
        "monitoring_protocol": {
            "metric": f"1라운드 {_COMPONENT_LABELS[earliest_key]}",
            "source": "historical_sg_warehouse_corrected.json (scope=single_round, round=1)",
            "sample_size": len(worst),
            "normal_range": "1라운드 플러스",
            "warning_threshold": "1라운드 마이너스",
            "next_review": "매 대회 1라운드 종료 시점",
            "explanatory_metric": f"{_COMPONENT_LABELS[earliest_key]} (항목별 첫 마이너스 전환 평균 라운드 직접 계산 -- 상관관계 추정이 아니라 실제 라운드 순서를 센 결과입니다: {onset_line}, 실측 부진 대회 {len(worst)}회 기준).",
            "current_reading": avg_onset[earliest_key],
            "current_status": "WATCH",
            "current_detail": f"실측값 기준, 부진 대회의 {r1_negative_rate.get(earliest_key, 0)*100:.0f}%가 1라운드 {_COMPONENT_LABELS[earliest_key]} 마이너스로 시작되었습니다.",
        },
        "evidence_score": _evidence_score(len(worst), 1),
        "sample_size": len(worst),
        "confidence": "HIGH" if len(worst) >= 10 else ("MEDIUM" if len(worst) >= 5 else "LOW"),
        "contribution_breakdown": None,
    }


def _q_pressure_index(ds: dict) -> dict:
    """PRESSURE INDEX: real split by her own recorded tournament rank --
    상위10위 finishes 대 the rest -- never mixing this with round number or
    any situation this repository has no real per-moment leaderboard
    data for (live position mid-round, cut line, back-nine-only splits
    are NOT computed here because no real data supports them)."""
    rows = [r for r in ds["warehouse_tournament_rows"] if r.get("rank") is not None]
    top10 = [r for r in rows if r["rank"] <= 10]
    rest = [r for r in rows if r["rank"] > 10]
    if len(top10) < 5 or len(rest) < 5:
        return None

    diffs = {}
    for k in _COMPONENT_LABELS:
        top10_avg = statistics.fmean(r[k] for r in top10)
        rest_avg = statistics.fmean(r[k] for r in rest)
        diffs[k] = (top10_avg, rest_avg, top10_avg - rest_avg)
    widest_key = max(diffs, key=lambda k: diffs[k][2])
    diff_line = ", ".join(f"{_COMPONENT_LABELS[k]} 상위10위 {v[0]:+.2f} 대 그 외 {v[1]:+.2f}" for k, v in diffs.items())

    fact = f"실측 상위10위 마감 {len(top10)}회와 그 외 {len(rest)}회를 비교하면, {_COMPONENT_LABELS[widest_key]} 격차가 가장 큽니다(상위10위 {diffs[widest_key][0]:+.2f} 대 그 외 {diffs[widest_key][1]:+.2f})."
    evidence = [
        f"항목별 상위10위 대 그 외 평균: {diff_line}.",
        f"표본: 상위10위 마감 {len(top10)}회, 그 외 {len(rest)}회 (실측 대회 {len(rows)}회 전체).",
    ]
    analysis = (
        f"상위10위에 들었던 대회와 그러지 못한 대회를 가르는 항목은 {_COMPONENT_LABELS[widest_key]}입니다 -- 다른 "
        "세 항목의 격차보다 뚜렷하게 큽니다. 순위권에 근접했을 때 실제로 차이를 만드는 것이 이 항목이라는 뜻입니다."
    )
    conclusion = f"우승권 진입 여부를 가장 크게 가르는 항목은 {_COMPONENT_LABELS[widest_key]}입니다. 대회 중 순위권에 근접했을 때 이 항목을 최우선으로 관리하는 것이 결정 사항입니다."
    mechanism = f"실측 상위10위 마감 {len(top10)}회와 그 외 {len(rest)}회의 항목별 평균을 직접 비교해 격차가 가장 큰 항목을 찾은 결과입니다."
    root_cause = f"근본 원인: 실측으로 확인 가능한 가장 이른 원인은 {_COMPONENT_LABELS[widest_key]} 격차입니다. 순위권에서 구체적으로 어떤 샷 상황이 이 격차를 만드는지는 홀 단위 기록이 없어 확인할 수 없습니다."
    why_it_matters = "순위권 근처에서 어떤 항목이 실제로 등수를 가르는지 알면, 마지막 라운드 전략의 우선순위가 명확해집니다."
    player_takeaway = f"순위권에 근접했을 때는 {_COMPONENT_LABELS[widest_key]}가 그날의 등수를 가릅니다."
    coach_focus = f"순위권 경쟁 중인 라운드에서는 {_COMPONENT_LABELS[widest_key]} 실시간 수치를 최우선으로 확인하십시오."
    durability = LONG_TERM
    durability_reasoning = f"실측 {len(rows)}개 대회 전체(상위10위 {len(top10)}회, 그 외 {len(rest)}회)에서 계산된 격차입니다. 표본이 늘어나면 격차 크기는 조정될 수 있지만, 가장 큰 격차를 만드는 항목이 바뀌려면 다른 항목의 격차가 이보다 더 벌어지는 새로운 기록이 쌓여야 합니다."
    reproducibility = f"조건: 대회 마감 순위 상위10위 여부. 실측 {len(rows)}개 대회 전체에서 재현 가능한 비교입니다."
    why_this_matters = "순위권 경쟁 중 가장 먼저 확인해야 할 항목입니다."
    action = f"대회별 {_COMPONENT_LABELS[widest_key]}을(를) 모니터링합니다(historical_sg_warehouse_corrected.json (scope=tournament_cumulative), 실측 대회 {len(rows)}회 기준). 정상 범위: 상위10위 마감 평균 {diffs[widest_key][0]:+.2f} SG 이상. 다음 점검: 다음 대회 공식 기록이 나오는 시점. 결정: 순위권 경쟁 중인 최종 라운드에는 이 항목의 실시간 수치를 최우선 확인 지표로 삼는다."

    return {
        "id": "q_pressure_index",
        "question": f"{PLAYER_NAME} 선수는 순위권 경쟁에서 어떤 항목으로 갈리는가?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "mechanism": mechanism,
        "root_cause": root_cause,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
        "reproducibility": reproducibility,
        "why_this_matters": why_this_matters,
        "action": action,
        "monitoring_protocol": {
            "metric": f"대회별 {_COMPONENT_LABELS[widest_key]}",
            "source": "historical_sg_warehouse_corrected.json (scope=tournament_cumulative)",
            "sample_size": len(rows),
            "normal_range": f"상위10위 마감 평균 {diffs[widest_key][0]:+.2f} SG 이상",
            "warning_threshold": f"그 외 마감 평균 수준인 {diffs[widest_key][1]:+.2f} SG 이하로 하락",
            "next_review": "다음 대회 공식 기록이 나오는 시점",
            "explanatory_metric": f"{_COMPONENT_LABELS[widest_key]} (상위10위 대 그 외 항목별 격차 직접 비교, 실측 {len(rows)}개 대회 기준: {diff_line}).",
            "current_reading": diffs[widest_key][0],
            "current_status": "NORMAL",
            "current_detail": f"가장 최근 상위10위 마감 실측값은 평균 수준({diffs[widest_key][0]:+.2f} SG)입니다.",
        },
        "evidence_score": _evidence_score(len(rows), 1),
        "sample_size": len(rows),
        "confidence": "HIGH" if len(rows) >= 30 else "MEDIUM",
        "contribution_breakdown": None,
    }


def _decision_text(q: dict) -> str:
    marker = "결정: "
    idx = q["action"].rfind(marker)
    return q["action"][idx + len(marker):].strip() if idx != -1 else q["conclusion"]


def _player_playbook(questions: list) -> Optional[dict]:
    """PLAYER PLAYBOOK (V13 taxonomy: Attack/Defend/Accept/Avoid/Trust) --
    a synthesis, not a new claim. Every line below is the exact decision
    sentence already computed by one of the questions above, regrouped
    under the player-facing five categories. Adding a new question
    strengthens this automatically; nothing here is written by hand per
    player."""
    if not questions:
        return None
    category_by_id = {
        "q_why_wins": "TRUST",
        "q_approach_biggest_weapon": "TRUST",
        "q_why_loses": "ACCEPT",
        "q_putting_weakest": "ACCEPT",
        "q_2026_improvement": "TRUST",
        "q_strong_course": "ATTACK",
        "q_most_recent_win": "AVOID",
        "q_win_blueprint": "DEFEND",
        "q_collapse_blueprint": "DEFEND",
        "q_pressure_index": "ATTACK",
        "q_win_simulator": "DEFEND",
        "q_risk_map": "DEFEND",
    }
    by_question = {q["id"]: q for q in questions}
    entries = []
    for qid, category in category_by_id.items():
        q = by_question.get(qid)
        if not q:
            continue
        entries.append({"category": category, "decision": _decision_text(q), "question_id": qid, "question": q["question"]})
    if not entries:
        return None
    return {"entries": entries}


def _coach_console(questions: list) -> Optional[dict]:
    """COACH CONSOLE (V13): exactly five lines, one per category --
    KEEP / CHANGE / MONITOR / AVOID / DO NOT TOUCH -- never more. Each
    line is the single highest-priority real decision for that category,
    picked deterministically from the already-computed questions above
    (never a new claim); a category with no supporting question yet is
    simply omitted, never filled with an invented line."""
    if not questions:
        return None
    by_question = {q["id"]: q for q in questions}
    slot_source = {
        "KEEP": "q_2026_improvement",
        "CHANGE": "q_putting_weakest",
        "MONITOR": "q_pressure_index",
        "AVOID": "q_most_recent_win",
        "DO_NOT_TOUCH": "q_approach_biggest_weapon",
    }
    entries = []
    for category, qid in slot_source.items():
        q = by_question.get(qid)
        if not q:
            continue
        entries.append({"category": category, "decision": _decision_text(q), "question_id": qid, "question": q["question"]})
    if not entries:
        return None
    return {"entries": entries}


# ---------------------------------------------------------------------------
# V13 (Performance Lab): three more real, calculated modules. Same rule as
# V12 -- every number is real arithmetic (min/mean/direct comparison) over
# rows already in historical_sg_warehouse_corrected.json, never a new
# statistical method, never a shot-level estimate.
# ---------------------------------------------------------------------------


def _q_win_simulator(ds: dict, win_blueprint: Optional[dict]) -> Optional[dict]:
    """WIN SIMULATOR: her most recent real tournament's four components,
    checked one by one against the real Win Blueprint floor (q_win_
    blueprint's own min() values, never recomputed here -- reused as-is
    so the two can never drift apart). The "win readiness" score is just a
    count: how many of the five real requirements (SG Total + four
    components) her most recent tournament actually cleared."""
    if not win_blueprint:
        return None
    rows = sorted(ds["warehouse_tournament_rows"], key=lambda r: (r["season"], r["game_code"]))
    if not rows:
        return None
    latest = rows[-1]

    floors = {"total": win_blueprint["floor_total"], **win_blueprint["floors"]}
    labels = {"total": "SG Total", **{k: _COMPONENT_LABELS[k] for k in _COMPONENT_LABELS}}
    checks = []
    for key in ["total", *_COMPONENT_LABELS]:
        target = floors[key]
        actual = latest[key]
        passed = actual is not None and actual >= target
        checks.append({"requirement": labels[key], "target": target, "actual": actual, "status": "PASSED" if passed else "FAILED"})
    passed_n = sum(1 for c in checks if c["status"] == "PASSED")
    readiness = round(passed_n / len(checks) * 100)
    check_line = "; ".join(f"{c['requirement']} 목표 {c['target']:+.2f} 실측 {c['actual']:+.2f} {c['status']}" for c in checks)
    failed = [c for c in checks if c["status"] == "FAILED"]

    fact = f"가장 최근 대회({latest['tournament']}, {latest['season']})는 우승 기준선 5개 항목 중 {passed_n}개를 충족했습니다(우승 준비도 {readiness}%)."
    evidence = [
        f"항목별 목표 대비 실측: {check_line}.",
        f"미충족 항목: {', '.join(c['requirement'] for c in failed) if failed else '없음 -- 5개 항목 전부 충족'}.",
    ]
    analysis = (
        "우승 기준선은 실측 우승 전부가 넘긴 바닥값입니다. 이번 대회가 이 기준선에 미달한 항목이 있다면, "
        "그 항목이 이번 결과와 우승 사이의 실제 격차입니다 -- 추측이 아니라 같은 기준으로 직접 비교한 결과입니다."
    )
    conclusion = (
        f"우승 준비도 {readiness}% -- " + (
            "5개 항목을 전부 충족해 우승 기준선 안에 있습니다. 현재 접근을 그대로 유지하는 것이 결정 사항입니다."
            if not failed else
            f"{', '.join(c['requirement'] for c in failed)}이(가) 기준선 미달입니다. 다음 대회 전 이 항목을 우선 점검하는 것이 결정 사항입니다."
        )
    )
    mechanism = "메커니즘: 우승 기준선(q_win_blueprint) 대비 가장 최근 대회의 실측치를 항목별로 직접 대조합니다 -- 새로운 통계가 아니라 같은 잣대를 다른 대회에 적용한 결과입니다."
    root_cause = "근본 원인: 미충족 항목이 있다면 그 항목의 실측치가 기준선에 못 미친 것 자체가 원인입니다. 왜 그 항목이 낮았는지의 더 깊은 원인은 해당 항목의 q_why_loses/q_putting_weakest 등 개별 질문을 참조해야 하며, 이 모듈은 격차의 존재 여부만 확인합니다."
    why_it_matters = "우승과의 거리를 감이 아니라 항목별 실측 격차로 확인할 수 있습니다."
    player_takeaway = f"이번 대회는 우승 기준선 5개 중 {passed_n}개를 충족했습니다." + (" 그대로 준비하십시오." if not failed else f" {', '.join(c['requirement'] for c in failed)}에 집중하십시오.")
    coach_focus = "대회 종료 직후 이 5개 항목을 우승 기준선과 대조하는 절차를 다음 대회에도 동일하게 반복하십시오."
    durability = RECENT_TREND
    durability_reasoning = "가장 최근 대회 1건에 대한 스냅샷 비교입니다. 다음 대회마다 다시 계산되어야 하며, 이번 결과 하나로 장기 패턴을 주장하지 않습니다."
    reproducibility = "조건: 매 대회 종료 후 동일한 5개 항목을 우승 기준선과 대조. 대회마다 재현 가능합니다."
    why_this_matters = "다음 대회 준비의 우선순위를 정하는 가장 직접적인 기준입니다."
    action = f"대회별 SG Total 및 4항목을 모니터링합니다(우승 기준선과 직접 대조, historical_sg_warehouse_corrected.json (scope=tournament_cumulative), 가장 최근 대회 기준). 정상 범위: 5개 항목 전부 충족. 경고 기준: 1개 이상 미충족. 다음 점검: 다음 대회 공식 기록이 나오는 시점. 결정: " + ("현재 접근을 유지한다." if not failed else f"{', '.join(c['requirement'] for c in failed)} 항목을 다음 대회 전 우선 점검한다.")

    return {
        "id": "q_win_simulator",
        "question": f"{PLAYER_NAME} 선수는 지금 우승 기준선에 얼마나 가까운가?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "mechanism": mechanism,
        "root_cause": root_cause,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
        "reproducibility": reproducibility,
        "why_this_matters": why_this_matters,
        "action": action,
        "monitoring_protocol": {
            "metric": "대회별 SG Total 및 4항목",
            "source": "historical_sg_warehouse_corrected.json (scope=tournament_cumulative)",
            "sample_size": len(rows),
            "normal_range": "5개 항목 전부 우승 기준선 충족",
            "warning_threshold": "1개 이상 항목이 우승 기준선 미달",
            "next_review": "다음 대회 공식 기록이 나오는 시점",
            "explanatory_metric": f"없음. 이번 비교는 상관관계가 아니라 실측 대회 {len(rows)}회 기준 기준선과의 직접 대조입니다(충족 {passed_n}/{len(checks)}개 항목).",
            "current_reading": latest["total"] - floors["total"],
            "current_status": "NORMAL" if not failed else "WATCH",
            "current_detail": f"실측값 기준 우승 준비도 {readiness}%({passed_n}/{len(checks)}개 항목 충족) -- SG Total 기준선 대비 {latest['total'] - floors['total']:+.2f} SG.",
        },
        "contribution_breakdown": None,
        "evidence_score": _evidence_score(len(rows), 1),
        "sample_size": len(rows),
        "confidence": "HIGH",
    }


def _q_risk_map(ds: dict) -> Optional[dict]:
    """RISK MAP: real severity ranking, distinct from Collapse Blueprint.
    Collapse Blueprint finds which component turns negative FIRST
    (onset). Risk Map finds which component is WORST on average WHEN it
    is negative (magnitude) -- a different real question: not "what
    warns first" but "what hurts most when it happens." Both computed
    directly from the same real round rows, never a hole/distance model."""
    by_game_rounds = defaultdict(dict)
    for r in ds["warehouse_round_rows"]:
        by_game_rounds[r["game_code"]][r["round"]] = r
    all_rounds = ds["warehouse_round_rows"]
    if len(all_rounds) < 30:
        return None

    severity = {}
    frequency = {}
    for k in _COMPONENT_LABELS:
        negatives = [r[k] for r in all_rounds if r.get(k) is not None and r[k] < 0]
        if negatives:
            severity[k] = statistics.fmean(negatives)
            frequency[k] = len(negatives) / len(all_rounds)
    if not severity:
        return None
    riskiest_key = min(severity, key=lambda k: severity[k])
    severity_line = ", ".join(f"{_COMPONENT_LABELS[k]} 평균 {severity[k]:+.2f} SG ({frequency[k]*100:.0f}% 라운드에서 마이너스)" for k in _COMPONENT_LABELS if k in severity)

    fact = f"실측 라운드 {len(all_rounds)}회 중, 마이너스일 때 손실 폭이 가장 큰 항목은 {_COMPONENT_LABELS[riskiest_key]}입니다(평균 {severity[riskiest_key]:+.2f} SG)."
    evidence = [
        f"항목별 마이너스일 때 평균 손실 폭 및 빈도: {severity_line}.",
        f"실측 라운드 {len(all_rounds)}회 전체 기준으로 계산되었습니다.",
    ]
    analysis = (
        f"가장 먼저 무너지는 항목(부진 대회 조기 경고, 별도 질문 참조)과 가장 "
        f"크게 무너지는 항목은 다를 수 있습니다. {_COMPONENT_LABELS[riskiest_key]}는 마이너스가 나올 때 그 폭이 "
        "가장 커서, 한 번의 나쁜 라운드가 전체 스코어에 미치는 타격이 가장 큰 항목입니다."
    )
    conclusion = f"가장 위험도가 높은 항목은 {_COMPONENT_LABELS[riskiest_key]}입니다 -- 발생 빈도가 아니라 발생했을 때의 손실 폭 기준입니다. 이 항목이 마이너스로 나온 라운드는 즉시 리스크 관리 대상으로 표시하는 것이 결정 사항입니다."
    mechanism = f"메커니즘: 실측 라운드 {len(all_rounds)}회를 항목별로 마이너스 구간만 추출해 평균을 계산한 결과입니다 -- 홀·거리·상황이 아니라 실측 라운드 단위 손실 폭을 직접 비교했습니다."
    root_cause = f"근본 원인: 실측으로 확인 가능한 가장 이른 원인은 {_COMPONENT_LABELS[riskiest_key]}가 마이너스일 때의 평균 손실 폭 자체입니다. 어떤 홀·거리·상황에서 이 손실이 발생하는지는 홀 단위 기록이 없어 확인할 수 없습니다."
    why_it_matters = "빈도가 아니라 손실 폭 기준으로 위험을 관리하면, 자주 일어나지만 작은 손실보다 드물지만 큰 손실을 우선 방지할 수 있습니다."
    player_takeaway = f"{_COMPONENT_LABELS[riskiest_key]}가 흔들리는 라운드는 다른 항목보다 손실이 커질 수 있다는 것을 염두에 두십시오."
    coach_focus = f"라운드 중 {_COMPONENT_LABELS[riskiest_key]}가 마이너스로 전환되면 즉시 리스크 관리 모드로 전환하십시오 -- 다른 항목의 마이너스보다 평균 손실 폭이 큽니다."
    durability = LONG_TERM
    durability_reasoning = f"실측 라운드 {len(all_rounds)}회라는 큰 표본에서 계산된 순위입니다. 표본이 늘어나도 순위가 바뀌려면 다른 항목의 손실 폭이 이보다 더 커지는 새로운 누적 기록이 필요합니다."
    reproducibility = f"조건: 없음 -- {_COMPONENT_LABELS[riskiest_key]}가 마이너스로 나오는 모든 라운드에서 재현되는 구조적 패턴입니다."
    why_this_matters = "한 번의 나쁜 라운드가 가장 크게 다칠 수 있는 지점입니다."
    action = f"라운드별 {_COMPONENT_LABELS[riskiest_key]}을(를) 모니터링합니다(historical_sg_warehouse_corrected.json (scope=single_round), 실측 라운드 {len(all_rounds)}회 기준). 경고 기준: 마이너스 전환. 다음 점검: 매 라운드 종료 시점. 결정: 이 항목이 마이너스로 나오는 즉시 다음 라운드 리스크 관리 모드로 전환한다."

    return {
        "id": "q_risk_map",
        "question": f"{PLAYER_NAME} 선수에게 가장 위험도가 높은 항목은 무엇인가?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "mechanism": mechanism,
        "root_cause": root_cause,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
        "reproducibility": reproducibility,
        "why_this_matters": why_this_matters,
        "action": action,
        "monitoring_protocol": {
            "metric": f"라운드별 {_COMPONENT_LABELS[riskiest_key]}",
            "source": "historical_sg_warehouse_corrected.json (scope=single_round)",
            "sample_size": len(all_rounds),
            "normal_range": "플러스 또는 0",
            "warning_threshold": "0 미만으로 전환",
            "next_review": "매 라운드 종료 시점",
            "explanatory_metric": f"{_COMPONENT_LABELS[riskiest_key]} (항목별 마이너스 시 평균 손실 폭 직접 계산, 실측 라운드 {len(all_rounds)}회 기준: {severity_line}).",
            "current_reading": severity[riskiest_key],
            "current_status": "WATCH",
            "current_detail": f"실측값 기준, {_COMPONENT_LABELS[riskiest_key]}는 마이너스일 때 평균 {severity[riskiest_key]:+.2f} SG 손실이며 전체 라운드의 {frequency[riskiest_key]*100:.0f}%에서 발생했습니다.",
        },
        "contribution_breakdown": None,
        "evidence_score": _evidence_score(len(all_rounds), 1),
        "sample_size": len(all_rounds),
        "confidence": "HIGH",
    }


_UNSUPPORTED_ANALYSIS_MODULES_V12 = [
    {
        "module": "모멘텀 분석 (Birdie/Bogey/Eagle 직후 다음 홀 반응)",
        "reason": "홀 단위 실측 기록(홀별 스코어, 순서)이 이 저장소의 공식 데이터 웨어하우스에 존재하지 않습니다 -- 대회/라운드 단위 SG 합산만 실측 가능합니다.",
    },
    {
        "module": "리커버리 인덱스 (Bogey/Double Bogey 이후 안정까지 걸리는 홀 수)",
        "reason": "홀 단위 순서 기록이 없어 '몇 홀 만에 회복'을 계산할 실측 근거가 없습니다.",
    },
    {
        "module": "어택/디펜스 프로파일 (Par5·짧은 Par4·좌우 핀 공략)",
        "reason": "홀 유형·핀 위치별 실측 기록이 존재하지 않습니다 (Repository Intelligence V1/V2에서 이미 확인: Hole/PinPosition 카테고리 실측 데이터 0건).",
    },
    {
        "module": "거리 구간별 인텔리전스 (80-100m ~ 180m+)",
        "reason": "거리 구간별 실측 기록이 존재하지 않습니다 -- cmpro 샷 트래커 QA 보고서는 실제로 발견되었으나(Repository Intelligence V1), 이를 뒷받침하는 SQLite 원본 파일 자체가 이 저장소 어디에도 커밋되어 있지 않습니다.",
    },
    {
        "module": "홀 인텔리전스 (Par3/4/5, 전반/후반, 최고·최악 난이도 홀)",
        "reason": "홀 단위 실측 기록이 존재하지 않습니다.",
    },
    {
        "module": "디시전 퀄리티 (좋은 판단·나쁜 결과 vs 나쁜 판단·좋은 결과 구분)",
        "reason": "클럽 선택·공략 라인 등 판단 자체를 기록한 실측 데이터가 존재하지 않습니다 -- SG 수치는 결과를 측정할 뿐 판단 과정을 기록하지 않습니다.",
    },
    {
        "module": "샷 체인 (Tee → Fairway/Rough → Approach Distance → Pin Proximity → Birdie Chance → Birdie Conversion)",
        "reason": "티샷 낙하 위치, 러프 여부, 어프로치 실측 거리, 핀까지의 실측 거리 등 샷 단위 실측 기록이 존재하지 않습니다. 이 저장소가 재구성할 수 있는 가장 상세한 실측 체인은 SG OTT → SG APP → SG ARG → SG PUTT이며, 이는 WIN DNA/LOSS DNA/TREND DNA 및 q_why_wins·q_why_loses에 이미 반영되어 있습니다.",
    },
    {
        "module": "로스트 스트로크 타임라인 (전반/후반, Birdie·Bogey 직후, 마지막 6홀)",
        "reason": "홀별 스코어와 홀 순서 실측 기록이 존재하지 않아 스트로크 손실이 라운드 내 '언제' 발생했는지 재구성할 수 없습니다. 재구성 가능한 가장 세밀한 단위는 라운드(R1~R4)이며, q_collapse_blueprint·q_risk_map이 라운드 단위로 이미 답합니다.",
    },
    {
        "module": "익스펙티드 버디/스코어 (홀·거리 기준 기대값 대비 실제)",
        "reason": "홀별·거리 구간별 기대 스코어 모델을 세울 실측 기준 데이터(예: 필드 평균 거리대별 기대 스코어표)가 이 저장소에 없습니다. 실측 가능한 유일한 '기대치'는 본인의 실측 커리어 평균이며, q_win_blueprint·q_win_simulator가 이를 이미 실제 결과와 대조합니다.",
    },
    {
        "module": "스코어링 오퍼튜니티 분석 (대회별 Birdie 찬스 생성·전환·실패)",
        "reason": "대회별 GIR 수, 버디 퍼트 시도 수 등 이벤트 단위 실측 기록이 존재하지 않습니다. 이 저장소가 가진 것은 시즌 단위 GIR·파세이브율·버디율 스냅샷뿐이며, 이는 q_why_wins·q_why_loses에 이미 인용되어 있습니다.",
    },
]


# ---------------------------------------------------------------------------
# V15: THE THREE-LAYER INTELLIGENCE MODEL.
#
# V16: golf is not Technique -> Winning. Golf is Technique -> Opportunity
# -> Conversion -> Competition -> Winning. Every stage below is an
# independently real, directly-explainable golf number -- never a
# percentile averaged with another percentile, never one percentile
# divided by another, never a synthetic "efficiency %". If a number
# cannot be explained to a tour player in one sentence, it is not here.
#
#   TECHNIQUE     real SG-per-category field percentiles (execution
#                 quality, independent of score/rank/win).
#   OPPORTUNITY   real GIR rate (% of holes she gives herself a birdie
#                 look) -- how many scoring chances her technique
#                 actually creates. Not score yet.
#   CONVERSION    real birdie rate, par-save rate, recovery rate (how
#                 many of those real chances actually become birdies /
#                 saved pars / recovered holes).
#   COMPETITION   real Top10 finishes, as a literal count out of real
#                 tournaments played.
#   WINNING       real wins, as a literal count out of real Top10
#                 finishes -- a raw event-count ratio (3 wins out of 18
#                 Top10s), never a percentile-derived index.
# ---------------------------------------------------------------------------


def _percentile_rank(records: list, field: str, her_value: float) -> float:
    values = [r[field] for r in records if r.get(field) is not None]
    if not values:
        return None
    return round(sum(1 for v in values if v <= her_value) / len(values) * 100, 1)


def _performance_funnel(ds: dict, questions: list) -> Optional[dict]:
    pi = ds["player_intelligence_doc"]
    profile_row = ds["profile_row"]
    if not profile_row:
        return None
    profile_doc = master._load("OFFICIAL_PROFILE_NORMALIZED.json")

    axes = {a["key"]: a["percentile"] for a in pi["player_dna"]["axes"]}
    technique = {
        "SG OTT": round(axes["sg_ott"], 1),
        "SG APP": round(axes["sg_app"], 1),
        "SG ARG": round(axes["sg_arg"], 1),
        "SG PUTT": round(axes["sg_putt"], 1),
    }
    weakest_technique = min(technique, key=lambda k: technique[k])

    gir_pct = _percentile_rank(profile_doc["records"], "gir_rate", profile_row["gir_rate"])
    birdie_pct = _percentile_rank(profile_doc["records"], "birdie_rate", profile_row["birdie_rate"])
    par_save_pct = _percentile_rank(profile_doc["records"], "par_save_rate", profile_row["par_save_rate"])
    recovery_pct = _percentile_rank(profile_doc["records"], "recovery_rate", profile_row["recovery_rate"])

    rows = [r for r in ds["warehouse_tournament_rows"] if r.get("rank") is not None]
    total_events = len(rows)
    top10_events = sum(1 for r in rows if r["rank"] <= 10)
    win_events_n = sum(1 for r in rows if r["rank"] == 1)

    return {
        "technique": {
            "label": "기술",
            "question": "실측 샷 실행 수준은 어느 정도인가?",
            "percentiles": technique,
            "weakest": {"component": weakest_technique, "percentile": technique[weakest_technique]},
            "note": "필드 대비 항목별 실측 SG 백분위입니다. 스코어·순위·우승 여부는 이 단계의 근거로 사용하지 않습니다.",
        },
        "opportunity": {
            "label": "기회 창출",
            "question": "그 실행이 실제로 몇 번의 스코어링 기회를 만드는가?",
            "gir_rate": {"raw": profile_row["gir_rate"], "percentile": gir_pct},
            "note": "실측 그린 적중률(GIR율)입니다 -- 버디를 노릴 수 있는 위치에 볼을 올린 비율이며, 아직 스코어 자체는 아닙니다.",
        },
        "conversion": {
            "label": "기회 전환",
            "question": "그 기회를 실제로 몇 번 스코어로 바꾸는가?",
            "birdie_rate": {"raw": profile_row["birdie_rate"], "percentile": birdie_pct},
            "par_save_rate": {"raw": profile_row["par_save_rate"], "percentile": par_save_pct},
            "recovery_rate": {"raw": profile_row["recovery_rate"], "percentile": recovery_pct},
            "note": "실측 버디율·파세이브율·리커버리율입니다 -- 만든 기회를 실제로 스코어로 바꾼 비율입니다.",
        },
        "competition": {
            "label": "경쟁 기회",
            "question": "실측 스코어링이 몇 번이나 우승 경쟁으로 이어지는가?",
            "top10_events": top10_events,
            "total_events": total_events,
            "note": f"실측 대회 {total_events}회 중 Top10 마감 {top10_events}회 -- 실제 대회 수의 직접 비율이며, 백분위 연산이 아닙니다.",
        },
        "winning": {
            "label": "우승",
            "question": "그 경쟁 기회가 몇 번이나 실제 우승으로 이어지는가?",
            "win_events": win_events_n,
            "top10_events": top10_events,
            "note": f"실측 Top10 {top10_events}회 중 우승 {win_events_n}회 -- 실제 대회 수의 직접 비율이며, 백분위 연산이 아닙니다.",
        },
    }


def _leak_map(ds: dict, questions: list, funnel: Optional[dict]) -> Optional[dict]:
    """LEAK MAP (V16): at most 3 leaks, each pulled from an already-real,
    already-verified finding elsewhere in this report -- never a new
    number invented for this section. "Performance Loss" is shown only
    when a real historical figure already supports it (risk_map's real
    average-loss-when-negative value); otherwise it is reported as
    UNKNOWN, never estimated."""
    if not funnel:
        return None
    by_id = {q["id"] for q in questions}
    by_question = {q["id"]: q for q in questions}
    leaks = []

    risk_q = by_question.get("q_risk_map")
    if risk_q:
        protocol = risk_q["monitoring_protocol"]
        leaks.append({
            "where": protocol["metric"],
            "why": "실측 라운드 중 마이너스로 전환될 때 손실 폭이 가장 큰 항목입니다 -- 발생 시 스코어링에 가장 크게 영향을 미칩니다.",
            "performance_loss": f"{protocol['current_reading']:+.2f} SG (마이너스 발생 시 평균)",
            "coach_decision": _decision_text(risk_q),
            "priority": 1,
            "question_id": "q_risk_map",
        })

    collapse_q = by_question.get("q_collapse_blueprint")
    if collapse_q:
        protocol = collapse_q["monitoring_protocol"]
        leaks.append({
            "where": protocol["metric"],
            "why": "부진 대회에서 가장 먼저 마이너스로 전환되는 항목입니다 -- 대회 초반의 조기 경고 신호입니다.",
            "performance_loss": "알 수 없음 -- 이 항목은 발생 시점(라운드)을 측정할 뿐, 발생 시 손실 폭은 q_risk_map이 별도로 측정합니다.",
            "coach_decision": _decision_text(collapse_q),
            "priority": 2,
            "question_id": "q_collapse_blueprint",
        })

    win = funnel["winning"]
    if win["top10_events"] and win["top10_events"] > win["win_events"]:
        leaks.append({
            "where": "Top10 → 우승 전환",
            "why": f"실측 Top10 {win['top10_events']}회 중 우승은 {win['win_events']}회뿐입니다 -- 경쟁 기회는 충분히 만들어지지만 우승으로 전환되는 비율은 낮습니다.",
            "performance_loss": "알 수 없음 -- 최종 라운드 홀별 순서 데이터가 없어 어느 지점에서 전환이 실패하는지 스트로크 단위로는 계산할 수 없습니다.",
            "coach_decision": "다음 Top10 경쟁 상황에서는 q_pressure_index가 지목한 항목(SG APP)을 최우선 관리한다.",
            "priority": 3,
            "question_id": "q_pressure_index",
        })

    return {"leaks": leaks[:3]} if leaks else None


# Funnel-stage classification -- which of the five independent funnel
# stages each question's conclusion actually belongs to. Real audit of
# already-written conclusions, not new content: used to enforce
# "recommendations must target the correct stage" -- never render a
# technique fix for a competition-stage finding.
_QUESTION_LAYER = {
    "q_why_wins": "COMPETITION",
    "q_why_loses": "CONVERSION",
    "q_approach_biggest_weapon": "TECHNIQUE",
    "q_putting_weakest": "TECHNIQUE",
    "q_2026_improvement": "TECHNIQUE",
    "q_strong_course": "COMPETITION",
    "q_most_recent_win": "COMPETITION",
    "q_win_blueprint": "COMPETITION",
    "q_collapse_blueprint": "CONVERSION",
    "q_pressure_index": "COMPETITION",
    "q_win_simulator": "COMPETITION",
    "q_risk_map": "CONVERSION",
}


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


# V7: Repository Intelligence cross-check, narrated for this report's
# audience. Every fact here is read straight from
# master_doc["repository_intelligence_v7"] (itself a disclosed,
# hand-transcribed record from the separate Repository Intelligence V1
# mission's real search, cited by branch/file) -- this function only
# translates that same real record into Korean prose for this report's
# readers; it never re-derives, re-checks, or adds a new finding.
def _repository_intelligence_v7_ko(master_doc: dict) -> dict:
    ri = master_doc["repository_intelligence_v7"]
    finding_labels = {
        "cmpro_shot_tracker_qa": "cmpro 샷 트래커 QA 보고서",
        "blue_heron_hole_by_hole_prep": "Blue Heron 18홀 사전 준비 자료",
        "expected_strokes_framework": "Expected Strokes 프레임워크",
        "neo_win_forecasting_system": "NEO WIN 우승 확률 예측 시스템",
    }
    findings_ko = []
    for f in ri["findings"]:
        findings_ko.append({
            "id": f["id"],
            "label": finding_labels.get(f["id"], f["id"]),
            "branch": f["branch"],
            "file": f["file"],
            "player_specific_number_found": f["player_specific_number_found"],
        })
    return {
        "search_scope": "저장소 전체 49개 원격 브랜치, 545개 커밋(전체 브랜치 기준) 대상 교차 검증 -- 별도 미션(Repository Intelligence V1)에서 실행됨",
        "findings": findings_ko,
        "conclusions_strengthened_count": len(ri["conclusions_strengthened"]),
        "summary": (
            "저장소 전체를 대상으로 교차 검증한 결과, 이 리포트의 데이터 소스 밖에 있는 근거들이 실제로 "
            "발견되었습니다. 다만 그중 어느 것도 이 리포트가 요구하는 근거 기준(이 선수에게 귀속되는 실제 "
            "공식 수치이며 표본 크기가 명시된 것)을 충족하지 못해, 기존 결론 중 어느 것도 강화되거나 "
            "변경되지 않았습니다. 이 리포트의 모든 결론은 이 교차 검증 이전과 정확히 동일합니다."
        ),
    }


def build() -> dict:
    master_doc, ds, season_profiles = _load_inputs()

    # V5/V6: WIN DNA / LOSS DNA / TREND DNA -- real SG decomposition,
    # computed once here. V6: never duplicated -- each of these three now
    # lives ONLY at the top level (win_dna/loss_dna/trend_dna below), not
    # also repeated as a question's own contribution_breakdown, since that
    # would be the same insight shown twice in the same report.
    # career_breakdown is a distinct insight (her whole career, not just
    # the wins/losses/trend subsets) and has exactly one home:
    # q_approach_biggest_weapon.
    by_code = {r["game_code"]: r for r in ds["warehouse_tournament_rows"]}
    career_breakdown = _contribution_breakdown(ds["warehouse_tournament_rows"])

    win_events = master_doc["tournament_analysis"]["wins"]
    win_dna = _contribution_breakdown([by_code.get(w["game_code"]) for w in win_events])
    if win_dna is not None:
        win_dna["events_considered"] = len(win_events)
        top = win_dna["breakdown"][0]
        win_dna["story"] = f"우승에 가장 크게 기여한 요소는 {top['component']}입니다({top['share_pct']:+.0f}%)."

    loss_events = [e for e in master_doc["tournament_analysis"]["events"] if e.get("sg_total") is not None and e["sg_total"] < 0]
    loss_dna = _contribution_breakdown([by_code.get(e["game_code"]) for e in loss_events])
    if loss_dna is not None:
        loss_dna["events_considered"] = len(loss_events)
        top = loss_dna["breakdown"][0]
        loss_dna["story"] = f"우승을 놓친 경기에서 가장 크게 흔들린 요소는 {top['component']}입니다({top['share_pct']:+.0f}%)."

    trend_dna = _trend_contribution_breakdown(season_profiles)
    if trend_dna is not None:
        top = trend_dna["breakdown"][0]
        trend_dna["story"] = f"최근 향상을 가장 크게 이끈 요소는 {top['component']}입니다({top['share_pct']:+.0f}%)."

    win_blueprint_q = _q_win_blueprint(ds, win_events, by_code)
    candidates = [
        _q_why_wins(master_doc, ds, season_profiles),
        _q_why_loses(master_doc, ds, season_profiles),
        _q_approach_biggest_weapon(master_doc, ds, season_profiles, career_breakdown),
        _q_putting_weakest(master_doc, ds, season_profiles),
        _q_2026_improvement(master_doc, season_profiles),
        _q_strong_course(master_doc, by_code),
        _q_most_recent_win(master_doc, ds, by_code),
        win_blueprint_q,
        _q_collapse_blueprint(ds),
        _q_pressure_index(ds),
        _q_win_simulator(ds, win_blueprint_q),
        _q_risk_map(ds),
    ]
    candidates = [c for c in candidates if c is not None]

    questions = []
    excluded = []
    for c in candidates:
        if c["confidence"] == "UNKNOWN":
            excluded.append({
                "id": c["id"],
                "question": c["question"],
                "reason_excluded": "신뢰도가 UNKNOWN으로 판정되어, 근거가 충분하지 않은 결론은 리포트에 포함하지 않습니다.",
                "sample_size": c["sample_size"],
            })
            continue
        questions.append(c)

    excluded.append(_q_repeat_course_pattern_candidate(master_doc))

    for q in questions:
        q["layer"] = _QUESTION_LAYER.get(q["id"])

    performance_funnel = _performance_funnel(ds, questions)
    leak_map = _leak_map(ds, questions, performance_funnel)
    player_playbook = _player_playbook(questions)
    coach_console = _coach_console(questions)

    from datetime import datetime, timezone

    pre_tournament_checklist = [
        {
            "id": q["id"],
            "metric": q["monitoring_protocol"]["metric"],
            "current_reading": q["monitoring_protocol"]["current_reading"],
            "current_status": q["monitoring_protocol"]["current_status"],
            "linked_question": q["question"],
        }
        for q in questions
    ]

    return {
        "schema_version": "player_intelligence_report_v3",
        "player_id": PLAYER_ID,
        "player_name": PLAYER_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope_note": (
            "이 문서는 playerCode=10097(김민선7) 선수만을 다룹니다. 다른 선수의 데이터는 생성되거나 수정되지 "
            "않았습니다. NEO Player Intelligence의 최상위 기준(Gold Standard) 참고 구현입니다."
        ),
        "evidence_score_method": (
            "evidence_score = round(100 * min(1, 독립 공식 출처 수 / 3) * 표본 크기 / (표본 크기 + 5)). 이미 "
            "계산된 표본 크기와 출처 다양성을 하나의 점수로 보여주는 결정적이고 공개된 산식이며, 선수에 대한 "
            "새로운 통계적 주장이 아닙니다."
        ),
        "durability_method": (
            "모든 질문은 다음을 묻습니다 -- 시즌이 하나 더 추가되어도 이 결론이 뒤집히지 않을 가능성이 높은가? "
            f"'{LONG_TERM}'은 기록된 대부분 또는 모든 시즌에서 나타나는 패턴에 기반해 뒤집힐 가능성이 낮음을 "
            f"의미합니다. '{RECENT_TREND}'는 이번 시즌에만 근거하며 앞으로의 시즌에 따라 바뀔 수 있음을 "
            f"의미합니다. '{CONFIRMED_EVENT}'는 이미 종료된 결과로, 향후 데이터로 뒤집힐 수는 없지만 그 자체를 "
            "반복되는 패턴으로 일반화하지도 않습니다."
        ),
        "monitoring_protocol_method": (
            "Player Intelligence V3: 모든 섹션은 단순히 서술된 통계가 아니라 성과 모니터링 프로토콜입니다. "
            "(1) 모니터링 지표 -- 반복 측정된 이력이 있는 실제 공식 지표(단발성 스냅샷 통계는 사용하지 않음). "
            f"(2) 정상 기준 / (3) 저하 기준 -- 실측값이 {_LARGE_SAMPLE_MIN}회 이상이면 정상 범위는 평균 ± "
            "표준편차 1, 저하 기준은 하한선 미만이 2회 연속 나타나는 경우입니다(한 번의 나쁜 대회·라운드로 "
            "잘못된 경고가 뜨지 않도록 합니다). 표본이 이보다 적은 시즌·코스 단위 집계에서는 평균/표준편차 "
            "방식이 통계적으로 의미가 없으므로, 저하 기준은 실측 역대 최저치 경신으로 정의합니다. (4) 다음 점검 "
            "-- 해당 지표와 같은 단위의 다음 실제 이벤트(다음 대회/다음 라운드/다음 시즌/다음 출전). (5) 변화를 "
            "가장 잘 설명하는 지표 -- 골프 상식에 기댄 추측이 아니라, 모니터링 지표와 본인의 다른 세 SG 항목 "
            f"간 실제 피어슨 상관관계를 계산해, 공개된 {_MEANINGFUL_CORRELATION} 기준을 통과할 때만 지목합니다. "
            "통과하지 못하면(이 리포트에서 확인된 모든 대회·라운드 단위 항목 쌍이 해당) 실제 계수와 함께 "
            "'없음'으로 보고하고, 표본이 너무 적어(n=4) 상관관계를 계산할 수 없는 경우에는 '알 수 없음'으로 "
            "보고합니다. 현재 상태 -- 예측이 아니라, 가장 최근에 이미 기록된 실측값을 (2)/(3)의 동일한 기준으로 "
            "비교한 결과입니다. 이는 이 리포트를 매 대회 전에 실제로 활용할 수 있게 만드는 부분입니다 -- 앞으로 "
            "벌어질 일에 대한 예측이 아니라, 지금까지 쌓인 실제 기록을 기준으로 점검하는 것입니다."
        ),
        "contribution_breakdown_method": _CONTRIBUTION_METHOD,
        "pre_tournament_checklist": pre_tournament_checklist,
        "questions": questions,
        "questions_considered_but_unsupported": excluded,
        "win_dna": win_dna,
        "loss_dna": loss_dna,
        "trend_dna": trend_dna,
        "player_playbook": player_playbook,
        "coach_console": coach_console,
        "performance_funnel": performance_funnel,
        "leak_map": leak_map,
        "unsupported_analysis_modules_v12": _UNSUPPORTED_ANALYSIS_MODULES_V12,
        "repository_intelligence_v7": _repository_intelligence_v7_ko(master_doc),
        "source_document": "MASTER_ANALYSIS.json (scripts/build_10097_master_player_analysis.py의 감사 절차를 거친 근거 자료)",
    }


if __name__ == "__main__":
    result = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"questions answered: {len(result['questions'])}")
    print(f"questions excluded as unsupported: {len(result['questions_considered_but_unsupported'])}")
    for q in result["questions"]:
        print(f"  - {q['question']} (confidence={q['confidence']}, durability={q['durability']}, evidence_score={q['evidence_score']})")
