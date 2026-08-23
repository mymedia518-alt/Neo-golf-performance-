"""Plain dataclasses shared between parsers, adapters, and the DB layer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Tournament:
    tournament_id: str
    tournament_name: str
    season: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    course_name: Optional[str] = None
    par: Optional[int] = None
    yardage: Optional[int] = None
    rounds_scheduled: Optional[int] = None
    tournament_type: Optional[str] = None
    status: Optional[str] = None
    in_model_scope: Optional[bool] = None
    source_url: Optional[str] = None


@dataclass
class Player:
    player_id: str
    player_name: str


@dataclass
class PlayerEvent:
    tournament_id: str
    player_id: str
    final_rank: Optional[str] = None
    final_rank_numeric: Optional[int] = None
    final_score: Optional[int] = None
    total_strokes: Optional[int] = None
    rounds_played: Optional[int] = None
    made_cut: Optional[bool] = None
    win: bool = False
    top5: bool = False
    top10: bool = False
    top20: bool = False


@dataclass
class RoundResult:
    tournament_id: str
    player_id: str
    round_number: int
    round_score: Optional[int] = None
    strokes: Optional[int] = None
    round_rank: Optional[str] = None
