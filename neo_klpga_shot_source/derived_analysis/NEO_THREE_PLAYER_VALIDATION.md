# NEO Three-Player Shot Tracker Validation — 하이트진로 챔피언십 2026100005

Purpose: verify that the derived metric layer actually explains real
players' real performance — not to rebuild the model. Players were
selected **strictly by official final result**, before any derived
metric was examined.

## Player selection (official result only, rule fixed before selection)

Pool: all 61 real 4-round completers from the official final-round
leaderboard (`fetch_official_standings.py`, real network fetch).
None of the 6 confirmed SOURCE_GAP players are in this pool at all —
5 were cut after R2, 1 stopped during R1, so they were never going to
qualify as "4R completers" regardless of exclusion.

| Tier | Rule | Player | playerCode | Rank | Total |
|---|---|---|---|---|---|
| 상위권 | Rank 1 | 유해란 | 9115 | **1 (우승)** | 284 (−4) |
| 중위권 | Closest to median index (30/61); 3-way tie at rank27 broken by the site's own listed order | 이재윤 | 9708 | 27 | 297 (+9) |
| 하위권 | Worst rank among 4R completers | 박서현 | 9111 | 61 (최하위) | 314 (+26) |

## STEP 1 — Player basic comparison (n shown for every rate)

| | 유해란 (TOP, #1) | 이재윤 (MID, #27) | 박서현 (BOTTOM, #61) |
|---|---|---|---|
| R1/R2/R3/R4 | 73/69/73/69 | 76/75/74/72 | 75/78/81/80 |
| Total | 284 (−4) | 297 (+9) | 314 (+26) |
| FW Hit % | 64.3% (n=56) | 57.1% (n=56) | 55.4% (n=56) |
| GIR % | 73.6% (n=72) | 59.7% (n=72) | 58.3% (n=72) |
| FW→GIR % | 83.3% (n=36) | 68.8% (n=32) | 64.5% (n=31) |
| FW Miss→GIR % | 45.0% (n=20) | 50.0% (n=24) | 44.0% (n=25) |
| Rough→GIR % | 42.9% (n=14) | 50.0% (n=24) | 47.8% (n=23) |
| GIR Miss→Par Save % | 68.4% (n=19) | 65.5% (n=29) | **43.3% (n=30)** |
| 평균 score_to_par | −0.056 | 0.125 | 0.361 |

**교차검증:** 72홀 평균 score_to_par × 72 = 각 선수의 실제 official total_under_par와 정확히 일치 (−4.03≈−4, 9.0=9, 26.0=26) — derived 데이터가 실제 공식 성적을 오차 없이 재현함을 독립적으로 확인.

**가장 뚜렷한 차이:** FW Hit%와 FW Miss→GIR%는 세 선수 간 차이가 크지 않다 (FW Hit 64→55%, FW Miss→GIR 45→50→44%, 순위와 단조적이지도 않음). 반면 **GIR Miss→Par Save%는 68.4%/65.5% vs 43.3%로 BOTTOM에서 뚜렷하게 급락** — 그린을 놓친 뒤 파를 지켜내는 능력이 상/중위권과 최하위권을 가장 크게 갈랐다.

## STEP 2 — Independent 72-hole RAW reconstruction

Each player's full 4R×18H shot sequence was re-read directly from the
RAW `group_shot` JSON archive (never from the derived CSV or sqlite)
and every field (par, strokes, score_to_par, first-shot state, FW
hit, tee-miss state, GIR, GIR shot number, par-or-better) was
recomputed from scratch and diffed against the published derived CSV.

**Result: 0 mismatches across 3 players × 72 holes (216 hole-rows).**
Full reconstruction, including each hole's actual shot-state sequence,
is in `neo_three_player_raw_reconstruction.csv`.

**STEP 2 VERDICT: PASS.**

## STEP 3 — Same-hole comparison across all three players

*(Note: your message describing which holes to compare here was cut
off after "특히 기존 분석에서 중요한 홀을" — I used the two holes the
existing tournament-wide analysis already flagged as significant:
Hole 8, the single biggest reliable miss-penalty/DEFEND hole, and
Hole 7, the strongest ATTACK hole. Tell me if you meant different
holes and I'll add them.)*

### Hole 8 (Par 4, DEFEND, biggest reliable miss penalty: +0.550 strokes)

| | R1 | R2 | R3 | R4 |
|---|---|---|---|---|
| 유해란 | 1\|3\|10 → **3 (birdie)** | 1\|3\|3\|10 → 4 (par) | 1\|3\|3\|10 → 4 (par) | 2\|2\|3\|10 → 4 (par, FW miss but GIR miss anyway, saved) |
| 이재윤 | 1\|12\|3\|10 → 4 (par) | 2\|3\|3\|10 → 4 (par) | 1\|3\|3\|10 → 4 (par) | 1\|2\|3\|10 → 4 (par) |
| 박서현 | 2\|2\|3\|3\|10 → **5 (bogey)** | 2\|2\|3\|10 → 4 (par) | 1\|5\|8\|2\|12\|3\|10 → **7 (triple bogey)** | 1\|3\|3\|10 → 4 (par) |

박서현의 R3 Hole8 실제 시퀀스: FAIRWAY→PENALTY_AREA→PENALTY_STROKE→ROUGH→FRINGE→GREEN→HOLED, 7타. 이 한 홀에서만 +3타 — 하위권 선수에게 Hole8의 "Miss Penalty"가 통계가 아니라 실제로 일어난 사건임을 직접 확인. 유해란과 이재윤은 4라운드 내내 이 홀에서 보기 이상을 전혀 범하지 않음 (파 또는 버디만).

### Hole 7 (Par 5, ATTACK, strongest birdie hole)

All three players scored **par-or-better on all 12 played instances** (0 bogey-or-worse across the board), including 3 birdies (유해란 R2, 이재윤 R4, 박서현 R4). This matches the ATTACK classification exactly: a low-risk, reward-rich hole where even the lowest-ranked player of the three never lost a stroke to par.

**STEP 3 finding: the course-wide ATTACK/DEFEND classification holds up at the individual-player level, not just in aggregate** — Hole 8 produced real bogey-or-worse outcomes concentrated in the lower-ranked player, while Hole 7 was uniformly safe for all three regardless of skill tier.

## Overall verification verdict

Derived metrics **PASS** both the row-level RAW cross-check (Step 2, 0 mismatches) and the real-outcome cross-check (Step 1's score_to_par sum == official total_under_par). The tournament-wide hole classification (Step 3) is corroborated by concrete, individual real shot sequences, not just statistics. No evidence found that the derived layer misrepresents any of these 3 players' actual rounds.
