# NEO Blue Heron Shot Deep Dive — derived analysis layer

Read-only against the immutable RAW/normalized Shot Tracker data.
Produces derived metrics only; never writes back to the source table.

See `NEO_BLUE_HERON_SHOT_DEEP_DIVE.md` for the full report.

## Regenerating

`klpga_shots_RAW_READONLY.sqlite` is gitignored (12MB binary, already
durably stored on the `collector-output/2026100005-shot-tracker-full-field`
orphan branch — no need to duplicate it in this branch's history). To
regenerate the derived CSVs from scratch:

```
git show origin/collector-output/2026100005-shot-tracker-full-field:__out/klpga_shots.sqlite \
  > klpga_shots_RAW_READONLY.sqlite
python3 derive_shot_analysis.py
```

`players_RAW_READONLY.json` (the real player-field discovery output) is
committed as-is since it is small and text-based.
