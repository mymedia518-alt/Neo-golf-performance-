"""Endpoint + constant configuration for the KLPGA collectors.

Every value in the CONFIRMED sections below was observed directly in a
browser DevTools Network capture against the live site (see
docs/SITE_STRUCTURE_TODO.md for the capture log). Nothing here is a
guessed selector or an assumed endpoint path.

Anything NOT yet confirmed against a live response is called out
explicitly in a comment — do not treat those as verified.
"""
from __future__ import annotations

# ============================================================
# CONFIRMED — browser Network capture, see docs/SITE_STRUCTURE_TODO.md
# ============================================================

BASE_URL = "https://klpga.co.kr"

# [1] Tournament list ("정규투어 대회 목록")
#   POST https://klpga.co.kr/ajax/tourInfo/getGameList
#   Content-Type: application/x-www-form-urlencoded
#   form: season=<year>, tourType=RE, year=
#   response: application/json, top-level key "gameList" (a list).
GAME_LIST_ENDPOINT = f"{BASE_URL}/ajax/tourInfo/getGameList"

# Confirmed tourType value for the KLPGA regular tour.
# Other tour types (Dream Tour / Jump Tour / Champions Tour / events) exist
# on the site but their tourType codes have NOT been confirmed — do not
# assume values for them.
TOUR_TYPE_REGULAR = "RE"

# Confirmed gameFinish value meaning "tournament completed".
# Other gameFinish values (e.g. in-progress, cancelled, upcoming) have NOT
# been confirmed — do not assume what they are.
GAME_FINISH_DONE = "F"

# [2] Full leaderboard, per round ("FULL LEADERBOARD" round buttons)
#   POST https://klpga.co.kr/load/leaderboard/roundLeaderboard
#   Content-Type: application/x-www-form-urlencoded
#   form: gameCode=<code>, round=<n>
#   response: HTML fragment (NOT JSON) — see
#   klpga.parsers.leaderboard_parser.
ROUND_LEADERBOARD_ENDPOINT = f"{BASE_URL}/load/leaderboard/roundLeaderboard"

# ============================================================
# UNCONFIRMED / project-level assumptions — recheck against live
# responses before trusting them. See docs/SITE_STRUCTURE_TODO.md.
# ============================================================

# Historical Database spec target: exactly 100 most-recently-completed
# regular tour events. This is a project requirement, not a site fact.
TARGET_COMPLETED_TOURNAMENTS = 100

# KLPGA regular tour events are commonly scheduled over 4 rounds, but this
# has NOT been confirmed from a live response (no "rounds_scheduled"-like
# field has been observed in getGameList). Collectors use this only as a
# starting point to probe for the actual final round via
# klpga.collectors.leaderboard.discover_final_round — never as a value
# written directly into tournament_master.rounds_scheduled.
PROBE_MAX_ROUNDS = 4

# Earliest season to walk back to when accumulating the 100 most recent
# completed events, purely a safety bound against an infinite loop if the
# site ever returns an unexpectedly empty gameList for many seasons in a
# row. Not derived from any confirmed site fact.
MIN_SEASON_FLOOR = 2000
