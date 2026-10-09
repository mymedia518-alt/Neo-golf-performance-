# HJ 2026100004 POST-R2 Stableford Monte Carlo V1 -- Methodology

R1+R2 are real, official KLPGA results (not simulated); the official
cut (top 60 and ties) has already been applied by KLPGA, yielding
61 real survivors, 46 missed-cut, 1 WD. Only rounds 3+4 are drawn,
per-player, from the SAME per-hole outcome distribution
(stableford_monte_carlo_experiment.load_field) used by the PRE-event
V1 run -- their skill model is not re-fit on R1/R2 results. Final
score = real R1+R2 total + simulated R3 + simulated R4. Seed=20261007,
n_sims=60000, cross-seed checks at (20261008, 777).
No cut-line is simulated -- all 61 players are already through by
construction. Public output is limited to 컷 통과(always 100% here,
kept for schema parity)/TOP20/TOP10/우승 -- Top5 and SG are never
rendered publicly.
