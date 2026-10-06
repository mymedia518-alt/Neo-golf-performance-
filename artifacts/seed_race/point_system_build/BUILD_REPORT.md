# 2027 포인트 시드 전쟁 — PUBLIC BUILD 보고 v3 (WHY 카피 정정, point_rank는 여전히 LOCKED)

**기준**: 2027 시드 기준 전환 OFFICIAL PASS(`8642b0c`) + OFFICIAL RELAY #3(`38b03b7`, TOP10 커브) + 55~80위 실제 포인트 값(`25552f5`) + 이번 턴 **WHY 카피 수정 + mainRecord 재구성 시도(수행 불가)**

> **PUBLIC PROBABILITY = LOCKED, 변함없음.** 사용자가 2026 전체 mainRecord(선수×대회×포인트, 수천 행)를 직접 수집해 전체 선수 point_rank를 재구성하라고 지시했으나, **klpga.co.kr의 모든 경로가 이번에도 403 차단**돼 수행하지 못했다(아래 1번). 알고 있는 19명의 누적값에 맞춰 대회별 기록을 역산해 지어내는 것도 하지 않았다 — 실제 경기 기록이 아니라 숫자 맞추기이기 때문이다. 대신 **mainRecord가 오면 바로 돌아가는 재구성 스크립트**를 준비했고, **새 데이터 없이 가능한 WHY 카피 수정**은 요청하신 정확한 문구로 반영했다. point_rank/delta/reversal은 **이번에도 LOCKED.**

---

## 0. v3 — 이번 턴 요약

1. **mainRecord 전체 수집·재구성: 수행 불가.** `klpga.co.kr/web/record/mainRecord`, `klpga.co.kr/web/tourInfo/record`, `data.klpga.co.kr/record/mainRecord.jsp` 전부 재시도, 전부 403(`connect_rejected`) — 이 세션 내내 반복된 패턴과 동일. 상세 사유는 `SEED_POINT_SYSTEM_GAP.md` 섹션 13.
2. **역산(reverse-engineering) 거부**: 19명의 알려진 누적값에 맞는 "그럴듯한" 대회별 기록을 만들 수는 있지만, 그것은 실제 기록이 아니라 지어낸 허구라서 하지 않았다.
3. **대신 준비한 것**: `mainrecord_TEMPLATE.csv`(요청 스키마 그대로, 0행) + `reconcile_point_totals.py`(mainRecord를 합산해 기존 19명 공식값과 자동 대조, 빈 데이터엔 실행 거부하는 가드 포함 — 직접 테스트로 거부 확인).
4. **WHY 카피 수정(새 데이터 불필요, 완료)**: "상금은 컷을 통과해도 쌓인다. 대상포인트는 Top10 순위에 들어야 쌓인다." — 정확히 요청된 문구로 교체. "10명만 받는다"는 헤드카운트 표현 대신 "Top10 순위"라는 순위 기준 표현 사용(공동순위 때문에 10명보다 많은 인원이 받을 수 있어, 특정 인원수를 명시하지 않음). 자동검증에 "10명만" 금지어 체크 추가.

---

## 1. v1 → v2, 무엇이 바뀌었나

| | v1 (`38b03b7`) | v2 (이번 턴) |
|---|---|---|
| 55~80위 버블 표시 | 26명 전원 "포인트순위 확보 전"(동일 문구 반복) | **26명 전원 실제 대상포인트 값**(또는 "—" + 각주) |
| HERO 비교 카드 | 없음(예시 선수 지정 금지 상태 유지) | **데이터로 계산된 4장**: 포인트 최고(조아연 73)·최저(김하은2 20)·현재 60위(김새로미 57)·60위 밖 최강(홍정민 67) |
| 포인트순위(랭크) 번호 | 없음 | **여전히 없음** — 26명만 정렬해 순위를 매기는 "단순 sort"를 명시적으로 금지했기 때문(아래 2번) |
| 공동순위 처리 규칙 | 미확인 | **OFFICIAL 사례로 확인**(12억원 대회 T2/T5/T8) — 동순위 전원이 해당 순위 포인트를 동일하게 받음(평균·분할 아님) |
| WHY 카피 | "포인트는 상위권에 집중된다"(일반화) | **"10억원 일반대회 기준"으로 명시 scoping**, 다른 대회에 일반화하지 않는다는 문장 추가 |

---

## 2. 왜 "포인트순위"는 여전히 공개하지 않는가 — 사용자 지시 그대로 준수

사용자가 명시: *"현재 공식 전체 선수 point 값을 이용해 point ranking을 재구성한다... 단순 sort만 하고 끝내지 마라... 공식 point_rank와 일치할 때만 PUBLIC point_rank 노출."*

이번에 받은 것은 **55~80위(money_rank 기준) 26명의 포인트 값**뿐이다. 전체 투어 선수(120명 이상) 중 이 26명 밖에 있는 약 90명의 포인트는 여전히 모른다. 이 26명만 포인트 기준으로 정렬해 "1위, 2위…"를 매기면, 그 26명 밖 선수가 실제로는 그 사이에 끼어들 수 있는데도 없는 것처럼 취급하는 셈이 된다 — 이것이 사용자가 명시적으로 금지한 "단순 sort". 그래서:

- **포인트 값**은 공개한다(실제 relay된 사실).
- **포인트 순위(몇 등)**는 공개하지 않는다(전체 선수 포인트 미확보).
- 대신 "포인트순위: 전체 선수 집계 후 공개"라고 매 행에 명시해, 독자가 "이 숫자가 등수가 아니라 점수"라는 것을 바로 알게 했다.

---

## 3. BLANK 처리 — 사용자가 금지한 것 그대로 피함

사용자 지시: *"blank를 '데이터 없음'이라고 쓰지 마라. A(실제 2026 포인트 획득 없음)/B(순위 자격 미충족)/C(source missing) 구분. 확정 전까지 '—'로 표시."*

6명(한아름·이재윤·유지나·이주미·왕즈쉬엔·박서현)이 원본에서 공란이었다. 이 중 어느 케이스인지 구분할 근거가 없어 **셋 다 가능성으로 열어두고 "—"로 표시**, 섹션 하단에 A/B/C 세 가지 가능성을 그대로 각주로 달았다(어느 하나로 단정하지 않음).

---

## 4. 변경/생성 파일

| 파일 | 역할 |
|---|---|
| `point_values_bubble_55_80_2026-10-06.csv`(신규, `artifacts/seed_race/` 루트) | 55~80위 26명의 실제 대상포인트 값(relay 그대로), blank는 `BLANK_UNRESOLVED`로 명시, `point_rank_status=UNRECONCILED` 고정 |
| `tie_handling_fixture_OFFICIAL.csv`(신규, 루트) | 12억원 대회 공동순위 사례(T2/T5/T8/10위) — 회귀 테스트용 고정 자료 |
| `point_system_build/build.py` | 버블 26명 렌더링을 "포인트순위 확보 전" 반복에서 **실제 포인트 값 + "전체 집계 후 공개" 고지**로 전면 교체, HERO 비교 카드 4장(코드로 계산, 사전 지정 없음) 추가, TOP10 섹션에 공동순위 고정표 추가, WHY 카피 scoping 수정 |
| `point_system_build/verify_source_match.py` | 아래 5번 신규 체크 대거 추가 |
| `point_system_build/screenshots/*.png` | 재캡처 |

`public_build/`(상금순위 Top60 페이지)는 이번에도 건드리지 않았다.

---

## 5. 테스트 결과

`python3 artifacts/seed_race/point_system_build/verify_source_match.py` — **225개 체크 전부 PASS**(v2 222 + WHY 카피 검증 3건 추가).

핵심 신규 체크:
- 26명 전원의 포인트 값이 `point_values_bubble_55_80_2026-10-06.csv`와 1:1 일치, 상금도 공식 JSON과 재대조
- blank 6명 전원 "—" 표시, 금액 숫자가 포인트로 오인되지 않는지 확인
- **26명 중 누구에게도 "포인트순위 N위"라는 숫자 주장이 없음**을 정규식으로 전수 확인(`포인트순위\s*\d+\s*위` 패턴 매치 0건)
- HERO 카드 4장이 CSV에서 직접 계산한 최고/최저/60위/60위 밖 최강과 정확히 일치(코드가 계산, 수작업 지정 아님) — 조아연(73)·김하은2(20)·김새로미(57)·홍정민(67) 자동 산출 확인
- 홍정민 카드에 "별도 시드 확보" 배지 포함 확인
- 공동순위 고정표가 `tie_handling_fixture_OFFICIAL.csv`와 정확히 일치
- WHY/TOP10 카피에 "10억원 일반대회에서는" scoping 문구와 "일반화하지 않는다" 면책 문구 둘 다 존재
- 내부 enum 값(`CONFIRMED_VALUE`, `BLANK_UNRESOLVED`, `UNRECONCILED` 등)이 공개 HTML에 노출되지 않음(data 속성에서도 제거)
- 기존 체크(확률 숫자 부재, TOP10 커브, GROUP B 1명 등) 전부 재확인 PASS

---

## 6. Desktop / Mobile 스크린샷

`screenshots/desktop_1440x900.png`, `screenshots/mobile_390x844.png` — 직접 열어서 확인함. 가로 스크롤 없음. 모바일에서 다음을 크롭 확대해 개별 확인:
- 한아름(61위) 행 — "—"에 위첨자 각주 표시, 숫자처럼 보이지 않음
- 홍정민(66위) 행 — "별도 시드 확보" 배지 + "대상포인트 67점" + "포인트순위: 전체 선수 집계 후 공개"가 겹치지 않고 모두 표시
- HERO 카드 4장 — 모바일에서는 1열로 쌓임(반응형), 홍정민 카드에 배지 정상 표시
- 공동순위 고정표(T2/T5/T8/10위) — 표와 설명 문구 모두 정상 렌더링

---

## 7. 실제 페이지 경로 / DEPLOY

**아직 어디에도 배포되지 않음.** `artifacts/seed_race/point_system_build/index.html`(production `docs/` 밖). **DEPLOY는 계속 HOLD** — 포인트순위 cutoff, 전체 선수 포인트(버블존 밖 ~90명), 아이스버그 2위 이하 배점이 확보되기 전까지 유지한다.

---

```
[NEO 2027 POINT SEED WAR — v2 DATA PASS]

PUBLIC PROBABILITY: LOCKED (검증됨)
POINT VALUES (55-80위 26명): PUBLISHED (실제 값, 26/26)
POINT RANK (55-80위): STILL LOCKED (단순 정렬 금지 — 전체 필드 미확보)
BLANK SEMANTICS: A/B/C 각주로 명시, 단정 없음 (6명)
HERO CARDS: 데이터 기반 자동 산출 4장
TIE HANDLING: OFFICIAL 고정 (12억원 대회 T2/T5/T8/10위)
SOURCE↔UI: PASS (225/225)
MOBILE: PASS
DESKTOP: PASS
DEPLOY: HOLD
```
