# 2026100003 FR 종료 검증 자료 보존 기록

- 대회: 아이스버그골프 · 서울신문 오픈
- gameCode: `2026100003`
- 최종 라운드: FR (공식 round 3)
- 기록일: 2026-10-18
- 저장 브랜치: `neo-website-v2`

## 공식 결과

공식 우승자는 마서영(선수 ID `10083`), 최종 212타(-4)다. 성유진도 212타(-4)지만 공식 사이트가 동률 표시 없이 1위와 2위를 구분했다. 순위는 별도 재계산하지 않고 공식 텍스트를 따른다.

상태별 인원은 FINISHED 61명, CUT 41명, WD(R2) 5명, WD(R1) 1명으로 총 108명이다. round 4 공식 리더보드는 0건이어서 이 대회를 3라운드제로 확인했다.

## 저장된 대회 자료

다음 산출물과 원본은 저장소에 이미 존재하며, FR 종료 검증의 재현 자료로 함께 보존한다.

- 원본 공식 페이지 캡처 8개 및 SHA-256 manifest: `klpga_pipeline/content/website_v2/raw_capture/2026100003_fr/`
- 검증된 FR 공식 결과: `klpga_pipeline/content/website_v2/ICEBERG_2026100003_FR_OFFICIAL_V1.json`
- R2 종료 시점 예측 자료: `klpga_pipeline/content/website_v2/ICEBERG_2026100003_POST_R2_FORECAST_V1.json`
- FR 결과 생성/검증: `klpga_pipeline/scripts/257_build_iceberg_2026100003_fr_official.py`
- FR 페이지 빌더: `klpga_pipeline/scripts/258_build_iceberg_2026100003_fr_page.py`
- HOME 미러 승격 도구: `klpga_pipeline/scripts/259_promote_iceberg_2026100003_home_fr.py`
- 게시된 FR 페이지: `docs/tournaments/2026/2026100003/fr/index.html`
- HOME FR 미러: `docs/index.html`
- 기존 대회 사전 검증 보고서: `klpga_pipeline/reports/2026100003/VALIDATION_REPORT_V1.json`, `klpga_pipeline/reports/2026100003/REVIEW_REPORT_V1.md`

## 종료 검증 결과

이 기록은 작업 세션의 FR 종료 검증 보고를 보존한다.

- 61명 완주자 전원에서 R1 + R2 + FR 합계와 공식 총타수가 일치했다.
- 순위와 투파의 단조성 및 동률 그룹 자기정합성 검증을 통과했다.
- FR 리더보드에 포함된 선수별 R1/R2 타수와 기존 R2 공식 결과 간 불일치가 없었다.
- 렌더링된 108행(61 완주, 41 컷, 6 기권)을 공식 결과와 대조했을 때 순위/이름/R1/R2/FR/합계/상태 배지 불일치가 없었다.
- R2 예측값은 `sg_adjusted_top20`, `sg_adjusted_top10`, `sg_adjusted_top5`, `win_probability`를 그대로 표시했다. 재계산하지 않았다.
- 61명 완주자 중 57명은 예측값에 연결됐다. 선수 ID `8903`, `8906`, `10101`, `9823`은 원본 예측 자료의 `NO_BASE_FEATURE`에 따라 “데이터 부족”으로 표시했다.
- FR 표는 “FR 결과 61명”이며 컬럼은 순위, 선수, 합계, R1, R2, FR, TOP20, TOP10, TOP5, 우승확률 순이다. FR이 공식 round 3이므로 중복되는 R3 컬럼은 두지 않았다. 컷/기권 선수는 완주 순위표와 분리하고 기존 Missed cut 구분선과 CUT/WD 배지를 유지했다.
- 사용자 세션에서 보고된 데스크톱/모바일 확인: 모바일 390px에서 페이지 자체 가로 오버플로 없이 표 내부 가로 스크롤로 모든 확률 컬럼에 접근 가능; 우승자 표시, Missed cut, CUT/WD 및 “데이터 부족” 표시 확인.

## 테스트와 배포 증거

- 사용자 세션에서 보고된 관련 테스트는 클린 기준 커밋 `d9d07e81`에서도 동일한 6 failures / 14 errors였고 이번 작업에서 새 회귀는 없었다. 지목된 기존 문제는 Hitejinro 테스트 픽스처 누락(`2026100005`), `2026100004` game_code 하드코딩, `2026120001` 운영 데이터 쓰기 가드였다.
- 직접 확인 가능한 GitHub Actions의 Previous-tournament link E2E run은 [39107410661](https://github.com/mymedia518-alt/Neo-golf-performance-/actions/runs/39107410661)이다. 체크아웃 SHA는 `a49bb44914cffe1e8a834bb82491df2df4565508`; 4 passed, 1 skipped, 1 failed였다. 실패는 `test_hitejinro_r1_page_hero_includes_the_shared_previous_tournament_link`가 임시 fixture 내 `HITEJINRO_2026100005_POST_R1_FORECAST.json` 부재로 FileNotFoundError를 낸 것이다.
- 사용자 보고 기준 Pages 배포는 run [39107410102](https://github.com/mymedia518-alt/Neo-golf-performance-/actions/runs/39107410102), deployment `7151422363` 성공, 대상 커밋 `a49bb44914cffe1e8a834bb82491df2df4565508`이다. Pages artifact ID `12128878413`, SHA-256 `0b8cc877135f68c681ae6f2ed25f84f816c67513df604591c3451d8663837760`; 이 artifact는 2026-10-19 만료 예정이므로 이 보고서의 대회 원본/JSON/HTML이 장기 보존본이다.
- 저장소 운영 브랜치의 이후 확인된 HEAD는 `07545114b9c2db3b18170c8be25b7a670e5f7641`이며, 이번 보고서는 그 위에 추가됐다.

## 보존 범위와 남은 한계

작업 스크립트, 공식 원본 캡처, 검증된 JSON, 게시 HTML, 사용자 보고 검증 결과와 확인 가능한 CI 결과를 저장소에서 추적할 수 있도록 기록했다. 이 환경에서 원래 업로드된 이미지/GIF 경로는 파일을 찾을 수 없었고, 로컬 pytest 원문 로그 및 모바일 QA 스크린샷도 전달되지 않아 별도 원본 파일로 보존하지 않았다. 이를 생성하거나 검증된 증거처럼 재구성하지 않았다.

`docs/assets/neo.css`의 기존 보류 변경은 이번 저장 작업에서 수정하지 않았다.
