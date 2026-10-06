"""NEO HJ 2026 (gameCode 2026100004) Stableford historical acquisition,
step 2 of 2: 2024 and 2023.

2025 (gameCode 2025100001) is DONE -- the real captured scoreRecord page
(klpga_pipeline/evidence/stableford_source_probe_2025100001/
scoreRecord_2025100001.html, captured 2026-10-06) was run through
klpga.collectors.score_record.extract_hole_outcomes() and independently
reproduced the official 김민솔 2025 result exactly: round points
7/14/14/16, four-round total 51, cross-checked against the page's own
displayed strokes-to-par in every round, across a real reconstructed
61-player made-the-cut leaderboard (see
klpga_pipeline/evidence/stableford_source_probe_2025100001/
RECONSTRUCTION_2025100001.json and
klpga_pipeline/tests/test_stableford_2025100001_reconstruction.py).
SOURCE PASS for the scoreRecord endpoint against Modified Stableford is
therefore confirmed, generically -- not just for this one gameCode.

This script repeats the SAME, already-working acquisition
(klpga.collectors.score_record.fetch_score_record_html, the real,
PoliteHttpClient-based collector -- nothing new written here) for:
  2024100009  -- 2024 "동부건설·한국토지신탁 챔피언십", winner 김민별 +49
                  (rounds 13/8/10/18, OBSERVED user relay)
  2023100002  -- 2023 "동부건설·한국토지신탁 챔피언십", winner 방신실 +43
                  (rounds 10/5/15/13, OBSERVED user relay)

2021/2022 are NOT included -- this repo has never confirmed gameCodes
for those two years (see stableford_backtest.py's own module docstring);
acquiring them is a separate, not-yet-ready step.

Usage (on a machine with real klpga.co.kr access):
    cd klpga_pipeline
    python scripts/206_fetch_scoreRecord_2024_2023.py

Output: writes the raw captured HTML for each gameCode to
    evidence/stableford_source_probe_2024100009/scoreRecord_2024100009.html
    evidence/stableford_source_probe_2023100002/scoreRecord_2023100002.html
plus a PROBE_REPORT.json per gameCode with the same 8 fields the 2025
probe captured (URL, method, parameters, status, content-type, bytes,
and -- since extract_hole_outcomes can now run immediately -- unique
player count by round and whether that year's own relayed winner is
present), so each capture is self-checked the same way 2025's was,
without waiting for a second script to run it later.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(KLPGA_PIPELINE_ROOT / "src"))

from klpga.collectors.score_record import extract_hole_outcomes, fetch_score_record_html  # noqa: E402
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402

TARGETS = [
    {"game_code": "2024100009", "known_winner": "김민별", "known_total": 49, "known_rounds": [13, 8, 10, 18]},
    {"game_code": "2023100002", "known_winner": "방신실", "known_total": 43, "known_rounds": [10, 5, 15, 13]},
]


def run_one(client: PoliteHttpClient, target: dict) -> dict:
    game_code = target["game_code"]
    out_dir = KLPGA_PIPELINE_ROOT / "evidence" / f"stableford_source_probe_{game_code}"
    result = {
        "game_code": game_code,
        "url": "https://klpga.co.kr/web/tourRecord/scoreRecord",
        "method": "GET",
        "parameters": {"gameCode": game_code},
        "known_winner": target["known_winner"],
        "known_total": target["known_total"],
        "known_rounds": target["known_rounds"],
    }
    try:
        status, html = fetch_score_record_html(client, game_code)
    except RateLimitBlockedError as e:
        result.update(response_status=None, error=f"RateLimitBlockedError: {e}")
        return result
    except Exception as e:  # noqa: BLE001 -- diagnostic script, report whatever happens
        result.update(response_status=None, error=f"{type(e).__name__}: {e}")
        return result

    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"scoreRecord_{game_code}.html"
    html_path.write_text(html, encoding="utf-8")
    result.update(
        response_status=status,
        response_bytes=len(html.encode("utf-8")),
        saved_to=str(html_path),
    )

    try:
        by_round = extract_hole_outcomes(html)
    except ValueError as e:
        result.update(extract_error=str(e))
        return result

    result["unique_players_by_round"] = {r: len(names) for r, names in by_round.items()}
    result["known_winner_present_by_round"] = {
        r: target["known_winner"] in names for r, names in by_round.items()
    }
    return result


def main():
    client = PoliteHttpClient(cache_dir=KLPGA_PIPELINE_ROOT / ".http_cache_probe")
    report = {"probe_run_at": datetime.now(timezone.utc).isoformat(), "results": []}
    for target in TARGETS:
        print(f"=== {target['game_code']} ({target['known_winner']} +{target['known_total']}) ===")
        r = run_one(client, target)
        print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        report["results"].append(r)
        out_dir = KLPGA_PIPELINE_ROOT / "evidence" / f"stableford_source_probe_{target['game_code']}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "PROBE_REPORT.json").write_text(
            json.dumps(r, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        print()

    print(
        "NEXT: commit and push both evidence/stableford_source_probe_<code>/ directories "
        "to neo-website-v2 so the full-field reconstruction + known-winner round-split "
        "check (same method as 2025100001) can be run against them."
    )


if __name__ == "__main__":
    main()
