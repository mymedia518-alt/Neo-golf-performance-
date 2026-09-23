"""Tournament DNA Engine (Sprint 4).

Answers "what kind of golfer wins HERE" -- never "who is winning". The
Knowledge Engine, Player Intelligence schema and Generator (Sprints 1-2)
are frozen: this module only reads their already-computed output
(load_player_intelligence_doc, build_evidence, the field-percentile
helper, the course-series token-matching helper, and the frozen
thresholds in knowledge_rules.py) plus real tournament-identity and
hole-by-hole artifacts. It never invents a statistic, a threshold, or a
prediction -- every fact traces back to a real source file, and a
section with no real evidence reports that honestly instead of guessing.

Architecture: Official Data -> Knowledge Engine -> Tournament DNA Engine
-> TournamentDNA.json -> Website. No duplicated logic: course-series
matching reuses knowledge_engine._tokenize_tournament_name, percentile
ranking reuses knowledge_engine.field_percentile, trend thresholds reuse
knowledge_rules.REVERSAL_MIN_IMPROVEMENT_SG, and player-type / axis
percentiles are read straight out of each player's own already-generated
Player Intelligence document.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from klpga.tournament_context import ACTIVE_TOURNAMENT_PATH, CONTENT_DIR, TournamentContext

from . import knowledge_engine as ke
from . import knowledge_rules as rules
from .player_intelligence_generator import players_for_tournament

MAX_BEST_FITS = 5
MAX_WATCH_LIST = 5
MAX_DANGER_HOLES = 3
MAX_OPPORTUNITY_HOLES = 3
MAX_STORY_FACTS = 5
MIN_HOLE_SAMPLE = 3  # rounds needed before a hole's bogey/birdie rate is reported

# axis_key -> (warehouse SG field, player-doc field key, Korean label)
COURSE_DNA_AXES = (
    ("driving", "off_the_tee", "sg_ott", "드라이빙"),
    ("iron", "approach", "sg_app", "아이언"),
    ("recovery", "around_green", "sg_arg", "리커버리"),
    ("putting", "putting", "sg_putt", "퍼팅"),
    ("scoring", "total", "sg_total", "스코어링"),
)
_AXIS_BY_KEY = {key: (src_field, doc_field, label) for key, src_field, doc_field, label in COURSE_DNA_AXES}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TournamentIdentity:
    game_code: str
    tournament_name: str
    venue: Optional[str]
    par: Optional[int]
    holes: Optional[int]
    purse: Optional[int]
    cut_after_round: Optional[int]
    field_size: Optional[int]
    sources: tuple


@dataclass(frozen=True)
class CourseDNAAxis:
    key: str
    label: str
    avg_sg: float
    percentile: float


@dataclass(frozen=True)
class CourseDNA:
    axes: tuple
    sample_events: int
    matched_game_codes: tuple


@dataclass(frozen=True)
class WinningProfileItem:
    key: str
    label: str
    threshold_sg: float
    sample_size: int


@dataclass(frozen=True)
class FieldCompositionEntry:
    key: str
    label: str
    count: int


@dataclass(frozen=True)
class BestFit:
    player_id: str
    player_name: str
    axis: str
    axis_label: str
    percentile: float
    why: str


@dataclass(frozen=True)
class HoleStat:
    hole: int
    par: Optional[int]
    sample: int
    bogey_rate: float
    birdie_rate: float
    difficulty_stars: int


@dataclass(frozen=True)
class WatchListEntry:
    player_id: str
    player_name: str
    component_label: str
    direction: str  # "개선" | "하락"
    delta: float


@dataclass(frozen=True)
class TournamentVerdict:
    summary: str


@dataclass(frozen=True)
class TournamentDNAResult:
    identity: TournamentIdentity
    course_dna: CourseDNA
    winning_profile: tuple
    field_composition: tuple
    field_unclassified: int
    best_fits: tuple
    danger_holes: tuple
    opportunity_holes: tuple
    story: tuple
    watch_list: tuple
    verdict: TournamentVerdict
    generated_at: str


# ---------------------------------------------------------------------------
# Section 1: Tournament Identity
# ---------------------------------------------------------------------------


def load_tournament_identity(context: TournamentContext) -> TournamentIdentity:
    sources = []
    par = holes = purse = cut_after_round = field_size = None
    venue = context.venue

    readiness_path = context.artifact_path("operational_readiness")
    if readiness_path.exists():
        import json

        doc = json.loads(readiness_path.read_text(encoding="utf-8"))
        t = doc.get("tournament", {})
        par = t.get("par")
        holes = t.get("holes")
        purse = t.get("purse")
        venue = venue or t.get("venue")
        sources.append(readiness_path.name)

    course_path = CONTENT_DIR / "beta001.json"
    if par is None and course_path.exists():
        import json

        doc = json.loads(course_path.read_text(encoding="utf-8"))
        if doc.get("tournament", {}).get("tournament_id") == context.game_code:
            course = doc.get("course", {})
            par = course.get("par")
            venue = venue or course.get("name")
            sources.append(course_path.name)

    if ACTIVE_TOURNAMENT_PATH.exists():
        import json

        active = json.loads(ACTIVE_TOURNAMENT_PATH.read_text(encoding="utf-8"))
        if str(active.get("game_code")) == context.game_code and active.get("cut_after_round") is not None:
            cut_after_round = active["cut_after_round"]
            sources.append("active_tournament.json")

    try:
        field_size = len(players_for_tournament(context))
        sources.append(f"{context.game_code}_ENTRY_SNAPSHOT.json")
    except FileNotFoundError:
        field_size = None

    return TournamentIdentity(
        game_code=context.game_code,
        tournament_name=context.tournament_name,
        venue=venue,
        par=par,
        holes=holes,
        purse=purse,
        cut_after_round=cut_after_round,
        field_size=field_size,
        sources=tuple(sources),
    )


# ---------------------------------------------------------------------------
# Course-series matching (reuses knowledge_engine's own token matcher)
# ---------------------------------------------------------------------------


def _retained_tournament_rows(warehouse_doc: dict) -> list:
    return [
        r
        for r in warehouse_doc.get("records", [])
        if r.get("scope") == "tournament_cumulative" and r.get("identity_state") == "RETAINED"
    ]


def matching_game_codes(tournament_name: str, warehouse_doc: dict) -> tuple:
    """Every distinct game_code in the warehouse whose own tournament
    name is the same course series as `tournament_name` -- the exact
    token-overlap rule knowledge_engine.find_course_history() already
    uses for one player, applied once across the whole warehouse."""
    target_tokens = ke._tokenize_tournament_name(tournament_name)
    if not target_tokens:
        return ()
    seen = {}
    for r in _retained_tournament_rows(warehouse_doc):
        gc, name = r.get("game_code"), r.get("tournament")
        if not gc or not name or gc in seen:
            continue
        tokens = ke._tokenize_tournament_name(name)
        if not tokens:
            continue
        overlap = len(tokens & target_tokens) / len(tokens | target_tokens)
        if overlap >= rules.COURSE_SERIES_OVERLAP_THRESHOLD:
            seen[gc] = name
    return tuple(sorted(seen.keys()))


def _event_axis_averages(game_codes, warehouse_doc: dict) -> dict:
    game_codes = set(game_codes)
    rows_by_game = defaultdict(list)
    for r in _retained_tournament_rows(warehouse_doc):
        gc = r.get("game_code")
        if gc in game_codes:
            rows_by_game[gc].append(r)

    out = {}
    for gc, rows in rows_by_game.items():
        avgs = {}
        for _key, src_field, _doc_field, _label in COURSE_DNA_AXES:
            values = [r[src_field] for r in rows if r.get(src_field) is not None]
            avgs[src_field] = sum(values) / len(values) if values else None
        out[gc] = avgs
    return out


# ---------------------------------------------------------------------------
# Section 2: Course DNA
# ---------------------------------------------------------------------------


def compute_course_dna(tournament_name: str, warehouse_doc: dict) -> CourseDNA:
    matched = matching_game_codes(tournament_name, warehouse_doc)
    if not matched:
        return CourseDNA(axes=(), sample_events=0, matched_game_codes=())

    all_game_codes = {r["game_code"] for r in _retained_tournament_rows(warehouse_doc) if r.get("game_code")}
    all_event_avgs = _event_axis_averages(all_game_codes, warehouse_doc)
    matched_event_avgs = _event_axis_averages(matched, warehouse_doc)

    axes = []
    for axis_key, src_field, _doc_field, label in COURSE_DNA_AXES:
        matched_values = [a[src_field] for a in matched_event_avgs.values() if a.get(src_field) is not None]
        if not matched_values:
            continue
        course_avg = sum(matched_values) / len(matched_values)
        population = [a[src_field] for a in all_event_avgs.values() if a.get(src_field) is not None]
        pctl = ke.field_percentile(course_avg, population)
        if pctl is None:
            continue
        axes.append(CourseDNAAxis(key=axis_key, label=label, avg_sg=course_avg, percentile=pctl))

    return CourseDNA(axes=tuple(axes), sample_events=len(matched), matched_game_codes=matched)


# ---------------------------------------------------------------------------
# Section 3: Winning Profile
# ---------------------------------------------------------------------------


def compute_winning_profile(tournament_name: str, warehouse_doc: dict) -> tuple:
    matched = set(matching_game_codes(tournament_name, warehouse_doc))
    if not matched:
        return ()
    winners = [r for r in _retained_tournament_rows(warehouse_doc) if r.get("game_code") in matched and r.get("rank") == 1]
    if not winners:
        return ()

    items = []
    for axis_key, src_field, _doc_field, label in COURSE_DNA_AXES:
        values = [w[src_field] for w in winners if w.get(src_field) is not None]
        if not values:
            continue
        items.append(WinningProfileItem(key=axis_key, label=label, threshold_sg=min(values), sample_size=len(values)))
    return tuple(items)


# ---------------------------------------------------------------------------
# Section 4: Field Composition
# ---------------------------------------------------------------------------


def compute_field_composition(player_ids) -> tuple:
    counts = Counter()
    labels = {}
    unclassified = 0
    for pid in player_ids:
        doc = ke.load_player_intelligence_doc(pid)
        if doc is None:
            unclassified += 1
            continue
        pt = doc.get("player_type", {})
        key = pt.get("key")
        if not key:
            unclassified += 1
            continue
        counts[key] += 1
        labels[key] = pt.get("label_ko", key)

    entries = tuple(
        FieldCompositionEntry(key=key, label=labels[key], count=count)
        for key, count in sorted(counts.items(), key=lambda kv: -kv[1])
    )
    return entries, unclassified


# ---------------------------------------------------------------------------
# Section 5: Best Fits (never a ranking sort -- a DNA-match sort)
# ---------------------------------------------------------------------------


def _player_percentile_for_axis(doc: dict, doc_field: str) -> Optional[float]:
    for a in doc.get("player_dna", {}).get("axes", []):
        if a.get("key") == doc_field:
            return a.get("percentile")
    for item in list(doc.get("strengths", [])) + list(doc.get("weaknesses", [])):
        if item.get("metric") == doc_field:
            return item.get("percentile")
    return None


def compute_best_fits(player_ids, course_dna: CourseDNA, max_fits: int = MAX_BEST_FITS) -> tuple:
    if not course_dna.axes:
        return ()
    strongest = max(course_dna.axes, key=lambda a: a.percentile)
    _src_field, doc_field, _label = _AXIS_BY_KEY[strongest.key]

    candidates = []
    for pid in player_ids:
        doc = ke.load_player_intelligence_doc(pid)
        if doc is None:
            continue
        pctl = _player_percentile_for_axis(doc, doc_field)
        if pctl is None:
            continue
        candidates.append((pid, doc.get("hero", {}).get("player_name", pid), pctl))

    candidates.sort(key=lambda c: -c[2])
    fits = []
    for pid, name, pctl in candidates[:max_fits]:
        why = f"이 코스는 {strongest.label} 능력이 중요한 코스이며, {name}은(는) 이 항목에서 {rules.pctl_phrase(pctl)} 수준입니다."
        fits.append(BestFit(player_id=pid, player_name=name, axis=strongest.key, axis_label=strongest.label, percentile=pctl, why=why))
    return tuple(fits)


# ---------------------------------------------------------------------------
# Sections 6-7: Danger Holes / Opportunity Holes
# ---------------------------------------------------------------------------


def discover_hole_rows(context: TournamentContext) -> list:
    """Real per-hole scorecard rows for this game_code, or []. Never
    fabricates a hole statistic when none exists -- Sections 6/7 report
    honestly empty rather than guessing."""
    import json

    path = context.artifact_path("hole_by_hole")
    if path.exists():
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc.get("holes") or doc.get("records") or []

    # The one currently-real archived per-hole scorecard dataset (KG
    # Ladies Open) uses this legacy filename, not the generic
    # artifact_path() convention -- checked explicitly rather than
    # silently missed.
    legacy = CONTENT_DIR / f"kg_{context.game_code}_official.json"
    if legacy.exists():
        doc = json.loads(legacy.read_text(encoding="utf-8"))
        return doc.get("holes") or []

    return []


def compute_hole_stats(hole_rows: list) -> tuple:
    by_hole = defaultdict(list)
    for r in hole_rows:
        hole = r.get("hole")
        if hole is not None:
            by_hole[hole].append(r)

    raw = []
    for hole, rows in by_hole.items():
        n = len(rows)
        if n < MIN_HOLE_SAMPLE:
            continue
        bogeys = sum(1 for r in rows if (r.get("relative_to_par") or 0) >= 1)
        birdies = sum(1 for r in rows if (r.get("relative_to_par") or 0) <= -1)
        pars = [r.get("par") for r in rows if r.get("par") is not None]
        raw.append(
            {
                "hole": hole,
                "par": pars[0] if pars else None,
                "sample": n,
                "bogey_rate": 100.0 * bogeys / n,
                "birdie_rate": 100.0 * birdies / n,
            }
        )
    if not raw:
        return ()

    bogey_rates = [h["bogey_rate"] for h in raw]
    lo, hi = min(bogey_rates), max(bogey_rates)
    span = hi - lo

    def _stars(bogey_rate):
        if span <= 0:
            return 3
        return 1 + round(4 * (bogey_rate - lo) / span)

    stats = [
        HoleStat(
            hole=h["hole"],
            par=h["par"],
            sample=h["sample"],
            bogey_rate=h["bogey_rate"],
            birdie_rate=h["birdie_rate"],
            difficulty_stars=_stars(h["bogey_rate"]),
        )
        for h in raw
    ]
    stats.sort(key=lambda h: h.hole)
    return tuple(stats)


def compute_danger_holes(hole_stats: tuple, max_holes: int = MAX_DANGER_HOLES) -> tuple:
    return tuple(sorted(hole_stats, key=lambda h: -h.bogey_rate)[:max_holes])


def compute_opportunity_holes(hole_stats: tuple, max_holes: int = MAX_OPPORTUNITY_HOLES) -> tuple:
    return tuple(sorted(hole_stats, key=lambda h: (-h.birdie_rate, h.bogey_rate))[:max_holes])


# ---------------------------------------------------------------------------
# Section 9: Watch List
# ---------------------------------------------------------------------------

_COMPONENT_LABELS = {"avg_ott": "드라이빙", "avg_app": "아이언", "avg_arg": "리커버리", "avg_putt": "퍼팅"}


def compute_watch_list(player_ids, max_entries: int = MAX_WATCH_LIST, *, warehouse_doc: Optional[dict] = None) -> tuple:
    """Reuses knowledge_engine.compute_season_profiles() (Sprint 1's own
    public function) directly against one shared warehouse_doc, instead
    of build_evidence() per player -- build_evidence() also reloads the
    SG-field/profile-field/unified-snapshot files this section never
    needs, which made a 100+ player field take tens of seconds for no
    reason. Same data, same frozen logic, just not redundantly reloaded
    per player."""
    warehouse_doc = warehouse_doc if warehouse_doc is not None else ke.load_warehouse()

    entries = []
    for pid in player_ids:
        seasons = ke.compute_season_profiles(pid, warehouse_doc)
        if len(seasons) < 2:
            continue
        player_name = next((r.get("player") for r in warehouse_doc.get("records", []) if r.get("player_id") == pid), pid)
        prev, cur = seasons[-2], seasons[-1]
        for comp, label in _COMPONENT_LABELS.items():
            prev_v, cur_v = getattr(prev, comp), getattr(cur, comp)
            if prev_v is None or cur_v is None:
                continue
            delta = cur_v - prev_v
            if abs(delta) >= rules.REVERSAL_MIN_IMPROVEMENT_SG:
                direction = "개선" if delta > 0 else "하락"
                entries.append(WatchListEntry(player_id=pid, player_name=player_name, component_label=label, direction=direction, delta=delta))
    entries.sort(key=lambda e: -abs(e.delta))
    return tuple(entries[:max_entries])


# ---------------------------------------------------------------------------
# Section 8 & 10: Story / Verdict (pure composition of already-computed facts)
# ---------------------------------------------------------------------------


def build_tournament_story(
    identity: TournamentIdentity,
    course_dna: CourseDNA,
    winning_profile: tuple,
    field_composition: tuple,
    max_facts: int = MAX_STORY_FACTS,
) -> tuple:
    facts = []
    if course_dna.axes:
        strongest = max(course_dna.axes, key=lambda a: a.percentile)
        facts.append(f"이 코스는 {strongest.label} 능력을 특히 요구하는 코스로, 필드 내 {rules.pctl_phrase(strongest.percentile)}에 해당합니다.")
    if winning_profile:
        best = max(winning_profile, key=lambda w: w.threshold_sg)
        facts.append(f"역대 우승자들은 {best.label} SG {best.threshold_sg:+.2f} 이상을 기록했습니다({best.sample_size}명 기준).")
    if field_composition:
        top = field_composition[0]
        facts.append(f"이번 대회 참가 선수 중 {top.count}명이 {top.label} 유형입니다.")
    if course_dna.sample_events:
        facts.append(f"이 코스 시리즈는 최근 {course_dna.sample_events}회 대회의 실제 기록을 근거로 분석되었습니다.")
    if identity.field_size:
        facts.append(f"이번 대회 참가 선수는 총 {identity.field_size}명입니다.")
    return tuple(facts[:max_facts])


def build_tournament_verdict(identity: TournamentIdentity, course_dna: CourseDNA, field_composition: tuple) -> TournamentVerdict:
    """Exactly 2 sentences: FACT + INTERPRETATION, never a prediction --
    the same discipline as player_intelligence_generator.build_neo_verdict()."""
    fact = f"{identity.tournament_name}({identity.venue or '코스 미상'})은(는) 실제 과거 기록 {course_dna.sample_events}회를 근거로 분석된 코스입니다."
    if course_dna.axes:
        strongest = max(course_dna.axes, key=lambda a: a.percentile)
        interpretation = f"이 코스는 {strongest.label} 능력이 뛰어난 선수에게 유리한 것으로 나타납니다."
    elif field_composition:
        interpretation = f"참가 선수 중 가장 많은 유형은 {field_composition[0].label}입니다."
    else:
        interpretation = "이 코스의 특성을 판단할 실제 과거 기록이 아직 충분하지 않습니다."
    return TournamentVerdict(summary=f"{fact} {interpretation}")


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def generate_tournament_dna(context: TournamentContext) -> TournamentDNAResult:
    warehouse_doc = ke.load_warehouse()
    identity = load_tournament_identity(context)

    try:
        player_ids = players_for_tournament(context)
    except FileNotFoundError:
        player_ids = []

    course_dna = compute_course_dna(context.tournament_name, warehouse_doc)
    winning_profile = compute_winning_profile(context.tournament_name, warehouse_doc)
    field_composition, unclassified = compute_field_composition(player_ids)
    best_fits = compute_best_fits(player_ids, course_dna)

    hole_rows = discover_hole_rows(context)
    hole_stats = compute_hole_stats(hole_rows)
    danger_holes = compute_danger_holes(hole_stats)
    opportunity_holes = compute_opportunity_holes(hole_stats)

    watch_list = compute_watch_list(player_ids, warehouse_doc=warehouse_doc)
    story = build_tournament_story(identity, course_dna, winning_profile, field_composition)
    verdict = build_tournament_verdict(identity, course_dna, field_composition)

    return TournamentDNAResult(
        identity=identity,
        course_dna=course_dna,
        winning_profile=winning_profile,
        field_composition=field_composition,
        field_unclassified=unclassified,
        best_fits=best_fits,
        danger_holes=danger_holes,
        opportunity_holes=opportunity_holes,
        story=story,
        watch_list=watch_list,
        verdict=verdict,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def to_json_dict(result: TournamentDNAResult) -> dict:
    identity = result.identity
    return {
        "identity": {
            "game_code": identity.game_code,
            "tournament_name": identity.tournament_name,
            "venue": identity.venue,
            "par": identity.par,
            "holes": identity.holes,
            "purse": identity.purse,
            "cut_after_round": identity.cut_after_round,
            "field_size": identity.field_size,
            "sources": list(identity.sources),
        },
        "course_dna": {
            "axes": [{"key": a.key, "label": a.label, "avg_sg": a.avg_sg, "percentile": a.percentile} for a in result.course_dna.axes],
            "sample_events": result.course_dna.sample_events,
            "matched_game_codes": list(result.course_dna.matched_game_codes),
        },
        "winning_profile": [
            {"key": w.key, "label": w.label, "threshold_sg": w.threshold_sg, "sample_size": w.sample_size} for w in result.winning_profile
        ],
        "field_composition": [{"key": f.key, "label": f.label, "count": f.count} for f in result.field_composition],
        "field_unclassified": result.field_unclassified,
        "best_fits": [
            {"player_id": b.player_id, "player_name": b.player_name, "axis": b.axis, "axis_label": b.axis_label, "percentile": b.percentile, "why": b.why}
            for b in result.best_fits
        ],
        "danger_holes": [
            {"hole": h.hole, "par": h.par, "sample": h.sample, "bogey_rate": h.bogey_rate, "birdie_rate": h.birdie_rate, "difficulty_stars": h.difficulty_stars}
            for h in result.danger_holes
        ],
        "opportunity_holes": [
            {"hole": h.hole, "par": h.par, "sample": h.sample, "bogey_rate": h.bogey_rate, "birdie_rate": h.birdie_rate, "difficulty_stars": h.difficulty_stars}
            for h in result.opportunity_holes
        ],
        "story": list(result.story),
        "watch_list": [
            {"player_id": w.player_id, "player_name": w.player_name, "component_label": w.component_label, "direction": w.direction, "delta": w.delta}
            for w in result.watch_list
        ],
        "verdict": {"summary": result.verdict.summary},
        "generated_at": result.generated_at,
    }
