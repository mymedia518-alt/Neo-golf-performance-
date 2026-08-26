# NEO Data Rights Matrix — Mission 5 (framework only, no evidence gathered)

**Status: framework skeleton only, 2026-08-26 (Round 2). Every
substantive cell is `UNKNOWN`.** This document could not be populated
with real evidence — this session has no network access to
`klpga.co.kr`/`data.klpga.co.kr` (re-confirmed immediately before this
round: a fresh `curl` to both hosts still returns `403` at the egress
proxy). Mission 5 requires quoting actual Terms of Use, robots.txt,
copyright-notice, and Data Center clause text with a retrieval date —
none of that could be read this session. **Nothing below is a legal
conclusion, and nothing below should be treated as if the real terms
were checked.**

This exists so the next DevTools round has a ready-made table to fill
in, and so the four questions the brief requires are asked in the
right shape even before evidence exists.

---

## The four questions, kept separate (per instruction: A does not prove B/C/D)

| # | Question | Answer |
|---|---|---|
| A | Can a human publicly VIEW the data? | **Provisionally yes** — the user's own Round-1 DevTools session viewed `loadLocationRecord` responses through the ordinary public site UI, no login observed. This is the *only* one of the four questions this project has any direct evidence for. |
| B | Can software automatically RETRIEVE it? | **UNKNOWN** — no robots.txt has ever been read for either host, by anyone, at any point in this project's history (see `docs/SITE_STRUCTURE_TODO.md` §4). Viewability (A) is not evidence for this. |
| C | Can NEO STORE factual values in its own database? | **UNKNOWN** — depends on ToS/database-rights language never read. |
| D | Can NEO commercially publish DERIVED analysis based on those facts? | **UNKNOWN** — depends on ToS language never read, and on how Korean database-protection law treats a transformed/derived output, which this session has no ability to research from primary sources. |

---

## Evidence log

**Empty.** No official document was retrieved this session. This table
exists to be filled in during the next live round — every row must
carry an official URL, the document/page title as it appears, the
retrieval date, and the specific clause/article quoted (short passages
only, per instruction).

| Official URL | Document/page title | Retrieval date | Relevant clause (short quote) | Notes |
|---|---|---|---|---|
| *(not yet retrieved)* | Terms of Use (이용약관) | — | — | Concrete next step: visit directly during the next DevTools session |
| *(not yet retrieved)* | Copyright policy (저작권) | — | — | Same |
| *(not yet retrieved)* | `klpga.co.kr/robots.txt` | — | — | Same — a two-second check, highest value-per-effort item in this whole matrix |
| *(not yet retrieved)* | `data.klpga.co.kr/robots.txt` | — | — | Same |
| *(not yet retrieved)* | Data Center (데이터센터) terms/notices, if separately published | — | — | `data.klpga.co.kr` may carry its own terms distinct from the main site's |
| *(not yet retrieved)* | Any published API/data-use notice | — | — | No evidence one exists; check for it rather than assuming absence |
| *(not yet retrieved)* | Photo/image usage rules | — | — | Relevant only if NEO ever displays official KLPGA imagery — out of scope for the current text-only site, flagged for completeness |

---

## Rights matrix — planned NEO uses × GREEN/YELLOW/RED/UNKNOWN

Per instruction, classification is evidence-based, not a general
prudence guess — since no evidence exists yet, **every row is
`UNKNOWN`**. The "provisional prior" column carries forward the
reasoning already published in `docs/KLPGA_OFFICIAL_DATA_MAP.md`'s
Round-1 legal-track section, so the next round has a working
hypothesis to confirm or overturn — it is explicitly *not* the same
thing as the official classification column.

| Planned NEO use | Official classification | Provisional prior (Round 1 reasoning, not evidence) |
|---|---|---|
| Displaying KLPGA tables verbatim (e.g. rendering the SG or distance-bucket tables as-is) | **UNKNOWN** | Likely closer to elevated risk — closest to wholesale reproduction of the source site's own presentation |
| Storing official raw statistics internally, never published | **UNKNOWN** | Likely lower exposure than publishing, but an automated-collection restriction in a ToS would apply regardless of whether the output is ever made public |
| Transforming statistics into NEO-derived metrics (Power-Control Tradeoff, DNA dimensions) | **UNKNOWN** | Likely lower risk than verbatim display, but "derived work" protection varies by jurisdiction; Korea's own Database Protection Act framework is specifically relevant here and has not been researched |
| Publishing NEO rankings/probabilities (what Prediction #001 already does) | **UNKNOWN** | Already in production; built from a transformation (a probability), the more defensible end of the spectrum in principle, but still ultimately sourced from official underlying data |
| Publishing selected supporting official statistics next to a prediction (e.g. "SG Total: 2.38") | **UNKNOWN** | Likely the most exposed use case short of verbatim display — close to direct redistribution of a specific official number |
| Publishing historical databases built from this data | **UNKNOWN** | Likely the highest-exposure use case — bulk redistribution as a database product, most likely to implicate both ToS redistribution clauses and database-rights law |
| Commercial subscription/API access built on this data | **UNKNOWN** | Cannot be assessed technically at all — a licensing/business conversation, not an engineering question |

---

## What would actually move a row out of UNKNOWN

Concretely, for the next DevTools round:

1. Open `klpga.co.kr/robots.txt` and `data.klpga.co.kr/robots.txt`
   directly — either has content or returns 404; both are informative,
   and both take seconds.
2. Find and open the site's 이용약관 (Terms of Use) and 저작권
   (Copyright) pages — usually linked in the site footer — and copy
   the relevant clauses (automated access, redistribution, commercial
   use, database rights) verbatim into the evidence log above.
3. Check specifically for a Data Center-specific notice, since
   `data.klpga.co.kr` was described in the prior audit as a separate
   product build-out from the main site and may carry its own terms.
4. Do not infer a policy from silence — if no explicit automated-access
   or redistribution clause is found, record that as "not found" (still
   informative — it changes the honest classification from `UNKNOWN`
   toward something more specific, but still isn't a green light on its
   own), not as an assumed absence of restriction.

---

*Numbers · Evidence · Oracle — Golf Intelligence. This is a risk-evidence
framework, not a legal conclusion. Research only — no database, model,
archive, prediction, or website change.*
