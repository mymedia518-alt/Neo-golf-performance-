"""OK Open R1 FINAL reconciliation against the official scoreRecord
source -- the ONLY place allowed to set OK_OPEN_STAGE_STATE.json's
r1_complete / r2_ready to true.

This is a SEPARATE pathway from the 30-minute live active cycle
(scripts/96_ok_open_r1_active_cycle.py), which keeps running unchanged
for in-progress display -- this script never touches r1_snapshots/ or
OK_OPEN_2026_R1_LIVE_SNAPSHOT.json. Before this script existed,
scripts/96 itself flipped r1_complete/r2_ready to true whenever its own
18-hole heuristic (klpga.neo_win.r1_readiness.assess_r1) thought every
ACTIVE player was done -- that heuristic runs against the roundLeader-
board endpoint, which has never been observed reporting an actual
WD/DQ/DNS determination (only the generic "999" rank sentinel -> status
="INCOMPLETE"). Treating that heuristic as authoritative for the public
"R1 official complete" claim risked closing R1 on an inference, not a
confirmed official record. scripts/96 no longer sets those two flags at
all (see its own docstring) -- only a PASSED run of THIS script may.

Pipeline: fetch scoreRecord's raw HTML (klpga.collectors.score_record)
-> save it immutably (klpga.neo_win.r1_final_store, a directory
completely separate from the live collector's own snapshot store) ->
parse it into the clean {player_id, official_status, final_score,
rank_display} contract (klpga.collectors.score_record.
parse_score_record_html -- NOT YET IMPLEMENTED, see that function's
docstring) -> reconcile against the full official entry list by
player_id (klpga.neo_win.r1_final_reconciliation.reconcile_r1_final:
every normal player needs a real final_score, WD/DQ/DNS come ONLY from
scoreRecord's own status field, INCOMPLETE is never inferred as WD) ->
save the reconciled result as its own immutable FINAL snapshot -> only
on PASS, flip r1_complete/r2_ready.

Until parse_score_record_html is implemented against a real captured
page (see scripts/97_fetch_score_record_sample.py), --live here will
always stop right after saving the raw response, with a clear
PARSER_NOT_IMPLEMENTED result -- never a crash, never a guessed
reconciliation, and r1_complete/r2_ready are never touched.

Safe by default: with no --live flag, this makes ZERO HTTP requests and
reports a DRY_RUN, matching every other real-collection script in this
project.

Usage:
    python scripts/98_ok_open_r1_final_reconciliation.py           # dry run, no HTTP
    python scripts/98_ok_open_r1_final_reconciliation.py --live    # real fetch + reconciliation attempt

Always prints exactly one JSON summary line to stdout as its last line.
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
ENTRY_SNAPSHOT = CONTENT / "OK_OPEN_2026_ENTRY_SNAPSHOT.json"
STAGE_STATE = CONTENT / "OK_OPEN_STAGE_STATE.json"
GAME_CODE = "2026120001"
KST = datetime.timezone(datetime.timedelta(hours=9))
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.r1_final_reconciliation import reconcile_r1_final  # noqa: E402
from klpga.neo_win import r1_final_store  # noqa: E402


def _read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _kst_stamp(now: datetime.datetime) -> str:
    return now.astimezone(KST).strftime("%Y%m%dT%H%M%S")


def _fetch_score_record() -> tuple[int, str]:
    """Real HTTP fetch, isolated in its own function so tests can
    monkeypatch it directly rather than needing a real network or a
    real parser (klpga.collectors.score_record.parse_score_record_html
    is not implemented yet -- see that module)."""
    from klpga.collectors.score_record import fetch_score_record_html
    from klpga.http_client import PoliteHttpClient

    client = PoliteHttpClient(cache_dir=ROOT / "data" / "raw_cache" / "r1_final")
    return fetch_score_record_html(client, GAME_CODE)


def _parse_score_record(raw_html: str) -> list[dict]:
    """Isolated the same way as _fetch_score_record -- delegates to the
    real (currently NotImplementedError-raising) parser, so tests can
    monkeypatch this one function to exercise the PASS/FAIL
    reconciliation paths without needing a real captured page."""
    from klpga.collectors.score_record import parse_score_record_html

    return parse_score_record_html(raw_html)


def _attach_player_ids(rows: list[dict], expected_ids: list[str]) -> list[dict]:
    """Resolve scoreRecord's exact official names to current entry IDs.

    scoreRecord's observed DOM exposes no playerCode. We first use the
    immutable entry snapshot, then refresh the official entry page only when
    late substitutions are absent from that snapshot. Ambiguous or unknown
    names fail closed; no player-specific fallback is allowed.
    """
    if all(row.get("player_id") for row in rows):
        return rows
    import re
    def norm(value):
        return re.sub(r"\s+", " ", str(value or "").strip())
    entry = _read_json(ENTRY_SNAPSHOT, {"entries": []}).get("entries", [])
    by_name = {}
    for item in entry:
        name = norm(item.get("player_name") or item.get("canonical_name"))
        if name and name in by_name and by_name[name] != str(item.get("player_id")):
            raise ValueError(f"ambiguous entry identity for player_name={name!r}")
        if name:
            by_name[name] = str(item.get("player_id"))
    missing = [row for row in rows if norm(row.get("player_name")) not in by_name]
    if missing:
        from klpga.collectors.entry_list import fetch_entry_list
        from klpga.http_client import PoliteHttpClient
        from klpga.parsers.entry_list_parser import parse_entry_list_html
        client = PoliteHttpClient(cache_dir=ROOT / "data" / "raw_cache" / "r1_final")
        fresh = parse_entry_list_html(fetch_entry_list(client, GAME_CODE)).rows
        for item in fresh:
            name = norm(item.player_name)
            if name in by_name and by_name[name] != str(item.player_code):
                raise ValueError(f"ambiguous fresh entry identity for player_name={name!r}")
            by_name[name] = str(item.player_code)
    resolved = []
    for row in rows:
        pid = row.get("player_id") or by_name.get(norm(row.get("player_name")))
        if not pid:
            raise ValueError(f"unresolved scoreRecord identity for player_name={row.get('player_name')!r}")
        item = dict(row)
        item["player_id"] = str(pid)
        resolved.append(item)
    if len(resolved) != len(expected_ids) or len({str(r["player_id"]) for r in resolved}) != len(resolved):
        raise ValueError("scoreRecord identity count or uniqueness does not match the official entry set")
    return resolved


def main() -> int:
    live = "--live" in sys.argv[1:]

    entry = _read_json(ENTRY_SNAPSHOT, {"entries": []})
    expected_ids = [str(e["player_id"]) for e in entry.get("entries", [])]
    retrieved_at = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    if not live:
        result = {"action": "DRY_RUN", "reason": "no --live flag; matches every other real-collection script's safe default", "expected_player_count": len(expected_ids), "retrieved_at": retrieved_at}
        print(json.dumps(result, ensure_ascii=False))
        return 0

    from klpga.http_client import RateLimitBlockedError
    import requests

    now = datetime.datetime.now(datetime.timezone.utc)
    kind = _kst_stamp(now)

    try:
        status, raw_html = _fetch_score_record()
    except (RateLimitBlockedError, requests.exceptions.RequestException) as exc:
        result = {"action": "WAIT", "reason": f"{type(exc).__name__}: {exc}", "retrieved_at": retrieved_at}
        print(json.dumps(result, ensure_ascii=False))
        return 0

    raw_path = r1_final_store.save_raw_response_immutable(GAME_CODE, kind, raw_html)
    try:
        raw_response_path_str = str(raw_path.relative_to(ROOT))
    except ValueError:
        raw_response_path_str = str(raw_path)
    result = {"retrieved_at": retrieved_at, "http_status": status, "raw_response_path": raw_response_path_str}

    try:
        rows = _attach_player_ids(_parse_score_record(raw_html), expected_ids)
        # The immutable PRE entry can be superseded by official late
        # substitutions. The scoreRecord row set is the current official
        # identity set; reconciliation uses that set after exact-name mapping.
        expected_ids = sorted({str(row["player_id"]) for row in rows})
    except NotImplementedError as exc:
        result["action"] = "PARSER_NOT_IMPLEMENTED"
        result["reason"] = str(exc)
        print(json.dumps(result, ensure_ascii=False))
        print("[r1-final-reconciliation] raw response saved for review; r1_complete/r2_ready NOT touched", file=sys.stderr)
        return 1
    except (ValueError, KeyError) as exc:
        result["action"] = "PARSER_FAILED"
        result["reason"] = str(exc)
        print(json.dumps(result, ensure_ascii=False))
        print("[r1-final-reconciliation] parser failed; r1_complete/r2_ready NOT touched", file=sys.stderr)
        return 1

    reconciliation = reconcile_r1_final(rows, expected_ids)
    result["reconciliation"] = {
        "passed": reconciliation.passed, "reason": reconciliation.reason,
        "active_confirmed": reconciliation.active_confirmed, "wd": reconciliation.wd,
        "dq": reconciliation.dq, "dns": reconciliation.dns,
    }

    snapshot_path = r1_final_store.save_snapshot_immutable(
        GAME_CODE, kind,
        {"round": 1, "collected_at": retrieved_at, "official_data_source": "scoreRecord", "rows": rows, "reconciliation": result["reconciliation"]},
    )
    try:
        result["snapshot_path"] = str(snapshot_path.relative_to(ROOT))
    except ValueError:
        result["snapshot_path"] = str(snapshot_path)

    if not reconciliation.passed:
        result["action"] = "RECONCILIATION_FAILED"
        print(json.dumps(result, ensure_ascii=False))
        print(f"[r1-final-reconciliation] FAILED: {reconciliation.reason} -- r1_complete/r2_ready NOT touched", file=sys.stderr)
        return 1

    state = _read_json(STAGE_STATE, {"stages": {}})
    state.setdefault("stages", {}).setdefault("r1", {})["final_reconciliation"] = {
        "passed": True, "reason": reconciliation.reason, "retrieved_at": retrieved_at, "snapshot_kind": kind,
    }
    state["r1_complete"] = True
    state["r2_ready"] = True
    STAGE_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    result["action"] = "FINAL_RECONCILED"
    result["r1_complete"] = True
    result["r2_ready"] = True
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
