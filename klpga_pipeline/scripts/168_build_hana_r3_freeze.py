"""Build 2026090002_R3_FROZEN_EVIDENCE.json for Hana (하나금융그룹 챔피언십)
from the real, official R3 leaderboard HTML capture the operator
supplied (content/website_v2/incoming_evidence/2026090002/HANA_
2026090002_R3_LEADERBOARD_RAW_V1.html), using klpga.neo_win.r3_freeze's
generic, already-existing freeze schema -- the SAME one KB's own R3
freeze uses. No live network access, no new freeze schema.

NO NEW CUT EVENT AT R3 (see r3_freeze.py's own module docstring): the
R3-eligible population IS the R2 freeze's own 64 ACTIVE (advancing)
players -- verified below to be an exact bijection with the real R3
leaderboard capture (64/64 matched, 0 duplicates, 0 missing, 0 WD
during R3).

Parsing reuses klpga.parsers.leaderboard_parser.parse_round_leaderboard_html,
the same trusted parser already used for R1/R2 (confirmed against this
exact file: same data-round1score/round2score/round3score/data-
totunderpar/_playercode attribute shape).
"""
from __future__ import annotations
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_context import load_tournament_context  # noqa: E402
from klpga.parsers.leaderboard_parser import parse_round_leaderboard_html  # noqa: E402
from klpga.neo_win.r3_freeze import build_r3_frozen_evidence, r3_freeze_exists, write_r3_freeze_immutable  # noqa: E402
import json  # noqa: E402

GAME_CODE = "2026090002"
CONTENT = ROOT / "content" / "website_v2"
RAW_HTML_PATH = CONTENT / "incoming_evidence" / GAME_CODE / "HANA_2026090002_R3_LEADERBOARD_RAW_V1.html"
R2_FREEZE_PATH = CONTENT / "2026090002_R2_FROZEN_EVIDENCE.json"


def main():
    context = load_tournament_context(GAME_CODE)
    if r3_freeze_exists(context):
        print(f"[FREEZE] {context.artifact_path('r3_frozen_evidence')} already exists (immutable) -- not rebuilding")
        return

    raw_bytes = RAW_HTML_PATH.read_bytes()
    html = raw_bytes.decode("utf-8")
    rows = parse_round_leaderboard_html(html, game_code=GAME_CODE, round_number=3)
    print(f"[PARSE] {len(rows)} rows parsed from real R3 official leaderboard capture")

    r2_freeze = json.loads(R2_FREEZE_PATH.read_text(encoding="utf-8"))
    r2_active = [r for r in r2_freeze["records"] if r["status"] == "ACTIVE"]
    r2_active_ids = {r["player_id"] for r in r2_active}
    assert len(r2_active_ids) == 64, f"expected 64 R2 ACTIVE survivors, got {len(r2_active_ids)}"

    dup_check = {}
    for r in rows:
        dup_check.setdefault(str(r.player_code), []).append(r)
    duplicates = {k: v for k, v in dup_check.items() if len(v) > 1}
    if duplicates:
        raise RuntimeError(f"REFUSING: duplicate player_code(s) in parsed R3 leaderboard: {list(duplicates)}")

    parsed_ids = {str(r.player_code) for r in rows}
    missing_from_r3 = r2_active_ids - parsed_ids
    extra_in_r3 = parsed_ids - r2_active_ids
    if missing_from_r3:
        raise RuntimeError(f"REFUSING: R2 survivor(s) missing from real R3 leaderboard: {missing_from_r3}")
    if extra_in_r3:
        raise RuntimeError(f"REFUSING: R3 leaderboard has player(s) never in the R2 ACTIVE survivor set: {extra_in_r3}")
    print(f"[IDENTITY GATE] R2 survivors == R3 leaderboard population: 64/64 matched, 0 duplicates, 0 missing")

    r1_by_id = {r["player_id"]: r["r1_score_to_par"] for r in r2_active}
    r2_by_id = {r["player_id"]: r["r2_score_to_par"] for r in r2_active}

    records = []
    missing_r3_score = []
    wd_dq_dns_evidence = []
    for r in rows:
        pid = str(r.player_code)
        if r.round3_score is None:
            missing_r3_score.append(pid)
            status = "WD"
            r3_score_to_par = None
            wd_dq_dns_evidence.append({"player_id": pid, "status": "WD", "evidence": "no real round3_score on official R3 leaderboard row"})
        else:
            status = "ACTIVE"
            r3_score_to_par = r.today_under_par
        records.append({
            "player_id": pid,
            "player_name": r.player_name,
            "status": status,
            "r1_score_to_par": r1_by_id[pid],
            "r2_score_to_par": r2_by_id[pid],
            "r3_score_to_par": r3_score_to_par,
            "r3_total_under_par": r.total_under_par,
            "made_cut": True,
        })
    if missing_r3_score:
        raise RuntimeError(f"REFUSING: {len(missing_r3_score)} confirmed cutmaker(s) missing a real R3 score: {missing_r3_score}")

    status_counts = {"ACTIVE": 0, "WD": 0, "DQ": 0, "DNS": 0}
    for rec in records:
        status_counts[rec["status"]] += 1
    print(f"[STATUS COUNTS] {status_counts}")

    evidence = build_r3_frozen_evidence(
        context=context,
        official_source_identity="klpga.co.kr web/leaderboard/leaderboard (gameCode=2026090002), operator-supplied real R3 capture",
        official_source_url=f"https://klpga.co.kr/web/leaderboard/leaderboard?gameCode={GAME_CODE}",
        collection_timestamp=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        raw_official_response=raw_bytes,
        records=records,
        expected_field_count=64,
        status_counts=status_counts,
        wd_dq_dns_evidence=wd_dq_dns_evidence,
        r2_freeze_path=R2_FREEZE_PATH,
        repo_root=REPO_ROOT,
        build_id=f"hana_r3_freeze_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
    )
    out_path = write_r3_freeze_immutable(context, evidence)
    print(f"[FREEZE] wrote {out_path}")


if __name__ == "__main__":
    main()
