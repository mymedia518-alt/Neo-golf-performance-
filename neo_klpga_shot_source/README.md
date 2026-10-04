# NEO KLPGA Shot Source

Independent, laptop-local collector for KLPGA Shot Tracker data. Does not read
or write any existing NEO operating environment path (e.g. a desktop
`D:\NEO_DATA_ROOT`) -- all output goes under this directory's own
`NEO_DATA_ROOT_LOCAL/` (gitignored; raw/normalized output is not committed to
the main repo tree, only the collector tooling and validation reports are).

Source endpoints, confirmed from real KLPGA player-detail HTML evidence:
- `POST /ajax/leaderboard/getShotTracker` -- params `gameCode, round, hole, playerCode`
  - response: `shotTrackerList`, `baseHoleInfo`, `holeInfo`
- `POST /ajax/leaderboard/getGroupShotTracker` -- params `gameCode, round, hole, groupNo`
  - response: `groupPlayerList`, `groupShotTrackerList`, `baseHoleInfo`, `holeInfo`
  - NOT yet adopted as primary. Per operating instruction, the group API only
    replaces the per-player API after a real, evidence-based completeness
    comparison confirms equivalence. Until then it is validation/fallback only.

Canonical shot key: `(game_code, player_code, round, hole, shot)`.

Raw policy (never violated):
- RAW response bytes are never modified.
- A raw file is never overwritten; a differing response at the same
  (game, player, round, hole) path is saved under a sha256-suffixed filename.
- Every real field present in a `shotTrackerList` row is preserved, both in
  named normalized columns (for the known field set) and verbatim in the
  row's `raw_json` column (for any field, named or not). Any field name seen
  outside the known set is also logged to `logs/<game>/extra_fields_seen.jsonl`
  so it is never silently lost track of.

pp_state mapping (official KLPGA UI labels):
```
1 FAIRWAY        6 BUNKER
2 ROUGH          7 LOST_BALL
3 GREEN          8 PENALTY_STROKE
4 OB             9 GREENSIDE_BUNKER
5 PENALTY_AREA  10 HOLED
                12 FRINGE
```
A code outside this table is never interpreted. It is preserved as
`UNKNOWN_<code>` in both the ko/en name columns and logged to
`logs/<game>/unknown_pp_state.jsonl`.

## Validated collection sequence (explicit operating instruction)

1. Single hole, one player (유해란 / 9115), round 4 hole 18 -- smoke test.
2. Full FR (round 4, holes 1-18) for the same player -- validate.
3. Full tournament (rounds 1-4) for the same player -- validate.
4. Only once step 3 reports VALIDATION: PASS does collection expand to the
   full player field. Expansion to all players is a separate, later step --
   not performed automatically.

Collection against the real klpga.co.kr endpoints runs via GitHub Actions
(`.github/workflows/collect-shot-tracker-oneoff.yml`), since the agent
sandbox this tooling was built in has no direct network path to klpga.co.kr.
