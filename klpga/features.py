"""python -m klpga.features

Builds point-in-time rolling features per (tournament, player) using only
tournaments strictly before that tournament's start_date — no future
information ever leaks into a feature row. SG (Strokes Gained) columns are
always present in the schema but only ever populated from a confirmed
official source; they are NULL here because no such source has been wired
up yet, never filled with invented values.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from datetime import datetime, timezone
from typing import List, Optional

from . import config, db

WINDOW_SIZES = (5, 10, 20, 50, 100)


def _safe_mean(values) -> Optional[float]:
    values = [v for v in values if v is not None]
    return statistics.fmean(values) if values else None


def _safe_stdev(values) -> Optional[float]:
    values = [v for v in values if v is not None]
    return statistics.pstdev(values) if len(values) >= 2 else None


def compute_features(conn) -> List[dict]:
    tournaments = conn.execute(
        "SELECT tournament_id, start_date FROM tournaments "
        "WHERE in_model_scope = 1 AND start_date IS NOT NULL ORDER BY start_date ASC"
    ).fetchall()

    rows_out: List[dict] = []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for idx, t in enumerate(tournaments):
        tid, start_date = t["tournament_id"], t["start_date"]
        past_ids = [p["tournament_id"] for p in tournaments[:idx]]
        if not past_ids:
            continue

        players = conn.execute(
            "SELECT DISTINCT player_id FROM player_events WHERE tournament_id = ?", (tid,)
        ).fetchall()

        for prow in players:
            pid = prow["player_id"]
            placeholders = ",".join("?" * len(past_ids))
            history = conn.execute(
                f"""
                SELECT pe.tournament_id, pe.final_score, pe.made_cut, pe.win, pe.top5,
                       pe.top10, pe.top20, t.start_date
                FROM player_events pe JOIN tournaments t ON t.tournament_id = pe.tournament_id
                WHERE pe.player_id = ? AND pe.tournament_id IN ({placeholders})
                ORDER BY t.start_date DESC
                """,
                (pid, *past_ids),
            ).fetchall()

            if not history:
                continue

            for window in WINDOW_SIZES:
                window_rows = history[:window]
                event_ids = [r["tournament_id"] for r in window_rows]
                events_used = len(event_ids)
                if events_used == 0:
                    continue

                round_strokes = []
                ph2 = ",".join("?" * len(event_ids))
                rr = conn.execute(
                    f"SELECT strokes FROM rounds WHERE player_id = ? AND tournament_id IN ({ph2}) "
                    f"AND strokes IS NOT NULL",
                    (pid, *event_ids),
                ).fetchall()
                round_strokes = [r["strokes"] for r in rr]

                made_cut_known = [r["made_cut"] for r in window_rows if r["made_cut"] is not None]
                cut_rate = (
                    sum(1 for v in made_cut_known if v == 1) / len(made_cut_known)
                    if made_cut_known else None
                )

                rows_out.append(
                    {
                        "tournament_id": tid,
                        "player_id": pid,
                        "as_of_date": start_date,
                        "window_size": window,
                        "events_used": events_used,
                        "avg_final_score": _safe_mean([r["final_score"] for r in window_rows]),
                        "win_count": sum(r["win"] for r in window_rows),
                        "win_rate": sum(r["win"] for r in window_rows) / events_used,
                        "top5_rate": sum(r["top5"] for r in window_rows) / events_used,
                        "top10_rate": sum(r["top10"] for r in window_rows) / events_used,
                        "top20_rate": sum(r["top20"] for r in window_rows) / events_used,
                        "cut_rate": cut_rate,
                        "avg_round_strokes": _safe_mean(round_strokes),
                        "sub70_rate": (
                            sum(1 for s in round_strokes if s < 70) / len(round_strokes)
                            if round_strokes else None
                        ),
                        "volatility_score": _safe_stdev([r["final_score"] for r in window_rows]),
                        "sg_total": None,
                        "sg_ott": None,
                        "sg_app": None,
                        "sg_putt": None,
                        "computed_at": now,
                    }
                )

    return rows_out


def persist(conn, rows: List[dict]) -> None:
    with conn:
        for row in rows:
            conn.execute(
                """
                INSERT INTO player_features (
                    tournament_id, player_id, as_of_date, window_size, events_used,
                    avg_final_score, win_count, win_rate, top5_rate, top10_rate, top20_rate,
                    cut_rate, avg_round_strokes, sub70_rate, volatility_score,
                    sg_total, sg_ott, sg_app, sg_putt, computed_at
                ) VALUES (
                    :tournament_id, :player_id, :as_of_date, :window_size, :events_used,
                    :avg_final_score, :win_count, :win_rate, :top5_rate, :top10_rate, :top20_rate,
                    :cut_rate, :avg_round_strokes, :sub70_rate, :volatility_score,
                    :sg_total, :sg_ott, :sg_app, :sg_putt, :computed_at
                )
                ON CONFLICT(tournament_id, player_id, window_size) DO UPDATE SET
                    as_of_date = excluded.as_of_date,
                    events_used = excluded.events_used,
                    avg_final_score = excluded.avg_final_score,
                    win_count = excluded.win_count,
                    win_rate = excluded.win_rate,
                    top5_rate = excluded.top5_rate,
                    top10_rate = excluded.top10_rate,
                    top20_rate = excluded.top20_rate,
                    cut_rate = excluded.cut_rate,
                    avg_round_strokes = excluded.avg_round_strokes,
                    sub70_rate = excluded.sub70_rate,
                    volatility_score = excluded.volatility_score,
                    sg_total = excluded.sg_total,
                    sg_ott = excluded.sg_ott,
                    sg_app = excluded.sg_app,
                    sg_putt = excluded.sg_putt,
                    computed_at = excluded.computed_at
                """,
                row,
            )


def export_csv(rows: List[dict]) -> None:
    out_path = config.EXPORT_DIR / "player_features.csv"
    if not rows:
        out_path.write_text("", encoding="utf-8-sig")
        return
    columns = list(rows[0].keys())
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m klpga.features",
        description="Build point-in-time (no future leakage) rolling features from the historical DB.",
    )
    parser.parse_args(argv)

    conn = db.get_connection()
    db.init_db(conn)
    try:
        rows = compute_features(conn)
        if not rows:
            print(
                "No feature rows computed - the historical DB does not yet contain "
                "enough in-scope tournament history. Run 'python -m klpga.collect' first."
            )
            return 0
        persist(conn, rows)
        export_csv(rows)
        print(
            f"Computed {len(rows)} feature rows -> DB player_features table and "
            f"{config.EXPORT_DIR / 'player_features.csv'}"
        )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
