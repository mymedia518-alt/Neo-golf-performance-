# Stableford V1 — reproduction verification (2026-10-07)

Per explicit instruction: before any 2026 application, locate the EXACT calculation logic the 2023/2024/2025 blind backtests actually used, confirm it reproduces those results exactly, and do not invent a new 0-100 "Stableford Fit" score. This document is that verification. **No weight was changed. No new model was built.**

## 1. Where V1 actually lives in this repo

- **Formula**: `klpga/website_v2/stableford_player_value.py::from_season_rates` — pure arithmetic over the OFFICIAL Modified Stableford point table (`klpga.website_v2.stableford_scoring.SCORING_TABLE`), not an invented weighting:

  ```
  net_expected_value_per_hole =
      8 × P(albatross) + 5 × P(eagle) + 2 × P(birdie)   <- positive_scoring_contribution
    − 1 × P(bogey)                                       <- bogey_cost
    − 3 × P(double_or_worse)                             <- double_plus_downside
  ```

  These coefficients (8/5/2/−1/−3) are the tournament's own real Modified Stableford scoring table — the same one `2026100004_TOURNAMENT_INFO.json` records for HJ중공업·동부건설 itself — not a tunable hyperparameter this project chose.

- **Inputs**: real per-hole outcome RATES (albatross/eagle/birdie/par/bogey/double-or-worse rate), computed in `klpga/website_v2/stableford_blind_backtest.py::_aggregate_prior_outcomes` by summing real hole-by-hole classifications from every pre-cutoff tournament's own `scoreRecord` capture (`klpga.collectors.score_record.extract_hole_outcomes`) — never a season-average stat page, never SG, never GIR/driving-distance/fairway data.

- **Ranking rule**: `build_preevent_snapshot` sorts the full target field by `-net_expected_value` (descending — higher is better) and assigns `pre_event_rank = 1, 2, 3, ...`. Percentile: `100 × (n − rank) / (n − 1)`.

- **No "ordinary rank" exists anywhere in this frozen pipeline.** The only rank V1 ever produces is `pre_event_rank`. (See section 3 below — a disclosure about where an "ordinary rank" number came from in an earlier report.)

## 2. Reproduction confirmed, exactly

Re-ran the already-frozen pipeline live this turn (not merely read from a cached file):

```
$ cd /home/user/Neo-golf-performance- && python3 -m pytest klpga_pipeline/tests/test_stableford_blind_backtest_matches_frozen_2025.py -q
2 passed in 89.24s
```

- `test_generic_snapshot_matches_frozen_2025_hash_exactly`: the generalized `stableford_blind_backtest.build_preevent_snapshot("2025100001", ...)` produces a SHA-256 digest **identical** to the original, hand-written 2025-only module's frozen result (`232aee3f8e3ac368...`), and the full per-player payload is byte-identical (`==`), not just hash-equal.
- `test_generic_join_actual_results_matches_frozen_2025_evaluation`: confirms `winner_pre_event_rank == 9` and `spearman_correlation == 0.5905` for 김민솔/2025 — reproduced exactly.

Cross-checked directly against the committed frozen snapshot files for all 3 years:

| Year | Winner | `pre_event_rank` | Field size | Percentile | SHA-256 (frozen artifact) |
|---|---|---|---|---|---|
| 2023 | 방신실 | **14** | 106 covered / 108 field | 87.62 | `7d32813aab7a11fa...` |
| 2024 | 김민별 | **16** | 105 covered / 108 field | 85.58 | `e55a64403d75c4eb...` |
| 2025 | 김민솔 | **9** | 105 covered / 108 field | 92.31 | `232aee3f8e3ac368...` |

These exactly match every number reported throughout this whole session (2023 BLIND BACKTEST: PASS, 2024 BLIND BACKTEST: PASS, 2025 TRUE BLIND BACKTEST: PASS commits). **V1 is confirmed reproducible, unchanged, and none of its 2023-2025 results were altered by generalizing the module for replication** — that is the entire purpose of `test_stableford_blind_backtest_matches_frozen_2025.py` as a regression gate.

## 3. "Ordinary rank" — disclosure, not a hidden feature of V1

The three-winner profile report's control-comparison table (section 5) shows lines like "임채리 (ordinary rank 45 → Stableford 57)". **This number does not come from any committed code in this repo.** A repo-wide search of `src/` and `scripts/` found zero functions that compute an "ordinary" pre-event rank. The only rank-vs-rank comparison that exists in committed code is `klpga/website_v2/stableford_vs_strokeplay.py`, and that module is explicitly POST-event (same tournament's own actual stroke-play rank vs. actual Stableford rank, from real finished rounds) — not a pre-event predictive comparison, and its own docstring says so directly.

Conclusion: the "ordinary rank" figures in that earlier table were an illustrative, uncommitted scratch computation from an earlier turn in this session, not a frozen or reproducible part of V1. They are **not** used here, and are not to be treated as validated.

**Recommendation for the homepage's "일반 경기력 #X → Stableford #Y" display** (no new invention needed): use the REAL, already-sourced official KLPGA K-RANKING (`official_klpga_rank` in the existing `*_CURRENT_PLAYER_MASTER.json` schema, already displayed as the "KLPGA K-RANKING" column on the existing 2026100005 homepage) as "일반," paired with V1's own `pre_event_rank` as "Stableford." Both are real and already independently sourced — no new "ordinary" formula needs to be invented.

## 4. Three-Winner Profile stays a separate layer

The CORE/SUPPORTING/REJECTED metrics from `STABLEFORD_THREE_WINNER_PRE_EVENT_PROFILE_V1.md` (Birdie rate, Driving Distance, GIR, SG Tee-to-Green, official Average Score, etc.) are **not** inputs to V1's `net_expected_value` formula above, and this verification did not merge them in. They remain a distinct explanatory "DNA" layer, to be computed and reported separately once a real 2026 field exists (a future "DNA CHECK" comparing each 2026 entrant's own profile against the already-validated CORE traits) — never blended into, and never used to retune, V1's frozen coefficients.

## 5. What's needed before V1 can be applied to the 2026 field

1. The real HJ중공업·동부건설 (2026100004) entry list — **acquisition script built this turn, not yet run** (see `scripts/215_acquire_hj_2026100004_entry_list.py` and the Windows command below).
2. A real, leakage-verified "prior tournament" manifest for the 2026 season equivalent to `STABLEFORD_2023/2024/2025_PRIOR_TOURNAMENT_MANIFEST_V1.json` — i.e. every 2026 tournament strictly before 2026100004's own start date, with real `scoreRecord` captures — **not yet built, not attempted this turn** (out of scope until the entry list is secured, per explicit instruction).
3. Running the SAME `build_preevent_snapshot` function (unchanged) against that 2026 data once both of the above exist.

No 2026 ranking, probability, or "Stableford Fit" score is computed in this update.
