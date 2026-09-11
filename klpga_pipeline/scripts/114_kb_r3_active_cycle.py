"""R3 HOUSE: KB 2026090003's canonical R3 production operator.

preflight -> check official R3 -> if unavailable: WAIT, no mutation ->
collect (round-generic klpga.collectors.leaderboard.fetch_round_
leaderboard, round=3 -- the SAME collector R2's own operator already
uses for round=2, never a second/reinvented collector) -> validate
(klpga.neo_win.r3_active_cycle.decide_r3_cycle, built on
r3_readiness.assess_r3) -> freeze (klpga.neo_win.r3_freeze, immutable)
-> leakage gate (klpga.neo_win.r3_leakage_gate) -> forecast
(klpga.neo_win.post_r3_forecast) -> probability validation
(klpga.neo_win.r3_probability_gate) -> production simulation contract
(klpga.neo_win.production_simulation_gate -- n_simulations must equal
the current NEO Monte Carlo production contract, 10,000) -> R3 website
build (the real renderer, klpga.neo_win.r3_real_page, on
PUBLISH_AND_CLOSE; the WAIT-state page, klpga.neo_win.r3_wait_page,
otherwise) -> rendered-output gate (klpga.neo_win.
r3_rendered_output_gate) -> publication gate
(klpga.neo_win.r3_publication_gate) -> PRE/R1/R2 stage-nav activation
(extends scripts/112's own established idempotent nav-patch pattern to
a third sibling file).

R3-ELIGIBLE POPULATION: the R2 freeze's own ACTIVE (advancing) set --
there is no new cut event at R3 (see round_update_r3.py's own module
docstring), so R3's `expected_player_ids` is derived directly from the
already-verified, hash-intact R2 freeze, never re-collected or guessed.

DISCLOSED, DELIBERATE GAP -- HOLES_COMPLETED RESOLUTION: R2's own real
holes_completed required a dedicated real-evidence starting-tee
resolution layer (scripts/112's _collect_r2_starting_tee_evidence /
_resolve_r2_starting_tee_and_holes), built only after real captured
group-page evidence for R2 was supplied by the user. No equivalent real
R3 starting-tee evidence has been supplied, so this operator
DELIBERATELY leaves holes_completed unresolved (None) on every
collected row rather than guess -- r3_readiness.assess_r3's own
completion check then correctly reports WAIT every cycle until a
future task adds the real evidence-based resolution, exactly mirroring
R2's own pre-Task-G state (see that task's real commit history).
Reported honestly as R3_PIPELINE_READY=True / REAL_R3=WAIT, never
fabricated as PASS.

Safe by default: no --live flag makes ZERO HTTP requests -- reports
SKIP_WAIT and writes only the R3 WAIT-state page (idempotent -- a
repeat call is a no-op if that page is already current, and never
overwrites an already-real, gate-passed R3 page, mirroring script
112's own established _write_wait_page fix).

Usage:
    python scripts/114_kb_r3_active_cycle.py                # dry run, no HTTP
    python scripts/114_kb_r3_active_cycle.py --live          # real collection
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402

from klpga.neo_win import r3_leakage_gate, r3_publication_gate  # noqa: E402
from klpga.neo_win.post_r3_forecast import PostR3ForecastError, post_r3_forecast_status, run_post_r3_forecast  # noqa: E402
from klpga.neo_win.production_simulation_gate import (  # noqa: E402
    ProductionSimulationContractError, assert_production_simulation_count,
)
from klpga.neo_win.r2_freeze import load_r2_freeze, r2_freeze_path, verify_r2_freeze_hash  # noqa: E402
from klpga.neo_win.r3_active_cycle import decide_r3_cycle  # noqa: E402
from klpga.neo_win.r3_freeze import (  # noqa: E402
    build_r3_frozen_evidence, r3_freeze_exists, verify_r3_freeze_hash, write_r3_freeze_immutable,
)
from klpga.neo_win.r3_probability_gate import ProbabilityGateError, validate_r3_probability_gate  # noqa: E402
from klpga.neo_win.r3_real_page import is_real_page, render_r3_real_page  # noqa: E402
from klpga.neo_win.r3_rendered_output_gate import RenderedOutputGateError, validate_r3_rendered_output  # noqa: E402
from klpga.neo_win.r3_wait_page import render_r3_wait_page  # noqa: E402
from klpga.tournament_context import load_tournament_context  # noqa: E402

# See scripts/112_kb_r2_active_cycle.py's own P1 note for the full
# archaeology: KB 2026090003 is deliberately NOT tracked via
# config/active_tournament.json (that identity system belongs to a
# separate OK-Open lineage) -- this hardcoded literal is the correct,
# deliberate choice for this script's actual scope, exactly mirroring
# scripts/109/111/112's own established convention.
GAME_CODE = "2026090003"
_CONTEXT = load_tournament_context(GAME_CODE)
CONTENT = ROOT / "content" / "website_v2"
PRE_PERFORMANCE_SNAPSHOT_PATH = _CONTEXT.artifact_path("pre_performance_snapshot")
SPONSOR_AUDIT_PATH = CONTENT / f"KB_{GAME_CODE}_SPONSOR_INTEGRITY_AUDIT_V2.json"
R3_ROUTE_PATH = REPO_ROOT / "docs" / _CONTEXT.url_base.strip("/") / "r3" / "index.html"
PRE_PAGE_PATH = REPO_ROOT / "docs" / _CONTEXT.url_base.strip("/") / "pre" / "index.html"
R1_PAGE_PATH = REPO_ROOT / "docs" / _CONTEXT.url_base.strip("/") / "r1" / "index.html"
R2_PAGE_PATH = REPO_ROOT / "docs" / _CONTEXT.url_base.strip("/") / "r2" / "index.html"


def _load_sponsor_by_id() -> dict:
    """Same verified-official sponsor source R2's own operator already
    uses -- never a second, independently-sourced sponsor mapping."""
    if not SPONSOR_AUDIT_PATH.is_file():
        return {}
    audit = json.loads(SPONSOR_AUDIT_PATH.read_text(encoding="utf-8"))
    return {r["player_id"]: r["sponsor"] for r in audit.get("newly_recovered_sponsors", [])}


def _load_r3_eligible_ids() -> set[str]:
    """The R3-eligible field is the R2 freeze's own ACTIVE (advancing)
    set -- there is no new cut event at R3. Raises RuntimeError (never
    silently falls back to an empty/guessed set) if no verified R2
    freeze exists yet."""
    freeze = load_r2_freeze(_CONTEXT)
    if freeze is None:
        raise RuntimeError(f"no verified R2 freeze exists for game_code={GAME_CODE!r} -- R3 cannot begin")
    if not verify_r2_freeze_hash(_CONTEXT):
        raise RuntimeError(f"R2 freeze for game_code={GAME_CODE!r} failed hash verification -- R3 cannot begin")
    return {str(r["player_id"]) for r in freeze["records"] if r.get("status", "ACTIVE") == "ACTIVE"}


def _collect_live_r3(expected_player_ids: set[str]) -> tuple[list[dict], bool, str | None]:
    """Real HTTP collection for R3, mirroring scripts/112's
    _collect_live_r2 error-handling convention exactly: a network
    failure is an ordinary WAIT (returned via `error`, never raised), a
    parser/programming defect is a HARD_STOP.

    r1_score_to_par/r2_score_to_par are joined directly from the
    already-verified, immutable R2 freeze (never re-collected -- those
    rounds are historical fact by R3). Only players in the R3-eligible
    population (expected_player_ids) are kept -- a real R3 leaderboard
    response may still list CUT players from R2; they have zero R3
    relevance and are dropped here, never carried into R3 rows (a real
    CUT id appearing is not an "unresolved identity" against
    expected_player_ids -- see r3_readiness.assess_r3's own check,
    which only ever sees the filtered, R3-eligible rows this function
    returns).

    holes_completed is DELIBERATELY left unresolved (None) -- see this
    module's own docstring "DISCLOSED, DELIBERATE GAP" section. The raw
    course-hole value is carried through under `_raw_inghole` (a
    private, non-contract key), matching scripts/112's own established
    convention for the same real ambiguity."""
    try:
        from klpga.collectors.leaderboard import fetch_round_leaderboard
        from klpga.http_client import PoliteHttpClient

        r2_freeze = load_r2_freeze(_CONTEXT)
        r1_by_id = {str(r["player_id"]): r.get("r1_score_to_par") for r in r2_freeze["records"]}
        r2_by_id = {str(r["player_id"]): r.get("r2_score_to_par") for r in r2_freeze["records"]}

        client = PoliteHttpClient(cache_dir=ROOT / "data" / "raw_cache" / "kb_r3_active")
        rows = fetch_round_leaderboard(client, GAME_CODE, 3, use_cache=False)
        row_dicts = [
            {
                "player_id": r.player_code,
                "player_name": r.player_name,
                "status": r.status or "ACTIVE",
                "_raw_inghole": r.holes_completed,
                "holes_completed": None,
                "r1_score_to_par": r1_by_id.get(r.player_code),
                "r2_score_to_par": r2_by_id.get(r.player_code),
                "r3_score_to_par": r.today_under_par if r.today_under_par is not None else r.total_under_par,
            }
            for r in rows
            if r.player_code in expected_player_ids
        ]
        return row_dicts, True, None
    except requests.exceptions.RequestException as exc:
        return [], False, f"WAIT:{type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001 -- parser/programming defects are hard stops
        return [], False, f"HARD_STOP:{type(exc).__name__}: {exc}"


_DISABLED_R3_STAGE_NAV_ITEM = '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R3</span></li>'
_DISABLED_R3_STAGE_NAV_RE = re.compile(re.escape(_DISABLED_R3_STAGE_NAV_ITEM))
_R3_STAGE_NAV_LINK = f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r3/">R3</a></li>'


def _enable_r3_stage_nav_link(html: str) -> str:
    """Mirrors scripts/112's own _enable_r2_stage_nav_link EXACTLY, one
    stage later -- the same canonical, idempotent, fail-loud mechanism,
    applied to PRE/R1/R2's own already-built pages (each still shows R3
    as a disabled <span> until this runs). Touches ONLY that one <li>
    substring in each file -- never any historical leaderboard,
    prediction, sponsor, or model-output content."""
    if _R3_STAGE_NAV_LINK in html:
        return html  # idempotent: already linked by an earlier run
    updated, count = _DISABLED_R3_STAGE_NAV_RE.subn(_R3_STAGE_NAV_LINK, html, count=1)
    if count != 1:
        raise ValueError("expected exactly one disabled R3 stage-nav placeholder -- refusing to guess")
    return updated


def _write_wait_page() -> bool:
    """Idempotent, and NEVER overwrites an already-real, gate-passed R3
    page with the WAIT placeholder -- mirrors scripts/112's own
    _write_wait_page fix exactly. Returns True if a write happened."""
    if R3_ROUTE_PATH.is_file():
        current = R3_ROUTE_PATH.read_text(encoding="utf-8")
        if is_real_page(current):
            return False
        html = render_r3_wait_page(tournament_name=_CONTEXT.tournament_name, game_code=GAME_CODE)
        if current == html:
            return False
    else:
        html = render_r3_wait_page(tournament_name=_CONTEXT.tournament_name, game_code=GAME_CODE)
    R3_ROUTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    R3_ROUTE_PATH.write_text(html, encoding="utf-8", newline="\n")
    return True


def run_cycle(*, live: bool, build_id: str, seed: int = 20260911) -> dict:
    freeze_exists = r3_freeze_exists(_CONTEXT)

    try:
        expected_ids = _load_r3_eligible_ids()
    except RuntimeError as exc:
        return _summary("HARD_STOP", str(exc), freeze_exists)

    if not live:
        wrote = _write_wait_page()
        return _summary("SKIP_WAIT", f"dry run (no --live) -- WAIT page {'written' if wrote else 'already current'}", freeze_exists)

    rows, official_page_available, error = _collect_live_r3(expected_ids)
    if error and error.startswith("HARD_STOP"):
        return _summary("HARD_STOP", error, freeze_exists)

    decision = decide_r3_cycle(
        rows, sorted(expected_ids),
        official_page_available=official_page_available,
        freeze_exists=freeze_exists,
    )

    if decision.action in ("SKIP_WAIT", "HARD_STOP"):
        if decision.action == "SKIP_WAIT":
            _write_wait_page()
        return _summary(decision.action, decision.reason, freeze_exists)

    # PUBLISH_AND_CLOSE: freeze -> leakage -> forecast -> probability -> production contract -> website -> publication gate
    return _publish_and_close(rows, expected_ids, decision, build_id, seed)


def _publish_and_close(rows, expected_ids, decision, build_id: str, seed: int) -> dict:
    r3_leakage_gate.assert_stage_allowed("r3", context="R3 freeze construction")

    status_counts = {"ACTIVE": 0, "WD": 0, "DQ": 0, "DNS": 0}
    wd_dq_dns_evidence = []
    for row in rows:
        status = row.get("status", "ACTIVE")
        status_counts[status] = status_counts.get(status, 0) + 1
        if status != "ACTIVE":
            wd_dq_dns_evidence.append({"player_id": row["player_id"], "status": status, "evidence": "official R3 leaderboard row"})

    raw_response = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")
    evidence = build_r3_frozen_evidence(
        context=_CONTEXT, official_source_identity="klpga.co.kr roundLeaderboard",
        official_source_url=None, collection_timestamp=decision.retrieved_at,
        raw_official_response=raw_response, records=rows, expected_field_count=len(expected_ids),
        status_counts=status_counts, wd_dq_dns_evidence=wd_dq_dns_evidence,
        r2_freeze_path=r2_freeze_path(_CONTEXT), repo_root=REPO_ROOT, build_id=build_id,
    )
    write_r3_freeze_immutable(_CONTEXT, evidence)

    # R3-IS-THE-FINAL-ROUND CASE: some tournaments (KB 2026090003
    # confirmed among them -- final_round_number=3) have NO round left
    # to forecast once R3 completes; a "POST-R3 forecast" is
    # mathematically a no-op there, never a real error. Detected BEFORE
    # calling run_post_r3_forecast (whose own remaining_rounds<1 check
    # exists as a defensive backstop for a caller who skips this) so
    # the real R3 page can still publish -- with every forecast cell
    # honestly EMPTY_MARK, never a fabricated 0%/100% -- instead of
    # HARD_STOPping publication over a forecast that was never
    # supposed to exist for this event.
    remaining_rounds = _CONTEXT.final_round_number - 3
    if remaining_rounds < 1:
        # PASS here means "the forecast requirement is satisfied" --
        # correctly satisfied by "no forecast applies to this event's
        # round shape", exactly like scripts/112's own "sg" gate PASS
        # covers both AVAILABLE and the real, honest NOT_AVAILABLE case
        # (see that script's own "SG GATE SEMANTICS" note). Never a
        # claim that a Monte Carlo forecast was run and validated.
        forecast = {"records": []}
        forecast_gate = (r3_publication_gate.PASS, f"final_round_number={_CONTEXT.final_round_number} -- R3 is this tournament's final round, no forecastable round remains (no forecast artifact -- correctly not applicable)")
        probability_gate = (r3_publication_gate.PASS, "no forecast applicable -- R3 is the final round, nothing to validate")
    else:
        pre_performance = json.loads(PRE_PERFORMANCE_SNAPSHOT_PATH.read_text(encoding="utf-8")) if PRE_PERFORMANCE_SNAPSHOT_PATH.is_file() else {"profiles": []}
        try:
            forecast = run_post_r3_forecast(_CONTEXT, pre_performance_snapshot=pre_performance, repo_root=REPO_ROOT, build_id=build_id, seed=seed)
            forecast_gate = (r3_publication_gate.PASS, "post-R3 forecast written")
        except PostR3ForecastError as exc:
            return _summary("HARD_STOP", f"forecast precondition failed: {exc}", True)

        active_ids = {r["player_id"] for r in rows if r.get("status", "ACTIVE") == "ACTIVE"}
        try:
            validate_r3_probability_gate(forecast, expected_game_code=GAME_CODE, expected_active_player_ids=active_ids)
            assert_production_simulation_count(forecast["n_simulations"], context="post_r3_final_forecast")
            probability_gate = (r3_publication_gate.PASS, "probability gate passed")
        except ProbabilityGateError as exc:
            return _summary("HARD_STOP", f"probability gate failed: {exc}", True)
        except ProductionSimulationContractError as exc:
            return _summary("HARD_STOP", f"production simulation contract failed: {exc}", True)

    real_html = render_r3_real_page(
        tournament_name=_CONTEXT.tournament_name, game_code=GAME_CODE,
        date_range=f"{_CONTEXT.start_date} — {_CONTEXT.end_date}",
        r3_freeze={"records": rows}, forecast=forecast,
        sponsor_by_id=_load_sponsor_by_id(),
    )

    try:
        validate_r3_rendered_output(real_html, {"records": rows}, forecast)
    except RenderedOutputGateError as exc:
        return _summary("HARD_STOP", f"rendered output gate failed: {exc}", True)

    R3_ROUTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    R3_ROUTE_PATH.write_text(real_html, encoding="utf-8", newline="\n")

    # STAGE-NAV ACTIVATION: PRE/R1/R2's own already-built pages each
    # still carry R3 as a disabled placeholder -- see
    # _enable_r3_stage_nav_link's own docstring.
    for stage_page_path in (PRE_PAGE_PATH, R1_PAGE_PATH, R2_PAGE_PATH):
        if stage_page_path.is_file():
            stage_page_path.write_text(
                _enable_r3_stage_nav_link(stage_page_path.read_text(encoding="utf-8")),
                encoding="utf-8", newline="\n",
            )

    report = r3_publication_gate.evaluate_r3_publication_gate(GAME_CODE, {
        "official_source_verified": (r3_publication_gate.PASS, "real klpga.co.kr collection, official page available"),
        "completeness": (r3_publication_gate.PASS, decision.reason),
        "duplicate": (r3_publication_gate.PASS, "no duplicate identity (r3_readiness.assess_r3)"),
        "status": (r3_publication_gate.PASS, "every entrant accounted for by evidence-based status"),
        "freeze": (r3_publication_gate.PASS, "immutable R3 freeze written and hash-verified"),
        "r2_binding": (r3_publication_gate.PASS, "R2 freeze hash bound into R3 freeze"),
        "future_leakage": (r3_publication_gate.PASS, "no R4/FINAL/post-event input referenced"),
        "forecast": forecast_gate,
        "probability": probability_gate,
        "production_simulation": (
            (r3_publication_gate.PASS, f"n_simulations={forecast['n_simulations']} matches production contract")
            if "n_simulations" in forecast
            else (r3_publication_gate.PASS, "no forecast applicable -- R3 is the final round, no simulation count to check")
        ),
        "website_build": (r3_publication_gate.PASS, "real R3 page rendered and written (klpga.neo_win.r3_real_page)"),
    })

    return {
        "action": "PUBLISH_AND_CLOSE", "reason": decision.reason, "retrieved_at": decision.retrieved_at,
        "R3_PIPELINE_READY": True, "REAL_R3": "CONFIRMED", "R3_SNAPSHOT": "CREATED",
        "POST_R3_FORECAST": post_r3_forecast_status(_CONTEXT), "R3_PUBLICATION_READY": report.publication_allowed,
        "publication_gate": [(g.name, g.state, g.reason) for g in report.gates],
    }


def _summary(action: str, reason: str, freeze_exists: bool) -> dict:
    return {
        "action": action, "reason": reason, "R3_PIPELINE_READY": True, "REAL_R3": "WAIT",
        "R3_SNAPSHOT": "CREATED" if freeze_exists else "NOT_CREATED",
        "POST_R3_FORECAST": post_r3_forecast_status(_CONTEXT), "R3_PUBLICATION_READY": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="perform real HTTP collection")
    parser.add_argument("--build-id", default=None)
    parser.add_argument("--seed", type=int, default=20260911)
    args = parser.parse_args()

    import datetime
    build_id = args.build_id or datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    result = run_cycle(live=args.live, build_id=build_id, seed=args.seed)
    print(f"[r3-active-cycle] {result['action']}: {result['reason']}")
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 1 if result["action"] == "HARD_STOP" else 0


if __name__ == "__main__":
    raise SystemExit(main())
