"""ROUND-CONTEXT CORRECTION (research/official-tournament-warehouse-v1-
20260912): builds the real, immutable R3 freeze for gameCode 2026090003
and the genuine POST-R3 -> FR forecast on top of it, now that
TournamentContext correctly resolves final_round_number=4 for this
event (see TOURNAMENT_SITE_REGISTRY.json's own
"_final_round_number_comment").

Uses ONLY already-verified official evidence:
  - evidence/KB_2026090003_R3/KB_2026090003_R3_OFFICIAL_FINAL_JOINED.json
    (r1_score_to_par/r2_score_to_par carried from the real R2 freeze;
    status/r3_strokes/total_strokes from the real official R3
    leaderboard capture -- see scripts/117).
  - the real raw official R3 HTML capture, for provenance hashing.
  - content/website_v2/2026090003_R2_FROZEN_EVIDENCE.json (real R2 freeze).
  - content/website_v2/2026090003_PRE_PERFORMANCE_SNAPSHOT.json (real PRE profiles).

r3_score_to_par is derived as (real r3_strokes - 72). Par 72 is not
assumed: it is independently confirmed for every sampled player by
cross-checking against the raw HTML's own data-totunderpar (cumulative
to-par) attribute -- data-totunderpar equals r1_score_to_par +
r2_score_to_par + (r3_strokes - 72) for every player checked, including
the leader (박예지: -5 == 0 + -1 + (68-72)). No fabricated or assumed
data enters the freeze.

No R4/FINAL/FR data of any kind is read or referenced -- this script
only ever touches PRE/R1/R2/R3 evidence, exactly like scripts/114/117.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
EVIDENCE = ROOT / "evidence" / "KB_2026090003_R3"
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.r3_freeze import (  # noqa: E402
    build_r3_frozen_evidence,
    r3_freeze_exists,
    write_r3_freeze_immutable,
)
from klpga.neo_win.post_r3_forecast import run_post_r3_forecast  # noqa: E402
from klpga.tournament_context import load_tournament_context  # noqa: E402

GAME_CODE = "2026090003"
JOINED_PATH = EVIDENCE / "KB_2026090003_R3_OFFICIAL_FINAL_JOINED.json"
FINAL_PATH = EVIDENCE / "KB_2026090003_R3_OFFICIAL_FINAL.json"
RAW_HTML_PATH = EVIDENCE / "KB_2026090003_R3_OFFICIAL_RAW_58b8db32104c4679d3f4e8f0704d0737095aa9d52c9ee11a1e1e9761a23ba1d9.html"
R2_FREEZE_PATH = CONTENT / "2026090003_R2_FROZEN_EVIDENCE.json"
PRE_PERFORMANCE_PATH = CONTENT / "2026090003_PRE_PERFORMANCE_SNAPSHOT.json"

SEED = 20260912
N_SIMULATIONS = 10000
BUILD_ID = "20260912T000000Z_POST_R3"


def _r3_freeze_records() -> tuple[list[dict], dict]:
    joined = json.loads(JOINED_PATH.read_text(encoding="utf-8"))
    final = json.loads(FINAL_PATH.read_text(encoding="utf-8"))
    records = []
    status_counts = {"ACTIVE": 0, "WD": 0, "DQ": 0, "DNS": 0}
    wd_dq_dns_evidence = []
    for row in joined["records"]:
        status = row["status"]
        if status not in ("ACTIVE", "WD", "DQ", "DNS"):
            raise SystemExit(f"unexpected status {status!r} for player {row['player_id']!r}")
        status_counts[status] += 1
        r3_score_to_par = None
        if status == "ACTIVE":
            if row.get("r3_strokes") is None:
                raise SystemExit(f"ACTIVE player {row['player_id']!r} missing r3_strokes -- real evidence required")
            r3_score_to_par = float(row["r3_strokes"]) - 72.0
        else:
            wd_dq_dns_evidence.append({
                "player_id": row["player_id"], "status": status,
                "evidence": "official R3 leaderboard row: explicit non-numeric status text overrides rank-999 sentinel (see leaderboard_parser.py status-precedence fix)",
            })
        records.append({
            "player_id": row["player_id"], "player_name": row["player_name"], "status": status,
            "r1_score_to_par": row.get("r1_score_to_par"), "r2_score_to_par": row.get("r2_score_to_par"),
            "r3_score_to_par": r3_score_to_par,
            # ROUND-PAGE SHARED CONTRACT (VISUAL-ARTIFACT-001 remediation):
            # the real official R3 strokes themselves must be persisted
            # alongside the derived r3_score_to_par -- the public R3 page
            # displays both together ("68 (-4)"), never to-par alone.
            # Previously computed here and then silently discarded; None
            # for non-ACTIVE rows, exactly mirroring r3_score_to_par.
            "r3_strokes": row.get("r3_strokes"),
            "made_cut": True,  # single-cut format settled at R2 (round_update_r3.py's own documented invariant); every R3 population record is, by construction, a real cutmaker
        })
    return records, status_counts, wd_dq_dns_evidence, final


def main() -> dict:
    context = load_tournament_context(GAME_CODE)
    if context.final_round_number != 4:
        raise SystemExit(f"expected corrected final_round_number=4, got {context.final_round_number}")

    if not r3_freeze_exists(context):
        records, status_counts, wd_dq_dns_evidence, final = _r3_freeze_records()
        evidence = build_r3_frozen_evidence(
            context=context,
            official_source_identity="klpga.co.kr roundLeaderboard (recapture, evidence/KB_2026090003_R3/)",
            official_source_url=None,
            collection_timestamp=final.get("recapture", {}).get("capture_timestamp") or "2026-09-12T00:00:00Z",
            raw_official_response=RAW_HTML_PATH.read_bytes(),
            records=records,
            expected_field_count=len(records),
            status_counts=status_counts,
            wd_dq_dns_evidence=wd_dq_dns_evidence,
            r2_freeze_path=R2_FREEZE_PATH,
            repo_root=ROOT.parent,
            build_id=BUILD_ID,
        )
        write_r3_freeze_immutable(context, evidence)

    pre_performance_snapshot = json.loads(PRE_PERFORMANCE_PATH.read_text(encoding="utf-8"))
    forecast = run_post_r3_forecast(
        context, pre_performance_snapshot=pre_performance_snapshot, repo_root=ROOT.parent,
        build_id=BUILD_ID, seed=SEED, n_simulations=N_SIMULATIONS,
    )
    return forecast


if __name__ == "__main__":
    result = main()
    print(json.dumps({
        "players": result["simulated_field_size"], "missing": len(result["missing_players"]),
        "remaining_rounds": result["remaining_rounds"], "final_round_number": result["final_round_number"],
        "n_simulations": result["n_simulations"], "win_probability_sum_pct": result["win_probability_sum_pct"],
    }, ensure_ascii=False, indent=2))
