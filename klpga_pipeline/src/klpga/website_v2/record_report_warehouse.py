"""KLPGA official "전체 기록레포트" (Record Report) Warehouse.

This is NOT a tournament round snapshot -- no game_code/round/CUT
semantics apply here. It is the official, cumulative, season-to-date
record report (money / 평균 타수 / 평균 퍼팅 / 평균 버디율 / 그린 적중률 /
파세이브율 / 파브레이크율 / 리커버리율), keyed by official playerCode,
scraped from https://klpga.co.kr/web/record/totalRecord after the
official "총보기" (View All) control is triggered (POST
/load/record/loadTotalRecord with startRow=1, endRow=999 -- see
scripts/110_build_record_report_warehouse.py for how that request is
reconstructed from a real saved capture).

The source never exposes an official total-row count anywhere in its
markup, so `population_completeness` on every snapshot this module
builds is unconditionally "UNVERIFIED" -- it must never be flipped to
"PASS" just because a parse returned more than the previous capture's
row count. That would be exactly the row-count-as-proxy-for-complete-
ness mistake this Warehouse's own audit trail exists to prevent.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

PARSER_VERSION = "record_report_v1"
SOURCE_TYPE = "klpga_official_record_report_total_view"

_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
_CODE_RE = re.compile(r"_favoritplayercode=\"(\d*)\"")
_RANK_RE = re.compile(r'class="text-start">(\d*)<')
_NAME_RE = re.compile(r'playerCode=\d+">\s*([^<\n]+?)\s*</a>')
_MONEY_RE = re.compile(r'class="record">\s*([\d,]*)')
_DATA_RE = {i: re.compile(rf'class="data{i}">([^<]*)<') for i in range(1, 8)}

# klpga.co.kr's own column order: data1..data7 == 평균 타수/평균 퍼팅/평균
# 버디율/그린 적중률/파세이브율/파브레이크율/리커버리율 (confirmed from the
# <thead> of both raw captures).
DATA_FIELD_NAMES = {
    1: "average_score",
    2: "average_putts",
    3: "birdie_rate",
    4: "gir_rate",
    5: "par_save_rate",
    6: "par_break_rate",
    7: "recovery_rate",
}


class RecordReportParseError(RuntimeError):
    """The HTML does not match the expected official record-report
    table shape -- never silently return a partial/empty result."""


class RecordReportSnapshotConflict(RuntimeError):
    """A snapshot already exists at this path with the SAME
    snapshot_id but DIFFERENT normalized content -- refuses to
    overwrite. This is the write-once hard gate: same source SHA256
    must always normalize to the same content, or something (parser
    bug, parser_version drift, wrong file) is wrong and must be
    investigated, never silently clobbered."""


def _clean_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    s = raw.strip().replace(",", "")
    return int(s) if s else None


def _clean_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    s = raw.strip()
    return float(s) if s else None


def parse_record_report_html(html: str) -> list[dict]:
    """Pure parse of the official <table class="table table-record
    table-hover"> -- one dict per real <tr>. Every *_raw field is the
    exact string found in that cell (empty string if the cell itself
    is empty); the corresponding parsed field is None when *_raw is
    empty -- NEVER 0. Tied official_rank values are preserved exactly
    as rendered (uniqueness is never enforced on rank, only on
    playerCode)."""
    start = html.find('<table class="table table-record table-hover">')
    if start == -1:
        raise RecordReportParseError("record-report table not found in HTML")
    end = html.find("</table>", start)
    if end == -1:
        raise RecordReportParseError("record-report table has no closing </table>")
    tbody_idx = html.find("<tbody>", start)
    if tbody_idx == -1 or tbody_idx > end:
        raise RecordReportParseError("record-report <tbody> not found")
    tbody = html[tbody_idx:end]

    records = []
    for row in _ROW_RE.findall(tbody):
        code_m = _CODE_RE.search(row)
        rank_m = _RANK_RE.search(row)
        name_m = _NAME_RE.search(row)
        money_m = _MONEY_RE.search(row)
        if code_m is None or not code_m.group(1):
            raise RecordReportParseError(f"row missing playerCode: {row[:200]!r}")
        if name_m is None or not name_m.group(1).strip():
            raise RecordReportParseError(f"row missing player_name: {row[:200]!r}")
        money_raw = money_m.group(1).strip() if money_m else ""
        record = {
            "official_rank": _clean_int(rank_m.group(1)) if rank_m else None,
            "playerCode": code_m.group(1),
            "player_name": name_m.group(1).strip(),
            "money_raw": money_raw,
            "money": _clean_int(money_raw),
        }
        for i, field in DATA_FIELD_NAMES.items():
            m = _DATA_RE[i].search(row)
            raw_value = m.group(1).strip() if m else ""
            record[f"{field}_raw"] = raw_value
            record[field] = _clean_float(raw_value)
        records.append(record)
    return records


def _canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


@dataclass(frozen=True)
class RecordReportSnapshot:
    snapshot_id: str
    effective_season: int
    capture_timestamp: str
    source_url: str
    source_type: str
    source_sha256: str
    parser_version: str
    menu_mode: str
    expanded_view: bool
    source_rows: int
    unique_players: int
    population_completeness: str
    records: list[dict]
    normalized_sha256: str


def build_snapshot(
    *,
    html: str,
    source_sha256: str,
    source_url: str,
    capture_timestamp: str,
    effective_season: int,
    menu_mode: str = "All",
    expanded_view: bool,
) -> RecordReportSnapshot:
    """Parse + validate + content-address one raw capture. Raises
    RecordReportParseError on any structural violation (duplicate
    playerCode, blank identity) -- never returns a snapshot that
    hasn't passed those hard gates."""
    records = parse_record_report_html(html)
    codes = [r["playerCode"] for r in records]
    if len(set(codes)) != len(codes):
        from collections import Counter
        dupes = {c: n for c, n in Counter(codes).items() if n > 1}
        raise RecordReportParseError(f"duplicate playerCode within a single source parse: {dupes}")

    payload_for_hash = {"parser_version": PARSER_VERSION, "menu_mode": menu_mode, "records": records}
    normalized_sha256 = sha256_bytes(_canonical_json(payload_for_hash).encode("utf-8"))
    snapshot_id = f"record_report_{PARSER_VERSION}_{source_sha256[:16]}"

    return RecordReportSnapshot(
        snapshot_id=snapshot_id,
        effective_season=effective_season,
        capture_timestamp=capture_timestamp,
        source_url=source_url,
        source_type=SOURCE_TYPE,
        source_sha256=source_sha256,
        parser_version=PARSER_VERSION,
        menu_mode=menu_mode,
        expanded_view=expanded_view,
        source_rows=len(records),
        unique_players=len(set(codes)),
        population_completeness="UNVERIFIED",
        records=records,
        normalized_sha256=normalized_sha256,
    )


def snapshot_to_dict(snapshot: RecordReportSnapshot) -> dict:
    return asdict(snapshot)


def write_snapshot_immutable(snapshot: RecordReportSnapshot, path: Path) -> bool:
    """Write-once, content-addressed. Returns True if a new file was
    written, False if an identical snapshot already existed
    (idempotent no-op). Raises RecordReportSnapshotConflict if the
    path already holds the same snapshot_id but different normalized
    content, or a different snapshot_id entirely."""
    path = Path(path)
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("snapshot_id") != snapshot.snapshot_id:
            raise RecordReportSnapshotConflict(
                f"{path} already holds a different snapshot_id {existing.get('snapshot_id')!r} "
                f"(new snapshot_id would be {snapshot.snapshot_id!r})"
            )
        if existing.get("normalized_sha256") != snapshot.normalized_sha256:
            raise RecordReportSnapshotConflict(
                f"snapshot_id {snapshot.snapshot_id} already exists at {path} with a DIFFERENT "
                f"normalized_sha256 ({existing.get('normalized_sha256')!r} != {snapshot.normalized_sha256!r})"
            )
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot_to_dict(snapshot), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def join_identity_by_player_code(record_report_records: list[dict], cohort: list[dict]) -> dict:
    """Join STRICTLY by official playerCode/player_id -- never a
    name-only fallback. `cohort` rows must each carry player_id and
    player_name (e.g. TOP120 rows, or a NEO-ranked/pending subset of
    them)."""
    by_code = {r["playerCode"]: r for r in record_report_records}
    matched, unmatched, name_conflicts = [], [], []
    for row in cohort:
        pid = str(row["player_id"])
        rr = by_code.get(pid)
        if rr is None:
            unmatched.append({"player_id": pid, "player_name": row["player_name"]})
            continue
        matched.append(pid)
        if rr["player_name"] != row["player_name"]:
            name_conflicts.append({
                "player_id": pid,
                "record_report_name": rr["player_name"],
                "cohort_name": row["player_name"],
            })
    return {"matched": matched, "unmatched": unmatched, "name_conflicts": name_conflicts}
