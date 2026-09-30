"""NEO Sync command-line entry point.

    python -m klpga.neo_reader.cli sync --game-code 2026100001 --season 2026

Runs on a machine with real network access to klpga.co.kr /
k-rankings.klpga.co.kr -- this sandbox does not have one. Stages 1-4
(collect/normalize/warehouse/validate) always run; stage 5 (review
report) is always written; stage 6 (git publish) runs unless
--skip-github-upload or --dry-run is passed, and even then only if
validation PASSed."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # .../klpga_pipeline/src, so `import klpga...` resolves

from klpga.neo_reader.publish import publish_sync_artifacts  # noqa: E402
from klpga.neo_reader.review_report import write_review_report  # noqa: E402
from klpga.neo_reader.sync import run_sync  # noqa: E402
from klpga.neo_reader.validate import validate_sync  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]  # klpga_pipeline's parent (repo root)
PIPELINE_ROOT = ROOT / "klpga_pipeline"


def _default_paths() -> dict:
    return {
        "db_path": PIPELINE_ROOT / "data" / "klpga.sqlite",
        "raw_root": PIPELINE_ROOT / "raw",
        "normalized_root": PIPELINE_ROOT / "normalized",
        "reports_root": PIPELINE_ROOT / "reports",
        "content_root": PIPELINE_ROOT / "content" / "website_v2",
        "cache_dir": PIPELINE_ROOT / "data" / "raw_cache" / "http",
    }


def cmd_sync(args: argparse.Namespace) -> int:
    paths = _default_paths()

    season = args.season
    if season is None:
        if len(args.game_code) < 4 or not args.game_code[:4].isdigit():
            print(f"ERROR: cannot infer --season from gameCode={args.game_code!r} -- pass --season explicitly.", file=sys.stderr)
            return 2
        season = int(args.game_code[:4])
        print(f"No --season given; inferred season={season} from gameCode's leading 4 digits.")

    print(f"=== NEO Sync: gameCode={args.game_code} season={season} stage={args.stage} ===")
    result = run_sync(
        args.game_code, season, stage=args.stage,
        db_path=paths["db_path"], raw_root=paths["raw_root"],
        normalized_root=paths["normalized_root"], reports_root=paths["reports_root"],
        content_root=paths["content_root"], cache_dir=paths["cache_dir"],
    )
    for s in result.stages:
        print(f"  [{s.status.upper():8}] {s.name}: {s.error_message or s.detail}")

    if not result.ok:
        print("\nSync did not complete successfully. Not validating, not publishing.")
        return 1

    print("\n=== Validating ===")
    validation = validate_sync(args.game_code, paths["normalized_root"])
    for c in validation.checks:
        print(f"  [{c.status:4}] {c.name}: {c.detail}")
    print(f"Overall: {validation.overall}")

    print("\n=== Writing review report ===")
    report_path = write_review_report(paths["reports_root"], result, validation)
    print(f"  wrote {report_path}")

    if args.dry_run:
        print("\n--dry-run: skipping stage 6 (GitHub upload).")
        return 0 if validation.overall == "PASS" else 1

    if args.skip_github_upload:
        print("\n--skip-github-upload: skipping stage 6.")
        return 0 if validation.overall == "PASS" else 1

    print("\n=== Publishing ===")
    publish = publish_sync_artifacts(
        ROOT, args.game_code, event_name=args.game_code,
        raw_root=paths["raw_root"], normalized_root=paths["normalized_root"],
        reports_root=paths["reports_root"], content_root=paths["content_root"],
        validation_ok=(validation.overall == "PASS"),
    )
    print(f"  {publish.message}")
    return 0 if publish.ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sync_parser = sub.add_parser("sync", help="Run the full NEO Sync pipeline for one gameCode")
    sync_parser.add_argument("--game-code", required=True, dest="game_code")
    sync_parser.add_argument("--season", type=int, default=None,
                              help="Defaults to the gameCode's own leading 4 digits (e.g. 2026100001 -> 2026) if omitted.")
    sync_parser.add_argument("--stage", choices=["pre", "results"], default="pre",
                              help="'pre' = tournament info + entry list + K-Ranking (before any round is played). "
                                   "'results' additionally collects the round leaderboard (only once real round data exists).")
    sync_parser.add_argument("--dry-run", action="store_true", help="Run stages 1-5 only; never touches git.")
    sync_parser.add_argument("--skip-github-upload", action="store_true", dest="skip_github_upload")
    sync_parser.set_defaults(func=cmd_sync)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
