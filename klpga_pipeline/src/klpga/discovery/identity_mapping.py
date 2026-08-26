"""Round 12 — the identity_key → storage-field mapping for the 248
unique canonical request identities. Answers, per canonical `(identity_
key, label)` pair, "which parsed response field carries this value's
data" — never a translated named column (see `docs/HISTORICAL_METRICS_
COLLECTION_DESIGN.md` §2's architecture decision: storage is a
normalized fact table keyed by `identity_key` + `label` directly, so
this module's job is narrower than a classic column-mapping layer —
it only needs to resolve which `record`/`record1`/... field in the
PARSED response a given canonical label's value actually lives in).

Reuses, unmodified: `canonical_plan.build_canonical_plan`,
`identity_key_audit.audit_identity_key_collisions` (for colliding
groups) and its private but already-tested `_normalize_label`/
`_classify_label_against_response` (for the 218 non-colliding
identities, which the audit never touches since it only processes
collisions), and `response_parser.parse_record_response`. No new
label-matching logic is invented here — only re-application of the
SAME matcher to the un-collided majority, plus translating the
audit's already-computed match/compound-title/container results into
a concrete field_name for the colliding minority.

Every canonical `(identity_key, label)` pair not backed by a saved raw
response, or whose value-column cannot be pinned down without
guessing, is preserved as a structured record with an honest status —
never silently dropped, never a fabricated field_name.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from klpga.discovery.canonical_plan import build_canonical_plan
from klpga.discovery.identity_key_audit import (
    _LABEL_MATCH_CONTAINER_CANDIDATE,
    _LABEL_MATCH_EXACT,
    _LABEL_MATCH_SUBSTRING,
    _classify_label_against_response,
    _normalize_label,
    audit_identity_key_collisions,
)
from klpga.discovery.record_fetch import sanitize_identity_key_for_filename
from klpga.discovery.response_parser import parse_record_response

STATUS_MAPPED = "MAPPED"
"""A specific parsed response field (`field_name`) is confirmed, by
direct label matching (exact/substring) or by a compound-menu-title
pairing whose OTHER half independently matched a field, to carry this
label's value."""

STATUS_CONTAINER_LABEL = "UNMAPPED_CONTAINER_LABEL"
"""A generic/family label (e.g. "티샷") that substring-matches more
than one response column — not attributable to a single field without
guessing which one. See `identity_key_audit.CATEGORY_CONTAINER_CHILD`."""

STATUS_NEEDS_REVIEW = "UNMAPPED_NEEDS_REVIEW"
"""No textual relationship to any response column, and no compound-
menu-title evidence explains it either — the same real case as
`identity_key_audit`'s remaining `Around::Around01::030101` group."""

STATUS_COMPOUND_TITLE_COLUMN_UNCONFIRMED = "UNMAPPED_COMPOUND_TITLE_COLUMN_UNCONFIRMED"
"""The IDENTITY-KEY collision itself is explained (the response's own
menuName confirms this label and another group label together form
one compound title — see `identity_key_audit.CATEGORY_COMPOUND_MENU_
TITLE_CONFIRMED`), but that OTHER label ALSO never independently
matched a response column (the real `Around::Around05::030401` shape:
both halves of the compound title are unmatched, resolved only
against each other) — so which specific response field carries the
value is NOT independently confirmed by direct label matching. Never
assumed from the pattern other, unrelated groups happen to follow."""

STATUS_EMPTY_RESPONSE = "UNMAPPED_EMPTY_RESPONSE"
"""The saved response has zero rows and no column labels at all — no
field exists to map to for ANY label sharing this identity_key (the
confirmed `Sg::All` shape)."""

STATUS_PENDING_EVIDENCE = "UNMAPPED_PENDING_EVIDENCE"
"""No saved raw response exists for this identity_key at all. Cannot
be mapped without either live/cached evidence or a new, separately-
authorized request."""


@dataclass
class MappingRecord:
    identity_key: str
    menu1: str
    menu2: str
    menu3: Optional[str]
    label: str
    status: str
    field_name: Optional[str] = None
    """"record" | "record1" | ... — the parsed response field this
    label's value lives in. Only set when `status == STATUS_MAPPED`."""
    response_column_label: Optional[str] = None
    """The original (non-normalized) response column display text
    `field_name` resolved against, when known."""
    match_method: Optional[str] = None
    """"exact" | "substring" | "compound_menu_title" | None."""
    paired_with_label: Optional[str] = None
    """For a compound-menu-title resolution, which OTHER canonical
    label (in the same identity_key group) it was found concatenated
    with in the real menuName string."""
    raw_sample_path: Optional[str] = None
    notes: str = ""


def _field_by_response_label(parsed) -> dict[str, str]:
    """First-wins lookup from a response column's ORIGINAL label text
    to the parsed field_name that carries it. First-wins matches this
    project's existing `original_by_normalized` pattern in `identity_
    key_audit.py` (a later column sharing an identical label text is
    never expected in real evidence and is not specially handled)."""
    by_label: dict[str, str] = {}
    for c in parsed.column_semantics:
        if c.label and c.label not in by_label:
            by_label[c.label] = c.field_name
    return by_label


def build_identity_metric_mapping(
    taxonomy: dict, *, raw_samples_dir: Path, season: str
) -> list[MappingRecord]:
    """One `MappingRecord` per `(identity_key, label)` pair in the full
    canonical plan (281 entries across 248 unique identity_keys, as of
    the Round 11 rebuild) — sorted by `(identity_key, label)` for
    determinism. Never fires a live request; only reads already-saved
    raw response files."""
    _counts, plan = build_canonical_plan(taxonomy)
    by_key: dict[str, list[dict]] = {}
    for entry in plan:
        by_key.setdefault(entry["identity_key"], []).append(entry)

    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=raw_samples_dir, season=season)
    audit_by_key = {a.request_identity_key: a for a in audits}

    records: list[MappingRecord] = []
    for identity_key in sorted(by_key):
        entries = by_key[identity_key]
        raw_path = raw_samples_dir / f"{sanitize_identity_key_for_filename(identity_key)}__{season}.html"

        if not raw_path.exists():
            for entry in entries:
                records.append(
                    MappingRecord(
                        identity_key=identity_key,
                        menu1=entry["menu1"],
                        menu2=entry["menu2"],
                        menu3=entry.get("menu3"),
                        label=entry["label"] or "",
                        status=STATUS_PENDING_EVIDENCE,
                        raw_sample_path=str(raw_path),
                        notes=f"No saved raw response at {raw_path} — cannot map without live/cached evidence.",
                    )
                )
            continue

        html = raw_path.read_text(encoding="utf-8")
        parsed = parse_record_response(html)
        response_labels = [c.label for c in parsed.column_semantics if c.label]

        if len(parsed.rows) == 0 and not response_labels:
            for entry in entries:
                records.append(
                    MappingRecord(
                        identity_key=identity_key,
                        menu1=entry["menu1"],
                        menu2=entry["menu2"],
                        menu3=entry.get("menu3"),
                        label=entry["label"] or "",
                        status=STATUS_EMPTY_RESPONSE,
                        raw_sample_path=str(raw_path),
                        notes="Shared response has zero rows and no column labels — no field exists to map to.",
                    )
                )
            continue

        field_by_label = _field_by_response_label(parsed)
        group_audit = audit_by_key.get(identity_key)

        if group_audit is None:
            # Non-colliding identity_key: exactly one canonical label,
            # never processed by the collision audit at all — apply
            # the SAME matcher directly.
            entry = entries[0]
            label = entry["label"] or ""
            norm_label = _normalize_label(label)
            normalized_response_labels = [_normalize_label(l) for l in response_labels]
            tier, matched_norm = _classify_label_against_response(norm_label, normalized_response_labels)
            common = dict(
                identity_key=identity_key, menu1=entry["menu1"], menu2=entry["menu2"],
                menu3=entry.get("menu3"), label=label, raw_sample_path=str(raw_path),
            )
            if tier in (_LABEL_MATCH_EXACT, _LABEL_MATCH_SUBSTRING):
                idx = normalized_response_labels.index(matched_norm)
                column_label = response_labels[idx]
                records.append(
                    MappingRecord(
                        **common, status=STATUS_MAPPED, field_name=field_by_label.get(column_label),
                        response_column_label=column_label, match_method=tier,
                    )
                )
            elif tier == _LABEL_MATCH_CONTAINER_CANDIDATE:
                records.append(
                    MappingRecord(
                        **common, status=STATUS_CONTAINER_LABEL,
                        notes="Generic/short label — substring-ambiguous across multiple response columns.",
                    )
                )
            else:
                records.append(
                    MappingRecord(
                        **common, status=STATUS_NEEDS_REVIEW,
                        notes="No textual relationship to any response column.",
                    )
                )
            continue

        # Colliding identity_key: reuse the audit's already-computed
        # per-label resolution instead of re-deriving it.
        match_by_label = {d.taxonomy_label: d for d in group_audit.match_details}
        pair_by_label = dict(group_audit.compound_title_pairs)
        for entry in entries:
            label = entry["label"] or ""
            common = dict(
                identity_key=identity_key, menu1=entry["menu1"], menu2=entry["menu2"],
                menu3=entry.get("menu3"), label=label, raw_sample_path=str(raw_path),
            )
            if label in match_by_label:
                d = match_by_label[label]
                records.append(
                    MappingRecord(
                        **common, status=STATUS_MAPPED, field_name=field_by_label.get(d.response_column),
                        response_column_label=d.response_column, match_method=d.method,
                    )
                )
            elif label in group_audit.compound_title_confirmed_labels:
                paired = pair_by_label.get(label)
                paired_detail = match_by_label.get(paired) if paired else None
                if paired_detail is not None:
                    records.append(
                        MappingRecord(
                            **common, status=STATUS_MAPPED,
                            field_name=field_by_label.get(paired_detail.response_column),
                            response_column_label=paired_detail.response_column,
                            match_method="compound_menu_title", paired_with_label=paired,
                            notes=(
                                f"Resolved via the response's own compound menuName; shares the SAME "
                                f"response field as '{paired}', which independently matched a column."
                            ),
                        )
                    )
                else:
                    records.append(
                        MappingRecord(
                            **common, status=STATUS_COMPOUND_TITLE_COLUMN_UNCONFIRMED,
                            paired_with_label=paired,
                            notes=(
                                f"Compound menuName confirms this label and '{paired}' describe the SAME "
                                f"metric, but NEITHER independently matched a response column — which of "
                                f"{response_labels} carries the value is not confirmed, not guessed."
                            ),
                        )
                    )
            elif label in group_audit.container_candidate_labels:
                records.append(
                    MappingRecord(
                        **common, status=STATUS_CONTAINER_LABEL,
                        notes="Generic/family label — substring-ambiguous across multiple response columns.",
                    )
                )
            else:
                records.append(
                    MappingRecord(
                        **common, status=STATUS_NEEDS_REVIEW,
                        notes=group_audit.notes or "No textual or compound-title relationship found.",
                    )
                )

    return sorted(records, key=lambda r: (r.identity_key, r.label))
