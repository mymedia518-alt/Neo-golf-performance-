# HJ중공업·동부건설 챔피언십 (2026100004) — A/B/C Data Gate (2026-10-07)

Per explicit instruction, the three layers are never mixed:

- **A. Stableford V1** (frozen, unchanged formula, `net_expected_value`/`pre_event_rank`) — **READY**
- **B. Three-Winner DNA** (Birdie production, Scoring ceiling, Average Score, SG Total, SG Tee-to-Green, Driving Distance, GIR, Par5=SUPPORTING) — **PARTIAL, gated below**
- **C. Official KLPGA K-RANKING** — **NOT ACQUIRED**

PRE/HOME is not built until A/B/C are all ready. Current status:

## A. Stableford V1 — READY (unchanged from the prior report)

`STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json`, 106/108 ranked, 2 `DATA_LIMITED_NO_PRIOR_DATA`. No change this turn.

## B. Three-Winner DNA — investigated, partially closed this turn

Searched this repo (and confirmed the D:\NEO_DATA_ROOT path named in the instruction is on the user's own Windows machine, outside this sandbox's reach — it was not inspected, and nothing here assumes what it contains) for existing, already-validated collection pipelines before building anything new, per instruction:

### B1. SG Total / SG Tee-to-Green — mostly already in this repo, no new acquisition method needed

`content/website_v2/historical_sg_warehouse_corrected_v2.json` (the same warehouse already used for the three-winner CORE validation) **already covers 22 of the 24 real pre-cutoff 2026 tournaments** — found by direct inspection, not assumed. `scripts/224_build_hj_2026_sg_profile.py` reuses the exact already-validated aggregation rule (`stableford_backtest_snapshot._mean`'s simple per-tournament mean, unchanged) with exact-date filtering (not the original month-only conservative rule, since real exact dates are now known for all 24 tournaments).

**Result: 106/108 players already have a real SG Total/Tee-to-Green profile.** 2 tournaments are missing from the warehouse — `2026090002` (하나금융그룹 챔피언십) and `2026120001` (OK저축은행 읏맨 오픈) — not estimated, not interpolated. `scripts/collect_sg_from_leaderboard.py` is the already-existing, already-generic SG collector (built for exactly this situation — see its own docstring's "no gameCode-specific logic" mission) — no new script was written; it only needs to be run twice, live, on Windows.

### B2. Driving Distance / GIR — same weighted season-to-date reconstruction method reused, new acquisition needed

Reuses `klpga.collectors.official_season_stat_reconstruction` and `klpga.collectors.public_record_season_detail` **completely unchanged** (the exact modules already validated for the three historical winners' fields, commit `eadf36f`) — no new formula, no new gate logic.

- `scripts/222_build_hj_2026_gir_dd_reconstruction_manifest.py` (built, tested, 4/4 passing): for each of the 108 real entrants, finds every one of the 24 real pre-cutoff tournaments she actually played, with the real per-tournament round count (ground truth for the two-layer gate) — **2,264 total (player, tournament) calls needed**, 2 players (the same 2 brand-new entrants) with zero prior tournaments.
- `scripts/223_acquire_hj_2026_gir_dd.py` (built, tested, 3/3 passing): a thin wrapper that imports and reuses `scripts/213`'s `run_preflight_pilot`/`acquire_and_reconstruct_player` **unchanged**, pointed at the new 2026 manifest. Not yet run — blocked by the same sandbox network restriction as every prior official-source step this session.

### Par5 scoring (SUPPORTING, not CORE) and Average Score/birdie-ceiling metrics

Already computable with zero new acquisition (confirmed last turn) — unchanged.

## C. K-RANKING — unchanged, still blocked

`scripts/220_acquire_hj_2026_kranking.py` (built, tested last turn) — `k-rankings.klpga.co.kr` confirmed unreachable from this sandbox. Not yet run.

## The 3 Windows steps, in one sequence (none overlap, order doesn't matter, run all before re-closing the DNA/K-RANKING gates)

```powershell
cd klpga_pipeline

# B1 -- SG for the 2 missing tournaments (fast, 2 bulk requests)
python scripts/collect_sg_from_leaderboard.py --game-code 2026090002 --season 2026 --tournament "하나금융그룹 챔피언십" --live
python scripts/collect_sg_from_leaderboard.py --game-code 2026120001 --season 2026 --tournament "OK저축은행 읏맨 오픈" --live

# B2 -- Driving Distance / GIR reconstruction (2,264 calls -- the largest step, budget real time for this one)
python scripts/223_acquire_hj_2026_gir_dd.py

# C -- K-RANKING (1 bulk request)
python scripts/220_acquire_hj_2026_kranking.py
```

After running these, commit and push:
  - the updated `historical_sg_warehouse_corrected_v2.json` (B1)
  - `evidence/hj_2026100004_gir_dd_reconstructed/` (B2)
  - `evidence/hj_2026100004_kranking_acquisition/` (C)

Once pushed, this session will re-run `scripts/224` (SG) to pick up the 2 new tournaments automatically, finalize the full Three-Winner DNA CHECK with all CORE metrics (not the partial 8/13 version from the prior turn — that result is **withdrawn**, not to be treated as final, per instruction), connect the real K-RANKING as its own column, and only then proceed to PRE/HOME.
