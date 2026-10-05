# PLAYER_DELIVERABLES_EXPORT_MANIFEST

Produced by: Claude (cloud session, no D:\ access). For local Codex: `git pull` → read this manifest → copy listed paths to `D:\NEO_DATA_ROOT\...` → verify SHA-256 → done. No re-analysis needed.

Git branch: `claude/klpga-tournament-data-collection-k47i28`
Game: 2026100005 (하이트진로 챔피언십, Blue Heron)
Scope: Hole 1 + Hole 12 only (both already PASSed/locked). Hole 8 not started.

## Entry point (browser)

Published Artifact (works immediately, no setup): **https://claude.ai/artifact/2NKbMfoRbdLt91NBsGs2eg**

Local file (same content, for D: deployment): `neo_klpga_shot_source/derived_analysis/artifact_data/player_product.html` — self-contained HTML, needs `hole_1.png` and `hole_12.png` (listed below) in the same directory to render the course maps.

## 1. Product files (new/modified this task)

| Path | Role | Bytes | SHA-256 |
|---|---|---|---|
| `neo_klpga_shot_source/derived_analysis/artifact_data/player_product.html` | The product itself — player/hole selector, strategy card, course map, 4-tier risk, evidence, detail. Self-contained (data embedded inline). | 198959 | `ae0e139534f0e207d3d2011fe666901ca121bf9d92f59b1850409463314112b4` |
| `neo_klpga_shot_source/derived_analysis/player_product_data.json` | The exact data blob embedded in the HTML above (geometry + shots + content), kept standalone for inspection/reuse. | 175093 | `dd8e00affe43a41aaa9fc2ece029e182e325fbd193471cafd4e04ed55b9e9eb8` |
| `neo_klpga_shot_source/derived_analysis/player_deliverables_data.json` | Intermediate: per-player reachability/ability/imperfect-golf cases pulled from already-verified source files. | 25639 | `f43f868d43eb49a50dd3b092736551421e8f7e9bd32ba17afa2cabe56670bf0a` |
| `neo_klpga_shot_source/derived_analysis/build_player_product.py` | Reproduction script: assembles player_product_data.json (geometry, shots, hand-authored Korean strategy content, field stats). Re-run anytime source reports change. | 14203 | `cb2111a725a75da611e9e5cef93e20ce70574e0e3659b03099f9f160997d6587` |
| `neo_klpga_shot_source/derived_analysis/build_player_deliverables_data.py` | Reproduction script: assembles player_deliverables_data.json from the already-committed Hole1/Hole12 JSON + tournament-wide CSV. | 6158 | `8fd90e6867873a608047017daabf19b74fe25b4afd80f5945366be4fa1b51ffd` |
| `neo_klpga_shot_source/derived_analysis/PLAYER_PRODUCT_RED_TEAM.md` | Q1–Q7 red-team answers per player + cross-player differentiation check. | 5838 | `5b56bc42e7ee2e1a6c6ef45eaa2ff809bd9a2448b727a4ab7dff42fc351b1c69` |
| `neo_klpga_shot_source/derived_analysis/PLAYER_DELIVERABLES_EXPORT_MANIFEST.md` | This file. | (self) | (self) |

Images the product references (already committed earlier this project, unchanged):
`neo_klpga_shot_source/hole_images/hole_1.png`, `neo_klpga_shot_source/hole_images/hole_12.png` (both 650×433, real KLPGA Shot Tracker images, already verified).

## 2. QA screenshots (visual proof, actually opened and reviewed, not just Playwright-PASS)

All in `neo_klpga_shot_source/derived_analysis/qa_screenshots/`:

| File | Player | Hole | Viewport | Bytes | SHA-256 (first 16) |
|---|---|---|---|---|---|
| haeran_h1_desktop.png | 유해란 | Hole 1 | 1440×900 | 258833 | 6345bca76cde9b29 |
| haeran_h1_mobile.png | 유해란 | Hole 1 | 390×844 | 155014 | 32f4b2095895a161 |
| haeran_h12_desktop.png | 유해란 | Hole 12 | 1440×900 | 259524 | 1265ec111a008a8e |
| haeran_h12_mobile.png | 유해란 | Hole 12 | 390×844 | 154429 | d365b35327981a8e |
| haeran_h12_desktop_evidence.png | 유해란 | Hole 12 | 1440×1400 (evidence expanded) | 310262 | 438bab45ca296448 |
| jaeyoon_h1_desktop.png | 이재윤 | Hole 1 | 1440×900 | 245576 | 51239e82a108d0bd |
| jaeyoon_h1_mobile.png | 이재윤 | Hole 1 | 390×844 | 140299 | 225c29c7de962695 |
| jaeyoon_h12_desktop.png | 이재윤 | Hole 12 | 1440×900 | 239644 | 46c808d41f6b16d8 |
| jaeyoon_h12_mobile.png | 이재윤 | Hole 12 | 390×844 | 137051 | 1f394ae7d335dd11 |
| seohyun_h1_desktop.png | 박서현 | Hole 1 | 1440×900 | 241042 | 08dd1e890539fc58 |
| seohyun_h1_mobile.png | 박서현 | Hole 1 | 390×844 | 137747 | ed532d95bfcfcfa9 |
| seohyun_h12_desktop.png | 박서현 | Hole 12 | 1440×900 | 267796 | 133e6fec60291fdd |
| seohyun_h12_mobile.png | 박서현 | Hole 12 | 390×844 | 166274 | c0eb9458bbf4bc24 |

Each was opened and visually reviewed (not just a Playwright pass/fail). One real defect was found and fixed during review: on Hole 1, the TEE marker's floating text label visually collided with a player's real landing-dot cluster, making both unreadable. Fixed by dropping floating TEE/GREEN text labels in favor of small hollow-ring markers explained in the legend, drawn after player dots so they're never buried. Screenshots above are post-fix. A secondary, non-blocking cosmetic issue remains: when a player's real multi-round landings fall within a few pixels of each other (e.g. 박서현's Hole 1 R1/R2/R4), the auto-separation nudges them apart but very tight clusters can still touch slightly — real data, not a rendering error, and every point remains individually clickable.

## 3. Reproduction

```
cd neo_klpga_shot_source/derived_analysis
python3 build_player_deliverables_data.py   # -> player_deliverables_data.json
python3 build_player_product.py             # -> player_product_data.json
# then re-inject player_product_data.json into artifact_data/player_product.html
# (see the injection snippet used this session, same pattern as hole1_map.html)
```
All three scripts only read already-committed files (`hole12_distance_calibrated_analysis.json`, `hole12_master_template.json`, `hole1_full_analysis.json`, `neo_hole1_records.csv`, `neo_player_event_shot_metrics.csv`, `players_RAW_READONLY.json`) — no network access, no RAW re-fetch.

## 4. Source files used (read-only, unmodified, already verified in earlier work on this branch)

- `NEO_HOLE12_MASTER_TEMPLATE.md`, `NEO_HOLE12_DISTANCE_CALIBRATED_REPORT.md`, `NEO_HOLE12_PIN_CORRECTED_REPORT.md`, `NEO_COURSE_IDENTITY_VERIFICATION.md`
- `NEO_HOLE1_FULL_ANALYSIS.md`
- `hole12_distance_calibrated_analysis.json`, `hole12_master_template.json`, `hole1_full_analysis.json`
- `neo_hole1_records.csv`, `neo_hole12_distance_calibrated_records.csv`, `neo_player_event_shot_metrics.csv`
- `players_RAW_READONLY.json`
- `artifact_data/hole12_map_final.html` (source of H12 pixel geometry + DATA3), `artifact_data/hole1_DATA.json` / `hole1_DATA3.json` (H1 equivalents)

None of these were modified by this task. No new RAW was fetched or added to git.

## 5. Recommended D: destination (for local Codex, not executed by this session)

```
D:\NEO_DATA_ROOT\tournaments\2026100005\artifact\player_product\
  player_product.html
  hole_1.png
  hole_12.png
  player_product_data.json

D:\NEO_DATA_ROOT\tournaments\2026100005\reports\
  PLAYER_PRODUCT_RED_TEAM.md
  PLAYER_DELIVERABLES_EXPORT_MANIFEST.md

D:\NEO_DATA_ROOT\tournaments\2026100005\derived\
  player_deliverables_data.json
  build_player_product.py
  build_player_deliverables_data.py

D:\NEO_DATA_ROOT\tournaments\2026100005\qa\player_product\
  (all 13 files from qa_screenshots/)
```
This mirrors the existing `raw/normalized/derived/pin/course/validation/reports/artifact/manifest` structure from the earlier D: inventory request (that request itself was never executed by this cloud session — no D:\ access here, confirmed).

## 6. Git

Commit and push status reported separately at the end of this turn (see chat reply) — this manifest is written assuming that commit has landed; if it has not, treat "Git commit" in the final report as authoritative over this line.
