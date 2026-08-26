"""Builds the static NEO GOLF PREDICTIONS public site from the
immutable prediction archive (`predictions/`). Read-only against the
archive (opens each `*.json` for reading only, via
`klpga.archive.prediction_archive.read_prediction_snapshot`), and
never opens the SQLite database or calls
`klpga.models.inference.run_inference` — the archived JSON is the
ONLY prediction source for this site. Writes only under `--output-dir`.

The generated site is a build artifact, not committed to git (see
docs/PREDICTIONS_SITE.md) — rerun this command whenever a new
prediction is archived, then redeploy `--output-dir`'s contents.

Usage:
    python scripts/25_build_predictions_site.py
    python scripts/25_build_predictions_site.py --predictions-dir predictions --output-dir web/dist

Local preview after building:
    python -m http.server 8000 --directory web/dist
    # then open http://localhost:8000/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.site.build import SiteBuildIntegrityError, build_site  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--predictions-dir", default=str(ROOT / "predictions"))
    parser.add_argument("--output-dir", default=str(ROOT / "web" / "dist"))
    args = parser.parse_args()

    predictions_dir = Path(args.predictions_dir)
    if not predictions_dir.exists():
        print(f"ERROR: {predictions_dir} does not exist.", file=sys.stderr)
        return 2

    try:
        result = build_site(predictions_dir, Path(args.output_dir))
    except SiteBuildIntegrityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Built {result.predictions_rendered} prediction page(s); latest = #{result.latest_prediction_id}")
    print(f"Output: {result.output_root}")
    for f in result.written_files:
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
