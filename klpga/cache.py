"""Simple on-disk HTTP response cache keyed by request URL (+ params).

Keeps re-runs of the collector from re-fetching pages it already has, and
keeps load on klpga.co.kr / data.klpga.co.kr low.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional, Tuple

from . import config


def _key(url: str, params: Optional[dict]) -> str:
    raw = url + "?" + json.dumps(params or {}, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _paths(key: str) -> Tuple[Path, Path]:
    body = config.CACHE_DIR / f"{key}.body"
    meta = config.CACHE_DIR / f"{key}.json"
    return body, meta


def get(url: str, params: Optional[dict] = None, ttl_seconds: Optional[int] = None) -> Optional[str]:
    ttl = config.CACHE_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    key = _key(url, params)
    body_path, meta_path = _paths(key)
    if not body_path.exists() or not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if time.time() - meta.get("fetched_at", 0) > ttl:
        return None
    try:
        return body_path.read_text(encoding="utf-8")
    except OSError:
        return None


def set(url: str, params: Optional[dict], body: str) -> None:
    key = _key(url, params)
    body_path, meta_path = _paths(key)
    body_path.write_text(body, encoding="utf-8")
    meta_path.write_text(
        json.dumps({"url": url, "params": params, "fetched_at": time.time()}),
        encoding="utf-8",
    )
