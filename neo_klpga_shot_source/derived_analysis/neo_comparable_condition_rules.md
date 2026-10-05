# 비슷한 조건 — 데이터 규칙

"거의 같은 위치", "비슷한 거리", "같은 조건"이라는 표현을 데이터 규칙으로 정의한다.

## 비교 요소 체크리스트

| 요소 | 통제 방법 |
|---|---|
| 같은 홀인가 | same-start/same-miss는 같은 (round, hole) 내에서만 비교 — 다른 홀 비교는 same_location_player_execution.csv에서만, 좌표가 아니라 실제 야드 거리로 |
| 같은 라운드인가 | 핀이 라운드마다 다르므로, 같은 홀 비교는 같은 라운드일 때 핀이 자동으로 동일함 |
| 같은 실제 핀인가 | same-hole 비교는 구조적으로 보장됨(같은 round+hole) |
| 같은 lie인가 | 반드시 명시적으로 일치 확인 (FAIRWAY=FAIRWAY, ROUGH=ROUGH 등) |
| 남은 거리가 비슷한가 | 민감도 테스트 완료 (아래) |
| 시작 위치가 비슷한가 | same-start 테스트의 핵심 조건 |
| 도착 위치가 비슷한가 | same-miss/same-location 테스트의 핵심 조건 |
| 같은 shot stage인가 | 티샷은 티샷끼리, 미스는 미스 지점끼리만 비교 (서로 다른 샷 번호라도 "상태"가 같으면 비교 — same_location_player_execution.csv는 이 방식) |

## 거리 허용오차 민감도 테스트

`comparable_condition_sensitivity.csv` 참고. 페어웨이 착지(남은거리) 비교는 ±3/5/10yd, 그린 주변
미스(핀거리) 비교는 ±1/2/3/5yd로 각각 테스트했다. 허용오차를 넓히면 사례 수는 늘지만(3→6→10,
2→3→3→4), **가장 엄격한 기준(±1yd, ±3yd)에서도 이미 사례가 존재**하므로, 발견된 패턴이 허용오차
선택 자체에서 만들어진 것이 아님을 확인했다.

## 채택한 기본값

- same-start-different-end: ±3~5yd (필드 decile 기반 홀별 동적 허용오차와 고정 ±3yd 결과가 거의
  일치 — 교차검증됨)
- same-miss-different-recovery: ±5yd (±1yd에서도 패턴이 존재함을 먼저 확인한 뒤 채택)
- same-location-player-execution (홀 무관): ±1yd — 가장 엄격한 기준, 13,755개 매칭 쌍 중 2,310개가
  실제로 strokes-to-finish가 다름을 확인
