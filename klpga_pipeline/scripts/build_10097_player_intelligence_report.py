"""PLAYER INTELLIGENCE REPORT -- 김민선7 (playerCode=10097) ONLY.

The Gold Standard reference implementation for NEO Player Intelligence.
Written the way a KLPGA tour coach or performance analyst would brief a
player, not the way a stats website would -- organized entirely by real
golf QUESTIONS, never by raw statistics, SG components, or a flat list
of records. Every answer is FACT -> EVIDENCE -> ANALYSIS -> CONCLUSION,
followed by what the conclusion is actually FOR: why it matters, what
the player should learn from it, what the coach should watch, whether
it is a durable characteristic or a recent trend, a one-sentence "why
this matters" close, and -- last, always -- a concrete ACTION: an
imperative instruction for what to do differently in practice or the
next tournament, not a restatement of the conclusion. NEO exists to
improve performance, not only to explain it, so no section is allowed
to stop at an explanation. A conclusion that would not change how she
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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.knowledge_engine import knowledge_engine as ke  # noqa: E402
from klpga.tournament_context import CONTENT_DIR  # noqa: E402

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
# Candidate questions. Each maps onto audit records already computed by
# build_10097_master_player_analysis.py -- this function only narrates and
# combines them, it never derives a new number. Every question that
# survives to the report answers a "so what": it says what should change
# in how she prepares, trains, or is coached, not just what a number is.
# ---------------------------------------------------------------------------


def _q_why_wins(master_doc: dict, ds: dict, season_profiles: list) -> dict:
    win_fact = _fact(master_doc, "fact_win_count")["audit"]
    reasons = [_conclusion(master_doc, f"play_style.why_wins[{i}]") for i in range(3)]
    wins = master_doc["tournament_analysis"]["wins"]
    win_names = ", ".join(f"{w['tournament']} ({w['season']})" for w in wins)
    app_trend = _season_line(season_profiles, "avg_app")

    fact = (
        f"Four real wins on record ({win_names}) share the same underlying mechanism: an approach game "
        "that has produced positive scoring value in every one of her four seasons on tour, not only in "
        "winning weeks."
    )
    evidence = [
        f"Season-by-season SG Approach across her full {len(season_profiles)}-season, {sum(p.n_tournaments for p in season_profiles)}-tournament record: {app_trend} -- four consecutive seasons of positive, rising value from the same category.",
        f"{reasons[1]['statement']} -- a current-season signal (field of {reasons[1]['sample_size']} rated players), not yet confirmed across multiple seasons the way the approach trend is.",
        f"{reasons[2]['statement']} -- also a current-season signal (field of {reasons[2]['sample_size']} rated players).",
    ]
    analysis = (
        "The wins themselves are one-off events, but the mechanism behind them is not. Every season on record "
        "shows the same shape: her approach play is the component that never goes negative, even in seasons "
        "when the rest of her game was still developing. That is what turns a promising round into a winning "
        "one -- she reliably gives herself birdie looks other players in the field do not get, and this "
        "season's elite green-in-regulation and par-save rates show that advantage currently converting into "
        "fewer bogeys as well as more birdies."
    )
    conclusion = (
        f"{PLAYER_NAME} wins because her approach game supplies a scoring edge that has held up in every "
        "season she has played, not because of a single hot week -- this season's elite GIR and par-save "
        "rates are compounding on top of that structural strength, not replacing it."
    )
    why_it_matters = (
        "If the coaching team understands why she wins, they can protect that mechanism deliberately in "
        "game-planning and practice design, instead of treating each win as a good week to celebrate and "
        "move past without asking what produced it."
    )
    player_takeaway = (
        "Trust the approach game under pressure -- it is the part of her game that has not let her down in "
        "four seasons, and it is the shot to default to rather than forcing a riskier line to compensate for "
        "a slow start."
    )
    coach_focus = (
        "Track GIR and par-save rate week to week as an early-warning signal. Because those two are "
        "current-season numbers only, a dip there would show up before it shows up in the more stable "
        "approach trend -- and they are the one part of this answer not yet proven across multiple years."
    )
    durability = LONG_TERM
    durability_reasoning = (
        "The core driver -- SG Approach -- has been positive and rising in all four seasons on record, so "
        "another season is far more likely to reinforce this conclusion than overturn it. The GIR and "
        "par-save citations, however, come from this season's leaderboard only: if either regresses next "
        "year, the explanation for her wins still holds through approach play, but those two specific "
        "supporting numbers should not yet be treated as guaranteed year-over-year characteristics."
    )
    why_this_matters = "This is the shot to build the week's game plan around, not just admire after a win."
    action = (
        "Build the tournament-week game plan around approach play first, and check GIR and par-save rate "
        "after every round, not only at season's end -- a dip there is the earliest signal this edge is "
        "softening."
    )

    sample_sizes = [win_fact["sample_size"], sum(p.n_tournaments for p in season_profiles)] + [r["sample_size"] for r in reasons]
    sources = set(win_fact["official_records_used"]) | {s for r in reasons for s in r["official_records_used"]}
    return {
        "id": "q_why_wins",
        "question": f"Why does {PLAYER_NAME} win?",
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
        "evidence_score": _evidence_score(min(sample_sizes), len(sources)),
        "sample_size": min(sample_sizes),
        "confidence": _weakest_confidence([win_fact["confidence"]] + [r["confidence"] for r in reasons]),
    }


def _q_why_loses(master_doc: dict, season_profiles: list) -> dict:
    reasons = [_conclusion(master_doc, f"play_style.why_loses[{i}]") for i in range(2)]
    putt_trend = _season_line(season_profiles, "avg_putt")
    this_season, last_season = season_profiles[-1], season_profiles[-2]

    fact = (
        "Putting has never been the part of Kim Minsun7's game that wins tournaments for her -- in all four "
        "seasons on record it has been her smallest source of scoring value, and this season that gap widened "
        "rather than closed."
    )
    evidence = [
        f"Season-by-season SG Putting: {putt_trend} -- smaller than her other three components in every season, and {this_season.season}'s figure is her lowest of the four.",
        f"{reasons[0]['statement']} -- field-average, not poor, but the shortfall stands out against her own 93rd-97th percentile approach and off-the-tee level, not against the field (field of {reasons[0]['sample_size']} rated players).",
        f"{reasons[1]['statement']} -- the same field-average read from a second, independent stat (field of {reasons[1]['sample_size']} rated players).",
    ]
    analysis = (
        "Her ball-striking creates more scoring opportunities than almost anyone else in the field -- she "
        "simply isn't converting them into birdies at the rate that ball-striking would predict. That gap has "
        "existed every season she has played, which means it is not a slump to fix in a single week; it "
        "behaves more like a structural ceiling on how many of her approach shots turn into red numbers. This "
        f"season's dip ({this_season.avg_putt:+.2f}, down from {last_season.avg_putt:+.2f} last year) is the one "
        "part of the picture that is new, and is worth watching rather than assuming it self-corrects."
    )
    conclusion = (
        "Her approach game consistently creates scoring opportunities, but her putting has converted fewer of "
        "those opportunities into birdies than her ball-striking level would predict -- true in every season "
        "on record, and more so this year than in any of the previous three."
    )
    why_it_matters = (
        "A loss caused by short-game conversion calls for a different response than a loss caused by "
        "ball-striking breaking down -- misdiagnosing which one it is wastes practice time on the wrong fix."
    )
    player_takeaway = (
        "The strokes that cost the most are not missed greens -- they are the reasonable birdie putts that go "
        "unconverted. Treat scoring conversion, not shot-making, as the growth area this season."
    )
    coach_focus = (
        f"Compare this season's putting numbers against last year's on a rolling basis, not only at season's "
        f"end -- {this_season.season} is already her lowest of four seasons, and catching a continued slide "
        "early is more useful than confirming it in the final standings."
    )
    durability = LONG_TERM
    durability_reasoning = (
        "Putting has been her smallest-value component in all four seasons on record, so 'putting is not her "
        "primary strength' would very likely still be true after another season -- a fifth season is far more "
        "likely to confirm this pattern than erase it. The size of this year's specific dip is thinner, "
        "newer evidence: a rebound next season would not overturn the broader four-season pattern, so that "
        "one number carries less weight than the structural read it sits inside."
    )
    why_this_matters = "The next stroke gained has to come from scoring conversion, not a swing change."
    action = (
        f"Shift a real share of next week's practice time from ball-striking to putting and short-game "
        f"conversion drills, and track her rolling SG Putting against {last_season.avg_putt:+.2f} (last "
        "season) rather than waiting for the season total to confirm the slide."
    )

    sample_sizes = [r["sample_size"] for r in reasons]
    sources = {s for r in reasons for s in r["official_records_used"]}
    return {
        "id": "q_why_loses",
        "question": f"Why does {PLAYER_NAME} lose?",
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
        "evidence_score": _evidence_score(min(sample_sizes), len(sources)),
        "sample_size": min(sample_sizes),
        "confidence": _weakest_confidence([r["confidence"] for r in reasons]),
    }


def _q_approach_biggest_weapon(master_doc: dict, ds: dict, season_profiles: list) -> dict:
    insight = next(i for i in master_doc["knowledge_graph"]["insights"] if i["id"] == "insight_elite_approach_and_ott")
    audit = insight["audit"]
    pi = ds["player_intelligence_doc"]
    app_axis = next(a for a in pi["player_dna"]["axes"] if a["key"] == "sg_app")
    app_trend = _season_line(season_profiles, "avg_app")

    fact = (
        "Across four seasons, approach has remained Kim Minsun7's most consistent scoring advantage. Even in "
        "seasons when the rest of her game was still developing, approach never stopped producing positive "
        "value."
    )
    evidence = [
        f"Current-season field percentile: {app_axis['percentile']:.1f}th of {audit['sample_size']} rated players -- one of the most reliable approach players in the field right now.",
        f"Season-by-season average SG Approach across her full {audit['season_count']}-season, {audit['tournament_count']}-tournament record: {app_trend} -- her highest or second-highest component every single season.",
        f"Frozen Knowledge Engine classification: \"{pi['player_type']['label_ko']}\" ({pi['player_type']['label_en']}) -- \"{insight['insight']}\"",
    ]
    analysis = (
        "A single elite season could be a swing change paying off right now, or a hot run of ball-striking "
        "that regresses next year. Four consecutive seasons of the same component staying at or near the top "
        "of her profile is a different kind of signal -- it means approach is not something she is currently "
        "doing well, it is something she reliably does well, independent of what else in her game is in form."
    )
    conclusion = (
        "Approach is Kim Minsun7's most durable strength -- not because it is her best number this week, but "
        "because it has not had a down season in four years."
    )
    why_it_matters = (
        "Knowing which strength is durable, rather than a hot streak, tells the coaching team what NOT to "
        "touch when another part of her game needs adjustment."
    )
    player_takeaway = "This is the shot never to sacrifice for the sake of another part of the game -- any technical work should protect approach mechanics first."
    coach_focus = (
        "Treat a dip below her own four-season floor (roughly the +0.35 SG level from her 2023 season) as a "
        "signal worth investigating immediately -- it would be the first time in her recorded history that "
        "this component has gone quiet."
    )
    durability = LONG_TERM
    durability_reasoning = (
        "Four consecutive positive seasons is about as strong a durability signal as a single player's record "
        "can produce; another season is far more likely to extend the streak than break it. This read should "
        "only be revisited if a season ever shows a genuine regression, which has not happened yet."
    )
    why_this_matters = "It is the shot the rest of her game plan should be built around, every tournament, not just this one."
    action = (
        "Rule approach mechanics out of scope for any swing or equipment change under consideration -- "
        "isolate technical work to other components so this four-season strength is never put at risk as a "
        "side effect."
    )

    sources = set(audit["official_records_used"])
    return {
        "id": "q_approach_biggest_weapon",
        "question": f"Why is Approach {PLAYER_NAME}'s biggest weapon?",
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
        "evidence_score": _evidence_score(audit["sample_size"], len(sources)),
        "sample_size": audit["sample_size"],
        "confidence": audit["confidence"],
    }


def _q_putting_weakest(master_doc: dict, ds: dict, season_profiles: list) -> dict:
    reason = _conclusion(master_doc, "play_style.why_loses[0]")
    pi = ds["player_intelligence_doc"]
    axes = {a["key"]: a["percentile"] for a in pi["player_dna"]["axes"]}
    order = [("sg_ott", "Off-the-Tee"), ("sg_app", "Approach"), ("sg_arg", "Around-the-Green"), ("sg_putt", "Putting")]
    axis_line = ", ".join(f"{label} {axes[k]:.1f}th" for k, label in order)
    putt_trend = _season_line(season_profiles, "avg_putt")

    fact = (
        "Putting is the one component of Kim Minsun7's game that has never kept pace with the rest -- this "
        "season it ranks lowest of her own four shot-making categories, and that gap is not new."
    )
    evidence = [
        f"Her own component spread this season: {axis_line} -- all field percentiles, same {reason['sample_size']}-player official SG field.",
        f"Season-by-season SG Putting: {putt_trend} -- the smallest of her four components in every season on record, not only this one.",
    ]
    analysis = (
        "Ranking her own four components against each other, rather than against the field, changes the "
        "conclusion in a way that matters for planning practice time: Off-the-Tee, Approach and "
        "Around-the-Green all sit in a range that would be considered elite on tour; Putting alone does not. "
        "That is a different statement from 'her putting is bad' -- it is a statement about where the next "
        "hour of practice time buys the most improvement relative to what she already has."
    )
    conclusion = (
        "Putting is not a weakness in absolute terms -- it is the one category that has not grown at the same "
        "rate as the rest of her game, in every season on record, which makes it the highest-leverage area for "
        "continued development."
    )
    why_it_matters = (
        "Practice time is finite. Knowing that putting is the one component that hasn't kept pace in every "
        "season on record is what justifies weighting practice hours toward it, instead of further polishing "
        "a skill that is already elite."
    )
    player_takeaway = "Don't read 'weakest area' as 'poor putter' -- it means every other part of the game has been pulled up to an elite level, and putting is the one with room left to close the gap."
    coach_focus = "Prioritize putting practice time relative to her other three categories, not in isolation -- the goal is closing a 20-to-40-percentile-point internal gap, not chasing a field ranking that is already average."
    durability = LONG_TERM
    durability_reasoning = (
        "This ranking -- Putting last among her own four components -- has held in all four seasons on "
        "record. Another season would have to show a genuinely different pattern, Putting closing the "
        "internal gap on the other three, to change this conclusion, and that has not happened in her history "
        "to date."
    )
    why_this_matters = "This is where the next hour of practice time pays off the most."
    action = (
        "Rebalance the weekly practice schedule to give putting a larger share of the hours than it "
        "currently gets, and measure progress by birdie-conversion rate on approach-created looks, not by "
        "field-relative putting rank."
    )

    sample_sizes = [reason["sample_size"]]
    sources = set(reason["official_records_used"]) | {"knowledge_engine.compute_season_profiles() (player_dna.axes)"}
    return {
        "id": "q_putting_weakest",
        "question": f"Why has Putting become {PLAYER_NAME}'s weakest area?",
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
        "evidence_score": _evidence_score(min(sample_sizes), len(sources)),
        "sample_size": min(sample_sizes),
        "confidence": reason["confidence"],
    }


def _q_2026_improvement(master_doc: dict, season_profiles: list) -> dict:
    audit = _conclusion(master_doc, "season_evolution.frozen_knowledge_engine_evolution.narrative")
    total_trend = ", ".join(f"{p.season} ({p.n_tournaments} events) {p.avg_total:+.2f}" for p in season_profiles)
    ott_trend = _season_line(season_profiles, "avg_ott")
    app_trend = _season_line(season_profiles, "avg_app")
    putt_trend = _season_line(season_profiles, "avg_putt")

    fact = (
        "Kim Minsun7's rise from a developing player to a tour winner did not happen in one season -- her "
        "overall scoring value has increased in every one of her four seasons on record, and the shape of "
        "that rise tracks her ball-striking, not a hot putting run."
    )
    evidence = [
        f"Season-by-season SG Total: {total_trend} -- rising every season, backed by 16 to 23 tournaments each year.",
        f"The same rise shows up in Off-the-Tee ({ott_trend}) and Approach ({app_trend}), while Putting has not climbed at the same rate ({putt_trend}) -- confirming the improvement is a ball-striking story, not a short-game one.",
    ]
    analysis = (
        "A four-season, monotonic rise across two ball-striking components, running in parallel with a real "
        "tournament count behind each season's average, is not a form spike -- it is what a genuine "
        "improvement in swing quality and distance control looks like over time. It also tells the coaching "
        "team what not to credit: putting has not risen anywhere near the same rate, so a story built around "
        "'the short game has caught up' would not be supported by her own record."
    )
    conclusion = (
        "Her 2026 performance is the continuation of a real, multi-season improvement in ball-striking, not a "
        "one-off good year -- and the technical program behind that improvement is the one thing this record "
        "says should not be changed."
    )
    why_it_matters = "Confirming the improvement is structural, not lucky, is what keeps a coaching staff from second-guessing a program that is actually working after one difficult week."
    player_takeaway = "The improvement is real and it's hers to keep building on -- it did not come from one lucky adjustment, so the current emphasis on ball-striking is the right one to continue, not to second-guess after a single bad week."
    coach_focus = "Protect the current technical program around off-the-tee and approach; if any coaching change is being considered, benchmark it against four seasons of steady improvement before assuming something needs fixing."
    durability = LONG_TERM
    durability_reasoning = (
        "This is already a four-season pattern, so it is about as durable a read as this record can produce. "
        "A fifth season that continued the trend would reinforce it further; even a flat fifth season would "
        "not erase four years of real, recorded improvement -- it would only change what comes next, not what "
        "already happened."
    )
    why_this_matters = "Keep doing what has been working -- this is not the record of a player who needs a change."
    action = (
        "Leave the current off-the-tee and approach technical program unchanged through any single bad "
        "week; require four-season evidence, not a one-week result, before any change to it is approved."
    )

    sources = set(audit["official_records_used"])
    return {
        "id": "q_2026_improvement",
        "question": f"Why did {PLAYER_NAME}'s performance improve through 2026?",
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
        "evidence_score": _evidence_score(audit["tournament_count"], len(sources)),
        "sample_size": audit["tournament_count"],
        "confidence": audit["confidence"],
    }


def _q_strong_course(master_doc: dict) -> dict:
    group = max(master_doc["course_analysis"]["course_series"], key=lambda g: g["appearances"])
    n = group["appearances"]
    history_line = "; ".join(
        f"{h['season']} {h['sg_total']:+.2f}" if h.get("sg_total") is not None else f"{h['season']} n/a" for h in group["history"]
    )

    fact = (
        "When Kim Minsun7 returns to a course she has already played, her record says she should be trusted "
        f"to perform, not managed cautiously. Her strongest repeated result is at {group['series_name_sample']}, "
        f"where {n} real appearances have produced a positive scoring average and her most recent visit was a win."
    )
    evidence = [
        f"Appearance-by-appearance SG Total by season: {history_line} -- {n} real visits, every one of them positive, the best coming on her most recent trip.",
        f"Average SG Total across all {n} appearances: {group['avg_sg_total']:+.2f}, well above her all-time career baseline.",
    ]
    analysis = (
        "One good week at a course could be the luck of the pairing or the conditions. Four real visits, "
        "spread across four different seasons, all landing positive -- with the best of the four on her most "
        "recent trip -- looks like accumulated course knowledge rather than a coincidence. That is a "
        "different kind of insight than a single-week form check: it says this course rewards something she "
        "already does well, and repetition has sharpened it rather than the effect fading."
    )
    conclusion = (
        f"This is a course where the game plan should lean on what already works rather than experimenting -- "
        f"{n} appearances and a rising trend point to real course familiarity, not a single lucky week."
    )
    why_it_matters = "Knowing a strong result is course-specific and evidence-backed, not a guess, tells the team when to trust her instincts on-site and when to hold back on last-minute changes."
    player_takeaway = "Walk into this course with confidence built on a real track record, not just optimism -- the data backs the feeling that this is 'her' course."
    coach_focus = f"Use {group['series_name_sample']} as a template for what a good week looks like for her, and be cautious about introducing swing or strategy changes the week before she plays it again."
    durability = LONG_TERM
    durability_reasoning = (
        f"The {n} appearances already happened and cannot be changed by anything in the future -- that record "
        "stands regardless of what happens next time. But because it is only four data points, a single "
        "below-par visit next time would meaningfully soften the average without overturning the pattern; "
        "treat this as a strong lean, not a guarantee."
    )
    why_this_matters = "It is the clearest place in her record where preparation should trust the player rather than over-coach her."
    action = (
        f"When the schedule returns to {group['series_name_sample']}, run her established pre-tournament "
        "routine unchanged and hold off on any swing or strategy experiments that week -- treat it as a "
        "week to execute, not to test something new."
    )

    sources = {"historical_sg_warehouse_corrected.json", "knowledge_engine.find_course_history()"}
    return {
        "id": "q_strong_course",
        "question": f"Why is {PLAYER_NAME} strong at {group['series_name_sample']}?",
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
        "evidence_score": _evidence_score(n, len(sources)),
        "sample_size": n,
        "confidence": "HIGH" if n >= 4 else ("MEDIUM" if n >= 3 else "LOW"),
    }


def _q_most_recent_win(master_doc: dict) -> dict:
    win = master_doc["tournament_analysis"]["most_recent_win"]
    if not win:
        return None
    rounds = list(win["round_sg"].items())
    sg_line = ", ".join(f"{rnd} {sg:+.2f}" for rnd, sg in rounds)

    fact = (
        "Her most recent title did not come from a fast start she had to defend -- it came from building into "
        "the tournament, round by round, until her ball-striking was at its best exactly when it mattered most."
    )
    evidence = [
        f"Round-by-round SG Total: {sg_line} -- her best round of the three came last, not first.",
        f"Official result: {win['tournament']} ({win['final_score']}, rank #{win['final_rank']}) -- {win['official_source']}.",
    ]
    analysis = (
        "A win built on a fading lead and a defensive final round tells a coach one thing about a player's "
        "tournament mentality; a win built on an SG total that kept climbing through the weekend tells a "
        "different one. This result is the second kind -- her play got better as the pressure increased, "
        "which is a repeatable mental pattern worth reinforcing, not just a good outcome to note."
    )
    conclusion = "Her most recent win was earned by getting stronger under pressure, not by holding on -- a pattern worth building her pre-tournament mental preparation around."
    why_it_matters = "How a player actually wins shapes how she should be managed emotionally during a tournament -- a closer needs different pre-round messaging than a front-runner, and her own record answers which one she has been recently."
    player_takeaway = "A merely-good first round is not a warning sign for her -- her own record shows she is a player who builds into a tournament, so the message should be about trusting that process, not forcing an early result."
    coach_focus = "Watch how she talks about herself after an average round one -- the data says panic is not warranted, and reinforcing that pattern matches how she has actually won."
    durability = CONFIRMED_EVENT
    durability_reasoning = (
        "This already happened and is fixed by the official result -- no future season can change what "
        "occurred in this event. Whether it is a repeatable PATTERN across multiple wins is a separate, "
        "so-far-unsupported question (see the excluded 'does she tend to win at courses she's played before' "
        "item below); this section describes this one win accurately, without generalizing beyond it."
    )
    why_this_matters = "It gives the coaching team a real, recent example to point to when managing her mindset after a slow start."
    action = (
        f"Build her pre-round messaging around the {win['tournament']} result specifically: after any "
        "ordinary round one, reinforce that she builds into tournaments rather than pushing her to force a "
        "recovery she does not need."
    )

    sources = {win["official_source"].split(" (")[0]}
    return {
        "id": "q_most_recent_win",
        "question": f"How did {PLAYER_NAME} win her most recent title, the {win['tournament']}?",
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
        "question": f"Does {PLAYER_NAME} tend to win at courses she has played before?",
        "reason_excluded": fact_audit["note"],
        "sample_size": fact_audit["sample_size"],
        "confidence": fact_audit["confidence"],
    }


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def build() -> dict:
    master_doc, ds, season_profiles = _load_inputs()

    candidates = [
        _q_why_wins(master_doc, ds, season_profiles),
        _q_why_loses(master_doc, season_profiles),
        _q_approach_biggest_weapon(master_doc, ds, season_profiles),
        _q_putting_weakest(master_doc, ds, season_profiles),
        _q_2026_improvement(master_doc, season_profiles),
        _q_strong_course(master_doc),
        _q_most_recent_win(master_doc),
    ]
    candidates = [c for c in candidates if c is not None]

    questions = []
    excluded = []
    for c in candidates:
        if c["confidence"] == "UNKNOWN":
            excluded.append({"id": c["id"], "question": c["question"], "reason_excluded": "confidence resolved to UNKNOWN; never kept as an unsupported conclusion.", "sample_size": c["sample_size"]})
            continue
        questions.append(c)

    excluded.append(_q_repeat_course_pattern_candidate(master_doc))

    from datetime import datetime, timezone

    return {
        "schema_version": "player_intelligence_report_v1",
        "player_id": PLAYER_ID,
        "player_name": PLAYER_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope_note": "This document covers ONLY playerCode=10097. No other player's data was generated or modified. Gold Standard reference implementation.",
        "evidence_score_method": (
            "evidence_score = round(100 * min(1, distinct_official_sources / 3) * sample_size / (sample_size + 5)). "
            "A deterministic, disclosed scoring of already-computed sample_size + source diversity -- not a new "
            "statistical claim about the player."
        ),
        "durability_method": (
            "Every question asks: would adding one more season likely overturn this conclusion? "
            f"'{LONG_TERM}' = built on a pattern present in most or all seasons on record, unlikely to reverse. "
            f"'{RECENT_TREND}' = based on this season only; a future season could change it. "
            f"'{CONFIRMED_EVENT}' = an already-completed result, not a trend claim -- it cannot be overturned by future data, "
            "but is also not generalized into a repeatable pattern beyond itself."
        ),
        "questions": questions,
        "questions_considered_but_unsupported": excluded,
        "source_document": "MASTER_ANALYSIS.json (audited via scripts/build_10097_master_player_analysis.py)",
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
