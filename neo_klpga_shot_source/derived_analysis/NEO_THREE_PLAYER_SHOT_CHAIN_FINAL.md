# NEO Three-Player Shot Tracker SPATIAL CHAIN Analysis — Final

Game 2026100005, Blue Heron. 유해란(1위,284,−4) / 이재윤(27위,297,+9) / 박서현(61위,314,+26).
216/216 player-hole plays, 895 individual shot-level records, all freshly built from RAW this task.
Full casebook of 14 real cases: `NEO_SHOT_TRACKER_CASEBOOK_THREE_PLAYERS.md`.

Method, not stats-first: every finding below traces to an actual shot sequence in
`three_player_spatial_chain_master.csv` (coordinates, real-yard distances, lies) before any aggregate
number is quoted. Aggregates (FW%, GIR%, etc.) appear only as the final validation layer, exactly as
instructed — never as the starting explanation.

---

## 왜 유해란 1위, 이재윤 27위, 박서현 61위였는가 — 실제 샷 체인으로

**같은 코스를 세 선수가 서로 다르게 썼다.** 숫자가 아니라 실제로 공이 어디로 갔는지로 보면:

**유해란**은 완벽한 골프를 치지 않았다. 그녀도 페어웨이를 지키고도 보기를 했고(Case 9, R2H3), 비슷한
위치에서 이재윤·박서현에게 홀을 내준 적도 있다(Case 5, 6, 7 — 세 번 모두 실제로 "졌다"). 그녀가 다른
것은 **나쁜 시작이 큰 손실로 번지지 않았다는 것**이다. 티샷을 잃어버린 홀(R3H6, Case 11)에서도 페널티
이후 approach를 6.0야드까지 붙여 보기로 막았고, 72홀 중 Double+(2오버 이상)는 **단 1번**뿐이었다.
결정적 순간의 approach 품질과, 나쁜 상황에서의 recovery가 계속 "보기 이하"로 손실을 가둔 것 — 이게
스코어 차이의 실제 메커니즘이다.

**이재윤**은 Double+가 72홀 동안 **0번**이다 — 큰 사고가 없다. 하지만 그린을 맞혀도(GIR) 첫 퍼트
거리가 평균 **8.4야드**로 유해란의 **7.06야드**보다 길었고, GIR 홀에서 버디로 이어진 비율은
**9.3%**로 유해란의 **28.3%**의 1/3 수준이다(Case 14는 그가 실제로 버디를 만든 드문 사례지만, 그만큼
드물다는 뜻이기도 하다). 그는 사고를 막았지만, 그 안전함을 득점 기회로 바꾸는 approach 정밀도가
부족했다 — "안전하지만 득점으로 이어지지 않는 위치"가 반복됐다.

**박서현**은 "그냥 못 친 선수"가 아니다. 정상적인 체인이 깨지는 지점이 명확히 있다: **티샷 → 페어웨이
실패**(그녀 보기의 47%가 TEE_MISS로 시작)와, 그보다 더 결정적으로 **approach/penalty 단계에서 한 번의
실수가 2~3타 손실로 커지는 지점**이다(Case 1, R3H8: approach가 penalty area로 들어간 순간부터 7타가
시작됐다). 특히 **Hole 8/9**에서 반복됐는데, field 전체 데이터로 검증한 결과 Hole 8은 전체 선수에게도
실제로 어려운 홀(필드 평균 +0.387, 더블+ 10.3%)이지만 **Hole 9는 필드 전체엔 오히려 쉬운 홀**(필드
평균 +0.127)이었다 — 즉 Hole 8의 어려움은 코스 자체의 문제이고, Hole 9의 반복된 실패는 박서현
개인에게 특정된 패턴이다(Case 12). 또한 그녀의 러프 회복 par-save율(38%)은 그녀 자신의 라운드뿐
아니라 필드 전체 평균(46.3%, n=1152)보다도 낮다(Case 13) — 이건 "상대가 세서 상대적으로 약해 보이는"
것이 아니라 필드 기준으로도 real gap이다.

**결론: 세 선수 모두 완벽하지도, 일관되게 열등하지도 않았다. 같은 코스에서 유해란은 나쁜 상황을
보기로 가두는 구조를 가졌고, 이재윤은 사고는 막았지만 득점 전환이 약했고, 박서현은 특정 지점(approach/
penalty 단계, 그리고 그녀만의 반복 홀인 Hole 9)에서 정상 체인이 깨지면 손실이 눈덩이처럼 커졌다.**

---

## Players

### 유해란

- **WHERE SHE CREATED SCORE:** approach shots that finish inside ~7yd of the pin (her own GIR-hole
  average first-putt distance, n=53) convert to birdie 28.3% of the time — the highest conversion rate
  of the three. Case 10 (R2H7, rough tee shot → 1.5yd approach → birdie) is a direct example.
- **WHERE SHE SAVED SCORE:** Case 11 (R3H6, lost ball + penalty → still only Bogey via a 137.7yd
  approach to 6.0yd) is her signature pattern — bad starts capped at Bogey, not escalating to Double+
  (1 Double+ event in 72 holes, tournament-low).
- **WHAT LOCATIONS WORKED FOR HER:** recovery positions that still allow a full approach swing
  (fairway-after-penalty, rough-but-clear) rather than a blocked/obstructed lie — every one of her
  Bogey-preservation cases (6 total, `three_player_score_preservation_cases.csv`) reaches a clean
  recovery position before the green.
- **WHERE SHE WAS STILL VULNERABLE:** 3-putts from genuinely makeable range (Cases 2, 5: 2.7yd and
  3.4yd first putts both ended in 3-putts) — her only real recurring leak, and it's on the green, not
  from the tee or fairway.
- **WHAT TO PREPARE NEXT:** short-range (under 10ft / ~3yd) lag/finish putting specifically — not
  ball-striking, which is already her strength.

### 이재윤

- **WHERE SHE CONTROLLED DAMAGE:** 0 Double+ events in 72 holes (tournament-best alongside 유해란's
  near-zero rate) — her rough-miss recoveries (Cases 7, 8) are genuinely competitive, beating 유해란 in
  Case 7 from a worse starting distance.
- **WHERE SCORING OPPORTUNITIES WERE LOST:** GIR-hole first-putt distance averages 8.4yd vs 유해란's
  7.06yd (n=43 vs 53) — her approach shots reach the green, but not close enough to convert regularly;
  birdie conversion from GIR is 9.3% vs 유해란's 28.3%.
- **WHICH LOCATIONS PRODUCED SAFE BUT LOW-UPSIDE OUTCOMES:** the pattern repeats across many of her
  GIR holes — reaching the green is not the bottleneck, proximity is. Case 14 (a rare birdie, 1.6yd
  first putt) shows what it looks like when the approach IS tight — it is simply uncommon for her.
- **WHAT TO PREPARE NEXT:** approach-shot proximity on GIR-range shots specifically (not swing changes
  broadly) — tightening her average first-putt distance toward the 7yd range would, on this data's
  evidence, convert some of her many pars into the birdies she is currently leaving on the table.

### 박서현

- **WHERE NORMAL PLAY BROKE DOWN:** two distinct, separable breakpoints — (1) tee→fairway on par-4s
  (47% of her 19 bogeys start with a tee miss) and (2) approach→penalty specifically on Hole 8/Hole 9
  in R3–R4 (3 of her 5 Double+/TriplePlus events there).
- **WHICH LOCATIONS CREATED EXPENSIVE NEXT SHOTS:** greenside bunkers that her recovery shot fails to
  clear in one (Case 4: her bunker shot gained only 5.1yd and stayed in rough, vs 유해란's 10.1yd that
  reached the green directly, from the same starting distance) — the miss location was no worse than
  유해란's, the recovery execution was.
- **WHERE RECOVERY FAILED:** rough-miss par-save rate is 38% — below not just 유해란 (64%) and 이재윤
  (61%) but below the full 107-player field baseline (46.3%, n=1152) — a real, field-validated gap,
  not an artifact of tough comparisons.
- **WHICH BIG NUMBERS WERE LOCATION-DRIVEN vs EXECUTION-DRIVEN:** Hole 8's difficulty is shared by the
  whole field (course location risk, confirmed n=331) — her R3H8 TriplePlus is partly a course-risk
  event. Hole 9 is NOT difficult for the field (n=331, actually below-average difficulty) — her repeat
  trouble there (R3, R4) is a real, player-specific pattern, not course risk.
- **WHAT TO PREPARE NEXT:** two concrete, separate items — conservative tee strategy specifically on
  Hole 8/9's corridor (course-risk-aware), and dedicated rough/bunker recovery practice (her own
  largest, field-validated skill gap).

---

## Player / caddie actions (location → next-shot condition → risk → player fit, not "hit the fairway")

- **유해란, par-3/approach-to-makeable-range situations:** when her approach finishes inside ~3yd,
  history this week (n=2 of her 2 closest misses, Cases 2 and 5) shows a real 3-putt risk from exactly
  this range — worth a specific short-putt routine check before those putts, not a general "putt
  better" note.
- **이재윤, GIR-but-outside-8yd situations:** this is where her birdie conversion collapses (9.3% vs
  28.3% for 유해란 from a tighter average). The actionable target is not "hit more greens" (she already
  does, 68.8% FW-hit→GIR from the earlier audit) but "hit greens closer" — a specific proximity target
  inside 7yd on approach clubs she currently leaves at 8–10yd.
- **박서현, approach shots on Hole 8's corridor:** this hole is a confirmed field-wide risk area
  (n=331, +0.387 avg, 10.3% Double+) — a conservative target (center of green, not pin-hunting) is
  supported by field data, not just her own results.
- **박서현, greenside bunker recovery specifically:** when her ball is in a greenside bunker at
  roughly 10–13yd (the exact range seen in Case 4), the data shows her recovery shot has previously
  fallen short of the green entirely (5.1yd gained, landing in rough) where a comparable shot from
  the same distance (Case 4, 유해란) gained 10.1yd and reached the green — a specific technical target
  (distance control out of greenside sand from this range) rather than a general "work on bunkers" note.

---

## 숫자가 놓친 것 (FW%/GIR%가 설명하지 못한 것)

- FW%만 보면 세 선수(64%/57%/55%)는 9%p 안에 몰려 있어 격차를 설명하지 못한다. 하지만 Case 9(FW
  hit → bogey)와 Case 10(FW miss → birdie)이 보여주듯, FW 적중 자체는 애초에 스코어를 결정하지 않는다.
- GIR miss rate만 보면 "좋은 miss"와 "나쁜 miss"를 구분하지 못한다. Case 4는 똑같은 GREENSIDE_BUNKER
  미스(12.1 vs 12.5yd)가 Par와 Double로 완전히 갈라지는 걸 보여준다 — 미스 자체가 아니라 recovery 샷의
  실행이 갈랐다.
- 이재윤의 "Double+ 0회"만 보면 왜 그가 유해란과 13타 차이가 나는지 설명되지 않는다 — 첫 퍼트 평균
  거리(7.06 vs 8.4yd)와 GIR-to-birdie 전환율(28.3% vs 9.3%)을 봐야 "안전하지만 득점이 부족하다"는
  실제 메커니즘이 보인다.
- 유해란의 GIR%만 보면 그녀가 어디서 스코어를 지켰는지 보이지 않는다 — Case 11의 실제 체인(잃어버린
  공 → 페널티 → 그래도 보기)이 그녀의 진짜 "손실 제한" 구조를 보여준다.

---

## Created files

| File | Role |
|---|---|
| `build_spatial_chain_master.py` | Builds the 895-shot-level master chain fresh from RAW |
| `analyze_spatial_chains.py` | Gap events, counterexamples, same-start/same-miss analyses |
| `field_spatial_validation.py` | 107-player field validation for key clusters |
| `build_remaining_csvs.py` | Score-preservation, big-number autopsy, counterexamples CSVs |
| `build_spatial_maps.py` | 6 coordinate-space maps |
| `neo_three_player_spatial_chain.json` | Master data: 216 hole summaries + 895 shot records |
| `three_player_spatial_chain_master.csv` | Shot-level table, all required fields |
| `three_player_same_start_different_end.csv` | 3 cases, data-driven tolerance stated per row |
| `three_player_same_miss_different_recovery.csv` | 4 cases, ±5yd tolerance |
| `three_player_score_preservation_cases.csv` | 유해란's 6 Bogey-preservation chains |
| `three_player_big_number_spatial_autopsy.csv` | All 6 Double+/TriplePlus events, shot-by-shot |
| `three_player_counterexamples.csv` | 20 hole-plays where 유해란 did not win the hole |
| `three_player_field_spatial_validation.csv` | Field (n=331/1152/16) baselines for key clusters |
| `spatial_analysis_intermediate.json` | All intermediate case data behind the casebook |
| `map01_score_gap_casebook.png` … `map06_same_miss_different_recovery.png` | 6 required maps |
| `NEO_SHOT_TRACKER_CASEBOOK_THREE_PLAYERS.md` | 14-case casebook |
| This file | Final report |

Steps 1–25 and the attribution audit files are preserved, untouched. No Hole-8 standalone analysis was
started (Hole 8 appears only as part of the three-player comparison and field validation above, scoped
exactly to what this mission required). No PLAYER UI, website, or `/player/9115/` work was touched.
