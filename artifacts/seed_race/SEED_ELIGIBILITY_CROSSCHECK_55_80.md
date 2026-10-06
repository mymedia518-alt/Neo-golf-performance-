# 55~80위 2027 참가자격 교차검증 — v2 (OFFICIAL EVIDENCE 반영, 여전히 전원 GROUP C)

> **[UPDATE LOG]** v1(`f529145`)은 55~80위 26명 전원을 "아무 근거 없음"으로 GROUP C 처리했다. 이번 턴에 사용자가 klpga.co.kr 공식 참가자격 페이지 3개를 직접 열람해 relay한 구체적 사례(OFFICIAL EVIDENCE 1/2/3)를 받아 반영했다 — **8명의 "2026 entry category"를 OBSERVED로 채웠다.** 단, 사용자 지시대로 **이것만으로 어떤 선수도 GROUP A/B로 옮기지 않았다** — 2026 entry category는 "왜 지금 뛰고 있는가"일 뿐 "2027에도 자격이 있는가"의 답이 아니기 때문이다. **26명 전원 여전히 GROUP C.**

**지시**: "[SEED ELIGIBILITY — OFFICIAL EVIDENCE RELAY]" — `f529145`의 "전원 GROUP C"를 그 자체로 최종 결론 삼지 말고, 사용자가 relay한 공식 증거를 CSV에 반영 + OBSERVED/RULE-CONFIRMED 분리 + 그룹 정의 재정의.

---

## 1. 이 턴에 한 일 요약

1. `klpga.co.kr`(www 없는 버전 포함) 재접속 시도 — **다시 403 확인**(아래 2번).
2. 사용자가 relay한 OFFICIAL EVIDENCE 1/2/3을 그대로 기록(아래 3번) — **내가 직접 그 페이지를 열어 확인한 것이 아니라, 사용자가 공식 URL에서 본 내용을 전달받은 것**임을 명시.
3. OFFICIAL EVIDENCE 1/2에 나온 10명(고지우·김민별·고지원·김민선7·김민솔·김민주·김수지·박보겸·서교림·성유진)을 공식 상금순위 데이터와 대조 → **전원 1~41위, 55~80위 구간 밖.** 즉 이 10명의 우승 이력 사례는 "일반대회/메이저 우승자 자격이 단순 1년이 아니라는 것을 보여주는 일반 정황 증거"일 뿐, 55~80위 26명 개개인의 데이터가 아니다.
4. OFFICIAL EVIDENCE 3에 나온 8명(김새로미·김소정·안재희·김우정·유지나·김나현2·김서윤2·손예빈)은 전부 55~80위 구간 안에 있음을 확인 → `eligibility_crosscheck_55_80.csv`의 **`OFFICIAL_2026_ENTRY_CATEGORY`** 열에 OBSERVED로 기록.
5. 그룹 정의를 사용자 지시대로 재정의(아래 5번) — **entry category를 알았다고 자동으로 C→A/B 이동하지 않음.**

---

## 2. KLPGA 재접속 재시도 — 다시 차단 확인

```
$ curl https://klpga.co.kr/web/tourInfo/entry?gameCode=2026040002
curl: (56) CONNECT tunnel failed, response 403
klpga.co.kr:443 — connect_rejected (organization policy)

WebFetch(url="https://klpga.co.kr/web/tourInfo/entry?gameCode=2026040002", ...)
→ {"error_type":"EGRESS_BLOCKED","domain":"klpga.co.kr", ...}
```

`www.klpga.co.kr`뿐 아니라 `klpga.co.kr`(서브도메인 없는 버전)도 동일하게 차단된다 — 이 컨테이너에서는 어떤 경로로도 klpga.co.kr에 직접 접근할 수 없다. **이하 OFFICIAL EVIDENCE는 전부 사용자가 자신의 환경에서 직접 열람해 relay한 것이며, 나는 그 페이지를 직접 열어 재확인하지 못했다.** 이 구분(OBSERVED = 사용자 relay, 독립 재확인 불가 / RULE-CONFIRMED = 규정 원문으로 확정)을 모든 표기에서 유지한다.

---

## 3. 사용자가 relay한 OFFICIAL EVIDENCE (그대로 기록)

### OFFICIAL EVIDENCE 1 — 2026 참가자격 페이지 (`gameCode=2026040002`)

| 선수 | 현재순위(공식) | relay된 사례 |
|---|---|---|
| 고지우 | 21위 | 2024 일반대회 우승자 |
| 김민별 | 41위 | 2024 일반대회 우승자 |
| 고지원 | 17위 | 2025 일반대회 우승자 |
| 김민선7 | 3위 | 2025 일반대회 우승자 |
| 김민솔 | 1위 | 2025 일반대회 우승자 |
| 김민주 | 10위 | 2025 일반대회 우승자 |
| 김수지 | 20위 | 2023 메이저대회 우승자 |

### OFFICIAL EVIDENCE 2 — 2025 참가자격 페이지 (`gameCode=2025100012`)

| 선수 | relay된 사례 |
|---|---|
| 고지우 | 2023 일반대회 우승자 |
| 김민별 | 2024 일반대회 우승자 |
| 김수지 | 2023 메이저대회 우승자 |

**이 10명 전원 55~80위 구간 밖(1~41위)** — 공식 상금순위 데이터(`official_money_rank_2026-10-06_full.json`)로 대조 확인. 따라서 이 두 EVIDENCE는 55~80위 26명 개개인의 직접 증거가 아니라, **"일반대회 우승자 자격이 우승 다음 시즌에만 존재하는 단순 1년 자격은 아니다"라는 패턴을 보여주는 정황 증거**로만 기록한다 — 예: 고지우는 2023 우승 사례(EVIDENCE 2)와 2024 우승 사례(EVIDENCE 1)가 각각 별도로 등장, 김민별도 2024 우승 사례가 2025·2026 두 페이지에 걸쳐 relay됨. **다만 이것이 "몇 년간 유효하다"는 정확한 기간을 확정해주지는 않는다 — 규정 원문 없이는 OBSERVED 패턴일 뿐 RULE-CONFIRMED가 아니다(사용자 지시 그대로 적용, 추론으로 기간을 확정하지 않음).**

### OFFICIAL EVIDENCE 3 — 2026 블루헤런 참가자격 페이지 (`gameCode` 미지정)

전체 선두권: 김민솔·박보겸·서교림(2026 메이저 우승자), 성유진(2025 메이저 우승자), 김수지(2023 메이저 우승자) — 전부 55~80위 밖.

**55~80위 구간 직접 해당 사례 (8명)**:

| 현재순위 | 선수 | OFFICIAL_2026_ENTRY_CATEGORY (OBSERVED) |
|---|---|---|
| 58 | 안재희 | 2025 드림투어 상금순위 20위 이내 |
| 60 | 김새로미 | 2025 드림투어 상금순위 20위 이내 |
| 64 | 김우정 | 2025 정규투어 상금순위 60위 이내 |
| 70 | 김소정 | 2025 드림투어 상금순위 20위 이내 |
| 71 | 김나현2 | 시드순위자 |
| 73 | 김서윤2 | 시드순위자 |
| 75 | 유지나 | 2025 정규투어 상금순위 60위 이내 |
| 77 | 손예빈 | 시드순위자 |

**중요 — 이것은 2026 ENTRY CATEGORY다.** "왜 2026시즌에 뛰고 있는가"에 대한 답이지 "2027에도 자격이 있는가"에 대한 답이 아니다. 자동 연장하지 않는다.

---

## 4. OBSERVED vs RULE-CONFIRMED — 용어 정의

| 구분 | 의미 | 이 문서에서의 예 |
|---|---|---|
| **OBSERVED** | 공식 페이지에서 특정 연도·특정 선수에 대해 실제로 표시된 사례를 확인(사용자 relay, 내가 독립 재확인은 못함) | "고지우 = 2024 일반대회 우승자로 2026 페이지에 표시됨" |
| **RULE-CONFIRMED** | 규정 원문(참가자격 규정/경기 운영 규정)으로 "몇 년간 유효한가", "중복 시 어떻게 처리하는가" 등이 명문으로 확정됨 | **아직 0건** — 원문을 확보한 적이 없음 |

OFFICIAL EVIDENCE 1/2가 보여주는 것은 OBSERVED 수준의 패턴(우승 다음 해를 넘어서도 "우승자" 표시가 유지되는 사례가 있다)이다. **"일반대회 우승자 자격 = N년"이라는 구체적 숫자는 RULE-CONFIRMED 아님 — 추론하지 않는다(사용자 지시).**

---

## 5. 55~80위 26명 — 업데이트된 교차검증 테이블

전체 18개 컬럼 CSV: `eligibility_crosscheck_55_80.csv`(신규 컬럼 `OFFICIAL_2026_ENTRY_CATEGORY`, `entry_category_evidence_type`, `entry_category_source` 추가). 아래는 핵심 요약 — **CSV에서 직접 재생성, 수기 입력 없음.**

| 현재순위 | 선수 | 현재상금(공식) | 2026_win(공식) | OFFICIAL_2026_ENTRY_CATEGORY | entry_category 근거 | known_2027_exemption | status |
|---|---|---|---|---|---|---|---|
| 55 | 마서영 | 164,138,333 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 56 | 지한솔 | 162,531,765 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 57 | 김지윤2 | 154,330,000 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 58 | 안재희 | 147,941,051 | 0 | 2025 드림투어 상금순위 20위 이내 | OBSERVED | UNKNOWN | GROUP C |
| 59 | 조아연 | 147,340,000 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 60 | 김새로미 | 147,312,262 | 0 | 2025 드림투어 상금순위 20위 이내 | OBSERVED | UNKNOWN | GROUP C |
| 61 | 한아름 | 146,194,643 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 62 | 한지원 | 144,250,000 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 63 | 최정원 | 142,181,250 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 64 | 김우정 | 140,947,857 | 0 | 2025 정규투어 상금순위 60위 이내 | OBSERVED | UNKNOWN | GROUP C |
| 65 | 마다솜 | 138,882,523 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 66 | 홍정민 | 134,968,333 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 67 | 최민경 | 129,244,285 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 68 | 박결 | 125,776,429 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 69 | 홍지원 | 125,517,143 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 70 | 김소정 | 123,000,000 | 0 | 2025 드림투어 상금순위 20위 이내 | OBSERVED | UNKNOWN | GROUP C |
| 71 | 김나현2 | 120,950,000 | 0 | 시드순위자 | OBSERVED | UNKNOWN | GROUP C |
| 72 | 이재윤 | 118,499,643 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 73 | 김서윤2 | 115,551,250 | 0 | 시드순위자 | OBSERVED | UNKNOWN | GROUP C |
| 74 | 김하은2 | 113,178,333 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 75 | 유지나 | 112,322,143 | 0 | 2025 정규투어 상금순위 60위 이내 | OBSERVED | UNKNOWN | GROUP C |
| 76 | 이주미 | 109,730,000 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 77 | 손예빈 | 96,270,000 | 0 | 시드순위자 | OBSERVED | UNKNOWN | GROUP C |
| 78 | 왕 즈쉬엔 | 94,440,715 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 79 | 박서현 | 94,024,643 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 80 | 현세린 | 93,047,500 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |

win-history 컬럼들(2024_win/2025_win/major_win_year 등)은 **이 26명 중 누구에 대해서도 아직 증거가 없어 전부 UNKNOWN 그대로** — OFFICIAL EVIDENCE 1/2가 보여준 우승자들은 전부 이 26명 밖의 다른 선수였기 때문(3번 참조).

---

## 6. 그룹 정의 재정의 (사용자 지시 그대로) 및 적용 결과

> A = 공식 근거상 2027 Top60이 필요한 것으로 확인
> B = 공식 근거상 Top60 밖이어도 2027 정규투어 자격 확보
> C = 아직 2027 자격 판정 불가능
> 현재 참가자격을 알게 됐다고 C→A/B로 자동 이동하지 않는다.

**적용 결과**:

- **A: 0명.** 어떤 선수에 대해서도 "2027에 다른 경로가 전혀 없다"는 것이 공식적으로 확인된 적이 없다 — 8명의 2026 entry category를 알아도, 그들이 2027에 Top60 외에 다른 자격(예: 2026시즌 중 우승, 드림투어 2026 성적 등)을 얻을 가능성은 여전히 미확인이므로 "Top60이 필요하다"고 단정할 수 없다.
- **B: 0명.** `known_2027_exemption`이 CONFIRMED인 선수가 없다. 8명의 OBSERVED 2026 entry category는 **2026년 자격이지 2027년 자격이 아니므로** B의 근거가 될 수 없다(사용자가 명시적으로 금지한 자동 연장에 해당).
- **C: 26명 전원.** 8명은 "2026 entry category가 OBSERVED로 확인됨"이라는 추가 정보가 붙은 채로 C에 남고, 나머지 18명은 이전과 동일하게 아무 정보 없이 C에 남는다.

---

## 7. 다음 최우선 작업 (사용자 지시) — 아직 수행 못함

사용자가 지정한 다음 우선순위: **55~80위의 2024/2025/2026 정규투어 우승 이력을 공식 대회 결과·참가자격 페이지와 교차해서 찾는 것** (일반대회 우승자/메이저 우승자/우승연도/2027까지 효력 지속 여부).

**이번 턴에는 수행하지 못했다** — OFFICIAL EVIDENCE 1/2에서 relay받은 우승자 10명이 전부 이 26명 밖이었고(3번), klpga.co.kr은 여전히 직접 접근 불가(2번)이기 때문이다. 이 작업을 진행하려면 다음 중 하나가 필요하다:

1. 55~80위 26명 각각의 "2026 참가자격 페이지"(`gameCode=2026040002` 또는 동일 선수 명단이 있는 다른 공식 페이지)에 **일반대회/메이저 우승자**로 표시된 사람이 있는지 — 있다면 몇 년도 우승인지. (지금까지 확인된 8명은 전부 "우승자" 카테고리가 아니라 드림투어/정규투어 Top60/시드순위자였다 — 즉 **지금까지 relay된 증거만으로는 이 26명 중 2024~2026 우승자가 1명도 없다.** 이것도 기록해 둔다: 이는 "없다고 확인됨"이 아니라 "아직 못 봤다"는 뜻이다.)
2. 2024/2025/2026 KLPGA 정규투어 대회별 공식 결과(우승자 명단)를 이 26명 이름과 대조.

사용자가 추가로 relay해 주면 즉시 반영한다.

---

## 8. DEPLOY 상태

**HOLD 유지.** 8명의 2026 entry category가 밝혀졌지만, 이는 "왜 2026에 뛰고 있는가"일 뿐 "2027 자격이 있는가"와는 무관하다 — 그룹 분류는 전원 GROUP C로 변함없다. `SEED_ELIGIBILITY_GAP.md`, `eligibility_crosscheck_55_80.csv`와 함께 참조.
