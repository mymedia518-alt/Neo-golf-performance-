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
klpga.neo_reader.cli sync --game-code XXXXXXXXXX --season YYYY --stage pre
    │  Stage 1: collect  (Tournament Info + Entry List + K-Ranking,
    │           via the exact already-confirmed endpoints in
    │           klpga_pipeline/src/klpga/config.py)
    │  Stage 2: normalize (→ normalized/<gameCode>/*.json)
    │  Stage 3: warehouse (→ data/klpga.sqlite, via klpga.db.upsert —
    │           this file is a CI-runner-local working store, rebuilt
    │           fresh each run; normalized/<gameCode>/ENTRY_SNAPSHOT.json
    │           is the durable, committed record of what it holds)
    │  Stage 4: validate  (real checks — see klpga.neo_reader.validate;
    │           no PASS without evidence)
    │  Stage 5: review report (reports/<gameCode>/REVIEW_REPORT_V1.md)
    │  Stage 6: git publish (see below — runs unless --dry-run/
    │           --skip-github-upload, and only once validation PASSes)
    ▼
git push --force origin reader/<gameCode>: raw/<gameCode>,
    normalized/<gameCode>, reports/<gameCode>, content/<gameCode>_*.json
    committed straight into the repository, on a dedicated branch.
    ▼
Claude: `git fetch origin reader/<gameCode>` and reads the committed
    files directly — NEVER via GitHub Actions Artifact download, NEVER
    via a manually pasted HTML capture. Extracts/reads
    klpga_pipeline/{raw,normalized,reports}/<gameCode>/ and
    klpga_pipeline/content/website_v2/<gameCode>_*.json, exactly where
    the existing 139/151/160/174/181/156 build scripts already expect
    to find that data.
    ▼
Claude builds PRE (139_build_hana_pre_kb_structure.py's own pattern,
    generalized to the new gameCode), then Entry List / K-Ranking / NEO
    Ranking / PRE Prediction / Course Analysis / Deep Dive, then flips
    HOME from the previous tournament's FINAL to this tournament's PRE
    — same rules as every prior tournament on this site: no UX changes,
    no layout changes, sponsor and player-name positions unchanged,
    visual QA before publishing.
```

## Why a git branch, not a GitHub Actions Artifact

**ARCHITECTURE CORRECTION (2026-09-30):** this document originally
specified `actions/upload-artifact` + Artifact download as the default
route. That was tried for real and found broken: the GitHub Actions
Artifact-download API hands back a short-lived *signed URL* pointing at
Azure Blob Storage (`productionresultssa14.blob.core.windows.net`), and
that host is blocked from Claude's sandbox the same way klpga.co.kr is
(confirmed via direct curl — same 403 CONNECT-tunnel failure). So the
Artifact route cannot actually be consumed by Claude, even though the
CI job producing it succeeds.

The corrected, verified-working route: stage 6 (`klpga.neo_reader.publish`)
commits the sync output straight into the repository on a dedicated
`reader/<gameCode>` branch and `git push --force`s it. This branch is a
disposable "latest snapshot only" branch, not accumulated history —
each re-sync of the same gameCode fully replaces the last one, so
force-push is the correct operation here, not a workaround. `git
fetch`/`git pull` against this repository has been proven reachable
from Claude's sandbox throughout this whole project, unlike Azure Blob
Storage.

`actions/upload-artifact` is still run in the workflow too, kept purely
as a convenience for a human operator who does not have Claude's sandbox
restriction and wants a quick local zip download — it is never Claude's
own path to the data.

**Claude's own operating rule, going forward**: once this route exists,
Claude uses the `reader/<gameCode>` branch as the *only* source for a
new tournament's raw/normalized/reports data. Claude never asks the
operator for HTML, a player list, or a tournament table again unless
this route itself is confirmed broken (see "Escape hatch" below) — the
gameCode is the only thing still asked for.

## Running it

1. Trigger `.github/workflows/neo-sync.yml` (`workflow_dispatch`) with
   `game_code` (required) and `season` (optional, inferred from the
   gameCode's leading 4 digits if omitted). The workflow file must exist
   on the repository's default branch to be dispatchable at all, but
   `ref` controls which branch's code actually runs — use
   `neo-website-v2`, where `klpga.neo_reader` itself lives.
2. Wait for the run to complete. Its job summary shows the same
   PASS/FAIL table `neo_reader.review_report` renders locally.
3. If it succeeded, `git fetch origin reader/<gameCode>` and read the
   committed files directly, then proceed to build PRE. If it failed,
   the job summary and the uploaded (even-on-failure) raw captures say
   exactly which stage failed and why — Claude reports that, never
   guesses past it.

## Escape hatch (only if the git-publish route itself is broken)

If GitHub Actions cannot reach klpga.co.kr either (see
`.github/workflows/test-klpga-reachability.yml`, the diagnostic that
should be run once before relying on this route for the first time), or
a specific sync run fails for a reason unrelated to the tournament's own
data, `neo-sync.ps1` remains available for the operator to run locally
per the original design (see that script's own header comment) — its
output can be fed to Claude the same way, just via a local path instead
of the `reader/<gameCode>` branch.

## Status

This document is registered as the default starting route once
Section "Running it" above has been exercised end-to-end for a real
gameCode and produced a PASSing review report and a usable Artifact —
see the End-to-End Test Log below.

### End-to-End Test Log

<!-- Appended after each real run of this route; never edited after the
     fact, only appended to — same "amend, never rewrite" discipline as
     OPERATING_RULES.md's archive manifests. -->

**2026-09-30 — gameCode=2026100005 (제26회 하이트진로 챔피언십), season=2026, stage=pre**

- Workflow run: `neo-sync.yml` run #6 (https://github.com/mymedia518-alt/Neo-golf-performance-/actions/runs/36704095843), `ref=neo-website-v2`, conclusion=`success`.
- Trigger phrase this proves: an operator saying "이번 대회 시작" with a
  gameCode is now sufficient — no HTML capture, no manual player list, no
  manual tournament table were supplied or needed for this run.
- Collection stages: `tournament_info` SUCCESS (제26회 하이트진로 챔피언십,
  20261001–20261004), `entry_list` SUCCESS (108 entrants, 0 unparsed),
  `kranking` SUCCESS (2026-W39, 747 ranked players).
- Validation: **Overall PASS** — all 7 checks passed:
  `tournament_info_required_fields`, `tournament_info_game_code_matches`,
  `entry_list_nonempty`, `entry_list_no_unparsed_rows`,
  `entry_list_matches_page_total`, `kranking_top10_crosscheck`,
  `kranking_top120_population`.
- Publish: pushed to `reader/2026100005` (commit `19f5aebe095e`) —
  `raw/2026100005/`, `normalized/2026100005/`, `reports/2026100005/`,
  `content/website_v2/2026100005_{TOURNAMENT_INFO,ENTRY_SNAPSHOT,KRANKING_TOP120}.json`
  all present and readable via `git fetch origin reader/2026100005`.
- Two real bugs were found and fixed by this same route before this run
  went fully green (both via live CI output/data, not guessed): (1)
  K-Ranking's live table markup had drifted to a new CSS class/cell
  layout since the original parser was written — see
  `scripts/87_collect_kranking_top120.py`'s `_FULL_TABLE_LAYOUTS`; (2)
  re-syncing the same gameCode a second time hit a non-fast-forward
  push rejection on `reader/<gameCode>` — see `neo_reader/publish.py`'s
  `git push --force` fix and rationale.
- Status: **this route is registered as the default starting route of
  the NEO Operation Manual**, per the criteria this section's own header
  states — exercised end-to-end for a real gameCode, produced a PASSing
  review report, and the committed branch is directly usable by Claude
  with no live KLPGA access.
