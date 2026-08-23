"""CSS/DOM selectors used by parsers, isolated in one place on purpose.

None of these have been confirmed against the live klpga.co.kr /
data.klpga.co.kr markup — the development environment this project was
built in has no outbound network access to those hosts. Update these
constants after inspecting the real pages in a browser; the parser
modules that use them should not need to change, only these values.

See docs/SITE_STRUCTURE_TODO.md for what to confirm.
"""

TOURNAMENT_LIST = {
    "row": "table.tourSchedule tbody tr",
    "name": "td.tournament-name a",
    "id_attr": "href",
    "period": "td.period",
    "status": "td.status",
    "type": "td.tour-type",
}

TOURNAMENT_DETAIL = {
    "course_name": ".tournament-info .course-name",
    "par": ".tournament-info .par",
    "yardage": ".tournament-info .yardage",
    "rounds_scheduled": ".tournament-info .rounds",
}

LEADERBOARD = {
    "row": "table.leaderboard tbody tr",
    "rank": "td.rank",
    "player_name": "td.player-name a",
    "player_id_attr": "href",
    "total_score": "td.total-score",
    "total_strokes": "td.total-strokes",
    "round_cell": "td.round-score",
}
