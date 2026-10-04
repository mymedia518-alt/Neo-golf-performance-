# NEO Reader — 공식 Player Profile 수집 구조 (2026-10-03 확정)

이 문서는 앞으로 NEO가 사용하는 KLPGA 공식 Player Profile 수집 구조를 기록한다.
모든 내용은 2026-10-03 GitHub Actions 실제 네트워크 세션에서 직접 확인한
실측 결과이며, 추측된 엔드포인트는 없다.

## 1. 왜 이 구조가 필요했는가

`PLAYER_PROFILE_ENDPOINT`(`/web/profile/mainRecord?playerCode=<code>`)의
HTML은 `<td class="avgScore"></td>` 등 통계 셀이 전부 빈 값으로 서버에서
내려온다 — 클라이언트 JS가 채우는 구조다. 이 세션(Claude Code 클라우드
샌드박스)은 klpga.co.kr에 대한 네트워크 접근이 차단되어 있어
JS를 실행하는 실제 브라우저로 직접 확인할 수 없었다. 대신 **GitHub
Actions 러너**(실제 인터넷 접근, `live-capture-r2-oneoff.yml`)로 해당
페이지의 인라인 `<script>`를 읽어 실제 데이터가 로드되는 AJAX 엔드포인트를
역추적했다.

## 2. 확인된 실제 엔드포인트

| 엔드포인트 | 메서드 | 용도 | 필수 파라미터 |
|---|---|---|---|
| `/load/profile/publicRecordSeasonDetail` | POST | 시즌 단위 공식 기록 (평균타수/버디율/GIR/페어웨이/드라이브거리/평균퍼팅/파브레이크율/벙커세이브율/리커버리율) | `playerCode`, `season`, `tourType`(기본 `RE`), `gameCode`(빈 문자열=전체) |
| `/load/profile/scoreDetail` | POST | 특정 대회의 라운드별·홀별 스코어카드 (PAR/실제타수/공식 분류 `par`/`birdies`/`bogeys`/`Dbogeys` CSS 클래스/누적 스코어) | `playerCode`, `gameCode`(실제 선수가 뛴 대회), `playerName` |
| `/load/profile/locationRecordSeasonDetail` | POST | SG 분해 + 티샷/어프로치/그린주변/퍼팅 상세(구간별 비거리/적중률, 투어 전체 평균 비교) — **확인만 완료, 파서는 아직 없음** | `playerCode`, `season`, `gameCode` |

세 엔드포인트 모두 jQuery `.load(url, params)` 호출로 발견했다 —
`.load()`에 객체 파라미터를 주면 항상 POST가 된다. 응답은 JSON이 아니라
HTML 조각(fragment)이다.

### 발견 방법 (재현 가능한 절차)

1. `live-capture-r2-oneoff.yml`을 대상 사람 페이지 URL로 dispatch (예:
   `/web/profile/{score,publicRecordSeason,locationRecordSeason}?playerCode=<id>`).
2. 받은 `live_raw.html`에서 `grep -oE "/load/profile/[a-zA-Z]+"`로 해당
   페이지가 실제로 호출하는 엔드포인트를 찾는다.
3. 해당 함수(`loadDetail()` 등)의 본문에서 실제 전달 파라미터를 읽는다.
4. 같은 워크플로를 `post_data` 입력(2026-10-03 추가, 하위호환 — 기본값
   빈 문자열이면 기존 GET 동작 100% 유지)으로 그 엔드포인트에 직접
   POST해 실제 응답을 받는다.

## 3. Reader 코드 구조

```
klpga_pipeline/src/klpga/
├── config.py
│   ├── PUBLIC_RECORD_SEASON_DETAIL_ENDPOINT   (신규, 확인됨)
│   └── SCORE_DETAIL_ENDPOINT                   (신규, 확인됨)
├── collectors/player_profile.py
│   ├── fetch_public_record_season_detail_html / parse_public_record_season_detail_html
│   └── fetch_score_detail_html / parse_score_detail_html
└── website_v2/official_detail_enrichment.py    (신규 모듈 — "Collector만 추가",
    │                                             새 Player History 엔진 아님)
    ├── collect_official_season_detail()
    ├── collect_official_scorecards()
    ├── compute_hole_distribution()
    ├── compute_round_momentum()
    ├── enrich_player_history_doc()              (기존 PLAYER_HISTORY.json에
    │                                             새 키만 추가, 기존 키 불변)
    └── run_official_detail_enrichment(player_id, player_name, ...)  ← 유일한
        진입점. playerCode만 바뀌면 동일하게 동작 (하드코딩 없음).
```

## 4. 선수 한 명을 수집하는 전체 파이프라인

### 4.1 최초 수집 (신규 선수, 실제 네트워크 필요 — GitHub Actions)

```
official_detail_enrichment.run_official_detail_enrichment(player_id, player_name)
    1. collect_official_season_detail()   → publicRecordSeasonDetail 실제 POST
    2. collect_official_scorecards()      → scoreDetail 실제 POST (PLAYER_HISTORY.json의
                                             tournament_history[*].game_code 재사용,
                                             새 game_code 추측 없음)
    3. PLAYER_PROFILE_RAW.json 저장        (원본 증거 계층, 재수집 없이 재계산 가능)
```

`PoliteHttpClient`가 실제 네트워크를 쓰므로 이 단계는 **GitHub Actions
러너에서 실행**해야 한다 (Claude 샌드박스는 klpga.co.kr 차단).
`fetch_*`/`parse_*` 함수는 완전히 분리되어 있어, 이미 받아둔 raw HTML이
있으면 `parse_*`만 샌드박스에서도 실행·검증 가능하다 (이번 세션은 이
방식으로 5명 전원 — 유현주 8436, 유해란 9115, 서교림 11134, 김민솔
10725, 김민선7 10097 — 의 파서 정확성을 실측 검증했다).

### 4.2 매번 리포트를 빌드할 때 — 엔진이 보장하는 순서 (2026-10-04 확정)

`build_player_report.py`는 PLAYER_HISTORY.json을 **다시 생성할 때마다**
official_detail_enrichment를 반드시 거치도록, 아래 순서를 코드로
강제한다:

```
python scripts/build_player_report.py --player-id <id>
        │
        ▼
[1/4] build_10097_player_history.main()
      reconcile + 창고 데이터만으로 PLAYER_HISTORY.json 1차 생성
      (official_detail_enrichment를 전혀 모름 — 여기서 멈추면
       official_detail_record 등 5개 필드가 전부 사라진다)
        │
        ▼
[2/4] official_detail_enrichment.reapply_cached_official_detail_enrichment(player_id)
      PLAYER_PROFILE_RAW.json이 존재하는가?
        있으면 → enrich_player_history_doc() 재적용, PLAYER_HISTORY.json
                 덮어쓰기 (재수집 없음, 네트워크 없음, 선수별 분기 없음)
        없으면 → 아무것도 하지 않고 스킵 (로그만 출력)
        │
        ▼
[3/4] page_188.build_one(player_id)   → docs/player/<id>/index.html
        │
        ▼
[4/4] page_189.build_one(player_id)   → docs/player/<id>/data-quality/index.html
```

즉 실제 실행 순서는
`build_player_report.py → PLAYER_HISTORY(1차) → official_detail_enrichment
→ PLAYER_HISTORY(최종) → HTML` 이며, [2/4]가 PLAYER_HISTORY.json을 HTML
빌드 **전에** 다시 덮어쓰므로 [3/4]/[4/4]가 읽는 PLAYER_HISTORY.json은
항상 enrichment가 반영된 최종본이다. `reapply_cached_official_detail_
enrichment`는 `player_id`만 받고, 그 안에서 분기하는 조건은
"이 player_id의 PLAYER_PROFILE_RAW.json이 존재하는가" 하나뿐이다 —
이름/ID로 분기하는 코드는 없다.

**2026-10-04 검증**: 10097(김민선7)의 PLAYER_PROFILE_RAW.json을 신규
생성한 뒤 코드 변경 없이 `build_player_report.py --player-id 10097`을
그대로 실행 — 첫 실행에 자동으로 enrichment가 적용되고
`docs/player/10097/index.html`에 `ph-neo-snapshot`이 처음으로 등장함을
확인했다. 이어서 10725/8436/9115/11134도 동일 스크립트로 재실행해
전원 "re-applied" 로그와 함께 PLAYER_HISTORY.json이 수렴함을 재확인했다
(10097 포함 5명 전원 동일 엔진).

## 5. PLAYER_HISTORY.json에 추가된 필드 (기존 필드는 전부 유지)

```
official_detail_record: {
    average_score, avg_birdie_per_round, birdie_rate, par_break_rate,
    eagle_count, hole_in_one_count, fairway_hit_rate, avg_driving_distance,
    avg_putts, gir_rate, bunker_save_rate, recovery_rate
}
hole_distribution: {
    counts: {Eagle, Birdie, Par, Bogey, "Double Bogey", "Triple Bogey+"},
    total_holes, double_bogey_avoidance_rate, source_rounds
}
round_momentum: {
    rounds: [{game_code, round, total_strokes, out_strokes, in_strokes}, ...]
}
```

**주의 — 정직하게 비워둔 항목**:
- `par_save_rate`(파세이브율)는 이 엔드포인트에 없다. `기존 totalRecord`
  소스(`OFFICIAL_PROFILE_NORMALIZED.json`)의 `par_save_rate`와 혼동하지
  않도록 이 enrichment는 그 이름을 쓰지 않고, 대신 실제로 존재하는
  `bunker_save_rate`(벙커세이브율, 다른 지표)만 기록한다.
- 값이 `null`인 필드는 "0"이 아니라 "KLPGA 응답 자체가 비어 있었다"는
  뜻이다 (예: 유해란 9115의 2026시즌 RE 집계 — 실제 서버 응답이 전부
  공란, 사유 불명, 추가 조사 필요 — 코드 결함 아님, 재현 가능).
- "Scrambling"·"Putting Average per GIR"은 이 두 엔드포인트에 직접적인
  라벨이 없다 — `avg_putts`/`gir_rate`로부터 유도 계산이 필요하면 별도
  논의 후 진행한다(현재 추가하지 않음, 임의 계산 금지 원칙).
- Player DNA / Course Fit은 기존 PLAYER_HISTORY.json의 `career_dna` /
  `course_profile` 필드가 이미 같은 역할을 한다 — 새 필드로 중복 생성하지
  않았다.
