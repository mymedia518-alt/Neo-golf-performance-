"""KLPGA official Strokes-Gained (SG) Warehouse.

Parses https://klpga.co.kr/web/record/locationRecord (총보기) into an
immutable, content-addressed snapshot -- the OFFICIAL SG figures KLPGA
itself publishes per player (SG 전체/티샷/어프로치/그린주변/퍼팅, plus
측정 라운드 수, the number of rounds that SG figure was measured over).

This is deliberately a SEPARATE namespace from NEO's own internally
computed SG figures (klpga.website_v2.record_report_warehouse /
home_ranking / neo_ranking_backtest). OFFICIAL SG and NEO SG must
never be merged into the same field -- every field name here is
prefixed `official_sg_*` specifically to make an accidental merge
structurally obvious in a code review.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

PARSER_VERSION = "official_sg_v1"
SOURCE_TYPE = "klpga_official_sg_location_record"

_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
_CODE_RE = re.compile(r"_favoritplayercode=\"(\d*)\"")
_RANK_RE = re.compile(r'class="text-start">(\d*)<')
_NAME_RE = re.compile(r'class="text-start player_name">(.*?)</td>', re.DOTALL)
_TOTAL_RE = re.compile(r'class="record"[^>]*>(.*?)<!--', re.DOTALL)
_DATA_RE = {i: re.compile(rf'class="data{i}"[^>]*>(.*?)</td>', re.DOTALL) for i in range(1, 6)}

# klpga.co.kr's own column order on this page's <thead>: SG:전체(record),
# data1=SG:티샷, data2=SG:어프로치, data3=SG:그린주변, data4=SG:퍼팅,
# data5=측정 라운드 수 (an integer round count, NOT a rate/SG value).
_DATA_FIELD_NAMES = {
    1: "official_sg_ott",
    2: "official_sg_app",
    3: "official_sg_arg",
    4: "official_sg_putt",
}


class OfficialSGParseError(RuntimeError):
    pass


class OfficialSGSnapshotConflict(RuntimeError):
    """Same snapshot_id (same source_sha256) but different normalized
    content already exists on disk -- refuses to overwrite silently."""


def _strip_html_whitespace(raw: str) -> str:
    # cell text is buried in nested whitespace/comments; the outermost
    # numeric token is what klpga.co.kr actually displays.
    text = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _clean_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    s = raw.strip()
    return float(s) if s else None


def _clean_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    s = raw.strip()
    return int(s) if s else None


def parse_official_sg_html(html: str) -> list[dict]:
    """Pure parse of the official SG <table class="table table-record
    table-hover"> on locationRecord. One dict per <tr>. Every
    *_raw field is the exact displayed text (empty string if blank);
    the parsed field is None (never 0) when *_raw is empty.
    official_rank may legitimately be blank (unranked -- e.g. below
    the site's own ranking cutoff), preserved as None, never guessed."""
    start = html.find('<table class="table table-record table-hover">')
    if start == -1:
        raise OfficialSGParseError("official SG table not found in HTML")
    end = html.find("</table>", start)
    if end == -1:
        raise OfficialSGParseError("official SG table has no closing </table>")
    tbody_idx = html.find("<tbody>", start)
    if tbody_idx == -1 or tbody_idx > end:
        raise OfficialSGParseError("official SG <tbody> not found")
    tbody = html[tbody_idx:end]

    records = []
    for row in _ROW_RE.findall(tbody):
        code_m = _CODE_RE.search(row)
        rank_m = _RANK_RE.search(row)
        name_m = _NAME_RE.search(row)
        total_m = _TOTAL_RE.search(row)
        if code_m is None or not code_m.group(1):
            raise OfficialSGParseError(f"row missing playerCode: {row[:200]!r}")
        player_name = _strip_html_whitespace(name_m.group(1)) if name_m else ""
        if not player_name:
            raise OfficialSGParseError(f"row missing player_name: {row[:200]!r}")
        total_raw = _strip_html_whitespace(total_m.group(1)) if total_m else ""
        record = {
            "official_rank": _clean_int(rank_m.group(1)) if rank_m else None,
            "playerCode": code_m.group(1),
            "player_name": player_name,
            "official_sg_total_raw": total_raw,
            "official_sg_total": _clean_float(total_raw),
        }
        for i, field in _DATA_FIELD_NAMES.items():
            m = _DATA_RE[i].search(row)
            raw_value = _strip_html_whitespace(m.group(1)) if m else ""
            record[f"{field}_raw"] = raw_value
            record[field] = _clean_float(raw_value)
        rounds_m = _DATA_RE[5].search(row)
        rounds_raw = _strip_html_whitespace(rounds_m.group(1)) if rounds_m else ""
        record["official_sg_rounds_raw"] = rounds_raw
        record["official_sg_rounds"] = _clean_int(rounds_raw)
        records.append(record)
    return records


def _canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


@dataclass(frozen=True)
class OfficialSGSnapshot:
    snapshot_id: str
    effective_season: int
    capture_timestamp: str
    source_url: str
    source_type: str
    source_sha256: str
    parser_version: str
    menu_mode: str
    source_rows: int
    unique_players: int
    population_completeness: str
    records: list[dict]
    normalized_sha256: str


def build_snapshot(
    *, html: str, source_sha256: str, source_url: str, capture_timestamp: str,
    effective_season: int, menu_mode: str = "All",
) -> OfficialSGSnapshot:
    records = parse_official_sg_html(html)
    codes = [r["playerCode"] for r in records]
    if len(set(codes)) != len(codes):
        from collections import Counter
        dupes = {c: n for c, n in Counter(codes).items() if n > 1}
        raise OfficialSGParseError(f"duplicate playerCode within a single source parse: {dupes}")

    payload_for_hash = {"parser_version": PARSER_VERSION, "menu_mode": menu_mode, "records": records}
    normalized_sha256 = sha256_bytes(_canonical_json(payload_for_hash).encode("utf-8"))
    snapshot_id = f"official_sg_{PARSER_VERSION}_{source_sha256[:16]}"

    return OfficialSGSnapshot(
        snapshot_id=snapshot_id, effective_season=effective_season, capture_timestamp=capture_timestamp,
        source_url=source_url, source_type=SOURCE_TYPE, source_sha256=source_sha256, parser_version=PARSER_VERSION,
        menu_mode=menu_mode, source_rows=len(records), unique_players=len(set(codes)),
        population_completeness="UNVERIFIED", records=records, normalized_sha256=normalized_sha256,
    )


def snapshot_to_dict(snapshot: OfficialSGSnapshot) -> dict:
    return asdict(snapshot)


def write_snapshot_immutable(snapshot: OfficialSGSnapshot, path: Path) -> bool:
    path = Path(path)
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("snapshot_id") != snapshot.snapshot_id:
            raise OfficialSGSnapshotConflict(
                f"{path} already holds a different snapshot_id {existing.get('snapshot_id')!r} "
                f"(new snapshot_id would be {snapshot.snapshot_id!r})"
            )
        if existing.get("normalized_sha256") != snapshot.normalized_sha256:
            raise OfficialSGSnapshotConflict(
                f"snapshot_id {snapshot.snapshot_id} already exists at {path} with a DIFFERENT "
                f"normalized_sha256 ({existing.get('normalized_sha256')!r} != {snapshot.normalized_sha256!r})"
            )
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot_to_dict(snapshot), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True
