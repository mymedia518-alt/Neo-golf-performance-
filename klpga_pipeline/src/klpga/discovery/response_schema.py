"""Phase B1 — response-schema analysis over an already-parsed
`ParsedRecordResponse` (see response_parser.py). Pure functions, no
network access. Column "kind" (RATE/COUNT/ROUNDS/DISTANCE/AVERAGE/RTP)
is INFERRED from explicit Korean label text found in the response
itself — never from column position alone, and never promoted to
CONFIRMED without a labeled source backing it.

PIT status is a hardcoded constant everywhere in this module
(`PIT_STATUS = "PIT_UNVERIFIED"`) — per explicit instruction, nothing
in Phase B1 may classify a metric as PIT-safe merely because a season
parameter happened to work.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from klpga.discovery.response_parser import ColumnSemantics, ParsedRecordResponse, PlayerRecordRow

PIT_STATUS = "PIT_UNVERIFIED"
"""The only PIT classification Phase B1 is allowed to emit. See module
docstring — this is a hardcoded constant, not a computed value, by
design."""

KIND_SG = "SG"
KIND_PERCENTAGE = "PERCENTAGE"
KIND_RATE = "RATE"
KIND_COUNT = "COUNT"
KIND_PUTT_COUNT = "PUTT_COUNT"
KIND_ROUNDS = "ROUNDS"
KIND_DISTANCE = "DISTANCE"
KIND_AVERAGE = "AVERAGE"
KIND_RTP = "RTP"
KIND_TEXT = "TEXT"
KIND_OTHER_NUMERIC = "OTHER_NUMERIC"
KIND_UNKNOWN = "UNKNOWN"
"""Expanded primary-value type taxonomy (Phase B1). KIND_SG/KIND_PUTT_COUNT/
KIND_TEXT/KIND_OTHER_NUMERIC exist as classification capability only —
per evidence discipline, a kind is only ever emitted when a real label
keyword backs it; nothing here is a guess about a metric this session
has not seen a labeled column for."""

_RTP_RE = re.compile(r"\brtp\b", re.IGNORECASE)
_SG_RE = re.compile(r"\bsg\b", re.IGNORECASE)


def classify_column_kind(label: Optional[str]) -> str:
    """INFERRED from explicit label text only — never from position.
    Priority order matters — most specific keyword families are
    checked before broader ones so e.g. "측정 라운드" isn't accidentally
    classified as a rate, and "1퍼트 횟수" isn't classified as a plain
    COUNT indistinguishable from an unrelated shot-attempt count."""
    if not label:
        return KIND_UNKNOWN
    if _RTP_RE.search(label):
        return KIND_RTP
    if _SG_RE.search(label):
        return KIND_SG
    if "라운드" in label:
        return KIND_ROUNDS
    if "퍼트" in label and ("횟수" in label or "카운트" in label):
        return KIND_PUTT_COUNT
    if "%" in label:
        return KIND_PERCENTAGE
    if label.endswith("률") or "비율" in label:
        return KIND_RATE
    if "횟수" in label or "카운트" in label:
        return KIND_COUNT
    if "거리" in label or "야드" in label:
        return KIND_DISTANCE
    if "평균" in label:
        return KIND_AVERAGE
    if "구분" in label or "상태" in label or "유형" in label:
        return KIND_TEXT
    return KIND_UNKNOWN


_RATE_KINDS = (KIND_RATE, KIND_PERCENTAGE)
"""RATE and PERCENTAGE are distinguished for classification/reporting
(explicit "%" unit vs. a bare "률"/"비율" label), but for raw-pair
numerator/denominator detection and range validation they are the same
underlying value shape — both are checked together wherever this
module previously checked KIND_RATE alone."""


def build_schema_fingerprint(column_semantics: list[ColumnSemantics]) -> str:
    """Deterministic fingerprint from the ORDERED sequence of column
    kinds (skipping columns with no value/label at all). Two metrics
    with structurally identical columns get the same fingerprint —
    used to cluster the sample into response-schema families."""
    kinds = [classify_column_kind(c.label) for c in column_semantics if c.label]
    if not kinds:
        return "EMPTY_SCHEMA"
    return "_".join(kinds)


@dataclass
class RateValidationResult:
    numerator_field: str
    denominator_field: str
    checked_rows: int
    matches_within_tolerance: int
    max_abs_difference: Optional[float]
    """Largest |official_rate - numerator/denominator*100| observed —
    None if no row had both a parseable rate and both counts."""


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


@dataclass
class RawPairAnalysis:
    status: str
    """CONFIRMED_RAW_PAIR | PARTIAL_RAW_PAIR | RATE_ONLY | COUNT_ONLY |
    NOT_APPLICABLE | UNKNOWN"""
    rate_field: Optional[str] = None
    numerator_field: Optional[str] = None
    denominator_field: Optional[str] = None
    validation: Optional[RateValidationResult] = None


def analyze_raw_pair(
    column_semantics: list[ColumnSemantics], rows: list[PlayerRecordRow], tolerance: float = 0.5
) -> RawPairAnalysis:
    """Never recomputes and silently replaces the official percentage
    — only validates it against numerator/denominator when both exist,
    and reports the difference. `tolerance` is a percentage-point
    tolerance for ordinary rounding, not a data-correction mechanism."""
    if not column_semantics or all(c.source == "unknown" for c in column_semantics):
        return RawPairAnalysis(status="UNKNOWN")

    rate_fields = [c.field_name for c in column_semantics if classify_column_kind(c.label) in _RATE_KINDS]
    count_fields = [c.field_name for c in column_semantics if classify_column_kind(c.label) == KIND_COUNT]

    if not rate_fields and not count_fields:
        return RawPairAnalysis(status="NOT_APPLICABLE")
    if rate_fields and not count_fields:
        return RawPairAnalysis(status="RATE_ONLY", rate_field=rate_fields[0])
    if count_fields and not rate_fields:
        return RawPairAnalysis(status="COUNT_ONLY")
    if len(count_fields) == 1:
        return RawPairAnalysis(status="PARTIAL_RAW_PAIR", rate_field=rate_fields[0], numerator_field=count_fields[0])

    # >= 2 count-kind fields + a rate field: assume ordering
    # numerator-then-denominator (the field appearing first among the
    # two, in column order) — an INFERRED assumption, verified below
    # against the displayed rate wherever possible.
    rate_field = rate_fields[0]
    numerator_field, denominator_field = count_fields[0], count_fields[1]

    checked = 0
    matched = 0
    max_diff: Optional[float] = None
    for row in rows:
        rate = _to_float(row.values.get(rate_field))
        num = _to_float(row.values.get(numerator_field))
        den = _to_float(row.values.get(denominator_field))
        if rate is None or num is None or den is None or den == 0:
            continue
        checked += 1
        calculated = num / den * 100
        diff = abs(calculated - rate)
        max_diff = diff if max_diff is None else max(max_diff, diff)
        if diff <= tolerance:
            matched += 1

    validation = RateValidationResult(
        numerator_field=numerator_field,
        denominator_field=denominator_field,
        checked_rows=checked,
        matches_within_tolerance=matched,
        max_abs_difference=max_diff,
    )

    return RawPairAnalysis(
        status="CONFIRMED_RAW_PAIR",
        rate_field=rate_field,
        numerator_field=numerator_field,
        denominator_field=denominator_field,
        validation=validation,
    )


@dataclass
class SampleSizeField:
    sample_size_type: str
    """The column's own label, verbatim — distinct types are NEVER
    merged (e.g. "측정 라운드" and "샷 시도 횟수" stay separate, per
    explicit instruction: 74% over 20 attempts must stay
    distinguishable from 74% over 220 attempts, and neither is
    conflated with a rounds-played count)."""
    field_name: str
    example_values: list[str] = field(default_factory=list)


def detect_sample_size_fields(column_semantics: list[ColumnSemantics], rows: list[PlayerRecordRow]) -> list[SampleSizeField]:
    results = []
    for c in column_semantics:
        kind = classify_column_kind(c.label)
        if kind not in (KIND_COUNT, KIND_ROUNDS):
            continue
        examples = [row.values.get(c.field_name) for row in rows[:3] if row.values.get(c.field_name)]
        results.append(SampleSizeField(sample_size_type=c.label, field_name=c.field_name, example_values=examples))
    return results


def detect_rtp_status(column_semantics: list[ColumnSemantics], rows: list[PlayerRecordRow]) -> tuple[str, Optional[str]]:
    """Returns (status, example_value). Never treats RTP as SG or any
    other metric — this only reports whether an explicitly RTP-labeled
    column is present and, if so, one example value exactly as shown."""
    if not column_semantics:
        return "RTP_UNKNOWN", None
    rtp_fields = [c for c in column_semantics if classify_column_kind(c.label) == KIND_RTP]
    if not rtp_fields:
        if all(c.source == "unknown" for c in column_semantics):
            return "RTP_UNKNOWN", None
        return "RTP_ABSENT", None
    field_name = rtp_fields[0].field_name
    example = next((row.values.get(field_name) for row in rows if row.values.get(field_name)), None)
    return "RTP_PRESENT", example


@dataclass
class DataQualityFlags:
    duplicate_player_rows: int = 0
    missing_player_code: int = 0
    missing_player_name: int = 0
    non_numeric_numeric_fields: int = 0
    blank_values: int = 0
    duplicate_ranks: int = 0
    percentage_out_of_range: int = 0
    successes_exceed_attempts: int = 0
    negative_counts: int = 0
    non_positive_measured_rounds: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def any_flagged(self) -> bool:
        return any(
            [
                self.duplicate_player_rows,
                self.missing_player_code,
                self.missing_player_name,
                self.non_numeric_numeric_fields,
                self.blank_values,
                self.duplicate_ranks,
                self.percentage_out_of_range,
                self.successes_exceed_attempts,
                self.negative_counts,
                self.non_positive_measured_rounds,
            ]
        )


def run_data_quality_checks(
    column_semantics: list[ColumnSemantics], rows: list[PlayerRecordRow], raw_pair: RawPairAnalysis
) -> DataQualityFlags:
    flags = DataQualityFlags()

    seen_codes: set[str] = set()
    seen_ranks: dict[str, int] = {}
    numeric_fields = {c.field_name for c in column_semantics if classify_column_kind(c.label) != KIND_UNKNOWN}
    rate_fields = {c.field_name for c in column_semantics if classify_column_kind(c.label) in _RATE_KINDS}
    rounds_fields = {c.field_name for c in column_semantics if classify_column_kind(c.label) == KIND_ROUNDS}
    count_fields = {c.field_name for c in column_semantics if classify_column_kind(c.label) == KIND_COUNT}

    for row in rows:
        if row.player_code is not None:
            if row.player_code in seen_codes:
                flags.duplicate_player_rows += 1
            seen_codes.add(row.player_code)
        else:
            flags.missing_player_code += 1

        if row.player_name is None:
            flags.missing_player_name += 1

        if row.rank is not None:
            seen_ranks[row.rank] = seen_ranks.get(row.rank, 0) + 1

        for field_name, value in row.values.items():
            if value == "":
                flags.blank_values += 1
                continue
            if field_name not in numeric_fields or value is None:
                continue
            parsed = _to_float(value)
            if parsed is None:
                flags.non_numeric_numeric_fields += 1
                continue
            if field_name in rate_fields and not (0 <= parsed <= 100):
                flags.percentage_out_of_range += 1
            if field_name in (rounds_fields | count_fields) and parsed < 0:
                flags.negative_counts += 1
            if field_name in rounds_fields and parsed <= 0:
                flags.non_positive_measured_rounds += 1

        if raw_pair.status == "CONFIRMED_RAW_PAIR" and raw_pair.numerator_field and raw_pair.denominator_field:
            num = _to_float(row.values.get(raw_pair.numerator_field))
            den = _to_float(row.values.get(raw_pair.denominator_field))
            if num is not None and den is not None and num > den:
                flags.successes_exceed_attempts += 1

    flags.duplicate_ranks = sum(1 for count in seen_ranks.values() if count > 1)

    return flags


@dataclass
class MetricSchemaAnalysis:
    schema_fingerprint: str
    raw_pair: RawPairAnalysis
    sample_size_fields: list[SampleSizeField]
    rtp_status: str
    rtp_example_value: Optional[str]
    data_quality: DataQualityFlags
    pit_status: str = PIT_STATUS


def analyze_response(parsed: ParsedRecordResponse) -> MetricSchemaAnalysis:
    fingerprint = build_schema_fingerprint(parsed.column_semantics)
    raw_pair = analyze_raw_pair(parsed.column_semantics, parsed.rows)
    sample_size_fields = detect_sample_size_fields(parsed.column_semantics, parsed.rows)
    rtp_status, rtp_example = detect_rtp_status(parsed.column_semantics, parsed.rows)
    data_quality = run_data_quality_checks(parsed.column_semantics, parsed.rows, raw_pair)

    return MetricSchemaAnalysis(
        schema_fingerprint=fingerprint,
        raw_pair=raw_pair,
        sample_size_fields=sample_size_fields,
        rtp_status=rtp_status,
        rtp_example_value=rtp_example,
        data_quality=data_quality,
    )


# ---------------------------------------------------------------
# Historical-season classification — pure comparison logic. The
# ACTUAL historical-season fetch only happens in a live run; this
# function just classifies two already-fetched responses.
# ---------------------------------------------------------------


def classify_historical_availability(
    current: ParsedRecordResponse, historical: ParsedRecordResponse
) -> str:
    """HISTORICAL_SEASON_RESPONSE_CONFIRMED | CURRENT_ONLY | UNKNOWN.
    Per explicit instruction, this is NEVER a PIT classification — it
    only answers "did the site return real, different-looking data for
    a prior season," not "is this safe to use as a model feature." The
    CONFIRMED-suffixed name is deliberate: it names what was actually
    observed (a genuinely different response), not an assumption about
    how far back historical data goes or how the site produced it."""
    if historical.parse_status in ("FAILED", "EMPTY"):
        return "CURRENT_ONLY" if current.rows else "UNKNOWN"
    if not historical.rows:
        return "CURRENT_ONLY"
    if not current.rows:
        return "UNKNOWN"

    # "Meaningfully different" is checked at the value level, not just
    # "a response came back" — an endpoint that silently echoes the
    # current season's data for any season parameter would otherwise
    # be misclassified as historically available.
    current_values = {(r.player_code, tuple(sorted(r.values.items()))) for r in current.rows}
    historical_values = {(r.player_code, tuple(sorted(r.values.items()))) for r in historical.rows}
    if current_values == historical_values:
        return "UNKNOWN"
    return "HISTORICAL_SEASON_RESPONSE_CONFIRMED"


# ---------------------------------------------------------------
# Cross-metric playerCode identity-consistency — does the SAME player,
# appearing across multiple independently-sampled metrics, resolve to
# the SAME player_code every time? Pure comparison over already-parsed
# responses; no network access, no assumption about players who only
# appear in one sampled metric (not cross-checkable at all).
# ---------------------------------------------------------------

IDENTITY_CONSISTENCY_CONFIRMED = "CONFIRMED"
IDENTITY_CONSISTENCY_PARTIAL = "PARTIAL"
IDENTITY_CONSISTENCY_NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass
class PlayerIdentityRecord:
    player_name: str
    codes_by_metric: dict[str, Optional[str]]
    """identity_key -> player_code observed for this player in that
    metric's response (None if the row had no name-linked code at all,
    which is preserved rather than dropped)."""
    consistent: bool
    """True iff every non-None code observed for this player across
    metrics is identical. A player seen in only one metric (nothing to
    cross-check) is trivially consistent=True but excluded from the
    overall CONFIRMED/PARTIAL rollup below — see cross_checkable."""


def build_player_identity_report(
    parsed_by_key: dict[str, ParsedRecordResponse]
) -> tuple[str, list[PlayerIdentityRecord]]:
    """Groups rows by player_name across every sampled metric's parsed
    response and checks whether player_code stays consistent for each
    player who appears in 2+ of the sampled responses.

    Overall status:
      CONFIRMED     — every cross-checkable player (2+ metrics) has the
                      same code everywhere it appears.
      PARTIAL       — at least one cross-checkable player has
                      DIFFERENT codes across metrics.
      NOT_AVAILABLE — no player appears in 2+ sampled metrics (nothing
                      to cross-check), or there are no rows at all.

    Matching is by player_name only (the one identifier every response
    is expected to carry) — never by row position or rank, which are
    metric-specific and not a player identity signal."""
    by_name: dict[str, dict[str, Optional[str]]] = {}
    for identity_key, parsed in parsed_by_key.items():
        for row in parsed.rows:
            if not row.player_name:
                continue
            by_name.setdefault(row.player_name, {})[identity_key] = row.player_code

    records: list[PlayerIdentityRecord] = []
    for name, codes_by_metric in by_name.items():
        non_none = [c for c in codes_by_metric.values() if c is not None]
        consistent = len(set(non_none)) <= 1
        records.append(
            PlayerIdentityRecord(player_name=name, codes_by_metric=codes_by_metric, consistent=consistent)
        )

    cross_checkable = [r for r in records if len(r.codes_by_metric) >= 2]
    if not cross_checkable:
        overall = IDENTITY_CONSISTENCY_NOT_AVAILABLE
    elif all(r.consistent for r in cross_checkable):
        overall = IDENTITY_CONSISTENCY_CONFIRMED
    else:
        overall = IDENTITY_CONSISTENCY_PARTIAL

    return overall, records
