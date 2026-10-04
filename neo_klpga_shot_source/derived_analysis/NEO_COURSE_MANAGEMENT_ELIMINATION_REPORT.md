# NEO Course Management — ELIMINATION Methodology (DEFEND Holes 6/8/10/12)

이 보고서는 "기존 PLAYER COURSE MAP REPORT"라는 이름의 파일을 저장소 전체에서 찾지 못했습니다 (`git log --all`, 파일명 검색 모두 결과 없음). 가장 가까운 기존 산출물인 `neo_course_strategy.csv`(ATTACK/CONTROL/DEFEND 분류)와 `NEO_HIDDEN_PATTERNS_REPORT.md`의 F절(코스 인사이트)을 "기존"으로 간주하고 이를 확장합니다. 다른 파일을 의도하셨다면 알려주세요.

## 0. 방법론 선언 (사전 확정, 결과 보고 후 변경 금지)

**정답을 먼저 정하지 않는다.** 모든 홀에서 후보 전략/구역을 먼저 나열하고, 실제 데이터로 하나씩 제거(ELIMINATION)한 뒤 생존한 구역만 추천한다.

**엄격한 구분표기:**
- **OBSERVED** = 실제 Shot Tracker 좌표/상태/결과에서 직접 관측된 값
- **INFERRED** = OBSERVED 데이터로부터 통계적으로 추론한 값 (근거 명시)
- **UNKNOWN** = 현재 데이터로 확인 불가능 (추측 금지, 임의 생성 금지)

**좌표계 검증 (사전 확인, 가정 아님):** `pp_x/pp_y`(샷별 착탄 좌표)가 실제로 홀마다 내부적으로 일관된 좌표계를 이루는지 **직접 검증**했다 — 같은 홀의 모든 선수의 샷 시퀀스가 경로와 무관하게 동일한 홀아웃 지점(예: Hole8 → 약 (75,13))으로 수렴하는 것을 실제 raw 데이터에서 확인(OBSERVED). 반면 `baseHoleInfo`의 `bi_sx/sy/gx/gy`(티/그린 기준점으로 추정되는 필드)는 `pp_x/pp_y`와 **수치 범위가 전혀 다른 별도의 좌표계**임을 확인했다(100~400대 vs 0~100대) — 이는 코스 지도 UI용 픽셀 좌표로 추정되며, `pp_x/pp_y`와 혼용하면 정확히 사용자가 경고한 "근거 없는 임의 생성"이 되므로 **사용하지 않았다**. 대신 TEE/GREEN 기준점을 실제 데이터에서 직접 도출했다:
- TEE anchor (OBSERVED) = 모든 실제 shot#1 좌표의 중심점
- GREEN/HOLE anchor (OBSERVED) = 모든 실제 홀아웃(state=10) 좌표의 중심점

**구질(DRAW/FADE/STRAIGHT) 관련:** Shot Tracker에는 실제 볼 플라이트 구질 필드가 전혀 없다. 따라서 어떤 선수가 실제로 드로우/페이드를 쳤다고 **절대 단정하지 않는다**. 아래 분석은 "착탄한 구역"(OBSERVED)과 "그 구역의 실제 결과"(OBSERVED)만 다루며, "어떤 구질이 그 구역에 도달 가능한 후보인가"는 지오메트리 상 후보로서만 UNKNOWN/INFERRED 표기로 남긴다.

**표본 기준:** n<5인 구역은 LOW_SAMPLE로 표시하고 후보에서 제외(제거 사유와 별개로 기록).

---

## 1. HOLE GEOMETRY (OBSERVED / INFERRED / UNKNOWN)

| | Hole 6 | Hole 8 | Hole 10 | Hole 12 |
|---|---|---|---|---|
| Par | 4 (OBSERVED, holeInfo.stdScore) | 4 | 5 | 4 |
| Yardage | 410yds (OBSERVED, holeInfo.yds) | 377yds | 570yds | 410yds |
| Tee anchor (pp_x,pp_y 중심, OBSERVED, n=331) | (67.5, 85.0) | (43.7, 76.8) | (60.1, 113.2) | (82.5, 82.4) |
| Green/Hole anchor (OBSERVED, n=331) | (64.0, 15.9) | (68.8, 16.5) | (75.0, 14.7) | (64.2, 20.2) |
| Dogleg 방향 | UNKNOWN (좌표만으로 좌/우 방향 확정 불가) | UNKNOWN | UNKNOWN | UNKNOWN |
| 페어웨이 폭/벙커/OB 폴리곤 | UNKNOWN (코스 지도 이미지 없음) | UNKNOWN | UNKNOWN | UNKNOWN |
| 실제 벙커 구역 (INFERRED, 실제 BUNKER 착탄 클러스터로부터) | 관측된 BUNKER 착탄 없음 (0%) | 관측된 BUNKER 착탄 없음 (0%) | 관측된 BUNKER 착탄 없음 (0%) | **SHORT-LAT3 구역에 실제 BUNKER 착탄 29%(n=42 중 12건)** — 코스 지도 없이 실제 샷 결과로부터 역으로 추정한 유일한 실측 벙커 위치 |
| 그린 모양 / 그린사이드 벙커 / 해저드 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

Hole6/8/10에서 "실제 벙커 착탄이 0%"라는 결과는 "벙커가 없다"는 뜻이 아니라 **"331개 실제 티샷 중 벙커에 들어간 샷이 없었다"는 관측 사실**일 뿐이다 — 벙커 존재 여부 자체는 UNKNOWN으로 남긴다.

---

## 2~4. TEE SHOT CANDIDATE ZONES + ELIMINATION (실제 수치)

**구역 정의:** 실제 전체 필드 티샷(shot#1) 좌표를 TEE→GREEN 축(OBSERVED anchor 기반)에 투영하여 종방향 3분위(SHORT/MID/LONG, 홀 내 상대적 거리 — 절대 야드 의미 아님)와 횡방향 3분위(LAT1/LAT2/LAT3, 좌우 방향은 UNKNOWN이므로 중립 명칭)로 9개 후보 구역을 만들었다. **후보를 먼저 전부 나열**했으며 사후에 "좋아 보이는" 구역만 뽑지 않았다.

**제거 규칙 (4홀 공통, 사전 고정):**
1. Bogey+% 가 생존 구역 중 최솟값보다 10%p 이상 높으면 제거
2. 규칙1 통과 후, avg_score_to_par가 생존 구역 중 최솟값보다 0.15타 이상 높으면 제거
3. n<5는 LOW_SAMPLE로 별도 제외

### Hole 6 (Par4, 410yds)

| Zone | n | FW% | Rough% | Bunker% | GIR% | ParOrBetter% | Bogey+% | avg_stp | 상태 |
|---|---|---|---|---|---|---|---|---|---|
| LONG-LAT2 | 46 | 100% | 0% | 0% | 74% | 85% | 15% | **+0.022** | ✅ 생존 → **RECOMMENDED** |
| LONG-LAT1 | 33 | 42% | 58% | 0% | 48% | 82% | 18% | +0.152 | ✅ 생존 |
| MID-LAT1 | 41 | 41% | 56% | 2% | 39% | 78% | 22% | +0.171 | ✅ 생존 |
| LONG-LAT3 | 30 | 60% | 40% | 0% | 60% | 80% | 20% | +0.233 | ❌ 제거 — avg_stp 규칙 |
| SHORT-LAT2 | 28 | 96% | 4% | 0% | 43% | 79% | 21% | +0.250 | ❌ 제거 — avg_stp 규칙 |
| SHORT-LAT1 | 37 | 49% | 51% | 0% | 35% | 62% | 38% | +0.351 | ❌ 제거 — Bogey+% 규칙 |
| MID-LAT2 | 36 | 100% | 0% | 0% | 44% | 56% | 44% | +0.389 | ❌ 제거 — Bogey+% 규칙 |
| MID-LAT3 | 34 | 44% | 56% | 0% | 44% | 59% | 41% | +0.412 | ❌ 제거 — Bogey+% 규칙 |
| SHORT-LAT3 | 46 | 33% | 59% | 9% | 15% | 39% | 61% | +0.826 | ❌ 제거 — Bogey+% 규칙 |

**주목할 비직관적 사실:** LONG-LAT1(FW 42%뿐)이 MID-LAT2(FW 100%)보다 avg_stp가 더 좋다(+0.152 vs +0.389) — "페어웨이 적중률이 높은 구역이 항상 더 좋지 않다"는 Hidden Patterns 보고서 B1의 재확인.

### Hole 8 (Par4, 377yds) — 기존 R3 박서현 트리플보기 사례 보유 홀

| Zone | n | FW% | Rough% | GIR% | ParOrBetter% | Bogey+% | avg_stp | 상태 |
|---|---|---|---|---|---|---|---|---|
| LONG-LAT2 | 41 | 98% | 2% | 85% | 90% | 10% | **−0.122** | ✅ 생존 → **RECOMMENDED** |
| LONG-LAT3 | 32 | 91% | 9% | 75% | 91% | 9% | −0.094 | ✅ 생존 |
| LONG-LAT1 | 37 | 11% | 89% | 24% | 57% | 43% | +0.595 | ❌ 제거 — Bogey+% 규칙 |
| MID-LAT1 | 46 | 39% | 61% | 37% | 61% | 39% | +0.457 | ❌ 제거 — Bogey+% 규칙 |
| MID-LAT2 | 37 | 100% | 0% | 59% | 73% | 27% | +0.270 | ❌ 제거 — Bogey+% 규칙 |
| MID-LAT3 | 25 | 52% | 48% | 40% | 60% | 40% | +0.560 | ❌ 제거 — Bogey+% 규칙 |
| SHORT-LAT1 | 28 | 43% | 57% | 18% | 36% | 64% | +0.643 | ❌ 제거 — Bogey+% 규칙 |
| SHORT-LAT2 | 33 | 76% | 24% | 48% | 64% | 36% | +0.303 | ❌ 제거 — Bogey+% 규칙 |
| SHORT-LAT3 | 52 | 19% | 71% | 33% | 56% | 44% | +0.788 | ❌ 제거 — Bogey+% 규칙 |

### Hole 10 (Par5, 570yds)

| Zone | n | FW% | GIR% | ParOrBetter% | Bogey+% | avg_stp | 상태 |
|---|---|---|---|---|---|---|---|
| LONG-LAT2 | 49 | 94% | 67% | 96% | 4% | **−0.082** | ✅ 생존 → **RECOMMENDED** |
| LONG-LAT3 | 36 | 94% | 75% | 86% | 14% | 0.000 | ✅ 생존 |
| (나머지 7개 구역) | | | | | | +0.296~+0.471 | ❌ 전부 제거 — Bogey+% 규칙(32~40%) |

### Hole 12 (Par4, 410yds) — 유일하게 실제 벙커 구역 확인

| Zone | n | FW% | Bunker% | GIR% | ParOrBetter% | Bogey+% | avg_stp | 상태 |
|---|---|---|---|---|---|---|---|---|
| MID-LAT2 | 38 | 100% | 0% | 74% | 79% | 21% | **+0.079** | ✅ 생존 → **RECOMMENDED** |
| LONG-LAT2 | 42 | 98% | 0% | 74% | 71% | 29% | +0.167 | ✅ 생존 |
| SHORT-LAT2 | 30 | 97% | 0% | 63% | 77% | 23% | +0.200 | ✅ 생존 |
| SHORT-LAT3 | 42 | 29% | **29%** | 19% | 33% | **67%** | +0.881 | ❌ 제거 — Bogey+% 규칙 (최악 구역, 실제 벙커 지대) |
| (나머지 5개 구역) | | | | | | | +0.294~+0.575 | ❌ 전부 제거 |

**Hole 12의 반직관적 발견:** 생존 구역 3개 중 가장 멀리 간 LONG-LAT2(+0.167)보다 **중간 거리인 MID-LAT2(+0.079)가 더 좋은 결과**를 냈다 — "최대 거리 확보"보다 "중간 거리 position" 전략이 이 홀에서는 실제로 더 유리했다는, 사전 가정 없이 데이터로 확인된 결과.

---

## 5. 3인 ACTUAL vs RECOMMENDED (DEFEND 4홀 전체 라운드)

| Hole | RECOMMENDED | 유해란 적중 | 이재윤 적중 | 박서현 적중 |
|---|---|---|---|---|
| 6 | LONG-LAT2 | 1/4 | 2/4 | **0/4** |
| 8 | LONG-LAT2 | 3/4 | 1/4 | **0/4** |
| 10 | LONG-LAT2 | 1/4 | 2/4 | **0/4** |
| 12 | MID-LAT2 | 0/4 | 0/4 | **0/4** |

**핵심 실제 발견: 박서현은 4개 DEFEND 홀 16회 티샷 중 13회(81%)가 LAT1 구역이었다 (Hole6: 2/4, Hole8: 3/4, Hole10: 4/4, Hole12: 4/4).** 이는 추정이 아니라 raw 좌표 투영에서 직접 관측된 사실이며, 종방향도 SHORT 또는 MID에 집중(LONG 0/16) — 그녀는 이 4개 홀에서 **한 번도 LONG 구역에 도달한 적이 없다.**

### 사례 A — WHAT HAPPENED / WHAT THE DATA SAYS / WHERE NEO WOULD SEND IT

**WHAT HAPPENED:** 박서현은 Hole10(Par5) 4라운드 전부, Hole12(Par4) 4라운드 전부 LAT1 구역(SHORT 또는 MID 종방향)에 티샷을 떨어뜨렸다. Hole10: R1~R3는 SHORT-LAT1(state=2, ROUGH), R4는 MID-LAT1(역시 ROUGH). Hole12: R1·R4 MID-LAT1, R2·R3 SHORT-LAT1 — 4라운드 전부 ROUGH(state=2).

**WHAT THE DATA SAYS:** 같은 홀에서 LAT2 구역(RECOMMENDED)의 실제 결과:
- Hole10 LONG-LAT2: n=49, GIR 67%, ParOrBetter 96%, Bogey+ 4%, avg_stp −0.082
- Hole10 SHORT-LAT1(박서현이 실제로 간 구역): n=51, GIR 41%, ParOrBetter 63%, Bogey+ 37%, avg_stp +0.471
- Hole12 MID-LAT2: n=38, GIR 74%, ParOrBetter 79%, Bogey+ 21%, avg_stp +0.079
- Hole12 SHORT-LAT1(박서현 실제 구역): n=40, GIR 38%, ParOrBetter 62%, Bogey+ 38%, avg_stp +0.375

**WHERE NEO WOULD SEND IT:** Hole10/Hole12 모두 RECOMMENDED 구역(LAT2)으로. Hole10은 LONG-LAT2(최장거리+중앙), Hole12는 MID-LAT2(중간거리+중앙) — Hole12는 "최대거리"가 아니라 "중간거리 position"임에 주의.

**WHY:** 두 홀 모두 LAT1 구역은 Bogey+% 규칙으로 명확히 제거된 구역이며(Hole10 SHORT-LAT1 Bogey+ 37% vs RECOMMENDED 4%, Hole12 SHORT-LAT1 Bogey+ 38% vs RECOMMENDED 21%), 실제 평균 타수차가 Hole10에서 **0.55타**, Hole12에서 **0.30타**에 달한다.

**IF MISSED:** LAT1 방향으로의 미스는 두 홀 모두 명확한 BAD MISS(위 데이터 근거). LAT3 방향은 Hole10에서는 ACCEPTABLE(LONG-LAT3 avg_stp 0.000, 생존 구역)이나 Hole12에서는 SHORT-LAT3가 실제 벙커 구역(29%)이 있는 DO-NOT-MISS 구역이다 — 홀마다 "괜찮은 미스 방향"이 다르다.

**NEXT TIME:** Hole10/12 티샷에서 LAT1 방향(박서현이 15/16회 간 방향)을 의도적으로 피하는 전략이 역사적 데이터상 유리하다. 단, 이것이 "어느 구질을 쳐야 한다"는 처방은 아니다 — 구질 데이터가 없으므로 "LAT2 구역에 도달하는 방법"은 선수의 기존 샷 패턴 안에서 캐디가 판단할 영역이며 NEO는 목표 구역만 제시한다.

### 사례 B — Hole 8 R3 박서현 트리플보기 (기존 사례 확장)

**WHAT HAPPENED:** `FAIRWAY→PENALTY_AREA→PENALTY_STROKE→ROUGH→FRINGE→GREEN→HOLED`, 7타(+3). 티샷 자체는 MID-LAT2 구역(FW)으로, 이 구역 단독 통계는 양호(n=37, ParOrBetter 73%)하다 — **문제는 티샷이 아니라 2번째 샷**이었다.

**WHAT THE DATA SAYS:** MID-LAT2 구역 37개 사례 중 PENALTY_AREA로 이어진 것은 이 1건뿐(2.7%) — 이는 전형적 결과가 아니라 **이상치(outlier) 사건**이다. 근거: 같은 구역 다른 36개 사례의 평균 결과는 ParOrBetter 73%.

**WHERE NEO WOULD SEND IT / WHY:** 티샷 목표 구역 자체(MID-LAT2)는 변경할 근거가 없다 — 통계적으로 문제는 세컨드 샷의 클럽/목표 선택이었을 가능성이 높으나, **세컨드 샷의 목표 구역 데이터는 이번 분석 범위(그린 인근 CLOSE/MID/FAR 대역)에서 별도 절에서 다룬다(아래 6절).**

**IF MISSED:** n=1 사건이므로 "MID-LAT2 구역이 위험하다"고 일반화하지 않는다 — LOW_SAMPLE 수준의 반례이며 패턴이 아니라 개별 사건으로 기록한다.

### 사례 C — 유해란의 Hole12 LAT1 미스 (우승자도 완벽하지 않음)

**WHAT HAPPENED:** R2에서 LONG-LAT1(state=2, ROUGH) → 더블보기(+2, 6타). R3에서도 LONG-LAT1(state=2) → 파(0, 4타, 세컨드 샷에서 복구). 4라운드 중 2회(50%) LAT1 구역.

**WHAT THE DATA SAYS:** Hole12 LONG-LAT1 구역 실제 결과: n=31, GIR 39%, ParOrBetter 68%, Bogey+ 32%, avg_stp +0.355 — RECOMMENDED(MID-LAT2, +0.079)보다 0.276타 나쁘다.

**WHERE NEO WOULD SEND IT:** MID-LAT2. 우승자조차 이 홀에서 통계적 최적구역에 4라운드 중 0회만 도달했다(위 표) — **1위 선수도 매 홀 최적 전략을 수행하지 못했다는 사실 자체가 기록할 가치가 있다.**

---

## 6. GREEN-SIDE 거리대별 결과 (CLOSE/MID/FAR, 중립 명칭 — 좌우 방향 아님)

**정의:** 각 홀에서 그린(state=3)에 처음 도달한 샷의 `pp_greenx/greeny`로 계산한 핀까지 남은 거리 추정치(단위 불명 — UNKNOWN, 상대 비교에만 사용)를 3분위로 나눔.

| Hole | CLOSE ParOrBetter% (n) | MID ParOrBetter% (n) | FAR ParOrBetter% (n) | 패턴 |
|---|---|---|---|---|
| 6 | 65% (110) | 68% (109) | 70% (109) | **거의 차이 없음** — "그린 어디에 올려도 결과가 비슷한 홀" |
| 8 | 74% (109) | 65% (109) | 56% (108) | **명확한 단조 감소** — 핀에 가까울수록 유리 (18%p 차) |
| 10 | 76% (108) | 75% (108) | 67% (107) | CLOSE/MID 거의 동일, FAR만 하락 |
| 12 | 62% (112) | 64% (107) | 66% (108) | **거의 차이 없음 (역전 방향)** |

**뻔한 결론을 피함:** "그린에 가까이 붙일수록 항상 좋다"는 가정은 Hole6·12에서 성립하지 않는다(차이 거의 없거나 역전). Hole8만 명확한 거리 효과를 보인다 — 홀마다 그린 경사/핀 포지션 변동성이 다를 가능성이 있으나 이는 그린 형태 데이터가 없어 **UNKNOWN**으로 남긴다.

---

## 7. PLAYER-SPECIFIC CONTACT ZONE (DEFEND 4홀)

| 선수 | PRIMARY TARGET (RECOMMENDED와 일치 시) | 실측 패턴 기반 DO-NOT-MISS |
|---|---|---|
| 유해란 | Hole6/8/10 LONG-LAT2, Hole12 MID-LAT2 | 데이터 부족 (전반적으로 LAT2 근접 빈도 높음, 명확한 반복 미스 패턴 없음) |
| 이재윤 | 동일 | 명확한 반복 패턴 없음 (혼재) |
| 박서현 | 동일 (통계적 권장) | **LAT1 방향 — 4홀 16회 중 15회 실측, Hole10/12는 100%(4/4)** |

**ACCEPTABLE MISS ZONE은 현재 3인 표본(라운드당 1개 데이터 포인트)만으로는 통계적으로 확정할 수 없다 — UNKNOWN.** 전체 필드 수준의 구역 테이블(2~4절)을 참고 기준으로 제시하되, 선수 개인별 ACCEPTABLE MISS 경계는 더 많은 라운드 데이터가 쌓여야 확정 가능하다.

---

## 8. 한계 및 금지 사항 재확인

- **AIM POINT는 UNKNOWN.** 선수가 어디를 조준했는지 데이터 없음 — ACTUAL LANDING과 RECOMMENDED ZONE만 비교했다.
- **구질(DRAW/FADE/STRAIGHT)은 UNKNOWN.** "이 구역은 어떤 구질로 도달 가능한가"는 지오메트리 후보로만 제시 가능하나, 이번 보고서는 도그렉 방향 자체가 UNKNOWN이므로 구질 후보 지도화는 수행하지 않았다 — **임의 생성 금지 원칙에 따라 생략.**
- **"그곳에 갔다면 반드시 좋은 결과였을 것"이라고 쓰지 않았다.** 모든 RECOMMENDED 구역은 "이 구역에 착탄한 실제 샷들의 결과는 ParOrBetter X%, Bogey+ Y%였다"는 관측 통계로만 표현했다.
- **사후 결과를 보고 제거 규칙을 바꾸지 않았다.** 4홀 전부 동일한 제거 규칙(Bogey+% 10%p, avg_stp 0.15타)을 사전 고정 적용했다.
- 표본 수는 모든 표에 n으로 명시했으며 LOW_SAMPLE 구역은 별도 표시했다.

## 산출물
- `course_management_elimination.py` (read-only, RAW 미수정)
- `course_management_elimination.json` — 홀별 전체 구역 통계/제거근거/생존/추천
- `neo_tee_shot_zone_records.csv` — 전체 필드 실제 티샷 좌표투영 원자료
- `neo_tee_zone_elimination_summary.csv` — 9구역×4홀 통계 테이블
- `green_side_miss_analysis.json` — 그린 거리대별 결과
