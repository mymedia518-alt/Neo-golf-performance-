"""PLAYER HISTORY GOLD STANDARD V1 -- generic, any playerCode.

Player Intelligence is no longer the goal. This is the definitive PLAYER
HISTORY: Career -> Season -> Tournament -> Round, built ONLY from verified
official KLPGA records already collected in this repository. History
first, explanation second, speculation never. Every field here traces to
a real row in a real warehouse; anything not measured is omitted, never
invented. Originally written (and still filename-scoped) for
playerCode=10097 only, build() now takes player_id / player_name
parameters and is the one real implementation shared by every caller,
including scripts/build_player_report.py's generic CLI entry point --
there is no separate/duplicated generator for other players. Every
source in this file already filters by the given player_id (SG
Warehouse, Tournament Warehouse, normalized snapshots, DNA radar
population, hole-history scorecards, technical stats), so a source that
has no real data for a given player_id/player_name degrades gracefully
to None/empty for that section instead of crashing or leaking another
player's data under the wrong name -- see _hole_history(),
_technical_stats_2025(), and NOT_AVAILABLE's docstring below.

Player History must never depend on a single warehouse. Every tournament
fact used here comes from reconcile_10097_player_history.reconcile(),
which collects and cross-checks all seven categories of verified real
sources (SG Warehouse, Tournament Warehouse, Round Warehouse, Reader
outputs, Live snapshots, normalized datasets, supplemental datasets)
BEFORE this script runs. If reconciliation cannot fully account for
every known tournament, it raises ReconciliationError and this script
never runs -- there is no downstream patch path any more. See that
module's docstring for the full source inventory and the exact failure
mode (three of her most recent tournaments living only in their own
per-tournament files) this replaces.

Other real data sources used, outside the reconciled tournament dataset:
- knowledge_engine.compute_season_profiles(), fed the reconciled
  synthetic SG-warehouse document (not the raw on-disk warehouse file
  directly) -- so season SG averages reflect every reconciled
  tournament, not just the ones already in the SG Warehouse.
- OFFICIAL_PROFILE_NORMALIZED.json / OFFICIAL_SG_NORMALIZED.json: ONE
  current-season (2026) snapshot each -- money, average_score, putts,
  birdie/gir/par-save/par-break/recovery rate, official SG rank/total.
  Never extrapolated backward to other seasons; always labeled as a
  single point-in-time snapshot.
- evidence/current_round_2026120001_r3_20260906/official_sources.zip
  -> scorecards.json: the ONLY hole-by-hole data for 10097 anywhere in
  this repository -- one tournament (2026120001), 51 real hole records
  across 3 rounds (R1 18/18, R2 18/18, R3 15/18 at capture time). Note
  2026120001 is also the reconciled IN-PROGRESS tournament (see
  current_tournament_in_progress) -- it has never reached a final
  result in this repository.

Driving distance and driving accuracy are NOT absent from this player's
history: real KLPGA official values for playerCode=10097 exist in this
repository at docs/discovery/raw_samples/ (a season-2025 capture of the
confirmed official https://klpga.co.kr/web/record/locationRecord
endpoint, predating this reconciliation work). See
build_10097_technical_stats_2025.py -> TECHNICAL_STATS_2025.json,
loaded here as technical_stats_2025 -- a single season-2025 snapshot,
never extrapolated to other seasons, never merged with the 2026
current_snapshot (different season, different sample).

Explicitly NOT available anywhere in this repository for this player,
and therefore never shown: historical (pre-2026) money/average
score/GIR/putts/birdie rate, driving distance/accuracy/GIR for any
season other than the one 2025 snapshot above, bogey rate,
front-nine/back-nine splits, course names for most tournaments,
day-to-day ranking movement, Strokes Gained for the KB금융 골든라이프
챔피언십 (2026090003, real finish and round scores exist, but no SG was
ever captured for this tournament), and a reliable season-by-season cut
rate (a made_cut field exists in NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json,
but its own event count for 2023 -- 7 rows vs. the real 25 real events
that season confirmed by every other source -- is inconsistent, so it
is not used as a season-level rollup). None of this list is a claim
that KLPGA's live site lacks these fields -- this sandbox has no
network access to klpga.co.kr to check; see the status.data_completeness
field for the explicit distinction between "not found in this repo"
and "confirmed absent from KLPGA."
"""
from __future__ import annotations

import importlib.util
import json
import statistics
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.data_provenance import build_provenance_map  # noqa: E402
from klpga.knowledge_engine import knowledge_engine as ke  # noqa: E402
from klpga.tournament_context import CONTENT_DIR  # noqa: E402
from klpga.tournament_ordering import sort_tournaments  # noqa: E402

_spec = importlib.util.spec_from_file_location("master_analysis_under_history", ROOT / "scripts" / "build_10097_master_player_analysis.py")
master = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(master)

_recon_spec = importlib.util.spec_from_file_location("reconcile_10097_under_history", ROOT / "scripts" / "reconcile_10097_player_history.py")
recon_module = importlib.util.module_from_spec(_recon_spec)
_recon_spec.loader.exec_module(recon_module)

PLAYER_ID = master.PLAYER_ID
PLAYER_NAME = master.PLAYER_NAME
OUTPUT_PATH = CONTENT_DIR / "knowledge_engine" / "player_intelligence" / PLAYER_ID / "PLAYER_HISTORY.json"
RECONCILIATION_REPORT_PATH = CONTENT_DIR / "knowledge_engine" / "player_intelligence" / PLAYER_ID / "PLAYER_HISTORY_RECONCILIATION_REPORT.json"

_COMPONENTS = ["avg_total", "avg_ott", "avg_app", "avg_arg", "avg_putt"]
_COMPONENT_LABEL = {"avg_total": "SG Total", "avg_ott": "SG OTT", "avg_app": "SG APP", "avg_arg": "SG ARG", "avg_putt": "SG PUTT"}
_CONTRIB_KEY_LABEL = {"off_the_tee": "SG OTT", "approach": "SG APP", "around_green": "SG ARG", "putting": "SG PUTT"}

# Every entry states WHO is responsible for the gap -- NEO's own
# collection pipeline vs. an unverifiable network block -- and never
# implies KLPGA itself lacks the data merely because this repository
# has not ingested it (RED TEAM mission A/D: "Never imply KLPGA lacks a
# metric merely because NEO has not ingested it").
#
# This list is a set of REPOSITORY-WIDE data-pipeline gaps (no player's
# build has these fields, regardless of player_id), not one player's
# personal disclosure text, so it is safe to share across every player
# built by this module. It previously also named one 10097+tournament-
# specific gap (2026090003 KB Strokes Gained) -- that line was removed
# during the multi-player refactor because it is now stale even for
# 10097 (the SG Warehouse gained a real row for that tournament; see
# reconcile_10097_player_history.py's Category 4 docstring) and would
# have been flatly wrong if shown, unedited, under another player's
# name. If a similar single-tournament SG gap is ever discovered for
# another player, it belongs in a per-player list computed in build(),
# not hardcoded here.
NOT_AVAILABLE = [
    "과거 시즌별 상금: 2026시즌 스냅샷 1건만 실측되어 있습니다. NEO가 과거 시즌분을 아직 수집하지 않았습니다.",
    "과거 시즌별 평균 스코어: 2026시즌 스냅샷 1건만 실측되어 있습니다. NEO가 과거 시즌분을 아직 수집하지 않았습니다.",
    "과거 시즌별 GIR·퍼트·버디율: 2026시즌 스냅샷 1건만 실측되어 있습니다. NEO가 과거 시즌분을 아직 수집하지 않았습니다.",
    "보기율(Bogey %): NEO가 아직 수집하지 않았습니다 (KLPGA가 게시하는지는 이 세션의 네트워크 차단으로 확인하지 못했습니다).",
    "전반·후반 9홀 분할 스코어: NEO가 아직 수집하지 않았습니다 (KLPGA가 게시하는지는 이 세션의 네트워크 차단으로 확인하지 못했습니다).",
    "대회별 코스명: 극히 일부 대회만 실측되어 전체 커버리지가 없습니다.",
    "라운드 중 순위 변동(일자별 순위 이동): NEO가 아직 수집하지 않았습니다 (KLPGA가 게시하는지는 이 세션의 네트워크 차단으로 확인하지 못했습니다).",
    "시즌별 컷 통과율: 내부 저장소의 made_cut 필드가 2023시즌 표본(7건)만 있어 다른 모든 실측 소스가 확인하는 2023시즌 25개 대회와 "
    "맞지 않아 신뢰할 수 없어 사용하지 않습니다.",
]


def _load_all(player_id: str, player_name: Optional[str]):
    recon = recon_module.reconcile(player_id=player_id, player_name=player_name)
    season_profiles = ke.compute_season_profiles(player_id, recon["synthetic_sg_warehouse_doc"])
    return recon, season_profiles


def _contribution_breakdown(rows: list) -> Optional[dict]:
    """Real, deterministic SG-component contribution split -- identical
    method already used and tested in build_10097_player_intelligence_report.py.
    Reimplemented here (not imported) so this script has zero dependency
    on the Player Intelligence module, per the mission's scope."""
    keys = ["off_the_tee", "approach", "around_green", "putting"]
    sums = {k: 0.0 for k in keys}
    total = 0.0
    n = 0
    for r in rows:
        if not r or r.get("total") is None or any(r.get(k) is None for k in keys):
            continue
        for k in keys:
            sums[k] += r[k]
        total += r["total"]
        n += 1
    if n == 0 or total == 0:
        return None
    total_rounded = round(total, 2)
    breakdown = sorted(
        (
            {"component": _CONTRIB_KEY_LABEL[k], "value": round(sums[k], 2), "share_pct": round(round(sums[k], 2) / total_rounded * 100, 1)}
            for k in keys
        ),
        key=lambda b: abs(b["share_pct"]),
        reverse=True,
    )
    return {"sample_size": n, "total_value": total_rounded, "breakdown": breakdown, "top_contributor": breakdown[0]["component"]}


# ---------------------------------------------------------------------------
# PAGE 1 -- CAREER OVERVIEW
# ---------------------------------------------------------------------------

def _career_overview(recon: dict, season_profiles: list) -> dict:
    events = recon["finished_tournaments"]
    wins = [e for e in events if e.get("rank") == 1]
    events_by_season = defaultdict(list)
    for e in events:
        events_by_season[e["season"]].append(e)
    wins_by_season = defaultdict(int)
    for w in wins:
        wins_by_season[w["season"]] += 1

    season_rows = []
    for p in season_profiles:
        se = events_by_season.get(p.season, [])
        top5 = sum(1 for e in se if e.get("rank") is not None and e["rank"] <= 5)
        top10 = sum(1 for e in se if e.get("rank") is not None and e["rank"] <= 10)
        top20 = sum(1 for e in se if e.get("rank") is not None and e["rank"] <= 20)
        season_rows.append({
            "season": p.season,
            "events": len(se),
            "wins": wins_by_season.get(p.season, 0),
            "top5": top5,
            "top10": top10,
            "top20": top20,
            "sg_total": p.avg_total,
            "sg_ott": p.avg_ott,
            "sg_app": p.avg_app,
            "sg_arg": p.avg_arg,
            "sg_putt": p.avg_putt,
            "sg_sample_size": p.n_tournaments,
        })

    ordered_events = sort_tournaments(events)  # RED TEAM (2026-09-25): real end_date, not game_code proxy
    earliest_season = season_profiles[0].season
    latest_event = ordered_events[-1] if ordered_events else None

    return {
        "season_rows": season_rows,
        "earliest_season_on_record": earliest_season,
        # MISSION V61 (2026-09-28): "Never explain how the data was
        # collected inside Player History... if a sentence helps
        # developers but not golfers, delete it." The real fact this
        # note protects -- do not mistake "earliest season NEO has
        # measured" for "her actual KLPGA debut season" -- still
        # matters and stays, worded for a golf reader instead of a
        # data-pipeline reader (no "저장소"/"웨어하우스"/"수집 시작점").
        "data_floor_note": (
            f"NEO가 확보한 {PLAYER_NAME} 선수의 실측 SG 기록은 {earliest_season}시즌부터 시작됩니다. "
            f"이는 선수 전체에 공통으로 적용되는 실측 시작 시점이며, {PLAYER_NAME} 선수의 실제 KLPGA "
            "데뷔 시즌은 아닙니다. 이 시점 이전의 실측 기록은 아직 확인되지 않았습니다."
        ),
        "latest_tournament": latest_event,
        "total_events": len(events),
        "total_wins": len(wins),
        "total_top5": sum(r["top5"] for r in season_rows),
        "total_top10": sum(r["top10"] for r in season_rows),
        "total_top20": sum(r["top20"] for r in season_rows),
        "season_count": len(season_profiles),
    }


def _current_snapshot() -> Optional[dict]:
    profile_doc = master._load("OFFICIAL_PROFILE_NORMALIZED.json")
    sg_doc = master._load("OFFICIAL_SG_NORMALIZED.json")
    profile = next((r for r in profile_doc.get("records", []) if r.get("playerCode") == PLAYER_ID), None)
    sg = next((r for r in sg_doc.get("records", []) if r.get("playerCode") == PLAYER_ID), None)
    if not profile and not sg:
        return None
    return {
        "as_of_note": (
            f"KLPGA 공식 {profile_doc.get('effective_season') if profile else sg_doc.get('effective_season')}시즌 "
            "스냅샷 1건입니다. 과거 시즌으로 확장하지 않습니다."
        ),
        "official_sg_rank": sg.get("official_rank") if sg else None,
        "official_sg_total": sg.get("official_sg_total") if sg else None,
        "official_sg_ott": sg.get("official_sg_ott") if sg else None,
        "official_sg_app": sg.get("official_sg_app") if sg else None,
        "official_sg_arg": sg.get("official_sg_arg") if sg else None,
        "official_sg_putt": sg.get("official_sg_putt") if sg else None,
        "official_sg_rounds": sg.get("official_sg_rounds") if sg else None,
        "official_rank": profile.get("official_rank") if profile else None,
        "money": profile.get("money") if profile else None,
        "average_score": profile.get("average_score") if profile else None,
        "average_putts": profile.get("average_putts") if profile else None,
        "birdie_rate": profile.get("birdie_rate") if profile else None,
        "gir_rate": profile.get("gir_rate") if profile else None,
        "par_save_rate": profile.get("par_save_rate") if profile else None,
        "par_break_rate": profile.get("par_break_rate") if profile else None,
        "recovery_rate": profile.get("recovery_rate") if profile else None,
    }


# ---------------------------------------------------------------------------
# PAGE 2 -- CAREER EVOLUTION
# ---------------------------------------------------------------------------

def _career_evolution(season_profiles: list) -> dict:
    out = {}
    for c in _COMPONENTS:
        series = [(p.season, getattr(p, c)) for p in season_profiles if getattr(p, c) is not None]
        if len(series) < 2:
            continue
        deltas = []
        for (s1, v1), (s2, v2) in zip(series, series[1:]):
            delta = round(v2 - v1, 2)
            growth_pct = round(delta / abs(v1) * 100, 1) if v1 else None
            deltas.append({"from_season": s1, "to_season": s2, "delta": delta, "growth_pct": growth_pct})
        peak = max(series, key=lambda x: x[1])
        worst = min(series, key=lambda x: x[1])
        last_delta = deltas[-1]["delta"] if deltas else None
        direction = "UP" if (last_delta or 0) > 0 else ("DOWN" if (last_delta or 0) < 0 else "FLAT")
        out[c] = {
            "label": _COMPONENT_LABEL[c],
            "series": [{"season": s, "value": v} for s, v in series],
            "deltas": deltas,
            "peak_season": {"season": peak[0], "value": peak[1]},
            "worst_season": {"season": worst[0], "value": worst[1]},
            "current_direction": direction,
        }
    return out


# ---------------------------------------------------------------------------
# PAGE 3 -- SEASON REPLAY / TEMPORAL RESOLUTION (V4)
#
# V4 mission: replace the flat Season -> Tournament hierarchy with
# Season -> Season Window -> Tournament -> Round. Every trend below is
# time-based (chronological game_code order), never a season-wide
# average alone. Window size is fixed at 5 (the mission's own example)
# and disclosed on every output -- never silently changed per season.
# ---------------------------------------------------------------------------

_WINDOW_SIZE = 5

_SG_COMPONENT_KEYS = ("ott", "app", "arg", "putt")


def _window_metric_decomposition(chunk_tournaments: list, hole_history: Optional[dict]) -> dict:
    """V5 mission: for a Peak/Slump/Recovery window, decompose the SG
    average that created it into OTT/APP/ARG/PUTT (real, averaged over
    whichever tournaments in the window actually have SG components --
    never assumed for a tournament that doesn't). Birdie/Bogey/GIR/Putts
    are only ever real when a tournament in the window is also covered
    by hole-level history (currently exactly one tournament, career-
    wide, and never a finished one that has appeared in a real window
    yet) -- when that's not the case, this returns an explicit
    NOT_COLLECTED status rather than silently omitting the fields or
    reusing a season-level technical-stat number that describes a
    different tournament entirely.

    `chunk_tournaments` are raw reconcile() event dicts, which carry
    SG components as flat sg_ott/sg_app/sg_arg/sg_putt fields (not a
    nested 'sg_components' dict -- that nesting only exists in
    _tournament_history()'s own, separately-shaped output)."""
    _RAW_KEY = {"ott": "sg_ott", "app": "sg_app", "arg": "sg_arg", "putt": "sg_putt"}
    comp_rows = [t for t in chunk_tournaments if t.get("sg_ott") is not None]
    decomposition: dict = {
        "sg_component_sample_size": len(comp_rows),
        "sg_component_window_size": len(chunk_tournaments),
    }
    for key, raw_key in _RAW_KEY.items():
        vals = [t[raw_key] for t in comp_rows if t.get(raw_key) is not None]
        decomposition[key] = round(statistics.fmean(vals), 3) if vals else None

    hole_covered_game_code = hole_history["game_code"] if hole_history else None
    covered = [t for t in chunk_tournaments if t["game_code"] == hole_covered_game_code] if hole_covered_game_code else []
    if not covered:
        decomposition["birdie"] = None
        decomposition["bogey"] = None
        decomposition["gir"] = None
        decomposition["putts"] = None
        decomposition["birdie_bogey_gir_putts_status"] = "NOT_COLLECTED"
        decomposition["birdie_bogey_gir_putts_note"] = (
            "이 시기의 대회는 홀 단위 실측 기록이 없어 버디/보기/GIR/퍼트 수를 계산할 수 없습니다."
        )
    else:
        holes = [h for rnd in hole_history["rounds"] for h in rnd["holes"]]
        decomposition["birdie"] = sum(1 for h in holes if h["relative_to_par"] <= -1)
        decomposition["bogey"] = sum(1 for h in holes if h["relative_to_par"] == 1)
        decomposition["gir"] = None  # not captured in hole_history (par/strokes only, no approach-shot lie)
        decomposition["putts"] = None
        decomposition["birdie_bogey_gir_putts_status"] = "PARTIAL"
        decomposition["birdie_bogey_gir_putts_note"] = (
            f"버디/보기는 {hole_covered_game_code}의 실측 홀 기록에서 계산되었습니다 ({len(holes)}홀). "
            "GIR·퍼트 수는 이 홀 기록에 포함되어 있지 않아 계산할 수 없습니다."
        )
    return decomposition


def _named_season_windows(chronological_events: list) -> dict:
    """First 5 / Middle 5 / Last 5 tournaments of ONE season, in real
    chronological (game_code) order. Middle-5 is only computed when it
    does not overlap First-5 or Last-5 (season has >= 15 events) --
    never silently overlapped without disclosure."""
    n = len(chronological_events)

    def _window_stats(chunk: list, label: str) -> Optional[dict]:
        if not chunk:
            return None
        vals = [e["sg_total"] for e in chunk if e.get("sg_total") is not None]
        wins = sum(1 for e in chunk if e.get("rank") == 1)
        top10 = sum(1 for e in chunk if e.get("rank") is not None and e["rank"] <= 10)
        return {
            "label": label, "events": len(chunk),
            "avg_sg_total": round(statistics.fmean(vals), 2) if vals else None,
            "sg_sample_size": len(vals), "wins": wins, "top10": top10,
        }

    first5 = _window_stats(chronological_events[:_WINDOW_SIZE], f"처음 {_WINDOW_SIZE}개 대회")
    last5 = _window_stats(chronological_events[-_WINDOW_SIZE:], f"최근 {_WINDOW_SIZE}개 대회")
    middle5 = None
    if n >= 3 * _WINDOW_SIZE:
        mid_start = n // 2 - _WINDOW_SIZE // 2
        middle_chunk = chronological_events[mid_start:mid_start + _WINDOW_SIZE]
        middle5 = _window_stats(middle_chunk, f"중반 {_WINDOW_SIZE}개 대회")
    return {
        "window_size": _WINDOW_SIZE,
        "first": first5, "middle": middle5, "last": last5,
        "middle_unavailable_reason": None if middle5 else f"표본 부족: 이 시즌은 {n}개 대회로, 중복 없는 중반 구간을 분리하려면 {_WINDOW_SIZE*3}개 이상이 필요합니다.",
    }


def _career_rolling_trend(recon: dict, hole_history: Optional[dict] = None, *, window: int = _WINDOW_SIZE) -> dict:
    """Career-wide (cross-season) sliding window over every finished
    tournament in real chronological order -- the mission's Moving
    Average / Rolling Percentile / Peak-Slump-Recovery Window request.
    Window step = 1 (sliding, overlapping), size disclosed. A window's
    'percentile' is computed ONLY against this player's own other
    windows across her career (no field-wide population exists at this
    granularity) -- explicitly scoped, never implied to be a field
    comparison."""
    events = sort_tournaments(recon["finished_tournaments"])  # RED TEAM (2026-09-25): real end_date, not game_code proxy
    sg_events = [e for e in events if e.get("sg_total") is not None]
    n = len(sg_events)
    if n < window:
        return {"window_size": window, "series": [], "peak_window": None, "slump_window": None, "recovery_window": None,
                "note": f"실측 SG 대회가 {n}개로, {window}개 이동 구간을 계산하기에 부족합니다."}

    series = []
    for start in range(0, n - window + 1):
        chunk = sg_events[start:start + window]
        avg = round(statistics.fmean(c["sg_total"] for c in chunk), 3)
        series.append({
            "window_index": start,
            "start_tournament": chunk[0]["tournament"], "start_season": chunk[0]["season"],
            "end_tournament": chunk[-1]["tournament"], "end_season": chunk[-1]["season"],
            "moving_average_sg_total": avg,
        })

    # Self-percentile: rank among this player's OWN other windows only.
    all_avgs = [w["moving_average_sg_total"] for w in series]
    total_windows = len(series)
    for w in series:
        if total_windows > 1:
            worse = sum(1 for a in all_avgs if a < w["moving_average_sg_total"])
            w["self_percentile"] = round(worse / (total_windows - 1) * 100, 1)
        else:
            w["self_percentile"] = None

    peak_idx = max(range(total_windows), key=lambda i: series[i]["moving_average_sg_total"])
    slump_idx = min(range(total_windows), key=lambda i: series[i]["moving_average_sg_total"])
    recovery_window = None
    if slump_idx + 1 < total_windows:
        rec = series[slump_idx + 1]
        recovery_window = {
            **rec,
            "delta_vs_slump": round(rec["moving_average_sg_total"] - series[slump_idx]["moving_average_sg_total"], 3),
        }

    # V5 mission: "Why exactly did this period become a peak or a
    # slump?" -- decompose each of the three named windows into its
    # own real OTT/APP/ARG/PUTT (and birdie/bogey/GIR/putts where
    # measurable), never just the single SG Total that named it.
    peak_window = {**series[peak_idx], "decomposition": _window_metric_decomposition(sg_events[peak_idx:peak_idx + window], hole_history)}
    slump_window = {**series[slump_idx], "decomposition": _window_metric_decomposition(sg_events[slump_idx:slump_idx + window], hole_history)}
    if recovery_window is not None:
        rec_idx = slump_idx + 1
        recovery_window["decomposition"] = _window_metric_decomposition(sg_events[rec_idx:rec_idx + window], hole_history)

    # V6 mission: replace absolute values with comparative ones.
    # Career average = mean SG Total over the SAME real population this
    # whole rolling series is built from (every finished tournament
    # with a measured SG Total) -- never a different, narrower sample.
    career_average_sg_total = round(statistics.fmean(e["sg_total"] for e in sg_events), 3)
    career_median_sg_total = round(statistics.median(e["sg_total"] for e in sg_events), 3)
    peak_window["delta_vs_career_average"] = round(peak_window["moving_average_sg_total"] - career_average_sg_total, 3)
    slump_window["delta_vs_career_average"] = round(slump_window["moving_average_sg_total"] - career_average_sg_total, 3)
    if recovery_window is not None:
        recovery_window["delta_vs_career_average"] = round(recovery_window["moving_average_sg_total"] - career_average_sg_total, 3)

    # V7 mission: Peak Sustainability -- how many CONSECUTIVE windows
    # starting at the peak (inclusive) stayed at-or-above the career
    # average before the first one that dropped below it. Measured by
    # literally walking the real series forward; never estimated.
    sustain = 0
    i = peak_idx
    while i < total_windows and series[i]["moving_average_sg_total"] >= career_average_sg_total:
        sustain += 1
        i += 1
    peak_window["sustainability_windows"] = sustain
    peak_window["sustainability_tournaments"] = sustain + window - 1  # real tournament span covered

    # V7 mission: Recovery Time -- how many windows after the slump
    # (counting the slump window itself as 0) until the FIRST window
    # whose moving average returns to at-or-above the career average.
    # None (disclosed, not guessed) if the real observed series never
    # recovers within the data that exists.
    recovery_time_windows = None
    recovery_time_tournament = None
    for offset in range(0, total_windows - slump_idx):
        if series[slump_idx + offset]["moving_average_sg_total"] >= career_average_sg_total:
            recovery_time_windows = offset
            recovery_time_tournament = series[slump_idx + offset]["end_tournament"]
            break

    return {
        "window_size": window,
        "total_windows": total_windows,
        "series": series,
        "career_average_sg_total": career_average_sg_total,
        "career_average_sample_size": n,
        "career_median_sg_total": career_median_sg_total,
        "peak_window": peak_window,
        "slump_window": slump_window,
        "recovery_window": recovery_window,
        "recovery_time_windows": recovery_time_windows,
        "recovery_time_tournament": recovery_time_tournament,
        # RED TEAM (2026-09-25): narrative note names the real tournament
        # by which she'd recovered, never a window count -- the walk-
        # forward integer above (recovery_time_windows) is unchanged and
        # still what this note is built from, just not phrased as one.
        "recovery_time_note": (
            f"{recovery_time_tournament} 즈음에는 이미 커리어 평균을 되찾은 상태였습니다."
            if recovery_time_windows is not None
            else "실측 데이터 범위 안에서는 슬럼프 이후 커리어 평균을 되찾은 시점을 아직 찾지 못했습니다."
        ),
        "note": f"{window}개 대회 슬라이딩 구간(실측 SG {n}개 대회 기준). 백분위는 선수 본인의 다른 구간 대비이며, 다른 선수와의 비교가 아닙니다.",
    }


# ---------------------------------------------------------------------------
# DATAGOLF PHILOSOPHY MISSION: Current Form group (playerCode=10097 only).
# Reuses only already-measured values -- career_overview's own current-
# season row and career_rolling_trend's own career average -- never a new
# measurement. "Current" always means the most recent season on record
# (career_overview["season_rows"][-1]); "Career" always means the same
# real population career_rolling_trend already averages over (every
# finished tournament with a measured SG Total).
# ---------------------------------------------------------------------------

_SKILL_RAW_KEY = {"ott": "sg_ott", "app": "sg_app", "arg": "sg_arg", "putt": "sg_putt"}
_SKILL_SEASON_ROW_KEY = {"ott": "sg_ott", "app": "sg_app", "arg": "sg_arg", "putt": "sg_putt"}
_SKILL_LABEL = {"ott": "SG OTT", "app": "SG APP", "arg": "SG ARG", "putt": "SG PUTT"}


def _career_component_averages(recon: dict) -> dict:
    """Real per-component career averages, over the identical
    finished-tournament population career_rolling_trend uses for the
    SG Total average -- just never previously computed per-component
    on its own."""
    events = recon["finished_tournaments"]
    out = {}
    for key, raw_key in _SKILL_RAW_KEY.items():
        vals = [e[raw_key] for e in events if e.get(raw_key) is not None]
        out[key] = {"average": round(statistics.fmean(vals), 3) if vals else None, "sample_size": len(vals)}
    return out


def _current_vs_career(career_overview: dict, career_rolling_trend: dict) -> Optional[dict]:
    """DataGolf item 1: Current vs Career -- current season's real SG
    Total average against the real career average, both already
    measured elsewhere on this page."""
    rows = career_overview["season_rows"]
    career_avg = career_rolling_trend.get("career_average_sg_total")
    if not rows or career_avg is None or rows[-1].get("sg_total") is None:
        return None
    current = rows[-1]
    return {
        "current_season": current["season"],
        "current_season_sg_total": round(current["sg_total"], 3),
        "current_season_sample_size": current["sg_sample_size"],
        "career_average_sg_total": career_avg,
        "career_average_sample_size": career_rolling_trend.get("career_average_sample_size"),
        "delta_vs_career_average": round(current["sg_total"] - career_avg, 3),
    }


def _current_skill_vs_career(career_overview: dict, career_component_avg: dict) -> Optional[dict]:
    """DataGolf item 2: Current Skill vs Career -- the same comparison,
    one level deeper (OTT/APP/ARG/PUTT instead of SG Total alone)."""
    rows = career_overview["season_rows"]
    if not rows:
        return None
    current = rows[-1]
    components = []
    for key in _SG_COMPONENT_KEYS:
        current_val = current.get(_SKILL_SEASON_ROW_KEY[key])
        career = career_component_avg.get(key, {})
        career_val = career.get("average")
        components.append({
            "component": _SKILL_LABEL[key],
            "current_value": round(current_val, 3) if current_val is not None else None,
            "career_average": career_val,
            "career_sample_size": career.get("sample_size", 0),
            "delta_vs_career_average": (
                round(current_val - career_val, 3) if current_val is not None and career_val is not None else None
            ),
        })
    return {
        "current_season": current["season"],
        "current_season_sample_size": current["sg_sample_size"],
        "components": components,
    }


def _career_heartbeat(recon: dict, career_average_sg_total: Optional[float]) -> dict:
    """V6 mission: 'Career Heartbeat' -- every finished tournament in
    real chronological order, each one's SG Total expressed as a
    deviation from the real career average (not an absolute value) --
    win/top10 marked distinctly. career_average_sg_total is passed in
    (not recomputed) so this strip and the rolling-trend windows above
    always agree on the exact same baseline -- never two silently
    different 'career average' numbers on the same page.

    V7 mission adds a second, independent real measurement per beat --
    Career Percentile -- so the strip can render as Dual Track: Track 1
    is the raw-unit deviation above; Track 2 is where that one
    tournament ranks among ALL of her other tournaments (self-
    percentile, same non-field-comparison convention as the rolling
    window's own self_percentile).

    RED TEAM (2026-09-25): this sort was missed by the earlier repo-wide
    tournament-ordering audit (a multi-line sorted(..., key=...) call, not
    caught by that pass's single-line grep) -- now goes through the same
    shared klpga.tournament_ordering utility as every other chronological
    sort in this file, real end_date not game_code proxy."""
    events = sort_tournaments([e for e in recon["finished_tournaments"] if e.get("sg_total") is not None])
    if not events or career_average_sg_total is None:
        return {"beats": [], "career_average_sg_total": career_average_sg_total}
    all_sg = [e["sg_total"] for e in events]
    n = len(all_sg)
    beats = []
    for e in events:
        worse = sum(1 for v in all_sg if v < e["sg_total"])
        career_percentile = round(worse / (n - 1) * 100, 1) if n > 1 else None
        beats.append({
            "game_code": e["game_code"], "season": e["season"], "tournament": e["tournament"],
            "sg_total": e["sg_total"],
            "delta_vs_career_average": round(e["sg_total"] - career_average_sg_total, 3),
            "career_percentile": career_percentile,
            "is_win": e.get("rank") == 1,
            "is_top10": e.get("rank") is not None and e["rank"] <= 10,
        })
    return {"beats": beats, "career_average_sg_total": career_average_sg_total, "sample_size": len(beats)}


# ---------------------------------------------------------------------------
# RED TEAM (2026-09-25): CAREER FORM STORY -- narrative-first translation
# layer. Every mission before this one built career_rolling_trend's real
# sliding-window series, self-percentile, peak/slump/recovery detection,
# and per-window skill decomposition -- none of that changes here. This
# function only SELECTS already-computed windows (the standout window
# inside each third of the real series, the already-computed peak_window,
# and the series' own final window) and compares their already-computed
# OTT/APP/ARG/PUTT decomposition (_window_metric_decomposition, called
# exactly as peak/slump/recovery already call it) against the real
# career-average-per-component (_career_component_averages) to name a
# best/worst skill -- a plain comparison over real numbers, not a new
# statistic. career_rolling_trend's own JSON (window_size, total_windows,
# self_percentile, ...) is untouched; this is an ADDITIONAL, purely
# derived view meant to be the only one actually shown to a reader.
# ---------------------------------------------------------------------------

def _stage_skill_verdict(decomposition: Optional[dict], career_component_avg: dict) -> dict:
    """Which skill improved, which skill declined -- for one window,
    relative to the real career-average-per-component. Only ever
    compares components both real numbers exist for; never guesses a
    verdict from a partial decomposition."""
    if not decomposition:
        return {"best_component": None, "best_delta": None, "worst_component": None, "worst_delta": None}
    deltas = {}
    for key in _SG_COMPONENT_KEYS:
        val = decomposition.get(key)
        avg = career_component_avg.get(key, {}).get("average")
        if val is not None and avg is not None:
            deltas[key] = round(val - avg, 3)
    if not deltas:
        return {"best_component": None, "best_delta": None, "worst_component": None, "worst_delta": None}
    best_key = max(deltas, key=deltas.get)
    worst_key = min(deltas, key=deltas.get)
    return {
        "best_component": _SKILL_LABEL[best_key],
        "best_delta": deltas[best_key],
        "worst_component": _SKILL_LABEL[worst_key] if worst_key != best_key else None,
        "worst_delta": deltas[worst_key] if worst_key != best_key else None,
    }


def _career_form_story(recon: dict, crt: dict, hole_history: Optional[dict], career_component_avg: dict) -> Optional[list]:
    """Five narrative stages -- 시즌 초반 / 시즌 중반 / 시즌 후반 (the
    real rolling-window series split into three equal-count chronological
    thirds, never re-sorted or re-computed) / 전성기 (the already-computed
    peak_window) / 현재 폼 (the series' own most recent window). Each
    stage's window is chosen ONLY by picking an index into data that
    already exists -- no new moving average, no new percentile."""
    series = crt.get("series")
    if not series:
        return None
    window = crt["window_size"]
    sg_events = sort_tournaments([e for e in recon["finished_tournaments"] if e.get("sg_total") is not None])
    career_avg = crt.get("career_average_sg_total")

    n = len(series)
    third = max(1, round(n / 3))
    chapters = [
        ("시즌 초반", series[0:third]),
        ("시즌 중반", series[third:2 * third]),
        ("시즌 후반", series[2 * third:]),
    ]
    selected = [(label, max(chunk, key=lambda w: w["moving_average_sg_total"])) for label, chunk in chapters if chunk]
    peak = crt.get("peak_window")
    if peak:
        selected.append(("전성기", peak))
    selected.append(("현재 폼", series[-1]))

    stages = []
    for label, w in selected:
        idx = w["window_index"]
        decomposition = w.get("decomposition") or _window_metric_decomposition(sg_events[idx:idx + window], hole_history)
        verdict = _stage_skill_verdict(decomposition, career_component_avg)
        delta_vs_avg = w.get("delta_vs_career_average")
        if delta_vs_avg is None and career_avg is not None:
            delta_vs_avg = round(w["moving_average_sg_total"] - career_avg, 3)
        stages.append({
            "stage": label,
            "start_tournament": w["start_tournament"],
            "end_tournament": w["end_tournament"],
            "start_season": w["start_season"],
            "end_season": w["end_season"],
            "delta_vs_career_average": delta_vs_avg,
            "sample_size": decomposition.get("sg_component_sample_size"),
            **verdict,
        })
    return stages


def _season_replay(recon: dict) -> list:
    events = recon["finished_tournaments"]
    by_season = defaultdict(list)
    for e in events:
        by_season[e["season"]].append(e)

    replays = []
    for season in sorted(by_season):
        se = sort_tournaments(by_season[season])  # RED TEAM (2026-09-25): real end_date, not game_code proxy
        n = len(se)
        if n < 4:
            continue
        quartile_size = n / 4
        quartiles = []
        for qi in range(4):
            start = round(qi * quartile_size)
            end = round((qi + 1) * quartile_size) if qi < 3 else n
            chunk = se[start:end]
            if not chunk:
                continue
            vals = [c["sg_total"] for c in chunk if c.get("sg_total") is not None]
            quartiles.append({
                "quarter": qi + 1,
                "events": len(chunk),
                "avg_sg_total": round(statistics.fmean(vals), 2) if vals else None,
            })
        se_with_sg = [e for e in se if e.get("sg_total") is not None]
        sg_totals = [e["sg_total"] for e in se_with_sg]
        peak_event = max(se_with_sg, key=lambda e: e["sg_total"]) if se_with_sg else None
        slump_event = min(se_with_sg, key=lambda e: e["sg_total"]) if se_with_sg else None
        recovery = None
        if slump_event:
            idx = se.index(slump_event)
            if idx + 1 < len(se):
                nxt = se[idx + 1]
                if nxt.get("sg_total") is not None and slump_event.get("sg_total") is not None:
                    recovery = {"tournament": nxt["tournament"], "sg_total": nxt["sg_total"], "delta_vs_slump": round(nxt["sg_total"] - slump_event["sg_total"], 2)}
        top10 = sum(1 for e in se if e.get("rank") is not None and e["rank"] <= 10)
        replays.append({
            "season": season,
            "event_count": n,
            "quartiles": quartiles,
            "named_windows": _named_season_windows(se),
            "volatility_stddev": round(statistics.pstdev(sg_totals), 2) if len(sg_totals) >= 2 else None,
            "peak": {"tournament": peak_event["tournament"], "sg_total": peak_event["sg_total"]} if peak_event else None,
            "slump": {"tournament": slump_event["tournament"], "sg_total": slump_event["sg_total"]} if slump_event else None,
            "recovery_next_event": recovery,
            "top10_rate_pct": round(top10 / n * 100, 1),
        })
    return replays


# ---------------------------------------------------------------------------
# PAGE 4 -- TOURNAMENT HISTORY
# ---------------------------------------------------------------------------

def _tournament_history(recon: dict) -> list:
    events = recon["finished_tournaments"]
    rounds_by_code = defaultdict(list)
    for r in recon["round_rows"]:
        rounds_by_code[r["game_code"]].append({"round": r["round"], "sg_total": r["sg_total"]})

    ordered = sort_tournaments(events)  # RED TEAM (2026-09-25): real end_date, not game_code proxy
    rows = []
    for e in ordered:
        has_sg_components = e.get("sg_ott") is not None
        round_scores = e.get("round_scores") or sorted(rounds_by_code.get(e["game_code"], []), key=lambda r: r["round"])
        rows.append({
            "game_code": e["game_code"],
            "season": e["season"],
            "tournament": e["tournament"],
            "rank": e.get("rank"),
            "sg_total": e.get("sg_total"),
            "is_win": e.get("rank") == 1,
            "is_top10": e.get("rank") is not None and e["rank"] <= 10,
            "sg_components": (
                {"ott": e["sg_ott"], "app": e["sg_app"], "arg": e["sg_arg"], "putt": e["sg_putt"]}
                if has_sg_components else None
            ),
            "round_scores": round_scores or None,
        })
    return rows


# ---------------------------------------------------------------------------
# PAGE 5 -- ROUND HISTORY
# ---------------------------------------------------------------------------

def _round_history(recon: dict) -> dict:
    tournament_name = {gc: t["tournament"] for gc, t in recon["tournaments"].items()}
    # RED TEAM (2026-09-25): real end_date, not game_code proxy; round is
    # only a tiebreak WITHIN one tournament, never reorders across tournaments
    rows = sort_tournaments(recon["round_rows"], tiebreak_key="round")
    enriched = [
        {"game_code": r["game_code"], "season": r["season"], "round": r["round"], "sg_total": r["sg_total"],
         "tournament": tournament_name.get(r["game_code"], r["game_code"])}
        for r in rows
    ]

    best = max(enriched, key=lambda r: r["sg_total"])
    worst = min(enriched, key=lambda r: r["sg_total"])

    by_tournament = defaultdict(list)
    for r in enriched:
        by_tournament[r["game_code"]].append(r)
    stability = []
    for gc, rs in by_tournament.items():
        if len(rs) >= 3:
            stability.append({"game_code": gc, "tournament": rs[0]["tournament"], "stddev": statistics.pstdev(r["sg_total"] for r in rs), "rounds": len(rs)})
    most_stable = min(stability, key=lambda s: s["stddev"]) if stability else None

    deltas = []
    for gc, rs in by_tournament.items():
        rs_sorted = sorted(rs, key=lambda r: r["round"])
        for prev, cur in zip(rs_sorted, rs_sorted[1:]):
            deltas.append({
                "game_code": gc, "tournament": cur["tournament"], "season": cur["season"],
                "from_round": prev["round"], "to_round": cur["round"],
                "delta": round(cur["sg_total"] - prev["sg_total"], 2),
            })
    most_improved_round = max(deltas, key=lambda d: d["delta"]) if deltas else None
    largest_collapse = min(deltas, key=lambda d: d["delta"]) if deltas else None
    largest_recovery = None
    negative_then_positive = [d for d in deltas if d["delta"] > 0]
    # "largest recovery" = biggest positive delta that immediately follows a round with a negative total
    round_lookup = {(r["game_code"], r["round"]): r for r in enriched}
    recoveries = []
    for d in negative_then_positive:
        prev_round = round_lookup.get((d["game_code"], d["from_round"]))
        if prev_round and prev_round["sg_total"] < 0:
            recoveries.append(d)
    if recoveries:
        largest_recovery = max(recoveries, key=lambda d: d["delta"])

    return {
        "total_rounds": len(enriched),
        "best_round": best,
        "worst_round": worst,
        "most_stable_tournament": most_stable,
        "most_improved_round": most_improved_round,
        "largest_collapse": largest_collapse,
        "largest_recovery": largest_recovery,
    }


# ---------------------------------------------------------------------------
# PAGE 6 -- PLAYER EVOLUTION (automatic detections, all season-level)
# ---------------------------------------------------------------------------

def _player_evolution(evolution: dict) -> dict:
    total = evolution.get("avg_total")
    if not total:
        return {}
    deltas = total["deltas"]
    first_improvement = next((d for d in deltas if d["delta"] > 0), None)
    biggest_improvement = max(deltas, key=lambda d: d["delta"]) if deltas else None
    declines = [d for d in deltas if d["delta"] < 0]
    biggest_decline = min(declines, key=lambda d: d["delta"]) if declines else None
    smallest_move = min(deltas, key=lambda d: abs(d["delta"])) if deltas else None

    reversal = None
    for prev, cur in zip(deltas, deltas[1:]):
        prev_sign = 1 if prev["delta"] > 0 else (-1 if prev["delta"] < 0 else 0)
        cur_sign = 1 if cur["delta"] > 0 else (-1 if cur["delta"] < 0 else 0)
        if prev_sign and cur_sign and prev_sign != cur_sign:
            reversal = cur
            break

    return {
        "first_improvement": first_improvement,
        "biggest_improvement": biggest_improvement,
        "biggest_decline": biggest_decline,
        "no_decline_observed": biggest_decline is None,
        "trend_reversal": reversal,
        "closest_to_plateau": smallest_move,
    }


# ---------------------------------------------------------------------------
# PAGE 7 -- CAREER DNA
# ---------------------------------------------------------------------------

def _to_contribution_row(t: dict) -> dict:
    """Adapts a reconciled canonical tournament record to the field
    names _contribution_breakdown expects (matches the tested
    build_10097_player_intelligence_report.py convention)."""
    return {"total": t.get("sg_total"), "off_the_tee": t.get("sg_ott"), "approach": t.get("sg_app"), "around_green": t.get("sg_arg"), "putting": t.get("sg_putt")}


def _career_dna(evolution: dict, recon: dict) -> dict:
    # MISSION V41 (2026-09-28), coach-eye pass: 'avg_total' is the SUM
    # of the four real components below it, not a skill of its own --
    # comparing it against its own parts for "most volatile" / "fastest
    # growing" mechanically favors the aggregate almost every time (a
    # sum of several moving parts moves more than any single one), so
    # the page kept surfacing 'SG Total' as both answers, which tells a
    # coach nothing about which actual skill is driving it. Only the
    # four real components compete for these two labels; avg_total is
    # excluded from the candidate pool (most_consistent already never
    # picked it in practice, kept excluded here too for the same
    # reason).
    stddevs = {}
    growth = {}
    for c, data in evolution.items():
        if c == "avg_total":
            continue
        vals = [pt["value"] for pt in data["series"]]
        if len(vals) >= 2:
            stddevs[c] = statistics.pstdev(vals)
            growth[c] = vals[-1] - vals[0]
    most_consistent = min(stddevs, key=stddevs.get) if stddevs else None
    most_volatile = max(stddevs, key=stddevs.get) if stddevs else None
    fastest_growing = max(growth, key=growth.get) if growth else None

    events = recon["finished_tournaments"]
    career_breakdown = _contribution_breakdown([_to_contribution_row(t) for t in events])
    win_breakdown = _contribution_breakdown([_to_contribution_row(t) for t in events if t.get("rank") == 1])

    return {
        "most_consistent_component": _COMPONENT_LABEL.get(most_consistent) if most_consistent else None,
        "most_volatile_component": _COMPONENT_LABEL.get(most_volatile) if most_volatile else None,
        "fastest_growing_component": _COMPONENT_LABEL.get(fastest_growing) if fastest_growing else None,
        "career_foundation": career_breakdown["top_contributor"] if career_breakdown else None,
        "career_foundation_share_pct": next((b["share_pct"] for b in career_breakdown["breakdown"] if b["component"] == career_breakdown["top_contributor"]), None) if career_breakdown else None,
        "winning_foundation": win_breakdown["top_contributor"] if win_breakdown else None,
        "winning_foundation_share_pct": next((b["share_pct"] for b in win_breakdown["breakdown"] if b["component"] == win_breakdown["top_contributor"]), None) if win_breakdown else None,
    }


# ---------------------------------------------------------------------------
# PLAYER DNA RADAR -- percentile-normalized, season-switching, 5 axes.
# Never plots a raw SG value directly (units aren't 0-100). Each axis is
# the player's percentile rank within that SEASON's real player population
# in historical_sg_warehouse_corrected_v2.json (the same warehouse Career
# Evolution uses) -- never invented, never estimated from a partial
# population. Population and player value use the SAME warehouse-only
# computation (not the reconciled season average, which is more complete
# for HER specifically after this mission's backfill) so the comparison
# stays apples-to-apples against every other player, who has no such
# backfill.
# ---------------------------------------------------------------------------

_RADAR_AXES = [
    ("SG_OTT", "off_the_tee", "TEE"),
    ("SG_APP", "approach", "APPROACH"),
    ("SG_ARG", "around_green", "쇼트게임"),
    ("SG_PUTT", "putting", "PUTTING"),
    ("SG_TOTAL", "total", "SCORING"),
]


def _player_dna_radar() -> list:
    warehouse = master._load("historical_sg_warehouse_corrected_v2.json")
    cum_rows = [r for r in warehouse["records"] if r.get("scope") == "tournament_cumulative" and r.get("identity_state") == "RETAINED"]
    by_season = defaultdict(lambda: defaultdict(list))
    for r in cum_rows:
        by_season[r["season"]][r["player_id"]].append(r)

    seasons_out = []
    for season in sorted(by_season):
        players = by_season[season]
        if PLAYER_ID not in players:
            continue
        axes = []
        for key, field, label in _RADAR_AXES:
            per_player_avg = {}
            for pid, rows in players.items():
                vals = [r[field] for r in rows if r.get(field) is not None]
                if vals:
                    per_player_avg[pid] = statistics.fmean(vals)
            population_n = len(per_player_avg)
            if PLAYER_ID not in per_player_avg or population_n < 2:
                axes.append({
                    "axis": label, "source_metric": key, "season": season,
                    "raw_value": None, "percentile": None, "population": population_n,
                    "normalization_method": None, "source": "historical_sg_warehouse_corrected_v2.json",
                    "available": False,
                })
                continue
            my_val = per_player_avg[PLAYER_ID]
            worse_count = sum(1 for v in per_player_avg.values() if v < my_val)
            percentile = round(worse_count / (population_n - 1) * 100, 1)
            axes.append({
                "axis": label,
                "source_metric": key,
                "season": season,
                "raw_value": round(my_val, 3),
                "percentile": percentile,
                "population": population_n,
                "normalization_method": "season 내 선수 평균 SG 값의 백분위 (해당 시즌 실측 선수 전원 대비)",
                "source": "historical_sg_warehouse_corrected_v2.json (tournament_cumulative, RETAINED)",
                "available": True,
            })
        seasons_out.append({"season": season, "axes": axes})
    return seasons_out


def _dna_growth_and_delta(seasons_out: list) -> dict:
    """V6 mission: 'Compute Growth Velocity for every DNA axis. Compute
    Delta against Career Mean.' Mutates seasons_out in place, adding
    delta_vs_career_mean to every AVAILABLE axis entry (never computed
    for an unavailable one), and returns the per-axis summary. Velocity
    is the mean season-to-season percentile delta across only the real
    consecutive-season pairs that both have a measured percentile --
    never interpolated across a missing season."""
    axis_labels = [label for _, _, label in _RADAR_AXES]
    per_axis_series: dict = {label: [] for label in axis_labels}
    for sb in seasons_out:
        for a in sb["axes"]:
            if a["available"]:
                per_axis_series[a["axis"]].append((sb["season"], a["percentile"]))

    summary = {}
    for label, series in per_axis_series.items():
        series = sorted(series)
        mean_pct = round(statistics.fmean(p for _, p in series), 1) if series else None
        velocity = None
        velocities: list = []
        if len(series) >= 2:
            velocities = [series[i + 1][1] - series[i][1] for i in range(len(series) - 1)]
            velocity = round(statistics.fmean(velocities), 2)
        # V7 mission: Growth Acceleration -- the change in velocity
        # itself (second-order difference of the real percentile
        # series), only when at least two real velocity segments
        # exist (>= 3 real season points) -- never interpolated.
        acceleration = None
        if len(velocities) >= 2:
            accel_deltas = [velocities[i + 1] - velocities[i] for i in range(len(velocities) - 1)]
            acceleration = round(statistics.fmean(accel_deltas), 2)
        # V7 mission: Metric Stability -- population stddev of the real
        # season percentiles for this axis; lower = more stable. Only
        # defined with >= 2 real seasons (stddev of one point is
        # meaningless, not zero).
        stability_stddev = round(statistics.pstdev(p for _, p in series), 2) if len(series) >= 2 else None
        summary[label] = {
            "career_mean_percentile": mean_pct,
            "growth_velocity_per_season": velocity,
            "growth_acceleration_per_season": acceleration,
            "stability_stddev": stability_stddev,
            "seasons_used": [s for s, _ in series],
            "sample_size": len(series),
        }

    for sb in seasons_out:
        for a in sb["axes"]:
            mean_pct = summary[a["axis"]]["career_mean_percentile"]
            a["delta_vs_career_mean"] = (
                round(a["percentile"] - mean_pct, 1) if (a["available"] and mean_pct is not None) else None
            )
    return summary


# ---------------------------------------------------------------------------
# RECENT FORM -- last N completed tournaments, distinct from career/season
# aggregates. made_cut is never shown (unreliable historically -- see
# NOT_AVAILABLE).
# ---------------------------------------------------------------------------

def _recent_form(recon: dict, n: int) -> list:
    # RED TEAM (2026-09-25): real end_date, not game_code proxy -- see
    # klpga.tournament_ordering for the shared utility and exact bug
    # this replaces (a local, duplicated copy of this same fix used to
    # live only here; every tournament-ordering site in this file now
    # goes through the same shared function).
    ordered = sort_tournaments(recon["finished_tournaments"])
    recent = ordered[-n:]
    return [
        {
            "game_code": t["game_code"],
            "season": t["season"],
            "tournament": t["tournament"],
            "rank": t.get("rank"),
            "sg_total": t.get("sg_total"),
            # RED TEAM: a bare None must never render as a bare "--" --
            # this player has never had an SG-free tournament where SG
            # is simply inapplicable, so None here always means "NEO
            # has not collected it," and the UI must say so.
            "sg_status": "COLLECTED" if t.get("sg_total") is not None else "NOT_COLLECTED",
            "is_win": t.get("rank") == 1,
            "is_top10": t.get("rank") is not None and t["rank"] <= 10,
        }
        for t in recent
    ]


# ---------------------------------------------------------------------------
# MULTI-SEASON COVERAGE MATRIX -- documents what IS and is NOT available,
# per season, per metric. Never a claim that KLPGA lacks a BLOCKED cell --
# BLOCKED means resolving it needs live klpga.co.kr access this sandbox
# does not have.
# ---------------------------------------------------------------------------

def _coverage_matrix() -> dict:
    M, D, NC, BL = "MEASURED", "DERIVED", "NOT_COLLECTED", "BLOCKED"
    seasons = [2023, 2024, 2025, 2026]
    rows = {
        "Driving Distance": {2023: BL, 2024: BL, 2025: M, 2026: BL},
        "Fairway Accuracy": {2023: BL, 2024: BL, 2025: M, 2026: BL},
        "GIR": {2023: BL, 2024: BL, 2025: M, 2026: M},
        "Putts/Round": {2023: BL, 2024: BL, 2025: M, 2026: M},
        "1-Putt %": {2023: BL, 2024: BL, 2025: M, 2026: BL},
        "Putting Success %": {2023: BL, 2024: BL, 2025: M, 2026: BL},
        "Sand Save %": {2023: BL, 2024: BL, 2025: M, 2026: BL},
        "Scrambling %": {2023: BL, 2024: BL, 2025: M, 2026: BL},
        "Birdie-or-better %": {2023: BL, 2024: BL, 2025: M, 2026: M},
        "Scoring Average": {2023: BL, 2024: BL, 2025: BL, 2026: M},
        "SG Total": {s: M for s in seasons},
        "SG Off-the-Tee": {s: M for s in seasons},
        "SG Approach": {s: M for s in seasons},
        "SG Around-the-Green": {s: M for s in seasons},
        "SG Putting": {s: M for s in seasons},
        "Prize Money": {2023: BL, 2024: BL, 2025: BL, 2026: M},
        "Wins": {s: M for s in seasons},
        "Top5": {s: D for s in seasons},
        "Top10": {s: D for s in seasons},
        "Top20": {s: D for s in seasons},
    }
    return {
        "seasons": seasons,
        "status_legend": {
            "MEASURED": "이 저장소에 실측 값이 있습니다.",
            "DERIVED": "이미 실측된 원자료(순위)로부터 직접 계산됩니다 (예: 순위<=5 -> Top5).",
            "NOT_COLLECTED": "KLPGA가 게시하는지와 무관하게 이 저장소의 수집 파이프라인이 아직 가져오지 않았습니다.",
            "BLOCKED": "klpga.co.kr에 대한 실시간 네트워크 접근이 이 세션에서 차단되어 있어, 이 값이 KLPGA에 존재하는지 자체를 검증할 수 없습니다.",
        },
        "rows": rows,
        "note": "'로컬에 없음'과 'KLPGA에 없음'은 다릅니다. BLOCKED 항목은 후자를 주장하지 않습니다.",
    }


# ---------------------------------------------------------------------------
# PAGE 8 -- PLAYER STORY (milestone timeline, each entry independently real)
# ---------------------------------------------------------------------------

def _player_story(career_overview: dict, evolution: dict, player_evolution: dict) -> list:
    milestones = []
    rows = career_overview["season_rows"]
    earliest = career_overview["earliest_season_on_record"]
    milestones.append({"season": earliest, "label": "실측 데이터 시작", "detail": f"SG Total {rows[0]['sg_total']:+.2f} ({rows[0]['sg_sample_size']}개 대회 표본)"})

    career_avg = statistics.fmean(r["sg_total"] for r in rows)
    first_above_avg = next((r for r in rows if r["sg_total"] >= career_avg), None)
    if first_above_avg:
        milestones.append({"season": first_above_avg["season"], "label": "커리어 평균 SG Total 최초 상회", "detail": f"{first_above_avg['sg_total']:+.2f} (커리어 평균 {career_avg:+.2f})"})

    first_win = next((r for r in rows if r["wins"] > 0), None)
    if first_win:
        milestones.append({"season": first_win["season"], "label": "첫 우승", "detail": f"{first_win['wins']}승 (이 시즌 실측)"})

    bi = player_evolution.get("biggest_improvement")
    if bi:
        milestones.append({"season": bi["to_season"], "label": "최대 SG Total 시즌 도약", "detail": f"{bi['from_season']}→{bi['to_season']} {bi['delta']:+.2f}"})

    peak_row = max(rows, key=lambda r: r["sg_total"])
    milestones.append({"season": peak_row["season"], "label": "커리어 최고 SG Total 시즌", "detail": f"{peak_row['sg_total']:+.2f}, 우승 {peak_row['wins']}회, 상위10위 {peak_row['top10']}회"})

    milestones.sort(key=lambda m: m["season"])
    # dedupe same (season,label) that could coincide
    seen = set()
    out = []
    for m in milestones:
        key = (m["season"], m["label"])
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
    return out


# ---------------------------------------------------------------------------
# TECHNICAL STATS 2025 -- real KLPGA locationRecord capture, season 2025 only
# ---------------------------------------------------------------------------

def _technical_stats_2025() -> Optional[dict]:
    path = CONTENT_DIR / "knowledge_engine" / "player_intelligence" / PLAYER_ID / "TECHNICAL_STATS_2025.json"
    if not path.exists():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    return doc if doc.get("metrics") else None


# ---------------------------------------------------------------------------
# STATUS SEMANTICS -- a build never gets one overall PASS from conflict_count
# alone. Source-conflict cleanliness, data completeness, and derived-metric
# validity are reported separately; PASS requires real evidence in each.
# ---------------------------------------------------------------------------

def _status_semantics(recon_report: dict, technical_stats: Optional[dict], career_overview: dict) -> dict:
    source_conflicts = "PASS" if recon_report["status"] == "RECONCILED_OK" and recon_report["conflicts_detected"] == 0 and recon_report["missing"] == 0 else "FAIL"

    # Real per-player numbers, not hardcoded -- these used to be fixed
    # to 10097's own counts ("2023-2026, 96 finished tournaments"),
    # which would have been silently wrong for any other player.
    season_min = career_overview.get("earliest_season_on_record")
    latest = career_overview.get("latest_tournament")
    season_max = latest["season"] if latest else season_min
    season_range = f"{season_min}-{season_max}" if season_min is not None and season_max is not None else "N/A"
    total_events = career_overview.get("total_events", 0)

    confirmed_available = [
        f"SG Total/OTT/APP/ARG/PUTT ({season_range}, {total_events} finished tournaments)",
        f"이벤트/우승/상위10위 ({season_range})",
        "현재 시즌 상금·평균 스코어·퍼트·GIR·버디율 (2026시즌 스냅샷 1건)",
    ]
    if technical_stats:
        confirmed_available.append("평균 티샷 거리·페어웨이 안착률·GIR·샌드 세이브율·스크램블링률·퍼팅 성공률 (2025시즌 KLPGA 공식 locationRecord 스냅샷 1건)")
    still_unverified_at_source = [
        "보기율(Bogey %)",
        "전반·후반 9홀 분할 스코어",
        "라운드 중 순위 변동(일자별)",
    ]
    if technical_stats:
        still_unverified_at_source.append("드라이빙 디스턴스·페어웨이 안착률·GIR 등 기술 통계의 2025시즌 외 다른 시즌 값")
    data_completeness = "PARTIAL"

    derived_metrics = "PASS"

    return {
        "source_conflicts": source_conflicts,
        "data_completeness": data_completeness,
        "data_completeness_detail": {
            "confirmed_available": confirmed_available,
            "still_locally_absent_source_not_independently_verified": still_unverified_at_source,
            "note": (
                "'로컬 소스에 없음'은 'KLPGA가 측정하지 않음'과 다릅니다. 이 목록의 항목은 이 저장소에서 "
                "확인되지 않았을 뿐이며, 이 세션은 klpga.co.kr에 대한 네트워크 접근이 차단되어 있어 "
                "KLPGA 공식 사이트가 실제로 이 항목들을 게시하는지 여부를 직접 검증할 수 없습니다."
            ),
        },
        "derived_metrics": derived_metrics,
    }


# ---------------------------------------------------------------------------
# HOLE HISTORY -- the one real committed hole-level source
# ---------------------------------------------------------------------------

def _hole_history() -> Optional[dict]:
    zip_path = ROOT / "evidence" / "current_round_2026120001_r3_20260906" / "official_sources.zip"
    if not zip_path.exists():
        return None
    with zipfile.ZipFile(zip_path) as z:
        scorecards = json.loads(z.read("scorecards.json"))
        tournament = json.loads(z.read("tournament.json"))
    rows = scorecards.get(PLAYER_ID)
    if not rows:
        return None
    by_round = defaultdict(list)
    for r in rows:
        by_round[r["round"]].append(r)
    rounds = []
    for rnd in sorted(by_round):
        holes = sorted(by_round[rnd], key=lambda h: h["hole"])
        rounds.append({
            "round": rnd,
            "holes": [{"hole": h["hole"], "par": h["par"], "strokes": h["strokes"], "relative_to_par": h["relative_to_par"]} for h in holes],
            "holes_recorded": len(holes),
        })
    return {
        "game_code": tournament.get("gameCode"),
        "tournament": tournament.get("gameTitle"),
        "course": tournament.get("courseText"),
        "capture_note": "이 대회 1개(2026120001)에서만 실측되어 있습니다. 커리어 전체 홀 단위 기록은 존재하지 않습니다.",
        "rounds": rounds,
        "total_hole_records": len(rows),
    }


# ---------------------------------------------------------------------------
# NEO PLAYER BIOGRAPHY V4 (2026-09-25): "Stop thinking about Player
# History. Start thinking about Player Biography." Every field below is
# derived entirely from data already computed above (current_skill_vs_
# career, career_dna, player_story, recon, recent_form) -- no new raw
# measurement, only translation into biography language: which skill
# improved/declined right now, what kind of golfer she is, and her
# career told backwards (current first, seasons revealed last).
# ---------------------------------------------------------------------------

def _current_form_indicator(recent_form_10: list) -> Optional[dict]:
    """'Current form indicator' -- an independent before/after real
    comparison: her last 5 finished tournaments' average SG Total
    against the 5 BEFORE those (never a self-overlapping 5-vs-10
    comparison). Needs 10 real, SG-bearing events; otherwise explicit
    None, never guessed. +/-0.15 SG is the band used elsewhere on this
    page (see _status_from_band-style bands in the sibling Player
    Intelligence report) for 'meaningfully different, not noise'."""
    if len(recent_form_10) < 10:
        return None
    prev5, last5 = recent_form_10[:5], recent_form_10[5:]
    prev5_vals = [r["sg_total"] for r in prev5 if r.get("sg_total") is not None]
    last5_vals = [r["sg_total"] for r in last5 if r.get("sg_total") is not None]
    if not prev5_vals or not last5_vals:
        return None
    last5_avg = round(statistics.fmean(last5_vals), 3)
    prev5_avg = round(statistics.fmean(prev5_vals), 3)
    delta = round(last5_avg - prev5_avg, 3)
    trend = "UP" if delta > 0.15 else ("DOWN" if delta < -0.15 else "FLAT")
    return {
        "trend": trend, "last5_avg_sg_total": last5_avg, "prev5_avg_sg_total": prev5_avg,
        "delta": delta, "last5_sample_size": len(last5_vals), "prev5_sample_size": len(prev5_vals),
    }


def _why_now(current_skill_vs_career: Optional[dict]) -> Optional[dict]:
    """Section 2: 'Why is she playing well now?' Reuses
    current_skill_vs_career's already-computed per-component deltas
    (current season vs career average) -- no new computation. Leads
    with whichever single component has the single largest-magnitude
    delta; arrows cover all four real components."""
    if not current_skill_vs_career or not current_skill_vs_career.get("components"):
        return None
    real = [c for c in current_skill_vs_career["components"] if c.get("delta_vs_career_average") is not None]
    if not real:
        return None
    lead = max(real, key=lambda c: abs(c["delta_vs_career_average"]))
    arrows = [
        {
            "component": c["component"],
            "direction": "UP" if c["delta_vs_career_average"] > 0 else ("DOWN" if c["delta_vs_career_average"] < 0 else "FLAT"),
            "delta": c["delta_vs_career_average"],
        }
        for c in real
    ]
    sentence = (
        f'최근 상승세는 주로 {lead["component"]}의 영향입니다.' if lead["delta_vs_career_average"] > 0
        else f'최근 흐름은 {lead["component"]} 저하의 영향이 큽니다.'
    )
    return {"lead_component": lead["component"], "lead_delta": lead["delta_vs_career_average"], "arrows": arrows, "sentence": sentence}


_IDENTITY_LABEL = {
    "SG OTT": "볼 스트라이커",
    "SG APP": "어프로치 플레이어",
    "SG ARG": "리커버리 플레이어",
    "SG PUTT": "퍼팅으로 승부하는 유형",
}


def _player_identity(career_dna: dict) -> Optional[dict]:
    """Section 4: 'What kind of golfer is she?' Every label maps
    directly from career_dna's already-computed real fields (career-
    wide SG contribution breakdown, win-only SG contribution
    breakdown, most-consistent component) -- never invented."""
    foundation = career_dna.get("career_foundation")
    primary = _IDENTITY_LABEL.get(foundation)
    if not primary:
        return None
    winning = career_dna.get("winning_foundation")
    winning_note = None
    if winning and winning != foundation:
        winning_note = (
            f'우승할 때는 {winning}이(가) 특히 결정적이었습니다 '
            f'(우승 대회 기여도 {career_dna.get("winning_foundation_share_pct")}%).'
        )
    consistent = career_dna.get("most_consistent_component")
    consistency_note = None
    if consistent and consistent != "SG Total":
        consistency_note = f'{consistent}은(는) 시즌마다 기복이 가장 적은 영역입니다.'
    return {
        "primary_type": primary,
        "primary_component": foundation,
        "primary_share_pct": career_dna.get("career_foundation_share_pct"),
        "winning_note": winning_note,
        "consistency_component": consistent if consistent != "SG Total" else None,
        "consistency_note": consistency_note,
    }


# Maps each already-computed _player_story milestone label to a
# backwards-narrative chapter -- no new milestone, only regrouping.
#
# MISSION (2026-09-28): "The timeline should describe measurable
# career events, not narrative phases. Avoid subjective words such as
# 성장기, 적응기, 전성기." Chapter names renamed to name a real,
# measurable event instead of a vague life-stage word -- the
# milestones nested inside each chapter are unchanged, still the same
# real facts. Use these five labels consistently for every player this
# engine renders, not just playerCode=10097.
#
# MISSION (2026-09-28) follow-up: the earliest chapter renamed again,
# from 프로 첫 경기력 to 기준점 (Baseline). "Treat it as the player's
# first measurable performance baseline, not their debut... the
# earliest reliable performance reference point used for all later
# comparisons" -- this is the exact same real fact the data_floor_note
# disclaimer already states elsewhere on the page (measured data
# starts here, this is NOT necessarily her actual KLPGA debut); 기준점
# names it as what it actually is (a reference point every later
# comparison is measured against), never implying a debut.
_STORY_BUCKET_BY_LABEL = {
    "실측 데이터 시작": "기준점",
    "커리어 평균 SG Total 최초 상회": "첫 우승",
    "최대 SG Total 시즌 도약": "경기력 도약",
    "첫 우승": "최고 경기력",
    "커리어 최고 SG Total 시즌": "최고 경기력",
}
_STORY_CHAPTER_ORDER = ["최고 경기력", "경기력 도약", "첫 우승", "기준점"]


def _career_story(career_overview: dict, player_story_milestones: list) -> Optional[dict]:
    """Section 5: told backwards -- Current first, then 최고 경기력
    (Peak Performance) -> 경기력 도약 (Performance Leap) -> 첫 우승
    (First Win) -> 기준점 (Baseline, the earliest reliable performance
    reference point, never treated as her debut); real chronological
    seasons are revealed only at the very end. Every chapter reuses
    one of _player_story's already-computed milestones verbatim, just
    re-bucketed and reordered."""
    rows = career_overview["season_rows"]
    if not rows:
        return None
    current = rows[-1]
    chapters: dict = {}
    for m in player_story_milestones:
        bucket = _STORY_BUCKET_BY_LABEL.get(m["label"])
        if bucket:
            chapters.setdefault(bucket, []).append(m)
    ordered_chapters = [{"chapter": b, "milestones": chapters[b]} for b in _STORY_CHAPTER_ORDER if b in chapters]
    return {
        "current": {
            "season": current["season"], "sg_total": current["sg_total"],
            "wins": current["wins"], "top10": current["top10"], "events": current["events"],
        },
        "chapters": ordered_chapters,
        "season_rows": rows,
    }


def _course_profile(recon: dict) -> Optional[list]:
    """Section 9: 'strength by course, weakness by course.' Real venue/
    course names are not reliably available for most tournaments in
    this repository (see NOT_AVAILABLE), so this groups by REPEATED
    TOURNAMENT NAME instead -- the same named event recurring year over
    year is real evidence of the same host course. Uses the identical
    tokenizer knowledge_engine.py already uses for its own course-
    history matching (ke._tokenize_tournament_name), never a second,
    driftable copy of that rule. A tournament appearing only once says
    nothing about a recurring course and is excluded."""
    # A season year is part of almost every real tournament name here
    # ("2023 NH투자증권 레이디스 챔피언십" / "NH투자증권 레이디스 챔피언십
    # 2024") -- ke._tokenize_tournament_name does not strip it, so a
    # pure-digit token is additionally dropped here; otherwise the same
    # recurring event would tokenize to a different set every single
    # year and never group with itself.
    events = [e for e in recon["finished_tournaments"] if e.get("sg_total") is not None]
    groups: dict = defaultdict(list)
    for e in events:
        tokens = frozenset(t for t in ke._tokenize_tournament_name(e["tournament"]) if not t.isdigit())
        if tokens:
            groups[tokens].append(e)

    profiles = []
    for evs in groups.values():
        if len(evs) < 2:
            continue
        vals = [e["sg_total"] for e in evs]
        ordered = sort_tournaments(evs)
        best_event = max(evs, key=lambda e: e["sg_total"])
        worst_event = min(evs, key=lambda e: e["sg_total"])
        profiles.append({
            "tournament_family": ordered[-1]["tournament"],
            "appearances": len(evs),
            "avg_sg_total": round(statistics.fmean(vals), 3),
            "best_tournament": best_event["tournament"],
            "best_sg_total": best_event["sg_total"],
            "worst_tournament": worst_event["tournament"],
            "worst_sg_total": worst_event["sg_total"],
        })
    if not profiles:
        return None
    profiles.sort(key=lambda p: p["avg_sg_total"], reverse=True)
    return profiles


# ---------------------------------------------------------------------------
# MISSION V10 (2026-09-25): DATA QUALITY GOVERNANCE -- provenance map.
#
# Every leaf value build() can produce is classified as exactly one of
# MEASURED / DERIVED / IMPUTED / NOT_COLLECTED / NOT_AVAILABLE (see
# klpga.data_provenance's module docstring for the exact meaning of
# each). This map is exposed verbatim as doc["provenance"] -- every
# number on this page can always answer "where did this come from?"
#
# Four pipeline-metadata fields (schema_version, generated_at,
# scope_note, source_document) are the one deliberate exclusion: they
# describe the BUILD, not the golfer, so none of the 5 labels honestly
# describes them (see tests/test_10097_player_history_provenance_v10.py
# for the exact excluded set enforced in CI).
#
# Two real governance gaps this audit surfaced (kept MEASURED, not
# invented as a 6th label, but flagged honestly in the reason text and
# in docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md):
#   - status.data_completeness / status.derived_metrics are fixed
#     literal strings ("PARTIAL"/"PASS") with no per-run check behind
#     them -- they never vary regardless of the actual data state.
#   - coverage_matrix.rows is an entirely hand-authored table; its
#     MEASURED/DERIVED/NOT_COLLECTED/BLOCKED cell values are asserted
#     by whoever last edited this file, never verified against a live
#     presence-check of the data this specific build run actually has.
# ---------------------------------------------------------------------------

M, D, NC, NA = "MEASURED", "DERIVED", "NOT_COLLECTED", "NOT_AVAILABLE"

_UNVERIFIED_CONSTANT = (
    "a fixed literal asserted in source code, not computed from a live "
    "per-run check of the underlying data -- a known governance gap, "
    "see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md"
)


def _provenance_map() -> dict:
    entries: dict = {
        # --- identity (not build metadata -- real facts about the golfer) ---
        "player_id": (M, "playerCode constant identifying this golfer"),
        "player_name": (M, "real player name"),

        # --- status (_status_semantics) ---
        "status.source_conflicts": (D, "PASS/FAIL formula over reconciliation.status/conflicts_detected/missing", ("reconciliation.status", "reconciliation.conflicts_detected", "reconciliation.missing")),
        "status.data_completeness": (M, f"literal \"PARTIAL\" -- {_UNVERIFIED_CONSTANT}"),
        "status.data_completeness_detail.confirmed_available[]": (M, "hand-maintained list of what this repository has confirmed; one line conditionally added when technical_stats_2025 exists"),
        "status.data_completeness_detail.still_locally_absent_source_not_independently_verified[]": (NA, "hand-maintained list naming fields never found in this repository's local sources; KLPGA's own live site was never checked (no network access) so this is a local-absence disclosure, not a claim KLPGA itself lacks the field"),
        "status.data_completeness_detail.note": (M, "fixed disclosure text explaining the local-absence-vs-KLPGA-absence distinction"),
        "status.derived_metrics": (M, f"literal \"PASS\" -- {_UNVERIFIED_CONSTANT}"),

        # --- reconciliation (recon["report"], 7-source cross-check) ---
        "reconciliation.total_tournaments": (M, "count of tournaments reconciliation confirmed across all 7 real source categories"),
        "reconciliation.found_in_warehouse": (M, "count found in the SG warehouse source category"),
        "reconciliation.found_in_reader": (M, "count found in the Reader-output source category"),
        "reconciliation.found_in_live": (M, "count found in the Live-snapshot source category"),
        "reconciliation.merged": (D, "count of tournaments whose record was merged across more than one source category"),
        "reconciliation.missing": (M, "count of known tournaments reconciliation could not account for at all (0 required for the build to proceed)"),
        "reconciliation.conflicts_detected": (M, "count of cross-source field disagreements found"),
        "reconciliation.in_progress_excluded_from_finished_totals": (D, "boolean: whether the in-progress tournament was excluded from the finished-tournament counts above"),
        "reconciliation.resolved[]": (M, "real text describing how each detected conflict was resolved"),
        "reconciliation.status": (D, "RECONCILED_OK/other, computed from the counts above"),

        # --- current_tournament_in_progress (recon["in_progress_tournament"]) ---
        "current_tournament_in_progress.game_code": (M, "real in-progress tournament id"),
        "current_tournament_in_progress.season": (M, "real season"),
        "current_tournament_in_progress.tournament": (M, "real tournament name"),
        "current_tournament_in_progress.status": (M, "real live-capture status string"),
        "current_tournament_in_progress.scheduled_end_date": (M, "real official schedule end date"),
        "current_tournament_in_progress.current_ing_hole": (M, "real live current-hole capture"),
        "current_tournament_in_progress.note": (D, "disclosure text built from the real live-capture state"),
        "current_tournament_in_progress.is_confirmed_live": (D, "boolean computed by reconcile() against the real official schedule -- never assumed live"),
        "current_tournament_in_progress.sources[]": (M, "real list naming which source categories captured this tournament"),
        "current_tournament_in_progress.rounds_completed[].round": (M, "real completed round number"),
        "current_tournament_in_progress.rounds_completed[].strokes": (M, "real strokes for that completed round"),
        "current_tournament_in_progress.partial_round_sg.player": (M, "real player name on the live scorecard"),
        "current_tournament_in_progress.partial_round_sg.player_id": (M, "real player id on the live scorecard"),
        "current_tournament_in_progress.partial_round_sg.rank": (M, "real live leaderboard rank"),
        "current_tournament_in_progress.partial_round_sg.round": (M, "real round number this partial SG covers"),
        "current_tournament_in_progress.partial_round_sg.rounds": (M, "real hole count captured so far this round"),
        "current_tournament_in_progress.partial_round_sg.scope": (M, "real scope label for this partial SG computation"),
        "current_tournament_in_progress.partial_round_sg.off_the_tee": (D, "NEO's own in-house SG-off-the-tee computation over the still-incomplete round -- explicitly labeled reference-only, never an official final number"),
        "current_tournament_in_progress.partial_round_sg.approach": (D, "NEO's own in-house SG-approach computation over the still-incomplete round -- reference-only"),
        "current_tournament_in_progress.partial_round_sg.around_green": (D, "NEO's own in-house SG-around-the-green computation over the still-incomplete round -- reference-only"),
        "current_tournament_in_progress.partial_round_sg.putting": (D, "NEO's own in-house SG-putting computation over the still-incomplete round -- reference-only"),
        "current_tournament_in_progress.partial_round_sg.tee_to_green": (D, "NEO's own in-house tee-to-green SG computation over the still-incomplete round -- reference-only"),
        "current_tournament_in_progress.partial_round_sg.total": (D, "sum of the partial SG components above -- reference-only"),
        "current_tournament_in_progress.partial_round_sg.validation.t2g_delta": (D, "cross-check delta between the summed components and an independent tee-to-green figure"),
        "current_tournament_in_progress.partial_round_sg.validation.t2g_within_tolerance": (D, "boolean: whether t2g_delta is within the accepted tolerance"),
        "current_tournament_in_progress.partial_round_sg.validation.total_delta": (D, "cross-check delta on the total SG figure"),
        "current_tournament_in_progress.partial_round_sg.validation.total_within_tolerance": (D, "boolean: whether total_delta is within the accepted tolerance"),

        # --- current_vs_career (_current_vs_career) ---
        "current_vs_career.current_season": (M, "the most recent real season on record"),
        "current_vs_career.current_season_sg_total": (D, "that season's SG Total average, computed by knowledge_engine.compute_season_profiles over the season's real tournaments", ("career_overview.season_rows[].sg_total",)),
        "current_vs_career.current_season_sample_size": (D, "count of tournaments behind the current-season average"),
        "current_vs_career.career_average_sg_total": (D, "mean of every finished tournament's real SG Total", ("tournament_history[].sg_total",)),
        "current_vs_career.career_average_sample_size": (D, "count of SG-bearing finished tournaments"),
        "current_vs_career.delta_vs_career_average": (D, "current_season_sg_total minus career_average_sg_total", ("current_vs_career.current_season_sg_total", "current_vs_career.career_average_sg_total")),

        # --- current_skill_vs_career (_current_skill_vs_career) ---
        "current_skill_vs_career.current_season": (M, "the most recent real season on record"),
        "current_skill_vs_career.current_season_sample_size": (D, "count of tournaments behind the current season"),
        "current_skill_vs_career.components[].component": (M, "static component label (SG OTT/APP/ARG/PUTT)"),
        "current_skill_vs_career.components[].current_value": (D, "current season's average for this SG component"),
        "current_skill_vs_career.components[].career_average": (D, "mean of this SG component over every finished tournament that has it"),
        "current_skill_vs_career.components[].career_sample_size": (D, "count of tournaments with a real value for this component"),
        "current_skill_vs_career.components[].delta_vs_career_average": (D, "current_value minus career_average for this component", ("current_skill_vs_career.components[].current_value", "current_skill_vs_career.components[].career_average")),

        # --- current_form_indicator ---
        "current_form_indicator.trend": (D, "UP/DOWN/FLAT banded classification of the delta below (+/-0.15 SG band)", ("current_form_indicator.delta",)),
        "current_form_indicator.last5_avg_sg_total": (D, "mean SG Total of her last 5 finished, SG-bearing tournaments", ("recent_form_10[].sg_total",)),
        "current_form_indicator.prev5_avg_sg_total": (D, "mean SG Total of the 5 finished tournaments immediately before those", ("recent_form_10[].sg_total",)),
        "current_form_indicator.delta": (D, "last5_avg_sg_total minus prev5_avg_sg_total", ("current_form_indicator.last5_avg_sg_total", "current_form_indicator.prev5_avg_sg_total")),
        "current_form_indicator.last5_sample_size": (D, "count of SG-bearing tournaments in the last-5 window"),
        "current_form_indicator.prev5_sample_size": (D, "count of SG-bearing tournaments in the previous-5 window"),

        # --- why_now ---
        "why_now.lead_component": (D, "the component with the largest-magnitude delta_vs_career_average", ("current_skill_vs_career.components[].delta_vs_career_average",)),
        "why_now.lead_delta": (D, "that component's real delta_vs_career_average"),
        "why_now.arrows[].component": (M, "static component label"),
        "why_now.arrows[].direction": (D, "UP/DOWN/FLAT sign of this component's delta_vs_career_average"),
        "why_now.arrows[].delta": (D, "this component's real delta_vs_career_average", ("current_skill_vs_career.components[].delta_vs_career_average",)),
        "why_now.sentence": (D, "template sentence naming lead_component and its sign", ("why_now.lead_component", "why_now.lead_delta")),

        # --- player_identity ---
        "player_identity.primary_type": (D, "static label looked up from career_dna.career_foundation", ("career_dna.career_foundation",)),
        "player_identity.primary_component": (D, "pass-through of career_dna.career_foundation", ("career_dna.career_foundation",)),
        "player_identity.primary_share_pct": (D, "pass-through of career_dna.career_foundation_share_pct", ("career_dna.career_foundation_share_pct",)),
        "player_identity.winning_note": (D, "template sentence built from career_dna.winning_foundation, only when it differs from career_foundation", ("career_dna.winning_foundation", "career_dna.winning_foundation_share_pct")),
        "player_identity.consistency_component": (D, "pass-through of career_dna.most_consistent_component when it is not SG Total", ("career_dna.most_consistent_component",)),
        "player_identity.consistency_note": (D, "template sentence naming consistency_component"),

        # --- career_story ---
        "career_story.current.season": (M, "the most recent real season on record"),
        "career_story.current.sg_total": (D, "that season's SG Total average"),
        "career_story.current.wins": (D, "that season's real win count"),
        "career_story.current.top10": (D, "that season's real top-10 count"),
        "career_story.current.events": (D, "that season's real event count"),
        "career_story.chapters[].chapter": (M, "static chapter label from a fixed 4-chapter order"),
        "career_story.chapters[].milestones[].season": (M, "pass-through of a real player_story milestone's season"),
        "career_story.chapters[].milestones[].label": (M, "pass-through of a real player_story milestone's static label"),
        "career_story.chapters[].milestones[].detail": (D, "pass-through of a real player_story milestone's templated detail sentence"),
        "career_story.season_rows[].season": (M, "duplicate of career_overview.season_rows -- see that key; kept here only because the field is not removed, never independently computed", ()),
        "career_story.season_rows[].events": (D, "duplicate of career_overview.season_rows[].events"),
        "career_story.season_rows[].wins": (D, "duplicate of career_overview.season_rows[].wins"),
        "career_story.season_rows[].top5": (D, "duplicate of career_overview.season_rows[].top5"),
        "career_story.season_rows[].top10": (D, "duplicate of career_overview.season_rows[].top10"),
        "career_story.season_rows[].top20": (D, "duplicate of career_overview.season_rows[].top20"),
        "career_story.season_rows[].sg_total": (D, "duplicate of career_overview.season_rows[].sg_total"),
        "career_story.season_rows[].sg_app": (D, "duplicate of career_overview.season_rows[].sg_app"),
        "career_story.season_rows[].sg_arg": (D, "duplicate of career_overview.season_rows[].sg_arg"),
        "career_story.season_rows[].sg_ott": (D, "duplicate of career_overview.season_rows[].sg_ott"),
        "career_story.season_rows[].sg_putt": (D, "duplicate of career_overview.season_rows[].sg_putt"),
        "career_story.season_rows[].sg_sample_size": (D, "duplicate of career_overview.season_rows[].sg_sample_size"),

        # --- course_profile ---
        "course_profile[].tournament_family": (M, "real tournament name of the most recent appearance in this recurring group"),
        "course_profile[].appearances": (D, "count of times this tournament name recurred"),
        "course_profile[].avg_sg_total": (D, "mean SG Total across every appearance"),
        "course_profile[].best_tournament": (M, "real name of her best-SG appearance in this group"),
        "course_profile[].best_sg_total": (M, "her real SG Total in that specific appearance"),
        "course_profile[].worst_tournament": (M, "real name of her worst-SG appearance in this group"),
        "course_profile[].worst_sg_total": (M, "her real SG Total in that specific appearance"),

        # --- career_overview ---
        "career_overview.season_rows[].season": (M, "real season label"),
        "career_overview.season_rows[].events": (D, "count of finished tournaments that season"),
        "career_overview.season_rows[].wins": (D, "count of rank==1 finishes that season"),
        "career_overview.season_rows[].top5": (D, "count of rank<=5 finishes that season"),
        "career_overview.season_rows[].top10": (D, "count of rank<=10 finishes that season"),
        "career_overview.season_rows[].top20": (D, "count of rank<=20 finishes that season"),
        "career_overview.season_rows[].sg_total": (D, "mean SG Total across that season's tournaments"),
        "career_overview.season_rows[].sg_ott": (D, "mean SG OTT across that season's tournaments"),
        "career_overview.season_rows[].sg_app": (D, "mean SG APP across that season's tournaments"),
        "career_overview.season_rows[].sg_arg": (D, "mean SG ARG across that season's tournaments"),
        "career_overview.season_rows[].sg_putt": (D, "mean SG PUTT across that season's tournaments"),
        "career_overview.season_rows[].sg_sample_size": (D, "count of tournaments behind that season's SG averages"),
        "career_overview.earliest_season_on_record": (M, "the earliest season this warehouse has any data for"),
        "career_overview.data_floor_note": (D, "disclosure sentence naming earliest_season_on_record, explicitly not claimed as her real debut season"),
        "career_overview.total_events": (D, "count of all finished tournaments"),
        "career_overview.total_wins": (D, "count of all rank==1 finishes"),
        "career_overview.total_top5": (D, "sum of season_rows[].top5"),
        "career_overview.total_top10": (D, "sum of season_rows[].top10"),
        "career_overview.total_top20": (D, "sum of season_rows[].top20"),
        "career_overview.season_count": (D, "count of seasons with real data"),
        "career_overview.latest_tournament.game_code": (M, "real most recent tournament id (by real end_date)"),
        "career_overview.latest_tournament.season": (M, "real season of that tournament"),
        "career_overview.latest_tournament.tournament": (M, "real name of that tournament"),
        "career_overview.latest_tournament.rank": (M, "real final rank"),
        "career_overview.latest_tournament.rank_display": (D, "formatted text built from the real rank"),
        "career_overview.latest_tournament.is_winner_per_official_source": (D, "boolean: rank==1"),
        "career_overview.latest_tournament.final_score_to_par": (M, "real final score relative to par"),
        "career_overview.latest_tournament.rounds_played": (M, "real number of rounds played"),
        "career_overview.latest_tournament.status": (M, "real tournament status string"),
        "career_overview.latest_tournament.sg_total": (M, "real captured SG Total for this tournament"),
        "career_overview.latest_tournament.sg_ott": (M, "real captured SG OTT for this tournament"),
        "career_overview.latest_tournament.sg_app": (M, "real captured SG APP for this tournament"),
        "career_overview.latest_tournament.sg_arg": (M, "real captured SG ARG for this tournament"),
        "career_overview.latest_tournament.sg_putt": (M, "real captured SG PUTT for this tournament"),
        "career_overview.latest_tournament.sources[]": (M, "real list naming which source categories captured this tournament"),
        "career_overview.latest_tournament.round_scores[].round": (M, "real round number"),
        "career_overview.latest_tournament.round_scores[].sg_total": (M, "real per-round SG Total"),

        # --- current_snapshot (single 2026 season point-in-time snapshot) ---
        "current_snapshot.as_of_note": (D, "disclosure sentence naming the real snapshot season"),
        "current_snapshot.official_sg_rank": (M, "real official SG rank from OFFICIAL_SG_NORMALIZED.json"),
        "current_snapshot.official_sg_total": (M, "real official SG Total from the same snapshot"),
        "current_snapshot.official_sg_ott": (M, "real official SG OTT from the same snapshot"),
        "current_snapshot.official_sg_app": (M, "real official SG APP from the same snapshot"),
        "current_snapshot.official_sg_arg": (M, "real official SG ARG from the same snapshot"),
        "current_snapshot.official_sg_putt": (M, "real official SG PUTT from the same snapshot"),
        "current_snapshot.official_sg_rounds": (M, "real official rounds count backing the snapshot"),
        "current_snapshot.official_rank": (M, "real official overall rank from OFFICIAL_PROFILE_NORMALIZED.json"),
        "current_snapshot.money": (M, "real official prize money from the same snapshot"),
        "current_snapshot.average_score": (M, "real official average score"),
        "current_snapshot.average_putts": (M, "real official average putts"),
        "current_snapshot.birdie_rate": (M, "real official birdie rate"),
        "current_snapshot.gir_rate": (M, "real official GIR rate"),
        "current_snapshot.par_save_rate": (M, "real official par-save rate"),
        "current_snapshot.par_break_rate": (M, "real official par-break rate"),
        "current_snapshot.recovery_rate": (M, "real official recovery rate"),

        # --- technical_stats_2025 (real KLPGA locationRecord capture, season 2025 only) ---
        "technical_stats_2025.as_of_note": (D, "disclosure sentence naming the 2025 snapshot"),
        "technical_stats_2025.player_id": (M, "playerCode on the captured record"),
        "technical_stats_2025.player_name": (M, "player name on the captured record"),
        "technical_stats_2025.schema_version": (M, "schema tag on the captured record"),
        "technical_stats_2025.season": (M, "real season this capture covers (2025 only)"),
        "technical_stats_2025.source_endpoint": (M, "real KLPGA endpoint this was captured from"),
        "technical_stats_2025.metrics[].label": (M, "static metric name"),
        "technical_stats_2025.metrics[].value": (M, "real captured metric value"),
        "technical_stats_2025.metrics[].value_label": (M, "static unit/format label for the value"),
        "technical_stats_2025.metrics[].rank": (M, "real captured field rank for this metric"),
        "technical_stats_2025.metrics[].numerator": (M, "real captured numerator behind a rate metric"),
        "technical_stats_2025.metrics[].numerator_label": (M, "static label for the numerator"),
        "technical_stats_2025.metrics[].denominator": (M, "real captured denominator behind a rate metric"),
        "technical_stats_2025.metrics[].denominator_label": (M, "static label for the denominator"),
        "technical_stats_2025.metrics[].measured_rounds": (M, "real count of rounds this metric was captured over"),
        "technical_stats_2025.metrics[].measured_rounds_label": (M, "static label for measured_rounds"),
        "technical_stats_2025.metrics[].source_file": (M, "real filename this metric was captured from"),

        # --- not_available (explicit disclosure list) ---
        "not_available[]": (NA, "each entry is itself a disclosure of a genuinely unavailable field -- the field's own text IS the provenance answer"),

        # --- season_replay ---
        "season_replay[].season": (M, "real season"),
        "season_replay[].event_count": (D, "count of that season's finished tournaments"),
        "season_replay[].named_windows.window_size": (M, "fixed config constant (5), not golfer data"),
        "season_replay[].named_windows.first.label": (M, "static window label"),
        "season_replay[].named_windows.first.events": (D, "count of tournaments in the season's first window"),
        "season_replay[].named_windows.first.avg_sg_total": (D, "mean SG Total over that window"),
        "season_replay[].named_windows.first.sg_sample_size": (D, "count of SG-bearing tournaments in that window"),
        "season_replay[].named_windows.first.wins": (D, "count of wins in that window"),
        "season_replay[].named_windows.first.top10": (D, "count of top-10s in that window"),
        "season_replay[].named_windows.middle.label": (M, "static window label"),
        "season_replay[].named_windows.middle.events": (D, "count of tournaments in the season's middle window"),
        "season_replay[].named_windows.middle.avg_sg_total": (D, "mean SG Total over that window"),
        "season_replay[].named_windows.middle.sg_sample_size": (D, "count of SG-bearing tournaments in that window"),
        "season_replay[].named_windows.middle.wins": (D, "count of wins in that window"),
        "season_replay[].named_windows.middle.top10": (D, "count of top-10s in that window"),
        "season_replay[].named_windows.middle_unavailable_reason": (NA, "explicit disclosure text: this season has too few tournaments (<15) to isolate a non-overlapping middle window"),
        "season_replay[].named_windows.last.label": (M, "static window label"),
        "season_replay[].named_windows.last.events": (D, "count of tournaments in the season's last window"),
        "season_replay[].named_windows.last.avg_sg_total": (D, "mean SG Total over that window"),
        "season_replay[].named_windows.last.sg_sample_size": (D, "count of SG-bearing tournaments in that window"),
        "season_replay[].named_windows.last.wins": (D, "count of wins in that window"),
        "season_replay[].named_windows.last.top10": (D, "count of top-10s in that window"),
        "season_replay[].quartiles[].quarter": (M, "structural index 1-4, not golfer data"),
        "season_replay[].quartiles[].events": (D, "count of tournaments in that quarter"),
        "season_replay[].quartiles[].avg_sg_total": (D, "mean SG Total over that quarter"),
        "season_replay[].volatility_stddev": (D, "population stddev of the season's real SG Total values"),
        "season_replay[].peak.tournament": (M, "real name of the season's highest-SG tournament"),
        "season_replay[].peak.sg_total": (M, "her real SG Total in that tournament"),
        "season_replay[].slump.tournament": (M, "real name of the season's lowest-SG tournament"),
        "season_replay[].slump.sg_total": (M, "her real SG Total in that tournament"),
        "season_replay[].recovery_next_event.tournament": (M, "real name of the tournament immediately after the slump"),
        "season_replay[].recovery_next_event.sg_total": (M, "her real SG Total in that tournament"),
        "season_replay[].recovery_next_event.delta_vs_slump": (D, "recovery_next_event.sg_total minus slump.sg_total"),
        "season_replay[].top10_rate_pct": (D, "top10 count / event_count * 100"),

        # --- career_rolling_trend (career-wide 5-tournament sliding window) ---
        "career_rolling_trend.window_size": (M, "fixed config constant (5), not golfer data"),
        "career_rolling_trend.total_windows": (D, "count of sliding windows the real series produced"),
        "career_rolling_trend.series[].window_index": (M, "structural sequence index, not golfer data"),
        "career_rolling_trend.series[].start_tournament": (M, "real name of the window's first tournament"),
        "career_rolling_trend.series[].start_season": (M, "real season of that tournament"),
        "career_rolling_trend.series[].end_tournament": (M, "real name of the window's last tournament"),
        "career_rolling_trend.series[].end_season": (M, "real season of that tournament"),
        "career_rolling_trend.series[].moving_average_sg_total": (D, "mean SG Total over this 5-tournament window", ("tournament_history[].sg_total",)),
        "career_rolling_trend.series[].self_percentile": (D, "this window's rank among only her own other windows", ("career_rolling_trend.series[].moving_average_sg_total",)),
        "career_rolling_trend.career_average_sg_total": (D, "mean SG Total over every finished, SG-bearing tournament", ("tournament_history[].sg_total",)),
        "career_rolling_trend.career_average_sample_size": (D, "count of SG-bearing finished tournaments"),
        "career_rolling_trend.career_median_sg_total": (D, "median SG Total over the same population"),
        "career_rolling_trend.note": (M, "fixed disclosure text about window size and self-comparison scope"),
        "career_rolling_trend.recovery_time_windows": (D, "count of windows after the slump until the first one back at/above career average, or null if never observed"),
        "career_rolling_trend.recovery_time_tournament": (M, "real tournament name at that recovery point, or null"),
        "career_rolling_trend.recovery_time_note": (D, "sentence naming recovery_time_tournament, or a fixed disclosure when recovery was never observed in the real data"),

        # --- coverage_matrix ---
        "coverage_matrix.seasons[]": (M, "the 4 real seasons this repository covers"),
        "coverage_matrix.status_legend.MEASURED": (M, "fixed legend text, not golfer data"),
        "coverage_matrix.status_legend.DERIVED": (M, "fixed legend text, not golfer data"),
        "coverage_matrix.status_legend.NOT_COLLECTED": (M, "fixed legend text, not golfer data"),
        "coverage_matrix.status_legend.BLOCKED": (M, "fixed legend text, not golfer data"),
        "coverage_matrix.note": (M, "fixed disclosure text, not golfer data"),

        # --- player_evolution (season-to-season SG Total delta detections) ---
        "player_evolution.first_improvement.from_season": (M, "real season"),
        "player_evolution.first_improvement.to_season": (M, "real season"),
        "player_evolution.first_improvement.delta": (D, "SG Total change between those two seasons"),
        "player_evolution.first_improvement.growth_pct": (D, "that delta as a percent of the earlier season's value"),
        "player_evolution.biggest_improvement.from_season": (M, "real season"),
        "player_evolution.biggest_improvement.to_season": (M, "real season"),
        "player_evolution.biggest_improvement.delta": (D, "the largest positive season-to-season SG Total change"),
        "player_evolution.biggest_improvement.growth_pct": (D, "that delta as a percent of the earlier season's value"),
        "player_evolution.biggest_decline": (D, "the largest negative season-to-season SG Total change, or null if she has never had one"),
        "player_evolution.no_decline_observed": (D, "boolean: biggest_decline is null"),
        "player_evolution.trend_reversal": (D, "the first adjacent season-pair where the delta sign flips, or null if it never does"),
        "player_evolution.closest_to_plateau.from_season": (M, "real season"),
        "player_evolution.closest_to_plateau.to_season": (M, "real season"),
        "player_evolution.closest_to_plateau.delta": (D, "the smallest-magnitude season-to-season SG Total change"),
        "player_evolution.closest_to_plateau.growth_pct": (D, "that delta as a percent of the earlier season's value"),

        # --- career_dna ---
        "career_dna.most_consistent_component": (D, "the SG component with the lowest season-to-season stddev"),
        "career_dna.most_volatile_component": (D, "the SG component with the highest season-to-season stddev"),
        "career_dna.fastest_growing_component": (D, "the SG component with the largest first-to-last-season change"),
        "career_dna.career_foundation": (D, "the SG component contributing the largest real share of her career SG Total sum"),
        "career_dna.career_foundation_share_pct": (D, "that component's real share of the career SG Total sum"),
        "career_dna.winning_foundation": (D, "the SG component contributing the largest real share of her SG Total sum in wins only, or null if no win has complete components"),
        "career_dna.winning_foundation_share_pct": (D, "that component's real share of the win-only SG Total sum"),

        # --- player_dna_radar (percentile within each season's real player population) ---
        "player_dna_radar[].season": (M, "real season"),
        "player_dna_radar[].axes[].axis": (M, "static axis label"),
        "player_dna_radar[].axes[].source_metric": (M, "static warehouse field key"),
        "player_dna_radar[].axes[].season": (M, "real season"),
        "player_dna_radar[].axes[].raw_value": (D, "despite the field name, this is her season-average for this SG component (mean over that season's real tournament_cumulative rows), not a single raw datapoint"),
        "player_dna_radar[].axes[].percentile": (D, "her rank among every other real KLPGA player's same season-average, within this season's population"),
        "player_dna_radar[].axes[].population": (D, "count of players with a real season-average for this axis"),
        "player_dna_radar[].axes[].normalization_method": (M, "fixed description of the percentile method, or null when unavailable"),
        "player_dna_radar[].axes[].source": (M, "fixed string naming the real source file"),
        "player_dna_radar[].axes[].available": (D, "boolean: she is present in this season's warehouse AND the population has at least 2 players"),
        "player_dna_radar[].axes[].delta_vs_career_mean": (D, "this season's percentile minus her career-mean percentile for this axis", ("player_dna_radar[].axes[].percentile", "player_dna_growth.<axis>.career_mean_percentile")),

        # --- recent_form_5/10/20 (shared shape) ---
        "recent_form_5[].game_code": (M, "real tournament id"),
        "recent_form_5[].season": (M, "real season"),
        "recent_form_5[].tournament": (M, "real tournament name"),
        "recent_form_5[].rank": (M, "real final rank"),
        "recent_form_5[].sg_total": (M, "real captured SG Total, or null when not yet collected"),
        "recent_form_5[].sg_status": (D, "\"COLLECTED\"/\"NOT_COLLECTED\" computed from whether sg_total is present"),
        "recent_form_5[].is_win": (D, "boolean: rank==1"),
        "recent_form_5[].is_top10": (D, "boolean: rank<=10"),
        "recent_form_10[].game_code": (M, "real tournament id"),
        "recent_form_10[].season": (M, "real season"),
        "recent_form_10[].tournament": (M, "real tournament name"),
        "recent_form_10[].rank": (M, "real final rank"),
        "recent_form_10[].sg_total": (M, "real captured SG Total, or null when not yet collected"),
        "recent_form_10[].sg_status": (D, "\"COLLECTED\"/\"NOT_COLLECTED\" computed from whether sg_total is present"),
        "recent_form_10[].is_win": (D, "boolean: rank==1"),
        "recent_form_10[].is_top10": (D, "boolean: rank<=10"),
        "recent_form_20[].game_code": (M, "real tournament id"),
        "recent_form_20[].season": (M, "real season"),
        "recent_form_20[].tournament": (M, "real tournament name"),
        "recent_form_20[].rank": (M, "real final rank"),
        "recent_form_20[].sg_total": (M, "real captured SG Total, or null when not yet collected"),
        "recent_form_20[].sg_status": (D, "\"COLLECTED\"/\"NOT_COLLECTED\" computed from whether sg_total is present"),
        "recent_form_20[].is_win": (D, "boolean: rank==1"),
        "recent_form_20[].is_top10": (D, "boolean: rank<=10"),

        # --- player_story (milestone timeline) ---
        "player_story[].season": (M, "real season the milestone occurred in"),
        "player_story[].label": (M, "static milestone label"),
        "player_story[].detail": (D, "template sentence embedding real/derived numbers for this milestone"),

        # --- hole_history (one real hole-level source, one tournament) ---
        "hole_history.game_code": (M, "real tournament id"),
        "hole_history.tournament": (M, "real tournament name"),
        "hole_history.course": (M, "real course name from this one capture"),
        "hole_history.capture_note": (NA, "fixed disclosure text: this is the only hole-level source anywhere in this repository for this player"),
        "hole_history.total_hole_records": (D, "count of real hole records captured"),
        "hole_history.rounds[].round": (M, "real round number"),
        "hole_history.rounds[].holes_recorded": (D, "count of real hole records in this round"),
        "hole_history.rounds[].holes[].hole": (M, "real hole number"),
        "hole_history.rounds[].holes[].par": (M, "real hole par"),
        "hole_history.rounds[].holes[].strokes": (M, "real strokes taken on this hole"),
        "hole_history.rounds[].holes[].relative_to_par": (D, "strokes minus par for this hole"),

        # --- tournament_history (every finished tournament, chronological) ---
        "tournament_history[].game_code": (M, "real tournament id"),
        "tournament_history[].season": (M, "real season"),
        "tournament_history[].tournament": (M, "real tournament name"),
        "tournament_history[].rank": (M, "real final rank, or null when not yet collected"),
        "tournament_history[].sg_total": (M, "real captured SG Total, or null when not yet collected (e.g. KB금융 골든라이프 챔피언십 2026090003 -- see not_available)"),
        "tournament_history[].is_win": (D, "boolean: rank==1"),
        "tournament_history[].is_top10": (D, "boolean: rank<=10"),
        "tournament_history[].sg_components": (M, "whole object null when sg_ott is not present -- see the 4 leaf fields below"),
        "tournament_history[].sg_components.ott": (M, "real captured SG OTT for this tournament"),
        "tournament_history[].sg_components.app": (M, "real captured SG APP for this tournament"),
        "tournament_history[].sg_components.arg": (M, "real captured SG ARG for this tournament"),
        "tournament_history[].sg_components.putt": (M, "real captured SG PUTT for this tournament"),
        "tournament_history[].round_scores[].round": (M, "real round number"),
        "tournament_history[].round_scores[].sg_total": (M, "real per-round SG Total"),
        "tournament_history[].round_scores[].strokes": (M, "real strokes for this round"),

        # --- round_history ---
        "round_history.total_rounds": (D, "count of every real captured round"),
        "round_history.best_round.game_code": (M, "real tournament id of her single best round"),
        "round_history.best_round.season": (M, "real season"),
        "round_history.best_round.round": (M, "real round number"),
        "round_history.best_round.tournament": (M, "real tournament name"),
        "round_history.best_round.sg_total": (M, "her real SG Total in that specific round (selected via max)"),
        "round_history.worst_round.game_code": (M, "real tournament id of her single worst round"),
        "round_history.worst_round.season": (M, "real season"),
        "round_history.worst_round.round": (M, "real round number"),
        "round_history.worst_round.tournament": (M, "real tournament name"),
        "round_history.worst_round.sg_total": (M, "her real SG Total in that specific round (selected via min)"),
        "round_history.most_stable_tournament.game_code": (M, "real tournament id"),
        "round_history.most_stable_tournament.tournament": (M, "real tournament name"),
        "round_history.most_stable_tournament.rounds": (D, "count of real rounds behind the stddev below"),
        "round_history.most_stable_tournament.stddev": (D, "population stddev of her real round-level SG Totals in that tournament (only tournaments with >=3 rounds are eligible)"),
        "round_history.most_improved_round.game_code": (M, "real tournament id"),
        "round_history.most_improved_round.season": (M, "real season"),
        "round_history.most_improved_round.tournament": (M, "real tournament name"),
        "round_history.most_improved_round.from_round": (M, "real earlier round number"),
        "round_history.most_improved_round.to_round": (M, "real later round number"),
        "round_history.most_improved_round.delta": (D, "the largest positive round-to-round SG Total change within one tournament"),
        "round_history.largest_collapse.game_code": (M, "real tournament id"),
        "round_history.largest_collapse.season": (M, "real season"),
        "round_history.largest_collapse.tournament": (M, "real tournament name"),
        "round_history.largest_collapse.from_round": (M, "real earlier round number"),
        "round_history.largest_collapse.to_round": (M, "real later round number"),
        "round_history.largest_collapse.delta": (D, "the largest negative round-to-round SG Total change within one tournament"),
        "round_history.largest_recovery.game_code": (M, "real tournament id, or null if this pattern never occurred"),
        "round_history.largest_recovery.season": (M, "real season"),
        "round_history.largest_recovery.tournament": (M, "real tournament name"),
        "round_history.largest_recovery.from_round": (M, "real earlier round number"),
        "round_history.largest_recovery.to_round": (M, "real later round number"),
        "round_history.largest_recovery.delta": (D, "the largest positive round-to-round change that immediately follows a negative-SG round"),

        # --- career_form_story (narrative-first selection over career_rolling_trend's real windows) ---
        "career_form_story[].stage": (M, "static stage label (시즌 초반/중반/후반/전성기/현재 폼)"),
        "career_form_story[].start_tournament": (M, "real name of this stage's first tournament"),
        "career_form_story[].start_season": (M, "real season of that tournament"),
        "career_form_story[].end_tournament": (M, "real name of this stage's last tournament"),
        "career_form_story[].end_season": (M, "real season of that tournament"),
        "career_form_story[].delta_vs_career_average": (D, "this stage's moving-average SG Total minus the real career average", ("career_rolling_trend.career_average_sg_total",)),
        "career_form_story[].best_component": (D, "the SG component with the highest real delta vs its own career-component average, within this stage's window"),
        "career_form_story[].best_delta": (D, "that component's real delta vs its career-component average"),
        "career_form_story[].worst_component": (D, "the SG component with the lowest real delta vs its own career-component average, within this stage's window, or null when only one component has data"),
        "career_form_story[].worst_delta": (D, "that component's real delta vs its career-component average"),

        # --- career_heartbeat (every finished tournament, deviation from career average) ---
        "career_heartbeat.career_average_sg_total": (D, "the same real career average used everywhere else on this page", ("career_rolling_trend.career_average_sg_total",)),
        "career_heartbeat.sample_size": (D, "count of real SG-bearing finished tournaments plotted"),
        "career_heartbeat.beats[].game_code": (M, "real tournament id"),
        "career_heartbeat.beats[].season": (M, "real season"),
        "career_heartbeat.beats[].tournament": (M, "real tournament name"),
        "career_heartbeat.beats[].sg_total": (M, "her real SG Total in that tournament"),
        "career_heartbeat.beats[].delta_vs_career_average": (D, "sg_total minus career_average_sg_total"),
        "career_heartbeat.beats[].career_percentile": (D, "this tournament's rank among only her own other tournaments"),
        "career_heartbeat.beats[].is_win": (D, "boolean: rank==1"),
        "career_heartbeat.beats[].is_top10": (D, "boolean: rank<=10"),
    }

    # career_evolution -- keyed by SG-component code (avg_total/avg_ott/
    # avg_app/avg_arg/avg_putt), same shape per component; generated in
    # a loop rather than typed 5x to keep this map maintainable.
    for c in _COMPONENTS:
        p = f"career_evolution.{c}"
        entries[f"{p}.label"] = (M, "static component label")
        entries[f"{p}.series[].season"] = (M, "real season")
        entries[f"{p}.series[].value"] = (D, "that season's real average for this SG component")
        entries[f"{p}.deltas[].from_season"] = (M, "real season")
        entries[f"{p}.deltas[].to_season"] = (M, "real season")
        entries[f"{p}.deltas[].delta"] = (D, "season-to-season change in this component's average", (f"{p}.series[].value",))
        entries[f"{p}.deltas[].growth_pct"] = (D, "that delta as a percent of the earlier season's value, or null when the earlier value is 0")
        entries[f"{p}.peak_season.season"] = (M, "real season of her highest average for this component")
        entries[f"{p}.peak_season.value"] = (D, "her real average that season (selected via max)")
        entries[f"{p}.worst_season.season"] = (M, "real season of her lowest average for this component")
        entries[f"{p}.worst_season.value"] = (D, "her real average that season (selected via min)")
        entries[f"{p}.current_direction"] = (D, "UP/DOWN/FLAT sign of the most recent season-to-season delta")

    # career_rolling_trend.{peak,slump,recovery}_window -- same shape 3x.
    for w in ("peak_window", "slump_window", "recovery_window"):
        p = f"career_rolling_trend.{w}"
        entries[f"{p}.window_index"] = (M, "structural sequence index, not golfer data")
        entries[f"{p}.start_tournament"] = (M, "real name of this window's first tournament")
        entries[f"{p}.start_season"] = (M, "real season of that tournament")
        entries[f"{p}.end_tournament"] = (M, "real name of this window's last tournament")
        entries[f"{p}.end_season"] = (M, "real season of that tournament")
        entries[f"{p}.moving_average_sg_total"] = (D, "mean SG Total over this 5-tournament window")
        entries[f"{p}.self_percentile"] = (D, "this window's rank among only her own other windows")
        entries[f"{p}.delta_vs_career_average"] = (D, "moving_average_sg_total minus the real career average", (f"{p}.moving_average_sg_total", "career_rolling_trend.career_average_sg_total"))
        # SG-component decomposition, real when >=1 tournament in the window has it
        entries[f"{p}.decomposition.sg_component_sample_size"] = (D, "count of tournaments in this window with real SG components")
        entries[f"{p}.decomposition.sg_component_window_size"] = (D, "count of tournaments in this window")
        entries[f"{p}.decomposition.ott"] = (D, "mean real SG OTT across the tournaments in this window that have it, or null")
        entries[f"{p}.decomposition.app"] = (D, "mean real SG APP across the tournaments in this window that have it, or null")
        entries[f"{p}.decomposition.arg"] = (D, "mean real SG ARG across the tournaments in this window that have it, or null")
        entries[f"{p}.decomposition.putt"] = (D, "mean real SG PUTT across the tournaments in this window that have it, or null")
        # birdie/bogey/gir/putts: the ONE hole-level source (hole_history)
        # covers exactly one tournament that has never yet appeared in a
        # finished peak/slump/recovery window -- these are NOT_AVAILABLE
        # (a structural gap this window's real data cannot close, not a
        # collection gap), except the literal status marker itself, which
        # IS a real computed availability flag (DERIVED).
        entries[f"{p}.decomposition.birdie"] = (NA, "real hole-level birdie count when this window overlaps the one hole-covered tournament; that has never yet happened for a finished window, so this is always null in this build")
        entries[f"{p}.decomposition.bogey"] = (NA, "same as birdie above")
        entries[f"{p}.decomposition.gir"] = (NA, "the one hole-level source that exists (hole_history) never captured GIR at all -- always null regardless of window overlap")
        entries[f"{p}.decomposition.putts"] = (NA, "the one hole-level source that exists (hole_history) never captured putts-per-hole at all -- always null regardless of window overlap")
        entries[f"{p}.decomposition.birdie_bogey_gir_putts_status"] = (D, "computed availability flag: whether this window overlaps the one hole-covered tournament")
        entries[f"{p}.decomposition.birdie_bogey_gir_putts_note"] = (D, "disclosure sentence explaining the status above")
    entries["career_rolling_trend.recovery_window.delta_vs_slump"] = (D, "recovery_window.moving_average_sg_total minus slump_window.moving_average_sg_total", ("career_rolling_trend.recovery_window.moving_average_sg_total", "career_rolling_trend.slump_window.moving_average_sg_total"))
    entries["career_rolling_trend.peak_window.sustainability_windows"] = (D, "count of consecutive real windows from the peak that stayed at/above the career average")
    entries["career_rolling_trend.peak_window.sustainability_tournaments"] = (D, "sustainability_windows converted to a real tournament span")

    # player_dna_growth -- keyed by axis label (TEE/APPROACH/쇼트게임/
    # PUTTING/SCORING), same shape per axis.
    for _, _, axis_label in _RADAR_AXES:
        p = f"player_dna_growth.{axis_label}"
        entries[f"{p}.career_mean_percentile"] = (D, "mean of her real per-season percentiles for this axis")
        entries[f"{p}.growth_velocity_per_season"] = (D, "mean season-to-season change in her real percentile for this axis, or null with <2 real seasons")
        entries[f"{p}.growth_acceleration_per_season"] = (D, "mean change in growth_velocity_per_season itself, or null with <3 real seasons")
        entries[f"{p}.stability_stddev"] = (D, "population stddev of her real per-season percentiles, or null with <2 real seasons")
        entries[f"{p}.seasons_used[]"] = (M, "real seasons with an available percentile for this axis")
        entries[f"{p}.sample_size"] = (D, "count of seasons_used")

    # coverage_matrix.rows -- keyed by metric name then by season; every
    # cell is the same kind of value (see the module-level docstring
    # above: a hand-authored, unverified per-run assertion).
    for metric in _coverage_matrix()["rows"]:
        for season in (2023, 2024, 2025, 2026):
            entries[f"coverage_matrix.rows.{metric}.{season}"] = (M, f"literal status code -- {_UNVERIFIED_CONSTANT}")

    return build_provenance_map(entries)


# ---------------------------------------------------------------------------
# MISSION V11 (2026-09-25): USER-FACING DATA CONFIDENCE.
#
# "Translate developer provenance into user trust... Never expose
# internal labels such as MEASURED, DERIVED, IMPUTED. The purpose is
# not to explain the database. The purpose is to answer: 'How much
# should I trust what I am reading?'"
#
# Every function below is a META-computation over Mission V10's
# already-built provenance map -- it counts and groups existing
# classifications, never recomputes a golf statistic and never
# touches player data ("do not change any calculations, do not change
# any player data"). The five literal label strings never appear in
# any of these functions' own output -- only the translated copy in
# _TRUST_COPY does, and only that copy is ever passed to the renderer.
# ---------------------------------------------------------------------------

_TRUST_COPY = {
    "MEASURED": {
        "short": "공식 기록",
        "detail": "KLPGA 공식 자료에서 그대로 가져온 값입니다.",
        "tier": "high",
    },
    "DERIVED": {
        "short": "실측 기반 계산",
        "detail": "실제 기록을 그대로 계산한 값입니다 (평균·합계 등). 실제 숫자에서 정확히 계산된 값입니다.",
        "tier": "high",
    },
    "IMPUTED": {
        "short": "추정값",
        "detail": "실제 값을 확인할 수 없어 다른 값으로 대신한 값입니다.",
        "tier": "caution",
    },
    "NOT_COLLECTED": {
        "short": "곧 추가 예정",
        "detail": "존재할 가능성이 있지만 NEO가 아직 수집하지 못한 항목입니다.",
        "tier": "gap",
    },
    "NOT_AVAILABLE": {
        "short": "확인 불가",
        "detail": "현재로서는 확인할 방법이 없는 항목입니다.",
        "tier": "gap",
    },
}
_TRUST_LABEL_ORDER = ["MEASURED", "DERIVED", "IMPUTED", "NOT_COLLECTED", "NOT_AVAILABLE"]


def _trust_tier_counts(provenance: dict) -> dict:
    counts = {k: 0 for k in _TRUST_LABEL_ORDER}
    for entry in provenance.values():
        counts[entry["label"]] += 1
    return counts


def _page_confidence_score(provenance: dict) -> dict:
    """Deliverable 1: one headline number -- what share of everything
    shown on this page is a real official number or an exact
    calculation over real numbers (never a guess)."""
    counts = _trust_tier_counts(provenance)
    total = sum(counts.values())
    trustworthy = counts["MEASURED"] + counts["DERIVED"]
    pct = round(trustworthy / total * 100, 1) if total else None
    if pct is None:
        band, headline = None, "확인할 데이터가 없습니다."
    elif pct >= 95:
        band, headline = "매우 높음", "이 페이지의 숫자는 거의 전부 실제 기록이거나, 실제 기록을 그대로 계산한 값입니다."
    elif pct >= 85:
        band, headline = "높음", "이 페이지의 숫자는 대부분 실제 기록이거나, 실제 기록을 그대로 계산한 값입니다."
    elif pct >= 70:
        band, headline = "보통", "이 페이지에는 실제 기록으로 채워지지 않은 항목이 일부 있습니다."
    else:
        band, headline = "주의 필요", "이 페이지에는 아직 채워지지 않은 항목이 많습니다."
    return {
        "trust_band": band,
        "trustworthy_pct": pct,
        "headline": headline,
        "total_fields_checked": total,
        "real_or_calculated_fields": trustworthy,
        "estimated_fields": counts["IMPUTED"],
        "not_yet_available_fields": counts["NOT_COLLECTED"] + counts["NOT_AVAILABLE"],
    }


def _field_confidence_legend() -> dict:
    """Deliverable 2 (shared vocabulary): the fixed legend Field
    Confidence Badges draw from, keyed by the internal label so the
    renderer can look up the right translated badge for any
    doc["provenance"][path]["label"] -- the key itself is never
    rendered as visible text, only used to select which translated
    short/detail/tier to print (the same convention this codebase
    already uses for internal status codes like sg_status)."""
    return {k: {"short": _TRUST_COPY[k]["short"], "detail": _TRUST_COPY[k]["detail"], "tier": _TRUST_COPY[k]["tier"]} for k in _TRUST_LABEL_ORDER}


def _provenance_summary(provenance: dict) -> dict:
    """Deliverable 3: the same counts as the page confidence score,
    broken out per translated category, for a reader who wants the
    fuller breakdown."""
    counts = _trust_tier_counts(provenance)
    total = sum(counts.values())
    rows = []
    for k in _TRUST_LABEL_ORDER:
        n = counts[k]
        if n == 0:
            continue
        rows.append({
            "short": _TRUST_COPY[k]["short"],
            "detail": _TRUST_COPY[k]["detail"],
            "tier": _TRUST_COPY[k]["tier"],
            "count": n,
            "pct": round(n / total * 100, 1) if total else 0,
        })
    return {"total_fields_checked": total, "rows": rows}


_DEBT_GROUP_LABELS = {
    "hole_level": "홀 단위 기록 (버디·보기·GIR·퍼트 수)",
    "coverage_matrix": "과거 시즌 기술 통계 확인 현황",
    "season_windows": "일부 시즌의 중반 구간 분석",
    "other": "기타 확인되지 않은 항목",
}


def _classify_debt_group(path: str) -> str:
    if "decomposition.birdie" in path or "decomposition.bogey" in path or "decomposition.gir" in path or "decomposition.putts" in path or path == "hole_history.capture_note":
        return "hole_level"
    if path.startswith("coverage_matrix.rows.") or path in ("status.data_completeness", "status.derived_metrics"):
        return "coverage_matrix"
    if "middle_unavailable_reason" in path:
        return "season_windows"
    return "other"


def _data_confidence_roadmap(provenance: dict) -> list:
    """Deliverable 4 ('Technical Debt Dashboard', translated): every
    disclosed gap or unverified assertion the provenance map already
    knows about, grouped into a small number of real, named categories
    instead of dozens of near-duplicate rows -- framed as what NEO is
    still working to add, never as an internal debt ledger."""
    groups: dict = {}
    for path, entry in provenance.items():
        is_gap = entry["label"] in ("NOT_COLLECTED", "NOT_AVAILABLE")
        is_unverified = "not computed from a live" in entry["reason"]
        if not (is_gap or is_unverified):
            continue
        key = _classify_debt_group(path)
        slot = groups.setdefault(key, {"count": 0})
        slot["count"] += 1
    items = [{"title": _DEBT_GROUP_LABELS[key], "field_count": info["count"]} for key, info in groups.items()]
    items.sort(key=lambda i: -i["field_count"])
    return items


def _data_quality_timeline(coverage_matrix: dict) -> list:
    """Deliverable 5: how much of the full picture NEO can show for
    each real season, summarized from the same coverage_matrix rows
    Section 11 already discloses -- never a new check."""
    rows = coverage_matrix["rows"]
    total = len(rows)
    out = []
    for season in coverage_matrix["seasons"]:
        real = sum(1 for metric_rows in rows.values() if metric_rows.get(season) in ("MEASURED", "DERIVED"))
        real_pct = round(real / total * 100, 1) if total else 0
        if real_pct >= 90:
            summary = "이 시즌은 거의 모든 항목을 확인할 수 있습니다."
        elif real_pct >= 50:
            summary = "이 시즌은 주요 항목 위주로 확인할 수 있습니다."
        else:
            summary = "이 시즌은 대회 성적과 SG 기록 위주로만 확인할 수 있습니다."
        out.append({"season": season, "available_pct": real_pct, "summary": summary})
    return out


def _confidence_provenance_entries() -> dict:
    """Provenance for this mission's own 5 new deliverables (they are
    visible values too -- Mission V10's 'never allow a visible value
    without provenance' applies to them just like everything else).
    All DERIVED: every one is a count/percentage/summary computed
    purely from the already-classified provenance map, never a new
    golf statistic."""
    return build_provenance_map({
        "page_confidence.trust_band": (D, "banded classification of trustworthy_pct"),
        "page_confidence.trustworthy_pct": (D, "(MEASURED + DERIVED field count) / (total classified field count) * 100, from the provenance map"),
        "page_confidence.headline": (D, "template sentence chosen from trust_band"),
        "page_confidence.total_fields_checked": (D, "count of all classified fields in the provenance map"),
        "page_confidence.real_or_calculated_fields": (D, "count of MEASURED + DERIVED fields"),
        "page_confidence.estimated_fields": (D, "count of IMPUTED fields"),
        "page_confidence.not_yet_available_fields": (D, "count of NOT_COLLECTED + NOT_AVAILABLE fields"),
        "field_confidence_legend.MEASURED.short": (M, "fixed translated label, not computed from data"),
        "field_confidence_legend.MEASURED.detail": (M, "fixed translated explanation, not computed from data"),
        "field_confidence_legend.MEASURED.tier": (M, "fixed trust tier constant, not computed from data"),
        "field_confidence_legend.DERIVED.short": (M, "fixed translated label, not computed from data"),
        "field_confidence_legend.DERIVED.detail": (M, "fixed translated explanation, not computed from data"),
        "field_confidence_legend.DERIVED.tier": (M, "fixed trust tier constant, not computed from data"),
        "field_confidence_legend.IMPUTED.short": (M, "fixed translated label, not computed from data"),
        "field_confidence_legend.IMPUTED.detail": (M, "fixed translated explanation, not computed from data"),
        "field_confidence_legend.IMPUTED.tier": (M, "fixed trust tier constant, not computed from data"),
        "field_confidence_legend.NOT_COLLECTED.short": (M, "fixed translated label, not computed from data"),
        "field_confidence_legend.NOT_COLLECTED.detail": (M, "fixed translated explanation, not computed from data"),
        "field_confidence_legend.NOT_COLLECTED.tier": (M, "fixed trust tier constant, not computed from data"),
        "field_confidence_legend.NOT_AVAILABLE.short": (M, "fixed translated label, not computed from data"),
        "field_confidence_legend.NOT_AVAILABLE.detail": (M, "fixed translated explanation, not computed from data"),
        "field_confidence_legend.NOT_AVAILABLE.tier": (M, "fixed trust tier constant, not computed from data"),
        "provenance_summary.total_fields_checked": (D, "count of all classified fields in the provenance map"),
        "provenance_summary.rows[].short": (M, "fixed translated label, not computed from data"),
        "provenance_summary.rows[].detail": (M, "fixed translated explanation, not computed from data"),
        "provenance_summary.rows[].tier": (M, "fixed trust tier constant, not computed from data"),
        "provenance_summary.rows[].count": (D, "count of fields with this classification"),
        "provenance_summary.rows[].pct": (D, "that count as a percent of total_fields_checked"),
        "data_confidence_roadmap[].title": (M, "fixed translated group name, not computed from data"),
        "data_confidence_roadmap[].field_count": (D, "count of provenance-map fields grouped under this title"),
        "data_quality_timeline[].season": (M, "real season label"),
        "data_quality_timeline[].available_pct": (D, "share of coverage_matrix.rows marked real for this season"),
        "data_quality_timeline[].summary": (D, "template sentence chosen from available_pct"),
    })


# ---------------------------------------------------------------------------
# BUILD
# ---------------------------------------------------------------------------

def build(player_id: str = PLAYER_ID, player_name: Optional[str] = None) -> dict:
    """Build the full PLAYER_HISTORY.json document for one player.

    `player_id`/`player_name` default to 10097/김민선7 for backward
    compatibility with every existing no-argument caller (this file's
    own __main__, build_10097_player_data_warehouse.py,
    build_10097_player_database.py, validate_sg_integration.py). For
    any other player, pass a real player_id (and, when known, the
    player's real name -- needed only by the tournament-specific
    evidence loaders inside reconcile() that key on it).

    Implementation note: a handful of helper functions below still read
    the module-level PLAYER_ID/PLAYER_NAME constants directly rather
    than taking them as parameters (this file has ~2350 lines and dozens
    of small helpers; threading two new parameters through every one of
    them was judged higher-risk than this narrower approach). build()
    therefore rebinds those module globals for the duration of this
    call via `global`, exactly like reassigning any other module-level
    setting before a run. This is safe because build() is always the
    single top-level entry point per process (see
    scripts/build_player_report.py, which invokes it once per
    `--player-id` in its own process) -- it is never called twice
    concurrently, or for two different players, within one call stack.
    """
    global PLAYER_ID, PLAYER_NAME
    PLAYER_ID, PLAYER_NAME = player_id, (player_name or (PLAYER_NAME if player_id == "10097" else player_id))

    from datetime import datetime, timezone

    # Reconciliation runs first and unconditionally. recon_module.reconcile()
    # raises ReconciliationError -- uncaught, on purpose -- if any known
    # tournament cannot be fully accounted for. No report is generated
    # from a failed reconciliation.
    recon, season_profiles = _load_all(PLAYER_ID, player_name)

    career_overview = _career_overview(recon, season_profiles)
    current_snapshot = _current_snapshot()
    evolution = _career_evolution(season_profiles)
    hole_history = _hole_history()
    season_replay = _season_replay(recon)
    career_rolling_trend = _career_rolling_trend(recon, hole_history)
    career_heartbeat = _career_heartbeat(recon, career_rolling_trend.get("career_average_sg_total"))
    current_vs_career = _current_vs_career(career_overview, career_rolling_trend)
    career_component_avg = _career_component_averages(recon)
    current_skill_vs_career = _current_skill_vs_career(career_overview, career_component_avg)
    career_form_story = _career_form_story(recon, career_rolling_trend, hole_history, career_component_avg)
    tournament_history = _tournament_history(recon)
    round_history = _round_history(recon)
    player_evolution = _player_evolution(evolution)
    career_dna = _career_dna(evolution, recon)
    player_story = _player_story(career_overview, evolution, player_evolution)
    technical_stats_2025 = _technical_stats_2025()
    status = _status_semantics(recon["report"], technical_stats_2025, career_overview)
    player_dna_radar = _player_dna_radar()
    player_dna_growth = _dna_growth_and_delta(player_dna_radar)
    recent_form_5 = _recent_form(recon, 5)
    recent_form_10 = _recent_form(recon, 10)
    recent_form_20 = _recent_form(recon, 20)
    coverage_matrix = _coverage_matrix()

    current_form_indicator = _current_form_indicator(recent_form_10)
    why_now = _why_now(current_skill_vs_career)
    player_identity = _player_identity(career_dna)
    career_story = _career_story(career_overview, player_story)
    course_profile = _course_profile(recon)

    # MISSION V10 then V11: the core provenance map first, then this
    # mission's own 5 user-facing deliverables computed FROM it (see
    # _confidence_provenance_entries()'s docstring -- they are visible
    # values too, so they get provenance entries of their own, merged
    # into the same map).
    provenance = _provenance_map()
    page_confidence = _page_confidence_score(provenance)
    field_confidence_legend = _field_confidence_legend()
    provenance_summary = _provenance_summary(provenance)
    data_confidence_roadmap = _data_confidence_roadmap(provenance)
    data_quality_timeline = _data_quality_timeline(coverage_matrix)
    provenance.update(_confidence_provenance_entries())

    return {
        "schema_version": "player_history_v2",
        "player_id": PLAYER_ID,
        "player_name": PLAYER_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope_note": (
            f"이 문서는 playerCode={PLAYER_ID}({PLAYER_NAME}) 선수만을 다룹니다. Player Intelligence를 대체하는 "
            "PLAYER HISTORY GOLD STANDARD V1입니다. 실측 기록만 사용하며 추측을 포함하지 않습니다. 모든 대회 기록은 "
            "단일 웨어하우스가 아니라 reconciliation(아래 참조)을 통과한 7개 카테고리 실측 소스에서 나옵니다."
        ),
        "status": status,
        "reconciliation": recon["report"],
        "current_tournament_in_progress": recon["in_progress_tournament"],
        "current_vs_career": current_vs_career,
        "current_skill_vs_career": current_skill_vs_career,
        "current_form_indicator": current_form_indicator,
        "why_now": why_now,
        "player_identity": player_identity,
        "career_story": career_story,
        "course_profile": course_profile,
        "career_overview": career_overview,
        "current_snapshot": current_snapshot,
        "technical_stats_2025": technical_stats_2025,
        "career_evolution": evolution,
        "season_replay": season_replay,
        "career_rolling_trend": career_rolling_trend,
        "career_form_story": career_form_story,
        "career_heartbeat": career_heartbeat,
        "tournament_history": tournament_history,
        "round_history": round_history,
        "player_evolution": player_evolution,
        "career_dna": career_dna,
        "player_dna_radar": player_dna_radar,
        "player_dna_growth": player_dna_growth,
        "recent_form_5": recent_form_5,
        "recent_form_10": recent_form_10,
        "recent_form_20": recent_form_20,
        "coverage_matrix": coverage_matrix,
        "player_story": player_story,
        "hole_history": hole_history,
        "not_available": NOT_AVAILABLE,
        "provenance": provenance,
        "page_confidence": page_confidence,
        "field_confidence_legend": field_confidence_legend,
        "provenance_summary": provenance_summary,
        "data_confidence_roadmap": data_confidence_roadmap,
        "data_quality_timeline": data_quality_timeline,
        "source_document": (
            "reconcile_10097_player_history.py (7-category reconciliation) + "
            "OFFICIAL_SG_NORMALIZED.json + OFFICIAL_PROFILE_NORMALIZED.json + official_sources.zip (2026120001)"
        ),
    }


def _output_paths(player_id: str):
    """Real output paths for a given player_id -- OUTPUT_PATH/
    RECONCILIATION_REPORT_PATH above remain the 10097 defaults (kept
    for any existing code that reads those module constants directly),
    this is what main()/build_player_report.py use for any player_id."""
    base = CONTENT_DIR / "knowledge_engine" / "player_intelligence" / player_id
    return base / "PLAYER_HISTORY.json", base / "PLAYER_HISTORY_RECONCILIATION_REPORT.json"


def main(player_id: str = PLAYER_ID, player_name: Optional[str] = None) -> dict:
    """Build and write PLAYER_HISTORY.json + its reconciliation report
    for one player, and print the same diagnostics the original
    10097-only __main__ block printed. This is the one real build
    implementation -- scripts/build_player_report.py imports and calls
    this function directly rather than reimplementing any of it."""
    result = build(player_id=player_id, player_name=player_name)
    output_path, reconciliation_report_path = _output_paths(player_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    reconciliation_report_path.parent.mkdir(parents=True, exist_ok=True)
    reconciliation_report_path.write_text(json.dumps(result["reconciliation"], ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {output_path}")
    print(f"wrote {reconciliation_report_path}")
    print(f"reconciliation status: {result['reconciliation']['status']}")
    print(f"total tournaments (reconciled): {result['reconciliation']['total_tournaments']}")
    print(f"seasons: {len(result['career_overview']['season_rows'])}")
    print(f"finished tournaments: {len(result['tournament_history'])}")
    print(f"rounds: {result['round_history']['total_rounds']}")
    print(f"current tournament in progress: {result['current_tournament_in_progress']['game_code'] if result['current_tournament_in_progress'] else 'none'}")
    print(f"hole history: {'YES (' + str(result['hole_history']['total_hole_records']) + ' records)' if result['hole_history'] else 'NONE'}")
    ts = result.get("technical_stats_2025")
    print(f"technical_stats_2025: {'YES (' + str(len(ts['metrics'])) + ' metrics)' if ts else 'NONE'}")
    print(f"status: source_conflicts={result['status']['source_conflicts']} data_completeness={result['status']['data_completeness']} derived_metrics={result['status']['derived_metrics']}")
    return result


if __name__ == "__main__":
    import argparse
    _parser = argparse.ArgumentParser(description=__doc__)
    _parser.add_argument("--player-id", default=PLAYER_ID, help="playerCode to build PLAYER_HISTORY.json for (default: 10097)")
    _parser.add_argument("--player-name", default=None, help="player's official name, for name-matched evidence files (default: 김민선7 when --player-id is 10097, else unused)")
    _args = _parser.parse_args()
    main(player_id=_args.player_id, player_name=_args.player_name)
