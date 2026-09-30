# Entry List Validation Report — gameCode 2026100005 (제26회 하이트진로 챔피언십)

Source: `raw/2026100005/entry_list.html` and `normalized/2026100005/ENTRY_SNAPSHOT.json`,
both committed on `reader/2026100005` (commit `19f5aebe095e`) by the NEO Sync
pipeline. Every check below was independently re-derived directly from the raw
HTML and the structured snapshot in this session — not merely copied from
`neo_reader.validate`'s own PASS output — per this project's "no PASS without
evidence" rule.

## Checks performed and results

| Check | Result | Evidence |
|---|---|---|
| Row count vs. page's own declared total | **PASS** | Page declares "총 참가자" = 108. `ENTRY_SNAPSHOT.json` has exactly 108 records. |
| Category breakdown reconciles | **PASS** | Page declares 자격자=100, 추천자=6, 초청자=2 (sum 108). Recomputed directly from the 108 records: 자격자=100, 추천자=6, 초청자=2 — exact match. |
| Duplicate player_code | **PASS (none found)** | Recomputed from records independently: 0 duplicates. |
| Duplicate player_name | **PASS (none found)** | Recomputed from records independently: 0 duplicates. |
| Every record has player_code and player_name | **PASS** | 0 of 108 records missing either field. |
| Nationality field populated | **PASS** | 105 KOR, 1 CHN, 1 THA, 1 USA — all 108 populated, none blank. |
| qualification_reason present where the source page provides one | **PASS, explained** | 8 of 108 records have no qualification_reason: exactly the 2 초청자 (박성현, 유해란) and 6 추천자 (성아진, 양아연, 에리카 윤 스미스, 이수민, 임선아, 조하리) — the source page itself never renders a reason for these two categories, only for 자격자. Count matches page's declared 추천자+초청자 total (8) exactly, so this is the page's own real structure, not a parsing gap. |
| Independent second-parse cross-check (parser-bug guard) | **PASS** | The raw page renders the field twice: a desktop `<table class="table-blue">` (108 tbody rows — the one the pipeline's parser used) and a second, mobile-view table (111 tbody rows = the same 108 entrants + 3 inline category-divider rows, e.g. `"\| 자격자 : 100명"`). Re-parsed both independently with a from-scratch BeautifulSoup pass in this session: the same 108 names appear in both, confirming the parser picked the correct table and dropped nothing. |

**Overall: PASS.** No fabrication was needed for any of the above — every value
either came directly from the official page or was arithmetic performed on
values that did.

## Known limitation (real infrastructure gap, not a data-quality issue)

`ENTRY_SNAPSHOT.json` also reports `matched_count: 0, unmatched_count: 108`
against `player_master`. This is **not** a parsing or matching-logic bug —
confirmed by reading `klpga.collectors.entry_list.match_entries_to_player_master`
(exact-match on `player_master.player_id`, no fuzzy logic) and its caller in
`neo_reader/sync.py`. The `player_master` table lives in
`klpga_pipeline/data/klpga.sqlite`, which is `.gitignore`d
(`klpga_pipeline/.gitignore:5`) and was never committed to this repository —
confirmed via `git log --all -- klpga_pipeline/data/klpga.sqlite` (no history)
and a filesystem search (no copy exists anywhere in this sandbox). The GitHub
Actions runner that ran NEO Sync also starts from a fresh checkout with no such
file, so `run_sync` created a brand-new, empty sqlite database before matching
— every one of the 108 entrants is correctly reported unmatched against an
empty table; this is not evidence any of them are actually new/unknown
players. Many of the 108 player_codes here (e.g. 9702, 8380, 10097) are the
same IDs already referenced elsewhere in this repository's own historical
build scripts and content files, so the true `player_master` (wherever its
real, populated copy lives) almost certainly already knows most of them.

**This blocks**: any feature that needs to join these 108 entrants against
historical per-player data held only in that warehouse database — e.g. a
win-probability model needing prior-event counts/recent-form priors per
player, or player-history links. It does **not** block anything computed
directly from official, already-collected sources for this tournament itself
(entry list structure above; K-Ranking, which the sync already validated
PASS with zero database dependency).

**Not fixable by code alone from this sandbox or from the GitHub Actions
runner**: reproducing `player_master` requires either (a) the actual
`klpga.sqlite` file from wherever the project's historical collection work
has been persisting it (not present in this repository or this environment),
or (b) rebuilding it from scratch by re-collecting every prior season's
tournament data — a large, separate undertaking outside this sync's scope.
