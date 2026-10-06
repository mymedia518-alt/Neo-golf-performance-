# HJ중공업·동부건설 챔피언십 (gameCode 2026100004) — Stableford PRE-TOURNAMENT BUILD 보고 v2

기준: commit `409df41`(v1) 이후. `docs/`는 이번 턴에도 전혀 건드리지 않음.

> **검증: 여전히 FAIL(대부분 BLOCKED), 그러나 대회 식별 레벨의 블로커는 실제로 풀렸다.**
> 사용자가 외부에서 확인한 공식 데이터(출전 108명, 4라운드/72홀, 컷 규정, 과거 5개 대회
> 우승자)로 "과거 이 대회조차 특정 안 됨" 블로커를 해소했고, **이 repo 자신의 기존
> 작업(`docs/SITE_STRUCTURE_TODO.md`)이 독립적으로 그 식별을 교차검증**한다. 하지만
> 실제 Monte Carlo를 돌리는 데 필요한 "전체 필드 선수별 데이터"는 여전히 0건이고,
> **이 repo 자신의 기존 실측 작업이 이것이 이 세션의 네트워크 차단과 별개로 구조적으로도
> 막혀 있었다는 것까지 미리 확인해 놓았다.**

---

## GAP MATRIX (사용자 요청 형식)

| 항목 | 상태 |
|---|---|
| Tournament identification | **RESOLVED** |
| Field size | **RESOLVED** (108명) |
| Cut rule | **RESOLVED** (2R 종료 후 공동 60위까지) |
| Historical winners/results | **PARTIALLY RESOLVED** (우승자 요약 통계만, 전체 필드 아님) |
| Full 108-player entry names | 여전히 미확보 |
| Player hole-outcome distributions | 여전히 미확보 — **게다가 구조적으로도 막혀 있음(아래 참조)** |
| Historical pre-event player features | 여전히 미확보 — 같은 구조적 이유 |

---

## 1. Tournament identification — RESOLVED, repo 자체 교차검증까지 확보

사용자가 relay한 대로 "과거 이 대회"는 2026100004 자신의 과거 이름이다. 이번 턴에
`klpga_pipeline/docs/SITE_STRUCTURE_TODO.md`를 전수 검색해 **이 repo가 전혀 다른 작업
(2026-08-24, 실제 Windows PC에서 실행한 100개 대회 라이브 실행)에서 이미 독립적으로
확인해 둔 사실**을 찾았다:

> `gameMethod="2"`(Modified Stableford)인 KLPGA 대회 3개가 전부 **"동부건설 ·
> 한국토지신탁 챔피언십"**이라는 이름으로 적중했다 — `gameCode` 2023100002, 2024100009,
> 2025100001.

"동부건설"은 현재 대회명 "HJ중공업·**동부건설**" 챔피언십의 그 동부건설이다. 사용자가
relay한 2023/2024/2025 연도가 이 3개 gameCode와 정확히 일치한다 — **같은 대회라는 것을
사용자 relay와 repo 자체 기록 양쪽에서 교차확인**했다(`test_known_historical_winner_
gamecodes_match_this_repos_own_prior_confirmation`로 고정).

2021/2022 gameCode는 그 100개 대회 샘플에 없었다(부재 확인이 아니라 단지 그 표본에
없었을 뿐).

→ `2026100004_TOURNAMENT_INFO.json`의 `historical_identity`,
`klpga_pipeline/src/klpga/website_v2/stableford_backtest.py`의
`KNOWN_HISTORICAL_WINNER_SUMMARIES`에 반영.

---

## 2. Field size / Format / Cut rule — RESOLVED

- 출전 108명 (OBSERVED, 사용자가 KLPGA 현재 메인 + 대회 공식 홈페이지 양쪽에서 확인)
- 4라운드 72홀
- 2R 종료 후 공동 60위까지 본선 진출(컷)

→ `2026100004_TOURNAMENT_INFO.json`에 `field_size`, `rounds_scheduled`, `holes_total`,
`cut_rule` 필드로 반영. `stableford_monte_carlo.py`의 `MIN_FIELD_SIZE=90` 가드를
이제 만족하는 숫자라는 것도 확인(그러나 숫자만 알지 **명단 자체는 여전히 없음** — 아래
참조).

---

## 3. Historical winners/results — PARTIALLY RESOLVED (경고: 우승자만, 전체 필드 아님)

relay된 5개 대회 결과:

| 연도 | gameCode | 우승자 | 최종 | 라운드별 | 버디 |
|---|---|---|---|---|---|
| 2021 | 미확인 | 이정민 | +51 | — | 26 |
| 2022 | 미확인 | 이가영 | +49 | — | — |
| 2023 | 2023100002 | 방신실 | +43 | 10/5/15/13 | 21 + 이글1 |
| 2024 | 2024100009 | 김민별 | +49 | 13/8/10/18 | 26 |
| 2025 | 2025100001 | 김민솔 | +51 | 7/14/14/16 | 27 |

**자기정합성 확인(코드로 재검증)**: 라운드별 점수 합이 전부 최종 스코어와 정확히 일치
(10+5+15+13=43, 13+8+10+18=49, 7+14+14+16=51) — `test_known_historical_winner_round_
splits_are_self_consistent`로 고정.

**이것이 왜 "PARTIALLY"인가**: 이건 **우승자 1명씩, 5개 대회 분**이다. 2위~108위 데이터는
0건. "검증 관찰값일 뿐, 모델 상수로 맞추지 않는다"는 사용자 지시를 그대로 지켰다 —
`stableford_backtest.py`는 이 5개 값을 `KNOWN_HISTORICAL_WINNER_SUMMARIES`라는 별도
상수로 명확히 분리해 저장했고, 실제 예측을 계산하는 `stableford_scoring.py`/
`stableford_monte_carlo.py`에는 이 이름들이 전혀 등장하지 않는다(Red Team 체크로 확인).

---

## 4. 가장 중요한 발견 — "전체 필드 데이터"는 네트워크 차단과 별개로 구조적으로도 막혀 있다

`klpga_pipeline/docs/SITE_STRUCTURE_TODO.md` 1절을 다시 읽다가 발견:

> 이 repo의 `roundLeaderboard` 수집기(실제 대회별·라운드별 전체 선수 순위표를 가져오는
> 핵심 엔드포인트)가 **2026-08-24, 실제 Windows PC에서 진짜 KLPGA 엔드포인트에 대해
> `round=1..8` 전수 프로빙**을 통해, `gameMethod="2"`(Modified Stableford) 대회 3개
> (2023100002, 2024100009, 2025100001 — 바로 이 시리즈) **전부에서 매 라운드마다 선수
> row 0건**을 반환한다는 것을 이미 확인해 놓았다. "더 좁은 라운드 범위였을 뿐"이 아니라
> "이 엔드포인트 자체가 이 포맷의 데이터를 제공하지 않는다"로 명시적으로 결론 내려져 있다.

**의미**: Claude의 klpga.co.kr 접근이 설령 이 순간 뚫린다 해도, 이 repo가 지금 쓰고 있는
수집 방식으로는 애초에 이 대회 시리즈의 선수별·라운드별 데이터를 가져올 수 없다 —
이건 "접근 차단" 문제가 아니라 "이 엔드포인트가 이 포맷을 안 준다"는 **별도의, 더 근본적인
블로커**다. 공식 출전자 명단 엔드포인트(`getGameList`)나 공식 대회 홈페이지의 세부 기록
페이지(사용자가 이번에 "대회 공식 홈페이지"에서 라운드별 수치를 relay한 바로 그 경로)는
`roundLeaderboard`와 다른 경로일 가능성이 높다 — **다음 단계에서 가장 먼저 확인해야 할
것은 "어느 엔드포인트가 Modified Stableford 데이터를 실제로 주는가"다.**

---

## 5. 로컬 데이터 재탐색 — 전부 재확인, 전부 비어 있음

지시대로 Monte Carlo로 바로 가지 않고 기존 로컬 데이터부터 검색했다:

- `klpga_pipeline/data/klpga.sqlite`(git에는 없지만 디스크에 136KB로 실존) — 스키마 전부
  확인(`tournament_master`, `player_event`, `player_round`, `player_stats_snapshot`,
  `tournament_entry`, `official_metric_value`): **전부 0행**. `collection_runs` 테이블의
  4건 기록 전부 동일한 `klpga.co.kr` 프록시 403 오류(가장 최근 2026-10-01 11:23) — 이
  정확한 세션 환경에서 이미 여러 번 실시간 재시도했었고 전부 같은 이유로 실패했다는 뜻.
- `klpga_pipeline/raw/` — 디렉터리 자체가 없음(오프라인 폴백용 캡처 파일도 없음).
- 저장소 전체에서 "2023100002"/"2024100009"/"2025100001" 검색 — `SITE_STRUCTURE_TODO.md`
  문서 언급 1곳 외에는 실제 데이터 파일 0건.

**찾은 것(데이터는 아니지만 재사용 가능한 자산)**: `klpga_pipeline/src/klpga/backtest/`
— 이 repo의 기존 **포맷 중립적**(stroke-play 모델이 아닌, 순수 point-in-time 날짜
정합성 유틸리티) walk-forward 인프라:
- `temporal.py` — `is_strictly_before()`: 리크 방지용 날짜 비교, 이미 레드팀 요구사항으로
  검증된 유틸
- `historical_field.py`, `point_in_time_features.py`, `walk_forward.py` — 전부
  `player_event`/`player_round`에 의존(현재 0행이라 당장은 못 씀)

**이번 턴에 실제로 한 일**: `stableford_backtest.py`가 `temporal.is_strictly_before`를
실제로 import해서 `pre_cutoff_player_records`의 날짜를 검사하도록 연결했다 — 합성 리크
사례(대상 대회 당일 날짜의 레코드)를 실제로 거부하는 것을 테스트로 확인
(`test_backtest_detects_future_data_leakage_even_with_confirm_and_nonempty_data`).
이것은 모델 재사용이 아니라 순수 인프라 재사용이라 Red Team 항목 1("기존 스트로크플레이
모델 재사용 여부")에 저촉되지 않는다.

---

## 6. Red Team — v1의 4 PASS에서 5 PASS로, FAIL 0 유지

| 항목 | v1 | v2 |
|---|---|---|
| 기존 스트로크플레이 모델 재사용 여부 | PASS | PASS |
| Birdie% 과대평가 여부 | BLOCKED | BLOCKED |
| Double+ 꼬리위험 반영 여부 | PASS | PASS |
| 파5 4개 홀 효과 과대평가 여부 | BLOCKED | BLOCKED |
| 2025 우승자를 2026 예측 모델에 반영했는지 여부 | PASS | PASS (판정 기준 정교화 — 아래 참조) |
| 익산CC 코스효과를 에이원CC로 이식했는지 여부 | PASS | PASS |
| 미래 데이터 leakage 방지 메커니즘 존재 여부 | BLOCKED | **PASS (신규 — 실제 메커니즘 구현+테스트 확인)** |

**v1→v2 변경점 하나 설명**: `KNOWN_HISTORICAL_WINNER_SUMMARIES`에 "김민솔"을 OBSERVED
검증자료로 저장하자 기존의 단순 "이름이 어디에도 없어야 PASS" 체크가 FAIL로 바뀌었다 —
거짓 양성이었다. 체크를 "2026 예측을 실제로 계산하는 모듈(scoring/monte_carlo)에 이름이
있는가"로 정교화해 재확인: 그 두 모듈에는 없고, 과거 결과를 라벨 붙여 저장한
backtest 모듈에만 있다 — 의도된 용도 그대로. PASS로 복귀.

**TOTAL: 5 PASS / 0 FAIL / 2 BLOCKED.** FAIL은 없지만 BLOCKED가 남아 있고 Monte Carlo가
미실행이라 **PUBLIC 공개는 여전히 불가**.

---

## 7. 다음 단계 — 데이터 획득이 최우선, Monte Carlo 아님

가장 효과가 큰 순서:
1. **Modified Stableford 데이터를 실제로 제공하는 KLPGA 엔드포인트 특정** — `roundLeaderboard`가
   확인된 비작동 경로이므로, 사용자가 이번에 relay한 "대회 공식 홈페이지"의 라운드별 수치가
   어느 URL/엔드포인트에서 나왔는지가 다음으로 가장 중요한 정보다.
2. 2026100004 공식 출전 108명 명단 + 조편성(숫자는 확보, 명단은 미확보)
3. 위 엔드포인트가 특정되면: 2021~2025 5개 대회의 전체 필드(1~108위) 결과
4. 출전 예정 선수들의 2026시즌 Eagle/Birdie/Par/Bogey/Double+ 비율
5. 에이원CC 나머지 13홀 par/yardage

---

```
[NEO HJ 2026 — STABLEFORD PRE-TOURNAMENT BUILD — RESULT v2]

Continued from commit 409df41, not restarted.

GAP MATRIX:
  Tournament identification: RESOLVED (repo 자체 2026-08-24 실측 기록과 교차검증됨)
  Field size: RESOLVED (108명)
  Cut rule: RESOLVED (2R 후 공동60위)
  Historical winners/results: PARTIALLY RESOLVED (우승자 5명 요약값만, 전체 필드 아님)
  Full 108-player entry names: 여전히 미확보
  Player hole-outcome distributions: 여전히 미확보
  Historical pre-event player features: 여전히 미확보

핵심 신규 발견: roundLeaderboard 엔드포인트가 이 Stableford 대회 시리즈(2023100002/
  2024100009/2025100001) 전부에서 선수 row 0건을 반환한다는 것이 이 repo 자신의 2026-08-24
  실측(Windows PC, round=1..8 전수 프로빙)으로 이미 확인돼 있었다 -- 네트워크 차단과
  별개로 구조적 블로커. 다른 엔드포인트 특정이 다음 최우선 과제.

로컬 데이터 재탐색: klpga_pipeline/data/klpga.sqlite 전체 스키마 확인, 전부 0행
  (collection_runs 4건 전부 동일 프록시 403). raw/ 캡처 없음. 재사용 가능한 자산 발견:
  klpga.backtest.temporal(모델 아닌 순수 날짜유틸) -- stableford_backtest.py에 실제로
  연결해 리크 방지 메커니즘을 진짜로 구현(테스트로 거부 동작 확인).

Red Team: 5 PASS / 0 FAIL / 2 BLOCKED (v1 대비 +1 PASS, 거짓양성 1건 정교화로 재확인)

Monte Carlo guard: CLOSED 유지 (지시 그대로 -- 선수 필드/분포가 부족한 동안)

공개 가능 여부: 불가
docs/ 변경: 0바이트

다음 우선순위: ① Modified Stableford 데이터를 실제로 주는 KLPGA 엔드포인트 특정
  (가장 중요, 다른 모든 것의 전제조건) ② 108명 명단 ③ 위 엔드포인트로 과거 5개 대회
  전체 필드 ④ 선수별 Eagle/Birdie/Par/Bogey/Double+ ⑤ 에이원CC 13홀 추가

tests: 18/18 (신규 파일) + 62/62 (기존 아카이브) = 80/80 PASS
DEPLOY: HOLD
```
