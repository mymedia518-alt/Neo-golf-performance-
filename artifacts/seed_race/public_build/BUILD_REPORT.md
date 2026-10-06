# NEO KLPGA 2026 상금순위 Top60 — PUBLIC BUILD 보고

**기준 commit**: `e21e05b` (red-team 검증 완료, PASS WITH CORRECTIONS) + 이번 턴 **DEPLOY HOLD 용어 정정** 반영

> **[DEPLOY HOLD — 용어 정정]** 사용자 지시에 따라 "시드 생존확률"/"시드 유지확률" 표현을 전면 금지하고 **"상금순위 Top60 확률"**로 교체했다. 실제 2027 KLPGA 출전자격(시드)은 우승 시드 유효기간, 메이저/일반대회 차이, Top60 외 시드 자격, 중복자 승계 규정 등 공식 참가자격 규정을 전수 확인해야 알 수 있으며, 이번 세션은 네트워크 제약(klpga.co.kr 차단)으로 이를 확인하지 못했다 — 미확인 항목 전체 목록은 `../SEED_ELIGIBILITY_GAP.md` 참조. **60,000회 시뮬레이션 숫자는 전혀 바뀌지 않았다 — 라벨만 정정했고, 페이지 상단에 이 구분을 명시하는 경고 배너를 추가했다.**

새 모델 없음. 확률 재조정 없음. 새 가정 추가 없음. `artifacts/seed_race/seed_probability.csv`, `seed_probability_whatif.csv`, `final_60th_money_distribution.csv`를 직접 읽어 렌더링했다(아래 1번 참조).

---

## 1. 변경/생성 파일

전부 `artifacts/seed_race/public_build/` 아래, **production(`docs/`) 밖**에 생성 — 아직 배포 안 함.

| 파일 | 역할 |
|---|---|
| `build.py` | CSV 3종을 직접 읽어 `index.html`을 생성(숫자 하드코딩 없음, 전부 소스에서 읽음). 이번 턴에 "시드" 관련 공개 문구를 "상금순위 Top60"으로 전면 교체하고, 상단에 `.scope-banner`(2027 시드와의 구분 고지)와 methodology에 경고 박스를 추가 |
| `index.html` | 재생성된 공개 페이지 본체 |
| `verify_source_match.py` | 생성된 HTML을 **독립적으로 재파싱**해 CSV·raw 시뮬레이션 배열과 숫자 대조(아래 7번). 이번 턴에 "시드 생존확률" 등 금지 문구 부재 체크, scope-banner 존재 체크, methodology 고지 문구 체크 추가 |
| `screenshot.py` | Playwright로 desktop/mobile 스크린샷 재생성 + 가로 스크롤 오버플로우 검사 |
| `screenshots/desktop_1440x900.png`, `screenshots/mobile_390x844.png` | 정정 반영 후 실제 렌더링 재캡처 |
| `BUILD_REPORT.md` | 이 보고서 |

디자인은 `docs/about/index.html`, `docs/tournaments/2026/kg-ladies-open/final/index.html`에서 그대로 가져온 NEO GOLF DATA 기존 색상/폰트/카드 스타일(재디자인 없음): `--bg:#dde5f3`, `--accent:#0f9488`, `--accent-blue:#2f5fd9`, "Big Shoulders Display"/"Noto Sans KR"/"Roboto Mono", N/E/O 워드마크. 새로 추가한 `.scope-banner`만 경고 톤(amber `#fdf2e0`/`#7a5410`)으로 기존 팔레트와 의도적으로 구분했다.

---

## 2. 테스트 결과

`python3 artifacts/seed_race/public_build/verify_source_match.py` — **129개 체크 전부 PASS**, 실패 0건(이전 96개 + 이번 턴 추가 33개).

핵심 항목(이전 턴부터 유지, 전부 재확인됨):
- CSV rank60 = 김새로미 / 147,312,262원 / 31.9% ↔ HTML hero 동일 텍스트 일치
- **raw 시뮬레이션 배열(.npz)을 CSV·build.py와 독립적으로 재계산**: n=60,000, survive=19,157, 31.9%로 반올림 일치
- `final_60th_money_distribution.csv`의 P10=164,840,244 / MEDIAN=172,303,371 / P90=180,291,768이 HTML과 정확히 일치
- 55~70위 16명 전원 player/money/prob_top60/median_final_rank CSV-HTML 1:1 일치
- Top60 기준선 마커가 정확히 60위와 61위 사이에 위치
- WHAT-IF 박결 6개 시나리오(현재/CUT/30위/20위/10위/5위) 전부 `seed_probability_whatif.csv`와 일치
- 금지 문구 "최소 1,750만원" 부재 확인
- 내부 용어(`simulation array`, `payout curve`, `log-linear`, `JSON`, `Plackett`, `Gumbel`, `τ`, `Monte Carlo` 등) 전수 부재 확인

**이번 턴 신규 체크**:
- 모델 명칭 "NEO KLPGA 2026 상금순위 Top60 시뮬레이션" 존재, 금지된 "경기력 예측"/"SG 기반"/"최근 경기력 기반" 부재 확인
- **금지 문구 "시드 생존확률" / "시드 유지확률" / "시드를 지킬 확률" / "시드 레이스" 페이지 전체에서 부재 확인**
- scope-banner(2027 KLPGA 출전자격은 별도 기준이라는 고지) 존재 및 "2027 KLPGA 출전자격" 문구 포함 확인
- methodology 섹션에 Top60 확률 ≠ 시드 확정이라는 고지 문구 포함 확인

전체 출력은 `verify_source_match.py` 재실행으로 재현 가능.

---

## 3. Desktop screenshot (1440×900)

`screenshots/desktop_1440x900.png` — 직접 열어서 눈으로 확인함. 헤더 바로 아래 amber 색 scope-banner("이 페이지는 2026시즌 상금순위 Top60 확률만 계산합니다…") → HERO(31.9% 헤드라인, "상금순위 Top60 확률"로 표기) → MOVING CUT LINE → TOP60 BUBBLE(55~70위, 60/61 경계선) → WHAT-IF(박결 ladder) → METHODOLOGY(보간 민감도 + 시드 구분 고지 2개 경고 박스) → PUBLIC COPY → footer 순서로 렌더링. 가로 스크롤 없음(`scrollWidth == clientWidth == 1440`), 숫자/표 깨짐 없음.

## 4. Mobile screenshot (390×844)

`screenshots/mobile_390x844.png` — 직접 열어서 눈으로 확인함. scope-banner가 스크롤 없이 화면 상단에서 바로 보임. 가로 스크롤 없음(`scrollWidth == clientWidth == 390`), 선수명 줄바꿈 이상 없음, 확률 겹침 없음, 60위 기준선(강조 카드 + "Top60 기준선" 빨간 배지)이 스크롤 중 즉시 인지됨.

---

## 5. 최종 공개 문안 (실제 렌더링된 텍스트 그대로, 정정 반영 후)

**SCOPE BANNER (신규)**
> 이 페이지는 **2026시즌 상금순위 Top60 확률**만 계산합니다. 2027 KLPGA 출전자격(시드) 여부는 별도 공식 기준이 추가로 적용될 수 있어, 이 확률과 동일하다고 단정하지 않습니다.

**HERO**
> 현재 60위인데, 상금순위 Top60 확률은 31.9%
> 현재 60위 · 김새로미 · 147,312,262원
> NEO 상금순위 Top60 확률 **31.9%**
> 현재 순위보다 중요한 것은 시즌 마지막 날의 순위다.

**MOVING CUT LINE** (변경 없음)
> 60위선은 멈춰 있지 않는다
> 현재 60위 상금 147,312,262원
> 낮은 시나리오 164,840,244원(+17,527,982) · 중앙 시나리오 172,303,371원(+24,991,109) · 높은 시나리오 180,291,768원(+32,979,506)
> 지금의 147,312,262원은 중앙 시나리오 기준 60위 상금(172,303,371원)보다 낮다 — 현재 1억4,731만원이 시즌 종료 때는 안전선이 아닐 수 있다.

**TOP60 BUBBLE** (55~70위 표, 60/61 사이 "Top60 기준선")

**WHAT-IF** (변경 없음)
> 박결, 현재 68위 — 현재 11.2% · CUT 7.8% · 30위 8.8% · 20위 9.1% · 10위 10.6% · **5위 62.8%**
> 박결에게 "본선 통과 정도"(컷 탈락 → 20위)는 확률을 거의 못 바꾼다 — 상금이 10위에서 5위로 가는 구간에서 급등하기 때문에, 확실한 top5가 아니면 큰 의미가 없다.

**METHODOLOGY** (경고 박스 1개 추가)
> 현재 상금순위와 확인된 남은 대회 상금 구조를 바탕으로, 남은 시즌을 60,000번 반복해 각 경우의 최종 상금순위를 다시 계산했다. 매번 경쟁 선수들의 상금도 함께 변한다. 따라서 단순히 "현재 60위 상금을 넘는가"를 계산한 것이 아니다.
> 이 확률은 경기 결과를 보장하는 값이 아니라, 현재 확인 가능한 정보로 계산한 모델 추정치다.
> 상금배분표의 일부 구간은 공식 기준점 사이를 보간했으며, 보간 방식에 따른 불확실성이 존재한다 — 예를 들어 이 페이지의 헤드라인 확률(31.9%)도 보간 방식을 바꾸면 최대 약 3.8%p 달라질 수 있다.
> **(신규)** 이 페이지가 계산한 것은 "2026시즌 상금순위가 60위 안에서 끝나는가"이다. 실제 다음 시즌 KLPGA 출전자격은 우승에 따른 자격 유효기간, 대회 등급별 기준 차이, 상금순위 외의 별도 자격 등 추가 공식 기준의 영향을 받을 수 있으며, 이 페이지는 그 기준까지 전부 반영하지 않았다.

**PUBLIC COPY**
> KLPGA 상금순위 60위는 다음 시즌 출전자격 논의에서 자주 언급되는 경계선이다. 10월 6일 현재 60위는 김새로미. 상금은 147,312,262원이다. 그렇다면 지금 60위니까 안전할까? NEO가 남은 시즌의 상금 이동을 60,000번 시뮬레이션했다. NEO 시뮬레이션에서 김새로미의 상금순위 Top60 확률은 31.9%로 계산됐다. 이유는 간단하다. 60위 커트라인도 함께 움직이기 때문이다.
> 상금순위표는 오늘의 위치를 보여준다. NEO는 그 위치에서 시즌 마지막 날 상금순위가 어떻게 끝날지의 가능성을 계산한다.

---

## 6. 실제 페이지 경로

**아직 어디에도 배포되지 않음.** 로컬 생성물: `artifacts/seed_race/public_build/index.html` (production `docs/`와 완전히 분리된 위치). 배포는 **DEPLOY HOLD** 상태 — `../SEED_ELIGIBILITY_GAP.md`의 5개 미확인 항목이 공식 규정으로 확인되거나, 사용자가 "상금순위 Top60 확률로만 공개해도 된다"고 명시 승인하기 전까지 어떤 경로로도 배포하지 않는다.

---

## 7. source-data 대조 결과

`verify_source_match.py` 전체 출력 기준 **129/129 PASS, 0 FAIL**. 상세 내역은 위 2번 및 스크립트 자체 참조.

---

```
[NEO SEED RACE PUBLIC BUILD — DEPLOY HOLD 용어 정정]

SOURCE COMMIT: e21e05b

DATA LOCK: PASS
HERO: PASS
TOP60 BUBBLE: PASS
WHAT-IF: PASS
P10/MEDIAN/P90: PASS
MOBILE 390×844: PASS
DESKTOP 1440×900: PASS
INTERNAL LANGUAGE: PASS
MODEL DISCLAIMER: PASS
SEED-ELIGIBILITY TERMINOLOGY (신규): PASS — "시드 생존확률"류 표현 전면 제거, scope-banner·methodology 고지 추가
SOURCE ↔ UI NUMERIC MATCH: PASS (129/129)

DEPLOY: HOLD (SEED_ELIGIBILITY_GAP.md 5개 항목 미확인)
```
