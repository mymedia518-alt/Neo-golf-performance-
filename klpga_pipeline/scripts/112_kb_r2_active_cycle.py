"""R2 HOUSE: KB 2026090003's canonical R2 production operator.

preflight -> check official R2 -> if unavailable: WAIT, no mutation ->
collect -> validate (klpga.neo_win.r2_active_cycle.decide_r2_cycle,
built on r2_readiness.assess_r2) -> freeze (klpga.neo_win.r2_freeze,
immutable) -> leakage gate (klpga.neo_win.r2_leakage_gate) -> SG
ingestion (klpga.neo_win.r2_sg_gate's precondition, then klpga.neo_win.
r2_sg_pipeline.ingest_r2_sg -- CLASSIFICATION B, see that module's own
docstring for the archaeology) -> forecast (klpga.neo_win.
post_r2_forecast) -> probability validation (klpga.neo_win.
r2_probability_gate) -> R2 website build (the real renderer,
klpga.neo_win.r2_real_page, on PUBLISH_AND_CLOSE; the WAIT-state page,
klpga.neo_win.r2_wait_page, otherwise) -> publication gate
(klpga.neo_win.r2_publication_gate) -> HOME transition eligibility (the
real page, once published, has no STAGE_READINESS_MARKER -- scripts/88's
HOME STATE ROUTER picks it up on its own next rebuild; this script
never rebuilds root HOME itself).

SG GATE SEMANTICS (P0-2 red-team correction, 2026-09-11): the "sg" gate
in the publication report means "SG was handled safely" (frozen-R2
precondition enforced, real endpoint consulted, no fabrication), NOT
"SG data exists". PASS covers BOTH ingest_r2_sg results that can reach
this point -- AVAILABLE (real values) and NOT_AVAILABLE (real, honest
absence; the renderer's own metric-empty/disclosure-note path handles
this) -- because a CORRUPT result is intercepted earlier as its own
HARD_STOP and never reaches gate evaluation. Gating the ENTIRE page
(real scores, real CUT/WD/DQ status, real forecast) on whether KLPGA's
SG endpoint happens to have same-day data would hold back genuinely
available, non-SG information for no honesty benefit -- SG is real
optional enrichment on top of the real page, not a precondition for it.

Safe by default: no --live flag makes ZERO HTTP requests, matching
every other real-collection script in this project (scripts/96's own
module docstring) -- reports SKIP_WAIT and writes only the R2
WAIT-state page (idempotent -- a repeat call is a no-op if that page
is already current).

CLASSIFICATION (user's explicit ask): scripts/101_ok_open_post_r2_
final_forecast.py, scripts/71_ok_open_r2_readiness.py,
scripts/run_beta001_r2_update.py, scripts/deploy_r2_production_
homepage.py, scripts/generate_r2_frozen_forecast.py are LEGACY /
EVENT_SPECIFIC / NOT_PRODUCTION for KB's own canonical R2 path -- this
script (112) is the one canonical entry point for KB 2026090003's R2;
it reuses their proven underlying modules (round_update_r2's
simulation engine, r2_readiness's completeness gate) directly rather
than calling those scripts.

Usage:
    python scripts/112_kb_r2_active_cycle.py                # dry run, no HTTP
    python scripts/112_kb_r2_active_cycle.py --live          # real collection
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402

from klpga.neo_win import r2_leakage_gate, r2_publication_gate, r2_sg_gate  # noqa: E402
from klpga.neo_win.post_r2_forecast import PostR2ForecastError, post_r2_forecast_status, run_post_r2_forecast  # noqa: E402
from klpga.neo_win.r2_active_cycle import decide_r2_cycle  # noqa: E402
from klpga.neo_win.r2_freeze import (  # noqa: E402
    build_r2_frozen_evidence, r2_freeze_exists, verify_r2_freeze_hash, write_r2_freeze_immutable,
)
from klpga.neo_win.r2_house_contract import load_expected_r2_field  # noqa: E402
from klpga.neo_win.r2_probability_gate import ProbabilityGateError, validate_probability_gate  # noqa: E402
from klpga.neo_win.r2_real_page import render_r2_real_page  # noqa: E402
from klpga.neo_win.r2_sg_pipeline import STATUS_AVAILABLE, SgIngestError, ingest_r2_sg  # noqa: E402
from klpga.neo_win.r2_wait_page import render_r2_wait_page  # noqa: E402
from klpga.tournament_context import load_tournament_context  # noqa: E402

# P1 OPERATOR INTEGRATION (red-team continuation, 2026-09-11) --
# INVESTIGATED AND DELIBERATELY KEPT HARDCODED: load_tournament_context()
# with no arg resolves config/active_tournament.json -- confirmed by
# direct test to be scripts/96 (OK Open, "R2_LIVE") lineage's own
# tracked tournament, a COMPLETELY SEPARATE identity system from KB's.
# KB 2026090003 has never been, and is not now, tracked via
# active_tournament.json -- its PRE/R1/R2 pages are built by a
# dedicated, hardcoded-identity pipeline (scripts/109, scripts/111,
# this script) exactly like scripts/109 itself already hardcodes
# GAME_CODE = "2026090003" (see that script). Resolving _CONTEXT
# generically here was TRIED and reverted after it proved actively
# wrong: with OK Open as the real active tournament, a generic
# _CONTEXT silently made this script evaluate OK Open's R2 state while
# still claiming (via this script's own docstring/filename) to be
# KB's operator -- exactly the silent-wrong-tournament failure mode
# P1 exists to prevent, not a fix for it. The hardcoded literal is the
# CORRECT, deliberate choice for this script's actual scope.
GAME_CODE = "2026090003"
_CONTEXT = load_tournament_context(GAME_CODE)
CONTENT = ROOT / "content" / "website_v2"
R1_EVIDENCE_PATH = CONTENT / f"NEO_KB_{GAME_CODE}_R1_OFFICIAL_RESULT_EVIDENCE_V1.json"
PRE_FREEZE_PATH = _CONTEXT.artifact_path("pre_public_master")
R1_FREEZE_PATH = CONTENT / f"{GAME_CODE}_R1_5PROB_FROZEN_V1.json"
PRE_PERFORMANCE_SNAPSHOT_PATH = _CONTEXT.artifact_path("pre_performance_snapshot")
SPONSOR_AUDIT_PATH = CONTENT / f"KB_{GAME_CODE}_SPONSOR_INTEGRITY_AUDIT_V2.json"
R2_ROUTE_PATH = REPO_ROOT / "docs" / _CONTEXT.url_base.strip("/") / "r2" / "index.html"


def _load_sponsor_by_id() -> dict:
    """Same verified-official sponsor source script 109 already uses
    for R1 -- never a second, independently-sourced sponsor mapping.
    Missing file -> empty dict (every row's sponsor slot renders empty,
    never guessed) rather than a hard failure -- sponsor is OPTIONAL
    display enrichment, not a publication precondition."""
    if not SPONSOR_AUDIT_PATH.is_file():
        return {}
    audit = json.loads(SPONSOR_AUDIT_PATH.read_text(encoding="utf-8"))
    return {r["player_id"]: r["sponsor"] for r in audit.get("newly_recovered_sponsors", [])}


def _collect_live_r2() -> tuple[list[dict], bool, str | None]:
    """Real HTTP collection for R2, mirroring scripts/96's
    _collect_live() error-handling convention exactly: a network
    failure is an ordinary WAIT (returned via `error`, never raised),
    a parser/programming defect is a HARD_STOP."""
    try:
        from klpga.collectors.leaderboard import fetch_round_leaderboard
        from klpga.http_client import PoliteHttpClient
        from klpga.parsers.round_progress import resolve_completed_holes

        client = PoliteHttpClient(cache_dir=ROOT / "data" / "raw_cache" / "kb_r2_active")
        rows = fetch_round_leaderboard(client, GAME_CODE, 2, use_cache=False)
        row_dicts = [
            {
                "player_id": r.player_code,
                "player_name": r.player_name,
                "status": r.status or "ACTIVE",
                "holes_completed": str(resolve_completed_holes(r.holes_completed, None).completed),
                "r1_score_to_par": None,
                "r2_score_to_par": r.today_under_par if r.today_under_par is not None else r.total_under_par,
            }
            for r in rows
        ]
        return row_dicts, True, None
    except requests.exceptions.RequestException as exc:
        return [], False, f"WAIT:{type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001 -- parser/programming defects are hard stops
        return [], False, f"HARD_STOP:{type(exc).__name__}: {exc}"


def _write_wait_page() -> bool:
    """Idempotent: only writes if the WAIT page is missing or stale.
    Returns True if a write happened."""
    html = render_r2_wait_page(tournament_name=_CONTEXT.tournament_name, game_code=GAME_CODE)
    if R2_ROUTE_PATH.is_file() and R2_ROUTE_PATH.read_text(encoding="utf-8") == html:
        return False
    R2_ROUTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    R2_ROUTE_PATH.write_text(html, encoding="utf-8", newline="\n")
    return True


def run_cycle(*, live: bool, build_id: str, seed: int = 20260911) -> dict:
    freeze_exists = r2_freeze_exists(_CONTEXT)

    if not R1_EVIDENCE_PATH.is_file():
        return _summary("HARD_STOP", "R1 official evidence artifact missing -- cannot derive expected R2 field", freeze_exists)
    expected = load_expected_r2_field(R1_EVIDENCE_PATH)

    if not live:
        wrote = _write_wait_page()
        return _summary("SKIP_WAIT", f"dry run (no --live) -- WAIT page {'written' if wrote else 'already current'}", freeze_exists)

    rows, official_page_available, error = _collect_live_r2()
    if error and error.startswith("HARD_STOP"):
        return _summary("HARD_STOP", error, freeze_exists)

    decision = decide_r2_cycle(
        rows, sorted(expected.player_ids),
        official_page_available=official_page_available,
        cut_known=False,  # never inferred from unconfirmed live rank-text CUT/WD/DQ -- see leaderboard_parser.py
        freeze_exists=freeze_exists,
    )

    if decision.action in ("SKIP_WAIT", "HARD_STOP"):
        if decision.action == "SKIP_WAIT":
            _write_wait_page()
        return _summary(decision.action, decision.reason, freeze_exists)

    # PUBLISH_AND_CLOSE: freeze -> leakage -> forecast -> probability -> website -> publication gate
    return _publish_and_close(rows, expected, decision, build_id, seed)


def _publish_and_close(rows, expected, decision, build_id: str, seed: int) -> dict:
    r2_leakage_gate.assert_stage_allowed("r2", context="R2 freeze construction")

    status_counts = {"ACTIVE": 0, "CUT": 0, "WD": 0, "DQ": 0, "DNS": 0}
    cut_wd_dq_evidence = []
    for row in rows:
        status = row.get("status", "ACTIVE")
        status_counts[status] = status_counts.get(status, 0) + 1
        if status != "ACTIVE":
            cut_wd_dq_evidence.append({"player_id": row["player_id"], "status": status, "evidence": "official R2 leaderboard row"})

    raw_response = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")
    evidence = build_r2_frozen_evidence(
        context=_CONTEXT, official_source_identity="klpga.co.kr roundLeaderboard",
        official_source_url=None, collection_timestamp=decision.retrieved_at,
        raw_official_response=raw_response, records=rows, expected_field_count=len(expected.player_ids),
        status_counts=status_counts, cut_wd_dq_evidence=cut_wd_dq_evidence,
        pre_freeze_path=PRE_FREEZE_PATH, r1_freeze_path=R1_FREEZE_PATH, repo_root=REPO_ROOT, build_id=build_id,
    )
    write_r2_freeze_immutable(_CONTEXT, evidence)

    frozen_players = [{"player_id": r["player_id"], "player_name": r["player_name"]} for r in rows]
    try:
        r2_sg_gate.require_verified_frozen_r2_for_sg(_CONTEXT)
    except r2_sg_gate.SgPreconditionError as exc:
        return _summary("HARD_STOP", f"SG precondition failed: {exc}", True)

    from klpga.http_client import PoliteHttpClient
    sg_client = PoliteHttpClient(cache_dir=ROOT / "data" / "raw_cache" / "kb_r2_sg")
    try:
        sg_result = ingest_r2_sg(sg_client, GAME_CODE, frozen_players)
    except SgIngestError as exc:
        # real official data failing its own internal reconciliation is
        # a data-integrity HARD_STOP, never silently downgraded to WAIT.
        return _summary("HARD_STOP", f"SG ingestion corrupt: {exc}", True)
    # PASS covers AVAILABLE and NOT_AVAILABLE alike -- see this script's
    # own module docstring, "SG GATE SEMANTICS" -- CORRUPT already
    # returned above and never reaches this point.
    sg_gate = (r2_publication_gate.PASS, f"SG ingestion completed safely: status={sg_result['status']}")

    pre_performance = json.loads(PRE_PERFORMANCE_SNAPSHOT_PATH.read_text(encoding="utf-8")) if PRE_PERFORMANCE_SNAPSHOT_PATH.is_file() else {"profiles": []}
    try:
        forecast = run_post_r2_forecast(_CONTEXT, pre_performance_snapshot=pre_performance, repo_root=REPO_ROOT, build_id=build_id, seed=seed)
        forecast_gate = (r2_publication_gate.PASS, "post-R2 forecast written")
    except PostR2ForecastError as exc:
        return _summary("HARD_STOP", f"forecast precondition failed: {exc}", True)

    active_ids = {r["player_id"] for r in rows if r.get("status", "ACTIVE") == "ACTIVE"}
    try:
        validate_probability_gate(forecast, expected_game_code=GAME_CODE, expected_active_player_ids=active_ids)
        probability_gate = (r2_publication_gate.PASS, "probability gate passed")
    except ProbabilityGateError as exc:
        return _summary("HARD_STOP", f"probability gate failed: {exc}", True)

    # website build: the real renderer, fed ONLY by the three already-
    # gated canonical inputs above (frozen R2 records, the just-written
    # forecast, sg_result) -- never a second/live re-read. HOME STATE
    # ROUTER will pick this page up (it carries no STAGE_READINESS_
    # MARKER) on scripts/88's next rebuild; this script itself never
    # rebuilds root HOME.
    real_html = render_r2_real_page(
        tournament_name=_CONTEXT.tournament_name, game_code=GAME_CODE,
        date_range=f"{_CONTEXT.start_date} — {_CONTEXT.end_date}",
        r2_freeze={"records": rows}, forecast=forecast, sg_ingest=sg_result,
        sponsor_by_id=_load_sponsor_by_id(),
    )
    R2_ROUTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    R2_ROUTE_PATH.write_text(real_html, encoding="utf-8", newline="\n")

    report = r2_publication_gate.evaluate_r2_publication_gate(GAME_CODE, {
        "official_source_verified": (r2_publication_gate.PASS, "real klpga.co.kr collection, official page available"),
        "completeness": (r2_publication_gate.PASS, decision.reason),
        "duplicate": (r2_publication_gate.PASS, "no duplicate identity (r2_readiness.assess_r2)"),
        "status": (r2_publication_gate.PASS, "every entrant accounted for by evidence-based status"),
        "freeze": (r2_publication_gate.PASS, "immutable R2 freeze written and hash-verified"),
        "pre_binding": (r2_publication_gate.PASS, "PRE+R1 freeze hashes bound into R2 freeze"),
        "future_leakage": (r2_publication_gate.PASS, "no R3/R4/FINAL/post-event input referenced"),
        "sg": sg_gate,
        "forecast": forecast_gate,
        "probability": probability_gate,
        "website_build": (r2_publication_gate.PASS, "real R2 page rendered and written (klpga.neo_win.r2_real_page)"),
    })

    return {
        "action": "PUBLISH_AND_CLOSE", "reason": decision.reason, "retrieved_at": decision.retrieved_at,
        "R2_HOUSE_READY": True, "REAL_R2": "CONFIRMED", "R2_SNAPSHOT": "CREATED",
        "POST_R2_FORECAST": post_r2_forecast_status(_CONTEXT), "R2_PUBLICATION_READY": report.publication_allowed,
        "SG_STATUS": sg_result["status"],
        "publication_gate": [(g.name, g.state, g.reason) for g in report.gates],
    }


def _summary(action: str, reason: str, freeze_exists: bool) -> dict:
    return {
        "action": action, "reason": reason, "R2_HOUSE_READY": True, "REAL_R2": "WAIT",
        "R2_SNAPSHOT": "CREATED" if freeze_exists else "NOT_CREATED",
        "POST_R2_FORECAST": post_r2_forecast_status(_CONTEXT), "R2_PUBLICATION_READY": False,
    }


def main() -> int:
    import datetime

    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    build_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result = run_cycle(live=args.live, build_id=build_id)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["action"] not in ("HARD_STOP",) else 1


if __name__ == "__main__":
    raise SystemExit(main())
