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
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

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
    user_agent: str = DEFAULT_UA
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
