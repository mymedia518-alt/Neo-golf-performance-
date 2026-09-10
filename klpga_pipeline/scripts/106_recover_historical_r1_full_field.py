"""LOCAL RECOVERY (real network required): recover full-field historical
Round 1 results -- including CUT/WD/DQ players, not just eventual
cut-survivors -- for the 82 historical tournaments already established
in content/website_v2/HISTORICAL_R1_GROUPING_EVIDENCE_BLOCKER_
RESOLUTION_V1.json.

WHY THIS SCRIPT EXISTS: content/website_v2/historical_sg_warehouse.json
(the strokesGained_detail endpoint) is proven survivor-biased -- round-1
Strokes-Gained rows exist for 100% of eventual cut-survivors but only
2.16% of eventual cut-missers across the full corpus (see
KB_2026090003_R1_MODEL_V1_RESEARCH_V1.json). This script instead reuses
the roundLeaderboard endpoint via the EXISTING, already-proven collector
(klpga.collectors.leaderboard.fetch_round_leaderboard_html +
klpga.parsers.leaderboard_parser.parse_round_leaderboard_html), which
was specifically fixed in this project's own history (see that module's
docstring) to stop silently dropping CUT/WD/DQ players. Round 1 is
fetched directly (not discovered via the final round) because round 1
is the one round the full starting field is guaranteed to appear on.

Cannot run inside the Claude Code cloud sandbox: klpga.co.kr is
proxy-blocked there (re-verified via direct curl immediately before
this script was written: CONNECT tunnel failed, HTTP 403). Run this on
a machine with normal klpga.co.kr access instead -- see
NEO_RECOVER_HISTORICAL_R1_FULL_FIELD.bat.

Resumable: a game_code already recorded with status "OK" in the output
file (and whose archived raw evidence file still exists on disk) is
never re-fetched. Fails closed per game_code (HTTP error, empty
response, empty parsed result, duplicate player_code, or an
implausible row count vs. the known grouping-page field size) --
a failure is recorded with a reason and the run continues to the next
tournament; nothing is ever invented to fill a failed slot.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
EVIDENCE_DIR = ROOT / "evidence" / "historical_r1_full_field_v1"
OUTPUT_PATH = CONTENT / "NEO_HISTORICAL_R1_FULL_FIELD_V1.json"
AUDIT_PATH = CONTENT / "NEO_HISTORICAL_R1_FULL_FIELD_V1_AUDIT.json"
GROUPING_EVIDENCE_PATH = CONTENT / "HISTORICAL_R1_GROUPING_EVIDENCE_BLOCKER_RESOLUTION_V1.json"
TRUTH_WAREHOUSE_PATH = CONTENT / "NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json"

sys.path.insert(0, str(ROOT / "src"))


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def expected_game_codes() -> list[str]:
    grouping = load(GROUPING_EVIDENCE_PATH)
    return [r["game_code"] for r in grouping["records"]]


def expected_field_sizes() -> dict[str, int]:
    grouping = load(GROUPING_EVIDENCE_PATH)
    return {r["game_code"]: r["player_count"] for r in grouping["records"]}


def event_dates() -> dict[str, str]:
    tw = load(TRUTH_WAREHOUSE_PATH)
    out: dict[str, str] = {}
    for r in tw["records"]:
        out.setdefault(r["game_code"], r["tournament_start_date"])
    return out


def archive_raw_evidence(game_code: str, html: str) -> tuple[str, str]:
    """Persist immutable raw evidence before parsing. Returns
    (filename, sha256). Never overwrites an existing archived file --
    the filename is content-addressed, so a byte-identical re-fetch is
    a no-op and a byte-different one gets its own filename rather than
    silently replacing prior evidence."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    raw = html.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    filename = f"{game_code}_r1_{digest}.html.gz"
    path = EVIDENCE_DIR / filename
    if not path.exists():
        path.write_bytes(gzip.compress(raw, 9, mtime=0))
    return filename, digest


FetchFn = Callable[[str], str]
"""game_code -> raw roundLeaderboard round=1 HTML text. Injected so this
module is testable without real network access; main() wires it to the
real collector."""


def recover_one(
    game_code: str,
    fetch: FetchFn,
    *,
    expected_size: Optional[int],
    event_date: Optional[str],
    parse_fn,
) -> dict:
    """Fetch, archive, parse, and validate ONE tournament's R1 field.
    Fails closed: every failure path returns status='FAILED' with a
    specific `error`, never a partially-fabricated OK record."""
    try:
        html = fetch(game_code)
    except Exception as exc:  # noqa: BLE001 -- any network/HTTP failure is a real recovery failure
        return {"game_code": game_code, "status": "FAILED", "error": f"HTTP_ERROR: {type(exc).__name__}: {exc}", "retrieved_at": now()}

    if not html or not html.strip():
        return {"game_code": game_code, "status": "FAILED", "error": "EMPTY_RESPONSE", "retrieved_at": now()}

    raw_evidence, source_sha256 = archive_raw_evidence(game_code, html)

    try:
        rows = parse_fn(html, game_code=game_code, round_number=1)
    except Exception as exc:  # noqa: BLE001
        return {
            "game_code": game_code, "status": "FAILED",
            "error": f"PARSER_ERROR: {type(exc).__name__}: {exc}",
            "raw_evidence": raw_evidence, "source_sha256": source_sha256, "retrieved_at": now(),
        }

    if not rows:
        return {
            "game_code": game_code, "status": "FAILED", "error": "EMPTY_RESULT",
            "raw_evidence": raw_evidence, "source_sha256": source_sha256, "retrieved_at": now(),
        }

    player_codes = [r.player_code for r in rows if r.player_code is not None]
    if len(player_codes) != len(set(player_codes)):
        return {
            "game_code": game_code, "status": "FAILED", "error": "DUPLICATE_PLAYER_CODE",
            "raw_evidence": raw_evidence, "source_sha256": source_sha256, "retrieved_at": now(),
        }

    if expected_size is not None:
        # Real field sizes can differ slightly from the pre-round
        # grouping page (a late scratch never posts a score row; a
        # grouping-listed alternate never starts) -- but a wildly
        # different count means something is structurally wrong with
        # this response, not a normal edge case, so it is never
        # silently accepted.
        if len(rows) == 0 or len(rows) > expected_size + 10 or len(rows) < expected_size - 40:
            return {
                "game_code": game_code, "status": "FAILED",
                "error": f"IMPOSSIBLE_ROW_COUNT: got {len(rows)}, expected ~{expected_size}",
                "raw_evidence": raw_evidence, "source_sha256": source_sha256, "retrieved_at": now(),
            }

    players = []
    for row in rows:
        r1_to_par = row.today_under_par if row.today_under_par is not None else row.total_under_par
        r1_to_par_display = row.today_under_par_display if row.today_under_par is not None else row.total_under_par_display
        r1_score = row.round1_score if row.round1_score is not None else row.total_strokes
        players.append({
            "player_code": row.player_code,
            "player_name": row.player_name,
            "r1_score": r1_score,
            "r1_to_par": r1_to_par,
            "r1_to_par_display": r1_to_par_display,
            "r1_rank": row.rank,
            "r1_rank_display": row.rank_display,
            "r1_status": row.status,
        })

    return {
        "game_code": game_code,
        "status": "OK",
        "event_date": event_date,
        "official_source": "https://klpga.co.kr/load/leaderboard/roundLeaderboard",
        "request_parameters": {"gameCode": game_code, "round": "1"},
        "retrieved_at": now(),
        "raw_evidence": raw_evidence,
        "source_sha256": source_sha256,
        "player_row_count": len(players),
        "duplicate_player_code_count": 0,
        "expected_field_size": expected_size,
        "players": players,
    }


def already_recovered(existing_by_gc: dict[str, dict], game_code: str) -> bool:
    rec = existing_by_gc.get(game_code)
    if not rec or rec.get("status") != "OK":
        return False
    raw_evidence = rec.get("raw_evidence")
    if not raw_evidence or not (EVIDENCE_DIR / raw_evidence).exists():
        return False
    return True


def run_recovery(fetch: FetchFn, parse_fn, *, limit: Optional[int] = None) -> dict:
    codes = expected_game_codes()
    if limit is not None:
        codes = codes[:limit]
    sizes = expected_field_sizes()
    dates = event_dates()

    existing = load(OUTPUT_PATH) if OUTPUT_PATH.exists() else {"records": []}
    existing_by_gc = {r["game_code"]: r for r in existing.get("records", [])}

    records = []
    for i, game_code in enumerate(codes, 1):
        if already_recovered(existing_by_gc, game_code):
            records.append(existing_by_gc[game_code])
            print(f"[{i}/{len(codes)}] {game_code} SKIP (already recovered)", flush=True)
            continue

        rec = recover_one(
            game_code, fetch,
            expected_size=sizes.get(game_code), event_date=dates.get(game_code),
            parse_fn=parse_fn,
        )
        records.append(rec)
        status_line = rec["status"] if rec["status"] == "OK" else f"FAILED ({rec['error']})"
        print(f"[{i}/{len(codes)}] {game_code} {status_line}", flush=True)

        # Write after every tournament, not just at the end -- a run
        # interrupted partway through must not lose already-recovered
        # tournaments (this is what makes the script resumable).
        write(OUTPUT_PATH, {
            "schema_version": "neo_historical_r1_full_field_v1",
            "purpose": "Full-field (CUT/WD/DQ-inclusive) historical Round 1 results, recovered from the roundLeaderboard endpoint to replace the survivor-biased strokesGained_detail source for R1 model training.",
            "generated_at_utc": now(),
            "collector": "klpga.collectors.leaderboard.fetch_round_leaderboard_html + klpga.parsers.leaderboard_parser.parse_round_leaderboard_html",
            "record_count": len(records),
            "records": records,
        })

    return load(OUTPUT_PATH)


def build_audit(full_field: dict) -> dict:
    expected_codes = expected_game_codes()
    tw = load(TRUTH_WAREHOUSE_PATH)
    outcome_by_key = {(r["game_code"], r["player_id"]): r["outcome"] for r in tw["records"]}

    ok_records = [r for r in full_field["records"] if r["status"] == "OK"]
    failed_records = [r for r in full_field["records"] if r["status"] != "OK"]

    covered_keys: set[tuple[str, str]] = set()
    wd_dq_rows = 0
    identity_unresolved = []
    for rec in ok_records:
        for player in rec["players"]:
            key = (rec["game_code"], player["player_code"])
            covered_keys.add(key)
            if player["r1_status"] in ("WD", "DQ"):
                wd_dq_rows += 1
            if key not in outcome_by_key:
                identity_unresolved.append({"game_code": rec["game_code"], "player_code": player["player_code"], "player_name": player["player_name"]})

    cut_true_total = cut_true_covered = 0
    cut_false_total = cut_false_covered = 0
    for (game_code, player_id), outcome in outcome_by_key.items():
        if game_code not in expected_codes:
            continue
        if outcome["made_cut"]:
            cut_true_total += 1
            if (game_code, player_id) in covered_keys:
                cut_true_covered += 1
        else:
            cut_false_total += 1
            if (game_code, player_id) in covered_keys:
                cut_false_covered += 1

    return {
        "schema_version": "neo_historical_r1_full_field_v1_audit",
        "generated_at_utc": now(),
        "events_expected": len(expected_codes),
        "events_recovered": len(ok_records),
        "events_failed": len(failed_records),
        "failed_game_codes": [{"game_code": r["game_code"], "error": r["error"]} for r in failed_records],
        "player_events_recovered_total": sum(r["player_row_count"] for r in ok_records),
        "cut_survivor_coverage": {
            "total": cut_true_total, "covered": cut_true_covered,
            "rate": (cut_true_covered / cut_true_total) if cut_true_total else None,
        },
        "cut_misser_coverage": {
            "total": cut_false_total, "covered": cut_false_covered,
            "rate": (cut_false_covered / cut_false_total) if cut_false_total else None,
        },
        "wd_dq_row_count": wd_dq_rows,
        "duplicates_within_event": 0,
        "identity_unresolved_count": len(identity_unresolved),
        "identity_unresolved_sample": identity_unresolved[:20],
        "source_hashes": {r["game_code"]: r["source_sha256"] for r in ok_records},
    }


def final_status_line(full_field: dict) -> str:
    n_expected = len(full_field["records"])
    n_ok = sum(1 for r in full_field["records"] if r["status"] == "OK")
    if n_ok == 0:
        return "R1_FULL_FIELD_RECOVERY_FAIL"
    if n_ok == n_expected:
        return "R1_FULL_FIELD_RECOVERY_PASS"
    return "R1_FULL_FIELD_RECOVERY_PARTIAL"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="recover only the first N tournaments (testing only)")
    args = parser.parse_args()

    from klpga.collectors.leaderboard import fetch_round_leaderboard_html
    from klpga.http_client import PoliteHttpClient
    from klpga.parsers.leaderboard_parser import parse_round_leaderboard_html

    client = PoliteHttpClient(cache_dir=ROOT / "data" / "http_cache_r1_full_field")

    def fetch(game_code: str) -> str:
        return fetch_round_leaderboard_html(client, game_code, 1, use_cache=True)

    full_field = run_recovery(fetch, parse_round_leaderboard_html, limit=args.limit)
    audit = build_audit(full_field)
    write(AUDIT_PATH, audit)

    print(json.dumps(audit, ensure_ascii=False, indent=2))
    status = final_status_line(full_field)
    print(status)
    return 0 if status != "R1_FULL_FIELD_RECOVERY_FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
