# NEO KLPGA 시드 레이스 — PUBLIC BUILD 보고

**기준 commit**: `e21e05b` (red-team 검증 완료, PASS WITH CORRECTIONS)

새 모델 없음. 확률 재조정 없음. 새 가정 추가 없음. `artifacts/seed_race/seed_probability.csv`, `seed_probability_whatif.csv`, `final_60th_money_distribution.csv`를 직접 읽어 렌더링했다(아래 1번 참조).

---

## 1. 변경/생성 파일

전부 `artifacts/seed_race/public_build/` 아래, **production(`docs/`) 밖**에 생성 — 아직 배포 안 함.

| 파일 | 역할 |
|---|---|
| `build.py` | CSV 3종을 직접 읽어 `index.html`을 생성(숫자 하드코딩 없음, 전부 소스에서 읽음) |
| `index.html` | 생성된 공개 페이지 본체 |
| `verify_source_match.py` | 생성된 HTML을 **독립적으로 재파싱**해 CSV·raw 시뮬레이션 배열과 숫자 대조(아래 7번) |
| `screenshot.py` | Playwright로 desktop/mobile 스크린샷 생성 + 가로 스크롤 오버플로우 검사 |
| `screenshots/desktop_1440x900.png`, `screenshots/mobile_390x844.png` | 실제 렌더링 캡처 |
| `BUILD_REPORT.md` | 이 보고서 |

디자인은 `docs/about/index.html`, `docs/tournaments/2026/kg-ladies-open/final/index.html`에서 그대로 가져온 NEO GOLF DATA 기존 색상/폰트/카드 스타일(재디자인 없음): `--bg:#dde5f3`, `--accent:#0f9488`, `--accent-blue:#2f5fd9`, "Big Shoulders Display"/"Noto Sans KR"/"Roboto Mono", N/E/O 워드마크.

---

## 2. 테스트 결과

`python3 artifacts/seed_race/public_build/verify_source_match.py` — **96개 체크 전부 PASS**, 실패 0건.

핵심 항목:
- CSV rank60 = 김새로미 / 147,312,262원 / 31.9% ↔ HTML hero 동일 텍스트 일치
- **raw 시뮬레이션 배열(.npz)을 CSV·build.py와 독립적으로 재계산**: n=60,000, survive=19,157, 31.9%로 반올림 일치
- `final_60th_money_distribution.csv`의 P10=164,840,244 / MEDIAN=172,303,371 / P90=180,291,768이 HTML과 정확히 일치
- 55~70위 16명 전원 player/money/prob_top60/median_final_rank CSV-HTML 1:1 일치
- 시드 기준선(SEED LINE) 마커가 정확히 60위와 61위 사이에 위치
- WHAT-IF 박결 6개 시나리오(현재/CUT/30위/20위/10위/5위) 전부 `seed_probability_whatif.csv`와 일치
- 금지 문구 "최소 1,750만원" 부재 확인
- 내부 용어(`simulation array`, `payout curve`, `log-linear`, `JSON`, `Plackett`, `Gumbel`, `τ`, `Monte Carlo` 등) 전수 부재 확인
- 모델 명칭 "NEO KLPGA 시드 레이스 시뮬레이션" 존재, 금지된 "경기력 예측"/"SG 기반"/"최근 경기력 기반" 부재 확인

전체 출력은 `verify_source_match.py` 재실행으로 재현 가능.

---

## 3. Desktop screenshot (1440×900)

`screenshots/desktop_1440x900.png` — 직접 열어서 눈으로 확인함. HERO(31.9% 헤드라인) → MOVING CUT LINE(P10/중앙/P90 바 차트) → SEED BUBBLE(55~70위, 60/61 경계선) → WHAT-IF(박결 ladder) → METHODOLOGY → PUBLIC COPY → footer 순서로 렌더링. 가로 스크롤 없음(`scrollWidth == clientWidth == 1440`), 숫자/표 깨짐 없음.

## 4. Mobile screenshot (390×844)

`screenshots/mobile_390x844.png` — 직접 열어서 눈으로 확인함. 가로 스크롤 없음(`scrollWidth == clientWidth == 390`), 선수명 줄바꿈 이상 없음, 확률 겹침 없음, 60위 기준선(강조 카드 + "시드 기준선" 빨간 배지)이 스크롤 중 즉시 인지됨.

---

## 5. 최종 공개 문안 (실제 렌더링된 텍스트 그대로)

**HERO**
> 현재 60위인데, 시드를 지킬 확률은 31.9%
> 현재 60위 · 김새로미 · 147,312,262원
> NEO 시드 생존확률 **31.9%**
> 현재 순위보다 중요한 것은 시즌 마지막 날의 순위다.

**MOVING CUT LINE**
> 60위선은 멈춰 있지 않는다
> 현재 60위 상금 147,312,262원
> 낮은 시나리오 164,840,244원(+17,527,982) · 중앙 시나리오 172,303,371원(+24,991,109) · 높은 시나리오 180,291,768원(+32,979,506)
> 지금의 147,312,262원은 중앙 시나리오 기준 60위 상금(172,303,371원)보다 낮다 — 현재 1억4,731만원이 시즌 종료 때는 안전선이 아닐 수 있다.

**SEED BUBBLE** (55~70위 표, 60/61 사이 "시드 기준선")

**WHAT-IF**
> 박결, 현재 68위 — 현재 11.2% · CUT 7.8% · 30위 8.8% · 20위 9.1% · 10위 10.6% · **5위 62.8%**
> 박결에게 "본선 통과 정도"(컷 탈락 → 20위)는 확률을 거의 못 바꾼다 — 상금이 10위에서 5위로 가는 구간에서 급등하기 때문에, 확실한 top5가 아니면 큰 의미가 없다.

**METHODOLOGY**
> 현재 상금순위와 확인된 남은 대회 상금 구조를 바탕으로, 남은 시즌을 60,000번 반복해 각 경우의 최종 상금순위를 다시 계산했다. 매번 경쟁 선수들의 상금도 함께 변한다. 따라서 단순히 "현재 60위 상금을 넘는가"를 계산한 것이 아니다.
> 이 확률은 경기 결과를 보장하는 값이 아니라, 현재 확인 가능한 정보로 계산한 모델 추정치다.
> 상금배분표의 일부 구간은 공식 기준점 사이를 보간했으며, 보간 방식에 따른 불확실성이 존재한다 — 예를 들어 이 페이지의 헤드라인 확률(31.9%)도 보간 방식을 바꾸면 최대 약 3.8%p 달라질 수 있다.

**PUBLIC COPY** (요청하신 원문에, 레드팀 체크13 기준으로 "실제...이다" → "NEO 시뮬레이션에서...계산됐다"로 1곳만 수정)
> KLPGA에서 다음 시즌 시드를 지키기 위한 가장 중요한 경계 중 하나가 상금순위 60위다. 10월 6일 현재 60위는 김새로미. 상금은 147,312,262원이다. 그렇다면 지금 60위니까 안전할까? NEO가 남은 시즌의 상금 이동을 60,000번 시뮬레이션했다. NEO 시뮬레이션에서 김새로미의 시드 생존확률은 31.9%로 계산됐다. 이유는 간단하다. 60위 커트라인도 함께 움직이기 때문이다.
> 상금순위표는 오늘의 위치를 보여준다. NEO는 그 위치에서 시즌 마지막 날 살아남을 가능성을 계산한다.

---

## 6. 실제 페이지 경로

**아직 어디에도 배포되지 않음.** 로컬 생성물: `artifacts/seed_race/public_build/index.html` (production `docs/`와 완전히 분리된 위치). 배포 승인 시 예상 경로는 `docs/seed-race/index.html`(기존 `docs/about/`, `docs/tournaments/.../` 패턴과 동일한 정적 경로 구조) — 단, 경로는 승인 후 확정.

---

## 7. source-data 대조 결과

`verify_source_match.py` 전체 출력 기준 **96/96 PASS, 0 FAIL**. 상세 내역은 위 2번 및 스크립트 자체 참조.

---

```
[NEO SEED RACE PUBLIC BUILD]

SOURCE COMMIT: e21e05b

DATA LOCK: PASS
HERO: PASS
SEED BUBBLE: PASS
WHAT-IF: PASS
P10/MEDIAN/P90: PASS
MOBILE 390×844: PASS
DESKTOP 1440×900: PASS
INTERNAL LANGUAGE: PASS
MODEL DISCLAIMER: PASS
SOURCE ↔ UI NUMERIC MATCH: PASS (96/96)

DEPLOY: NOT YET
```
