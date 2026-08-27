"""BETA #001-C Phase 10 — pure comparison between a frozen BETA #001
PRE snapshot (klpga.neo_win.archive, prediction_id="001") and a frozen
BETA #001-C snapshot (klpga.neo_win.beta001c_archive) for the SAME
game_code. Read-only: takes two already-loaded snapshot objects, never
opens a DB connection or a file itself — callers (scripts/39) own all
I/O, so this module can never accidentally touch either archive's
files.

Per the release's explicit instruction: "Do not describe a higher Seo
probability as proof that the correction worked. The correction is
successful only if DATA INTEGRITY improved and the selected model
passed historical validation." This module reports numbers only — it
never characterizes a delta as "the correction working" or "failing."
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PlayerComparisonRow:
    player_code: str
    player_name: Optional[str]
    pre_001_win_pct: Optional[float]
    corrected_001c_win_pct: Optional[float]
    delta_pct: Optional[float]
    old_rank: Optional[int]
    new_rank: Optional[int]
    rank_change: Optional[int]
    """old_rank - new_rank: positive means the player RISED (moved to
    a better/lower rank number); negative means the player FELL. None
    when the player is present in only one of the two snapshots (a
    real, reportable state, never silently skipped)."""
    in_pre_001_only: bool
    in_001c_only: bool


def compare_beta001_to_beta001c(pre_snapshot, c_snapshot, *, highlighted_names: tuple[str, ...] = ()) -> dict:
    """`pre_snapshot` is a klpga.neo_win.archive.NeoWinPredictionSnapshot
    (BETA #001's own, prediction_id should be "001" — this function
    does not enforce that; the caller is responsible for loading the
    correct file). `c_snapshot` is a klpga.neo_win.beta001c_archive.
    NeoWinCPredictionSnapshot. `highlighted_names` is caller-supplied
    (e.g. via a script's --highlight flag) — this module never
    hardcodes a guessed Korean spelling for any specific player; the
    caller passes the exact real player_master.player_name string(s)
    from their own DB. Returns {"rows": [...], "biggest_risers": [...],
    "biggest_fallers": [...], "biggest_rank_changes": [...],
    "highlighted": {player_name: row_or_None}}."""
    pre_by_code = {e.player_code: e for e in pre_snapshot.predictions}
    c_by_code = {e.player_code: e for e in c_snapshot.predictions}
    all_codes = set(pre_by_code) | set(c_by_code)

    rows: list[PlayerComparisonRow] = []
    for code in all_codes:
        pre_e = pre_by_code.get(code)
        c_e = c_by_code.get(code)
        pre_pct = pre_e.win_probability * 100 if pre_e else None
        c_pct = c_e.win_probability * 100 if c_e else None
        delta = (c_pct - pre_pct) if (pre_pct is not None and c_pct is not None) else None
        old_rank = pre_e.rank if pre_e else None
        new_rank = c_e.rank if c_e else None
        rank_change = (old_rank - new_rank) if (old_rank is not None and new_rank is not None) else None
        name = (c_e.player_name if c_e else None) or (pre_e.player_name if pre_e else None)
        rows.append(
            PlayerComparisonRow(
                player_code=code,
                player_name=name,
                pre_001_win_pct=pre_pct,
                corrected_001c_win_pct=c_pct,
                delta_pct=delta,
                old_rank=old_rank,
                new_rank=new_rank,
                rank_change=rank_change,
                in_pre_001_only=pre_e is not None and c_e is None,
                in_001c_only=c_e is not None and pre_e is None,
            )
        )

    with_delta = [r for r in rows if r.delta_pct is not None]
    biggest_risers = sorted(with_delta, key=lambda r: -r.delta_pct)[:10]
    biggest_fallers = sorted(with_delta, key=lambda r: r.delta_pct)[:10]

    with_rank_change = [r for r in rows if r.rank_change is not None]
    biggest_rank_changes = sorted(with_rank_change, key=lambda r: -abs(r.rank_change))[:10]

    by_name = {r.player_name: r for r in rows if r.player_name}
    highlighted = {name: by_name.get(name) for name in highlighted_names}

    return {
        "rows": rows,
        "biggest_risers": biggest_risers,
        "biggest_fallers": biggest_fallers,
        "biggest_rank_changes": biggest_rank_changes,
        "highlighted": highlighted,
    }
