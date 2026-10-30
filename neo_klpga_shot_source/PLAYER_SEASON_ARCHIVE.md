# Player-season Shot Tracker archive (보존 · 정규화 · 검증)

한 선수의 한 시즌 `getShotTracker` 응답을 저장소에 영구 보존하고, 조인 가능한 표로 정리하고,
KLPGA 공식 선수 기록과 대조하는 도구. 대회 단위 수집 도구(`collector.py`, `validate.py`,
`schema.sql`)는 그대로 두고 그 위에 얹는다.

| 파일 | 역할 |
|---|---|
| `player_season_archive.py` | ZIP 또는 디렉터리(→ `<game>/R<n>/H<nn>.json` 또는 collector의 `raw/<game>/player_shot/<player>/R<n>/H<nn>.json`)를 받아 원본을 바이트 그대로 보존하고 `events/rounds/holes/shots.csv`와 `index.json`을 만든다. `--sqlite`로 `schema.sql` + `schema_player_season.sql` SQLite도 만든다(커밋 대상 아님). |
| `validate_player_season.py` | 원본을 직접 읽어 공식 선수 기록·공식 일정과 대조하고, 정규화 CSV가 원본을 그대로 재현하는지 확인한다. `--cross-sqlite`로 다른 수집(예: 그룹 엔드포인트 전 필드)과 필드 단위로 대조한다. FAIL이 있으면 종료 코드 1. |
| `schema_player_season.sql` | 추가 테이블 `klpga_hole_info`, `klpga_player_round_official`. `schema.sql`은 수정하지 않는다. |
| `tests/test_player_season_archive.py` | 합성 픽스처 테스트(보존·멱등성·덮어쓰기 금지·타수 불일치 FAIL·collector 경로 입력). `python -m pytest neo_klpga_shot_source/tests -q` |

원본 정책은 `collector.py`와 같다: 원본 바이트는 바꾸지 않고, 이미 있는 경로에 다른 내용이 오면
sha256 접미사 이름으로 따로 저장하고 `CONFLICT_saved_with_sha_suffix`로 기록한다. 입력마다
`source/intake_<sha12>.json`을 남기며, 이전 입력 기록은 덮어쓰지 않는다(`_run<k>` 접미사).

공식 점수 대조는 스트로크 플레이(`gameType == "0"`)만 한다. 매치플레이(`"2"`)의 라운드 값은 타수가
아니므로 `NOT_COMPARABLE_NON_STROKE_FORMAT`로 남긴다. 이는 `klpga_pipeline`이
`gameMethod != "0"` 대회를 일반 타수 집계에서 빼는 규칙과 같다.

첫 적용 사례와 해석 원칙, 3D 활용 범위: `klpga_pipeline/data/players/kim_saeromi/README.md`.
