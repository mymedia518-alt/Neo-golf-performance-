"""R2 HOUSE (P0-1): sync neo.css's ONE real source -- the `CSS` string
literal in scripts/84_build_ok_open_pre_website_candidate.py -- out to
every already-existing byte-for-byte mirror (docs/assets/neo.css plus
the three candidate/*/assets/neo.css copies), the same static-asset
copy-forward convention scripts 86/88/111 already use for this exact
file (see r2_sg_pipeline.py-adjacent archaeology in R2 HOUSE's own
history: neo.css has no template-regeneration step, it is carried
forward by copyfile).

Deliberately NARROW: this script extracts and re-copies ONLY the CSS
string (regex, never imports/executes script 84 -- that file has other
top-level side effects unrelated to CSS) -- it does not re-run the
OK-Open/KB PRE/R1 content-generation pipeline, so it cannot touch any
dynamic page content, only this one shared stylesheet asset. The new
rules added for the R2 HOUSE real-data renderer (P0-1) are purely
additive (a new .leaderboard-table--r2-full modifier class + one new
.metric-empty rule) -- every existing selector is byte-identical to
before, so this sync cannot regress any already-live PRE/R1/KG/OK Open
page.

Idempotent: reports "unchanged" for a target that already matches.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
PIPELINE_ROOT = SCRIPTS_DIR.parent
REPO_ROOT = PIPELINE_ROOT.parent
SOURCE_SCRIPT = SCRIPTS_DIR / "84_build_ok_open_pre_website_candidate.py"

TARGETS = [
    REPO_ROOT / "docs" / "assets" / "neo.css",
    PIPELINE_ROOT / "candidate" / "neo-data-home" / "assets" / "neo.css",
    PIPELINE_ROOT / "candidate" / "neo-data-home-top120" / "assets" / "neo.css",
    PIPELINE_ROOT / "candidate" / "website-v2-ok-open-pre" / "assets" / "neo.css",
]

CSS_RE = re.compile(r'^CSS = """\n(.*)\n"""\n', re.DOTALL | re.MULTILINE)


def extract_css() -> str:
    source_text = SOURCE_SCRIPT.read_text(encoding="utf-8")
    match = CSS_RE.search(source_text)
    if not match:
        raise ValueError(f"could not locate CSS = \"\"\"...\"\"\" block in {SOURCE_SCRIPT}")
    return match.group(1)


def sync() -> dict:
    css = extract_css()
    results = {}
    for target in TARGETS:
        # docs/assets/neo.css historically carries no leading blank
        # line; the three candidate/ mirrors carry one (the CSS
        # string's own leading "\n" after `"""`) -- preserve each
        # target's own existing convention rather than forcing a
        # cosmetic-only diff onto files this script isn't meant to
        # reformat.
        before = target.read_text(encoding="utf-8") if target.is_file() else None
        leading_blank = before is not None and before.startswith("\n")
        new_content = ("\n" + css + "\n") if leading_blank else (css + "\n")
        if before == new_content:
            results[str(target)] = "unchanged"
            continue
        target.write_text(new_content, encoding="utf-8", newline="\n")
        results[str(target)] = "updated"
    return results


def main() -> int:
    import json

    print(json.dumps(sync(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
