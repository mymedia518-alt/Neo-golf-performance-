# NEO GOLF PREDICTIONS — public site

**Status: implemented 2026-08-26.** A static-site generator over the
immutable NEO Prediction Archive (`docs/PREDICTION_ARCHIVE.md`). This
document describes the architecture, routes, data flow, and every
derived Korean label used in the UI.

`src/klpga/site/` computes nothing. It reads already-archived
`PredictionSnapshot` JSON files via
`klpga.archive.prediction_archive.read_prediction_snapshot` (reused
unmodified) and renders static HTML/CSS/vanilla-JS. It never opens the
SQLite database, never imports `klpga.models.inference.run_inference`,
and never mutates a `predictions/*.json`/`.csv` file. Enforced,
not just intended: `tests/test_predictions_site_build.py::test_build_module_source_never_mentions_run_inference_or_sqlite`
and `::test_build_module_does_not_import_run_inference_symbol` assert
this directly against the module source/namespace.

---

## Build artifact policy

The generated site (`web/dist/` by default) is a **build artifact,
not committed to git** — `.gitignore` excludes it. Git preserves
exactly the four things that make the site reproducible:

1. the immutable prediction archives (`predictions/`)
2. the site-generation source (`src/klpga/site/`, `scripts/25_build_predictions_site.py`)
3. tests (`tests/test_predictions_site_build.py`, `tests/test_predictions_site_browser.py`)
4. this documentation

Running `scripts/25_build_predictions_site.py` against any checkout of
this repository reproduces the exact same site (given the same
`predictions/` contents) — nothing about the build depends on
anything outside git.

**"Automatic" means rebuild, not push.** A new archived prediction
appears on the site only after `scripts/25` is rerun and the output
redeployed. There is no live server, no file-watcher, no database
connection at request time — visiting the page never triggers a
rebuild or a database read.

---

## Routes

| Route | Content |
|---|---|
| `/` | The latest archived prediction (by `cutoff_date`), rendered in full — tournament header, metadata, primary table, explanation, methodology panel, Prediction Record panel. |
| `/predictions/` | Index of every archived prediction (currently just #001). |
| `/predictions/<id>/` | Permalink to one specific prediction — identical table/data to `/` when `<id>` is the latest. |
| `/predictions/history/` | Stub: lists predictions with "결과: 대회 진행 전" (result: pending) — **post-tournament evaluation is not implemented**; this route exists so future evaluation results have a home without a routing change. |
| `/methodology/` | The same methodology + probability-explanation copy also shown collapsed on `/`, as a standalone page. |

Internal links are root-relative (`/predictions/`, not
`predictions/`) — this requires the page to be served over HTTP (see
"Local preview" below), not opened directly as a `file://` URL, which
is a standard static-site caveat, not a bug.

---

## Data flow (archive -> page)

Build time only, in `src/klpga/site/build.py` + `templates.py`:

1. `load_predictions()` globs `predictions/*/*.json` and calls
   `read_prediction_snapshot()` per file (existing archive-layer
   function, unmodified, read-only).
2. `_validate_snapshot_for_render()` re-checks, independently of
   trusting the archive layer's own write-time invariants, that:
   rendered player count equals `field_size`; the `rank` sequence is a
   dense, gap-free `1..N` permutation (a gap means a missing entrant,
   a duplicate means two entrants collapsed into one rank); and
   `maximum_probability` is strictly positive (the denominator for the
   probability-bar width). **Any violation raises
   `SiteBuildIntegrityError` and the build writes nothing** — see
   decision #6 of the site-build approval and
   `tests/test_predictions_site_build.py`'s hard-fail tests.
3. Entrants are always displayed in `build.ordered_entrants()` order —
   `sorted(snapshot.predictions, key=lambda e: e.rank)` — the archive's
   own `rank` field, never re-derived from probability.
4. Each page embeds a `<script type="application/json"
   id="prediction-data">` block containing `rank`, `player_code`,
   `player_name_display`, `win_probability` (full precision) for every
   entrant — a **transparency artifact**: anyone can view-source a
   page and confirm the visible table matches the archive exactly.
   The interactive JS (`static/app.js`) does NOT read this blob at
   runtime — it operates on the already-rendered DOM's `data-*`
   attributes instead (simpler, and guarantees the visible HTML and
   the "what JS sees" are the same rendering pass, not two that could
   drift).
5. Percent rounding (`_format_pct`, 2 decimal places) and the
   probability-bar width (`_bar_width_pct`, relative to the field's
   own `maximum_probability`, capped at 100%) are the ONLY two places
   a probability is rounded/transformed, and both are called only at
   render time. The embedded JSON, every `data-*` attribute, and the
   underlying `PredictionSnapshot` all keep the archive's full-precision
   float at all times.
6. Ranking is never recomputed client-side. `static/app.js`'s
   search/filter only toggle a `row-hidden` CSS class on rows that
   already exist, in the order they were rendered — there is no
   client-side sort anywhere, so "search cannot alter ranking" holds
   by construction, not by careful-but-fragile logic (verified at the
   DOM level by `tests/test_predictions_site_browser.py`).

---

## Reviewed Korean wording

Every derived label lives in `src/klpga/site/templates.py` as a named
constant, so it has one place to review and one place to change.

- **History-slice labels** (`HISTORY_SLICE_LABELS_KO`) map
  `klpga.models.walk_forward_eval.ROOKIE_SLICES`'s five frozen bucket
  names to plain Korean descriptions of participation-history depth
  (e.g. `established_20plus` -> "출전 이력 풍부 (20회 이상)"). A
  module-level assertion keeps this dict in lockstep with
  `ROOKIE_SLICES` — if a slice is ever added/renamed upstream, an
  unmapped label fails loudly at import time rather than rendering
  silently wrong.

- **`prior_recent_form_10` — CONFIRMED, 2026-08-26** (was previously
  flagged as a draft; the v1.1 public-copy audit re-derived this
  directly from source before any public-facing number was written —
  see `test_prior_avg_round_score_to_par_is_a_genuine_per_round_rate_by_formula`
  in `tests/test_predictions_site_build.py`). This is the mean of
  each prior tournament's TOTAL score-to-par (not a per-round average,
  not raw strokes, not a finish position) across up to the player's
  10 most recent PRIOR tournaments (never padded — see
  `klpga.backtest.point_in_time_features`'s module docstring). It is
  never labeled "per round" anywhere on the site — that would misstate
  its unit. Current wording (`RECENT_FORM_VALUE_LABEL_KO`,
  `WHY_RECENT_FORM_NOTE_KO`):

  > 최근 최대 10개 대회의 대회 합계 스코어(파 대비) 평균 /
  > 라운드 평균이 아닌 대회 전체 합산 스코어 기준입니다.

  By contrast, **`prior_avg_round_score_to_par` IS a genuine per-round
  rate** — `sum(score_to_par)/sum(rounds_played)`
  (`point_in_time_features.py`) — so the "왜 이 선수의 우승확률이
  높을까요?" section's `WHY_LONG_TERM_LABEL_KO` ("라운드당 평균
  스코어") is the only place on the site that legitimately says "per
  round." These two metrics must never be given the same unit framing.

- **`player_master_matched = false`** ("배윤설 0908(A)"-style entrants):
  labeled "선수 데이터베이스 미매칭" with an explanatory note
  ("출전자 명단에는 있으나 기존 선수 데이터베이스와 자동으로
  매칭되지 않은 경우입니다...") — factual about what "unmatched"
  means, without speculating "rookie" or any other unverified claim.

- **`provenance.source = "rerun_reconstruction"` — REMOVED from
  public UI, v1.1 (2026-08-26).** Previously surfaced inside the
  collapsed "Prediction Record" panel; as of v1.1 that panel shows
  only four fixed public facts (prediction number, cutoff, PRE-
  TOURNAMENT status, LOCKED status — see "Public copy" below) and no
  provenance/reconstruction language at all. The full provenance
  object (`source`, `original_run_status`,
  `original_machine_readable_snapshot_available`,
  `reconstruction_reason`, `verification`) remains completely intact
  in the archived JSON and in the page's transparency `<script
  type="application/json">` blob — it is not deleted, only no longer
  rendered as visible prose. `#001` must still never be called "the
  original run" anywhere this project writes about it, even though
  that specific disclosure is no longer public-facing.

---

## Public copy — model explanation, v1.1

**Status: implemented 2026-08-26**, in response to an explicit
public-release copy pass. Every constant referenced below lives in
`src/klpga/site/templates.py`.

**Removed from normal reader-facing UI**: the model name/version
("M4", "M4 Production v1"), the calibration-limitation disclosure
(`snapshot.known_limitations` — which also names an internal docs
file — is intentionally never rendered), and any `docs/`-path
reference. `model_id`/`model_version` remain in the page's embedded
transparency JSON blob (`_embedded_data_json`) — that block is treated
as internal/archive-provenance metadata, not reader-facing prose, the
same distinction the archive JSON itself already draws.

**Model explanation** (`_model_explanation_paragraphs`, rendered in
the "모델은 어떻게 계산하나요?" panel and the standalone
`/methodology/` page): a fixed three-sentence explanation, two of its
numbers (`training_tournament_count`, `field_size`) drawn from the
snapshot, one (`CORPUS_PLAYER_TOURNAMENT_ROWS_APPROX = "11,850"`)
FIXED editorial copy sourced from the real production coverage audit
run 2026-08-26 — not recomputed at build time, since the archive
schema has no player-target-row-count field and the site build never
queries the database. **Must be re-verified before reuse for a
prediction built against a materially different historical corpus.**

**"왜 이 선수의 우승확률이 높을까요?" section** (`_why_section_html`):
shown near the leaderboard, for the archive's rank-1 entrant only
(dynamic — not hardcoded to any one player), using only archived
values (`prior_events_n`, `prior_avg_round_score_to_par`,
`prior_recent_form_10`/`_n`). Never claims SG/GIR/driving/putting were
used — those inputs don't exist in this dataset at all (confirmed by
a 2026-08-26 data-coverage audit: `player_round`'s birdie/eagle/bogey/
GIR-adjacent columns are hardcoded NULL by the collector, and every
`player_stats_snapshot` official-Data-Center column — SG ×5, GIR,
driving, putting — has never been written by any code path in this
project; that audit was conversational and is not itself committed as
a doc, but its conclusion — SG/GIR/driving/putting are simply absent
from every table this site could read — is the same conclusion
`METHODOLOGY_EXCLUSION_KO` states).

**Summary strip** (`_summary_strip_html`): four facts — historical
tournament count, the fixed corpus-rows figure, field size, and the
constant "100%" probability-sum fact — replacing the old metadata
block (which named the model).

**Simplified Prediction Record** (`_prediction_record_block_html`):
exactly four items, no model name/version, no provenance detail —
see the `provenance.source` bullet above.

---

## Player names rendered verbatim

The web layer never corrects, normalizes, or reformats an archived
player name. `player_code=13355` is rendered exactly as the locked
archive stores it — **"배윤설 0908(A)"** — regardless of any earlier,
different spelling mentioned in prior conversation. The archive is
authoritative; the site layer's job is to display it exactly, not to
reconcile it against anything else.

---

## Visual direction

Single neutral accent color (`--neo-accent`, a muted teal), used only
for the probability-bar fill and active search/filter controls — no
favorite/underdog color coding, no green/red framing, no odds-style
number formatting. Probability bars are scaled RELATIVE to the
field's own top probability (`_bar_width_pct`), not an absolute 0-100%
domain — with 100+ entrants most probabilities are under 5%, so an
absolute scale would render nearly every bar as an invisible sliver.
The bar communicates relative strength only; the printed percentage
next to it is always the ground truth number.

System font stack only (Apple SD Gothic Neo / Malgun Gothic / Noto
Sans KR / Segoe UI fallback) — no bundled webfont.

---

## Windows commands

Build:
```
python scripts\25_build_predictions_site.py --predictions-dir predictions --output-dir web\dist
```

Local preview (serves the built output over HTTP so root-relative
links resolve correctly — opening `index.html` directly via `file://`
will break internal navigation, a standard static-site limitation):
```
python -m http.server 8000 --directory web\dist
```
Then open `http://localhost:8000/` in a browser.
