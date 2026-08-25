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

# Confirmed gameMethod value meaning "standard stroke play" — the only
# format the roundLeaderboard endpoint actually returns data for.
# CONFIRMED live, 2026-08-24 (100-tournament run): "1" (Match Play,
# e.g. Doosan Match Play) and "2" (Modified Stableford, e.g. 동부건설·
# 한국토지신탁 챔피언십) were BOTH found to return ZERO player rows
# across an exhaustive round=1..8 probe against the real endpoint — not
# a narrower round range, a genuinely different/unavailable data source
# for this endpoint. See docs/SITE_STRUCTURE_TODO.md for the full
# baseline-comparison writeup. Other gameMethod values may exist and
# are unconfirmed — treat anything other than "0" as unsupported by
# this pipeline until proven otherwise.
GAME_METHOD_STROKE_PLAY = "0"

# [2] Full leaderboard, per round ("FULL LEADERBOARD" round buttons)
#   POST https://klpga.co.kr/load/leaderboard/roundLeaderboard
#   Content-Type: application/x-www-form-urlencoded
#   form: gameCode=<code>, round=<n>
#   response: HTML fragment (NOT JSON) — see
#   klpga.parsers.leaderboard_parser.
ROUND_LEADERBOARD_ENDPOINT = f"{BASE_URL}/load/leaderboard/roundLeaderboard"

# [3] Upcoming/in-progress tournament entry list ("참가자 명단")
#   GET https://klpga.co.kr/web/tourInfo/entry?gameCode=<code>
#   response: text/html; charset=UTF-8 — a full rendered page (NOT JSON,
#   NOT an AJAX fragment) — see klpga.parsers.entry_list_parser.
#   Confirmed via manual browser capture, 2026-08-25 (gameCode=2026080001,
#   제15회 KG 레이디스 오픈; cross-checked against the full raw HTML the
#   user pasted verbatim, see tests/fixtures/entry_list_sample.html).
ENTRY_LIST_ENDPOINT = f"{BASE_URL}/web/tourInfo/entry"

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
