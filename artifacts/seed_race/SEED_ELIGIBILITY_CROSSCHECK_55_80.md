# 55~80위 2027 참가자격 교차검증 — v3 (최근 정규투어 우승 이력 3건 CONFIRMED, 여전히 GROUP B 확정 0명)

> **[UPDATE LOG]**
> - v1(`f529145`): 55~80위 26명 전원 "아무 근거 없음"으로 GROUP C.
> - v2(`aa2d153`): 사용자 relay한 OFFICIAL EVIDENCE 1/2/3 반영, 8명의 2026 entry category를 OBSERVED로 채움. 자동 연장 없이 26명 전원 GROUP C 유지.
> - **v3(이 턴)**: 사용자가 KLPGA 공식 선수 프로필(`klpga.co.kr/web/profile/history?playerCode=...`)에서 직접 확인한 **최근 정규투어 우승 이력**을 relay — 지한솔(56위)·마다솜(65위)·홍정민(66위) 3명의 "최근 정규투어 우승 = CONFIRMED"를 CSV에 반영하고, 이 3명을 단순 UNKNOWN과 구별해 **GROUP C-WIN**으로 표시했다. **GROUP B로는 확정하지 않았다** — "최근 우승 확인"과 "그 우승이 2027까지 자격을 보장하는가"는 여전히 별개 질문이며, 후자는 규정 원문 없이는 RULE-CONFIRMED 아님.

**지시**: "[SEED ELIGIBILITY — CRITICAL OFFICIAL WIN HISTORY UPDATE]" — `aa2d153`의 "전원 GROUP C"를 최종 결론으로 쓰지 말고, 최근 정규투어 우승 이력을 CSV에 반영 + GROUP C-WIN 신설 + 절대 GROUP B 확정 금지 + 다음 우선순위(우승자 자격 유효기간 규정, 특히 홍정민의 2025 메이저 우승) 명시.

---

## 1. 이번 턴에 한 일

1. klpga.co.kr 재접속 재시도(curl + WebFetch, 선수 프로필 URL 직접) — **다시 403 확인**. 그래서 이번에도 전부 **OBSERVED**(사용자가 공식 프로필 페이지에서 직접 확인해 relay, Claude 독립 재확인 불가)로 기록.
2. relay받은 3명(지한솔·마다솜·홍정민)의 현재순위·선수코드를 공식 상금순위 데이터와 대조 — **전부 정확히 일치**(지한솔=56위/코드1521, 마다솜=65위/코드9401, 홍정민=66위/코드9750 — `seed_probability.csv`에 이미 있던 코드와 완전히 동일). 추가로 **2026_win=0**(기존에 이미 공식 확인된 값)과도 모순이 없음(relay된 우승은 전부 2023~2025년, 2026시즌 우승이 아니므로).
3. `eligibility_crosscheck_55_80.csv`에 7개 컬럼 추가: `recent_regular_tour_win`, `win_year`, `win_event`, `major_status`, `official_profile_evidence`, `possible_2027_exemption`, `rule_confirmation`.
4. 지한솔·마다솜·홍정민의 `status`를 `GROUP C-WIN: 최근 정규투어 우승 확인, 2027 exemption 유효기간 확인 대기`로 변경. **나머지 23명은 손대지 않음**(v2에서 확정한 8명의 2026 entry category, 15명의 순수 UNKNOWN 그대로 유지).

---

## 2. relay된 WIN HISTORY — OFFICIAL EVIDENCE (그대로 기록)

### 지한솔 (56위, 코드 1521)

- 정규투어 통산 우승 수: relay된 범위 내 1승 확인
- **2024-10-24~27 덕신EPC·서울경제 레이디스 클래식 우승**
- 메이저 여부: 명시 없음(일반대회로 취급)
- 출처: `https://klpga.co.kr/web/profile/history?playerCode=1521`

### 마다솜 (65위, 코드 9401)

- **정규투어 통산 4승**
- 2024-09-26~29 하나금융그룹 챔피언십 우승
- 2024-10-31~11-03 S-OIL 챔피언십 2024 우승
- 2024-11-08~10 SK텔레콤·SK쉴더스 챔피언십 2024 우승
- 2023 OK금융그룹 읏맨 오픈 우승
- 메이저 여부: 4승 전부 명시 없음(일반대회로 취급)
- 출처: `https://klpga.co.kr/web/profile/history?playerCode=9401`

### 홍정민 (66위, 코드 9750)

- **정규투어 통산 4승**
- **2025-05-01~04 크리스에프앤씨 제47회 KLPGA 챔피언십 우승 — KLPGA 공식 뉴스에서 "메이저 대회 우승"으로 명시**
- 2025-08-14~17 메디힐·한국일보 챔피언십 우승
- 2025-10-10~12 K-FOOD 놀부·화미 마스터즈 우승
- 출처: `https://klpga.co.kr/web/profile/history?playerCode=9750`

**홍정민은 이 구간에서 유일하게 "메이저대회 우승자" 지위가 relay된 사례이며, 그 우승이 2025년이라 2027시즌까지 이어지는지가 가장 임박한 질문이다 — 사용자가 지정한 최우선 확인 대상.**

### 참고 (55~80위 범위 밖, 45위 이상 확대 시) — CSV에는 추가하지 않음

사용자가 범위를 45위 이상까지 넓혔을 때 확인한 사례도 기록만 해 둔다(이 26명 테이블의 공식 scope 밖이므로 `eligibility_crosscheck_55_80.csv`에는 행을 추가하지 않았다):

- **배소현(47위, 코드8589)**: 2025 오로라월드 레이디스 챔피언십 우승, 2024 정규투어 3승.
- **정윤지(50위, 코드9820)**: 2025 Sh수협은행 MBN 여자오픈 우승.

(두 선수 모두 현재순위·코드가 공식 데이터와 일치함을 확인.)

---

## 3. CONFIRMED vs 아직 필요한 것 — 명확히 분리

| 구분 | 상태 |
|---|---|
| **RECENT REGULAR TOUR WIN = CONFIRMED** | 지한솔(2024)·마다솜(2023~2024, 4승)·홍정민(2025, 4승, 그중 1승 메이저) — 전부 OBSERVED(사용자가 공식 프로필에서 직접 확인해 relay, Claude 독립 재확인은 여전히 불가) |
| **WIN EXEMPTION VALID THROUGH 2027 = RULE CONFIRMATION 미완료** | 일반대회/메이저대회 우승자의 정규투어 출전자격이 정확히 몇 시즌 유효한지 규정 원문을 아직 확보하지 못함. 따라서 이 3명이 2027에도 자격이 있는지는 **여전히 UNKNOWN** |

**즉 "최근 우승 확인됨"(사실) ≠ "2027 자격 확보됨"(규정 해석) — 이 둘을 섞지 않는다.**

---

## 4. 55~80위 26명 — 업데이트된 테이블 (CSV에서 직접 재생성)

전체 25개 컬럼: `eligibility_crosscheck_55_80.csv`. 아래는 핵심 요약.

| 현재순위 | 선수 | 현재상금(공식) | recent_regular_tour_win | win_year | major_status | OFFICIAL_2026_ENTRY_CATEGORY | status |
|---|---|---|---|---|---|---|---|
| 55 | 마서영 | 164,138,333 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 56 | 지한솔 | 162,531,765 | CONFIRMED | 2024 | 일반대회 (메이저 명시 없음) | UNKNOWN | **GROUP C-WIN** |
| 57 | 김지윤2 | 154,330,000 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 58 | 안재희 | 147,941,051 | UNKNOWN | UNKNOWN | UNKNOWN | 2025 드림투어 상금순위 20위 이내 | GROUP C |
| 59 | 조아연 | 147,340,000 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 60 | 김새로미 | 147,312,262 | UNKNOWN | UNKNOWN | UNKNOWN | 2025 드림투어 상금순위 20위 이내 | GROUP C |
| 61 | 한아름 | 146,194,643 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 62 | 한지원 | 144,250,000 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 63 | 최정원 | 142,181,250 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 64 | 김우정 | 140,947,857 | UNKNOWN | UNKNOWN | UNKNOWN | 2025 정규투어 상금순위 60위 이내 | GROUP C |
| 65 | 마다솜 | 138,882,523 | CONFIRMED | 2024(3승)/2023(1승) 통산4승 | 전부 일반대회 (메이저 명시 없음) | UNKNOWN | **GROUP C-WIN** |
| 66 | 홍정민 | 134,968,333 | CONFIRMED | 2025(3승) 통산4승 | 혼합 — 2025 KLPGA 챔피언십 **메이저**(공식뉴스 명시), 나머지 일반 | UNKNOWN | **GROUP C-WIN** |
| 67 | 최민경 | 129,244,285 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 68 | 박결 | 125,776,429 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 69 | 홍지원 | 125,517,143 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 70 | 김소정 | 123,000,000 | UNKNOWN | UNKNOWN | UNKNOWN | 2025 드림투어 상금순위 20위 이내 | GROUP C |
| 71 | 김나현2 | 120,950,000 | UNKNOWN | UNKNOWN | UNKNOWN | 시드순위자 | GROUP C |
| 72 | 이재윤 | 118,499,643 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 73 | 김서윤2 | 115,551,250 | UNKNOWN | UNKNOWN | UNKNOWN | 시드순위자 | GROUP C |
| 74 | 김하은2 | 113,178,333 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 75 | 유지나 | 112,322,143 | UNKNOWN | UNKNOWN | UNKNOWN | 2025 정규투어 상금순위 60위 이내 | GROUP C |
| 76 | 이주미 | 109,730,000 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 77 | 손예빈 | 96,270,000 | UNKNOWN | UNKNOWN | UNKNOWN | 시드순위자 | GROUP C |
| 78 | 왕 즈쉬엔 | 94,440,715 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 79 | 박서현 | 94,024,643 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 80 | 현세린 | 93,047,500 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |

---

## 5. 그룹 분류 현황 (갱신)

- **A (Top60이 사실상 필요)**: 0명 — 변동 없음.
- **B (Top60 밖이어도 2027 자격 확보)**: **0명 — 변동 없음.** 지한솔·마다솜·홍정민의 최근 우승이 CONFIRMED여도, 그 우승이 2027까지 유효한지(RULE CONFIRMATION)가 없는 한 B로 옮기지 않는다 — 사용자가 명시적으로 금지.
- **C (일반)**: 15명 — 아무 추가 정보 없음.
- **C (2026 entry category OBSERVED)**: 8명 — 안재희·김새로미·김우정·김소정·김나현2·김서윤2·유지나·손예빈.
- **C-WIN (최근 정규투어 우승 CONFIRMED, 2027 exemption 대기)**: **3명 — 지한솔·마다솜·홍정민(신규).**

26 = 15 + 8 + 3, 전원 합쳐도 여전히 GROUP A/B 확정자는 0명이다.

---

## 6. 다음 최우선 작업 (사용자 지시 그대로) — 아직 미해결

> "일반대회 우승자 / 메이저대회 우승자의 정규투어 출전자격 유효기간" 공식 규정 확인. 특히 홍정민의 2025 메이저 우승자 자격이 2027 시즌에도 유효한지 최우선 확인.

이번 턴에 klpga.co.kr 재접속을 다시 시도했으나(프로필 페이지, 참가자격 페이지 둘 다) **여전히 403으로 차단**되어 이 규정 원문 자체는 확보하지 못했다. 이 질문에 답하려면 다음 중 하나가 필요하다:

1. KLPGA 공식 "참가자격 규정"/"경기 운영 규정" 원문 — 일반대회·메이저대회 우승자의 출전자격 유효기간을 명시한 조항.
2. 또는 **2027년도 참가자격 페이지가 이미 공개되어 있다면**, 그 페이지에 홍정민·마다솜·지한솔이 "우승자" 카테고리로 등재되어 있는지 직접 확인(가장 확실한 간접 증거 — 다음 시즌 페이지 자체가 "지금 이 선수가 우승자 자격으로 뛴다"를 보여주므로).
3. 과거 사례(예: 2023년에 우승한 선수가 2024, 2025 참가자격 페이지에 몇 번이나 "우승자"로 계속 등재됐는지 — OFFICIAL EVIDENCE 1/2에서 고지우·김민별이 이미 이런 패턴을 보였다. 이 패턴을 홍정민/마다솜/지한솔에게도 추적할 수 있는 자료가 있다면 RULE-CONFIRMED까지는 아니어도 OBSERVED 증거가 강해진다)

어느 것이든 relay해 주시면 즉시 반영한다.

---

## 7. DEPLOY 상태

**HOLD 유지.** 3명의 GROUP C-WIN 승격은 "최근 우승이 있다는 사실"을 반영한 것일 뿐, 이들이 2027에 Top60과 무관하게 뛸 수 있는지는 여전히 미확정이다. GROUP B가 1명도 없는 한, "상금순위 Top60 확률"과 "2027 KLPGA 출전자격"을 동일시할 수 없다는 `SEED_ELIGIBILITY_GAP.md`의 근거는 그대로 유지된다.
