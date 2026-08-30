# NEO MULTI-EVENT SG EXPANSION RESULT

## VERDICT
PASS

## SEASONS
2025, 2026

## EVENTS ATTEMPTED / WITH SG / WITHOUT SG
49 attempted; 48 with usable official SG; 1 without usable SG after safe retry.

## NO-ROW REASON BREAKDOWN
The sole remaining no-row event is classified `OFFICIAL_SG_NOT_AVAILABLE`: its official SG response contains the table/header but zero body rows. No event was labeled unavailable merely because a parser returned zero. Earlier zero-row events were recovered by selecting the latest non-empty official leaderboard round (3-round events instead of assuming round 4).

## PLAYERS / TOTAL SG ROWS
220 canonical players; 14,245 official SG rows.

## ROW SCOPES
3,112 tournament-cumulative rows and 11,133 single-round rows.

## COMPONENT COVERAGE / MISSING DATA
SG Total, Tee-to-Green, Tee, Approach, Around-the-Green, and Putting are present for every parsed row in this warehouse; missingness is represented as NULL by the reusable schema. No synthetic zeros or values were introduced.

## NAME ENCODING STATUS
Player ID/player code is canonical. Standardized display names and raw names are carried with explicit encoding status; no display-name string is used as identity.

## PERFORMANCE WINDOWS
Recent 5 eligible players: 144. Recent 10 eligible players: 112. Season-profile eligible players: 220. Means, sample counts, dispersion, deterministic trends, recent-form and consistency integration remain separate from the win-probability model.

## PARK HYE-JUN CONFLICT STATUS
Still unresolved and unpublished. 6 birdies / 1 bogey remains UNVERIFIED; 5 birdies / 0 bogeys remains LOCAL_CANONICAL_PENDING_SOURCE_RECHECK.

## TESTS
Focused warehouse tests: 8 passed. Full repository suite is being rerun after this expansion; protected evidence verification passed before collection retry and after warehouse generation.

## PROTECTED EVIDENCE
PRE `0e1fbd013d1e5280887636fc7d504b537f71833dfca918bb876e7ce0fd5301ea`; R1 `be9b5fb56090667aea7924abdd7f481d079579687dc1eb1a561134f353b3400c`; R2 `531cac52a7c122e0a0a161f18704570f4972eb744b928128c1317fd06a49eeae`; R3 `30797700f3e2e6530c1de02575723d94dbb67da860ade493068d891294ffde15` — unchanged.

## COMMIT / PUSH
Pending until the full suite completes; candidate-only changes will be committed explicitly and pushed normally to `origin/neo-website-v2`.

## NEXT BOTTLENECK
Extend the same checkpointed collector to earlier seasons, preserving event-format and no-row reason evidence, then resolve the Park Hye-jun source discrepancy.

PRODUCTION: not modified; not deployed
