"""Pure rules and thresholds for the NEO Knowledge Engine.

No I/O here. Every threshold is a named constant so any generated sentence
can point back to the exact rule that produced it. Rule predicates receive
an `Evidence` object (defined in knowledge_engine.py) and return bool or,
for reason rules, a list of RuleResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

ELITE_PERCENTILE = 90.0
STRONG_PERCENTILE = 75.0
AVERAGE_BAND = (40.0, 60.0)

MIN_SEASONS_FOR_STRUCTURAL = 2
REVERSAL_MIN_IMPROVEMENT_SG = 0.05
RECENT_VS_LONGTERM_MULTIPLE = 1.5
CONVERSION_GAP_PERCENTILE_POINTS = 25.0
COURSE_HISTORY_MIN_APPEARANCES = 1
COURSE_UNDERPERFORM_SG_DELTA = 1.0

COURSE_SERIES_OVERLAP_THRESHOLD = 0.5

GENERIC_TOURNAMENT_WORDS = {
    "오픈",
    "챔피언십",
    "마스터즈",
    "마스터스",
    "클래식",
    "인비테이셔널",
    "위민스",
    "레이디스",
    "챔피언스",
    "투어",
    "골프",
    "대회",
}

SG_COMPONENT_LABELS = {
    "avg_ott": "SG Off-the-Tee",
    "avg_app": "SG Approach",
    "avg_arg": "SG Around-the-Green",
    "avg_putt": "SG Putting",
    "avg_total": "SG Total",
}

FIELD_METRIC_LABELS = {
    "sg_total": "SG Total",
    "sg_ott": "SG Off-the-Tee",
    "sg_app": "SG Approach",
    "sg_arg": "SG Around-the-Green",
    "sg_putt": "SG Putting",
    "birdie_rate": "버디율",
    "gir_rate": "그린 적중률",
    "par_save_rate": "파세이브율",
    "par_break_rate": "파브레이크율",
    "recovery_rate": "리커버리율",
    "average_putts": "평균 퍼트 수",
    "average_score": "평균 타수",
}


# ---------------------------------------------------------------------------
# Citation / rule result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Citation:
    source: str
    field_path: str
    value: object


@dataclass(frozen=True)
class RuleResult:
    key: str
    text: str
    citations: tuple = ()
    priority: float = 0.0


@dataclass(frozen=True)
class PlayerTypeRule:
    key: str
    label_ko: str
    label_en: str
    test: Callable
    priority: float = 0.0


@dataclass(frozen=True)
class ReasonRule:
    key: str
    priority: float
    test: Callable


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _pctl(evidence, key: str) -> Optional[float]:
    return evidence.field_percentiles.get(key)


def _season_component_avgs(evidence):
    """season -> {component: avg} for the seasons on record, chronological."""
    out = []
    for sp in evidence.season_profiles:
        out.append(
            (
                sp.season,
                {
                    "avg_ott": sp.avg_ott,
                    "avg_app": sp.avg_app,
                    "avg_arg": sp.avg_arg,
                    "avg_putt": sp.avg_putt,
                    "avg_total": sp.avg_total,
                },
            )
        )
    return out


# ---------------------------------------------------------------------------
# Player type rules (first match wins, ordered by descending priority)
# ---------------------------------------------------------------------------


def _rule_precision_ball_striker(evidence) -> bool:
    app = _pctl(evidence, "sg_app")
    ott = _pctl(evidence, "sg_ott")
    return app is not None and ott is not None and app >= STRONG_PERCENTILE and ott >= STRONG_PERCENTILE


def _rule_recovery_specialist(evidence) -> bool:
    arg = _pctl(evidence, "sg_arg")
    rec = _pctl(evidence, "recovery_rate")
    return arg is not None and rec is not None and arg >= STRONG_PERCENTILE and rec >= STRONG_PERCENTILE


def _rule_birdie_hunter(evidence) -> bool:
    putt = _pctl(evidence, "sg_putt")
    birdie = _pctl(evidence, "birdie_rate")
    return putt is not None and birdie is not None and putt >= STRONG_PERCENTILE and birdie >= STRONG_PERCENTILE


def _rule_stable_par_saver(evidence) -> bool:
    par_save = _pctl(evidence, "par_save_rate")
    return par_save is not None and par_save >= STRONG_PERCENTILE and (evidence.volatility or 0) <= 1.0


def _rule_balanced_unclassified(evidence) -> bool:
    return True


PLAYER_TYPE_RULES = (
    PlayerTypeRule(
        key="precision_ball_striker",
        label_ko="정교한 볼스트라이커",
        label_en="Precision Ball-Striker",
        test=_rule_precision_ball_striker,
        priority=100,
    ),
    PlayerTypeRule(
        key="recovery_specialist",
        label_ko="회복력 특화형",
        label_en="Recovery Specialist",
        test=_rule_recovery_specialist,
        priority=100,
    ),
    PlayerTypeRule(
        key="birdie_hunter",
        label_ko="버디 헌터",
        label_en="Birdie Hunter",
        test=_rule_birdie_hunter,
        priority=100,
    ),
    PlayerTypeRule(
        key="stable_par_saver",
        label_ko="안정적인 파세이버",
        label_en="Stable Par-Saver",
        test=_rule_stable_par_saver,
        priority=100,
    ),
    PlayerTypeRule(
        key="balanced",
        label_ko="균형형",
        label_en="Balanced",
        test=_rule_balanced_unclassified,
        priority=0,
    ),
)


# ---------------------------------------------------------------------------
# Why-she-wins rules
# ---------------------------------------------------------------------------


def _find_structural_component(evidence):
    """Component that stayed >= STRONG_PERCENTILE across every season on record."""
    seasons = _season_component_avgs(evidence)
    if len(seasons) < MIN_SEASONS_FOR_STRUCTURAL:
        return None
    components = ("avg_ott", "avg_app", "avg_arg", "avg_putt")
    field_key_by_component = {
        "avg_ott": "sg_ott",
        "avg_app": "sg_app",
        "avg_arg": "sg_arg",
        "avg_putt": "sg_putt",
    }
    best = None
    for comp in components:
        field_key = field_key_by_component[comp]
        pctl = _pctl(evidence, field_key)
        if pctl is None or pctl < STRONG_PERCENTILE:
            continue
        values = [avgs[comp] for _, avgs in seasons]
        if all(v is not None for v in values) and all(v > 0 for v in values):
            if best is None or pctl > best[1]:
                best = (comp, pctl)
    return best


def _win_structural_strength(evidence):
    best = _find_structural_component(evidence)
    if best is None:
        return []
    comp, pctl = best
    label = SG_COMPONENT_LABELS[comp]
    n = len(evidence.season_profiles)
    text = f"최근 {n}시즌 연속 {label}에서 상위 {100 - pctl:.0f}% 수준의 기록을 유지하고 있습니다."
    citation = Citation(source="historical_sg_warehouse_corrected.json", field_path=f"seasons[].{comp}", value=pctl)
    field_key_by_component = {"avg_ott": "sg_ott", "avg_app": "sg_app", "avg_arg": "sg_arg", "avg_putt": "sg_putt"}
    return [RuleResult(key=f"metric_{field_key_by_component[comp]}", text=text, citations=(citation,), priority=100)]


def _win_recent_trend_up(evidence):
    recent = evidence.recent_5_sg
    longterm = evidence.long_term_sg
    if recent is None or longterm is None or longterm <= 0:
        return []
    if recent >= longterm * RECENT_VS_LONGTERM_MULTIPLE and recent > 0:
        text = f"최근 5개 대회 SG Total({recent:+.2f})이 장기 평균({longterm:+.2f}) 대비 뚜렷한 상승세를 보이고 있습니다."
        citation = Citation(source="historical_sg_warehouse_corrected.json", field_path="recent_5_sg", value=recent)
        return [RuleResult(key="recent_trend_up", text=text, citations=(citation,), priority=80)]
    return []


def _win_weakness_reversal(evidence):
    seasons = _season_component_avgs(evidence)
    if len(seasons) < 2:
        return []
    components = ("avg_ott", "avg_app", "avg_arg", "avg_putt")
    field_key_by_component = {"avg_ott": "sg_ott", "avg_app": "sg_app", "avg_arg": "sg_arg", "avg_putt": "sg_putt"}
    prev_season, prev_avgs = seasons[-2]
    cur_season, cur_avgs = seasons[-1]
    results = []
    for comp in components:
        prev_v, cur_v = prev_avgs[comp], cur_avgs[comp]
        if prev_v is None or cur_v is None:
            continue
        if prev_v < 0 and cur_v - prev_v >= REVERSAL_MIN_IMPROVEMENT_SG and cur_v > 0:
            label = SG_COMPONENT_LABELS[comp]
            text = f"{prev_season}시즌 약점이던 {label}이(가) {cur_season}시즌 {cur_v:+.2f}로 반전에 성공했습니다."
            citation = Citation(source="historical_sg_warehouse_corrected.json", field_path=f"seasons[{cur_season}].{comp}", value=cur_v)
            results.append(RuleResult(key=f"metric_{field_key_by_component[comp]}", text=text, citations=(citation,), priority=70))
    return results


def _win_elite_field_metric(evidence):
    results = []
    for key, label in FIELD_METRIC_LABELS.items():
        if key in ("average_score", "average_putts"):
            continue
        pctl = _pctl(evidence, key)
        if pctl is None or pctl < ELITE_PERCENTILE:
            continue
        text = f"{label} 필드 상위 {100 - pctl:.0f}%에 해당하는 엘리트 수준입니다."
        citation = Citation(source="OFFICIAL_SG_NORMALIZED.json / OFFICIAL_PROFILE_NORMALIZED.json", field_path=key, value=pctl)
        priority = 30 + (pctl - ELITE_PERCENTILE) / 10
        results.append(RuleResult(key=f"metric_{key}", text=text, citations=(citation,), priority=priority))
    return results


def _win_course_strength(evidence):
    history = evidence.course_history or []
    if not history:
        return []
    positive = [h for h in history if h.get("sg_total") is not None and h["sg_total"] > 0]
    if len(positive) < COURSE_HISTORY_MIN_APPEARANCES:
        return []
    avg_sg = sum(h["sg_total"] for h in positive) / len(positive)
    if avg_sg <= 0:
        return []
    text = f"이 대회 시리즈 과거 {len(positive)}회 출전에서 평균 SG Total {avg_sg:+.2f}로 강세를 보였습니다."
    citation = Citation(source="historical_sg_warehouse_corrected.json", field_path="course_history[]", value=avg_sg)
    return [RuleResult(key="course_strength", text=text, citations=(citation,), priority=60)]


WIN_REASON_RULES = (
    ReasonRule(key="structural_strength", priority=100, test=_win_structural_strength),
    ReasonRule(key="recent_trend_up", priority=80, test=_win_recent_trend_up),
    ReasonRule(key="weakness_reversal", priority=70, test=_win_weakness_reversal),
    ReasonRule(key="course_strength", priority=60, test=_win_course_strength),
    ReasonRule(key="elite_field_metric", priority=30, test=_win_elite_field_metric),
)


# ---------------------------------------------------------------------------
# Why-she-loses rules
# ---------------------------------------------------------------------------


def _lose_structural_weakness(evidence):
    seasons = _season_component_avgs(evidence)
    if len(seasons) < MIN_SEASONS_FOR_STRUCTURAL:
        return []
    components = ("avg_ott", "avg_app", "avg_arg", "avg_putt")
    field_key_by_component = {
        "avg_ott": "sg_ott",
        "avg_app": "sg_app",
        "avg_arg": "sg_arg",
        "avg_putt": "sg_putt",
    }
    worst = None
    for comp in components:
        field_key = field_key_by_component[comp]
        pctl = _pctl(evidence, field_key)
        if pctl is None:
            continue
        values = [avgs[comp] for _, avgs in seasons]
        if all(v is not None for v in values) and all(v < 0 for v in values):
            if worst is None or pctl < worst[1]:
                worst = (comp, pctl)
    if worst is None:
        return []
    comp, pctl = worst
    label = SG_COMPONENT_LABELS[comp]
    n = len(seasons)
    text = f"최근 {n}시즌 연속 {label}이(가) 필드 평균 이하({pctl:.0f}퍼센타일)로 구조적 약점입니다."
    citation = Citation(source="historical_sg_warehouse_corrected.json", field_path=f"seasons[].{comp}", value=pctl)
    return [RuleResult(key=f"metric_{field_key_by_component[comp]}", text=text, citations=(citation,), priority=100)]


def _lose_newly_weakest(evidence):
    seasons = _season_component_avgs(evidence)
    if len(seasons) < 2:
        return []
    components = ("avg_ott", "avg_app", "avg_arg", "avg_putt")
    field_key_by_component = {"avg_ott": "sg_ott", "avg_app": "sg_app", "avg_arg": "sg_arg", "avg_putt": "sg_putt"}
    prev_season, prev_avgs = seasons[-2]
    cur_season, cur_avgs = seasons[-1]
    results = []
    for comp in components:
        prev_v, cur_v = prev_avgs[comp], cur_avgs[comp]
        if prev_v is None or cur_v is None:
            continue
        if prev_v > 0 and cur_v - prev_v <= -REVERSAL_MIN_IMPROVEMENT_SG and cur_v < 0:
            label = SG_COMPONENT_LABELS[comp]
            text = f"{prev_season}시즌 강점이던 {label}이(가) {cur_season}시즌 {cur_v:+.2f}로 악화되었습니다."
            citation = Citation(source="historical_sg_warehouse_corrected.json", field_path=f"seasons[{cur_season}].{comp}", value=cur_v)
            results.append(RuleResult(key=f"metric_{field_key_by_component[comp]}", text=text, citations=(citation,), priority=80))
    return results


def _lose_conversion_gap(evidence):
    gir = _pctl(evidence, "gir_rate")
    score = _pctl(evidence, "average_score")
    if gir is None or score is None:
        return []
    gap = gir - score
    if gap >= CONVERSION_GAP_PERCENTILE_POINTS:
        text = f"그린 적중률은 상위권({gir:.0f}퍼센타일)이지만 스코어 환산 효율({score:.0f}퍼센타일)이 이를 따라가지 못하고 있습니다."
        citation = Citation(source="OFFICIAL_PROFILE_NORMALIZED.json", field_path="gir_rate/average_score", value=gap)
        return [RuleResult(key="conversion_gap", text=text, citations=(citation,), priority=70)]
    return []


def _lose_course_underperformance(evidence):
    history = evidence.course_history or []
    if not history:
        return []
    negative = [h for h in history if h.get("sg_total") is not None and h["sg_total"] < 0]
    if len(negative) < COURSE_HISTORY_MIN_APPEARANCES:
        return []
    avg_sg = sum(h["sg_total"] for h in negative) / len(negative)
    if avg_sg > -COURSE_UNDERPERFORM_SG_DELTA:
        return []
    text = f"이 대회 시리즈 과거 {len(negative)}회 출전에서 평균 SG Total {avg_sg:+.2f}로 부진했습니다."
    citation = Citation(source="historical_sg_warehouse_corrected.json", field_path="course_history[]", value=avg_sg)
    return [RuleResult(key="course_underperformance", text=text, citations=(citation,), priority=60)]


def _lose_average_band_metric(evidence):
    total = _pctl(evidence, "sg_total")
    if total is None or total < ELITE_PERCENTILE:
        return []
    results = []
    for key, label in FIELD_METRIC_LABELS.items():
        if key in ("sg_total",):
            continue
        pctl = _pctl(evidence, key)
        if pctl is None:
            continue
        lo, hi = AVERAGE_BAND
        if lo <= pctl <= hi:
            text = f"전체 기량은 최상위권이지만 {label}은(는) 필드 평균 수준({pctl:.0f}퍼센타일)에 머물러 있습니다."
            citation = Citation(source="OFFICIAL_SG_NORMALIZED.json / OFFICIAL_PROFILE_NORMALIZED.json", field_path=key, value=pctl)
            results.append(RuleResult(key=f"metric_{key}", text=text, citations=(citation,), priority=30))
    return results


LOSE_REASON_RULES = (
    ReasonRule(key="structural_weakness", priority=100, test=_lose_structural_weakness),
    ReasonRule(key="newly_weakest", priority=80, test=_lose_newly_weakest),
    ReasonRule(key="conversion_gap", priority=70, test=_lose_conversion_gap),
    ReasonRule(key="course_underperformance", priority=60, test=_lose_course_underperformance),
    ReasonRule(key="average_band_metric", priority=30, test=_lose_average_band_metric),
)
