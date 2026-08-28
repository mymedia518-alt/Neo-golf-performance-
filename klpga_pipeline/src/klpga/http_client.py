"""Rate-limited, retrying, disk-cached HTTP client for KLPGA scraping.

Design goals (per project requirements):
 - Never hammer the official site: a minimum delay between requests plus
   jitter, enforced globally per host.
 - Cache every successful response to disk keyed by URL (+ params), so
   re-running a collection step during development does not re-hit the
   network, and so a failed later stage can resume without re-fetching
   pages already saved.
 - Retry transient failures (timeouts, 5xx, connection errors) with
   exponential backoff; do NOT retry 403/401/429 blindly (403/401 likely
   mean access is restricted and must be surfaced, not brute-forced; 429
   backs off much longer instead of retrying quickly).

**Phase B1.1 diagnostic note** (added after a Windows run of
scripts/27 produced no visible output and had to be Ctrl+C'd): every
value below was ALREADY finite before this round — no timeout/retry
value was weakened or newly added, only made visible via the optional
`on_retry` callback (see `PoliteHttpClient.on_retry`).

  - Connect timeout: `timeout_sec` (default 20.0s)
  - Read timeout: `timeout_sec` (default 20.0s, the SAME value —
    `requests` applies a single float to both phases separately, so
    one attempt's HTTP call can take up to ~2x `timeout_sec` in the
    worst case: slow connect, then a slow/stalled read)
  - Retry count: `stop_after_attempt(4)` — 4 total attempts (1 initial
    + 3 retries), only for `_retryable` exceptions (5xx, connection
    errors, timeouts, chunked-encoding errors) — NEVER for
    `RateLimitBlockedError` (401/403/429), which raises immediately
  - Backoff: `wait_exponential_jitter(initial=2, max=30)` — waits
    between attempts scale ~2s, ~4s, ~8s (+ random jitter), capped at
    30s; 3 such waits occur across 4 attempts
  - Rate-limit throttle: `min_interval_sec` (default 1.5s) +
    `random.uniform(0, jitter_sec)` (default up to 0.8s) BEFORE each
    top-level client call (get_json/get_text/post_text/post_json) —
    this is once per call, not once per retry attempt
  - Worst-case single top-level call, all 4 attempts exhausted and
    every attempt fully timing out on both connect and read:
    throttle (~2.3s) + 4 × (2 × 20.0s) [attempts] + (~2+4+8s) [backoff
    waits] ≈ 2.3 + 160 + 14 ≈ **~176s (~3 minutes), bounded, not
    infinite** — long enough to look like a hang without visible
    progress, which is exactly what the `on_retry` callback and
    scripts/27's REQUEST/RESPONSE markers now surface.
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger("klpga.http")

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class RateLimitBlockedError(RuntimeError):
    """Raised when the site itself returns 401/403/429 — do not brute force this."""


def _before_sleep_log(retry_state) -> None:
    """tenacity `before_sleep` hook — fires right before each retry's
    backoff sleep. Only produces visible output for a client that
    opted in via `on_retry` (see `PoliteHttpClient.on_retry`); every
    other existing caller of this client is completely unaffected
    (on_retry defaults to None). Added for scripts/27's hang
    diagnostics — a request stuck retrying looks identical to a truly
    hung request without this."""
    self = retry_state.args[0] if retry_state.args else None
    on_retry = getattr(self, "on_retry", None)
    if on_retry is None:
        return
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    wait = retry_state.next_action.sleep if retry_state.next_action else 0.0
    on_retry(
        f"attempt {retry_state.attempt_number} failed ({exc!r}); "
        f"sleeping {wait:.1f}s before retry"
    )


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, RateLimitBlockedError):
        return False
    if isinstance(exc, requests.exceptions.HTTPError):
        status = exc.response.status_code if exc.response is not None else None
        return status is not None and status >= 500
    return isinstance(
        exc,
        (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
        ),
    )


@dataclass
class PoliteHttpClient:
    """A requests.Session wrapper with per-host rate limiting + disk cache."""

    cache_dir: Path
    min_interval_sec: float = 1.5
    jitter_sec: float = 0.8
    timeout_sec: float = 20.0
    """Applied to BOTH the connect phase and the read phase (requests'
    behavior when given a single float — see
    https://requests.readthedocs.io/en/latest/user/advanced/#timeouts).
    A single request attempt can therefore take up to ~2x this value
    in the worst case (slow connect, then a slow/stalled read), not
    just this value once. See PoliteHttpClient's module-level docstring
    additions (Phase B1.1 diagnostic round) for the resulting
    worst-case-per-request math."""
    user_agent: str = DEFAULT_UA
    on_retry: Optional[Callable[[str], None]] = None
    """Optional callback invoked with a diagnostic string before each
    retry's backoff sleep. None (the default) means completely silent,
    unchanged behavior — every existing caller of this client keeps
    its current behavior exactly. Only a caller that explicitly wants
    visible retry/backoff progress (e.g. scripts/27's hang
    diagnostics) sets this."""
    session: requests.Session = field(default_factory=requests.Session)
    _last_request_ts: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            }
        )

    def _cache_key(self, url: str, params: Optional[dict] = None) -> str:
        raw = url + "|" + json.dumps(params or {}, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
        return digest

    def _cache_path(self, url: str, params: Optional[dict]) -> Path:
        return self.cache_dir / f"{self._cache_key(url, params)}.json"

    def _throttle(self, host: str) -> None:
        now = time.monotonic()
        last = self._last_request_ts.get(host)
        if last is not None:
            elapsed = now - last
            wait_for = self.min_interval_sec - elapsed
            if wait_for > 0:
                time.sleep(wait_for + random.uniform(0, self.jitter_sec))
        self._last_request_ts[host] = time.monotonic()

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=2, max=30),
        retry=retry_if_exception(_retryable),
        before_sleep=_before_sleep_log,
    )
    def _do_request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        resp = self.session.request(method, url, timeout=self.timeout_sec, **kwargs)
        if resp.status_code in (401, 403, 429):
            raise RateLimitBlockedError(
                f"{resp.status_code} from {url} — site-side access restriction, not retrying"
            )
        resp.raise_for_status()
        return resp

    def get_json(
        self,
        url: str,
        params: Optional[dict] = None,
        use_cache: bool = True,
        headers: Optional[dict] = None,
    ) -> Any:
        cache_path = self._cache_path(url, params)
        if use_cache and cache_path.exists():
            logger.debug("cache hit: %s %s", url, params)
            return json.loads(cache_path.read_text(encoding="utf-8"))["body_json"]

        host = requests.utils.urlparse(url).netloc
        self._throttle(host)
        resp = self._do_request("GET", url, params=params, headers=headers)
        data = resp.json()
        cache_path.write_text(
            json.dumps({"url": url, "params": params, "body_json": data}, ensure_ascii=False),
            encoding="utf-8",
        )
        return data

    def get_text(
        self,
        url: str,
        params: Optional[dict] = None,
        use_cache: bool = True,
        headers: Optional[dict] = None,
    ) -> str:
        cache_path = self._cache_path(url, params)
        if use_cache and cache_path.exists():
            logger.debug("cache hit: %s %s", url, params)
            return json.loads(cache_path.read_text(encoding="utf-8"))["body_text"]

        host = requests.utils.urlparse(url).netloc
        self._throttle(host)
        resp = self._do_request("GET", url, params=params, headers=headers)
        text = resp.text
        cache_path.write_text(
            json.dumps({"url": url, "params": params, "body_text": text}, ensure_ascii=False),
            encoding="utf-8",
        )
        return text

    def get_text_with_status(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> tuple[int, str]:
        """Always-live GET (never served from the disk cache) that
        returns `(status_code, body_text)`. Added for a caller that
        needs to report the real, current HTTP status of a single
        fetch (e.g. a diagnostic script proving a real network call
        actually happened) rather than just the body text `get_text`
        returns. Same throttle/retry/timeout behavior as every other
        method on this client; a non-2xx response still raises via
        `_do_request`'s `raise_for_status()` (or `RateLimitBlockedError`
        for 401/403/429) rather than being swallowed here."""
        host = requests.utils.urlparse(url).netloc
        self._throttle(host)
        resp = self._do_request("GET", url, params=params, headers=headers)
        return resp.status_code, resp.text

    def post_text(
        self,
        url: str,
        data: Optional[dict] = None,
        use_cache: bool = True,
        headers: Optional[dict] = None,
    ) -> str:
        """POST that returns an HTML/text body (e.g. roundLeaderboard,
        which responds with an HTML fragment rather than JSON)."""
        cache_key_params = {"data": data}
        cache_path = self._cache_path(url, cache_key_params)
        if use_cache and cache_path.exists():
            logger.debug("cache hit: %s %s", url, data)
            return json.loads(cache_path.read_text(encoding="utf-8"))["body_text"]

        host = requests.utils.urlparse(url).netloc
        self._throttle(host)
        resp = self._do_request("POST", url, data=data, headers=headers)
        text = resp.text
        cache_path.write_text(
            json.dumps(
                {"url": url, "params": cache_key_params, "body_text": text},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return text

    def post_json(
        self,
        url: str,
        data: Optional[dict] = None,
        json_body: Optional[dict] = None,
        use_cache: bool = True,
        headers: Optional[dict] = None,
    ) -> Any:
        cache_key_params = {"data": data, "json": json_body}
        cache_path = self._cache_path(url, cache_key_params)
        if use_cache and cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))["body_json"]

        host = requests.utils.urlparse(url).netloc
        self._throttle(host)
        resp = self._do_request("POST", url, data=data, json=json_body, headers=headers)
        result = resp.json()
        cache_path.write_text(
            json.dumps(
                {"url": url, "params": cache_key_params, "body_json": result},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return result
