"""Temporal, exploratory evaluation of the SG pre-event probability model.

Every test event is predicted using SG and score rows strictly before its
start date. Target-event SG is used only to verify data completeness, never
as an input. The score-only comparator uses the same shrinkage and outcome
simulator, changing only the per-round performance signal.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.sg_pre_v1 import (  # noqa: E402
    DEFAULT_CUT_POSITION,
    estimate_player_sg_forecasts,
    load_2026_sg_round_history,
    simulate_sg_tournament_outcomes,
)

CONTENT = ROOT / "content" / "website_v2"
DEFAULT_DB = ROOT / "data" / "klpga.sqlite"
OUT_JSON = CONTENT / "research" / "NEO_PRE_SG_V1_WALK_FORWARD_2026_EXPLORATORY.json"
OUT_MD = CONTENT / "research" / "NEO_PRE_SG_V1_WALK_FORWARD_2026_EXPLORATORY.md"
HALF_LIFE_DAYS = 90.0
PRIOR_ROUNDS = 20.0
VOLATILITY_PRIOR_DF = 12.0
BACKTEST_SIMULATIONS = 5_000
SEED_BASE = 20261028


def _iceberg_event() -> dict:
    doc = json.loads((CONTENT / "ICEBERG_2026100003_FR_OFFICIAL_V1.json").read_text(encoding="utf-8"))
    records = []
    for row in doc["records"]:
        player_id = str(row["player_id"])
        status = str(row.get("status", ""))
        rank = row.get("final_rank_numeric")
        records.append({
            "player_id": player_id,
            "player_name": row["player_name"],
            "finish_position_numeric": rank,
            "made_cut": int(status != "CUT"),
        })
    return {
        "game_code": "2026100003",
        "event_name": "아이스버그골프 · 서울신문 오픈",
        "start_date": "2026-10-16",
        "end_date": "2026-10-18",
        "rounds": 3,
        "records": records,
    }


def _load_events(conn: sqlite3.Connection) -> list[dict]:
    events = []
    masters = conn.execute(
        "SELECT event_id, game_code, event_name, start_date, end_date FROM tournament_master ORDER BY start_date"
    ).fetchall()
    for event_id, code, name, start, end in masters:
        rows = conn.execute(
            "SELECT player_id, player_name, finish_position_numeric, made_cut, rounds_played "
            "FROM player_event WHERE event_id=? ORDER BY player_id",
            (event_id,),
        ).fetchall()
        round_count = max(int(row[4] or 0) for row in rows)
        events.append({
            "game_code": str(code), "event_name": name, "start_date": start,
            "end_date": end, "rounds": round_count,
            "records": [
                {"player_id": str(row[0]), "player_name": row[1],
                 "finish_position_numeric": row[2], "made_cut": int(row[3])}
                for row in rows
            ],
        })
    events.append(_iceberg_event())
    events.sort(key=lambda item: item["start_date"])
    return events


def _load_score_history(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT pr.player_id, pr.event_id, pr.round_number, pr.round_to_par, tm.game_code, tm.end_date "
        "FROM player_round pr JOIN tournament_master tm USING(event_id) "
        "ORDER BY tm.end_date, tm.game_code, pr.player_id, pr.round_number"
    ).fetchall()
    # Higher values indicate better play, matching the SG signal direction.
    return [
        {"player_id": str(pid), "game_code": str(code), "round": int(rnd),
         "date": str(end_date), "scope": "single_round", "total": -float(to_par)}
        for pid, _event_id, rnd, to_par, code, end_date in rows
    ]


def _metrics(predictions: dict[str, dict], event: dict) -> dict:
    actual = {str(row["player_id"]): row for row in event["records"]}
    all_ids = [pid for pid in predictions if pid in actual]
    finish_ids = [
        pid for pid in all_ids
        if actual[pid].get("finish_position_numeric") is not None or not actual[pid].get("made_cut")
    ]
    if not finish_ids:
        raise ValueError(f"No ranked actual records for {event['game_code']}")
    result = {}
    for key in ("cut_probability", "top20_probability", "top10_probability", "top5_probability", "win_probability"):
        target_key = {
            "cut_probability": "made_cut",
            "top20_probability": "top20",
            "top10_probability": "top10",
            "top5_probability": "top5",
            "win_probability": "win",
        }[key]
        ys = []
        ps = []
        metric_ids = all_ids if target_key == "made_cut" else finish_ids
        for pid in metric_ids:
            rank = actual[pid]["finish_position_numeric"]
            y = float(actual[pid]["made_cut"]) if target_key == "made_cut" else float(
                (rank == 1 if rank is not None else False)
                if target_key == "win"
                else (rank is not None and rank <= int(target_key.removeprefix("top")))
            )
            ys.append(y)
            ps.append(predictions[pid][key])
        brier = sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ys)
        logloss = -sum(y * math.log(max(p, 1e-12)) + (1 - y) * math.log(max(1 - p, 1e-12))
                       for p, y in zip(ps, ys)) / len(ys)
        result[key] = {"brier": brier, "log_loss": logloss}

    winners = [pid for pid in finish_ids if actual[pid]["finish_position_numeric"] == 1]
    if not winners:
        raise ValueError(f"No winner label for {event['game_code']}")
    winner_p = sum(predictions[pid]["win_probability"] for pid in winners) / len(winners)
    ordered = sorted(finish_ids, key=lambda pid: (-predictions[pid]["win_probability"], pid))
    win_rank = min(ordered.index(pid) + 1 for pid in winners)
    t20_ordered = sorted(finish_ids, key=lambda pid: (-predictions[pid]["top20_probability"], pid))
    actual_top20 = {pid for pid in finish_ids if actual[pid]["finish_position_numeric"] is not None and actual[pid]["finish_position_numeric"] <= 20}
    predicted_top20 = set(t20_ordered[:20])
    result["winner"] = {"probability": winner_p, "predicted_rank": win_rank, "top20_hits": len(actual_top20 & predicted_top20)}
    return result


def run(db_path: Path, simulations: int = BACKTEST_SIMULATIONS) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        events = _load_events(conn)
        score_history = _load_score_history(conn)
    finally:
        conn.close()
    sg_history, source_summary = load_2026_sg_round_history(CONTENT)

    event_results = []
    skipped = []
    for index, event in enumerate(events):
        cutoff = event["start_date"]
        prior_sg = [row for row in sg_history if row["date"] < cutoff]
        if not prior_sg:
            skipped.append({"game_code": event["game_code"], "reason": "no prior official SG event"})
            continue
        field_ids = [str(row["player_id"]) for row in event["records"]]
        sg_forecasts = estimate_player_sg_forecasts(
            field_ids, prior_sg, cutoff_date=cutoff,
            half_life_days=HALF_LIFE_DAYS, prior_rounds=PRIOR_ROUNDS,
            volatility_prior_df=VOLATILITY_PRIOR_DF,
        )
        sg_probs = simulate_sg_tournament_outcomes(
            sg_forecasts, rounds=event["rounds"], cut_after_round=2,
            cut_position=DEFAULT_CUT_POSITION, n_simulations=simulations,
            seed=SEED_BASE + index,
        )

        prior_scores = [row for row in score_history if row["date"] < cutoff]
        score_forecasts = estimate_player_sg_forecasts(
            field_ids, prior_scores, cutoff_date=cutoff,
            half_life_days=HALF_LIFE_DAYS, prior_rounds=PRIOR_ROUNDS,
            volatility_prior_df=VOLATILITY_PRIOR_DF,
        )
        score_probs = simulate_sg_tournament_outcomes(
            score_forecasts, rounds=event["rounds"], cut_after_round=2,
            cut_position=DEFAULT_CUT_POSITION, n_simulations=simulations,
            seed=SEED_BASE + index,
        )
        event_results.append({
            "game_code": event["game_code"],
            "event_name": event["event_name"],
            "start_date": cutoff,
            "rounds": event["rounds"],
            "field_size": len(field_ids),
            "prior_sg_round_rows": len(prior_sg),
            "sg_connected_players": sum(sg_forecasts[pid].has_player_sg for pid in field_ids),
            "actual_winner": next(row["player_name"] for row in event["records"] if row.get("finish_position_numeric") == 1),
            "sg": _metrics(sg_probs, event),
            "score_only": _metrics(score_probs, event),
            "probability_invariants": {
                "sum_win_sg": sum(x["win_probability"] for x in sg_probs.values()),
                "sum_win_score_only": sum(x["win_probability"] for x in score_probs.values()),
                "sg_nesting_violations": sum(
                    not (x["cut_probability"] >= x["top20_probability"] >= x["top10_probability"] >= x["top5_probability"] >= x["win_probability"])
                    for x in sg_probs.values()
                ),
            },
        })

    metric_keys = ("cut_probability", "top20_probability", "top10_probability", "top5_probability", "win_probability")
    aggregate = {}
    for signal in ("sg", "score_only"):
        aggregate[signal] = {}
        for key in metric_keys:
            aggregate[signal][key] = {
                metric: sum(event[signal][key][metric] for event in event_results) / len(event_results)
                for metric in ("brier", "log_loss")
            }
        aggregate[signal]["winner_log_loss"] = sum(
            -math.log(max(event[signal]["winner"]["probability"], 1e-12)) for event in event_results
        ) / len(event_results)
        aggregate[signal]["winner_top10_rate"] = sum(
            event[signal]["winner"]["predicted_rank"] <= 10 for event in event_results
        ) / len(event_results)
        aggregate[signal]["actual_top20_capture_rate"] = sum(
            event[signal]["winner"]["top20_hits"] for event in event_results
        ) / sum(min(20, event["field_size"]) for event in event_results)

    deltas = {}
    for key in metric_keys:
        deltas[key] = {
            metric: aggregate["sg"][key][metric] - aggregate["score_only"][key][metric]
            for metric in ("brier", "log_loss")
        }
    payload = {
        "schema_version": "NEO_PRE_SG_V1_WALK_FORWARD_2026_EXPLORATORY",
        "model_version": "NEO_PRE_SG_V1",
        "evaluation_type": "strictly_prior_rolling_origin",
        "data_cutoff": "2026-10-18",
        "signal_formula": {
            "input": "official total SG per round; strictly prior to target event start",
            "recency_half_life_days": HALF_LIFE_DAYS,
            "prior_equivalent_rounds": PRIOR_ROUNDS,
            "round_sd": "pooled within-player SD, with player SD shrunk toward pooled SD",
            "simulation": "independent round-level SG draws; convert to stroke differences; apply 60th-place cut and ties after R2",
            "component_handling": "total SG only; component SG is not added again",
        },
        "simulation_count_per_event": simulations,
        "source_summary": source_summary,
        "test_event_count": len(event_results),
        "skipped_events": skipped,
        "aggregate": aggregate,
        "sg_minus_score_only_deltas": deltas,
        "events": event_results,
        "limitations": [
            "The evaluation covers one 2026 season and only events with retained round-level SG.",
            "The sample is exploratory and cannot establish multi-season probability calibration.",
            "The score-only comparator uses the same simulator and shrinkage recipe; it is not the frozen M4 production baseline.",
            "Historical fields are reconstructed from players in the final result records; pre-event entry snapshots are not retained for every test event.",
            "The S-OIL joint SG simulation has not observed its future tournament result.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return payload


def render_markdown(report: dict) -> str:
    a = report["aggregate"]
    lines = [
        "# NEO PRE SG V1 2026 시간순 검증 (탐색 결과)",
        "",
        f"검증 대회 {report['test_event_count']}개 · 시뮬레이션 {report['simulation_count_per_event']:,}회/대회 · 자료 기준일 {report['data_cutoff']}",
        "",
        "## 확률 품질 비교",
        "",
        "값이 낮을수록 좋은 Brier·Log Loss는 각 대회 예측을 먼저 계산한 뒤 대회 평균을 냈습니다. 승자 로그손실은 실제 우승자 확률만 평가합니다.",
        "",
        "| 결과 | SG Brier | 타수 Brier | SG Log Loss | 타수 Log Loss |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, label in (("cut_probability", "컷 통과"), ("top20_probability", "TOP20"),
                       ("top10_probability", "TOP10"), ("top5_probability", "TOP5"),
                       ("win_probability", "우승")):
        lines.append(
            f"| {label} | {a['sg'][key]['brier']:.5f} | {a['score_only'][key]['brier']:.5f} "
            f"| {a['sg'][key]['log_loss']:.5f} | {a['score_only'][key]['log_loss']:.5f} |"
        )
    lines += [
        "",
        f"우승자 평균 로그손실: SG {a['sg']['winner_log_loss']:.3f} · 타수 {a['score_only']['winner_log_loss']:.3f}",
        f"예측 우승자 TOP10 적중: SG {a['sg']['winner_top10_rate']:.1%} · 타수 {a['score_only']['winner_top10_rate']:.1%}",
        f"실제 TOP20 선수 포착률: SG {a['sg']['actual_top20_capture_rate']:.1%} · 타수 {a['score_only']['actual_top20_capture_rate']:.1%}",
        "",
        "## 대회별 결과",
        "",
        "| 대회 | 필드 | SG 기록 연결 | 실제 우승자 | SG 우승확률 | SG 예측 순위 | 타수 우승확률 |",
        "|---|---:|---:|---|---:|---:|---:|",
    ]
    for event in report["events"]:
        lines.append(
            f"| {event['event_name']} | {event['field_size']} | {event['sg_connected_players']} "
            f"| {event['actual_winner']} | {event['sg']['winner']['probability']:.2%} "
            f"| {event['sg']['winner']['predicted_rank']}위 | {event['score_only']['winner']['probability']:.2%} |"
        )
    lines += ["", "## 해석", ""]
    lines.extend(f"- {item}" for item in report["limitations"])
    lines += ["", "이 결과는 탐색용 비교이며 공개 검증 통과 판정이 아닙니다.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--simulations", type=int, default=BACKTEST_SIMULATIONS)
    parser.add_argument("--json-output", type=Path, default=OUT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=OUT_MD)
    args = parser.parse_args()
    report = run(args.db, args.simulations)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"status": "written", "test_events": report["test_event_count"],
                      "skipped": report["skipped_events"], "aggregate": report["aggregate"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
