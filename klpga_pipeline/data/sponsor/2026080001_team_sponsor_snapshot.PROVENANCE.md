# 2026080001_team_sponsor_snapshot.csv — provenance

**Source**: a real, live collection run of
`scripts/56_collect_player_team_sponsor.py` executed by the project
owner on a Windows machine with real network access to klpga.co.kr,
against the real player-profile endpoint
(`https://klpga.co.kr/web/profile/mainRecord?playerCode=<code>`),
using the roster in `data/roster/r3_finalists_2026080001.csv` (62
game_code=2026080001 POST-R3 finalists, itself re-derived from the
already-validated production `docs/index.html` Player Journey rows).

**Windows run report** (pasted verbatim by the project owner):
```
FINALISTS 62
PROFILE FETCH 62/62
IDENTITY MATCH 62/62
TEAM PRESENT 49
TEAM EMPTY 13
PARSE FAILURE 0
DUPLICATE 0
49 + 13 = 62
```
Output file on that machine:
`C:\Users\user\Desktop\Neo-golf-performance-\klpga_pipeline\data\csv\player_team_sponsor_2026080001.csv`

That file is `data/csv/*.csv`-gitignored (a per-machine collector
output, not tracked) and was never transferred into this sandbox as a
file — the project owner instead pasted its content into chat as three
screenshots of the CSV text. This project (running in a sandbox with
no network access to klpga.co.kr) transcribed those screenshots and
cross-validated the transcription two ways before treating it as
trustworthy:

1. **Row order and player_code/player_name match**: the transcribed
   62 rows, in the order they appeared across the three screenshots,
   matched `data/roster/r3_finalists_2026080001.csv` exactly —
   same 62 player_codes, in the same order, including
   less-common-looking entries like `1521,지한솔` and
   `13502,왕 즈쉬엔` and `11391,양윤서 0801(A)`. Player name spelling in
   this snapshot is taken from the roster file (machine-extracted from
   the real production page, not OCR/screenshot-read) rather than
   re-transcribed from the screenshots, to avoid a transcription typo
   in a name; only the `team_or_sponsor` value was taken from the
   screenshots.
2. **Count reconciliation**: counting present ("") vs blank values in
   the transcription gives exactly 49 present / 13 empty / 62 total —
   matching the Windows run's own reported `TEAM PRESENT 49` /
   `TEAM EMPTY 13` / `49 + 13 = 62` exactly.

Two of the 62 values (playerCode=9788 박혜준 → `두산건설 We've`,
playerCode=11134 서교림 → `삼천리`) were additionally already
independently confirmed earlier in this project via
`scripts/54_verify_player_profile_parser.py` run against the real
saved HTML fixtures for those two players, and via the real markup
fragment the project owner pasted directly for playerCode=11134 (see
`tests/fixtures/player_profile_sample_11134.html`).

**Why a separate tracked snapshot instead of the gitignored collector
output**: `data/csv/*.csv` stays gitignored because it is a
per-machine, re-derivable collector artifact (like every other
collector CSV in this project). This snapshot is instead a deliberate,
one-time, hash-verified copy of that real collection's *result* for
the current tournament, matching the same pattern already used for
other production-facing static data in this project (checked-in,
reviewable, with its provenance recorded rather than silently
regenerated).

**No sponsor value in this file was estimated, guessed, or backfilled
from any other source** (name-based inference, web search, or
otherwise) — every non-empty value traces to the real Windows
collection run above, and every empty value is a real "no team/sponsor
field returned" result from that same run, not a placeholder.

**SHA256 of `2026080001_team_sponsor_snapshot.csv`**:
`5061a05eb372017c92721adfaed3e2bac637b9929ba66d60600dc7ac77cd2dab`

**Counts**: 62 rows total, 49 with a non-empty `team_or_sponsor`, 13
with an empty `team_or_sponsor`, 0 duplicate `player_code`, 0 duplicate
`player_name` (inherited from the already-validated roster).
