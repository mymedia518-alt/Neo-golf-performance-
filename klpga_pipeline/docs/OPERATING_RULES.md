# Operating Rules — Stage Version Preservation (PRE / R1 / R2 / R3 / FR)

**Status: adopted 2026-09-17.** This document is the durable, repo-wide
statement of a rule this branch's own work has already been following in
practice (see `klpga_pipeline/content/website_v2/archive/2026090002/pre/`
and `klpga_pipeline/scripts/145_archive_hana_pre_snapshot.py`): every
public-facing tournament stage must be snapshotted before the pipeline
moves on to the next stage, and once snapshotted, that stage's materials
are permanent.

## The five stages

A tournament's public site progresses through, at most, five stages
(not every tournament uses all five — see `docs/tournaments/2026/<game_code>/`
for which stages a given tournament actually built):

| Stage | Meaning |
|---|---|
| `PRE` | Pre-tournament analysis, published before Round 1 tees off |
| `R1` | Round 1 in-progress/complete public page |
| `R2` | Round 2 in-progress/complete public page |
| `R3` | Round 3 in-progress/complete public page |
| `FR` | Final-round-in-progress public page (used by tournaments whose FINAL
        recap is a distinct, later artifact from the live final-round page —
        e.g. `2026090003`) |

`FINAL` (the post-tournament recap/results page) is a separate,
already-governed artifact (see `klpga_pipeline/docs/PREDICTION_ARCHIVE.md`
for the prediction side of that boundary) and is out of scope for this
document.

## The rule

1. **Snapshot before advancing.** Before a tournament's pipeline is
   allowed to move from stage `N` to stage `N+1`, the raw / input /
   output / verification materials that produced stage `N`'s live public
   page must be archived under
   `klpga_pipeline/content/website_v2/archive/<game_code>/<stage>/`,
   with a `<STAGE>_ARCHIVE_MANIFEST_V1.json` recording, at minimum: the
   base commit the snapshot is pinned to, each archived file's sha256,
   the tournament's game_code, and the stage's key published facts (e.g.
   player-field size, counts of any "데이터 부족" rows, and any
   individually-named player facts the operator specifically flagged for
   verification).

2. **Archives are write-once.** Once a file exists under
   `archive/<game_code>/<stage>/`, no later pipeline run — for that
   stage, or for any later stage of the same tournament — may overwrite
   it. This is enforced structurally, not just by convention: the
   archiving script itself hard-asserts and refuses to run if any target
   path already exists (see `145_archive_hana_pre_snapshot.py`'s
   `assert not archive_path.exists()` guard), and the corresponding test
   suite independently re-verifies, for every archived file, that its
   current on-disk sha256 still matches the sha256 recorded in its
   stage's manifest (see `klpga_pipeline/tests/
   test_hana_pre_archive_immutability.py`).

3. **A manifest may be amended, never rewritten.** A manifest's already
   -recorded fields (base commit, per-file sha256, existing summary
   values) are never edited or removed after the fact. A later, narrowly
   -scoped, explicitly-provenanced addition (e.g. recording a
   previously-omitted summary count) may add new fields to the same
   manifest file, but must never change or delete anything already
   written, and the amendment's own script must independently
   re-derive and hard-assert every new value it adds before writing —
   consistent with this repo's standing "never estimate without official
   basis" and "purely additive" evidence discipline.

4. **R1's own snapshot never reaches back into PRE.** Building/archiving
   stage `R1` (or any later stage) must read only from that stage's own
   raw/input/output/verification sources. It must never read from, copy
   over, or regenerate anything under a prior stage's
   `archive/<game_code>/<stage>/` directory. Each stage directory is
   independently pinned to its own base commit.

5. **Purely additive across the whole tree.** As with every other
   evidence-handling rule already in force on this branch: archiving a
   stage never modifies, in place, anything outside its own new
   `archive/<game_code>/<stage>/` subtree — not `klpga.sqlite`, not
   `docs/assets/neo.css`, not another tournament's pages, not a KB FINAL
   page, and not a prior stage's already-archived files.
