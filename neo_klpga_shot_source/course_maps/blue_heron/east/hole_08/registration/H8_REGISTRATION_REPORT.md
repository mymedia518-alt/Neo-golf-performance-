# H8 Registration: KLPGA Shot Tracker map ↔ Blue Heron official East Hole 8 visual map

## STEP 1 — Visual identity QA

H8_IDENTITY = **PASS**

관찰 가능한 공통 geometry만으로 판단:
- 전체 홀 형상: 양쪽 모두 완만하게 휘어진 길쭉한 형태(크레센트형) — KLPGA는 가로(티 좌측→그린 우측), Blue Heron 공식은 세로(티 하단→그린 상단)로 그려져 있으나, KLPGA를 약 90° 회전하면 동일한 형태.
- WATER: 둘 다 그린 바로 앞~옆에 호수형 수계가 있음. Blue Heron 공식 tip 텍스트("그린 바로 앞부터 100YD 지점까지 연못이 버티고 있어")와 두 이미지 모두 정확히 일치.
- GREEN: 둘 다 그린이 홀 끝단, 수계 바로 옆/뒤에 위치.
- FAIRWAY: 둘 다 중간에 뚜렷한 landing-zone(스트라이프 텍스처) 구간이 존재.
- BUNKER: 어느 이미지에도 명확한 벙커 형상 없음 — 공식 tip 텍스트에도 벙커 언급 없음("양측이 OB이며... 연못이 버티고"). 벙커 landmark는 만들지 않음(없는 것을 없다고 기록).

## STEP 2 — Landmark correspondence

**6개 landmark** 확보(`h8_registration_landmarks.json`). 워터·티마커는 색상 기반 connected-component 세그멘테이션(프로그램적, 좌표 재현 가능)으로, 나머지는 확대 crop 상에서 픽셀 판독. 그린~티까지 분산 배치(그린 주변에만 몰리지 않음).

| id | klpga(x,y) | blueheron(x,y) | confidence |
|---|---|---|---|
| L1_TEE | (14,194) | (276,534) | LOW — KLPGA는 티 패드 1개, 공식 맵은 실제 4개 티마커(red/orange/white/blue)가 따로 있어 구조적으로 1:1 대응이 아님. 3개(red/orange/blue) 중심점 사용 |
| L2_FAIRWAY_LANDING_CENTER | (325,152) | (242,315) | HIGH |
| L3_FAIRWAY_LANDING_TEE_END | (228,158) | (242,380) | MEDIUM |
| L4_FAIRWAY_LANDING_GREEN_END | (425,142) | (242,250) | MEDIUM |
| L5_WATER_CENTROID | (524,193) | (268,183) | MEDIUM — KLPGA는 수계 1개 덩어리, 공식 맵은 2개로 분리된 호수(component 분석으로 확인: n=3821/3046). KLPGA 단일 블롭을 그린쪽(가까운) 호수 하나에 매칭 |
| L6_GREEN_CENTER | (603,218) | (293,123) | HIGH |

벙커 landmark: **없음** (만들지 않음).

## STEP 3 — Transform comparison

| 모델 | train median/max (px) | **LOO median/max (px)** | 판정 |
|---|---|---|---|
| Similarity (4 DOF) | 4.9 / 7.0 | **7.4 / 12.6** | ✅ 채택 |
| Affine (6 DOF) | 4.6 / 6.6 | 10.6 / 27.9 | train만 보면 더 좋아 보이나 LOO에서 악화 — 과적합 |
| Homography (8 DOF) | 3.2 / 5.8 | 11.6 / **203.7** | train 최고지만 LOO max가 폭발 — 명백한 과적합, **기각** |

**가장 복잡한 모델을 자동 채택하지 않음.** Homography는 6개 점에 대해 8자유도라 거의 항상 training error가 가장 작게 나오지만, held-out 예측에서 1개 landmark가 203px나 빗나가는 것은 사용 불가능한 수준. Similarity는 train 수치가 셋 중 가장 크지만(그래도 median 4.9px) LOO가 가장 안정적이라 이것을 채택.

적합된 similarity: **회전 −89.88°(≈90°), 스케일 0.691, 평행이동 포함.** 즉 두 그림은 "같은 홀을 약 90° 돌리고 균일 축척한 것"이라는 가장 단순한 관계로 설명됨 — 왜곡(shear)이나 원근 차이를 가정할 필요가 없었다는 의미이며, 이 자체가 두 지도가 같은 실제 지형을 그렸다는 정체성 판정을 보강한다.

LOO median 7.4px ≈ 홀 전장(377yd) 환산 약 **6.8야드**, LOO max 12.6px ≈ **11.6야드**. 스타일화된 일러스트 간 정합으로는 합리적 — 레이저 거리계 수준은 아니고 "샷이 홀의 올바른 구역에 찍히는" 시각화 목적에 적합.

## STEP 4 — 3-player overlay

유해란(3샷)/이재윤(4샷)/박서현(5샷) R1 H8 실제 Shot Tracker 좌표(Phase 1 `blue_heron_h8_debug.json`의 map_x/map_y)에 similarity transform 적용.

**골프 geometry 정합성 확인(점이 코스 안에 있다는 것만으로 PASS 처리하지 않음):**
- 티샷 착지 거리 상대 순서가 실측 remaining-distance와 일치: 박서현(실측 159yd 잔여) 착지점이 유해란(실측 123yd 잔여)보다 티 쪽에 더 가깝게 찍힘(변환 좌표 y=283.6 vs 239.8, 홀 진행축 기준 박서현이 더 티 쪽) — 독립적인 실측 데이터와 교차검증됨.
- 어프로치/그린 도착 샷 전원이 실제 그린 형상(콩팥 모양) 위에 정확히 찍힘.
- 어느 샷도 물/숲/코스 밖 같은 불가능한 위치에 찍히지 않음.
- 샷 순서(1→2→3…) 선이 역행하거나 교차 폭주하지 않음.

**알려진 한계(정직하게 기록, registration 단계에서 새로 생긴 오차 아님):** 박서현 shot2(ROUGH, 실측 잔여 32.4yd)가 시각적으로 그린에 더 가깝게 찍힘 — 확인 결과 이는 **Phase 1에서 이미 검증된 KLPGA overview 원본 좌표 자체**의 근거리 축척 특성(그린 인근에서 일러스트가 실제 비율만큼 펼쳐지지 않음)이며, 이번 registration이 추가로 만든 왜곡이 아님. BH 좌표는 KLPGA 좌표를 그대로 이식했을 뿐이다.

## STEP 5 — RED TEAM

1. 티사이드 포인트 정확한가? → **부분적**. L1(TEE) LOO residual이 6개 중 최대(12.6px) — 구조적으로 설명됨(1개 티패드 vs 실제 4개 티마커), transform 결함이 아님.
2. 그린사이드 포인트 정확한가? → **양호**. L6(GREEN) LOO=6.7px, L4(그린쪽 스트라이프 끝) LOO=6.8px.
3. 워터 경계 registration이 드리프트하는가? → L5 LOO=7.9px, 드리프트 크지 않음. 단 KLPGA가 2개 호수를 1개로 단순화해 그렸을 가능성이 있어 근사치.
4. 하나의 transform이 홀 전체에서 작동하는가? → **대체로 그렇다**. LOO median 7.4px이 티~그린 전 구간에서 큰 이상치 없이 분포(12.6px가 최대). 단일 similarity transform으로 전체 커버.
5. 두 이미지가 다른 원근/투영을 쓴다는 증거가 있는가? → **없음**. Affine/Homography가 similarity 대비 LOO에서 더 나빠졌다는 것 자체가 "선형 원근 왜곡"이 유의미하게 필요 없다는 증거 — 있었다면 affine/homography가 held-out에서도 더 잘 맞아야 했다.
6. Homography가 실제 held-out 정확도를 개선하는가, 랜드마크에만 맞춰지는가? → **랜드마크에만 맞춰짐(과적합)**. 위 STEP 3 수치가 직접 증거.
7. 변환된 샷 중 불가능한 위치에 놓인 것이 있는가? → **없음**(STEP 4 확인).

## PASS GATE 체크

| 조건 | 상태 |
|---|---|
| same-hole identity confirmed | ✅ PASS |
| 충분히 분산된 실제 landmark | ✅ 6개, 그린에만 몰리지 않음 |
| held-out residual acceptable | ✅ median 7.4px(~6.8yd) — 시각화 목적엔 적합, 서베이 정밀도는 아님 |
| tee AND green 영역 모두 정렬 | ⚠️ **PARTIAL** — green/fairway 영역은 양호, tee 영역은 구조적 사유로 LOO 오차 최대(12.6px) |
| water/bunker geometry consistent | ✅ water 일치(벙커는 애초에 이 홀에 존재하지 않아 해당 없음) |
| 3-player shot path 골프적으로 타당 | ✅ PASS (실측 거리와 교차검증까지 확인) |
| invented landmark 없음 | ✅ 확인 |
| 육안 검사 PASS | ✅ `h8_landmark_qa.png`, overlay 이미지로 확인 |

**종합 판정: PARTIAL.** Fairway/water/green 영역과 3선수 오버레이는 PASS 기준을 충족하지만, tee 영역의 landmark 신뢰도가 구조적 사유로 낮아 "tee AND green 모두 정렬"이라는 게이트 조건을 엄격히 만족하지 못한다. 이 PARTIAL은 **registration 방법의 결함이 아니라 KLPGA 쪽에 실제 티마커 좌표가 없다는 데이터 한계**이며, 티샷의 실제 플롯은 "티박스"가 아니라 "티샷이 떨어진 지점"(이미 fairway/green 영역과 동일한 신뢰도)을 쓰므로 3-player 오버레이 품질 자체에는 영향이 적다.

Phase 2로 진행하지 않음. 다음 단계 전 사용자 판단 필요: 이 PARTIAL(티 영역 저신뢰, 나머지 양호)을 그대로 받아들일지, 추가 landmark(가능하다면 실제 티박스 위치)를 더 확보해 L1 신뢰도를 올릴지.
