"""SG-based pre-tournament outcome model, version 1.

The model forecasts a player's round-level total Strokes Gained (SG)
from strictly prior official SG rounds, shrinks sparse histories toward
the tour's zero-SG reference, and simulates the tournament's stroke
results. Cut, TOP20, TOP10, TOP5, and win probabilities are counted from
the same simulated tournaments.

V1 intentionally uses total SG as its single performance signal. Total
SG already combines off-the-tee, approach, around-green, and putting;
adding those components again would double count the same performance.
Component-specific models are a separate challenger to validate.

This is a candidate model. Its small 2026-only walk-forward evaluation
must not be described as a definitive multi-season validation.
"""
from __future__ import annotations

import json
import math
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

SG_COMPONENT_FIELDS = (
    "total",
    "tee_to_green",
    "off_the_tee",
    "approach",
    "around_green",
    "putting",
)
SG_HALF_LIFE_DAYS = 90.0
SG_PRIOR_ROUNDS = 20.0
SG_VOLATILITY_PRIOR_DF = 12.0
DEFAULT_ROUND_SD = 2.7
DEFAULT_SIMULATIONS = 60_000
DEFAULT_CUT_POSITION = 60


@dataclass(frozen=True)
class PlayerSGForecast:
    player_id: str
    mean_sg: float
    round_sd: float
    rounds: int
    events: int
    effective_rounds: float
    latest_sg_date: str | None
    has_player_sg: bool


class _RoundThreeSGRows(HTMLParser):
    """Parse the official R3 single-round SG table used for Iceberg."""

    def __init__(self) -> None:
        super().__init__()
        self.context_depth = 0
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.rows: list[list[str]] = []
        self.row: list[str] = []
        self.cell = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "div" and attr.get("id") == "record-one" and self.context_depth == 0:
            self.context_depth = 1
            return
        if self.context_depth:
            if tag == "div":
                self.context_depth += 1
            elif tag == "table":
                self.in_table = True
            elif tag == "tr" and self.in_table:
                self.in_row = True
                self.row = []
            elif tag == "td" and self.in_row:
                self.in_cell = True
                self.cell = ""

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_cell:
            self.row.append(" ".join(self.cell.split()))
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.row:
                self.rows.append(self.row)
            self.in_row = False
        elif tag == "table" and self.in_table:
            self.in_table = False
        elif tag == "div" and self.context_depth:
            self.context_depth -= 1


def _number(value: str) -> float:
    import re

    match = re.match(r"\s*(-?\d+(?:\.\d+)?)", value)
    if not match:
        raise ValueError(f"Could not parse official SG value: {value!r}")
    return float(match.group(1))


def load_2026_sg_round_history(content_dir: Path) -> tuple[list[dict], dict]:
    """Load ID-resolved 2026 single-round SG rows retained in the repo.

    Sources are ten official event archives plus the three official
    rounds retained for the October 18 Iceberg event. Rows with no
    player ID are counted in diagnostics and excluded from player joins.
    """
    rows: list[dict] = []
    unresolved_rows = 0
    source_events: set[str] = set()
    for path in sorted((content_dir / "sg_official_history").glob("*/RECORDS.json")):
        records = json.loads(path.read_text(encoding="utf-8"))
        for row in records:
            if row.get("scope") != "single_round" or row.get("season") != 2026:
                continue
            if not row.get("player_id"):
                unresolved_rows += 1
                continue
            if row.get("date", "") > "2026-10-18":
                continue
            rows.append(dict(row))
            source_events.add(str(row["game_code"]))

    for round_number in (1, 2):
        path = content_dir / f"ICEBERG_2026100003_R{round_number}_SG_OFFICIAL_V1.json"
        artifact = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(dict(row) for row in artifact["records"] if row.get("player_id"))
        source_events.add("2026100003")

    entry = json.loads((content_dir / "2026100003_ENTRY_KRANKING_JOIN.json").read_text(encoding="utf-8"))
    id_by_name = {
        str(row["player_name"]): str(row["player_code"])
        for row in entry["records"]
        if row.get("player_name") and row.get("player_code")
    }
    r3_path = content_dir / "raw_capture" / "2026100003_fr" / "sg_r3.html"
    parser = _RoundThreeSGRows()
    parser.feed(r3_path.read_text(encoding="utf-8", errors="replace"))
    if len(parser.rows) != 61:
        raise ValueError(f"Expected 61 official Iceberg R3 SG rows, got {len(parser.rows)}")
    for row in parser.rows:
        if len(row) != 9:
            raise ValueError(f"Unexpected Iceberg R3 SG row shape: {row!r}")
        _, name, total, tee_to_green, off_the_tee, approach, around_green, putting, _ = row
        player_id = id_by_name.get(name)
        if not player_id:
            raise ValueError(f"Could not connect Iceberg R3 SG to entrant ID: {name}")
        rows.append({
            "player_id": player_id,
            "player_name": name,
            "total": _number(total),
            "tee_to_green": _number(tee_to_green),
            "off_the_tee": _number(off_the_tee),
            "approach": _number(approach),
            "around_green": _number(around_green),
            "putting": _number(putting),
            "game_code": "2026100003",
            "round": 3,
            "scope": "single_round",
            "date": "2026-10-18",
            "season": 2026,
        })

    key_rows: dict[tuple[str, str, int], dict] = {}
    for row in rows:
        key = (str(row["player_id"]), str(row["game_code"]), int(row["round"]))
        if key in key_rows:
            raise ValueError(f"Duplicate SG player/event/round row: {key}")
        if any(row.get(field) is None for field in SG_COMPONENT_FIELDS):
            raise ValueError(f"Missing SG component in official source row: {key}")
        key_rows[key] = row
    rows.sort(key=lambda row: (row["date"], row["game_code"], int(row["round"]), str(row["player_id"])))
    return rows, {
        "round_rows": len(rows),
        "event_count": len(source_events),
        "player_count": len({str(row["player_id"]) for row in rows}),
        "unresolved_id_rows": unresolved_rows,
        "components_complete": True,
        "latest_date": max(row["date"] for row in rows),
    }


def estimate_player_sg_forecasts(
    player_ids: list[str],
    history_rows: list[dict],
    *,
    cutoff_date: str,
    half_life_days: float = SG_HALF_LIFE_DAYS,
    prior_rounds: float = SG_PRIOR_ROUNDS,
    volatility_prior_df: float = SG_VOLATILITY_PRIOR_DF,
) -> dict[str, PlayerSGForecast]:
    """Estimate pre-event SG skill using only rows strictly before cutoff.

    The SG prior mean is zero (field average). Recency weights have a
    90-day half-life, and the weighted mean is shrunk by 20 equivalent
    rounds toward zero. Round-to-round volatility is player-specific
    when supported, shrunk toward the pooled prior-round volatility.
    """
    if half_life_days <= 0 or prior_rounds < 0 or volatility_prior_df < 0:
        raise ValueError("half-life must be positive and shrinkage strengths non-negative")
    cutoff = date.fromisoformat(cutoff_date)
    by_player: dict[str, list[dict]] = defaultdict(list)
    for row in history_rows:
        if date.fromisoformat(str(row["date"])) >= cutoff:
            continue
        if row.get("scope") != "single_round" or row.get("total") is None:
            continue
        by_player[str(row["player_id"])].append(row)

    pooled_residuals: list[float] = []
    for rows in by_player.values():
        if len(rows) > 1:
            raw = [float(row["total"]) for row in rows]
            center = statistics.mean(raw)
            pooled_residuals.extend(value - center for value in raw)
    if len(pooled_residuals) > 1:
        pooled_df = sum(max(0, len(rows) - 1) for rows in by_player.values())
        pooled_sd = math.sqrt(sum(value * value for value in pooled_residuals) / max(1, pooled_df))
        if not math.isfinite(pooled_sd) or pooled_sd <= 0:
            pooled_sd = DEFAULT_ROUND_SD
    else:
        pooled_sd = DEFAULT_ROUND_SD

    result: dict[str, PlayerSGForecast] = {}
    for player_id in sorted(set(map(str, player_ids))):
        rows = by_player.get(player_id, [])
        if not rows:
            result[player_id] = PlayerSGForecast(
                player_id, 0.0, pooled_sd, 0, 0, 0.0, None, False
            )
            continue
        weighted_sum = 0.0
        total_weight = 0.0
        for row in rows:
            age_days = (cutoff - date.fromisoformat(str(row["date"]))).days
            weight = 2.0 ** (-age_days / half_life_days)
            weighted_sum += weight * float(row["total"])
            total_weight += weight
        mean_sg = weighted_sum / (total_weight + prior_rounds) if total_weight + prior_rounds else 0.0

        own = [float(row["total"]) for row in rows]
        if len(own) >= 3:
            own_var = statistics.variance(own)
            own_df = len(own) - 1
            shrunk_var = (
                own_df * own_var + volatility_prior_df * pooled_sd * pooled_sd
            ) / (own_df + volatility_prior_df)
            round_sd = math.sqrt(max(shrunk_var, 0.25))
        else:
            round_sd = pooled_sd
        result[player_id] = PlayerSGForecast(
            player_id=player_id,
            mean_sg=mean_sg,
            round_sd=round_sd,
            rounds=len(rows),
            events=len({str(row["game_code"]) for row in rows}),
            effective_rounds=total_weight,
            latest_sg_date=max(str(row["date"]) for row in rows),
            has_player_sg=True,
        )
    return result


def _round_to_integer_strokes(value: float) -> int:
    """Half-away-from-zero rounding for simulated stroke differences."""
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def simulate_sg_tournament_outcomes(
    forecasts: dict[str, PlayerSGForecast],
    *,
    rounds: int = 4,
    cut_after_round: int = 2,
    cut_position: int = DEFAULT_CUT_POSITION,
    n_simulations: int = DEFAULT_SIMULATIONS,
    seed: int,
) -> dict[str, dict[str, float]]:
    """Simulate full tournaments from round-level SG forecasts.

    Higher SG is converted to fewer simulated strokes. The cut is applied
    after round two at the cut position including any tied score; all later
    outcomes are ranked among survivors. Top tiers count ties at the rank
    boundary; first-place ties divide win credit equally among tied players.
    """
    if not forecasts:
        return {}
    if rounds < 2 or not 1 <= cut_after_round < rounds:
        raise ValueError("rounds must exceed a valid cut_after_round")
    if cut_position <= 0 or n_simulations <= 0:
        raise ValueError("cut_position and n_simulations must be positive")
    players = sorted(forecasts)
    if any(not math.isfinite(f.mean_sg) or not math.isfinite(f.round_sd) or f.round_sd <= 0 for f in forecasts.values()):
        raise ValueError("all SG means and round standard deviations must be finite; SD must be positive")
    rng = random.Random(seed)
    counts = {p: [0, 0, 0, 0, 0] for p in players}  # cut, top20, top10, top5, win
    n_cut = min(cut_position, len(players))

    for _ in range(n_simulations):
        round_strokes = {
            p: [_round_to_integer_strokes(-rng.gauss(forecasts[p].mean_sg, forecasts[p].round_sd)) for _ in range(rounds)]
            for p in players
        }
        after_cut_round = {
            p: sum(round_strokes[p][:cut_after_round]) for p in players
        }
        cut_line = sorted(after_cut_round.values())[n_cut - 1]
        survivors = [p for p in players if after_cut_round[p] <= cut_line]
        total_strokes = {p: sum(round_strokes[p]) for p in survivors}
        best = min(total_strokes.values())
        winners = [p for p in survivors if total_strokes[p] == best]

        for p in survivors:
            rank = 1 + sum(score < total_strokes[p] for score in total_strokes.values())
            counts[p][0] += 1
            counts[p][1] += rank <= 20
            counts[p][2] += rank <= 10
            counts[p][3] += rank <= 5
            if total_strokes[p] == best:
                counts[p][4] += 1.0 / len(winners)

    output = {
        p: {
            "cut_probability": counts[p][0] / n_simulations,
            "top20_probability": counts[p][1] / n_simulations,
            "top10_probability": counts[p][2] / n_simulations,
            "top5_probability": counts[p][3] / n_simulations,
            "win_probability": counts[p][4] / n_simulations,
        }
        for p in players
    }
    for player_id, row in output.items():
        if not (
            row["cut_probability"] + 1e-12 >= row["top20_probability"]
            >= row["top10_probability"]
            >= row["top5_probability"]
            >= row["win_probability"]
        ):
            raise AssertionError(f"outcome nesting failed for {player_id}: {row}")
    if abs(sum(row["win_probability"] for row in output.values()) - 1.0) > 1e-9:
        raise AssertionError("win probabilities do not sum to one over the complete field")
    return output
