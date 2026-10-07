# HJ중공업·동부건설 챔피언십 (2026100004) — Stableford Monte Carlo 실험 방법론

**상태: EXPERIMENTAL. 아직 public website에 배포되지 않았다.** HOME/PRE의 현재
Stableford V1 사전평가 순위는 이 실험으로 변경되지 않았다. 이 문서와 결과는
검증/Red Team 전용이다.

## 0. 이 실험이 아닌 것

- 이 실험은 `STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json`
  (sha256 `575fd58e8b2b0a70b17fa98e5281d7b0966c5b970a3cbe108250c8479c348185`,
  commit `c4ab957`)을 **읽기만** 한다. 그 파일, 그 안의 `pre_event_rank`/
  `net_expected_value`, 또는 V1이 사용하는 어떤 공식·가중치도 수정하지 않았다.
- 이 실험은 새로운 0-100 점수나 새로운 가중치를 만들지 않는다.
- 이 실험은 2023~2025 실제 우승자 결과에 calibration/fitting 하지 않는다
  (근거: `stableford_monte_carlo_experiment.py`/`230_hj_2026_stableford_
  monte_carlo.py` 전체에 "2023"/"2024"/"2025"/과거 우승자 이름에 대한 참조가
  0건 — grep으로 확인).
- 이번 버전은 코스 효과(A-One course multiplier)를 포함하지 않는다
  (PLAYER STABLEFORD DISTRIBUTION ONLY, 지시사항 12번).

## 1. DATA CUTOFF / LEAKAGE

- target: `2026100004`, 대회 시작 `2026-10-08`.
- 입력 데이터는 전부 `STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json`의
  `records[*].{albatross,eagle,birdie,par,bogey,double_or_worse,rounds,holes}`
  뿐이다 — 이 필드들은 V1 자신이 이미 "2026-10-08 이전 데이터만, target
  2026100004 데이터 0" 조건으로 빌드하고 검증한 값이다(commit `c4ab957`,
  `ccf8321`).
- 이번 실험이 독립적으로 재확인한 것(`validate_target_leakage()`):
  1. snapshot의 `target_game_code == "2026100004"`, `target_start_date ==
     "2026-10-08"` 둘 다 일치.
  2. snapshot에 `leaderboard`/`scoreRecord`/`actual_result`/`r1`/`r2`/`r3`/
     `fr`/`final_result` 같은 사후(post-event) 키가 최상위에도, 레코드
     레벨에도 전혀 없다.
  3. `content/website_v2/` 디렉터리 전체에서 `2026100004_` 접두사를 가진
     파일 중 LEADERBOARD/SCORERECORD/ACTUAL_RESULT/_R1_/_R2_/_R3_/_FR_/
     _FINAL_RESULT 패턴을 가진 파일이 **0건** — target 실제 결과 파일 자체가
     레포에 존재하지 않는다(대회가 아직 시작되지 않았으므로 구조적으로
     존재할 수 없음).
- **결론: target leakage = 0 (증명됨, 코드로 재확인됨).**

## 2. FIELD

- 공식 출전선수 108명, `2026100004_CANONICAL_PLAYER_IDENTITY_V1.json` 기반
  canonical identity를 그대로 사용(frozen snapshot 레코드에 이미 반영됨).
- `data_status` 그대로 보존: 106/108 `OK`(실제 prior data 있음), 2명
  `DATA_LIMITED_THIN_SAMPLE`(성아진 6라운드/108홀, 박조은(A) 2라운드/36홀),
  2명 `DATA_LIMITED_NO_PRIOR_DATA`(김민서3, 이지유(A) — 매칭된 이전 대회
  기록 0건).
- **NO_PRIOR_DATA 처리 방법 (simulation 전 명시적으로 정의, PRIMARY 런)**:
  field-neutral prior — 해당 2명을 제외한 106명(OK + THIN_SAMPLE)의 실제
  category count를 홀 수 가중으로 전부 합산해 정규화한 "평균 투어 선수"
  분포를 사용. 이 분포는 V1 순위를 전혀 참조하지 않고 계산되며(
  `field_neutral_prior_counts()`는 `pre_event_rank`를 읽지도 않는다),
  두 선수 모두 동일한 분포를 공유한다. 결과 테이블에서 `prior_source:
  "field_neutral_prior"`로 명시 표시되고, 실제 개인 데이터가 아님을 report
  전체에서 반복 명시한다.
- **민감도(sensitivity) 비교**: 동일 seed로 해당 2명을 필드에서 완전히
  제외한 106명 필드로 재실행(SENSITIVITY 런). 나머지 106명(두 변형 모두에
  공통)의 win%/top10%/make-cut% 차이:
  - win% 최대 절대 차이: **0.0371%p**
  - top10% 최대 절대 차이: **0.375%p**
  → 2명의 synthetic prior가 나머지 필드에 주는 영향은 무시할 수준으로
  작다. (세부 수치는 `HJ_2026100004_STABLEFORD_MONTE_CARLO_V1_RESULTS.json`
  의 `sensitivity_no_prior_data_policy`에 108행 전부 기록됨.)
- THIN_SAMPLE 2명은 본인의 실제(작은) 표본 그대로 사용 — V1 순위를 맞추기
  위한 어떤 조정도 하지 않았다.

## 3. OFFICIAL STABLEFORD SCORING

`klpga.website_v2.stableford_scoring.SCORING_TABLE`(이미 존재하는 V1의 공식
점수표 모듈, 수정 없이 import)을 그대로 사용:

albatross +8, eagle +5, birdie +2, par 0, bogey -1, double bogey or worse -3

`validate_scoring_table()`이 매 실행마다 이 순서/값을 재확인하며, 다르면
즉시 실패한다.

## 4. PLAYER DISTRIBUTION

각 선수의 P(albatross)..P(double+)는 frozen snapshot의 실제 카운트
(`count / holes`)에서 직접 계산 — 반올림된 `_rate` 필드가 아니라 원본
정수 카운트를 사용해, 6개 카테고리 합이 부동소수점 오차 없이 정확히
1.0이 되도록 했다(106/106명 OK+THIN_SAMPLE 선수 전원에서 `albatross+eagle+
birdie+par+bogey+double_or_worse == holes` 사전 확인됨).

독립 재검증: 서교림(V1 #1)의 `expected_points_per_hole`을 이 모듈이 자체
계산한 확률 벡터로 재계산하면 `0.2807`로, V1 snapshot의 `net_expected_
value` 값과 **정확히 일치**한다 — V1과 이 실험 사이에 데이터 정의가
갈라지지 않았다는 직접 증거.

각 선수별 audit 가능한 필드(결과 JSON에 전부 기록): `sample_rounds`,
`sample_holes`, `category_probabilities`(6개), `expected_points_per_hole`.

## 5. MONTE CARLO

- 60,000회 반복, 108명 필드 × 4라운드 × 18홀.
- 구현: 선수별로 `numpy.random.Generator.multinomial(18, p, size=60000)`을
  라운드마다 호출해 그 라운드 18홀의 카테고리 카운트를 한 번에 뽑고
  (8,5,2,0,-1,-3) 벡터와 내적해 라운드 점수를 계산 — 홀 단위로 순차 추첨한
  것과 수학적으로 동일한 분포(다항분포는 정의상 n번의 iid 카테고리 추첨의
  합)이면서 훨씬 빠르다.
- 고정 seed(`20261007`)로 선수 순서·라운드 순서를 고정해 반복 실행하면
  완전히 동일한 결과가 나오도록 구성(아래 10번 참조).
- 명시적 가정(단순화): 라운드 간 상관관계(연속 호조/부진, 날씨, 코스
  적응 등)를 모델링하지 않는다 — 매 라운드 동일한 사전(pre-event) 분포에서
  독립적으로 추첨한다. 이것은 "PLAYER STABLEFORD DISTRIBUTION ONLY"라는
  명시적 지시(12번)와 일치하는 단순화이며, Red Team 보고서에서 한계로
  다시 명시한다.

## 6. CUT

R1+R2 (36홀) 누적 Stableford 점수 기준으로 상위 60명 + 동점자 전원 통과.
구현: 시뮬레이션마다 36홀 누적 점수를 내림차순 정렬해 60번째 값을 cutline
으로 삼고, cutline 이상인 모든 선수를 통과시킨다(60명보다 많아질 수 있음,
의도된 동작). `validate_cut_rule()`이 매 시뮬레이션에서 (a) 통과자가
60명 미만인 경우가 없는지, (b) 탈락자 중 어떤 선수도 통과자보다 높은 36홀
점수를 가진 경우가 없는지 전수 검증.

CUT 탈락 선수는 R3/R4를 "진행하지 않은 것"으로 최종 점수를 36홀 합계로
고정한다(R3/R4는 구현 단순화를 위해 내부적으로는 계산되지만, 그 선수의
해당 시뮬레이션 최종 점수/순위 계산에는 전혀 사용되지 않는다 — 버려지는
계산일 뿐, 결과에 영향 없음).

## 7. FINAL RANKING / TIES

- R4 종료 후(즉 72홀 누적, CUT 통과자만) 점수로 순위를 매긴다. CUT 탈락자는
  Win/Top5/Top10/Top20 산출에서 애초에 후보가 아니다(실제 대회에서 최종
  순위에 들 수 없는 것과 동일).
- **우승 동점**: 공동 1위 선수들에게 1.0 win credit을 균등 분할한다(예:
  2명 공동 1위 → 각 0.5). 플레이오프 승자를 임의로 예측하지 않는다 —
  "누가 이길지"가 아니라 "이 시뮬레이션에서 공동 선두에 몇 명이 있었는가"
  만 반영한다.
- **Top5/Top10/Top20**: 해당 순위 경계 점수와 동점인 선수는 전원 포함(실제
  골프 중계의 "공동 T5" 관례와 동일) — win과 달리 credit을 쪼개지 않고
  전원 카운트.

## 8. OUTPUT

`HJ_2026100004_STABLEFORD_MONTE_CARLO_V1_RESULTS.json`의 `players`(108행)에
다음을 전부 기록: player_code/player_name/official_sponsor/nationality/
v1_pre_event_rank/data_status/prior_source/sample_rounds/sample_holes/
category_probabilities(6개)/expected_points_per_hole/expected_72_hole_
points/median_final_points/p10_final_points/p90_final_points/stddev_
final_points/make_cut_pct/top20_pct/top10_pct/top5_pct/win_pct.
DATA_LIMITED 선수는 `data_status`/`prior_source` 필드로 명확히 표시된다
(별도 억제·숨김 없음 — 지시사항 8번대로 "표시"했지 "제외"하지 않음).

## 9. FIRST REPORT — V1 vs MC 비교

같은 파일의 `top20_by_win_probability`, `top20_by_v1_pre_event_rank`,
`v1_vs_mc_rank_movers`(|순위 변화| 내림차순, DATA_LIMITED_NO_PRIOR_DATA
2명은 V1 순위 자체가 없으므로 이 비교에서 제외)를 참조. 최상위권(V1 #1-8)은
MC에서도 거의 그대로 유지되며, 중하위권에서 ±7~19위 수준의 실질적 재배치가
나타난다 — Red Team 보고서에서 구체적 사례와 근거로 분석.

## 10. VALIDATION — 결과

모든 항목 PASS (근거는 `230_hj_2026_stableford_monte_carlo.py`의 실행 로그
+ `HJ_2026100004_STABLEFORD_MONTE_CARLO_V1_REPRODUCIBILITY.json`):

| 체크 | 결과 |
|---|---|
| probability vector 합 = 1.0 (전 선수) | PASS (`validate_probability_vectors`) |
| 공식 scoring 정확 | PASS (`validate_scoring_table`) |
| 108명 field identity 정확, 중복 0 | PASS (`validate_field_identity`) |
| target leakage = 0 | PASS (`validate_target_leakage`) |
| 60,000회 정확 | PASS (`SimulationConfig.n_sims=60000`, 결과 배열 shape로 확인) |
| CUT 상위 60+동점 정확 | PASS (`validate_cut_rule`) |
| 불가능한 점수/결과 없음 | PASS (`validate_no_impossible_outcome`) |
| 선수 중복 없음 | PASS (`validate_field_identity`) |
| 모든 시뮬레이션 점수가 공식 scoring에서 유도 가능 | PASS (라운드 점수 = multinomial count · POINTS_VECTOR, 다른 경로 없음) |
| seed 고정 및 report 기록 | PASS (seed=`20261007`, `HJ_2026100004_STABLEFORD_MONTE_CARLO_V1_REPRODUCIBILITY.json`에 기록) |
| 동일 seed 재실행 재현성 | **PASS, bit-identical** (`same_seed_rerun_bit_identical: true`) |
| 다른 seed 2개(20261008, 777) 민감도 | PASS — Top10-by-win 구성원 10/10 완전 동일, win% 최대 변화 0.21%p, 평균 변화 0.03%p 수준 |

## 13. WEBSITE — 변경 없음

이번 턴에서 `docs/` 아래 어떤 파일도 수정하지 않았다(아래 커밋 diff로
확인 가능). HOME/PRE의 V1 사전평가 순위는 그대로다. 이 실험 결과를 public
"우승확률"로 배포할지는 Red Team 보고서의 VERDICT에서 별도로 판단한다.
