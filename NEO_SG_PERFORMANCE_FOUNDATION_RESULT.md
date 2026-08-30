# NEO HISTORICAL SG + PLAYER PERFORMANCE FOUNDATION

## VERDICT
PASS

## EXISTING SG INFRASTRUCTURE FOUND
Reused the official KLPGA collector `scripts/60_collect_kg_official_analytics.py`, parser/validator `website_v2/official_data.py`, existing `official_metric_value` SQLite schema for season-level statistics, raw HTTP cache/checkpoint architecture, player-code identity space, and the candidate website analytics data contract. Existing recent-event form calculations remain in `analytics/player_stats.py`; `neo_consistency_stddev` remains in `neo_win/consistency.py`; checkpoint state remains in `discovery/b2_checkpoint.py`.

## HISTORICAL SG COVERAGE
The existing canonical event artifact contains 467 official KLPGA SG rows for gameCode `2026080001`: tournament-cumulative plus R1–R4 single-round records, across SG Total, Tee-to-Green, Tee, Approach, Around-the-Green, and Putting. The new canonical export preserves player/event/date/scope/round/source/retrieval metadata and validates 467/467 rows with no duplicate identity keys or missing player/event identity.

## FILES CHANGED
`klpga_pipeline/src/klpga/analytics/sg_performance.py`, `klpga_pipeline/scripts/62_build_historical_sg_series.py`, `klpga_pipeline/content/website_v2/historical_sg_series.json`, and `klpga_pipeline/tests/test_sg_performance.py`.

## DATABASE CHANGES
None. No SQLite schema or database contents were modified. The existing database schema remains the source for season-level official metrics; event/round SG is exported from the already collected official candidate artifact without creating a parallel database.

## PLAYER PERFORMANCE WINDOWS
Implemented reusable Recent 5, Recent 10, and Season SG summaries with mean, sample count, and sample dispersion. Missing components remain `null`; no zero substitution. Deterministic trend states are `최근 상승`, `비슷한 흐름`, `최근 하락`, or `표본 부족`, using a documented 0.25 SG threshold and minimum three samples.

## SLEEPING DATA ACTIVATED
Existing recent-form and `neo_consistency_stddev` modules were inspected and kept as integration inputs to the performance-profile contract; no replacements were created. The new profile explicitly carries recent form, consistency, score-to-par, hole tendencies, and an empty `forecast_model_inputs` list to preserve model separation.

## TEST RESULTS
Focused SG/performance tests: 15 passed. Full repository suite: 1632 passed, 11 skipped. Protected evidence verifier passed for PRE/R1/R2/R3 before and after implementation.

## DATA QUALITY
Identity, event, scope, duplicate, component-nullability, and source provenance checks pass for the canonical 467-row export. Tournament-cumulative and single-round scopes are distinct. No season-level rows were mixed into event scope. CUT/WD/DQ handling remains in the existing official leaderboard/player-event contracts and was not bypassed.

## AUTOMATION ACCEPTANCE
The export is deterministic and generated from the existing official KLPGA collection artifact. Website/model paths are not changed; SG remains historical performance analysis only and is not added to the current win-probability model.

## UNRESOLVED DATA GAPS
The repository currently contains one fully normalized event artifact rather than a populated multi-season event SG warehouse. Season-level official metrics remain conservatively PIT-qualified by the existing collector/audit. Player-name encoding normalization in some raw responses remains an upstream quality issue; player IDs are preserved as the canonical identity.

## NEXT IMPLEMENTATION BOTTLENECK
Populate additional historical game codes through the existing official collector/checkpoint path, then build point-in-time-safe multi-event SG windows and calibration/backtest joins without changing forecast formulas.

BRANCH: neo-website-v2
COMMIT: pending
REMOTE: origin/neo-website-v2
PRODUCTION: not modified; not deployed
