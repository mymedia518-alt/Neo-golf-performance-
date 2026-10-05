# Player Product Red-Team — Q1–Q7 per player

Product: `neo_klpga_shot_source/derived_analysis/artifact_data/player_product.html`
Source data: `player_product_data.json` ← `build_player_product.py` ← `build_player_deliverables_data.py`, all reading only already-verified committed files (`NEO_HOLE12_MASTER_TEMPLATE.md`, `NEO_HOLE12_DISTANCE_CALIBRATED_REPORT.md`, `NEO_HOLE1_FULL_ANALYSIS.md`, `hole12_distance_calibrated_analysis.json`, `hole12_master_template.json`, `hole1_full_analysis.json`, `neo_hole1_records.csv`, `neo_player_event_shot_metrics.csv`).

## 유해란

- **Q1 (yardage book만 봤으면 몰랐을 정보):** Hole 12에서 그녀의 유일한 더블보기가 "티샷+어프로치 연속 러프"일 때만 나왔다는 것, Hole 1에서는 실제 4라운드 전부 파 이상이고 벙커 2회 포함해도 전부 지켜졌다는 것 — 둘 다 실제 전적 데이터에서만 나오는 정보.
- **Q2 (실제 decision이 달라지는 점):** Hole 12에서 "그린까지 직접 안 가도 된다 — 러프에서도 1타 전진만 하면 방어된다"는 실제 근거 있는 damage-control 지침을 얻는다. 단순 "페어웨이를 지켜라"보다 구체적.
- **Q3 (다른 두 선수와 다른 이유):** 그녀만 두 홀 모두에서 real 4-round 샘플이 실수 사례 극소(H12 1회, H1 0회) — 데이터가 "현재 패턴 유지"를 가리킴. 이재윤(표본 부족), 박서현(회복력 약점)과 뚜렷이 다른 처방.
- **Q4 (observed tournament data까지 추적 가능):** 예 — 전략카드의 모든 숫자가 "실제 근거 보기" 테이블의 실제 4행(R1–R4, 티샷거리/라이/남은거리/어프로치라이/결과/스코어)과 직접 연결되고, 지도 점 클릭 시 동일 데이터가 팝업으로 뜬다.
- **Q5 (근거보다 강한 표현):** 없음 — Hole 1의 "큰 숫자 조건"은 명시적으로 "DATA INSUFFICIENT"로 표기, 실수 사례가 없다는 사실 이상으로 안전을 주장하지 않음.
- **Q6 (단순 "페어웨이를 지켜라" 이상):** 예 — "러프에 가도 1타 전진이면 방어 가능"은 페어웨이 유지보다 더 구체적인 손상관리 지침.
- **Q7 (완벽하지 않은 샷의 감당 범위):** 예 — NO-GO는 "짧은 거리+사이드 코리도 B"로 구체적 위치 지정, 그 전까지(사이드 코리도 B의 먼 거리권 포함)는 ACCEPTABLE로 명시.

## 이재윤

- **Q1:** Hole 1에서 유일한 보기가 그린을 "맞히고도" 3퍼트에서 나왔다는 것 — 세컨샷 거리/방향이 아니라 퍼팅이 실제 변수였다는 건 야디지북에 없음.
- **Q2:** Hole 12에서는 "실수 우선순위 UNKNOWN"이 명시되어, 캐디가 함부로 확신에 찬 지침을 주지 않도록 제한한다 — 이는 표본 부족을 숨기지 않는 실제 decision 영향(과신 방지).
- **Q3:** 세 선수 중 유일하게 Hole 12 개인 패턴이 "표본 부족으로 확정 불가"로 명시되고 field 근거만 적용 — 유해란(확정적 패턴)·박서현(확정적 약점)과 다른, "모른다"는 것 자체가 차별화.
- **Q4:** 예 — Hole 1의 "결과" 열에서 R3 행이 strokes=5(보기)로 실제 체인에서 직접 확인 가능.
- **Q5:** 없음 — "그린을 맞혀도 긴 퍼트면 3퍼트 위험"은 "추정, 표본 적음"으로 명시 격하됨.
- **Q6:** 예 — "그린을 맞혀도 끝이 아니다"는 단순 페어웨이/그린 적중 이상의 메시지(퍼팅 관리).
- **Q7:** 부분적 — Hole 12는 UNKNOWN으로 솔직히 비워둠(과도한 확신 대신), Hole 1은 "DATA INSUFFICIENT, 유일한 실수는 3퍼트"로 한계를 명시.

## 박서현

- **Q1:** Hole 12에서 field가 관찰한 최적 구역(센터 코리도)에 그녀의 실제 사거리가 거의 닿지 않는다는 것, 그리고 Hole 1에서는 정반대로 실제로 그 구역에 자주 도달한다는 것 — 같은 선수의 같은 유형 홀(Par4, 유사 거리)에서도 코스별로 전략이 뒤집힌다는 건 야디지북으로는 절대 알 수 없음.
- **Q2:** Hole 12에서 "field 최적구역을 억지로 노리지 말라"는 실제로 tee club/목표를 바꾸는 지침이 된다 — 안 닿는 목표를 주지 않음. Hole 1에서는 반대로 "현재 패턴 유지가 최우선"이 된다.
- **Q3:** 세 선수 중 유일하게 "회복력이 가장 약함(러프 파세이브 43%)"이 실제 숫자로 확인되고, 이것이 실수했을 때 우선순위("짧게라도 확실한 위치로")에 직접 반영된다 — 다른 두 선수는 이 문제가 없음.
- **Q4:** 예 — Hole 12 "실제 4라운드 착지: 사이드 코리도 A 4/4"는 테이블의 4행 landing_zone과 정확히 일치, 지도 위 실제 점(모두 사이드 A 근처)과도 시각적으로 일치.
- **Q5:** 없음 — Hole 12 ACCEPTABLE 칸에 "(본인 미검증)"을 명시해 그녀가 실제로 가본 적 없는 구역이라는 것을 숨기지 않음.
- **Q6:** 예 — "페어웨이를 지켜라" 수준이 아니라 "당신 사거리로는 field 1등 구역에 못 닿으니 짧은 구간 안에서 고르라"는 정반대 방향의 구체적 지침.
- **Q7:** 예 — "짧은 거리+사이드 코리도 B"가 "본인 사거리 안에서도 나올 수 있는 최악 조합"으로 명시, 그 직전 단계(사이드 코리도 A)는 ACCEPTABLE로 구분됨.

## 교차 검증 — 이름을 가려도 구분되는가

세 전략카드의 headline, send_distance, allowed/avoid, miss_priority, big_number_trigger를 모두 비교: 숫자(거리 범위)와 구조(IDEAL/ACCEPTABLE/DAMAGE CONTROL/NO-GO 내용)가 전부 다르고, 특히 박서현의 Hole12↔Hole1 역전과 유해란의 "사고 1회뿐"·이재윤의 "표본부족/퍼팅이슈"는 서로 대체 불가능한 문장이다. **이름을 가려도 세 선수임을 구분 가능 — PASS.**
