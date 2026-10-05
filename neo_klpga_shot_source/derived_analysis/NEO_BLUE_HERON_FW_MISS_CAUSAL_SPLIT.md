# 페어웨이를 놓치고도 상위권에 간 이유: GOOD MISS였나, RECOVERY EXECUTION이었나?

**데이터**: 2026 하이트진로 챔피언십 RAW Shot Tracker + 기존 derived data만 사용 (pin_placement_72hole_audit.json, neo_three_player_spatial_chain.json의 tee-green axis/lateral threshold 재사용). 외부 데이터 없음, 새 좌표 보정식 없음.
**단위**: PLAYER × ROUND × HOLE. FW 적용 14개 홀(파4/5)의 FW 미스 이벤트 전수 = **1,832건**, 중복 없음.
**순서 준수**: RAW 추출 → (점수를 보지 않은) MISS QUALITY 정의 → MATCH → 그 다음에만 GIR/점수 공개. 결과를 먼저 보고 "좋은 미스"를 정의하지 않았다.

---

## 결론 첫 페이지

| 지표 | 값 |
|---|---|
| TOP10 FW MISS n | 205 |
| FIELD REST FW MISS n | 839 |
| TOP10 favorable next-shot condition % (점수 공개 전 정의) | 67.8% |
| FIELD REST favorable next-shot condition % | 61.3% |
| matched comparable events n (동일 홀+동일 라운드(핀)+동일 lie, ±10yd) | TOP10측 187건 / REST측 매칭 고유 585건 (총 pair 1,115개) |
| matched TOP10 → GIR % | 51.3% |
| matched REST → GIR % | 45.3% |
| matched TOP10 → Par+ % | 72.2% |
| matched REST → Par+ % | 65.0% |
| matched TOP10 → Bogey+ % | 27.8% |
| matched REST → Bogey+ % | 35.0% |

**RAW(미매칭) Par+ 격차 7.0%p → MATCHED(동일조건) Par+ 격차 7.2%p.** 미스 조건을 통제해도 격차가 줄지 않았다(오히려 완화폭이 ±5yd에서는 5.0%p로 작아졌다가 ±20yd에서는 8.2%p로 커지는 등 톨러런스에 따라 등락은 있지만, 전체적으로 7%p대에서 유지됨). 즉 "더 좋은 곳에 놓쳤기 때문"이라는 설명으로는 격차가 사라지지 않는다.

### 최종 판정: **TYPE B — RECOVERY DOMINANT**
> "비슷한 FW 미스 조건에서도 상위권 선수들은 이후 손실을 더 자주 제한했다."

근거는 아래 전개 순서대로 제시한다. (단, 5절의 김소정-홍지원 개별 비교는 이 필드 전체 패턴과 다른 결과를 보였고, 그 사실도 숨기지 않고 그대로 보고한다.)

---

## 1. RAW: FW MISS 이벤트 추출 (107명, 1,832건)

파4/파5 14개 홀의 티샷 중 `fw_hit=False`(state_code≠"1")인 모든 PLAYER×ROUND×HOLE을 RAW Shot Tracker에서 직접 추출했다(`blue_heron_fw_miss_event_level.csv`, 1,832행, 중복 없음 검증 완료). 각 이벤트는 다음을 포함한다: 선수/최종순위/라운드/홀/파/해당 라운드 핀 좌표(`pin_placement_72hole_audit.json`, 72개 라운드-홀 전수 VERIFIED)/티샷 종료 x,y/티샷 lie/remaining distance(야드, RAW `distance` 필드—그린 도달 샷에서 그 필드가 실제 퍼트 거리와 일치함이 기존에 검증된 authoritative 필드)/다음 샷 시작·종료 좌표/다음 lie/GIR/그린 도달 시 핀까지 거리/penalty 발생 여부/recovery_required/lateral 구역(LAT1-3, 기존 전체 필드 기반 tee-green axis 재사용)/최종 스코어.

**remaining distance는 그 샷 자신의 RAW `distance` 필드를 사용했다** — "다음 샷의 이동거리"로 역산하지 않았다(그 방식은 상태 분류가 불안정한 구간에서 오차가 생길 수 있어, 검증된 authoritative 필드를 직접 썼다). OB/페널티구역/분실구/벌타 상태(`state_code 4,5,7,8`)에서는 distance 필드가 신뢰 불가로 알려져 있어 `remaining_distance_reliable=False`로 명시 처리하고 분석에서 제외했다(추정하지 않음).

---

## 2. MISS QUALITY 정의 — 점수를 보지 않고 (순환논리 방지)

**LIE 4분류**(state_code 기준, 기존 코드베이스 LIE_NAME 매핑 재사용): ROUGH / BUNKER / PENALTY_AREA / OTHER(OB, 분실구, 벌타 등).

**REMAINING DISTANCE band**: 홀별로 그 홀의 FW-미스 remaining distance **실제 분포의 3분위**를 구해 NEAR/MID/FAR로 분류했다(예: H9는 83.6~173.4yd 분포에서 120.7yd/135.3yd가 경계; H10은 280.3~371.1yd 분포에서 311.2yd/322.6yd가 경계 — 홀마다 분포가 다르므로 홀별로 따로 계산).

**SPATIAL LOCATION**: 홀 전체 필드(107명)의 실제 티샷 착지점으로 구한 tee→green 축에 투영한 LAT1/LAT2/LAT3 구역(기존 `neo_three_player_spatial_chain.json`의 `tee_green_axes`/`lat_thresholds`를 그대로 재사용 — 이미 전체 필드 기준으로 계산되어 있었다). **주의**: 원 요청의 "±3/5/10yd 공간 반경" 매칭은 사용하지 않았다 — RAW의 x/y 좌표계가 홀마다 선형변환 계수가 다르고(H9 좌표 검증 파일 기준) 야드 환산이 전체 홀에 걸쳐 검증된 바 없어, 근거 없는 추정을 피하기 위해 LAT 구역(상대적 위치, 야드 아님) + remaining distance(실측 야드)로 대체했다. 이 대체는 보수적 선택이며, 아래 결과는 이 좌표계 제약 안에서의 결과다.

**PENALTY EXPOSURE**: 해당 hole-play의 어떤 샷이든 penalty 상태(OB/PENALTY_AREA/LOST_BALL/PENALTY_STROKE)가 한 번이라도 발생했는지.

**사전 등록한 FAVORABLE 정의(GIR·점수 미참조)**:
```
favorable_condition = (tee_lie_bucket == 'ROUGH') AND (dist_band in {NEAR, MID}) AND (penalty == False)
unfavorable_condition = (lie_severity >= BUNKER 이상) OR (dist_band == FAR) OR (penalty == True)
```
이 정의는 1,832건 전체에 먼저 적용했고, **이후 어떤 결과를 보고도 바꾸지 않았다.**

---

## 3. 그룹별 FW MISS 조건 비교 (아직 GIR·점수 공개 전)

| 그룹 | n | ROUGH% | BUNKER% | PENALTY_AREA% | OTHER% | NEAR% | MID% | FAR% | favorable% | unfavorable% | penalty% | 평균 remaining(yd) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TOP5 | 153 | 89.5 | 8.5 | 0.7 | 1.3 | 46.7 | 34.7 | 18.7 | **70.6** | 20.9 | 3.9 | 186.4 |
| TOP10 | 205 | 90.2 | 7.8 | 0.5 | 1.5 | 42.3 | 35.8 | 21.9 | **67.8** | 24.4 | 3.9 | 184.4 |
| TOP20 | 467 | 90.8 | 7.7 | 0.2 | 1.3 | 42.2 | 34.3 | 23.5 | 66.8 | 25.7 | 3.6 | 186.2 |
| FIELD REST | 839 | 92.4 | 6.7 | 0.1 | 0.8 | 34.4 | 34.3 | 31.3 | **61.3** | 33.3 | 3.0 | 192.0 |

**질문: 상위권의 FW MISS 자체가 하위권보다 덜 위험한 상태를 만들었는가? → 부분적으로 그렇다.** LIE 분포는 그룹 간 차이가 거의 없다(ROUGH 비중이 오히려 FIELD REST가 더 높다 — TOP5가 BUNKER 비중이 약간 더 높음, 8.5% vs 6.7%). 차이는 **DISTANCE**에서 난다: TOP5는 NEAR 46.7% vs FIELD REST 34.4%(12.3%p 차이), 평균 remaining distance도 TOP5가 5.6yd 짧다. 이 distance 차이 때문에 종합 favorable%는 TOP5 70.6% vs FIELD REST 61.3%로 9.3%p 차이가 난다. **즉 미스의 질(quality) 차이는 "어디로 놓쳤나"가 아니라 "얼마나 가까이 놓쳤나"에서 real하게 존재한다.**

---

## 4. MATCHING: 동일 조건끼리 맞춘 뒤 결과 비교

**매칭 기준**: 같은 홀 + 같은 라운드(=같은 핀, 라운드 간 핀은 10~73 map-unit 떨어져 있어 실제로 다른 위치임을 확인했으므로 "같은 라운드"를 엄격 기준으로 사용) + 같은 lie bucket + remaining distance 차이 허용오차(±5/±10/±20yd 민감도 검증).

| 허용오차 | matched TOP10 n | TOP10 GIR% | TOP10 Par+% | matched REST n(고유) | REST GIR% | REST Par+% | Par+ 격차 |
|---|---|---|---|---|---|---|---|
| ±5yd | 171/205 (83.4%) | 53.2% | 71.3% | 413 | 45.3% | 66.3% | 5.0%p |
| ±10yd | 187/205 (91.2%) | 51.3% | 72.2% | 585 | 45.3% | 65.0% | **7.2%p** |
| ±20yd | 194/205 (94.6%) | 50.5% | 72.2% | 714 | 44.4% | 64.0% | 8.2%p |

매칭 안 된 TOP10 이벤트(±10yd 기준 18건)는 **UNMATCHED로 남겼다**(억지로 짝짓지 않음). 참고로 이 18건의 결과는 GIR 33.3%, Par+ 50.0%, Bogey+ 50.0%로 매칭된 187건보다 뚜렷이 나쁘다 — 즉 "극단적으로 나쁜 미스"일수록 비교 가능한 FIELD REST 짝을 못 찾는 경향이 있다는 뜻이고, 이는 분석에서 억지로 포함하지 않은 것이 맞는 선택이었음을 보여준다.

**핵심 수치**: RAW(미매칭) Par+ 격차 = 70.2%(TOP10 전체) − 63.2%(FIELD REST 전체) = **7.0%p**. MATCHED(동일 조건) Par+ 격차 = **7.2%p**(±10yd 기준). **매칭 전후로 격차가 줄지 않았다** — 세 허용오차 모두에서 5.0~8.2%p 범위로 유지됐다. GIR 격차도 동일 패턴: RAW 49.8% vs 43.0%(6.8%p) → MATCHED 51.3% vs 45.3%(6.0%p, ±10yd). **조건을 통제해도 격차가 사라지지 않는다는 것은, 3절에서 확인된 "거리가 더 가까운" 질적 차이가 이 결과 격차의 주된 원인이 아니라는 뜻이다.**

---

## 5. 세 효과의 분리

- **A. MISS QUALITY EFFECT** (더 좋은 next-shot condition을 만든 효과): 3절에서 확인 — distance 측면에서 real하게 존재(TOP5 평균 5.6yd 더 가까움, favorable% 9.3%p 높음). 그러나 **4절에서 이 효과를 통제해도 결과 격차가 줄지 않아, 이 quality 차이가 결과 격차의 설명력을 갖는다는 증거는 약하다.**
- **B. RECOVERY EXECUTION EFFECT** (비슷한 조건인데도 다음 샷 결과가 더 좋았던 효과): 4절의 matched 비교가 직접 증거다 — 동일 홀·동일 라운드(핀)·동일 lie·거리 ±10yd 조건에서 TOP10이 REST보다 GIR +6.0%p, Par+ +7.2%p, Bogey+ −7.2%p. **세 허용오차 모두에서 재현됨.**
- **C. DOWNSTREAM SCORE PRESERVATION** (GIR 실패해도 Bogey+로 안 번진 효과): matched TOP10의 GIR 51.3%인데 Par+ 72.2% — 즉 GIR 못 해도 20.9%p만큼 추가로 파를 지켰다(숏게임 세이브). matched REST는 GIR 45.3%, Par+ 65.0%로 19.7%p 추가 세이브. **이 폭 자체는 TOP10과 REST가 거의 같다(20.9%p vs 19.7%p)** — 즉 "그린을 놓쳐도 파를 지키는 숏게임 세이브 능력"은 매칭된 조건에서는 TOP10과 REST가 비슷하고, 오히려 **GIR 자체를 더 많이 만들어내는 것**(B의 핵심)이 TOP10의 주된 우위다.

### 보조 검증: 로지스틱 회귀 (OBSERVATIONAL CONDITIONAL ASSOCIATION, 인과 아님)
종속변수 Par+ 여부, 설명변수: lie bucket, distance band, hole 고정효과(13개 더미), round(3개 더미), TOP10 indicator. (ranked 1,291건 사용; PENALTY_AREA/OTHER lie는 표본이 희박해 추정이 불안정함을 명시한다.)

| 변수 | coef | SE | z | OR |
|---|---|---|---|---|
| dist_FAR (vs NEAR) | −0.884 | 0.156 | −5.66 | 0.41 |
| lie_BUNKER (vs ROUGH) | −0.291 | 0.265 | −1.10 | 0.75 |
| **TOP10_indicator** | **+0.219** | 0.176 | **+1.24** | **1.25** |

lie와 distance band, hole, round를 통제한 뒤에도 TOP10_indicator는 **방향은 4절의 matched 결과와 일치(양의 연관성, Par+ 가능성 ↑)하지만, 통상적 유의수준(z≥1.96)에는 못 미친다(z=1.24)** — 다수의 더미변수로 셀이 얇아진 영향으로 보인다. 이것은 인과효과가 아니라 **관측적 조건부 연관성**이며, 4절의 matched-pair 비교(표본이 더 크고 사전등록된 1차 방법)가 이 보고서의 주된 근거다.

---

## 6. 김소정(25건) vs 홍지원(16건) — 전부 하나씩 비교

**STEP 1: 점수를 숨긴 상태에서 miss quality만 비교**

| | 김소정(n=25) | 홍지원(n=16) |
|---|---|---|
| favorable_condition% | **80.0%** | **37.5%** |
| unfavorable_condition% | 12.0% | 62.5% |
| 평균 remaining distance | 178.2yd | 212.7yd |

**김소정의 미스가 홍지원의 미스보다 "원래" 훨씬 덜 위험했다(favorable 42.5%p 차이).** 이건 결과를 보기 전에 LIE+거리+penalty만으로 나온 숫자다.

**STEP 2: 점수 공개**

| | 김소정 | 홍지원 |
|---|---|---|
| GIR% | 60.0% | 50.0% |
| Par+% | 68.0% | 50.0% |
| Bogey+% | 32.0% | 50.0% |

RAW Par+ 격차 = 18.0%p.

**STEP 3: 비교 가능한 조건끼리 매칭** (같은 홀, 같은 lie bucket, 거리차 ±10yd, 라운드 무관 — 두 선수만 비교하므로 표본 확보를 위해 라운드 제약을 완화했다)

매칭된 김소정 이벤트: **5건**, 매칭된 홍지원 비교군: **4건**(표본이 매우 작음 — 아래 수치는 참고용이며 확정적 결론의 근거로 쓰지 않는다).

| | 김소정(matched, n=5) | 홍지원(matched, n=4) |
|---|---|---|
| GIR% | 40.0% | 100.0% |
| Par+% | 60.0% | 75.0% |

**매칭된 소표본에서는 격차가 역전된다**(홍지원이 오히려 높음). n이 너무 작아(4~5건) 이 역전 자체를 "홍지원이 회복력이 더 좋다"는 결론으로 쓸 수 없지만, 최소한 **"김소정이 홍지원보다 회복을 더 잘해서 격차가 났다"는 주장도 지지되지 않는다.**

### 답: 김소정 68% vs 홍지원 50% 격차는 GOOD MISS 때문인가, RECOVERY EXECUTION 때문인가?
**이 특정 쌍(pair)에 대해서는 → 압도적으로 GOOD MISS(MISS QUALITY) 때문이다.** 김소정의 미스가 홍지원의 미스보다 애초에 42.5%p 더 유리한 위치였다(favorable_condition 80.0% vs 37.5%). 동일 조건으로 맞춘 소표본(n=4~5)에서는 회복 실행력의 우위가 확인되지 않았다(오히려 반대 방향). **이것은 5절의 필드 전체 패턴(TYPE B, 회복 실행력 우위)과 다르다 — 김소정-홍지원 개별 비교는 필드 전체의 "회복 실행력" 스토리의 대표 사례가 아니라, 오히려 "미스의 질 차이가 결과를 가른" TYPE A에 가까운 개별 사례다.** 이전 보고서에서 이 쌍을 회복력 우위의 대표 사례로 제시한 것은, 이번 조건 통제 분석 결과 정확하지 않았다.

---

## 7. 유해란(1위) 20개 FW MISS 전수 분류

| R | H | lie | dist(yd/band) | favorable | next lie | GIR | approach거리 | score |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | BUNKER | 156.3 NEAR | X | GREEN | O | 6.4 | Par |
| 1 | 6 | ROUGH | 156.2 NEAR | O | GRNSD BUNKER | X | 2.8 | Par |
| 1 | 7 | ROUGH | 258.2 NEAR | O | ROUGH | O | 13.4 | Par |
| 1 | 9 | ROUGH | 143.8 **FAR** | X | ROUGH | X | 0.4 | **Par** |
| 1 | 18 | ROUGH | 272.3 NEAR | O | FAIRWAY | X | 0.7 | Par |
| 2 | 1 | BUNKER | 136.2 NEAR | X | ROUGH | X | 3.5 | Par |
| 2 | 7 | ROUGH | 263.1 NEAR | O | FAIRWAY | O | 1.5 | **Birdie** |
| 2 | 12 | ROUGH | 154.8 MID | O | ROUGH | X | 1.2 | Double |
| 2 | 18 | ROUGH | 249.0 NEAR | O | FAIRWAY | O | 3.3 | Par |
| 3 | 3 | ROUGH | 183.2 NEAR | O | ROUGH | X | 0.8 | Bogey |
| 3 | 6 | **LOST BALL** | — (불가) | X | PENALTY STROKE | X | 6.0 | Bogey |
| 3 | 7 | BUNKER | 289.5 MID | X | FAIRWAY | O | 12.1 | **Par** |
| 3 | 12 | ROUGH | 120.0 NEAR | O | FRINGE | X | 1.3 | Par |
| 3 | 17 | BUNKER | 116.8 NEAR | X | GREEN | O | 15.7 | **Birdie** |
| 4 | 3 | ROUGH | 179.2 NEAR | O | ROUGH | X | 0.8 | Par |
| 4 | 8 | ROUGH | 127.1 NEAR | O | ROUGH | X | 1.1 | Par |
| 4 | 9 | ROUGH | 103.5 NEAR | O | GREEN | O | 5.3 | Par |
| 4 | 14 | ROUGH | 147.2 MID | O | GREEN | O | 20.9 | Bogey |
| 4 | 15 | ROUGH | 158.3 MID | O | GREEN | O | 15.0 | Par |
| 4 | 18 | BUNKER | 264.5 NEAR | X | FAIRWAY | X | 0.5 | Par |

- favorable_condition: 13/20 (65%), unfavorable_condition: 2/20 (10%), 나머지 5건은 중립(어느 쪽에도 안 걸림, 주로 BUNKER+NEAR+no-penalty 조합).
- favorable일 때 Par+: 10/13 = **76.9%**
- unfavorable일 때 Par+: 1/2 = 50.0%
- 전체 Par+: 16/20 = 80.0%(13절 확인치와 일치)

**16/20 Par+가 좋은 미스가 많아서인지, 비슷한 나쁜 미스에서도 회복했기 때문인지, 둘 다인지:**
**둘 다다.** favorable 조건에서는 실제로 Par+ 비율이 더 높다(76.9% vs 50.0%) — 좋은 미스가 유리했던 건 맞다. 그러나 **unfavorable/중립 조건에서도 파를 지킨 사례가 다수** 있고, 특히 아래 두 사례는 "나쁜 미스에서의 회복"을 직접 보여준다.

### 유해란의 가장 나쁜 FW MISS 조건에서도 Par를 지킨 실제 사례
- **R1 H9**: lie=ROUGH, remaining=143.8yd이지만 그 홀 기준 **FAR band**(그 홀 미스 중 가장 먼 쪽) — GIR도 못 했는데(X) **Par**. GIR 없이 숏게임으로 막은, 순수 회복 실행력 사례.
- **R3 H7**: lie=BUNKER(불리한 lie) + MID band — 그런데도 GIR에 성공해 **Par**. 벙커에서도 어프로치를 그린에 올린 사례.

---

## 8. GOOD MISS → BAD RESULT (FW% 높은 하위권 선수)

FW%가 필드 평균(60.5%)보다 높은 rank 20위 밖 선수들 중, next-shot condition이 favorable(점수 공개 전 정의)이었는데도 Bogey+가 된 사례 **94건** 중 상위 10건(미스 심각도 오름차순):

| 선수(순위, FW%) | R/H | lie/거리(band) | next lie | GIR | score |
|---|---|---|---|---|---|
| 고지원(53위,67.9%) | R1H15 | ROUGH/141.1(NEAR) | GREEN | O | Bogey(3퍼트 추정) |
| 고지원(53위,67.9%) | R2H8 | ROUGH/114.3(NEAR) | ROUGH | X | Bogey |
| 고지원(53위,67.9%) | R4H6 | ROUGH/153.5(NEAR) | FAIRWAY | X | Bogey |
| 임진영(27위,60.7%) | R1H12 | ROUGH/150.6(NEAR) | ROUGH | X | Bogey |
| 임진영(27위,60.7%) | R2H8 | ROUGH/113.4(NEAR) | FAIRWAY | X | Bogey |
| 문정민(27위,64.3%) | R2H8 | ROUGH/123.4(NEAR) | FRINGE | X | Bogey |
| 문정민(27위,64.3%) | R2H15 | ROUGH/111.2(NEAR) | GREEN | O | Bogey(3퍼트 추정) |
| 문정민(27위,64.3%) | R4H9 | ROUGH/106.5(NEAR) | ROUGH | X | Bogey |
| 김가희2(27위,66.1%) | R4H10 | ROUGH/303.1(NEAR) | FAIRWAY | O | Bogey(GIR인데 보기) |
| 김하은2(40위,64.3%) | R1H17 | ROUGH/131.4(NEAR) | GREEN | O | Bogey(3퍼트 추정) |

(전체 CSV는 `blue_heron_fw_miss_quality_vs_execution.csv`의 보조 자료로 원 이벤트는 `blue_heron_fw_miss_event_level.csv`에서 player 필터링으로 재현 가능)

## 9. BAD MISS → PAR+ (상위 TOP20 선수)

unfavorable_condition(FAR band 등)인데도 Par+를 지킨 TOP20 선수 사례 **63건** 중 상위 10건(미스 심각도 내림차순, 가장 나쁜 조건부터):

| 선수(순위) | R/H | lie/거리(band) | next lie | GIR | score |
|---|---|---|---|---|---|
| 김민주(2위) | R1H1 | ROUGH/194.5(FAR) | ROUGH | X | Par |
| 김민주(2위) | R2H10 | ROUGH/325.8(FAR) | FAIRWAY | X | Par |
| 마서영(16위) | R1H6 | ROUGH/268.4(FAR) | FAIRWAY | X | Par |
| 마서영(16위) | R1H18 | ROUGH/295.5(FAR) | ROUGH | X | Par |
| 마서영(16위) | R3H13 | ROUGH/131.9(FAR) | GREEN | O | Par |
| 마서영(16위) | R3H15 | ROUGH/192.0(FAR) | ROUGH | X | Par |
| 방신실(20위) | R2H6 | ROUGH/215.5(FAR) | FAIRWAY | X | Par |
| 현세린(14위) | R1H13 | ROUGH/143.7(FAR) | GREEN | O | Par |
| 현세린(14위) | R2H10 | ROUGH/334.8(FAR) | ROUGH | X | Par |
| 현세린(14위) | R2H14 | ROUGH/160.2(FAR) | GREEN | O | Par |

---

## 10. "미스 위치가 전부가 아니다" — 거의 동일 조건, 다른 결과 (20쌍)

같은 홀 + 같은 라운드(=같은 핀) + 같은 lie bucket + remaining distance 차이 15yd 이내 + penalty 노출 동일 조건에서, 결과가 2단계 이상 갈린(예: PAR vs DOUBLE+, BIRDIE+ vs BOGEY) 실제 쌍을 전수 탐색해 **1,331건의 후보**를 찾았고, 매칭 강도(같은 라운드 우선 → 거리차 최소) 순으로 정렬한 상위 10쌍:

| 홀 | lie | 같은라운드 | 거리차 | 선수A(순위) | 거리 | 결과A | vs | 선수B(순위) | 거리 | 결과B |
|---|---|---|---|---|---|---|---|---|---|---|
| H18 | ROUGH | O | 0.0yd | 김지수(20위,R2) | 285.0 | **BIRDIE+** | vs | 한아름(49위,R2) | 285.0 | BOGEY |
| H10 | ROUGH | O | 0.0yd | 고지우(미완주,R1) | 319.3 | **BIRDIE+** | vs | 안지현(27위,R1) | 319.3 | BOGEY |
| H10 | ROUGH | O | 0.0yd | 박보겸(12위,R2) | 323.1 | **PAR** | vs | 김지영2(미완주,R2) | 323.1 | DOUBLE+ |
| H10 | ROUGH | O | 0.1yd | 임희정(55위,R4) | 308.4 | **BIRDIE+** | vs | 김하은2(40위,R4) | 308.3 | BOGEY |
| H12 | ROUGH | O | 0.1yd | 정수빈(미완주,R1) | 155.9 | **PAR** | vs | 김시현(14위,R1) | 155.8 | DOUBLE+ |
| H1 | ROUGH | O | 0.1yd | 이채은2(미완주,R2) | 162.4 | **PAR** | vs | 임희정(55위,R2) | 162.3 | DOUBLE+ |
| H14 | ROUGH | O | 0.1yd | 유서연2(9위,R2) | 145.4 | **PAR** | vs | 문정민(27위,R2) | 145.5 | DOUBLE+ |
| H9 | ROUGH | O | 0.1yd | 임진영(27위,R3) | 111.5 | **BIRDIE+** | vs | 홍지원(40위,R3) | 111.6 | BOGEY |
| H13 | ROUGH | O | 0.1yd | 최민경(57위,R3) | 143.1 | **BIRDIE+** | vs | 김가희2(27위,R3) | 143.2 | BOGEY |
| H17 | ROUGH | O | 0.1yd | 최민경(57위,R3) | 129.5 | **BIRDIE+** | vs | 안재희(59위,R3) | 129.6 | BOGEY |

(전체 20쌍은 `blue_heron_same_condition_different_result.csv`에 있다.) **같은 홀, 같은 핀, 같은 lie, 거리차 0.0~0.1야드인데도 BIRDIE+와 DOUBLE+로 갈리는 사례가 다수 존재한다 — 미스 위치만으로 결과를 예측할 수 없다는 직접 증거다.** 동시에 유서연2(9위)-문정민(27위), 임진영(27위)-홍지원(40위) 사례처럼, 상위권이 "좋은 쪽" 결과를 가져간 쌍도 섞여 있지만(순위와 결과가 일치하는 방향), 고지우/정수빈/이채은2처럼 **순위가 없는(컷 탈락) 선수가 더 좋은 결과를 가져간 쌍도 섞여 있어** — 동일 조건에서의 결과 자체가 깔끔하게 순위 순으로 정렬되지는 않는다. 이는 개별 hole-play 단위에서는 노이즈가 크고, 5절의 TYPE B 결론은 "개별 사례"가 아니라 "187쌍 matched 표본의 평균적 패턴"에서 나온 것임을 다시 분명히 한다.

---

## 결론: Par를 보지 않고 정의한 MISS QUALITY와, 그 다음에 공개한 RESULT를 분리한 결과

**필드 전체(TOP10 vs FIELD REST, matched n=187/585, 세 허용오차에서 재현)**: GOOD MISS 효과(3절에서 real하게 존재하는 distance 질 차이)를 통제해도 결과 격차가 사라지지 않았다 → **TYPE B, RECOVERY DOMINANT**. "비슷한 FW 미스 조건에서도 상위권 선수들은 이후 손실을 더 자주 제한했다." 보조 로지스틱 모델은 같은 방향이지만 통계적으로 유의하지는 않았다(z=1.24) — 이는 관측적 조건부 연관성이며 인과관계가 아니다.

**단, 이 보고서가 대표 사례로 검증한 김소정(68%) vs 홍지원(50%) 개별 쌍은 이 필드 패턴과 다르다**: 김소정의 우위는 주로 GOOD MISS(favorable% 80.0% vs 37.5%)에서 나왔고, 매칭된 소표본(n=4~5)에서는 회복 실행력 우위가 확인되지 않았다. 개별 선수 쌍의 설명과 필드 전체의 설명을 섞지 않고 각각 보고한다.

유해란(1위)의 80% Par+는 좋은 미스(favorable 조건에서 76.9% Par+)와 나쁜 미스에서의 회복(R1H9: FAR band, GIR 없이도 Par) **둘 다**에서 나왔다 — 그의 20건 중 특정 결과 하나만으로 미스의 질을 거꾸로 추론할 수 없다(8-9절의 "GOOD MISS→BAD RESULT", "BAD MISS→PAR+" 사례, 10절의 동일조건-다른결과 쌍이 이를 직접 뒷받침한다).

---

## 산출물
- `blue_heron_fw_miss_event_level.csv` — 1,832건 전수 이벤트 테이블
- `blue_heron_fw_miss_matched_pairs.csv` — TOP10-REST 매칭쌍 1,115행(±10yd 기준)
- `blue_heron_fw_miss_quality_vs_execution.csv` — 그룹별 quality/matched 분해 요약
- `kim_sojung_vs_hong_jiwon_fw_miss.csv` — 41건 전수 + matched subset 플래그
- `ryu_haeran_20_fw_misses.csv` — 20건 전수 체인
- `blue_heron_same_condition_different_result.csv` — 동일조건-다른결과 상위 20쌍

새 웹페이지/코스맵/상품/다른 선수 확장 없음. 외부 데이터 수집 없음.
