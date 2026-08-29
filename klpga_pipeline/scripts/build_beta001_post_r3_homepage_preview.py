"""BETA #001 POST-R3 homepage PREVIEW builder — for review before any
real deployment decision. READ-ONLY against the DB (opened `mode=ro`),
the frozen STAGE_R3 tournament_history record, and
`R2_R3_RECOVERY_COMPARISON.csv`. NEVER writes to any real production
file, NEVER touches BETA_R3_FULL.csv, NEVER touches any frozen PRE/R1/
R2/R3 artifact, NEVER recomputes a probability.

Source-of-truth split (fixed, never mixed):
  - current rank / 54-hole cumulative score / player status: the
    verified DB's real round_number 1-3 data (klpga.neo_win.
    player_status.classify_player_round_status for status).
  - WIN/TOP5/TOP10/TOP20%: the frozen STAGE_R3 record, read via
    klpga.neo_win.tournament_history.read_effective_history_stage,
    used EXACTLY as frozen.
  - R2->R3 WIN change: R2_R3_RECOVERY_COMPARISON.csv's own
    r2_to_r3_win_change_pct column, used exactly as already computed.

HARD STOPS (writes nothing) on: any real round_number=4 row already
existing, STAGE_R3 not found, the recovery CSV not found/malformed, a
duplicate player_code, WIN SUM among ACTIVE players not ~100%, any
WIN<=TOP5<=TOP10<=TOP20 (0-100) violation, an ACTIVE-in-DB player
entirely absent from STAGE_R3, or klpga.neo_win.player_status.
assess_field_readiness reporting a real ingestion gap at round_number=3.

Usage (once R3 has officially concluded and both source artifacts exist):
    python scripts/build_beta001_post_r3_homepage_preview.py --db data/klpga.sqlite \\
        --game-code 2026080001 --history-dir neo_tournament_history \\
        --r2-recovery-csv outputs/r2_r3_recovery_compare/2026080001/R2_R3_RECOVERY_COMPARISON.csv \\
        --tournament-name "제15회 KG 레이디스 오픈"
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import http.server
import socketserver
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.player_status import (  # noqa: E402
    READINESS_HARD_STOP,
    STATUS_COMPLETED,
    assess_field_readiness,
    classify_player_round_status,
)
from klpga.neo_win.post_r3_homepage_preview import (  # noqa: E402
    STATUS_ACTIVE,
    DbPlayerRow,
    build_preview_rows,
    check_duplicate_player_codes,
    check_probability_invariants,
    check_win_sum,
    reconcile_codes,
    render_preview_html,
)
from klpga.neo_win.tournament_history import (  # noqa: E402
    STAGE_R3,
    history_stage_path,
    read_effective_history_stage,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY_DIR = ROOT / "neo_tournament_history"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "beta_r3_homepage_preview"

_RECOVERY_CSV_FIELDNAMES = (
    "player_code", "player_name", "match_status", "r2_rank", "r2_total_score",
    "r2_win_pct", "r2_top5_pct", "r2_top10_pct", "r2_top20_pct",
    "r3_win_pct", "r3_top5_pct", "r3_top10_pct", "r3_top20_pct", "r2_to_r3_win_change_pct",
)


def _r4_row_count(conn: sqlite3.Connection, game_code: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM player_round WHERE game_code = ? AND round_number = 4", (game_code,)
    ).fetchone()[0]


def _round_scores(conn: sqlite3.Connection, game_code: str, round_number: int) -> dict:
    return dict(conn.execute(
        "SELECT player_id, round_to_par FROM player_round WHERE game_code = ? AND round_number = ? "
        "AND round_to_par IS NOT NULL",
        (game_code, round_number),
    ).fetchall())


def _entry_field_codes(conn: sqlite3.Connection, game_code: str) -> list[tuple[str, str]]:
    return conn.execute(
        "SELECT player_code, player_name_display FROM tournament_entry WHERE game_code = ? ORDER BY player_code",
        (game_code,),
    ).fetchall()


def _parse_optional_float(raw: str) -> Optional[float]:
    raw = (raw or "").strip()
    return None if raw == "" or raw == "unavailable" else float(raw)


def _read_recovery_csv(path: Path) -> tuple[dict[str, Optional[float]], list[str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or set(reader.fieldnames) != set(_RECOVERY_CSV_FIELDNAMES):
            return {}, [f"expected columns {_RECOVERY_CSV_FIELDNAMES}, found {tuple(reader.fieldnames or ())}"]
        change_by_code: dict[str, Optional[float]] = {}
        for row in reader:
            change_by_code[row["player_code"]] = _parse_optional_float(row["r2_to_r3_win_change_pct"])
    return change_by_code, []


def _capture_png(html_path: Path, png_path: Path) -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "playwright not installed in this environment"

    chromium_candidates = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")
    if not chromium_candidates:
        return False, "no Chromium executable found under /opt/pw-browsers"
    chromium_path = chromium_candidates[0]

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(html_path.parent), **kwargs)

        def guess_type(self, path):
            ctype = super().guess_type(path)
            if isinstance(ctype, tuple):
                ctype = ctype[0]
            return "text/html; charset=utf-8" if ctype == "text/html" else ctype

        def log_message(self, *args):
            pass

    port = 8955
    try:
        httpd = socketserver.TCPServer(("", port), _Handler)
    except OSError as exc:
        return False, f"could not start local preview server: {exc}"
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=chromium_path)
            ctx = browser.new_context(viewport={"width": 1000, "height": 1400})
            ctx.route("**/*", lambda route: route.continue_() if f"localhost:{port}" in route.request.url else route.abort())
            page = ctx.new_page()
            page.goto(f"http://localhost:{port}/{html_path.name}", wait_until="networkidle")
            page.screenshot(path=str(png_path), full_page=True)
            browser.close()
    except Exception as exc:  # noqa: BLE001 -- reported, never silently swallowed
        return False, f"Playwright render failed: {exc}"
    finally:
        httpd.shutdown()
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--history-dir", default=str(DEFAULT_HISTORY_DIR))
    parser.add_argument("--r2-recovery-csv", required=True)
    parser.add_argument("--tournament-name", default="")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-png", action="store_true", help="Skip Playwright PNG capture (HTML only).")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        r4_count = _r4_row_count(conn, args.game_code)
        readiness = assess_field_readiness(conn, args.game_code, round_number=3)
        r1_scores = _round_scores(conn, args.game_code, 1)
        r2_scores = _round_scores(conn, args.game_code, 2)
        r3_scores = _round_scores(conn, args.game_code, 3)

        db_rows: list[DbPlayerRow] = []
        for code, name in _entry_field_codes(conn, args.game_code):
            status_obj = classify_player_round_status(conn, args.game_code, code, round_number=3)
            if status_obj.classification == STATUS_COMPLETED:
                has_full = code in r1_scores and code in r2_scores and code in r3_scores
                cumulative = (r1_scores[code] + r2_scores[code] + r3_scores[code]) if has_full else None
                db_rows.append(DbPlayerRow(player_code=code, player_name=name, status=STATUS_ACTIVE, cumulative_score_to_par=cumulative))
            else:
                db_rows.append(DbPlayerRow(player_code=code, player_name=name, status=status_obj.classification, cumulative_score_to_par=None))
    finally:
        conn.close()

    stage_r3 = read_effective_history_stage(Path(args.history_dir), args.game_code, STAGE_R3)
    stage_r3_path = history_stage_path(Path(args.history_dir), args.game_code, STAGE_R3)
    stage_r3_hash = hashlib.sha256(stage_r3_path.read_bytes()).hexdigest() if stage_r3_path.exists() else None

    recovery_path = Path(args.r2_recovery_csv)
    recovery_change_by_code: dict = {}
    recovery_problems: list[str] = []
    recovery_hash = None
    if recovery_path.exists():
        recovery_hash = hashlib.sha256(recovery_path.read_bytes()).hexdigest()
        recovery_change_by_code, recovery_problems = _read_recovery_csv(recovery_path)

    stage_r3_entrants_by_code = {e.player_code: e for e in stage_r3.entrants} if stage_r3 is not None else {}

    print("=== NEO GOLF DATA BETA #001 POST-R3 HOMEPAGE PREVIEW — VALIDATION ===")
    print()
    print(f"STAGE_R3 source path: {stage_r3_path}")
    print(f"STAGE_R3 hash: {stage_r3_hash if stage_r3_hash else 'N/A (not found)'}")
    print(f"R2 recovery source path: {recovery_path}")
    print(f"R2 recovery hash: {recovery_hash if recovery_hash else 'N/A (not found)'}")

    hard_stops: list[str] = []
    warnings: list[str] = []

    if r4_count > 0:
        hard_stops.append(f"FUTURE_DATA_LEAKAGE — {r4_count} round_number=4 row(s) already exist")
    if stage_r3 is None:
        hard_stops.append("STAGE_R3 not found")
    if not recovery_path.exists():
        hard_stops.append(f"R2 recovery CSV not found at {recovery_path}")
    elif recovery_problems:
        hard_stops.append(f"R2 recovery CSV malformed: {recovery_problems}")
    if readiness.verdict == READINESS_HARD_STOP:
        hard_stops.append(f"R1-R3 official data completeness: {readiness.reason}")

    duplicate_codes = check_duplicate_player_codes([e.player_code for e in stage_r3.entrants]) if stage_r3 is not None else []
    if duplicate_codes:
        hard_stops.append(f"duplicate player_code in STAGE_R3: {duplicate_codes}")

    active_count = sum(1 for r in db_rows if r.status == STATUS_ACTIVE)
    print(f"ACTIVE player count (DB): {active_count}")
    print(f"R4 row count: {r4_count}")

    rows: list = []
    win_sum = None
    win_sum_ok = None
    invariant_violations: list[str] = []

    if not hard_stops:
        rows, join_warnings = build_preview_rows(db_rows, stage_r3_entrants_by_code, recovery_change_by_code)
        warnings.extend(join_warnings)

        win_sum, win_sum_ok = check_win_sum(rows)
        invariant_violations = check_probability_invariants(rows)
        if not win_sum_ok:
            hard_stops.append(f"WIN SUM = {win_sum}% (expected ~100%)")
        if invariant_violations:
            hard_stops.append(f"probability invariant violations: {len(invariant_violations)}")

        db_active_codes = {r.player_code for r in db_rows if r.status == STATUS_ACTIVE}
        stage_r3_codes = set(stage_r3_entrants_by_code)
        recon_db_stage = reconcile_codes("db_active", db_active_codes, "stage_r3", stage_r3_codes)
        if recon_db_stage["db_active_only"]:
            hard_stops.append(f"ACTIVE-in-DB but absent from STAGE_R3: {recon_db_stage['db_active_only']}")
        if recon_db_stage["stage_r3_only"]:
            warnings.append(f"in STAGE_R3 but not ACTIVE in DB (expected for confirmed CUT/WD/DQ players): {len(recon_db_stage['stage_r3_only'])}")

        recovery_codes = set(recovery_change_by_code)
        recon_recovery_stage = reconcile_codes("recovery", recovery_codes, "stage_r3", stage_r3_codes)
        if recon_recovery_stage["stage_r3_only"]:
            warnings.append(f"in STAGE_R3 but absent from recovery CSV: {len(recon_recovery_stage['stage_r3_only'])}")
        if recon_recovery_stage["recovery_only"]:
            warnings.append(f"in recovery CSV but absent from STAGE_R3: {len(recon_recovery_stage['recovery_only'])}")

    print(f"WIN probability sum: {win_sum if win_sum is not None else 'N/A'}%")
    print(f"duplicate player_code count: {len(duplicate_codes)}")
    print(f"probability invariant violations: {len(invariant_violations)}")
    print()

    if hard_stops:
        print("STATUS: HARD_STOP")
        for reason in hard_stops:
            print(f"  - {reason}")
        print()
        print("Nothing written.")
        return 0

    if warnings:
        print(f"WARN ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")
        print()

    print("STATUS: VALIDATION_PASSED")
    print()

    tournament_name = args.tournament_name or "(제15회 KG 레이디스 오픈)"
    html = render_preview_html(rows, tournament_name=tournament_name, game_code=args.game_code)

    output_dir = Path(args.output_dir) / args.game_code
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "preview.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"Wrote: {html_path}")

    png_path = output_dir / "preview.png"
    if args.no_png:
        print("PNG: skipped (--no-png)")
    else:
        ok, reason = _capture_png(html_path, png_path)
        if ok:
            print(f"Wrote: {png_path}")
        else:
            print(f"PNG: NOT captured — {reason}")

    active_sorted = sorted(
        (r for r in rows if r.status == STATUS_ACTIVE),
        key=lambda r: (r.win_pct if r.win_pct is not None else -1.0), reverse=True,
    )
    print()
    print("=== TOP 10 (WIN% descending) ===")
    for i, r in enumerate(active_sorted[:10], start=1):
        print(f"{i}. {r.player_name} ({r.player_code}) — WIN {r.win_pct:.2f}% "
              f"(R2->R3 {r.r2_to_r3_win_change_pct if r.r2_to_r3_win_change_pct is None else f'{r.r2_to_r3_win_change_pct:+.2f}%p'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
