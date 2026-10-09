"""Parse + validate real official R1/R2 Strokes Gained for HJ 2026100004
from already-fetched raw strokesGained_detail HTML (fetched for real via
.github/workflows/test-sg-endpoint-hj-2026100004-oneoff.yml -- a GitHub
Actions runner with real network access, since this sandbox cannot reach
klpga.co.kr directly) and write it to an INTERNAL-ONLY content file.

This file (and the SG values inside it) must NEVER be read by any public
page builder or copied into docs/. It exists only so NEO's internal R3
forecast can be red-teamed/cross-checked against real Strokes Gained,
per the operator's explicit SG non-disclosure rule.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klpga.website_v2.official_data import parse_sg_html, validate_sg_record

CONTENT = Path(__file__).resolve().parents[1] / "content" / "website_v2"
IDENTITY_PATH = CONTENT / "2026100004_CANONICAL_PLAYER_IDENTITY_V1.json"
OUT_PATH = CONTENT / "HJ_2026100004_SG_INTERNAL_R1_R2_V1.json"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--round1-html", type=Path, required=True)
    ap.add_argument("--round2-html", type=Path, required=True)
    args = ap.parse_args()

    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    canon_names = {r["player_name"] for r in identity["records"]}
    code_by_name = {r["player_name"]: r["player_code"] for r in identity["records"]}

    by_round = {}
    for round_number, html_path in ((1, args.round1_html), (2, args.round2_html)):
        html = html_path.read_text(encoding="utf-8")
        records = parse_sg_html(html, scope="single_round", round_number=round_number)
        assert records, f"round {round_number}: SG table parsed to zero rows"
        unknown = {r["player"] for r in records} - canon_names
        assert not unknown, f"round {round_number}: SG rows for unrecognized players: {unknown}"
        for record in records:
            validation = validate_sg_record(record)
            assert validation["total_within_tolerance"], f"round {round_number} {record['player']}: total SG component mismatch {validation}"
            assert validation["t2g_within_tolerance"], f"round {round_number} {record['player']}: tee-to-green SG component mismatch {validation}"
            record["player_code"] = code_by_name[record["player"]]
        by_round[str(round_number)] = records

    out = {
        "schema_version": 1,
        "target_game_code": "2026100004",
        "internal_only": True,
        "public_disclosure_policy": "SG raw data and SG values must NEVER appear on any public page, public data file, public report, or visible page source -- internal validation use only",
        "source": "POST https://klpga.co.kr/load/leaderboard/strokesGained_detail (form: gameCode, round) -- real network fetch via .github/workflows/test-sg-endpoint-hj-2026100004-oneoff.yml, this sandbox cannot reach klpga.co.kr directly",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "round_record_counts": {k: len(v) for k, v in by_round.items()},
        "round_record_counts_note": "round 2 has 107 (not 108): 손예빈 (WD) has no round-2 scorecard to compute SG from",
        "rounds": by_round,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"written": str(OUT_PATH), "round_record_counts": out["round_record_counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
