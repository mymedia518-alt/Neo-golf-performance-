# 왜 KLPGA 1부투어 선수들조차 Blue Heron 8번홀에서 스코어를 잃었는가?

**단위**: player+round+hole = 1 hole-play. 모든 수치는 Shot Tracker의 실제 샷 순서(SHOT 1→...→HOLED)를 보존한 chain에서 계산. TEE 원점(baseHoleInfo bi_sx/bi_sy)은 사용하지 않았다 — 분석은 SHOT 1의 **착지 지점**부터 시작하며, 이는 Phase 1.6에서 저신뢰로 분류된 "tee origin"이 아니다.

---

## 1. H8 필드 모집단 (reconciliation)

| | n |
|---|---|
| players_RAW_READONLY 기준 전체 player-round | **337** |
| H8에서 실제 샷 레코드 존재 | **331** |
| 결측 | 6 |
| — 그중 기존에 확인된 SOURCE_GAP(player,round 전체 180° 결측, derive_shot_analysis.py) | **6** |
| — 설명 안 되는 결측 | **0** |
| shot 순서 1..N 연속성 위반 | **0** |
| 전체 RAW shot rows (hole=8) | 1,452 |

**임의 보간 없음.** 331건 전수 사용. field average score-to-par = **+0.387**(사용자 제시값과 정확히 일치, 자체 재계산으로 재확인).

---

## 2. FIRST FAILURE — 알고리즘 (계산 전 고정)

샷 순서를 그대로 따라가며 **처음** 관찰되는 이상 상태만 본다. 최종 스코어로 역추론하지 않는다.

1. SHOT 1(티샷)이 FAIRWAY가 아니면 → `TEE_<lie>` (페널티 상태면 `TEE_PENALTY_<lie>`)
2. (1이 아니었다면) GIR 기준 샷(파4이므로 SHOT 2)이 GREEN이 아니면 → `APPROACH_MISS_TO_<lie>`
3. (1,2 모두 정상이었다면) 그린 적중 후 퍼트가 3개 이상이면 → `PUTTING_LOSS_3PLUS`
4. 셋 다 해당 없으면 → `NONE`(관찰된 실패 없음 — 반드시 Par 이상이어야 함, 아래서 검증)

**ESCALATION**은 first failure 발생 "이후" 샷에서만 집계: 페널티 상태 재발생(`PENALTY_AFTER_FIRST_FAILURE`), 그린 밖에서 그린 밖으로 또 실패한 리커버리(`RECOVERY_FAILED`), 3퍼트가 다른 실패 뒤에 덧붙는 경우(`THREE_PUTT_AFTER_EARLIER_FAILURE`). FIRST FAILURE와 ESCALATION은 코드 레벨에서 분리 — 같은 필드에 섞지 않았다.

**정합성 검증**: `NONE`(115건) 전원 Par 이상(89 Par + 26 Birdie+, Bogey 0건) — 정의상 당연하지만 버그 없음을 확인.

| FIRST FAILURE | n | 평균 홀 스코어 |
|---|---|---|
| NONE | 115 | **−0.226** |
| APPROACH_MISS_TO_FRINGE | 15 | 0.200 |
| APPROACH_MISS_TO_ROUGH | 33 | 0.424 |
| TEE_ROUGH | 138 | 0.645 |
| PUTTING_LOSS_3PLUS | 9 | 1.000 |
| APPROACH_MISS_TO_PENALTY_AREA | 16 | **1.750** |
| TEE_PENALTY_LOST_BALL | 5 | **2.200** |

깨끗한 평균 severity gradient. **워터(PENALTY_AREA) 관련 first failure가 TEE_ROUGH보다 홀당 1타 이상 더 비쌌다.**

---

## 3. ESCALATION

| 유형 | n |
|---|---|
| PENALTY_AFTER_FIRST_FAILURE | 58 |
| RECOVERY_FAILED | 56 |
| THREE_PUTT_AFTER_EARLIER_FAILURE | 5 |
| **합계 이벤트** | **119** (56개 hole-play, 331건 중 16.9%가 1회 이상 escalation) |

Map 3(`h8_escalation_map.png`)에서 PENALTY_AFTER_FIRST_FAILURE가 거의 전부 water hazard 경계에 몰려 있음을 육안 확인.

---

## 4. TEE SHOT LANDING — LOCATION VALUE (`h8_location_outcome.csv`)

실제 분포 기반 거리 3분위(NEAR≤130.4yd / MID≤147.1yd / FAR>147.1yd, n=326 reliable). Low-N(<8)은 색/강조 약화 대상으로 플래그.

| lie | dist band | n | GIR% | Par+% | Bogey% | Double+% | Penalty% | 평균 스코어 |
|---|---|---|---|---|---|---|---|---|
| FAIRWAY | NEAR | 76 | 80.3 | 90.8 | 6.6 | 2.6 | 3.9 | **−0.105** |
| FAIRWAY | MID | 62 | 61.3 | 75.8 | 16.1 | 8.1 | 12.9 | 0.274 |
| ROUGH | FAR | 58 | 10.3 | 39.7 | 44.8 | 15.5 | 13.8 | **0.845** |
| FAIRWAY | FAR | 50 | 50.0 | 60.0 | 30.0 | 10.0 | 10.0 | 0.380 |
| ROUGH | MID | 47 | 29.8 | 59.6 | 29.8 | 10.6 | 12.8 | 0.489 |
| ROUGH | NEAR | 33 | 33.3 | 60.6 | 30.3 | 9.1 | 18.2 | 0.515 |
| OTHER_PENALTY(LOST_BALL 등) | — | 5 (LOW_N) | 0.0 | 0.0 | 0.0 | 100.0 | 100.0 | 2.200 |

**핵심 발견**: "페어웨이를 지켰다"가 동질적이지 않다. FAIRWAY 안에서도 NEAR(−0.105)와 FAR(0.380) 사이에 **0.485타** 차이가 난다 — 페어웨이에 떨어졌어도 멀리 떨어지면 ROUGH/MID(0.489)만큼 나쁘다. 반대로 LIE 자체도 동일 거리대에서 항상 FAIRWAY가 ROUGH보다 유리(각 band에서 0.2~0.5타 격차 일관). **ROUGH·FAR(58건, 두 번째로 큰 표본)가 "일반적인" 조합 중 최악** — 거의 보기 확정(평균 0.845).

---

## 5. LOCATION vs EXECUTION (`h8_same_condition_different_result.csv`)

같은 lie + 같은 round(핀) + 거리차 ≤20yd 조건에서 결과가 2단계 이상 갈린 쌍 **754개** 발견(±5yd 200개, ±10yd 450개, ±20yd 754개 — 민감도 전 구간 표본 풍부).

상위 25쌍(거리차 최소순) 중 뚜렷한 2가지 패턴이 섞여 있다:

**A. LOCATION/COURSE-주도 패턴 (약 절반)**: 동일 fairway 위치(거리차 0.0~0.7yd)에서 한쪽은 `NONE`/`APPROACH_MISS_TO_ROUGH`로 PAR, 다른 쪽은 하필 `APPROACH_MISS_TO_PENALTY_AREA`로 DOUBLE+ — 예: 윤수아(127.8yd,PAR) vs 박현경(127.8yd,DOUBLE+), 서어진(132.9yd,PAR) vs 이다연(133.0yd,DOUBLE+). **거의 같은 지점에서 쳤는데 물을 만났는지 아닌지가 갈랐다** — 이건 선수 역량 차이로 설명하기 어렵다(상위~하위 랭킹 선수 양쪽에 모두 나타남: rank5 이다연도 포함).

**B. EXECUTION-주도 패턴**: 양쪽 다 같은 위험 노출(둘 다 ROUGH 티샷, 둘 다 물에 가지 않음)인데 한쪽만 Bogey/Double — 예: 전예성(180.2yd,ROUGH,PAR) vs 조하리(180.5yd,ROUGH,DOUBLE+); 현세린(NONE,BIRDIE+) vs 이승연(PUTTING_LOSS_3PLUS,BOGEY, 132yd대 동일 조건). **같은 조건·같은 위험 노출에서도 실행(어프로치 정확도, 퍼팅)이 갈랐다.**

LOCATION VALUE와 PLAYER EXECUTION을 같은 색/지표로 합치지 않았다 — 섹션 4(위치)와 섹션 5(위치 vs 실행 쌍)를 분리 유지.

---

## 6. COURSE risk vs PLAYER execution (관찰, 인과 아님)

| 패턴 | 반복성 | 분류 후보 |
|---|---|---|
| TEE_ROUGH (138/331, 41.7%) | 매우 많은 선수에게 반복 | **COURSE/LOCATION RISK 후보** — 페어웨이 자체가 좁음(공식 tip: "페어웨이 폭이 좁으며") |
| APPROACH_MISS_TO_PENALTY_AREA → 평균 1.750타 | 16건, 여러 다른 순위대 선수에 분산 | **COURSE/LOCATION RISK 후보** — 동일 지점에서 물을 만나는지가 결과를 가름(섹션5-A) |
| 같은 ROUGH 티샷·같은 거리에서 한쪽만 Bogey+ (섹션5-B) | 특정 쌍에 한정 | **PLAYER EXECUTION 후보** |

"COURSE risk"라고 분류한 것도 인과관계 주장이 아니라 "많은 선수에게 반복적으로 같은 지점에서 같은 유형의 손실이 관찰됨"이라는 기술(description)이다.

---

## 7. RED TEAM

- **표본 크기**: 주요 first-failure 범주 모두 n≥9(PUTTING_LOSS만 9), LOW_N 플래그 location-value 표에 명시(OTHER_PENALTY n=5).
- **round/pin**: section5 쌍 매칭은 전부 "같은 round"(=같은 핀) 조건으로 제한, 느슨화하지 않음.
- **lie/거리**: 모든 location-value·pair 비교가 lie+실측 remaining-distance 기준, 임의 거리 cutoff 없음(3분위는 실제 분포 기반).
- **퍼팅 변동성**: PUTTING_LOSS_3PLUS를 별도 카테고리로 분리해 "어프로치는 괜찮았는데 퍼팅에서 진" 경우를 섞지 않음.
- **단일 재해(catastrophe) 왜곡 여부**: TEE_PENALTY_LOST_BALL n=5로 작아 평균(2.2) 과대 해석 주의 — 표에 LOW_N 느낌으로 별도 언급, 단정적 주장에 사용하지 않음.
- **좌표 artifact**: 모든 맵 좌표는 Phase 1.6 similarity transform(LOO median ≈6.8yd) 사용 — 이 오차보다 작은 공간 구분(예: "정확히 몇 미터 차이")은 주장하지 않음. 섹션4/5는 주로 **실측 remaining-distance**(픽셀 아님)를 1차 근거로, 지도 좌표는 시각화·대략적 proximity 확인용으로만 사용.
- **registration 불확실성**: TEE 영역은 Phase 1.6에서 LOW CONFIDENCE로 확정됨 — 이번 분석에서 "tee origin" 위치·방향에 대한 주장은 전혀 하지 않았다(SHOT 1 착지점만 사용, 이는 fairway/mid-hole 영역으로 등록 신뢰도가 높음).
- **player vs location**: 섹션5에서 둘을 분리해 각각 실제 사례로 제시, 어느 한쪽으로 일반화하지 않음.
- **course vs player**: 섹션6은 "반복성"만으로 분류했고 인과 단어를 쓰지 않음.

---

## 8. 산출물

- `h8_hole_play_chain.csv` (1,452행, 샷 단위 전수)
- `h8_location_outcome.csv` (7행, location value)
- `h8_first_failure.csv` (331행)
- `h8_escalation.csv` (119행)
- `h8_same_condition_different_result.csv` (25쌍, 전체 754 후보 중 상위)
- `h8_field_score_loss.png` / `h8_first_failure_map.png` / `h8_escalation_map.png` / `h8_three_player_story.png`

---

## 결론 — STOP, 배포하지 않음

데이터가 지지하는 답: **H8의 +0.387은 단일 원인이 아니라 두 개의 독립적 손실원이 중첩된 결과다.**
1. **좁은 페어웨이 자체(COURSE)** — TEE_ROUGH가 41.7%로 가장 흔한 first failure, 그리고 FAIRWAY 안에서도 착지 거리에 따라 0.485타 차이가 나는 것은 코스 디자인(좁은 페어웨이 + 긴 세컨샷 요구)의 구조적 특성.
2. **그린 앞 연못(COURSE, 그러나 결과 분리력은 EXECUTION에 가깝게 보임)** — 같은 위치에서 쳤는데 물을 만났는지 아닌지가 결과를 가른 사례가 다수(섹션5-A) — 이는 선수 역량보다 어프로치 각도/클럽 선택의 순간적 변동에 더 가까운 위험.

NEO 최종 H8 story(공개용 한 문장)를 결정하기 전에 반드시 4개 맵을 직접 보고 판단할 것. 아직 HOME/website에 배포하지 않았다.
