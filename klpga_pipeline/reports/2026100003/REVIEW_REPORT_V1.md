# NEO Sync Review Report — gameCode 2026100003

- Season: 2026
- Sync stage requested: pre
- Generated at: 2026-10-15T09:13:33.129367+00:00
- Overall sync result: SUCCESS
- Overall validation result: PASS

## Collection stages

| Stage | Status | Detail |
|---|---|---|
| tournament_info | SUCCESS | event_name=아이스버그골프 · 서울신문 오픈, start_date=20261016, end_date=20261018, is_completed=False |
| entry_list | SUCCESS | parsed_row_count=108, unparsed_row_count=0, matched_count=0, unmatched_count=108 |
| kranking | SUCCESS | ranking_week=2026-W41, full_population_count=745 |

## Validation checks

| Check | Status | Detail |
|---|---|---|
| tournament_info_required_fields | PASS | event_name='아이스버그골프 · 서울신문 오픈' end_date='20261018' |
| tournament_info_game_code_matches | PASS | game_code matches |
| entry_list_nonempty | PASS | 108 entrants parsed |
| entry_list_no_unparsed_rows | PASS | every row on the page parsed |
| entry_list_matches_page_total | PASS | 108 == page's own 총 참가자 |
| kranking_top10_crosscheck | PASS | TOP10 agrees between both official sources |
| kranking_top120_population | PASS | 745 ranked players found |

## Recommendation

All required stages collected and validated. Safe to publish (stage 6) and, once reviewed, merge into the production branch for downstream PRE build.
