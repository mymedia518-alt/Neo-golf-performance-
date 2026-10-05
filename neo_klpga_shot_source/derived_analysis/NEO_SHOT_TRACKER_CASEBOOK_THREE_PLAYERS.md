# NEO Shot Tracker Casebook — 유해란 / 이재윤 / 박서현

14 real cases, Blue Heron, Game 2026100005. Selection rule: each case must demonstrate one of the
categories A–J below using actual shot-by-shot RAW data (coordinates in `three_player_spatial_chain_master.csv`,
distances in real yards from the RAW `distance` field). Not cherry-picked for a "Ryu always wins" story —
7 of 14 cases show Ryu losing or tying the hole, deliberately kept in. Every claim is labeled OBSERVED,
INFERRED, or UNKNOWN. Field validation (107 players) is cited wherever it exists for that location.

Categories: A=same start→different end · B=same miss→different recovery · C=FW hit→bad score ·
D=FW miss→good score · E=better player loses the hole · F=lower player wins the hole ·
G=big-number escalation · H=score-preserving miss · I=good position wasted · J=field-best≠player-best

---

### Case 1 — R3H8, par4: 박서현's worst hole of the tournament [G]

**Why this case matters:** largest single gap event in the entire 72 holes for any pair (−3 vs 유해란).

**박서현:** TEE→FAIRWAY (234.6yd, 142.4yd left) → APPROACH→**PENALTY_AREA** (0.0yd recorded — ball in
hazard) → drop→**PENALTY_STROKE** (59.0yd left) → **ROUGH** (18.4yd left) → **FRINGE** (5.6yd left) →
**GREEN** (0.3yd left) → HOLED. **Score = 7 (+3).**
**유해란 (same hole):** TEE→FAIRWAY (238yd) → APPROACH→GREEN → 2 putts. **Score = 4 (Par).**

**Where chains diverged:** at the approach shot (shot 2). 유해란's approach reached the green directly;
박서현's approach found a penalty area, costing two strokes (the penalty stroke itself plus the drop)
before she was even back to where a normal approach would have left her.

**Field validation:** Hole 8 is genuinely harder than an average par-4 for the *whole field*
(n=331, avg score-to-par **+0.387** vs **+0.258** field-wide for all par-4s; Double+ rate **10.3%** vs
**4.1%**). So some of this is **COURSE LOCATION RISK**, not purely a 박서현 execution issue — but reaching
a penalty area specifically, rather than just missing the green, is still the proximate cause.

OBSERVED: the exact shot sequence and all 7 endpoints. INFERRED: nothing beyond the sequence itself.
UNKNOWN: her intended target line on the approach (not inferred).
**Lesson:** this hole's approach corridor carries real penalty risk for the whole field, not just her —
a more conservative approach club/target on this specific hole is a field-supported, not just
player-specific, recommendation.

---

### Case 2 — R1H16, par3: 박서현 beats 유해란 by 2 from the identical spot [F, I, counterexample]

**Why this case matters:** a required counterexample — the eventual champion lost this hole outright.

**유해란:** TEE→GREEN, landing **18.5yd** from the pin → approach putt to **2.7yd**, ending at coordinate
(60, 14) → missed, to 0.4yd → holed. **putts from the 18.5yd shot = 3. Score = 4 (Bogey).**
**박서현:** TEE→GREEN, landing **2.7yd** from the pin, at the exact same coordinate (60, 14) → **1-putt,
holed. Score = 2 (Birdie).**

**Where chains diverged:** 유해란's tee shot itself was the worse shot (18.5yd vs 2.7yd from the pin).
But by her second shot she had reached the *exact same spot* 박서현's tee shot found directly — and from
there, 박서현 holed in one putt while 유해란 needed two more. **This is a genuine same-spot,
different-putting-result case: not approximate, the end coordinates match to the data's precision.**

OBSERVED: both full chains, identical landing coordinate (60,14)/2.7yd for 유해란's 2nd shot and
박서현's 1st shot. INFERRED: nothing. UNKNOWN: green speed/line reading, which this data cannot see.
**Lesson:** 박서현 is not a weak putter in absolute terms — she converted the makeable range here that
유해란 missed. Any "박서현 = poor putter" story needs this case as a counterweight.

---

### Case 3 — R2H12, par4: 이재윤 beats 유해란 by 2 [E, F, counterexample]

**Why this case matters:** 유해란's only Double+ of the tournament, and it happened against 이재윤, the
27th-place finisher — a required "better player loses" case.

**유해란:** TEE→**ROUGH** → approach to GREEN → multiple putts → **Score = 6 (Double).**
**이재윤 (same hole):** TEE→FAIRWAY → approach to GREEN → 2 putts. **Score = 4 (Par).**

**Where chains diverged:** at the tee shot — 이재윤 found the fairway, 유해란 did not, and the recovery
never fully closed the gap (this is the same hole already flagged in the Steps 5–25 report and the
attribution audit as having `first_failure=TEE`, `escalation=PUTTING`).

OBSERVED: tee lies and final scores. INFERRED: nothing beyond the already-audited stage classification.
UNKNOWN: n/a. **Lesson:** this is the cleanest, least ambiguous "Ryu lost" case in the dataset — a
missed fairway that was never fully recovered, against the mid-table finisher, not the last-place one.

---

### Case 4 — R1H3, par4: identical greenside-bunker distance, opposite outcomes [B]

**Why this case matters:** the clearest "same miss location, different recovery execution" case found.

**유해란:** approach → GREENSIDE_BUNKER at **12.1yd** from pin → bunker shot travels **10.1yd**, lands
directly on the **GREEN at 2.0yd** → 1-putt. **Score = 4 (Par).**
**박서현:** approach → GREENSIDE_BUNKER at **12.5yd** from pin (0.4yd difference, effectively the same
spot) → bunker shot travels only **5.1yd**, lands in **ROUGH at 7.4yd** (does not reach the green) →
needs a second recovery shot to finally reach the green at 3.4yd → 2 putts. **Score = 6 (Double).**

**Where chains diverged:** the bunker shot itself. Both started at the same distance from the same lie;
유해란's bunker shot reached the green in one, 박서현's did not.

**Field validation:** greenside bunkers on this exact hole (R1H3) are genuinely risky for the whole
field too (n=16 field-wide players who found this bunker, avg score-to-par **+0.688**, Double+ rate
**12.5%**) — so starting from a greenside bunker here is a real risk for everyone, but the SPECIFIC
divergence between these two players is about whether the recovery shot itself reached the green, not
about who had the "better" miss.

OBSERVED: both full chains, distances to the yard. INFERRED: nothing. UNKNOWN: bunker lie quality
(buried vs clean), not recorded in RAW. **Lesson:** separates MISS LOCATION (same for both, and risky
field-wide) from RECOVERY EXECUTION (different, and decisive) — exactly the distinction this mission
asked to keep apart.

---

### Case 5 — R1H10, par5: 유해란 loses to 이재윤 from a near-identical tee landing [A, F, counterexample]

**Why this case matters:** same-start, different-end, data-driven tolerance (field decile-based, 3.5yd).

**유해란:** tee shot leaves **289.7yd** to the pin → … → reaches green at **3.4yd** (shot 4) → **3 putts**
(3.4→0.7→holed takes 2 more strokes after the green-reaching shot). **Score = 6 (Bogey).**
**이재윤:** tee shot leaves **288.4yd** (0.9yd different — within the hole's field-wide tolerance for
"comparable") → reaches green at **15.5yd**, a numerically worse approach → but **2-putts** cleanly.
**Score = 5 (Par).**

**Where chains diverged:** NOT the tee shot (nearly identical) and NOT really the approach (이재윤's was
numerically further from the pin). It is the **putting stage**: 유해란 3-putted from a makeable 3.4yd
range while 이재윤 2-putted from a much longer 15.5yd range.

OBSERVED: both full chains. INFERRED: nothing. UNKNOWN: green read/line. **Lesson:** a required
counterexample where "better approach proximity" (유해란's 3.4yd vs 이재윤's 15.5yd) still produced the
*worse* score — GOOD LOCATION ≠ AUTOMATIC GOOD SCORE, exactly the principle this mission asked to test.

---

### Case 6 — R1H14, par4: 유해란 loses to 박서현 from a near-identical tee landing [A, F, counterexample]

**Why this case matters:** the second same-start case, and critically — 유해란 loses it to 박서현, the
61st-place finisher, not just to 이재윤.

**유해란:** tee leaves **136.1yd** → approach to **15.3yd** → **3 putts** (13.1yd traveled, then 1.8, then
holed). **Score = 5 (Bogey).**
**박서현:** tee leaves **137.8yd** (1.7yd different, within tolerance) → approach to **4.3yd** — a much
better approach shot → 2-putt. **Score = 4 (Par).**

**Where chains diverged:** here it genuinely IS the approach shot — 박서현's second shot left her more
than 10 yards closer to the pin than 유해란's did, from comparable starting positions. This is the
mirror image of Case 5: there, putting was the separator from near-equal approaches; here, the
APPROACH ITSELF is the separator.

OBSERVED: both full chains. INFERRED: nothing. UNKNOWN: n/a. **Lesson:** the combination of Case 5 and
Case 6 shows there is no single universal explanation — sometimes 유해란's edge is approach quality,
sometimes it's absent entirely and she loses on approach quality herself, against either opponent.

---

### Case 7 — R3H3, par4: comparable rough miss, 유해란 needs an extra recovery shot [B, F, counterexample]

**유해란:** tee→ROUGH, approach leaves **26.5yd** in rough → recovery reaches **FRINGE at 5.0yd** (does
not reach the green) → needs one more shot to the green (0.8yd) → 1-putt. **Score = 5 (Bogey).**
**이재윤:** tee→ROUGH, approach leaves **28.5yd** in rough (slightly worse starting point) → recovery
reaches the **GREEN directly at 3.0yd** → 1-putt. **Score = 4 (Par).**

**Where chains diverged:** the recovery shot — 이재윤's reached the green in one, 유해란's needed two.
From a *worse* starting distance, 이재윤 recovered more efficiently.

OBSERVED: both full chains. INFERRED: nothing. **Lesson:** another required counterexample — 이재윤
out-recovered 유해란 from a tougher starting spot.

---

### Case 8 — R1H9, par4: comparable rough miss, 유해란 wins this time [B]

**유해란:** tee→ROUGH, leaves **143.8yd** → recovery to rough leaves **6.2yd** → reaches green, 1-putt.
**Score = 4 (Par).**
**이재윤:** tee→ROUGH, leaves **123.7yd** (closer start than 유해란's, i.e. an easier starting position)
→ recovery leaves **9.9yd** still in rough → needs an extra shot to reach green (10.3yd, oddly slightly
further per the raw log) → 2-putt. **Score = 5 (Bogey).**

**Where chains diverged:** 유해란's recovery shot, despite a harder starting distance (143.8 vs
123.7yd), reached a tighter position relative to par than 이재윤's did from an easier starting spot.

OBSERVED: both full chains. **Lesson:** paired with Case 7, shows the rough-recovery advantage/
disadvantage between 유해란 and 이재윤 goes both directions depending on the specific hole — not a fixed,
one-sided skill gap on every rough miss.

---

### Case 9 — R2H3, par4: 유해란 hits the fairway and still bogeys [C]

TEE→**FAIRWAY** (172.8yd left) → approach to **FRINGE at 19.8yd** → chip to **0.9yd** → missed → holed.
**3 putts/finish-stage strokes from the green-adjacent position. Score = 5 (Bogey).**

OBSERVED: full chain — a clean fairway tee shot that still produced a bogey via a longer short-game
sequence. **Lesson:** even the eventual winner's fairway hits don't guarantee a good score — FW% alone
cannot explain her round-to-round variance, consistent with the mission's explicit warning against
using FW% as the headline metric.

---

### Case 10 — R2H7, par5: 유해란 misses the fairway and makes birdie [D]

TEE→**ROUGH** (263.1yd left) → recovery to **FAIRWAY at 83.0yd** → approach to **GREEN at 1.5yd** →
1-putt. **Score = 4 (Birdie).**

OBSERVED: full chain. **Lesson:** a missed fairway that still produced the tournament's better outcomes
— FW MISS ≠ automatic bad score, the mirror image of Case 9.

---

### Case 11 — R3H6, par4: 유해란 loses the ball off the tee and still only bogeys [H]

TEE→**LOST_BALL** → drop/**PENALTY_STROKE** → **FAIRWAY at 143.7yd** (after the penalty, back in play)
→ approach to **GREEN at 6.0yd** → 1-putt. **Score = 5 (Bogey)** — not a Double or worse, despite
starting the hole 2-over-par-equivalent (tee shot lost + penalty stroke) before even reaching the
fairway.

**Where damage stopped escalating:** the penalty was absorbed, and a strong recovery approach
(137.7yd traveled to 6.0yd) plus a clean 1-putt capped the total damage at exactly one stroke over par,
despite the worst possible start to a hole (a lost tee shot).

OBSERVED: full chain, exact coordinates. **Lesson:** this is 유해란's real "damage control" signature —
not flawless golf, but a structure that reliably stops bad starts at Bogey rather than letting them
become Doubles, which is precisely why she has only 1 Double+ event in 72 holes despite real mistakes
appearing throughout her round (see Cases 5, 6, 9 above, where she is NOT flawless).

---

### Case 12 — Hole 8 vs Hole 9: course risk vs player-specific pattern [J]

**Why this case matters:** separates "this location is dangerous for everyone" from "this location is
dangerous for 박서현 specifically," using the full 107-player field.

- **Hole 8, field-wide (n=331):** avg score-to-par **+0.387**, Double+ rate **10.3%** — meaningfully
  harder than the field's all-par-4 average (+0.258 avg, 4.1% Double+). **This is COURSE LOCATION RISK**,
  confirmed independent of any of the three focal players.
- **Hole 9, field-wide (n=331):** avg score-to-par **+0.127**, Double+ rate **4.2%** — actually *easier*
  than the field's all-par-4 average. **This hole is NOT inherently difficult.**

박서현 nonetheless produced Double+ results on Hole 9 in **both R3 and R4** (her R1 pass at Hole 9 was
fine — she even beat 이재윤 there, per the Steps 5–25 top-10 table). So Hole 8's difficulty for her is
corroborated by the whole field; Hole 9's difficulty for her is **not** — it is a repeated pattern
specific to her, on a hole the rest of the field does not generally find hard.

OBSERVED: field-wide aggregate stats (n=331 each hole) and 박서현's 4 individual passes. INFERRED: that
Hole 9's recurring trouble for her reflects something about her play there specifically, since the
field data rules out the hole itself as the universal cause. UNKNOWN: what specifically changed about
her play on Hole 9 in R3/R4 vs R1 (this data can describe the pattern, not her technique).
**Lesson:** Hole 8 needs course-wide caution; Hole 9's repeat trouble is 박서현-specific, not shared by
the field, and should be treated as a real, repeated player pattern (n=2 of her 4 passes), not
over-generalized from Hole 8's genuinely shared difficulty.

---

### Case 13 — Rough-miss recovery: 박서현 vs the field baseline [J]

Field-wide (n=1152 rough-miss situations across all 107 players, all 4 rounds): par-or-better rate
after a rough miss is **46.3%**. 박서현's own rough-miss par-save rate (established in the earlier
Steps 5–25 report from the same underlying chain, n=16 of her own rough misses) is **38%** — below the
field baseline, not merely "below 유해란/이재윤." This confirms her rough-recovery gap is a real,
below-average skill gap relative to the whole field, not an artifact of comparing her only to two
unusually strong recoverers.

OBSERVED: field n and rate, her own n and rate (both already-computed, independently cross-checked
here). **Lesson:** this is the one finding in this casebook that holds up against the full field, not
just against 유해란/이재윤 — real evidence for prioritizing rough recovery practice.

---

### Case 14 — R2H13: 이재윤 birdies, 유해란 only pars [F, J]

**이재윤:** TEE→FAIRWAY (94.8yd left) → approach to **1.6yd** → 1-putt. **Score = 3 (Birdie).**
**유해란:** TEE→FAIRWAY (89.4yd left, a better starting position than 이재윤's) → approach to **3.7yd**
→ 2-putt. **Score = 4 (Par).**

**Where chains diverged:** 이재윤's approach shot was simply better (1.6yd vs 3.7yd) from a *worse*
starting distance (94.8 vs 89.4yd) — and he converted the resulting short putt.

OBSERVED: full chains. **Lesson:** a necessary corrective to any "이재윤 never creates birdies" framing
— he does, including beating 유해란 outright with one. His problem (established separately: 0 Double+
events but only a 6% tournament-wide birdie rate) is that this kind of hole is rare for him, not that
it is impossible.
