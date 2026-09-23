"""NEO Knowledge Engine orchestrator.

Loads verified statistics from the pipeline's own source-of-truth files,
computes evidence, and applies knowledge_rules.py to produce traceable
player intelligence: player type, why-she-wins, why-she-loses, evolution,
and if-today scenarios.

Never invents a statistic or a formula. Every generated sentence carries
one or more Citation(source, field_path, value) pointing back to the
exact input that produced it.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from klpga.tournament_context import CONTENT_DIR

from . import knowledge_rules as rules

WAREHOUSE_FILE = "historical_sg_warehouse_corrected.json"
SG_FIELD_FILE = "OFFICIAL_SG_NORMALIZED.json"
PROFILE_FIELD_FILE = "OFFICIAL_PROFILE_NORMALIZED.json"
UNIFIED_FIELD_FILE = "OFFICIAL_PLAYER_UNIFIED_SNAPSHOT.json"
PLAYER_INTELLIGENCE_DIR = CONTENT_DIR / "knowledge_engine" / "player_intelligence"

MAX_REASONS = 3
MAX_SEASONS_IN_EVOLUTION = 4
MAX_SCENARIOS = 3

LOWER_IS_BETTER = {"average_score", "average_putts"}

SG_FIELD_KEY_MAP = {
    "sg_total": "official_sg_total",
    "sg_ott": "official_sg_ott",
    "sg_app": "official_sg_app",
    "sg_arg": "official_sg_arg",
    "sg_putt": "official_sg_putt",
}

PROFILE_FIELD_KEYS = (
    "average_score",
    "average_putts",
    "birdie_rate",
    "gir_rate",
    "par_save_rate",
    "par_break_rate",
    "recovery_rate",
)

SEASON_COMPONENT_SOURCE_KEYS = {
    "avg_total": "total",
    "avg_ott": "off_the_tee",
    "avg_app": "approach",
    "avg_arg": "around_green",
    "avg_putt": "putting",
}

FIELD_KEY_BY_COMPONENT = {
    "avg_ott": "sg_ott",
    "avg_app": "sg_app",
    "avg_arg": "sg_arg",
    "avg_putt": "sg_putt",
}


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_warehouse() -> dict:
    return _load_json(CONTENT_DIR / WAREHOUSE_FILE)


def load_sg_field() -> dict:
    return _load_json(CONTENT_DIR / SG_FIELD_FILE)


def load_profile_field() -> dict:
    return _load_json(CONTENT_DIR / PROFILE_FIELD_FILE)


def load_unified_field() -> dict:
    return _load_json(CONTENT_DIR / UNIFIED_FIELD_FILE)


def load_player_intelligence_doc(player_id: str) -> Optional[dict]:
    path = PLAYER_INTELLIGENCE_DIR / str(player_id) / "latest.json"
    if not path.exists():
        return None
    return _load_json(path)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SeasonProfile:
    season: int
    n_tournaments: int
    avg_total: Optional[float]
    avg_ott: Optional[float]
    avg_app: Optional[float]
    avg_arg: Optional[float]
    avg_putt: Optional[float]

    def _components(self) -> dict:
        return {
            k: v
            for k, v in {
                "avg_ott": self.avg_ott,
                "avg_app": self.avg_app,
                "avg_arg": self.avg_arg,
                "avg_putt": self.avg_putt,
            }.items()
            if v is not None
        }

    @property
    def strongest_component(self) -> Optional[str]:
        comps = self._components()
        return max(comps, key=comps.get) if comps else None

    @property
    def weakest_component(self) -> Optional[str]:
        comps = self._components()
        return min(comps, key=comps.get) if comps else None


@dataclass(frozen=True)
class Evidence:
    player_id: str
    player_name: str
    season_profiles: list
    current_season: Optional[int]
    current_season_components: dict
    current_season_rate_stats: dict
    field_percentiles: dict
    recent_5_sg: Optional[float]
    recent_10_sg: Optional[float]
    long_term_sg: Optional[float]
    volatility: Optional[float]
    sample_count: int
    course_history: list
    career_avg_total_sg: Optional[float]
    sources: tuple


@dataclass(frozen=True)
class Reason:
    text: str
    citations: tuple = ()


@dataclass(frozen=True)
class PlayerTypeResult:
    key: str
    label_ko: str
    label_en: str
    evidence_text: str
    citations: tuple = ()


@dataclass(frozen=True)
class SeasonEvolutionStep:
    season: int
    avg_total: Optional[float]
    delta_from_prev: Optional[float]
    strongest_component: Optional[str]
    weakest_component: Optional[str]


@dataclass(frozen=True)
class EvolutionResult:
    status: str
    steps: tuple
    narrative: str
    citations: tuple = ()


@dataclass(frozen=True)
class Scenario:
    condition: str
    observed: str
    citations: tuple = ()


@dataclass(frozen=True)
class PlayerIntelligence:
    player_id: str
    player_name: str
    player_type: PlayerTypeResult
    why_wins: tuple
    why_loses: tuple
    evolution: EvolutionResult
    if_today: tuple
    sources: tuple
    generated_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mean(values):
    return sum(values) / len(values) if values else None


def _stdev(values):
    return statistics.pstdev(values) if len(values) >= 2 else None


def field_percentile(value: float, population, lower_is_better: bool = False) -> Optional[float]:
    """% of the population this value beats. The value's own row stays in
    the population (mirrors a real player's row being part of the real
    field)."""
    population = list(population)
    if value is None or not population:
        return None
    n = len(population)
    if lower_is_better:
        beaten = sum(1 for v in population if v >= value)
    else:
        beaten = sum(1 for v in population if v <= value)
    return 100.0 * beaten / n


def compute_field_percentiles(player_id: str, sg_doc: dict, profile_doc: dict) -> dict:
    result = {}

    sg_records = sg_doc.get("records", [])
    player_sg = next((r for r in sg_records if r.get("playerCode") == player_id), None)
    if player_sg is not None:
        for out_key, src_key in SG_FIELD_KEY_MAP.items():
            value = player_sg.get(src_key)
            if value is None:
                continue
            population = [r[src_key] for r in sg_records if r.get(src_key) is not None]
            result[out_key] = field_percentile(value, population)

    profile_records = profile_doc.get("records", [])
    player_profile = next((r for r in profile_records if r.get("playerCode") == player_id), None)
    if player_profile is not None:
        for key in PROFILE_FIELD_KEYS:
            value = player_profile.get(key)
            if value is None:
                continue
            population = [r[key] for r in profile_records if r.get(key) is not None]
            result[key] = field_percentile(value, population, lower_is_better=key in LOWER_IS_BETTER)

    return result


def _player_tournament_rows(player_id: str, warehouse_doc: dict) -> list:
    return [
        r
        for r in warehouse_doc.get("records", [])
        if r.get("player_id") == player_id
        and r.get("scope") == "tournament_cumulative"
        and r.get("identity_state") == "RETAINED"
    ]


def _sorted_player_rows(player_id: str, warehouse_doc: dict) -> list:
    rows = _player_tournament_rows(player_id, warehouse_doc)
    return sorted(rows, key=lambda r: (r.get("season") or 0, r.get("game_code") or ""))


def compute_season_profiles(player_id: str, warehouse_doc: dict, max_seasons: int = MAX_SEASONS_IN_EVOLUTION) -> list:
    rows = _player_tournament_rows(player_id, warehouse_doc)
    by_season: dict = {}
    for r in rows:
        season = r.get("season")
        if season is None:
            continue
        by_season.setdefault(season, []).append(r)

    profiles = []
    for season in sorted(by_season.keys()):
        srows = by_season[season]

        def _avg(src_key):
            values = [r[src_key] for r in srows if r.get(src_key) is not None]
            return _mean(values)

        profiles.append(
            SeasonProfile(
                season=season,
                n_tournaments=len(srows),
                avg_total=_avg(SEASON_COMPONENT_SOURCE_KEYS["avg_total"]),
                avg_ott=_avg(SEASON_COMPONENT_SOURCE_KEYS["avg_ott"]),
                avg_app=_avg(SEASON_COMPONENT_SOURCE_KEYS["avg_app"]),
                avg_arg=_avg(SEASON_COMPONENT_SOURCE_KEYS["avg_arg"]),
                avg_putt=_avg(SEASON_COMPONENT_SOURCE_KEYS["avg_putt"]),
            )
        )
    return profiles[-max_seasons:]


def compute_career_avg_total_sg(player_id: str, warehouse_doc: dict) -> Optional[float]:
    rows = _player_tournament_rows(player_id, warehouse_doc)
    return _mean([r["total"] for r in rows if r.get("total") is not None])


def _tokenize_tournament_name(name: Optional[str]) -> set:
    if not name:
        return set()
    tokens = set(name.replace("·", " ").split())
    return {t for t in tokens if t not in rules.GENERIC_TOURNAMENT_WORDS}


def find_course_history(
    player_id: str,
    warehouse_doc: dict,
    current_tournament_name: Optional[str],
    overlap_threshold: float = rules.COURSE_SERIES_OVERLAP_THRESHOLD,
) -> list:
    current_tokens = _tokenize_tournament_name(current_tournament_name)
    if not current_tokens:
        return []

    rows = _player_tournament_rows(player_id, warehouse_doc)
    by_game: dict = {}
    for r in rows:
        game_code = r.get("game_code")
        tname = r.get("tournament")
        if not game_code or not tname:
            continue
        tokens = _tokenize_tournament_name(tname)
        if not tokens:
            continue
        overlap = len(tokens & current_tokens) / len(tokens | current_tokens)
        if overlap >= overlap_threshold:
            by_game[game_code] = r

    history = [
        {
            "game_code": gc,
            "tournament": r.get("tournament"),
            "season": r.get("season"),
            "sg_total": r.get("total"),
        }
        for gc, r in by_game.items()
    ]
    history.sort(key=lambda h: (h.get("season") or 0, h["game_code"]))
    return history


def build_evidence(player_id: str, tournament_context: Optional[dict] = None) -> Evidence:
    warehouse_doc = load_warehouse()
    sg_doc = load_sg_field()
    profile_doc = load_profile_field()
    unified_doc = load_unified_field()

    player_name = None
    for r in warehouse_doc.get("records", []):
        if r.get("player_id") == player_id:
            player_name = r.get("player")
            break
    if player_name is None:
        for r in unified_doc.get("records", []):
            if r.get("player_code") == player_id:
                player_name = r.get("player_name")
                break

    season_profiles = compute_season_profiles(player_id, warehouse_doc)
    field_percentiles = compute_field_percentiles(player_id, sg_doc, profile_doc)

    sorted_rows = _sorted_player_rows(player_id, warehouse_doc)
    recent_5 = sorted_rows[-5:]
    recent_10 = sorted_rows[-10:]
    recent_5_sg = _mean([r["total"] for r in recent_5 if r.get("total") is not None])
    recent_10_sg = _mean([r["total"] for r in recent_10 if r.get("total") is not None])
    volatility = _stdev([r["total"] for r in recent_10 if r.get("total") is not None])

    long_term_sg = compute_career_avg_total_sg(player_id, warehouse_doc)

    current_season_rate_stats = {}
    unified_row = next((r for r in unified_doc.get("records", []) if r.get("player_code") == player_id), None)
    if unified_row is not None:
        for key in PROFILE_FIELD_KEYS:
            if unified_row.get(key) is not None:
                current_season_rate_stats[key] = unified_row[key]

    tournament_name = (tournament_context or {}).get("tournament_name")
    course_history = find_course_history(player_id, warehouse_doc, tournament_name)

    current_season = season_profiles[-1].season if season_profiles else None
    current_season_components = (
        {
            "avg_total": season_profiles[-1].avg_total,
            "avg_ott": season_profiles[-1].avg_ott,
            "avg_app": season_profiles[-1].avg_app,
            "avg_arg": season_profiles[-1].avg_arg,
            "avg_putt": season_profiles[-1].avg_putt,
        }
        if season_profiles
        else {}
    )

    return Evidence(
        player_id=player_id,
        player_name=player_name or player_id,
        season_profiles=season_profiles,
        current_season=current_season,
        current_season_components=current_season_components,
        current_season_rate_stats=current_season_rate_stats,
        field_percentiles=field_percentiles,
        recent_5_sg=recent_5_sg,
        recent_10_sg=recent_10_sg,
        long_term_sg=long_term_sg,
        volatility=volatility,
        sample_count=len(sorted_rows),
        course_history=course_history,
        career_avg_total_sg=long_term_sg,
        sources=(WAREHOUSE_FILE, SG_FIELD_FILE, PROFILE_FIELD_FILE, UNIFIED_FIELD_FILE),
    )


# ---------------------------------------------------------------------------
# Player type classification
# ---------------------------------------------------------------------------

_PLAYER_TYPE_FIELD_KEYS = {
    "precision_ball_striker": ("sg_app", "sg_ott"),
    "recovery_specialist": ("sg_arg", "recovery_rate"),
    "birdie_hunter": ("sg_putt", "birdie_rate"),
    "stable_par_saver": ("par_save_rate",),
    "balanced": (),
}

_FIELD_SOURCE_BY_KEY = {
    "sg_total": SG_FIELD_FILE,
    "sg_ott": SG_FIELD_FILE,
    "sg_app": SG_FIELD_FILE,
    "sg_arg": SG_FIELD_FILE,
    "sg_putt": SG_FIELD_FILE,
}


def _field_source(key: str) -> str:
    return _FIELD_SOURCE_BY_KEY.get(key, PROFILE_FIELD_FILE)


def _player_type_citations(key: str, evidence: Evidence) -> tuple:
    citations = []
    for field_key in _PLAYER_TYPE_FIELD_KEYS.get(key, ()):
        pctl = evidence.field_percentiles.get(field_key)
        if pctl is not None:
            citations.append(rules.Citation(source=_field_source(field_key), field_path=field_key, value=pctl))
    return tuple(citations)


def _player_type_evidence_text(key: str, evidence: Evidence) -> str:
    p = evidence.field_percentiles
    if key == "precision_ball_striker":
        return f"SG Approach {rules.pctl_phrase(p['sg_app'])}, SG Off-the-Tee {rules.pctl_phrase(p['sg_ott'])} 수준입니다."
    if key == "recovery_specialist":
        return f"SG Around-the-Green {rules.pctl_phrase(p['sg_arg'])}, 리커버리율 {rules.pctl_phrase(p['recovery_rate'])} 수준입니다."
    if key == "birdie_hunter":
        return f"SG Putting {rules.pctl_phrase(p['sg_putt'])}, 버디율 {rules.pctl_phrase(p['birdie_rate'])} 수준입니다."
    if key == "stable_par_saver":
        return f"파세이브율 {rules.pctl_phrase(p['par_save_rate'])} 수준으로 변동성이 낮습니다."
    return "특정 강점 조합보다는 여러 지표가 고르게 분포된 균형형 선수입니다."


def classify_player_type(evidence: Evidence) -> PlayerTypeResult:
    for rule in rules.PLAYER_TYPE_RULES:
        if rule.test(evidence):
            return PlayerTypeResult(
                key=rule.key,
                label_ko=rule.label_ko,
                label_en=rule.label_en,
                evidence_text=_player_type_evidence_text(rule.key, evidence),
                citations=_player_type_citations(rule.key, evidence),
            )
    raise RuntimeError("no player type rule matched (balanced fallback should always match)")


# ---------------------------------------------------------------------------
# Why wins / why loses
# ---------------------------------------------------------------------------


def _dedupe_by_metric(results: list) -> list:
    best_by_key = {}
    for r in results:
        existing = best_by_key.get(r.key)
        if existing is None or r.priority > existing.priority:
            best_by_key[r.key] = r
    return list(best_by_key.values())


def generate_why_wins(evidence: Evidence, max_reasons: int = MAX_REASONS) -> tuple:
    results = []
    for rule in rules.WIN_REASON_RULES:
        results.extend(rule.test(evidence))
    results = _dedupe_by_metric(results)
    results.sort(key=lambda r: -r.priority)
    return tuple(Reason(text=r.text, citations=r.citations) for r in results[:max_reasons])


def generate_why_loses(evidence: Evidence, max_reasons: int = MAX_REASONS) -> tuple:
    results = []
    for rule in rules.LOSE_REASON_RULES:
        results.extend(rule.test(evidence))
    results = _dedupe_by_metric(results)
    results.sort(key=lambda r: -r.priority)
    return tuple(Reason(text=r.text, citations=r.citations) for r in results[:max_reasons])


# ---------------------------------------------------------------------------
# Evolution
# ---------------------------------------------------------------------------


def generate_evolution(evidence: Evidence) -> EvolutionResult:
    profiles = evidence.season_profiles
    if len(profiles) < 2:
        return EvolutionResult(status="INSUFFICIENT_SAMPLE", steps=(), narrative="4시즌 추이를 판단하기에 시즌 데이터가 부족합니다.")

    steps = []
    citations = []
    prev_total = None
    for sp in profiles:
        delta = None if prev_total is None or sp.avg_total is None else sp.avg_total - prev_total
        steps.append(
            SeasonEvolutionStep(
                season=sp.season,
                avg_total=sp.avg_total,
                delta_from_prev=delta,
                strongest_component=sp.strongest_component,
                weakest_component=sp.weakest_component,
            )
        )
        if sp.avg_total is not None:
            citations.append(
                rules.Citation(source=WAREHOUSE_FILE, field_path=f"seasons[{sp.season}].avg_total", value=sp.avg_total)
            )
        prev_total = sp.avg_total

    first_valid = next((s for s in steps if s.avg_total is not None), None)
    last_valid = next((s for s in reversed(steps) if s.avg_total is not None), None)
    if first_valid is not None and last_valid is not None and first_valid.season != last_valid.season:
        overall_delta = last_valid.avg_total - first_valid.avg_total
        direction = "상승" if overall_delta > 0 else ("하락" if overall_delta < 0 else "유지")
        narrative = (
            f"{first_valid.season}시즌 SG Total {first_valid.avg_total:+.2f}에서 "
            f"{last_valid.season}시즌 {last_valid.avg_total:+.2f}로 {direction} 추세입니다."
        )
    else:
        narrative = "시즌 간 비교 가능한 SG Total 데이터가 충분하지 않습니다."

    return EvolutionResult(status="OK", steps=tuple(steps), narrative=narrative, citations=tuple(citations))


# ---------------------------------------------------------------------------
# If today
# ---------------------------------------------------------------------------


def generate_if_today(evidence: Evidence, max_scenarios: int = MAX_SCENARIOS) -> tuple:
    scenarios = []

    if evidence.course_history:
        positive = [h for h in evidence.course_history if h.get("sg_total") is not None and h["sg_total"] > 0]
        if positive:
            avg_sg = _mean([h["sg_total"] for h in positive])
            tournament_label = positive[-1].get("tournament") or "이 대회"
            citation = rules.Citation(source=WAREHOUSE_FILE, field_path="course_history[]", value=avg_sg)
            scenarios.append(
                Scenario(
                    condition=f"과거 이 대회 시리즈({tournament_label})에 출전한다면",
                    observed=f"과거 {len(positive)}회 출전 평균 SG Total {avg_sg:+.2f}를 기록했습니다.",
                    citations=(citation,),
                )
            )

    if evidence.recent_5_sg is not None and evidence.long_term_sg is not None:
        if evidence.recent_5_sg >= evidence.long_term_sg * rules.RECENT_VS_LONGTERM_MULTIPLE and evidence.recent_5_sg > 0:
            citation = rules.Citation(source=WAREHOUSE_FILE, field_path="recent_5_sg", value=evidence.recent_5_sg)
            scenarios.append(
                Scenario(
                    condition="최근 폼을 그대로 유지한다면",
                    observed=(
                        f"최근 5개 대회 SG Total {evidence.recent_5_sg:+.2f}는 "
                        f"장기 평균 {evidence.long_term_sg:+.2f}을 크게 상회하는 수준입니다."
                    ),
                    citations=(citation,),
                )
            )

    if len(evidence.season_profiles) >= 2:
        prev_sp, cur_sp = evidence.season_profiles[-2], evidence.season_profiles[-1]
        components = ("avg_ott", "avg_app", "avg_arg", "avg_putt")
        for comp in components:
            prev_v, cur_v = getattr(prev_sp, comp), getattr(cur_sp, comp)
            if prev_v is None or cur_v is None:
                continue
            if prev_v < 0 and cur_v - prev_v >= rules.REVERSAL_MIN_IMPROVEMENT_SG and cur_v > 0:
                label = rules.SG_COMPONENT_LABELS[comp]
                citation = rules.Citation(
                    source=WAREHOUSE_FILE, field_path=f"seasons[{cur_sp.season}].{comp}", value=cur_v
                )
                scenarios.append(
                    Scenario(
                        condition=f"{cur_sp.season}시즌의 {label} 반전 흐름이 이어진다면",
                        observed=f"{prev_sp.season}시즌 {prev_v:+.2f}에서 {cur_sp.season}시즌 {cur_v:+.2f}로 개선되었습니다.",
                        citations=(citation,),
                    )
                )
                break

    return tuple(scenarios[:max_scenarios])


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def generate_player_intelligence(player_id: str, tournament_context: Optional[dict] = None) -> PlayerIntelligence:
    evidence = build_evidence(player_id, tournament_context=tournament_context)
    player_type = classify_player_type(evidence)
    why_wins = generate_why_wins(evidence)
    why_loses = generate_why_loses(evidence)
    evolution = generate_evolution(evidence)
    if_today = generate_if_today(evidence)

    return PlayerIntelligence(
        player_id=evidence.player_id,
        player_name=evidence.player_name,
        player_type=player_type,
        why_wins=why_wins,
        why_loses=why_loses,
        evolution=evolution,
        if_today=if_today,
        sources=evidence.sources,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def _citation_to_dict(citation: rules.Citation) -> dict:
    return {"source": citation.source, "field_path": citation.field_path, "value": citation.value}


def _reason_to_dict(reason: Reason) -> dict:
    return {"text": reason.text, "citations": [_citation_to_dict(c) for c in reason.citations]}


def to_json_dict(intel: PlayerIntelligence) -> dict:
    return {
        "player_id": intel.player_id,
        "player_name": intel.player_name,
        "player_type": {
            "key": intel.player_type.key,
            "label_ko": intel.player_type.label_ko,
            "label_en": intel.player_type.label_en,
            "evidence_text": intel.player_type.evidence_text,
            "citations": [_citation_to_dict(c) for c in intel.player_type.citations],
        },
        "why_wins": [_reason_to_dict(r) for r in intel.why_wins],
        "why_loses": [_reason_to_dict(r) for r in intel.why_loses],
        "evolution": {
            "status": intel.evolution.status,
            "narrative": intel.evolution.narrative,
            "steps": [
                {
                    "season": s.season,
                    "avg_total": s.avg_total,
                    "delta_from_prev": s.delta_from_prev,
                    "strongest_component": s.strongest_component,
                    "weakest_component": s.weakest_component,
                }
                for s in intel.evolution.steps
            ],
            "citations": [_citation_to_dict(c) for c in intel.evolution.citations],
        },
        "if_today": [
            {"condition": s.condition, "observed": s.observed, "citations": [_citation_to_dict(c) for c in s.citations]}
            for s in intel.if_today
        ],
        "sources": list(intel.sources),
        "generated_at": intel.generated_at,
    }


def render_text(intel: PlayerIntelligence) -> str:
    lines = [
        f"{intel.player_name} ({intel.player_id})",
        f"PLAYER TYPE: {intel.player_type.label_ko} / {intel.player_type.label_en}",
        f"  {intel.player_type.evidence_text}",
        "",
        "WHY SHE WINS:",
    ]
    for r in intel.why_wins:
        lines.append(f"  - {r.text}")
    if not intel.why_wins:
        lines.append("  (해당 없음)")
    lines.append("")
    lines.append("WHY SHE LOSES:")
    for r in intel.why_loses:
        lines.append(f"  - {r.text}")
    if not intel.why_loses:
        lines.append("  (해당 없음)")
    lines.append("")
    lines.append(f"PLAYER EVOLUTION ({intel.evolution.status}):")
    lines.append(f"  {intel.evolution.narrative}")
    lines.append("")
    lines.append("IF TODAY:")
    for s in intel.if_today:
        lines.append(f"  - {s.condition}: {s.observed}")
    if not intel.if_today:
        lines.append("  (해당 없음)")
    return "\n".join(lines)
