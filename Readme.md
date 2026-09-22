# NEO Golf Data

선수를 순위가 아니라 **플레이 방식**으로 읽는 골프 데이터 프로토타입.

## Player Intelligence

HOME / RANKING / TOURNAMENT / LEADERBOARD 어디에서든 선수 이름을 클릭하면
`/player/{playerCode}` 의 **Player Intelligence** 상세 페이지가 열린다.
프로필 페이지가 아니라 "이 선수는 어떤 골프를 하는 선수인가"에 답하는 분석 페이지다.

| Section | 내용 |
|---|---|
| 1 | Hero — 이름 + 한 줄 정의 + K-Ranking / NEO Ranking / Recent Form / Tournament Entry |
| 2 | AI Insight — 최근 5개 대회 변화 해석 (가장 큰 카드) |
| 3 | Player DNA — Accuracy / Aggression / Recovery / Pressure / Distance Consistency (0–100) |
| 4 | Shot DNA — Driver / Approach / Landing Distribution (inline SVG 차트) |
| 5 | Recent Evolution — Driver / Iron / Putting / Recovery / Pressure 추세 |
| 6 | Course Fit — 이번 대회 적합도 + Strength / Weakness |
| 7 | Hole Library — 최근 샷 테이블 (행 클릭 → 홀 상세) |
| 8 | AI Summary — 3줄 요약 |
| Right | Player Snapshot (sticky) — 최근 5경기 / 평균 순위 / 최근 컷 / Best Finish / 최근 상승 |
| Bottom | ← 이전 선수 · 다음 선수 → |

## 실행

```bash
npm start          # http://localhost:4173  (/player/{code} 라우팅 포함)
npm run capture    # Playwright Desktop / Tablet / Mobile 캡처 → screenshots/
```

정적 호스팅에서는 `vercel.json` / `_redirects` 의 리라이트 규칙 하나만 있으면 된다.

## 구조

```
assets/css/neo.css     디자인 시스템 (theme / color / radius / shadow 단일 소스)
assets/js/data.js      데이터 레이어 — 더미 데이터 생성기 (DB 교체 지점)
assets/js/charts.js    inline SVG 차트 컴포넌트 (외부 차트 라이브러리 없음)
assets/js/neo.js       공통 헤더 / 랭킹 / 리더보드 테이블
assets/js/player.js    Player Intelligence 렌더러
```
