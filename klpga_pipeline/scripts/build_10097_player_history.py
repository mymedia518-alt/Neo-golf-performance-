"""PLAYER HISTORY GOLD STANDARD V1 -- playerCode=10097 (김민선7) ONLY.

Player Intelligence is no longer the goal. This is the definitive PLAYER
HISTORY: Career -> Season -> Tournament -> Round, built ONLY from verified
official KLPGA records already collected in this repository. History
first, explanation second, speculation never. Every field here traces to
a real row in a real warehouse; anything not measured is omitted, never
invented. This script is scoped to playerCode=10097 only -- it is not a
reusable framework and is not intended to generalize to other players.

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

Explicitly NOT available anywhere in this repository for this player,
and therefore never shown: driving distance, driving accuracy,
historical (pre-2026) money/average score/GIR/putts/birdie rate, bogey
rate, front-nine/back-nine splits, course names for most tournaments,
day-to-day ranking movement, Strokes Gained for the KB금융 골든라이프
챔피언십 (2026090003, real finish and round scores exist, but no SG was
ever captured for this tournament), and a reliable season-by-season cut
rate (a made_cut field exists in NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json,
but its own event count for 2023 -- 7 rows vs. the real 25 real events
that season confirmed by every other source -- is inconsistent, so it
is not used as a season-level rollup).
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

from klpga.knowledge_engine import knowledge_engine as ke  # noqa: E402
from klpga.tournament_context import CONTENT_DIR  # noqa: E402

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

NOT_AVAILABLE = [
    "드라이빙 디스턴스 (Driving Distance) -- 이 저장소 어디에도 실측 기록 없음",
    "드라이빙 정확도 (Driving Accuracy) -- 이 저장소 어디에도 실측 기록 없음",
    "과거 시즌별 상금 (2026시즌 스냅샷 1건만 실측)",
    "과거 시즌별 평균 스코어 (2026시즌 스냅샷 1건만 실측)",
    "과거 시즌별 GIR·퍼트·버디율 (2026시즌 스냅샷 1건만 실측)",
    "보기율 (Bogey %) -- 이 저장소 어디에도 실측 기록 없음",
    "전반·후반 9홀 분할 스코어 -- 이 저장소 어디에도 실측 기록 없음",
    "대회별 코스명 -- 극히 일부 대회만 실측, 전체 커버리지 없음",
    "라운드 중 순위 변동 (일자별 순위 이동) -- 실측 기록 없음",
    "KB금융 골든라이프 챔피언십(2026090003)의 Strokes Gained -- 최종 순위·라운드별 스코어는 실측되었으나 "
    "이 대회의 SG 데이터는 이 저장소 어디에도 수집되지 않음",
    "시즌별 컷 통과율 -- NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json에 made_cut 필드가 있으나 "
    "2023시즌 표본(7건)이 다른 모든 실측 소스가 확인하는 2023시즌 25개 대회와 맞지 않아 신뢰할 수 없음 -- 사용하지 않음",
]


def _load_all():
    recon = recon_module.reconcile()
    season_profiles = ke.compute_season_profiles(PLAYER_ID, recon["synthetic_sg_warehouse_doc"])
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
        top10 = sum(1 for e in se if e.get("rank") is not None and e["rank"] <= 10)
        season_rows.append({
            "season": p.season,
            "events": len(se),
            "wins": wins_by_season.get(p.season, 0),
            "top10": top10,
            "sg_total": p.avg_total,
            "sg_ott": p.avg_ott,
            "sg_app": p.avg_app,
            "sg_arg": p.avg_arg,
            "sg_putt": p.avg_putt,
            "sg_sample_size": p.n_tournaments,
        })

    ordered_events = sorted(events, key=lambda e: (e["season"], e["game_code"]))
    earliest_season = season_profiles[0].season
    latest_event = ordered_events[-1] if ordered_events else None

    return {
        "season_rows": season_rows,
        "earliest_season_on_record": earliest_season,
        "data_floor_note": (
            f"이 저장소의 실측 SG 데이터는 {earliest_season}시즌부터 시작됩니다 -- 전체 웨어하우스가 모든 선수에 "
            f"대해 공통으로 가진 데이터 수집 시작점이며, {PLAYER_NAME} 선수의 실제 KLPGA 데뷔 시즌이라는 근거는 아닙니다."
        ),
        "latest_tournament": latest_event,
        "total_events": len(events),
        "total_wins": len(wins),
        "total_top10": sum(r["top10"] for r in season_rows),
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
            "스냅샷 1건 -- 과거 시즌으로 확장하지 않습니다."
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
# PAGE 3 -- SEASON REPLAY
# ---------------------------------------------------------------------------

def _season_replay(recon: dict) -> list:
    events = recon["finished_tournaments"]
    by_season = defaultdict(list)
    for e in events:
        by_season[e["season"]].append(e)

    replays = []
    for season in sorted(by_season):
        se = sorted(by_season[season], key=lambda e: e["game_code"])
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

    ordered = sorted(events, key=lambda e: (e["season"], e["game_code"]))
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
    rows = sorted(recon["round_rows"], key=lambda r: (r["season"], r["game_code"], r["round"]))
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
    stddevs = {}
    growth = {}
    for c, data in evolution.items():
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
        "capture_note": "이 대회 1개(2026120001)에서만 실측 -- 커리어 전체 홀 단위 기록은 존재하지 않습니다.",
        "rounds": rounds,
        "total_hole_records": len(rows),
    }


# ---------------------------------------------------------------------------
# BUILD
# ---------------------------------------------------------------------------

def build() -> dict:
    from datetime import datetime, timezone

    # Reconciliation runs first and unconditionally. recon_module.reconcile()
    # raises ReconciliationError -- uncaught, on purpose -- if any known
    # tournament cannot be fully accounted for. No report is generated
    # from a failed reconciliation.
    recon, season_profiles = _load_all()

    career_overview = _career_overview(recon, season_profiles)
    current_snapshot = _current_snapshot()
    evolution = _career_evolution(season_profiles)
    season_replay = _season_replay(recon)
    tournament_history = _tournament_history(recon)
    round_history = _round_history(recon)
    player_evolution = _player_evolution(evolution)
    career_dna = _career_dna(evolution, recon)
    player_story = _player_story(career_overview, evolution, player_evolution)
    hole_history = _hole_history()

    return {
        "schema_version": "player_history_v2",
        "player_id": PLAYER_ID,
        "player_name": PLAYER_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope_note": (
            "이 문서는 playerCode=10097(김민선7) 선수만을 다룹니다. Player Intelligence를 대체하는 "
            "PLAYER HISTORY GOLD STANDARD V1 -- 실측 기록만 사용하며 추측을 포함하지 않습니다. 모든 대회 기록은 "
            "단일 웨어하우스가 아니라 reconciliation(아래 참조)을 통과한 7개 카테고리 실측 소스에서 나옵니다."
        ),
        "reconciliation": recon["report"],
        "current_tournament_in_progress": recon["in_progress_tournament"],
        "career_overview": career_overview,
        "current_snapshot": current_snapshot,
        "career_evolution": evolution,
        "season_replay": season_replay,
        "tournament_history": tournament_history,
        "round_history": round_history,
        "player_evolution": player_evolution,
        "career_dna": career_dna,
        "player_story": player_story,
        "hole_history": hole_history,
        "not_available": NOT_AVAILABLE,
        "source_document": (
            "reconcile_10097_player_history.py (7-category reconciliation) + "
            "OFFICIAL_SG_NORMALIZED.json + OFFICIAL_PROFILE_NORMALIZED.json + official_sources.zip (2026120001)"
        ),
    }


if __name__ == "__main__":
    result = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    RECONCILIATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECONCILIATION_REPORT_PATH.write_text(json.dumps(result["reconciliation"], ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"wrote {RECONCILIATION_REPORT_PATH}")
    print(f"reconciliation status: {result['reconciliation']['status']}")
    print(f"total tournaments (reconciled): {result['reconciliation']['total_tournaments']}")
    print(f"seasons: {len(result['career_overview']['season_rows'])}")
    print(f"finished tournaments: {len(result['tournament_history'])}")
    print(f"rounds: {result['round_history']['total_rounds']}")
    print(f"current tournament in progress: {result['current_tournament_in_progress']['game_code'] if result['current_tournament_in_progress'] else 'none'}")
    print(f"hole history: {'YES (' + str(result['hole_history']['total_hole_records']) + ' records)' if result['hole_history'] else 'NONE'}")
