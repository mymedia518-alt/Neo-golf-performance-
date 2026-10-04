"""Official per-player detail record enrichment -- generic, any
playerCode. Extends the existing PLAYER_HISTORY.json (built by
scripts/build_10097_player_history.py's now-generic build()) with real
fields from the two confirmed collectors in
klpga.collectors.player_profile (publicRecordSeasonDetail +
scoreDetail -- see klpga.config.PUBLIC_RECORD_SEASON_DETAIL_ENDPOINT /
SCORE_DETAIL_ENDPOINT for the full live-discovery trail, 2026-10-03).

This is explicitly an ENRICHMENT step, not a second Player History
engine: it never recomputes or overwrites anything the existing
generator already produced. It only reads the PLAYER_HISTORY.json that
generator already wrote, and merges in a small number of NEW top-level
keys -- existing keys are passed through byte-for-byte. Runs AFTER
scripts/build_player_report.py in the real pipeline:

    build_player_report.py (reconcile + PLAYER_HISTORY.json + pages)
      -> run_official_detail_enrichment() (this module)

Real, generic, no player_id special-casing: every function here takes
player_id/player_name/game_codes as plain arguments. A player this
session's egress-blocked sandbox cannot reach gets a real, honest
PartialEvidenceError (never a fabricated/placeholder value) -- see
`OfficialDetailUnavailable`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from klpga.collectors.player_profile import (
    fetch_public_record_season_detail_html,
    fetch_score_detail_html,
    parse_public_record_season_detail_html,
    parse_score_detail_html,
)
from klpga.http_client import PoliteHttpClient
from klpga.tournament_context import CONTENT_DIR as CONTENT


class OfficialDetailUnavailable(RuntimeError):
    """Raised when a real fetch/parse genuinely fails -- never
    swallowed into a placeholder/zero value."""


def player_profile_raw_path(player_id: str, *, content_root: Optional[Path] = None) -> Path:
    root = content_root or CONTENT
    return root / "knowledge_engine" / "player_intelligence" / str(player_id) / "PLAYER_PROFILE_RAW.json"


# --- Real label -> field-name mapping, from the CONFIRMED publicRecordSeasonDetail
# response (see klpga.config.PUBLIC_RECORD_SEASON_DETAIL_ENDPOINT). A label
# this mapping does not cover stays available in the raw sections dict
# (parse_public_record_season_detail_html's own return value) but is not
# promoted into the normalized/engine-facing shape below -- never silently
# dropped, just not yet wired to a named field.
_SEASON_DETAIL_FIELD_MAP = (
    ("스코어", "평균타수", "average_score"),
    ("스코어", "평균버디", "avg_birdie_per_round"),
    ("스코어", "버디율", "birdie_rate"),
    ("스코어", "파브레이크율", "par_break_rate"),
    ("스코어", "이글", "eagle_count"),
    ("스코어", "홀인원", "hole_in_one_count"),
    ("기술", "페어웨이 안착률", "fairway_hit_rate"),
    ("기술", "드라이브 거리", "avg_driving_distance"),
    ("기술", "평균퍼팅", "avg_putts"),
    ("기술", "그린적중률", "gir_rate"),
    ("기술", "벙커세이브율", "bunker_save_rate"),
    ("기술", "리커버리율", "recovery_rate"),
)
# par_save_rate (파세이브율) is deliberately ABSENT here: it is not a
# label this confirmed endpoint publishes (see klpga.collectors.
# player_profile module docstring) -- a caller must not assume it is
# present just because other OFFICIAL_PROFILE_NORMALIZED.json records
# (sourced from a DIFFERENT endpoint, totalRecord) carry it.


def collect_official_season_detail(
    client: PoliteHttpClient, player_id: str, season: str, *, tour_type: str = "RE",
) -> dict:
    """Real fetch+parse+normalize of publicRecordSeasonDetail for one
    player/season. Returns
        {"raw_sections": {...full parse_public_record_season_detail_html output...},
         "normalized": {field_name: value_or_None, ...}}
    Raises OfficialDetailUnavailable on a real fetch/parse failure --
    never returns a partial result silently."""
    try:
        html = fetch_public_record_season_detail_html(client, player_id, season, tour_type=tour_type)
        raw_sections = parse_public_record_season_detail_html(html)
    except Exception as exc:  # real network/parse failure, never swallowed
        raise OfficialDetailUnavailable(
            f"publicRecordSeasonDetail collection failed for player_id={player_id} season={season}: {exc}"
        ) from exc

    normalized: dict = {}
    for section, label, field_name in _SEASON_DETAIL_FIELD_MAP:
        row = raw_sections.get(section, {}).get(label)
        normalized[field_name] = row["value"] if row else None
    return {"raw_sections": raw_sections, "normalized": normalized}


def collect_official_scorecards(
    client: PoliteHttpClient, player_id: str, player_name: str, game_codes: list[str],
) -> dict:
    """Real fetch+parse of scoreDetail for each real game_code the
    player actually played (caller sources these from the player's own
    already-reconciled PLAYER_HISTORY.json `tournament_history[*]
    .game_code` -- never guessed). Returns
    {game_code: {round_number: {...parse_score_detail_html's own per-round shape...}}}.
    A single game_code's fetch failure does not abort the others --
    each failure is recorded under that game_code's own key as
    {"error": str(exc)} so a caller can see exactly which tournaments
    have real hole-by-hole data and which do not, rather than losing
    the whole collection to one bad fetch."""
    out: dict = {}
    for game_code in game_codes:
        try:
            html = fetch_score_detail_html(client, player_id, game_code, player_name=player_name)
            out[game_code] = parse_score_detail_html(html)
        except Exception as exc:
            out[game_code] = {"error": str(exc)}
    return out


# Real per-hole classification labels this project's own
# klpga.collectors.player_profile.parse_score_detail_html already
# produces (see that module) -- reused verbatim, not redefined.
_HOLE_CLASSES = ("Eagle", "Birdie", "Par", "Bogey", "Double Bogey", "Triple Bogey+")


def compute_hole_distribution(scorecards: dict) -> dict:
    """Real aggregation across every successfully-collected round in
    `scorecards` (collect_official_scorecards's own output) -- counts
    per classification, plus the real total holes counted. A
    game_code/round that failed to collect (carries an "error" key, or
    has no real "holes" list) contributes nothing, never a guessed
    zero. Returns {"counts": {class: int}, "total_holes": int,
    "double_bogey_avoidance_rate": float_or_None, "source_rounds":
    [(game_code, round_number), ...]}."""
    counts = {c: 0 for c in _HOLE_CLASSES}
    total_holes = 0
    source_rounds: list[tuple[str, int]] = []
    for game_code, rounds in scorecards.items():
        if not isinstance(rounds, dict) or "error" in rounds:
            continue
        for round_number, round_data in rounds.items():
            holes = round_data.get("holes") or []
            if not holes:
                continue
            # Same int-normalization fix as compute_round_momentum
            # above (round_number can arrive as a string after a
            # PLAYER_PROFILE_RAW.json round-trip).
            source_rounds.append((game_code, int(round_number)))
            for hole in holes:
                cls = hole.get("class")
                if cls in counts:
                    counts[cls] += 1
                total_holes += 1
    double_bogey_plus = counts["Double Bogey"] + counts["Triple Bogey+"]
    avoidance_rate = (1 - double_bogey_plus / total_holes) if total_holes else None
    return {
        "counts": counts, "total_holes": total_holes,
        "double_bogey_avoidance_rate": avoidance_rate,
        "source_rounds": source_rounds,
    }


def compute_round_momentum(scorecards: dict) -> dict:
    """Real per-round strokes-relative-to-par trend across every
    successfully-collected game_code/round, in the order KLPGA's own
    response returned them (never re-sorted by any assumption about
    chronology this project has not independently verified for this
    specific set of rounds). Returns {"rounds": [{"game_code": str,
    "round": int, "total_strokes": float_or_None, "out_strokes":
    float_or_None, "in_strokes": float_or_None}, ...]}."""
    # BUG FIX (2026-10-04): JSON object keys are always strings -- a
    # round-trip through write_player_profile_raw()/
    # load_player_profile_raw() (PLAYER_PROFILE_RAW.json) turns
    # parse_score_detail_html()'s real int round-number keys into
    # strings ("1" instead of 1), which broke a later int comparison
    # in _round_momentum_v2_html (confirmed via a real TypeError on
    # the one real player with real collected rounds in this module's
    # own PLAYER_PROFILE_RAW.json evidence, the first time this
    # function ran against reloaded-from-disk data
    # rather than a freshly-parsed scorecard). Normalized to int here,
    # once, so every caller downstream (including a later JSON
    # round-trip) sees a real int, and so sorting by round number is
    # numeric, not lexicographic (string-sorting "10" before "2").
    rounds_out = []
    for game_code, rounds in scorecards.items():
        if not isinstance(rounds, dict) or "error" in rounds:
            continue
        normalized_rounds = {int(round_number): round_data for round_number, round_data in rounds.items()}
        for round_number, round_data in sorted(normalized_rounds.items()):
            rounds_out.append({
                "game_code": game_code, "round": round_number,
                "total_strokes": round_data.get("total_strokes"),
                "out_strokes": round_data.get("out_strokes"),
                "in_strokes": round_data.get("in_strokes"),
            })
    return {"rounds": rounds_out}


def write_player_profile_raw(
    player_id: str, player_name: str, season_detail: dict, scorecards: dict,
    *, content_root: Optional[Path] = None,
) -> Path:
    """Persist the real, unmerged collection output -- the project's
    own RAW evidence layer, kept separate from any derived/normalized
    shape so a future re-derivation never needs a re-fetch."""
    path = player_profile_raw_path(player_id, content_root=content_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "player_id": str(player_id), "player_name": player_name,
        "season_detail": season_detail, "scorecards": scorecards,
        "source": "klpga.collectors.player_profile (publicRecordSeasonDetail + scoreDetail)",
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_player_profile_raw(player_id: str, *, content_root: Optional[Path] = None) -> Optional[dict]:
    """Real doc in, or None if this player has no persisted
    PLAYER_PROFILE_RAW.json yet -- never a fabricated empty doc."""
    path = player_profile_raw_path(player_id, content_root=content_root)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def derive_player_dna(player_history_doc: dict) -> dict:
    """NEO Player History Engine V2's own "Player DNA" field -- a thin,
    honest re-exposure of the existing engine's own `career_dna`
    (already population-normalized by season, already generic per
    player_id), not a second, independently-computed classification.
    This project has no real tour-wide population baseline for the raw
    GIR/driving-distance/putts values collected by this module, so
    classifying a player's "type" from those raw numbers directly
    would be an unsupported, ad hoc judgment call -- `career_dna`'s own
    SG-percentile-based classification is the one real, already-
    verified basis this repository has for that question."""
    career_dna = player_history_doc.get("career_dna") or {}
    return {
        "foundation": career_dna.get("career_foundation"),
        "foundation_share_pct": career_dna.get("career_foundation_share_pct"),
        "most_consistent_component": career_dna.get("most_consistent_component"),
        "most_volatile_component": career_dna.get("most_volatile_component"),
        "fastest_growing_component": career_dna.get("fastest_growing_component"),
        "source": "derived from this player's own career_dna (existing engine, unchanged) -- "
                   "not a separate computation",
    }


def derive_course_fit_score(player_history_doc: dict) -> list[dict]:
    """NEO Player History Engine V2's own "Course Fit Score" field -- a
    thin, honest re-exposure of the existing engine's own
    `course_profile` (per-course real avg/best/worst SG Total, already
    generic per player_id). This project has no real, independently-
    verified field-wide course-difficulty baseline, so a "Course
    Difficulty x Player SG" composite score would require fabricating
    the difficulty term -- this function deliberately does not do
    that. Each entry's own `avg_sg_total` already IS this player's real
    fit at that course (her own performance there, relative to her own
    game, in SG terms); it is exposed under the new field name without
    an invented difficulty multiplier."""
    course_profile = player_history_doc.get("course_profile") or []
    return [
        {
            "course": row.get("tournament_family"),
            "appearances": row.get("appearances"),
            "avg_sg_total": row.get("avg_sg_total"),
            "best_sg_total": row.get("best_sg_total"),
            "worst_sg_total": row.get("worst_sg_total"),
            "difficulty_weighting": None,
            "note": "실제 필드 전체 대비 코스 난이도 기준선이 없어 난이도 가중치는 적용하지 않음 "
                    "(임의 계산 금지) -- avg_sg_total은 이 선수 본인의 실측 SG Total입니다.",
        }
        for row in course_profile
    ]


def enrich_player_history_doc(player_history_doc: dict, season_detail: dict, scorecards: dict) -> dict:
    """Return a NEW dict: every existing key in `player_history_doc`
    passed through unchanged, plus real new top-level keys --
    `official_detail_record`, `hole_distribution`, `round_momentum`,
    `player_dna`, `course_fit_score`. Never mutates the input dict.
    This is the one real "schema extension, not a new engine" seam
    this module exists to provide."""
    enriched = dict(player_history_doc)
    enriched["official_detail_record"] = season_detail["normalized"]
    enriched["hole_distribution"] = compute_hole_distribution(scorecards)
    enriched["round_momentum"] = compute_round_momentum(scorecards)
    enriched["player_dna"] = derive_player_dna(player_history_doc)
    enriched["course_fit_score"] = derive_course_fit_score(player_history_doc)
    return enriched


def run_official_detail_enrichment(
    player_id: str, player_name: str, *, season: str = "2026",
    game_codes: Optional[list[str]] = None, content_root: Optional[Path] = None,
    client: Optional[PoliteHttpClient] = None,
) -> dict:
    """Top-level orchestrator -- the one real entry point this module
    exists to provide:
        1. collect_official_season_detail (publicRecordSeasonDetail)
        2. collect_official_scorecards (scoreDetail, for each real
           game_code the caller supplies -- defaults to every
           `season`-year tournament already in this player's own
           reconciled PLAYER_HISTORY.json, never guessed)
        3. write_player_profile_raw (the raw evidence layer)
        4. read the existing PLAYER_HISTORY.json (already built by
           scripts/build_player_report.py -- this function never builds
           it itself, per this project's "extend, don't duplicate"
           rule), enrich it, write it back.
    Returns the enriched PLAYER_HISTORY.json dict. Raises
    FileNotFoundError if PLAYER_HISTORY.json does not exist yet for
    this player_id -- run scripts/build_player_report.py first."""
    from klpga.website_v2.player_provider import load_player_history, player_history_path

    client = client or PoliteHttpClient()
    history_doc = load_player_history(player_id)
    if history_doc is None:
        raise FileNotFoundError(
            f"no PLAYER_HISTORY.json for player_id={player_id} -- run "
            f"scripts/build_player_report.py --player-id {player_id} first"
        )

    if game_codes is None:
        game_codes = [
            t["game_code"] for t in history_doc.get("tournament_history", [])
            if str(t.get("season")) == str(season)
        ]

    season_detail = collect_official_season_detail(client, player_id, season)
    scorecards = collect_official_scorecards(client, player_id, player_name, game_codes)
    write_player_profile_raw(player_id, player_name, season_detail, scorecards, content_root=content_root)

    enriched = enrich_player_history_doc(history_doc, season_detail, scorecards)
    path = player_history_path(player_id)
    path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    return enriched


def reapply_cached_official_detail_enrichment(player_id: str, *, content_root: Optional[Path] = None) -> Optional[dict]:
    """BUG FIX (2026-10-04): scripts/build_10097_player_history.py's
    build() -- called by every scripts/build_player_report.py run --
    rebuilds PLAYER_HISTORY.json from the reconciled warehouses alone,
    with no knowledge of this module's enrichment. A rebuild after
    run_official_detail_enrichment() had already run therefore silently
    DELETED official_detail_record/hole_distribution/round_momentum/
    player_dna/course_fit_score from the file on disk -- confirmed via
    a real before/after SHA256 diff (PLAYER_HISTORY.json for
    a real reference player: 1711 lines changed, every V2 key gone) the first
    time scripts/build_player_report.py was re-run after a real
    enrichment pass.

    This function is the real, no-network fix: it re-reads this
    player's own already-persisted PLAYER_PROFILE_RAW.json (the raw
    evidence layer -- no new fetch, no network needed) and re-applies
    enrich_player_history_doc() to whatever PLAYER_HISTORY.json the
    reconciliation build just wrote, so the two steps can never drift
    apart again. Returns None (and changes nothing) when this player
    has no PLAYER_PROFILE_RAW.json yet -- a player never enriched stays
    exactly as before, never a fabricated/placeholder enrichment."""
    from klpga.website_v2.player_provider import load_player_history, player_history_path

    raw = load_player_profile_raw(player_id, content_root=content_root)
    if raw is None:
        return None
    history_doc = load_player_history(player_id)
    if history_doc is None:
        return None
    enriched = enrich_player_history_doc(history_doc, raw["season_detail"], raw["scorecards"])
    path = player_history_path(player_id)
    path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    return enriched
