"""Shared single-metric fetch+parse+analyze step for `loadLocationRecord`
requests — extracted from scripts/27_klpga_response_schema_sample.py
(Round 3 Phase B1) so Phase B2's full-canonical-sweep script
(scripts/29_execute_phase_b2_full_sweep.py, Round 9 follow-up) reuses
the EXACT same, already-tested request/parse/log-entry logic instead
of duplicating it. Behavior is unchanged from the original script-local
version — only the log sink became a parameter (`log`), since scripts/27
and scripts/29 each track their own last-known-execution-point state
for their own Ctrl+C diagnostics.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from klpga import config
from klpga.discovery.request_log import build_log_entry
from klpga.discovery.response_parser import parse_record_response
from klpga.discovery.response_schema import analyze_response
from klpga.discovery.sampler import SampledLeaf
from klpga.http_client import PoliteHttpClient


def _default_log(msg: str) -> None:
    print(msg, flush=True)


def request_form(leaf: SampledLeaf, season: str) -> dict:
    """TYPE A (menu2-level) or TYPE B (menu3-level) request shape, per
    the already-confirmed evidence — never a third shape."""
    form = {"season": season, "menu1": leaf.menu1, "menu2": leaf.menu2}
    if leaf.leaf_level == "menu3":
        form["menu3"] = leaf.menu3
    return form


def sanitize_identity_key_for_filename(key: str) -> str:
    """"Approach::Approach01::020101" -> "Approach__Approach01__020101"
    — filesystem-safe, still human-readable and traceable back to the
    exact canonical identity, unlike PoliteHttpClient's own hash-keyed
    cache filenames."""
    return key.replace("::", "__").replace("/", "_").replace("\\", "_")


def fetch_and_analyze(
    client: PoliteHttpClient,
    leaf: SampledLeaf,
    season: str,
    *,
    tag: str = "?",
    raw_dir: Optional[Path] = None,
    log: Callable[[str], None] = _default_log,
):
    """Returns (parsed, analysis, log_entry). Raises RateLimitBlockedError
    unmodified — the caller decides whether that halts the whole run.
    `tag` (e.g. "3/20" or "142/277") is purely for the REQUEST/
    RESPONSE/PARSE diagnostic markers below — it plays no role in the
    request itself.

    `raw_dir`, if given, saves the exact raw response body to
    `raw_dir/<identity_key>__<season>.html` — Phase B1.1's raw-evidence
    preservation (see Mission 3): PoliteHttpClient already caches every
    response under data/raw_cache/http/ keyed by an opaque content
    hash, which technically preserves the bytes but makes finding "the
    Putt::Putt01::040101 response" by hand impractical. This writes a
    second, small, human-named copy — bounded by the caller's own
    request cap, never unbounded."""
    form = request_form(leaf, season)
    log(f"[REQUEST {tag}] menu1={leaf.menu1!r} menu2={leaf.menu2!r} menu3={leaf.menu3!r} season={season!r}")
    timestamp = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    html = client.post_text(config.RECORD_TAXONOMY_ENDPOINT, data=form)
    elapsed = time.perf_counter() - start
    log(f"[RESPONSE {tag}] status=200(assumed — client raises on 401/403/429/5xx) bytes={len(html)} elapsed={elapsed:.2f}s")
    if raw_dir is not None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"{sanitize_identity_key_for_filename(leaf.source_metric_key)}__{season}.html"
        raw_path.write_text(html, encoding="utf-8")
        log(f"[RAW SAVED {tag}] {raw_path}")
    parsed = parse_record_response(html)
    log(f"[PARSE {tag}] parse_status={parsed.parse_status} rows={len(parsed.rows)}")
    analysis = analyze_response(parsed)
    log_entry = build_log_entry(
        timestamp=timestamp,
        endpoint=config.RECORD_TAXONOMY_ENDPOINT,
        method="POST",
        season=season,
        menu1=leaf.menu1,
        menu2=leaf.menu2,
        menu3=leaf.menu3,
        canonical_identity=leaf.source_metric_key,
        http_status=200,  # PoliteHttpClient raises rather than returning a non-2xx Response
        response_size=len(html),
        parse_status=parsed.parse_status,
    )
    return parsed, analysis, log_entry
