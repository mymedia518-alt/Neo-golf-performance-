# NEO Missing Data Report V1

**Mission V10 (2026-09-25), playerCode=10097 only.** Every field currently classified NOT_COLLECTED or NOT_AVAILABLE across Player History and Player Intelligence, generated directly from the live provenance maps -- and the pre-existing free-text `not_available` disclosure list Player History has carried since the original RED TEAM mission, for cross-reference.

## Player History

16 of 637 classified fields (2.5%) are a disclosed gap, not a real value.

| Path | Label | Reason |
|---|---|---|
| `career_rolling_trend.peak_window.decomposition.birdie` | NOT_AVAILABLE | real hole-level birdie count when this window overlaps the one hole-covered tournament; that has never yet happened for a finished window, so this is always null in this build |
| `career_rolling_trend.peak_window.decomposition.bogey` | NOT_AVAILABLE | same as birdie above |
| `career_rolling_trend.peak_window.decomposition.gir` | NOT_AVAILABLE | the one hole-level source that exists (hole_history) never captured GIR at all -- always null regardless of window overlap |
| `career_rolling_trend.peak_window.decomposition.putts` | NOT_AVAILABLE | the one hole-level source that exists (hole_history) never captured putts-per-hole at all -- always null regardless of window overlap |
| `career_rolling_trend.recovery_window.decomposition.birdie` | NOT_AVAILABLE | real hole-level birdie count when this window overlaps the one hole-covered tournament; that has never yet happened for a finished window, so this is always null in this build |
| `career_rolling_trend.recovery_window.decomposition.bogey` | NOT_AVAILABLE | same as birdie above |
| `career_rolling_trend.recovery_window.decomposition.gir` | NOT_AVAILABLE | the one hole-level source that exists (hole_history) never captured GIR at all -- always null regardless of window overlap |
| `career_rolling_trend.recovery_window.decomposition.putts` | NOT_AVAILABLE | the one hole-level source that exists (hole_history) never captured putts-per-hole at all -- always null regardless of window overlap |
| `career_rolling_trend.slump_window.decomposition.birdie` | NOT_AVAILABLE | real hole-level birdie count when this window overlaps the one hole-covered tournament; that has never yet happened for a finished window, so this is always null in this build |
| `career_rolling_trend.slump_window.decomposition.bogey` | NOT_AVAILABLE | same as birdie above |
| `career_rolling_trend.slump_window.decomposition.gir` | NOT_AVAILABLE | the one hole-level source that exists (hole_history) never captured GIR at all -- always null regardless of window overlap |
| `career_rolling_trend.slump_window.decomposition.putts` | NOT_AVAILABLE | the one hole-level source that exists (hole_history) never captured putts-per-hole at all -- always null regardless of window overlap |
| `hole_history.capture_note` | NOT_AVAILABLE | fixed disclosure text: this is the only hole-level source anywhere in this repository for this player |
| `not_available[]` | NOT_AVAILABLE | each entry is itself a disclosure of a genuinely unavailable field -- the field's own text IS the provenance answer |
| `season_replay[].named_windows.middle_unavailable_reason` | NOT_AVAILABLE | explicit disclosure text: this season has too few tournaments (<15) to isolate a non-overlapping middle window |
| `status.data_completeness_detail.still_locally_absent_source_not_independently_verified[]` | NOT_AVAILABLE | hand-maintained list naming fields never found in this repository's local sources; KLPGA's own live site was never checked (no network access) so this is a local-absence disclosure, not a claim KLPGA itself lacks the field |

## Player Intelligence Report

4 of 182 classified fields (2.2%) are a disclosed gap, not a real value.

| Path | Label | Reason |
|---|---|---|
| `questions[].decision_context` | NOT_COLLECTED | explicit disclosure that the real strategic decision (club/line selection) is unknown -- no such data exists in this repository |
| `repository_intelligence_v7.findings[].player_specific_number_found` | NOT_COLLECTED | whether that separate cross-repository search turned up a real number for this specific player -- consistently absent for this player per this file's own summary |
| `turning_points[].unknown_cause` | NOT_COLLECTED | explicit disclosure: the deeper cause (coaching/training change) cannot be determined -- no such log exists in this repository yet (see data_roadmap) |
| `unsupported_analysis_modules_v12[].reason` | NOT_COLLECTED | explicit disclosure that the hole/shot/pin/distance-level data this module would need does not exist anywhere in this repository's warehouse |

## Known governance gaps (not missing data -- unverified assertions)

These fields are classified MEASURED (a real factual assertion exists), but nothing in the pipeline currently re-verifies them against this specific run's actual data -- they are hand-authored constants that could silently drift from reality. Not a data gap, but a real governance gap this audit surfaced and did not fix (fixing it would mean writing a live presence-check, out of scope for an audit mission).

82 fields, 2 distinct top-level groups (dominated by `coverage_matrix.rows`'s 76 hand-authored cells).

Non-`coverage_matrix.rows` examples:

- `status.data_completeness`
- `status.derived_metrics`

Plus all 76 `coverage_matrix.rows.<metric>.<season>` cells (19 metrics x 4 seasons) -- see the full provenance report for the complete list.

## Player History's existing free-text disclosure list (`not_available`)

Carried since the original RED TEAM tournament-ordering mission, predating this audit -- listed here for cross-reference since it names the same real gaps in prose rather than as JSON paths.

- 과거 시즌별 상금: 2026시즌 스냅샷 1건만 실측되어 있습니다. NEO가 과거 시즌분을 아직 수집하지 않았습니다.
- 과거 시즌별 평균 스코어: 2026시즌 스냅샷 1건만 실측되어 있습니다. NEO가 과거 시즌분을 아직 수집하지 않았습니다.
- 과거 시즌별 GIR·퍼트·버디율: 2026시즌 스냅샷 1건만 실측되어 있습니다. NEO가 과거 시즌분을 아직 수집하지 않았습니다.
- 보기율(Bogey %): NEO가 아직 수집하지 않았습니다 (KLPGA가 게시하는지는 이 세션의 네트워크 차단으로 확인하지 못했습니다).
- 전반·후반 9홀 분할 스코어: NEO가 아직 수집하지 않았습니다 (KLPGA가 게시하는지는 이 세션의 네트워크 차단으로 확인하지 못했습니다).
- 대회별 코스명: 극히 일부 대회만 실측되어 전체 커버리지가 없습니다.
- 라운드 중 순위 변동(일자별 순위 이동): NEO가 아직 수집하지 않았습니다 (KLPGA가 게시하는지는 이 세션의 네트워크 차단으로 확인하지 못했습니다).
- KB금융 골든라이프 챔피언십(2026090003)의 Strokes Gained: 최종 순위와 라운드별 스코어는 실측되었지만, 이 대회의 SG 데이터는 NEO가 아직 수집하지 않았습니다 (KLPGA 자체 strokesGained 페이지 URL은 이 대회 리더보드에서 실제로 확인되었습니다).
- 시즌별 컷 통과율: 내부 저장소의 made_cut 필드가 2023시즌 표본(7건)만 있어 다른 모든 실측 소스가 확인하는 2023시즌 25개 대회와 맞지 않아 신뢰할 수 없어 사용하지 않습니다.

