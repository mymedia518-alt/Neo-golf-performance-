# NEO STABLEFORD — Three-Winner Pre-Event Player Profile Validation (2026-10-06, updated)

Continues from `2a0bcd2` (2023/2024/2025 blind backtests, all PASS) and from `aab671e` (this report's first version, which incorrectly labeled 5 official metrics "UNAVAILABLE"). Uses ONLY the already-acquired, SOURCE_PASS-verified prior-tournament captures (`evidence/stableford_prior_2023/2024/2025/`, 19/23/23 tournaments) and the already-built `klpga.website_v2.stableford_blind_backtest` / `stableford_backtest_snapshot` pipelines. **No frozen V1 artifact or hash was modified.**

**This update's new work**: (1) corrected the failure taxonomy — "UNAVAILABLE" never meant "no source exists," and the report now says so explicitly; (2) reconstructed official Average Score and Par5 scoring directly from already-held real pre-cutoff hole data, using KLPGA's own official formula (confirmed against a real `publicRecordSeasonDetail` fixture) — zero new network access; (3) built and tested a complete acquisition package (manifest covering 102/103/103 real playerCodes + a confirmed-real collector + an acquisition script with a built-in temporal-safety cross-check) for the 3 metrics that genuinely do require a new network fetch (Driving Distance, Fairway Accuracy, GIR%); (4) confirmed, via 3 independent methods, that this sandbox's network access to klpga.co.kr is blocked at the environment/proxy level — not a klpga.co.kr-side or data-non-existence issue — and documented the exact evidence.

핵심 질문: *"방신실·김민별·김민솔은 우승 결과를 제거해도 Stableford에서 가치가 높아질 공통 선수 프로필을 가지고 있었는가?"*

**Each winner's own target-event data is completely excluded.** Cutoffs: 방신실 < 2023-10-12, 김민별 < 2024-10-10, 김민솔 < 2025-10-01 — identical to the already-verified blind-backtest cutoffs, re-used unchanged.

## Data sources and acquisition status

**Taxonomy correction (this turn)**: the earlier "UNAVAILABLE" label conflated "not yet acquired inside this repo" with "no official source exists." It was wrong — all 5 metrics below have a confirmed real official KLPGA source. The status column now uses the corrected 5-way taxonomy: `SOURCE_EXISTS_AND_ACQUIRED` / `SOURCE_EXISTS_RECONSTRUCTED` / `SOURCE_EXISTS_BUT_ACCESS_BLOCKED` / `SOURCE_EXISTS_BUT_TEMPORAL_RECONSTRUCTION_FAILED` / `SOURCE_NOT_FOUND_AFTER_WEB_INVESTIGATION`. Absence from this repo is never, by itself, treated as `SOURCE_NOT_FOUND_AFTER_WEB_INVESTIGATION`.

| Category | Source | Status |
|---|---|---|
| Hole outcome counts/rates | 19/23/23 real `scoreRecord` prior captures | `SOURCE_EXISTS_AND_ACQUIRED`, full field |
| Round-level birdie counts, round stroke totals, round Stableford points | Same captures, re-parsed at round granularity | `SOURCE_EXISTS_AND_ACQUIRED`, full field |
| SG Total + 4 components (tee-to-green, off-the-tee, approach, around-green, putting) | `historical_sg_warehouse_corrected_v2.json` | `SOURCE_EXISTS_AND_ACQUIRED`, 102/106 (2023), 105/105 (2024), 103/105 (2025) |
| **Average Score (official 평균타수 = 전체타수/라운드수)** | Official formula confirmed against the real official fixture `tests/fixtures/official_detail/8436_publicRecordSeasonDetail.html`; reconstructed this turn directly from the same already-held, already-verified real pre-cutoff hole-by-hole `scoreRecord` data — no new network access needed | **`SOURCE_EXISTS_RECONSTRUCTED`** — 106/105/105, full field |
| **Par5 scoring (official 파5성적 = 파5전체타수/파5홀수)** | Same official formula, same fixture, same reconstruction method | **`SOURCE_EXISTS_RECONSTRUCTED`** — 106/105/105, full field |
| **Driving Distance / Fairway Accuracy / GIR (official 드라이브거리/페어웨이안착률/그린적중률)** | Real, confirmed-live official endpoint `POST https://klpga.co.kr/load/profile/publicRecordSeasonDetail` (`playerCode`/`season`/`gameCode`/`tourType=RE`) — confirmed real via the same fixture plus `klpga/config.py`'s own documented provenance note | **`SOURCE_EXISTS_BUT_ACCESS_BLOCKED`** in this sandbox only — see "Web access investigation" below. Full acquisition package (manifest for 102/103/103 players + collector `public_record_season_detail.py` + script `scripts/210_acquire_official_season_stats.py`, all built and tested this turn) is ready to run on a machine with real network access |

### Web access investigation (this turn, per explicit instruction not to conclude "no data" without first attempting live access)

Three independent methods were tried against both `https://klpga.co.kr` and `https://data.klpga.co.kr`. All three failed identically with an environment/proxy-level egress block — never a klpga.co.kr-side rejection, never a "page doesn't exist" result:

1. **curl** — `curl -v https://klpga.co.kr` → `CONNECT tunnel failed`, `< HTTP/1.1 403 Forbidden` on the `CONNECT klpga.co.kr:443` request itself (the egress proxy denies the tunnel before ever reaching klpga.co.kr's server).
2. **Agent-proxy status log** — `curl -sS http://127.0.0.1:43467/__agentproxy/status` → `recentRelayFailures` shows `{"kind":"connect_rejected","detail":"gateway answered 403 to CONNECT (policy denial or upstream failure)","host":"klpga.co.kr:443"}` (×2) and the same for `data.klpga.co.kr:443` (×1) — a structured, timestamped confirmation this is a policy-level block, not a site-level one.
3. **WebFetch** — called against `https://klpga.co.kr/web/profile/publicRecordSeason?playerCode=10095` and `https://data.klpga.co.kr` → both returned `{"error_type":"EGRESS_BLOCKED","domain":"<host>","message":"Access to <host> is blocked by the network egress proxy."}`.

Correctly classified as `SOURCE_EXISTS_BUT_ACCESS_BLOCKED`: the source's existence is independently confirmed (real fixture + `config.py` provenance); the failure is specific to this sandbox's network policy, not to klpga.co.kr or to data non-existence.

**To finish the acquisition**, on any machine with real klpga.co.kr access (e.g. the same Windows machine already used for scripts 205-209 earlier in this project):
```powershell
cd klpga_pipeline
python scripts\210_acquire_official_season_stats.py
```
This fetches, for all 102/103/103 manifested players across 2023/2024/2025, both a hypothesized temporal-safe gameCode-scoped call and a full-season (explicitly NOT temporal-safe) reference call, cross-checks the returned 라운드수 (round count) against each player's independently-known real pre-cutoff round count, classifies each player/metric as `SOURCE_EXISTS_AND_ACQUIRED` or `SOURCE_EXISTS_BUT_TEMPORAL_RECONSTRUCTION_FAILED`, and writes `evidence/stableford_official_stats_<year>/ACQUISITION_REPORT.json` plus every raw HTML response for audit. Commit and push that `evidence/` output back to `neo-website-v2`, and H1/H3(GIR)/H7 below can be finalized with real numbers.

## 1-3. Full metric table (value / percentile within that year's own Stableford pre-event field)

Percentile = this player's standing among that year's covered field (106/105/105 players), 0–100, higher = better **after** orienting each metric to its hypothesized "good" direction (bogey/double+ rates inverted; `round_points_variance` oriented HIGH-is-better per H6's own framing — Stableford caps downside at −3/hole but uncaps upside, so a scoring-ceiling/burst profile is the hypothesized advantage, not stability — decided before computing, not after).

| Metric | 방신실 2023 | pct | 김민별 2024 | pct | 김민솔 2025 | pct | Commonality |
|---|---|---|---|---|---|---|---|
| Total holes (pre-event) | 936 | — | 1,116 | — | 576 | — | n/a (sample size, see Red Team) |
| Rounds | 52 | — | 62 | — | 32 | — | n/a |
| Tournaments | 17 | — | 19 | — | 9 | — | n/a |
| Albatross rate | 0.0 | 100.0 | 0.0 | 100.0 | 0.0 | 100.0 | **CORE (degenerate — see note)** |
| Eagle rate | 0.32% | 98.10 | 0.18% | 80.77 | 0.69% | 100.0 | CORE (weak absolute magnitude) |
| Birdie rate | 19.55% | 98.10 | 17.92% | 78.85 | 22.05% | 97.12 | **CORE** |
| Par rate | 64.74% | 17.14 | 68.73% | 69.23 | 62.33% | 2.88 | NOT COMMON |
| Bogey rate | 12.29% | 86.67 | 12.01% | 83.65 | 12.67% | 67.31 | SUPPORTING |
| Double+ rate | 3.10% | 17.14 | 1.17% | 83.65 | 2.26% | 26.92 | NOT COMMON |
| Birdie+ rate (eagle+albatross+birdie) | 19.87% | 99.05 | 18.10% | 79.81 | 22.74% | 98.08 | **CORE** |
| Bogey+Double+ rate | 15.38% | 67.62 | 13.17% | 84.62 | 14.93% | 58.65 | SUPPORTING |
| Birdie+/Bogey+ ratio | 1.292 | 87.62 | 1.374 | 85.58 | 1.523 | 80.77 | **CORE** |
| Expected Stableford pts/hole | +0.191 | 87.62 | +0.212 | 85.58 | +0.281 | 92.31 | **CORE** |
| Avg birdies/round | 3.52 | 98.10 | 3.23 | 78.85 | 3.97 | 97.12 | **CORE** |
| Max birdies in one round | 7 | 77.14 | 8 | 89.42 | 9 | 94.23 | **CORE** |
| Top-10%-rounds avg birdies | 6.33 | 85.71 | 5.86 | 65.38 | 7.75 | 97.12 | SUPPORTING |
| Sub-70 round rate | 28.85% | 92.38 | 25.81% | 83.65 | 34.38% | 87.50 | **CORE** |
| Round Stableford-points variance | 27.40 | 83.81 | 21.02 | 58.65 | 43.68 | 99.04 | SUPPORTING |
| High-scoring round rate (≥10 pts/round) | 11.54% | 93.33 | 8.06% | 77.88 | 21.88% | 95.19 | **CORE** |
| SG Total | +1.118 | 85.15 | +1.049 | 86.54 | +1.534 | 89.22 | **CORE** |
| SG Tee-to-Green (GIR/ball-striking proxy) | +1.809 | 97.03 | +1.587 | 94.23 | +1.146 | 81.37 | **CORE** |
| SG Off-the-Tee (driving proxy) | +0.198 | 60.40 | +0.580 | 92.31 | +1.124 | 99.02 | SUPPORTING |
| SG Approach | +1.375 | 97.03 | +1.089 | 96.15 | +0.204 | 60.78 | SUPPORTING |
| SG Around-the-Green | +0.238 | 88.12 | −0.082 | 38.46 | −0.183 | 18.63 | NOT COMMON |
| SG Putting | −0.691 | 10.89 | −0.536 | 15.38 | +0.391 | 83.33 | NOT COMMON |
| Average Score (official, lower=better) | 71.7885 | 82.86 | 71.3065 | 86.54 | 70.9062 | 82.69 | **CORE** |
| Par5 scoring (official, lower=better) | 4.9095 | 74.29 | 4.888 | 76.92 | 4.7652 | 90.38 | SUPPORTING (2023's 74.29 falls just short of the 75 threshold — reported exactly, not rounded up) |
| Driving Distance | `SOURCE_EXISTS_BUT_ACCESS_BLOCKED` | — | `SOURCE_EXISTS_BUT_ACCESS_BLOCKED` | — | `SOURCE_EXISTS_BUT_ACCESS_BLOCKED` | — | pending acquisition (package ready) |
| Fairway Accuracy | `SOURCE_EXISTS_BUT_ACCESS_BLOCKED` | — | `SOURCE_EXISTS_BUT_ACCESS_BLOCKED` | — | `SOURCE_EXISTS_BUT_ACCESS_BLOCKED` | — | pending acquisition (package ready) |
| GIR (official %) | `SOURCE_EXISTS_BUT_ACCESS_BLOCKED` | — | `SOURCE_EXISTS_BUT_ACCESS_BLOCKED` | — | `SOURCE_EXISTS_BUT_ACCESS_BLOCKED` | — | pending acquisition (package ready) |

**Classification rule applied exactly as predeclared**: CORE = 3/3 in top 25% (percentile ≥75) same direction; SUPPORTING = 2/3 in top 25%, or 3/3 above the 50th percentile but not strongly; NOT COMMON = real player-to-player spread crossing the field average in different directions; no metric here required post-event data, so none fall in POST-HOC/REJECT.

**Degenerate-CORE note**: `albatross_rate` registers as CORE only because every one of the 106/105/105 covered players — not just the three winners — has exactly 0 albatrosses in these captures. A 100th-percentile tie among an entire field with zero variance is not a real shared elite trait; it is reported here for completeness and immediately discounted below.

## 4. Field-normalized comparison — already embedded above (percentile column)

## 5. Control comparison (separating "winner-only" from "generally Stableford-valuable")

| | #1 pre-event Stableford rank (did NOT win) | Winner's own rank | Ordinary-high / Stableford-low control |
|---|---|---|---|
| 2023 | 이예원 (rank 1, birdie 19.49%, bogey 10.08%, net +0.281) | 방신실 (rank 14) | 임채리 (ordinary rank 45 → Stableford 57; birdie 11.11%, bogey 13.89%) |
| 2024 | 윤이나 (rank 1, birdie 22.99%, bogey 10.17%, net +0.338) | 김민별 (rank 16) | 유효주 (ordinary 78 → Stableford 85; birdie 12.85%, bogey 15.54%) |
| 2025 | 유현조 (rank 1, birdie 22.37%, bogey 9.70%, net +0.348) | 김민솔 (rank 9) | 신다인 (ordinary 38 → Stableford 45; birdie 16.18%, bogey 11.36%) |

**Key finding**: the #1 pre-event-ranked player each year — who did NOT win — has a birdie/bogey profile essentially indistinguishable in character from the eventual winner (same high-birdie, moderate-bogey shape). This directly separates "traits that make a player Stableford-valuable" (shared by many players, including non-winners) from "traits that predict a win" (which these pre-event metrics do not claim to do — see the blind-backtest reports' own winner-rank results: 14th, 16th, 9th, never 1st). The ordinary-high/Stableford-low controls show consistently lower birdie rates and (in 2/3 years) higher bogey rates than either the winners or the #1-ranked non-winners — confirming the CORE metrics discriminate real field variation, not noise.

## 6. Hypothesis tests (predeclared, attacked adversarially)

| | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H1 | 장타(Driving Distance)가 공통점이다 | **PENDING (`SOURCE_EXISTS_BUT_ACCESS_BLOCKED`)** | Real official source confirmed (fixture + config.py provenance); 3-way-confirmed sandbox network block prevents live acquisition this turn. SG Off-the-Tee (distance+accuracy blend, not distance alone) is only SUPPORTING (60.40/92.31/99.02 — 2023 marginal), a weak partial signal, not a substitute for the real stat |
| H2 | 높은 Birdie rate가 공통점이다 | **SUPPORTED** | Birdie rate, Birdie+ rate, avg birdies/round, max birdies/round all CORE (3/3 top-25%); absolute rates genuinely elevated (17.9–22.1%, vs field medians well below) |
| H3 | 높은 GIR/Tee-to-Green이 공통점이다 | **PARTIAL** | Official GIR% is `SOURCE_EXISTS_BUT_ACCESS_BLOCKED` (pending the same acquisition as H1); the SG Tee-to-Green proxy IS CORE (97.03/94.23/81.37 — all top-25%), but a Strokes-Gained composite is not the same statistic as GIR%, so this remains partial support via proxy, not a direct confirmation |
| H4 | 낮은 Bogey/Double+가 공통점이다 | **REJECTED (for Double+), PARTIAL (for Bogey)** | Double+ rate is NOT COMMON — 방신실 and 김민솔 are actually BELOW the field median on avoiding double+ (17.14/26.92 percentile), only 김민별 is strong (83.65); Bogey rate alone is SUPPORTING, not CORE. The honest finding: these three winners are not uniformly bogey/double+-avoiders — two of three tolerate elevated double+ risk |
| H5 | Par5 scoring upside가 공통점이다 | **SUPPORTED (SUPPORTING tier, not CORE)** | Reconstructed this turn from real pre-cutoff hole data (파5전체타수/파5홀수, matching KLPGA's own official formula exactly) for the full 106/105/105-player field: percentiles 74.29 / 76.92 / 90.38. Only 2 of 3 clear the strict ≥75 top-25% CORE bar — 2023's 74.29 falls just short — so this is reported exactly as SUPPORTING, not rounded up to CORE |
| H6 | Scoring ceiling/burst(안정성보다)가 공통점이다 | **SUPPORTED** | High-scoring-round rate and max-birdies-per-round are both CORE (3/3 top-25%); round-points variance itself is only SUPPORTING (2/3, 2024's 58.65 percentile is middling) — but the convergence of 3 independent ceiling-type metrics, 2 of them CORE, supports the hypothesis overall, with the caveat that raw variance alone does not reach the strict 3/3 threshold |
| H7 | Fairway Accuracy는 핵심 공통조건이 아니다 | **PENDING (`SOURCE_EXISTS_BUT_ACCESS_BLOCKED`); not contradicted by the available proxy** | Official Fairway Accuracy% confirmed real, same acquisition package as H1, pending real network access. SG Off-the-Tee (a distance+accuracy blend, not accuracy alone) is only SUPPORTING (2023's 60.40 percentile is middling) — consistent with H7's claim that pure accuracy is not a strong common thread, but this cannot be directly confirmed without the real stat |
| H8 | 공식 평균타수(Average Score)가 공통점이다 | **SUPPORTED (CORE)** | Reconstructed this turn from real pre-cutoff hole data (전체타수/라운드수, matching KLPGA's own official formula exactly) for the full 106/105/105-player field: percentiles 82.86 / 86.54 / 82.69 — all 3 clear the ≥75 top-25% bar. All three winners were genuinely elite on the one stat KLPGA itself uses to rank players, before their win, with their own winning tournament excluded |

## 7. 세 선수의 CORE 공통특성

1. **Birdie-making ability, in every form measured**: birdie rate, birdie+ rate, avg birdies/round, max birdies/round, sub-70 round rate, high-scoring-round rate — all CORE, all 3/3 in the top 25% of their own year's field.
2. **Birdie+/Bogey+ ratio** (the asymmetric mechanism already found in the blind backtests) — CORE, 80.77–87.62 percentile.
3. **Expected Stableford points per hole itself** — CORE (87.62/85.58/92.31), i.e., the formula's own output correctly flags all three as strong, pre-event, without knowing they would win.
4. **SG Total and SG Tee-to-Green** — CORE, suggesting genuine all-around (and specifically tee-to-green/ball-striking-proxy) strength, not just a hot-putter or short-game illusion.
5. **Official Average Score (평균타수)** — CORE (82.86/86.54/82.69), reconstructed this turn directly from real pre-cutoff hole data using KLPGA's own official formula. All three winners were genuinely elite on KLPGA's own primary ranking stat before their win, with the win itself excluded — this is the strongest possible confirmation that the CORE birdie/Stableford-value signal above isn't an artifact of this project's own metrics; it shows up on the official stat too.
6. (Degenerate) Albatross rate — technically CORE but meaningless (zero variance field-wide); not counted as a real finding.

## 8. SUPPORTING 특성

Bogey rate, Bogey+Double+ rate, top-10%-rounds avg birdies, round-points variance, SG Off-the-Tee, SG Approach, **official Par5 scoring (파5성적, reconstructed this turn — 74.29/76.92/90.38, 2023 falls just short of CORE)** — each shows a real elevated pattern in 2/3 winners or a weak-but-positive pattern in all 3, but does not clear the strict 3/3-top-25% CORE bar.

## 8a. Six validation questions (per the user's explicit list), answered to the extent current evidence allows

1. **장타 선수였는가 (long hitters)?** — Cannot yet answer with the real stat; `SOURCE_EXISTS_BUT_ACCESS_BLOCKED` in this sandbox. The weak SG Off-the-Tee proxy (SUPPORTING, not CORE) does not resolve this either way.
2. **GIR 상위권이었는가?** — Cannot yet answer with the real stat; same block. The SG Tee-to-Green proxy is CORE, a real but non-equivalent signal in the same direction.
3. **Par5에서 강했는가?** — **Mostly yes**: real reconstructed Par5 scoring is SUPPORTING (2 of 3 in the top 25%; 2023 is just short at the 74.29th percentile) — a genuine but not unanimous pattern.
4. **Fairway Accuracy는 정말 공통점이 아니었는가?** — Cannot yet confirm directly; same block. Not contradicted by the weak SG Off-the-Tee proxy.
5. **공식 평균타수 상위권이었는가?** — **Yes, unanimously**: CORE, all 3 in the top 25% of their own year's field (82.86/86.54/82.69).
6. **Birdie+Tee-to-Green 공통점과 이 새 지표들의 관계는?** — Average Score is mechanically downstream of birdie-making (more birdies → lower average score), so its CORE status is consistent with, not independent evidence beyond, the already-found birdie/SG-Tee-to-Green commonality — it confirms the same underlying skill shows up on KLPGA's own official ranking stat, rather than revealing a new independent trait. Par5 scoring is directionally consistent (SUPPORTING) but weaker, suggesting the shared strength is general scoring ability more than a specific Par5-only edge.

## 3. (continued) 공통점이라고 생각했지만 탈락한 특성

- **Low Double+ rate** — actively rejected: 2 of 3 winners (방신실, 김민솔) are BELOW their field's median on double+ avoidance, not above it. A naive "winners avoid blow-up holes" narrative does not survive contact with the real per-player data.
- **Par rate** — NOT COMMON, wildly inconsistent (2.88th to 69.23rd percentile) — unsurprising since par rate is largely the complement of the other rates, but worth stating explicitly rather than assuming it tracks birdie rate.
- **SG Around-the-Green and SG Putting** — NOT COMMON, in fact near-opposite patterns across years (방신실 strong putting-adjacent/around-green, weak putting; 김민솔 the reverse). No consistent short-game signature.

## 4. 세 선수 각각의 다른 점

- **방신실 (2023)**: the only winner with a real elevated Double+ rate (3.10%, 17th percentile — i.e., worse than most of the field at avoiding blow-ups) and the only one with strong SG Around-the-Green (88th percentile) paired with weak Putting (11th percentile) — a ball-striking/short-game-adjacent profile rather than a pure putter.
- **김민별 (2024)**: the most "conventional" profile of the three — her birdie rate (78.85th percentile) and scoring-ceiling metrics (round variance only 58.65th percentile) are the weakest of the three winners on nearly every CORE metric, yet she still clears every CORE threshold — the marginal case that keeps several metrics at SUPPORTING rather than CORE.
- **김민솔 (2025)**: the most extreme scoring-ceiling profile (99.04th percentile round-points variance, 95.19th percentile high-scoring-round rate) and by far the smallest pre-event sample (32 rounds, 9 tournaments — under half of the other two winners') — her numbers are real but rest on the thinnest evidence base of the three.

## 5. 2026 후보선수 탐색에 사용 가능한 변수

Birdie rate / Birdie+ rate / avg birdies per round / max birdies per round / sub-70 round rate / high-scoring-round rate / Birdie+:Bogey+ ratio / expected Stableford points per hole / SG Total / SG Tee-to-Green / **official Average Score (reconstructed)** — all CORE, all independently computable pre-event from the same real `scoreRecord` + SG-warehouse pipeline already built (Average Score needs zero new acquisition — it's a direct formula on data already on disk).

Par5 scoring (reconstructed) is SUPPORTING, not CORE — usable as a secondary/tie-breaking signal, not a primary screen.

## 6. 사용하면 안 되는 변수

- **Low Double+ rate / Double+ avoidance** — actively contradicted by 2 of 3 winners; using it to screen OUT high-double+ players would have excluded 방신실 and 김민솔.
- **Par rate, SG Around-the-Green, SG Putting** — NOT COMMON, no consistent direction; using any of these as a screening filter would be fitting noise.
- **Driving Distance, Fairway Accuracy, GIR% (official)** — `SOURCE_EXISTS_BUT_ACCESS_BLOCKED` in this sandbox; the real official source exists and an acquisition package is ready, but no real value has been acquired yet — any claim about these for 2026 candidates would still be fabricated, not evidenced, until the acquisition actually runs.
- **Albatross rate** — degenerate (zero variance in every real sample seen); carries no discriminating information.

## 7. Red Team

| Check | Result |
|---|---|
| Target-event leakage | **PASS** — every metric above is computed exclusively from the same pre-cutoff prior-tournament captures already leakage-verified for the blind backtests; no winner's own Stableford-event round ever enters these numbers |
| Future-season leakage | **PASS** — same manifests, same season/month-bounded sources as the already-verified blind backtests; no change |
| Survivorship bias | **DISCLOSED, addressed via controls** — these are 3 winners who, by definition, survived to win; section 7's control comparison (the #1-ranked non-winner shares the same profile shape) is the direct mitigation, not a claim this report "solves" survivorship bias entirely |
| Winner-selection bias | **DISCLOSED, same mitigation** — see above; a true test would need a random sample of the full field, not just winners + 2 controls per year, which is a real scope limit of this report |
| Small sample | **FOUND, DISCLOSED** — 김민솔's 2025 pre-event sample (32 rounds / 9 tournaments) is roughly half of 방신실's (52/17) and about half of 김민별's (62/19); her most extreme-looking numbers (round variance, high-scoring rate) carry more sampling noise than the other two winners' |
| Unequal sample size | **FOUND, SAME AS ABOVE** — 17/19/9 tournaments is a real, uncorrected asymmetry; no normalization attempted beyond using rate-based (not count-based) metrics throughout |
| Player identity collision | **DISCLOSED, unprovable** — same name-string-only limitation carried from every prior Red Team section this session; no playerCode available in `scoreRecord` |
| Missing hole outcomes | **PASS** — every round record used has exactly 18 real hole cells; the extractor discards (never pads) any row that doesn't |
| SG availability differences by year | **FOUND, MINOR** — 102/106 (2023), 105/105 (2024), 103/105 (2025) SG-covered; the 4 uncovered 2023/2025 players are not any of the 3 winners, so this does not affect the headline table, but is disclosed for completeness |
| Field normalization consistency | **PASS** — identical percentile method (rank within that year's own Stableford pre-event field, same direction convention) applied uniformly across all 3 years and all metrics, including the two newly reconstructed metrics (same 106/105/105 field as the SG table) |
| Metric definition drift | **PASS** — every metric is computed by the same shared function across all 3 years (no year-specific logic branches); Average Score/Par5 scoring use KLPGA's own official formula, verified against the real fixture, not a project-invented approximation |
| CRLF/hash issue affecting frozen artifacts | **PASS, VERIFIED** — this turn touched no `*_FROZEN_PREEVENT_SNAPSHOT_V1.json` file (confirmed via `git diff --stat`); the already-disclosed 2023/2025 chain-of-custody findings remain exactly as reported in their own gate reports and are unaffected by this analysis |
| Post-cutoff/future-season leakage in acquisition design (new) | **ADDRESSED BY DESIGN, NOT YET LIVE-VERIFIED** — `gameCode=""` is documented by `config.py` as the full-season final (explicitly NOT temporal-safe, contaminated by post-cutoff tournaments); the acquisition script never trusts it, only fetches it as a labeled reference. The hypothesized temporal-safe call (specific last-pre-cutoff `gameCode`) is cross-checked per-player against that player's independently-known real pre-cutoff round count before being accepted — but this cross-check has not yet run against the real endpoint (blocked in this sandbox), so it is a verified *design*, not yet a verified *result* |
| Measured-hole bias in Driving Distance (new, disclosed from the real fixture) | **FOUND, DISCLOSED** — the real fixture's own 드라이브거리 detail shows `전체측정홀=15`, far smaller than that player's rounds×18 — KLPGA only measures driving distance on certain holes per round, not every hole. Any future Driving Distance comparison must use KLPGA's own 측정홀 count as the denominator, never assume full-hole coverage, and must not compare players whose measured-hole counts differ by a large multiple without disclosing it |
| Denominator consistency across the 3 pending metrics (new) | **DESIGN NOTE, DISCLOSED** — GIR's denominator (total rounds-implied holes), Fairway Accuracy's denominator (전체측정홀 for fairway opportunities, i.e. holes with a fairway — excludes par-3s), and Driving Distance's denominator (전체측정홀 for driving, a DIFFERENT, usually smaller count than fairway's) are three distinct counts that must never be conflated when the real data arrives |
| Unequal tournament counts feeding the acquisition's cross-check (new) | **DISCLOSED, SAME ROOT CAUSE AS ABOVE** — the same 17/19/9-tournament asymmetry already disclosed for the hole-level metrics also means each player's "expected_pre_cutoff_rounds_total" cross-check baseline differs in sample size; a thin baseline (e.g. 김민솔's 32 rounds) gives the cross-check less room to detect a scoping error than a thick one does |
| Player identity matching for the new acquisition (new) | **FOUND, DISCLOSED** — playerCode resolution (from `mainRecord?playerCode=` links already embedded in existing captures) covers 95.4%/96.3%/96.3% of each year's field (103/108, 104/108, 104/108); 4-5 players per year have no resolvable playerCode and are excluded from the acquisition manifest, not fabricated |

## 9. Final Gate

**PARTIAL (upgraded from the prior PARTIAL, but still not PASS)**

Real, consistent CORE commonality was found across all three independent winners on birdie-making ability (in every form measured), the Birdie+/Bogey+ asymmetry ratio, the Stableford value formula's own output, overall ball-striking (SG Total/Tee-to-Green), and — new this turn — **official Average Score**, reconstructed directly from real pre-cutoff data using KLPGA's own formula (CORE, 82.86/86.54/82.69). Official Par5 scoring is a real but weaker SUPPORTING signal (74.29/76.92/90.38). None of this was assumed; all of it computed fresh from pre-event-only data with each winner's own tournament completely excluded.

The hypothesis that "low Bogey/Double+" is part of the common profile remains actively REJECTED by the real data (2 of 3 winners tolerate elevated double+ risk). Driving Distance, Fairway Accuracy, and official GIR% remain genuinely untested — not because no source exists (it does, confirmed via a real fixture and `config.py`'s own provenance), but because this sandbox's network access to klpga.co.kr is confirmed blocked by 3 independent methods this turn. A complete, tested acquisition package (manifest + collector + script, with a built-in temporal-safety cross-check) is ready to run on any machine with real access. The control comparison still shows the CORE traits are shared by non-winners too — meaning they describe "a strong Stableford-value profile," not "a guaranteed winner." **Still not reported as PASS** because 3 of the originally-requested variables remain genuinely unacquired (not merely unreconstructed), and **not reported as FAIL** because every metric that has been computed — now including 2 newly reconstructed official KLPGA stats — shows a real, non-trivial, three-for-three or two-of-three consistent signal.
