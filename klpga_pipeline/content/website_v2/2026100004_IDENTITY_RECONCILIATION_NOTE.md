# HJ중공업·동부건설 챔피언십 (2026100004) — identity reconciliation (steps 1-4)

Source: real Windows acquisition, commit `9d40b92` (`evidence/hj_2026100004_entry_acquisition/RECONCILIATION_REPORT.json`), reshaped into `2026100004_CANONICAL_PLAYER_IDENTITY_V1.json` by `scripts/216_build_hj_2026100004_canonical_identity.py`.

## 1. 108명 identity 확정

- 공식 페이지 자체가 보고하는 총 참가자: **108** (자격자 104 + 추천자 4 + 초청자 0)
- 파싱된 행: 108/108, unparseable 0건
- Duplicate player_code: 0건, duplicate player_name: 0건
- Identity reconciliation: **MATCHED_EXISTING 105 / NEW_PLAYER 3** — 108명 전원 처리 완료, 누락 없음 (100% reconciliation PASS)
- Sponsor: 108/108 OK (캐시 재사용 88 + 실시간 조회 20) — 실제 소속 있음 90명, 공식 확인된 "소속 없음" 18명(공란, 추정 아님)
- 해외 선수: 3명

**`2026100004_TOURNAMENT_INFO.json`의 `field_size_evidence_type`이 이제 `OBSERVED (user relay)`에서 `CONFIRMED (real official entry list acquisition, commit 9d40b92)`로 업그레이드되어야 한다** — 108이라는 숫자가 더 이상 추정이 아니라 실제 공식 소스에서 직접 확인됨.

## 2. 신규 3명 (NEW_PLAYER — 기존 어떤 player_master/entry 파일에도 없던 선수)

| playerCode | 이름 | 국적 | 구분 | 공식 스폰서 | 비고 |
|---|---|---|---|---|---|
| 11426 | 김민서3 | KOR | 추천자 | HJ중공업 | 스폰서가 대회 주최사 자신과 동일 — 추천자(주최측 추천) 유형과 일치하는 실제 값, 추정 아님 |
| 10821 | 유아현 | KOR | 추천자 | (공란, 확인됨) | |
| 12472 | 이지유 0901(A) | KOR | 추천자 | (공란, 확인됨) | 이름 뒤 "0901(A)" 접미사 — 이 repo의 다른 선수 이름에서도 동일 패턴 관찰됨(예: 이시은 0901(A)), 그러나 "(A)"가 아마추어를 의미한다는 공식 근거는 이 repo에서 확인되지 않음 — **추정하지 않고 접미사 그대로 보존**만 함 |

## 3. 해외 선수 3명 (전부 MATCHED_EXISTING — 이전 대회에서 이미 확인된 선수)

| playerCode | 이름 | 국적 | 구분/자격 | 공식 스폰서 |
|---|---|---|---|---|
| 10789 | 리 슈잉 | CHN | 자격자 · 2025 일반대회 우승자 | 리쥬란 |
| 1485 | 빳차라쭈타 콩끄라판(I) | THA | 자격자 · 2025 시즌 IQT 우승자 | (공란, 확인됨) |
| 11770 | 짜라위 분짠(I) | THA | 자격자 · 2026 일반대회 우승자 | 하나금융그룹 |

## 4. Cutoff 고정

`2026100004_TOURNAMENT_INFO.json`의 실제 공식 `start_date=20261008` → **cutoff = 2026-10-08 (strictly before)**, 2023/2024/2025와 동일한 컨벤션("타겟 대회 자신의 시작일 당일부터 제외, 그 이전 모든 데이터만 pre-event로 인정"). target event(2026100004) 자체의 어떤 round/score 데이터도 prior-tournament manifest에 포함되어서는 안 됨 — 아직 시작도 하지 않은 대회이므로 자연히 0건.
