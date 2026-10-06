# 55~80위 2027 참가자격 교차검증 — 결과: 전원 GROUP C (규정 확인 필요)

**지시**: "[SEED ELIGIBILITY — CONTINUE, DO NOT STOP]" — `553e437`의 DEPLOY HOLD 유지, 55~80위 26명에 대해 2026 참가자격 카테고리와 2024~2026 우승 이력을 전수 교차검증.

**결론을 먼저 밝힌다**: 이번 세션에서 실제로 확인할 수 있었던 것은 **"26명 전원 2026시즌 우승 0회(공식 확인)"** 하나뿐이다. 나머지 모든 항목(2026 출전 근거 카테고리, 2024/2025 우승 이력, 메이저 우승 연도, 2027 별도 자격 여부, 자격 만료 시점, 중복자 승계 규정)은 **이번 세션에서는 확인 불가능했다 — UNKNOWN으로 유지한다.** 그 결과 **26명 전원이 GROUP C(규정 확인 필요)** 다. A/B로 나눌 수 있는 근거가 아직 없다.

---

## 1. 실제로 시도한 것과 그 결과

### 1-1. KLPGA 공식 페이지 직접 조회 — 차단 확인

이번 턴에 `klpga.co.kr`로의 접속을 두 가지 경로로 다시 시도했다:

```
$ curl -sS -o /dev/null -w "HTTP %{http_code}\n" https://www.klpga.co.kr/web/index.do
curl: (56) CONNECT tunnel failed, response 403
[agent-proxy] www.klpga.co.kr:443 — connect_rejected (organization policy)
```

```
WebFetch(url="https://www.klpga.co.kr/web/intro/criteria.do", ...)
→ {"error_type":"EGRESS_BLOCKED","domain":"www.klpga.co.kr", ...}
```

**두 경로 모두 조직 정책(organization policy)으로 403 차단 — 이 컨테이너에서는 klpga.co.kr 접근이 원천적으로 불가능하다.** 이전 단계들(상금순위 페이지, 대회 상금분배표)도 전부 같은 이유로 막혀, 사용자가 직접 첨부/relay한 데이터로만 진행해 왔다. 이번 참가자격 규정도 같은 방식이 아니면 확인할 수 없다.

### 1-2. 로컬 저장소 데이터 확인 — 없음

| 확인한 위치 | 결과 |
|---|---|
| `klpga_pipeline/data/klpga.sqlite` | 스키마만 존재, 전 테이블 0행(`player_master`, `tournament_master`, `player_event` 등) |
| `klpga_pipeline/data/raw_cache/` | 빈 디렉터리 |
| `klpga_pipeline/predictions/` | 대회 1개(`2026080001`, KG 레이디스 오픈)뿐 — 시즌 전체 우승 이력 아님 |
| `neo_klpga_shot_source/derived_analysis/standings_RAW_READONLY.json`, `players_RAW_READONLY.json` | 특정 대회(`game_code`) 1개의 라운드별 데이터 — 다년도 우승 이력 아님 |

**이 저장소 어디에도 선수별 2024~2026 우승 이력이나 참가자격 카테고리 데이터가 없다.**

### 1-3. 웹 검색 — 공식 수준 근거 확보 실패

"KLPGA 정규투어 참가자격 규정 2026 일반대회 우승자 시드 유효기간"으로 검색한 결과, klpga.co.kr 원문은 나오지 않았고 간접 기사만 나왔다. 그나마 나온 내용도 질문과 정확히 일치하지 않는다 — 검색 결과가 설명한 것은 **IQT(외국인 선수 대상 인터내셔널 퀄리파잉 토너먼트)** 우승자의 익년 시드이지, 사용자가 물은 **일반 정규대회/메이저대회 우승자**의 유효기간이 아니다. 이 둘을 같다고 보고 답을 만들면 그 자체가 오답이므로, **이 결과를 참가자격 판정에 쓰지 않았다.**

**결론**: 공식 원문도, 신뢰할 수 있는 2차 출처도 확보하지 못했다. 추측 없이 UNKNOWN으로 유지한다.

### 1-4. 유일하게 확인된 것: 2026시즌 우승 횟수 = 0 (26명 전원, 공식)

이전 단계에서 사용자가 첨부한 공식 상금순위 HTML(`official_money_rank_2026-10-06_full.json`, 2026-10-06 기준, 전수 검증됨)에 `wins`(해당 선수의 2026시즌 누적 우승 횟수) 필드가 있다. 55~80위 26명 전원 **`wins = 0`** — 즉 **2026시즌에 우승한 적이 있는 선수는 이 26명 중 아무도 없다는 것은 공식 자료로 확인된 사실이다.**

이것은 사용자가 지정한 확인 항목 중 **"3. 2026 우승자가 2027년에 자동 출전자격을 갖는지"**를 이 26명에게는 **적용 대상 없음(N/A)**으로 만든다 — 해당하는 2026 우승자가 애초에 이 구간에 없기 때문이다. (주의: 이것이 "2026 우승 자격 규정 자체가 확인됐다"는 뜻은 아니다. 규정 자체는 여전히 UNKNOWN이고, 단지 이 26명에게는 그 규정이 적용될 일 자체가 없다는 사실만 확인된 것이다.)

---

## 2. 사용자가 CONFIRMED로 제시한 카테고리 (그대로 기록, 검증 보류)

사용자가 KLPGA 공식 2026 참가자격 페이지에서 직접 확인했다고 밝힌 자격 카테고리 목록을 그대로 기록한다 — 이 목록의 **존재**는 사용자 confirmed, 각 항목의 **세부 규정(유효기간, 중복 처리 등)** 은 이번 세션에서 추가 검증하지 못했다:

- 전년도 정규투어 상금순위 60위 이내
- 일반대회 우승자
- 메이저대회 우승자
- 드림투어 상금순위 20위 이내
- 시드순위자
- 기타 대회별 참가자격

**중요 원칙(사용자 지시 그대로 적용)**: 2026 참가자격을 2027 자격으로 자동 연장하지 않는다. 예컨대 어떤 선수가 "2025 드림투어 20위 이내로 2026 정규투어 출전 중"이라는 사실이 확인되더라도, 이것만으로 "그 선수가 2027 시드도 확보했다"고 판정하지 않는다 — 2026 출전 근거와 2027 출전 자격은 별개 질문이며, 후자는 2026시즌 실적(상금순위 Top60, 2026년 우승 등)이나 별도의 2027 자격 공지로 다시 확인되어야 한다.

---

## 3. 55~80위 26명 교차검증 테이블

전체 CSV: `eligibility_crosscheck_55_80.csv` (16개 컬럼 전부, 기계 판독용). 아래는 핵심 요약.

| 현재순위 | 선수 | 현재상금(공식) | 2026_win(공식) | 2026_entry_category | 2025/2024_win | major_win_year | known_2027_exemption | top60_required_for_2027 | status |
|---|---|---|---|---|---|---|---|---|---|
| 55 | 마서영 | 164,138,333 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 56 | 지한솔 | 162,531,765 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 57 | 김지윤2 | 154,330,000 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 58 | 안재희 | 147,941,051 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 59 | 조아연 | 147,340,000 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 60 | 김새로미 | 147,312,262 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 61 | 한아름 | 146,194,643 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 62 | 한지원 | 144,250,000 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 63 | 최정원 | 142,181,250 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 64 | 김우정 | 140,947,857 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 65 | 마다솜 | 138,882,523 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 66 | 홍정민 | 134,968,333 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 67 | 최민경 | 129,244,285 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 68 | 박결 | 125,776,429 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 69 | 홍지원 | 125,517,143 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 70 | 김소정 | 123,000,000 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 71 | 김나현2 | 120,950,000 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 72 | 이재윤 | 118,499,643 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 73 | 김서윤2 | 115,551,250 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 74 | 김하은2 | 113,178,333 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 75 | 유지나 | 112,322,143 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 76 | 이주미 | 109,730,000 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 77 | 손예빈 | 96,270,000 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 78 | 왕 즈쉬엔 | 94,440,715 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 79 | 박서현 | 94,024,643 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |
| 80 | 현세린 | 93,047,500 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | GROUP C |

`2026_win_type`은 전원 `N/A (2026_win=0, confirmed)` — 2026 우승이 0회로 확인됐으므로 우승 종류(메이저/일반) 자체가 해당 없음. 그 외 모든 셀의 근거는 CSV `evidence` 컬럼에 동일하게 기록: "klpga.co.kr 네트워크 차단, 로컬 데이터셋 없음, 웹 검색으로도 신뢰 가능한 공식 수준 근거 확보 실패".

---

## 4. 반드시 확인하라고 지정된 5개 항목 — 전부 UNKNOWN

| # | 항목 | 상태 | 비고 |
|---|---|---|---|
| 1 | 일반대회 우승자의 정규투어 출전자격 유효기간 | **UNKNOWN** | 원문 미확보. 웹검색 결과(IQT 관련)는 질문 대상과 다른 카테고리라 사용 안 함 |
| 2 | 메이저대회 우승자의 유효기간 | **UNKNOWN** | 원문 미확보 |
| 3 | 2026 우승자가 2027년에 자동 출전자격을 갖는지 | **N/A for 이 26명** (2026_win=0 공식 확인) / 규정 자체는 **UNKNOWN** | 이 26명 중 해당자가 없어 적용 사례가 없을 뿐, 규정 자체가 확인된 것은 아님 |
| 4 | 2024/2025 우승자가 2027년에도 유효한지 | **UNKNOWN** | 2024/2025 우승 이력 데이터 자체가 없음 |
| 5 | Top60과 우승자 자격 중복 시 61위 이하로 승계되는지 | **UNKNOWN** | 원문 미확보 |

---

## 5. 최종 분류

**A. Top60이 사실상 필요한 선수**: **없음 (0명)** — 어떤 선수에 대해서도 "다른 2027 자격 경로가 없다"를 공식적으로 확정할 수 없기 때문에, Top60이 "사실상 필요하다"고 단정할 근거가 아직 없다.

**B. Top60 밖이어도 2027 출전자격 확보 선수**: **없음 (0명)** — `known_2027_exemption`이 CONFIRMED인 선수가 아직 1명도 없다.

**C. 규정 확인이 더 필요한 선수**: **26명 전원** — 55위 마서영부터 80위 현세린까지, 공식 참가자격 규정 원문 또는 선수별 2024~2026 우승 이력·드림투어 순위 데이터가 확보되기 전까지는 전원 이 분류에 남는다.

이 결과가 "아무것도 안 했다"는 뜻은 아니다 — 26명 전원의 2026시즌 우승 여부(0회, 공식)를 확인해 "2026 우승 자격"이라는 한 가지 경로는 이 구간 전원에서 배제했고, 네트워크·로컬 데이터·웹 검색 세 경로 모두 막혀 있다는 것을 직접 테스트로 확인했다. 남은 작업은 전적으로 **원문 데이터 확보**에 달려 있다.

---

## 6. 다음 단계 — 사용자에게 요청

이번 세션은 klpga.co.kr에 접근할 수 없고, 저장소에 다년도 우승 이력 데이터가 없다. 다음 중 하나(또는 여러 개)를 제공해 주시면 위 테이블의 UNKNOWN을 하나씩 CONFIRMED로 바꿀 수 있다 — 이전 단계들(상금순위 페이지, 대회별 상금분배 anchor)과 동일한 방식이다:

1. **KLPGA 공식 "참가자격 규정"/"경기 운영 규정" 원문**(PDF, HTML, 공지 캡처 등 무엇이든) — 특히 일반대회/메이저대회 우승자 시드 유효기간, Top60-우승자 중복 시 승계 규정 부분.
2. **2024/2025/2026 KLPGA 정규투어 대회별 우승자 명단**(메이저 여부 구분 포함) — 이 55~80위 26명 중 누가 포함되는지 대조하기 위함.
3. **2025 드림투어 최종 상금순위 20위 이내 명단** — 이 26명 중 해당자가 있는지 대조하기 위함.
4. KLPGA가 이미 공지한 **"2027 시드순위자/참가자격자" 명단**이 있다면 그것 자체.

하나라도 주시면 그 항목부터 즉시 반영하겠다. 아무것도 없으면 이 문서는 GROUP C 26명 그대로 유지되고, **DEPLOY는 계속 HOLD**다.

---

## 7. DEPLOY 상태

**HOLD 유지.** 이번 교차검증 결과(전원 GROUP C) 자체가 DEPLOY를 더더욱 보류해야 할 이유를 보강한다 — "상금순위 Top60 확률"이라는 라벨조차, 그 Top60 안의 선수 중 일부가 이미 다른 경로로 자격을 확보했는지 여부(중복자 승계 문제, 항목 5)가 확인되기 전까지는 "Top60 확률 = 새로 자격을 얻는 선수 수"라는 해석도 완전히 정확하다고 보장할 수 없다. 이 문서와 `SEED_ELIGIBILITY_GAP.md`를 함께 참조.
