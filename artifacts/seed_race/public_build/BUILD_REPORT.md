# KLPGA 2027 시드 전쟁 — PUBLIC BUILD 보고 (FINAL, 2027 ELIGIBILITY LAYER 반영)

**기준**: Top60 확률 시뮬레이션 `e21e05b` (변경 없음) + 2027 시드 교차검증 `eligibility_crosscheck_55_80.csv` v7(`3bd088f`)

> **[FINAL — 2027 ELIGIBILITY LAYER 추가]** 기존 Top60 확률(60,000회 시뮬레이션)은 **전혀 재계산하지 않았다.** 이번 턴에 추가된 것은 완전히 독립된 두 번째 필드 — **"2027 별도 시드"**(공식 참가자격·우승 시드 기간 규정 교차검증 결과) — 뿐이다. 두 필드가 섞이지 않도록 Top60 확률이 낮아도 2027 시드가 이미 확보된 선수(홍정민)는 "시드 확보"로 별도 표시한다. 상세 근거: `../SEED_ELIGIBILITY_CROSSCHECK_55_80.md` v7, `../SEED_ELIGIBILITY_GAP.md`.

새 모델 없음. 확률 재조정 없음. `seed_probability.csv`/`seed_probability_whatif.csv`/`final_60th_money_distribution.csv`(Top60 확률 소스, 불변)와 `eligibility_crosscheck_55_80.csv`(2027 시드 레이어, 이번 턴 추가)를 함께 직접 읽어 렌더링했다.

---

## 1. 변경 파일

전부 `artifacts/seed_race/public_build/` 아래, **production(`docs/`) 밖** — 아직 배포 안 함.

| 파일 | 역할 |
|---|---|
| `build.py` | 제목을 "KLPGA 2027 시드 전쟁"으로 변경, `eligibility_crosscheck_55_80.csv`를 추가로 읽어 각 선수 행에 "2027 별도 시드"/"실질 상태" 필드 추가, HERO에 Top60≠2027시드 고지 2줄 추가, methodology에 2027 레이어 설명+한계 고지 추가 |
| `index.html` | 재생성된 공개 페이지 본체 |
| `verify_source_match.py` | 기존 체크 전부 유지 + 2027 레이어 검증(CSV↔HTML 1:1 매치, GROUP B 1명뿐임을 확인, Top60 시뮬레이션 수치 불변 스냅샷 대조, 내부 분류 라벨 비노출 확인) |
| `screenshot.py` | 변경 없음, 재실행만 |
| `screenshots/*.png` | 재캡처 |
| `BUILD_REPORT.md` | 이 보고서 |

디자인은 기존 NEO GOLF DATA 팔레트 그대로(재디자인 없음). 2027 시드 배지(`.bubble-seed-badge`, `.bubble-seed2027-value.group-B`)만 기존 accent 색(`#0f9488`)을 재사용해 시각적 일관성을 유지했고, "Top60 필요"(GROUP A)는 경고색(`--warn`), "판정 보류"(GROUP C)는 중립색으로 구분했다.

---

## 2. 테스트 결과

`python3 artifacts/seed_race/public_build/verify_source_match.py` — **178개 체크 전부 PASS**, 실패 0건.

**이번 턴 신규 체크(핵심)**:
- 55~70위 16명 전원 `data-seed2027-group`이 `eligibility_crosscheck_55_80.csv`의 `final_2027_group`과 1:1 일치
- GROUP B(2027 시드 확보)가 정확히 1명이며 그 선수가 홍정민(66위)임을 확인
- "2027 시드 확보" 배지가 페이지 전체에서 정확히 1번만 등장(다른 선수에게 잘못 붙지 않음)
- **60K 시뮬레이션 불변 검증**: 55~70위 16명 전원의 `prob_top60`이 이번 턴 작업 시작 전 스냅샷과 소수점 4자리까지 완전히 동일, P10/MEDIAN/P90도 동일 — 2027 레이어 작업이 Top60 확률에 어떤 영향도 주지 않았음을 수치로 증명
- 내부 분류 라벨(`GROUP A/B/C/D`, `RULE_CONFIRMED`, `OFFICIAL_ENTRY_CONFIRMED`, `evidence_level`, `final_2027_group` 등 CSV 컬럼명·enum값)이 공개 텍스트에 전혀 노출되지 않음을 확인
- 기존 체크(시드 생존확률류 금지 문구, scope-banner, 최소 1750만원 금지, 내부 용어 전수, raw 시뮬레이션 재계산 대조 등) 전부 재확인 PASS

---

## 3. Desktop screenshot (1440×900)

`screenshots/desktop_1440x900.png` — 직접 열어서 눈으로 확인함. scope-banner(Top60 확률과 2027 출전자격을 분리한다는 고지) → HERO("현재 60위인데, 상금순위 Top60 확률은 31.9%" + "상금순위와 2027 시드는 같은 말이 아니다" 고지) → MOVING CUT LINE → TOP60 BUBBLE(55~70위, 각 행에 "2027 별도 시드"/"실질 상태" 추가, 홍정민 행에만 초록 배지) → WHAT-IF → METHODOLOGY(2027 레이어 설명 + 2019년판 핸드북 한계 고지) → PUBLIC COPY("KLPGA 2027 시드 전쟁") → footer. 가로 스크롤 없음, 숫자/배지 겹침 없음.

## 4. Mobile screenshot (390×844)

`screenshots/mobile_390x844.png` — 직접 열어서 눈으로 확인함. 홍정민 행을 확대 확인(크롭 캡처로 별도 검증) — "홍정민 [2027 시드 확보]" 이름 옆 배지, "2027 별도 시드: 확보 (~2028)", "실질 상태: 시드 확보"(초록 pill)가 바로 위 마다솜 행("없음 (2026년 만료)", "Top60 경쟁" 빨간 pill)과 뚜렷이 대비됨. 가로 스크롤 없음, 줄바꿈/겹침 이상 없음.

---

## 5. 최종 공개 문안 (실제 렌더링된 텍스트 그대로)

**SCOPE BANNER**
> 이 페이지는 두 가지를 분리해서 보여줍니다: **2026시즌 상금순위 Top60 확률**(60,000회 시뮬레이션)과 **2027 KLPGA 출전자격(시드) 상태**(공식 참가자격·우승 시드 규정 교차검증). 우승 시드 등으로 이미 2027 자격이 확인된 선수는 별도로 표시하며, 둘을 같은 숫자로 섞지 않습니다.

**HERO**
> 현재 60위인데, 상금순위 Top60 확률은 31.9%
> 현재 60위 · 김새로미 · 147,312,262원 · NEO 상금순위 Top60 확률 **31.9%**
> 현재 순위보다 중요한 것은 시즌 마지막 날의 순위다.
> 단, 상금순위와 2027 시드는 같은 말이 아니다. NEO는 우승 시드 등 별도 출전자격을 분리해 실제로 60위가 필요한 선수만 다시 본다.

**TOP60 BUBBLE** (55~70위, 각 행 추가 표시)
> 각 선수 아래 "2027 별도 시드"는 Top60 확률과는 다른 질문이다 — 우승 시드 등 공식 확인된 별도 자격이 있는지를 나타낸다. 홍정민은 2025 KLPGA 챔피언십(메이저) 우승으로 2027 시드가 이미 확보돼 있다 — 이 선수의 Top60 확률이 낮게 나와도 그것이 2027 시드 상실을 뜻하지 않는다.
> (홍정민 행) 15.1% · 2027 별도 시드: 확보(~2028) · 실질 상태: 시드 확보
> (마다솜 행) 17.7% · 2027 별도 시드: 없음(2026년 만료) · 실질 상태: Top60 경쟁

**METHODOLOGY** (신규 문단 2개)
> 이 페이지의 **Top60 확률**이 계산한 것은 "2026시즌 상금순위가 60위 안에서 끝나는가" 하나뿐이다. **2027 별도 시드**는 이것과 별개로, KLPGA 공식 참가자격·우승자 시드 기간 규정을 교차 대조해 표시한다 — 우승에 따른 시드가 2027까지 유효한 선수는 Top60 확률과 무관하게 "시드 확보"로 표시한다.
> 단, 이 2027 시드 판정에도 한계가 있다: 우승자 시드 기간 규정은 2019년판 공식 핸드북을 기준으로 하며(이후 개정 여부 미확인), 이번 교차검증은 55~80위 구간에 한정돼 있다. K-10 클럽·생애누적상금 등 이사회 재량으로 결정되는 특별시드는 확정 전까지 "조건부"로만 표시하며 자동으로 시드 확보 처리하지 않는다.

**PUBLIC COPY**
> 상금순위 60위가 끝이 아니다. … NEO는 여기서 한 걸음 더 나아가, 이미 시드를 가진 선수와 반드시 60위 안에 들어야 하는 선수를 분리했다. 이번 구간에서는 2025 메이저 우승자 홍정민이 Top60 확률과 무관하게 2027 시드를 확보한 유일한 선수로 확인됐다.

---

## 6. 실제 페이지 경로

**아직 어디에도 배포되지 않음.** `artifacts/seed_race/public_build/index.html`(production `docs/` 밖). **DEPLOY는 계속 HOLD** — 55~80위 26명 중 GROUP C(판정 보류) 14명이 남아 있고, 전체 KLPGA 참가자격 규정(2019년 핸드북 기준, 개정 여부 미확인) 자체도 완전히 확정된 상태는 아니다.

---

## 7. source-data 대조 결과

`verify_source_match.py` 전체 출력 기준 **178/178 PASS, 0 FAIL**.

---

```
[NEO 2027 SEED RACE — FINAL BUILD]

26 PLAYERS CLASSIFIED (55-80위):
A: 11 (Top60 필요)
B: 1  (2027 시드 CONFIRMED -- 홍정민)
C: 14 (판정 보류)
D: 0  (조건부 특별시드 -- 현재 해당자 없음)

CONFIRMED 2027 EXEMPT:
홍정민 (66위, 2025 KLPGA 챔피언십 메이저 우승, 2025~2028 커버)

TOP60 REQUIRED (GROUP A, 11명):
지한솔·안재희·김새로미·김우정·마다솜·홍지원·김소정·김나현2·김서윤2·유지나·손예빈

ELIGIBILITY TEST: PASS (16명 전원 CSV↔HTML 1:1 매치, GROUP B 1명·홍정민 확인, 배지 1회만 노출)

60K MODEL UNCHANGED: PASS (16명 prob_top60 + P10/MEDIAN/P90 전부 사전 스냅샷과 완전 일치)

MOBILE: PASS (390×844, 가로 스크롤 없음, 홍정민/마다솜 행 대비 확인)

DESKTOP: PASS (1440×900, 가로 스크롤 없음)

PUBLIC COPY: PASS (금지 문구·내부 라벨 전수 부재, 신규 고지 문구 전부 존재)

DEPLOY: HOLD
```
