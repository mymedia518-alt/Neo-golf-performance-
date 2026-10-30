# Validation — player 8380, season 2026

**Result: PASS** — INFO 6, PASS 19, WARN 1

| id | status | check |
|---|---|---|
| A1 | PASS | Every official round has raw data and vice versa |
| A2 | PASS | Each raw round has holes 1-18 |
| A3 | PASS | No conflicting re-collections (sha-suffixed copies) |
| A4 | PASS | Stated events count |
| A4 | PASS | Stated rounds count |
| A4 | PASS | Stated hole files count |
| B1 | PASS | Stored raw bytes still match intake sha256 |
| B2 | PASS | Collector error log is empty |
| C1 | PASS | Response structure identical across files; top-level blocks equal model blocks |
| D1 | PASS | gameCode/round/hole/playerCode inside every response match its path |
| E1 | PASS | Shots are 1..n per hole, exactly one HOLED(10), and it is the last shot |
| F1 | PASS | All pp_state codes are in the official table |
| F2 | PASS | No shot fields outside the known set |
| G1 | INFO | pp_distance on the HOLED shot (consistent with a remaining-to-hole distance if all 0) |
| H1 | PASS | Stroke-play rounds: shot rows == official round score |
| H2 | INFO | Non-stroke-play rounds excluded from score comparison (official value is not a stroke total) |
| H3 | PASS | Official schedule lists every event and its gameMethod equals the player record's gameType |
| I1 | PASS | Par of a hole is the same in every round of an event |
| I2 | INFO | Holes whose listed yds differ between rounds (tee changes are normal) |
| I3 | INFO | Course par per event (sum of holeInfo.stdScore) |
| J1 | INFO | Par-4/5 shot 1: pp_distanceLen + pp_distance compared with holeInfo.yds and holeInfo.meter |
| J2 | INFO | Observed value ranges (coordinate systems are NOT geographic; see archive README) |
| J3 | WARN | pp_altitude sentinel values (<= -1000) -- preserved as-is; must be excluded from any elevation use |
| K1 | PASS | Normalized CSVs reproduce raw exactly (row counts, raw_json, sha256) |
| K2 | PASS | Stated shot count |
| L1 | PASS | Same shots in independent collection (group endpoint full-field run, branch collector-output/2026100005-shot-tracker-full-field) |

Details for every check: `validation_report.json`.
