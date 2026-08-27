"""NEO GOLF — append-only prediction HISTORY for one tournament across
PRE -> R1 -> R2 -> R3 -> FINAL (roadmap priority #2). Read-only against
every existing frozen artifact — this module never opens a frozen
prediction file for writing, never re-derives a probability, and never
touches `klpga.neo_win.archive` / `klpga.neo_win.beta001c_archive` /
`klpga.neo_win.round_update_archive`'s own files or code paths. It only
CONVERTS an already-loaded snapshot (or an already-open DB connection,
for FINAL's real results) into a small, generic per-stage history
record, and writes THAT record to its own, separate, append-only
archive directory (`neo_tournament_history/` by default).

======================================================================
IDENTITY
======================================================================
`player_code` is the ONLY join key across stages — the same convention
every other module in this project already uses (klpga.neo_win.
identity_resolution, comparison.py). Never joined by player_name.

======================================================================
MISSING METRICS ARE EXPLICIT None, NEVER FABRICATED
======================================================================
PRE has no position/score/cut%/top10% at all (the tournament hasn't
started) — those fields are None for every PRE entrant, never a
default or an estimate. R1 (klpga.neo_win.round_update) has cut%/
top5/top10/top20% but not FINAL's actual result. R2/R3 have no
producing script in this repo yet (see docs/NEO_TOURNAMENT_DASHBOARD_
SPEC.md Section 9) — recording a R2/R3 stage before one exists is
simply not attempted here; nothing fabricates a placeholder.

======================================================================
FINAL — real DB results, never inferred from score alone
======================================================================
`build_final_stage_entry` reads `player_event` (finish_position_numeric,
score_to_par, made_cut/withdrawn/disqualified) joined to `tournament_
master.winner` — the SAME "confirmed win requires BOTH finish_position_
numeric==1 AND the winner NAME field agreeing" convention `klpga.neo_
win.audit.audit_2026_season` already established, reused here rather
than re-invented.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

RECORD_KIND = "neo_tournament_history_stage_v1"

STAGE_PRE = "PRE"
STAGE_R1 = "R1"
STAGE_R2 = "R2"
STAGE_R3 = "R3"
STAGE_FINAL = "FINAL"
STAGE_ORDER: tuple[str, ...] = (STAGE_PRE, STAGE_R1, STAGE_R2, STAGE_R3, STAGE_FINAL)


class HistoryStageAlreadyRecordedError(RuntimeError):
    """A (game_code, stage) history record already exists — the
    archive is append-only; this is the only way a duplicate stage is
    ever handled. Never silently overwritten."""


@dataclass(frozen=True)
class HistoryEntrant:
    player_code: str
    player_name: str
    win_pct: Optional[float] = None
    make_cut_pct: Optional[float] = None
    top5_pct: Optional[float] = None
    top10_pct: Optional[float] = None
    top20_pct: Optional[float] = None
    position: Optional[int] = None
    score_to_par: Optional[float] = None
    # FINAL-only real, DB-sourced ground truth (see build_final_stage_entry).
    actual_finish_position_numeric: Optional[int] = None
    actual_score_to_par: Optional[float] = None
    actual_made_cut: Optional[bool] = None
    actual_confirmed_winner: Optional[bool] = None


@dataclass(frozen=True)
class HistoryStageSnapshot:
    game_code: str
    stage: str
    record_kind: str
    recorded_at_utc: str
    source_prediction_id: str
    source_model_version: str
    source_generated_at_utc: str
    tournament_name: Optional[str]
    field_size: int
    entrants: tuple[HistoryEntrant, ...] = field(default_factory=tuple)


def _entrant_to_dict(e: HistoryEntrant) -> dict:
    return {
        "player_code": e.player_code,
        "player_name": e.player_name,
        "win_pct": e.win_pct,
        "make_cut_pct": e.make_cut_pct,
        "top5_pct": e.top5_pct,
        "top10_pct": e.top10_pct,
        "top20_pct": e.top20_pct,
        "position": e.position,
        "score_to_par": e.score_to_par,
        "actual_finish_position_numeric": e.actual_finish_position_numeric,
        "actual_score_to_par": e.actual_score_to_par,
        "actual_made_cut": e.actual_made_cut,
        "actual_confirmed_winner": e.actual_confirmed_winner,
    }


def _entrant_from_dict(d: dict) -> HistoryEntrant:
    return HistoryEntrant(
        player_code=d["player_code"],
        player_name=d["player_name"],
        win_pct=d.get("win_pct"),
        make_cut_pct=d.get("make_cut_pct"),
        top5_pct=d.get("top5_pct"),
        top10_pct=d.get("top10_pct"),
        top20_pct=d.get("top20_pct"),
        position=d.get("position"),
        score_to_par=d.get("score_to_par"),
        actual_finish_position_numeric=d.get("actual_finish_position_numeric"),
        actual_score_to_par=d.get("actual_score_to_par"),
        actual_made_cut=d.get("actual_made_cut"),
        actual_confirmed_winner=d.get("actual_confirmed_winner"),
    )


def snapshot_to_dict(snapshot: HistoryStageSnapshot) -> dict:
    return {
        "game_code": snapshot.game_code,
        "stage": snapshot.stage,
        "record_kind": snapshot.record_kind,
        "recorded_at_utc": snapshot.recorded_at_utc,
        "source_prediction_id": snapshot.source_prediction_id,
        "source_model_version": snapshot.source_model_version,
        "source_generated_at_utc": snapshot.source_generated_at_utc,
        "tournament_name": snapshot.tournament_name,
        "field_size": snapshot.field_size,
        "entrants": [_entrant_to_dict(e) for e in snapshot.entrants],
    }


def snapshot_from_dict(data: dict) -> HistoryStageSnapshot:
    return HistoryStageSnapshot(
        game_code=data["game_code"],
        stage=data["stage"],
        record_kind=data["record_kind"],
        recorded_at_utc=data["recorded_at_utc"],
        source_prediction_id=data["source_prediction_id"],
        source_model_version=data["source_model_version"],
        source_generated_at_utc=data["source_generated_at_utc"],
        tournament_name=data.get("tournament_name"),
        field_size=data["field_size"],
        entrants=tuple(_entrant_from_dict(e) for e in data.get("entrants", [])),
    )


# ----------------------------------------------------------------
# Converters — pure, read an ALREADY-LOADED source object/dict, never
# open a frozen file themselves (the caller owns that read).
# ----------------------------------------------------------------


def history_entry_from_neo_win_pre_snapshot(snapshot, *, recorded_at_utc: str) -> HistoryStageSnapshot:
    """`snapshot` is a klpga.neo_win.archive.NeoWinPredictionSnapshot
    (BETA #001's own frozen PRE, e.g. prediction_id="001")."""
    entrants = tuple(
        HistoryEntrant(player_code=e.player_code, player_name=e.player_name, win_pct=e.win_probability * 100)
        for e in snapshot.predictions
    )
    return HistoryStageSnapshot(
        game_code=snapshot.game_code,
        stage=STAGE_PRE,
        record_kind=RECORD_KIND,
        recorded_at_utc=recorded_at_utc,
        source_prediction_id=snapshot.prediction_id,
        source_model_version=snapshot.model_version,
        source_generated_at_utc=snapshot.created_at_utc,
        tournament_name=snapshot.tournament_name,
        field_size=snapshot.field_size,
        entrants=entrants,
    )


def history_entry_from_beta001c_snapshot(snapshot, *, recorded_at_utc: str) -> HistoryStageSnapshot:
    """`snapshot` is a klpga.neo_win.beta001c_archive.
    NeoWinCPredictionSnapshot (e.g. prediction_id="001-C")."""
    entrants = tuple(
        HistoryEntrant(player_code=e.player_code, player_name=e.player_name, win_pct=e.win_probability * 100)
        for e in snapshot.predictions
    )
    return HistoryStageSnapshot(
        game_code=snapshot.game_code,
        stage=STAGE_PRE,
        record_kind=RECORD_KIND,
        recorded_at_utc=recorded_at_utc,
        source_prediction_id=snapshot.prediction_id,
        source_model_version=snapshot.selected_model_id,
        source_generated_at_utc=snapshot.created_at_utc,
        tournament_name=snapshot.tournament_name,
        field_size=snapshot.field_size,
        entrants=entrants,
    )


def history_entry_from_round_update_dict(data: dict, *, recorded_at_utc: str) -> HistoryStageSnapshot:
    """`data` is the already-`json.load`-ed dict of a klpga.neo_win.
    round_update_archive.RoundUpdateSnapshot's own JSON file (that
    module has no dedicated reader function — this reads the same,
    already-documented, stable JSON shape its own `snapshot_to_dict`
    produces). Stage is always R1 (round_update.py's round_number is
    always 1 — see that module's own docstring)."""
    entrants = tuple(
        HistoryEntrant(
            player_code=p["player_code"],
            player_name=p["player_name"],
            win_pct=p.get("post_r1_win_pct"),
            make_cut_pct=p.get("post_r1_make_cut_pct"),
            top5_pct=p.get("post_r1_top5_pct"),
            top10_pct=p.get("post_r1_top10_pct"),
            top20_pct=p.get("post_r1_top20_pct"),
            position=p.get("r1_position"),
            score_to_par=p.get("r1_score_to_par"),
        )
        for p in data.get("predictions", [])
    )
    return HistoryStageSnapshot(
        game_code=data["game_code"],
        stage=STAGE_R1,
        record_kind=RECORD_KIND,
        recorded_at_utc=recorded_at_utc,
        source_prediction_id=data["prediction_id"],
        source_model_version="round_update",
        source_generated_at_utc=data["created_at_utc"],
        tournament_name=data.get("tournament_name"),
        field_size=data["field_size"],
        entrants=entrants,
    )


def build_final_stage_entry(
    conn: sqlite3.Connection,
    game_code: str,
    *,
    source_prediction_id: str,
    recorded_at_utc: str,
) -> HistoryStageSnapshot:
    """Real, DB-sourced actual results — never inferred from score
    alone. `actual_confirmed_winner` requires BOTH finish_position_
    numeric==1 AND tournament_master.winner matching the player's own
    name (same convention as klpga.neo_win.audit.audit_2026_season)."""
    tm_row = conn.execute(
        "SELECT event_name, winner, field_size FROM tournament_master WHERE game_code = ?", (game_code,)
    ).fetchone()
    tournament_name = tm_row[0] if tm_row else None
    tm_winner = tm_row[1] if tm_row else None
    field_size = tm_row[2] if tm_row and tm_row[2] is not None else 0

    rows = conn.execute(
        "SELECT player_id, player_name, finish_position_numeric, score_to_par, made_cut "
        "FROM player_event WHERE game_code = ?",
        (game_code,),
    ).fetchall()

    entrants = tuple(
        HistoryEntrant(
            player_code=player_id,
            player_name=player_name,
            actual_finish_position_numeric=finish_position_numeric,
            actual_score_to_par=score_to_par,
            actual_made_cut=bool(made_cut),
            actual_confirmed_winner=(finish_position_numeric == 1 and tm_winner is not None and tm_winner == player_name),
        )
        for player_id, player_name, finish_position_numeric, score_to_par, made_cut in rows
    )

    return HistoryStageSnapshot(
        game_code=game_code,
        stage=STAGE_FINAL,
        record_kind=RECORD_KIND,
        recorded_at_utc=recorded_at_utc,
        source_prediction_id=source_prediction_id,
        source_model_version="actual_result",
        source_generated_at_utc=recorded_at_utc,
        tournament_name=tournament_name,
        field_size=field_size or len(entrants),
        entrants=entrants,
    )


# ----------------------------------------------------------------
# Atomic, append-only storage — self-contained (zero code coupling to
# klpga.neo_win.archive / beta001c_archive / round_update_archive's
# own atomic-claim implementations), same durability guarantee.
# ----------------------------------------------------------------


def history_stage_path(history_root: Path, game_code: str, stage: str) -> Path:
    return Path(history_root) / game_code / f"{stage}.json"


def _atomic_claim(content_bytes: bytes, final_path: Path) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(final_path.parent), suffix=final_path.suffix + ".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content_bytes)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp_path, final_path)
        except FileExistsError as exc:
            raise HistoryStageAlreadyRecordedError(
                f"{final_path} already exists — tournament history is append-only per (game_code, stage)."
            ) from exc
        except (OSError, NotImplementedError) as exc:
            if final_path.exists():
                raise HistoryStageAlreadyRecordedError(
                    f"{final_path} already exists — tournament history is append-only per (game_code, stage)."
                ) from exc
            os.replace(tmp_path, final_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def write_history_stage_atomic(entry: HistoryStageSnapshot, history_root: Path) -> Path:
    import json

    path = history_stage_path(history_root, entry.game_code, entry.stage)
    content = (json.dumps(snapshot_to_dict(entry), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    _atomic_claim(content, path)
    return path


def read_history_stage(path: Path) -> HistoryStageSnapshot:
    import json

    return snapshot_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def read_full_tournament_history(history_root: Path, game_code: str) -> dict[str, HistoryStageSnapshot]:
    """Returns {stage: HistoryStageSnapshot} for every stage that has
    actually been recorded for `game_code`, in STAGE_ORDER — a stage
    with no file yet is simply absent from the dict, never a
    fabricated placeholder entry."""
    result: dict[str, HistoryStageSnapshot] = {}
    for stage in STAGE_ORDER:
        path = history_stage_path(history_root, game_code, stage)
        if path.exists():
            result[stage] = read_history_stage(path)
    return result


def join_final_to_stage(final_entry: HistoryStageSnapshot, prior_entry: HistoryStageSnapshot) -> list[dict]:
    """Joins FINAL's actual results to a prior stage's predicted
    values by player_code — the ONLY safe join key. A player present
    in only one side still appears, with the other side's fields None
    (never dropped, never fabricated)."""
    if final_entry.stage != STAGE_FINAL:
        raise ValueError(f"final_entry.stage must be {STAGE_FINAL!r}, got {final_entry.stage!r}")

    final_by_code = {e.player_code: e for e in final_entry.entrants}
    prior_by_code = {e.player_code: e for e in prior_entry.entrants}
    all_codes = set(final_by_code) | set(prior_by_code)

    rows = []
    for code in all_codes:
        f = final_by_code.get(code)
        p = prior_by_code.get(code)
        rows.append(
            {
                "player_code": code,
                "player_name": (f.player_name if f else None) or (p.player_name if p else None),
                "prior_stage": prior_entry.stage,
                "predicted_win_pct": p.win_pct if p else None,
                "predicted_make_cut_pct": p.make_cut_pct if p else None,
                "predicted_top10_pct": p.top10_pct if p else None,
                "actual_finish_position_numeric": f.actual_finish_position_numeric if f else None,
                "actual_confirmed_winner": f.actual_confirmed_winner if f else None,
                "actual_made_cut": f.actual_made_cut if f else None,
            }
        )
    return rows
