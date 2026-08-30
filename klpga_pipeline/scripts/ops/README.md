# NEO AUTO OPS — one-click launchers

- **`neo_final_close_launcher.bat`** — double-click this. Runs the real
  `scripts/final_close_preflight.py` for game_code=2026080001 (BETA #001),
  season=2026, expected_final_round=4, against `data/klpga.sqlite` and the
  live KLPGA site. Saves the full console output to
  `outputs/neo_ops/2026080001/live_final_close.txt` and a machine-readable
  summary to `outputs/neo_ops/2026080001/live_final_close.json`. Prints one
  line at the end: `NEO FINAL CLOSE: GO`, `WARN`, or `HARD STOP`. The window
  stays open (waits for a keypress) unless the result was GO.

- **`run_final_close.ps1`** — the actual logic the `.bat` delegates to.
  Accepts `-GameCode` / `-Season` / `-ExpectedFinalRound` / `-Finalists` /
  `-DbPath` overrides for a future tournament, e.g.:
  `neo_final_close_launcher.bat -GameCode 2026080002 -Season 2026`
  (today's defaults are BETA #001's real values — no args needed for a
  normal double-click run).

- **`register_task_scheduler.bat`** — a TEMPLATE for registering a Windows
  Task Scheduler entry that runs the launcher unattended. **Not scheduled
  by default** — it only registers anything if a human deliberately opens
  and runs it, after reviewing/editing the placeholder schedule inside.

None of these three files freeze FINAL, freeze an evaluation, modify
`docs/index.html`, deploy, commit, or push — they only ever invoke
`scripts/final_close_preflight.py`, which itself never does any of those
(see that script's own module docstring).
