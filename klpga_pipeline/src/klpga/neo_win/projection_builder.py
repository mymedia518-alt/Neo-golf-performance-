"""Projection Builder (Evidence First Architecture, 2026-10-02
mission). Evidence Warehouse -> Round Transition Engine -> Projection.

Produces the SAME schema klpga.neo_win.hitejinro_round_pipeline.
parse_leaderboard() already writes to 2026100005_LEADERBOARD.json, plus
two new fields per record (status, status_round) that carry the real
R1_CUT/R2_CUT distinction the legacy withdrawn/disqualified/missed_cut
booleans can't express. The legacy three booleans are still populated,
derived straight from status, so render_round_page() and every other
existing LEADERBOARD.json consumer need zero code changes -- this file
only changes HOW LEADERBOARD.json's content is computed, never its
shape. This is the whole point of the redesign: LEADERBOARD.json
becomes this Projection's output, not a second independent source of
truth.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from klpga.neo_win import hitejinro_round_pipeline as _rp
from klpga.neo_win import round_transition_engine as _engine

_STATUS_TO_LEGACY = {
    "WD": {"withdrawn": True, "disqualified": False, "missed_cut": False},
    "DQ": {"withdrawn": False, "disqualified": True, "missed_cut": False},
    "R1_CUT": {"withdrawn": False, "disqualified": False, "missed_cut": True},
    "R2_CUT": {"withdrawn": False, "disqualified": False, "missed_cut": True},
}
_LEGACY_DEFAULT = {"withdrawn": False, "disqualified": False, "missed_cut": False}


def build_projection(as_of_round: int, *, warehouse_root: Path, content_root: Path) -> dict:
    """Real Projection for as_of_round, computed fresh from the
    Evidence Warehouse every call -- never reads LEADERBOARD.json as
    an input (only ever writes it, as the materialized view of this
    function's own output)."""
    entrants = json.loads((content_root / f"{_rp.GAME_CODE}_ENTRY_KRANKING_JOIN.json").read_text(encoding="utf-8"))["records"]
    entrant_ids = [r["player_code"] for r in entrants]
    name_by_id = {r["player_code"]: r["player_name"] for r in entrants}

    state_by_id = _engine.compute_state(entrant_ids, as_of_round, warehouse_root=warehouse_root)

    raw_path = warehouse_root / "tournament" / _rp.GAME_CODE / f"R{as_of_round}" / "leaderboard_raw.html"
    raw_html = raw_path.read_text(encoding="utf-8")
    rank_and_todaypar = {}
    dom_order_ids: list[str] = []
    for m in _rp._LEADERBOARD_ROW_RE.finditer(raw_html):
        pid, rank, _name, totunderpar = m.group(1), m.group(2), m.group(3), m.group(4)
        rank_and_todaypar[pid] = (rank, totunderpar)
        dom_order_ids.append(pid)

    # Record order must match parse_leaderboard()'s own: this round's
    # raw-HTML DOM order first (klpga.co.kr's own real tie-break order
    # among same-rank players -- NOT re-derivable from any other
    # field), then any entrant entirely absent from this round's DOM
    # (carried forward) appended after, exactly like the original.
    ordered_ids = dom_order_ids + [pid for pid in entrant_ids if pid not in rank_and_todaypar]

    records = []
    not_yet_complete = []
    for pid in ordered_ids:
        st = state_by_id[pid]
        status = st["status"]
        legacy = _STATUS_TO_LEGACY.get(status, _LEGACY_DEFAULT)

        rank, totunderpar = rank_and_todaypar.get(pid, (None, None))
        incomplete = rank in (None, "999")
        if incomplete:
            not_yet_complete.append({"player_id": pid, "player_name": name_by_id.get(pid, "")})
            finish_position = None
            finish_position_numeric = None
            score_to_par = None
        else:
            finish_position = rank
            finish_position_numeric = int(rank)
            score_to_par = _rp._int_or_none(totunderpar)

        records.append({
            "player_id": pid,
            "player_name": name_by_id.get(pid, ""),
            "finish_position": finish_position,
            "finish_position_numeric": finish_position_numeric,
            "score_to_par": score_to_par,
            "r1_score": st["r1_score"], "r2_score": st["r2_score"],
            "r3_score": st["r3_score"], "r4_score": st["r4_score"],
            **legacy,
            "status": status,
            "status_round": st["status_round"],
        })

    score_field = f"r{as_of_round}_score"
    raw_sha256_entry = None
    manifest_path = warehouse_root / "tournament" / _rp.GAME_CODE / f"R{as_of_round}" / "MANIFEST.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw_sha256_entry = next((f["sha256"] for f in manifest["files"] if f["name"] == "leaderboard_raw.html"), None)

    return {
        "schema_version": "hitejinro_round_leaderboard_v2",
        "game_code": _rp.GAME_CODE,
        "final_round": as_of_round,
        "as_of": date.today().isoformat(),
        "source_raw": {
            "path": str(raw_path.relative_to(warehouse_root.parents[2])),
            "sha256": raw_sha256_entry,
            "saved_from_url": f"https://klpga.co.kr/web/leaderboard/sumScore?gameCode={_rp.GAME_CODE}",
        },
        "coverage": {
            "player_count": len(records),
            f"completed_round{as_of_round}_count": sum(1 for r in records if r[score_field] is not None),
            "not_yet_complete_at_capture_time": not_yet_complete,
        },
        "records": records,
    }


def write_projection(as_of_round: int, *, warehouse_root: Path, content_root: Path, out_path: Path) -> Path:
    projection = build_projection(as_of_round, warehouse_root=warehouse_root, content_root=content_root)
    out_path.write_text(json.dumps(projection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path
