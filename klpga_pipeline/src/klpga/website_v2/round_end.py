"""Reusable round-end routing and descriptive analytics for NEO.

The module is deliberately data-only: it never changes frozen forecasts and
never turns descriptive observations into causal claims.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Any, Callable, Iterable
from .analytics import classify_hole_score

STAGES = ("PRE", "R1", "R2", "R3", "FINAL")
STORY_QUESTIONS = {
    "R1": "누가 예상보다 달랐나?",
    "R2": "누가 우승 경쟁에 들어왔나?",
    "R3": "마지막 18홀의 우승 경쟁은 어떻게 생겼나?",
    "FINAL": "우승은 어디에서 만들어졌나?",
}


def validate_stage_freshness(*, page_stage: str, component_stage: str,
                             probability_checkpoint: str | None,
                             evidence_stage: str | None,
                             available_checkpoints: Iterable[str]) -> dict:
    """Fail stale stage-aware UI while allowing intentional historical views."""
    page, component = page_stage.upper(), component_stage.upper()
    available = {str(x).upper() for x in available_checkpoints}
    errors = []
    if page != component:
        errors.append("component stage differs from page stage")
    if probability_checkpoint and probability_checkpoint.upper() not in available:
        errors.append("probability checkpoint is unavailable")
    if evidence_stage and evidence_stage.upper() != component:
        errors.append("evidence reference differs from component stage")
    return {"valid": not errors, "page_stage": page, "component_stage": component,
            "probability_checkpoint": probability_checkpoint, "evidence_stage": evidence_stage,
            "errors": errors}


def stage_completeness(rows: Iterable[dict], required: Iterable[str] = ("player_id", "rank")) -> dict:
    rows = list(rows); missing = [field for field in required if any(not row.get(field) for row in rows)]
    ids = [row.get("player_id") for row in rows if row.get("player_id")]
    return {"complete": bool(rows) and not missing and len(ids) == len(set(ids)),
            "rows": len(rows), "missing_fields": missing, "duplicate_player_ids": len(ids)-len(set(ids))}


def classify_stage_route(stage: str, facts: dict | None = None) -> dict:
    stage = stage.upper(); question = STORY_QUESTIONS.get(stage, "대회의 변화는 무엇이었나?")
    return {"stage": stage, "question": question, "fallback": not bool(facts)}


def _detector(name: str, stage: str, players: list[str], trigger: dict, metrics: dict, confidence: str = "descriptive") -> dict:
    return {"detector": name, "stage": stage, "players": players, "trigger": trigger,
            "metrics": metrics, "confidence": confidence}


def detect_probability_surge(series: dict[str, list[dict]], stage: str = "R3") -> list[dict]:
    found=[]
    for player, points in series.items():
        values=[(p["stage"], p["value"]) for p in points if p.get("value") is not None]
        for (before, a), (after, b) in zip(values, values[1:]):
            if b is not None and a is not None and b-a >= 5:
                found.append(_detector("PROBABILITY_SURGE", stage, [player], {"from": before, "to": after}, {"change_pp": round(b-a, 3)}))
    return found


def detect_same_score_divergence(rows: Iterable[dict], score_key: str = "score_to_par", probability_key: str = "win") -> dict | None:
    groups=defaultdict(list)
    for row in rows:
        if row.get(score_key) is not None and row.get(probability_key) is not None: groups[row[score_key]].append(row)
    group=max(groups.values(), key=lambda x: max(r[probability_key] for r in x)-min(r[probability_key] for r in x), default=[])
    if len(group)<2: return None
    values=[r[probability_key] for r in group]
    return _detector("SAME_SCORE_DIVERGENCE", "R3", [r["player"] for r in group], {"score": group[0][score_key]}, {"probability_range": round(max(values)-min(values),3)})


def field_relative_hole_value(records: Iterable[dict], player_id: str, holes: Iterable[int] | None = None) -> list[dict]:
    """Compute strokes minus field mean; this is explicitly not Strokes Gained."""
    selected={int(h) for h in holes} if holes is not None else None
    groups=defaultdict(list)
    for row in records:
        if selected is None or int(row["hole"]) in selected: groups[int(row["hole"])].append(row)
    output=[]
    for hole, rows in sorted(groups.items()):
        target=[r for r in rows if str(r.get("player_id"))==str(player_id)]
        if not target: continue
        field_avg=mean(float(r["strokes"]) for r in rows); par=mean(float(r["par"]) for r in rows)
        output.append({"hole": hole, "par": par, "field_average_strokes": round(field_avg,3),
                       "field_average_to_par": round(field_avg-par,3),
                       "birdie_or_better_rate": round(sum(int(r["strokes"])-int(r["par"])<=-1 for r in rows)/len(rows),3),
                       "bogey_or_worse_rate": round(sum(int(r["strokes"])-int(r["par"])>=1 for r in rows)/len(rows),3),
                       "player_strokes": target[0]["strokes"], "player_to_par": target[0]["relative_to_par"],
                       "player_minus_field_average": round(float(target[0]["strokes"])-field_avg,3),
                       "metric": "field_relative_hole_value"})
    return output


def breakaway_timeline(records: Iterable[dict], *, players: Iterable[str], target_player: str, round_number: int = 4) -> list[dict]:
    """Describe a final-round starting group after every hole."""
    names=set(players); rows=[r for r in records if r.get("player") in names and int(r.get("round",0))==round_number]
    by_player=defaultdict(dict)
    for row in rows: by_player[row["player"]][int(row["hole"])] = int(row["relative_to_par"])
    cumulative={p:0 for p in names}; timeline=[]; sole_lead_seen=False
    for hole in range(1,19):
        for p in names: cumulative[p]+=by_player[p].get(hole,0)
        leader_score=min(cumulative.values()); leaders=sorted(p for p,v in cumulative.items() if v==leader_score)
        target=cumulative.get(target_player); challengers=sorted((v,p) for p,v in cumulative.items() if p!=target_player)
        nearest=challengers[0] if challengers else (None,None)
        if len(leaders)==1: sole_lead_seen=True
        timeline.append({"hole":hole,"cumulative_relative_to_par":dict(sorted(cumulative.items())),
                         "leader_score":leader_score,"leader_names":leaders,
                         "target_margin_vs_leader":None if target is None else target-leader_score,
                         "target_margin_vs_nearest_challenger":None if nearest[0] is None else nearest[0]-target,
                         "nearest_challenger":nearest[1],"sole_lead_seen":sole_lead_seen})
    return timeline


def separation_source(*, winner_final: float, field_final: float, challenger_final: float,
                      winner_baseline: float, challenger_baseline: float) -> dict:
    return {"winner_vs_field": round(winner_final-field_final,3),
            "winner_vs_closest_challenger": round(winner_final-challenger_final,3),
            "leader_group_vs_field": None, "winner_change_vs_baseline": round(winner_final-winner_baseline,3),
            "competitor_change_vs_baseline": round(challenger_final-challenger_baseline,3),
            "interpretation": "descriptive_components_only", "confidence": "descriptive"}

def compare_player_rounds(records: Iterable[dict], winner: str, challenger: str, round_number: int = 4) -> dict:
    """Descriptive score-composition comparison; never infers causality."""
    def summary(player: str) -> dict:
        rows=[r for r in records if r.get("player")==player and int(r.get("round",0))==round_number]
        counts=Counter(classify_hole_score(int(r["strokes"]), int(r["par"])) for r in rows)
        return {"score":sum(int(r["strokes"]) for r in rows), "birdies":counts["Birdie"], "bogeys":counts["Bogey"]}
    a,b=summary(winner),summary(challenger)
    return {"comparison_scope":f"{winner} vs {challenger} R{round_number}","winner_birdies":a["birdies"],"challenger_birdies":b["birdies"],"winner_bogeys":a["bogeys"],"challenger_bogeys":b["bogeys"],"score_difference":b["score"]-a["score"],"interpretation":"descriptive; no field-wide causal generalization"}


def build_story_object(*, story_id: str, stage: str, players: list[str], trigger: dict,
                       verified_facts: list[dict], metrics: dict, source_scope: str,
                       interpretation: list[str], visual_spec: dict, deep_dive_trigger: str,
                       content_priority: str = "primary") -> dict:
    return {"story_id":story_id,"stage":stage,"question":STORY_QUESTIONS.get(stage,"대회의 변화는 무엇이었나?"),
            "players":players,"trigger":trigger,"verified_facts":verified_facts,"metrics":metrics,
            "source_scope":source_scope,"interpretation":interpretation,"confidence":"verified/descriptive",
            "beginner_copy":interpretation[0] if interpretation else "검증된 숫자로 대회의 흐름을 확인합니다.",
            "expert_copy":interpretation,"visual_spec":visual_spec,"deep_dive_trigger":deep_dive_trigger,
            "content_priority":content_priority,"data_vs_interpretation":"separate"}


def build_infographic_story(story: dict, *, tournament: str, headline: str, visual_constraints: list[str]) -> dict:
    return {"story_id":story["story_id"],"tournament":tournament,"stage":story["stage"],"question":story["question"],
            "headline":headline,"verified_numbers":story["metrics"],"verified_events":story["verified_facts"],
            "player_names":story["players"],"timeline":story["visual_spec"].get("timeline",[]),"comparisons":story["visual_spec"].get("comparisons",[]),
            "allowed_interpretations":story["interpretation"],"forbidden_claims":["causal claims without evidence","unsupported shot/weather details"],
            "source_ledger":[story["source_scope"]],"visual_priority":story["content_priority"],"beginner_message":story["beginner_copy"],
            "expert_detail":story["expert_copy"],"required_labels":story["visual_spec"].get("required_labels",[]),"public_language":"Korean-first",
            "visual_constraints":visual_constraints,"do_not_invent":True}


ALLOWED_CLAIM_TYPES={"VERIFIED_DATA","VERIFIED_CONTEXT","NEO_INTERPRETATION","DECORATIVE_NON_FACTUAL","UNSUPPORTED"}
EVIDENCE_PRECEDENCE=("protected_frozen_evidence","canonical_validated_official","verified_official_external","verified_context","agent_analysis","generated_copy_visual")


def validate_evidence_precedence(*, protected_value: float, candidate_values: Iterable[dict]) -> dict:
    """Reject lower-precedence analytical/visual values that conflict with frozen evidence."""
    conflicts=[]
    for candidate in candidate_values:
        value=candidate.get("value")
        if value is None: continue
        if abs(float(value)-float(protected_value)) > 1e-9:
            conflicts.append({"source":candidate.get("source","unknown"),"value":value,"protected":protected_value})
    return {"valid":not conflicts,"protected_value":protected_value,"conflicts":conflicts,"precedence":EVIDENCE_PRECEDENCE}

def validate_completion_gate(*, official_status: str, playoff_resolved: bool = True,
                            hole_completion_known: bool = True) -> dict:
    """Zero-touch safety gate: calendar dates never imply a complete round."""
    errors=[]
    if official_status.upper() == "PLAYOFF" and not playoff_resolved:
        errors.append("playoff result unresolved")
    if not hole_completion_known:
        errors.append("hole completion state unknown (weather/suspension)")
    return {"valid": not errors, "errors": errors}

def _empty_detector(name: str, stage: str, context: dict) -> dict:
    return _detector(name, stage, [], {"available": False}, {}, "insufficient_data")

def detect_streak(context: dict, stage: str = "FINAL") -> dict:
    return _empty_detector("STREAK", stage, context)
def detect_breakaway(context: dict, stage: str = "FINAL") -> dict:
    return _empty_detector("BREAKAWAY", stage, context)
def detect_response(context: dict, stage: str = "FINAL") -> dict:
    return _empty_detector("RESPONSE", stage, context)
def detect_winner_acceleration(context: dict, stage: str = "FINAL") -> dict:
    return _empty_detector("WINNER_ACCELERATION", stage, context)

DETECTOR_REGISTRY = {
    "STREAK": detect_streak,
    "SAME_SCORE_DIVERGENCE": detect_same_score_divergence,
    "PROBABILITY_SURGE": detect_probability_surge,
    "BREAKAWAY": detect_breakaway,
    "RESPONSE": detect_response,
    "WINNER_ACCELERATION": detect_winner_acceleration,
}


def validate_visual_claims(claims: Iterable[dict]) -> dict:
    errors=[]
    for claim in claims:
        if claim.get("type") not in ALLOWED_CLAIM_TYPES: errors.append("unknown claim type")
        if claim.get("type") == "UNSUPPORTED" and claim.get("factual",True): errors.append(claim.get("text","unsupported factual visual"))
    return {"valid":not errors,"errors":errors}


class RoundEndOrchestrator:
    """Deterministic pipeline hook; callbacks keep collection/publish ownership external."""
    def __init__(self, *, ingest: Callable[[str], dict], freeze: Callable[[str,dict],dict], analyze: Callable[[str,dict],dict], accept: Callable[[str,dict],dict]):
        self.ingest, self.freeze, self.analyze, self.accept = ingest, freeze, analyze, accept

    def run(self, stage: str) -> dict:
        stage=stage.upper(); raw=self.ingest(stage); gate=raw.get("completeness",{})
        if raw.get("identity_conflict") or raw.get("rank_conflict") or raw.get("evidence_conflict"):
            raise ValueError("core integrity gate failed")
        frozen=self.freeze(stage,raw); analytics=self.analyze(stage,frozen); accepted=self.accept(stage,analytics)
        return {"state":"PUBLISH_GATE_READY" if accepted.get("valid",False) else "ACCEPTANCE_FAILED",
                "stage":stage,"official_data":raw,"snapshot":frozen,"analytics":analytics,"acceptance":accepted,
                "lanes":{"fast":"ready","deep":"partial" if raw.get("deep_partial") else "ready"},"completeness":gate}
