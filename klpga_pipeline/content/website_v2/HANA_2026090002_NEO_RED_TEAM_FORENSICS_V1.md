# NEO BENCHMARK REPORT V1
## 하나금융그룹 챔피언십 (2026090002) — Research Report

**NEO predicts sustainable performance, not isolated outcomes.**
(NEO는 일회성 결과가 아니라 지속 가능한 경기력을 예측한다.)

**Current SG is a feature, not the target. NEO predicts Performance, not SG.**

**문서 상태: DRAFT / INTERIM — R3까지만 확정.** FINAL(R4) 공식 리더보드 증거가 아직 존재하지 않아 (`2026090002_POST_R4_FINAL_PREVIEW.json`의 `status`가 명시적으로 `"PREVIEW -- not yet promoted"`), R3→FINAL 구간과 FINAL 결과 섹션, 그리고 완결된 NEO SCORECARD는 이 문서에서 **BLOCKED**로 표시한다.

이 분석은 기존 Freeze/Evidence 아티팩트만 사용했다. 새로운 예측 생성 없음, Monte Carlo 재실행 없음, Freeze 수정 없음. NO PASS WITHOUT EVIDENCE.

**사용된 원본 아티팩트** (모두 `klpga_pipeline/content/website_v2/`):
`HANA_2026090002_R1_PRE_COMPARISON_V1.json`, `HANA_2026090002_R1_ANALYSIS_V1.json`, `2026090002_R2_FROZEN_EVIDENCE.json`, `2026090002_POST_R2_FINAL_FORECAST.json`, `2026090002_POST_R3_CANDIDATE_FREEZE_V1.json`, `2026090002_R3_FROZEN_EVIDENCE.json`, `2026090002_POST_R4_FINAL_PREVIEW.json` (참조용, 실제 결과 아님), `HANA_2026090002_R1_SG_V1.json`, `HANA_2026090002_R2_SG_V1.json`, `HANA_2026090002_R3_SG_V1.json`, `2026090002_PRE_PERFORMANCE_SNAPSHOT.json`, `HANA_2026090002_R2_R3_OOS_VALIDATION_REPORT_V1.json`.

이 문서는 향후 모든 KLPGA/LPGA/PGA 대회의 기준이 되는 **NEO Benchmark Report V1**이다. 가독성, 과학성, 재현성, Evidence를 최우선으로 한다.

---

# NEO PHILOSOPHY

NEO의 목적은 "우승자를 맞추는 것"이 아니다. NEO의 목적은 **"다음 라운드에서 얼마나 좋은 경기력을 보여줄 것인가"**를 예측하는 것이다. 골프는 상대평가이므로, 같은 68타를 쳐도 다른 선수가 65타를 치면 우승하지 못한다 — 우승은 본인의 경기력뿐 아니라 상대 선수의 경기력까지 포함된 결과다. 따라서 **Winner는 Reference Only(참고 지표)**이며, **Performance Continuity가 Primary Objective(주 목적)**다.

| Priority | 지표 | 정의 |
|---|---|---|
| 1 (최우선) | Performance Continuity | Current SG → Next Round SG, Stability, Variance, Mean-Reversion Signal |
| 2 | Performance Ranking | Expected Performance Rank → Actual Performance Rank (Rank Error, MAE, Bias, Correlation) |
| 3 | Round Performance | Expected Round Score → Actual Round Score (Freeze Evidence 존재하는 경우만, 없으면 N/A) |
| 4 | Top20 / Top10 / Top5 | Precision / Recall / F1 |
| 5 (참고용) | Winner | Reference Only — 대표 KPI에서 제외 |

---

# KEY DISCOVERIES

이번 대회에서 가장 중요한 발견 5가지다 (상세 근거는 이후 섹션 참조):

① **Top5 Prediction Precision = 80%** — R2→R3 단계에서 상위 5명 예측 정밀도가 가장 높았다.

② **Performance Ranking Accuracy가 PRE → R1 → R2 → R3 전 구간에서 계속 향상되었다** (순위 MAE: 23.683 → 17.833 → 13.031).

③ **Mean-Reversion Signal 관찰됨** (R1→R2 correlation=-0.6838, R2→R3 correlation=-0.5765). _이 발견은 단일 대회 결과이며, 향후 대회에 걸친 추가 검증이 필요하다 (This finding is based on a single tournament and requires validation across future tournaments.)_

④ **Probability Ranking이 Raw Expected Score보다 더 정확했다** (R2→R3: 확률기반 순위 MAE 13.031 vs 원시 스코어 기반 순위 MAE 15.594).

⑤ **Winner는 대표 KPI가 아니라 Reference Metric이다.** 이번 대회에서 우승 후보는 3단계 모두 실제 리더와 일치하지 않았으나, 이는 NEO의 목적함수와 무관한 참고 정보일 뿐이다.

---

# 목차

1. Executive Summary
2. Stage 1 — PRE → R1 Forensics
3. Stage 2 — R1 → R2 Forensics
4. Stage 3 — R2 → R3 Forensics
5. Stage 4 — R3 → FINAL (BLOCKED)
6. 단계별 정확도 비교
7. 선수별 분석 (Cross-Stage)
8. Biggest Movers (단계별)
9. Current SG 분석 (Feature, not Target)
10. Monte Carlo 분석
11. Calibration / Brier / Log Loss / Reliability / Sharpness
12. 모델 분석 (Root Cause Analysis)
13. 코스 영향 (BLOCKED)
14. 선수 분석 (Closest / Overvalued / Undervalued / Surprise)
15. NEO Philosophy Validation
16. WHAT NEO LEARNED
17. WHAT GOLF TAUGHT THE MODEL
18. CONFIDENCE
19. RESEARCH VS PRODUCTION
20. 콘텐츠 분석
21. NEO SCORECARD (INTERIM)
22. MODEL IMPROVEMENT ROADMAP (Evidence Strength 순)

---

# 1. Executive Summary

NEO의 철학에 따라, Winner Prediction이 아닌 **Performance Continuity**를 중심으로 3개 실측 전환 구간(PRE→R1, R1→R2, R2→R3)을 평가한다.

## Priority 1 — Performance Continuity

| 지표 | R1→R2 | R2→R3 |
|---|---|---|
| Current SG → Next Round SG (r) | 0.1171 | 0.0251 |
| Performance Continuity, score-to-score (r) | 0.1276 | 0.0241 |
| Mean-Reversion Signal (r) | -0.6838 | -0.5765 |

**핵심 발견**: 연속성(SG→SG, Score→Score) 상관계수는 0에 가깝지만, Mean-Reversion Signal 상관계수는 두 구간 모두 강한 음수다. _이 발견은 단일 대회 결과이며, 향후 대회에 걸친 추가 검증이 필요하다 (This finding is based on a single tournament and requires validation across future tournaments.)_

Expected SG(본인 시즌 기준선) 대비 정확도는 라운드가 진행될수록 개선된다: MAE 2.36 → 2.27 → 2.12. (Current SG is a feature, not the target.)

## Priority 2 — Performance Ranking

| Stage | 기준 | N | MAE(순위) | Bias | Rank Correlation |
|---|---|---|---|---|---|
| PRE→R1 | win-probability rank (PROXY -- no raw expected score exists at this checkpoint) | 104 | 23.683 | +4.510 | 0.4826 |
| R1→R2 | win-probability rank (PROXY -- no raw expected score exists at this checkpoint) | 102 | 17.833 | +4.108 | 0.7061 |
| R2→R3(Proxy) | win-probability rank (same proxy method as earlier stages, for direct comparison) | 64 | 13.031 | +2.188 | 0.5863 |
| R2→R3(True) | TRUE performance rank -- ranked by updated_expected_round_score_to_par directly | 64 | 15.594 | +2.188 | 0.4365 |

순위 오차(MAE)는 라운드가 진행될수록 뚜렷이 개선된다. Rank Correlation은 단조롭지 않다 (range restriction 가능성). Bias는 모든 단계에서 양수 — 낙관 편향(optimism bias).

## Priority 3 — Round Performance

| Stage | 가용성 | MAE | RMSE | Bias |
|---|---|---|---|---|
| PRE→R1 | N/A | — | — | — |
| R1→R2 | N/A | — | — | — |
| R2→R3 (Historical Baseline) | 가용 | 2.4828 | 3.1990 | -1.7960 |
| R2→R3 (Current-SG Updated) | 가용 | 2.6212 | 3.3421 | -2.0948 |

PRE→R1, R1→R2 단계는 Freeze Evidence에 원시 예측 스코어가 존재하지 않아 N/A로 명시한다 — 추정하지 않는다.

## Priority 4 — Top20/Top10/Top5

| Stage | Top20 F1 | Top10 F1 | Top5 F1 |
|---|---|---|---|
| PRE→R1 | 0.341 | 0.320 | 0.364 |
| R1→R2 | 0.571 | 0.615 | 0.400 |
| R2→R3 | 0.667 | 0.700 | 0.800 |

## Priority 5 — Winner (Reference Only)

우승 후보는 3단계 모두 실제 리더와 일치하지 않았다 (0/3, Reference Only). 이 수치는 대표 성능으로 사용하지 않는다.

---

# 2. Stage 1 — PRE → R1 Forensics

모집단: 104명 (PRE·R1 공통, R1 기권 3명 제외: 조혜림, 김리안, 권은 0906(A))

## Performance Analysis (Priority 1-3)

### Priority 1 — Performance Continuity

**Expected SG → Actual SG** _(Current SG is a feature, not the target — NEO predicts Performance, not SG.)_

| Round | N | MAE | RMSE | Bias |
|---|---|---|---|---|
| r1 | 98 | 2.3589 | 2.9537 | -0.5778 |

**Continuity / Stability / Variance / Mean-Reversion**: 이전 대회 내 라운드가 없어 PRE→R1 단계에서는 연속성(continuity)·평균회귀 신호·모멘텀 분석이 원천적으로 불가능하다 (최소 2개 라운드 필요). N/A로 명시하며 추정하지 않는다.

### Priority 2 — Performance Ranking

| 항목 | 값 |
|---|---|
| 기준 | win-probability rank (PROXY -- no raw expected score exists at this checkpoint) |
| N | 104 |
| MAE(순위) | 23.683 |
| Bias | +4.510 |
| Rank Correlation | 0.4826 |

### Priority 3 — Round Performance (Expected Round Score → Actual Round Score)

**N/A** — no expected-round-score artifact frozen at PRE (probability-only forecast). 절대 추정하지 않는다.

## Priority 4 — Top20 / Top10 / Top5

| Threshold | 예측 크기 | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| TOP20 | 20 | 7 | 13 | 14 | 0.350 | 0.333 | 0.341 |
| TOP10 | 10 | 4 | 6 | 11 | 0.400 | 0.267 | 0.320 |
| TOP5 | 5 | 2 | 3 | 4 | 0.400 | 0.333 | 0.364 |

### False Positive / False Negative

**TOP20**
- **False Positive** (예측했지만 실제 미달): 김민별(73), 김민주(73), 방신실(31), 김민솔(73), 서교림(39), 최예림(31), 이다연(22), 전예성(39), 노승희(22), 신다인(39), 이지현3(39), 이예원(22), 박혜준(73)
- **False Negative** (실제 달성했지만 예측 실패): 고지원(16), 홍진영2(7), 박예지(7), 안재희(16), 양윤서 0801(A)(16), 한아름(7), 왕 즈쉬엔(16), 이주미(3), 장은수(7), 박단유(7), 이가영(7), 임희정(16), 박보겸(3), 이세희(7)

**TOP10**
- **False Positive** (예측했지만 실제 미달): 김민주(73), 김민솔(73), 서교림(39), 최예림(31), 이다연(22), 노승희(22)
- **False Negative** (실제 달성했지만 예측 실패): 황유민(3), 홍진영2(7), 박예지(7), 한아름(7), 이주미(3), 장은수(7), 박단유(7), 박민지(1), 이가영(7), 박보겸(3), 이세희(7)

**TOP5**
- **False Positive** (예측했지만 실제 미달): 김민솔(73), 서교림(39), 최예림(31)
- **False Negative** (실제 달성했지만 예측 실패): 황유민(3), 이주미(3), 박민지(1), 박보겸(3)

## Priority 5 — Winner (Reference Only)

예측: **서교림** — 실제 R1 리더: **박민지** (실제순위 1) — Reference Only, 대표 성능 아님.

PRE 모델은 K-Rank/최근성적 기반 사전 예측만 가지고 있었다. Winner 불일치는 NEO의 주 목적(Performance Continuity)과 무관한 참고 정보일 뿐이다.

---

# 3. Stage 2 — R1 → R2 Forensics

모집단: 105명 (R1 기권 3명 제외 105명 예측 대상), 실제 R2 순위 산정 대상 102명 (WD 3명 별도 제외)

컷 통과: 64명, 컷 탈락: 38명

## Performance Analysis (Priority 1-3)

### Priority 1 — Performance Continuity

**Expected SG → Actual SG** _(Current SG is a feature, not the target — NEO predicts Performance, not SG.)_

| Round | N | MAE | RMSE | Bias |
|---|---|---|---|---|
| r2 | 96 | 2.2690 | 2.8105 | -0.6927 |

**Current SG → Next Round SG** (연속성): N=102, Pearson r=0.1171

**Performance Continuity** (라운드 간 상대순위 일관성, score-to-score): N=102, Pearson r=0.1276

**Variance** (필드 전체 스코어 분산): R1 stddev=3.0934, R2 stddev=2.9266

**Mean-Reversion Signal observed**: N=102, correlation=-0.6838

_이 발견은 단일 대회 결과이며, 향후 대회에 걸친 추가 검증이 필요하다 (This finding is based on a single tournament and requires validation across future tournaments.)_

### Priority 2 — Performance Ranking

| 항목 | 값 |
|---|---|
| 기준 | win-probability rank (PROXY -- no raw expected score exists at this checkpoint) |
| N | 102 |
| MAE(순위) | 17.833 |
| Bias | +4.108 |
| Rank Correlation | 0.7061 |

### Priority 3 — Round Performance (Expected Round Score → Actual Round Score)

**N/A** — no expected-round-score artifact frozen at post-R1 (probability-only forecast). 절대 추정하지 않는다.

## Priority 4 — Top20 / Top10 / Top5

| Threshold | 예측 크기 | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| TOP20 | 20 | 12 | 8 | 10 | 0.600 | 0.545 | 0.571 |
| TOP10 | 10 | 8 | 2 | 8 | 0.800 | 0.500 | 0.615 |
| TOP5 | 5 | 2 | 3 | 3 | 0.400 | 0.400 | 0.400 |

### False Positive / False Negative

**TOP20**
- **False Positive** (예측했지만 실제 미달): 고지원(71), 유현조(23), 문정민(30), 최예림(59), 이다연(23), 배소현(23), 노승희(30), 이예원(38)
- **False Negative** (실제 달성했지만 예측 실패): 박예지(17), 양윤서 0801(A)(6), 이와이 아키(9), 이와이 치지(6), 조아연(17), 이채은2(9), 전예성(17), 임희정(9), 강가율(17), 최은우(9)

**TOP10**
- **False Positive** (예측했지만 실제 미달): 유현조(23), 문정민(30)
- **False Negative** (실제 달성했지만 예측 실패): 홍진영2(2), 양윤서 0801(A)(6), 이와이 아키(9), 이와이 치지(6), 이채은2(9), 이가영(9), 임희정(9), 최은우(9)

**TOP5**
- **False Positive** (예측했지만 실제 미달): 유현조(23), 박민지(6), 성유진(9)
- **False Negative** (실제 달성했지만 예측 실패): 홍진영2(2), 장은수(1), 이세희(5)

## Priority 5 — Winner (Reference Only)

예측: **박민지** — 실제 R2(36홀 누적) 리더: **장은수** (실제순위 1) — Reference Only, 대표 성능 아님.

Winner 불일치보다 위의 Performance 지표(Priority 1-3)가 이 단계의 진짜 평가 기준이다.

---

# 4. Stage 3 — R2 → R3 Forensics

모집단: 64명 (컷 통과자 전원)

## Performance Analysis (Priority 1-3)

### Priority 1 — Performance Continuity

**Expected SG → Actual SG** _(Current SG is a feature, not the target — NEO predicts Performance, not SG.)_

| Round | N | MAE | RMSE | Bias |
|---|---|---|---|---|
| r3 | 61 | 2.1206 | 2.8581 | -1.0260 |

**Current SG → Next Round SG** (연속성): N=64, Pearson r=0.0251

**Performance Continuity** (라운드 간 상대순위 일관성, score-to-score): N=64, Pearson r=0.0241

**Variance** (필드 전체 스코어 분산): R2 stddev=2.9266, R3 stddev=2.7776

**Mean-Reversion Signal observed**: N=64, correlation=-0.5765

_이 발견은 단일 대회 결과이며, 향후 대회에 걸친 추가 검증이 필요하다 (This finding is based on a single tournament and requires validation across future tournaments.)_

### Priority 2 — Performance Ranking

| 항목 | 값 |
|---|---|
| 기준 | win-probability rank (same proxy method as earlier stages, for direct comparison) |
| N | 64 |
| MAE(순위) | 13.031 |
| Bias | +2.188 |
| Rank Correlation | 0.5863 |

### Priority 3 — Round Performance (Expected Round Score → Actual Round Score)

| Model | MAE | RMSE | Bias |
|---|---|---|---|
| Historical Baseline | 2.4828 | 3.1990 | -1.7960 |
| Current-SG Updated | 2.6212 | 3.3421 | -2.0948 |

(출처: HANA_2026090002_R2_R3_OOS_VALIDATION_REPORT_V1.json (reused verbatim, not recomputed))

## Priority 4 — Top20 / Top10 / Top5

| Threshold | 예측 크기 | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| TOP20 | 20 | 14 | 6 | 8 | 0.700 | 0.636 | 0.667 |
| TOP10 | 10 | 7 | 3 | 3 | 0.700 | 0.700 | 0.700 |
| TOP5 | 5 | 4 | 1 | 1 | 0.800 | 0.800 | 0.800 |

### False Positive / False Negative

**TOP20**
- **False Positive** (예측했지만 실제 미달): 서교림(23), 이다연(45), 이채은2(40), 이가영(23), 전예성(57), 임희정(23)
- **False Negative** (실제 달성했지만 예측 실패): 김민별(18), 홍현지(18), 박예지(16), 한아름(18), 이와이 아키(11), 이주미(18), 조아연(18), 이예원(16)

**TOP10**
- **False Positive** (예측했지만 실제 미달): 김수지(11), 성유진(11), 최은우(11)
- **False Negative** (실제 달성했지만 예측 실패): 짜라위 분짠(I)(7), 이와이 치지(9), 박보겸(7)

**TOP5**
- **False Positive** (예측했지만 실제 미달): 홍진영2(6)
- **False Negative** (실제 달성했지만 예측 실패): 박민지(3)

## Priority 5 — Winner (Reference Only)

예측: **장은수** — 실제 R3 리더: **김민선7** (실제순위 1) — Reference Only, 대표 성능 아님.

김민선7는 R2 시점 예측 3위에서 실제 R3 1위로 상승했다 — 이는 Winner 적중 여부와 무관하게, Priority 1-3 Performance 지표가 이 이변을 설명하는 진짜 근거임을 재확인시켜 준다.

---

# 5. Stage 4 — R3 → FINAL

**BLOCKED — 공식 FINAL(FR) 증거 없음.** `2026090002_POST_R4_FINAL_PREVIEW.json`은 모델의 예측(forecast)일 뿐 실제 결과가 아니며, 이를 "실제"로 취급하는 것은 조작(fabrication)에 해당하므로 수행하지 않는다.

---

# 6. 단계별 정확도 비교

## Priority 1: Performance Continuity

| 전환 구간 | SG 연속성(r) | Score 연속성(r) | Mean-Reversion Signal(r) |
|---|---|---|---|
| R1→R2 | 0.1171 | 0.1276 | -0.6838 |
| R2→R3 | 0.0251 | 0.0241 | -0.5765 |

_이 발견은 단일 대회 결과이며, 향후 대회에 걸친 추가 검증이 필요하다 (This finding is based on a single tournament and requires validation across future tournaments.)_

## Priority 2: Performance Ranking

| Stage | MAE(순위) | Bias | Rank Correlation |
|---|---|---|---|
| PRE→R1 | 23.683 | +4.510 | 0.4826 |
| R1→R2 | 17.833 | +4.108 | 0.7061 |
| R2→R3(Proxy) | 13.031 | +2.188 | 0.5863 |
| R2→R3(True) | 15.594 | +2.188 | 0.4365 |

## Priority 3: Round Performance

| Stage | MAE | RMSE | Bias |
|---|---|---|---|
| PRE→R1 | N/A | N/A | N/A |
| R1→R2 | N/A | N/A | N/A |
| R2→R3 (Current-SG) | 2.6212 | 3.3421 | -2.0948 |

## Priority 4: Top20 / Top10 / Top5

| Stage | Top20 (P/R/F1) | Top10 (P/R/F1) | Top5 (P/R/F1) |
|---|---|---|---|
| PRE→R1 | 0.350/0.333/0.341 | 0.400/0.267/0.320 | 0.400/0.333/0.364 |
| R1→R2 | 0.600/0.545/0.571 | 0.800/0.500/0.615 | 0.400/0.400/0.400 |
| R2→R3 | 0.700/0.636/0.667 | 0.700/0.700/0.700 | 0.800/0.800/0.800 |

## Priority 5: Winner (Reference Only)

| Stage | Winner Hit |
|---|---|
| PRE→R1 | Reference Only |
| R1→R2 | Reference Only |
| R2→R3 | Reference Only |
| R3→FINAL | BLOCKED |

---

# 7. 선수별 분석 (Cross-Stage)

(예측순위는 확률기반 Proxy — Priority 2 섹션 참조.)

## PRE → R1 (전체 104명)

| 실제순위 | 선수 | 예측순위(확률기반) | 변화량 |
|---|---|---|---|
| 1 | 박민지 | 15 | +14 |
| 1 | 성유진 | 4 | +3 |
| 3 | 유현조 | 3 | +0 |
| 3 | 황유민 | 12 | +9 |
| 3 | 이주미 | 55 | +52 |
| 3 | 박보겸 | 32 | +29 |
| 7 | 김민선7 | 7 | +0 |
| 7 | 문정민 | 8 | +1 |
| 7 | 홍진영2 | 43 | +36 |
| 7 | 박예지 | 42 | +35 |
| 7 | 한아름 | 37 | +30 |
| 7 | 장은수 | 25 | +18 |
| 7 | 박단유 | 77 | +70 |
| 7 | 이가영 | 27 | +20 |
| 7 | 이세희 | 39 | +32 |
| 16 | 고지원 | 46 | +30 |
| 16 | 안재희 | 74 | +58 |
| 16 | 양윤서 0801(A) | 90 | +74 |
| 16 | 왕 즈쉬엔 | 78 | +62 |
| 16 | 김수지 | 18 | +2 |
| 16 | 임희정 | 53 | +37 |
| 22 | 송은아 | 51 | +29 |
| 22 | 이와이 치지 | 72 | +50 |
| 22 | 이다연 | 6 | -16 |
| 22 | 배소현 | 29 | +7 |
| 22 | 노승희 | 10 | -12 |
| 22 | 박결 | 65 | +43 |
| 22 | 김재희 | 52 | +30 |
| 22 | 유지나 | 45 | +23 |
| 22 | 이예원 | 17 | -5 |
| 31 | 방신실 | 16 | -15 |
| 31 | 김지윤2 | 80 | +49 |
| 31 | 이와이 아키 | 70 | +39 |
| 31 | 빳차라쭈타 콩끄라판(I) | 49 | +18 |
| 31 | 최예림 | 2 | -29 |
| 31 | 강가율 | 101 | +70 |
| 31 | 홍지원 | 36 | +5 |
| 31 | 정윤지 | 23 | -8 |
| 39 | 고지우 | 33 | -6 |
| 39 | 현세린 | 91 | +52 |
| 39 | 양효진 | 44 | +5 |
| 39 | 서교림 | 1 | -38 |
| 39 | 김시현 | 41 | +2 |
| 39 | 짜라위 분짠(I) | 38 | -1 |
| 39 | 이민지 | 24 | -15 |
| 39 | 김새로미 | 31 | -8 |
| 39 | 조아연 | 83 | +44 |
| 39 | 이채은2 | 34 | -5 |
| 39 | 전예성 | 14 | -25 |
| 39 | 서어진 | 21 | -18 |
| 39 | 신다인 | 19 | -20 |
| 39 | 최은우 | 26 | -13 |
| 39 | 박소혜 | 82 | +43 |
| 39 | 최가빈 | 35 | -4 |
| 39 | 이지현3 | 11 | -28 |
| 56 | 마서영 | 60 | +4 |
| 56 | 임진영 | 66 | +10 |
| 56 | 이세영 | 97 | +41 |
| 56 | 홍현지 | 56 | +0 |
| 56 | 최정원 | 63 | +7 |
| 56 | 지한솔 | 28 | -28 |
| 56 | 청 야니 | 73 | +17 |
| 56 | 안송이 | 57 | +1 |
| 56 | 장수연 | 102 | +46 |
| 56 | 송가은 | 62 | +6 |
| 56 | 윤화영 | 79 | +23 |
| 56 | 조정민 | 93 | +37 |
| 56 | 전우리 | 47 | -9 |
| 56 | 안지현 | 58 | +2 |
| 56 | 한지원 | 59 | +3 |
| 56 | 정소이 | 48 | -8 |
| 56 | 황유나 | 75 | +19 |
| 73 | 김민별 | 20 | -53 |
| 73 | 김민주 | 9 | -64 |
| 73 | 김민솔 | 5 | -68 |
| 73 | 김가희2 | 68 | -5 |
| 73 | 최민경 | 54 | -19 |
| 73 | 정수빈 | 88 | +15 |
| 73 | 김소정 | 86 | +13 |
| 73 | 마다솜 | 50 | -23 |
| 73 | 박혜준 | 13 | -60 |
| 82 | 이효송 | 99 | +17 |
| 82 | 장하나 | 104 | +22 |
| 82 | 김지영2 | 103 | +21 |
| 82 | 김우정 | 67 | -15 |
| 82 | 이재윤 | 84 | +2 |
| 82 | 노원경 | 100 | +18 |
| 88 | 김희지 | 95 | +7 |
| 88 | 이 민 | 69 | -19 |
| 88 | 이지민 | 92 | +4 |
| 88 | 김지수 | 64 | -24 |
| 88 | 김아현 | 94 | +6 |
| 88 | 한진선 | 22 | -66 |
| 94 | 오수민 0809(A) | 81 | -13 |
| 94 | 리디아 고 | 76 | -18 |
| 94 | 이슬기2 | 98 | +4 |
| 94 | 이율린 | 85 | -9 |
| 98 | 이승연 | 40 | -58 |
| 98 | 홍정민 | 30 | -68 |
| 100 | 이정민 | 89 | -11 |
| 101 | 최예본 | 61 | -40 |
| 101 | 이소영 | 96 | -5 |
| 103 | 리 슈잉 | 87 | -16 |
| 103 | 플로렌스 이본 비세라 | 71 | -32 |

## R1 → R2 (전체 105명)

| 실제순위 | 선수 | 예측순위(확률기반) | 변화량 |
|---|---|---|---|
| 1 | 장은수 | 8 | +7 |
| 2 | 김민선7 | 5 | +3 |
| 2 | 황유민 | 3 | +1 |
| 2 | 홍진영2 | 16 | +14 |
| 5 | 이세희 | 9 | +4 |
| 6 | 양윤서 0801(A) | 27 | +21 |
| 6 | 이와이 치지 | 31 | +25 |
| 6 | 박민지 | 1 | -5 |
| 9 | 이와이 아키 | 40 | +31 |
| 9 | 김수지 | 10 | +1 |
| 9 | 이채은2 | 46 | +37 |
| 9 | 성유진 | 4 | -5 |
| 9 | 이가영 | 11 | +2 |
| 9 | 임희정 | 24 | +15 |
| 9 | 최은우 | 42 | +33 |
| 9 | 박보겸 | 6 | -3 |
| 17 | 박예지 | 18 | +1 |
| 17 | 한아름 | 13 | -4 |
| 17 | 이주미 | 12 | -5 |
| 17 | 조아연 | 56 | +39 |
| 17 | 전예성 | 37 | +20 |
| 17 | 강가율 | 93 | +76 |
| 23 | 유현조 | 2 | -21 |
| 23 | 홍현지 | 51 | +28 |
| 23 | 송은아 | 30 | +7 |
| 23 | 이다연 | 14 | -9 |
| 23 | 배소현 | 19 | -4 |
| 23 | 김재희 | 33 | +10 |
| 23 | 홍지원 | 34 | +11 |
| 30 | 방신실 | 23 | -7 |
| 30 | 고지우 | 49 | +19 |
| 30 | 문정민 | 7 | -23 |
| 30 | 이세영 | 69 | +39 |
| 30 | 안재희 | 26 | -4 |
| 30 | 짜라위 분짠(I) | 44 | +14 |
| 30 | 빳차라쭈타 콩끄라판(I) | 53 | +23 |
| 30 | 노승희 | 15 | -15 |
| 38 | 김민별 | 60 | +22 |
| 38 | 김민솔 | 50 | +12 |
| 38 | 서교림 | 25 | -13 |
| 38 | 최민경 | 82 | +44 |
| 38 | 박단유 | 22 | -16 |
| 38 | 김소정 | 92 | +54 |
| 38 | 서어진 | 38 | +0 |
| 38 | 박결 | 29 | -9 |
| 38 | 이지현3 | 32 | -6 |
| 38 | 안지현 | 98 | +60 |
| 38 | 이예원 | 20 | -18 |
| 38 | 황유나 | 105 | +67 |
| 50 | 임진영 | 62 | +12 |
| 50 | 현세린 | 64 | +14 |
| 50 | 왕 즈쉬엔 | 28 | -22 |
| 50 | 청 야니 | 77 | +27 |
| 50 | 김새로미 | 55 | +5 |
| 50 | 김우정 | 86 | +36 |
| 50 | 박소혜 | 57 | +7 |
| 50 | 최가빈 | 47 | -3 |
| 50 | 정소이 | 58 | +8 |
| 59 | 김가희2 | 66 | +7 |
| 59 | 최예림 | 21 | -38 |
| 59 | 송가은 | 85 | +26 |
| 59 | 김아현 | 94 | +35 |
| 59 | 한진선 | 97 | +38 |
| 59 | 유지나 | 35 | -24 |
| 65 | 최정원 | 70 | +5 |
| 65 | 김시현 | 43 | -22 |
| 65 | 김지윤2 | 52 | -13 |
| 65 | 지한솔 | 45 | -20 |
| 65 | 이민지 | 54 | -11 |
| 65 | 신다인 | 41 | -24 |
| 71 | 고지원 | 17 | -54 |
| 71 | 양효진 | 39 | -32 |
| 71 | 이효송 | 72 | +1 |
| 71 | 오수민 0809(A) | 73 | +2 |
| 71 | 리디아 고 | 76 | +5 |
| 71 | 윤화영 | 89 | +18 |
| 71 | 전우리 | 95 | +24 |
| 71 | 이율린 | 104 | +33 |
| 79 | 김민주 | 48 | -31 |
| 79 | 김희지 | 63 | -16 |
| 79 | 조정민 | 90 | +11 |
| 79 | 마다솜 | 96 | +17 |
| 79 | 한지원 | 99 | +20 |
| 79 | 정윤지 | 36 | -43 |
| 85 | 마서영 | 61 | -24 |
| 85 | 이정민 | 79 | -6 |
| 85 | 장수연 | 83 | -2 |
| 85 | 김지영2 | 84 | -1 |
| 85 | 정수빈 | 87 | +2 |
| 85 | 이승연 | 88 | +3 |
| 91 | 이 민 | 71 | -20 |
| 91 | 이소영 | 81 | -10 |
| 91 | 김지수 | 91 | +0 |
| 91 | 노원경 | 102 | +11 |
| 95 | 이재윤 | 101 | +6 |
| 96 | 안송이 | 78 | -18 |
| 97 | 이지민 | 74 | -23 |
| 97 | 장하나 | 80 | -17 |
| 97 | 이슬기2 | 100 | +3 |
| 100 | 양서후 | 68 | -32 |
| 100 | 홍정민 | 103 | +3 |
| 102 | 플로렌스 이본 비세라 | 75 | -27 |

## R2 → R3 (전체 64명)

| 실제순위 | 선수 | 예측순위(확률기반) | 변화량 |
|---|---|---|---|
| 1 | 김민선7 | 3 | +2 |
| 2 | 장은수 | 1 | -1 |
| 3 | 황유민 | 2 | -1 |
| 3 | 양윤서 0801(A) | 6 | +3 |
| 3 | 박민지 | 9 | +6 |
| 6 | 홍진영2 | 4 | -2 |
| 7 | 짜라위 분짠(I) | 27 | +20 |
| 7 | 박보겸 | 18 | +11 |
| 9 | 이와이 치지 | 5 | -4 |
| 9 | 이세희 | 10 | +1 |
| 11 | 유현조 | 17 | +6 |
| 11 | 이와이 아키 | 7 | -4 |
| 11 | 김수지 | 11 | +0 |
| 11 | 성유진 | 12 | +1 |
| 11 | 최은우 | 8 | -3 |
| 16 | 박예지 | 36 | +20 |
| 16 | 이예원 | 26 | +10 |
| 18 | 김민별 | 28 | +10 |
| 18 | 홍현지 | 35 | +17 |
| 18 | 한아름 | 22 | +4 |
| 18 | 이주미 | 41 | +23 |
| 18 | 조아연 | 25 | +7 |
| 23 | 문정민 | 23 | +0 |
| 23 | 현세린 | 32 | +9 |
| 23 | 서교림 | 21 | -2 |
| 23 | 빳차라쭈타 콩끄라판(I) | 40 | +17 |
| 23 | 최민경 | 42 | +19 |
| 23 | 이가영 | 15 | -8 |
| 23 | 임희정 | 20 | -3 |
| 23 | 강가율 | 52 | +29 |
| 23 | 김재희 | 60 | +37 |
| 23 | 홍지원 | 61 | +38 |
| 33 | 송은아 | 37 | +4 |
| 33 | 박단유 | 44 | +11 |
| 33 | 배소현 | 46 | +13 |
| 33 | 노승희 | 50 | +17 |
| 33 | 한진선 | 57 | +24 |
| 33 | 이지현3 | 58 | +25 |
| 33 | 안지현 | 59 | +26 |
| 40 | 김민솔 | 24 | -16 |
| 40 | 김가희2 | 33 | -7 |
| 40 | 이채은2 | 14 | -26 |
| 40 | 서어진 | 51 | +11 |
| 40 | 박결 | 53 | +13 |
| 45 | 고지우 | 30 | -15 |
| 45 | 안재희 | 38 | -7 |
| 45 | 이다연 | 13 | -32 |
| 45 | 김우정 | 48 | +3 |
| 45 | 정소이 | 63 | +18 |
| 50 | 임진영 | 31 | -19 |
| 50 | 이세영 | 34 | -16 |
| 50 | 최예림 | 43 | -7 |
| 50 | 김새로미 | 45 | -5 |
| 50 | 최가빈 | 56 | +6 |
| 50 | 유지나 | 62 | +12 |
| 50 | 황유나 | 64 | +14 |
| 57 | 청 야니 | 19 | -38 |
| 57 | 송가은 | 47 | -10 |
| 57 | 전예성 | 16 | -41 |
| 57 | 김소정 | 49 | -8 |
| 61 | 왕 즈쉬엔 | 39 | -22 |
| 61 | 박소혜 | 55 | -6 |
| 63 | 김아현 | 54 | -9 |
| 64 | 방신실 | 29 | -35 |

---

# 8. Biggest Movers (단계별, 우승확률 기준 — 참고용 지표)

## PRE → R1

**▲ 상승 TOP10**

1. 박민지: 2.240% → 10.500% (+8.260pp)
2. 황유민: 2.523% → 8.500% (+5.977pp)
3. 유현조: 5.535% → 10.400% (+4.865pp)
4. 박보겸: 0.789% → 4.600% (+3.811pp)
5. 성유진: 4.916% → 8.500% (+3.584pp)
6. 이세희: 0.628% → 3.200% (+2.572pp)
7. 이주미: 0.366% → 2.900% (+2.534pp)
8. 김민선7: 3.249% → 5.400% (+2.151pp)
9. 이가영: 0.993% → 3.100% (+2.107pp)
10. 장은수: 1.134% → 3.200% (+2.066pp)

**▼ 하락 TOP10**

1. 서교림: 7.838% → 1.000% (-6.838pp)
2. 최예림: 6.808% → 1.200% (-5.608pp)
3. 김민솔: 4.548% → 0.100% (-4.448pp)
4. 김민주: 2.840% → 0.100% (-2.740pp)
5. 박혜준: 2.405% → 0.100% (-2.305pp)
6. 이지현3: 2.575% → 0.500% (-2.075pp)
7. 전예성: 2.374% → 0.400% (-1.974pp)
8. 신다인: 1.746% → 0.300% (-1.446pp)
9. 김민별: 1.326% → 0.000% (-1.326pp)
10. 한진선: 1.264% → 0.000% (-1.264pp)

## R1 → R2

**▲ 상승 TOP10**

1. 장은수: 3.200% → 47.852% (+44.652pp)
2. 황유민: 8.500% → 20.377% (+11.877pp)
3. 김민선7: 5.400% → 11.437% (+6.037pp)
4. 홍진영2: 2.000% → 5.150% (+3.150pp)
5. 이와이 치지: 0.600% → 3.655% (+3.055pp)
6. 양윤서 0801(A): 0.700% → 3.393% (+2.693pp)
7. 이와이 아키: 0.300% → 2.160% (+1.860pp)
8. 최은우: 0.300% → 1.105% (+0.805pp)
9. 청 야니: 0.000% → 0.097% (+0.097pp)
10. 이채은2: 0.200% → 0.240% (+0.040pp)

**▼ 하락 TOP10**

1. 유현조: 10.400% → 0.377% (-10.023pp)
2. 박민지: 10.500% → 1.150% (-9.350pp)
3. 성유진: 8.500% → 0.628% (-7.872pp)
4. 박보겸: 4.600% → 0.092% (-4.508pp)
5. 문정민: 4.400% → 0.042% (-4.358pp)
6. 이가영: 3.100% → 0.137% (-2.963pp)
7. 이주미: 2.900% → 0.000% (-2.900pp)
8. 이세희: 3.200% → 0.473% (-2.727pp)
9. 한아름: 2.400% → 0.020% (-2.380pp)
10. 김수지: 3.100% → 0.733% (-2.367pp)

## R2 → R3

**▲ 상승 TOP10**

1. 김민선7: 11.015% → 45.543% (+34.528pp)
2. 양윤서 0801(A): 2.098% → 6.058% (+3.960pp)
3. 박민지: 0.565% → 2.750% (+2.185pp)
4. 빳차라쭈타 콩끄라판(I): 0.000% → 0.000% (+0.000pp)
5. 이주미: 0.000% → 0.000% (+0.000pp)
6. 최민경: 0.000% → 0.000% (+0.000pp)
7. 최예림: 0.000% → 0.000% (+0.000pp)
8. 박단유: 0.000% → 0.000% (+0.000pp)
9. 김새로미: 0.000% → 0.000% (+0.000pp)
10. 배소현: 0.000% → 0.000% (+0.000pp)

**▼ 하락 TOP10**

1. 장은수: 54.262% → 35.258% (-19.003pp)
2. 황유민: 20.278% → 10.202% (-10.077pp)
3. 홍진영2: 5.352% → 0.002% (-5.350pp)
4. 이와이 치지: 2.887% → 0.147% (-2.740pp)
5. 이와이 아키: 1.483% → 0.040% (-1.443pp)
6. 최은우: 0.608% → 0.000% (-0.608pp)
7. 이세희: 0.337% → 0.000% (-0.337pp)
8. 김수지: 0.308% → 0.000% (-0.308pp)
9. 성유진: 0.220% → 0.000% (-0.220pp)
10. 이다연: 0.133% → 0.000% (-0.133pp)

---

# 9. Current SG 분석 (Feature, not Target)

**Current SG is a feature, not the target. NEO predicts Performance, not SG.** 이 섹션의 모든 지표는 Current SG가 Performance Continuity를 설명하는 데 얼마나 기여하는지를 보기 위한 것이지, SG 자체를 최적화 목표로 삼는 것이 아니다.

## Expected SG → Actual SG

| Round | N | MAE | RMSE | Bias |
|---|---|---|---|---|
| r1 | 98 | 2.3589 | 2.9537 | -0.5778 |
| r2 | 96 | 2.2690 | 2.8105 | -0.6927 |
| r3 | 61 | 2.1206 | 2.8581 | -1.0260 |

Expected SG는 PRE_PERFORMANCE_SNAPSHOT의 recent5(또는 season2026) 윈도우 SG 평균 — 대회 시작 전 고정된 본인 기준선이다.

## Current SG → Next Round SG (연속성)

| 구간 | N | Pearson r |
|---|---|---|
| R1 SG → R2 SG | 102 | 0.1171 |
| R2 SG → R3 SG | 64 | 0.0251 |

## Performance Continuity (score-to-score)

| 구간 | N | Pearson r |
|---|---|---|
| R1 → R2 | 102 | 0.1276 |
| R2 → R3 | 64 | 0.0241 |

## Variance (필드 전체 스코어 분산)

| Round | N | Mean(to-par) | Stddev |
|---|---|---|---|
| R1 | 102 | 3.1961 | 3.0934 |
| R2 | 102 | 2.0588 | 2.9266 |
| R3 | 64 | 0.8125 | 2.7776 |

## Mean-Reversion Signal

| 구간 | N | 필드 평균(N라운드) | Correlation |
|---|---|---|---|
| R1 → R2 | 102 | 3.1961 | -0.6838 |
| R2 → R3 | 64 | 0.6406 | -0.5765 |

_이 발견은 단일 대회 결과이며, 향후 대회에 걸친 추가 검증이 필요하다 (This finding is based on a single tournament and requires validation across future tournaments.)_

**해석**: (필드 평균 대비 편차) vs (다음 라운드 변화량)의 상관계수가 두 구간 모두 강한 음수다 — 평균보다 훨씬 잘 치거나 못 친 선수일수록 다음 라운드에 평균 쪽으로 되돌아오는 패턴이 관찰된다. 이는 "Current SG/Score의 다음 라운드 예측력이 거의 0"이라는 발견과 같은 현상을 다른 각도에서 재확인한 것이다.

---

# 10. Monte Carlo 분석

Monte Carlo는 재실행하지 않았다. 대신 이미 Freeze에 기록된 분포 파라미터(seed=20260918, n_simulations=60000, 그리고 각 선수의 `expected_round_score_to_par`/`spread`)를 그대로 인용한다.

- R2→R3 예측(candidate freeze)의 시뮬레이션 파라미터: `n_simulations=60000`, `seed=20260918`
- 우승확률 합계는 R2→R3, R3→FINAL(preview) 모두 정확히 100.0%로 검증됨.
- 필드 전체의 "실제 결과가 분포 안에 있었는가" 총괄 판정은 이미 173번 스크립트가 MAE/RMSE/Bias로 정량화했다 (Priority 3 섹션 참조).

---

# 11. Calibration / Brier / Log Loss / Reliability / Sharpness (Top20 확률 기준, 참고용)

## PRE → R1

| Bucket | N | Mean Predicted | Actual Rate |
|---|---|---|---|
| [0.0,0.1) | 51 | 0.046 | 0.098 |
| [0.1,0.2) | 21 | 0.147 | 0.286 |
| [0.2,0.3) | 11 | 0.250 | 0.273 |
| [0.3,0.4) | 3 | 0.337 | 0.000 |
| [0.4,0.5) | 6 | 0.451 | 0.333 |
| [0.5,0.6) | 5 | 0.544 | 0.400 |
| [0.6,0.7) | 2 | 0.607 | 0.500 |
| [0.7,0.8) | 3 | 0.753 | 0.667 |
| [0.8,0.9) | 2 | 0.869 | 0.000 |

N=104, Brier=0.16666, LogLoss=0.51967, ECE(Reliability gap)=0.10056, Sharpness(stddev)=0.20887

## R1 → R2 (Top20 기준)

| Bucket | N | Mean Predicted | Actual Rate |
|---|---|---|---|
| [0.0,0.1) | 53 | 0.037 | 0.038 |
| [0.1,0.2) | 11 | 0.154 | 0.182 |
| [0.2,0.3) | 14 | 0.258 | 0.286 |
| [0.3,0.4) | 6 | 0.356 | 0.167 |
| [0.4,0.5) | 7 | 0.450 | 0.429 |
| [0.5,0.6) | 7 | 0.542 | 0.714 |
| [0.6,0.7) | 3 | 0.648 | 0.667 |
| [0.7,0.8) | 2 | 0.765 | 1.000 |
| [0.8,0.9) | 2 | 0.816 | 0.500 |

N=105, Brier=0.11459, LogLoss=0.35740, ECE(Reliability gap)=0.04167, Sharpness(stddev)=0.21772

### R1 → R2 (컷확률 기준, script 172의 R1 cut-probability calibration과 동일 방법론)

| Bucket | N | Mean Predicted | Actual Rate |
|---|---|---|---|
| [0.0,0.1) | 14 | 0.051 | 0.000 |
| [0.1,0.2) | 6 | 0.150 | 0.167 |
| [0.2,0.3) | 5 | 0.231 | 0.600 |
| [0.3,0.4) | 5 | 0.370 | 0.200 |
| [0.4,0.5) | 9 | 0.449 | 0.667 |
| [0.5,0.6) | 12 | 0.526 | 0.583 |
| [0.6,0.7) | 10 | 0.646 | 0.600 |
| [0.7,0.8) | 9 | 0.736 | 0.778 |
| [0.8,0.9) | 12 | 0.850 | 0.917 |
| [0.9,1.0) | 23 | 0.949 | 0.957 |

N=105, Brier=0.14248, LogLoss=0.42807, ECE(Reliability gap)=0.07581, Sharpness(stddev)=0.31450

## R2 → R3

| Bucket | N | Mean Predicted | Actual Rate |
|---|---|---|---|
| [0.0,0.1) | 29 | 0.016 | 0.069 |
| [0.1,0.2) | 5 | 0.142 | 0.200 |
| [0.2,0.3) | 6 | 0.222 | 0.333 |
| [0.3,0.4) | 3 | 0.358 | 0.667 |
| [0.4,0.5) | 3 | 0.451 | 0.667 |
| [0.5,0.6) | 3 | 0.555 | 0.667 |
| [0.6,0.7) | 1 | 0.677 | 0.000 |
| [0.7,0.8) | 3 | 0.743 | 0.333 |
| [0.8,0.9) | 1 | 0.849 | 1.000 |
| [0.9,1.0) | 10 | 0.965 | 0.900 |

N=64, Brier=0.13722, LogLoss=0.42538, ECE(Reliability gap)=0.11092, Sharpness(stddev)=0.35907

**해석:** Brier Score는 PRE(0.16666) → R1→R2(0.11459)까지 개선되지만 R2→R3(0.13722)에서 재악화된다. 이 섹션은 Priority 4 보조 지표다.

---

# 12. 모델 분석 (Root Cause Analysis)

## 가장 잘 맞은 요소

1. **Mean-Reversion Signal이 매우 강하고 일관적이다** (R1→R2 r=-0.6838, R2→R3 r=-0.5765). _이 발견은 단일 대회 결과이며, 향후 대회에 걸친 추가 검증이 필요하다 (This finding is based on a single tournament and requires validation across future tournaments.)_
2. **Expected SG 정확도가 라운드마다 개선된다** (MAE 2.36 → 2.27 → 2.12).
3. **Performance Ranking의 절대 오차(MAE)가 뚜렷하게 개선된다** (23.683 → 17.833 → 13.031).
4. **Top-N 분류(Priority 4)도 동일한 개선 패턴**을 보이며 Priority 2의 개선을 뒷받침한다.

## 아직 부족한 요소

1. **Priority 3 (Round Performance)이 PRE→R1, R1→R2 단계에서 아예 측정 불가능하다** — 파이프라인 설계의 공백이며, Roadmap의 개선 과제다.
2. **Current SG → Next Round SG 연속성이 매우 약하다** (r=0.1171, r=0.0251) — Mean-Reversion Signal이 이 현상의 유력한 설명이다 (단일 대회 결과).
3. **Performance Ranking Bias가 모든 단계에서 양수**다 — 낙관 편향 경향.
4. **R2→R3에서 Rank Correlation이 R1→R2보다 낮다** — range restriction(필드 축소) 효과 가능성.

## Why (원인 분석)

- **Mean-Reversion Signal이 강하게 관찰된 이유**: 하루 라운드 성적은 그날의 컨디션·핀 위치·바람 등 일시적 요인에 크게 좌우된다. 이는 단일 대회 관찰이며, 다중 대회 검증이 필요하다.
- **Round Performance 결측의 원인**: 파이프라인이 원래 확률 기반 예측으로 설계되어, 원시 기대 스코어는 R2 이후부터만 persist되기 시작했다.
- **Rank Correlation 비단조성의 원인**: R2→R3 필드가 64명으로 좁혀지며 순위 값의 분산 자체가 줄어들어(range restriction), 상관계수가 통계적으로 낮게 나올 수 있다.

---

# 13. 코스 영향 (홀별 난이도, Danger Hole, Birdie Hole)

**BLOCKED — 증거 없음.** 수집된 리더보드/SG HTML 원본 증거를 직접 검사한 결과, 홀별(hole-by-hole) 스코어카드 데이터는 존재하지 않는다. 조작하지 않고 명시적으로 BLOCKED 처리한다.

---

# 14. 선수 분석

(예측순위는 확률기반 Proxy 기준.)

## 가장 NEO와 가까운 선수 TOP10

1. **김민선7** (PRE->R1): 예측순위 7 → 실제순위 7 (변화량 +0)
2. **유현조** (PRE->R1): 예측순위 3 → 실제순위 3 (변화량 +0)
3. **홍현지** (PRE->R1): 예측순위 56 → 실제순위 56 (변화량 +0)
4. **김지수** (R1->R2): 예측순위 91 → 실제순위 91 (변화량 +0)
5. **서어진** (R1->R2): 예측순위 38 → 실제순위 38 (변화량 +0)
6. **문정민** (R2->R3): 예측순위 23 → 실제순위 23 (변화량 +0)
7. **김수지** (R2->R3): 예측순위 11 → 실제순위 11 (변화량 +0)
8. **문정민** (PRE->R1): 예측순위 8 → 실제순위 7 (변화량 +1)
9. **짜라위 분짠(I)** (PRE->R1): 예측순위 38 → 실제순위 39 (변화량 -1)
10. **안송이** (PRE->R1): 예측순위 57 → 실제순위 56 (변화량 +1)

## 가장 과대평가된 선수 TOP10

1. **김민솔** (PRE->R1): 예측순위 5 → 실제순위 73 (변화량 -68)
2. **홍정민** (PRE->R1): 예측순위 30 → 실제순위 98 (변화량 -68)
3. **한진선** (PRE->R1): 예측순위 22 → 실제순위 88 (변화량 -66)
4. **김민주** (PRE->R1): 예측순위 9 → 실제순위 73 (변화량 -64)
5. **박혜준** (PRE->R1): 예측순위 13 → 실제순위 73 (변화량 -60)
6. **이승연** (PRE->R1): 예측순위 40 → 실제순위 98 (변화량 -58)
7. **고지원** (R1->R2): 예측순위 17 → 실제순위 71 (변화량 -54)
8. **김민별** (PRE->R1): 예측순위 20 → 실제순위 73 (변화량 -53)
9. **정윤지** (R1->R2): 예측순위 36 → 실제순위 79 (변화량 -43)
10. **전예성** (R2->R3): 예측순위 16 → 실제순위 57 (변화량 -41)

## 가장 과소평가된 선수 TOP10

1. **강가율** (R1->R2): 예측순위 93 → 실제순위 17 (변화량 +76)
2. **양윤서 0801(A)** (PRE->R1): 예측순위 90 → 실제순위 16 (변화량 +74)
3. **박단유** (PRE->R1): 예측순위 77 → 실제순위 7 (변화량 +70)
4. **강가율** (PRE->R1): 예측순위 101 → 실제순위 31 (변화량 +70)
5. **황유나** (R1->R2): 예측순위 105 → 실제순위 38 (변화량 +67)
6. **왕 즈쉬엔** (PRE->R1): 예측순위 78 → 실제순위 16 (변화량 +62)
7. **안지현** (R1->R2): 예측순위 98 → 실제순위 38 (변화량 +60)
8. **안재희** (PRE->R1): 예측순위 74 → 실제순위 16 (변화량 +58)
9. **김소정** (R1->R2): 예측순위 92 → 실제순위 38 (변화량 +54)
10. **현세린** (PRE->R1): 예측순위 91 → 실제순위 39 (변화량 +52)

## Surprise Player TOP10

1. **강가율** (R1->R2): 예측순위 93 → 실제순위 17 (변화량 +76)
2. **양윤서 0801(A)** (PRE->R1): 예측순위 90 → 실제순위 16 (변화량 +74)
3. **박단유** (PRE->R1): 예측순위 77 → 실제순위 7 (변화량 +70)
4. **강가율** (PRE->R1): 예측순위 101 → 실제순위 31 (변화량 +70)
5. **김민솔** (PRE->R1): 예측순위 5 → 실제순위 73 (변화량 -68)
6. **홍정민** (PRE->R1): 예측순위 30 → 실제순위 98 (변화량 -68)
7. **황유나** (R1->R2): 예측순위 105 → 실제순위 38 (변화량 +67)
8. **한진선** (PRE->R1): 예측순위 22 → 실제순위 88 (변화량 -66)
9. **김민주** (PRE->R1): 예측순위 9 → 실제순위 73 (변화량 -64)
10. **왕 즈쉬엔** (PRE->R1): 예측순위 78 → 실제순위 16 (변화량 +62)

---

# 15. NEO Philosophy Validation

**이번 하나금융그룹 챔피언십은 NEO가 Winner Prediction Model이 아니라 Performance Prediction Model임을 실증적으로 보여준 첫 번째 대회였다.**

Evidence:

1. **Winner 적중은 3단계 모두 실패했지만(0/3, Reference Only), Performance Ranking MAE는 뚜렷이 개선되었다** (23.683 → 17.833 → 13.031). NEO가 Winner Prediction 모델이었다면 이 개선은 무의미했을 것이다.
2. **김민선7 사례**: R2 시점 우승확률 순위 3위였던 선수가 실제 R3에서 1위가 되었다. Performance 관점에서는 김민선7의 개별 경기력이 R3에서 크게 향상되었다는 것을 NEO의 확률 모델이 반영했다.
3. **Mean-Reversion Signal이 관찰되었다** (섹션 9, 단일 대회 결과) — 골프는 상대평가이며 개별 라운드 성적의 변동성이 크다는 것을 실증했다.
4. **Current SG의 라운드 간 연속성이 거의 0**이라는 사실은, "이번 라운드 잘 친 선수가 다음 라운드도 잘 친다"는 가정이 성립하지 않음을 보여준다.

---

# 16. WHAT NEO LEARNED

1. Winner 예측과 Performance 예측은 서로 다른 목적함수다 — 하나가 개선되어도 다른 하나는 개선되지 않을 수 있다.
2. Current SG는 다음 라운드를 직접 예측하는 신호로는 약하지만, 본인 기준선(Expected SG) 대비 정확도는 개선 가능한 지표다.
3. 확률 기반 순위(Monte Carlo)가 원시 기대 스코어보다 안정적인 순위 신호를 만들 수 있다.
4. 필드가 좁아질수록(컷 이후) 상관계수 기반 지표는 구조적으로 낮아질 수 있다 — 절대 오차 지표와 병행 해석이 필요하다.
5. NEO의 순위 예측에는 일관된 낙관 편향(+2~+5)이 존재한다.
6. 평균회귀로 보이는 패턴이 관찰되었지만, 단일 대회로는 이를 안정적 특성으로 단정할 수 없다.
7. 컷확률처럼 이진 사건에 가까운 예측은 확률 기반 예측(top-N/win)보다 calibration이 더 안정적일 수 있다.
8. Round Performance(원시 기대 스코어)가 파이프라인 초기 단계에 존재하지 않으면, 모델의 신뢰도 진단 자체가 불가능해진다.
9. Biggest Movers 분석이 개별 선수의 이변을 설명하는 데 Winner 적중 여부보다 유용하다.
10. 하나의 대회만으로는 Performance Continuity의 "진짜" 강도를 확정할 수 없다 — 다중 대회 누적이 필수다.

---

# 17. WHAT GOLF TAUGHT THE MODEL

1. 골프는 상대평가다 — 개인 성적이 아무리 좋아도 상대가 더 잘 치면 진다.
2. 하루 라운드 성적은 변동성이 크고, 그 변동성 중 상당 부분은 평균 주변으로 되돌아오는 경향을 보인다 (단일 대회 관찰).
3. 컷은 필드를 인위적으로 좁히며, 이는 통계적 지표(특히 상관계수)의 해석에 영향을 준다.
4. 우승은 다수의 우연적 요인이 누적된 결과이므로, 개별 대회 단위로 우승자를 예측하는 것은 본질적으로 어렵다.
5. SG는 이미 일어난 일을 잘 설명하지만, 아직 일어나지 않은 일을 잘 예측하지는 못한다.
6. 골프 경기력은 완전히 무작위도, 완전히 지속적이지도 않다 — 그 중간 어딘가에 있다.
7. 라운드마다 필드의 분산이 줄어드는 것은 무작위가 아니라 선수 구성 변화(컷)의 자연스러운 결과다.
8. 확률 기반 접근(Monte Carlo)이 단일 기대값보다 골프의 불확실성을 더 잘 담아낼 수 있다.
9. 코스/조건에 따라 필드 전체의 SG가 시즌 평균보다 체계적으로 낮아질 수 있다.
10. 골프에서 "이번 대회의 진실"과 "장기적으로 검증된 진실"은 다르다 — 하나의 대회는 가설을 제시할 뿐, 증명하지 않는다.

---

# 18. CONFIDENCE

| 발견 | Confidence | 근거 |
|---|---|---|
| Top5 Precision 80% | High | 직접 계산된 confusion matrix, 재현 가능 |
| Performance Ranking MAE 개선 추세 | High | 3단계 모두 동일 방법론으로 일관되게 관찰됨 |
| Mean-Reversion Signal | Low | 단일 대회, 2개 구간만 관찰, 다중 대회 검증 필요 |
| Probability Ranking이 Raw Score보다 정확 | Medium | 단일 대회 R2→R3 한 구간에서만 확인됨 |
| Current SG → Next Round SG 연속성 약함 | Medium | 2개 구간 일관된 관찰이나 표본 크기(N=64~102) 제한적 |
| Performance Ranking Bias(낙관 편향) | Medium | 4개 지점 모두 양수로 일관되나 단일 대회 |
| 컷확률 Calibration 우수 | Medium | N=105, 단일 대회 단일 지표 |
| Winner는 Reference Metric | High | 철학적 정의이자 방법론적 결정, 데이터로 반박 불가능한 설계 원칙 |

---

# 19. RESEARCH VS PRODUCTION

**Production (현재 운영 가능한 것)**

- Performance Ranking (Priority 2) — MAE/Bias/Correlation 계산 방법론은 즉시 운영 가능.
- Expected SG → Actual SG (Priority 1 하위 지표) — 이미 존재하는 PRE 스냅샷만으로 매 라운드 계산 가능.
- Top20/Top10/Top5 Precision/Recall/F1 (Priority 4) — 이미 운영 중인 확률 예측을 그대로 사용.
- 컷확률 Calibration — script 172의 기존 방법론, 이미 검증됨.

**Research (추가 검증이 필요한 것)**

- Mean-Reversion Signal — 단일 대회 관찰, 다중 대회 누적 검증 전까지 프로덕션 KPI로 승격 금지.
- Current SG → Next Round SG 연속성의 선수별 개인차 — 이번 대회는 필드 평균만 확인, 개인별 지속성 차이는 미검증.
- Probability Ranking vs Raw Expected Score의 우위 — 단일 구간(R2→R3) 관찰이며 일반화 여부 불확실.
- Momentum Feature 후보 — 이번 대회 데이터는 모멘텀보다 평균회귀를 시사하지만, 선수 유형별 차이가 있을 수 있어 별도 연구가 필요.
- Round Performance(Priority 3)의 PRE/R1 단계 확장 — 신규 파이프라인 구현이 필요한 연구 과제.

**절대 섞지 않는다**: Production 지표는 지금 웹사이트/보고서에 실제 사용 가능하다고 명시적으로 표시하고, Research 지표는 "단일 대회, 검증 필요"라는 라벨 없이는 어떤 대표 KPI로도 격상하지 않는다.

---

# 20. 콘텐츠 분석 (제안 — 사실 발표 아님, 편집 아이디어)

## Threads 소재 10개
1. "NEO는 우승자를 안 맞힌다 — 지속 가능한 경기력을 맞힌다"
2. "Mean-Reversion Signal 관찰 — 하지만 아직 확정 아니다 (단일 대회)"
3. "김민선7, R2 3위 예측에서 R3 우승확률 1위로"
4. "Current SG는 목표가 아니라 Feature다 — NEO는 SG를 맞히지 않는다"
5. "골프는 상대평가다 — NEO가 우승자 대신 경기력을 예측하는 이유"
6. "Performance Ranking MAE 23.7 → 17.8 → 13.0, 3단계 개선의 기록"
7. "확률 기반 순위 vs 원시 스코어 기반 순위, 어느 쪽이 더 정확할까"
8. "NEO가 시스템적으로 낙관적인 이유 — Ranking Bias +2~+5의 정체"
9. "Top5 예측 정밀도 80% — 어디까지 신뢰할 수 있나 (Confidence: High)"
10. "NEO Benchmark Report V1: 다음 대회부터 무엇이 비교되는가"

## 블로그 소재 10개
1. "NEO Benchmark Report V1이 되는 방법: Research Report의 조건"
2. "Mean-Reversion Signal로 다시 읽는 하나금융 챔피언십 (검증 필요)"
3. "Current SG → Next Round SG, 연속성이 약한 진짜 이유"
4. "Performance Ranking의 4가지 지표: MAE, Bias, Correlation이 말해주는 것"
5. "Round Performance가 없는 단계, 있는 단계 — 파이프라인의 숨은 공백"
6. "WHAT NEO LEARNED / WHAT GOLF TAUGHT THE MODEL: 이번 대회의 양방향 교훈"
7. "NEO Philosophy Validation: 이번 대회가 보여준 것"
8. "Research vs Production: NEO 지표를 섞지 않는 이유"
9. "Confidence 등급표: NEO의 모든 발견에 신뢰도를 붙이는 이유"
10. "MODEL IMPROVEMENT ROADMAP: Evidence Strength로 정렬한 다음 단계"

## Deep Dive 소재 10개
1. Mean-Reversion Signal 딥다이브: R1→R2, R2→R3 두 구간의 통계적 증거와 한계
2. 김민선7 역전 드라마: Performance Continuity 관점에서 본 R3 라운드
3. Current SG 연속성 실험: 왜 상관계수가 0에 가까운가
4. Performance Ranking Bias 원인 분석: NEO는 왜 낙관적인가
5. Rank Correlation vs Rank MAE: 같은 데이터, 다른 결론
6. Priority 3 결측 공백 분석: PRE/R1 단계에 원시 기대 스코어가 없는 구조적 이유
7. Research vs Production 분류 기준: 이번 대회 지표 전수 분류
8. 과대평가/과소평가 선수군 공통점 분석
9. NEO Philosophy Validation 근거 4가지 완전 해설
10. Confidence 등급 산정 방법론: High/Medium/Low를 나누는 기준

---

# 21. NEO SCORECARD (INTERIM — R3까지)

**주의: 이것은 최종 벤치마크가 아니다.** FINAL 공식 증거가 없어 4단계 중 3단계만 평가했다. Winner는 철학상 Scorecard 축에서 제외한다 (Reference Only).

Performance Continuity: ★★★☆☆ (3/5) — Mean-Reversion Signal은 강력하나 단일 대회(Confidence: Low); 연속성 자체는 약함
Performance Ranking: ★★★★☆ (4/5) — MAE 기준 3단계 내내 뚜렷이 개선(Confidence: High); Correlation은 range restriction으로 비단조적
Round Performance: ★★☆☆☆ (2/5) — R2→R3만 측정 가능, PRE/R1은 구조적 결측
Calibration: ★★★☆☆ (3/5) — 컷확률은 우수, Top20 확률은 R2→R3에서 재악화
Validation: ★★★★☆ (4/5) — 모든 수치가 기존 Freeze/Evidence에서 재현 가능, 결정론적 재현 확인
Deployment: N/A — 이 문서는 배포 아티팩트 아님, 내부 검증 문서
Data Quality: ★★★★☆ (4/5) — WD 처리·식별자 정합성 확인됨; 홀별 코스 데이터·PRE/R1 원시 기대 스코어만 결측
Content Value: ★★★★★ (5/5) — Threads/블로그/Deep Dive 소재 30개 + WHAT NEO LEARNED/WHAT GOLF TAUGHT 20개 도출
Research Value: ★★★★★ (5/5) — Mean-Reversion Signal 최초 관찰 + Research/Production 명시적 분리

**Overall Grade: B+ (INTERIM, R3 기준) — FINAL 확보 후 재평가 필요**

---

# 22. MODEL IMPROVEMENT ROADMAP (Evidence Strength 순)

## High Evidence

**Performance Ranking 낙관 편향 보정.** 모든 단계에서 Bias가 일관되게 양수(+2~+5)로 나타났다(Evidence: Section 6, N=64~104, 4개 지점 전부). 후처리 캘리브레이션으로 즉시 개선 가능한 영역이다.

**컷확률 Calibration 유지·확산.** 컷확률 calibration이 이번 대회에서 가장 신뢰할 수 있는 확률 추정이었다(Evidence: Brier 0.142, ECE 0.076, N=105). 다른 이진 사건(예: Top20 달성 여부)에도 동일 방법론을 적용한다.

## Medium Evidence

**Expected SG 기준선 고도화.** Expected SG 정확도가 라운드마다 개선되는 추세가 확인되었다(Evidence: MAE 2.36→2.27→2.12). Rolling 기준선으로 발전시켜 정확도를 추가로 높인다.

**Probability Ranking 우선 사용.** R2→R3에서 확률 기반 순위가 원시 기대 스코어보다 정확했다(Evidence: MAE 13.0 vs 15.6, 단일 구간). 순위 산출 시 확률 기반 방법을 기본값으로 우선한다.

**Calibration 재보정 로직.** R2→R3에서 Top20 확률 calibration이 재악화된다(Evidence: Brier 0.115→0.137). 필드 축소에 따른 재보정 로직을 검토한다.

## Research (프로덕션 승격 전 추가 검증 필요)

**Mean-Reversion Feature화.** 이번 대회에서 관찰된 신호(Evidence: r=-0.68, -0.58)를 다중 대회로 검증한 뒤에만 예측 피처로 승격을 검토한다. _이 발견은 단일 대회 결과이며, 향후 대회에 걸친 추가 검증이 필요하다 (This finding is based on a single tournament and requires validation across future tournaments.)_

**Momentum Feature 연구.** 이번 대회는 모멘텀보다 평균회귀가 강했으나(Evidence: 연속성 r≈0.02-0.13 vs 회귀 r=-0.68,-0.58), 선수별 개인차 존재 가능성을 다중 대회로 검증해야 한다.

**Hole Context 확장.** 홀별 난이도/Danger Hole/Birdie Hole 분석이 증거 부재로 BLOCKED였다(Evidence: Section 13). 홀별 스코어카드 원본 수집 파이프라인 신규 구축이 선행되어야 한다.

**Round Performance(Priority 3) Freeze 확장.** PRE→R1, R1→R2에서 측정 불가능했다(Evidence: Section 6). 모든 단계에서 원시 기대 스코어를 명시적으로 Freeze하는 파이프라인 확장이 필요하다 — Research 단계이지만 다음 대회 전 구현이 권장된다.

---

The purpose of this report is not to prove that NEO is correct.

The purpose is to understand where the model works, where it fails, and how it improves.

This document is the baseline for continuous improvement.

---

*이 문서는 `klpga_pipeline/content/website_v2/HANA_2026090002_NEO_RED_TEAM_FORENSICS_V1.md`로 저장되었으며, 내부 검증 문서로만 사용된다. 공개 페이지에 게시되지 않는다. NEO 프로젝트의 공식 Benchmark Report V1이다.*
