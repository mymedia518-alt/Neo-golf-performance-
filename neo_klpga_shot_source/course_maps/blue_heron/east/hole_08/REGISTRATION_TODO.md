# H8 registration: KLPGA coordinate map ↔ Blue Heron official visual map

**Status: not started. Blocked on acquiring `visual.png` / `tip.png` (see `../../../../fetch_h8_official_assets.py`).**

## Why this is a separate problem from Phase 1

Phase 1 already registered KLPGA Shot Tracker `(pp_x, pp_y)` onto `hole_images/hole_8.png`
(650×433, PASS — `derived_analysis/H8_coordinate_alignment_validation.json`). That transform
is specific to that one image. The Blue Heron official `visual.png` is a **different
illustration from a different system** (different artist/pipeline, different resolution —
same-family assets run 527×704), so the Phase 1 transform cannot be assumed to carry over.
**Do not scale Shot Tracker points onto `visual.png` by width/height ratio alone.**

## What to actually do once both PNGs exist

1. Open `hole_8.png` (coordinate-validated) and `visual.png` (official) side by side.
2. Identify shared real-world landmarks visible in **both** images — only ones that are
   actually present in both, nothing assumed:
   - TEE box position
   - FAIRWAY outline shape (bends/doglegs)
   - GREEN outline + its position relative to the fairway
   - BUNKER positions (count and rough location)
   - WATER/hazard shape and position (Phase 1 already shows a lake right of the fairway
     approaching the green on `hole_8.png` — check whether `visual.png` shows the same
     water body in the same relative position)
3. For each shared landmark, record its pixel coordinate in **both** images — this is a
   manual correspondence table, not a formula.
4. Only once ≥4 well-distributed correspondence points exist, fit a transform (affine or
   homography, whichever the residual error supports) from `hole_8.png` pixel space to
   `visual.png` pixel space. Check the residual at each point; do not accept a transform
   that only "looks okay" visually without a numeric residual check.
5. Explicitly check for rotation — the two illustrations are not guaranteed to share the
   same up/down or tee-to-green screen direction. Confirm orientation from the landmarks
   themselves, not by assuming they match.
6. Only after that transform is fit and residual-checked does it become valid to project
   Shot Tracker shot points onto `visual.png`.

## What NOT to do

- Do not assume `visual.png`'s aspect ratio matches `hole_8.png`'s.
- Do not assume tee-to-green runs in the same screen direction in both images.
- Do not invent landmark positions for elements not clearly visible in `visual.png`.
- Do not skip the residual check and eyeball it as "close enough".
