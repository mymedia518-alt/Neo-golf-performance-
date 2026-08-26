"""Parser for one `loadLocationRecord` response — parser architecture
only, per Round 3's conditional approval. NOT wired into any
live-running script this round; Phase B (actually firing these
requests) stays deliberately unimplemented until separately
authorized.

Confirmed shape of the response (per the user's manual DevTools
capture): `POST /load/record/loadLocationRecord` returns
`text/html; charset=UTF-8` containing player-level rows with at least
`playerCode`, `player_name`, `rank`, and up to five value columns
referred to as `record`/`record1`/`record2`/`record3`/`record4`. The
user's own evidence is explicit that these five columns do NOT mean
the same thing for every metric (confirmed meaning for one Approach
GIR metric: record=GIR%, record1=successes, record2=attempts,
record3=measured rounds, record4=RTP — never assumed to generalize).

This module has NOT been validated against real captured HTML — no
real `loadLocationRecord` response has been available to this session
(no network access; see docs/KLPGA_OFFICIAL_DATA_MAP.md's methodology
limitation, unchanged since Round 1). It is built and tested against
fixtures constructed to match this project's own already-CONFIRMED
`data-*` attribute convention (see `klpga.parsers.leaderboard_parser`,
proven correct for the sibling `roundLeaderboard` endpoint) as the
most evidence-grounded working assumption available — not a guess from
nothing, but still unverified for this specific endpoint. **Must be
re-validated against real response HTML before Phase B ever runs**;
if the real shape differs, this module's row/column extraction will
need revising, not just its fixtures.

**Round 3 Phase B correction**: the record-field count is discovered
per-response (`_discover_record_fields`), not fixed at 5. Real SG
evidence (season=2026 season, menu1=Sg, menu2=Total: 서교림's SG Total
2.38 / SG Tee Shot 0.67 / SG Approach 1.00 / SG Around the Green 0.17 /
SG Putting 0.54 / measured rounds 61 — six named values) proved the
original fixed `record..record4` (5-field) assumption doesn't hold for
every metric family. A response with more or fewer `data-record*`
attributes than 5 is now handled correctly rather than silently
truncated or padded.

Column-semantics resolution is layered, most-trusted first, and always
records which layer actually supplied the answer:
  1. `metadata` — an embedded per-response metadata block (matching the
     `menu`/`menuName`/`recordNote`/`record`/`record1..4`/`order` keys
     the user's own DevTools inspection surfaced) if present anywhere
     in the response (a `<script>` block or `data-*` attributes on a
     metadata container).
  2. `dynamic_header_vars` — CONFIRMED against a real cached response
     (Phase B1): KLPGA populates header text client-side via jQuery
     (`$(".recordName").html(record)`) from separate `var record =
     "...";`/`var record1 = "...";` JS declarations. The static HTML
     this parser receives has the `<th class="recordName">` (etc.)
     elements present but EMPTY — the real label text exists only in
     these `var` assignments, never in the JSON-object shape layer 1
     looks for. This is the confirmed root cause of a real 231-row
     response classifying as EMPTY_SCHEMA before this layer existed
     (see docs/KLPGA_OFFICIAL_DATA_MAP.md's Phase B1 dynamic-header
     section). A blank `var record4 = "";` is never stored as a label
     here — see `_extract_dynamic_header_labels`.
  2b. `menu_switch_vars` — CONFIRMED against a real cached Sg-family
     response (Round 7, docs/KLPGA_OFFICIAL_DATA_MAP.md's Round 7
     section): the Sg family uses a THIRD, distinct client-side
     pattern neither layer 1 nor layer 2 recognizes — a
     `var menu = "<identity>";` declaration followed by an
     `if(menu == "X") { ... } else if(menu == "Y") { ... }` chain,
     each branch assigning `menuName`/`recordNote`/`order` and up to
     five `data1`.."data5" value-column labels. Only the ONE branch
     whose condition matches the response's own `menu` value is
     read — see `_extract_menu_switch_metadata`. The Nth `dataN` label
     maps to the (N-1)th `record*` field position — the SAME
     positional-correspondence principle layer 3 below already uses.
     Round 8 (docs/KLPGA_OFFICIAL_DATA_MAP.md's Round 8 section)
     obtained real `<td>`/`<tr>` row-markup evidence for this family
     for the FIRST time, but only for player-identity extraction (see
     `_extract_player_name_from_cell` below) — the dataN-label-to-
     record*-value positional mapping itself remains unconfirmed by
     row-level evidence, which is why this layer still never sets
     `metadata.found = True` (kept at the same honesty tier as layer
     2, not layer 1).
  3. `table_header` — visible, NON-BLANK `<th>` text, in column order,
     used only when neither layer 1, 2, nor 2b supplied a label for
     that column.
  4. `unknown` — none of the above found a non-blank label; the column
     is preserved in the parsed row but its semantic label is left
     `None`, never invented.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup, Tag

_RECORD_ATTRS = ["record", "record1", "record2", "record3", "record4"]
"""Fallback field list, used only when no data-record* attribute is
found anywhere in a response at all (see _discover_record_fields)."""
_METADATA_KEYS = ["menu", "menuName", "recordNote", "order"]
_RECORD_FIELD_PATTERN = re.compile(r"^data-record(\d*)$")


def _attr(tag: Tag, name: str) -> Optional[str]:
    for key, value in tag.attrs.items():
        if key.lower() == name.lower():
            return value if isinstance(value, str) else " ".join(value)
    return None


def _discover_record_fields(soup: BeautifulSoup) -> list[str]:
    """Scans every tag's attributes for `data-record`/`data-record<N>`
    and returns the field names actually present, in numeric order
    (`record`, `record1`, `record2`, ...) — NOT a fixed count. Falls
    back to the historical 5-field list only if no such attribute is
    found anywhere in the response."""
    found: dict[int, str] = {}
    for tag in soup.find_all(True):
        for key in tag.attrs:
            match = _RECORD_FIELD_PATTERN.match(key.lower())
            if match:
                idx = int(match.group(1)) if match.group(1) else 0
                found[idx] = "record" if idx == 0 else f"record{idx}"
    if not found:
        return list(_RECORD_ATTRS)
    return [found[i] for i in sorted(found)]


@dataclass
class ColumnSemantics:
    """What one `record*` column means for THIS metric only — never
    reused across metrics without re-deriving it from that metric's
    own response."""

    field_name: str  # "record", "record1", ...
    label: Optional[str]
    source: str  # "metadata" | "table_header" | "unknown"


@dataclass
class ResponseMetadata:
    """The `menu`/`menuName`/`recordNote`/`order` block, when found —
    preferred over heuristic column-position interpretation, per
    explicit instruction."""

    menu: Optional[str] = None
    menu_name: Optional[str] = None
    record_note: Optional[str] = None
    order: Optional[str] = None
    found: bool = False


@dataclass
class PlayerRecordRow:
    player_code: Optional[str]
    player_name: Optional[str]
    rank: Optional[str]
    values: dict[str, Optional[str]] = field(default_factory=dict)
    """Keyed by "record"/"record1".../"record<N>" -> raw string value
    (N is discovered per-response, not fixed at 4) — exactly as found,
    no unit conversion, no float parsing here."""
    player_code_source: Optional[str] = None
    """"data_attribute" | "href_query_param" | None (no code found at
    all) — which extraction method actually supplied player_code."""


@dataclass
class SampleDefinition:
    """Only populated from the response's own labels/recordNote/
    menuName — per explicit instruction, never generated from
    assumption. Any field that can't be traced to real response text
    stays None (UNKNOWN), not guessed."""

    rate_semantics: Optional[str] = None
    numerator_semantics: Optional[str] = None
    denominator_semantics: Optional[str] = None
    sample_definition_text: Optional[str] = None


@dataclass
class ParsedRecordResponse:
    metadata: ResponseMetadata
    column_semantics: list[ColumnSemantics]
    rows: list[PlayerRecordRow]
    sample_definition: SampleDefinition
    parse_status: str  # "CONFIRMED" | "DISCOVERED_NOT_VALIDATED" | "EMPTY" | "AMBIGUOUS" | "FAILED"
    notes: list[str] = field(default_factory=list)


def _extract_metadata(soup: BeautifulSoup) -> ResponseMetadata:
    """Look for an embedded metadata block carrying the
    menu/menuName/recordNote/order keys the user's DevTools inspection
    surfaced. Tries a <script> JSON-ish blob first, then a metadata
    container's own data-* attributes. Returns found=False rather than
    a guess if neither is present."""
    for script in soup.find_all("script"):
        text = script.string or ""
        if not any(key in text for key in _METADATA_KEYS):
            continue
        match = re.search(r"\{[^{}]*\"menu(?:Name)?\"[^{}]*\}", text)
        if not match:
            continue
        try:
            obj = json.loads(match.group(0))
        except (json.JSONDecodeError, ValueError):
            continue
        return ResponseMetadata(
            menu=obj.get("menu"),
            menu_name=obj.get("menuName"),
            record_note=obj.get("recordNote"),
            order=obj.get("order"),
            found=True,
        )

    meta_container = soup.find(attrs={"data-menuname": True}) or soup.find(attrs={"data-menu-name": True})
    if meta_container is not None:
        return ResponseMetadata(
            menu=_attr(meta_container, "data-menu"),
            menu_name=_attr(meta_container, "data-menuname") or _attr(meta_container, "data-menu-name"),
            record_note=_attr(meta_container, "data-recordnote") or _attr(meta_container, "data-record-note"),
            order=_attr(meta_container, "data-order"),
            found=True,
        )

    return ResponseMetadata(found=False)


_DYNAMIC_HEADER_VAR_RE = re.compile(r'var\s+(record\d*)\s*=\s*"([^"]*)"\s*;')
"""Matches KLPGA's confirmed dynamic-header JS pattern (Phase B1 real
cached-response evidence):

    var record  = "그린 적중률(%)";
    var record1 = "그린 적중 횟수";
    ...
    $(".recordName").html(record);

The site fills `<th class="recordName">` (etc.) client-side via
jQuery — the static HTML this parser actually receives has those `<th>`
elements present but EMPTY, which is the confirmed root cause of a
231-real-row response classifying as EMPTY_SCHEMA (see
docs/KLPGA_OFFICIAL_DATA_MAP.md's Phase B1 dynamic-header section):
`_extract_metadata()`'s JSON-object regex never matches these separate
`var` assignments, and the table-header fallback below reads only the
(blank) static text, never the real label the `var` declarations carry.
No escaping beyond a plain quoted string is handled — none was present
in the real evidence; Mission instruction is explicit that escape
handling must be evidence-based, not speculative."""


def _extract_dynamic_header_labels(html: str, record_fields: list[str]) -> dict[str, str]:
    """Scans the RAW response body (not the parsed DOM — script content
    extraction via BeautifulSoup is unreliable across script tags with
    mixed content) for `var record<N> = "...";` declarations. Returns
    only NON-BLANK labels for field names that are actually in
    `record_fields` — a blank `var record4 = "";` is deliberately
    OMITTED from the returned dict (not stored as an empty string),
    so it can never be mistaken for "a real label was found" by a
    caller that only checks dict membership. This is the "blank
    labels must not create a fake metric" requirement."""
    found: dict[str, str] = {}
    for field_name, label in _DYNAMIC_HEADER_VAR_RE.findall(html):
        if field_name in record_fields and label:
            found[field_name] = label
    return found


_MENU_SWITCH_VAR_RE = re.compile(r'var\s+menu\s*=\s*"([^"]*)"\s*;')
_MENU_SWITCH_MENUNAME_RE = re.compile(r'\bmenuName\s*=\s*"([^"]*)"\s*;')
_MENU_SWITCH_RECORDNOTE_RE = re.compile(r'\brecordNote\s*=\s*"([^"]*)"\s*;')
_MENU_SWITCH_ORDER_RE = re.compile(r'\border\s*=\s*"([^"]*)"\s*;')
_MENU_SWITCH_DATA_VAR_RE = re.compile(r'\bdata(\d+)\s*=\s*"([^"]*)"\s*;')


def _find_matching_brace_block(html: str, open_brace_index: int) -> str:
    """Returns the substring strictly between `html[open_brace_index]`
    (must be `'{'`) and its matching closing brace — a simple depth
    counter, sufficient for the plain assignment statements the real
    evidence for this pattern shows (no nested object literals
    observed). Returns the remainder of the string if no matching
    close is found (malformed/truncated input degrades rather than
    raising)."""
    depth = 0
    for i in range(open_brace_index, len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                return html[open_brace_index + 1 : i]
    return html[open_brace_index + 1 :]


def _extract_menu_switch_metadata(html: str) -> tuple[ResponseMetadata, dict[int, str]]:
    """CONFIRMED against a real cached Sg-family response (Round 7 —
    see docs/KLPGA_OFFICIAL_DATA_MAP.md's Round 7 section): KLPGA's
    Sg-family responses use a THIRD, distinct client-side templating
    pattern that neither `_extract_metadata` (a JSON-object blob) nor
    `_extract_dynamic_header_labels` (`var record<N> = "...";`)
    recognizes — a `var menu = "<identity>";` declaration followed by
    an `if(menu == "X") { ... } else if(menu == "Y") { ... }` chain,
    each branch assigning `menuName`/`recordNote`/`order` and up to
    five `data1`.."data5" value-column labels. The static HTML this
    parser receives already has `menu` set to the CURRENT response's
    own requested identity (e.g. `var menu = "Around";` for an
    Sg::Around request) — only the ONE branch whose condition matches
    that exact value is semantically relevant to THIS response; every
    other branch describes a DIFFERENT Sg sub-metric and is never read
    here. If no branch matches `menu`'s value (confirmed real case:
    `var menu = "All";` with no `else if(menu == "All")` branch in the
    switch at all — the real `Sg::All` response, which returns zero
    rows), this returns not-found rather than fabricating anything.

    Returns `(ResponseMetadata(..., found=False), {1: data1_label, 2:
    data2_label, ...})`. `found` is deliberately kept `False` — this
    layer's per-column mapping (the Nth `dataN` label to the (N-1)th
    `record*` field position) mirrors the SAME positional-
    correspondence principle `_extract_column_semantics`'s
    `table_header` layer already uses, and is NOT independently
    confirmed by real `<td>`/`<tr>` row-markup evidence for the Sg
    family (this session has not been given one) — so this stays at
    the same honesty tier as `dynamic_header_vars`, never claiming
    layer-1 (`metadata`) confidence."""
    menu_match = _MENU_SWITCH_VAR_RE.search(html)
    if not menu_match or not menu_match.group(1):
        return ResponseMetadata(found=False), {}
    menu_value = menu_match.group(1)

    branch_pattern = re.compile(r'menu\s*==\s*"' + re.escape(menu_value) + r'"\s*\)\s*\{')
    branch_match = branch_pattern.search(html)
    if not branch_match:
        return ResponseMetadata(found=False), {}
    block = _find_matching_brace_block(html, branch_match.end() - 1)

    menu_name_match = _MENU_SWITCH_MENUNAME_RE.search(block)
    record_note_match = _MENU_SWITCH_RECORDNOTE_RE.search(block)
    order_match = _MENU_SWITCH_ORDER_RE.search(block)

    data_labels: dict[int, str] = {}
    for idx_str, label in _MENU_SWITCH_DATA_VAR_RE.findall(block):
        if label:
            data_labels[int(idx_str)] = label

    metadata = ResponseMetadata(
        menu=menu_value,
        menu_name=menu_name_match.group(1) if menu_name_match else None,
        record_note=record_note_match.group(1) if record_note_match else None,
        order=order_match.group(1) if order_match else None,
        found=False,
    )
    return metadata, data_labels


def _extract_column_semantics(
    soup: BeautifulSoup,
    metadata: ResponseMetadata,
    record_fields: list[str],
    dynamic_labels: Optional[dict[str, str]] = None,
    menu_switch_position_labels: Optional[list[Optional[str]]] = None,
) -> list[ColumnSemantics]:
    if metadata.found and metadata.record_note:
        # The recordNote is a single free-text description of the whole
        # metric, not a per-column label — attach it to `record` (the
        # primary value column) only; other columns stay unknown from
        # this source and fall through to the layers below.
        pass

    dynamic_labels = dynamic_labels or {}
    menu_switch_position_labels = menu_switch_position_labels or []

    header_cells = soup.select("thead th") or soup.select("tr th")
    header_labels = [th.get_text(strip=True) for th in header_cells]

    # Heuristic, NOT confirmed: this project's already-CONFIRMED
    # roundLeaderboard convention leads with rank/name columns before
    # any stat column (see leaderboard_parser.py's data-rank/data-name
    # ordering) — so if there are MORE header cells than record fields,
    # assume the record-field headers are the trailing ones, not the
    # leading ones (which are far more likely to be rank/name/etc.).
    # This is a working assumption carried over from a DIFFERENT
    # endpoint's confirmed shape, not something observed for
    # loadLocationRecord itself — must be re-verified against a real
    # response before Phase B trusts it.
    record_header_labels = header_labels[-len(record_fields):] if header_labels else []

    semantics: list[ColumnSemantics] = []
    for i, field_name in enumerate(record_fields):
        # Priority: (1) a non-blank dynamic-header JS var — CONFIRMED
        # real evidence this label source exists and, per the same
        # evidence, is the ONLY source with real text for KLPGA's
        # dynamic-header response shape; (1b) the Sg-family menu-switch
        # JS vars (see _extract_menu_switch_metadata) — the SAME
        # confidence tier as (1), just a different real client-side
        # pattern; (2) the static table-header text, when non-blank;
        # (3) unknown, never guessed.
        if field_name in dynamic_labels:
            semantics.append(
                ColumnSemantics(field_name=field_name, label=dynamic_labels[field_name], source="dynamic_header_vars")
            )
        elif i < len(menu_switch_position_labels) and menu_switch_position_labels[i]:
            semantics.append(
                ColumnSemantics(field_name=field_name, label=menu_switch_position_labels[i], source="menu_switch_vars")
            )
        elif record_header_labels and i < len(record_header_labels) and record_header_labels[i]:
            semantics.append(
                ColumnSemantics(field_name=field_name, label=record_header_labels[i], source="table_header")
            )
        else:
            semantics.append(ColumnSemantics(field_name=field_name, label=None, source="unknown"))
    return semantics


def _extract_player_name_from_cell(tr: Tag) -> Optional[str]:
    """Fallback player-name source, used only when no `data-name`/
    `data-playername` attribute exists on the row. Real evidence
    (docs/discovery/raw_samples/Sg__Around__2025.html, pasted directly
    by the user 2026-08-26 — see docs/KLPGA_OFFICIAL_DATA_MAP.md's
    Round 8 row-extraction section) showed the Sg family's real rows
    carry NO name attribute on the `<tr>` at all: the name is the text
    of a `<a href=".../mainRecord?playerCode=...">Name</a>` nested
    inside a `<td class="text-start player_name">` cell — the same
    anchor `_extract_player_code_from_href` already reads the
    `playerCode` query param from. Falls back to the cell's own text
    if no `<a>` is present, since the evidence-confirmed container is
    the cell, not specifically its anchor child."""
    cell = tr.find(class_="player_name")
    if cell is None:
        return None
    anchor = cell.find("a")
    text = anchor.get_text(strip=True) if anchor is not None else cell.get_text(strip=True)
    return text or None


def _extract_player_code_from_href(tag: Tag) -> Optional[str]:
    """Fallback player-code source: a profile link such as
    `/web/profile/mainRecord?playerCode=9235`, per the user's directly
    reported evidence — used only when no `data-playercode`-style
    attribute is present on the row itself."""
    for a in tag.find_all("a"):
        href = _attr(a, "href") or ""
        match = re.search(r"[?&]playerCode=([^&\"'#\s]+)", href, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_rows(soup: BeautifulSoup, record_fields: list[str]) -> list[PlayerRecordRow]:
    row_tags = soup.select("tbody tr") or [
        tr for tr in soup.find_all("tr") if _attr(tr, "data-playercode") or _attr(tr, "data-player-code")
    ]

    rows: list[PlayerRecordRow] = []
    for tr in row_tags:
        player_code = (
            _attr(tr, "data-playercode")
            or _attr(tr, "data-player-code")
            or _attr(tr, "data-code")
        )
        player_code_source = "data_attribute" if player_code is not None else None
        if player_code is None:
            href_code = _extract_player_code_from_href(tr)
            if href_code is not None:
                player_code = href_code
                player_code_source = "href_query_param"

        player_name = _attr(tr, "data-name") or _attr(tr, "data-playername") or _extract_player_name_from_cell(tr)
        rank = _attr(tr, "data-rank")

        values: dict[str, Optional[str]] = {}
        for field_name in record_fields:
            values[field_name] = _attr(tr, f"data-{field_name}")

        if player_code is None and player_name is None and not any(values.values()):
            # A <tr> with none of the expected data-* attributes at all
            # is not a player row this parser recognizes — skip it
            # rather than emit a garbage row (e.g. a header/footer tr).
            continue

        rows.append(
            PlayerRecordRow(
                player_code=player_code,
                player_name=player_name,
                rank=rank,
                values=values,
                player_code_source=player_code_source,
            )
        )

    return rows


def _build_sample_definition(
    column_semantics: list[ColumnSemantics], metadata: ResponseMetadata
) -> SampleDefinition:
    labels = {c.field_name: c.label for c in column_semantics}
    rate_semantics = labels.get("record")
    numerator_semantics = labels.get("record1")
    denominator_semantics = labels.get("record2")

    sample_text = None
    if numerator_semantics and denominator_semantics:
        sample_text = f"{numerator_semantics} / {denominator_semantics}"
    elif metadata.record_note:
        sample_text = metadata.record_note

    return SampleDefinition(
        rate_semantics=rate_semantics,
        numerator_semantics=numerator_semantics,
        denominator_semantics=denominator_semantics,
        sample_definition_text=sample_text,
    )


def parse_record_response(html: str) -> ParsedRecordResponse:
    """Parse one loadLocationRecord response body. Never raises on
    malformed/unexpected input — returns parse_status="FAILED" with a
    note instead, so a batch run over many metrics can't be aborted by
    one bad response."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as exc:  # noqa: BLE001 - genuinely any parse failure should degrade, not crash
        return ParsedRecordResponse(
            metadata=ResponseMetadata(found=False),
            column_semantics=[],
            rows=[],
            sample_definition=SampleDefinition(),
            parse_status="FAILED",
            notes=[f"HTML parse error: {exc}"],
        )

    record_fields = _discover_record_fields(soup)
    metadata = _extract_metadata(soup)
    menu_switch_data_labels: dict[int, str] = {}
    if not metadata.found:
        menu_switch_metadata, menu_switch_data_labels = _extract_menu_switch_metadata(html)
        if menu_switch_metadata.menu is not None:
            metadata = menu_switch_metadata
    menu_switch_position_labels = [menu_switch_data_labels.get(i) for i in range(1, len(record_fields) + 1)]
    dynamic_labels = _extract_dynamic_header_labels(html, record_fields)
    column_semantics = _extract_column_semantics(
        soup, metadata, record_fields, dynamic_labels, menu_switch_position_labels
    )
    rows = _extract_rows(soup, record_fields)
    sample_definition = _build_sample_definition(column_semantics, metadata)

    notes: list[str] = []
    if not rows:
        status = "EMPTY"
        notes.append("No player rows found — could be a genuinely empty result or an unrecognized row shape.")
    elif all(c.source == "unknown" for c in column_semantics):
        status = "AMBIGUOUS"
        notes.append("Player rows found but no column-semantics source (metadata, dynamic-header vars, or table header) was found.")
    elif metadata.found:
        status = "CONFIRMED"
    elif dynamic_labels:
        status = "DISCOVERED_NOT_VALIDATED"
        notes.append(
            "Rows found; semantics resolved from KLPGA's dynamic-header JS vars "
            "(var record/record1/.../recordN = \"...\"), not an embedded metadata block or static table-header text."
        )
    elif any(menu_switch_position_labels):
        status = "DISCOVERED_NOT_VALIDATED"
        notes.append(
            "Rows found; semantics resolved from KLPGA's Sg-family menu-switch JS vars "
            "(var menu = \"X\"; ... else if(menu == \"X\") { data1..dataN = \"...\"; }), not an embedded "
            "metadata block or static table-header text — see _extract_menu_switch_metadata."
        )
    else:
        status = "DISCOVERED_NOT_VALIDATED"
        notes.append("Rows and header-derived labels found, but no embedded metadata block — semantics rely on table-header order only.")

    return ParsedRecordResponse(
        metadata=metadata,
        column_semantics=column_semantics,
        rows=rows,
        sample_definition=sample_definition,
        parse_status=status,
        notes=notes,
    )
