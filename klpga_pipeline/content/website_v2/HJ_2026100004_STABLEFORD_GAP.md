# HJ중공업·동부건설 챔피언십 (gameCode 2026100004) — Stableford PRE-TOURNAMENT BUILD 보고

기준: `neo-website-v2` 브랜치, `docs/`는 이번 턴에 전혀 건드리지 않음(지시 그대로 — "아직
건드리지 않는다").

> **검증: FAIL (정확히는 대부분 BLOCKED).** 공식 대회 기본 정보(일정·코스·총상금·배점표)는
> 사용자 relay로 확정했다. 그러나 Monte Carlo를 돌리기 위해 필요한 모든 실제 데이터
> (출전선수 명단, 선수별 Eagle/Birdie/Par/Bogey/Double+ 비율, 18홀 전체 par/yardage,
> 과거 변형 스테이블포드 대회 결과)는 이번 턴에 단 하나도 relay되지 않았다. Claude의
> klpga.co.kr/data.klpga.co.kr 접근은 이번 턴에도 재시도 후 재차 차단(curl + WebFetch 둘 다
> `EGRESS_BLOCKED`) — 이 세션 전체에서 단 한 번도 뚫린 적이 없다는 기존 결론과 동일.

---

## 1. 공식 데이터 수집 — 부분 확정, 핵심 블로커

**확정(OBSERVED, 사용자 relay, 출처 `https://data.klpga.co.kr/pressn_detail.jsp?Rownum=1&pageNum=1&sn=131870`)**:
- gameCode `2026100004`, 일정 2026-10-08~10-11
- 코스: 에이원CC 남(OUT)·서(IN), 파72·6,504야드
- 총상금 10억원, 우승상금 1억8천만원
- 경기방식: 변형 스테이블포드 — 알바트로스 +8 / 이글 +5 / 버디 +2 / 파 0 / 보기 -1 / 더블보기 이하 -3
- 주요 승부처로 지목된 홀(정성적 설명만, 홀별 정확한 수치 아님): 파5 3·9·13·15번, 파3 17번

→ `klpga_pipeline/content/website_v2/2026100004_TOURNAMENT_INFO.json`,
`OFFICIAL_KLPGA_SCHEDULE.json`에 반영.

**BLOCKED**: 출전선수 전체 명단, 조편성. "현재 repo의 오래된 entry를 재사용하지 않는다"는
지시를 지키려면 애초에 공식 출전자 명단 자체가 있어야 하는데 이번 턴에 전달받지 못했다.

---

## 2. 에이원CC 코스 분석 — 18홀 중 13홀 미확보

전달받은 것: 코스 레벨 합계(파72/6,504yd)와 5개 홀(파5 4개 + 파3 1개)의 *역할 설명*뿐 —
`hole / par / yardage` 18행 전체 표는 받지 못했다. 나머지 13개 홀의 par/yardage를
**추정하여 채우지 않았다**(지시 "추정해서 채우지 않는다" 그대로 적용). 5개 핵심 홀도
"공격적 세팅"이라는 KLPGA 설명을 특정 선수 유형의 유불리로 **자동 해석하지 않았다** —
`2026100004_TOURNAMENT_INFO.json`의 `official_key_holes_as_described`에 이 경고를
명시적으로 기록.

---

## 3. 선수별 Stableford 원자료 — 0명 확보

Eagle+%/Birdie%/Par%/Bogey%/Double+%(전체 및 파3/파4/파5 분리), 최근 5·10개 대회
변화 — 이번 세션(이 브랜치와 `klpga-tournament-data-collection-k47i28` 브랜치 양쪽 모두)
전체에서 단 한 번도 이 수준의 mainRecord 데이터가 확보된 적이 없다. 이번 턴에도
relay되지 않았다. **0명.**

---

## 4. Stableford 기대점수 — 공식만 구현 완료(실행 가능, 데이터만 없음)

`klpga_pipeline/src/klpga/website_v2/stableford_scoring.py` — 공식 배점표 그대로
`8×P(Albatross) + 5×P(Eagle) + 2×P(Birdie) - P(Bogey) - 3×P(Double+)`를 구현했다.
**이것이 이번 턴에 유일하게 "실제로 완성되고 실행 가능한" 산출물**이다(데이터 없이도
순수 수식이라 구현 가능했음). 분산(`variance_points`)도 평균과 별도로 보존 — "평균만
계산하지 말고 분산도 보존" 지시 충족. 18홀 합산(`expected_round_points`)도 구현.
**선수별 실제 확률을 이 함수에 넣을 입력값이 없다**(3절 참조) — 함수 자체는 테스트 14개
전부 PASS.

---

## 5. 과거 블라인드 검증 — BLOCKED (가장 중요한 단계인데 가장 막혀 있음)

`klpga_pipeline/src/klpga/website_v2/stableford_backtest.py` — 가드 구조만 구현, **실행
불가**. 필요하지만 없는 것:
1. "과거 이 대회"가 정확히 어느 대회(연도/gameCode)인지조차 특정되지 않음 — 과거 변형
   스테이블포드 결과 0건.
2. 그 대회 직전까지의 선수 실제 기록(선수별 par별 성적) — 0건.
3. 익산CC(과거 코스) 코스효과 데이터 — 0건. "과거 코스는 익산CC이고 2026은 에이원CC이므로
   과거 코스 효과를 2026에 그대로 이식하지 않는다"는 지시를 지키려면 애초에 익산CC
   코스효과 자체를 알아야 하는데, 그 데이터가 없다.

`run_blind_backtest()`는 `confirm_real_data` 플래그와 실데이터 존재 여부를 둘 다 확인해
**무조건 거부**하도록 가드돼 있다(테스트로 재확인).

---

## 6. 기존 NEO 대비 비교 — 수행 불가

5절의 backtest가 PASS해야 "왜 올라갔는지"를 실제 데이터로 설명할 근거가 생긴다. 지금은
비교할 Stableford 평가 자체가 없다. **0명 비교.**

---

## 7. Monte Carlo — BLOCKED, 실행하지 않음

`klpga_pipeline/src/klpga/website_v2/stableford_monte_carlo.py` — 가드만 구현.
요구 조건(출전자 명단 ≥90명, 선수별 outcome rate ≥90명, 18홀 전체 코스표, backtest
PASS, 60,000회 이상) 중 **단 하나도 충족되지 않아 실행 자체를 거부**한다(테스트로 확인).
30k/60k/100k convergence 비교도 당연히 수행하지 않았다 — 비교할 결과 자체가 없다.

---

## 8. Red Team — 구조적으로 확인 가능한 4개만 실제 실행, 나머지 3개는 정직하게 BLOCKED

`klpga_pipeline/src/klpga/website_v2/stableford_redteam.py` — 실제로 돌려 PASS/FAIL/BLOCKED을
코드로 산출(하드코딩/사후 날조 아님):

| 항목 | 결과 | 근거 |
|---|---|---|
| 기존 스트로크플레이 모델 재사용 여부 | **PASS** | AST로 stableford_*.py 전체 import 검사, stroke-play 모델(neo_win/r1_live_probability/seedrace) import 0건 |
| Birdie% 과대평가 여부 | BLOCKED | 실제 데이터 없음 |
| Double+ 꼬리위험 반영 여부 | **PASS** | `variance_points()`가 double_or_worse 항을 포함한 2차 모멘트로 분산 계산(평균으로 축소 안 함) |
| 파5 4개 홀 효과 과대평가 여부 | BLOCKED | 실제 데이터 없음 |
| 2025 김민솔 우승 사후인지 여부 | **PASS** | 전체 파일에 "김민솔" 하드코딩 0건(체커 자신 제외) |
| 익산CC→에이원CC 코스효과 이식 여부 | **PASS** | 실제 적용 모듈(scoring/monte_carlo)에 익산CC 언급 0건 — 애초에 코스효과 로직 자체가 구현돼 있지 않음 |
| 미래 데이터 leakage 여부 | BLOCKED | backtest가 실행된 적이 없어 확인할 대상이 없음 |

**4 PASS / 0 FAIL / 3 BLOCKED.** FAIL은 없지만 BLOCKED가 있고 애초에 공개할 확률이
존재하지 않으므로 **PUBLIC 공개는 여전히 불가**("확률 검증 없으면 PUBLIC 금지" 그대로 적용).

---

## 9. 홈페이지 — 손대지 않음

`docs/`(neo-website-v2 공개 산출물) 관련 파일은 이번 턴에 0바이트도 수정하지 않았다
(`git status`로 확인). 검증이 끝나지 않았으므로 HJ PRE 페이지에 반영할 결과 자체가 없다.

---

## 10. 다음 단계 (이 블로커를 풀려면)

가장 효과가 큰 순서:
1. 2026100004 공식 출전선수 명단 + 조편성
2. 선수별(특히 출전 예정자) 2026시즌 Eagle/Birdie/Par/Bogey/Double+ 비율(가능하면 파3/파4/파5 분리) + 최근 5·10개 대회
3. "과거 이 대회"의 정확한 식별(연도/gameCode) + 그 대회의 실제 변형 스테이블포드 결과
4. 에이원CC 나머지 13홀의 par/yardage
5. 익산CC 코스효과를 추정할 수 있는 근거(가능하면)

---

```
[NEO HJ 2026 — STABLEFORD PRE-TOURNAMENT BUILD — RESULT]

검증 PASS/FAIL: FAIL (Red Team 구조 체크 4 PASS/0 FAIL/3 BLOCKED, 그러나 Monte Carlo 자체가
  BLOCKED라 "검증을 통과한 확률"이 존재하지 않음 -- 종합 판정 FAIL)
출전자 수: 미확보 (공식 명단 0건)
분석 가능 선수 수: 0명 (선수별 Eagle/Birdie/Par/Bogey/Double+ 데이터 0건)
과거 검증 성능: 수행 안 됨 (backtest BLOCKED -- 과거 대회 식별조차 안 됨)
Stableford 적합도 Top10: 없음 (입력 데이터 없음)
우승확률 Top10: 없음 (Monte Carlo 미실행)
기존 NEO 대비 가장 크게 상승/하락한 선수: 없음 (비교할 대상 없음)
데이터 부족 선수: 전원 (공식 명단조차 없어 "몇 명"이라고 말할 수도 없음)
공개 가능 여부: 불가 (DEPLOY: HOLD)

이번 턴에 실제로 완성된 것:
- 공식 대회 기본 정보 확정 (일정/코스/상금/배점표) -- JSON 2개
- Stableford 기대점수/분산 공식 구현 + 테스트 14/14 PASS (유일하게 데이터 없이 완성 가능했던 부분)
- Backtest/Monte Carlo 가드 구조 구현 (허위 데이터로 실행되지 않도록 차단, 테스트로 거부 확인)
- Red Team 체커 실제 실행 가능한 코드로 구현 (4 PASS/0 FAIL/3 BLOCKED, 전부 날조 아님)
- docs/ 0바이트 변경 (지시대로 아직 건드리지 않음)

DEPLOY: HOLD
```
