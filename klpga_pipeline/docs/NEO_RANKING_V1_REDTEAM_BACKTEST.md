# NEO Ranking V1 RED TEAM & Historical Backtest

> 판정: **REJECT** — V1은 validation-only heuristic이며 historical K-Ranking baseline 부재, 약한 순위/결과 상관, target-field archival limitation 때문에 PUBLIC/BETA 승격 근거가 없다.

## Frozen formula

- Model: `neo-ranking-validation-v1`; weights were not tuned during this audit.
- Features: recent5 SG 0.35, recent10 SG 0.25, long-term SG 0.25, consistency (`-volatility`) 0.10, sample reliability 0.05.
- Normalization: each target cohort's eligible players within each SG feature are population z-scored; zero dispersion maps to 0.
- Recent windows: strictly the latest 5/10 prior events whose start dates precede the target; long-term and volatility use every prior event.
- Eligibility: at least 10 prior validated SG events. Missing SG is never imputed; ineligible players receive no rank.
- Sample reliability: `min(prior_event_count / 20, 1) * 0.05`.
- Cut/WD/DQ: prior official SG remains an observed feature when present; no zero is inserted. WD/DQ targets are excluded from finish correlation. Made-cut evaluation uses the DB's confirmed flag.
- Recency: event-date ordering and fixed 5/10 windows; no exponential decay.

## Backtest coverage

- 82 tournaments; 7830 player-event observations; 211 players.
- Every feature date is strictly earlier than its target start date.
- Historical K-Ranking: NOT EVALUABLE. Current W35 ranking was rejected as a historical baseline because it would leak future information.

## Performance

- Mean Spearman, NEO rank vs finish: 0.4813
- Mean Spearman, NEO score vs subsequent SG Total: 0.4202
- Top10 precision / recall: 0.3366 / 0.3366
- Top20 precision / recall: 0.4902 / 0.4902
- Made-cut AUC: 0.7120
- K-Ranking metrics and incremental predictive value: N/A (point-in-time snapshots unavailable).

## Extreme current deltas

- **서지은** K 119 / NEO 32 / Δ +87 / score 0.504559; SG n=18, recent n=5; contributions: recent_5_sg=+0.1376, recent_10_sg=+0.0708, long_term_sg=+0.1379, consistency=+0.1131, sample_reliability=+0.0450; main driver: long_term_sg; recent: 2026040005:- CUT, 2025100005:- CUT, 2025090002:9, 2025090001:61, 2025080003:84 CUT.
- **정슬기** K 117 / NEO 58 / Δ +59 / score -0.000319; SG n=46, recent n=5; contributions: recent_5_sg=+0.0067, recent_10_sg=+0.0969, long_term_sg=-0.1406, consistency=-0.0133, sample_reliability=+0.0500; main driver: long_term_sg; recent: 2026080004:6, 2026050003:74 CUT, 2025080003:18, 2024100011:78 CUT, 2024100010:53.
- **이주미** K 113 / NEO 55 / Δ +58 / score 0.030770; SG n=69, recent n=5; contributions: recent_5_sg=+0.0502, recent_10_sg=-0.0338, long_term_sg=-0.0782, consistency=+0.0426, sample_reliability=+0.0500; main driver: long_term_sg; recent: 2026080001:6 CUT, 2026080002:73 CUT, 2026080003:50, 2026080004:43, 2026070001:90 CUT.
- **홍지원** K 83 / NEO 33 / Δ +50 / score 0.434029; SG n=95, recent n=5; contributions: recent_5_sg=+0.2267, recent_10_sg=+0.0799, long_term_sg=-0.0050, consistency=+0.0824, sample_reliability=+0.0500; main driver: recent_5_sg; recent: 2026080001:75 CUT, 2026080002:25, 2026080003:10, 2026080004:23, 2026070001:54.
- **고지우** K 15 / NEO 64 / Δ -49 / score -0.082379; SG n=89, recent n=5; contributions: recent_5_sg=-0.1463, recent_10_sg=-0.0055, long_term_sg=+0.0731, consistency=-0.0537, sample_reliability=+0.0500; main driver: recent_5_sg; recent: 2026080001:52 CUT, 2026080002:4, 2026080003:68, 2026080004:116 CUT, 2026070001:71 CUT.
- **홍정민** K 8 / NEO 52 / Δ -44 / score 0.076906; SG n=75, recent n=5; contributions: recent_5_sg=-0.2711, recent_10_sg=+0.0681, long_term_sg=+0.2662, consistency=-0.0363, sample_reliability=+0.0500; main driver: recent_5_sg; recent: 2026080001:- CUT, 2026080002:- CUT, 2026080003:- CUT, 2026070001:- CUT, 2026070002:83 CUT.
- **고지원** K 11 / NEO 40 / Δ -29 / score 0.332940; SG n=79, recent n=5; contributions: recent_5_sg=+0.1428, recent_10_sg=+0.1178, long_term_sg=+0.0353, consistency=-0.0129, sample_reliability=+0.0500; main driver: recent_5_sg; recent: 2026080001:6 CUT, 2026080002:15, 2026080003:50, 2026080004:82 CUT, 2026070001:7.

## Hard validation

- future leakage: 0
- duplicate event-player: 0
- invalid player mapping: 0
- insufficient sample forcibly ranked: 0
- reproducibility / deterministic output: True / True

## Model defects

1. V1 weights are heuristic and correlated recent5/recent10/long-term windows double-count related SG signal.
2. Cohort z-scores make a player's score depend on who else is present and are not calibrated across events.
3. Reliability is a positive bonus rather than uncertainty shrinkage; it can lift mediocre high-sample players.
4. Volatility is penalized symmetrically and may suppress genuinely improving players.
5. Historical field reconstruction comes from retained SG rows, not archived pre-event entry snapshots; unresolved/non-SG players reduce coverage.
6. Point-in-time historical K-Ranking snapshots are absent, preventing the required K-versus-NEO and incremental-value test.

No V2 weights were fitted or changed in this audit.
