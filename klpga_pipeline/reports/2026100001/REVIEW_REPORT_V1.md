# NEO Sync Review Report — gameCode 2026100001

- Season: 2026
- Sync stage requested: results
- Generated at: 2026-10-31T09:04:10.974674+00:00
- Overall sync result: SUCCESS
- Overall validation result: PASS

## Collection stages

| Stage | Status | Detail |
|---|---|---|
| tournament_info | SUCCESS | event_name=제20회 S-OIL 챔피언십, start_date=20261029, end_date=20261101, is_completed=False |
| entry_list | SUCCESS | parsed_row_count=96, unparsed_row_count=0, matched_count=0, unmatched_count=96 |
| kranking | SUCCESS | ranking_week=2026-W43, full_population_count=736 |
| leaderboard | SUCCESS | final_round=4, player_count=96, winner_score=204 |

## Validation checks

| Check | Status | Detail |
|---|---|---|
| tournament_info_required_fields | PASS | event_name='제20회 S-OIL 챔피언십' end_date='20261101' |
| tournament_info_game_code_matches | PASS | game_code matches |
| entry_list_nonempty | PASS | 96 entrants parsed |
| entry_list_no_unparsed_rows | PASS | every row on the page parsed |
| entry_list_matches_page_total | PASS | 96 == page's own 총 참가자 |
| kranking_top10_crosscheck | PASS | TOP10 agrees between both official sources |
| kranking_top120_population | PASS | 736 ranked players found |

## Recommendation

All required stages collected and validated. Safe to publish (stage 6) and, once reviewed, merge into the production branch for downstream PRE build.
