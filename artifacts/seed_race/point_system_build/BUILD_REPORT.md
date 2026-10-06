# 2027 포인트 시드 전쟁 — PUBLIC BUILD 보고 (확률 LOCKED, 사실 기반 콘텐츠만)

**기준**: 2027 시드 기준 전환 OFFICIAL PASS(`8642b0c`) + 이번 턴 OFFICIAL RELAY #3(TOP10 포인트 커브, IQT 독립시드 구조)

> **PUBLIC PROBABILITY = LOCKED.** 포인트순위 cutoff(몇 위까지 시드를 받는지)가 공식 발표에 없어, 이 페이지 어디에도 "시드확률 N%" 숫자가 없다. 대신 **확실히 공식 확인된 사실만** 보여준다: 제도 변경 자체, 실제 확보된 포인트 데이터 5명, TOP10 포인트 배점, 확정된 독립 시드(홍정민), 그리고 55~80위 버블존은 "포인트순위 확보 전"으로 정직하게 표시한다.

---

## 1. 왜 "빈 페이지"가 아닌가

사용자 지시("빈칸 페이지 금지")를 다음과 같이 해석해 적용했다: **빈칸을 가짜 숫자로 채우지 않되, 실제로 완성 가능한 모든 모듈은 완성한다.** 이 페이지에서 유일하게 "아직 확보 전"으로 비워둔 것은 55~80위 버블존 26명의 포인트순위 하나뿐이다 — 이것조차 "미확인" 대신 공란으로 두거나 숨기지 않고, **26명 전원을 명단으로 보여주되 각자의 상태를 "포인트순위 확보 전"이라고 명시**했다(선수명·현재상금은 이미 공식 확인된 값 그대로). 그 외 모든 섹션(제도 변경, TOP10 배점, 역전 사례, 독립 시드, 보류 이유)은 전부 실제 공식 데이터로 완성했다.

---

## 2. 변경/생성 파일

전부 `artifacts/seed_race/point_system_build/` — **production(`docs/`) 밖**, 아직 배포 안 함. 기존 `public_build/`(상금순위 Top60 페이지)는 건드리지 않았다.

| 파일 | 역할 |
|---|---|
| `build.py` | `point_table_PARTIAL_2026-10-06.csv`(5명), `remaining_events_point_PARTIAL_2026-10-06.csv`(HJ/S-OIL TOP10+제로앵커, 아이스버그 1위만), `seed_probability.csv`(55-80 버블), `eligibility_crosscheck_55_80.csv`(독립시드), 공식 상금순위 JSON을 직접 읽어 렌더링 |
| `index.html` | 생성된 페이지 본체 |
| `verify_source_match.py` | 독립 재파싱 검증(아래 4번) |
| `screenshot.py` | Playwright 캡처 |
| `screenshots/*.png` | 실제 렌더링 |
| `BUILD_REPORT.md` | 이 보고서 |

디자인은 기존 NEO GOLF DATA 팔레트/워드마크 그대로(재디자인 없음), `public_build/`와 동일한 CSS 변수 체계 사용.

---

## 3. 이번 턴에 추가 확보된 데이터 (OFFICIAL RELAY #3)

- **TOP10 포인트 커브**(10억~12억미만 구간, HJ·S-OIL 적용): 1위 70 · 2위 35 · 3위 33 · 4위 31 · 5위 29 · 6위 27 · 7위 25 · 8위 23 · 9위 21 · 10위 20 · **11위 이하 0**. 지난 턴엔 1~3위만 있었는데, 이번에 10위까지 + "11위 이하 0"이라는 완전한 커브를 받아 HJ·S-OIL 두 대회는 **포인트 배점표가 사실상 완성**됐다(11위 밖은 전부 0이므로 "몇 등까지"가 아니라 "0이 되는 지점"만 알면 전체 커브가 결정된다).
- 아이스버그골프·서울신문(15억 이상 구간)은 **여전히 1위=90만 확인**, 2위 이하는 미확보.
- **IQT(인터내셔널 퀄리파잉 토너먼트) 우승자 = 익년 정규투어 시드권**이라는 독립 자격 경로를 공식 구조로 추가 — 단 55~80위 구간에 해당자는 현재 확인된 바 없어 "조건부·미확인"으로 표시.

`point_simulation_SCAFFOLD.py`의 가드도 이에 맞춰 보강: "순위별 행이 40개 미만이어도, 포인트=0인 제로앵커 행이 있으면 그 대회는 완성된 것으로 인정"하도록 로직을 바꾸고, 실제로 HJ/S-OIL은 이제 가드를 통과(이벤트 커버리지 기준으로는)하지만 **선수 포인트 테이블이 5명뿐이라 전체 실행은 여전히 거부됨**을 직접 재테스트로 확인했다.

---

## 4. 테스트 결과

`python3 artifacts/seed_race/point_system_build/verify_source_match.py` — **140개 체크 전부 PASS**.

핵심 항목:
- **확률 숫자 전수 부재 확인**: "시드 확률"이라는 문구가 등장하는 모든 위치가 "확률 공개를 보류" 문맥인지 정규식으로 하나하나 확인(다른 문맥이면 FAIL), "확률" 근처에 `%` 숫자가 전혀 없음을 확인
- 5명의 money↔point 커넥터 행이 `point_table_PARTIAL_2026-10-06.csv`와 1:1 일치(이름/상금순위/포인트순위/포인트값), 공식 상금순위 JSON과도 재대조
- TOP10 커브 표가 CSV의 실제 값(70/35/33/31/29/27/25/23/21/20 + 11위이하=0)과 정확히 일치
- 55~80위 버블 26명 전원이 `seed_probability.csv`와 이름 일치, **전원 "포인트순위 확보 전"** 문구이고 숫자화된 포인트순위 주장이 단 하나도 없음을 확인
- "2027 시드 확보" 배지가 정확히 1개(홍정민, 66위)만 존재 — `eligibility_crosscheck_55_80.csv`의 GROUP B 1명과 일치
- 내부 용어(`GROUP A/B/C/D`, `RULE_CONFIRMED`, `gameCode`, `Gumbel` 등) 전수 부재

---

## 5. Desktop / Mobile 스크린샷

`screenshots/desktop_1440x900.png`, `screenshots/mobile_390x844.png` — 직접 열어서 확인함. 가로 스크롤 없음(`scrollWidth == clientWidth`). 모바일에서 홍정민 행(66위)을 크롭 확대해 "2027 시드 확보" 배지와 "포인트순위 확보 전" 라벨이 겹치지 않고 나란히 표시됨을 확인 — 두 사실(독립 시드 확보 여부 vs 포인트순위 데이터 유무)이 서로 다른 질문이라는 것이 시각적으로도 명확하다.

---

## 6. 실제 페이지 경로

**아직 어디에도 배포되지 않음.** `artifacts/seed_race/point_system_build/index.html`(production `docs/` 밖). 기존 `public_build/`(상금순위 Top60) 페이지와는 별개의 산출물 — 어느 쪽도 이번 턴에 서로를 대체하지 않았다. **DEPLOY는 계속 HOLD** — 포인트순위 cutoff와 55~80위 버블존 포인트 데이터가 확보되기 전까지는 이 상태를 유지한다.

---

```
[NEO 2027 POINT SEED WAR — INFORMATIONAL BUILD]

PUBLIC PROBABILITY: LOCKED (검증됨 — 어디에도 % 숫자 없음)
RULE CHANGE CONTENT: COMPLETE (공식 발표 기준)
TOP10 POINT CURVE: COMPLETE for HJ/S-OIL, PARTIAL for 아이스버그(1위만)
MONEY↔POINT REVERSAL: 5명 확보분 완성, 55-80 버블존은 PENDING(정직하게 표시)
INDEPENDENT EXEMPTION: 홍정민 CONFIRMED, IQT/K-10 구조 정의(해당자 없음)
SOURCE↔UI: PASS (140/140)
MOBILE: PASS
DESKTOP: PASS
DEPLOY: HOLD
```
