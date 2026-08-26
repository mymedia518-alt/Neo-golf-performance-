"""Round 10 continued (docs/KLPGA_OFFICIAL_DATA_MAP.md's Round 10
section) — offline classification of canonical-plan `identity_key`
collision groups. NEVER fires a live HTTP request: classifies each
colliding group using ONLY an already-saved raw response, if one
exists at `<raw_samples_dir>/<sanitized_identity>__<season>.html`
(the exact naming convention `klpga.discovery.record_fetch.
fetch_and_analyze` already uses to save raw evidence for scripts/27
and scripts/29). A group with no saved evidence is reported as
insufficient-evidence, never guessed.

Confirmed architectural finding this round: the SAME `(menu1, menu2,
menu3)` request can legitimately return MULTIPLE distinct, labeled
value columns in one response (independently reconfirmed for
Around::Around04::030306, Tee::Tee01::010101, Putt::Putt01::040101 —
each response's real column_semantics carried a separate label
matching each of that identity's taxonomy-mapped labels). This means
"canonical metric identity" (one row per DOM-discovered label,
`identity_key`) and "HTTP request identity" (one row per distinct live
request, `request_identity_key`) are genuinely different concepts,
even though they are computed from the same (menu1, menu2, menu3)
tuple and therefore have the SAME string value today —
`derive_request_identity_key` exists so the code expresses that
distinction explicitly rather than reusing `identity_key` by
convention.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from klpga.discovery.canonical_plan import build_canonical_plan
from klpga.discovery.record_fetch import sanitize_identity_key_for_filename
from klpga.discovery.response_parser import parse_record_response

CATEGORY_MULTI_METRIC_CONFIRMED = "C_MULTI_METRIC_ONE_REQUEST_CONFIRMED"
"""Every label mapped to this identity_key matches a distinct column
label found in the already-saved response for that SAME request —
direct evidence multiple canonical metrics are intentionally served
by one HTTP request."""

CATEGORY_EMPTY_SHARED_RESPONSE = "EMPTY_SHARED_RESPONSE"
"""A saved response exists but has zero rows and no labeled columns —
no data exists for ANY label in this group under this identity (the
confirmed Sg::All shape). Not classified as A/B/C/D: there is no
metric data to attribute to any label, so the "multiple metrics share
one request" question does not apply here at all."""

CATEGORY_EXACT_DUPLICATE = "A_EXACT_DUPLICATE_DOM_REPRESENTATION"
"""Two or more labels in the group normalize (whitespace-collapsed,
case-folded) to the IDENTICAL text despite not being byte-identical —
byte-identical same-label duplicates are already structurally
impossible to reach a collision group (see canonical_plan.py's
exact-duplicate dedup key), so this is the next tier down: a likely
DOM markup artifact, not a real distinct metric. Checked BEFORE
needing any raw response, since it is a pure taxonomy-label
comparison."""

CATEGORY_CONTAINER_CHILD = "B_CONTAINER_CHILD"
"""At least one label is a CONFIRMED match (exact or substring) to a
specific response column, and every OTHER label in the group is a
"container-candidate" — a short/generic label whose only textual
relationship to the response is an ambiguous substring hit (matches
2+ columns) or falls below the minimum meaningful-match length (see
`_MIN_SUBSTRING_MATCH_LENGTH`). Real example confirmed this round:
Putt::Putt01::040101's "1퍼트 성공률" matches the response's
"성공률(%)" column (substring, after stripping the trailing "(%)"
annotation), while "퍼팅" — 2 characters, a substring of every column
in the Putt family — is the generic parent label, not a distinct
metric of its own."""

CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW = "PARTIAL_MATCH_NEEDS_REVIEW"
"""At least one label is genuinely UNMATCHED (no exact/substring/
container relationship to any response column at all), while at
least one other label in the group DID resolve (matched or
container-candidate). Deliberately left for human review rather than
auto-classified as B or D — string comparison alone cannot prove
whether the unmatched label is a derived metric (e.g. a rate computed
from a returned count column — real example: Tee::Tee01::010101's
"Par4,5 티샷 비율" versus the response's "Par4,5 티샷 횟수", which
differ only in their final word, 비율 vs 횟수) or a genuine gap."""

CATEGORY_UNRESOLVED = "D_UNRESOLVED_REQUEST_IDENTITY_COLLISION"
"""The saved response is non-empty, but NONE of the group's labels
have even a container-candidate relationship to any of its column
labels — the strongest evidence this codebase can produce, without a
new request, that this collision may be a genuine request-identity-
model gap rather than a benign container/multi-metric case."""

CATEGORY_INSUFFICIENT_EVIDENCE = "UNRESOLVED_INSUFFICIENT_EVIDENCE"
"""No saved raw response exists for this identity at all — cannot be
classified without either finding cached evidence elsewhere or a new,
separately-authorized request. Never guessed."""

_MIN_SUBSTRING_MATCH_LENGTH = 3
"""Minimum character length (of the SHORTER of the two compared
strings) for a substring relationship to count as a confirmed
per-label match rather than a container-candidate signal. Derived
directly from real evidence, not an arbitrary guess: "성공률" (3
chars) is a genuine, specific metric-name fragment and should count;
"티샷"/"퍼팅" (2 chars each) are generic family names that substring-
match every column in their own group and should NOT count as tied to
one specific column."""

_TRAILING_PARENTHETICAL = re.compile(r"\s*\([^)]*\)\s*$")
"""Strips a trailing "(...)" annotation — e.g. "(yds)", "(%)" — that
real evidence (docs/KLPGA_OFFICIAL_DATA_MAP.md's Round 10 section)
showed response column labels carry but taxonomy labels do not.
Applied to BOTH sides symmetrically; harmless when absent."""


def derive_request_identity_key(entry: dict) -> str:
    """The deterministic key that defines ONE live HTTP request.
    Identical in VALUE to `identity_key` today — both are derived
    from menu1/menu2/menu3 only, matching `record_fetch.request_form`'s
    exact POST body (`{season, menu1, menu2, menu3-if-present}`) — but
    computed and named independently, so "canonical metric identity"
    and "HTTP request identity" are two distinct concepts in the code,
    per this round's confirmed finding that multiple canonical metrics
    can share one request."""
    if entry.get("leaf_level") == "menu3":
        return f"{entry.get('menu1')}::{entry.get('menu2')}::{entry.get('menu3')}"
    return f"{entry.get('menu1')}::{entry.get('menu2')}"


def _normalize_label(label: Optional[str]) -> str:
    if label is None:
        return ""
    collapsed = re.sub(r"\s+", " ", label).strip().casefold()
    return _TRAILING_PARENTHETICAL.sub("", collapsed).strip()


_LABEL_MATCH_EXACT = "exact"
_LABEL_MATCH_SUBSTRING = "substring"
_LABEL_MATCH_CONTAINER_CANDIDATE = "container_candidate"
_LABEL_MATCH_NONE = "none"


def _classify_label_against_response(
    norm_label: str, normalized_response_labels: list[str]
) -> tuple[str, Optional[str]]:
    """Per-label match tier against the FULL list of the response's
    normalized column labels (not a set — needed to detect an
    AMBIGUOUS substring hit, i.e. a label that substring-matches more
    than one column, which is exactly the generic/container-label
    signature confirmed by real evidence this round). Returns
    (tier, matched_normalized_response_label_or_None) — the second
    element is set only for `exact`/`substring` tiers, so a caller can
    report exactly which response column a taxonomy label resolved
    against."""
    if not norm_label:
        return _LABEL_MATCH_NONE, None
    if norm_label in normalized_response_labels:
        return _LABEL_MATCH_EXACT, norm_label

    substring_hits = [
        resp for resp in normalized_response_labels
        if norm_label in resp or resp in norm_label
    ]
    if not substring_hits:
        return _LABEL_MATCH_NONE, None

    shorter_len = min(len(norm_label), min(len(resp) for resp in substring_hits))
    if len(substring_hits) == 1 and shorter_len >= _MIN_SUBSTRING_MATCH_LENGTH:
        return _LABEL_MATCH_SUBSTRING, substring_hits[0]
    return _LABEL_MATCH_CONTAINER_CANDIDATE, None


@dataclass
class LabelMatchDetail:
    taxonomy_label: str
    response_column: str
    """The ORIGINAL (non-normalized) response column label text."""
    method: str
    """"exact" | "substring" — which tier resolved this label."""


@dataclass
class GroupAudit:
    request_identity_key: str
    labels: list[str]
    category: str
    matched_labels: list[str] = field(default_factory=list)
    match_details: list[LabelMatchDetail] = field(default_factory=list)
    """One entry per confirmed (exact/substring) match, pairing the
    taxonomy label with the SPECIFIC original response column it
    resolved against and how — never just "matched: True"."""
    container_candidate_labels: list[str] = field(default_factory=list)
    unmatched_labels: list[str] = field(default_factory=list)
    response_column_labels: list[str] = field(default_factory=list)
    raw_sample_path: Optional[str] = None
    notes: str = ""


def audit_identity_key_collisions(
    taxonomy: dict, *, raw_samples_dir: Path, season: str
) -> list[GroupAudit]:
    """One `GroupAudit` per colliding `identity_key` group in the
    canonical plan (see `canonical_plan.build_canonical_plan`), sorted
    by `identity_key`. Never fires a live request — only reads an
    already-saved raw response file if one exists."""
    _counts, plan = build_canonical_plan(taxonomy)

    by_key: dict[str, list[dict]] = {}
    for entry in plan:
        by_key.setdefault(entry["identity_key"], []).append(entry)
    colliding_groups = {key: entries for key, entries in by_key.items() if len(entries) > 1}

    audits: list[GroupAudit] = []
    for identity_key in sorted(colliding_groups):
        group = colliding_groups[identity_key]
        request_key = derive_request_identity_key(group[0])
        labels = [entry["label"] or "" for entry in group]
        normalized = [_normalize_label(label) for label in labels]

        if len(set(normalized)) < len(normalized):
            audits.append(
                GroupAudit(
                    request_identity_key=request_key,
                    labels=labels,
                    category=CATEGORY_EXACT_DUPLICATE,
                    notes=(
                        "Two or more labels normalize to identical text (whitespace/case-only "
                        "difference) — likely a DOM markup artifact, not a real distinct metric."
                    ),
                )
            )
            continue

        raw_path = raw_samples_dir / f"{sanitize_identity_key_for_filename(request_key)}__{season}.html"
        if not raw_path.exists():
            audits.append(
                GroupAudit(
                    request_identity_key=request_key,
                    labels=labels,
                    category=CATEGORY_INSUFFICIENT_EVIDENCE,
                    raw_sample_path=str(raw_path),
                    notes=f"No saved raw response at {raw_path} — cannot classify without live/cached evidence.",
                )
            )
            continue

        html = raw_path.read_text(encoding="utf-8")
        parsed = parse_record_response(html)
        response_labels = [c.label for c in parsed.column_semantics if c.label]
        normalized_response_labels = [_normalize_label(label) for label in response_labels]

        if len(parsed.rows) == 0 and not response_labels:
            audits.append(
                GroupAudit(
                    request_identity_key=request_key,
                    labels=labels,
                    category=CATEGORY_EMPTY_SHARED_RESPONSE,
                    response_column_labels=response_labels,
                    raw_sample_path=str(raw_path),
                    notes="Shared response has zero rows and no column labels — no data exists for any label in this group.",
                )
            )
            continue

        original_by_normalized: dict[str, str] = {}
        for original, norm in zip(response_labels, normalized_response_labels):
            original_by_normalized.setdefault(norm, original)

        matched, match_details, container_candidates, unmatched = [], [], [], []
        for label, norm in zip(labels, normalized):
            tier, matched_norm = _classify_label_against_response(norm, normalized_response_labels)
            if tier in (_LABEL_MATCH_EXACT, _LABEL_MATCH_SUBSTRING):
                matched.append(label)
                match_details.append(
                    LabelMatchDetail(
                        taxonomy_label=label,
                        response_column=original_by_normalized.get(matched_norm, matched_norm or ""),
                        method=tier,
                    )
                )
            elif tier == _LABEL_MATCH_CONTAINER_CANDIDATE:
                container_candidates.append(label)
            else:
                unmatched.append(label)

        if unmatched:
            category = CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW if (matched or container_candidates) else CATEGORY_UNRESOLVED
        elif container_candidates:
            category = CATEGORY_CONTAINER_CHILD if matched else CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW
        else:
            category = CATEGORY_MULTI_METRIC_CONFIRMED

        note_parts = []
        if unmatched:
            note_parts.append(f"{len(unmatched)} of {len(labels)} label(s) had no textual relationship to any response column")
        if container_candidates:
            note_parts.append(f"{len(container_candidates)} label(s) matched as a generic/container candidate: {container_candidates}")

        audits.append(
            GroupAudit(
                request_identity_key=request_key,
                labels=labels,
                category=category,
                matched_labels=matched,
                match_details=match_details,
                container_candidate_labels=container_candidates,
                unmatched_labels=unmatched,
                response_column_labels=response_labels,
                raw_sample_path=str(raw_path),
                notes="; ".join(note_parts),
            )
        )

    return audits
