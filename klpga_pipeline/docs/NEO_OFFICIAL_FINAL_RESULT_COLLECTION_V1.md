# NEO official final-result collection

The two-event validator does not treat a live snapshot, news article, or
screen capture as a final result. The official KLPGA leaderboard is fetched
from the confirmed `roundLeaderboard` endpoint and saved in three parts:

1. Raw final-round HTML under `outputs/official_final_results/<game_code>/`.
2. A scoreable final-result JSON under `klpga_pipeline/content/website_v2/`.
3. A source-audit JSON beside the result, including the request form,
   timestamp, raw-response hash, result hash, and official page URL.

Run from the repository root:

```powershell
.\NEO_COLLECT_AND_VALIDATE_TWO_EVENTS.bat
```

The wrapper currently collects the official Round 3 result for
`2026120001` and then runs the existing two-event validation report. It
does not enable model tuning or freeze evidence unless every manifest gate
passes. Use `--freeze` only after reviewing the report.

If a result or source-audit file already exists, the collector preserves it
and stops. An overwrite requires an explicit direct invocation with
`--overwrite` after reviewing the existing artifact.
