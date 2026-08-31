# OK Open 2026 · KLPGA Data Center profile validation

Canonical current source: `https://k-rankings.klpga.co.kr/kranking.jsp` and its linked `playerprofile.jsp?player_code=...` profiles. One snapshot week (`2026-W35`) is used for all records.

## Result

- Frozen entrants: 120; profile rows collected: 120
- Current name: 119 parsed, 1 official endpoint access failure (`player_id=7963` returned HTTP 500 after three retries)
- K-RANKING / ranking points / total points / events played: 119 parsed; the same endpoint failure remains explicitly classified
- TEAM: 97 parsed; 22 `OFFICIAL_NULL` (the profile renders no team value); 1 `ACCESS_FAILURE`; parser failures: 0; identity failures: 0
- No historical amateur/status suffix was used to derive current identity.

## Controls

- `서교림` (`player_id=11134`): K-RANKING 2, TEAM `삼천리`, ranking points 9.5546, total points 544.61, events played 57.
- `김민솔` (`player_id=10725`): current name `김민솔`, TEAM `두산건설 We've`, K-RANKING 1, ranking points 10.7425, total points 547.87, events played 51. Historical `김민솔 0606(A)` remains provenance only.

The audit artifact records source URL, ranking week, retrieval timestamp, parser state, and explicit team-null/access classifications for every entrant. Because one canonical profile endpoint remains unavailable, the 120-player canonical audit is **HARD STOP / incomplete**. Website generation and deployment were not performed.
