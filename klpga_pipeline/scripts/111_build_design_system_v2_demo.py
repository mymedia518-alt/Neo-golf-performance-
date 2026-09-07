"""NEO SITE V5 Mission 1 proof-of-concept: migrate the ABOUT page (matrix
classification B) to the HOME V4 site-wide design system, demonstrating
content/presentation separation for real.

ABOUT's body content comes from the SAME, unmodified _about() function
migration.py's production candidate pipeline already uses (imported
here, not copied/reimplemented) -- this script changes ONLY which shell
wraps that content (render_page(..., design_system="v2") instead of the
default "v1"). The factual/content HTML this script emits inside <main>
is therefore byte-identical to what the existing v1 candidate pipeline
produces for the same page; only the header/nav/stylesheet chrome
differs. This script writes to its own candidate/ directory -- it does
not touch candidate/neo-data-home-top120/ (the real v1 candidate tree)
or docs/ (production).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.migration import _about  # noqa: E402
from klpga.website_v2.shell import render_page  # noqa: E402

OUTPUT = ROOT / "candidate" / "neo-site-v5-design-system-demo"


def build() -> Path:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    (OUTPUT / "about").mkdir()
    (OUTPUT / "about" / "index.html").write_text(
        render_page(title="NEO 소개", active_section="about", body_html=_about(), design_system="v2"),
        encoding="utf-8", newline="\n",
    )

    assets = OUTPUT / "assets"
    assets.mkdir()
    static = ROOT / "src" / "klpga" / "website_v2" / "static"
    for name in ("neo-design-system.css", "neo-site.css", "neo-site.js", "home-v4.js"):
        shutil.copyfile(static / name, assets / name)

    print(f"WROTE design-system-v2 demo: {OUTPUT / 'about' / 'index.html'}")
    return OUTPUT


if __name__ == "__main__":
    build()
