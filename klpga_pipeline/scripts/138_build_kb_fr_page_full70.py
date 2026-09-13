#!/usr/bin/env python3
"""MISSION J -- KB FR OFFICIAL 70/70 DATA GATE: build the real, COMPLETE
70-player FR page from the validated official dataset.

Hard-stops (never fabricates, never continues on a partial result) unless
scripts/137_kb_fr_70_data_gate_validate.build()'s own gate reports
status == "PASS" -- i.e. accounted_for==70, ambiguous==0, unsupported==0,
arithmetic_errors==0, conflicts==0 (39/39 crosscheck clean), and the R3
freeze fingerprint is unchanged. Reuses klpga.neo_win.fr_real_page's
existing renderer unchanged (same design system, same sponsor-invariant
helper) -- only the evidence payload passed to it is new: an
evidence["confirmed_records"] list built from the validated 70-row
dataset, with sponsor merged in from V3 for the 39 already-known players
and left blank (never guessed) for the other 31 players, and
positions_confirmed_gapless_through=70 since the field is now complete.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.fr_real_page import render_fr_real_page  # noqa: E402
from klpga.tournament_context import load_tournament_context  # noqa: E402

GATE_SPEC = importlib.util.spec_from_file_location(
    "kb_fr_v3_gate", ROOT / "scripts" / "137_kb_fr_70_data_gate_validate.py"
)
gate_mod = importlib.util.module_from_spec(GATE_SPEC)
sys.modules["kb_fr_v3_gate"] = gate_mod
GATE_SPEC.loader.exec_module(gate_mod)

PAR_PER_ROUND = 72
EXPECTED_FIELD = 70

_POSITION_DIGITS_RE = re.compile(r"\d+")


def _position_from(final_position: str) -> int:
    match = _POSITION_DIGITS_RE.search(final_position)
    if not match:
        raise SystemExit(f"refusing to build FR page: unparseable final_position {final_position!r}")
    return int(match.group())


def build_evidence() -> dict:
    gate_result = gate_mod.build()
    if gate_result["status"] != "PASS":
        raise SystemExit(
            "refusing to build FR page: DATA GATE is not PASS "
            f"(status={gate_result['status']}, gate={gate_result['completeness_gate']})"
        )

    supplied = json.loads(gate_mod.SUPPLIED_PATH.read_text(encoding="utf-8"))
    v3 = json.loads(gate_mod.V3_PATH.read_text(encoding="utf-8"))
    resolved_ids = gate_result["resolved_player_ids_by_name"]

    sponsor_by_id = {r["player_id"]: r.get("sponsor") for r in v3["confirmed_records"]}

    records = []
    for p in supplied["players"]:
        player_id = resolved_ids[p["player_name"]]
        records.append({
            "player_id": player_id,
            "player_name": p["player_name"],
            "sponsor": sponsor_by_id.get(player_id),  # None (blank) unless V3-verified
            "final_rank": p["final_position"],
            "position_from": _position_from(p["final_position"]),
            "r1_strokes": p["r1_score"],
            "r2_strokes": p["r2_score"],
            "r3_strokes": p["r3_score"],
            "r4_strokes": p["fr_score"],
            "final_total_strokes": p["total_strokes"],
            "final_to_par": p["to_par"],
            "status": p.get("status", "ACTIVE"),
        })

    if len(records) != EXPECTED_FIELD:
        raise SystemExit(f"refusing to build FR page: expected {EXPECTED_FIELD} records, got {len(records)}")

    return {
        "par_per_round": PAR_PER_ROUND,
        "positions_confirmed_gapless_through": EXPECTED_FIELD,
        "confirmed_records": records,
    }


def main() -> None:
    evidence = build_evidence()

    context = load_tournament_context("2026090003")
    html = render_fr_real_page(
        tournament_name=context.tournament_name,
        game_code=context.game_code,
        date_range=context.display_date_range,
        evidence=evidence,
    )

    out_path = REPO_ROOT / "docs" / context.url_base.strip("/") / "fr" / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({
        "written": str(out_path),
        "confirmed_records": len(evidence["confirmed_records"]),
        "positions_confirmed_gapless_through": evidence["positions_confirmed_gapless_through"],
        "data_gate_status": "PASS",
    }))


if __name__ == "__main__":
    main()
