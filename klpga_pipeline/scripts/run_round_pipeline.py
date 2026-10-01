"""Single, round-agnostic entry point for the HITE JINRO (game_code
2026100005) tournament pipeline -- PRE, R1, R2, R3, FR all go through
this one script instead of a hand-maintained copy per round:

    python scripts/run_round_pipeline.py 2026100005 R2

For R1/R2/R3/FR this automatically, in order:
  1. requires this round's official leaderboard/SG/scorecard raw
     captures already on disk (never auto-fetched -- no Reader
     offline mode exists here; fails closed with "공식 데이터 없음" the
     moment one is missing, before touching anything)
  2. parses the leaderboard raw capture into LEADERBOARD.json
  3. parses the Strokes Gained raw capture into a round-scoped SG file
  4. cross-validates both against the separate scorecard raw capture
     (raises loudly on any mismatch -- never tolerates one)
  5. merges the validated SG into historical_sg_warehouse_corrected_v2.json
  6. regenerates every participating player's Player Intelligence
  7. builds this round's public page
  8. re-promotes HOME to mirror the new current stage
  9. runs a Playwright smoke check (HOME + PRE + this round, desktop
     and mobile, no console errors)
 10. commits exactly the files this run touched and pushes

For PRE, runs the existing pre-tournament build (scripts/190 + 193)
instead -- there is no round evidence to parse before the tournament
starts.

Every step after evidence parsing reuses the SAME shared, round-
agnostic code every stage already shares -- see
klpga.neo_win.hitejinro_round_pipeline (evidence parsing + page
build), klpga.knowledge_engine.player_intelligence_generator (Player
Intelligence), scripts/190+192+193 (PRE build + HOME promotion, both
already round-agnostic on their own). Nothing here duplicates any of
those; this script only orchestrates them in the right order and adds
the one thing none of them already did: committing and pushing the
result.
"""
from __future__ import annotations

import argparse
import http.server
import json
import re
import subprocess
import sys
import threading
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent  # klpga_pipeline/
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.hitejinro_round_pipeline import (  # noqa: E402
    GAME_CODE as HITEJINRO_GAME_CODE,
    build_round_page,
    cross_validate,
    merge_sg_into_warehouse,
    parse_leaderboard,
    parse_sg,
    require_raw_evidence,
)
from klpga.neo_win.hitejinro_round_page import STAGE_LABELS  # noqa: E402
from klpga.knowledge_engine.player_intelligence_generator import regenerate_for_tournament  # noqa: E402

STAGE_TO_ROUND = {label: n for n, (_key, label) in STAGE_LABELS.items()}  # {"R1": 1, "R2": 2, "R3": 3, "FR": 4}
PLAYWRIGHT_PORT = 8943
# The one console message every page's browser-internal /favicon.ico
# 404 produces (confirmed empirically -- see playwright_verify's own
# docstring). Not a pipeline error; every other message still fails
# the check.
_KNOWN_HARMLESS_CONSOLE_ERRORS = ["Failed to load resource: the server responded with a status of 404 (File not found)"]


def _run_script(name: str) -> None:
    result = subprocess.run([sys.executable, str(SCRIPTS_DIR / name)], cwd=ROOT, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"{name} failed (exit {result.returncode})")


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}")
    return result.stdout


def run_pre(game_code: str) -> dict:
    _run_script("190_build_hitejinro_pre_page.py")
    m4_path = ROOT / "content" / "website_v2" / f"HITEJINRO_{game_code}_PRE_M4_CANDIDATE_V1.json"
    if m4_path.is_file():
        # 193 fits a fresh Monte Carlo model from a real training corpus
        # (NEO_DATA_ROOT) that this sandbox has never had -- it fails
        # closed here every time, by design (see its own module
        # docstring). The committed M4 file was built once, on a
        # machine that DID have that corpus, and is read thereafter by
        # every PRE/round page via hitejinro_player_metrics.load_m4_by_id()
        # -- never blindly regenerated on a run that can't possibly
        # produce a better one.
        print(json.dumps({"skipped": "193_build_hitejinro_pre_m4.py", "reason": f"{m4_path} already exists"}))
    else:
        _run_script("193_build_hitejinro_pre_m4.py")
    _run_script("192_promote_hitejinro_home.py")
    return {"stage": "PRE"}


def run_round(game_code: str, stage: str) -> dict:
    round_number = STAGE_TO_ROUND[stage]

    require_raw_evidence(round_number)  # fails closed: 공식 데이터 없음, before any write

    leaderboard_path = parse_leaderboard(round_number)
    sg_path = parse_sg(round_number)
    validation = cross_validate(round_number)  # raises SystemExit on any mismatch -- no further step runs
    merge_result = merge_sg_into_warehouse(round_number)

    pi_batch = regenerate_for_tournament(game_code, force=True)
    if pi_batch.errors:
        raise SystemExit(f"Player Intelligence regeneration had errors, refusing to continue: {pi_batch.errors}")

    page_path = build_round_page(round_number)
    _run_script("192_promote_hitejinro_home.py")

    return {
        "stage": stage,
        "leaderboard_path": str(leaderboard_path),
        "sg_path": str(sg_path),
        "cross_validation": validation,
        "warehouse_merge": merge_result,
        "player_intelligence": {
            "written": len(pi_batch.written),
            "skipped": len(pi_batch.skipped),
            "errors": len(pi_batch.errors),
        },
        "page_path": str(page_path),
    }


def playwright_verify(game_code: str, stage_key: str) -> dict:
    """HOME + PRE + this stage, desktop (1440x900) and mobile
    (390x844), served over a local HTTP server rooted at docs/ (same
    pattern as tests/test_previous_tournament_e2e_browser.py, so
    absolute asset paths resolve) -- fails loudly on any console error
    other than a bare favicon 404 (a harmless browser default present
    on every static page, unrelated to this pipeline). Chromium fetches
    /favicon.ico through an internal path this sandbox's headless
    Playwright never surfaces via page 'response'/'requestfailed'
    events (confirmed empirically: the server log shows the request
    and its 404, but no page-level event fires for it) -- the only
    observable signal is the generic console message every 404
    produces. _KNOWN_HARMLESS_CONSOLE_ERRORS lists that exact string;
    anything else, or that string alongside any other error, still
    fails the check.

    HOME is only required to mirror THIS stage when this stage is
    really the tournament's most advanced published one right now
    (klpga.website_v2.previous_tournament_link.latest_published_stage_url,
    the same real on-disk check HOME's own promotion script uses) --
    rebuilding an earlier stage (e.g. PRE, after R1 already went live)
    must not fail this check against a page HOME was never supposed to
    mirror in the first place."""
    from playwright.sync_api import sync_playwright

    from klpga.website_v2.previous_tournament_link import latest_published_stage_url

    docs = REPO_ROOT / "docs"
    paths = {
        "HOME": "/",
        "PRE": f"/tournaments/2026/{game_code}/pre/",
        stage_key.upper(): f"/tournaments/2026/{game_code}/{stage_key}/",
    }
    viewports = {"desktop": {"width": 1440, "height": 900}, "mobile": {"width": 390, "height": 844}}

    def handler_factory(*args, **kwargs):
        return http.server.SimpleHTTPRequestHandler(*args, directory=str(docs), **kwargs)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", PLAYWRIGHT_PORT), handler_factory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    real_errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
            for label, url_path in paths.items():
                for vp_name, vp in viewports.items():
                    page = browser.new_page(viewport=vp)
                    console_errors = []
                    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                    page.on("pageerror", lambda exc: console_errors.append(str(exc)))
                    page.goto(f"http://127.0.0.1:{PLAYWRIGHT_PORT}{url_path}")
                    page.wait_for_timeout(300)
                    remaining = list(console_errors)
                    for known in _KNOWN_HARMLESS_CONSOLE_ERRORS:
                        if known in remaining:
                            remaining.remove(known)
                    if remaining:
                        real_errors.append({"page": label, "viewport": vp_name, "errors": remaining})
                    page.close()
            browser.close()
    finally:
        server.shutdown()

    current_stage_href = latest_published_stage_url(f"/tournaments/2026/{game_code}/", repo_root=REPO_ROOT)
    current_stage_key = current_stage_href.strip("/").rsplit("/", 1)[-1]

    home_html = (docs / "index.html").read_text(encoding="utf-8")
    current_stage_html = (docs / "tournaments" / "2026" / game_code / current_stage_key / "index.html").read_text(encoding="utf-8")
    home_main = "<main>" + home_html.split("<main>", 1)[1].rsplit("</main>", 1)[0] + "</main>"
    current_stage_main = "<main>" + current_stage_html.split("<main>", 1)[1].rsplit("</main>", 1)[0] + "</main>"

    result = {
        "pages_checked": list(paths.keys()),
        "viewports_checked": list(viewports.keys()),
        "console_errors": real_errors,
        "current_stage": current_stage_key,
        "home_mirrors_current_stage": home_main == current_stage_main,
    }
    if real_errors or not result["home_mirrors_current_stage"]:
        raise SystemExit(f"Playwright verification failed: {json.dumps(result, ensure_ascii=False, indent=2)}")
    return result


def commit_and_push(game_code: str, stage: str, stage_key: str | None) -> dict:
    pathspecs = [
        f"docs/index.html",
        "content/website_v2/knowledge_engine/player_intelligence/*/latest.json",
        "content/website_v2/knowledge_engine/player_intelligence/*/history/*.json",
    ]
    if stage == "PRE":
        pathspecs += [
            f"docs/tournaments/2026/{game_code}/pre/index.html",
            f"content/website_v2/HITEJINRO_{game_code}_PRE_M4_CANDIDATE_V1.json",
        ]
    else:
        pathspecs += [
            f"docs/tournaments/2026/{game_code}/{stage_key}/index.html",
            f"content/website_v2/{game_code}_LEADERBOARD.json",
            f"content/website_v2/HITEJINRO_{game_code}_{stage}_SG_V1.json",
            "content/website_v2/historical_sg_warehouse_corrected_v2.json",
        ]

    _git("add", "--", *pathspecs)
    staged = _git("diff", "--cached", "--name-only").strip()
    if not staged:
        return {"committed": False, "reason": "nothing changed"}

    message = f"HITE JINRO {stage}: official data pipeline run via run_round_pipeline.py"
    _git("commit", "-m", message)
    commit_hash = _git("rev-parse", "--short", "HEAD").strip()
    _git("push", "-u", "origin", "neo-website-v2")
    return {"committed": True, "commit": commit_hash, "staged_files": staged.splitlines()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("game_code")
    parser.add_argument("stage", choices=["PRE", "R1", "R2", "R3", "FR"])
    parser.add_argument("--no-commit", action="store_true", help="run and verify only, skip git commit/push")
    args = parser.parse_args()

    if args.game_code != HITEJINRO_GAME_CODE:
        raise SystemExit(
            f"no pipeline wired for game_code {args.game_code!r} -- this script currently only supports "
            f"{HITEJINRO_GAME_CODE} (HITE JINRO). Never fabricates support for an unwired tournament."
        )

    if args.stage == "PRE":
        result = run_pre(args.game_code)
        stage_key = "pre"
    else:
        result = run_round(args.game_code, args.stage)
        stage_key = STAGE_LABELS[STAGE_TO_ROUND[args.stage]][0]
    print(json.dumps(result, ensure_ascii=False, indent=2))

    verify = playwright_verify(args.game_code, stage_key)
    print(json.dumps(verify, ensure_ascii=False, indent=2))

    if args.no_commit:
        print(json.dumps({"committed": False, "reason": "--no-commit"}, ensure_ascii=False))
        return

    push_result = commit_and_push(args.game_code, args.stage, None if args.stage == "PRE" else stage_key)
    print(json.dumps(push_result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
