"""Parser for the KLPGA roundLeaderboard HTML fragment.

Confirmed via browser Network capture against
  POST https://klpga.co.kr/load/leaderboard/roundLeaderboard
  form: gameCode=<code>, round=<n>
which returns an HTML fragment (not JSON).

Confirmed per-player fields, observed as attributes on the DOM (see
docs/SITE_STRUCTURE_TODO.md for the capture):

  Row-level (rank/score summary):
    data-rank            e.g. "1", "T2", "999" (see below), "CUT"/"WD"/"DQ" per
                          the task's written spec (never actually observed as
                          literal text in any live response so far)
    data-name            player's Korean name
    data-totunderpar     total score to par, e.g. "-7", "E", "+2"
    data-inghole         holes completed so far, e.g. "18" — meaning not fully
                          understood yet, see docs/SITE_STRUCTURE_TODO.md
    data-todayunderpar   today's round score to par
    data-score           total strokes
    data-round1score .. data-round4score   per-round strokes, "" if none
    data-updown           mirrors data-rank exactly in every observed case so
                          far; not otherwise used

  Detail-level (player identity):
    _gameCode, _playerCode, _playerName, _playerEngName, _round, _hole

  CONFIRMED live, 2026-08-24 (real HTML, gameCode=2026080002): a player
  who does not complete a round gets data-rank="999" (mirrored in
  data-updown) instead of a real rank, with data-score /
  data-totunderpar / data-todayunderpar all reset to the placeholder
  "0" alongside it — NOT real zero values. This is a genuine sentinel,
  handled explicitly below (see _RANK_SENTINELS). No literal "WD" or
  "DQ" text, class name, or attribute was found anywhere in the
  surrounding markup for these rows — this endpoint does not appear to
  textually distinguish withdrawal from disqualification, so this
  parser deliberately does NOT guess between them (see
  klpga.collectors.aggregate for how made_cut/withdrawn/disqualified
  are derived from this).

HTML normalizes attribute names to lowercase, and the user's capture
notes may have been taken from a JS object dump rather than raw markup,
so attribute lookups here are case-insensitive on purpose rather than
assuming one exact casing.

Design intent: don't rely on where text is positioned on the rendered
page (fragile) — read the data-* / _-prefixed attributes directly, since
those are what's actually confirmed to exist regardless of surrounding
markup/CSS changes. Anything not present in a given row is left as None
(NULL) rather than guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup, Tag

# Per the task's written spec — never actually observed as literal
# data-rank text in any live response captured so far. Kept in case a
# future response does use them.
_STATUS_VALUES = {"CUT", "WD", "DQ"}

# CONFIRMED live, 2026-08-24 (gameCode=2026080002): data-rank="999" is
# the site's real sentinel for "did not complete this round" — not a
# literal numeric rank. It cannot be distinguished into WD vs. DQ from
# this endpoint's data (no other marker was found alongside it), so it
# gets its own status distinct from the (unconfirmed) CUT/WD/DQ text
# values above, rather than being guessed into one of them.
_RANK_SENTINELS = {"999": "INCOMPLETE"}

_TIE_RANK_RE = re.compile(r"^T(\d+)$", re.IGNORECASE)
_SIGNED_INT_RE = re.compile(r"^[+-]?\d+$")

# The row scope is any element carrying data-rank — this is the one
# confirmed anchor attribute for "this element represents one player's
# leaderboard row."
_ROW_SELECTOR = "[data-rank]"

# Candidate attribute names (case-insensitive) for locating the nested
# "detail" element that carries _playerCode etc. A row's own tag may
# itself carry these attributes, or a descendant may.
_DETAIL_ATTR_CANDIDATES = ("_playercode", "_playername", "_playerengname", "_gamecode", "_round", "_hole")


def _attrs_lower(tag: Tag) -> dict[str, str]:
    return {str(k).lower(): v for k, v in tag.attrs.items()}


def _attr(tag: Optional[Tag], *names: str) -> Optional[str]:
    """Case-insensitive attribute lookup, first match among aliases wins."""
    if tag is None:
        return None
    lower = _attrs_lower(tag)
    for name in names:
        val = lower.get(name.lower())
        if val is not None:
            return val
    return None


def _clean_str(text: Optional[str]) -> Optional[str]:
    """Empty string -> None. Never invents a value for missing data."""
    if text is None:
        return None
    if isinstance(text, list):  # bs4 can return a list for some attrs
        text = " ".join(text)
    text = text.strip()
    return text if text != "" else None


def _to_plain_int(text: Optional[str]) -> Optional[int]:
    """Parse an unsigned/plain integer string (e.g. round strokes, total
    strokes, hole count). Empty/non-numeric -> None, never guessed."""
    text = _clean_str(text)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _to_stroke_count(text: Optional[str]) -> Optional[int]:
    """Parse a stroke count (a single round's score, or a tournament
    total). CONFIRMED live, 2026-08-24: a literal "0" is used as a
    placeholder alongside the data-rank="999" sentinel (see
    _RANK_SENTINELS) rather than a real score — 0 strokes is never a
    realistic value for a round or a tournament total in golf, so it's
    treated as no-data here, never as a genuine zero."""
    value = _to_plain_int(text)
    return None if value == 0 else value


def _to_signed_int(text: Optional[str]) -> Optional[int]:
    """Parse a signed 'to par' style value such as '-7' or '+2'.
    Non-numeric values like 'E' (even par) are preserved only in the
    *_display field, not forced into a fabricated 0 here."""
    text = _clean_str(text)
    if text is None:
        return None
    if not _SIGNED_INT_RE.match(text):
        return None
    return int(text)


def _find_detail_tag(row: Tag) -> Optional[Tag]:
    """Find the element (row itself, or a descendant) carrying the
    _playerCode-style detail attributes."""
    if any(_attr(row, name) is not None for name in _DETAIL_ATTR_CANDIDATES):
        return row
    for candidate_name in _DETAIL_ATTR_CANDIDATES:
        found = row.find(attrs={candidate_name: True})
        if found is not None:
            return found
    return None


@dataclass
class PlayerRoundRow:
    """One player's leaderboard row as returned for a single
    (gameCode, round) roundLeaderboard request.

    Fields mirror the confirmed minimum-collection-field list. Rank and
    to-par values keep BOTH the raw response string (never altered) and a
    best-effort normalized numeric parse (None when not cleanly numeric,
    e.g. CUT/WD/DQ/'E')."""

    game_code: Optional[str]
    player_code: Optional[str]
    player_name: Optional[str]
    player_eng_name: Optional[str]
    round_number: Optional[int]

    rank_display: Optional[str]      # raw data-rank text, e.g. "1", "T2", "CUT"
    rank: Optional[int]              # normalized numeric rank, None if not applicable
    tie_flag: bool                   # True if rank_display matched T<n>
    status: Optional[str]            # 'CUT'/'WD'/'DQ' (unconfirmed text values,
                                      # never observed live) or 'INCOMPLETE' (the
                                      # confirmed "999" rank sentinel), else None

    total_under_par_display: Optional[str]   # raw data-totunderpar text
    total_under_par: Optional[int]           # signed-int parse, None if e.g. 'E'

    today_under_par_display: Optional[str]   # raw data-todayunderpar text
    today_under_par: Optional[int]

    total_strokes: Optional[int]     # data-score
    holes_completed: Optional[str]   # data-inghole, kept as raw text (may be non-numeric)

    round1_score: Optional[int]
    round2_score: Optional[int]
    round3_score: Optional[int]
    round4_score: Optional[int]

    def has_all_four_rounds(self) -> bool:
        return all(
            v is not None
            for v in (self.round1_score, self.round2_score, self.round3_score, self.round4_score)
        )


def parse_rank(raw: Optional[str]) -> tuple[Optional[str], Optional[int], bool, Optional[str]]:
    """Returns (rank_display, rank_numeric, tie_flag, status)."""
    raw = _clean_str(raw)
    if raw is None:
        return None, None, False, None
    upper = raw.upper()
    if upper in _STATUS_VALUES:
        return raw, None, False, upper
    if raw in _RANK_SENTINELS:
        return raw, None, False, _RANK_SENTINELS[raw]
    m = _TIE_RANK_RE.match(raw)
    if m:
        return raw, int(m.group(1)), True, None
    if raw.isdigit():
        return raw, int(raw), False, None
    # Unrecognized rank text: preserve raw, don't force a numeric guess.
    return raw, None, False, None


def parse_round_leaderboard_html(
    html: str,
    game_code: Optional[str] = None,
    round_number: Optional[int] = None,
) -> list[PlayerRoundRow]:
    """Parse a roundLeaderboard HTML fragment into one PlayerRoundRow per
    player. `game_code`/`round_number` are fallbacks used only when a row
    doesn't itself carry a confirmed _gameCode/_round attribute — the
    per-row attribute always takes priority when present."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[PlayerRoundRow] = []
    seen_player_codes: set[str] = set()

    for row in soup.select(_ROW_SELECTOR):
        detail = _find_detail_tag(row)

        rank_display, rank_numeric, tie_flag, status = parse_rank(_attr(row, "data-rank"))

        # CONFIRMED live, 2026-08-24: when data-rank is the "999"
        # sentinel (status == "INCOMPLETE"), data-totunderpar /
        # data-todayunderpar are placeholder "0" alongside it, not real
        # even-par values — unlike a normal row, where "0" genuinely
        # means "E" (even par) and must be kept. Only suppressed for
        # this specific confirmed sentinel case, not generically for
        # every non-None status (CUT/WD/DQ text values are unconfirmed
        # and may behave differently if ever actually observed).
        is_incomplete_sentinel = status == "INCOMPLETE"
        total_under_par_display = None if is_incomplete_sentinel else _clean_str(_attr(row, "data-totunderpar"))
        today_under_par_display = None if is_incomplete_sentinel else _clean_str(_attr(row, "data-todayunderpar"))

        row_player_name = _clean_str(_attr(row, "data-name"))
        detail_player_name = _clean_str(_attr(detail, "_playername"))
        detail_round = _to_plain_int(_attr(detail, "_round"))
        detail_game_code = _clean_str(_attr(detail, "_gamecode"))

        player_code = _clean_str(_attr(detail, "_playerCode", "playerCode", "data-player-code"))
        # The official fragment currently renders identical desktop/mobile
        # rows twice.  Collapse only byte-identical player identities here;
        # conflicting rows remain visible to the safety gate.
        if player_code and player_code in seen_player_codes:
            continue
        if player_code:
            seen_player_codes.add(player_code)
        rows.append(
            PlayerRoundRow(
                game_code=detail_game_code or game_code,
                player_code=_clean_str(_attr(detail, "_playercode")),
                player_name=detail_player_name or row_player_name,
                player_eng_name=_clean_str(_attr(detail, "_playerengname")),
                round_number=detail_round if detail_round is not None else round_number,
                rank_display=rank_display,
                rank=rank_numeric,
                tie_flag=tie_flag,
                status=status,
                total_under_par_display=total_under_par_display,
                total_under_par=_to_signed_int(total_under_par_display),
                today_under_par_display=today_under_par_display,
                today_under_par=_to_signed_int(today_under_par_display),
                total_strokes=_to_stroke_count(_attr(row, "data-score")),
                holes_completed=_clean_str(_attr(row, "data-inghole")),
                round1_score=_to_stroke_count(_attr(row, "data-round1score")),
                round2_score=_to_stroke_count(_attr(row, "data-round2score")),
                round3_score=_to_stroke_count(_attr(row, "data-round3score")),
                round4_score=_to_stroke_count(_attr(row, "data-round4score")),
            )
        )

    return rows
