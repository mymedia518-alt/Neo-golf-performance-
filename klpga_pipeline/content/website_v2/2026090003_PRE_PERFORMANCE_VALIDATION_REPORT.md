# KB금융 골든라이프 챔피언십 2026 — Pre-tournament Performance Validation

- Official field size: **120**
- Identity matches: **120/120**; duplicates: 0; unresolved: 0
- Data cutoff: **2026-09-10T00:00:00+09:00 Asia/Seoul**; future KB금융 골든라이프 챔피언십 data excluded.
- SG coverage: {'ENTRY + SUFFICIENT SG': 107, 'ENTRY + LIMITED SG': 8, 'ENTRY + NO OFFICIAL SG': 5}

This is performance validation, not a forecast or player pick. No composite index or winner prediction is produced. Window disagreement and sample bands are retained per entrant in the frozen JSON snapshot.

## Frozen provenance

Entry source: `https://klpga.co.kr/web/tourInfo/entry?gameCode=2026090003`; entry snapshot SHA-256: `573831b519e50900c1e62b2785330c0d3246266a18c9f7d113be9411bf11f4b7`. Warehouse: `historical_sg_warehouse.json`; calculation: `ok_open_pre_performance_v1`.

## Highlight groups

Players are grouped only when the frozen evidence state supports the label; complete per-player values and confidence are in the JSON snapshot.

### CURRENT HIGH LEVEL

강가율, 고은혜, 고지우, 고지원, 구래현, 김가희2, 김나현2, 김리안, 김민별, 김민선7, 김민솔, 김민주, 김새로미, 김소정, 김수지, 김시현, 김아현, 김우정, 김재희, 김지수

### RISING — SUPPORTED

강가율, 김나현2, 김민주, 김새로미, 김소정, 김수지, 김하은2, 김희지, 노승희, 박보겸, 박예지, 배소현, 서교림, 서어진, 양효리, 유서연2, 유지나, 유현조, 윤수아, 윤화영

### RISING — BUT WINDOW CONFLICT

강가율, 고은혜, 고지우, 고지원, 구래현, 김가희2, 김나현2, 김리안, 김민별, 김민선7, 김민솔, 김민주, 김새로미, 김소정, 김시현, 김아현, 김우정, 김재희, 김하은2, 김효문

### HIGH CONSISTENCY

강가율, 고은혜, 고지우, 고지원, 구래현, 김가희2, 김나현2, 김리안, 김민별, 김민선7, 김민솔, 김민주, 김새로미, 김소정, 김수지, 김시현, 김우정, 김재희, 김지수, 김하은2

### HIGH VARIANCE

김아현, 김지윤2, 노원경, 양효리, 이세영, 이슬기2, 이지민, 조정민

### APPROACH-LED

고지원, 김리안, 김민선7, 김민주, 김새로미, 김수지, 김시현, 김우정, 김지수, 김하은2, 노승희, 박민지, 박보겸, 박혜준, 방신실, 배소현, 서교림, 서어진, 성유진, 양서후

### PUTTING-LED

강가율, 고은혜, 김민별, 김소정, 김재희, 김지영2, 김지윤2, 김효문, 김희지, 마다솜, 마서영, 박단유, 박서현, 성은정, 손예빈, 안선주, 안지현, 양효리, 유서연2, 윤화영

### LIMITED DATA

김지영2, 리 슈잉, 양서후, 유다겸(I), 이윤서, 조은채, 허윤서, 전인지, 구민지 0706(A), 김연서, 박조은 0806(A), 윤다감 0907(A), 정민서

## Limitations

The official entry page exposes listed entrants and qualification fields but no explicit withdrawal marker at retrieval. SG history is available only where official KLPGA SG rows exist; NULL is preserved.
