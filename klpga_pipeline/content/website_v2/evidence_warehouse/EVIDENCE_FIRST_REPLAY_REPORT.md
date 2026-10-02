# Evidence First Architecture — Replay Test Report (2026-10-02)

## R2: PASS — 100% byte-identical
`Evidence Warehouse → Round Transition Engine → Projection Builder → render_round_page()`
produced an HTML file whose SHA256 exactly matches the currently-published
`docs/tournaments/2026/2026100005/r2/index.html`:

```
efdad22daf5d82ac573aec15407d5346d0991a4d4538e6c68ca80a17941b8043
```

All 108 real entrants' `finish_position` / `finish_position_numeric` /
`score_to_par` / `r{1..4}_score` / `withdrawn` / `disqualified` / `missed_cut`
fields matched exactly (0 mismatches) between the Projection and the
currently-committed `2026100005_LEADERBOARD.json`.

Fixed during this validation: the Projection's record order initially
followed `ENTRY_KRANKING_JOIN.json`'s roster order, not the raw-HTML DOM
order real tie-break order within same-rank groups comes from. Corrected
to replay `parse_leaderboard()`'s own exact record order (raw-HTML match
order first, carried-forward/absent entrants appended after) — this is
what made the replay byte-identical.

## R2 update (2026-10-02, later same day): now NOT byte-identical — root cause is the Projection predating the R1_CUT/R2_CUT status-model mission, not a defect in this architecture

The 2026-10-02 "상태 모델" mission added real `status`
(`R1_CUT`/`R2_CUT`/`WD`/`DQ`/`None`) and `status_round` fields directly to
the live production pipeline, `hitejinro_round_pipeline.py::parse_leaderboard()`
— a separate, already-live module, explicitly in scope for that mission.
That mission's instructions also explicitly froze this Warehouse/Engine/
Projection architecture ("Warehouse Replay Transition Engine Collector
Projection 전부 수정 금지"), so `projection_builder.py` was deliberately
NOT updated to emit the new fields.

`hitejinro_round_page.py::_status_display_label()` was simplified in the
same mission to read `record.get("status_round")` directly (previously it
re-derived the same value from r1-r4 scores at render time). Fed a real
`parse_leaderboard()` record, this is correct — the live page is unaffected
(confirmed byte-identical to the already-LIVE-verified `96e9995` output).
Fed a `projection_builder.py` record, which has no `status_round` key at
all, `_status_display_label()` falls back to the bare status string
("CUT"/"WD" with no round qualifier) instead of the now-correct "R1 CUT"/
"R1 WD" qualified label — hence the Replay Test's SHA256 mismatch.

This is the same class of pre-existing-staleness divergence as the R1
section below, just surfacing on R2 this time: the frozen Projection
Builder's output schema predates a later, explicitly-scoped-elsewhere
change to the live pipeline's own schema. `round_transition_engine.py`
and `projection_builder.py` remain untouched, per that mission's explicit
instruction. `tests/test_evidence_first_replay.py`'s R2 byte-identical
assertion is marked `xfail(strict=True)` with this section referenced in
the reason, rather than silently skipped or deleted — exactly the
documentation discipline already applied to the R1 divergence below.
Should `projection_builder.py` ever be revisited (out of scope for now),
adding `status`/`status_round` passthrough would restore the byte-identical
match.

## R1: NOT byte-identical — root cause is pre-existing staleness, not a defect in this architecture

Two independent, already-documented causes, both predating this mission:

1. **Missing columns.** The currently-published R1 page only has an `R1`
   column (no R2/R3/FR). The "always render all 4 rounds" fix (commit
   `b53f674`, 2026-10-02) was applied to R2 and HOME only — R1's own page
   was never rebuilt after that fix. The Evidence-First replay correctly
   produces all 4 columns, per the current (already-approved) code.
2. **Missing WD player.** 마다솜 (player 9401) is entirely absent from the
   currently-published R1 page — the exact, already-documented symptom of
   the hardcoded `withdrawn=False` bug fixed in commit `0d52297`
   ("HITE JINRO R2: official data pipeline + real WD/CUT status fix"),
   which was likewise never backfilled to R1's own page.
3. **NEO 경기력 band score drift.** Unrelated to both of the above: the
   band score (`data-neo-score`) is read from
   `historical_sg_warehouse_corrected_v2.json`, a file that keeps changing
   as SG data is merged in over time (e.g. `merge_sg_into_warehouse(2)`,
   run later this session). Any rebuild of R1 today — via the old code
   path or this new one — would show a different band score than what's
   currently published, for reasons entirely outside this mission's scope.

None of these three are caused by the new Evidence Warehouse / Round
Transition Engine / Projection Builder — they are proof that R1's
published page is stale relative to already-approved, already-committed
fixes. Republishing R1 would be a legitimate, separate content change;
it was not done here without explicit confirmation (same discipline this
session has applied to every other live-page change).

## What was NOT changed

`klpga.neo_win.hitejinro_round_page.render_round_page()`,
`klpga.neo_win.hitejinro_round_pipeline.parse_leaderboard()`, and every
script under `scripts/196-204_*` are unchanged. The live R2 page's
generation path is still `parse_leaderboard()` → `LEADERBOARD.json` →
`render_round_page()`, exactly as before. `round_transition_engine.py`
and `projection_builder.py` are new, additive, parallel code, proven
equivalent to the live path for round 2 by this Replay Test — not yet
wired in as the live path's own implementation. See the design doc's
own risk discussion for why: swapping the entry point used by a
mid-tournament, currently-live page is a materially different, higher-
risk action than adding and proving an equivalent implementation
alongside it.
