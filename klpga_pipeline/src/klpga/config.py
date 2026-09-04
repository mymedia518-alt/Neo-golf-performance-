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

# [4] Official record interface ("거리기록 / 전체기록보기" — SG, tee
#   shot, approach, putting, etc.)
#   POST https://klpga.co.kr/load/record/loadLocationRecord
#   Content-Type: application/x-www-form-urlencoded (inferred from
#   "form-data parameters" — exact method/content-type not literally
#   confirmed, see docs/KLPGA_OFFICIAL_DATA_MAP.md)
#   form: season=<year>, menu1=<code>, menu2=<code>, menu3=<code>
#   response: text/html; charset=UTF-8 — a player-row table whose
#   record/record1..4 columns mean something DIFFERENT per metric,
#   never assumed to generalize — see klpga.discovery.response_parser.
#   Confirmed via manual browser Network capture, 2026-08-26 — see
#   docs/KLPGA_OFFICIAL_DATA_MAP.md Rounds 1-3 for the full evidence
#   log, including the still-open menu3 collision (e.g. "010102").
RECORD_TAXONOMY_ENDPOINT = f"{BASE_URL}/load/record/loadLocationRecord"

# [5] Round grouping / tee-time page ("조편성")
#   GET https://klpga.co.kr/web/tourInfo/group?gameCode=<code>
#   response: HTTP 200, text/html; charset=UTF-8
#   Confirmed via manual browser Network capture, 2026-08-28
#   (gameCode=2026080001) — the page is displaying the official Round 3
#   grouping for that gameCode at capture time.
#   ONLY the URL, HTTP method, and response content-type are confirmed.
#   The page's DOM structure — in particular how the 1R/2R/3R tabs are
#   represented (a `round` query parameter producing a distinct request
#   per tab, a client-side JS toggle with all three rounds already
#   embedded in one HTML response, or something else entirely) — has
#   NOT been confirmed against real markup. No query parameter beyond
#   gameCode is assumed or added here. See
#   klpga.collectors.group_page, which fetches this page's raw HTML and
#   deliberately does not parse it until a real markup sample (e.g.
#   tests/fixtures/group_page_sample.html, matching the
#   entry_list_sample.html precedent for klpga.parsers.entry_list_parser)
#   has been captured and reviewed.
GROUP_PAGE_ENDPOINT = f"{BASE_URL}/web/tourInfo/group"

# [5b] Official tournament record page ("대회기록")
#   GET https://klpga.co.kr/web/tourRecord/scoreRecord?gameCode=<code>
#   URL confirmed from a real captured page: the literal nav link
#   `<a class="nav-link " href="/web/tourRecord/scoreRecord?gameCode=
#   2026080001">대회기록</a>` appears in tests/fixtures/entry_list_sample
#   .html (the same real, user-pasted HTML entry_list_parser.py is
#   built and tested against for gameCode=2026080001). Only the URL
#   itself is confirmed this way -- the page has never been fetched or
#   its own DOM inspected in this project. Follow the GROUP_PAGE_
#   ENDPOINT / PLAYER_PROFILE_ENDPOINT precedent exactly: fetch only,
#   never parse, until a real HTML sample has been captured and
#   reviewed (see klpga.collectors.score_record and
#   scripts/97_fetch_score_record_sample.py).
SCORE_RECORD_ENDPOINT = f"{BASE_URL}/web/tourRecord/scoreRecord"

# [6] Player profile page ("선수 프로필" — 소속/team-sponsor, birth
#   year, member number, join year, grade)
#   GET https://klpga.co.kr/web/profile/mainRecord?playerCode=<code>
#   NOT independently confirmed by a live fetch in this project/session
#   — this sandbox has no network access to klpga.co.kr. The URL and
#   the field ORDER ("PLAYER → 선수명 → 등급 → 소속 → 출생년도 →
#   회원번호 → 입회년도") were reported by the user in chat, with two
#   claimed examples (playerCode=9788 박혜준 → 두산건설 We've;
#   playerCode=11134 서교림 → 삼천리) that are plausible (both
#   player_codes match this project's own independently-verified
#   roster for game_code=2026080001) but have NOT been cross-checked
#   against a real HTTP response by this project. Follow the
#   GROUP_PAGE_ENDPOINT precedent exactly: fetch only, do not parse,
#   until a real HTML sample has been captured — see
#   klpga.collectors.player_profile and
#   scripts/53_fetch_player_profile_sample.py.
PLAYER_PROFILE_ENDPOINT = f"{BASE_URL}/web/profile/mainRecord"

# The landing page whose DOM carries the data-menu1/data-menu2/
# data-menu3 attributes that RECORD_TAXONOMY_ENDPOINT's menu1/menu2/
# menu3 form fields are drawn from — NOT confirmed. No URL is guessed
# here; klpga.discovery.menu_taxonomy operates on whatever HTML it is
# given, and scripts/26_discover_klpga_record_taxonomy.py requires
# --source-url to be supplied explicitly rather than defaulting to an
# unverified guess. See docs/KLPGA_OFFICIAL_DATA_MAP.md's "DOM
# architecture" open question.
RECORD_TAXONOMY_SOURCE_URL = None  # intentionally unset — see above

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
