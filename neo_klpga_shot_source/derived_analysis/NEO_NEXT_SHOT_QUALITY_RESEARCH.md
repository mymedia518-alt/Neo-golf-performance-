# NEO 다음 샷 조건의 질 — 연구 결과

## A. 다음 샷 조건의 질 — 필드 전체 기준 (`neo_next_shot_quality.csv`)

23개 (lie, distance band) 구간, 모두 n≥5. 평균 최종 score-to-par의 3분위로 유리/중립/위험 분류.

**유리(상위 1/3):** BUNKER 100-150yd(n=9), FAIRWAY 50-100yd(n=439), FAIRWAY 100-150yd(n=496),
GREEN 6-9yd(n=798), GREEN 9-12yd(n=534), GREEN 3-6yd(n=1195), GREEN 12-20yd(n=583), FRINGE
9-12yd(n=103).

**위험(하위 1/3):** FRINGE 6-9yd(n=165), ROUGH 0-50yd(n=1064), GREENSIDE_BUNKER 0-50yd(n=222),
ROUGH 150-200yd(n=49), FAIRWAY 200yd+(n=43), BUNKER 50-100yd(n=8), ROUGH 200yd+(n=37, double+60%).

**방법론적 주의(AF08):** GREEN 0-3yd가 "중립"으로 분류됐는데 bogey+ 비율이 34%나 된다 — 이는 "처음
도착한 아주 가까운 위치"와 "이미 한 번 놓치고 남은 짧은 퍼트"가 섞여 있기 때문이다. 이 구간은 순수
approach 품질이 아니라 "그 지점에 섰을 때 필드가 실제로 낸 결과"로만 해석해야 한다.

## B. 위치 가치 — 예뻐 보이는 위치가 좋은 위치가 아니다

FAIRWAY 200yd+는 "페어웨이에 있다"는 사실만으로는 안심할 수 없다 — bogey+70%, double+40%(n=43)로
가장 위험한 구간 중 하나다. 반대로 FRINGE 9-12yd(n=103)는 그린을 놓친 상태인데도 "유리" 등급이다.
**위치 → 다음 샷 → 최종 스코어로 평가해야 하는 이유가 바로 이것**: lie 이름만으로는(FAIRWAY vs
FRINGE) 가치 순서를 예측할 수 없다.

## C. 미스의 질 — GIR MISS 하나로 묶지 않음 (`neo_gir_paradox_cases.csv`)

216개 홀-플레이 전수 분류:

| 카테고리 | n |
|---|---|
| GIR → Par | 101 |
| GIR → Birdie+ | 23 |
| GIR → Bogey | 13 |
| GIR → Double+ | 1 |
| GIR MISS → Par | 45 |
| GIR MISS → Bogey | 28 |
| GIR MISS → Double+ | 5 |

GIR을 달성해도 14건(13+1)은 Bogey 이상으로 끝났고, GIR을 놓쳐도 45건은 오히려 Par로 끝났다 — GIR
이진 지표가 숨기는 정보량이 상당하다.

## D. 손실 억제 능력 — 단순 Par Save%와 다른 개념

Par Save%는 "GIR 미스 후 Par 이상으로 끝냈는가"만 본다. NEO의 손실 억제는 "실수 이후 추가 손실을
얼마나 막았는가"를 본다 — 예: R3H6(유해란, 로스트볼+페널티)는 Par Save에 애초에 해당하지 않는
사건이지만(GIR 여부를 따질 상황이 아님), 실제로는 "최악의 시작에서도 1타 손실로 막은" 가장 강한
손실억제 사례다. 이 개념은 `three_player_score_preservation_cases.csv`(기존)와 `direct_cost`/
`excess_cost` 분리(attribution audit에서 이미 구축)를 그대로 재사용한다.

## E. FW/GIR의 실제 한계 — shot chain으로 증명

`neo_fairway_paradox_cases.csv`: FW_HIT_GOOD 78건(가장 큰 범주 — FW%가 무의미하다는 뜻은 아님),
FW_MISS_GOOD 49건, FW_HIT_BAD 21건, FW_MISS_BAD 20건. **같은 FW HIT이라도 다음 샷 조건이 완전히
달랐던 사례(21건)와, FW MISS가 오히려 나은 결과로 이어진 사례(49건)가 모두 실수로 확인됐다 — "FW는
중요하지 않다"가 아니라 "FW 적중이라는 이진 지표가 티샷의 실제 가치를 항상 설명하지는 못한다"는
것이다.**

## F. 접근 거리 구간별 전환율 — A/B/C 분리 (`approach_proximity_conversion.csv`)

| 거리구간 | 유해란 Birdie% (n) | 이재윤 Birdie% (n) | 박서현 Birdie% (n) | FIELD Birdie% (n) |
|---|---|---|---|---|
| 0-3yd | 80%(10) | 50%(6) | 100%(1, 표본부족-기각) | 62.5%(461) |
| 3-6yd | 17.6%(17) | 12.5%(8) | 0%(13) | 21.1%(861) |
| 6-9yd | 20%(10) | 0%(13) | 20%(10) | 10.8%(807) |
| 9-12yd | 14.3%(7) | 0%(9) | 20%(5) | 5.7%(579) |
| 12yd+ | 11.1%(9) | 0%(7) | 0%(13) | 2.5%(902) |

**핵심 질문에 대한 답: 이재윤의 낮은 Birdie율은 B(거리를 통제해도 전환율이 낮음)에 가깝다.** 6-9yd,
9-12yd, 12yd+ 세 구간 모두에서 그는 필드 평균보다도 낮은 0%를 기록했다(필드는 각각 10.8%/5.7%/2.5%).
거리 자체(A)가 원인이 아니라는 뜻은 아니다 — 그의 평균 첫퍼트 거리(8.4yd)가 유해란(7.06yd)보다 길다는
사실(A)과, 같은 거리에서도 전환율이 낮다는 사실(B)이 **둘 다** 작용하는 것으로 보인다(C). 단, 구간별
표본이 7~13으로 작아 **신뢰도는 MEDIUM**으로 제한한다 — "이재윤의 접근 정밀도가 나쁘다"를 HIGH
확신으로 단정하지 않는다.
