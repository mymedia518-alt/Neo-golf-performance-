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

CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW = "PARTIAL_MATCH_NEEDS_REVIEW"
"""SOME (not all, not none) of the group's labels match a response
column. Deliberately NOT auto-classified as B (container/child) or D
(unresolved) — that call needs a human to look at which specific
label(s) went unmatched (a real category-header label vs. a
genuinely missing metric are indistinguishable from label-matching
alone)."""

CATEGORY_UNRESOLVED = "D_UNRESOLVED_REQUEST_IDENTITY_COLLISION"
"""The saved response is non-empty, but NONE of the group's labels
match any of its column labels — the strongest evidence this
codebase can produce, without a new request, that this collision may
be a genuine request-identity-model gap rather than a benign
container/multi-metric case."""

CATEGORY_INSUFFICIENT_EVIDENCE = "UNRESOLVED_INSUFFICIENT_EVIDENCE"
"""No saved raw response exists for this identity at all — cannot be
classified without either finding cached evidence elsewhere or a new,
separately-authorized request. Never guessed."""


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
    return re.sub(r"\s+", " ", label).strip().casefold()


@dataclass
class GroupAudit:
    request_identity_key: str
    labels: list[str]
    category: str
    matched_labels: list[str] = field(default_factory=list)
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
                    notes=f"No saved raw response at {raw_path} — cannot classify without live/cached evidence.",
                )
            )
            continue

        html = raw_path.read_text(encoding="utf-8")
        parsed = parse_record_response(html)
        response_labels = [c.label for c in parsed.column_semantics if c.label]
        normalized_response_labels = {_normalize_label(label) for label in response_labels}

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

        matched, unmatched = [], []
        for label, norm in zip(labels, normalized):
            (matched if norm in normalized_response_labels else unmatched).append(label)

        if not unmatched:
            category = CATEGORY_MULTI_METRIC_CONFIRMED
        elif not matched:
            category = CATEGORY_UNRESOLVED
        else:
            category = CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW

        audits.append(
            GroupAudit(
                request_identity_key=request_key,
                labels=labels,
                category=category,
                matched_labels=matched,
                unmatched_labels=unmatched,
                response_column_labels=response_labels,
                raw_sample_path=str(raw_path),
                notes="" if not unmatched else f"{len(unmatched)} of {len(labels)} label(s) matched no response column.",
            )
        )

    return audits
