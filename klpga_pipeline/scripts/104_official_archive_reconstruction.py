"""NEO Ranking V2 -- official KLPGA archive reconstruction attempt
(VALIDATION_MODEL_NOT_PRODUCTION).

RED TEAM FOLLOW-UP: scripts/77_repair_sg_row_retention.py already proves the
repository has a real official round-leaderboard retrieval path:

    POST https://klpga.co.kr/load/leaderboard/roundLeaderboard
        {"gameCode": <code>, "round": <1|2|3|4>}

parsed by the EXISTING, reused (not reimplemented) parser
``klpga.website_v2.official_data.parse_leaderboard_html`` -- which already
exposes player_id, R1-R4 numeric scores, and WD/DQ/FINISHED status.

Per instruction, this script does NOT assume data/klpga.sqlite's absence is
the final blocker. It ATTEMPTS the real retrieval, against a small
representative sample first, and classifies the actual outcome:

  - NETWORK_EGRESS_DENIED : the HTTP request itself could not be made
    (connection/proxy/TLS failure before any server response was received)
  - HTTP_ERROR             : a response was received with a non-2xx status
  - EMPTY_LEADERBOARD      : a 2xx response parsed to zero rows
  - PARSE_FAILURE          : parse_leaderboard_html raised
  - IDENTITY_MISMATCH      : rows retrieved but none join to the local
                              SG warehouse's player_id for that event
  - RETRIEVED              : usable rows obtained

This script never overwrites historical_sg_warehouse_corrected.json or any
other existing warehouse -- it writes a new, separate, immutable artifact:
content/website_v2/NEO_RANKING_V2_OFFICIAL_ARCHIVE_RECONSTRUCTION.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from klpga.website_v2.official_data import parse_leaderboard_html  # noqa: E402

BASE = "https://klpga.co.kr"
LB = "/load/leaderboard/roundLeaderboard"

CONTENT = ROOT / "content" / "website_v2"
SAMPLE_SIZE = 5


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_round(session: requests.Session, game_code: str, rnd: int) -> dict:
    """Attempt one official roundLeaderboard retrieval; classify the outcome
    precisely instead of collapsing every failure into a single blocked flag."""
    try:
        resp = session.post(
            BASE + LB,
            data={"gameCode": game_code, "round": str(rnd)},
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": BASE},
            timeout=45,
        )
    except requests.exceptions.RequestException as exc:
        return {
            "status": "NETWORK_EGRESS_DENIED",
            "detail": f"{type(exc).__name__}: {exc}",
            "rows": None,
        }

    if resp.status_code < 200 or resp.status_code >= 300:
        return {
            "status": "HTTP_ERROR",
            "detail": f"HTTP {resp.status_code}",
            "rows": None,
        }

    html = resp.content.decode("utf-8", "replace")
    try:
        rows = parse_leaderboard_html(html)
    except Exception as exc:  # parser is a fixed, reused dependency -- any raise is a real parse failure
        return {
            "status": "PARSE_FAILURE",
            "detail": f"{type(exc).__name__}: {exc}",
            "rows": None,
        }

    if not rows:
        return {"status": "EMPTY_LEADERBOARD", "detail": "0 rows parsed from 2xx response", "rows": []}

    return {"status": "RETRIEVED", "detail": f"{len(rows)} rows parsed", "rows": rows}


def attempt_event(session: requests.Session, game_code: str, local_player_ids: set[str]) -> dict:
    per_round = {}
    any_retrieved = False
    for rnd in (1, 2, 3, 4):
        outcome = fetch_round(session, game_code, rnd)
        per_round[str(rnd)] = {"status": outcome["status"], "detail": outcome["detail"]}
        if outcome["status"] == "RETRIEVED":
            any_retrieved = True
            retrieved_ids = {str(r.get("player_id")) for r in outcome["rows"] if r.get("player_id")}
            if local_player_ids and not (retrieved_ids & local_player_ids):
                per_round[str(rnd)]["status"] = "IDENTITY_MISMATCH"
                per_round[str(rnd)]["detail"] += " (no overlap with local SG warehouse player_ids for this event)"

    statuses = {v["status"] for v in per_round.values()}
    if "RETRIEVED" in statuses:
        event_status = "RETRIEVED"
    elif statuses == {"NETWORK_EGRESS_DENIED"}:
        event_status = "NETWORK_EGRESS_DENIED"
    elif "IDENTITY_MISMATCH" in statuses:
        event_status = "IDENTITY_MISMATCH"
    elif "PARSE_FAILURE" in statuses:
        event_status = "PARSE_FAILURE"
    elif "HTTP_ERROR" in statuses:
        event_status = "HTTP_ERROR"
    else:
        event_status = "EMPTY_LEADERBOARD"

    return {"game_code": game_code, "event_status": event_status, "rounds": per_round, "any_retrieved": any_retrieved}


def main() -> int:
    sg_path = CONTENT / "historical_sg_warehouse_corrected.json"
    sg = json.loads(sg_path.read_text(encoding="utf-8"))

    by_code_ids: dict[str, set[str]] = {}
    codes_ordered: list[str] = []
    for r in sg["records"]:
        code = r.get("game_code")
        if not code:
            continue
        if code not in by_code_ids:
            by_code_ids[code] = set()
            codes_ordered.append(code)
        pid = r.get("player_id")
        if pid:
            by_code_ids[code].add(str(pid))

    sample_codes = sorted(codes_ordered)[:SAMPLE_SIZE]

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    sample_results = [attempt_event(session, code, by_code_ids.get(code, set())) for code in sample_codes]

    sample_ok = sum(1 for r in sample_results if r["event_status"] == "RETRIEVED")

    report = {
        "schema_version": "neo_ranking_v2_official_archive_reconstruction_v1",
        "model_state": "VALIDATION_MODEL_NOT_PRODUCTION",
        "generated_at": now(),
        "endpoint": BASE + LB,
        "parser_reused": "klpga.website_v2.official_data.parse_leaderboard_html (not reimplemented)",
        "note": (
            "This artifact records an ACTUAL retrieval attempt against the live official "
            "endpoint. It does not assume data/klpga.sqlite's absence is the blocker -- "
            "the outcome below is what the endpoint itself returned (or failed to return) "
            "in this environment, classified by failure type."
        ),
        "sample_phase": {
            "sample_size_requested": SAMPLE_SIZE,
            "sample_game_codes": sample_codes,
            "sample_results": sample_results,
            "sample_retrieved_count": sample_ok,
            "proceed_to_full_population": sample_ok > 0,
        },
    }

    if sample_ok == 0:
        report["full_population_phase"] = {
            "attempted": False,
            "reason": "sample_phase retrieved 0/{} events -- expanding to the full 97-event population would not "
                      "produce different evidence and would just repeat the same failure at scale.".format(len(sample_codes)),
        }
        report["hard_gate"] = {
            "status": "BLOCKED",
            "reason": (
                "Official archive reconstruction FAILED at the sample phase. All {} sampled events returned "
                "event_status != RETRIEVED. This is a real, evidenced outcome (see sample_results for the exact "
                "per-round failure classification), not an assumption -- round-count verification via the "
                "official leaderboard remains unavailable in this environment."
            ).format(len(sample_codes)),
        }
    else:
        # Full population phase only runs if the sample proves the endpoint is reachable.
        remaining_codes = sorted(codes_ordered)[SAMPLE_SIZE:]
        full_results = list(sample_results)
        for code in remaining_codes:
            full_results.append(attempt_event(session, code, by_code_ids.get(code, set())))
        retrieved = sum(1 for r in full_results if r["event_status"] == "RETRIEVED")
        report["full_population_phase"] = {
            "attempted": True,
            "events_requested": len(full_results),
            "events_retrieved": retrieved,
            "results": full_results,
        }
        report["hard_gate"] = {
            "status": "BLOCKED" if retrieved < len(full_results) else "SAMPLE_AND_FULL_RETRIEVAL_SUCCEEDED",
            "reason": f"{retrieved}/{len(full_results)} events retrieved successfully.",
        }

    out_path = CONTENT / "NEO_RANKING_V2_OFFICIAL_ARCHIVE_RECONSTRUCTION.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "sample_size": len(sample_codes),
        "sample_retrieved_count": sample_ok,
        "hard_gate": report["hard_gate"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
