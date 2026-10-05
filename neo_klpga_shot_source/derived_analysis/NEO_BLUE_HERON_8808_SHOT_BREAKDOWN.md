블루헤런에서 퍼팅을 제외한 후속샷 8,808회는 실제로 무엇이었는가?

**데이터**: 2026 하이트진로 챔피언십 RAW Shot Tracker (`klpga_player_shot`, game_code 2026100005) 24,993행 전수. 클럽 종류는 RAW에 없으므로 추정하지 않았다 — 모든 분류는 Shot Tracker 자체의 `state_code`(직전 샷의 종료 상태 = 이번 샷의 시작 lie, 이번 샷의 종료 상태 = 끝 lie)만 사용했다.

**기준 재확인**: 전체 24,993 = 티샷 5,958 + 퍼팅 전 후속샷 8,808 + 퍼팅 10,227. 이번 작업은 8,808만을 전수 분해한다.

---

## 1. STARTING LIE 분해 (8,808건, 8분류)

| CATEGORY | COUNT | % OF 8,808 |
|---|---|---|
| FAIRWAY START | 3,879 | 44.04% |
| ROUGH START | 3,431 | 38.95% |
| BUNKER START | 152 | 1.73% |
| GREENSIDE BUNKER START | 259 | 2.94% |
| FRINGE START | 737 | 8.37% |
| PENALTY_AREA START | 139 | 1.58% |
| LOST_BALL/PENALTY_STROKE/OB 후 재개 START | 211 | 2.40% |
| OTHER | 0 | 0.00% |
| **합계** | **8,808** | **100.00%** |

(시작 lie = 직전 샷의 결과 state. 각 state의 Shot Tracker 원 분류: FAIRWAY=state 1, ROUGH=state 2, BUNKER=state 6, GREENSIDE_BUNKER=state 9, FRINGE=state 12, PENALTY_AREA=state 5, OB=state 4/LOST_BALL=state 7/PENALTY_STROKE=state 8를 "LOST_BALL/PENALTY 후 재개"로 묶었다. GREEN(3)·HOLED(10)은 정의상 이 8,808에 시작 lie로 나타날 수 없음 — 실제로 0건, 구조적 정합성 확인됨.)

---

## 2. SHOT ROLE 분해 (8,808건, 6분류)

**분류 규칙 (결과/점수 미참조, 시작·종료 lie와 par만 사용)**:
- FRINGE 시작 → SHORT GAME
- PENALTY_AREA 또는 LOST_BALL/PENALTY_STROKE/OB 시작 → PENALTY/RESTART
- ROUGH, BUNKER, GREENSIDE_BUNKER 시작 → RECOVERY
- FAIRWAY 시작 & 종료 lie가 GREEN/FRINGE → NORMAL APPROACH
- FAIRWAY 시작 & 종료 lie가 GREEN/FRINGE 아님 & 파5 → ADVANCE/LAY-UP
- FAIRWAY 시작 & 종료 lie가 GREEN/FRINGE 아님 & 파3/4 → **OTHER/UNRESOLVED** (레이업이라 부를 근거도, 정상 어프로치라 부를 근거도 없음 — 짧은 홀에서 페어웨이를 치고도 그린에 못 올린 샷으로, 억지 분류하지 않았다)

**주의(용어 중복 공개)**: 사용자 요청의 B(RECOVERY) 예시에는 "greenside bunker → green"이 포함되어 있고, E(SHORT GAME) 설명에도 GREENSIDE_BUNKER가 포함되어 있어 원 정의 자체가 중복된다. 본 분석은 B의 구체 예시를 따라 GREENSIDE_BUNKER 시작 샷 전부를 RECOVERY로 분류했고, SHORT GAME은 FRINGE 시작 샷으로만 한정했다(임의 거리 기준 생성 없음). "그린 근처 ROUGH"를 ROUGH에서 분리할 근거(검증된 야드 환산)가 없어 분리하지 않고 ROUGH는 전부 RECOVERY에 포함했다.

| SHOT ROLE | COUNT | % |
|---|---|---|
| NORMAL APPROACH | 2,466 | 28.00% |
| ADVANCE / LAY-UP | 938 | 10.65% |
| RECOVERY | 3,842 | 43.62% |
| SHORT GAME | 737 | 8.37% |
| PENALTY / RESTART | 350 | 3.97% |
| OTHER / UNRESOLVED | 475 | 5.39% |
| **합계** | **8,808** | **100.00%** |

OTHER/UNRESOLVED 475건은 전수 확인 결과 전부 "FAIRWAY 시작, 파3/4, 종료 lie가 GREEN/FRINGE 아님"인 단일 케이스였다(예: 김민별 R1H17 FAIRWAY→ROUGH, 파4). 다른 미분류 사유는 없다.

---

## 3. SHOT NUMBER 분해 (8,808건)

| SHOT # | COUNT | % |
|---|---|---|
| #2 | 5,034 | 57.15% |
| #3 | 2,983 | 33.87% |
| #4 | 640 | 7.27% |
| #5 | 117 | 1.33% |
| #6 | 28 | 0.32% |
| #7+ | 6 | 0.07% |
| **합계** | **8,808** | **100.00%** |

**shot# × 시작/종료 lie × GIR × 결과**:

| shot# | n | 주요 시작 lie(상위3) | 주요 종료 lie(상위3) | GIR% | Par+% |
|---|---|---|---|---|---|
| #2 | 5,034 | FAIRWAY 2,802 / ROUGH 1,868 / BUNKER 129 | GREEN 2,048 / ROUGH 1,244 / FAIRWAY 987 | 53.36% | 71.69% |
| #3 | 2,983 | ROUGH 1,244 / FAIRWAY 987 / FRINGE 392 | GREEN 2,317 / ROUGH 262 / FRINGE 197 | 31.08% | 61.28% |
| #4 | 640 | ROUGH 262 / FRINGE 199 / FAIRWAY 73 | GREEN 513 / ROUGH 43 / FRINGE 27 | 0.31% | 34.06% |
| #5 | 117 | ROUGH 43 / FRINGE 34 / PENALTY/RESTART 17 | GREEN 84 / FRINGE 12 / ROUGH 11 | 5.13% | 2.56% |
| #6 | 28 | FRINGE 12 / ROUGH 11 / GRNSD BUNKER 2 | GREEN 24 / ROUGH 3 / FRINGE 1 | 0.00% | 0.00% |
| #7+ | 6 | FRINGE 3 / ROUGH 3 | GREEN 4 / FRINGE 2 | 0.00% | 0.00% |

(shot#4 이후 GIR%가 거의 0%인 것은 정의상 당연하다 — GIR은 파-2타 이내 그린 도달을 요구하므로, 파4에서 shot#4, 파5에서 shot#5 이상은 이미 GIR 기준을 초과한 상태다. 이건 "회복력이 없다"는 뜻이 아니라 GIR 정의 자체의 산술적 귀결이다.)

### PAR별 8,808 발생 횟수

| | n (8,808 중) |
|---|---|
| **PAR3** 소계 | 526 |
| PAR4 소계 | 5,132 |
| PAR5 소계 | 3,150 |
| **합계** | **8,808** |

**PAR3** (526건, 전부 "티샷 이후 비퍼팅 후속샷"): shot#2=400, shot#3=110, shot#4=13, shot#5=2, shot#6=1
**PAR4** (5,132건): shot#2=3,310 / shot#3+=1,822
**PAR5** (3,150건): shot#2=1,324 / shot#3=1,324 / shot#4+=502

**파5의 shot#2를 전부 "어프로치"라 부르지 않은 이유**: 파5 shot#2(1,324건)와 shot#3(1,324건)이 정확히 같은 건수다 — 즉 파5에서 비퍼팅 shot#2가 있는 거의 모든 경우, 그 다음에도 비퍼팅 shot#3이 이어진다(2절의 ADVANCE/LAY-UP 938건이 주로 여기서 나온다). 파5 shot#2는 그린을 직접 공략하는 경우도 있지만(그 경우 종료 lie가 GREEN/FRINGE → NORMAL APPROACH로 분류됨), 상당수는 레이업이다.

---

## 4. 핵심 시작 lie → 종료 lie 실측 횟수

| TRANSITION | COUNT |
|---|---|
| FAIRWAY → GREEN | 2,159 |
| ROUGH → GREEN | 1,777 |
| BUNKER → GREEN | 36 |
| GREENSIDE_BUNKER → GREEN | 203 |
| FRINGE → GREEN 또는 HOLED | 731 |
| ROUGH → GREEN 또는 HOLED | 1,798 |

---

## 5. FW HIT 후 첫 후속샷 vs FW MISS 후 첫 후속샷 (shot#2, 파4/5만, n=4,634)

이것은 기존 FW MISS 분석의 확장이 아니라, 8,808 중 shot#2(5,034건)의 절반 이상을 차지하는 파4/5 "첫 후속샷"의 정체를 설명하기 위한 집계다.

| | FW HIT 후(n=2,802) | FW MISS 후(n=1,832) |
|---|---|---|
| → GREEN | 1,309 (46.72%) | 452 (24.67%) |
| → ROUGH | 584 (20.84%) | 632 (34.50%) |
| → BUNKER(BUNKER+GRNSD) | 112 (4.00%) | 87 (4.75%) |
| → FRINGE | 224 (7.99%) | 146 (7.97%) |
| → PENALTY(PENALTY_AREA+LOST_BALL/PENALTY_STROKE/OB) | 30 (1.07%) | 71 (3.88%) |
| → FAIRWAY(레이업성 이동 포함) | 543 (19.38%) | 444 (24.24%) |
| **GIR %** | **68.88%** | **41.27%** |

---

## 6. 전체 TRANSITION MATRIX (45개 start→end 조합, 8,808건 전수)

SHOT RESULT(이 샷이 어디로 갔는가)와 HOLE RESULT(그 홀이 결국 몇 타였는가)를 분리해서 제시한다 — 예를 들어 ROUGH→GREEN(그린에 올렸다는 샷 결과)이어도 Bogey+가 37.08%나 되는 것은 퍼팅에서 더 비싸졌기 때문이며, 이 샷 자체를 "나쁜 샷"이라 부르지 않는다. 상위 20개(건수 기준, 전체 45개는 `blue_heron_8808_transition_matrix.csv`):

| START | END | COUNT | % | 평균 홀 투파 | Par+% | Bogey+% | Double+% |
|---|---|---|---|---|---|---|---|
| FAIRWAY | GREEN | 2,159 | 24.51% | -0.036 | 87.82% | 12.18% | 1.48% |
| ROUGH | GREEN | 1,777 | 20.17% | 0.398 | 62.92% | 37.08% | 5.46% |
| ROUGH | ROUGH | 792 | 8.99% | 0.706 | 45.33% | 54.67% | 13.64% |
| FRINGE | GREEN | 701 | 7.96% | 0.496 | 58.77% | 41.23% | 5.85% |
| FAIRWAY | ROUGH | 689 | 7.82% | 0.433 | 59.51% | 40.49% | 6.10% |
| FAIRWAY | FAIRWAY | 556 | 6.31% | -0.088 | 89.75% | 10.25% | 1.44% |
| ROUGH | FAIRWAY | 435 | 4.94% | 0.320 | 63.45% | 36.55% | 6.90% |
| FAIRWAY | FRINGE | 307 | 3.49% | 0.238 | 74.59% | 25.41% | 0.98% |
| ROUGH | FRINGE | 257 | 2.92% | 0.611 | 48.25% | 51.75% | 8.56% |
| GREENSIDE_BUNKER | GREEN | 203 | 2.30% | 0.596 | 43.84% | 56.16% | 4.43% |
| FAIRWAY | GREENSIDE_BUNKER | 124 | 1.41% | 0.774 | 33.87% | 66.13% | 9.68% |
| PENALTY_AREA | LOST_BALL/PENALTY 재개 | 116 | 1.32% | 1.940 | 2.59% | 97.41% | 75.86% |
| LOST_BALL/PENALTY 재개 | GREEN | 99 | 1.12% | 1.788 | 3.03% | 96.97% | 73.74% |
| ROUGH | GREENSIDE_BUNKER | 88 | 1.00% | 0.739 | 38.64% | 61.36% | 11.36% |
| BUNKER | FAIRWAY | 56 | 0.64% | 0.554 | 53.57% | 46.43% | 7.14% |
| LOST_BALL/PENALTY 재개 | LOST_BALL/PENALTY 재개 | 38 | 0.43% | 2.395 | 0.00% | 100.00% | 92.11% |
| BUNKER | GREEN | 36 | 0.41% | -0.028 | 88.89% | 11.11% | 2.78% |
| BUNKER | ROUGH | 32 | 0.36% | 0.781 | 34.38% | 65.62% | 12.50% |
| FRINGE | HOLED | 30 | 0.34% | -0.533 | 93.33% | 6.67% | 0.00% |
| LOST_BALL/PENALTY 재개 | FAIRWAY | 30 | 0.34% | 2.200 | 0.00% | 100.00% | 86.67% |

(나머지 25개 조합 — ROUGH→PENALTY_AREA, FAIRWAY→PENALTY_AREA, GREENSIDE_BUNKER→FRINGE, LOST_BALL/PENALTY 재개→ROUGH, ROUGH→LOST_BALL/PENALTY 재개 등 — 모두 `blue_heron_8808_transition_matrix.csv`에 있다.)

---

## 세 번의 검증 (모두 통과)

| 분류축 | 합계 |
|---|---|
| STARTING LIE 분류 합계 | 8,808 |
| SHOT ROLE 분류 합계 | 8,808 |
| SHOT NUMBER 분류 합계 | 8,808 |

세 축 모두 8,808과 정확히 일치. FAIL 없음.

---

## 요약 숫자만 다시

- 8,808 = FAIRWAY 시작 3,879 + ROUGH 시작 3,431 + BUNKER 시작 152 + GREENSIDE_BUNKER 시작 259 + FRINGE 시작 737 + PENALTY_AREA 시작 139 + LOST_BALL/PENALTY 재개 시작 211 + OTHER 0
- 8,808 = NORMAL APPROACH 2,466 + ADVANCE/LAY-UP 938 + RECOVERY 3,842 + SHORT GAME 737 + PENALTY/RESTART 350 + OTHER/UNRESOLVED 475
- 8,808 = shot#2 5,034 + shot#3 2,983 + shot#4 640 + shot#5 117 + shot#6 28 + shot#7+ 6
- FW HIT 후 첫 후속샷 GIR% = 68.88%(n=2,802) / FW MISS 후 첫 후속샷 GIR% = 41.27%(n=1,832)

## 산출물
- `blue_heron_8808_shot_breakdown.csv` — 8,808건 전수, 샷 단위
- `blue_heron_8808_transition_matrix.csv` — 45개 start→end 조합, 집계
