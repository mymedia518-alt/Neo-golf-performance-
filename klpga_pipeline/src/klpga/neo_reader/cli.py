"""NEO Sync command-line entry point.

    python -m klpga.neo_reader.cli sync --game-code 2026100001 --season 2026

Runs on a machine with real network access to klpga.co.kr /
k-rankings.klpga.co.kr -- this sandbox does not have one. Stages 1-4
(collect/normalize/warehouse/validate) always run; stage 5 (review
report) is always written; stage 6 (git publish) runs unless
--skip-github-upload or --dry-run is passed, and even then only if
validation PASSed.

BUG FIX (2026-09-30): raw_root/normalized_root/db_path/cache_dir now go
through klpga.ops.paths, the same NEO_DATA_ROOT resolution 193_build_
hitejinro_pre_m4.py already uses -- before this fix, `sync` (online or
--offline) always read/wrote klpga_pipeline/raw and klpga_pipeline/
normalized regardless of NEO_DATA_ROOT, so setting NEO_DATA_ROOT=D:\\
NEO_DATA_ROOT on a production machine had no effect on this command at
all. It now resolves to D:\\NEO_DATA_ROOT\\raw and D:\\NEO_DATA_ROOT\\
normalized automatically, matching ops.paths.raw_root/normalized_root's
own documented contract -- no behavior change when NEO_DATA_ROOT is
unset (falls back to the exact same klpga_pipeline/raw,
klpga_pipeline/normalized this module always defaulted to).

    python -m klpga.neo_reader.cli export-raw --game-code 2026100005

No network. Automatically, with no file selection by the person running
it: (1) lists every archived raw/<game_code>/* capture, (2) classifies
each one by PARSER CAPABILITY -- reads the file's real content and
tries every existing parser (klpga.neo_reader.capability_detect) --
"parser_exists"/"adapter_exists" the moment any real parser actually
returns real rows against it, regardless of filename (a file literally
named leaderboard.html IS parser_exists if its bytes match the
confirmed roundLeaderboard shape), or "parser_missing" only once NONE
of them do (course/history_record/pin_placement, or any other content
no existing parser's real contract accepts -- exhaustive repo search
2026-09-30 found no parser, confirmed parser, or even an unconfirmed
fetch-only stub for those three anywhere in this project), (3) runs
every parser/adapter that exists immediately via run_sync_offline
(unless --skip-run) -- which itself now also discovers each stage's
input file by the same capability probe when the canonical archive_raw
filename isn't present, not by hard-requiring one exact name -- and
(4) bundles raw HTML + MANIFEST.json + a parser_samples/ copy of only
the parser-missing files into one zip (or directory) -- so a developer
building course_parser.py/etc. gets exactly the files that need one,
decided by the tool, never by the person running it."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # .../klpga_pipeline/src, so `import klpga...` resolves

from klpga.neo_reader.capability_detect import classify_file_by_content  # noqa: E402
from klpga.neo_reader.publish import publish_sync_artifacts  # noqa: E402
from klpga.neo_reader.review_report import write_review_report  # noqa: E402
from klpga.neo_reader.sync import run_sync, run_sync_offline  # noqa: E402
from klpga.neo_reader.validate import validate_sync  # noqa: E402
from klpga.ops.paths import cache_dir as _resolve_cache_dir  # noqa: E402
from klpga.ops.paths import db_path as _resolve_db_path  # noqa: E402
from klpga.ops.paths import normalized_root as _resolve_normalized_root  # noqa: E402
from klpga.ops.paths import raw_root as _resolve_raw_root  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]  # klpga_pipeline's parent (repo root)
PIPELINE_ROOT = ROOT / "klpga_pipeline"


def _default_paths() -> dict:
    return {
        "db_path": _resolve_db_path(),
        "raw_root": _resolve_raw_root(),
        "normalized_root": _resolve_normalized_root(),
        "reports_root": PIPELINE_ROOT / "reports",
        "content_root": PIPELINE_ROOT / "content" / "website_v2",
        "cache_dir": _resolve_cache_dir(),
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

    mode = "OFFLINE (no network -- reading already-archived raw/ captures)" if args.offline else "online"
    print(f"=== NEO Sync: gameCode={args.game_code} season={season} stage={args.stage} mode={mode} ===")
    if args.offline:
        result = run_sync_offline(
            args.game_code, season, stage=args.stage,
            db_path=paths["db_path"], raw_root=paths["raw_root"],
            normalized_root=paths["normalized_root"], content_root=paths["content_root"],
        )
    else:
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


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_export_raw(args: argparse.Namespace) -> int:
    """No network. Fully automatic: classifies every archived file BY
    PARSER CAPABILITY (klpga.neo_reader.capability_detect.
    classify_file_by_content -- reads real content, tries every real
    parser, never guesses from the filename), runs every parser/
    adapter that exists against this exact capture set (reusing
    run_sync_offline unchanged -- no duplicated parsing logic), and
    bundles raw HTML + MANIFEST.json + a parser_samples/ copy of only
    the parser-missing files. The person running this never chooses
    which files matter -- classify_file_by_content does."""
    raw_root = Path(args.raw_root) if args.raw_root else _resolve_raw_root()
    game_dir = raw_root / args.game_code
    if not game_dir.is_dir():
        print(f"ERROR: {game_dir} does not exist -- nothing to export.", file=sys.stderr)
        return 2

    all_files = sorted(
        p for p in game_dir.iterdir()
        if p.is_file() and p.name != "RAW_MANIFEST_V1.json"  # archive_raw's own bookkeeping file, not page content
    )
    if not all_files:
        print(f"ERROR: {game_dir} exists but contains no files -- nothing to export.", file=sys.stderr)
        return 2

    if args.only:
        wanted = [name.strip() for name in args.only.split(",") if name.strip()]
        present_names = {p.name for p in all_files}
        missing = [name for name in wanted if name not in present_names]
        selected = [p for p in all_files if p.name in wanted]
        if missing:
            print(f"NOTE: requested but NOT found in {game_dir}: {missing}")
        if not selected:
            print(f"ERROR: none of the requested files {wanted} exist in {game_dir}.", file=sys.stderr)
            print(f"Files that DO exist there: {sorted(present_names)}", file=sys.stderr)
            return 2
    else:
        selected = all_files

    # -------------------------------------------------------------
    # 1+2: classify every selected file automatically.
    # -------------------------------------------------------------
    manifest_entries = []
    classification_by_path = {}
    for p in selected:
        classification = classify_file_by_content(p)
        classification_by_path[p] = classification
        manifest_entries.append({
            "filename": p.name,
            "size_bytes": p.stat().st_size,
            "sha256": _sha256_file(p),
            "parser_status": classification["status"],
            "stage_name": classification["stage_name"],
            "classification_detail": classification["detail"],
            "run_status": None,
            "run_detail": None,
        })

    # -------------------------------------------------------------
    # 3: run every real/adapter parser immediately, unless --skip-run.
    # A parser crashing must never block delivering the raw export
    # itself, so this is caught and reported, not left to abort the
    # whole command.
    # -------------------------------------------------------------
    run_result = None
    if args.skip_run:
        print("--skip-run: not executing any parser.")
    else:
        season = args.season
        if season is None and len(args.game_code) >= 4 and args.game_code[:4].isdigit():
            season = int(args.game_code[:4])
        if season is None:
            print(f"NOTE: could not infer season from gameCode={args.game_code!r}; pass --season to run parsers. Skipping run.")
        else:
            paths = _default_paths()
            print(f"\n=== Running every known parser/adapter against raw/{args.game_code} (season={season}) ===")
            try:
                run_result = run_sync_offline(
                    args.game_code, season, stage="results",
                    db_path=paths["db_path"], raw_root=raw_root,
                    normalized_root=paths["normalized_root"], content_root=paths["content_root"],
                )
            except Exception as exc:  # noqa: BLE001 -- a parser raising must not block delivering the export
                print(f"NOTE: parser run raised an unexpected error (export continues): {exc}")
            else:
                stage_by_name = {s.name: s for s in run_result.stages}
                for entry in manifest_entries:
                    stage = stage_by_name.get(entry["stage_name"]) if entry["stage_name"] else None
                    if stage is not None:
                        entry["run_status"] = stage.status
                        entry["run_detail"] = stage.error_message or stage.detail
                for s in run_result.stages:
                    print(f"  [{s.status.upper():8}] {s.name}: {s.error_message or s.detail}")

    manifest = {
        "game_code": args.game_code,
        "raw_root": str(raw_root),
        "files": manifest_entries,
        "parser_missing_files": [e["filename"] for e in manifest_entries if e["parser_status"] == "parser_missing"],
    }

    # -------------------------------------------------------------
    # 4+5: bundle raw HTML + MANIFEST.json + parser_samples/ (only the
    # parser-missing files, auto-selected -- never a manual choice).
    # -------------------------------------------------------------
    missing_parser_files = [p for p in selected if classification_by_path[p]["status"] == "parser_missing"]
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)

    if args.zip:
        out_path = Path(args.out) if args.out else (raw_root.parent / "exports" / f"{args.game_code}_raw_export.zip")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in selected:
                zf.write(p, arcname=f"raw/{p.name}")  # byte-for-byte: writes the file's real bytes, never re-encodes
            for p in missing_parser_files:
                zf.write(p, arcname=f"parser_samples/{p.name}")
            zf.writestr("MANIFEST.json", manifest_json)
        print(f"\nWrote raw/ ({len(selected)} file(s)) + MANIFEST.json + parser_samples/ ({len(missing_parser_files)} file(s)) into {out_path}")
    else:
        out_dir = Path(args.out) if args.out else (game_dir / "_export")
        (out_dir / "raw").mkdir(parents=True, exist_ok=True)
        for p in selected:
            shutil.copyfile(p, out_dir / "raw" / p.name)  # copyfile preserves bytes exactly, no text re-encoding
        if missing_parser_files:
            (out_dir / "parser_samples").mkdir(parents=True, exist_ok=True)
            for p in missing_parser_files:
                shutil.copyfile(p, out_dir / "parser_samples" / p.name)
        (out_dir / "MANIFEST.json").write_text(manifest_json, encoding="utf-8")
        print(f"\nWrote raw/ ({len(selected)} file(s)) + MANIFEST.json + parser_samples/ ({len(missing_parser_files)} file(s)) into {out_dir}")

    print("\nMANIFEST:")
    for entry in manifest_entries:
        run_note = f"  run={entry['run_status']}" if entry["run_status"] else ""
        print(f"  {entry['filename']:32} {entry['parser_status']:15}{run_note}")
    if manifest["parser_missing_files"]:
        print(f"\nNo parser exists for: {manifest['parser_missing_files']} -- auto-copied to parser_samples/ for review.")

    return 0


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
    sync_parser.add_argument(
        "--offline", action="store_true",
        help="Make ZERO network calls. Reads already-archived raw/<game_code>/*.html (and "
             "game_list.json) captures back off disk -- written by an earlier online sync run, "
             "or copied into place from another machine -- and produces normalized/<game_code> "
             "from them using the exact same parsers the online path uses. Fails closed with a "
             "clear 'not found' error naming the missing raw path if a required capture isn't "
             "there; never fabricates normalized output for data that was never captured.",
    )
    sync_parser.set_defaults(func=cmd_sync)

    export_parser = sub.add_parser(
        "export-raw",
        help="Copy already-archived raw/<game_code>/* files byte-for-byte into one export bundle "
             "(for handing a real HTML sample to a developer). Read-only: no network, no parsing.",
    )
    export_parser.add_argument("--game-code", required=True, dest="game_code")
    export_parser.add_argument(
        "--raw-root", default=None, dest="raw_root",
        help="Override the raw/ root. Defaults to NEO_DATA_ROOT/raw if that env var is set, else klpga_pipeline/raw.",
    )
    export_parser.add_argument(
        "--only", default=None,
        help="Comma-separated filenames to export, e.g. course.html,history_record.html,pin_placement.html. "
             "Default: export every file actually present under raw/<game_code>/.",
    )
    export_parser.add_argument(
        "--out", default=None,
        help="Output directory (or, with --zip, the .zip file path). "
             "Default: raw/<game_code>/_export/, or exports/<game_code>_raw_export.zip with --zip.",
    )
    export_parser.add_argument("--zip", action="store_true", help="Produce a single .zip instead of a directory.")
    export_parser.add_argument("--season", type=int, default=None,
                                help="Only needed to run parsers (tournament_info needs it). "
                                     "Defaults to the gameCode's own leading 4 digits if omitted.")
    export_parser.add_argument("--skip-run", action="store_true", dest="skip_run",
                                help="Classify and bundle files only -- do not execute any parser/adapter.")
    export_parser.set_defaults(func=cmd_export_raw)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
