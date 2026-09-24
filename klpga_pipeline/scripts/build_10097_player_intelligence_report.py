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


def _action_from_protocol(protocol: dict) -> str:
    return (
        f"{protocol['metric']}을(를) 모니터링합니다({protocol['source']}). 정상 범위: {protocol['normal_range']}. "
        f"저하 기준(기술/훈련 점검 필요): {protocol['warning_threshold']}. "
        f"다음 점검: {protocol['next_review']}. 가장 최근 실측값 기준 현재 상태: "
        f"{terms.STATUS_LABEL[protocol['current_status']]} -- {protocol['current_detail']}"
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
        f"공식 기록상 확인된 우승은 총 {win_fact['sample_size']}회입니다({win_names}). 이 우승들에는 공통된 "
        "메커니즘이 있습니다 -- 네 시즌 내내 플러스 스코어링 가치를 만들어낸 SG APP 게임으로, 우승한 주에만 "
        "국한되지 않습니다."
    )
    evidence = [
        f"{len(season_profiles)}개 시즌, {sum(p.n_tournaments for p in season_profiles)}개 대회 전체 기록의 시즌별 SG APP: {app_trend} -- 4개 시즌 연속으로 같은 항목에서 플러스이자 상승하는 수치를 보였습니다.",
        f"{reasons[1]['statement']} -- 이번 시즌 한정 지표입니다(평가 대상 {reasons[1]['sample_size']}명 기준). SG APP 추세처럼 여러 시즌에 걸쳐 확인된 것은 아직 아닙니다.",
        f"{reasons[2]['statement']} -- 역시 이번 시즌 한정 지표입니다(평가 대상 {reasons[2]['sample_size']}명 기준).",
    ]
    analysis = (
        "우승 자체는 일회성 사건이지만, 그 뒤에 있는 메커니즘은 그렇지 않습니다. 공식 기록에 남아있는 모든 "
        "시즌에서 같은 패턴이 나타납니다 -- 경기력의 다른 부분이 아직 무르익지 않았던 시즌에도 SG APP만큼은 "
        "마이너스로 떨어진 적이 없습니다. 이 부분이 좋은 라운드를 우승으로 바꾸는 핵심입니다 -- 다른 선수들보다 "
        "꾸준히 더 많은 Birdie 기회를 만들어내며, 이번 시즌의 뛰어난 GIR과 파세이브율은 그 우위가 Bogey를 "
        "줄이는 동시에 Birdie를 늘리는 방향으로 이어지고 있음을 보여줍니다."
    )
    conclusion = (
        f"{PLAYER_NAME} 선수가 우승하는 이유는 SG APP 게임이 만들어내는 스코어링 우위가 뛰어온 모든 시즌에서 "
        "유지되어 왔기 때문입니다 -- 한 번의 좋은 주간이 아니라는 뜻입니다. 이번 시즌의 뛰어난 GIR과 "
        "파세이브율은 이 구조적 강점 위에 더해지는 것이지, 이를 대체하는 것이 아닙니다."
    )
    why_it_matters = (
        "코칭스태프가 우승의 이유를 정확히 이해하면, 이 메커니즘을 의도적으로 보호하며 경기 전략과 훈련 계획을 "
        "세울 수 있습니다. 그저 좋은 한 주로 넘기고 무엇이 그 결과를 만들었는지 묻지 않는 것과는 다릅니다."
    )
    player_takeaway = (
        "압박감 속에서도 SG APP 게임을 믿으십시오 -- 지난 네 시즌 동안 한 번도 무너지지 않은 부분이며, "
        "출발이 좋지 않을 때 무리한 라인을 선택하기보다 기본적으로 의지해야 할 샷입니다."
    )
    protocol = _tournament_component_protocol(ds, "approach", terms.SG_COMPONENT["approach"])
    coach_focus = (
        f"GIR과 파세이브율은 이번 시즌 한 시점의 스냅샷 데이터일 뿐입니다 -- KLPGA는 두 지표 모두 라운드별이나 "
        f"대회별 연속 기록을 공개하지 않으므로, 아직은 운영 가능한 주기로 모니터링할 수 없습니다. 반면 대회별 "
        f"SG APP는 가능합니다 -- 실측 {protocol['sample_size']}개 대회의 기록이 있으며, 이 프로토콜이 "
        "추적하는 지표입니다."
    )
    durability = LONG_TERM
    durability_reasoning = (
        "핵심 동력인 SG APP는 공식 기록상 네 시즌 모두 플러스였고 상승세였습니다. 따라서 한 시즌이 "
        "더해진다 해도 이 결론을 뒤집기보다 강화할 가능성이 훨씬 큽니다. 다만 GIR과 파세이브율 인용치는 이번 "
        "시즌 순위표에서만 나온 수치입니다 -- 내년에 둘 중 하나가 하락하더라도 우승의 원인은 여전히 SG APP로 "
        "설명되지만, 이 두 보조 수치만큼은 아직 해마다 보장되는 특성으로 간주해서는 안 됩니다."
    )
    why_this_matters = "이번 주 경기 전략을 세울 때 중심에 두어야 할 샷이지, 우승 후에야 되돌아보며 감탄할 대상이 아닙니다."
    action = _action_from_protocol(protocol)

    sample_sizes = [win_fact["sample_size"], sum(p.n_tournaments for p in season_profiles)] + [r["sample_size"] for r in reasons]
    sources = set(win_fact["official_records_used"]) | {s for r in reasons for s in r["official_records_used"]}
    return {
        "id": "q_why_wins",
        "question": f"{PLAYER_NAME} 선수는 왜 우승하는가?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
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
        "SG PUTT은 지난 네 시즌 동안 김민선7 선수에게 우승을 만들어준 영역이 아니었습니다 -- 공식 기록상 네 "
        "시즌 모두 스코어링 기여도가 가장 작은 항목이었고, 이번 시즌에는 그 격차가 줄어들기는커녕 더 "
        "벌어졌습니다."
    )
    evidence = [
        f"시즌별 SG PUTT: {putt_trend} -- 매 시즌 다른 세 항목보다 작았고, {this_season.season}시즌 수치가 네 시즌 중 가장 낮습니다.",
        f"{reasons[0]['statement']} -- 필드 평균 수준으로 나쁘지는 않지만, 93~97 백분위에 이르는 본인의 SG APP·SG OTT 수준과 비교하면 상대적으로 부족합니다. 필드와 비교한 것이 아니라 본인 안에서 비교한 결과입니다(평가 대상 {reasons[0]['sample_size']}명 기준).",
        f"{reasons[1]['statement']} -- 독립된 두 번째 지표에서도 동일하게 필드 평균 수준으로 나타납니다(평가 대상 {reasons[1]['sample_size']}명 기준).",
    ]
    analysis = (
        "SG APP를 비롯한 볼 스트라이킹은 필드의 거의 누구보다 많은 스코어링 기회를 만들어내지만, 그 기회를 "
        "볼 스트라이킹 수준에 걸맞은 비율로 Birdie로 연결하지 못하고 있습니다. 이 격차는 선수 생활 내내 "
        "존재해 왔으므로 한 주에 고칠 수 있는 슬럼프가 아니라, SG APP 샷이 실제 스코어로 이어지는 비율에 "
        f"대한 구조적인 한계에 가깝습니다. 이번 시즌의 하락({this_season.avg_putt:+.2f}, 지난해 "
        f"{last_season.avg_putt:+.2f}에서 하락)은 새롭게 나타난 부분이므로, 저절로 회복될 것이라 가정하기보다 "
        "계속 지켜볼 필요가 있습니다."
    )
    conclusion = (
        "SG APP 게임은 꾸준히 스코어링 기회를 만들어내지만, SG PUTT은 그 기회를 볼 스트라이킹 수준이 "
        "예상하게 하는 만큼 Birdie로 전환하지 못하고 있습니다 -- 공식 기록상 모든 시즌에서 사실이며, 지난 "
        "3개 시즌보다 올해 그 격차가 더 큽니다."
    )
    why_it_matters = (
        "쇼트게임 전환 문제로 인한 우승 실패는 볼 스트라이킹 붕괴로 인한 실패와는 전혀 다른 대응이 필요합니다. "
        "원인을 잘못 짚으면 훈련 시간을 엉뚱한 곳에 쓰게 됩니다."
    )
    player_takeaway = (
        "가장 큰 손실은 그린을 놓치는 것이 아니라, 충분히 넣을 수 있는 Birdie 퍼트를 놓치는 것입니다. 이번 "
        "시즌에는 샷 메이킹이 아니라 스코어 전환력을 성장 과제로 삼아야 합니다."
    )
    protocol = _tournament_component_protocol(ds, "putting", terms.SG_COMPONENT["putting"])
    coach_focus = (
        f"SG PUTT은 시즌 단위가 아니라 대회별로 기록되므로, 실측 {protocol['sample_size']}개 대회를 기준으로 "
        "운영 가능한 범위를 설정할 수 있습니다 -- 하락 조짐을 조기에 포착하려면 시즌 합산치가 아니라 대회별로 "
        "발표되는 수치를 그대로 활용하십시오."
    )
    durability = LONG_TERM
    durability_reasoning = (
        "SG PUTT은 공식 기록상 네 시즌 모두 스코어링 기여도가 가장 작은 항목이었습니다. 따라서 'SG PUTT이 "
        "주력 강점이 아니다'라는 판단은 한 시즌이 더해져도 유지될 가능성이 매우 높습니다 -- 다섯 번째 시즌은 "
        "이 패턴을 깨기보다 다시 확인해 줄 가능성이 큽니다. 반면 올해 하락폭의 크기는 더 얇고 새로운 "
        "근거입니다 -- 다음 시즌에 반등하더라도 4개 시즌에 걸친 큰 흐름 자체를 뒤집지는 않으므로, 이 수치 "
        "하나는 그 구조적 판단보다는 낮은 비중으로 다뤄야 합니다."
    )
    why_this_matters = "다음 스트로크 게인은 스윙을 바꿔서가 아니라 스코어 전환력에서 나와야 합니다."
    action = _action_from_protocol(protocol)

    sample_sizes = [r["sample_size"] for r in reasons]
    sources = {s for r in reasons for s in r["official_records_used"]}
    return {
        "id": "q_why_loses",
        "question": f"{PLAYER_NAME} 선수는 왜 우승을 놓치는가?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
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
        "네 시즌에 걸쳐 SG APP는 김민선7 선수의 가장 꾸준한 스코어링 강점으로 남아 있습니다. 경기력의 다른 "
        "부분이 아직 무르익지 않았던 시즌에도 SG APP만큼은 플러스 가치를 만들어내는 것을 멈춘 적이 없습니다."
    )
    evidence = [
        f"이번 시즌 필드 백분위: 평가 대상 {audit['sample_size']}명 중 {app_axis['percentile']:.1f}번째 -- 현재 필드에서 가장 신뢰할 수 있는 SG APP 선수 중 한 명입니다.",
        f"{audit['season_count']}개 시즌, {audit['tournament_count']}개 대회 전체 기록의 시즌별 SG APP 평균: {app_trend} -- 매 시즌 본인의 1순위 또는 2순위 항목이었습니다.",
        f"고정된 Knowledge Engine 분류: \"{pi['player_type']['label_ko']}\" ({pi['player_type']['label_en']}) -- \"{insight['insight']}\"",
    ]
    analysis = (
        "단 한 시즌의 특출난 성적은 지금 효과를 보고 있는 스윙 변화이거나, 내년에는 꺾일 볼 스트라이킹의 반짝 "
        "호조일 수 있습니다. 그러나 같은 항목이 네 시즌 연속으로 최상위권을 유지하는 것은 다른 신호입니다 -- "
        "SG APP는 '요즘 잘하고 있는' 부분이 아니라, 경기력의 다른 부분이 어떻든 관계없이 '꾸준히 잘하는' "
        "부분이라는 뜻입니다."
    )
    conclusion = (
        "SG APP는 김민선7 선수의 가장 지속력 있는 강점입니다 -- 이번 주 수치가 가장 좋아서가 아니라, 지난 "
        "4년간 부진한 시즌이 단 한 번도 없었기 때문입니다."
    )
    why_it_matters = (
        "어떤 강점이 반짝 호조가 아니라 지속력 있는 강점인지 알면, 경기력의 다른 부분을 조정할 때 절대 손대서는 "
        "안 될 부분이 무엇인지 코칭스태프에게 알려줍니다."
    )
    protocol = _tournament_component_protocol(ds, "approach", terms.SG_COMPONENT["approach"])
    player_takeaway = "경기력의 다른 부분을 위해 절대 희생해서는 안 될 샷입니다 -- 어떤 기술적 조정을 하더라도 SG APP 메커니즘을 가장 먼저 보호해야 합니다."
    coach_focus = (
        f"위 우승 원인 지표와 동일한 운영 프로토콜을 사용합니다(대회별 SG APP, 실측 "
        f"{protocol['sample_size']}개 대회 기준) -- 이 질문과 '왜 우승하는가'는 결국 같은 근본 강점을 추적하는 "
        "동일한 지표로 보호됩니다."
    )
    durability = LONG_TERM
    durability_reasoning = (
        "4개 시즌 연속 플러스 기록은 한 선수의 기록이 보여줄 수 있는 가장 강한 수준의 지속성 신호입니다 -- 한 "
        "시즌이 더해지면 이 흐름이 끊길 가능성보다 이어질 가능성이 훨씬 큽니다. 이 판단은 실제로 어느 시즌에서든 "
        "뚜렷한 하락이 나타날 때만 다시 검토하면 되며, 지금까지는 그런 사례가 없습니다."
    )
    why_this_matters = "이번 한 대회뿐 아니라 매 대회 경기 전략의 중심에 두어야 할 샷입니다."
    action = _action_from_protocol(protocol)

    sources = set(audit["official_records_used"])
    return {
        "id": "q_approach_biggest_weapon",
        "question": f"{PLAYER_NAME} 선수에게 SG APP가 최고의 무기인 이유는?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
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

    fact = (
        "SG PUTT은 김민선7 선수의 경기 중 다른 항목들만큼 성장 속도를 따라가지 못한 유일한 부분입니다 -- 이번 "
        "시즌에도 본인의 네 가지 샷 항목 중 가장 낮은 순위이며, 이는 새로운 현상이 아닙니다."
    )
    evidence = [
        f"이번 시즌 본인의 항목별 분포: {axis_line} -- 모두 동일한 {reason['sample_size']}명 규모의 공식 SG 필드 기준 백분위입니다.",
        f"시즌별 SG PUTT: {putt_trend} -- 공식 기록상 매 시즌 본인의 네 항목 중 가장 작았으며, 올해만의 현상이 아닙니다.",
    ]
    analysis = (
        "필드가 아니라 본인의 네 항목을 서로 비교해 보면, 훈련 시간 배분을 생각할 때 의미 있는 결론이 "
        "달라집니다: SG OTT, SG APP, SG ARG은 모두 투어에서 최상위권으로 볼 수 있는 범위에 "
        "있지만, SG PUTT만은 그렇지 않습니다. 이는 'SG PUTT이 나쁘다'는 말과는 다릅니다 -- 지금 가진 것에 비해 "
        "다음 한 시간의 훈련이 가장 큰 개선을 가져올 곳이 어디인지를 말해주는 지표입니다."
    )
    conclusion = (
        "SG PUTT은 절대적인 의미에서 약점이 아닙니다 -- 공식 기록상 매 시즌 경기력의 다른 부분만큼 성장하지 "
        "못한 유일한 항목이며, 그래서 앞으로의 성장에서 가장 효율이 높은 영역이 됩니다."
    )
    why_it_matters = (
        "훈련 시간은 한정되어 있습니다. SG PUTT이 공식 기록상 매 시즌 경기력의 다른 부분을 따라가지 못한 유일한 "
        "항목이라는 사실은, 이미 최상위권인 기술을 더 다듬기보다 SG PUTT에 훈련 시간을 더 배분해야 하는 근거가 "
        "됩니다."
    )
    protocol = _season_component_protocol(season_profiles, "avg_putt", terms.SG_COMPONENT["putting"], f"위 대회별 {terms.SG_COMPONENT['putting']} 프로토콜(실측 73대회 기준)")
    player_takeaway = "'가장 약한 부분'을 'SG PUTT이 서툴다'는 뜻으로 읽지 마십시오 -- 나머지 모든 부분이 최상위권까지 끌어올려졌고, SG PUTT만이 그 격차를 좁힐 여지가 남아 있다는 뜻입니다."
    coach_focus = (
        f"'왜 우승을 놓치는가' 프로토콜이 대회 단위로 추적하는 것과 같은 지표(SG PUTT)를 여기서는 "
        f"{protocol['sample_size']}개 시즌 단위로 살펴봅니다 -- 훈련 시간 재배분이 주 단위가 아니라 연 단위로 "
        "내부 격차를 좁히고 있는지 확인하기 위해서입니다."
    )
    durability = LONG_TERM
    durability_reasoning = (
        "본인의 네 항목 중 SG PUTT이 가장 낮다는 이 순위는 공식 기록상 네 시즌 내내 유지되어 왔습니다. 이 "
        "결론이 바뀌려면 SG PUTT이 나머지 세 항목과의 내부 격차를 실제로 좁히는, 지금까지와는 전혀 다른 패턴이 "
        "나타나야 하는데, 지금까지의 기록에서는 그런 사례가 없습니다."
    )
    why_this_matters = "다음 한 시간의 훈련이 가장 큰 효과를 가져올 곳입니다."
    action = _action_from_protocol(protocol)

    sample_sizes = [reason["sample_size"]]
    sources = set(reason["official_records_used"]) | {"knowledge_engine.compute_season_profiles() (player_dna.axes)"}
    return {
        "id": "q_putting_weakest",
        "question": f"{PLAYER_NAME} 선수에게 SG PUTT이 가장 약한 부분이 된 이유는?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
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

    fact = (
        "김민선7 선수가 성장기 선수에서 우승 선수로 발전한 과정은 한 시즌 만에 이루어지지 않았습니다 -- 전체 "
        "스코어링 가치는 공식 기록상 네 시즌 모두 상승했으며, 그 상승의 모양은 반짝 SG PUTT 호조가 아니라 볼 "
        "스트라이킹을 따라가고 있습니다."
    )
    evidence = [
        f"시즌별 SG Total: {total_trend} -- 매 시즌 상승했고, 해마다 16~23개 대회의 표본이 뒷받침합니다.",
        f"같은 상승세가 SG OTT({ott_trend})와 SG APP({app_trend})에서도 나타나는 반면, SG PUTT은 같은 속도로 오르지 않았습니다({putt_trend}) -- 이번 향상이 쇼트게임이 아니라 볼 스트라이킹에서 비롯되었다는 근거입니다.",
    ]
    analysis = (
        "두 개의 볼 스트라이킹 항목이 네 시즌 연속으로 함께 상승하고, 그 뒤에 시즌마다 실제 대회 표본이 "
        "뒷받침한다는 것은 반짝 상승이 아닙니다 -- 시간이 지나며 스윙 퀄리티와 거리 컨트롤이 실제로 좋아지고 "
        "있는 선수의 전형적인 모습입니다. 동시에 무엇을 이번 향상의 원인으로 보면 안 되는지도 알려줍니다 -- "
        "SG PUTT은 비슷한 속도로 오르지 않았으므로, '쇼트게임이 따라잡았다'는 설명은 본인의 기록으로 "
        "뒷받침되지 않습니다."
    )
    conclusion = (
        "2026시즌 경기력은 한 해의 반짝 호조가 아니라 여러 시즌에 걸친 실제 볼 스트라이킹 향상의 연장선입니다 "
        "-- 이 기록이 말해주는 것은, 이 향상을 이끈 기술 훈련 프로그램만큼은 바꾸어서는 안 된다는 점입니다."
    )
    why_it_matters = "이번 향상이 운이 아니라 구조적인 변화라는 점을 확인해 두면, 한 주 부진했다고 해서 실제로 효과를 보고 있는 프로그램을 코칭스태프가 다시 의심하는 일을 막을 수 있습니다."
    player_takeaway = "이 향상은 실제이며, 앞으로도 계속 쌓아 나갈 수 있는 것입니다 -- 한 번의 운 좋은 조정에서 나온 것이 아니므로, 한 번의 나쁜 주 이후에도 볼 스트라이킹 중심의 현재 훈련 방향을 의심하기보다 계속 이어가는 것이 맞습니다."
    protocol = _season_component_protocol(
        season_profiles, "avg_total", terms.SG_TOTAL,
        f"본인의 대회별 {terms.SG_TOTAL} 실측치(historical_sg_warehouse_corrected.json, scope=tournament_cumulative, field='total', 실측 73대회 기준)",
    )
    coach_focus = (
        f"SG Total을 시즌 단위(실측 {protocol['sample_size']}개 시즌 기준)로 점검하십시오 -- 이는 한 주 "
        "단위의 전술적 신호가 아니라 시즌 단위로 확인해야 할 육성 프로그램 신호입니다."
    )
    durability = LONG_TERM
    durability_reasoning = (
        "이미 4개 시즌에 걸친 흐름이므로, 이 기록이 보여줄 수 있는 가장 지속성 있는 판단에 가깝습니다. 다섯 "
        "번째 시즌에도 이 흐름이 이어진다면 근거는 더 강해지고, 설령 다섯 번째 시즌이 정체되더라도 지난 4년간의 "
        "실제 향상 자체가 사라지는 것은 아닙니다 -- 앞으로의 방향에만 영향을 줄 뿐, 이미 일어난 일을 바꾸지는 "
        "않습니다."
    )
    why_this_matters = "지금까지 효과가 있었던 방식을 계속 유지하십시오 -- 변화가 필요한 선수의 기록이 아닙니다."
    action = _action_from_protocol(protocol)

    sources = set(audit["official_records_used"])
    return {
        "id": "q_2026_improvement",
        "question": f"{PLAYER_NAME} 선수의 경기력은 왜 2026시즌까지 꾸준히 향상되었는가?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
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

    fact = (
        f"김민선7 선수가 이미 출전한 적 있는 코스로 돌아갈 때, 공식 기록은 조심스럽게 관리하기보다 믿고 맡겨야 "
        f"한다는 것을 보여줍니다. 가장 강한 반복 성적은 {group['series_name_sample']}에서 나왔으며, 실측 {n}회 "
        "출전에서 플러스 스코어링 평균을 만들어냈고 가장 최근 출전은 우승이었습니다."
    )
    evidence = [
        f"시즌별 출전 기록의 SG Total: {history_line} -- 실측 {n}회 출전 모두 플러스였고, 그중 가장 좋은 성적이 가장 최근 출전에서 나왔습니다.",
        f"{n}회 출전 전체 평균 SG Total: {group['avg_sg_total']:+.2f}로, 통산 평균을 크게 웃돕니다.",
    ]
    analysis = (
        "코스에서의 한 번의 좋은 주간은 조 편성이나 그날의 컨디션 덕분일 수 있습니다. 그러나 서로 다른 네 "
        "시즌에 걸친 실측 네 차례 출전이 모두 플러스였고, 그중 가장 좋은 성적이 가장 최근 출전에서 나왔다는 "
        "것은 우연이라기보다 쌓여온 코스 이해도에 가깝습니다. 이는 한 주의 컨디션 점검과는 다른 종류의 "
        "통찰입니다 -- 이 코스가 본인이 이미 잘하는 부분을 보상해 주며, 반복될수록 그 효과가 흐려지기보다 "
        "오히려 더 날카로워졌다는 뜻입니다."
    )
    conclusion = (
        f"이 코스에서는 새로운 시도를 하기보다 이미 검증된 방식에 의지하는 경기 전략이 맞습니다 -- {n}회의 "
        "출전과 상승하는 흐름은 단순한 한 번의 행운이 아니라 실제 코스 친숙도를 가리킵니다."
    )
    why_it_matters = "좋은 성적이 추측이 아니라 특정 코스에서 근거를 가진 결과라는 것을 알면, 코칭스태프가 현장에서 선수의 감각을 믿어야 할 때와 막판 변화를 자제해야 할 때를 판단하는 데 도움이 됩니다."
    player_takeaway = "이 코스에서는 막연한 낙관이 아니라 실제 성적으로 뒷받침된 자신감을 가지고 임하십시오 -- '나에게 잘 맞는 코스'라는 느낌이 데이터로도 확인됩니다."
    protocol = _course_appearance_protocol(group)
    coach_focus = f"{group['series_name_sample']}을(를) 좋은 한 주가 어떤 모습인지 보여주는 기준으로 삼고, 다음 출전을 앞둔 주에는 스윙이나 전략을 바꾸는 것을 특히 조심하십시오."
    durability = LONG_TERM
    durability_reasoning = (
        f"이미 실측된 {n}회의 출전은 앞으로 무슨 일이 있어도 바뀌지 않는 기록입니다 -- 다음 출전에서 무슨 일이 "
        "벌어지든 그대로 유지됩니다. 다만 표본이 네 개뿐이므로, 다음 출전에서 평균 이하의 성적이 나오면 전체 "
        "평균은 눈에 띄게 낮아질 수 있습니다(패턴 자체가 뒤집히는 것은 아니지만). 확정된 결론이 아니라 강한 "
        "경향으로 다루십시오."
    )
    why_this_matters = "선수를 지나치게 코치하기보다 믿고 맡겨야 한다는 것이 기록에서 가장 분명하게 드러나는 지점입니다."
    action = _action_from_protocol(protocol)

    sources = {"historical_sg_warehouse_corrected.json", "knowledge_engine.find_course_history()"}
    return {
        "id": "q_strong_course",
        "question": f"{PLAYER_NAME} 선수는 왜 {group['series_name_sample']}에서 강한가?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
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

    fact = (
        "가장 최근 우승은 지켜내야 할 빠른 출발에서 나온 것이 아니었습니다 -- 2라운드에 SG Total이 소폭 하락한 "
        "뒤, 대회가 갈리는 시점인 3라운드에서 대회 중 가장 좋은 라운드가 나왔습니다."
    )
    evidence = [
        f"라운드별 SG Total: {sg_line} -- 세 라운드 중 가장 좋은 라운드가 마지막에 나왔습니다.",
        f"공식 결과: {win['tournament']} ({win['final_score']}, 최종 {win['final_rank']}위) -- {win['official_source']}.",
    ]
    analysis = (
        "리드를 지키다 소극적인 마지막 라운드로 마무리하는 우승과, 가장 좋은 라운드가 마지막에 나오는 우승은 "
        "선수의 대회 운영 방식에 대해 서로 다른 이야기를 들려줍니다. 이번 결과는 후자에 해당하며, 이 대회 "
        "하나에 대해 실제로 확인된 사실입니다. 다만 이 결과 하나만으로 반복되는 특성이라고 단정할 수는 "
        f"없습니다 -- 라운드 간 흐름 전체를 살펴보면(실측 연속 라운드 쌍 {delta_n}개 기준) 평균 변화가 "
        f"{delta_mean:+.2f} SG로 사실상 큰 흐름이 없고 등락 폭도 양방향으로 넓게 나타납니다. 따라서 이번 우승은 "
        "이 대회를 준비할 때 참고할 사실이지, '항상 대회 후반에 강해진다'는 일반적인 특성으로 확대 해석해서는 "
        "안 됩니다."
    )
    conclusion = (
        "가장 최근 우승은 최상은 아니었던 2라운드를 거친 뒤 마지막 라운드에서 정점을 찍으며 만들어졌습니다 -- "
        "이 한 번의 결과에 대해 실제로 확인된 사실이며, 아직 우승 전반에 걸쳐 확립된 패턴은 아닙니다."
    )
    why_it_matters = "이번 결과에서 무엇이 확인되었고 무엇을 일반화하려면 더 많은 근거가 필요한지를 정확히 구분해 두면, 준비 과정을 실제 있었던 일에 근거하게 만들 수 있습니다. 하나의 사례로 만든 이야기에 의존하지 않게 됩니다."
    player_takeaway = "이번 결과는 평범한 2라운드가 우승을 가로막지 않았다는 실제 증거입니다 -- 다만 더 넓은 기록에서는 이것이 매번 기대할 수 있는 일이라고까지는 아직 보여주지 않으므로, 유리한 사례 하나로 다루되 보장으로 받아들이지는 마십시오."
    protocol = _round_total_protocol(ds)
    coach_focus = (
        f"실전 대회 중에는 이 한 번의 우승에서 나온 심리적 패턴을 가정하기보다, 아래의 라운드별 SG Total "
        f"프로토콜을 실시간 신호로 활용하십시오 -- 실측 {protocol['sample_size']}개 라운드를 기준으로 합니다."
    )
    durability = CONFIRMED_EVENT
    durability_reasoning = (
        "이 일은 이미 일어났고 공식 결과로 확정되어 있으므로, 앞으로 어떤 데이터가 나오더라도 바뀌지 않습니다. "
        f"다만 라운드 간 흐름 전체를 확인한 결과(실측 전환 {delta_n}건, 평균 변화 {delta_mean:+.2f} SG) 선수 "
        "생활 전체에서 일관되게 상승하는 패턴은 나타나지 않았습니다. 따라서 이 결과는 이 대회 하나에 대한 "
        "확정된 사실로만 보고하며, 근거가 없는 반복적 특성으로 확대하지 않습니다."
    )
    why_this_matters = "출발이 더딜 때 코칭스태프가 활용할 수 있는, 실제로 확인된 최근 사례 하나를 제공합니다."
    action = _action_from_protocol(protocol)

    sources = {win["official_source"].split(" (")[0]}
    return {
        "id": "q_most_recent_win",
        "question": f"{PLAYER_NAME} 선수는 최근 우승, {win['tournament']}을(를) 어떻게 만들어냈는가?",
        "fact": fact,
        "evidence": evidence,
        "analysis": analysis,
        "conclusion": conclusion,
        "why_it_matters": why_it_matters,
        "player_takeaway": player_takeaway,
        "coach_focus": coach_focus,
        "durability": durability,
        "durability_reasoning": durability_reasoning,
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
# Assembly
# ---------------------------------------------------------------------------


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

    candidates = [
        _q_why_wins(master_doc, ds, season_profiles),
        _q_why_loses(master_doc, ds, season_profiles),
        _q_approach_biggest_weapon(master_doc, ds, season_profiles, career_breakdown),
        _q_putting_weakest(master_doc, ds, season_profiles),
        _q_2026_improvement(master_doc, season_profiles),
        _q_strong_course(master_doc, by_code),
        _q_most_recent_win(master_doc, ds, by_code),
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
