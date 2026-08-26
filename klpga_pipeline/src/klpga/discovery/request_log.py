"""Auditable Phase B request log. Structurally redacted: the entry
dataclass has no field capable of holding cookies, auth tokens,
session secrets, or headers of any kind — this is enforced by the
schema itself, not by a filter that could be forgotten or bypassed.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass
from typing import Optional


@dataclass(frozen=True)
class RequestLogEntry:
    timestamp: str
    endpoint: str
    method: str
    season: str
    menu1: str
    menu2: str
    menu3: Optional[str]
    canonical_identity: str
    http_status: Optional[int]
    response_size: Optional[int]
    parse_status: str


def build_log_entry(
    *,
    timestamp: str,
    endpoint: str,
    method: str,
    season: str,
    menu1: str,
    menu2: str,
    menu3: Optional[str],
    canonical_identity: str,
    http_status: Optional[int],
    response_size: Optional[int],
    parse_status: str,
) -> RequestLogEntry:
    return RequestLogEntry(
        timestamp=timestamp,
        endpoint=endpoint,
        method=method,
        season=season,
        menu1=menu1,
        menu2=menu2,
        menu3=menu3,
        canonical_identity=canonical_identity,
        http_status=http_status,
        response_size=response_size,
        parse_status=parse_status,
    )


def to_log_jsonl(entries: list[RequestLogEntry]) -> str:
    return "\n".join(json.dumps(asdict(e), ensure_ascii=False) for e in entries)


def to_log_csv(entries: list[RequestLogEntry]) -> str:
    buf = io.StringIO()
    fieldnames = [
        "timestamp",
        "endpoint",
        "method",
        "season",
        "menu1",
        "menu2",
        "menu3",
        "canonical_identity",
        "http_status",
        "response_size",
        "parse_status",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for e in entries:
        row = asdict(e)
        row["menu3"] = row["menu3"] or ""
        writer.writerow(row)
    return buf.getvalue()
