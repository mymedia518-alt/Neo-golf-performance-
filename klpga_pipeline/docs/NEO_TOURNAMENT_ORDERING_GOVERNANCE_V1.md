# NEO Tournament Ordering Governance V1

**Mission V9 (2026-09-25).** Follow-up to the original tournament-ordering
RED TEAM mission (`src/klpga/tournament_ordering.py`), which fixed the real
bug — `game_code` is an internal id, not a date, and sorting a player's
tournaments by `(season, game_code)` alone can put a later-ended tournament
before an earlier-ended one within the same season — across every module
that renders a player's career chronology to a reader.

That mission deliberately excluded SG walk-forward models, ranking/backtest
algorithms, and raw collection/export scripts as "a different risk class."
This document turns that exclusion into an explicit, enforced classification
instead of an unenforced convention, per the instruction: **do not make this
a repository-wide import rule** — classify every module into exactly one of
three roles, and only two of the three ever carry a requirement.

## The three roles

### 1. Chronology Consumer
Renders tournament history to users. **MUST** import and use
`klpga.tournament_ordering`. CI fails otherwise.

### 2. Chronology Producer
Collects, reconciles, exports, or stores tournament data. **No
requirement** to use `tournament_ordering.py`. This is the default role —
a module not explicitly classified as Consumer or Algorithm is a Producer,
by design.

### 3. Algorithm
Ranking, walk-forward, Monte Carlo, Expected Strokes, simulations,
backtests. May use their own ordering — **but every local ordering must
carry a one-line comment explaining why `tournament_ordering.py` is
intentionally not used.** CI fails if that justification comment is
missing.

## Directories / files per role

### Consumer (must import `klpga.tournament_ordering`)

| File | Status |
|---|---|
| `src/klpga/knowledge_engine/knowledge_engine.py` | already compliant (original mission) |
| `scripts/build_10097_player_history.py` | already compliant (original mission) |
| `scripts/build_10097_player_intelligence_report.py` | already compliant (original mission) |
| `scripts/build_10097_master_player_analysis.py` | already compliant (original mission) |
| `scripts/build_9431_player_intelligence_report.py` | already compliant (original mission) |
| `scripts/build_9431_master_player_analysis.py` | already compliant (original mission) |
| `src/klpga/website_v2/tournament_chronology.py` | **fixed this mission** — see below |

Forward-looking coverage (no test edit needed for a new player): any file
matching `scripts/build_*_player_history.py`,
`scripts/build_*_player_intelligence_report.py`,
`scripts/build_*_master_player_analysis.py`, or any file under
`src/klpga/website_v2/` whose name contains `player_history`,
`player_intelligence`, `tournament_chronology`, or `tournament_history`.

**The one real gap found and fixed:** `tournament_chronology.py` (HOME's
지난/이번/다음 대회 cards) sorted schedule entries by their own real
`start_date`/`end_date` directly — never the `(season, game_code)` proxy,
so the original bug class could not occur here — but the sort itself lived
outside the one shared module. `tournament_ordering.py` gained a second,
honest helper, `sort_by_official_date(items, date_key, *, reverse=False)`,
for exactly this "every item already has a real date, no proxy fallback
needed" case, and `tournament_chronology.py` now calls it. Behavior is
byte-for-byte identical (same sort keys, same order) — confirmed by running
the full `tests/test_phase8_public_ui.py` / `tests/test_home_state_router.py`
suites before and after.

### Algorithm (own ordering allowed, justification comment required)

Directories (every file under these, present or future, is in scope):
- `src/klpga/neo_win/`
- `src/klpga/backtest/`
- `src/klpga/models/`

Individual files:
- `src/klpga/website_v2/neo_ranking_v2a.py`
- `src/klpga/website_v2/neo_ranking_v2b.py`
- `src/klpga/website_v2/neo_ranking_backtest.py`
- `src/klpga/website_v2/home_ranking.py`
- `src/klpga/analytics/sg_performance.py`
- `scripts/82_build_corrected_sg_total_rank.py`

**Ten genuine chronology-adjacent sort sites found; all ten now carry the
`# ALGORITHM ORDERING (MISSION V9): ...` marker comment** (plus one
pre-existing comment in `point_in_time_features.py` extended with the same
marker so the CI check recognizes it):

| File:line | Why `tournament_ordering.py` is not used |
|---|---|
| `neo_win/current_sg_walk_forward.py:213` | walk-forward needs real `effective_date`, not a display-order proxy |
| `neo_win/current_sg_walk_forward_r4.py:198` | same |
| `neo_win/win_features.py:87` | win-probability feature window over already date-filtered rows |
| `neo_win/r1_frozen_snapshot.py:86` | **false-positive on the detection heuristic** — `game_code` here is only part of a file-glob pattern for one tournament's own snapshot, never a cross-tournament sort key. Commented rather than carved out as an exception, so the CI rule stays uniform (see "Detection heuristic" below). |
| `backtest/point_in_time_features.py:266` | point-in-time backtest feature window, real `effective_date`, no missing-date case to fall back from |
| `models/walk_forward_eval.py:147` | backtest evaluation ordering by `target_start_date`, not display order |
| `website_v2/neo_ranking_v2a.py:151`, `:246` | ranking-formula recent-N window selection; switching to the real-date override would **change ranking output** — out of scope ("do not change ranking behavior") |
| `website_v2/neo_ranking_v2b.py:91`, `:173` | same |
| `website_v2/neo_ranking_backtest.py:64` | backtest replay order over externally supplied real dates |
| `website_v2/home_ranking.py:72` | same ranking-output-stability reason as v2a/v2b |
| `analytics/sg_performance.py:86` | SG window summary's existing date semantics; a formula-output change is out of scope |
| `scripts/82_build_corrected_sg_total_rank.py:55` | validated ranking formula's "latest five" window; a real-date reorder could change which five rows are selected |

### Producer (no requirement — default role, not enumerated)

Everything not listed above, including (non-exhaustive, by directory):
`src/klpga/collectors/`, `src/klpga/discovery/`, `src/klpga/tournament_discovery.py`,
`src/klpga/tournament_pre_state.py`, `src/klpga/tournament_runtime.py`,
`scripts/reconcile_*.py` (reconciliation is explicitly a Producer activity
per the role definition, even though `reconcile_10097_player_history.py`
happens to already import `tournament_ordering.py` from the original
mission — over-compliance, not required, left as-is), `scripts/build_official_warehouse.py`,
`scripts/build_repository_index.py`, and the ~100 numbered
`scripts/NN_*.py` per-tournament collection/freeze/forecast pipeline
scripts (Hana/KB/OK Open R1–R4 machinery).

Absence from the Consumer/Algorithm lists above **is** the Producer
classification — this is intentional: only two of the three roles ever
carry a CI requirement, so a Producer module is never blocked by this
rule no matter what ordering it implements internally.

## The CI rule

`tests/test_tournament_ordering_governance_v9.py`, run as part of the
normal pytest suite (this repository's CI):

1. **`test_every_consumer_module_with_a_chronology_sort_imports_the_shared_utility`**
   — scans every `.py` file under `src/` and `scripts/`; for any file
   classified Consumer (explicit list above, or matching the forward-looking
   glob/name patterns) that contains a chronology-relevant sort, asserts the
   file imports `klpga.tournament_ordering`.
2. **`test_every_algorithm_module_with_a_chronology_sort_has_a_justification_comment`**
   — same scan, scoped to files classified Algorithm; asserts the
   `# ALGORITHM ORDERING (MISSION V9)` marker comment appears within 8
   lines above the sort call.
3. Three guard tests (`..._never_overlap`, `..._is_exempt_from_both_rules`,
   `..._are_still_real_files_on_disk`) protect the classification lists
   themselves from silent drift (a file renamed/deleted, or accidentally
   double-classified).

**Detection heuristic:** a "chronology-relevant sort" is one physical line
containing `.sort(` or `sorted(` together with `game_code`, `season`,
`end_date`, `start_date`, or `effective_date` on that same line — the exact
heuristic used to manually audit the whole repository for this mission.
Documented limitation: a sort call split across multiple physical lines is
not detected. Every real site this mission found is a single line (verified
against the full `src/`/`scripts/` tree before this test was written), so
today this has zero false negatives; a future multi-line sort would need
the heuristic extended, not a reason to weaken the rule. It does have
occasional false positives (a `game_code` that only appears inside a glob
pattern, not a sort key — see `r1_frozen_snapshot.py` above) — the policy
for those is to add the marker comment anyway, explaining that the sort
isn't really chronology-relevant, rather than carve out per-file exceptions
in the check itself. A uniform rule with one documented false-positive
comment is easier to audit than a rule with silent exceptions.

**Currently green with zero grandfathered exceptions** — every real gap
found by this audit was fixed in this mission (one Consumer import, ten
Algorithm justification comments), so no baseline/ratchet file was needed.

## Migration plan

Nothing outstanding today. If a **new** file is added under an Algorithm
directory (`neo_win/`, `backtest/`, `models/`) or one of the explicit
Algorithm/Consumer files, and it sorts by a chronology-shaped key, CI will
fail immediately with the file:line and the missing requirement — the
failure message itself is the migration instruction (add the marker
comment for Algorithm, or import `tournament_ordering` for Consumer).

If this classification ever needs to widen (e.g. a numbered
`scripts/NN_*.py` pipeline script starts rendering chronology to a public
page, moving it from Producer to Consumer): add its exact path to
`CONSUMER_FILES` (or extend a glob) in
`tests/test_tournament_ordering_governance_v9.py`, then either wire it
through `tournament_ordering.py` or `sort_by_official_date()`, or document
why it can't. No other file in the repository needs to change for that
addition — this was the entire point of not making it a repository-wide
rule.
