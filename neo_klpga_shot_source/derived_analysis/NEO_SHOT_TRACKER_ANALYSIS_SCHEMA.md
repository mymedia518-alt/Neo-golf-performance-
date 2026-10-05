# NEO Shot Tracker 분석법 — 재사용 가능한 내부 분석 스키마

앞으로의 모든 대회 분석에 재사용하기 위한 내부 방법론 문서. 이번 작업(유해란/이재윤/박서현, Game
2026100005)에서 실제 데이터로 끝까지 검증했고, 성립하지 않는 부분은 억지로 만들지 않고 UNKNOWN 또는
NO RECOMMENDATION으로 남겼다.

## 분석 파이프라인 (실제로 성립함을 확인)

```
RAW SHOT (klpga_player_shot)
  ↓
실제 핀 결합 (해당 라운드의 홀아웃 좌표 평균, VERIFIED 상태만 사용 — pin_placement_72hole_audit.json)
  ↓
공간 정규화 (티-그린 축: 전체 필드 티샷+홀아웃 좌표 평균으로 홀마다 재계산, 좌/우 라벨 없이 LAT1/2/3만 사용)
  ↓
Shot Chain 구성 (상태0~4, 아래 참고)
  ↓
비슷한 상태 매칭 (lie + 실제 야드 거리 허용오차, sensitivity test로 확정)
  ↓
전체 필드 위치 가치 (n>=5 bin만 사용, terciles로 유리/중립/위험 분류)
  ↓
선수별 위치 가치 (같은 bin, 선수 개인 n — 필드와 별도 레이어로 유지, 절대 합산 금지)
  ↓
다음 샷 조건의 질 (해당 위치에 섰을 때 필드가 실제로 낸 결과로 정의 — 보기 좋은 위치가 아니라 결과로 정의)
  ↓
미스의 질 (미스 위치 → recovery 조건 → recovery 결과 → 최종 스코어, 하나로 뭉치지 않음)
  ↓
손실 억제 (실수 이후 추가 손실을 막았는가 — 기존 Par Save%와 다른 개념으로 유지)
  ↓
코스 위험 × 선수 위험 (2축 분리, course_player_risk_matrix.csv가 실제로 이 분리가 가능함을 증명)
  ↓
선수/캐디 의사결정 (근거 부족하면 NO RECOMMENDATION)
```

## Shot Chain 5-상태 구조 (`neo_shot_chain_states.csv`에서 실제 구현)

| 상태 | 정의 | 필드 |
|---|---|---|
| 상태0 | 샷 전 조건 | lie_before, remaining_before_yd |
| 상태1 | 샷 결과 위치 | end_coord, lie_after, remaining_after_yd |
| 상태2 | 다음 샷 조건 | next_shot_lie_hint, recovery_needed, penalty_next |
| 상태3 | 다음 샷 결과 | next_shot_outcome_lie, next_shot_remaining_after_yd |
| 상태4 | 최종 스코어 | final_score, score_bucket |

679개의 "qualifying shot"(마지막 홀아웃 샷 제외, 유해란/이재윤/박서현 72홀×3)에서 실제로 이 5단계가
전부 RAW 필드로 채워짐을 확인했다. 비어있는 칸(예: 거리 불명 상태코드)은 공란으로 남겼고 임의로 채우지
않았다.

## "비슷한 조건" — 데이터 규칙 (`neo_comparable_condition_rules.md` 요약)

하나의 임의 기준으로 끝내지 않고 민감도 테스트를 실행했다 (`comparable_condition_sensitivity.csv`):

| 테스트 | 허용오차 | 발견 사례 수 |
|---|---|---|
| same-start-different-end (페어웨이 착지, 남은거리) | ±3yd | 3 |
| | ±5yd | 6 |
| | ±10yd | 10 |
| same-miss-different-recovery (같은 lie, 핀까지 거리) | ±1yd | 2 |
| | ±2yd | 3 |
| | ±3yd | 3 |
| | ±5yd | 4 |

**결론: 허용오차를 바꿔도 발견된 패턴(같은 조건에서 결과가 갈리는 사례가 존재한다는 것)은 유지된다 —
개수만 늘거나 준다. 허용오차가 패턴 자체를 만들어낸 것이 아니다.** 본 분석에서는 same-start는
±3~5yd(필드 decile 기반과 일치), same-miss는 ±5yd를 기본값으로 채택했다 — 가장 보수적인(±1yd) 조건
에서도 사례가 존재했으므로 더 느슨한 기준을 쓴다고 패턴이 '만들어진' 것이 아님을 확인했다.

## 다음 샷 조건의 질 — 분류 규칙

필드 전체(107명) 기준, (lie, distance band)별 n≥5인 23개 구간의 최종 스코어 평균을 3분위(tercile)로
나눠 유리/중립/위험을 분류했다(`neo_next_shot_quality.csv`). **중요한 방법론적 한계**: GREEN/FRINGE
구간은 "처음 도착한 위치"와 "이미 한 번 놓치고 남은 퍼트 위치"가 섞여 있다 — 순수 approach 품질
지표가 아니라 "그 지점에 섰을 때 필드가 낸 실제 결과"로 읽어야 한다 (AF08 참고).

## 절대 하지 않은 것

- 좌표만 보고 실제 조준 의도(draw/fade/클럽선택/멘탈) 추정 — 전부 UNKNOWN 처리.
- 서로 다른 홀의 원시 (x,y) 좌표를 직접 비교 — 핀 상대 좌표(green_x,green_y − pin) 또는 실제 야드
  거리만 홀을 넘나들며 비교했다.
- 눈으로 본 "위험해 보이는 위치"를 그대로 라벨링 — 모든 유리/중립/위험 라벨은 실제 field n과 결과로만
  정의했다.
- 필드에서 좋은 위치 = 선수에게도 좋은 위치라는 가정 — `field_vs_player_location_value.csv`와
  `course_player_risk_matrix.csv`가 이 둘을 독립된 레이어로 유지하고, 실제로 갈리는 사례(Hole 9)를
  찾아 증명했다.
- 1회성 사건을 선수 특성으로 명명 — 모든 주요 발견에 n과 반복 횟수를 표시했고, 재검토 결과 "반복"이
  아니라 "같은 사건의 중복 비교"였던 경우(AF11)는 신뢰도를 낮췄다.

## 앞으로 모든 분석이 답해야 할 8가지 질문 (체크리스트)

1. 공은 실제 어디에 떨어졌는가 — 좌표/lie/남은거리로 답할 것.
2. 그 위치가 다음 샷에 어떤 조건을 만들었는가 — 상태2로 답할 것.
3. 전체 필드는 그 위치에서 어떤 결과를 냈는가 — n과 함께.
4. 이 선수는 그 위치에서 어떻게 달랐는가 — 필드와 별도 레이어로.
5. 이 선수에게 손실이 적은 miss 위치는 어디인가 — 표본 있을 때만.
6. 어느 위치부터 이 선수의 실수가 비싸지는가 — direct cost vs escalation 분리.
7. 이 선수에게 가장 좋은 다음 샷 조건을 만드는 위치는 어디인가 — 표본 있을 때만.
8. 그래서 선수와 캐디는 무엇을 다르게 준비해야 하는가 — 근거 부족하면 NO RECOMMENDATION.
