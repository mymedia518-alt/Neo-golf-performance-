# START_TOURNAMENT — the one-command tournament start

**Goal of this document**: from now on, starting a new tournament is one
sentence — *"이번 대회 시작"* ("this tournament starts") — plus one real
fact only a human can supply: the official KLPGA `gameCode`. Everything
after that runs through the same, already-verified pipeline every time.
No manual HTML captures. No manual player lists. No hand-built tournament
tables. No live network access from Claude's own sandbox, ever.

## The one thing a human must still provide

**The gameCode.** Nothing else. Claude never guesses it, never derives it
from "this week," and never asks for anything else once it has this —
see `klpga_pipeline/src/klpga/neo_reader/`'s own module docstrings for
why: this sandbox cannot reach klpga.co.kr (confirmed: `klpga.co.kr:443`
returns 403 at the egress proxy's CONNECT step), so the gameCode is the
one real fact that has to cross that boundary by hand.

## The pipeline, end to end

```
Operator: "이번 대회 시작. gameCode=XXXXXXXXXX"
    │
    ▼
GitHub Actions: .github/workflows/neo-sync.yml (workflow_dispatch)
    │  runs on a GitHub-hosted runner, which DOES have real internet
    │  access — unlike Claude's own sandbox
    ▼
klpga.neo_reader.cli sync --game-code XXXXXXXXXX --season YYYY --stage pre --dry-run
    │  Stage 1: collect  (Tournament Info + Entry List + K-Ranking,
    │           via the exact already-confirmed endpoints in
    │           klpga_pipeline/src/klpga/config.py)
    │  Stage 2: normalize (→ normalized/<gameCode>/*.json)
    │  Stage 3: warehouse (→ data/klpga.sqlite, via klpga.db.upsert)
    │  Stage 4: validate  (real checks — see klpga.neo_reader.validate;
    │           no PASS without evidence)
    │  Stage 5: review report (reports/<gameCode>/REVIEW_REPORT_V1.md)
    │  (Stage 6, git publish, is intentionally SKIPPED here — see below)
    ▼
actions/upload-artifact: raw/<gameCode>, normalized/<gameCode>,
    reports/<gameCode>, content/<gameCode>_*.json
    → one GitHub Actions Artifact, named neo-sync-<gameCode>-<run_id>
    ▼
Claude: downloads that Artifact via the GitHub Actions API
    (mcp__github__actions_get, method=download_workflow_run_artifact) —
    NEVER via a git branch, NEVER via a manually pasted HTML capture.
    Extracts it into klpga_pipeline/{raw,normalized,reports}/<gameCode>/
    and klpga_pipeline/content/website_v2/<gameCode>_*.json, exactly
    where the existing 139/151/160/174/181/156 build scripts already
    expect to find that data.
    ▼
Claude builds PRE (139_build_hana_pre_kb_structure.py's own pattern,
    generalized to the new gameCode), then Entry List / K-Ranking / NEO
    Ranking / PRE Prediction / Course Analysis / Deep Dive, then flips
    HOME from the previous tournament's FINAL to this tournament's PRE
    — same rules as every prior tournament on this site: no UX changes,
    no layout changes, sponsor and player-name positions unchanged,
    visual QA before publishing.
```

## Why GitHub Actions Artifacts, not a git branch

`klpga.neo_reader.publish` (stage 6) *can* commit sync output to a
dedicated `reader/<gameCode>` branch — that path still exists for a
human running `neo-sync.ps1` locally. But the **default, automated**
route (this document) uses `actions/upload-artifact` instead:

- No push credentials needed inside the CI job beyond the default,
  read-scoped `GITHUB_TOKEN`.
- Never touches git history or any branch — nothing to review/revert if
  a sync run turns out bad; the artifact simply isn't used.
- Claude fetches it the same well-defined way every time (one API call
  per run), instead of needing to know which branch a given sync's
  results happen to live on.

**Claude's own operating rule, going forward**: once this route exists,
Claude uses GitHub Actions Artifacts as the *only* source for a new
tournament's raw/normalized/reports data. Claude never asks the operator
for HTML, a player list, or a tournament table again unless this
Artifact-based route itself is confirmed broken (see "Escape hatch"
below) — the gameCode is the only thing still asked for.

## Running it

1. Trigger `.github/workflows/neo-sync.yml` (`workflow_dispatch`) with
   `game_code` (required) and `season` (optional, inferred from the
   gameCode's leading 4 digits if omitted).
2. Wait for the run to complete. Its job summary shows the same
   PASS/FAIL table `neo_reader.review_report` renders locally.
3. If it succeeded, Claude downloads the `neo-sync-<gameCode>-<run_id>`
   artifact and proceeds to build PRE. If it failed, the job summary
   and the uploaded (even-on-failure) raw captures say exactly which
   stage failed and why — Claude reports that, never guesses past it.

## Escape hatch (only if the Artifact route itself is broken)

If GitHub Actions cannot reach klpga.co.kr either (see
`.github/workflows/test-klpga-reachability.yml`, the diagnostic that
should be run once before relying on this route for the first time), or
a specific sync run fails for a reason unrelated to the tournament's own
data, `neo-sync.ps1` remains available for the operator to run locally
per the original design (see that script's own header comment) — its
output can be fed to Claude the same way, just via a local path instead
of a downloaded Artifact.

## Status

This document is registered as the default starting route once
Section "Running it" above has been exercised end-to-end for a real
gameCode and produced a PASSing review report and a usable Artifact —
see the End-to-End Test Log below.

### End-to-End Test Log

<!-- Appended after each real run of this route; never edited after the
     fact, only appended to — same "amend, never rewrite" discipline as
     OPERATING_RULES.md's archive manifests. -->
