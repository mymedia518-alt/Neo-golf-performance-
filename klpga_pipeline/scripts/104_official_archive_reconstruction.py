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

SECOND RED TEAM ROUND: the first version of this script only persisted
retrieval STATUS/COUNTS, not the actual parsed official leaderboard rows --
useless as evidence for the round-count audit, which needs the real
player-level R1-R4 scores. This version persists both:

  - content/website_v2/NEO_RANKING_V2_OFFICIAL_ARCHIVE_RECONSTRUCTION.json
    -- the lightweight retrieval-status summary (unchanged schema).
  - content/website_v2/NEO_RANKING_V2_OFFICIAL_LEADERBOARD_ARCHIVE.json
    -- the actual parsed player rows for every successfully retrieved
    round, keyed by game_code -> round -> players[], so the round-count
    audit can join on (game_code, player_id) against real official data.

Neither artifact overwrites historical_sg_warehouse_corrected.json or any
other existing warehouse.

ONE-COMMAND WORKFLOW: after writing both artifacts, this script
automatically invokes scripts/105_round_count_audit_v2.py's round-count
audit rebuild, so a single invocation on a machine with real KLPGA network
access (1) retrieves all events, (2) persists the actual leaderboard rows,
and (3) rebuilds NEO_RANKING_V2_ROUND_COUNT_AUDIT.json against that real
evidence. In this sandbox (network egress blocked), the same command runs
honestly and records the real failure -- it never fabricates a successful
retrieval.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
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


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def fetch_round(session: requests.Session, game_code: str, rnd: int) -> dict:
    """Attempt one official roundLeaderboard retrieval; classify the outcome
    precisely instead of collapsing every failure into a single blocked flag."""
    retrieved_at = now()
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
            "retrieved_at": retrieved_at,
        }

    if resp.status_code < 200 or resp.status_code >= 300:
        return {
            "status": "HTTP_ERROR",
            "detail": f"HTTP {resp.status_code}",
            "rows": None,
            "retrieved_at": retrieved_at,
        }

    html = resp.content.decode("utf-8", "replace")
    try:
        rows = parse_leaderboard_html(html)
    except Exception as exc:  # parser is a fixed, reused dependency -- any raise is a real parse failure
        return {
            "status": "PARSE_FAILURE",
            "detail": f"{type(exc).__name__}: {exc}",
            "rows": None,
            "retrieved_at": retrieved_at,
        }

    if not rows:
        return {"status": "EMPTY_LEADERBOARD", "detail": "0 rows parsed from 2xx response", "rows": [], "retrieved_at": retrieved_at}

    return {"status": "RETRIEVED", "detail": f"{len(rows)} rows parsed", "rows": rows, "retrieved_at": retrieved_at}


def attempt_event(session: requests.Session, game_code: str, local_player_ids: set[str]) -> dict:
    """Attempts all 4 rounds for one event. Every round's classification AND
    its actual parsed rows (when any were retrieved) are kept in the
    returned dict -- callers that only need the status summary can ignore
    the "rows" key; the leaderboard-archive builder consumes it."""
    per_round = {}
    any_retrieved = False
    for rnd in (1, 2, 3, 4):
        outcome = fetch_round(session, game_code, rnd)
        per_round[str(rnd)] = {
            "status": outcome["status"],
            "detail": outcome["detail"],
            "rows": outcome.get("rows"),
            "retrieved_at": outcome.get("retrieved_at"),
        }
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


def strip_rows_for_summary(event_result: dict) -> dict:
    """The lightweight retrieval-status summary artifact keeps its original,
    pre-existing shape (status/detail only per round) -- the actual rows
    live only in the leaderboard archive artifact, never duplicated here."""
    slim = copy.deepcopy(event_result)
    for round_entry in slim["rounds"].values():
        round_entry.pop("rows", None)
        round_entry.pop("retrieved_at", None)
    return slim


def build_leaderboard_archive(event_results: list[dict]) -> dict:
    """Turns the raw attempt_event results (which still carry the actual
    parsed rows) into the persisted leaderboard-archive shape: every
    successfully retrieved round's real player rows, augmented with
    game_code/requested_round/retrieved_at for a strict (game_code,
    player_id) join later. Never invents a round that was not retrieved."""
    events: dict[str, dict] = {}
    for result in event_results:
        game_code = result["game_code"]
        rounds_out: dict[str, dict] = {}
        for rnd_str, round_entry in result["rounds"].items():
            rows = round_entry.get("rows") or []
            players = []
            for row in rows:
                augmented = dict(row)
                augmented["game_code"] = game_code
                augmented["requested_round"] = int(rnd_str)
                augmented["retrieved_at"] = round_entry.get("retrieved_at")
                players.append(augmented)
            rounds_out[rnd_str] = {
                "round_retrieval_state": round_entry["status"],
                "retrieved_at": round_entry.get("retrieved_at"),
                "row_count": len(players),
                "players": players,
            }
        retrieved_rounds = [r for r in rounds_out.values() if r["round_retrieval_state"] == "RETRIEVED"]
        if len(retrieved_rounds) == 4:
            event_retrieval_state = "RETRIEVED"
        elif retrieved_rounds:
            event_retrieval_state = "PARTIAL"
        else:
            event_retrieval_state = result["event_status"]
        events[game_code] = {"event_retrieval_state": event_retrieval_state, "rounds": rounds_out}
    return events


def rebuild_round_count_audit() -> None:
    """One-command workflow: after (re)writing the leaderboard archive,
    immediately rebuild the round-count audit against whatever real
    evidence now exists -- zero fabricated rows either way."""
    spec = importlib.util.spec_from_file_location(
        "round_count_audit_v2", ROOT / "scripts" / "105_round_count_audit_v2.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    module.main()


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
            "in this environment, classified by failure type. The actual parsed player rows "
            "(when retrieved) are persisted separately in "
            "NEO_RANKING_V2_OFFICIAL_LEADERBOARD_ARCHIVE.json, not duplicated in this summary."
        ),
        "sample_phase": {
            "sample_size_requested": SAMPLE_SIZE,
            "sample_game_codes": sample_codes,
            "sample_results": [strip_rows_for_summary(r) for r in sample_results],
            "sample_retrieved_count": sample_ok,
            "proceed_to_full_population": sample_ok > 0,
        },
    }

    all_results_with_rows = list(sample_results)

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
        all_results_with_rows = full_results
        retrieved = sum(1 for r in full_results if r["event_status"] == "RETRIEVED")
        report["full_population_phase"] = {
            "attempted": True,
            "events_requested": len(full_results),
            "events_retrieved": retrieved,
            "results": [strip_rows_for_summary(r) for r in full_results],
        }
        report["hard_gate"] = {
            "status": "BLOCKED" if retrieved < len(full_results) else "SAMPLE_AND_FULL_RETRIEVAL_SUCCEEDED",
            "reason": f"{retrieved}/{len(full_results)} events retrieved successfully.",
        }

    out_path = CONTENT / "NEO_RANKING_V2_OFFICIAL_ARCHIVE_RECONSTRUCTION.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    official_data_path = ROOT / "src" / "klpga" / "website_v2" / "official_data.py"
    leaderboard_archive = {
        "schema_version": "neo_ranking_v2_official_leaderboard_archive_v1",
        "model_state": "VALIDATION_MODEL_NOT_PRODUCTION",
        "generated_at": now(),
        "endpoint": BASE + LB,
        "parser_reused": "klpga.website_v2.official_data.parse_leaderboard_html (not reimplemented)",
        "parser_version_sha256": sha256_of(official_data_path),
        "note": (
            "Persists the ACTUAL parsed official roundLeaderboard rows for every event/round "
            "this environment could retrieve -- not just retrieval counts. Never fabricates a "
            "round that was not genuinely retrieved and parsed."
        ),
        "source_provenance": {
            "historical_sg_warehouse_corrected": {
                "path": str(sg_path.relative_to(ROOT)), "sha256": sha256_of(sg_path),
            },
            "official_data.py": {
                "path": str(official_data_path.relative_to(ROOT)), "sha256": sha256_of(official_data_path),
            },
        },
        "events": build_leaderboard_archive(all_results_with_rows),
    }
    archive_path = CONTENT / "NEO_RANKING_V2_OFFICIAL_LEADERBOARD_ARCHIVE.json"
    archive_path.write_text(json.dumps(leaderboard_archive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "sample_size": len(sample_codes),
        "sample_retrieved_count": sample_ok,
        "hard_gate": report["hard_gate"],
    }, ensure_ascii=False, indent=2))

    rebuild_round_count_audit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
