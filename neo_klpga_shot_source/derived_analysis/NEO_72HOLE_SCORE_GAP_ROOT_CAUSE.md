# NEO 72-Hole Score Gap Root Cause — 유해란 / 이재윤 / 박서현

Game 2026100005. Steps 1–4 (partial — see note at bottom on truncated instructions).

## Step 1 — OFFICIAL BASELINE (locked, unchanged)

| | 유해란 | 이재윤 | 박서현 |
|---|---|---|---|
| 순위 | 1위 | 27위 | 61위 |
| 합계 | 284 (-4) | 297 (+9) | 314 (+26) |
| R1–R4 | 73/69/73/69 | 76/75/74/72 | 75/78/81/80 |

Pairwise gap: 유해란↔이재윤 13타, 이재윤↔박서현 17타, 유해란↔박서현 30타.

## Step 2 — 72-hole score-gap map (re-verified from RAW, all 72 hole-plays present for all 3 players, 0 missing)

| Pair | net gap | ALL TIED | A GAIN | B GAIN | magnitude: 0 / 1 / 2 / 3+ |
|---|---|---|---|---|---|
| 유해란–이재윤 | 13 | 36 | 24 | 12 | 36 / 33 / 3 / 0 |
| 이재윤–박서현 | 17 | 43 | 20 | 9 | 43 / 24 / 4 / 1 |
| 유해란–박서현 | 30 | 33 | 31 | 8 | 33 / 31 / 7 / 1 |

**질문: 30타 차이가 72홀 전체에서 조금씩 발생했는가, 소수 hole-play에 집중됐는가?**
**답: 둘 다 — 60%는 상위 10개 hole-play에 집중됐지만(아래 §3), 나머지 40%는 나머지 62개 hole-play에 걸쳐 분산됐다.** 더 작은 두 격차(유해란–이재윤 13타, 이재윤–박서현 17타)는 오히려 훨씬 더 소수에 집중(top10이 92~94%)됐다는 점이 실제로 더 눈에 띄는 대조다 — 가장 큰 격차(30타)가 세 쌍 중 가장 "덜 집중된" 격차라는 것은 직관과 반대되는 실제 결과.

## Step 3 — Score-gap concentration (top-N as % of net gap)

| Pair | Top1 | Top3 | Top5 | Top10 | exact ties |
|---|---|---|---|---|---|
| 유해란–이재윤 (13) | 15.4% | 38.5% | 53.8% | **92.3%** | 36/72 |
| 이재윤–박서현 (17) | 17.6% | 41.2% | 64.7% | **94.1%** | 43/72 |
| 유해란–박서현 (30) | 10.0% | 23.3% | 36.7% | **60.0%** | 33/72 |

**기존 발견 재검증 결과: 유해란 vs 박서현 30타 격차, 33개 완전 동타 홀, top10 hole-play가 격차의 60.0% 설명 — RAW에서 독립적으로 정확히 재확인됨 (오차 없음).**

이는 확인되었듯 중요한 사실이다: **"박서현이 72홀 내내 유해란보다 계속 못 친 것이 아니다"** — 33/72홀(46%)은 완전히 동타였고, 31/72홀에서만 유해란이 더 나았다(8홀은 오히려 박서현이 더 나음). 단, 아직 원인은 아니다.

Top-10 hole-plays (유해란–박서현, 크기순):

| Round | Hole | Par | 유해란 | 박서현 | diff |
|---|---|---|---|---|---|
| R3 | H8 | 4 | 4 | 7 | −3 |
| R1 | H3 | 4 | 4 | 6 | −2 |
| R1 | H8 | 4 | 3 | 5 | −2 |
| R2 | H11 | 3 | 2 | 4 | −2 |
| R4 | H4 | 5 | 4 | 6 | −2 |
| R4 | H9 | 4 | 4 | 6 | −2 |
| R4 | H10 | 5 | 4 | 6 | −2 |
| R1 | H2 | 3 | 2 | 3 | −1 |
| R1 | H6 | 4 | 4 | 5 | −1 |
| R1 | H13 | 4 | 4 | 5 | −1 |

(Shot-chain dissection of these 10 hole-plays is a later step, not yet done.)

## Step 4 — Round environment adjustment (partial)

Field round averages re-verified directly from RAW (sum of real strokes across all 18 holes, only player-rounds with complete 18-hole data, i.e. the same 331 player-rounds already used throughout this project):

| Round | n (complete player-rounds) | Field avg |
|---|---|---|
| R1 | 107 | 76.729 |
| R2 | 102 | 76.029 |
| R3 | 61 | 74.311 |
| R4 | 61 | 73.689 |

Matches the given reference (≈76.75/76.05/74.32/73.70) closely — **re-confirmed: the course/round scoring environment got easier each round, field-wide, independent of any one player.**

FIELD-RELATIVE ROUND PERFORMANCE (player raw round score − field round average, **not SG**, provisional per instruction):

| | R1 | R2 | R3 | R4 | total |
|---|---|---|---|---|---|
| 유해란 | −3.73 | **−7.03** | −1.31 | −4.69 | −16.76 |
| 이재윤 | −0.73 | −1.03 | −0.31 | −1.69 | −3.76 |
| 박서현 | **−1.73** | +1.97 | **+6.69** | +6.31 | +13.24 |

**핵심 결과:**
- **이재윤의 76→75→74→72 raw 추세는 field-relative로 보면 뚜렷한 개선 추세가 아니다** — R1 −0.73, R2 −1.03, R3 −0.31(오히려 가장 나쁜 상대 라운드), R4 −1.69. 4라운드 내내 field보다 꾸준히 조금 나은 수준(−0.3~−1.7)이었을 뿐, "라운드를 거듭할수록 나아졌다"는 해석은 **field 전체가 쉬워진 효과와 뒤섞여 있었다는 것이 확인됨** — 사용자가 경고한 그대로.
- **박서현의 75→78→81→80 raw 추세는 field-relative로 보면 더 뚜렷해진다, 사라지지 않는다.** R1은 field보다 1.73타 더 좋았다(상위권 선수 수준의 하루였다는 뜻) — 그런데 field가 점점 쉬워지는 동안(R1→R4 field avg가 3타 가까이 낮아짐) 그녀는 반대로 점점 field 대비 나빠져 R3·R4에는 field보다 6타 이상 나빴다. **이것은 course/round 환경 변화로 설명되지 않는 실제 선수 변화다** — 오히려 환경 보정을 하면 하락폭이 raw 점수 차이보다 더 커 보인다.
- 유해란은 전 라운드 field 대비 뚜렷한 우위, R2가 field-relative 기준 최고 라운드(−7.03).

**PLAYER CHANGE vs COURSE/ROUND ENVIRONMENT CHANGE 분리 결과(1차):** 이재윤 쪽은 상당 부분이 환경 변화로 설명되고, 박서현 쪽은 환경 변화로 설명되지 않는 실제 하락이다. 아직 가설 수준 — 다음 단계(hole-level/shot-chain)에서 추가 검증 필요.

---

**참고:** 이 메시지의 2번째 지시가 "4. ROUND ENVIRONMENT ADJUSTMENT" 섹션 중간("박서현의 75→78" 부분)에서 다시 끊겼습니다. 위 내용은 지시된 범위 안에서 실행 가능한 부분을 모두 완료한 것이며, 이후 단계(5번 이후)는 아직 지시받지 못했습니다.
