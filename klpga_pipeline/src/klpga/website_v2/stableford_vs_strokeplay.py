"""Stableford-vs-stroke-play ranking divergence (HJ 2026100004 gap,
step 6 of the pre-event blind backtest task, 2026-10-06).

NOT a pre-event predictive feature -- this uses each historical event's
own REAL, already-reconstructed 4-round hole outcomes (see
klpga.collectors.score_record.extract_hole_outcomes and
tests/test_stableford_2025100001_reconstruction.py /
test_stableford_2024_2023_reconstruction.py, both already SOURCE-PASS
verified) to demonstrate the SCORING TRANSFORMATION itself: for the
SAME real round of golf, why does a player's value differ between
ordinary stroke-play ranking and Modified Stableford ranking. This
validates the Stableford player archetype/scoring mechanism using
historical outcomes as worked examples -- it is explicitly NOT a
course-effect or pre-event prediction claim (see this module's sibling
stableford_backtest.py for why Iksan CC course effects must never be
transplanted to A-One CC).

THE MATHEMATICAL MECHANISM (confirmed against real field data, not
theorized in the abstract):

  Ordinary stroke-play score-to-par treats birdie and bogey
  SYMMETRICALLY: birdie = -1, bogey = +1 -- a player who trades one
  birdie for one bogey nets to zero change in stroke-play score.

  Modified Stableford's official table treats them ASYMMETRICALLY:
  birdie = +2, bogey = -1 -- a birdie is worth TWICE as much as a
  bogey costs. A player who trades one birdie for one bogey at a 1:1
  rate still GAINS +1 net Stableford point (not zero).

  Consequence: a high-birdie/high-bogey ("boom-bust") player is
  systematically UNDERVALUED by stroke-to-par and systematically
  FAVORED by Stableford scoring, relative to a low-birdie/low-bogey
  ("steady") player with the same stroke-play score-to-par. This is
  confirmed in the real 2025100001 field: 박민지 (birdie=14, bogey=9,
  eagle=2, stroke_to_par=-9, stroke-play rank 42/61) scores 29
  Stableford points (rank 28/61) -- a real rank IMPROVEMENT under
  Stableford -- while 이예원 (birdie=16, bogey=3, eagle=0,
  stroke_to_par=-13, stroke-play rank 22/61, a BETTER stroke score)
  scores the SAME 29 Stableford points but ranks 27/61 -- essentially
  unchanged, despite her stronger stroke-play card, because she had
  far fewer bogeys to begin with for the asymmetry to help her overcome.

  A second, structurally real but less sharply observed mechanism in
  this specific field: double-bogey-or-worse is capped at a flat -3 in
  Stableford regardless of how bad the hole actually was (a triple,
  quadruple, or worse all cost the same -3), while stroke-play score-
  to-par is uncapped (a quadruple bogey costs 4 strokes, not the same
  as a double's 2). A player prone to occasional blow-up holes is
  therefore relatively protected under Stableford vs stroke play --
  this project has not yet observed a field with enough high-magnitude
  blow-up holes to quantify this effect's real-world size the same way
  the birdie/bogey asymmetry above was quantified."""
from __future__ import annotations

from dataclasses import dataclass

from klpga.collectors.score_record import extract_hole_outcomes
from klpga.website_v2.stableford_scoring import HoleOutcomeCounts

ROUNDS = ("1R", "2R", "3R", "4R")


@dataclass(frozen=True)
class PlayerDivergence:
    player_name: str
    stroke_to_par: int
    stroke_play_rank: int
    stableford_points: int
    stableford_rank: int
    hole_outcomes: HoleOutcomeCounts

    @property
    def rank_shift(self) -> int:
        """Positive = ranks BETTER under Stableford than stroke play
        (stroke_play_rank - stableford_rank, both 1-best)."""
        return self.stroke_play_rank - self.stableford_rank


def compute_divergence(html: str) -> list[PlayerDivergence]:
    """Real extraction + real arithmetic, no synthetic data. Restricted
    to players present in the 4R table (made the cut, completed all 4
    rounds) with a parseable final stroke-to-par total -- the same
    "made-the-cut finalist" population already used for the full-field
    Stableford reconstruction tests."""
    from bs4 import BeautifulSoup

    by_round = extract_hole_outcomes(html)
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select("table.table-scorecard, .table-scorecard table")

    stroke_total: dict[str, int] = {}
    for table in tables:
        thead = table.find("thead")
        round_label = thead.find_all("tr")[1].find("th").get_text(strip=True)
        if round_label != "4R":
            continue
        tbody = table.find("tbody")
        for tr in tbody.find_all("tr", recursive=False):
            name_cell = tr.select_one("td.name")
            if name_cell is None:
                continue
            total_text = tr.select_one("td.total").get_text(strip=True)
            if total_text == "E":
                value = 0
            elif total_text.lstrip("+-").isdigit():
                value = int(total_text)
            else:
                continue
            stroke_total[" ".join(name_cell.get_text(" ", strip=True).split())] = value

    finalists = sorted(set(by_round["4R"].keys()) & set(stroke_total.keys()))

    def aggregate(name: str) -> HoleOutcomeCounts:
        e = b = p = bg = d = alb = 0
        for r in ROUNDS:
            c = by_round[r].get(name)
            if c is None:
                continue
            alb += c.albatross
            e += c.eagle
            b += c.birdie
            p += c.par
            bg += c.bogey
            d += c.double_or_worse
        return HoleOutcomeCounts(albatross=alb, eagle=e, birdie=b, par=p, bogey=bg, double_or_worse=d)

    outcomes = {name: aggregate(name) for name in finalists}
    stableford_points = {name: outcomes[name].total_points() for name in finalists}

    sp_order = sorted(finalists, key=lambda n: stroke_total[n])
    sp_rank = {n: i + 1 for i, n in enumerate(sp_order)}
    sf_order = sorted(finalists, key=lambda n: -stableford_points[n])
    sf_rank = {n: i + 1 for i, n in enumerate(sf_order)}

    return [
        PlayerDivergence(
            player_name=name,
            stroke_to_par=stroke_total[name],
            stroke_play_rank=sp_rank[name],
            stableford_points=stableford_points[name],
            stableford_rank=sf_rank[name],
            hole_outcomes=outcomes[name],
        )
        for name in finalists
    ]
