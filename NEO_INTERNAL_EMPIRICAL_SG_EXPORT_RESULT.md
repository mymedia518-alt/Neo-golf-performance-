# NEO Internal Empirical SG Export

Status: PASS (internal research export; no public UI changes)

## Existing data reused

The export reuses the resumable official KLPGA SG warehouse and checkpoint
(`klpga_pipeline/content/website_v2/historical_sg_warehouse.json` and
`sg_warehouse_checkpoint.json`). Identity is keyed by canonical `player_id`;
source URLs and retrieval timestamps are retained on every event/round row.

## Artifacts

Generated under `klpga_pipeline/content/website_v2/empirical_sg/`:

- `player_event_series.json`: 6,609 cumulative player-event rows.
- `player_history_depth.json`: 305 player profiles and depth distributions.
- `between_player_distributions.json`: component percentiles, variance and sample-size distribution.
- `incremental_windows.json`: current, recent3, recent5, recent10, season and multi-season windows with counts.
- `bad_tail_distributions.json`: empirical p01/p05/p10 tails for event and round SG; threshold intentionally not selected.
- `participation_sg_coverage.json`: explicit event SG-availability states, including no-row starts.
- `result_performance_join.json`: validated official FINAL result joined to SG where available.
- `export_summary.json`: machine-readable counts and completeness summary.

## Coverage and history

- Seasons: 2023–2026.
- Events with SG: 102; no SG rows: 5 official-unavailable events; one distinct round-selection issue is preserved.
- Cumulative rows: 6,609; round rows: 23,203; players: 305.
- History depth: 1+ 305, 3+ 219, 5+ 194, 10+ 161, 20+ 109, 30+ 84; multiple seasons 180.
- All six SG components are complete for observed rows; missing values remain NULL in the export logic.

## Integrity and separation

No synthetic values or editorial conclusions are generated. Starts without SG
remain explicit (`OFFICIAL_SG_NOT_AVAILABLE` or `ROUND-SELECTION_ISSUE`) and
are not compressed into zeros. Performance exports are separate from the win
probability model and do not alter forecast records.

Protected PRE/R1/R2/R3 evidence verification passed before and after export:

```
PRE 0e1fbd013d1e5280887636fc7d504b537f71833dfca918bb876e7ce0fd5301ea
R1  be9b5fb56090667aea7924babdd7f481d079579687dc1eb1a561134f353b3400c
R2  531cac52a7c122e0a0a161f18704570f4972eb744b928128c1317fd06a49eeae
R3  30797700f3e2e6530c1de02575723d94dbb67da860ade493068d891294ffde15
```

The repository contains legacy/prototype surfaces with 7.40%, while the
protected `beta001.json` display record and verified R3 evidence use 7.47%.
This export does not overwrite either surface; protected evidence remains
authoritative and the discrepancy remains documented for separate forensic
resolution. The Park Hye-jun 6-birdie/1-bogey versus local 5-birdie/0-bogey
conflict remains UNRESOLVED pending authoritative source recheck and is not
published as an editorial fact.

## Validation

- Focused SG/export tests: 10 passed.
- Full repository suite: 1,634 passed, 11 skipped.
- Evidence verifier: all four protected hashes PASS; forecast/result separation PASS.
- Production `docs/`, database, model, and AUTO OPS: unchanged; no deployment.

Implementation files: `scripts/65_export_empirical_sg_validation.py`,
`tests/test_empirical_sg_export.py`, expanded warehouse/checkpoint/audit and
the eight JSON artifacts listed above.
