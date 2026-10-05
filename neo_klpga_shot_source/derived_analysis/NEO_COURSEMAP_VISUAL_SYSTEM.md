# NEO 코스맵 시각화 시스템 — H8/H9 Prototype

Blue Heron 공식 KLPGA Shot Tracker 코스맵(`neo_klpga_shot_source/hole_images/`, branch
`feat/cmpro-shot-data-v0`@`e25e79fb`, 36개 파일, 전체 650×433 검증 완료)을 배경이 아니라 분석 화면 그
자체로 사용한다. `map11_course_player_risk_matrix.png`는 **INTERNAL DIAGNOSTIC ONLY**로 유지 —
"어느 홀을 조사할 것인가"를 찾는 내부 도구이지 선수/캐디용 최종 화면이 아니다. 삭제하지 않았다.

## 1. 좌표 정렬 방법 (추측 없음, 실제 코드 기반)

KLPGA 사이트 자체 Shot Tracker 렌더링 JS(세션 scratchpad에 남아있던 `evidence_playerDetail_9115.html`
에서 직접 확인)에 이미 존재하는 공식 변환식을 그대로 재사용했다 — H8/H9용으로 새로 추정한 식이 아니다:

```
overview:  x = (390 - pp_y*2) * 1.815,  y = (pp_x*2) * 1.815     (SVG viewBox 0 0 708 471)
green:     x = (390 - pp_greeny*2) * 1.815,  y = (pp_greenx*2) * 1.815   (동일 공식, green_x/green_y에 적용)
```

708×471 뷰박스를 실제 fetch된 650×433 PNG에 맞춰 스케일(≈0.9181/0.9193)한 정확한 선형식(H1 분석에서
이미 검증된 상수, 재사용):

```
px = A·raw_y + B   (A=-3.3326271186440724, B=649.8622881355936)
py = C·raw_x        (C=3.337133757961783)
```

**H8/H9에도 동일 상수를 그대로 사용했다.** 새 transform을 추정하거나 눈대중으로 보정하지 않았다.

## 2. H8/H9 재검증 결과 (`H8_coordinate_alignment_validation.json`, `H9_coordinate_alignment_validation.json`)

이미지 자체의 픽셀 색상을 ground truth로 사용 — 눈대중 아님. "course mask"(흰 배경이 아닌 모든
픽셀)와 별도의 "water mask"(파란 픽셀)를 이미지에서 직접 추출해 각 실제 샷 좌표가 그 마스크 위에
떨어지는지 검증했다.

| 검증 항목 | Hole 8 | Hole 9 |
|---|---|---|
| FAIRWAY 샷이 코스 영역에 위치 | 100% (n=214) | 100% (n=168) |
| ROUGH 샷이 코스 영역에 위치 | 96.6% (n=238) | 96.2% (n=239) |
| PENALTY_AREA 샷이 **물 픽셀**에 위치 | 78.4% (n=37) | 100% (n=8) |
| GREEN 샷이 그린 상세도 영역에 위치 | 100% (n=542) | 100% (n=569) |
| R1~R4 실제 핀이 그린 영역 내부 | 4/4 PASS | 4/4 PASS |
| LOST_BALL(n=5, H8만) | 0% on-course — **코스 영역 밖에 떨어지는 것이 정상**(로스트볼의 정의 자체가 그려진 코스 폴리곤 밖), overall_alignment 판정에서 제외 |

**최종 판정: Hole 8 PASS, Hole 9 PASS.** 눈대중 보정 없이 통과했고, LOST_BALL의 "코스 밖" 결과는
결함이 아니라 오히려 정렬이 맞다는 추가 증거(실제로 로스트볼이 코스 그림 밖으로 벗어난 위치임)로
해석했다 — 이것을 억지로 "코스 안"으로 끼워 맞추려 하지 않았다.

## 3. 레이어 구조

```
[실제 KLPGA 코스 이미지]           ← 배경이 아니라 분석 화면 그 자체
  ↓
[전체 필드 context, 낮은 alpha]    ← 실제 관찰된 샷 좌표, 최종 스코어로 색칠(빨강=Bogey+, 회색=Par 이하)
  ↓
[3선수 R1~R4 실제 shot trace]      ← 전경, 색상=선수, 마커모양=라운드
  ↓
[실제 라운드별 핀 (그린 상세도)]   ← 노란 마커, 선수 approach endpoint와 직접 연결
```
FIELD는 맥락(흐리게), PLAYER는 이야기(진하게) — field 점 때문에 player chain이 묻히지 않도록 alpha와
zorder를 분리했다. WHOLE HOLE 패널은 TEE→그린 도달 직전까지만 그려 혼잡을 줄였고(과거 prototype에서
putts까지 전부 그렸을 때 선이 과도하게 겹치는 문제를 발견해 수정함), 짧은 게임(그린 주변 miss/
recovery/finish)은 GREEN DETAIL 패널에서만 표시한다.

## 4. 선 = 실제 기록, Actual Aim 아님

모든 연결선은 "실제 기록된 샷의 시작점 → 실제 종료 좌표"를 잇는 trace일 뿐이다. 선수의 실제 조준
의도를 암시하지 않는다 — 코드 주석에도 명시했고, 이 문서에도 명시한다.

## 5. 한국어 처리에 대한 제약

이 샌드박스 렌더링 환경에는 CJK(한글) 폰트가 설치되어 있지 않다 — 이번 세션의 모든 이전 차트
(chart1~6, chartA/B, map01~12)에서 이미 동일하게 확인된 제약이다. PNG 내부 텍스트(제목/범례)는
영어로 렌더링하고, 한국어 설명은 이 문서와 최종 보고 텍스트에서 제공한다. 한글 폰트를 설치할 수
있는 환경이라면(`fc-list`로 재확인 가능) 추후 PNG 자체에도 한국어를 직접 넣을 수 있다.

## 6. Red Team 자기 검토

| 질문 | 판정 |
|---|---|
| 코스맵이 단순 배경 장식인가? | 아니다 — 모든 레이어가 실제 픽셀 좌표에 정렬되어 분석 내용 자체를 구성 |
| 실제 위치가 분석의 중심인가? | 그렇다 |
| density가 표본 수 착시를 만드는가? | 낮은 alpha(0.22)의 raw scatter만 사용, 매끈한 heatmap/KDE로 뭉개지 않음 — 점 개수 자체가 눈에 보이는 투명도로 정직하게 반영됨 |
| pin 차이를 무시했는가? | 아니다 — R1~R4 핀을 전부 별도 마커로 표시, 라운드마다 실제 핀이 다름을 그대로 보여줌 |
| Actual Aim을 암시했는가? | 아니다 — 선은 기록된 trace일 뿐이라고 코드/문서에 명시 |
| 한 번의 catastrophe를 반복 패턴으로 보였는가? | H9 제목에 "R3/R4 only"를 명시해 4라운드 전체 반복이 아님을 숫자로 한정했다 — 실제로 R1/R2는 Par였다 |
| course risk와 player risk를 섞었는가? | 아니다 — H8/H9 비교 자체가 이 둘을 분리해서 보여주는 것이 목적 |
| first failure와 escalation을 섞었는가? | GREEN DETAIL 패널의 선이 approach→miss→recovery→finish 순서를 그대로 보여주므로 섞이지 않음(순서가 공간적으로 드러남) |
| result와 cause를 섞었는가? | 색상(빨강/회색)은 **result**(최종 스코어)만 인코딩 — 원인은 선의 경로 자체로 보여주지 라벨로 주장하지 않음 |
| 글을 읽어야만 이해되는가? | NO_TEXT_QA 버전에서 재확인: 색상(선수)·모양(라운드)·노란 핀마커·빨강 field dot만으로 "어디가 위험했고 선수가 어떻게 달랐는지"가 보인다 |

**최종 판정: PASS.** 근거: 좌표 정렬이 이미지 픽셀 자체로 재검증됐고(눈대중 아님), field와 player가
명확히 분리된 레이어로 공존하며, H8(코스 공통 위험)과 H9(선수별 반복 위험, R3/R4 한정)의 차이가 숫자
라벨 없이도 공간 배치만으로 드러난다.
