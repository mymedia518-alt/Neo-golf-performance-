# 김새로미 (KLPGA playerCode 8380) — 2026 시즌 Shot Tracker 아카이브

## 범위

- 출처: KLPGA 선수 기록(`getToursRecord`, 2026 정규투어)과 KLPGA Shot Tracker 선수별 응답
  (`POST /ajax/leaderboard/getShotTracker`, 파라미터 `gameCode, round, hole, playerCode`).
- 2026 시즌 정규투어 **26개 대회, 74라운드, 홀별 응답 1,332개, 샷 기록 5,369개**.
  선수 기록의 `joinGameNum`(26)과 라운드 점수 칸으로 기대 범위를 만들고, 원본과 1:1로 대조했다(아래 검증).
- 수집 오류 기록(`source/collection_errors.json`)은 빈 배열 `[]`이다. 빈 홀은 없다.
- 입력 ZIP: `kim_saeromi_2026_klpga_shottracker_raw.zip`
  (sha256 `c8c6e4fbcaf4…`, 전체 값과 파일별 해시는 `source/intake_c8c6e4fbcaf4.json`).

## 구조

```
kim_saeromi/
  README.md
  source/
    profile_getToursRecord_2026.json   KLPGA 선수 기록 원본 응답 (바이트 그대로)
    collection_errors.json             수집 오류 로그 원본
    official_schedule_2026.json        KLPGA 공식 일정 응답 (코스명·인/아웃 코스·gameMethod)
    intake_c8c6e4fbcaf4.json           입력 파일별 sha256·크기·저장 위치·처리 결과
  2026/
    raw/<gameCode>/player_shot/8380/R<라운드>/H<홀>.json   Shot Tracker 원본 응답 (바이트 그대로)
    normalized/events.csv  rounds.csv  holes.csv  shots.csv  정규화 자료 (원본에서 매번 재생성)
    index.json                                           건수·경로·연결 키
    validation/validation_report.{json,md}               검증 결과
    cmpro_raw/2026100005_browser_capture.json            KLPGA 3D Shot Tracker(cmpro) GPS 응답 18홀, 원본 그대로 (MANIFEST.json에 해시·검증)
    report/                                              시즌 리포트 1판, 실지형 3D, 평면 3D, 분석 스크립트
  source/terrain/blueheron_terrain_z15.json              블루헤런 지형 타일 원본 (AWS Terrain Tiles z15)
```

`official_schedule_2026.json`은 이 저장소 브랜치 `codex/yoo-hyunjo-raw-data-2025-2026`
(커밋 65cb858, `klpga_pipeline/data/players/yoo_hyunjo/source/`)에 이미 보존된 KLPGA 공식 응답을
바이트 그대로 복사한 것이다(sha256 `65e6ae24…bbc88c37`). 새로 수집한 자료가 아니다.

### 왜 이 구조인가

- **선수 단위 아카이브 위치**(`klpga_pipeline/data/players/<이름>/`, `source/`, `index.json`,
  `<시즌>/`)는 유현조 아카이브(`codex/yoo-hyunjo-raw-data-2025-2026`)의 규칙을 따랐다.
- **원본 경로**(`raw/<gameCode>/player_shot/<playerCode>/R<n>/H<nn>.json`)는
  `neo_klpga_shot_source/collector.py`가 `NEO_DATA_ROOT_LOCAL/raw/`에 쓰는 경로와 똑같다.
  유현조 아카이브는 다른 엔드포인트(`cmpro.klpga.co.kr/map3d`, 위경도형 필드)라서 라운드 축이 없는
  `hole_XX.json` 구조를 쓰지만, 이 자료는 `getShotTracker` 응답이고 라운드별로 따로 받는다.
  그래서 기존 Shot Tracker 도구(`collector.py`, `validate.py`, `schema.sql`)가 그대로 읽을 수 있는
  경로를 택했다.
- 정규화 컬럼은 `schema.sql`의 `klpga_player_shot`과 같은 필드를 담고, `schema.sql`은 수정하지 않았다.
  홀 정보와 공식 라운드 점수는 추가 스키마(`neo_klpga_shot_source/schema_player_season.sql`)에 넣었다.

## 연결 방식 (조인 키)

| 단위 | 키 | 파일 |
|---|---|---|
| 대회 | `game_code` | `events.csv` (공식 제목·날짜·형식·코스·공식 라운드 점수) |
| 라운드 | `game_code, round` | `rounds.csv` (샷 수, 파 합계, 공식 점수 대조 결과) |
| 홀 | `game_code, round, hole` | `holes.csv` (파·yds·meter·필드 평균·난이도 순위·baseHoleInfo 원값, 원본 경로·sha256) |
| 샷 | `game_code, player_code, round, hole, shot` | `shots.csv` (`schema.sql`의 정식 샷 키와 동일, `raw_json`에 원본 행 그대로) |

모든 정규화 행에는 `source_id`(`player_shot:<game>:<player>:R<n>:H<nn>:<sha256 앞 16자리>`)와
`raw_path`가 있어 원본 파일과 바이트 단위로 되짚을 수 있다.

## 필드 해석 원칙 (확인된 것과 안 된 것)

- `pp_state`: `collector.py`의 공식 KLPGA 라벨 표로만 이름을 붙였다. 이번 자료에는 표 밖 코드가 없다.
  상태 8(PENALTY_STROKE)은 샷 행으로 기록되며, 행 수가 공식 타수와 일치한다(벌타 포함).
- `pp_distance`: 홀아웃 샷 1,332개 모두 0.0이다. 남은 거리(홀까지)라는 기존 해석과 일치한다.
- 거리 단위: 파포·파파이브 1번 샷의 `pp_distanceLen + pp_distance`가 `holeInfo.yds`와 중앙값 −9.6
  차이, `holeInfo.meter`와는 +26.7 차이다(n=1,032). 야드와 같은 척도라는 **근거**이며,
  출처가 단위를 표기한 것은 아니다.
- `pp_x, pp_y`: 홀마다 따로 정의되는 화면 좌표다(이번 자료 범위 x 13~110, y 3~189).
  **위경도나 GPS가 아니다.** 기존 분석(`derived_analysis/NEO_COURSEMAP_VISUAL_SYSTEM.md`,
  `H*_coordinate_alignment_validation.json`)은 KLPGA 홀 이미지(650×433)에 대해 홀별 선형 변환을
  실측으로 맞춰 정렬했다. 홀이 다르면 원시 좌표끼리 비교하지 않는다.
- `pp_greenx, pp_greeny`: 그린 상세 이미지(`hole_N_G.png`)용 별도 좌표다. 그린 밖 샷은 이미지 범위를
  크게 벗어난다(y 최대 2,047).
- `pp_altitude`: 의미는 확정하지 않았다. **2026060003(한국여자오픈)에 −10000 값 8행**이 있다.
  센티널로 보고 원본 그대로 두었으며, 고도로 쓰면 안 된다(검증 J3).
- `baseHoleInfo`(`bi_sx, bi_sy, bi_gx, bi_gy, bi_gpx, bi_gpy`): `pp_*`와 범위가 다른 별도 좌표계다.
  기존 문서의 "`bi_gx/2, bi_gy/2` ≈ 핀" 관계는 이 자료에서 **재현되지 않았다**
  (홀아웃 지점과의 차이 중앙값 74, 1,332개 중 1 이내는 0개). 해석하지 않고 원값만 보존한다.
- `holeInfo.count`, `holeInfo.rank`, `bi_trueHole`: 원값 보존. `bi_trueHole`은 이번 자료에서 항상 `hole`과 같다.

## 검증 결과 요약 (`2026/validation/validation_report.md`)

결과 **PASS** — PASS 19, INFO 6, WARN 1 (FAIL 0).

- 공식 기록의 26개 대회·74라운드와 원본이 정확히 일치하고, 라운드마다 1~18번 홀이 모두 있다.
- 스트로크 플레이 70라운드 모두 **샷 행 수 = 공식 라운드 점수**.
- HJ중공업·동부건설 챔피언십(2026100004)은 `gameType`·공식 일정 `gameMethod`가 모두 `"2"`인
  매치플레이다. 공식 라운드 값(8, 13, 8, 4)은 타수가 아니므로 비교하지 않았다(검증 H2·H3).
- 홀마다 샷 번호가 1..n이고, HOLED(10)가 정확히 한 번, 마지막 샷에만 나온다.
- 독립 수집과의 교차 대조: 하이트진로 챔피언십(2026100005)은 그룹 엔드포인트로 전 필드를 따로 모은
  자료(브랜치 `collector-output/2026100005-shot-tracker-full-field`)가 있다. 김새로미 303샷이
  상태·거리·고도·좌표 모든 필드에서 일치했다(L1).
- 경고 1건: 위의 `pp_altitude` −10000 센티널 8행.

## 3D 리포트 활용 범위

**지금 바로 쓸 수 있는 것** (확보된 원본만으로)
- 홀별 샷 순서와 각 샷이 끝난 위치(`pp_x, pp_y`)와 상태(lie), 남은 거리, 샷 길이.
- 라운드별 홀아웃 지점(= 그 라운드 핀 위치가 찍힌 지점, 관측값).
- 홀별 파·yds·meter·필드 평균·난이도 순위. 공식 라운드 점수와 맞춘 라운드 합계.
- 하이트진로 챔피언십(블루헤런, 2026100005)은 저장소에 KLPGA 홀 이미지 18홀(`hole_images/`)과
  기존 정렬 검증이 있어, 2D 홀 지도 위에 샷을 올리는 것까지 가능하다.

**추가로 필요한 코스 자료** (샷 좌표로 지어내지 않음)
1. **나머지 25개 대회의 KLPGA 홀 이미지**(`/DATA/holeImg2/<gameCode>/<hole>.png`, `_G.png`) — 기존
   `fetch-hole-images-oneoff.yml` 워크플로로 대회별 수집 가능. 수집 후 홀별 좌표 정렬을 다시 검증해야 한다.
2. **티 위치**: 원본 1번 샷 행은 티샷이 *끝난* 위치다. 티 좌표는 원본에 확인된 형태로 없다
   (`bi_sx/bi_sy` 후보는 미검증).
3. **실제 지형(고도 모델)·그린 경사·해저드 경계**: 원본에 없다. `pp_altitude`의 의미도 확정되지 않았다.
   3D 지형은 코스 측량·DEM 등 별도 자료가 있어야 한다.
4. **지리 기준 정렬**(홀 이미지 ↔ 실제 코스 지도): 블루헤런 동코스 8번 홀만 공식 코스 지도와 정합
   검증이 있다(`course_maps/blue_heron/east/hole_08/registration/`). 다른 홀·코스는 각각 필요하다.
5. **대회 홀 번호 ↔ 실제 코스 홀**: 공식 일정의 인/아웃 코스 이름은 `events.csv`에 넣었지만,
   대회 홀 번호와 물리적 홀의 대응은 블루헤런 외에는 검증되지 않았다.

## 재실행

```bash
# 1) 보존 + 정규화 (원본은 덮어쓰지 않음; 같은 파일이면 건너뜀, 다르면 sha 접미사로 따로 저장)
python neo_klpga_shot_source/player_season_archive.py \
  --input kim_saeromi_2026_klpga_shottracker_raw.zip \
  --schedule <official_schedule_2026.json> \
  --root klpga_pipeline/data/players/kim_saeromi --season 2026 --player 8380 \
  --sqlite NEO_DATA_ROOT_LOCAL/normalized/kim_saeromi_2026.sqlite   # 선택, 커밋하지 않음

# 2) 검증 (FAIL이 있으면 종료 코드 1)
python neo_klpga_shot_source/validate_player_season.py \
  --root klpga_pipeline/data/players/kim_saeromi --season 2026 --player 8380 \
  --expect-events 26 --expect-rounds 74 --expect-hole-files 1332 --expect-shots 5369 \
  --cross-sqlite <full-field klpga_shots.sqlite>   # 선택

# 3) 기존 도구 호환 확인 (대회별)
python neo_klpga_shot_source/validate.py NEO_DATA_ROOT_LOCAL/normalized/kim_saeromi_2026.sqlite --game 2026030001
```

새로 수집할 때는 기존 `collector.py --game <code> --player 8380 --rounds .. --holes 1-18 --root <dir>`로
같은 경로 구조의 원본을 받은 뒤, 그 디렉터리를 `--input`으로 넣으면 된다.

## 리포트와 3D (2026-10-30)

| 폴더 | 내용 | 온라인 (claude.ai, 비공개) |
|---|---|---|
| `2026/report/season_report/` | 시즌 리포트 1판 | https://claude.ai/artifact/YZyxVzABQsPGMAjcxi1KFW |
| `2026/report/terrain_3d/` | 하이트진로(블루헤런) 실지형 3D, 샷 자동 재생. `prep.py`가 `data.json`을 만듦 | https://claude.ai/artifact/GTmE4ru3teYF1mymvsgYvL |
| `2026/report/flat_3d/` | KLPGA 홀 이미지 평면 3D | https://claude.ai/artifact/Hd1TkyMs2bz58ZHhPTTvDH |
| `2026/report/analysis/` | 시즌 타수 장부(`ledger.py`), 어프로치 분석(`approach.py`), 결과 JSON, 김새로미 공식 SG 기록(`sg_8380.jsonl`, `collector-output/sg-recovery-*` 브랜치에서 추출) | — |

- cmpro GPS 응답과 지형 타일은 2026-10-30 TJ가 PC 크롬 콘솔에서 받은 것이다(이 작업 환경은 klpga.co.kr·AWS에 직접 접속 불가).
- cmpro 응답의 `ShotNum 0`은 티 위치다. 1번 샷 `DistFromPrev`가 이 지점에서 잰 거리와 일치한다.
- 위경도로 잰 샷 간 거리와 `DistFromPrev`(yd)의 비율 중앙값 1.0001 — 좌표는 실제 WGS84, 거리 단위는 야드로 확인.
- KLPGA 홀 이미지 ↔ GPS 홀별 정합 오차 중앙값 1m 이하, 최대 1.9m. 지형과 실측 고도(450곳) 상관 0.991, 지형이 평균 3.75m 높아 보정.
- `2026/report/`의 `prep.py`, `ledger.py`, `approach.py`는 작업 당시 경로(작업 공간 scratchpad)를 가리키므로 다시 돌릴 때 경로를 이 저장소 기준으로 바꿔야 한다.
