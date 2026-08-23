"""Project-wide configuration: paths, network endpoints, and tunables.

Endpoints and selectors marked TODO are best-effort placeholders. The
development environment this project was built in has no outbound network
access to klpga.co.kr / data.klpga.co.kr, so these values have never been
verified against the live site. Before running a real collection:

1. Open https://klpga.co.kr and https://data.klpga.co.kr in a browser with
   devtools open, find the real schedule/leaderboard pages and API calls.
2. Update ENDPOINTS below and the selectors in klpga/selectors.py.
3. Run `python -m klpga.collect --events 1` against a single tournament
   first and inspect data/klpga_history.db before doing a full run.

See docs/SITE_STRUCTURE_TODO.md for the full checklist.
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
EXPORT_DIR = DATA_DIR / "export"
LOG_DIR = PROJECT_ROOT / "logs"
REPORT_DIR = PROJECT_ROOT / "reports"
DB_PATH = DATA_DIR / "klpga_history.db"

for _dir in (DATA_DIR, CACHE_DIR, EXPORT_DIR, LOG_DIR, REPORT_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://klpga.co.kr"
DATA_BASE_URL = "https://data.klpga.co.kr"

# --- Endpoints -----------------------------------------------------------
# TODO(CONFIRM ON A PC WITH REAL ACCESS): these paths are unverified
# placeholders and must be corrected before real collection will work.
ENDPOINTS = {
    "tournament_list": f"{DATA_BASE_URL}/web/tour/scheduleList.do",
    "tournament_detail": f"{DATA_BASE_URL}/web/tour/scheduleDetail.do",
    "leaderboard": f"{DATA_BASE_URL}/web/tour/playerScoreList.do",
}

# --- HTTP client tunables --------------------------------------------------
USER_AGENT = os.environ.get(
    "KLPGA_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NeoGolfDataCollector/0.1 "
    "(+https://github.com/mymedia518-alt/neo-golf-performance-)",
)
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("KLPGA_TIMEOUT", "20"))
MAX_RETRIES = int(os.environ.get("KLPGA_MAX_RETRIES", "4"))
BACKOFF_BASE_SECONDS = float(os.environ.get("KLPGA_BACKOFF_BASE", "1.5"))
MIN_REQUEST_INTERVAL_SECONDS = float(os.environ.get("KLPGA_MIN_INTERVAL", "1.2"))
CACHE_TTL_SECONDS = int(os.environ.get("KLPGA_CACHE_TTL", str(7 * 24 * 3600)))

PLAYWRIGHT_NAV_TIMEOUT_MS = int(os.environ.get("KLPGA_PW_TIMEOUT_MS", "30000"))
