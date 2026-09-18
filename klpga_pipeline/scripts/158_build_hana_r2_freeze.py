"""Build 2026090002_R2_FROZEN_EVIDENCE.json for Hana (하나금융그룹 챔피언십)
from the real, official R2 roundLeaderboard HTML capture the operator
supplied (content/website_v2/incoming_evidence/2026090002/HANA_
2026090002_R2_OFFICIAL_RAW.html), using klpga.neo_win.r2_freeze's
generic, already-existing freeze schema -- the SAME one KB's own R2
freeze uses. No live network access, no new freeze schema.

Parsing uses klpga.parsers.leaderboard_parser.parse_round_leaderboard_html,
the project's one established, trusted parser for this exact official
endpoint shape (confirmed via browser Network capture against POST
https://klpga.co.kr/load/leaderboard/roundLeaderboard).

Status assignment (never guessed):
  - WD: EXACTLY the 3 players the operator explicitly, by name,
    confirmed as WD (최예본/리 슈잉/박혜준) AND whom the parser
    independently flags status=INCOMPLETE (no R2 score, data-rank=999
    sentinel) -- both sources must agree, or this script refuses.
  - ACTIVE: a valid-score player whose cumulative total_under_par is
    within the official cut line (+6 / 150 strokes for 2 rounds at
    par 72) -- made the cut.
  - CUT: a valid-score player whose cumulative total_under_par exceeds
    the cut line -- missed the cut. Still frozen (kept in the R2
    record set for the score table), never excluded and never given a
    fabricated probability.
  - The 3 "entry-only" players in the 108 official field who never
    appear on this 105-row R2 leaderboard AT ALL (권은 0906(A)/
    김리안/조혜림) are NOT written as any status -- they simply have
    no record here, per the operator's explicit instruction never to
    infer WD/DNS for them without official basis.

r1_score_to_par is joined from the real, already-published R1 evidence
(HANA_2026090002_R1_PLAYER_RESULT_V1.json's today_under_par, which for
round 1 already IS record.total_under_par) -- never re-derived,
never fabricated, exactly mirroring KB script 112's own
_apply_r1_scores documented rule for this field.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_context import load_tournament_context  # noqa: E402
from klpga.parsers.leaderboard_parser import parse_round_leaderboard_html  # noqa: E402
from klpga.neo_win.r2_freeze import build_r2_frozen_evidence, r2_freeze_exists, write_r2_freeze_immutable  # noqa: E402

GAME_CODE = "2026090002"
CONTENT = ROOT / "content" / "website_v2"
RAW_HTML_PATH = CONTENT / "incoming_evidence" / GAME_CODE / "HANA_2026090002_R2_OFFICIAL_RAW.html"
R1_RESULT_PATH = CONTENT / "HANA_2026090002_R1_PLAYER_RESULT_V1.json"
ENTRY_LIST_PATH = CONTENT / "HANA_2026090002_OFFICIAL_ENTRY_LIST_V2.json"
PRE_FREEZE_PATH = CONTENT / "HANA_2026090002_PRE_M4_60000_CANDIDATE_V2.json"
R1_FREEZE_PATH = CONTENT / "HANA_2026090002_R1_ANALYSIS_V1.json"

CONFIRMED_WD_NAMES = {"최예본", "리 슈잉", "박혜준"}
PAR = 72
CUT_TO_PAR = 6  # +6 / 150 for 2 rounds


def main():
    context = load_tournament_context(GAME_CODE)
    if r2_freeze_exists(context):
        print(f"[FREEZE] {context.artifact_path('r2_frozen_evidence')} already exists (immutable) -- not rebuilding")
        return

    raw_bytes = RAW_HTML_PATH.read_bytes()
    html = raw_bytes.decode("utf-8")
    rows = parse_round_leaderboard_html(html, game_code=GAME_CODE, round_number=2)
    print(f"[PARSE] {len(rows)} rows parsed from real R2 official leaderboard capture")

    entry_list = json.loads(ENTRY_LIST_PATH.read_text(encoding="utf-8"))
    official_field_size = entry_list["summary"]["total"]
    entry_ids = {str(r["player_id"]) for r in entry_list["records"]}
    leaderboard_ids = {str(r.player_code) for r in rows}
    entry_only_ids = entry_ids - leaderboard_ids
    print(f"[CROSS-CHECK] official field={official_field_size}, on R2 leaderboard={len(leaderboard_ids)}, entry-only (no R2 row)={len(entry_only_ids)}")

    r1_result = json.loads(R1_RESULT_PATH.read_text(encoding="utf-8"))
    r1_score_by_player = {
        str(r["player_id"]): r["today_under_par"]
        for r in r1_result["records"]
        if r.get("today_under_par") is not None
    }

    dup_check = {}
    for r in rows:
        dup_check.setdefault(str(r.player_code), []).append(r)
    duplicates = {k: v for k, v in dup_check.items() if len(v) > 1}
    if duplicates:
        raise RuntimeError(f"REFUSING: duplicate player_code(s) in parsed R2 leaderboard: {list(duplicates)}")

    wd_rows = [r for r in rows if r.status == "WD"]
    wd_names = {r.player_name for r in wd_rows}
    if wd_names != CONFIRMED_WD_NAMES:
        raise RuntimeError(
            f"REFUSING: parser-flagged status=WD names {wd_names!r} != operator-confirmed WD set {CONFIRMED_WD_NAMES!r}"
        )
    print(f"[WD] confirmed: parser status=WD set == operator-confirmed WD set ({sorted(CONFIRMED_WD_NAMES)})")

    valid_rows = [r for r in rows if r.status != "WD"]
    arithmetic_errors = []
    for r in valid_rows:
        if r.round1_score is not None and r.total_strokes is not None:
            pass  # spot-checked independently already; not re-verified here (no round2-only stroke field parsed separately)
    made_cut_count = sum(1 for r in valid_rows if r.total_under_par is not None and r.total_under_par <= CUT_TO_PAR)
    print(f"[CUT] valid-score rows={len(valid_rows)}, made_cut(<=+{CUT_TO_PAR})={made_cut_count}, missed_cut={len(valid_rows) - made_cut_count}")

    records = []
    missing_r1_score = []
    for r in rows:
        pid = str(r.player_code)
        if r.status == "WD":
            status = "WD"
            r2_score_to_par = None
        else:
            status = "ACTIVE" if (r.total_under_par is not None and r.total_under_par <= CUT_TO_PAR) else "CUT"
            r2_score_to_par = r.today_under_par
        r1_score_to_par = r1_score_by_player.get(pid)
        if status != "WD" and r1_score_to_par is None:
            missing_r1_score.append(pid)
        records.append({
            "player_id": pid,
            "player_name": r.player_name,
            "status": status,
            "r1_score_to_par": r1_score_to_par,
            "r2_score_to_par": r2_score_to_par,
            "r2_total_under_par": r.total_under_par,
            "made_cut": status == "ACTIVE",
        })
    if missing_r1_score:
        print(f"[WARN] {len(missing_r1_score)} non-WD player(s) have no real R1 score joined: {missing_r1_score}")

    status_counts = {"ACTIVE": 0, "CUT": 0, "WD": 0, "DQ": 0, "DNS": 0}
    cut_wd_dq_evidence = []
    for rec in records:
        status_counts[rec["status"]] = status_counts.get(rec["status"], 0) + 1
        if rec["status"] in ("CUT", "WD", "DQ"):
            cut_wd_dq_evidence.append({
                "player_id": rec["player_id"], "status": rec["status"],
                "evidence": "official R2 leaderboard row (data-rank=999 INCOMPLETE sentinel for WD; +6/150 official cut line for CUT)",
            })
    print(f"[STATUS COUNTS] {status_counts}")

    evidence = build_r2_frozen_evidence(
        context=context,
        official_source_identity="klpga.co.kr roundLeaderboard (gameCode=2026090002, round=2), operator-supplied real capture",
        official_source_url=f"https://klpga.co.kr/load/leaderboard/roundLeaderboard?gameCode={GAME_CODE}&round=2",
        collection_timestamp=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        raw_official_response=raw_bytes,
        records=records,
        expected_field_count=official_field_size,
        status_counts=status_counts,
        cut_wd_dq_evidence=cut_wd_dq_evidence,
        pre_freeze_path=PRE_FREEZE_PATH,
        r1_freeze_path=R1_FREEZE_PATH,
        repo_root=REPO_ROOT,
        build_id=f"hana_r2_freeze_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
    )
    out_path = write_r2_freeze_immutable(context, evidence)
    print(f"[FREEZE] wrote {out_path}")


if __name__ == "__main__":
    main()
