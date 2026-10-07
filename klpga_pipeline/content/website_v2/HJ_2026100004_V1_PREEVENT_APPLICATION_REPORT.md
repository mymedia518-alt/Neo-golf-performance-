# HJ중공업·동부건설 챔피언십 (2026100004) — Stableford V1 pre-event application (2026-10-07)

Applies the **frozen, unchanged** Stableford V1 formula to the real 108-player field. No new model, no new weights, no threshold change after seeing results.

## 1-2. Evidence verification

- `evidence/stableford_prior_2026/ACQUISITION_REPORT.json`: **24/24 ACQUIRED, 24/24 SOURCE_PASS, 0 FAIL** — real official scoreRecord captures for every 2026 tournament strictly before 2026-10-08, from 2026030001 (2026-03-12) through 2026100005 (2026-10-01, 하이트진로, the last prior event).
- Target event `2026100004` is **structurally absent** from the manifest (`scripts/217`'s `assert_no_leakage` excludes it by construction) — confirmed by direct check: not in the 24 acquired game_codes.
- Field sizes per tournament are real and plausible (108–140 entrants pre-cut, dropping to ~60–75 post-cut) — consistent with genuine KLPGA fields, not synthetic data.

## 3. Canonical field ↔ playerCode connection

`content/website_v2/2026100004_CANONICAL_PLAYER_IDENTITY_V1.json` (108 real entrants, already built and committed `6605508`) is the single field-identity source used throughout. No new identity work was needed this step.

## 4-5. Hole-by-hole reconstruction, per-player sample

Reused `klpga.website_v2.stableford_blind_backtest._aggregate_prior_outcomes` **unchanged** against the new 24-tournament manifest. Per-player real counts (rounds/holes/albatross/eagle/birdie/par/bogey/double+) are in `STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json`.

- **106/108** entrants matched by exact name string against the real prior-tournament data (no fuzzy matching, per instruction).
- **2/108** (김민서3, 이지유 0901(A) — both already-known NEW_PLAYER/추천자 entrants from the entry reconciliation) have **zero** matched prior data → `DATA_LIMITED_NO_PRIOR_DATA`, no rank assigned, no imputed value.
- **2/106** matched players have a thin sample (<10 rounds — the same pre-declared floor already used and justified in `scripts/214`): 성아진 (6 rounds), 박조은 0806(A) (2 rounds) → flagged `DATA_LIMITED_THIN_SAMPLE` but **still ranked**, matching the exact precedent set by the 2023/2024/2025 blind backtests (which never excluded thin-sample players either).

## 6. Frozen V1 application (unchanged formula)

```
net_expected_value = 8·P(albatross) + 5·P(eagle) + 2·P(birdie) − 1·P(bogey) − 3·P(double_or_worse)
```
Sorted descending → `pre_event_rank`. Formula and ranking code are imported directly from `klpga.website_v2.stableford_player_value.from_season_rates` and the same ranking snippet used in `stableford_blind_backtest.build_preevent_snapshot` — not reimplemented, not retuned.

**Top 20 (real result):**

| Rank | Player | net_expected_value | Rounds |
|---|---|---|---|
| 1 | 서교림 | 0.2807 | 77 |
| 2 | 김민솔 | 0.2793 | 73 |
| 3 | 유현조 | 0.2482 | 62 |
| 4 | 박현경 | 0.2394 | 55 |
| 5 | 김민선7 | 0.2392 | 72 |
| 6 | 김민주 | 0.2356 | 83 |
| 7 | 문정민 | 0.2296 | 75 |
| 8 | 전예성 | 0.2277 | 71 |
| 9 | 이예원 | 0.2248 | 64 |
| 10 | 성유진 | 0.2175 | 70 |
| 11 | 유서연2 | 0.2087 | 78 |
| 12 | 방신실 | 0.2072 | 74 |
| 13 | 김시현 | 0.2044 | 81 |
| 14 | 최예림 | 0.2009 | 78 |
| 15 | 이지현3 | 0.1898 | 72 |
| 16 | 장은수 | 0.1804 | 81 |
| 17 | 노승희 | 0.1775 | 77 |
| 18 | 신다인 | 0.1758 | 73 |
| 19 | 김수지 | 0.1754 | 76 |
| 20 | 한진선 | 0.1752 | 72 |

김민솔 (rank 2) and 방신실 (rank 12) — the already-validated three-winner profile holders — land high in this real, independently-run application, a genuine internal-consistency signal (not a designed-in result; the formula has no knowledge of who previously won).

## 7. Red Team

| Check | Result |
|---|---|
| Target-event leakage | **PASS, structural** — `2026100004` never appears in the manifest or evidence directory; `test_217`'s own test asserts this |
| Post-cutoff leakage | **PASS** — every one of the 24 tournaments' real start_date is `< 2026-10-08` (`assert_no_leakage`, re-verified) |
| Formula/weights unchanged | **PASS** — `stableford_player_value.py` and `stableford_blind_backtest.py` were not edited this turn (imported only); coefficients are the tournament's own official Modified Stableford table |
| No new threshold invented | **PASS** — `MIN_ROUNDS_QUALIFIED=10` is the same floor already used and justified in `scripts/214_finalize_reconstruction_verdict.py`, not a new number chosen for this result |
| No post-hoc threshold tuning | **PASS** — threshold fixed before computing; not adjusted after seeing ranks |
| DATA_LIMITED never imputed | **PASS, tested** — `test_no_unmatched_name_silently_fabricated_as_zero_rate` asserts every DATA_LIMITED_NO_PRIOR_DATA field is `None`, never `0.0` |
| Thin-sample handling | **DISCLOSED, included not excluded** — matches 2023-2025 precedent exactly, not a new rule |
| Name-matching risk | **DISCLOSED** — exact string match only; 2 genuinely new entrants correctly show zero prior data rather than a fabricated rate; no evidence of silent mismatching found (106/108 exact matches, consistent with the already-confirmed 0 duplicate names in the field) |
| Three-Winner CORE kept separate from V1 | **PASS, structural** — `stableford_2026_preevent.py` never imports or references `stableford_round_level_profile.py`; the DNA check (`scripts/221`) is a fully separate artifact that reads V1's OUTPUT but never feeds back into it |

**Red Team: PASS.**

## 8. Three-Winner DNA CHECK (separate layer)

`HJ_2026100004_THREE_WINNER_DNA_CHECK_V1.json` — per real HJ entrant (field_n=104, same ≥10-round floor), checks how many of the **already-available** CORE criteria (top-25%-of-own-field, same rule validated on the 3 historical winners) each player clears. **Explicitly partial**: 8 of the original ~13 CORE/SUPPORTING metrics are computable now (avg birdies/round, max birdies/round, sub-70 round rate, high-scoring-round rate, reconstructed official Average Score, reconstructed Par5 scoring, Birdie+/Bogey+ ratio, net expected value). **4 are NOT computed and not estimated**: official GIR, Driving Distance, SG Total, SG Tee-to-Green — these require the `publicRecordSeasonDetail` season-cumulative reconstruction (scripts 210-214) run across the full 108-player × 24-tournament field, a materially larger acquisition not undertaken this turn.

방신실: 7/8 available criteria met. 김민솔: 8/8. Never interpreted as a win-probability — this is a resemblance check against an already-disclosed profile, nothing more.

## 9. K-RANKING

**BLOCKED — same sandbox network restriction as every prior official-source step this session.** `scripts/220_acquire_hj_2026_kranking.py` is built and tested (reusing `scripts/72`'s already-provenance-tracked `collect_rankings_live`/`collect_rankings_offline` unchanged), confirmed `k-rankings.klpga.co.kr` is unreachable from this sandbox (`curl` → connection failure, same pattern as every other klpga.co.kr-family host this session). No offline capture exists yet for 2026100004 either. **K-RANKING has not been acquired — the homepage cannot show a real K-RANKING column yet.**

## Website status

**NOT YET BUILT.** Per explicit instruction, K-RANKING must be a real, acquired column before PRE/HOME is built — not fabricated, not omitted. The one remaining Windows step:

```powershell
cd klpga_pipeline
python scripts/220_acquire_hj_2026_kranking.py
```

Once that evidence is pushed, the homepage (reusing the existing 2026100005 template byte-for-byte, per the locked template instruction) can be completed with real Stableford V1 rank + real K-RANKING + the already-real canonical identity (name/sponsor/nationality), followed by Playwright QA at 390×844 and 1440×900.
