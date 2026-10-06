"""NEO HJ 2026 (gameCode 2026100004) Stableford data-source discovery probe.

ONE script, run ONCE, from a machine with real internet access to
klpga.co.kr (this sandbox's egress is blocked -- confirmed again this
session via curl/WebFetch, consistent with every attempt all session).

Purpose: find out whether EITHER of two already-confirmed-for-stroke-play
KLPGA endpoints also serves data for Modified Stableford tournaments --
the one endpoint actually tried so far for this (roundLeaderboard) was
live-confirmed (2026-08-24, round=1..8 exhaustive probe) to return ZERO
player rows for gameCode 2023100002/2024100009/2025100001 (see
HJ_2026100004_STABLEFORD_GAP.md section 4). These two have NOT been tried
against a Stableford gameCode yet:

  1. PRIMARY: GET https://klpga.co.kr/web/tourRecord/scoreRecord?gameCode=<code>
     ("대회기록" -- tournament record). Real, already-confirmed-working
     fixture on file for a STROKE-PLAY tournament
     (tests/fixtures/score_record_2026120001_r1.html, OK저축은행 읏맨 오픈
     R1, 821KB, real KLPGA page markup) carries exactly the per-hole
     outcome CSS classes needed (`class="par"` x2091, `"birdies"` x413,
     `"bogeys"` x586, `"Dbogeys"` x60 in that one fixture, across what
     looks like the whole field in one page) -- this collector
     (klpga.collectors.score_record.fetch_score_record_html) already
     exists and is reused here unmodified, not reimplemented.

  2. SECONDARY (fallback if #1 doesn't pan out): POST
     https://klpga.co.kr/load/profile/scoreDetail with
     playerCode/gameCode/playerName -- real, live-confirmed 2026-10-03
     (GitHub Actions runner) for a stroke-play gameCode, with a saved
     218KB real fixture (tests/fixtures/official_detail/8436_scoreDetail
     .html) carrying the same par/birdies/bogeys/Dbogeys classes. This is
     PER-PLAYER (one call per player), so even if it works for Stableford
     it only "extends to the full field" via N calls, not one -- #1 is
     strictly better if it works.

Targets 2025100001 first (2025's "동부건설 · 한국토지신탁 챔피언십" =
this tournament's own prior identity -- see HJ_2026100004_STABLEFORD_GAP
.md section 1), with 김민솔 (playerCode 10725, already cross-validated
this session against official money-rank data) as the known-answer check:
her official final score was +51 (modified Stableford points) -- per the
official round-by-round split relayed this session, +7/+14/+14/+16.

SOURCE PASS requires ALL of:
  1. player names actually come back
  2. 김민솔 identifiable in the response
  3. round/hole or Stableford-point data readable
  4. arithmetically connects to the official +51
  5. structure extends to the full field (not just one player)

Does NOT touch any local database -- this is a pure network probe that
writes its raw results to disk as new files, nothing destructive.

Usage (on a machine with real klpga.co.kr access):
    cd klpga_pipeline
    python scripts/205_probe_stableford_score_sources.py

Output: prints a structured report to stdout AND writes
    evidence/stableford_source_probe_2025100001/
        scoreRecord_2025100001.html        (raw response body, if any)
        scoreDetail_10725_2025100001.html  (raw response body, if any)
        PROBE_REPORT.json                  (the structured fields below)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(KLPGA_PIPELINE_ROOT / "src"))

from klpga import config  # noqa: E402
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402

GAME_CODE_2025 = "2025100001"  # 2025 "동부건설 · 한국토지신탁 챔피언십" = this tournament's own 2025 identity
KIM_MIN_SOL_PLAYER_CODE = "10725"  # cross-validated this session against official money-rank data
KIM_MIN_SOL_NAME = "김민솔"
OFFICIAL_FINAL_POINTS = 51  # +51, OBSERVED user relay
OFFICIAL_ROUND_SPLIT = [7, 14, 14, 16]  # OBSERVED user relay -- sums to 51

OUT_DIR = KLPGA_PIPELINE_ROOT / "evidence" / "stableford_source_probe_2025100001"


def probe_score_record(client: PoliteHttpClient) -> dict:
    """PRIMARY candidate: bulk, gameCode-scoped tournament record page."""
    url = config.SCORE_RECORD_ENDPOINT
    params = {"gameCode": GAME_CODE_2025}
    result = {
        "label": "PRIMARY: scoreRecord (bulk, gameCode-scoped)",
        "url": url, "method": "GET", "parameters": params,
    }
    host = __import__("requests").utils.urlparse(url).netloc
    client._throttle(host)
    try:
        resp = client._do_request("GET", url, params=params)
    except RateLimitBlockedError as e:
        result.update(response_status=None, error=f"RateLimitBlockedError: {e}")
        return result
    except Exception as e:  # noqa: BLE001 -- diagnostic script, report whatever happens
        result.update(response_status=None, error=f"{type(e).__name__}: {e}")
        return result

    body = resp.text
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "scoreRecord_2025100001.html").write_text(body, encoding="utf-8")
    result.update(
        response_status=resp.status_code,
        content_type=resp.headers.get("Content-Type"),
        response_bytes=len(resp.content),
        player_name_present=KIM_MIN_SOL_NAME in body,
        par_cells=body.count('class="par"'),
        birdie_cells=body.count('class="birdies"'),
        bogey_cells=body.count('class="bogeys"'),
        double_bogey_cells=body.count('class="Dbogeys"'),
        eagle_cells=body.count('class="eagles"'),
        saved_to=str(OUT_DIR / "scoreRecord_2025100001.html"),
    )
    return result


def probe_score_detail(client: PoliteHttpClient) -> dict:
    """SECONDARY/fallback candidate: per-player hole-by-hole scorecard."""
    url = config.SCORE_DETAIL_ENDPOINT
    data = {
        "playerCode": KIM_MIN_SOL_PLAYER_CODE,
        "gameCode": GAME_CODE_2025,
        "playerName": KIM_MIN_SOL_NAME,
    }
    result = {
        "label": "SECONDARY: scoreDetail (per-player, fallback)",
        "url": url, "method": "POST", "parameters": data,
    }
    host = __import__("requests").utils.urlparse(url).netloc
    client._throttle(host)
    try:
        resp = client._do_request("POST", url, data=data)
    except RateLimitBlockedError as e:
        result.update(response_status=None, error=f"RateLimitBlockedError: {e}")
        return result
    except Exception as e:  # noqa: BLE001
        result.update(response_status=None, error=f"{type(e).__name__}: {e}")
        return result

    body = resp.text
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "scoreDetail_10725_2025100001.html").write_text(body, encoding="utf-8")
    result.update(
        response_status=resp.status_code,
        content_type=resp.headers.get("Content-Type"),
        response_bytes=len(resp.content),
        player_name_present=KIM_MIN_SOL_NAME in body,
        round_div_count=body.count('class="roundDiv"') or body.count("roundDiv"),
        par_cells=body.count('class="par"'),
        birdie_cells=body.count('class="birdies"'),
        bogey_cells=body.count('class="bogeys"'),
        double_bogey_cells=body.count('class="Dbogeys"'),
        eagle_cells=body.count('class="eagles"'),
        saved_to=str(OUT_DIR / "scoreDetail_10725_2025100001.html"),
    )
    return result


def main():
    client = PoliteHttpClient(cache_dir=KLPGA_PIPELINE_ROOT / ".http_cache_probe")
    report = {
        "probe_run_at": datetime.now(timezone.utc).isoformat(),
        "target_game_code": GAME_CODE_2025,
        "target_player": {"name": KIM_MIN_SOL_NAME, "player_code": KIM_MIN_SOL_PLAYER_CODE},
        "official_known_answer": {"final_points": OFFICIAL_FINAL_POINTS, "round_split": OFFICIAL_ROUND_SPLIT},
        "results": [],
    }

    print("=== PROBE 1: scoreRecord (bulk) ===")
    r1 = probe_score_record(client)
    print(json.dumps(r1, ensure_ascii=False, indent=2, default=str))
    report["results"].append(r1)

    print("\n=== PROBE 2: scoreDetail (per-player, fallback) ===")
    r2 = probe_score_detail(client)
    print(json.dumps(r2, ensure_ascii=False, indent=2, default=str))
    report["results"].append(r2)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUT_DIR / "PROBE_REPORT.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {report_path}")
    print(
        "\nNEXT: check PROBE_REPORT.json + the saved HTML bodies for (1) 김민솔 present, "
        "(2) real par/birdie/bogey/double-bogey cell counts > 0, (3) whether a per-hole or "
        "per-round breakdown can be isolated for her specifically and summed against the "
        "official +51 (7/14/14/16 by round) using klpga.website_v2.stableford_scoring's "
        "official point table. Do not report SOURCE PASS until that arithmetic check is done "
        "by hand against the saved real response."
    )


if __name__ == "__main__":
    main()
