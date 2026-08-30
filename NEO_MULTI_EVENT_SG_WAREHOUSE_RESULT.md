# NEO MULTI-EVENT KLPGA SG WAREHOUSE

## EXISTING SG INFRASTRUCTURE FOUND
Reused `collectors.tournaments.fetch_game_list` and `filter_completed_regular_tour`, the established official `roundLeaderboard`/`strokesGained_detail` collector surfaces, `website_v2.official_data.parse_sg_html` and `validate_sg_record`, the existing HTTP cache/checkpoint conventions, canonical player IDs, and the existing SG performance window module.

## HISTORICAL SEASONS COLLECTED
2025 and 2026.

## TOURNAMENTS COLLECTED
49 completed stroke-play events attempted through the existing tournament infrastructure; 28 events returned usable official SG rows. 21 events returned no parseable SG rows and remain recorded in the resumable checkpoint rather than being fabricated.

## PLAYERS / TOTAL SG ROWS
205 canonical player IDs; 9,006 official SG rows.

## COMPONENT COVERAGE
Each parsed row carries SG Total, Tee-to-Green, Tee, Approach, Around-the-Green, and Putting fields with official component validation. Tournament-cumulative and single-round scopes are separate (1,802 cumulative; 7,204 single-round rows).

## MISSING DATA
Missing SG components are nullable and never replaced with zero. Events with no usable SG response remain checkpointed as attempted/no-row coverage. No synthetic records were added.

## NAME ENCODING STATUS
Player IDs/player codes remain canonical identity. Public display names are standardized from the official parser output; the warehouse records raw and standardized names plus an explicit encoding status. Current warehouse rows are clean after parser normalization; any future corrupted raw value is preserved and flagged rather than used for identity.

## RECENT5 REAL DATA STATUS
Available through reusable `sg_window_summary`/`compute_sg_windows` over real multi-event cumulative SG rows.

## RECENT10 REAL DATA STATUS
Available where a player has at least ten real cumulative event rows; sample count is explicit and smaller samples are not mislabeled as complete windows.

## SEASON PROFILE STATUS
Available for the collected 2025–2026 event set. Profiles retain mean, sample count, dispersion, score/form/consistency integration slots, and explicit separation from forecast-model inputs.

## PARK HYE-JUN CONFLICT STATUS
Unresolved and unpublished. `6 birdies / 1 bogey` remains UNVERIFIED; `5 birdies / 0 bogeys` remains LOCAL_CANONICAL_PENDING_SOURCE_RECHECK. No editorial interpretation uses either claim until reconciled against an authoritative source.

## TESTS
Focused SG tests: 7 passed. Previous full repository baseline remains 1632 passed, 11 skipped before this cycle; the new warehouse tests pass against the populated artifact. Protected evidence verifier passed for PRE/R1/R2/R3.

## NEXT BOTTLENECK
Extend collection across additional seasons using the same checkpoint path, and perform an authoritative Park Hye-jun scorecard recheck before exposing R4 composition editorially.

COMMIT: pending
REMOTE: origin/neo-website-v2
PRODUCTION: not modified; not deployed
