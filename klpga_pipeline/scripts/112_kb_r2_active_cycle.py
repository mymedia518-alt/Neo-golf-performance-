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
from klpga.neo_win.r2_real_page import is_real_page, render_r2_real_page  # noqa: E402
from klpga.neo_win.r2_rendered_output_gate import RenderedOutputGateError, validate_r2_rendered_output  # noqa: E402
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
    a parser/programming defect is a HARD_STOP.

    BUGFIX (fix/kb-r2-official-cut-gate-20260911, starting-tee pass):
    this no longer resolves holes_completed itself. KLPGA's real
    data-inghole is the LAST ACTUAL COURSE HOLE played (klpga.parsers.
    leaderboard_parser's own confirmed contract), not a completed-hole
    count -- correct only for a real 1-tee (OUT) start. Calling
    resolve_completed_holes(raw, None) here (the previous behavior)
    silently assumed every player started at tee 1, which is unsafe:
    for a real 10-tee starter it can fabricate a false-complete 18 from
    a partial round (see _resolve_r2_starting_tee_and_holes's own
    docstring, test case C). The raw course-hole value is now carried
    through under `_raw_inghole` -- a private, non-contract key never
    read by assess_r2/build_r2_frozen_evidence/the renderers -- and
    only `_resolve_r2_starting_tee_and_holes` (called from run_cycle
    with the real, separately-fetched official starting-tee evidence)
    is allowed to turn it into the real `holes_completed` field."""
    try:
        from klpga.collectors.leaderboard import fetch_round_leaderboard
        from klpga.http_client import PoliteHttpClient

        client = PoliteHttpClient(cache_dir=ROOT / "data" / "raw_cache" / "kb_r2_active")
        rows = fetch_round_leaderboard(client, GAME_CODE, 2, use_cache=False)
        row_dicts = [
            {
                "player_id": r.player_code,
                "player_name": r.player_name,
                "status": r.status or "ACTIVE",
                "_raw_inghole": r.holes_completed,
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


_UNRESOLVED_STARTING_TEE = "UNRESOLVED_STARTING_TEE"


def _build_starting_tee_map(groupings) -> dict:
    """Pure: turns a list of klpga.parsers.group_page_parser.GroupingRow
    (real parsed rows from the official group/tee-time page's Round 2
    grouping table) into {"tee_by_player": {player_code: starting_tee},
    "ambiguous_player_ids": frozenset({player_code, ...})}. Factored out
    of _collect_r2_starting_tee_evidence so this ambiguity rule is
    directly unit-testable with synthetic GroupingRow objects, without
    any real HTTP fetch.

    A player_code that appears more than once in `groupings` with two
    DIFFERING starting_tee values is placed in ambiguous_player_ids and
    excluded from tee_by_player entirely -- a genuine identity/data
    conflict, never silently resolved by picking either value (mirrors
    _reconcile_cut_evidence's own conflict discipline elsewhere in this
    script). A player_code repeated with the SAME starting_tee value
    (e.g. present on more than one tee-time row by a page quirk) is not
    a conflict."""
    tee_by_player: dict[str, str] = {}
    ambiguous: set[str] = set()
    for g in groupings:
        if g.starting_tee is None:
            continue
        pid = g.player_code
        if pid in ambiguous:
            continue
        if pid in tee_by_player and tee_by_player[pid] != g.starting_tee:
            ambiguous.add(pid)
            del tee_by_player[pid]
            continue
        tee_by_player[pid] = g.starting_tee
    return {"tee_by_player": tee_by_player, "ambiguous_player_ids": frozenset(ambiguous)}


def _collect_r2_starting_tee_evidence() -> tuple[dict | None, str | None]:
    """Best-effort fetch + parse of the official group/tee-time page's
    own Round 2 grouping (klpga.collectors.group_page.
    fetch_group_page_html + klpga.parsers.group_page_parser.
    parse_round_grouping(round_number=2)) -- the SAME real, confirmed
    source scripts/96's own _fetch_round1_starting_tees already uses
    for R1, joined here by the one stable official identity the group
    page itself carries directly: player_code (a[href*="playerCode="],
    see that parser's own module docstring) -- never player_name alone.
    This is a STRONGER identity than _reconcile_cut_evidence's
    name-only join above, which is only a name join because that is
    genuinely the sole identity the scoreRecord page carries; the group
    page carries player_code directly, so that identity is used here.

    Returns (evidence, error). evidence = {"tee_by_player":
    {player_code: starting_tee, ...}, "ambiguous_player_ids":
    frozenset({player_code, ...})}. A player_code is placed in
    ambiguous_player_ids (and excluded from tee_by_player) if the real
    grouping table lists it more than once with two DIFFERING
    starting_tee values -- a genuine data conflict, never silently
    resolved by picking either (mirrors _reconcile_cut_evidence's own
    conflict discipline).

    Mirrors _collect_cut_boundary_evidence's own error convention
    exactly: a network failure, or Round 2's grouping not being
    published yet (ValueError from parse_round_grouping), is an
    ordinary, non-fatal WAIT -- evidence is simply None, and callers
    (_resolve_r2_starting_tee_and_holes) must never silently assume tee
    1 for a player with no real evidence; they leave that player's
    holes_completed as the explicit _UNRESOLVED_STARTING_TEE sentinel,
    which naturally routes through assess_r2's own existing, unmodified
    completion check to WAIT -- exactly the same "missing secondary
    evidence degrades to the primary gate's own WAIT" pattern already
    used for cut-boundary evidence in this script. A parser/programming
    defect is a HARD_STOP. Never raises."""
    try:
        from klpga.collectors.group_page import fetch_group_page_html
        from klpga.http_client import PoliteHttpClient
        from klpga.parsers.group_page_parser import parse_round_grouping

        client = PoliteHttpClient(cache_dir=ROOT / "data" / "raw_cache" / "kb_r2_starting_tee")
        _status, html_text = fetch_group_page_html(client, GAME_CODE)
        groupings = parse_round_grouping(html_text, round_number=2)
        return _build_starting_tee_map(groupings), None
    except requests.exceptions.RequestException as exc:
        return None, f"WAIT:{type(exc).__name__}: {exc}"
    except ValueError as exc:
        # Round 2's grouping tab-pane not published yet (or its table
        # missing) -- a real, expected WAIT state, never a programming
        # defect.
        return None, f"WAIT:{exc}"
    except Exception as exc:  # noqa: BLE001 -- parser/programming defects are hard stops
        return None, f"HARD_STOP:{type(exc).__name__}: {exc}"


def _resolve_r2_starting_tee_and_holes(rows: list[dict], tee_evidence: dict | None) -> tuple[list[dict], list[str]]:
    """The ONLY place allowed to turn a row's raw `_raw_inghole` (last
    actual course hole played) into the real `holes_completed`
    (current-round completed-hole count) -- via klpga.parsers.
    round_progress.resolve_completed_holes, unmodified, fed a REAL
    starting_tee looked up from `tee_evidence["tee_by_player"]` by the
    row's own player_id. Never derives starting tee from `_raw_inghole`
    itself, rank, score, row order, OUT/IN score, or player count --
    the only inputs read here are the row's player_id and the
    independently-collected tee_evidence.

    Three cases per row:
      1. Real, unambiguous starting_tee found for this player_id ->
         holes_completed = str(resolve_completed_holes(raw, tee).completed),
         a real, tee-adjusted current-round count.
      2. player_id is in tee_evidence's ambiguous_player_ids (two real
         group-page entries disagreeing on this player's starting tee)
         -> holes_completed = _UNRESOLVED_STARTING_TEE, AND the
         player_id is returned in `conflicts` -- callers MUST HARD_STOP
         on any conflict, exactly like _reconcile_cut_evidence's own
         conflict contract. Never silently guesses which tee is real.
      3. No evidence at all for this player_id (tee_evidence is None,
         evidence collection failed/not-yet-published, or this
         player_id simply isn't in tee_by_player) -> holes_completed =
         _UNRESOLVED_STARTING_TEE, no conflict recorded (absence is not
         itself a conflict). This sentinel never matches assess_r2's
         own "36"/"F"/"FINAL" cumulative-completion check, so an
         ACTIVE/CUT row with unresolved starting tee correctly WAITs --
         it can NEVER be silently treated as complete. WD/DQ/DNS rows
         are unaffected either way, since assess_r2 never checks
         holes_completed for those statuses.

    Returns (resolved_rows, conflicting_player_ids); the private
    `_raw_inghole` key is stripped from every returned row -- it is
    never part of the R2 field contract (klpga.neo_win.
    r2_house_contract) and must never reach the freeze evidence writer
    or any renderer."""
    from klpga.parsers.round_progress import resolve_completed_holes

    tee_by_player = (tee_evidence or {}).get("tee_by_player", {})
    ambiguous_ids = set((tee_evidence or {}).get("ambiguous_player_ids", ()))

    resolved: list[dict] = []
    conflicts: list[str] = []
    for row in rows:
        raw_inghole = row.get("_raw_inghole")
        player_id = str(row.get("player_id"))
        clean_row = {k: v for k, v in row.items() if k != "_raw_inghole"}

        if player_id in ambiguous_ids:
            conflicts.append(player_id)
            clean_row["holes_completed"] = _UNRESOLVED_STARTING_TEE
            resolved.append(clean_row)
            continue

        starting_tee = tee_by_player.get(player_id)
        if starting_tee is None:
            clean_row["holes_completed"] = _UNRESOLVED_STARTING_TEE
            resolved.append(clean_row)
            continue

        clean_row["holes_completed"] = str(resolve_completed_holes(raw_inghole, starting_tee).completed)
        resolved.append(clean_row)
    return resolved, conflicts


def _derive_cut_known(rows: list[dict], *, cut_boundary_published: bool = False) -> bool:
    """BUGFIX (fix/kb-r2-official-cut-gate-20260911): the ONE honest
    signal that the official CUT determination has actually been
    published for this round -- at least one collected row carries the
    official leaderboard parser's own literal status=="CUT" (set only
    when KLPGA's roundLeaderboard response itself has data-rank="CUT"
    on that row, klpga.parsers.leaderboard_parser.parse_rank -- a
    direct, explicit read of the official source's own text, never a
    computation this pipeline performs).

    Deliberately does NOT look at: rank, score, holes_completed, row
    count, which players are missing from `rows` vs. the expected
    field, or any cut-line arithmetic -- none of those are the official
    source stating a real CUT, and inferring from any of them is
    exactly the fabrication this gate exists to prevent (see
    r2_readiness.assess_r2's own "no CUT inferred" reason string, which
    this function's return value feeds directly). A player who is
    simply absent from this round's rows (WD/DQ elsewhere in the
    tournament, or not yet reached in collection) never contributes a
    "CUT" status here, because there is no row for them to read a
    status off of -- absence is not evidence.

    Also NOT a signal: the confirmed data-rank="999" sentinel (parsed
    as status="INCOMPLETE" -- "did not complete this round," which
    could mean anything from "still playing" to WD/DQ, never CUT
    specifically) and explicit WD/DQ statuses (real, but a different
    determination than CUT -- assess_r2 counts and returns them under
    their own status, untouched by this function).

    Archaeology note (klpga.collectors.aggregate's own module
    docstring, CONFIRMED live 2026-08-24): KLPGA's roundLeaderboard
    endpoint has never actually been observed emitting literal "CUT"
    text at all in any real captured response -- so in practice this
    currently evaluates False against real live data, the same
    behavior the previous hardcoded `cut_known=False` produced. The
    defect being fixed is not "the wrong boolean value today" (both
    versions currently produce WAIT against real data) but a hardcoded
    literal that could never become True even if the official source
    ever does start publishing an explicit CUT marker -- this function
    would correctly flip to True the moment real evidence appears,
    with zero further code changes.

    FINAL R2 EVIDENCE-GATE UPDATE (2026-09-11): `cut_boundary_published`
    is the SECOND, independently-sufficient explicit official signal --
    KLPGA's own real tr.table-cut/"Missed Cut" divider row on the
    scoreRecord page (klpga.collectors.score_record.
    parse_score_record_round_table), confirmed against a real captured
    R2 response for gameCode=2026090003 (see _collect_cut_boundary_
    evidence and this task's own final report). Either signal alone is
    sufficient -- the literal per-row "CUT" text path above was never
    observed live and may never fire in practice; the real boundary
    row IS what a real page actually uses."""
    return cut_boundary_published or any(row.get("status") == "CUT" for row in rows)


def _collect_cut_boundary_evidence() -> tuple[dict | None, str | None]:
    """Best-effort fetch + parse of the official scoreRecord page's own
    R2 tab (klpga.collectors.score_record.fetch_score_record_html +
    parse_score_record_round_table, round_tab_id="round-two") for real
    cut-boundary evidence. Mirrors _collect_live_r2's own error
    convention exactly: a network failure or "round not published yet"
    is an ordinary, non-fatal WAIT (evidence simply unavailable this
    cycle -- callers fall back to the a7a2a24 defensive path, never
    blocked on it); a parser/programming defect is a HARD_STOP. Never
    raises -- always returns (evidence_or_None, error_or_None)."""
    try:
        from klpga.collectors.score_record import fetch_score_record_html, parse_score_record_round_table
        from klpga.http_client import PoliteHttpClient

        client = PoliteHttpClient(cache_dir=ROOT / "data" / "raw_cache" / "kb_r2_cut_evidence")
        _status, html = fetch_score_record_html(client, GAME_CODE)
        evidence = parse_score_record_round_table(html, round_tab_id="round-two")
        return evidence, None
    except requests.exceptions.RequestException as exc:
        return None, f"WAIT:{type(exc).__name__}: {exc}"
    except ValueError as exc:
        # round-two tab-pane not published yet (or its table missing) --
        # a real, expected WAIT state, never a programming defect.
        return None, f"WAIT:{exc}"
    except Exception as exc:  # noqa: BLE001 -- parser/programming defects are hard stops
        return None, f"HARD_STOP:{type(exc).__name__}: {exc}"


_TERMINAL_STATUSES = frozenset({"WD", "DQ", "DNS", "CUT"})


def _reconcile_cut_evidence(rows: list[dict], evidence: dict) -> tuple[list[dict], list[str]]:
    """Overlays real, explicit WD/DQ/DNS/CUT statuses from the
    scoreRecord cut-boundary evidence onto the primary roundLeaderboard
    rows, joined by player_name (the only identity both real sources
    actually carry -- see klpga.neo_win.r2_sg_pipeline's own
    identity-join precedent for the same name-only-join situation).

    GENERIC STATUS-PRECEDENCE CONTRACT (fix/kb-r2-official-cut-gate-
    20260911, real-live-execution correction: a real --live run against
    gameCode=2026090003 HARD_STOPped on "cut-evidence conflict ... for:
    ['양서후']" even though the real scoreRecord evidence explicitly
    shows 양서후 = WD, physically after the Missed Cut boundary. Root
    cause: the primary roundLeaderboard source's real status for that
    player was NOT itself an explicit competing determination -- it was
    ACTIVE/unset/the confirmed data-rank="999" INCOMPLETE sentinel
    (klpga.parsers.leaderboard_parser's own confirmed "did not complete
    this round, could mean anything, never CUT specifically" contract,
    see _derive_cut_known's docstring) -- but the previous `current_
    status in (None, "ACTIVE")` check only recognized two of the many
    real non-terminal placeholder values roundLeaderboard can emit, so
    it fell through to the conflict branch by omission, not because the
    two sources genuinely disagreed. Fixed generically (never by
    player_id/name), by naming the actual real terminal-status set
    (WD/DQ/DNS/explicit-literal-CUT) instead of enumerating every
    non-terminal placeholder:

      1. current_status not in _TERMINAL_STATUSES (covers None, "ACTIVE",
         the "INCOMPLETE" 999-sentinel, and any other real non-terminal
         placeholder) -> never a real competing determination; always
         safe to enrich from the evidence's official_status.
      2. current_status == official_status -> already agree, untouched.
      3. current_status is terminal, official_status == "CUT" -> the
         scoreRecord page's own real per-row official_status cannot
         itself distinguish a literal "CUT" text cell from a
         section-derived (post-Missed-Cut-boundary) CUT (both come out
         identically as official_status="CUT" from
         parse_score_record_round_table); to stay safely conservative
         this evidence-side CUT is always treated as the WEAKER,
         subordinate signal here and never overrides the primary
         source's own real, explicit WD/DQ/DNS/CUT -- the primary
         status wins, untouched, no conflict.
      4. Otherwise: two genuinely different real, explicit terminal
         statuses (e.g. primary WD vs evidence DQ, or primary's own
         literal CUT vs evidence WD) -- a real disagreement between two
         official sources, never silently resolved -- recorded as a
         CONFLICT; callers must HARD_STOP.

    A primary row with no matching evidence row (name not found on the
    scoreRecord page) is left untouched -- absence of a match is not
    itself a conflict, since the two pages may legitimately cover
    slightly different real-time snapshots. A player entirely missing
    from `rows` is never touched by this function at all -- absence is
    never evidence of WD/CUT (see assess_r2's own separate, unmodified
    "entrant absent" HARD_STOP for that case).

    Returns (reconciled_rows, conflicting_player_names)."""
    evidence_by_name = {r["player_name"]: r for r in evidence.get("rows", [])}
    reconciled: list[dict] = []
    conflicts: list[str] = []
    for row in rows:
        match = evidence_by_name.get(row.get("player_name"))
        if match is None or match.get("official_status") is None:
            reconciled.append(row)
            continue
        current_status = row.get("status")
        official_status = match["official_status"]
        if current_status not in _TERMINAL_STATUSES:
            reconciled.append({**row, "status": official_status})
        elif current_status == official_status:
            reconciled.append(row)
        elif official_status == "CUT":
            reconciled.append(row)  # primary's own explicit terminal status wins over evidence's CUT
        else:
            conflicts.append(str(row.get("player_name")))
            reconciled.append(row)
    return reconciled, conflicts


def _apply_r2_cumulative_completion(rows: list[dict], expected_player_ids) -> list[dict]:
    """BUGFIX (fix/kb-r2-official-cut-gate-20260911): reconciles
    _collect_live_r2's per-row `holes_completed` -- which klpga.parsers.
    round_progress.resolve_completed_holes computes as CURRENT-ROUND-ONLY
    (0-18) by design, see that module's own docstring -- with
    r2_readiness.assess_r2's own separate, deliberate contract that an R2
    row's `holes_completed` means CUMULATIVE completion across R1+R2 (its
    "36"/"F"/"FINAL" check). Neither of those two modules is wrong or
    needs to change: round_progress is correctly generic and reused
    across every round of every tournament; assess_r2's "36" is a
    self-contained, already-tested R2-specific completeness signal. The
    actual defect is entirely in HOW this script's own _collect_live_r2
    fed one straight into the other -- passing R2's own 0-18 value
    directly into a field assess_r2 expects to already be cumulative,
    which real data could never satisfy.

    R1 completion (18 real holes) is NEVER re-derived here via arithmetic
    or a second live fetch -- it is an already-established fact taken
    directly from KB's own real, committed R1 evidence artifact's own
    contract: every player_id in expected_player_ids (NEO_KB_..._R1_
    OFFICIAL_RESULT_EVIDENCE_V1.json's `players[]`, i.e.
    r1_forward_population) really did complete R1's 18 holes -- that
    artifact's own `contract` dict explicitly documents r1_forward_
    population as EXCLUDING every official R1 WD (tracked separately in
    its own `official_wd` list), so a player only reaches expected_
    player_ids at all once R1 completion is a confirmed fact. Adding that
    guaranteed 18 to R2's own real, already-tee-adjusted current-round
    value is the ONLY arithmetic this function performs -- it never
    touches identity, WD/DQ/DNS status, rank, or score.

    A row whose player_id is not in expected_player_ids is left
    completely untouched (no cumulative computed) -- that is a genuine
    identity anomaly assess_r2's own separate, pre-existing HARD_STOP
    path already catches; this function is not the place to reason about
    it. A row whose holes_completed cannot be parsed as an int (already
    "F"/"FINAL", or absent) is also left untouched -- never coerced or
    guessed.

    KNOWN, DISCLOSED, OUT-OF-SCOPE LIMITATION: _collect_live_r2 itself
    hardcodes starting_tee=None when calling resolve_completed_holes, so
    a real 10th-tee starter's own current-round value is only as correct
    as that (separate, pre-existing) wiring gap allows -- this function
    adds the guaranteed R1 18 to whatever current-round value it is
    given, it does not and cannot fix how that current-round value itself
    was derived. See this task's final report [REMAINING BLOCKERS]."""
    expected = {str(pid) for pid in expected_player_ids}
    updated: list[dict] = []
    for row in rows:
        if str(row.get("player_id")) not in expected:
            updated.append(row)
            continue
        try:
            r2_round_holes = int(row["holes_completed"])
        except (KeyError, TypeError, ValueError):
            updated.append(row)
            continue
        updated.append({**row, "holes_completed": str(18 + r2_round_holes)})
    return updated


def _num_to_par(v) -> float | None:
    """Same numeric convention klpga.neo_win.post_r2_forecast._num
    already uses for score-to-par text ("E"/"EVEN" -> 0.0, a leading
    "+" stripped, "-5" -> -5.0) -- duplicated here (not imported) to
    keep this collection-time join independent of that later-stage
    module, matching this script's own established style of inlining
    small pure helpers rather than reaching into downstream consumers."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().upper().replace("+", "")
    if s in ("E", "EVEN"):
        return 0.0
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _load_r1_score_by_player(r1_evidence: dict) -> dict[str, float]:
    """Pure: real R1 to-par score by player_id, taken directly from the
    same real, committed R1 evidence artifact (NEO_KB_..._R1_OFFICIAL_
    RESULT_EVIDENCE_V1.json's `players[]`) that expected_player_ids is
    already derived from -- its own real `toPar` field (e.g. "-5",
    "E"), never re-derived from `r1Score` (raw strokes) or re-fetched
    live. A player whose real toPar can't be parsed is simply absent
    from the returned map -- never a guessed 0."""
    scores: dict[str, float] = {}
    for p in r1_evidence.get("players", []):
        v = _num_to_par(p.get("toPar"))
        if v is not None:
            scores[str(p["playerCode"])] = v
    return scores


def _apply_r1_scores(rows: list[dict], r1_score_by_player: dict[str, float]) -> list[dict]:
    """BUGFIX (fix/kb-r2-official-cut-gate-20260911, real --live
    execution correction): a real live run reached the probability gate
    and HARD_STOPped with "population mismatch: 71 missing" -- the
    generated forecast's own missing_players evidence showed profile=
    true, r2_score=true, r1_score=false for every one of them.

    ROOT CAUSE: _collect_live_r2() hardcodes `"r1_score_to_par": None`
    on every row it builds -- R1's real score was simply never joined
    into the R2 collection at all, live or otherwise, so every ACTIVE
    row written into the R2 freeze carried a permanently-null r1_score_
    to_par. klpga.neo_win.post_r2_forecast.run_post_r2_forecast reads
    r1_score_to_par directly off the FROZEN r2_freeze record (never
    re-derives it) and excludes any row where it is None -- exactly
    reproducing the real HARD_STOP's own missing_players evidence.

    FIX: R1's real score, like R1's real 18-hole completion in
    _apply_r2_cumulative_completion above, is an already-established
    fact from that SAME real, committed R1 evidence artifact -- never
    re-derived via arithmetic, never re-fetched live. This function
    joins it onto every row whose player_id has a real R1 score in
    `r1_score_by_player` (see _load_r1_score_by_player), overwriting
    whatever placeholder r1_score_to_par _collect_live_r2 set (there is
    no competing PRIMARY source for this field the way there is for
    status -- R1's official evidence is the one and only real source of
    a player's R1 score, so this is a direct fill, not a conflict-aware
    reconciliation). A row whose player_id has no real R1 score in the
    evidence is left completely untouched -- never fabricated, never
    coerced to 0."""
    updated: list[dict] = []
    for row in rows:
        pid = str(row.get("player_id"))
        r1_score = r1_score_by_player.get(pid)
        if r1_score is None:
            updated.append(row)
            continue
        updated.append({**row, "r1_score_to_par": r1_score})
    return updated


def _write_wait_page() -> bool:
    """Idempotent: only writes if the WAIT page is missing or stale.

    BUGFIX (fix/kb-r2-official-cut-gate-20260911, discovered while
    verifying Task L's fix): NEVER overwrites an already-real,
    gate-passed R2 page with the WAIT placeholder. The previous version
    of this function compared unconditionally against the WAIT page's
    own rendered HTML -- once a real R2 page has been published, its
    content will always differ from the WAIT page, so EVERY subsequent
    dry-run call (run_cycle(live=False), including a routine, "safe by
    default, zero HTTP requests" health-check cycle -- see this
    script's own module docstring) would silently regress the real,
    published page back to the WAIT placeholder. Discovered because it
    is exactly what happened to this repo's own real R2 page mid test
    suite (klpga.neo_win.r2_end_to_end_synthetic's real-state-check test
    calls run_cycle(live=False) against the real repo). Returns True if
    a write happened."""
    if R2_ROUTE_PATH.is_file():
        current = R2_ROUTE_PATH.read_text(encoding="utf-8")
        if is_real_page(current):
            return False
        html = render_r2_wait_page(tournament_name=_CONTEXT.tournament_name, game_code=GAME_CODE)
        if current == html:
            return False
    else:
        html = render_r2_wait_page(tournament_name=_CONTEXT.tournament_name, game_code=GAME_CODE)
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

    # STARTING-TEE EVIDENCE-GATE (fix/kb-r2-official-cut-gate-20260911):
    # the real, official group/tee-time page's own Round 2 grouping is
    # the ONLY source ever allowed to turn a row's raw last-course-hole
    # value into a real current-round completed-hole count. Missing
    # evidence (page unavailable / not yet published) never blocks the
    # cycle here -- it degrades every affected row's holes_completed to
    # the explicit _UNRESOLVED_STARTING_TEE sentinel, which naturally
    # routes through assess_r2's own existing, unmodified completion
    # check to WAIT. A real conflict (two group-page entries disagreeing
    # on one player's starting tee) is never silently resolved -- it is
    # a HARD_STOP, exactly like a cut-evidence conflict below.
    tee_evidence, tee_evidence_error = _collect_r2_starting_tee_evidence()
    if tee_evidence_error and tee_evidence_error.startswith("HARD_STOP"):
        return _summary("HARD_STOP", tee_evidence_error, freeze_exists)
    rows, tee_conflicts = _resolve_r2_starting_tee_and_holes(rows, tee_evidence)
    if tee_conflicts:
        return _summary(
            "HARD_STOP",
            f"ambiguous official starting-tee evidence (conflicting group-page entries) for: {sorted(tee_conflicts)}",
            freeze_exists,
        )

    # FINAL R2 EVIDENCE-GATE (2026-09-11): best-effort second evidence
    # source, the official scoreRecord page's own real cut-boundary
    # marker. Never blocks the primary path -- unavailable (network,
    # round not published yet) degrades to cut_boundary_published=False,
    # the exact a7a2a24 defensive behavior; a real disagreement between
    # the two sources is a HARD_STOP, never silently resolved.
    cut_evidence, cut_evidence_error = _collect_cut_boundary_evidence()
    if cut_evidence_error and cut_evidence_error.startswith("HARD_STOP"):
        return _summary("HARD_STOP", cut_evidence_error, freeze_exists)
    cut_boundary_published = False
    if cut_evidence is not None:
        rows, conflicts = _reconcile_cut_evidence(rows, cut_evidence)
        if conflicts:
            return _summary(
                "HARD_STOP",
                f"cut-evidence conflict between roundLeaderboard and scoreRecord for: {sorted(conflicts)}",
                freeze_exists,
            )
        cut_boundary_published = cut_evidence["cut_boundary_published"]

    # BUGFIX (fix/kb-r2-official-cut-gate-20260911): _collect_live_r2's
    # holes_completed is R2's own current-round-only value (0-18);
    # assess_r2 expects a cumulative R1+R2 value ("36"/"F"/"FINAL"). See
    # _apply_r2_cumulative_completion's own docstring for the full
    # semantic-contract trace.
    rows = _apply_r2_cumulative_completion(rows, expected.player_ids)

    # BUGFIX (fix/kb-r2-official-cut-gate-20260911, probability-gate real
    # --live correction): _collect_live_r2 hardcodes r1_score_to_par=None
    # on every row; join the real R1 to-par score from the same R1
    # evidence artifact expected.player_ids is already derived from. See
    # _apply_r1_scores's own docstring for the full root-cause trace.
    r1_evidence = json.loads(R1_EVIDENCE_PATH.read_text(encoding="utf-8"))
    rows = _apply_r1_scores(rows, _load_r1_score_by_player(r1_evidence))

    decision = decide_r2_cycle(
        rows, sorted(expected.player_ids),
        official_page_available=official_page_available,
        cut_known=_derive_cut_known(rows, cut_boundary_published=cut_boundary_published),
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

    # RENDERED-OUTPUT GATE (fix/kb-r2-official-cut-gate-20260911, real
    # production visual QA correction): every gate above validates the
    # canonical DATA artifacts -- nothing ever checked the actual
    # rendered HTML against them. A failure here means the page must
    # NEVER reach docs/ -- see r2_rendered_output_gate.py's own
    # docstring for the real production incident this closes.
    try:
        validate_r2_rendered_output(real_html, {"records": rows})
    except RenderedOutputGateError as exc:
        return _summary("HARD_STOP", f"rendered output gate failed: {exc}", True)

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
