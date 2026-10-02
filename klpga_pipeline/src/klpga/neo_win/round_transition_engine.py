"""Round Transition Engine (Evidence First Architecture, 2026-10-02
mission). Computes each player's STATE by comparing consecutive
rounds' raw evidence -- never reads or writes a stored state. Call it
again and you get the same answer, derived fresh every time from the
same real evidence, exactly like klpga.neo_win.hitejinro_round_page's
own _advancement_summary already does for the cut-line banner (this
module generalizes that one real precedent into a reusable, per-player,
multi-round state machine).

State vocabulary: ENTRY, ACTIVE, R1_CUT, R2_CUT, WD, DQ, FINISHED.
R1_CUT and R2_CUT are the tournament's own two real cut points
(confirmed this session against raw evidence's own legend: "* +16
컷오프 = CUT", landing exactly on the real 87/88 R1-score boundary
already used by hitejinro_round_page._advancement_summary). WD/DQ can
happen in any round. FINISHED is reached only once a real r4_score
(FR) exists for a player who was never cut/withdrawn/disqualified.

Deliberately reuses klpga.neo_win.hitejinro_round_pipeline's own
already-real, already-battle-tested raw-HTML parsing (the leaderboard
row regex and the per-player bounded exclusion-text search) rather
than re-implementing it -- a second, slightly-different regex would be
the real risk here, not a private-module import.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from klpga.neo_win import hitejinro_round_pipeline as _rp

STATES = ("ENTRY", "ACTIVE", "R1_CUT", "R2_CUT", "WD", "DQ", "FINISHED")
_TERMINAL_STATES = {"R1_CUT", "R2_CUT", "WD", "DQ"}
# This tournament's own two real cut points (not a general rule for
# every tournament -- see the design doc's evidence for why rounds 3/4
# have no further cut here).
_CUT_ROUNDS = {1: "R1_CUT", 2: "R2_CUT"}


@dataclass(frozen=True)
class RoundFact:
    """One player's real, raw-evidence-derived fact for one round --
    never a computed/derived state, only what the raw HTML literally
    says."""
    present: bool
    score: int | None
    status_text: str | None  # literal WD/DQ/CUT/기권/실격/컷오프 text, or None


def parse_round_facts(round_number: int, *, warehouse_root: Path) -> dict[str, RoundFact]:
    """Real per-player facts for one round, parsed straight from the
    Evidence Warehouse's own copy of that round's raw leaderboard
    capture (never from LEADERBOARD.json or any other derived file).
    Returns {} if this round's evidence doesn't exist in the warehouse
    yet -- never fabricates a round that hasn't happened."""
    raw_path = warehouse_root / "tournament" / _rp.GAME_CODE / f"R{round_number}" / "leaderboard_raw.html"
    if not raw_path.is_file():
        return {}
    raw_html = raw_path.read_text(encoding="utf-8")
    facts: dict[str, RoundFact] = {}
    for m in _rp._LEADERBOARD_ROW_RE.finditer(raw_html):
        player_id = m.group(1)
        rank = m.group(2)
        r_scores = {1: m.group(8), 2: m.group(9), 3: m.group(10), 4: m.group(11)}
        incomplete = rank == "999"
        score = _rp._int_or_none(r_scores[round_number]) if not incomplete else None
        status_text = _rp._exclusion_text_for_player(raw_html, player_id) if incomplete else None
        facts[player_id] = RoundFact(present=True, score=score, status_text=status_text)
    return facts


def _attributed_round(round_number: int, scores_so_far: dict[int, int | None]) -> int:
    """A WD/DQ/CUT signal can be first VISIBLE in round_number's
    evidence while actually applying to an EARLIER round (confirmed
    this session: klpga.co.kr's own system only exposes the CUT marker
    for 조하리/이수민/이소영 starting at R2's capture, even though the
    real cut was decided on R1's score alone -- they never played R2
    at all; the same real pattern holds for 고지우/황정미's WD). The
    status therefore belongs to the last round this player has a REAL
    recorded score for, never to round_number itself -- that would
    misattribute "detected at" as "applies to". Falls back to
    round_number only when the player never completed any round at all
    (e.g. 마다솜, WD before R1 itself)."""
    last_completed = max((r for r, s in scores_so_far.items() if s is not None), default=0)
    return last_completed or round_number


def _classify(
    round_number: int, fact: RoundFact | None, scores_so_far: dict[int, int | None],
) -> tuple[str, int] | None:
    """A single round's own real signal -> (new status, the round it
    actually applies to), or None if this round's evidence says
    nothing new about this player (e.g. absent from this round's DOM
    with no exclusion text -- the caller carries the prior state
    forward in that case, same real rule
    hitejinro_round_pipeline.parse_leaderboard's carry-forward already
    uses)."""
    if fact is None or not fact.present:
        return None
    if fact.status_text in ("WD", "기권"):
        return "WD", _attributed_round(round_number, scores_so_far)
    if fact.status_text in ("DQ", "실격"):
        return "DQ", _attributed_round(round_number, scores_so_far)
    if fact.status_text in ("CUT", "컷오프"):
        applies_to = _attributed_round(round_number, scores_so_far)
        return _CUT_ROUNDS.get(applies_to, "R1_CUT"), applies_to
    if fact.score is not None:
        return "ACTIVE", round_number
    return None


def compute_state(
    entrant_ids: list[str], as_of_round: int, *, warehouse_root: Path,
) -> dict[str, dict]:
    """Every entrant's state as of as_of_round, recomputed fresh from
    the Evidence Warehouse every call -- never cached to disk. Returns
    {player_id: {"status": str, "status_round": int|None,
    "r1_score": int|None, ..., "carried_forward_from_round": int|None}}.

    Terminal states (R1_CUT/R2_CUT/WD/DQ) freeze -- once reached, later
    rounds are never consulted again for that player (same principle
    as the existing carry-forward logic, generalized to every round
    instead of just handling an entirely-absent row)."""
    facts_by_round = {n: parse_round_facts(n, warehouse_root=warehouse_root) for n in range(1, as_of_round + 1)}

    result: dict[str, dict] = {}
    for pid in entrant_ids:
        status = "ENTRY"
        status_round: int | None = None
        carried_forward_from_round: int | None = None
        scores: dict[int, int | None] = {1: None, 2: None, 3: None, 4: None}

        for n in range(1, as_of_round + 1):
            if status in _TERMINAL_STATES:
                break
            fact = facts_by_round[n].get(pid)
            classified = _classify(n, fact, scores)
            if classified is None:
                continue
            new_status, applies_to_round = classified
            if fact is not None and fact.score is not None:
                scores[n] = fact.score
            if new_status != status:
                status = new_status
                status_round = applies_to_round

        if status not in _TERMINAL_STATES and status != "ENTRY":
            # real score recorded for every round up through as_of_round's
            # own cut-eligible round and the player is still ACTIVE ->
            # FINISHED only applies once FR's own real score exists.
            if as_of_round >= 4 and scores.get(4) is not None:
                status = "FINISHED"

        result[pid] = {
            "status": status,
            "status_round": status_round,
            "r1_score": scores[1], "r2_score": scores[2], "r3_score": scores[3], "r4_score": scores[4],
            "carried_forward_from_round": carried_forward_from_round,
        }
    return result
