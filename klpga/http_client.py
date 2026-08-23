"""HTTP client with timeout, retry+backoff, rate limiting, caching, and logging.

This is the only place that talks to the network for static (non-JS)
pages. Keeping all of the resilience/politeness behavior in one function
means every adapter gets it for free.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from . import cache, config

logger = logging.getLogger("klpga.http")

_last_request_at = 0.0


class FetchError(Exception):
    """Raised when a URL could not be fetched after all retries."""


def _respect_rate_limit() -> None:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    wait = config.MIN_REQUEST_INTERVAL_SECONDS - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def get(
    url: str,
    *,
    params: Optional[dict] = None,
    use_cache: bool = True,
    cache_ttl_seconds: Optional[int] = None,
    session: Optional[requests.Session] = None,
) -> str:
    """Fetch a URL and return response text.

    Uses the on-disk cache first, then retries live requests with
    exponential backoff, waiting at least MIN_REQUEST_INTERVAL_SECONDS
    between live requests. Raises FetchError if the request ultimately
    fails after config.MAX_RETRIES attempts.
    """
    if use_cache:
        cached = cache.get(url, params, cache_ttl_seconds)
        if cached is not None:
            logger.debug("cache hit: %s", url)
            return cached

    sess = session or requests.Session()
    headers = {"User-Agent": config.USER_AGENT}

    last_exc: Optional[Exception] = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        _respect_rate_limit()
        try:
            resp = sess.get(url, params=params, headers=headers, timeout=config.REQUEST_TIMEOUT_SECONDS)
            if resp.status_code >= 500 or resp.status_code == 429:
                raise requests.HTTPError(f"retryable status {resp.status_code}", response=resp)
            resp.raise_for_status()
            resp.encoding = resp.encoding or "utf-8"
            text = resp.text
            if use_cache:
                cache.set(url, params, text)
            logger.info("fetched %s (attempt %d, %d bytes)", url, attempt, len(text))
            return text
        except requests.RequestException as exc:
            last_exc = exc
            backoff = config.BACKOFF_BASE_SECONDS ** attempt
            logger.warning(
                "fetch failed (%s), attempt %d/%d, backing off %.1fs: %s",
                url, attempt, config.MAX_RETRIES, backoff, exc,
            )
            if attempt < config.MAX_RETRIES:
                time.sleep(backoff)

    raise FetchError(f"failed to fetch {url} after {config.MAX_RETRIES} attempts") from last_exc
