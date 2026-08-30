"""Optional Discord webhook notification for NEO ops pipelines.

Reads the target webhook URL from the NEO_DISCORD_WEBHOOK_URL
environment variable by default. A missing/empty webhook is a normal,
silent no-op — it must NEVER fail or change the exit code of the
pipeline that calls this. A real network/HTTP failure while posting is
caught here and reported back as False, never re-raised, for the same
reason: a Discord outage must never block a FINAL CLOSE run.
"""
from __future__ import annotations

import os
from typing import Optional

import requests

ENV_VAR = "NEO_DISCORD_WEBHOOK_URL"


def send_discord_notification(content: str, webhook_url: Optional[str] = None, timeout: float = 10.0) -> bool:
    """Returns True only if a POST was actually attempted and the
    webhook returned a 2xx status. Returns False (never raises) for:
    missing/empty webhook, a network error, or a non-2xx response."""
    url = webhook_url if webhook_url is not None else os.environ.get(ENV_VAR)
    if not url:
        return False
    try:
        resp = requests.post(url, json={"content": content}, timeout=timeout)
        return 200 <= resp.status_code < 300
    except requests.exceptions.RequestException:
        return False
