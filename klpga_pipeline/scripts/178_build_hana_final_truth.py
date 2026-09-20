"""HANA FINAL -- build the write-once FinalTruth artifact for the Hana
Financial Group Championship (2026090002) 4th/final round, using the
already-existing generic schema in klpga.neo_win.final_truth (do not
invent a new truth schema) and the already-existing, already-trusted
klpga.parsers.leaderboard_parser (the SAME parser already proven for
this tournament's R1/R3 official leaderboard captures -- same
data-rank/_playerCode-style markup, confirmed below against the real
4R capture).

Source: operator-supplied HTML save of
  https://klpga.co.kr/web/leaderboard/leaderboard?gameCode=2026090002
captured after Round 4 (FINAL) completed -- content/website_v2/
incoming_evidence/2026090002/HANA_2026090002_R4_LEADERBOARD_RAW_V1.html
(byte-identical copy of the operator-supplied source; sha256 recorded
below and again inside the FinalTruth artifact's own provenance field).

CONFIRMED (2026-09-20, against the real capture, not asserted on the
operator's word alone):
  - 64 total rows after de-duplication by player_id (the DOM renders a
    hidden "favorites" copy of every row twice; parse_round_leaderboard_html
    already collapses this by player_code -- see its own docstring).
  - 63 ACTIVE (status=None from the parser) + 1 WD (방신실, player_id
    10095) -- the WD row's real (non-hidden) list item shows the
    literal displayed text "WD" next to the player's name (confirmed via
    a direct BeautifulSoup text search on that specific row, not merely
    the parser's own classification) and holes_completed="10" (withdrew
    partway through Round 4; R1 74 / R2 73 / R3 82 fully completed).
  - Winner: 김민선7 (10097), R1 71 / R2 70 / R3 67 / R4 68 / TOTAL 276 /
    FINAL -12 (par 288). Runner-up: 장은수 (8243), TOTAL 280, FINAL -8,
    rank 2.
  - R1+R2+R3+R4 == TOTAL and TOTAL-288 == to-par for all 63 ACTIVE
    players (verified programmatically below; a single mismatch halts
    this script rather than silently proceeding).
  - Tied official ranks (e.g. two players both displaying rank "4") are
    preserved exactly as shown -- final_rank is the parser's own
    unmodified numeric parse of the site's own data-rank text, never
    renumbered to break a tie.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.parsers.leaderboard_parser import parse_round_leaderboard_html  # noqa: E402
from klpga.neo_win import final_truth  # noqa: E402
from klpga.tournament_context import load_tournament_context  # noqa: E402

GAME_CODE = "2026090002"
RAW_PATH = CONTENT / "incoming_evidence" / GAME_CODE / "HANA_2026090002_R4_LEADERBOARD_RAW_V1.html"
PAR_TOTAL = 288  # par 72 x 4 rounds

EXPECTED_WD_IDS = {"10095"}
EXPECTED_WINNER_ID = "10097"


def _to_par_display(n: int) -> str:
    if n == 0:
        return "E"
    return f"+{n}" if n > 0 else str(n)


def main() -> None:
    context = load_tournament_context(GAME_CODE)

    if final_truth.final_truth_exists(context):
        print(f"[FINAL TRUTH] {final_truth.final_truth_path(context)} already exists (immutable) -- not rebuilding")
        return

    raw_bytes = RAW_PATH.read_bytes()
    raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    html = raw_bytes.decode("utf-8", errors="replace")

    rows = parse_round_leaderboard_html(html, game_code=GAME_CODE, round_number=4)
    print(f"[PARSE] {len(rows)} rows parsed (deduplicated by player_id) from the real official 4R leaderboard capture")

    ids = [r.player_code for r in rows]
    assert len(ids) == len(set(ids)), f"REFUSING: duplicate player_id(s) after parser de-dup: {[i for i in ids if ids.count(i) > 1]}"
    assert len(rows) == 64, f"expected 64 total players in the official FINAL field, got {len(rows)}"

    active_rows = [r for r in rows if r.status is None]
    wd_rows = [r for r in rows if r.status == "WD"]
    assert len(active_rows) == 63, f"expected 63 ACTIVE finishers, got {len(active_rows)}"
    assert len(wd_rows) == 1, f"expected exactly 1 WD player, got {len(wd_rows)}"
    wd_ids = {r.player_code for r in wd_rows}
    assert wd_ids == EXPECTED_WD_IDS, f"WD id set mismatch: got {wd_ids}, expected {EXPECTED_WD_IDS}"

    # Arithmetic invariant (all 63 ACTIVE): R1+R2+R3+R4 == TOTAL and
    # TOTAL - 288 == to-par. A single mismatch halts this script.
    arithmetic_fails = []
    for r in active_rows:
        rounds_sum = r.round1_score + r.round2_score + r.round3_score + r.round4_score
        if rounds_sum != r.total_strokes:
            arithmetic_fails.append((r.player_code, r.player_name, "round_sum_ne_total", rounds_sum, r.total_strokes))
        if (r.total_strokes - PAR_TOTAL) != r.total_under_par:
            arithmetic_fails.append((r.player_code, r.player_name, "total_ne_topar", r.total_strokes - PAR_TOTAL, r.total_under_par))
    if arithmetic_fails:
        raise RuntimeError(f"REFUSING: arithmetic invariant failed for {len(arithmetic_fails)} player(s): {arithmetic_fails}")
    print(f"[ARITHMETIC] R1+R2+R3+R4==TOTAL and TOTAL-{PAR_TOTAL}==to-par verified for all {len(active_rows)} ACTIVE players -- 0 mismatches")

    winner_rows = [r for r in active_rows if r.rank == 1]
    assert len(winner_rows) == 1, f"expected exactly 1 player at rank 1, found {len(winner_rows)}"
    assert winner_rows[0].player_code == EXPECTED_WINNER_ID, f"winner mismatch: got {winner_rows[0].player_code}, expected {EXPECTED_WINNER_ID}"
    winner = winner_rows[0]
    print(f"[WINNER] {winner.player_code} {winner.player_name} R1 {winner.round1_score} R2 {winner.round2_score} "
          f"R3 {winner.round3_score} R4 {winner.round4_score} TOTAL {winner.total_strokes} FINAL {_to_par_display(winner.total_under_par)}")

    runner_up_rows = [r for r in active_rows if r.rank == 2]
    assert len(runner_up_rows) == 1
    ru = runner_up_rows[0]
    print(f"[RUNNER-UP] {ru.player_code} {ru.player_name} TOTAL {ru.total_strokes} FINAL {_to_par_display(ru.total_under_par)} rank {ru.rank}")

    records = []
    for r in active_rows:
        rank = r.rank
        records.append({
            "player_id": r.player_code,
            "player_name": r.player_name,
            "final_rank": rank,
            "final_score": _to_par_display(r.total_under_par),
            "r4_score": r.today_under_par,
            "rounds_completed": 4,
            "status": "ACTIVE",
            "top5_actual": rank <= 5,
            "top10_actual": rank <= 10,
            "top20_actual": rank <= 20,
        })
    for r in wd_rows:
        # WD: holes_completed (data-inghole) tells us how far into round 4
        # the player got. Confirmed 10095/방신실 completed R1-R3 fully
        # (74/73/82, both real, non-placeholder scores) and withdrew after
        # 10 holes of R4 -- rounds_completed=3 (the last FULLY completed
        # round), never a fabricated numeric final_rank.
        records.append({
            "player_id": r.player_code,
            "player_name": r.player_name,
            "final_rank": "WD",
            "final_score": "—",  # em dash, matches r3_real_page.EMPTY_MARK convention
            "r4_score": None,
            "rounds_completed": 3,
            "status": "WD",
            "top5_actual": False,
            "top10_actual": False,
            "top20_actual": False,
        })

    assert len(records) == 64
    truth = final_truth.build_final_truth(
        context=context,
        official_source="klpga.co.kr web/leaderboard/leaderboard (gameCode=2026090002), operator-supplied real FINAL (4R) capture",
        collected_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        raw_official_response=raw_bytes,
        records=records,
        repo_root=REPO_ROOT,
        build_id=f"hana_final_truth_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
    )
    out_path = final_truth.write_final_truth_immutable(context, truth)
    print(f"[FINAL TRUTH] wrote {out_path}")
    print(f"[PROVENANCE] raw_sha256={raw_sha256}")
    print(f"[PROVENANCE] raw_official_response_sha256(recorded)={truth.raw_official_response_sha256}")
    print(f"[PROVENANCE] parsed_canonical_sha256={truth.parsed_canonical_sha256}")
    print(f"[STATUS COUNTS] {truth.status_counts}")


if __name__ == "__main__":
    main()
