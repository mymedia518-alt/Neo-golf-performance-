"""NEO Reader / NEO Sync -- the one pipeline that turns a bare gameCode
into the official, committed artifact set (raw/, normalized/, reports/)
every downstream workflow (PRE, R1-R4, FINAL, HOME, Player Reports,
Rankings) is required to build from.

MISSION (2026-09-30, operator directive): "The Sync pipeline becomes the
official source of truth. After a successful sync, every downstream
workflow must consume only the synchronized artifacts. No downstream
workflow should ever depend on live KLPGA access again." This package
is the only place in the pipeline that is allowed to reach klpga.co.kr
or k-rankings.klpga.co.kr; every page-builder script continues to read
only already-materialized files under content/website_v2/, exactly as
139/151/160/174/181/156 already do for tournament 2026090002.

This package does not invent any endpoint. Every URL it calls is one
already confirmed and documented in klpga.config (GAME_LIST_ENDPOINT,
ENTRY_LIST_ENDPOINT, ROUND_LEADERBOARD_ENDPOINT) or already cited as
the real source in scripts/87_collect_kranking_top120.py
(k-rankings.klpga.co.kr). No new endpoint is guessed into existence
here -- see klpga.neo_reader.kranking's own docstring for the one
narrow exception (a live-fetch wrapper around an already-confirmed URL
that previously only had a local-file-input path).

Runs entirely from a machine with real network access to klpga.co.kr --
this sandbox does not have one (confirmed: klpga.co.kr:443 returns 403
at the egress proxy's CONNECT step). See scripts/neo-sync.ps1 for the
operator-facing entry point."""
