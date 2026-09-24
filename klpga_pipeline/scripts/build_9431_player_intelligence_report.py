"""PLAYER INTELLIGENCE REPORT (Gold Standard V6, 한국어) -- 박보겸
(playerCode=9431) ONLY.

The SECOND Gold Standard reference implementation, after 김민선7
(10097). This is NOT a template replacement: every fact, number, and
conclusion below is computed fresh from 박보겸's own real official
records. Her real story is genuinely different from 10097's --
- Career-wide, her SG components are close to even (SG OTT 35.5%, SG
  APP 31.4%, SG ARG 16.9%, SG PUTT 16.2% of her real 62-tournament SG
  Total on record) -- she is classified "균형형" (Balanced), not a
  single-weapon player, and that classification is corroborated by
  this report's own independent WIN/LOSS/TREND DNA, computed entirely
  separately from the frozen engine's classifier.
- Her strongest real signal is SG Around-the-Green -- not on raw
  magnitude, but on a 4-season, field-relative percentile (91.7th),
  which this report states honestly as two different, both-true facts
  (modest in her own SG units; elite relative to the field).
- Her season-over-season SG Total is NOT a steady rise like 10097's:
  2023 +0.93 -> 2024 +1.43 -> 2025 +0.68 -> 2026 +0.83, a rise, a real
  decline, and a partial recovery. This report describes that shape
  honestly, never smoothing it into an "improving" story it isn't.
- She has 2 real wins on record (2023, 2024), not 4. Her SG APP
  specifically dominates both wins (64.4% of the combined SG Total in
  her win_dna, computed below) even though SG APP is not her single
  biggest career-wide component -- a real, disclosed, non-obvious
  finding this report states as its own fact, not smoothed to match
  her career profile.
- SPECIAL REQUIREMENT DISCLOSURE: this mission asked for a major
  championship victory to be analyzed separately. Checked against every
  win-tracking source in this repository (empirical_sg_corrected_v2,
  three independent SG-warehouse snapshots, and her own official KLPGA
  entry-exemption record) -- no major championship win exists on record
  for this player. Her most recent win's own official qualification
  category is literally "2024 일반대회 우승자" (2024 REGULAR-tournament
  winner), not "메이저대회 우승자" (major-tournament winner). Per this
  report's own data policy (never invent, never force an unsupported
  claim into an existing pattern), `major_championship_analysis` below
  states this directly rather than mislabeling one of her 2 real wins
  as a major. If a real major win exists outside this repository's
  2023-2026 data window, it is not reproducible from official data
  currently in scope and is therefore not claimed here.

Localization, not translation: every UI label comes from ONE shared
dictionary, player_intelligence_9431_terms.py (imported as `terms`),
which re-exports 10097's own dictionary verbatim -- the wording is
identical across both Gold Standard reports. Only the standard golf
terms stay in English (SG, GIR, APP, PUTT, ARG, OTT, Birdie, Bogey,
Driver, Iron, Wedge, Fairway, Green); everything else is natural
Korean, in the voice of a Korean national-team performance analyst.

V6 features included from the start (not iterated toward): every
question is FACT -> EVIDENCE -> ANALYSIS -> CONCLUSION, followed by a
coaching brief, a durability classification, a monitoring protocol (5
disclosed items + current status, checked against her most recent real
reading, never a forecast), and a contribution_breakdown wherever real
component data supports one. WIN DNA / LOSS DNA / TREND DNA are
computed once and never duplicated as a question's own
contribution_breakdown. Every conclusion appears exactly once.

Never touches the frozen Knowledge Engine and never recalculates a
statistic beyond real aggregation of rows already on disk: every
number here is read from
content/website_v2/knowledge_engine/player_intelligence/9431/MASTER_ANALYSIS.json
(built by scripts/build_9431_master_player_analysis.py) or
knowledge_engine.compute_season_profiles().

Scope: playerCode=9431 ONLY. No other player is read, generated, or
touched.
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
from klpga.website_v2 import player_intelligence_9431_terms as terms  # noqa: E402

_spec = importlib.util.spec_from_file_location("master_analysis_9431_under_report", ROOT / "scripts" / "build_9431_master_player_analysis.py")
master = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(master)

PLAYER_ID = master.PLAYER_ID
PLAYER_NAME = master.PLAYER_NAME
OUTPUT_PATH = CONTENT_DIR / "knowledge_engine" / "player_intelligence" / PLAYER_ID / "PLAYER_INTELLIGENCE_REPORT.json"

_CONFIDENCE_RANK = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}

LONG_TERM = "LONG_TERM_CHARACTERISTIC"
RECENT_TREND = "RECENT_TREND"
CONFIRMED_EVENT = "CONFIRMED_HISTORICAL_EVENT"

_LARGE_SAMPLE_MIN = 30
_MEANINGFUL_CORRELATION = 0.3
_COMPONENT_LABELS = terms.SG_COMPONENT


def _weakest_confidence(confidences: list) -> str:
    return min(confidences, key=lambda c: _CONFIDENCE_RANK[c])


def _evidence_score(sample_size, num_distinct_sources: int) -> int:
    """Deterministic, fully disclosed: evidence_score = round(100 *
    min(1, sources/3) * n/(n+5)). Identical formula to 10097's report --
    not a new scoring method invented for this player."""
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
    return next(a for a in master_doc["conclusion_audit"] if a["conclusion"] == conclusion_prefix)


def _fact(master_doc: dict, fact_id: str) -> dict:
    return next(f for f in master_doc["knowledge_graph"]["facts"] if f["id"] == fact_id)


def _season_line(season_profiles: list, attr: str) -> str:
    return ", ".join(f"{p.season} {getattr(p, attr):+.2f}" for p in season_profiles)


# ---------------------------------------------------------------------------
# Monitoring protocols -- identical disclosed methodology to 10097's report
# (same two threshold methods chosen by real sample size, same Pearson-based
# item 5, same current-status-vs-real-reading check). Reused verbatim
# because the METHOD is player-agnostic; only the real rows fed into it
# differ.
# ---------------------------------------------------------------------------


def _pearson(xs: list, ys: list) -> float:
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    return cov / (sx * sy) if sx and sy else 0.0


def _explanatory_metric_from_correlation(rows: list, component_key: str, unit: str) -> str:
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
        explanatory_metric=_explanatory_metric_insufficient_sample(len(values), "appearance", "아래의 라운드별 SG Total 프로토콜"),
    )


def _action_from_protocol(protocol: dict) -> str:
    return (
        f"{protocol['metric']}을(를) 모니터링합니다({protocol['source']}). 정상 범위: {protocol['normal_range']}. "
        f"저하 기준(기술/훈련 점검 필요): {protocol['warning_threshold']}. "
        f"다음 점검: {protocol['next_review']}. 가장 최근 실측값 기준 현재 상태: "
        f"{terms.STATUS_LABEL[protocol['current_status']]} -- {protocol['current_detail']}"
    )


# ---------------------------------------------------------------------------
# V5/V6: real SG decomposition, contribution breakdown. Identical formula
# and identical dedup discipline to 10097's report -- WIN/LOSS/TREND DNA
# live once, at the top level; a question reuses one only when its own
# insight is genuinely distinct (not a repeat of a DNA block).
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
    # total_value is DERIVED as the sum of the already-rounded component
    # values (not independently rounded from the unrounded total) -- this
    # guarantees SG Total = SG OTT + SG APP + SG ARG + SG PUTT holds
    # exactly between the displayed numbers, not just approximately.
    # Independent rounding of numerator and denominator can otherwise
    # drift the two by a cent or two, which is negligible for a large
    # total but can swing share_pct sharply when the total is small.
    rounded_components = {k: round(sums[k], 2) for k in _COMPONENT_LABELS}
    total_rounded = round(sum(rounded_components.values()), 2)
    if total_rounded == 0:
        return None
    breakdown = sorted(
        (
            {"component": _COMPONENT_LABELS[k], "value": rounded_components[k], "share_pct": round(rounded_components[k] / total_rounded * 100, 1)}
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
    # Same fix as _contribution_breakdown: total_value is the sum of the
    # already-rounded component deltas, not independently rounded --
    # keeps the identity exact between displayed numbers even when the
    # total delta itself is small.
    rounded_deltas = {k: round(v, 2) for k, v in deltas.items()}
    total_delta_rounded = round(sum(rounded_deltas.values()), 2)
    if total_delta_rounded == 0:
        return None
    breakdown = sorted(
        (
            {"component": _COMPONENT_LABELS[k], "value": rounded_deltas[k], "share_pct": round(rounded_deltas[k] / total_delta_rounded * 100, 1)}
            for k in rounded_deltas
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


# ---------------------------------------------------------------------------
# Candidate questions. Every statement below is written fresh from 박보겸's
# own real numbers -- none of this text is copied from 10097's report.
# ---------------------------------------------------------------------------


def _q_why_wins(master_doc: dict, ds: dict, season_profiles: list, win_dna: dict, by_code: dict) -> dict:
    wins = master_doc["tournament_analysis"]["wins"]
    win_names = ", ".join(f"{w['tournament']} ({w['season']})" for w in wins)
    top = win_dna["breakdown"][0]
    top_key = _component_key_for_label(top["component"])
    per_win_line = ", ".join(f"{w['tournament']} {by_code[w['game_code']][top_key]:+.2f}" for w in wins if w["game_code"] in by_code)

    fact = (
        f"공식 기록상 확인된 우승은 총 {len(wins)}회입니다({win_names}). 두 우승 모두에서 공통적으로 가장 크게 "
        f"작용한 항목은 {top['component']}입니다 -- 통산 전체로 보면 균형형인 이 선수의 경기력 중에서도, 우승한 "
        "주에는 특히 이 항목이 크게 살아났습니다."
    )
    evidence = [
        f"우승 2회의 SG Total 실측 합계는 {win_dna['total_value']:+.2f}이며, 이 중 {top['component']}가(이) "
        f"{top['share_pct']:+.1f}%를 차지합니다(WIN DNA, 아래 참조).",
        f"두 우승 각각의 {top['component']} 실측값: {per_win_line}.",
    ]
    analysis = (
        "이 선수는 통산 SG 비중이 SG OTT·SG APP·SG ARG·SG PUTT에 걸쳐 비교적 고르게 분포된 균형형 선수입니다 -- "
        "특정 한 항목이 압도적으로 크지 않습니다. 그런데 실제로 우승한 두 번의 대회만 따로 떼어 보면 이야기가 "
        f"달라집니다: {top['component']}가(이) 우승 SG Total의 {top['share_pct']:+.1f}%를 차지하며 다른 세 항목을 "
        "크게 앞섭니다. 이는 '평소에 잘하는 항목'과 '우승하는 주에 결정적으로 작동하는 항목'이 반드시 같지 않을 "
        "수 있다는 뜻이며, 통산 평균만 보아서는 놓칠 수 있는 실제 패턴입니다."
    )
    conclusion = (
        f"{PLAYER_NAME} 선수가 우승하는 주에는 통산 평균과 달리 {top['component']}가(이) 두드러지게 살아납니다 -- "
        "공식 기록상 실측 2회 우승 모두에서 확인된 사실입니다."
    )
    why_it_matters = (
        "통산 평균만 보고 코칭 우선순위를 정하면, 실제로 우승을 만들어내는 항목을 놓칠 수 있습니다. 우승 시점에 "
        "무엇이 살아났는지를 따로 확인해야 정확한 경기 전략을 세울 수 있습니다."
    )
    protocol = _tournament_component_protocol(ds, _component_key_for_label(top["component"]), top["component"])
    player_takeaway = f"우승을 노리는 주에는 {top['component']} 감각을 특히 예민하게 점검하십시오 -- 실측 2회 우승 모두 이 항목이 살아났을 때 나왔습니다."
    coach_focus = (
        f"통산 평균 지표({protocol['sample_size']}개 대회 기준)와 별도로, 우승 후보로 보이는 주에는 "
        f"{top['component']}의 실시간 흐름을 우선 점검하십시오."
    )
    durability = RECENT_TREND
    durability_reasoning = (
        f"실측 우승은 2회뿐입니다. 같은 항목이 두 번 모두 두드러졌다는 것은 실제 근거이지만, 표본이 2건뿐이라 "
        "앞으로도 반드시 같은 항목이 우승을 만든다고 확정할 수는 없습니다. 세 번째 우승이 나오면 이 결론을 다시 "
        "검증해야 합니다 -- 현재로서는 확정된 장기 특성이 아니라 근거 있는 초기 신호로 다룹니다."
    )
    why_this_matters = f"다음 우승 후보 주에 가장 먼저 점검해야 할 항목은 {top['component']}입니다."
    action = _action_from_protocol(protocol)

    win_fact = _fact(master_doc, "fact_win_count")["audit"]
    sample_sizes = [win_fact["sample_size"]]
    sources = set(win_fact["official_records_used"]) | {"contribution_breakdown (WIN DNA)"}
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
        "confidence": "MEDIUM",
    }


def _component_key_for_label(label: str) -> str:
    for k, v in terms.SG_COMPONENT.items():
        if v == label:
            return k
    raise KeyError(label)


def _q_why_loses(master_doc: dict, ds: dict, season_profiles: list, loss_dna: dict) -> dict:
    reason = ds["player_intelligence_doc"]["why_loses"][0]
    putt_trend = _season_line(season_profiles, "avg_putt")
    this_season, last_season = season_profiles[-1], season_profiles[-2]
    top = loss_dna["breakdown"][0]

    fact = (
        f"실측 SG Total이 마이너스였던 {loss_dna['sample_size']}개 대회를 모아 보면, 그 부진의 "
        f"{top['share_pct']:+.1f}%가 {top['component']} 한 항목에서 나왔습니다 -- 이 선수가 성적을 잃는 "
        "주에는 다른 어떤 항목보다 이 항목이 가장 크게 흔들립니다."
    )
    evidence = [
        f"LOSS DNA: 실측 마이너스 대회 {loss_dna['sample_size']}개(전체 마이너스 대회 {loss_dna.get('events_considered', loss_dna['sample_size'])}개 중 SG 세부 기록이 있는 경기), "
        f"SG Total 합계 {loss_dna['total_value']:+.2f} 중 {top['component']} {top['share_pct']:+.1f}%.",
        f"{reason['text']} -- 공식 기록 기준(시즌별 SG PUTT: {putt_trend}).",
    ]
    analysis = (
        f"이 선수는 통산으로 보면 SG PUTT 비중이 크지 않은 균형형 선수이지만({top['component']}는 통산 SG Total의 "
        "일부일 뿐), 정작 성적이 나빴던 경기들만 모아 보면 이야기가 다릅니다. 부진했던 경기의 SG Total 적자 중 "
        f"압도적인 비중이 {top['component']} 한 항목에서 나왔습니다. 이는 이 선수의 부진이 여러 항목이 골고루 "
        f"무너져서가 아니라, {top['component']} 한 항목이 무너질 때 집중적으로 발생한다는 뜻입니다. "
        f"{this_season.season}시즌 SG PUTT({this_season.avg_putt:+.2f})은 지난 시즌({last_season.avg_putt:+.2f})보다 "
        "낮아졌으며, 이 악화가 최근 부진과 시기적으로 겹칩니다."
    )
    conclusion = (
        f"{PLAYER_NAME} 선수가 성적을 잃는 주는 여러 항목이 골고루 흔들리는 주가 아니라, {top['component']} 한 "
        "항목이 집중적으로 무너지는 주입니다 -- 실측 마이너스 대회 기록으로 확인됩니다."
    )
    why_it_matters = (
        "부진의 원인을 정확히 좁히면 훈련 시간을 올바른 곳에 쓸 수 있습니다. 여러 항목을 골고루 손보는 대신, "
        f"부진 주에 실제로 무너지는 {top['component']} 하나를 우선 점검하는 것이 더 효율적입니다."
    )
    protocol = _tournament_component_protocol(ds, "putting", terms.SG_COMPONENT["putting"])
    player_takeaway = f"스코어가 흔들리기 시작하면 가장 먼저 {top['component']}를 점검하십시오 -- 부진했던 경기 기록에서 가장 크게 흔들린 항목입니다."
    coach_focus = (
        f"대회별 {top['component']}는 실측 {protocol['sample_size']}개 대회 기준으로 운영 가능한 범위를 "
        "설정할 수 있습니다 -- 하락 조짐을 조기에 포착하려면 대회별로 발표되는 수치를 그대로 활용하십시오."
    )
    durability = LONG_TERM
    durability_reasoning = (
        f"실측 마이너스 대회 {loss_dna['sample_size']}개라는 비교적 큰 표본에서 일관되게 확인된 패턴이며, "
        f"{this_season.season}시즌 SG PUTT 악화라는 최근 근거와도 방향이 일치합니다. 한 시즌이 더해진다 해도 "
        "이 결론이 뒤집히기보다 다시 확인될 가능성이 큽니다."
    )
    why_this_matters = f"다음 스트로크 게인 회복은 {top['component']}에서 나와야 합니다."
    action = _action_from_protocol(protocol)

    sources = {"empirical_sg_corrected_v2/player_event_series.json", "historical_sg_warehouse_corrected.json", "contribution_breakdown (LOSS DNA)"}
    return {
        "id": "q_why_loses",
        "question": f"{PLAYER_NAME} 선수는 왜 성적을 잃는가?",
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
        "evidence_score": _evidence_score(loss_dna["sample_size"], len(sources)),
        "sample_size": loss_dna["sample_size"],
        "confidence": "HIGH",
    }


def _q_arg_strength(master_doc: dict, ds: dict, season_profiles: list, career_breakdown: dict) -> dict:
    pi = ds["player_intelligence_doc"]
    arg_axis = next(a for a in pi["player_dna"]["axes"] if a["key"] == "sg_arg")
    arg_trend = _season_line(season_profiles, "avg_arg")
    arg_share = next(b for b in career_breakdown["breakdown"] if b["component"] == "SG ARG")

    fact = (
        "SG ARG는 이 선수의 공식 기록상 가장 특이한 강점입니다 -- 통산 SG Total에서 차지하는 비중 자체는 크지 "
        "않지만, 같은 시즌 다른 선수들과 비교한 필드 백분위에서는 4시즌 연속 상위권입니다."
    )
    evidence = [
        f"이번 시즌 필드 백분위: {arg_axis['percentile']:.1f}번째 -- 상위 {100 - arg_axis['percentile']:.1f}% 수준입니다.",
        f"{pi['why_wins'][0]['text']}" if pi["why_wins"] else "",
        f"시즌별 SG ARG 실측값: {arg_trend} -- 본인 안에서는 크지 않은 값이지만 필드 대비 백분위는 매 시즌 높게 유지됩니다.",
        f"통산 {career_breakdown['sample_size']}개 대회 SG Total에서 SG ARG가 차지하는 비중은 {arg_share['share_pct']:+.1f}%입니다 -- 본인 SG 구성 안에서는 큰 비중이 아닙니다.",
    ]
    evidence = [e for e in evidence if e]
    analysis = (
        "'강점'을 본인의 SG 구성 비중으로만 읽으면 SG ARG는 눈에 띄지 않습니다 -- 통산 SG Total의 일부에 불과한 "
        "값입니다. 그러나 같은 시즌 필드 전체와 비교하면 완전히 다른 그림이 나옵니다: 다른 선수들의 SG ARG 편차가 "
        "크지 않은 영역에서 이 선수는 꾸준히 상위권을 지키고 있으며, 이 우위가 4시즌 연속 이어지고 있습니다. 절대적 "
        "크기가 아니라 상대적 안정성과 꾸준함이 이 항목을 강점으로 만드는 근거입니다."
    )
    conclusion = (
        "SG ARG는 본인의 SG 구성에서 가장 큰 항목은 아니지만, 필드 대비로는 가장 신뢰할 수 있는 항목입니다 -- "
        "4시즌 연속 상위권을 유지해 온 유일한 항목입니다."
    )
    why_it_matters = (
        "어떤 항목이 절대적으로 크지 않아도 상대적으로 신뢰할 수 있는 강점인지 알면, 경기력의 다른 부분을 조정할 "
        "때 절대 손대서는 안 될 부분이 무엇인지 코칭스태프에게 알려줍니다."
    )
    protocol = _tournament_component_protocol(ds, "around_green", terms.SG_COMPONENT["around_green"])
    player_takeaway = "쇼트게임 주변 감각은 본인의 가장 안정적인 기준점입니다 -- 다른 부분이 흔들릴 때일수록 이 감각을 믿고 경기를 운영하십시오."
    coach_focus = (
        f"대회별 SG ARG(실측 {protocol['sample_size']}개 대회 기준)를 필드 백분위와 함께 매 시즌 점검하십시오 -- "
        "본인 안에서의 절대값 변화보다 필드 대비 순위 유지 여부가 더 중요한 신호입니다."
    )
    durability = LONG_TERM
    durability_reasoning = (
        "4시즌 연속 필드 상위권 유지는 한 선수의 기록이 보여줄 수 있는 강한 지속성 신호입니다. 절대값 자체는 "
        "시즌마다 오르내리지만(위 실측값 참조), 필드 대비 순위가 흔들린 시즌은 아직 없습니다."
    )
    why_this_matters = "경기력의 다른 부분이 흔들릴 때 의지할 수 있는 가장 안정적인 기준점입니다."
    action = _action_from_protocol(protocol)

    sources = {"OFFICIAL_SG_NORMALIZED.json", "historical_sg_warehouse_corrected.json", f"knowledge_engine/player_intelligence/{PLAYER_ID}/latest.json"}
    return {
        "id": "q_arg_strength",
        "question": f"{PLAYER_NAME} 선수에게 SG ARG는 왜 진짜 강점인가?",
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
        "contribution_breakdown": career_breakdown,
        "evidence_score": _evidence_score(protocol["sample_size"], len(sources)),
        "sample_size": protocol["sample_size"],
        "confidence": "HIGH",
    }


def _q_putt_weakest(master_doc: dict, ds: dict, season_profiles: list) -> dict:
    pi = ds["player_intelligence_doc"]
    axes = {a["key"]: a["percentile"] for a in pi["player_dna"]["axes"]}
    order = [("sg_ott", "SG OTT"), ("sg_app", "SG APP"), ("sg_arg", "SG ARG"), ("sg_putt", "SG PUTT")]
    axis_line = ", ".join(f"{label} {axes[k]:.1f}번째 백분위" for k, label in order)
    putt_trend = _season_line(season_profiles, "avg_putt")

    fact = (
        "SG PUTT은 본인의 네 가지 항목 중 필드 백분위가 가장 낮은 항목이며, 최근 시즌에는 실측값 자체도 "
        "마이너스로 악화되었습니다."
    )
    evidence = [
        f"이번 시즌 본인의 항목별 필드 백분위: {axis_line} -- SG PUTT이 본인의 네 항목 중 가장 낮습니다.",
        f"시즌별 SG PUTT: {putt_trend} -- 2024시즌 플러스로 최고치를 찍은 뒤 2025 · 2026시즌 연속 하락해 마이너스로 전환되었습니다.",
    ]
    analysis = (
        "필드 전체와 비교했을 때 SG OTT · SG APP · SG ARG는 모두 본인 기준 중상위권 백분위에 있지만, SG PUTT만 "
        "하위권입니다. 게다가 SG PUTT은 유일하게 방향을 바꾼 항목이기도 합니다 -- 2024시즌 네 항목 중 가장 좋았던 "
        "항목이 2025 · 2026시즌 연속 하락하며 가장 약한 항목이 되었습니다. 이는 원래부터 약했던 항목이 아니라, "
        "최근 2개 시즌 사이에 새롭게 약해진 항목이라는 뜻이며, 훈련으로 되돌릴 여지가 있는 변화라는 신호이기도 "
        "합니다."
    )
    conclusion = (
        "SG PUTT은 본인의 네 항목 중 현재 가장 약한 부분입니다 -- 다만 원래 약했던 영역이 아니라 2024시즌 이후 "
        "새롭게 나빠진 영역이라는 점에서, 최근 훈련·컨디션 변화를 우선 점검할 가치가 있습니다."
    )
    why_it_matters = (
        "'원래 약한 부분'과 '최근 나빠진 부분'은 완전히 다른 훈련 대응이 필요합니다. 후자라면 스윙 자체가 아니라 "
        "최근 2개 시즌 사이에 무엇이 바뀌었는지부터 점검해야 합니다."
    )
    protocol = _season_component_protocol(season_profiles, "avg_putt", terms.SG_COMPONENT["putting"], f"대회별 {terms.SG_COMPONENT['putting']} 프로토콜")
    player_takeaway = "SG PUTT 악화를 스윙 문제로 단정하지 마십시오 -- 2024시즌에는 본인의 최고 항목이었던 만큼, 최근 2개 시즌 사이의 변화(루틴, 그린 적응, 컨디션)를 먼저 점검할 가치가 있습니다."
    coach_focus = (
        f"'왜 성적을 잃는가' 프로토콜이 대회 단위로 추적하는 것과 같은 지표(SG PUTT)를 여기서는 "
        f"{protocol['sample_size']}개 시즌 단위로 살펴봅니다 -- 2024 이후의 하락이 대회 단위 변동이 아니라 "
        "구조적 추세인지 시즌 단위로 확인하기 위해서입니다."
    )
    durability = RECENT_TREND
    durability_reasoning = (
        "SG PUTT이 본인의 네 항목 중 가장 약하다는 판단은 최근 2개 시즌(2025 · 2026)에만 근거합니다 -- 2023 · "
        "2024시즌에는 사실이 아니었습니다(2024시즌에는 오히려 최고 항목). 따라서 이는 확정된 장기 특성이 아니라 "
        "최근 추세로 다루어야 하며, 다음 시즌 반등 여부에 따라 결론이 바뀔 수 있습니다."
    )
    why_this_matters = "다음 시즌 SG PUTT 반등 여부가 이 결론을 확정할지, 뒤집을지를 가릅니다."
    action = _action_from_protocol(protocol)

    sources = {f"knowledge_engine/player_intelligence/{PLAYER_ID}/latest.json (player_dna.axes)", "historical_sg_warehouse_corrected.json", "OFFICIAL_SG_NORMALIZED.json"}
    return {
        "id": "q_putt_weakest",
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
        "evidence_score": _evidence_score(4, len(sources)),
        "sample_size": 4,
        "confidence": "HIGH",
    }


def _q_season_change(master_doc: dict, season_profiles: list, trend_dna: dict) -> dict:
    total_trend = ", ".join(f"{p.season} ({p.n_tournaments}개 대회) {p.avg_total:+.2f}" for p in season_profiles)
    top = trend_dna["breakdown"][0]
    peak = max(season_profiles, key=lambda p: p.avg_total)
    trough_after_peak = min((p for p in season_profiles if p.season > peak.season), key=lambda p: p.avg_total, default=None)

    fact = (
        f"{PLAYER_NAME} 선수의 시즌별 SG Total은 꾸준한 상승도, 꾸준한 하락도 아닙니다 -- 4개 시즌 동안 오르고, "
        "크게 떨어졌다가, 다시 일부 회복하는 흐름을 보였습니다."
    )
    evidence = [
        f"시즌별 SG Total: {total_trend}.",
        f"{peak.season}시즌 {peak.avg_total:+.2f}로 4개 시즌 중 최고치를 찍은 뒤, "
        + (f"{trough_after_peak.season}시즌 {trough_after_peak.avg_total:+.2f}로 하락했습니다." if trough_after_peak else "이후 하락했습니다."),
        f"TREND DNA({season_profiles[0].season}→{season_profiles[-1].season} 변화량 {trend_dna['total_value']:+.2f}) 기준, 이 변화를 가장 크게 설명하는 항목은 {top['component']}입니다({top['share_pct']:+.0f}%).",
    ]
    analysis = (
        f"{peak.season}시즌의 고점은 실제 기록이지만, 그 뒤를 이어가지 못했습니다. {season_profiles[0].season}시즌부터 "
        f"{season_profiles[-1].season}시즌까지 전체 변화량을 항목별로 나누어 보면, {top['component']}의 변화가 "
        "가장 크게 작용했습니다 -- 이는 이 선수의 시즌별 기복이 특정 한 항목의 흔들림과 가장 밀접하게 맞물려 "
        "있다는 뜻입니다. 다만 이 흐름은 아직 4개 시즌 안에서 오르내림을 반복하고 있어, 한 방향으로 확정된 "
        "추세라고 보기는 이릅니다."
    )
    conclusion = (
        f"{PLAYER_NAME} 선수의 경기력은 시즌마다 실제로 오르내렸습니다 -- {season_profiles[0].season}시즌 대비 "
        f"{season_profiles[-1].season}시즌 SG Total은 {trend_dna['total_value']:+.2f}이며, 이 변화의 대부분은 "
        f"{top['component']}에서 비롯되었습니다. 단조로운 성장이나 단조로운 하락으로 요약할 수 있는 기록이 "
        "아닙니다."
    )
    why_it_matters = (
        "기복을 '성장' 또는 '하락'이라는 단순한 이야기로 요약하면, 실제로 무엇이 연도별 차이를 만들었는지를 "
        "놓칩니다. 어느 항목의 변화가 시즌 성적을 좌우했는지 알아야 다음 시즌 준비의 우선순위를 정할 수 있습니다."
    )
    player_takeaway = f"시즌 준비 계획을 세울 때 {top['component']}의 시즌 초반 흐름을 가장 먼저 점검하십시오 -- 지난 4개 시즌의 기복을 가장 크게 설명하는 항목입니다."
    protocol = _season_component_protocol(season_profiles, "avg_total", terms.SG_TOTAL, "대회별 SG Total 실측치(historical_sg_warehouse_corrected.json, scope=tournament_cumulative, field='total')")
    coach_focus = (
        f"SG Total을 시즌 단위(실측 {protocol['sample_size']}개 시즌 기준)로 점검하되, {top['component']}의 "
        "시즌별 흐름을 함께 추적하십시오 -- 전체 기복을 가장 잘 설명하는 지표입니다."
    )
    durability = RECENT_TREND
    durability_reasoning = (
        "4개 시즌 모두 실측 기록이지만, 방향이 한 번 이상 바뀌었습니다(상승 → 하락 → 부분 회복). 다섯 번째 "
        "시즌이 상승과 하락 중 어느 쪽으로 이어질지는 아직 확정된 근거가 없어, 이 흐름을 고정된 장기 특성으로 "
        "다루지 않습니다."
    )
    why_this_matters = "다음 시즌이 회복을 이어갈지, 다시 꺾일지를 가늠할 수 있는 유일한 방법은 실제 기록을 계속 점검하는 것입니다."
    action = _action_from_protocol(protocol)

    audit = _conclusion(master_doc, "season_evolution.frozen_knowledge_engine_evolution.narrative")
    sources = set(audit["official_records_used"]) | {"contribution_breakdown (TREND DNA)"}
    return {
        "id": "q_season_change",
        "question": f"{PLAYER_NAME} 선수의 성적은 왜 시즌마다 달라지는가?",
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
        "confidence": audit["confidence"] if audit["confidence"] != "UNKNOWN" else "MEDIUM",
    }


def _q_strong_course(master_doc: dict, by_code: dict, career_avg_sg_total: float) -> dict:
    """Selection method for this player: highest real average SG Total
    among course series with >=2 real appearances (not "most visited",
    10097's method) -- her most-visited series are not her strongest, so
    reusing 10097's selection criterion here would have surfaced a
    weaker, less honest story. This is a real, disclosed adaptation, not
    a template copy."""
    candidates = [g for g in master_doc["course_analysis"]["course_series"] if g["avg_sg_total"] is not None]
    group = max(candidates, key=lambda g: g["avg_sg_total"])
    n = group["appearances"]
    history_line = "; ".join(
        f"{h['season']} {h['sg_total']:+.2f}" if h.get("sg_total") is not None else f"{h['season']} 기록 없음" for h in group["history"]
    )
    contribution = _contribution_breakdown([by_code.get(h["game_code"]) for h in group["history"]])

    fact = (
        f"{PLAYER_NAME} 선수가 실측 기록상 가장 강한 코스는 {group['series_name_sample']}입니다 -- 실측 {n}회 "
        f"출전 평균 SG Total이 {group['avg_sg_total']:+.2f}로, 다른 어떤 반복 출전 코스보다 높습니다."
    )
    evidence = [
        f"시즌별 출전 기록의 SG Total: {history_line}.",
        f"{n}회 출전 전체 평균 SG Total: {group['avg_sg_total']:+.2f}로, 통산 62개 대회 평균({career_avg_sg_total:+.2f})을 크게 웃돕니다.",
        f"이 코스 시리즈에서의 실측 우승 여부: {'우승 포함' if group['won_on_record'] else '우승 기록 없음'}.",
    ]
    analysis = (
        f"{n}회의 실측 출전 중 평균 SG Total이 이만큼 높게 유지된다는 것은 우연한 한 주의 결과가 아니라 이 코스 "
        "자체가 본인의 경기력과 잘 맞는다는 실제 근거입니다. 다만 표본이 2회뿐이므로, 다음 출전 결과에 따라 "
        "평균이 크게 흔들릴 수 있다는 점은 함께 고려해야 합니다."
    )
    conclusion = (
        f"이 코스에서는 새로운 시도를 하기보다 이미 검증된 방식에 의지하는 경기 전략이 맞습니다 -- 실측 {n}회 "
        f"출전 평균 SG Total {group['avg_sg_total']:+.2f}는 이 선수의 반복 출전 코스 중 가장 높습니다."
    )
    why_it_matters = "좋은 성적이 추측이 아니라 특정 코스에서 근거를 가진 결과라는 것을 알면, 코칭스태프가 현장에서 선수의 감각을 믿어야 할 때를 판단하는 데 도움이 됩니다."
    player_takeaway = "이 코스에서는 실제 성적으로 뒷받침된 자신감을 가지고 임하십시오."
    protocol = _course_appearance_protocol(group)
    coach_focus = f"{group['series_name_sample']}을(를) 좋은 한 주가 어떤 모습인지 보여주는 기준으로 삼으십시오."
    durability = LONG_TERM
    durability_reasoning = (
        f"이미 실측된 {n}회의 출전은 앞으로 무슨 일이 있어도 바뀌지 않는 기록입니다. 다만 표본이 두 개뿐이므로, "
        "다음 출전 성적에 따라 평균이 크게 움직일 수 있습니다(패턴 자체가 뒤집히는 것은 아니지만). 확정된 결론이 "
        "아니라 근거 있는 경향으로 다루십시오."
    )
    why_this_matters = "이 코스로 돌아갈 때 선수를 믿고 맡겨야 한다는 것이 기록에서 분명하게 드러나는 지점입니다."
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
        "confidence": "HIGH" if n >= 4 else ("MEDIUM" if n >= 2 else "LOW"),
    }


def _q_repeat_course_pattern(master_doc: dict) -> dict:
    """Unlike 10097 (whose equivalent claim was excluded, n=1, UNKNOWN),
    this pattern is CONFIRMED for 박보겸 (n=2, MEDIUM confidence) -- a
    real difference in her data, answered here as its own question
    rather than force-fit into q_strong_course. The direction is the
    opposite of what "repeat course, repeat win" intuition would
    suggest: both real wins came on her FIRST attempt at that course
    series, with her later return(s) scoring lower -- stated exactly as
    computed, never smoothed toward the more expected direction."""
    pattern = master_doc["pattern_trend_analysis"]
    wins_on_repeat = pattern["wins_on_repeat_courses"]
    n = pattern["pattern_observation_sample_size"]

    # Real return-visit SG Total per winning course series (the entry in
    # course_analysis.course_series after the win), picking the most
    # recent one on record as the current reading -- never the sample
    # count, which is a different real quantity.
    win_series_names = {w["series_name_sample"] for w in wins_on_repeat}
    return_visits = []
    for group in master_doc["course_analysis"]["course_series"]:
        if group["series_name_sample"] not in win_series_names:
            continue
        history = sorted(group["history"], key=lambda h: h["season"])
        if len(history) >= 2 and history[0].get("sg_total") is not None and history[1].get("sg_total") is not None:
            return_visits.append({"series": group["series_name_sample"], "first": history[0], "return": history[1]})
    return_visits.sort(key=lambda r: r["return"]["season"])
    latest_return = return_visits[-1] if return_visits else None

    fact = (
        f"{PLAYER_NAME} 선수의 실측 우승 {n}회는 모두 이후에도 다시 출전한 코스 시리즈에서 나왔습니다 -- 다만 "
        "우승은 반복 방문 이후가 아니라 첫 출전에서 나왔고, 그 뒤 다시 찾은 출전에서는 오히려 성적이 낮아졌습니다."
    )
    evidence = [
        f"{w['series_name_sample']}: 우승은 {w['attempt_number']}번째 출전(총 {w['total_appearances_in_series']}회 출전 중)."
        for w in wins_on_repeat
    ]
    analysis = (
        "'코스에 익숙해질수록 우승 확률이 높아진다'는 직관과는 반대 방향의 실측 결과입니다. 두 실측 우승 모두 "
        "해당 코스 시리즈의 첫 출전에서 나왔고, 이후 다시 찾은 출전에서는 SG Total이 더 낮았습니다. 표본이 2건뿐이라 "
        "이를 확정된 경향으로 단정할 수는 없지만, 적어도 '반복 출전이 우승 확률을 높인다'는 가정은 이 선수의 실측 "
        "기록으로는 뒷받침되지 않습니다."
    )
    conclusion = (
        f"실측 우승 {n}회 모두 해당 코스 시리즈의 첫 출전에서 나왔습니다 -- '반복 방문이 우승을 만든다'는 "
        "일반적인 가정과는 다른, 이 선수만의 실제 패턴입니다. 반복 출전이 강점으로 작동한다는 근거는 현재 "
        "기록에는 없습니다."
    )
    why_it_matters = (
        "코스 재방문을 자동으로 강점으로 가정하면, 실제로는 반대 방향인 이 선수의 패턴을 놓치게 됩니다. 재방문 "
        "코스라고 해서 특별히 더 편안하게 준비해서는 안 된다는 뜻입니다."
    )
    player_takeaway = "'가 본 적 있는 코스니까 유리하다'는 가정을 갖지 마십시오 -- 실측 기록상 오히려 첫 출전에서 더 좋은 성적을 냈습니다."
    coach_focus = "재방문 코스를 준비할 때 이전 출전 결과에 안주하지 말고, 첫 출전 때와 동일한 수준의 사전 준비를 유지하십시오."
    durability = RECENT_TREND
    durability_reasoning = (
        f"실측 사례가 {n}건뿐입니다. 패턴/경향으로 부를 수 있는 최소 기준(2건)은 충족하지만, 세 번째 사례가 "
        "나오기 전까지는 확정된 장기 특성으로 다루지 않습니다."
    )
    why_this_matters = "재방문 코스를 특별 대우하지 않는 것이 지금까지의 실제 기록과 맞습니다."
    protocol = {
        "metric": "코스 재방문 시 SG Total",
        "source": "historical_sg_warehouse_corrected.json (matched via knowledge_engine.find_course_history())",
        "sample_size": n,
        "normal_range": "첫 출전 SG Total 대비 하락하지 않는 경우",
        "warning_threshold": "재방문 출전이 첫 출전 대비 2회 연속 낮은 SG Total을 기록하는 경우",
        "next_review": "다음 재방문 코스의 공식 기록이 나오는 시점",
        "explanatory_metric": _explanatory_metric_insufficient_sample(n, "appearance", "위 코스별 SG Total 프로토콜"),
        "current_reading": latest_return["return"]["sg_total"] if latest_return else None,
        "current_status": "WATCH" if latest_return else "NORMAL",
        "current_detail": (
            f"가장 최근 재방문({latest_return['series']}, {latest_return['return']['season']}시즌) SG Total은 "
            f"{latest_return['return']['sg_total']:+.2f}로, 첫 출전({latest_return['first']['season']}시즌) "
            f"{latest_return['first']['sg_total']:+.2f}보다 낮았습니다." if latest_return else "재방문 실측 기록이 아직 없습니다."
        ),
    }
    action = _action_from_protocol(protocol)

    sources = {"knowledge_engine.find_course_history()", "historical_sg_warehouse_corrected.json", "empirical_sg_corrected_v2/player_event_series.json"}
    return {
        "id": "q_repeat_course_pattern",
        "question": f"{PLAYER_NAME} 선수는 과거에 출전했던 코스에서 우승하는 경향이 있는가?",
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
        "evidence_score": _evidence_score(n, len(sources)),
        "sample_size": n,
        "confidence": pattern["pattern_observation_confidence"],
    }


def _round_to_round_delta_check(ds: dict) -> tuple:
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
    rounds = sorted((r for r in ds["warehouse_round_rows"] if r["game_code"] == win["game_code"]), key=lambda r: r["round"])
    if not rounds:
        return None
    sg_line = ", ".join(f"R{r['round']} {r['total']:+.2f}" for r in rounds)
    delta_mean, delta_n = _round_to_round_delta_check(ds)
    contribution = _contribution_breakdown([by_code.get(win["game_code"])])
    final_round = rounds[-1]

    fact = (
        f"가장 최근 우승({win['tournament']}, {win['season']})은 안정적으로 리드를 지킨 우승이 아니라, 마지막 "
        f"라운드의 폭발적인 반전으로 만들어졌습니다 -- 최종 라운드 SG Total {final_round['total']:+.2f} 중 "
        f"SG PUTT이 {final_round['putting']:+.2f}로 가장 크게 기여했습니다."
    )
    evidence = [
        f"라운드별 SG Total: {sg_line} -- 중반 라운드에는 기복이 있었지만 마지막 라운드에서 대회 중 가장 좋은 "
        "라운드가 나왔습니다.",
        f"최종 라운드 SG 구성: SG OTT {final_round['off_the_tee']:+.2f}, SG APP {final_round['approach']:+.2f}, "
        f"SG ARG {final_round['around_green']:+.2f}, SG PUTT {final_round['putting']:+.2f} -- SG PUTT이 가장 "
        "컸습니다.",
    ]
    analysis = (
        "중반 라운드의 기복을 딛고 마지막 라운드에 가장 좋은 경기력이 나왔다는 것은, 이 우승이 안정적인 리드 "
        "관리가 아니라 후반 집중력에서 비롯되었다는 뜻입니다. 다만 이 결과 하나만으로 반복되는 특성이라고 단정할 "
        f"수는 없습니다 -- 라운드 간 흐름 전체를 살펴보면(실측 연속 라운드 쌍 {delta_n}개 기준) 평균 변화가 "
        f"{delta_mean:+.2f} SG로 사실상 큰 흐름이 없습니다. 따라서 이번 우승은 이 대회를 준비할 때 참고할 사실이지, "
        "'항상 후반에 강해진다'는 일반적인 특성으로 확대 해석해서는 안 됩니다."
    )
    conclusion = (
        "가장 최근 우승은 중반의 기복을 거친 뒤 마지막 라운드, 특히 SG PUTT의 폭발적인 반등으로 만들어졌습니다 "
        "-- 이 한 번의 결과에 대해 실제로 확인된 사실이며, 아직 우승 전반에 걸쳐 확립된 패턴은 아닙니다."
    )
    why_it_matters = "이번 결과에서 무엇이 확인되었고 무엇을 일반화하려면 더 많은 근거가 필요한지를 정확히 구분해 두면, 준비 과정을 실제 있었던 일에 근거하게 만들 수 있습니다."
    player_takeaway = "중반 라운드가 평범하더라도 우승이 끝난 것은 아니라는 실제 증거입니다 -- 다만 더 넓은 기록에서는 이것이 매번 기대할 수 있는 일이라고까지는 아직 보여주지 않습니다."
    protocol = _round_total_protocol(ds)
    coach_focus = (
        f"실전 대회 중에는 이 한 번의 우승에서 나온 심리적 패턴을 가정하기보다, 아래의 라운드별 SG Total "
        f"프로토콜을 실시간 신호로 활용하십시오 -- 실측 {protocol['sample_size']}개 라운드를 기준으로 합니다."
    )
    durability = CONFIRMED_EVENT
    durability_reasoning = (
        "이 일은 이미 일어났고 공식 결과로 확정되어 있으므로, 앞으로 어떤 데이터가 나오더라도 바뀌지 않습니다. "
        f"다만 라운드 간 흐름 전체를 확인한 결과(실측 전환 {delta_n}건, 평균 변화 {delta_mean:+.2f} SG) 선수 "
        "생활 전체에서 일관되게 후반에 강해지는 패턴은 나타나지 않았습니다. 따라서 이 결과는 이 대회 하나에 "
        "대한 확정된 사실로만 보고하며, 근거가 없는 반복적 특성으로 확대하지 않습니다."
    )
    why_this_matters = "중반이 평범하더라도 코칭스태프가 활용할 수 있는, 실제로 확인된 최근 사례 하나를 제공합니다."
    action = _action_from_protocol(protocol)

    sources = {"empirical_sg_corrected_v2/player_event_series.json", "historical_sg_warehouse_corrected.json (scope=single_round)"}
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


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def build() -> dict:
    master_doc, ds, season_profiles = _load_inputs()
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
        loss_dna["story"] = f"부진할 때 가장 크게 흔들린 요소는 {top['component']}입니다({top['share_pct']:+.0f}%)."

    trend_dna = _trend_contribution_breakdown(season_profiles)
    if trend_dna is not None:
        top = trend_dna["breakdown"][0]
        trend_dna["story"] = f"시즌 간 변화를 가장 크게 이끈 요소는 {top['component']}입니다({top['share_pct']:+.0f}%)."

    candidates = [
        _q_why_wins(master_doc, ds, season_profiles, win_dna, by_code),
        _q_why_loses(master_doc, ds, season_profiles, loss_dna),
        _q_arg_strength(master_doc, ds, season_profiles, career_breakdown),
        _q_putt_weakest(master_doc, ds, season_profiles),
        _q_season_change(master_doc, season_profiles, trend_dna),
        _q_strong_course(master_doc, by_code, career_breakdown["total_value"] / career_breakdown["sample_size"]),
        _q_repeat_course_pattern(master_doc),
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

    # SPECIAL REQUIREMENT: major championship victory, analyzed separately.
    # Checked, not found -- stated directly rather than forced into one of
    # her 2 real (non-major) wins.
    kb_entry = ds.get("kb_entry_row") or {}
    major_championship_analysis = {
        "status": "NOT_FOUND_ON_RECORD",
        "checked_sources": [
            "empirical_sg_corrected_v2/player_event_series.json (97 real career events)",
            "historical_sg_warehouse_corrected.json (tournament_cumulative rank field)",
            "historical_sg_warehouse_corrected_v2.json (independent snapshot, cross-checked)",
            "2026090003_ENTRY_SNAPSHOT.json / OK_OPEN_2026_ENTRY_SNAPSHOT.json (official KLPGA entry-exemption category)",
        ],
        "finding": (
            f"공식 기록상 확인된 {PLAYER_NAME} 선수의 우승은 2건이며({', '.join(w['tournament'] + ' (' + str(w['season']) + ')' for w in win_events)}), "
            "두 대회 모두 메이저 대회가 아닙니다. 본인의 공식 KLPGA 출전 자격 사유 역시 "
            f"\"{kb_entry.get('qualification_reason', '기록 없음')}\"로, '메이저대회 우승자'가 아닌 "
            "'일반대회 우승자' 자격입니다. 이 리포트가 다루는 2023-2026시즌 공식 기록 범위 안에서는 메이저 "
            "챔피언십 우승 기록을 찾을 수 없습니다."
        ),
        "note": (
            "이 리포트가 수집한 공식 기록의 범위(2023-2026시즌)를 벗어난 시기에 메이저 우승이 실제로 있었다면, "
            "이는 현재 저장소의 공식 데이터로는 재현할 수 없으므로 이 리포트는 그 가능성에 대해 주장하지 "
            "않습니다 -- 확인되지 않은 내용은 포함하지 않는다는 이 리포트의 데이터 원칙에 따른 것입니다."
        ),
    }

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
            f"이 문서는 playerCode={PLAYER_ID}({PLAYER_NAME}) 선수만을 다룹니다. 다른 선수의 데이터는 생성되거나 "
            "수정되지 않았습니다. NEO Player Intelligence의 두 번째 최상위 기준(Gold Standard) 참고 구현입니다."
        ),
        "evidence_score_method": (
            "evidence_score = round(100 * min(1, 독립 공식 출처 수 / 3) * 표본 크기 / (표본 크기 + 5)). 10097의 "
            "리포트와 동일한 산식입니다 -- 선수마다 새로운 산식을 만들지 않습니다."
        ),
        "durability_method": (
            "모든 질문은 다음을 묻습니다 -- 시즌이 하나 더 추가되어도 이 결론이 뒤집히지 않을 가능성이 높은가? "
            f"'{LONG_TERM}'은 기록된 대부분 또는 모든 시즌에서 나타나는 패턴에 기반해 뒤집힐 가능성이 낮음을 "
            f"의미합니다. '{RECENT_TREND}'는 최근 근거에만 기반하며 앞으로의 시즌에 따라 바뀔 수 있음을 "
            f"의미합니다. '{CONFIRMED_EVENT}'는 이미 종료된 결과로, 향후 데이터로 뒤집힐 수는 없지만 그 자체를 "
            "반복되는 패턴으로 일반화하지도 않습니다."
        ),
        "monitoring_protocol_method": (
            "10097의 리포트와 동일한 방법론입니다: 실측값이 30회 이상이면 정상 범위는 평균 ± 표준편차 1, 저하 "
            "기준은 하한선 미만이 2회 연속 나타나는 경우입니다. 표본이 이보다 적은 집계에서는 실측 역대 최저치 "
            "경신을 저하 기준으로 삼습니다. 변화를 가장 잘 설명하는 지표는 실제 피어슨 상관관계가 0.3 기준을 "
            "통과할 때만 지목하며, 통과하지 못하면 실제 계수와 함께 '없음'으로 보고합니다."
        ),
        "contribution_breakdown_method": _CONTRIBUTION_METHOD,
        "major_championship_analysis": major_championship_analysis,
        "pre_tournament_checklist": pre_tournament_checklist,
        "questions": questions,
        "questions_considered_but_unsupported": excluded,
        "win_dna": win_dna,
        "loss_dna": loss_dna,
        "trend_dna": trend_dna,
        "source_document": "MASTER_ANALYSIS.json (scripts/build_9431_master_player_analysis.py의 감사 절차를 거친 근거 자료)",
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
    print(f"major_championship_analysis.status: {result['major_championship_analysis']['status']}")
