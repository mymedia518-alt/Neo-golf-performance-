# NEO Data Provenance Report V1

**Mission V10 (2026-09-25), playerCode=10097 only.** "Every number shown on NEO can always answer: 'Where did this come from?'" Generated directly from the live `_provenance_map()` in each builder (`scripts/generate_provenance_reports_v10.py`) -- never hand-maintained, so this table cannot drift out of sync with the code. Re-run that script after any provenance map change.

## The five labels

| Label | Meaning |
|---|---|
| **MEASURED** | A real, directly-collected raw data point. No arithmetic was applied to produce this exact value. |
| **DERIVED** | Computed via a deterministic formula/aggregation from one or more MEASURED (or other DERIVED) values. |
| **IMPUTED** | Estimated, interpolated, or defaulted to stand in for missing data. |
| **NOT_COLLECTED** | The pipeline is capable of having this data, but NEO has not ingested it for this case. |
| **NOT_AVAILABLE** | Not obtainable at all in this pipeline's current design/environment. |

## Methodology

- Classification is at the **JSON-path-schema level** (e.g. `tournament_history[].sg_total` covers all ~96 rows with one entry), not per literal value instance -- the one documented exception is `questions[].monitoring_protocol.current_reading` in the Player Intelligence report, where a real IMPUTED instance (id=q_win_blueprint) is disclosed in that entry's own reason text rather than given a separate schema path (see the Player Intelligence section below).
- Pure build/pipeline metadata (`schema_version`, `generated_at`, `scope_note`, `source_document`, and Player Intelligence's own methodology-description strings) is excluded: none of the 5 labels honestly describes a build timestamp or a schema tag.
- Two real governance gaps this audit surfaced -- kept **MEASURED** (a factual assertion, not a formula or a data gap) rather than invented as an unlisted 6th label, but named explicitly here and in every affected entry's own reason text:
  - `status.data_completeness` / `status.derived_metrics` (Player History) are fixed literal strings (`"PARTIAL"`/`"PASS"`) with no per-run check behind them -- they never vary regardless of the actual data state.
  - `coverage_matrix.rows` (Player History) is an entirely hand-authored table; its MEASURED/DERIVED/NOT_COLLECTED/BLOCKED cell values are asserted by whoever last edited the source file, never verified against a live presence-check of what this specific build run actually has.

## Player History (build_10097_player_history.py)

637 classified fields.

| Label | Count |
|---|---|
| MEASURED | 352 |
| DERIVED | 269 |
| IMPUTED | 0 |
| NOT_COLLECTED | 0 |
| NOT_AVAILABLE | 16 |

### `career_dna`

| Path | Label | Reason |
|---|---|---|
| `career_dna.career_foundation` | DERIVED | the SG component contributing the largest real share of her career SG Total sum |
| `career_dna.career_foundation_share_pct` | DERIVED | that component's real share of the career SG Total sum |
| `career_dna.fastest_growing_component` | DERIVED | the SG component with the largest first-to-last-season change |
| `career_dna.most_consistent_component` | DERIVED | the SG component with the lowest season-to-season stddev |
| `career_dna.most_volatile_component` | DERIVED | the SG component with the highest season-to-season stddev |
| `career_dna.winning_foundation` | DERIVED | the SG component contributing the largest real share of her SG Total sum in wins only, or null if no win has complete components |
| `career_dna.winning_foundation_share_pct` | DERIVED | that component's real share of the win-only SG Total sum |

### `career_evolution`

| Path | Label | Reason |
|---|---|---|
| `career_evolution.avg_app.current_direction` | DERIVED | UP/DOWN/FLAT sign of the most recent season-to-season delta |
| `career_evolution.avg_app.deltas[].delta` | DERIVED | season-to-season change in this component's average |
| `career_evolution.avg_app.deltas[].from_season` | MEASURED | real season |
| `career_evolution.avg_app.deltas[].growth_pct` | DERIVED | that delta as a percent of the earlier season's value, or null when the earlier value is 0 |
| `career_evolution.avg_app.deltas[].to_season` | MEASURED | real season |
| `career_evolution.avg_app.label` | MEASURED | static component label |
| `career_evolution.avg_app.peak_season.season` | MEASURED | real season of her highest average for this component |
| `career_evolution.avg_app.peak_season.value` | DERIVED | her real average that season (selected via max) |
| `career_evolution.avg_app.series[].season` | MEASURED | real season |
| `career_evolution.avg_app.series[].value` | DERIVED | that season's real average for this SG component |
| `career_evolution.avg_app.worst_season.season` | MEASURED | real season of her lowest average for this component |
| `career_evolution.avg_app.worst_season.value` | DERIVED | her real average that season (selected via min) |
| `career_evolution.avg_arg.current_direction` | DERIVED | UP/DOWN/FLAT sign of the most recent season-to-season delta |
| `career_evolution.avg_arg.deltas[].delta` | DERIVED | season-to-season change in this component's average |
| `career_evolution.avg_arg.deltas[].from_season` | MEASURED | real season |
| `career_evolution.avg_arg.deltas[].growth_pct` | DERIVED | that delta as a percent of the earlier season's value, or null when the earlier value is 0 |
| `career_evolution.avg_arg.deltas[].to_season` | MEASURED | real season |
| `career_evolution.avg_arg.label` | MEASURED | static component label |
| `career_evolution.avg_arg.peak_season.season` | MEASURED | real season of her highest average for this component |
| `career_evolution.avg_arg.peak_season.value` | DERIVED | her real average that season (selected via max) |
| `career_evolution.avg_arg.series[].season` | MEASURED | real season |
| `career_evolution.avg_arg.series[].value` | DERIVED | that season's real average for this SG component |
| `career_evolution.avg_arg.worst_season.season` | MEASURED | real season of her lowest average for this component |
| `career_evolution.avg_arg.worst_season.value` | DERIVED | her real average that season (selected via min) |
| `career_evolution.avg_ott.current_direction` | DERIVED | UP/DOWN/FLAT sign of the most recent season-to-season delta |
| `career_evolution.avg_ott.deltas[].delta` | DERIVED | season-to-season change in this component's average |
| `career_evolution.avg_ott.deltas[].from_season` | MEASURED | real season |
| `career_evolution.avg_ott.deltas[].growth_pct` | DERIVED | that delta as a percent of the earlier season's value, or null when the earlier value is 0 |
| `career_evolution.avg_ott.deltas[].to_season` | MEASURED | real season |
| `career_evolution.avg_ott.label` | MEASURED | static component label |
| `career_evolution.avg_ott.peak_season.season` | MEASURED | real season of her highest average for this component |
| `career_evolution.avg_ott.peak_season.value` | DERIVED | her real average that season (selected via max) |
| `career_evolution.avg_ott.series[].season` | MEASURED | real season |
| `career_evolution.avg_ott.series[].value` | DERIVED | that season's real average for this SG component |
| `career_evolution.avg_ott.worst_season.season` | MEASURED | real season of her lowest average for this component |
| `career_evolution.avg_ott.worst_season.value` | DERIVED | her real average that season (selected via min) |
| `career_evolution.avg_putt.current_direction` | DERIVED | UP/DOWN/FLAT sign of the most recent season-to-season delta |
| `career_evolution.avg_putt.deltas[].delta` | DERIVED | season-to-season change in this component's average |
| `career_evolution.avg_putt.deltas[].from_season` | MEASURED | real season |
| `career_evolution.avg_putt.deltas[].growth_pct` | DERIVED | that delta as a percent of the earlier season's value, or null when the earlier value is 0 |
| `career_evolution.avg_putt.deltas[].to_season` | MEASURED | real season |
| `career_evolution.avg_putt.label` | MEASURED | static component label |
| `career_evolution.avg_putt.peak_season.season` | MEASURED | real season of her highest average for this component |
| `career_evolution.avg_putt.peak_season.value` | DERIVED | her real average that season (selected via max) |
| `career_evolution.avg_putt.series[].season` | MEASURED | real season |
| `career_evolution.avg_putt.series[].value` | DERIVED | that season's real average for this SG component |
| `career_evolution.avg_putt.worst_season.season` | MEASURED | real season of her lowest average for this component |
| `career_evolution.avg_putt.worst_season.value` | DERIVED | her real average that season (selected via min) |
| `career_evolution.avg_total.current_direction` | DERIVED | UP/DOWN/FLAT sign of the most recent season-to-season delta |
| `career_evolution.avg_total.deltas[].delta` | DERIVED | season-to-season change in this component's average |
| `career_evolution.avg_total.deltas[].from_season` | MEASURED | real season |
| `career_evolution.avg_total.deltas[].growth_pct` | DERIVED | that delta as a percent of the earlier season's value, or null when the earlier value is 0 |
| `career_evolution.avg_total.deltas[].to_season` | MEASURED | real season |
| `career_evolution.avg_total.label` | MEASURED | static component label |
| `career_evolution.avg_total.peak_season.season` | MEASURED | real season of her highest average for this component |
| `career_evolution.avg_total.peak_season.value` | DERIVED | her real average that season (selected via max) |
| `career_evolution.avg_total.series[].season` | MEASURED | real season |
| `career_evolution.avg_total.series[].value` | DERIVED | that season's real average for this SG component |
| `career_evolution.avg_total.worst_season.season` | MEASURED | real season of her lowest average for this component |
| `career_evolution.avg_total.worst_season.value` | DERIVED | her real average that season (selected via min) |

### `career_form_story`

| Path | Label | Reason |
|---|---|---|
| `career_form_story[].best_component` | DERIVED | the SG component with the highest real delta vs its own career-component average, within this stage's window |
| `career_form_story[].best_delta` | DERIVED | that component's real delta vs its career-component average |
| `career_form_story[].delta_vs_career_average` | DERIVED | this stage's moving-average SG Total minus the real career average |
| `career_form_story[].end_season` | MEASURED | real season of that tournament |
| `career_form_story[].end_tournament` | MEASURED | real name of this stage's last tournament |
| `career_form_story[].stage` | MEASURED | static stage label (시즌 초반/중반/후반/전성기/현재 폼) |
| `career_form_story[].start_season` | MEASURED | real season of that tournament |
| `career_form_story[].start_tournament` | MEASURED | real name of this stage's first tournament |
| `career_form_story[].worst_component` | DERIVED | the SG component with the lowest real delta vs its own career-component average, within this stage's window, or null when only one component has data |
| `career_form_story[].worst_delta` | DERIVED | that component's real delta vs its career-component average |

### `career_heartbeat`

| Path | Label | Reason |
|---|---|---|
| `career_heartbeat.beats[].career_percentile` | DERIVED | this tournament's rank among only her own other tournaments |
| `career_heartbeat.beats[].delta_vs_career_average` | DERIVED | sg_total minus career_average_sg_total |
| `career_heartbeat.beats[].game_code` | MEASURED | real tournament id |
| `career_heartbeat.beats[].is_top10` | DERIVED | boolean: rank<=10 |
| `career_heartbeat.beats[].is_win` | DERIVED | boolean: rank==1 |
| `career_heartbeat.beats[].season` | MEASURED | real season |
| `career_heartbeat.beats[].sg_total` | MEASURED | her real SG Total in that tournament |
| `career_heartbeat.beats[].tournament` | MEASURED | real tournament name |
| `career_heartbeat.career_average_sg_total` | DERIVED | the same real career average used everywhere else on this page |
| `career_heartbeat.sample_size` | DERIVED | count of real SG-bearing finished tournaments plotted |

### `career_overview`

| Path | Label | Reason |
|---|---|---|
| `career_overview.data_floor_note` | DERIVED | disclosure sentence naming earliest_season_on_record, explicitly not claimed as her real debut season |
| `career_overview.earliest_season_on_record` | MEASURED | the earliest season this warehouse has any data for |
| `career_overview.latest_tournament.final_score_to_par` | MEASURED | real final score relative to par |
| `career_overview.latest_tournament.game_code` | MEASURED | real most recent tournament id (by real end_date) |
| `career_overview.latest_tournament.is_winner_per_official_source` | DERIVED | boolean: rank==1 |
| `career_overview.latest_tournament.rank` | MEASURED | real final rank |
| `career_overview.latest_tournament.rank_display` | DERIVED | formatted text built from the real rank |
| `career_overview.latest_tournament.round_scores[].round` | MEASURED | real round number |
| `career_overview.latest_tournament.round_scores[].sg_total` | MEASURED | real per-round SG Total |
| `career_overview.latest_tournament.rounds_played` | MEASURED | real number of rounds played |
| `career_overview.latest_tournament.season` | MEASURED | real season of that tournament |
| `career_overview.latest_tournament.sg_app` | MEASURED | real captured SG APP for this tournament |
| `career_overview.latest_tournament.sg_arg` | MEASURED | real captured SG ARG for this tournament |
| `career_overview.latest_tournament.sg_ott` | MEASURED | real captured SG OTT for this tournament |
| `career_overview.latest_tournament.sg_putt` | MEASURED | real captured SG PUTT for this tournament |
| `career_overview.latest_tournament.sg_total` | MEASURED | real captured SG Total for this tournament |
| `career_overview.latest_tournament.sources[]` | MEASURED | real list naming which source categories captured this tournament |
| `career_overview.latest_tournament.status` | MEASURED | real tournament status string |
| `career_overview.latest_tournament.tournament` | MEASURED | real name of that tournament |
| `career_overview.season_count` | DERIVED | count of seasons with real data |
| `career_overview.season_rows[].events` | DERIVED | count of finished tournaments that season |
| `career_overview.season_rows[].season` | MEASURED | real season label |
| `career_overview.season_rows[].sg_app` | DERIVED | mean SG APP across that season's tournaments |
| `career_overview.season_rows[].sg_arg` | DERIVED | mean SG ARG across that season's tournaments |
| `career_overview.season_rows[].sg_ott` | DERIVED | mean SG OTT across that season's tournaments |
| `career_overview.season_rows[].sg_putt` | DERIVED | mean SG PUTT across that season's tournaments |
| `career_overview.season_rows[].sg_sample_size` | DERIVED | count of tournaments behind that season's SG averages |
| `career_overview.season_rows[].sg_total` | DERIVED | mean SG Total across that season's tournaments |
| `career_overview.season_rows[].top10` | DERIVED | count of rank<=10 finishes that season |
| `career_overview.season_rows[].top20` | DERIVED | count of rank<=20 finishes that season |
| `career_overview.season_rows[].top5` | DERIVED | count of rank<=5 finishes that season |
| `career_overview.season_rows[].wins` | DERIVED | count of rank==1 finishes that season |
| `career_overview.total_events` | DERIVED | count of all finished tournaments |
| `career_overview.total_top10` | DERIVED | sum of season_rows[].top10 |
| `career_overview.total_top20` | DERIVED | sum of season_rows[].top20 |
| `career_overview.total_top5` | DERIVED | sum of season_rows[].top5 |
| `career_overview.total_wins` | DERIVED | count of all rank==1 finishes |

### `career_rolling_trend`

| Path | Label | Reason |
|---|---|---|
| `career_rolling_trend.career_average_sample_size` | DERIVED | count of SG-bearing finished tournaments |
| `career_rolling_trend.career_average_sg_total` | DERIVED | mean SG Total over every finished, SG-bearing tournament |
| `career_rolling_trend.career_median_sg_total` | DERIVED | median SG Total over the same population |
| `career_rolling_trend.note` | MEASURED | fixed disclosure text about window size and self-comparison scope |
| `career_rolling_trend.peak_window.decomposition.app` | DERIVED | mean real SG APP across the tournaments in this window that have it, or null |
| `career_rolling_trend.peak_window.decomposition.arg` | DERIVED | mean real SG ARG across the tournaments in this window that have it, or null |
| `career_rolling_trend.peak_window.decomposition.birdie` | NOT_AVAILABLE | real hole-level birdie count when this window overlaps the one hole-covered tournament; that has never yet happened for a finished window, so this is always null in this build |
| `career_rolling_trend.peak_window.decomposition.birdie_bogey_gir_putts_note` | DERIVED | disclosure sentence explaining the status above |
| `career_rolling_trend.peak_window.decomposition.birdie_bogey_gir_putts_status` | DERIVED | computed availability flag: whether this window overlaps the one hole-covered tournament |
| `career_rolling_trend.peak_window.decomposition.bogey` | NOT_AVAILABLE | same as birdie above |
| `career_rolling_trend.peak_window.decomposition.gir` | NOT_AVAILABLE | the one hole-level source that exists (hole_history) never captured GIR at all -- always null regardless of window overlap |
| `career_rolling_trend.peak_window.decomposition.ott` | DERIVED | mean real SG OTT across the tournaments in this window that have it, or null |
| `career_rolling_trend.peak_window.decomposition.putt` | DERIVED | mean real SG PUTT across the tournaments in this window that have it, or null |
| `career_rolling_trend.peak_window.decomposition.putts` | NOT_AVAILABLE | the one hole-level source that exists (hole_history) never captured putts-per-hole at all -- always null regardless of window overlap |
| `career_rolling_trend.peak_window.decomposition.sg_component_sample_size` | DERIVED | count of tournaments in this window with real SG components |
| `career_rolling_trend.peak_window.decomposition.sg_component_window_size` | DERIVED | count of tournaments in this window |
| `career_rolling_trend.peak_window.delta_vs_career_average` | DERIVED | moving_average_sg_total minus the real career average |
| `career_rolling_trend.peak_window.end_season` | MEASURED | real season of that tournament |
| `career_rolling_trend.peak_window.end_tournament` | MEASURED | real name of this window's last tournament |
| `career_rolling_trend.peak_window.moving_average_sg_total` | DERIVED | mean SG Total over this 5-tournament window |
| `career_rolling_trend.peak_window.self_percentile` | DERIVED | this window's rank among only her own other windows |
| `career_rolling_trend.peak_window.start_season` | MEASURED | real season of that tournament |
| `career_rolling_trend.peak_window.start_tournament` | MEASURED | real name of this window's first tournament |
| `career_rolling_trend.peak_window.sustainability_tournaments` | DERIVED | sustainability_windows converted to a real tournament span |
| `career_rolling_trend.peak_window.sustainability_windows` | DERIVED | count of consecutive real windows from the peak that stayed at/above the career average |
| `career_rolling_trend.peak_window.window_index` | MEASURED | structural sequence index, not golfer data |
| `career_rolling_trend.recovery_time_note` | DERIVED | sentence naming recovery_time_tournament, or a fixed disclosure when recovery was never observed in the real data |
| `career_rolling_trend.recovery_time_tournament` | MEASURED | real tournament name at that recovery point, or null |
| `career_rolling_trend.recovery_time_windows` | DERIVED | count of windows after the slump until the first one back at/above career average, or null if never observed |
| `career_rolling_trend.recovery_window.decomposition.app` | DERIVED | mean real SG APP across the tournaments in this window that have it, or null |
| `career_rolling_trend.recovery_window.decomposition.arg` | DERIVED | mean real SG ARG across the tournaments in this window that have it, or null |
| `career_rolling_trend.recovery_window.decomposition.birdie` | NOT_AVAILABLE | real hole-level birdie count when this window overlaps the one hole-covered tournament; that has never yet happened for a finished window, so this is always null in this build |
| `career_rolling_trend.recovery_window.decomposition.birdie_bogey_gir_putts_note` | DERIVED | disclosure sentence explaining the status above |
| `career_rolling_trend.recovery_window.decomposition.birdie_bogey_gir_putts_status` | DERIVED | computed availability flag: whether this window overlaps the one hole-covered tournament |
| `career_rolling_trend.recovery_window.decomposition.bogey` | NOT_AVAILABLE | same as birdie above |
| `career_rolling_trend.recovery_window.decomposition.gir` | NOT_AVAILABLE | the one hole-level source that exists (hole_history) never captured GIR at all -- always null regardless of window overlap |
| `career_rolling_trend.recovery_window.decomposition.ott` | DERIVED | mean real SG OTT across the tournaments in this window that have it, or null |
| `career_rolling_trend.recovery_window.decomposition.putt` | DERIVED | mean real SG PUTT across the tournaments in this window that have it, or null |
| `career_rolling_trend.recovery_window.decomposition.putts` | NOT_AVAILABLE | the one hole-level source that exists (hole_history) never captured putts-per-hole at all -- always null regardless of window overlap |
| `career_rolling_trend.recovery_window.decomposition.sg_component_sample_size` | DERIVED | count of tournaments in this window with real SG components |
| `career_rolling_trend.recovery_window.decomposition.sg_component_window_size` | DERIVED | count of tournaments in this window |
| `career_rolling_trend.recovery_window.delta_vs_career_average` | DERIVED | moving_average_sg_total minus the real career average |
| `career_rolling_trend.recovery_window.delta_vs_slump` | DERIVED | recovery_window.moving_average_sg_total minus slump_window.moving_average_sg_total |
| `career_rolling_trend.recovery_window.end_season` | MEASURED | real season of that tournament |
| `career_rolling_trend.recovery_window.end_tournament` | MEASURED | real name of this window's last tournament |
| `career_rolling_trend.recovery_window.moving_average_sg_total` | DERIVED | mean SG Total over this 5-tournament window |
| `career_rolling_trend.recovery_window.self_percentile` | DERIVED | this window's rank among only her own other windows |
| `career_rolling_trend.recovery_window.start_season` | MEASURED | real season of that tournament |
| `career_rolling_trend.recovery_window.start_tournament` | MEASURED | real name of this window's first tournament |
| `career_rolling_trend.recovery_window.window_index` | MEASURED | structural sequence index, not golfer data |
| `career_rolling_trend.series[].end_season` | MEASURED | real season of that tournament |
| `career_rolling_trend.series[].end_tournament` | MEASURED | real name of the window's last tournament |
| `career_rolling_trend.series[].moving_average_sg_total` | DERIVED | mean SG Total over this 5-tournament window |
| `career_rolling_trend.series[].self_percentile` | DERIVED | this window's rank among only her own other windows |
| `career_rolling_trend.series[].start_season` | MEASURED | real season of that tournament |
| `career_rolling_trend.series[].start_tournament` | MEASURED | real name of the window's first tournament |
| `career_rolling_trend.series[].window_index` | MEASURED | structural sequence index, not golfer data |
| `career_rolling_trend.slump_window.decomposition.app` | DERIVED | mean real SG APP across the tournaments in this window that have it, or null |
| `career_rolling_trend.slump_window.decomposition.arg` | DERIVED | mean real SG ARG across the tournaments in this window that have it, or null |
| `career_rolling_trend.slump_window.decomposition.birdie` | NOT_AVAILABLE | real hole-level birdie count when this window overlaps the one hole-covered tournament; that has never yet happened for a finished window, so this is always null in this build |
| `career_rolling_trend.slump_window.decomposition.birdie_bogey_gir_putts_note` | DERIVED | disclosure sentence explaining the status above |
| `career_rolling_trend.slump_window.decomposition.birdie_bogey_gir_putts_status` | DERIVED | computed availability flag: whether this window overlaps the one hole-covered tournament |
| `career_rolling_trend.slump_window.decomposition.bogey` | NOT_AVAILABLE | same as birdie above |
| `career_rolling_trend.slump_window.decomposition.gir` | NOT_AVAILABLE | the one hole-level source that exists (hole_history) never captured GIR at all -- always null regardless of window overlap |
| `career_rolling_trend.slump_window.decomposition.ott` | DERIVED | mean real SG OTT across the tournaments in this window that have it, or null |
| `career_rolling_trend.slump_window.decomposition.putt` | DERIVED | mean real SG PUTT across the tournaments in this window that have it, or null |
| `career_rolling_trend.slump_window.decomposition.putts` | NOT_AVAILABLE | the one hole-level source that exists (hole_history) never captured putts-per-hole at all -- always null regardless of window overlap |
| `career_rolling_trend.slump_window.decomposition.sg_component_sample_size` | DERIVED | count of tournaments in this window with real SG components |
| `career_rolling_trend.slump_window.decomposition.sg_component_window_size` | DERIVED | count of tournaments in this window |
| `career_rolling_trend.slump_window.delta_vs_career_average` | DERIVED | moving_average_sg_total minus the real career average |
| `career_rolling_trend.slump_window.end_season` | MEASURED | real season of that tournament |
| `career_rolling_trend.slump_window.end_tournament` | MEASURED | real name of this window's last tournament |
| `career_rolling_trend.slump_window.moving_average_sg_total` | DERIVED | mean SG Total over this 5-tournament window |
| `career_rolling_trend.slump_window.self_percentile` | DERIVED | this window's rank among only her own other windows |
| `career_rolling_trend.slump_window.start_season` | MEASURED | real season of that tournament |
| `career_rolling_trend.slump_window.start_tournament` | MEASURED | real name of this window's first tournament |
| `career_rolling_trend.slump_window.window_index` | MEASURED | structural sequence index, not golfer data |
| `career_rolling_trend.total_windows` | DERIVED | count of sliding windows the real series produced |
| `career_rolling_trend.window_size` | MEASURED | fixed config constant (5), not golfer data |

### `career_story`

| Path | Label | Reason |
|---|---|---|
| `career_story.chapters[].chapter` | MEASURED | static chapter label from a fixed 4-chapter order |
| `career_story.chapters[].milestones[].detail` | DERIVED | pass-through of a real player_story milestone's templated detail sentence |
| `career_story.chapters[].milestones[].label` | MEASURED | pass-through of a real player_story milestone's static label |
| `career_story.chapters[].milestones[].season` | MEASURED | pass-through of a real player_story milestone's season |
| `career_story.current.events` | DERIVED | that season's real event count |
| `career_story.current.season` | MEASURED | the most recent real season on record |
| `career_story.current.sg_total` | DERIVED | that season's SG Total average |
| `career_story.current.top10` | DERIVED | that season's real top-10 count |
| `career_story.current.wins` | DERIVED | that season's real win count |
| `career_story.season_rows[].events` | DERIVED | duplicate of career_overview.season_rows[].events |
| `career_story.season_rows[].season` | MEASURED | duplicate of career_overview.season_rows -- see that key; kept here only because the field is not removed, never independently computed |
| `career_story.season_rows[].sg_app` | DERIVED | duplicate of career_overview.season_rows[].sg_app |
| `career_story.season_rows[].sg_arg` | DERIVED | duplicate of career_overview.season_rows[].sg_arg |
| `career_story.season_rows[].sg_ott` | DERIVED | duplicate of career_overview.season_rows[].sg_ott |
| `career_story.season_rows[].sg_putt` | DERIVED | duplicate of career_overview.season_rows[].sg_putt |
| `career_story.season_rows[].sg_sample_size` | DERIVED | duplicate of career_overview.season_rows[].sg_sample_size |
| `career_story.season_rows[].sg_total` | DERIVED | duplicate of career_overview.season_rows[].sg_total |
| `career_story.season_rows[].top10` | DERIVED | duplicate of career_overview.season_rows[].top10 |
| `career_story.season_rows[].top20` | DERIVED | duplicate of career_overview.season_rows[].top20 |
| `career_story.season_rows[].top5` | DERIVED | duplicate of career_overview.season_rows[].top5 |
| `career_story.season_rows[].wins` | DERIVED | duplicate of career_overview.season_rows[].wins |

### `course_profile`

| Path | Label | Reason |
|---|---|---|
| `course_profile[].appearances` | DERIVED | count of times this tournament name recurred |
| `course_profile[].avg_sg_total` | DERIVED | mean SG Total across every appearance |
| `course_profile[].best_sg_total` | MEASURED | her real SG Total in that specific appearance |
| `course_profile[].best_tournament` | MEASURED | real name of her best-SG appearance in this group |
| `course_profile[].tournament_family` | MEASURED | real tournament name of the most recent appearance in this recurring group |
| `course_profile[].worst_sg_total` | MEASURED | her real SG Total in that specific appearance |
| `course_profile[].worst_tournament` | MEASURED | real name of her worst-SG appearance in this group |

### `coverage_matrix`

| Path | Label | Reason |
|---|---|---|
| `coverage_matrix.note` | MEASURED | fixed disclosure text, not golfer data |
| `coverage_matrix.rows.1-Putt %.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.1-Putt %.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.1-Putt %.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.1-Putt %.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Birdie-or-better %.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Birdie-or-better %.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Birdie-or-better %.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Birdie-or-better %.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Driving Distance.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Driving Distance.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Driving Distance.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Driving Distance.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Fairway Accuracy.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Fairway Accuracy.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Fairway Accuracy.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Fairway Accuracy.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.GIR.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.GIR.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.GIR.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.GIR.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Prize Money.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Prize Money.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Prize Money.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Prize Money.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Putting Success %.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Putting Success %.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Putting Success %.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Putting Success %.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Putts/Round.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Putts/Round.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Putts/Round.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Putts/Round.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Approach.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Approach.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Approach.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Approach.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Around-the-Green.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Around-the-Green.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Around-the-Green.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Around-the-Green.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Off-the-Tee.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Off-the-Tee.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Off-the-Tee.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Off-the-Tee.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Putting.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Putting.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Putting.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Putting.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Total.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Total.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Total.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.SG Total.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Sand Save %.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Sand Save %.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Sand Save %.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Sand Save %.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Scoring Average.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Scoring Average.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Scoring Average.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Scoring Average.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Scrambling %.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Scrambling %.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Scrambling %.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Scrambling %.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Top10.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Top10.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Top10.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Top10.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Top20.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Top20.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Top20.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Top20.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Top5.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Top5.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Top5.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Top5.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Wins.2023` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Wins.2024` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Wins.2025` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.rows.Wins.2026` | MEASURED | literal status code -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `coverage_matrix.seasons[]` | MEASURED | the 4 real seasons this repository covers |
| `coverage_matrix.status_legend.BLOCKED` | MEASURED | fixed legend text, not golfer data |
| `coverage_matrix.status_legend.DERIVED` | MEASURED | fixed legend text, not golfer data |
| `coverage_matrix.status_legend.MEASURED` | MEASURED | fixed legend text, not golfer data |
| `coverage_matrix.status_legend.NOT_COLLECTED` | MEASURED | fixed legend text, not golfer data |

### `current_form_indicator`

| Path | Label | Reason |
|---|---|---|
| `current_form_indicator.delta` | DERIVED | last5_avg_sg_total minus prev5_avg_sg_total |
| `current_form_indicator.last5_avg_sg_total` | DERIVED | mean SG Total of her last 5 finished, SG-bearing tournaments |
| `current_form_indicator.last5_sample_size` | DERIVED | count of SG-bearing tournaments in the last-5 window |
| `current_form_indicator.prev5_avg_sg_total` | DERIVED | mean SG Total of the 5 finished tournaments immediately before those |
| `current_form_indicator.prev5_sample_size` | DERIVED | count of SG-bearing tournaments in the previous-5 window |
| `current_form_indicator.trend` | DERIVED | UP/DOWN/FLAT banded classification of the delta below (+/-0.15 SG band) |

### `current_skill_vs_career`

| Path | Label | Reason |
|---|---|---|
| `current_skill_vs_career.components[].career_average` | DERIVED | mean of this SG component over every finished tournament that has it |
| `current_skill_vs_career.components[].career_sample_size` | DERIVED | count of tournaments with a real value for this component |
| `current_skill_vs_career.components[].component` | MEASURED | static component label (SG OTT/APP/ARG/PUTT) |
| `current_skill_vs_career.components[].current_value` | DERIVED | current season's average for this SG component |
| `current_skill_vs_career.components[].delta_vs_career_average` | DERIVED | current_value minus career_average for this component |
| `current_skill_vs_career.current_season` | MEASURED | the most recent real season on record |
| `current_skill_vs_career.current_season_sample_size` | DERIVED | count of tournaments behind the current season |

### `current_snapshot`

| Path | Label | Reason |
|---|---|---|
| `current_snapshot.as_of_note` | DERIVED | disclosure sentence naming the real snapshot season |
| `current_snapshot.average_putts` | MEASURED | real official average putts |
| `current_snapshot.average_score` | MEASURED | real official average score |
| `current_snapshot.birdie_rate` | MEASURED | real official birdie rate |
| `current_snapshot.gir_rate` | MEASURED | real official GIR rate |
| `current_snapshot.money` | MEASURED | real official prize money from the same snapshot |
| `current_snapshot.official_rank` | MEASURED | real official overall rank from OFFICIAL_PROFILE_NORMALIZED.json |
| `current_snapshot.official_sg_app` | MEASURED | real official SG APP from the same snapshot |
| `current_snapshot.official_sg_arg` | MEASURED | real official SG ARG from the same snapshot |
| `current_snapshot.official_sg_ott` | MEASURED | real official SG OTT from the same snapshot |
| `current_snapshot.official_sg_putt` | MEASURED | real official SG PUTT from the same snapshot |
| `current_snapshot.official_sg_rank` | MEASURED | real official SG rank from OFFICIAL_SG_NORMALIZED.json |
| `current_snapshot.official_sg_rounds` | MEASURED | real official rounds count backing the snapshot |
| `current_snapshot.official_sg_total` | MEASURED | real official SG Total from the same snapshot |
| `current_snapshot.par_break_rate` | MEASURED | real official par-break rate |
| `current_snapshot.par_save_rate` | MEASURED | real official par-save rate |
| `current_snapshot.recovery_rate` | MEASURED | real official recovery rate |

### `current_tournament_in_progress`

| Path | Label | Reason |
|---|---|---|
| `current_tournament_in_progress.current_ing_hole` | MEASURED | real live current-hole capture |
| `current_tournament_in_progress.game_code` | MEASURED | real in-progress tournament id |
| `current_tournament_in_progress.is_confirmed_live` | DERIVED | boolean computed by reconcile() against the real official schedule -- never assumed live |
| `current_tournament_in_progress.note` | DERIVED | disclosure text built from the real live-capture state |
| `current_tournament_in_progress.partial_round_sg.approach` | DERIVED | NEO's own in-house SG-approach computation over the still-incomplete round -- reference-only |
| `current_tournament_in_progress.partial_round_sg.around_green` | DERIVED | NEO's own in-house SG-around-the-green computation over the still-incomplete round -- reference-only |
| `current_tournament_in_progress.partial_round_sg.off_the_tee` | DERIVED | NEO's own in-house SG-off-the-tee computation over the still-incomplete round -- explicitly labeled reference-only, never an official final number |
| `current_tournament_in_progress.partial_round_sg.player` | MEASURED | real player name on the live scorecard |
| `current_tournament_in_progress.partial_round_sg.player_id` | MEASURED | real player id on the live scorecard |
| `current_tournament_in_progress.partial_round_sg.putting` | DERIVED | NEO's own in-house SG-putting computation over the still-incomplete round -- reference-only |
| `current_tournament_in_progress.partial_round_sg.rank` | MEASURED | real live leaderboard rank |
| `current_tournament_in_progress.partial_round_sg.round` | MEASURED | real round number this partial SG covers |
| `current_tournament_in_progress.partial_round_sg.rounds` | MEASURED | real hole count captured so far this round |
| `current_tournament_in_progress.partial_round_sg.scope` | MEASURED | real scope label for this partial SG computation |
| `current_tournament_in_progress.partial_round_sg.tee_to_green` | DERIVED | NEO's own in-house tee-to-green SG computation over the still-incomplete round -- reference-only |
| `current_tournament_in_progress.partial_round_sg.total` | DERIVED | sum of the partial SG components above -- reference-only |
| `current_tournament_in_progress.partial_round_sg.validation.t2g_delta` | DERIVED | cross-check delta between the summed components and an independent tee-to-green figure |
| `current_tournament_in_progress.partial_round_sg.validation.t2g_within_tolerance` | DERIVED | boolean: whether t2g_delta is within the accepted tolerance |
| `current_tournament_in_progress.partial_round_sg.validation.total_delta` | DERIVED | cross-check delta on the total SG figure |
| `current_tournament_in_progress.partial_round_sg.validation.total_within_tolerance` | DERIVED | boolean: whether total_delta is within the accepted tolerance |
| `current_tournament_in_progress.rounds_completed[].round` | MEASURED | real completed round number |
| `current_tournament_in_progress.rounds_completed[].strokes` | MEASURED | real strokes for that completed round |
| `current_tournament_in_progress.scheduled_end_date` | MEASURED | real official schedule end date |
| `current_tournament_in_progress.season` | MEASURED | real season |
| `current_tournament_in_progress.sources[]` | MEASURED | real list naming which source categories captured this tournament |
| `current_tournament_in_progress.status` | MEASURED | real live-capture status string |
| `current_tournament_in_progress.tournament` | MEASURED | real tournament name |

### `current_vs_career`

| Path | Label | Reason |
|---|---|---|
| `current_vs_career.career_average_sample_size` | DERIVED | count of SG-bearing finished tournaments |
| `current_vs_career.career_average_sg_total` | DERIVED | mean of every finished tournament's real SG Total |
| `current_vs_career.current_season` | MEASURED | the most recent real season on record |
| `current_vs_career.current_season_sample_size` | DERIVED | count of tournaments behind the current-season average |
| `current_vs_career.current_season_sg_total` | DERIVED | that season's SG Total average, computed by knowledge_engine.compute_season_profiles over the season's real tournaments |
| `current_vs_career.delta_vs_career_average` | DERIVED | current_season_sg_total minus career_average_sg_total |

### `data_confidence_roadmap`

| Path | Label | Reason |
|---|---|---|
| `data_confidence_roadmap[].field_count` | DERIVED | count of provenance-map fields grouped under this title |
| `data_confidence_roadmap[].title` | MEASURED | fixed translated group name, not computed from data |

### `data_quality_timeline`

| Path | Label | Reason |
|---|---|---|
| `data_quality_timeline[].available_pct` | DERIVED | share of coverage_matrix.rows marked real for this season |
| `data_quality_timeline[].season` | MEASURED | real season label |
| `data_quality_timeline[].summary` | DERIVED | template sentence chosen from available_pct |

### `field_confidence_legend`

| Path | Label | Reason |
|---|---|---|
| `field_confidence_legend.DERIVED.detail` | MEASURED | fixed translated explanation, not computed from data |
| `field_confidence_legend.DERIVED.short` | MEASURED | fixed translated label, not computed from data |
| `field_confidence_legend.DERIVED.tier` | MEASURED | fixed trust tier constant, not computed from data |
| `field_confidence_legend.IMPUTED.detail` | MEASURED | fixed translated explanation, not computed from data |
| `field_confidence_legend.IMPUTED.short` | MEASURED | fixed translated label, not computed from data |
| `field_confidence_legend.IMPUTED.tier` | MEASURED | fixed trust tier constant, not computed from data |
| `field_confidence_legend.MEASURED.detail` | MEASURED | fixed translated explanation, not computed from data |
| `field_confidence_legend.MEASURED.short` | MEASURED | fixed translated label, not computed from data |
| `field_confidence_legend.MEASURED.tier` | MEASURED | fixed trust tier constant, not computed from data |
| `field_confidence_legend.NOT_AVAILABLE.detail` | MEASURED | fixed translated explanation, not computed from data |
| `field_confidence_legend.NOT_AVAILABLE.short` | MEASURED | fixed translated label, not computed from data |
| `field_confidence_legend.NOT_AVAILABLE.tier` | MEASURED | fixed trust tier constant, not computed from data |
| `field_confidence_legend.NOT_COLLECTED.detail` | MEASURED | fixed translated explanation, not computed from data |
| `field_confidence_legend.NOT_COLLECTED.short` | MEASURED | fixed translated label, not computed from data |
| `field_confidence_legend.NOT_COLLECTED.tier` | MEASURED | fixed trust tier constant, not computed from data |

### `hole_history`

| Path | Label | Reason |
|---|---|---|
| `hole_history.capture_note` | NOT_AVAILABLE | fixed disclosure text: this is the only hole-level source anywhere in this repository for this player |
| `hole_history.course` | MEASURED | real course name from this one capture |
| `hole_history.game_code` | MEASURED | real tournament id |
| `hole_history.rounds[].holes[].hole` | MEASURED | real hole number |
| `hole_history.rounds[].holes[].par` | MEASURED | real hole par |
| `hole_history.rounds[].holes[].relative_to_par` | DERIVED | strokes minus par for this hole |
| `hole_history.rounds[].holes[].strokes` | MEASURED | real strokes taken on this hole |
| `hole_history.rounds[].holes_recorded` | DERIVED | count of real hole records in this round |
| `hole_history.rounds[].round` | MEASURED | real round number |
| `hole_history.total_hole_records` | DERIVED | count of real hole records captured |
| `hole_history.tournament` | MEASURED | real tournament name |

### `not_available`

| Path | Label | Reason |
|---|---|---|
| `not_available[]` | NOT_AVAILABLE | each entry is itself a disclosure of a genuinely unavailable field -- the field's own text IS the provenance answer |

### `page_confidence`

| Path | Label | Reason |
|---|---|---|
| `page_confidence.estimated_fields` | DERIVED | count of IMPUTED fields |
| `page_confidence.headline` | DERIVED | template sentence chosen from trust_band |
| `page_confidence.not_yet_available_fields` | DERIVED | count of NOT_COLLECTED + NOT_AVAILABLE fields |
| `page_confidence.real_or_calculated_fields` | DERIVED | count of MEASURED + DERIVED fields |
| `page_confidence.total_fields_checked` | DERIVED | count of all classified fields in the provenance map |
| `page_confidence.trust_band` | DERIVED | banded classification of trustworthy_pct |
| `page_confidence.trustworthy_pct` | DERIVED | (MEASURED + DERIVED field count) / (total classified field count) * 100, from the provenance map |

### `player_dna_growth`

| Path | Label | Reason |
|---|---|---|
| `player_dna_growth.APPROACH.career_mean_percentile` | DERIVED | mean of her real per-season percentiles for this axis |
| `player_dna_growth.APPROACH.growth_acceleration_per_season` | DERIVED | mean change in growth_velocity_per_season itself, or null with <3 real seasons |
| `player_dna_growth.APPROACH.growth_velocity_per_season` | DERIVED | mean season-to-season change in her real percentile for this axis, or null with <2 real seasons |
| `player_dna_growth.APPROACH.sample_size` | DERIVED | count of seasons_used |
| `player_dna_growth.APPROACH.seasons_used[]` | MEASURED | real seasons with an available percentile for this axis |
| `player_dna_growth.APPROACH.stability_stddev` | DERIVED | population stddev of her real per-season percentiles, or null with <2 real seasons |
| `player_dna_growth.PUTTING.career_mean_percentile` | DERIVED | mean of her real per-season percentiles for this axis |
| `player_dna_growth.PUTTING.growth_acceleration_per_season` | DERIVED | mean change in growth_velocity_per_season itself, or null with <3 real seasons |
| `player_dna_growth.PUTTING.growth_velocity_per_season` | DERIVED | mean season-to-season change in her real percentile for this axis, or null with <2 real seasons |
| `player_dna_growth.PUTTING.sample_size` | DERIVED | count of seasons_used |
| `player_dna_growth.PUTTING.seasons_used[]` | MEASURED | real seasons with an available percentile for this axis |
| `player_dna_growth.PUTTING.stability_stddev` | DERIVED | population stddev of her real per-season percentiles, or null with <2 real seasons |
| `player_dna_growth.SCORING.career_mean_percentile` | DERIVED | mean of her real per-season percentiles for this axis |
| `player_dna_growth.SCORING.growth_acceleration_per_season` | DERIVED | mean change in growth_velocity_per_season itself, or null with <3 real seasons |
| `player_dna_growth.SCORING.growth_velocity_per_season` | DERIVED | mean season-to-season change in her real percentile for this axis, or null with <2 real seasons |
| `player_dna_growth.SCORING.sample_size` | DERIVED | count of seasons_used |
| `player_dna_growth.SCORING.seasons_used[]` | MEASURED | real seasons with an available percentile for this axis |
| `player_dna_growth.SCORING.stability_stddev` | DERIVED | population stddev of her real per-season percentiles, or null with <2 real seasons |
| `player_dna_growth.TEE.career_mean_percentile` | DERIVED | mean of her real per-season percentiles for this axis |
| `player_dna_growth.TEE.growth_acceleration_per_season` | DERIVED | mean change in growth_velocity_per_season itself, or null with <3 real seasons |
| `player_dna_growth.TEE.growth_velocity_per_season` | DERIVED | mean season-to-season change in her real percentile for this axis, or null with <2 real seasons |
| `player_dna_growth.TEE.sample_size` | DERIVED | count of seasons_used |
| `player_dna_growth.TEE.seasons_used[]` | MEASURED | real seasons with an available percentile for this axis |
| `player_dna_growth.TEE.stability_stddev` | DERIVED | population stddev of her real per-season percentiles, or null with <2 real seasons |
| `player_dna_growth.쇼트게임.career_mean_percentile` | DERIVED | mean of her real per-season percentiles for this axis |
| `player_dna_growth.쇼트게임.growth_acceleration_per_season` | DERIVED | mean change in growth_velocity_per_season itself, or null with <3 real seasons |
| `player_dna_growth.쇼트게임.growth_velocity_per_season` | DERIVED | mean season-to-season change in her real percentile for this axis, or null with <2 real seasons |
| `player_dna_growth.쇼트게임.sample_size` | DERIVED | count of seasons_used |
| `player_dna_growth.쇼트게임.seasons_used[]` | MEASURED | real seasons with an available percentile for this axis |
| `player_dna_growth.쇼트게임.stability_stddev` | DERIVED | population stddev of her real per-season percentiles, or null with <2 real seasons |

### `player_dna_radar`

| Path | Label | Reason |
|---|---|---|
| `player_dna_radar[].axes[].available` | DERIVED | boolean: she is present in this season's warehouse AND the population has at least 2 players |
| `player_dna_radar[].axes[].axis` | MEASURED | static axis label |
| `player_dna_radar[].axes[].delta_vs_career_mean` | DERIVED | this season's percentile minus her career-mean percentile for this axis |
| `player_dna_radar[].axes[].normalization_method` | MEASURED | fixed description of the percentile method, or null when unavailable |
| `player_dna_radar[].axes[].percentile` | DERIVED | her rank among every other real KLPGA player's same season-average, within this season's population |
| `player_dna_radar[].axes[].population` | DERIVED | count of players with a real season-average for this axis |
| `player_dna_radar[].axes[].raw_value` | DERIVED | despite the field name, this is her season-average for this SG component (mean over that season's real tournament_cumulative rows), not a single raw datapoint |
| `player_dna_radar[].axes[].season` | MEASURED | real season |
| `player_dna_radar[].axes[].source` | MEASURED | fixed string naming the real source file |
| `player_dna_radar[].axes[].source_metric` | MEASURED | static warehouse field key |
| `player_dna_radar[].season` | MEASURED | real season |

### `player_evolution`

| Path | Label | Reason |
|---|---|---|
| `player_evolution.biggest_decline` | DERIVED | the largest negative season-to-season SG Total change, or null if she has never had one |
| `player_evolution.biggest_improvement.delta` | DERIVED | the largest positive season-to-season SG Total change |
| `player_evolution.biggest_improvement.from_season` | MEASURED | real season |
| `player_evolution.biggest_improvement.growth_pct` | DERIVED | that delta as a percent of the earlier season's value |
| `player_evolution.biggest_improvement.to_season` | MEASURED | real season |
| `player_evolution.closest_to_plateau.delta` | DERIVED | the smallest-magnitude season-to-season SG Total change |
| `player_evolution.closest_to_plateau.from_season` | MEASURED | real season |
| `player_evolution.closest_to_plateau.growth_pct` | DERIVED | that delta as a percent of the earlier season's value |
| `player_evolution.closest_to_plateau.to_season` | MEASURED | real season |
| `player_evolution.first_improvement.delta` | DERIVED | SG Total change between those two seasons |
| `player_evolution.first_improvement.from_season` | MEASURED | real season |
| `player_evolution.first_improvement.growth_pct` | DERIVED | that delta as a percent of the earlier season's value |
| `player_evolution.first_improvement.to_season` | MEASURED | real season |
| `player_evolution.no_decline_observed` | DERIVED | boolean: biggest_decline is null |
| `player_evolution.trend_reversal` | DERIVED | the first adjacent season-pair where the delta sign flips, or null if it never does |

### `player_id`

| Path | Label | Reason |
|---|---|---|
| `player_id` | MEASURED | playerCode constant identifying this golfer |

### `player_identity`

| Path | Label | Reason |
|---|---|---|
| `player_identity.consistency_component` | DERIVED | pass-through of career_dna.most_consistent_component when it is not SG Total |
| `player_identity.consistency_note` | DERIVED | template sentence naming consistency_component |
| `player_identity.primary_component` | DERIVED | pass-through of career_dna.career_foundation |
| `player_identity.primary_share_pct` | DERIVED | pass-through of career_dna.career_foundation_share_pct |
| `player_identity.primary_type` | DERIVED | static label looked up from career_dna.career_foundation |
| `player_identity.winning_note` | DERIVED | template sentence built from career_dna.winning_foundation, only when it differs from career_foundation |

### `player_name`

| Path | Label | Reason |
|---|---|---|
| `player_name` | MEASURED | real player name |

### `player_story`

| Path | Label | Reason |
|---|---|---|
| `player_story[].detail` | DERIVED | template sentence embedding real/derived numbers for this milestone |
| `player_story[].label` | MEASURED | static milestone label |
| `player_story[].season` | MEASURED | real season the milestone occurred in |

### `provenance_summary`

| Path | Label | Reason |
|---|---|---|
| `provenance_summary.rows[].count` | DERIVED | count of fields with this classification |
| `provenance_summary.rows[].detail` | MEASURED | fixed translated explanation, not computed from data |
| `provenance_summary.rows[].pct` | DERIVED | that count as a percent of total_fields_checked |
| `provenance_summary.rows[].short` | MEASURED | fixed translated label, not computed from data |
| `provenance_summary.rows[].tier` | MEASURED | fixed trust tier constant, not computed from data |
| `provenance_summary.total_fields_checked` | DERIVED | count of all classified fields in the provenance map |

### `recent_form_10`

| Path | Label | Reason |
|---|---|---|
| `recent_form_10[].game_code` | MEASURED | real tournament id |
| `recent_form_10[].is_top10` | DERIVED | boolean: rank<=10 |
| `recent_form_10[].is_win` | DERIVED | boolean: rank==1 |
| `recent_form_10[].rank` | MEASURED | real final rank |
| `recent_form_10[].season` | MEASURED | real season |
| `recent_form_10[].sg_status` | DERIVED | "COLLECTED"/"NOT_COLLECTED" computed from whether sg_total is present |
| `recent_form_10[].sg_total` | MEASURED | real captured SG Total, or null when not yet collected |
| `recent_form_10[].tournament` | MEASURED | real tournament name |

### `recent_form_20`

| Path | Label | Reason |
|---|---|---|
| `recent_form_20[].game_code` | MEASURED | real tournament id |
| `recent_form_20[].is_top10` | DERIVED | boolean: rank<=10 |
| `recent_form_20[].is_win` | DERIVED | boolean: rank==1 |
| `recent_form_20[].rank` | MEASURED | real final rank |
| `recent_form_20[].season` | MEASURED | real season |
| `recent_form_20[].sg_status` | DERIVED | "COLLECTED"/"NOT_COLLECTED" computed from whether sg_total is present |
| `recent_form_20[].sg_total` | MEASURED | real captured SG Total, or null when not yet collected |
| `recent_form_20[].tournament` | MEASURED | real tournament name |

### `recent_form_5`

| Path | Label | Reason |
|---|---|---|
| `recent_form_5[].game_code` | MEASURED | real tournament id |
| `recent_form_5[].is_top10` | DERIVED | boolean: rank<=10 |
| `recent_form_5[].is_win` | DERIVED | boolean: rank==1 |
| `recent_form_5[].rank` | MEASURED | real final rank |
| `recent_form_5[].season` | MEASURED | real season |
| `recent_form_5[].sg_status` | DERIVED | "COLLECTED"/"NOT_COLLECTED" computed from whether sg_total is present |
| `recent_form_5[].sg_total` | MEASURED | real captured SG Total, or null when not yet collected |
| `recent_form_5[].tournament` | MEASURED | real tournament name |

### `reconciliation`

| Path | Label | Reason |
|---|---|---|
| `reconciliation.conflicts_detected` | MEASURED | count of cross-source field disagreements found |
| `reconciliation.found_in_live` | MEASURED | count found in the Live-snapshot source category |
| `reconciliation.found_in_reader` | MEASURED | count found in the Reader-output source category |
| `reconciliation.found_in_warehouse` | MEASURED | count found in the SG warehouse source category |
| `reconciliation.in_progress_excluded_from_finished_totals` | DERIVED | boolean: whether the in-progress tournament was excluded from the finished-tournament counts above |
| `reconciliation.merged` | DERIVED | count of tournaments whose record was merged across more than one source category |
| `reconciliation.missing` | MEASURED | count of known tournaments reconciliation could not account for at all (0 required for the build to proceed) |
| `reconciliation.resolved[]` | MEASURED | real text describing how each detected conflict was resolved |
| `reconciliation.status` | DERIVED | RECONCILED_OK/other, computed from the counts above |
| `reconciliation.total_tournaments` | MEASURED | count of tournaments reconciliation confirmed across all 7 real source categories |

### `round_history`

| Path | Label | Reason |
|---|---|---|
| `round_history.best_round.game_code` | MEASURED | real tournament id of her single best round |
| `round_history.best_round.round` | MEASURED | real round number |
| `round_history.best_round.season` | MEASURED | real season |
| `round_history.best_round.sg_total` | MEASURED | her real SG Total in that specific round (selected via max) |
| `round_history.best_round.tournament` | MEASURED | real tournament name |
| `round_history.largest_collapse.delta` | DERIVED | the largest negative round-to-round SG Total change within one tournament |
| `round_history.largest_collapse.from_round` | MEASURED | real earlier round number |
| `round_history.largest_collapse.game_code` | MEASURED | real tournament id |
| `round_history.largest_collapse.season` | MEASURED | real season |
| `round_history.largest_collapse.to_round` | MEASURED | real later round number |
| `round_history.largest_collapse.tournament` | MEASURED | real tournament name |
| `round_history.largest_recovery.delta` | DERIVED | the largest positive round-to-round change that immediately follows a negative-SG round |
| `round_history.largest_recovery.from_round` | MEASURED | real earlier round number |
| `round_history.largest_recovery.game_code` | MEASURED | real tournament id, or null if this pattern never occurred |
| `round_history.largest_recovery.season` | MEASURED | real season |
| `round_history.largest_recovery.to_round` | MEASURED | real later round number |
| `round_history.largest_recovery.tournament` | MEASURED | real tournament name |
| `round_history.most_improved_round.delta` | DERIVED | the largest positive round-to-round SG Total change within one tournament |
| `round_history.most_improved_round.from_round` | MEASURED | real earlier round number |
| `round_history.most_improved_round.game_code` | MEASURED | real tournament id |
| `round_history.most_improved_round.season` | MEASURED | real season |
| `round_history.most_improved_round.to_round` | MEASURED | real later round number |
| `round_history.most_improved_round.tournament` | MEASURED | real tournament name |
| `round_history.most_stable_tournament.game_code` | MEASURED | real tournament id |
| `round_history.most_stable_tournament.rounds` | DERIVED | count of real rounds behind the stddev below |
| `round_history.most_stable_tournament.stddev` | DERIVED | population stddev of her real round-level SG Totals in that tournament (only tournaments with >=3 rounds are eligible) |
| `round_history.most_stable_tournament.tournament` | MEASURED | real tournament name |
| `round_history.total_rounds` | DERIVED | count of every real captured round |
| `round_history.worst_round.game_code` | MEASURED | real tournament id of her single worst round |
| `round_history.worst_round.round` | MEASURED | real round number |
| `round_history.worst_round.season` | MEASURED | real season |
| `round_history.worst_round.sg_total` | MEASURED | her real SG Total in that specific round (selected via min) |
| `round_history.worst_round.tournament` | MEASURED | real tournament name |

### `season_replay`

| Path | Label | Reason |
|---|---|---|
| `season_replay[].event_count` | DERIVED | count of that season's finished tournaments |
| `season_replay[].named_windows.first.avg_sg_total` | DERIVED | mean SG Total over that window |
| `season_replay[].named_windows.first.events` | DERIVED | count of tournaments in the season's first window |
| `season_replay[].named_windows.first.label` | MEASURED | static window label |
| `season_replay[].named_windows.first.sg_sample_size` | DERIVED | count of SG-bearing tournaments in that window |
| `season_replay[].named_windows.first.top10` | DERIVED | count of top-10s in that window |
| `season_replay[].named_windows.first.wins` | DERIVED | count of wins in that window |
| `season_replay[].named_windows.last.avg_sg_total` | DERIVED | mean SG Total over that window |
| `season_replay[].named_windows.last.events` | DERIVED | count of tournaments in the season's last window |
| `season_replay[].named_windows.last.label` | MEASURED | static window label |
| `season_replay[].named_windows.last.sg_sample_size` | DERIVED | count of SG-bearing tournaments in that window |
| `season_replay[].named_windows.last.top10` | DERIVED | count of top-10s in that window |
| `season_replay[].named_windows.last.wins` | DERIVED | count of wins in that window |
| `season_replay[].named_windows.middle.avg_sg_total` | DERIVED | mean SG Total over that window |
| `season_replay[].named_windows.middle.events` | DERIVED | count of tournaments in the season's middle window |
| `season_replay[].named_windows.middle.label` | MEASURED | static window label |
| `season_replay[].named_windows.middle.sg_sample_size` | DERIVED | count of SG-bearing tournaments in that window |
| `season_replay[].named_windows.middle.top10` | DERIVED | count of top-10s in that window |
| `season_replay[].named_windows.middle.wins` | DERIVED | count of wins in that window |
| `season_replay[].named_windows.middle_unavailable_reason` | NOT_AVAILABLE | explicit disclosure text: this season has too few tournaments (<15) to isolate a non-overlapping middle window |
| `season_replay[].named_windows.window_size` | MEASURED | fixed config constant (5), not golfer data |
| `season_replay[].peak.sg_total` | MEASURED | her real SG Total in that tournament |
| `season_replay[].peak.tournament` | MEASURED | real name of the season's highest-SG tournament |
| `season_replay[].quartiles[].avg_sg_total` | DERIVED | mean SG Total over that quarter |
| `season_replay[].quartiles[].events` | DERIVED | count of tournaments in that quarter |
| `season_replay[].quartiles[].quarter` | MEASURED | structural index 1-4, not golfer data |
| `season_replay[].recovery_next_event.delta_vs_slump` | DERIVED | recovery_next_event.sg_total minus slump.sg_total |
| `season_replay[].recovery_next_event.sg_total` | MEASURED | her real SG Total in that tournament |
| `season_replay[].recovery_next_event.tournament` | MEASURED | real name of the tournament immediately after the slump |
| `season_replay[].season` | MEASURED | real season |
| `season_replay[].slump.sg_total` | MEASURED | her real SG Total in that tournament |
| `season_replay[].slump.tournament` | MEASURED | real name of the season's lowest-SG tournament |
| `season_replay[].top10_rate_pct` | DERIVED | top10 count / event_count * 100 |
| `season_replay[].volatility_stddev` | DERIVED | population stddev of the season's real SG Total values |

### `status`

| Path | Label | Reason |
|---|---|---|
| `status.data_completeness` | MEASURED | literal "PARTIAL" -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `status.data_completeness_detail.confirmed_available[]` | MEASURED | hand-maintained list of what this repository has confirmed; one line conditionally added when technical_stats_2025 exists |
| `status.data_completeness_detail.note` | MEASURED | fixed disclosure text explaining the local-absence-vs-KLPGA-absence distinction |
| `status.data_completeness_detail.still_locally_absent_source_not_independently_verified[]` | NOT_AVAILABLE | hand-maintained list naming fields never found in this repository's local sources; KLPGA's own live site was never checked (no network access) so this is a local-absence disclosure, not a claim KLPGA itself lacks the field |
| `status.derived_metrics` | MEASURED | literal "PASS" -- a fixed literal asserted in source code, not computed from a live per-run check of the underlying data -- a known governance gap, see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `status.source_conflicts` | DERIVED | PASS/FAIL formula over reconciliation.status/conflicts_detected/missing |

### `technical_stats_2025`

| Path | Label | Reason |
|---|---|---|
| `technical_stats_2025.as_of_note` | DERIVED | disclosure sentence naming the 2025 snapshot |
| `technical_stats_2025.metrics[].denominator` | MEASURED | real captured denominator behind a rate metric |
| `technical_stats_2025.metrics[].denominator_label` | MEASURED | static label for the denominator |
| `technical_stats_2025.metrics[].label` | MEASURED | static metric name |
| `technical_stats_2025.metrics[].measured_rounds` | MEASURED | real count of rounds this metric was captured over |
| `technical_stats_2025.metrics[].measured_rounds_label` | MEASURED | static label for measured_rounds |
| `technical_stats_2025.metrics[].numerator` | MEASURED | real captured numerator behind a rate metric |
| `technical_stats_2025.metrics[].numerator_label` | MEASURED | static label for the numerator |
| `technical_stats_2025.metrics[].rank` | MEASURED | real captured field rank for this metric |
| `technical_stats_2025.metrics[].source_file` | MEASURED | real filename this metric was captured from |
| `technical_stats_2025.metrics[].value` | MEASURED | real captured metric value |
| `technical_stats_2025.metrics[].value_label` | MEASURED | static unit/format label for the value |
| `technical_stats_2025.player_id` | MEASURED | playerCode on the captured record |
| `technical_stats_2025.player_name` | MEASURED | player name on the captured record |
| `technical_stats_2025.schema_version` | MEASURED | schema tag on the captured record |
| `technical_stats_2025.season` | MEASURED | real season this capture covers (2025 only) |
| `technical_stats_2025.source_endpoint` | MEASURED | real KLPGA endpoint this was captured from |

### `tournament_history`

| Path | Label | Reason |
|---|---|---|
| `tournament_history[].game_code` | MEASURED | real tournament id |
| `tournament_history[].is_top10` | DERIVED | boolean: rank<=10 |
| `tournament_history[].is_win` | DERIVED | boolean: rank==1 |
| `tournament_history[].rank` | MEASURED | real final rank, or null when not yet collected |
| `tournament_history[].round_scores[].round` | MEASURED | real round number |
| `tournament_history[].round_scores[].sg_total` | MEASURED | real per-round SG Total |
| `tournament_history[].round_scores[].strokes` | MEASURED | real strokes for this round |
| `tournament_history[].season` | MEASURED | real season |
| `tournament_history[].sg_components` | MEASURED | whole object null when sg_ott is not present -- see the 4 leaf fields below |
| `tournament_history[].sg_components.app` | MEASURED | real captured SG APP for this tournament |
| `tournament_history[].sg_components.arg` | MEASURED | real captured SG ARG for this tournament |
| `tournament_history[].sg_components.ott` | MEASURED | real captured SG OTT for this tournament |
| `tournament_history[].sg_components.putt` | MEASURED | real captured SG PUTT for this tournament |
| `tournament_history[].sg_total` | MEASURED | real captured SG Total, or null when not yet collected (e.g. KB금융 골든라이프 챔피언십 2026090003 -- see not_available) |
| `tournament_history[].tournament` | MEASURED | real tournament name |

### `why_now`

| Path | Label | Reason |
|---|---|---|
| `why_now.arrows[].component` | MEASURED | static component label |
| `why_now.arrows[].delta` | DERIVED | this component's real delta_vs_career_average |
| `why_now.arrows[].direction` | DERIVED | UP/DOWN/FLAT sign of this component's delta_vs_career_average |
| `why_now.lead_component` | DERIVED | the component with the largest-magnitude delta_vs_career_average |
| `why_now.lead_delta` | DERIVED | that component's real delta_vs_career_average |
| `why_now.sentence` | DERIVED | template sentence naming lead_component and its sign |

## Player Intelligence Report (build_10097_player_intelligence_report.py)

182 classified fields.

| Label | Count |
|---|---|
| MEASURED | 61 |
| DERIVED | 117 |
| IMPUTED | 0 |
| NOT_COLLECTED | 4 |
| NOT_AVAILABLE | 0 |

### `career_reconstruction`

| Path | Label | Reason |
|---|---|---|
| `career_reconstruction.data_floor_note` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `career_reconstruction.earliest_season_on_record` | MEASURED | earliest season this shared warehouse has any data for |
| `career_reconstruction.latest_season_on_record` | MEASURED | latest season this shared warehouse has any data for |
| `career_reconstruction.season_count_on_record` | DERIVED | count of real seasons on record |
| `career_reconstruction.summary` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `career_reconstruction.total_events_on_record` | DERIVED | count of real tournament events on record |
| `career_reconstruction.total_top10_on_record` | DERIVED | count of real rank<=10 finishes on record |
| `career_reconstruction.total_wins_on_record` | DERIVED | count of real rank==1 finishes on record |

### `coach_console`

| Path | Label | Reason |
|---|---|---|
| `coach_console.entries[].category` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `coach_console.entries[].decision` | DERIVED | extracted from the source question's own real action/conclusion field |
| `coach_console.entries[].question` | MEASURED | fixed Korean question text for this question id |
| `coach_console.entries[].question_id` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |

### `coach_report`

| Path | Label | Reason |
|---|---|---|
| `coach_report.development_priority` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `coach_report.development_priority_source` | DERIVED | pointer to which real turning_points entry this priority came from, or null |
| `coach_report.trajectory_verdict` | DERIVED | deterministic classification over a real count of consecutive positive/negative season deltas |

### `data_roadmap`

| Path | Label | Reason |
|---|---|---|
| `data_roadmap[].collection_method` | MEASURED | fixed authored text describing how it could be collected |
| `data_roadmap[].id` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `data_roadmap[].missing_data` | MEASURED | fixed authored text naming the specific missing data type |
| `data_roadmap[].priority_rank` | DERIVED | rank among all roadmap items by that real count (argsort) |
| `data_roadmap[].unlocks[]` | MEASURED | fixed authored list of report sections this data would unlock |
| `data_roadmap[].value` | DERIVED | real count of this item's own unlocks list |
| `data_roadmap[].why_missing` | MEASURED | fixed authored text explaining why it is missing |

### `growth_timeline`

| Path | Label | Reason |
|---|---|---|
| `growth_timeline.narrative` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `growth_timeline.steps[].avg_total` | DERIVED | that season's real SG Total average |
| `growth_timeline.steps[].delta_from_prev` | DERIVED | season-to-season change vs the previous real season's average |
| `growth_timeline.steps[].season` | MEASURED | real season label |
| `growth_timeline.steps[].strongest_component` | DERIVED | the SG component with this season's highest real average (argmax) |
| `growth_timeline.steps[].weakest_component` | DERIVED | the SG component with this season's lowest real average (argmin) |

### `leak_map`

| Path | Label | Reason |
|---|---|---|
| `leak_map.leaks[].coach_decision` | DERIVED | extracted from the linked question's own real action field, or a fixed sentence |
| `leak_map.leaks[].performance_loss` | DERIVED | either a real formatted delta pulled from the linked question's monitoring_protocol.current_reading, or an explicit disclosed "알 수 없음" (unknown) when no real join exists between the two real numbers this would require -- see data_roadmap.collapse_onset_loss_join |
| `leak_map.leaks[].priority` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `leak_map.leaks[].question_id` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `leak_map.leaks[].where` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `leak_map.leaks[].why` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |

### `loss_dna`

| Path | Label | Reason |
|---|---|---|
| `loss_dna.breakdown[].component` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `loss_dna.breakdown[].share_pct` | DERIVED | value divided by total_value, as a percent |
| `loss_dna.breakdown[].value` | DERIVED | sum of this component's real values across those losses |
| `loss_dna.events_considered` | DERIVED | count of real negative-SG events considered |
| `loss_dna.sample_size` | DERIVED | count of real negative-SG events with complete SG components |
| `loss_dna.story` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `loss_dna.top_contributor` | DERIVED | the component with the largest real share_pct (argmax) |
| `loss_dna.total_value` | DERIVED | sum of real SG Total across those losses |

### `performance_funnel`

| Path | Label | Reason |
|---|---|---|
| `performance_funnel.competition.label` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `performance_funnel.competition.note` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `performance_funnel.competition.question` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `performance_funnel.competition.top10_events` | DERIVED | count of real rank<=10 finishes |
| `performance_funnel.competition.total_events` | DERIVED | count of real finished tournaments |
| `performance_funnel.conversion.birdie_rate.percentile` | DERIVED | her real rank among the full official field with a birdie rate on file |
| `performance_funnel.conversion.birdie_rate.raw` | MEASURED | real official birdie rate |
| `performance_funnel.conversion.label` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `performance_funnel.conversion.note` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `performance_funnel.conversion.par_save_rate.percentile` | DERIVED | her real rank among the full official field with a par-save rate on file |
| `performance_funnel.conversion.par_save_rate.raw` | MEASURED | real official par-save rate |
| `performance_funnel.conversion.question` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `performance_funnel.conversion.recovery_rate.percentile` | DERIVED | her real rank among the full official field with a recovery rate on file |
| `performance_funnel.conversion.recovery_rate.raw` | MEASURED | real official recovery rate |
| `performance_funnel.opportunity.gir_rate.percentile` | DERIVED | her real rank among the full official field with a GIR rate on file |
| `performance_funnel.opportunity.gir_rate.raw` | MEASURED | real official GIR rate from OFFICIAL_PROFILE_NORMALIZED.json |
| `performance_funnel.opportunity.label` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `performance_funnel.opportunity.note` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `performance_funnel.opportunity.question` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `performance_funnel.technique.label` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `performance_funnel.technique.note` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `performance_funnel.technique.percentiles.SG APP` | DERIVED | her real percentile for this component, computed upstream |
| `performance_funnel.technique.percentiles.SG ARG` | DERIVED | her real percentile for this component, computed upstream |
| `performance_funnel.technique.percentiles.SG OTT` | DERIVED | her real percentile for this component, computed upstream (frozen Knowledge Engine) |
| `performance_funnel.technique.percentiles.SG PUTT` | DERIVED | her real percentile for this component, computed upstream |
| `performance_funnel.technique.question` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `performance_funnel.technique.weakest.component` | DERIVED | the component with the lowest real percentile (argmin) |
| `performance_funnel.technique.weakest.percentile` | DERIVED | that component's real percentile |
| `performance_funnel.winning.label` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `performance_funnel.winning.note` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `performance_funnel.winning.question` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `performance_funnel.winning.top10_events` | DERIVED | pass-through of competition.top10_events |
| `performance_funnel.winning.win_events` | DERIVED | count of real rank==1 finishes |

### `player_id`

| Path | Label | Reason |
|---|---|---|
| `player_id` | MEASURED | playerCode constant identifying this golfer |

### `player_identity`

| Path | Label | Reason |
|---|---|---|
| `player_identity.constant_strength` | DERIVED | the SG component that was her strongest in every real season, or null if it varied |
| `player_identity.constant_strength_finding` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `player_identity.constant_strength_seasons` | DERIVED | count of real seasons behind that check |
| `player_identity.identity_win_alignment.finding` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `player_identity.identity_win_alignment.identity_strength` | DERIVED | pass-through of constant_strength |
| `player_identity.identity_win_alignment.matches` | DERIVED | boolean: whether identity_strength equals win_strength |
| `player_identity.identity_win_alignment.win_strength` | DERIVED | pass-through of win_dna.top_contributor |

### `player_name`

| Path | Label | Reason |
|---|---|---|
| `player_name` | MEASURED | real player name |

### `player_playbook`

| Path | Label | Reason |
|---|---|---|
| `player_playbook.entries[].category` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `player_playbook.entries[].decision` | DERIVED | extracted from the source question's own real action/conclusion field |
| `player_playbook.entries[].question` | MEASURED | fixed Korean question text for this question id |
| `player_playbook.entries[].question_id` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |

### `pre_tournament_checklist`

| Path | Label | Reason |
|---|---|---|
| `pre_tournament_checklist[].current_reading` | DERIVED | pass-through of the linked question's own monitoring_protocol.current_reading -- see that field's own entry below for the one known exception |
| `pre_tournament_checklist[].current_status` | DERIVED | pass-through of the linked question's own monitoring_protocol.current_status |
| `pre_tournament_checklist[].id` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `pre_tournament_checklist[].linked_question` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `pre_tournament_checklist[].metric` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |

### `questions`

| Path | Label | Reason |
|---|---|---|
| `questions[].action` | DERIVED | template string assembling the real monitoring_protocol fields plus a fixed decision sentence |
| `questions[].analysis` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `questions[].coach_focus` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `questions[].conclusion` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `questions[].confidence` | DERIVED | a real deterministic threshold rule over sample_size for most question types; a fixed constant for a few (most_recent_win/win_simulator/risk_map/collapse_blueprint) -- see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `questions[].contribution_breakdown` | DERIVED | whole object null when the underlying rows don't support a valid split -- see the leaf fields below |
| `questions[].contribution_breakdown.breakdown[].component` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `questions[].contribution_breakdown.breakdown[].share_pct` | DERIVED | value divided by total_value, as a percent |
| `questions[].contribution_breakdown.breakdown[].value` | DERIVED | sum of this component's real values across those rows |
| `questions[].contribution_breakdown.sample_size` | DERIVED | count of real rows with all 4 SG components + total present |
| `questions[].contribution_breakdown.top_contributor` | DERIVED | the component with the largest real share_pct (argmax) |
| `questions[].contribution_breakdown.total_value` | DERIVED | sum of real SG Total across those rows |
| `questions[].decision_context` | NOT_COLLECTED | explicit disclosure that the real strategic decision (club/line selection) is unknown -- no such data exists in this repository |
| `questions[].durability` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `questions[].durability_reasoning` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `questions[].evidence[]` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `questions[].evidence_score` | DERIVED | disclosed formula: round(100 * min(1, sources/3) * n/(n+5)) over real sample_size/source count |
| `questions[].fact` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `questions[].floor_total` | DERIVED | min() of real SG Total across her real win rows |
| `questions[].floors.approach` | DERIVED | min() of real SG APP across her real win rows |
| `questions[].floors.around_green` | DERIVED | min() of real SG ARG across her real win rows |
| `questions[].floors.off_the_tee` | DERIVED | min() of real SG OTT across her real win rows |
| `questions[].floors.putting` | DERIVED | min() of real SG PUTT across her real win rows |
| `questions[].id` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `questions[].layer` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `questions[].mechanism` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `questions[].monitoring_protocol.current_detail` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `questions[].monitoring_protocol.current_reading` | DERIVED | her most recent real value for this metric for most question types (or a disclosed real formula, e.g. latest-minus-floor for win_simulator) -- ONE NAMED EXCEPTION: for id=q_win_blueprint, this falls back to the already-derived floor_total when the true most-recent-win row is missing from the warehouse lookup, an undisclosed-in-JSON IMPUTED substitution -- see docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md |
| `questions[].monitoring_protocol.current_status` | DERIVED | a real comparison of current_reading against normal_range/warning_threshold for most question types; a fixed literal "NORMAL" for q_win_blueprint specifically (mathematically always true by construction, but not run through the real comparison every other question uses) |
| `questions[].monitoring_protocol.explanatory_metric` | DERIVED | a real Pearson correlation among her 4 SG components when the sample is large enough to trust one (season/course-appearance grain explicitly discloses an insufficient-sample "알 수 없음" instead of a false correlation) |
| `questions[].monitoring_protocol.metric` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `questions[].monitoring_protocol.next_review` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `questions[].monitoring_protocol.normal_range` | DERIVED | real mean +/- 1 stdev (n>=30) or real min()..max() (n<30) over her own real history |
| `questions[].monitoring_protocol.sample_size` | DERIVED | count of real rows behind this protocol |
| `questions[].monitoring_protocol.source` | MEASURED | fixed string naming the real warehouse file this metric is drawn from |
| `questions[].monitoring_protocol.warning_threshold` | DERIVED | text encoding the same real band/floor rule as normal_range |
| `questions[].player_takeaway` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `questions[].question` | MEASURED | fixed Korean question text, PLAYER_NAME interpolated |
| `questions[].reproducibility` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `questions[].root_cause` | DERIVED | sentence stating the real finding, several explicitly disclosing that a deeper cause cannot be determined from this repository's data (no hole/shot-level source) |
| `questions[].sample_size` | DERIVED | a real count, or a real min() over real per-question rows depending on question type |
| `questions[].why_it_matters` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `questions[].why_this_matters` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |

### `questions_considered_but_unsupported`

| Path | Label | Reason |
|---|---|---|
| `questions_considered_but_unsupported[].confidence` | DERIVED | pass-through of the excluded candidate's own real confidence |
| `questions_considered_but_unsupported[].id` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `questions_considered_but_unsupported[].question` | MEASURED | fixed Korean question text |
| `questions_considered_but_unsupported[].reason_excluded` | DERIVED | template text wrapping the real confidence/sample_size check that excluded this candidate |
| `questions_considered_but_unsupported[].sample_size` | DERIVED | pass-through of the excluded candidate's own real sample_size |

### `repository_intelligence_v7`

| Path | Label | Reason |
|---|---|---|
| `repository_intelligence_v7.conclusions_strengthened_count` | DERIVED | count of real conclusions that search actually strengthened (0 for this player, per the summary) |
| `repository_intelligence_v7.findings[].branch` | MEASURED | real, hand-transcribed git branch name from that separate search |
| `repository_intelligence_v7.findings[].file` | MEASURED | real, hand-transcribed file location from that separate search |
| `repository_intelligence_v7.findings[].id` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `repository_intelligence_v7.findings[].label` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `repository_intelligence_v7.findings[].player_specific_number_found` | NOT_COLLECTED | whether that separate cross-repository search turned up a real number for this specific player -- consistently absent for this player per this file's own summary |
| `repository_intelligence_v7.search_scope` | MEASURED | fixed text describing a separate cross-repository search mission's real scope |
| `repository_intelligence_v7.summary` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |

### `season_by_season_table`

| Path | Label | Reason |
|---|---|---|
| `season_by_season_table[].avg_app` | DERIVED | mean SG APP across that season's real tournaments |
| `season_by_season_table[].avg_arg` | DERIVED | mean SG ARG across that season's real tournaments |
| `season_by_season_table[].avg_ott` | DERIVED | mean SG OTT across that season's real tournaments |
| `season_by_season_table[].avg_putt` | DERIVED | mean SG PUTT across that season's real tournaments |
| `season_by_season_table[].avg_total` | DERIVED | mean SG Total across that season's real tournaments, computed by knowledge_engine.compute_season_profiles |
| `season_by_season_table[].events_on_record` | DERIVED | count of real events that season |
| `season_by_season_table[].season` | MEASURED | real season label |
| `season_by_season_table[].sg_sample_size` | DERIVED | count of tournaments behind that season's SG averages |
| `season_by_season_table[].top10` | DERIVED | count of real top-10s that season |
| `season_by_season_table[].wins` | DERIVED | count of real wins that season |

### `trend_dna`

| Path | Label | Reason |
|---|---|---|
| `trend_dna.breakdown[].component` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `trend_dna.breakdown[].share_pct` | DERIVED | value divided by total_value, as a percent |
| `trend_dna.breakdown[].value` | DERIVED | this component's real average delta between the two seasons |
| `trend_dna.from_season` | MEASURED | earliest real season on record |
| `trend_dna.story` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `trend_dna.to_season` | MEASURED | latest real season on record |
| `trend_dna.top_contributor` | DERIVED | the component with the largest real share_pct (argmax) |
| `trend_dna.total_value` | DERIVED | SG Total average delta between those two real seasons |

### `turning_points`

| Path | Label | Reason |
|---|---|---|
| `turning_points[].finding` | DERIVED | sentence built from a real argmax delta or a real detected component-weakness change |
| `turning_points[].id` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `turning_points[].label` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `turning_points[].season` | MEASURED | real season the turning point occurred in |
| `turning_points[].unknown_cause` | NOT_COLLECTED | explicit disclosure: the deeper cause (coaching/training change) cannot be determined -- no such log exists in this repository yet (see data_roadmap) |

### `unsupported_analysis_modules_v12`

| Path | Label | Reason |
|---|---|---|
| `unsupported_analysis_modules_v12[].module` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `unsupported_analysis_modules_v12[].reason` | NOT_COLLECTED | explicit disclosure that the hole/shot/pin/distance-level data this module would need does not exist anywhere in this repository's warehouse |

### `win_dna`

| Path | Label | Reason |
|---|---|---|
| `win_dna.breakdown[].component` | MEASURED | a fixed label/id/category constant baked into this file's source code -- asserted, not computed from this run's data |
| `win_dna.breakdown[].share_pct` | DERIVED | value divided by total_value, as a percent |
| `win_dna.breakdown[].value` | DERIVED | sum of this component's real values across those wins |
| `win_dna.events_considered` | DERIVED | count of real win events considered |
| `win_dna.sample_size` | DERIVED | count of real win events with complete SG components |
| `win_dna.story` | DERIVED | a deterministic Korean sentence template wrapping already-computed real numbers -- the template itself never introduces a new number |
| `win_dna.top_contributor` | DERIVED | the component with the largest real share_pct (argmax) |
| `win_dna.total_value` | DERIVED | sum of real SG Total across those wins |

