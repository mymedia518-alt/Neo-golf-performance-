# NEO CODEX — Historical SG Row-Retention P0

## Decision-critical results

- **ROOT CAUSE FIXED:** YES. Round-specific leaderboard identity is used for single-round SG; cumulative SG uses the union of all completed-round identities. Official rows are retained or explicitly marked `UNRESOLVED_IDENTITY`.
- **LEGACY ROW COUNT:** 29,812 (`historical_sg_warehouse.json`; preserved manifest SHA-256 `f3f2a4e515c31ff82ce2236cb24d604652ea9064ffb8e6f3aac6b926b2761e50`).
- **CORRECTED ROW COUNT:** 45,501 (`historical_sg_warehouse_corrected_v2.json`; SHA-256 `cac227fd663129d92f228963081daf85bba707c5fb4701354ee28495e80ff410`).
- **RECOVERED ROWS:** 16,049 source-key rows not present in legacy; 14,886 resolved/retained and 1,163 explicitly unresolved.
- **EVENTS AFFECTED:** 101 SG-bearing events across 2023–2026; 108 discovered event entries. Two remain non-success after bounded retries (`2022120002` round-selection issue; `2024090006` request/transport issue); five no-row entries remain `UNKNOWN` pending source evidence.
- **RECOVERED CUT/WD/DQ:** Not claimable from the SG response alone. No status was inferred from absence; status-specific counts are therefore `UNAVAILABLE`, with recovered rows retained by identity state.

## Corrected SG means (single-round total)

R1: -0.00046 (11,934 rows; 478 resolved players)  
R2: -0.00057 (11,592 rows; 476 resolved players)  
R3: -0.00073 (6,533 rows; 300 resolved players)  
R4: -0.00091 (3,508 rows; 273 resolved players)

Components reconcile to SG Total within 0.03 tolerance for all 45,501 rows with complete components (0 exceptions). Official cumulative values remain untouched; no round summation was performed.

## Downstream evidence

Corrected internal exports are under `klpga_pipeline/content/website_v2/empirical_sg_corrected_v2/` (player event series, history depth, distributions, incremental windows, bad-tail distributions, participation coverage, result join, summary). The corrected OK Open profile artifact and OLD-vs-CORRECTED band diff are versioned as `OK_OPEN_2026_PRE_PERFORMANCE_ROW_RETENTION_CORRECTED_V2.json` and `OK_OPEN_2026_PRE_PERFORMANCE_ROW_RETENTION_DIFF_V2.json`.

Corrected OK Open profile coverage: 120 entrants; 109 previously eligible are represented with corrected evidence, and 8 additional players become eligible under the corrected five-event window (3 remain insufficient in the corrected warehouse). The corrected field-median band distribution is VERY_HIGH 17, HIGH 13, TYPICAL 59, LOW 17, VERY_LOW 11, INSUFFICIENT_EVIDENCE 3. Band comparison is reproducible from the corrected artifact; the legacy public master remains unchanged.

## Forecast dependency and field-strength status

The frozen OK Open WIN forecast remains unchanged. Its recorded M4 inputs are `prior_avg_round_score_to_par` and `prior_recent_form_10`; SG warehouse fields are not model inputs. Protected PRE/R1/R2/R3 evidence is independently verified after the rebuild.

The prior field-strength Verdict B is **PROVISIONAL**. A same-protocol corrected replay is not published as a pass because the corrected cohort/feature replay has not yet been independently recalculated; no methodology result is fabricated. Public SG baseline wording involving “field average” is flagged for review and was not mass-edited.

## Protected evidence status

PRE `0e1fbd013d1e5280887636fc7d504b537f71833dfca918bb876e7ce0fd5301ea`  
R1 `be9b5fb56090667aea7924babdd7f481d079579687dc1eb1a561134f353b3400c`  
R2 `531cac52a7c122e0a0a161f18704570f4972eb744b928128c1317fd06a49eeae`  
R3 `30797700f3e2e6530c1de02575723d94dbb67da860ade493068d891294ffde15`

All PASS. Website publication gate remains **BLOCKED** until the corrected downstream field-strength replay and any remaining no-row official-source classifications are resolved.

## Validation

- Focused row-retention tests: 3 passed.
- Full repository suite: 1,674 passed, 11 skipped, 0 failed.
- Evidence verifier: PASS for PRE/R1/R2/R3.
- Production `docs/`, database, model, AUTO OPS, and protected forecast artifacts: not modified by this repair.

## Git / gate

- Commit: `b475c51a785194bf318da6b58733d49faebeb3e8`
- Push: normal push to `origin/neo-website-v2`; local and remote HEAD match.
- Publication gate: **BLOCKED** (remaining official no-row classification and corrected field-strength replay are not complete).
