"""UNIFIED PLAYER HISTORY RECONCILIATION -- playerCode=10097 (김민선7) ONLY.

Player History must never depend on a single warehouse. Before ANY
report is generated, this module collects her career record from every
verified real source in this repository, in priority order, and
reconciles them into one canonical per-tournament dataset:

  1. Official SG Warehouse           (historical_sg_warehouse_corrected_v2.json)
  2. Official Tournament Warehouse   (evidence/official_tournament_warehouse_v1/*.json)
  3. Official Round Warehouse        (embedded in #2's round_rows -- no
                                       separately-named artifact exists;
                                       confirmed by repository-wide search)
  4. Official Reader outputs         (evidence/*_FR//*_R3/ leaderboard scrapes)
  5. Official Live Tournament snapshots (content/website_v2/*_LIVE_SNAPSHOT.json,
                                       HANA_2026090002_R{1-4}_SG_V1.json)
  6. Official normalized datasets    (OFFICIAL_SG_NORMALIZED.json,
                                       OFFICIAL_PROFILE_NORMALIZED.json --
                                       current-season snapshot only, not
                                       merged into per-tournament records)
  7. Verified supplemental datasets  (2026090002_FINAL_TRUTH.json)

Root cause this replaces: three of her most recent tournaments --
2026090002 (Hana, her most recent win), 2026090003 (KB), and 2026120001
(OK Open, still in progress) -- live entirely in their own dedicated
per-tournament files and were never backfilled into the SG warehouse.
Prior code (build_10097_master_player_analysis.py, build_10097_player_history.py)
patched only the Hana win, one tournament at a time, using only R1-R3 of
her real R1-R4 round SG (missing the official R4 file entirely, which
also carries the tournament's own official 4-round cumulative SG --
4.50, not the 4.63 the old R1-R3-only patch produced). That is exactly
the failure mode this reconciliation replaces: every known real source
is consulted for every tournament, every time, and a NEW tournament
that appears in a shape this module does not already know how to read
raises ReconciliationError instead of being silently dropped.

Every tournament must be accounted for exactly once. If reconciliation
does not fully account for every known tournament, or a genuine
conflict is found between two sources describing the same fact,
reconcile() raises ReconciliationError and no report may be generated
from a failed reconciliation.
"""
from __future__ import annotations

import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_context import CONTENT_DIR  # noqa: E402

PLAYER_ID = "10097"
PLAYER_NAME = "김민선7"
EVIDENCE_DIR = ROOT / "evidence"

# Tournaments handled with a dedicated reconciled loader because the
# SG Warehouse does not (yet) contain them. Every one of these MUST be
# independently re-discoverable by _discover_special_game_codes() below --
# that discovery pass is what turns "the next missing tournament" into a
# loud failure instead of a silent gap.
_KNOWN_SPECIAL_GAME_CODES = {"2026090002", "2026090003", "2026120001"}


class ReconciliationError(Exception):
    """Raised when the repository's known real sources cannot be fully
    and unambiguously reconciled into one canonical tournament dataset.
    Per mission: if reconciliation fails, report generation must stop."""


def _load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_content(name: str) -> Optional[dict]:
    return _load_json(CONTENT_DIR / name)


def _rank_from_display(display) -> Optional[int]:
    """'T16' / '24' / 1 -> 16 / 24 / 1. None if not parseable."""
    if display is None:
        return None
    if isinstance(display, int):
        return display
    s = str(display).strip().lstrip("Tt")
    try:
        return int(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# CATEGORY 1 -- Official SG Warehouse (base ~94 tournaments)
# ---------------------------------------------------------------------------

def _load_sg_warehouse_rows() -> list:
    doc = _load_content("historical_sg_warehouse_corrected_v2.json")
    if not doc:
        raise ReconciliationError("Official SG Warehouse (historical_sg_warehouse_corrected_v2.json) is missing -- cannot reconcile without the primary source.")
    return [r for r in doc.get("records", []) if r.get("player_id") == PLAYER_ID]


def _sg_warehouse_tournaments(rows: list) -> dict:
    """game_code -> canonical record, tournament_cumulative scope only."""
    out = {}
    for r in rows:
        if r.get("scope") != "tournament_cumulative" or r.get("identity_state") != "RETAINED":
            continue
        gc = r["game_code"]
        out[gc] = {
            "game_code": gc,
            "season": r["season"],
            "tournament": r.get("tournament"),
            "status": "FINISHED",
            "rank": r.get("rank"),
            "rank_display": str(r.get("rank")) if r.get("rank") is not None else None,
            "rounds_played": r.get("rounds"),
            "sg_total": r.get("total"),
            "sg_ott": r.get("off_the_tee"),
            "sg_app": r.get("approach"),
            "sg_arg": r.get("around_green"),
            "sg_putt": r.get("putting"),
            "sources": ["sg_warehouse"],
        }
    return out


def _sg_warehouse_round_rows(rows: list) -> list:
    return [
        {"game_code": r["game_code"], "season": r["season"], "round": r["round"], "sg_total": r["total"], "source": "sg_warehouse"}
        for r in rows
        if r.get("scope") == "single_round" and r.get("identity_state") == "RETAINED" and r.get("total") is not None
    ]


# ---------------------------------------------------------------------------
# CATEGORY 2/3 -- Official Tournament Warehouse / Round Warehouse
# (round_rows embedded in the Tournament Warehouse -- no separate
# "Round Warehouse" artifact exists anywhere in the repository; verified
# by a full repository search before writing this module)
# ---------------------------------------------------------------------------

def _load_tournament_warehouse_round_rows() -> list:
    """Raw per-round strokes for this player, wherever the Tournament
    Warehouse module recorded them. Complements, never replaces, SG
    Warehouse rows -- rank fields here are SCORE rank, not SG rank, so
    they are never compared against SG Warehouse rank as if they were
    the same fact."""
    out = []
    doc = _load_json(EVIDENCE_DIR / "official_tournament_warehouse_v1" / "OFFICIAL_TOURNAMENT_WAREHOUSE_V1.json")
    if doc:
        for row in doc.get("round_rows", []):
            if row.get("playerCode") == PLAYER_ID:
                out.append({
                    "game_code": row["gameCode"], "round": row["round"],
                    "strokes": row.get("round_score"), "score_rank": (row.get("raw_source_values") or {}).get(f"r{row['round']}_rank"),
                    "source": "tournament_warehouse",
                })
    return out


def _load_ok_open_round_rows() -> list:
    """2026120001 (OK Open) round-level truth -- the tournament is still
    IN PROGRESS as of the latest capture in this repository (R1, R2
    complete; R3 partial). Never treated as a finished tournament."""
    doc = _load_json(EVIDENCE_DIR / "official_tournament_warehouse_v1" / "2026120001_RECONCILED_PLAYER_ROUNDS.json")
    if not doc:
        return []
    return [
        {"game_code": row["gameCode"], "round": row["round"], "rank_display": row.get("rank"),
         "strokes": int(row["round_score"]) if row.get("round_score") not in (None, "0") else None,
         "total_strokes": int(row["total_score"]) if row.get("total_score") is not None else None,
         "ing_hole": row.get("ingHole"), "source": "tournament_warehouse"}
        for row in doc.get("rows", []) if row.get("playerCode") == PLAYER_ID
    ]


# ---------------------------------------------------------------------------
# CATEGORY 4 -- Official Reader outputs (KB 2026090003)
# ---------------------------------------------------------------------------

def _load_kb_reader_final() -> Optional[dict]:
    """KB금융 골든라이프 챔피언십 (2026090003) -- never in the SG
    Warehouse. No SG data exists for this tournament anywhere in the
    repository (confirmed by search); only raw strokes/finish. The FR
    (final round) supplied leaderboard is the authoritative final
    result; the R3 official leaderboard is used only to cross-check the
    R1-R3 cumulative arithmetic before FR is trusted."""
    fr_doc = _load_json(EVIDENCE_DIR / "KB_2026090003_FR" / "KB_2026090003_KLPGA_OFFICIAL_FR_70_SUPPLIED.json")
    r3_doc = _load_json(EVIDENCE_DIR / "KB_2026090003_R3" / "KB_2026090003_R3_OFFICIAL_FINAL.json")
    if not fr_doc:
        return None
    fr_row = next((p for p in fr_doc.get("players", []) if p.get("player_name") == PLAYER_NAME), None)
    if not fr_row:
        return None
    r3_row = None
    if r3_doc:
        r3_row = next((r for r in r3_doc.get("rows", []) if r.get("playerCode") == PLAYER_ID), None)

    resolved = []
    if r3_row:
        r3_cumulative_check = fr_row["r1_score"] + fr_row["r2_score"] + fr_row["r3_score"]
        if r3_cumulative_check != r3_row["cumulative_score"]:
            raise ReconciliationError(
                f"2026090003: Reader R1+R2+R3 sum ({r3_cumulative_check}) does not match "
                f"Reader R3 official cumulative_score ({r3_row['cumulative_score']}) -- unresolved conflict."
            )
        resolved.append(
            f"2026090003 (KB): Reader R3 cumulative_score ({r3_row['cumulative_score']}) == R1+R2+R3 "
            f"({fr_row['r1_score']}+{fr_row['r2_score']}+{fr_row['r3_score']}) -- agrees."
        )
    fr_total_check = fr_row["r1_score"] + fr_row["r2_score"] + fr_row["r3_score"] + fr_row["fr_score"]
    if fr_total_check != fr_row["total_strokes"]:
        raise ReconciliationError(
            f"2026090003: Reader FR round sum ({fr_total_check}) does not match Reader FR total_strokes "
            f"({fr_row['total_strokes']}) -- unresolved conflict."
        )
    resolved.append(
        f"2026090003 (KB): Reader FR total_strokes ({fr_row['total_strokes']}) == R1+R2+R3+FR "
        f"({fr_row['r1_score']}+{fr_row['r2_score']}+{fr_row['r3_score']}+{fr_row['fr_score']}) -- agrees. "
        "FR (final round) leaderboard used as the canonical final result."
    )

    record = {
        "game_code": "2026090003",
        "season": 2026,
        "tournament": fr_doc.get("tournament"),
        "status": "FINISHED",
        "rank": _rank_from_display(fr_row["final_position"]),
        "rank_display": fr_row["final_position"],
        "rounds_played": 4,
        "sg_total": None, "sg_ott": None, "sg_app": None, "sg_arg": None, "sg_putt": None,
        "sources": ["reader"],
        "round_scores": [
            {"round": 1, "strokes": fr_row["r1_score"]},
            {"round": 2, "strokes": fr_row["r2_score"]},
            {"round": 3, "strokes": fr_row["r3_score"]},
            {"round": 4, "strokes": fr_row["fr_score"]},
        ],
        "total_strokes": fr_row["total_strokes"],
        "to_par": fr_row.get("to_par"),
    }
    return {"record": record, "resolved": resolved}


# ---------------------------------------------------------------------------
# CATEGORY 5 -- Official Live Tournament snapshots (Hana R1-R4, OK Open)
# ---------------------------------------------------------------------------

def _load_hana_live_sg() -> Optional[dict]:
    """2026090002 (하나금융그룹 챔피언십). Per-round SG for R1-R4 plus
    the official 4-round cumulative SG (real, not re-derived by this
    module) -- this cumulative figure is what the earlier R1-R3-only
    patch was missing R4 for."""
    rounds = {}
    for n in (1, 2, 3, 4):
        doc = _load_content(f"HANA_2026090002_R{n}_SG_V1.json")
        if not doc:
            continue
        if n == 4:
            recs = (doc.get("r4_single_round_sg") or {}).get("records", [])
        else:
            recs = doc.get("records", [])
        row = next((r for r in recs if r.get("player_id") == PLAYER_ID), None)
        if row:
            rounds[n] = row["total"]
    if not rounds:
        return None

    cumulative = None
    r4_doc = _load_content("HANA_2026090002_R4_SG_V1.json")
    if r4_doc:
        cum_recs = (r4_doc.get("total_cumulative_sg") or {}).get("records", [])
        cumulative = next((r for r in cum_recs if r.get("player_id") == PLAYER_ID), None)

    resolved = []
    if cumulative and rounds:
        mean_of_rounds = round(sum(rounds.values()) / len(rounds), 4)
        if abs(mean_of_rounds - cumulative["total"]) > 0.02:
            raise ReconciliationError(
                f"2026090002: mean of R1-R{len(rounds)} SG Total ({mean_of_rounds}) does not match the "
                f"official cumulative SG Total ({cumulative['total']}) within tolerance -- unresolved conflict."
            )
        resolved.append(
            f"2026090002 (Hana): mean of real R1-R{len(rounds)} SG Total ({mean_of_rounds}) matches the "
            f"official 4-round cumulative SG Total ({cumulative['total']}) within tolerance -- confirms the "
            "warehouse's 'tournament_cumulative = mean of rounds' convention holds here too. Official "
            "cumulative used directly (not re-derived) since it is itself a primary official computation."
        )

    return {
        "rounds": rounds,
        "cumulative": cumulative,
        "resolved": resolved,
    }


def _load_ok_open_live_snapshots() -> dict:
    """2026120001 -- confirms Tournament Warehouse's raw R1/R2 strokes
    against the Live Snapshot's own capture, and surfaces the R3
    partial-round SG (holes_completed < 18, never treated as a finished
    round)."""
    out = {"rounds": {}, "r3_partial_sg": None, "resolved": []}
    r1 = _load_content("OK_OPEN_2026_R1_LIVE_SNAPSHOT.json")
    r2 = _load_content("OK_OPEN_2026_R2_LIVE_SNAPSHOT.json")
    r3 = _load_content("OK_OPEN_2026_R3_LIVE_SNAPSHOT.json")
    for n, doc in ((1, r1), (2, r2), (3, r3)):
        if not doc:
            continue
        row = next((p for p in doc.get("player_table", []) if p.get("player_code") == PLAYER_ID), None)
        if row:
            out["rounds"][n] = row
    if r3:
        sg_row = next((s for s in r3.get("sg", []) if s.get("player_id") == PLAYER_ID and s.get("scope") == "single_round"), None)
        if sg_row and sg_row.get("round") == 3:
            out["r3_partial_sg"] = sg_row
    return out


# ---------------------------------------------------------------------------
# CATEGORY 7 -- Verified supplemental datasets (Hana FINAL_TRUTH)
# ---------------------------------------------------------------------------

def _load_hana_final_truth() -> Optional[dict]:
    doc = _load_content("2026090002_FINAL_TRUTH.json")
    if not doc:
        return None
    row = next((r for r in doc.get("records", []) if r.get("player_id") == PLAYER_ID), None)
    if not row:
        return None
    return {"doc": doc, "row": row}


# ---------------------------------------------------------------------------
# DISCOVERY -- catch the NEXT missing tournament instead of patching it in
# ---------------------------------------------------------------------------

def _discover_special_game_codes() -> set:
    """Scan every known 'primary per-tournament truth' file SHAPE
    (not filename) in the repository for a real 10097 record whose
    game_code is not already in the SG Warehouse. This is what turns
    a future missing tournament into a loud ReconciliationError instead
    of a silent gap the way Hana was for months."""
    found = set()

    for path in CONTENT_DIR.glob("*_FINAL_TRUTH.json"):
        doc = _load_json(path)
        if doc and doc.get("game_code") and any(r.get("player_id") == PLAYER_ID for r in doc.get("records", [])):
            found.add(doc["game_code"])

    twh_dir = EVIDENCE_DIR / "official_tournament_warehouse_v1"
    if twh_dir.exists():
        for path in twh_dir.glob("*_RECONCILED_PLAYER_ROUNDS.json"):
            doc = _load_json(path)
            if doc and doc.get("gameCode") and any(r.get("playerCode") == PLAYER_ID for r in doc.get("rows", [])):
                found.add(doc["gameCode"])

    if EVIDENCE_DIR.exists():
        for sub in EVIDENCE_DIR.iterdir():
            if not sub.is_dir():
                continue
            for path in list(sub.glob("*_SUPPLIED.json")) + list(sub.glob("*_OFFICIAL_FINAL.json")):
                doc = _load_json(path)
                if not doc:
                    continue
                gc = doc.get("game_code") or doc.get("gameCode")
                if not gc:
                    continue
                rows = doc.get("players") or doc.get("rows") or []
                hit = any(
                    r.get("player_id") == PLAYER_ID or r.get("playerCode") == PLAYER_ID or r.get("player_name") == PLAYER_NAME
                    for r in rows
                )
                if hit:
                    found.add(gc)

    return found


# ---------------------------------------------------------------------------
# RECONCILE
# ---------------------------------------------------------------------------

def reconcile() -> dict:
    resolved_log: list = []
    conflicts: list = []

    sg_rows = _load_sg_warehouse_rows()
    tournaments = _sg_warehouse_tournaments(sg_rows)
    sg_warehouse_codes = set(tournaments.keys())
    round_rows = _sg_warehouse_round_rows(sg_rows)

    # Category 2/3: enrich (never overwrite) with raw stroke data where
    # the Tournament Warehouse independently captured the same round.
    tw_rounds = _load_tournament_warehouse_round_rows()
    merged_categories = defaultdict(lambda: {"sg_warehouse"})
    for code in tournaments:
        merged_categories[code] = {"sg_warehouse"}
    for row in tw_rounds:
        gc = row["game_code"]
        if gc not in tournaments:
            continue  # handled elsewhere (e.g. OK Open, not in SG warehouse at all)
        tournaments[gc].setdefault("raw_round_supplement", []).append({"round": row["round"], "strokes": row["strokes"]})
        resolved_log.append(
            f"{gc}: SG Warehouse tournament_cumulative rank (SG-based) and Tournament Warehouse R{row['round']} "
            f"score_rank ({row.get('score_rank')}) are different ranking systems (SG rank vs. stroke rank), not "
            f"comparable as the same fact -- no conflict. Real R{row['round']} raw strokes ({row['strokes']}) merged in."
        )
        merged_categories[gc].add("tournament_warehouse")

    # Category 4: KB (2026090003) -- not in SG warehouse at all.
    kb = _load_kb_reader_final()
    if kb:
        gc = kb["record"]["game_code"]
        if gc in tournaments:
            raise ReconciliationError(f"{gc}: expected to be reader-only (not in SG Warehouse) but SG Warehouse already has a row -- reconciliation logic is stale, update it before regenerating Player History.")
        tournaments[gc] = kb["record"]
        resolved_log.extend(kb["resolved"])
        merged_categories[gc] = {"reader"}

    # Category 5 + 7: Hana (2026090002) -- not in SG warehouse at all.
    hana_live = _load_hana_live_sg()
    hana_truth = _load_hana_final_truth()
    if hana_live or hana_truth:
        gc = "2026090002"
        if gc in tournaments:
            raise ReconciliationError(f"{gc}: expected to be live/supplemental-only (not in SG Warehouse) but SG Warehouse already has a row -- reconciliation logic is stale, update it before regenerating Player History.")
        if not (hana_live and hana_truth):
            raise ReconciliationError(f"{gc}: only one of Live Snapshot / Supplemental FINAL_TRUTH is present -- cannot reconcile a finished tournament from a partial source set.")
        row = hana_truth["row"]
        cum = hana_live["cumulative"] or {}
        tournaments[gc] = {
            "game_code": gc,
            "season": 2026,
            "tournament": hana_truth["doc"].get("tournament_name"),
            "status": "FINISHED",
            "rank": row["final_rank"],
            "rank_display": str(row["final_rank"]),
            "rounds_played": row["rounds_completed"],
            "sg_total": cum.get("total"),
            "sg_ott": cum.get("off_the_tee"),
            "sg_app": cum.get("approach"),
            "sg_arg": cum.get("around_green"),
            "sg_putt": cum.get("putting"),
            "sources": ["live_snapshot", "supplemental"],
            "round_scores": [{"round": n, "sg_total": v} for n, v in sorted(hana_live["rounds"].items())],
            "final_score_to_par": row.get("final_score"),
            "is_winner_per_official_source": True,
        }
        resolved_log.extend(hana_live["resolved"])
        resolved_log.append(
            f"2026090002 (Hana): Supplemental FINAL_TRUTH final_rank ({row['final_rank']}) and rounds_completed "
            f"({row['rounds_completed']}) merged with Live Snapshot per-round SG -- no conflict, complementary facts."
        )
        merged_categories[gc] = {"live_snapshot", "supplemental"}

    # Category 2/3 + 5: OK Open (2026120001) -- IN PROGRESS, not in SG warehouse.
    ok_rounds = _load_ok_open_round_rows()
    ok_live = _load_ok_open_live_snapshots()
    in_progress_tournament = None
    if ok_rounds:
        gc = "2026120001"
        if gc in tournaments:
            raise ReconciliationError(f"{gc}: expected to be warehouse/round + live-only (not in SG Warehouse tournament_cumulative) but a row already exists -- reconciliation logic is stale.")
        by_round = {r["round"]: r for r in ok_rounds}
        for n, live_row in ok_live["rounds"].items():
            tw_row = by_round.get(n)
            if not tw_row:
                continue
            live_score = live_row.get(f"round{n}_score")
            if live_score is not None and tw_row.get("strokes") is not None and live_score != tw_row["strokes"]:
                raise ReconciliationError(f"{gc} R{n}: Tournament/Round Warehouse strokes ({tw_row['strokes']}) != Live Snapshot round{n}_score ({live_score}) -- unresolved conflict.")
            if live_score is not None:
                resolved_log.append(f"2026120001 (OK Open) R{n}: Tournament/Round Warehouse strokes ({tw_row.get('strokes')}) == Live Snapshot round{n}_score ({live_score}) -- agrees.")

        complete_rounds = [r for r in ok_rounds if r.get("strokes") is not None]
        in_progress_tournament = {
            "game_code": gc,
            "season": 2026,
            "tournament": "OK금융그룹 오픈",
            "status": "IN_PROGRESS",
            "rounds_completed": [{"round": r["round"], "strokes": r["strokes"]} for r in complete_rounds],
            "current_ing_hole": next((r["ing_hole"] for r in ok_rounds if r.get("ing_hole")), None),
            "partial_round_sg": ok_live.get("r3_partial_sg"),
            "note": "이 대회는 아직 진행 중입니다 (최신 캡처 기준 R3 진행 중) -- 커리어 완료 대회 통계에 포함하지 않습니다.",
            "sources": ["tournament_warehouse", "live_snapshot"],
        }
        merged_categories[gc] = {"tournament_warehouse", "live_snapshot"}

    # -------------------------------------------------------------------
    # ACCOUNTABILITY GATE: every discoverable special tournament must be
    # one this module explicitly handled above. A new shape -> loud stop.
    # -------------------------------------------------------------------
    discovered = _discover_special_game_codes()
    handled_special = set(tournaments.keys()) - sg_warehouse_codes
    if in_progress_tournament:
        handled_special.add(in_progress_tournament["game_code"])
    unhandled = discovered - handled_special - sg_warehouse_codes
    if unhandled:
        raise ReconciliationError(
            f"Reconciliation FAILED: discovered real 10097 record(s) for game_code(s) {sorted(unhandled)} "
            "in a recognized source shape, but no loader in this module accounts for them. Add a dedicated "
            "loader (see Hana/KB/OK Open above) before regenerating Player History -- do not patch this "
            "downstream in the report builder."
        )
    missing = _KNOWN_SPECIAL_GAME_CODES - handled_special
    if missing:
        raise ReconciliationError(f"Reconciliation FAILED: known special tournament(s) {sorted(missing)} could not be loaded from any real source.")

    all_round_rows = round_rows + [
        {"game_code": "2026090002", "season": 2026, "round": n, "sg_total": v, "source": "live_snapshot"}
        for n, v in (hana_live["rounds"].items() if hana_live else [])
    ]

    finished = sorted(
        (t for t in tournaments.values() if t.get("status") == "FINISHED"),
        key=lambda t: (t["season"], t["game_code"]),
    )

    report = {
        "total_tournaments": len(tournaments) + (1 if in_progress_tournament else 0),
        "found_in_warehouse": len(sg_warehouse_codes),
        "found_in_reader": 1 if kb else 0,
        "found_in_live": sum(1 for c in ((hana_live and "2026090002") or None, (ok_live["rounds"] and "2026120001") or None) if c),
        "merged": sum(1 for codes in merged_categories.values() if len(codes) > 1),
        "missing": 0,
        "conflicts_detected": len(conflicts),
        "resolved": resolved_log,
        "in_progress_excluded_from_finished_totals": 1 if in_progress_tournament else 0,
        "status": "RECONCILED_OK",
    }

    return {
        "tournaments": tournaments,
        "finished_tournaments": finished,
        "in_progress_tournament": in_progress_tournament,
        "round_rows": all_round_rows,
        "synthetic_sg_warehouse_doc": {
            "records": [
                {
                    "player_id": PLAYER_ID, "game_code": t["game_code"], "season": t["season"],
                    "tournament": t.get("tournament"), "scope": "tournament_cumulative", "identity_state": "RETAINED",
                    "rank": t.get("rank"), "rounds": t.get("rounds_played"),
                    "total": t.get("sg_total"), "off_the_tee": t.get("sg_ott"), "approach": t.get("sg_app"),
                    "around_green": t.get("sg_arg"), "putting": t.get("sg_putt"),
                }
                for t in finished if t.get("sg_total") is not None
            ]
        },
        "report": report,
    }


if __name__ == "__main__":
    result = reconcile()
    r = result["report"]
    print(f"status: {r['status']}")
    print(f"total_tournaments: {r['total_tournaments']}")
    print(f"found_in_warehouse: {r['found_in_warehouse']}")
    print(f"found_in_reader: {r['found_in_reader']}")
    print(f"found_in_live: {r['found_in_live']}")
    print(f"merged: {r['merged']}")
    print(f"missing: {r['missing']}")
    print(f"conflicts_detected: {r['conflicts_detected']}")
    print(f"resolved ({len(r['resolved'])}):")
    for line in r["resolved"]:
        print(f"  - {line}")
    print(f"finished_tournaments: {len(result['finished_tournaments'])}")
    print(f"in_progress_tournament: {result['in_progress_tournament']['game_code'] if result['in_progress_tournament'] else None}")
