# OK 복원 + 공개 언어 정리 — 보고서

기준: commit `21a8f07` (대회 기록 아카이브 + HJ scaffold) 이후, neo-website-v2 브랜치.

---

## 1. OK저축은행 읏맨 오픈 — 실제 기록 발견 위치

`docs/tournaments/2026/ok-savings-bank-open/*`는 953바이트 "공사중" placeholder였지만,
저장소 안에 **동일한 커밋 역사를 가진 백업 사본**이 이미 존재했다:
`docs_internal_archive/tournaments/2026/ok-savings-bank-open/{pre,r1,r2,r3,final}/index.html`.

### 원본 commit / 증거

- 잠금(lockdown) commit: **`ecf507d0c712cdb61f0ea3910f518a043e810828`**
  ("Lock down public site to main page only; every other docs/ path shows a construction placeholder")
  — 이 커밋의 메시지에 직접 명시: *"every other real page/data file is preserved (never
  deleted) under docs_internal_archive/ ... and replaced in place ... with a minimal
  Korean 'under construction' notice."*
- 검증: `git diff ecf507d^:docs/tournaments/2026/ok-savings-bank-open/pre/index.html
  ecf507d:docs_internal_archive/tournaments/2026/ok-savings-bank-open/pre/index.html`
  → **빈 diff**(완전히 동일) — 잠금 직전 공개 상태와 보존된 사본이 바이트 단위로 일치함을 확인.
- `git log ecf507d..neo-website-v2 -- docs_internal_archive/.../ok-savings-bank-open` →
  **빈 결과** — 잠금 이후 이 사본이 단 한 번도 수정되지 않았음을 확인.
- 빌드 메타: `<meta name="neo-build-source-commit" content="dc4511905db6f83528d212f820a792145b8f82d3">`,
  `<meta name="neo-build-id" content="20260909T195554Z">`.
- 선수 확인: 최예림 언급 PRE/R1/R2/R3 각 1회(FINAL 제외) — 사용자가 말한 "최예림 우승예측" 기록과 일치.

### 복원 원칙 적용

- **그대로 복원**(재작성/재계산 없음): `cp docs_internal_archive/.../ok-savings-bank-open/{f}
  docs/.../ok-savings-bank-open/{f}` — 5개 파일 전부 바이트 단위로 사본과 일치함을 `diff`로 재확인.
- **FINAL은 실제로 "아직 시작 전"이었다**: `final/index.html`은 "공식 FINAL 데이터가 아직 없습니다 /
  아직 시작 전" 상태 그대로다 — 이 세션(및 저장소 전체 76개 branch 중 조사한 다른 branch들)에서
  OK Open의 실제 완료된 FINAL 결과는 어디에도 없었다. R3(제목 "R3 (FINAL) 예측")가 실질적으로
  마지막으로 공개됐던 실제 콘텐츠다 — R2 결과 기반 R3/FINAL 승률 예측(최예림 99.340%)이며,
  **사후 결과를 반영해 수정하지 않았다**(원본 그대로).
- Archive 카드의 대회명 링크는 `r3`로 연결(실제로 마지막까지 공개됐던 페이지), FINAL 스테이지는
  (아래 2 절 규칙에 따라) 스테이지 링크 목록에서 제외.

### 다른 branch 조사 (교차검증)

OK Open 관련 commit 137개 전수 확인(`git log --all --grep`), 그 중 FINAL 경로를 가진 branch
6개(`feat/neo-auto-pipeline-v1`, `feature/player-intelligence-v1`,
`origin/claude/wizardly-dirac-txqytb`, `origin/feat/public-ui-tournament-dashboard-20260908-phase8-final`,
`origin/fix/ok-open-postround-regression-20260907`, `origin/neo-tournament-engine-v1`)의 FINAL 페이지를
직접 열람 — **전부** "아직 시작 전" 상태이거나 R3를 FINAL로 표시. 어떤 branch에도 실제 완료된
FINAL 결과는 없었다. 이것이 저장소 전체에서 확인 가능한 OK Open의 진짜 마지막 상태다.

---

## 2. 제15회 KG 레이디스 오픈 — 조사 결과

직전 턴에 "KG는 실제 분석 없음"으로 판정한 것은 **오류였다** — 당시 공개(`docs/`) 경로만 확인하고
`docs_internal_archive/` 백업 경로를 조사하지 못했다. 이번 턴에 재조사해 정정한다.

`docs_internal_archive/tournaments/2026/kg-ladies-open/{pre,r1,r2,r3,final}/index.html` +
`kg-ladies-open/index.html`(대회 허브 페이지)이 전부 실존하며, **완결된 실제 분석**이다:

- FINAL 페이지(49,620바이트)는 실제 우승자 **신다인**의 완주 스토리 — "신다인은 어떻게
  우승했나", "7.47%였는데 우승했습니다. 확률과 실제 결과는 같은 개념이 아닙니다" 같은 사후
  검증 섹션까지 포함된 완성된 포스트모템 페이지.
- OK와 동일한 lockdown commit(`ecf507d`)으로 보존됐고, 동일한 방식(`git diff` 빈 결과)으로
  보존 사본이 잠금 직전 공개본과 바이트 단위로 일치함을 확인.

**복원**: 6개 파일 전부(pre/r1/r2/r3/final + 허브 index.html) 그대로 복사, `diff`로 바이트 일치 재확인.
Archive 카드 이름 링크는 `final`(완결된 실제 결과)로 연결.

---

## 3. 대회 기록 최종 목록 (5개, 전부 동등)

| 대회 | 이름 링크 대상 | 실제 스테이지 |
|---|---|---|
| 제26회 하이트진로 챔피언십 | `/fr/` | 사전분석·R1·R2·R3·FR (최종검증·코스분석·딥다이브 전부 제외 — 11절 참조) |
| 하나금융그룹 챔피언십 | `/final/` | 사전분석·R1·R2·R3·FINAL |
| KB금융 골든라이프 챔피언십 | `/final/` | 사전분석·R1·R2·R3·FR·FINAL |
| OK저축은행 읏맨 오픈 (복원) | `/r3/` | 사전분석·R1·R2·R3 (FINAL 제외 — 실제로 없었음) |
| 제15회 KG 레이디스 오픈 (복원) | `/final/` | 사전분석·R1·R2·R3·FINAL |

5개 전부 "준비 중" placeholder 없이 동일한 "과거 NEO 기록" 카드로 표시된다.

---

## 4. 추가로 발견한 문제: 하이트진로 "딥 다이브" = self-flagged mock 데이터

`docs/tournaments/2026/2026100005/deep-dive/index.html`에
`<meta name="neo-stage-publication-ready" content="false">` +
`<meta name="neo-mock-data" content="true">`가 있다 — 저장소 전체에서 이 조합을 가진
유일한 파일(다른 모든 `neo-stage-publication-ready` 파일은 전부 `true`, mock 플래그 없음).
"DATA QUALITY / 수집 PASS / 검증 PASS / 라운드 PASS" 같은 내부 QA 라벨도 그대로 노출돼 있었다.

**1차 조치(지난 턴)**: 파일 자체는 건드리지 않고, archive 카드의 "딥 다이브" 스테이지 링크에서
제외해 click-through로 도달 불가능하게 했다.

**2차 조치(이번 턴, 사용자 지시)**: "Do not stop at the HiteJinro deep-dive leak" 지시에 따라
이 파일의 "DATA QUALITY / PASS / PASS / PASS" 블록을 실제로 정리했다.

- `<h2>DATA QUALITY</h2>` → `<h2>자료 안내</h2>`
- "수집/검증/라운드" 3개 값 `PASS` → `확인 완료`
- "출처: KLPGA", "플레이어: 107/107"은 원래부터 독자 언어였으므로 미변경
- 변경은 이 `<section id="data-quality">` 블록 4곳의 텍스트뿐임을 `difflib`으로 재확인
  (`DATA QUALITY`→`자료 안내`, `PASS`→`확인 완료` ×3 — 그 외 바이트 0건 변경)

**추가로 발견한 더 심각한 문제**: 같은 페이지에 `더미 성적 데이터 · 레이아웃 미리보기`,
`레이아웃 미리보기 — 더미 데이터 (6번홀 코스 정보/영상은 실제)`라는 **시각적으로 노출된
한글 문구**가 8곳 있다 — 영문 금지어 목록(PASS/FAIL/...)에는 없었지만 더 직접적으로
"이 페이지의 수치는 가짜"라고 선언하는 내용이다. 이것은 **정직한 공개(disclosure)**이지
숨겨야 할 내부 은어가 아니므로 **제거하지 않았다** — 지우면 가짜 수치를 진짜처럼 보이게
만드는 결과가 되어 이 프로젝트 전체의 "허구 데이터를 진짜처럼 보이지 않게 한다" 원칙에
정반대로 위배된다. 대신:
- 이 페이지는 **계속 archive 어디에서도 링크되지 않는다**(click-through로 도달 불가 유지).
- `klpga_pipeline/tests/test_archive_navigation_legacy_protection.py`에
  `test_dummy_data_disclosure_confined_to_the_known_mock_page_only`를 추가 —
  "더미"라는 단어가 이 한 파일에만 존재하고 다른 어떤 공개 페이지에도 나타나지 않음을
  회귀 테스트로 고정(다른 페이지에 나타나면 진짜 버그로 잡아낸다).

---

## 5. 내부 용어 Audit 결과

전수 스캔(사용자 제공 금지어 목록 + 확장 목록, script/style 제외 visible text 기준) —
`klpga_pipeline/tests/test_archive_navigation_legacy_protection.py::test_public_term_audit_zero_hits_in_visible_text`.

**0건** (제외: 위 4절의 self-flagged mock 페이지 1개, 의도적으로 click-through 경로에서
제외했으므로 공개 지면이 아님).

발견 당시 실제 히트 5건, 전부 수정:
1. `docs/index.html` — "예측 잠금" / "검증될 때까지" (HOME 공개 문구, 이번 턴에 작성한 것)
2. `docs/tournaments/2026/2026100004/index.html` — 동일 (HJ scaffold, 이번 턴에 작성한 것)
3. `docs/tournaments/2026/2026100005/deep-dive/index.html` — "PASS"×3 (→ 4절 방식으로 처리, 파일 자체는 미수정)

KB/하나/하이트진로/OK(복원)/KG(복원)의 **실제 분석 본문**에는 애초에 내부 용어가 없었다
(이 저장소가 과거 "Phase 8... developer-info removal" 작업을 이미 거쳤기 때문).

---

## 6. 변경된 공개 표현

| 이전 (내부 표현) | 이후 (독자 언어) |
|---|---|
| "예측 잠금" + "NEO 예측 모델이 스테이블포드 포맷에 대해 검증될 때까지 확률은 공개하지 않습니다" | "이번 대회는 변형 스테이블포드 방식으로 진행됩니다. 경기 방식에 맞춘 NEO 분석은 준비되는 대로 공개합니다." |
| meta description: "...예측 모델 검증 전까지 확률은 공개하지 않습니다" | "...변형 스테이블포드 방식으로 진행되며, 경기 방식에 맞춘 NEO 분석은 준비되는 대로 공개합니다." |

---

## 7. 숫자/데이터 Diff 결과

- **KB/하나/하이트진로**: `docs/tournaments/2026/{2026090002,2026090003,2026100005}/**`
  이번 턴에 **0바이트도 건드리지 않음** — `git status`로 확인, 기존
  `ARCHIVE_NAV_LEGACY_PROTECTED_MANIFEST.json` 해시 재검증 전부 PASS.
- **OK/KG**: 복원 파일은 `docs_internal_archive/`의 보존 사본과 바이트 단위로 100% 일치
  (`diff` 결과 전부 무출력) — 복원 과정에서 숫자·확률·순위·스폰서·결과 전부 원본 그대로.
  언어 정리 대상 용어도 원래 없었으므로 복원 후 추가 수정 없음.
- **DATA DIFF = 0 / PROBABILITY DIFF = 0 / RESULT DIFF = 0** 전부 확인. COPY DIFF는
  `docs/index.html`과 `docs/tournaments/2026/2026100004/index.html`(둘 다 이번 세션에서 새로
  작성한 파일, "레거시"가 아님) 2곳의 안내 문구뿐.

---

## 8. Click-through QA

`klpga_pipeline/scripts/archive_navigation_playwright_gate.py` — 1440×900 / 390×844 둘 다:
- HOME → 현재 대회 → HJ scaffold
- HOME → 대회 기록 → 5개 대회명 클릭 → 각 실제 기록 페이지
- 5개 대회 전부, 존재하는 모든 스테이지 링크를 실제로 클릭 → 200 응답(404 없음), mojibake 없음
- 하이트진로 "딥 다이브"가 archive 카드에 더 이상 없음을 확인
- javascript:void/#/빈 href 0건

**176/176 PASS.**

---

## 9. 알려진 기존 이슈 (이번 작업 범위 밖, 수정하지 않음)

복원된 KG 페이지 중 `pre/`, `r3/`, `final/` 3개가 모바일(390px) 뷰포트에서 **페이지 레벨
horizontal overflow**를 가진다(scrollWidth 682 vs clientWidth 390). `docs_internal_archive/`
원본과 바이트 단위로 동일한 콘텐츠이므로 **이번 복원이 만든 문제가 아니라 2026-09-09 잠금
이전부터 있던 레이아웃 이슈**다. 이번 작업 지시("디자인 변경 작업이 아니다", "LEGACY
PROTECTION: VISIBLE COPY ONLY")상 레이아웃/CSS 수정은 범위 밖이라 **건드리지 않고 그대로
보고만 한다.**

---

## 11. 하이트진로 공개 navigation 추가 정리 (최종 검증 · 코스 분석 제거)

사용자가 명시적으로 지정: 하이트진로 공개 stage는 정확히 `사전 분석 | R1 | R2 | R3 | FR`
— `최종 검증`(verification)과 `코스 분석`(course-analysis)은 (딥다이브와 달리 **실제로
publication-ready한 real 페이지**임에도) 공개 navigation에서 제외한다.

### 구현 — "존재함(real)"과 "공개함(public)"을 코드 레벨에서 분리

기존 `real_stages()`는 "디스크에 존재하고 공사중/mock이 아님"만 판정했다 — 이 기준으로는
verification/course-analysis가 통과하므로(둘 다 진짜 콘텐츠), 자동 discovery가 재빌드마다
계속 노출시킬 수 있었다. 이번에 `PUBLIC_STAGE_ALLOWLIST`를 추가해 "실제로 존재함"과 "공개
결정"을 분리했다:

```python
PUBLIC_STAGE_ALLOWLIST: dict[str, set[str]] = {
    "2026100005": {"pre", "r1", "r2", "r3", "fr"},  # 최종 검증·코스 분석 제외
}
```

`public_stages(dirname) = real_stages(dirname) ∩ PUBLIC_STAGE_ALLOWLIST[dirname]`
(allowlist가 없는 대회는 real_stages() 그대로 사용). Archive 빌더는 이제 `public_stages()`만
호출한다 — **향후 재빌드에서도 이 두 페이지는 allowlist를 직접 고치지 않는 한 다시 노출될 수
없다.** (요구사항: "자동 stage discovery가 해당 두 페이지를 다시 공개하지 않도록 ... 이후
archive rebuild를 해도 두 링크가 다시 살아나면 안 된다" — 충족.)

### 변경/미변경 확인

- **삭제 없음**: `verification/index.html`, `course-analysis/index.html` 둘 다 디스크에
  그대로 존재(파일 크기·내용 확인됨).
- **내용 미수정**: `git status`로 확인 — 이번 턴에 변경된 파일은 `docs/tournaments/index.html`
  (archive, 생성물)과 빌드 스크립트/테스트뿐, verification/course-analysis 파일 자체는
  0바이트도 건드리지 않음.
- **HOME/다른 공개 페이지**: `docs/index.html`, `docs/tournaments/2026/2026100004/index.html`
  어디에도 verification/course-analysis로 가는 링크가 없었음(원래도 없었음, 재확인만 함).
- **대회명 클릭 → FR 그대로**: archive 카드의 `<h2><a>` 링크는 변경 없이
  `/tournaments/2026/2026100005/fr/`.
- **OK/KB/하나/KG 변경 없음**: 4개 대회 전부 기존 stage 목록 그대로(하나 5개/KB 6개/
  OK 4개/KG 5개, 전부 재확인).

### 테스트

- `test_hitejinro_public_stages_are_exactly_pre_r1_r2_r3_fr` — stage-links가 정확히
  `[사전 분석, R1, R2, R3, FR]`인지, 이름 링크가 FR인지, verification/course-analysis
  URL·라벨이 archive HTML 어디에도 없는지, 두 파일이 삭제되지 않고 내용도 그대로인지 확인.
- `test_no_public_page_links_to_hitejinro_verification_or_course_analysis` — HOME/archive/
  HJ scaffold 3개 공개 페이지 전수 재확인.

### Playwright

`klpga_pipeline/scripts/archive_navigation_playwright_gate.py`에 하이트진로 카드 전용
체크 추가: `최종 검증`/`코스 분석` 미노출 확인 + PRE/R1/R2/R3/FR 5개 전부 실제 클릭해
공사중이 아닌 실제 페이지로 진입하는지 확인. **194/194 PASS**(1440×900 + 390×844).

---

## 12. 테스트

`klpga_pipeline/tests/test_archive_navigation_legacy_protection.py` — **62/62 PASS**
(이전 60 + 신규 2: 하이트진로 public stage 고정, HOME/archive/HJ 3개 페이지
verification·course-analysis 링크 부재 확인).

---

```
[NEO TOURNAMENT ARCHIVE — OK RESTORE + LANGUAGE CLEANUP — RESULT, v3]

OK 발견 위치: docs_internal_archive/tournaments/2026/ok-savings-bank-open/
OK 원본 commit: ecf507d0 (lockdown, 보존) / build-source dc451190
복원 stages: PRE, R1, R2, R3 (FINAL 제외 -- 실제로 없었음, "아직 시작 전" 그대로)
KG 조사 결과: 정정 -- 실제 분석 존재(docs_internal_archive), 전부 복원(PRE/R1/R2/R3/FINAL)
archive 최종 목록: 5개 전부 동등한 실제 기록 카드
하이트진로 공개 stage: 정확히 사전 분석 | R1 | R2 | R3 | FR
  (최종 검증·코스 분석 제거 -- real하지만 editorial exclusion, PUBLIC_STAGE_ALLOWLIST로
  real/public 판정을 코드 레벨에서 분리해 재빌드해도 재노출 불가능하도록 고정)
  파일 삭제 없음, 내용 미수정, HOME/archive/HJ 어디에도 두 페이지 링크 없음 재확인
하이트진로 딥다이브 "DATA QUALITY/PASS×3": "자료 안내"/"확인 완료"로 정리
  (difflib으로 이 4곳 텍스트만 변경됐음을 재확인, 그 외 0바이트)
하이트진로 딥다이브 "더미 데이터" 공개: 의도적으로 유지(정직한 고지, 삭제 시 가짜
  수치가 진짜처럼 보임) -- 이 페이지는 여전히 archive 어디서도 링크되지 않음,
  "더미" 단어가 이 1개 파일에만 있음을 회귀 테스트로 고정
내부 용어(PASS/FAIL/HOLD/LOCK/...) audit: 0건, 전체 공개 페이지 전수(딥다이브 포함)
공개 표현 변경: HOME + HJ scaffold locked-state 안내문 2곳 + 딥다이브 DATA QUALITY 블록
데이터/확률/순위/결과 diff: 0 (KB/하나/OK/KG/verification/course-analysis 전부 미변경)
click-through QA: 194/194 PASS (1440x900 + 390x844)
tests: 62/62 PASS
알려진 기존 이슈: KG 3개 페이지 모바일 overflow (레거시, 미수정, 보고만 함)
DEPLOY: HOLD
```
