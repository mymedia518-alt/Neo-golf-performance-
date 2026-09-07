# NEO SITE V5 — Page Migration Matrix

Inventory of every public page currently live in `docs/` (production,
`neo-website-v2` @ `75d2ea1`), classified for migration to the HOME V4
site-wide design system (Mission 1). Produced by direct inspection of
the shipped HTML and its generator scripts — no pre-existing site-map
document existed in the repo to draw from.

Classification legend: **A** already HOME V4 compliant · **B** needs
visual migration only (same DOM shape, restyle-safe) · **C** needs
structural/template migration · **D** historical/frozen — content must
never be rewritten, presentation-only wrapper permitted · **E**
obsolete/orphaned.

| Page/Template | File(s) | Generating script | Current CSS | Class | Reasoning |
|---|---|---|---|---|---|
| Homepage | `docs/index.html` | `scripts/109_build_home_v4_data_terminal.py` (candidate branch only — not merged into `neo-website-v2`'s own `scripts/`, only its output was promoted) | `neo-site.css` + `home-v4.css` | **A** | The HOME V4 reference implementation itself. |
| NEO LAB | `docs/neo-lab/index.html` | same script, `render_neo_lab_page()` | same as above | **A** | Same scaffold, same build. |
| Ranking (K-Ranking TOP120) | `docs/ranking/index.html` | `scripts/88_build_neo_top120_candidate.py` → `scripts/94_promote_top120_to_production.py` | `neo-site.css` only | **B** | Old `neo-global-header` + table-based content, already dashboard-shaped; needs nav-component swap + re-skin, not a content-model rebuild. |
| Deep Dive | `docs/deep-dive/index.html` | `src/klpga/website_v2/migration.py` `_deep()` → script 94 | `neo-site.css` only | **B** | Same structural DNA as the rest of the old system; restylable without DOM changes. |
| About | `docs/about/index.html` | `src/klpga/website_v2/migration.py` `_about()` → script 94 | `neo-site.css` only | **B** | **Migrated as the Mission 1 proof-of-concept** — see `scripts/111_build_design_system_v2_demo.py` and `candidate/neo-site-v5-design-system-demo/about/`. Body content verified byte-identical to production; only chrome (header/nav/stylesheet) changed. |
| Tournaments hub | `docs/tournaments/index.html` | `migration.py` `_tournaments()` → script 94, subsequently hand-patched by narrow "fix:" commits | `neo-site.css` only | **B** | Live-updated summary/status page, not a frozen result; safe to restyle fully. |
| KG Ladies Open — hub | `.../kg-ladies-open/index.html` | `migration.py` `_overview()` → script 94 | `neo-site.css` only | **B** | Per-tournament index/summary, not itself a results record. |
| KG Ladies Open — PRE / R3 / FINAL | `.../pre/`, `.../r3/`, `.../final/` | `migration.py` `_pre()`/`_stage()`/`_final()` via `shell.py` → script 94 | `neo-site.css` only | **D** | Point-in-time forecasts + the final result, each SHA-256-hashed, explicitly "never revised after the fact" (module docstrings, NEO Prediction Archive design intent). Presentation-only wrapper allowed; content frozen. |
| KG Ladies Open — R1 / R2 | `.../r1/`, `.../r2/` | `src/klpga/neo_win/r1_frozen_snapshot.py` + `r2_html_render.py`/`r2_production_page.py` | `neo-site.css` only (+ page-specific Google Fonts) | **D** | Explicitly named "immutable" in their own module docstrings; older sub-template than pre/r3/final (no `<main>` wrapper). Content frozen regardless. |
| OK Savings Bank Open — PRE / R1 / R2 | `.../pre/`, `.../r1/`, `.../r2/` | `scripts/84_build_ok_open_pre_website_candidate.py` → script 94, R1/R2 additionally live-patched by `scripts/build_current_round_page.py` | `neo-site.css` + `neo.css` | **D** | Dated, evidence-linked snapshots for an already-played tournament (2026-09-04–06). |
| OK Savings Bank Open — R3 | `.../r3/index.html` | Same class family as script 84's output; exact originating script not confidently attributable (script 84 as currently checked in only loops `r1/r2/final`) — flagged, not guessed | `neo-site.css` + `neo.css` | **D** | Same frozen-result rationale; attribution gap does not change the classification. |
| OK Savings Bank Open — FINAL | `.../final/index.html` (509 bytes) | No script — a hand-authored static redirect stub to `.../r3/` (OK Open is 54-hole/3-round, so R3 *is* FINAL) | none | **D** | Zero UI to restyle; any future work here is routing only. |
| Protected / evidence archive | `docs/protected/beta001/{r1,r2,r3}.html` | Not independently attributed; referenced by SHA-256 from every KG stage page's methodology disclosure | inline `<style>` only | **D** | Canonical "must never be rewritten" case — a raw, hash-verified evidence record, deliberately outside the main nav structure. |

**Config files** (not classified, confirmed present): `docs/CNAME`
(`neogolfdata.com`), `docs/.nojekyll`.

**Tournaments present:** `kg-ladies-open` (2026.08.27–30, concluded,
full stage set) and `ok-savings-bank-open` (2026.09.04–06, 54-hole/3-
round, no separate hub page). No orphaned (**E**) page was found among
the currently-live files above — the one previously-orphaned artifact
(`docs/data/neo-top120-evaluation.json`) was already removed by the
HOME V4 promotion commit itself.

## What this unlocks

- **B-classified pages** (ranking, deep-dive, about, tournaments hub,
  KG overview) can all be migrated the same way About was: swap their
  `render_page(..., design_system="v1")` call to `"v2"` — zero content
  changes, per `shell.py`'s `render_page()` contract (see
  `tests/test_design_system_v2.py::test_render_page_v2_body_content_
  byte_identical_to_v1`).
- **D-classified pages** may ALSO adopt the new header/nav chrome
  (their own generators already call `inject_global_navigation()`,
  the same mechanism `inject_global_navigation_v2()` mirrors) — doing
  so changes zero result data, only the page frame. Not done in this
  pass; flagged as the next, still-isolated-branch step so it can be
  reviewed on its own before any promotion.
- **C-classified pages**: none were found in the current inventory —
  every legacy page turned out to share the same underlying
  `neo-global-header` shell family, so no page required a full DOM
  rebuild just to adopt the new chrome. A genuine C case would be a
  page whose structure diverges enough that `inject_global_navigation_v2()`
  cannot find a marked header or `<body>` tag to anchor on.
