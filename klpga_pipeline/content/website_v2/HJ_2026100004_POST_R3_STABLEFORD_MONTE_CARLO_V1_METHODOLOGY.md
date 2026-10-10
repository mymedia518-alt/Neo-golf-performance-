# HJ 2026100004 POST-R3 Stableford Monte Carlo V1 -- Methodology

R1+R2+R3 are real, official KLPGA results (not simulated); no
additional cut is applied after R2 for this tournament format, so
the same 61 real survivors continue through R4. Only round 4 is
drawn, per-player, from the SAME per-hole outcome distribution
(stableford_monte_carlo_experiment.load_field) used by the PRE-event
and POST-R2 runs -- their skill model is not re-fit on R1/R2/R3
results. Final score = real R1+R2+R3 total + simulated R4.
Seed=20261007, n_sims=60000, cross-seed checks at (20261008, 777).
No cut-line is simulated -- all 61 players are already through by
construction. Public output on FR/HOME is TOP20/TOP10/TOP5/우승
(updated 2026-10-10); PRE/R1/R2/R3 never show TOP20 or TOP5. SG is
never rendered publicly, on any page.
