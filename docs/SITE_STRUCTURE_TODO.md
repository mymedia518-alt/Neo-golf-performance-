# 실제 사이트 구조 확인 체크리스트

이 프로젝트는 개발 환경(Claude Code 클라우드 세션)에서
`klpga.co.kr` / `data.klpga.co.kr` 로의 아웃바운드 HTTPS 접속이
프록시 정책으로 차단되어 있는 상태에서 작성되었습니다. 따라서
`klpga/config.py`의 `ENDPOINTS`와 `klpga/selectors.py`의 CSS 선택자는
**전부 미확인 placeholder**이며, 실제 KLPGA 마크업과 다를 가능성이 높습니다.

인터넷 접속이 가능한 PC에서 아래 항목을 확인한 뒤 두 파일만 고치면
나머지 파서/어댑터/CLI 코드는 그대로 동작하도록 설계되어 있습니다.

## 1. 대회 목록 (Tournament List)

- [ ] 실제 URL 확인 (`klpga/config.py`의 `ENDPOINTS["tournament_list"]`)
- [ ] 정적 HTML에 표가 그대로 들어있는지, 아니면 JS로 렌더링되는지 확인
      (개발자도구 Network 탭에서 XHR/fetch 호출도 함께 확인 — API 엔드포인트가
      있다면 requests로 직접 호출하는 편이 더 안정적입니다)
- [ ] 대회명, 대회 상세 링크(및 그 안의 대회 ID), 기간, 상태(완료/예정/취소 등),
      대회 구분(정규투어/이벤트 등) 각각의 실제 CSS 선택자 확인
      → `klpga/selectors.py`의 `TOURNAMENT_LIST` 갱신
- [ ] `klpga/parsers/tournament_list_parser.py`의 `_extract_id_from_href`가
      실제 링크 형식(쿼리 파라미터 `?tid=...`인지, path 형식인지)에 맞는지 확인

## 2. 대회 상세 (Tournament Detail)

- [ ] 실제 URL 확인 (`ENDPOINTS["tournament_detail"]`)
- [ ] 코스명, 파(par), 야디지, 라운드 수가 노출되는 위치와 선택자 확인
      → `klpga/selectors.py`의 `TOURNAMENT_DETAIL` 갱신
- [ ] 표기 형식 확인 (예: "Par 72" 처럼 텍스트에 섞여 있는지, 숫자만 있는지)
      → 필요시 `klpga/parsers/tournament_detail_parser.py`의 정규식 조정

## 3. 리더보드 / 스코어카드 (Leaderboard)

- [ ] 실제 URL 확인 (`ENDPOINTS["leaderboard"]`)
- [ ] 순위, 선수명, 선수 상세 링크(선수 ID), 합계 스코어(오버파), 합계 타수,
      라운드별 타수 각각의 실제 선택자 확인 → `klpga/selectors.py`의 `LEADERBOARD` 갱신
- [ ] CUT/WD/DQ 등 완주하지 못한 선수의 표기 형식 확인
      → `klpga/rank_utils.py`의 `_CUT_MARKERS` / `_WITHDRAWN_MARKERS` /
      `_DISQUALIFIED_MARKERS`가 실제 표기와 일치하는지 확인
- [ ] 공식 SG(Strokes Gained) 등 추가 통계가 실제로 제공되는지 확인.
      제공된다면 `klpga/db.py`의 `player_event_stats` 테이블에 저장하는
      로직을 어댑터에 추가 (없으면 절대 채우지 말 것)

## 4. 예의(rate limiting) 관련

- [ ] `robots.txt` 확인 (`https://klpga.co.kr/robots.txt`,
      `https://data.klpga.co.kr/robots.txt`) 후 `klpga/config.py`의
      `MIN_REQUEST_INTERVAL_SECONDS`를 상황에 맞게 조정
- [ ] 과도한 요청으로 서비스에 부담을 주지 않도록 소규모(`--events 1~5`)로
      먼저 테스트할 것

## 5. 검증

- [ ] `python -m klpga.collect --events 1` 로 대회 1개만 수집해서
      `data/klpga_history.db`를 직접 열어 값이 실제 KLPGA 사이트와
      일치하는지 눈으로 대조
- [ ] 문제 없으면 `python -m klpga.collect --events 100`으로 확장
