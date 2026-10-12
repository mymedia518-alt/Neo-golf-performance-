# 유현조 (KLPGA playerCode 10146) shot-tracker archive

## Coverage

- Collection date: 2026-10-12 (KST).
- Seasons: 2025 and 2026 through events completed by 2026-10-12. Future 2026 events are not yet included.
- Official schedule scope: 31 completed 2025 regular-tour events and 26 completed 2026 regular-tour events. Official entry pages were checked to identify the player’s events.
- Shot endpoint returned target-player rows in 44 events. Another 4 entry-list candidate events returned no target rows across all 18 holes. One 2025 match-play event returned HTTP 500 on the probe. Events where the player was not on the official entry list are marked in `event_audit.csv` and were not queried.
- Collected 48 candidate events × 18 holes = 864 HTTP 200 shot responses. Responses contain records for other players too; each response is preserved unchanged.
- Derived target-only CSVs contain 13,469 records total: 7,994 in 2025 and 5,475 in 2026.

## Layout

- `2025/<gameCode>_<event>/raw/hole_01.json` … `hole_18.json`: exact API response bodies.
- `2025/<gameCode>_<event>/yoo_hyunjo_shots.csv`: target-only derived rows.
- `2025/<gameCode>_<event>/collection_metadata.json`: query details, status, SHA-256, row counts and round coverage.
- Same layout under `2026/`.
- `source/official_schedule_2025.json`, `source/official_schedule_2026.json`: KLPGA schedule responses used for event scope.
- `source/official_entrylist_scan.json`: official entry-list scan metadata and response hashes.
- `source/shot_api_availability_probe.json`: per-event API availability probe.
- `event_audit.csv`: all completed regular-tour event decisions, including not-on-entry-list events and data gaps.
- `index.json`: event-level collection index.

## Source and interpretation

Shot endpoint: `https://cmpro.klpga.co.kr/map3d/getData?method=shotData&gameCode={gameCode}&playerCode=10146&round=4&hole={hole}`. The `round=4` parameter is retained from the working tracker request; each response’s `GameRound` field is used to identify the actual round.

`ShotNum=0` is a location/reference row and is included in raw files and CSVs; exclude it from stroke-count calculations. `ShotType` code meanings are not inferred here. Two-round coverage is the observed API coverage only; it is not independently labeled as a cut, withdrawal, or tournament-format outcome.

## Reproducibility and integrity

Each event manifest records file SHA-256 hashes. Raw responses are never overwritten by derived transformations. `source/` carries the endpoint probe and official event schedule/entry evidence so collection boundaries remain auditable.
