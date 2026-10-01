"""RED TEAM: independently cross-check 2026100005_LEADERBOARD.json
(built from the leaderboard raw capture) against the SEPARATE scorecard
raw capture -- two independently-rendered official KLPGA pages for the
same round, each with its own markup. Compares player_count, to-par,
and the real R1 stroke score per player_id; fails loudly on any
mismatch, prints a 100% match confirmation on success. Never silently
tolerates a discrepancy.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
GAME_CODE = "2026100005"

SCORECARD_PATH = CONTENT / "incoming_evidence" / GAME_CODE / "HITEJINRO_2026100005_R1_SCORECARD_RAW.html"
LEADERBOARD_PATH = CONTENT / f"{GAME_CODE}_LEADERBOARD.json"


def parse_scorecard(html: str) -> dict[str, dict]:
    chunks = re.split(r"(?=playerCode=\d+)", html)
    by_id: dict[str, dict] = {}
    for chunk in chunks[1:]:
        pc_m = re.match(r"playerCode=(\d+)", chunk)
        if not pc_m:
            continue
        pid = pc_m.group(1)
        window = chunk[:2500]
        name_m = re.search(r"<span class=\"name\"><b>([^<]+)</b></span>", window)
        topar_m = re.search(r"<span class=\"(?:upcolor|dncolor|evcolor)?\"><b>(\+?-?\d+|E)</b></span>", window)
        r1_m = re.search(r"bg-bright\">(\d+)(?:\((\d+)\))?</td>", window)
        by_id[pid] = {
            "name": name_m.group(1) if name_m else None,
            "to_par": None if topar_m is None else (0 if topar_m.group(1) == "E" else int(topar_m.group(1))),
            "r1_score": int(r1_m.group(1)) if r1_m else None,
        }
    return by_id


def main() -> None:
    leaderboard = json.loads(LEADERBOARD_PATH.read_text(encoding="utf-8"))
    lb_by_id = {r["player_id"]: r for r in leaderboard["records"]}

    scorecard_html = SCORECARD_PATH.read_text(encoding="utf-8")
    sc_by_id = parse_scorecard(scorecard_html)

    mismatches = []

    if len(lb_by_id) != len(sc_by_id):
        mismatches.append(f"player_count: leaderboard={len(lb_by_id)} scorecard={len(sc_by_id)}")

    if set(lb_by_id) != set(sc_by_id):
        mismatches.append(
            f"player_id sets differ -- only in leaderboard: {sorted(set(lb_by_id) - set(sc_by_id))}, "
            f"only in scorecard: {sorted(set(sc_by_id) - set(lb_by_id))}"
        )

    for pid in sorted(set(lb_by_id) & set(sc_by_id)):
        lb = lb_by_id[pid]
        sc = sc_by_id[pid]
        if lb["player_name"] != sc["name"]:
            mismatches.append(f"{pid}: name leaderboard={lb['player_name']!r} scorecard={sc['name']!r}")
        if lb["score_to_par"] != sc["to_par"]:
            mismatches.append(f"{pid} ({lb['player_name']}): to_par leaderboard={lb['score_to_par']!r} scorecard={sc['to_par']!r}")
        if lb["r1_score"] != sc["r1_score"]:
            mismatches.append(f"{pid} ({lb['player_name']}): r1_score leaderboard={lb['r1_score']!r} scorecard={sc['r1_score']!r}")

    result = {
        "game_code": GAME_CODE,
        "leaderboard_player_count": len(lb_by_id),
        "scorecard_player_count": len(sc_by_id),
        "compared_fields": ["player_name", "score_to_par", "r1_score"],
        "mismatches": mismatches,
        "verdict": "100% MATCH" if not mismatches else "MISMATCH FOUND",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
