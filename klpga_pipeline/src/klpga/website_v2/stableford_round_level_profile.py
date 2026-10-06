"""Round-level pre-event scoring-ceiling/volatility profile (HJ
2026100004 gap, three-winner pre-event profile validation, continued
2026-10-06).

Reuses the SAME 19/23/23 real prior-tournament scoreRecord captures
already acquired and SOURCE_PASS-verified for the 2023/2024/2025 blind
backtests (evidence/stableford_prior_<year>/) -- no new acquisition,
no new network access. klpga.collectors.score_record.extract_hole_outcomes
collapses each player's rows into one HoleOutcomeCounts per (round
table, player) already; what's new here is NOT re-aggregating across
tournaments the way klpga.website_v2.stableford_blind_backtest does --
this module keeps every individual round as its own row, because
scoring-ceiling/volatility questions (avg birdies per round, round-to-
round variance, "sub-70 round" frequency) need the per-round
granularity that module intentionally discards.

STROKE TOTALS are read directly from each hole-outcome-classed td's own
raw digit text (not derived from the outcome class), since the class
alone can't distinguish a double bogey from a triple -- this is the
exact same raw-digit-summing approach used earlier this session to
cross-check 김민솔's displayed strokes-to-par, just applied here to get
an absolute round total rather than a relative one."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

from klpga.website_v2.stableford_scoring import HoleOutcomeCounts, SCORING_TABLE

_OUTCOME_CLASSES = ("par", "birdies", "bogeys", "Dbogeys", "eagles", "albatross", "albatrosses")
_CLASS_TO_FIELD = {
    "par": "par", "birdies": "birdie", "bogeys": "bogey", "Dbogeys": "double_or_worse",
    "eagles": "eagle", "albatross": "albatross", "albatrosses": "albatross",
}


@dataclass(frozen=True)
class RoundRecord:
    player_name: str
    game_code: str
    round_label: str
    stroke_total: int  # raw sum of the 18 hole-cell digits, absolute strokes
    counts: HoleOutcomeCounts
    hole_pars: tuple[int, ...]  # the 18 real hole pars from this table's own header, same order as hole_strokes
    hole_strokes: tuple[int, ...]  # the 18 real raw stroke digits, same order as hole_pars

    @property
    def stableford_points(self) -> int:
        return self.counts.total_points()

    @property
    def par5_strokes(self) -> list[int]:
        return [s for p, s in zip(self.hole_pars, self.hole_strokes) if p == 5]


def _extract_hole_pars(header_rows) -> list[int]:
    """The real per-hole par row -- same header row2 already used
    elsewhere in this project for the round label, filtered to the
    18 real numeric hole-par th's (excluding today/out/in)."""
    return [
        int(th.get_text(strip=True))
        for th in header_rows[1].find_all("th")
        if not any(c in ("today", "out", "in") for c in (th.get("class") or []))
        and th.get_text(strip=True).isdigit()
    ]


def extract_round_records(html: str, game_code: str) -> list[RoundRecord]:
    """One RoundRecord per (round table, player row with 18 real hole
    cells) -- rows with 0 holes (WD/no-show) are skipped, matching
    every other module's convention in this project."""
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for table in soup.select("table.table-scorecard, .table-scorecard table"):
        thead = table.find("thead")
        tbody = table.find("tbody")
        if thead is None or tbody is None:
            continue
        header_rows = thead.find_all("tr")
        if len(header_rows) < 2:
            continue
        round_label_th = header_rows[1].find("th")
        round_label = " ".join(round_label_th.get_text(" ", strip=True).split()) if round_label_th else None
        if not round_label:
            continue
        hole_pars = _extract_hole_pars(header_rows)
        if len(hole_pars) != 18:
            continue  # malformed header -- skip this table entirely rather than mis-zip pars to strokes

        for tr in tbody.find_all("tr", recursive=False):
            name_cell = tr.select_one("td.name")
            if name_cell is None:
                continue
            player_name = " ".join(name_cell.get_text(" ", strip=True).split())
            cells = [
                td for td in tr.find_all("td")
                if any(c in _OUTCOME_CLASSES for c in (td.get("class") or []))
            ]
            if len(cells) != 18:
                continue
            counts_dict = {"albatross": 0, "eagle": 0, "birdie": 0, "par": 0, "bogey": 0, "double_or_worse": 0}
            stroke_total = 0
            hole_strokes: list[int] = []
            valid = True
            for td in cells:
                text = td.get_text(strip=True)
                if not text.isdigit():
                    valid = False
                    break
                field = next(_CLASS_TO_FIELD[c] for c in (td.get("class") or []) if c in _CLASS_TO_FIELD)
                counts_dict[field] += 1
                stroke_total += int(text)
                hole_strokes.append(int(text))
            if not valid:
                continue
            counts = HoleOutcomeCounts(**counts_dict)
            if counts.total_holes != 18:
                continue
            records.append(RoundRecord(
                player_name=player_name, game_code=game_code, round_label=round_label,
                stroke_total=stroke_total, counts=counts,
                hole_pars=tuple(hole_pars), hole_strokes=tuple(hole_strokes),
            ))
    return records


def load_all_round_records(manifest_path: Path, prior_dir: Path) -> dict[str, list[RoundRecord]]:
    """player_name -> every real round record across every prior
    tournament in the manifest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    game_codes = [e["game_code"] for e in manifest["entries"]]
    by_player: dict[str, list[RoundRecord]] = {}
    for game_code in game_codes:
        html = (prior_dir / f"{game_code}_scoreRecord.html").read_text(encoding="utf-8")
        for rec in extract_round_records(html, game_code):
            by_player.setdefault(rec.player_name, []).append(rec)
    return by_player


HIGH_SCORING_ROUND_THRESHOLD = 10  # net Stableford points in a single round -- predeclared, not tuned to any result


@dataclass(frozen=True)
class ScoringCeilingProfile:
    player_name: str
    rounds_n: int
    tournaments_n: int
    avg_birdies_per_round: float
    max_birdies_per_round: int
    top10pct_avg_birdies_per_round: float  # average of the top ceil(10%) rounds by birdie count, min 1 round
    sub70_round_rate: float  # fraction of rounds with stroke_total < 70
    round_points_variance: float  # population variance of per-round Stableford points
    high_scoring_round_rate: float  # fraction of rounds with round Stableford points >= HIGH_SCORING_ROUND_THRESHOLD


def compute_scoring_ceiling_profile(player_name: str, rounds: list[RoundRecord]) -> ScoringCeilingProfile:
    n = len(rounds)
    tournaments_n = len({r.game_code for r in rounds})
    birdie_counts = [r.counts.birdie for r in rounds]
    avg_birdies = sum(birdie_counts) / n
    max_birdies = max(birdie_counts)
    top_k = max(1, -(-n // 10))  # ceil(n * 0.10), at least 1
    top10pct_avg = sum(sorted(birdie_counts, reverse=True)[:top_k]) / top_k
    sub70 = sum(1 for r in rounds if r.stroke_total < 70) / n
    points = [r.stableford_points for r in rounds]
    mean_points = sum(points) / n
    variance = sum((p - mean_points) ** 2 for p in points) / n
    high_scoring_rate = sum(1 for p in points if p >= HIGH_SCORING_ROUND_THRESHOLD) / n
    return ScoringCeilingProfile(
        player_name=player_name, rounds_n=n, tournaments_n=tournaments_n,
        avg_birdies_per_round=round(avg_birdies, 4), max_birdies_per_round=max_birdies,
        top10pct_avg_birdies_per_round=round(top10pct_avg, 4), sub70_round_rate=round(sub70, 4),
        round_points_variance=round(variance, 4), high_scoring_round_rate=round(high_scoring_rate, 4),
    )


@dataclass(frozen=True)
class ReconstructedOfficialStats:
    """Average Score and Par5 scoring, RECONSTRUCTED (category B, see
    STABLEFORD_THREE_WINNER_PRE_EVENT_PROFILE_V1.md) directly from the
    same real pre-cutoff hole-by-hole captures already used everywhere
    else in this project -- no new network access, no new acquisition.
    Matches KLPGA's own official definition (평균타수 = 전체타수/라운드수,
    파5성적 = 파5 전체타수/파5 홀수, confirmed against the real
    publicRecordSeasonDetail fixture: tests/fixtures/official_detail/
    8436_publicRecordSeasonDetail.html) -- the same arithmetic, applied
    to this project's own real pre-cutoff rounds instead of KLPGA's
    season-cumulative (and therefore not usable as-is without the
    gameCode-scoping question resolved -- see the acquisition script
    for that separate, GIR/Fairway/Driving-Distance-only effort)."""
    player_name: str
    rounds_n: int
    avg_score: float  # total strokes / rounds
    total_strokes: int
    par5_holes_n: int
    par5_scoring: float | None  # total par5 strokes / par5 holes count, None if par5_holes_n == 0


def compute_reconstructed_official_stats(player_name: str, rounds: list[RoundRecord]) -> ReconstructedOfficialStats:
    n = len(rounds)
    total_strokes = sum(r.stroke_total for r in rounds)
    par5_strokes: list[int] = []
    for r in rounds:
        par5_strokes.extend(r.par5_strokes)
    par5_n = len(par5_strokes)
    par5_scoring = round(sum(par5_strokes) / par5_n, 4) if par5_n else None
    return ReconstructedOfficialStats(
        player_name=player_name, rounds_n=n,
        avg_score=round(total_strokes / n, 4), total_strokes=total_strokes,
        par5_holes_n=par5_n, par5_scoring=par5_scoring,
    )
