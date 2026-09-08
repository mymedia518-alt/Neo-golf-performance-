# Probability-unit validation fix

The OK Open forecast stores `win_pct`, `top5_pct`, `top10_pct`, and
`top20_pct` as percentages. A value below `1.0` remains a valid percentage;
for example, `0.298` means `0.298%`, not `29.8%`.

The validator now uses field names to determine units:

- Explicit `*_pct` fields are read as percentages without magnitude-based conversion.
- Legacy fields such as `win_probability` may still use fractions in `[0, 1]`.

This changes validation only. It does not alter the frozen forecast or any
simulation output.
