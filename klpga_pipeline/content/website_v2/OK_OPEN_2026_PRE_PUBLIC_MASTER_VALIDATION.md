# OK Open 2026 PRE public data-layer validation

Generated 2026-08-31 from official pre-tournament sources. Website generation is intentionally **not run**.

## Coverage

- Entrants: 120; canonical identities: 120; duplicate/unresolved: 0/0
- Current official name/status: 120/120
- Current official sponsor/affiliation: 97/120 (the official profile has no affiliation for 23 entrants; values remain NULL)
- Official K-RANKING (week 2026-W35): 119/120 (one entrant is not present in the published ranking and remains NULL)
- Validated PRE SG Total rank: 117/120 (recent5 historical arithmetic-mean scope; insufficient history remains NULL)
- Existing M4 PRE WIN probability: 120/120; range and normalization validated
- TOP20/TOP10/TOP5: not emitted by the current model; deliberately NULL
- `neo_pre_rank`: not emitted; independent methodology approval is still required

## Official source handling

Current identity/status/affiliation uses `https://klpga.co.kr/web/profile/mainRecord?playerCode=...` with UTF-8 byte decoding. Ranking uses the public weekly K-RANKING form at `https://k-rankings.klpga.co.kr/allplayer.jsp` (`Rank_week=202635`). Historical names are retained only in provenance.

Kim Min-sol audit (`player_id=10725`): historical `김민솔 0606(A)`; current official name `김민솔`; status `정회원`; affiliation `두산건설 We've`. The historical amateur marker is not used for current identity.

Two current official profiles retain their official disambiguation/status suffix (`박서진 0804(A)`, `오수민 0809(A)`); these are not regex-cleaned and are explicitly sourced from the current profile response.

## Artifacts

- `OK_OPEN_2026_CURRENT_PLAYER_MASTER.json` — single 120-entrant identity/public-data master; includes field-level provenance.
- `OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json` — official weekly K-RANKING join.
- `OK_OPEN_2026_PRE_WIN_FORECAST.json` — immutable WIN-only M4 forecast export, cutoff 2026-09-04 KST.
- `OK_OPEN_2026_PRE_SG_TOTAL_RANK.json` — validated historical SG Total field rank (arithmetic mean of completed rounds, never summed).
- `OK_OPEN_2026_NEO_PRE_RANKING_EVIDENCE.json` — evidence export; no invented NEO rank.

No protected historical evidence, database, model, AUTO OPS, production docs, or Website 2.0 files were modified.
