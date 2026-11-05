# NEO Sync Review Report — gameCode 2026110001

- Season: 2026
- Sync stage requested: pre
- Generated at: 2026-11-05T11:49:51.557249+00:00
- Overall sync result: SUCCESS
- Overall validation result: PASS

## Collection stages

| Stage | Status | Detail |
|---|---|---|
| tournament_info | SUCCESS | event_name=대보 하우스디 챔피언십, start_date=20261106, end_date=20261108, is_completed=False |
| entry_list | SUCCESS | parsed_row_count=60, unparsed_row_count=0, matched_count=0, unmatched_count=60 |
| kranking | SUCCESS | ranking_week=2026-W44, full_population_count=733 |

## Validation checks

| Check | Status | Detail |
|---|---|---|
| tournament_info_required_fields | PASS | event_name='대보 하우스디 챔피언십' end_date='20261108' |
| tournament_info_game_code_matches | PASS | game_code matches |
| entry_list_nonempty | PASS | 60 entrants parsed |
| entry_list_no_unparsed_rows | PASS | every row on the page parsed |
| entry_list_matches_page_total | PASS | 60 == page's own 총 참가자 |
| kranking_top10_crosscheck | PASS | TOP10 agrees between both official sources |
| kranking_top120_population | PASS | 733 ranked players found |

## Recommendation

All required stages collected and validated. Safe to publish (stage 6) and, once reviewed, merge into the production branch for downstream PRE build.
