# Knowledge Engine course/tournament split -- impact analysis + migration plan

Mission: 2026-10-02, operator instruction. Target structure:

```
knowledge_engine/
  course/<course_id>/course_layout.json, hole_layout.json,
                      landing_distribution.json, course_dna.json, pin_history.json
  tournament/<game_code>/leaderboard.json, sg.json,
                          pin_position.json, hole_difficulty.json
```

Reader generates both warehouses; Player Intelligence/PRE/Deep Dive
prefer the Course Warehouse; the game_code-only design becomes
course_id-based.

## 0. What "폐기" actually means here

The mission says to discard the current `knowledge_engine/course/2026100005/`
structure. **That directory does not exist on `neo-website-v2` or `main`.**
A repo-wide branch search (`git ls-tree -r` across every local and remote
ref) found `course_hole_data.json` on exactly one branch:
`claude/wizardly-dirac-txqytb` -- never merged, and not read by any code on
that branch either (confirmed via `git grep` on that branch itself). So
there is no live structure to migrate away from; this is a fresh build,
not a cutover of working data.

## 1. Impact analysis (real, evidence-based)

### 1a. Scale of the `game_code` design

`grep -rl "game_code" src/klpga --include="*.py"` matches **131 files**
across the entire package -- collectors, analytics, backtest, models,
`knowledge_engine/`, every `neo_win/*` tournament-phase module, and most
of `website_v2/`. `course_id` has zero occurrences anywhere today. This
is not a local detail to swap -- it is the project's foundational
identity key, used by tournaments this project already shipped (Hana
2026090002, KB 2026090003) as much as by HITE JINRO.

### 1b. The root abstraction: `tournament_context.py`

`TournamentContext.artifact_path()` (`src/klpga/tournament_context.py:102`)
generates every "real pipeline" artifact's filename as
`<game_code>_<ARTIFACT_TYPE>.<ext>` and is resolved strictly from
`active_tournament.json`'s `game_code`. This is the one place a
`course_id` concept would need to be added for every "final_*"/Phase-6
module (`final_course_deep_dive.py`, `final_pre_freeze.py`,
`final_report.py`, `final_truth.py`, etc. -- ~15 modules) to gain
course-awareness without each reinventing its own lookup.

### 1c. A second, pre-existing, incompatible "real course data" contract

`src/klpga/neo_win/final_course_deep_dive.py` is **already** a real
(never-fabricating) Deep Dive connector. It is BLOCKED today -- by
design, since (its own docstring) "a full repository search ... found
ZERO existing course data anywhere." Its `REQUIRED_FIELDS` are
`field_average_relative_score, birdie_plus_rate, bogey_plus_rate,
attacking_holes, defensive_holes, danger_zone_holes, hole_difficulty`
-- a **different shape** than this mission's `course_dna.json`/
`hole_layout.json` split. Building the new structure without reconciling
this creates two competing "real course data" contracts in the same
repository. This must be resolved explicitly (Phase 1 below), not
silently left as two parallel designs.

### 1d. Shared, multi-tournament modules vs. HITE-JINRO-only modules

| Module | Scope | Risk of a course_id cutover |
|---|---|---|
| `knowledge_engine/knowledge_engine.py` (752 lines) | **every tournament** | High -- touches all shipped tournaments' data |
| `knowledge_engine/player_intelligence_generator.py` (453 lines) | **every tournament** | High -- regenerates every player's Player Intelligence |
| `knowledge_engine/tournament_dna_generator.py` (125 lines) | **every tournament** | Medium |
| `neo_win/hitejinro_round_pipeline.py`, `hitejinro_round_page.py`, `hitejinro_player_metrics.py`, `hitejinro_deep_dive_mock_page.py` | HITE JINRO (2026100005) only | Low -- already game_code="2026100005"-scoped at module level, self-contained |

"PI/PRE/Deep Dive가 Course Warehouse를 우선 참조" means editing the
first three shared rows above -- every change there is a change for
Hana and KB too, not just HITE JINRO, and needs regression coverage
across all of them before it ships.

### 1e. Real data available today vs. not

| New file | Real data available? | Evidence |
|---|---|---|
| `course/blue_heron/course_layout.json` | **Partial, real** | Blue Heron's own official course-overview page (operator upload, 2026-10-01): West/East par 36 / 9 holes / 3,499 / 3,541 yards |
| `course/blue_heron/hole_layout.json` | **Partial, real** | Same source, East Hole 6 only (par/hdcp/tee yardages/Pro Tip) -- other 17 holes have zero evidence |
| `course/blue_heron/landing_distribution.json` | None | No shot-tracking/landing-zone source has ever been collected |
| `course/blue_heron/course_dna.json` | None | Needs real per-hole scoring; klpga.co.kr captures give round totals only |
| `course/blue_heron/pin_history.json` | None | No pin-position source has ever been collected |
| `tournament/2026100005/leaderboard.json` | **Full, real** | Mirror of the already-real `2026100005_LEADERBOARD.json` |
| `tournament/2026100005/sg.json` | **Full, real** | Mirror of real `HITEJINRO_2026100005_R{1,2}_SG_V1.json` |
| `tournament/2026100005/pin_position.json` | None | Same as course/pin_history -- no source |
| `tournament/2026100005/hole_difficulty.json` | None | Needs real per-hole scorecards, which don't exist in any evidence source this project reads |

## 2. Phased plan

**Phase 0 -- DONE this commit (additive, zero risk, no existing consumer touched):**
- New directory tree under `content/website_v2/knowledge_engine/{course,tournament}/`.
- `course/COURSE_REGISTRY.json`: real `game_code -> course_id` entry for 2026100005 -> blue_heron.
- `course/blue_heron/course_layout.json`, `hole_layout.json`: populated with the real evidence in 1e; the other three Course Warehouse files are explicit `SCHEMA_ONLY_NO_REAL_DATA` stubs.
- `tournament/2026100005/leaderboard.json`, `sg.json`: real content mirrors (with sha256 provenance back to the canonical source file) of already-real data; `pin_position.json`, `hole_difficulty.json` are explicit stubs.
- `src/klpga/knowledge_engine/course_registry.py`: `resolve_course_id()` / `course_warehouse_dir()` / `tournament_warehouse_dir()`. Confirmed zero existing imports -- wired into nothing yet.
- Targeted regression suite (`pytest -m round_pipeline`): 116 passed, 1 skipped, 0 failed, both before and after -- confirms this phase changed no existing behavior.

**Phase 1 -- needs explicit go-ahead (low-medium risk, HITE-JINRO/Deep-Dive scoped):**
- Reconcile `final_course_deep_dive.py`'s `REQUIRED_FIELDS` contract with the new `course_dna.json`/`hole_layout.json` shape (pick one real schema, not two).
- Add a `course_id`-aware resolution path to `TournamentContext` (additive method alongside the existing `game_code`-based `artifact_path()`, not a replacement -- so every other `final_*` module keeps working unchanged until explicitly migrated).
- Wire `hitejinro_deep_dive_mock_page.py`'s real-data path (currently 100% mock, explicitly deferred since the V1 commit) to read `course/blue_heron/hole_layout.json` for East Hole 6 specifically, where real data now exists -- the other 17 holes stay mock until real evidence exists for them too.

**Phase 2 -- needs explicit go-ahead (high risk, affects every tournament):**
- Change `player_intelligence_generator.py` / `knowledge_engine.py` / PRE builder to look up the Course Warehouse first, Tournament Warehouse second, per the mission's "우선 참조" instruction. Requires regression coverage across Hana (2026090002) and KB (2026090003) as well as HITE JINRO, since these modules are shared.
- Decide the fallback behavior precisely for a game_code whose COURSE_REGISTRY entry doesn't exist yet (every tournament but HITE JINRO, today) -- must degrade to the current game_code-only behavior, never block Hana/KB's already-shipped pages.

**Phase 3 -- needs explicit go-ahead (Reader split):**
- `neo_reader/sync.py` currently has one `--stage results` collection flow with no course/tournament warehouse distinction. Splitting it into two explicit warehouse-generating paths is new design work, not a renaming -- needs its own spec before implementation.

## 3. Why Phases 1-3 aren't in this commit

Phases 1-3 edit modules shared by every tournament this project has
shipped (1d above), with no real data yet for 5 of the 9 new files (1e
above) to validate the new lookup order against. Shipping a blind
cutover of shared, multi-tournament, already-working modules in the
same pass as the schema design itself is exactly the kind of
high-blast-radius change this project's own established discipline
(fail closed, confirm before a hard-to-reverse change to a live system)
says to pause on. Phase 0 is real, additive, and fully regression-tested;
Phases 1-3 are ready to execute on confirmation of scope/order.
