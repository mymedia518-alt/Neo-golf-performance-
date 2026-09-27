# NEO Derived-Value Dependency Graph V1

**Mission V10 (2026-09-25), playerCode=10097 only.** For every DERIVED field whose provenance entry declares real `depends_on` paths, this is the adjacency list of what it was computed from -- a plain data structure (a graph), not a rendered chart/diagram (this mission explicitly forbids building UI or charts). Only DERIVED entries that named their real inputs are listed; most DERIVED entries in this codebase are simple aggregations (a mean, a count, an argmax) over raw rows rather than over another already-classified JSON field, so they have no `depends_on` edge to show here -- their reason text still states the formula in prose (see the provenance report).

## Player History

- `career_evolution.avg_app.deltas[].delta`
  - depends on `career_evolution.avg_app.series[].value`
- `career_evolution.avg_arg.deltas[].delta`
  - depends on `career_evolution.avg_arg.series[].value`
- `career_evolution.avg_ott.deltas[].delta`
  - depends on `career_evolution.avg_ott.series[].value`
- `career_evolution.avg_putt.deltas[].delta`
  - depends on `career_evolution.avg_putt.series[].value`
- `career_evolution.avg_total.deltas[].delta`
  - depends on `career_evolution.avg_total.series[].value`
- `career_form_story[].delta_vs_career_average`
  - depends on `career_rolling_trend.career_average_sg_total`
- `career_heartbeat.career_average_sg_total`
  - depends on `career_rolling_trend.career_average_sg_total`
- `career_rolling_trend.career_average_sg_total`
  - depends on `tournament_history[].sg_total`
- `career_rolling_trend.peak_window.delta_vs_career_average`
  - depends on `career_rolling_trend.peak_window.moving_average_sg_total`
  - depends on `career_rolling_trend.career_average_sg_total`
- `career_rolling_trend.recovery_window.delta_vs_career_average`
  - depends on `career_rolling_trend.recovery_window.moving_average_sg_total`
  - depends on `career_rolling_trend.career_average_sg_total`
- `career_rolling_trend.recovery_window.delta_vs_slump`
  - depends on `career_rolling_trend.recovery_window.moving_average_sg_total`
  - depends on `career_rolling_trend.slump_window.moving_average_sg_total`
- `career_rolling_trend.series[].moving_average_sg_total`
  - depends on `tournament_history[].sg_total`
- `career_rolling_trend.series[].self_percentile`
  - depends on `career_rolling_trend.series[].moving_average_sg_total`
- `career_rolling_trend.slump_window.delta_vs_career_average`
  - depends on `career_rolling_trend.slump_window.moving_average_sg_total`
  - depends on `career_rolling_trend.career_average_sg_total`
- `current_form_indicator.delta`
  - depends on `current_form_indicator.last5_avg_sg_total`
  - depends on `current_form_indicator.prev5_avg_sg_total`
- `current_form_indicator.last5_avg_sg_total`
  - depends on `recent_form_10[].sg_total`
- `current_form_indicator.prev5_avg_sg_total`
  - depends on `recent_form_10[].sg_total`
- `current_form_indicator.trend`
  - depends on `current_form_indicator.delta`
- `current_skill_vs_career.components[].delta_vs_career_average`
  - depends on `current_skill_vs_career.components[].current_value`
  - depends on `current_skill_vs_career.components[].career_average`
- `current_vs_career.career_average_sg_total`
  - depends on `tournament_history[].sg_total`
- `current_vs_career.current_season_sg_total`
  - depends on `career_overview.season_rows[].sg_total`
- `current_vs_career.delta_vs_career_average`
  - depends on `current_vs_career.current_season_sg_total`
  - depends on `current_vs_career.career_average_sg_total`
- `player_dna_radar[].axes[].delta_vs_career_mean`
  - depends on `player_dna_radar[].axes[].percentile`
  - depends on `player_dna_growth.<axis>.career_mean_percentile`
- `player_identity.consistency_component`
  - depends on `career_dna.most_consistent_component`
- `player_identity.primary_component`
  - depends on `career_dna.career_foundation`
- `player_identity.primary_share_pct`
  - depends on `career_dna.career_foundation_share_pct`
- `player_identity.primary_type`
  - depends on `career_dna.career_foundation`
- `player_identity.winning_note`
  - depends on `career_dna.winning_foundation`
  - depends on `career_dna.winning_foundation_share_pct`
- `status.source_conflicts`
  - depends on `reconciliation.status`
  - depends on `reconciliation.conflicts_detected`
  - depends on `reconciliation.missing`
- `why_now.arrows[].delta`
  - depends on `current_skill_vs_career.components[].delta_vs_career_average`
- `why_now.lead_component`
  - depends on `current_skill_vs_career.components[].delta_vs_career_average`
- `why_now.sentence`
  - depends on `why_now.lead_component`
  - depends on `why_now.lead_delta`

## Player Intelligence Report

No DERIVED entry in this report declares a `depends_on` edge onto another classified field.

