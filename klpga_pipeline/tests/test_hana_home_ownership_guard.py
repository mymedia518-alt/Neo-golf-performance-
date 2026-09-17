"""Tests for the "no round-page builder may ever write to root HOME"
guard (operator-flagged incident: an earlier scratchpad script had
overwritten docs/index.html directly from a round-page builder's own
output path, bypassing any dedicated homepage identity at all). root
HOME (www.neogolfdata.com / neogolfdata.com) has exactly one legitimate
writer, scripts/156_build_home_page.py -- per later, separate operator
instruction, 156 itself is free to render the current tournament's R1
leaderboard directly into root HOME (see
test_hana_home_r1_data_consistency.py for that contract); what this
guard prevents is any *other* script (151/R2/R3/FR builders, present
or future) writing to docs/index.html directly.

Two lines of defense, both exercised here:
1. klpga.website_v2.home_ownership_guard.assert_not_root_home() itself
   actually raises when pointed at root HOME and is a no-op for any
   other path -- the mechanism 151 (and any future R2/R3/FR builder)
   is expected to call.
2. A naming-convention-independent static scan of every script under
   klpga_pipeline/scripts/ for the literal docs/index.html output-path
   pattern -- this is the durable backstop: it catches ANY future
   script that writes root HOME, whichever filename it ends up with,
   without depending on that future author remembering to call (1)."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
KLPGA_ROOT = REPO_ROOT / "klpga_pipeline"
SCRIPTS_DIR = KLPGA_ROOT / "scripts"

_R1_PAGE_BUILDER = SCRIPTS_DIR / "151_build_hana_r1_page.py"


def test_assert_not_root_home_blocks_root_home_and_allows_everything_else(tmp_path):
    import sys

    sys.path.insert(0, str(KLPGA_ROOT / "src"))
    from klpga.website_v2.home_ownership_guard import HomeOwnershipError, assert_not_root_home

    fake_repo = tmp_path
    (fake_repo / "docs").mkdir()
    root_home = fake_repo / "docs" / "index.html"

    with pytest.raises(HomeOwnershipError, match="root HOME"):
        assert_not_root_home(root_home, repo_root=fake_repo)

    # A real round page's own stage path must never trip the guard.
    assert_not_root_home(fake_repo / "docs" / "tournaments" / "2026" / "2026090002" / "r1" / "index.html", repo_root=fake_repo)


def test_r1_page_builder_calls_the_root_home_guard():
    assert _R1_PAGE_BUILDER.is_file(), f"expected R1 page builder missing: {_R1_PAGE_BUILDER}"
    source = _R1_PAGE_BUILDER.read_text(encoding="utf-8")
    assert 'from klpga.website_v2.home_ownership_guard import assert_not_root_home' in source, (
        f"{_R1_PAGE_BUILDER.name} must import assert_not_root_home from "
        "klpga.website_v2.home_ownership_guard -- refusing to trust a same-named local shadow."
    )
    assert source.count("assert_not_root_home(") >= 2, (
        f"{_R1_PAGE_BUILDER.name} must call assert_not_root_home() both at module load "
        "(guards R1_PAGE as soon as it's defined) and again immediately before writing the "
        "page, so the guard can't be bypassed by reassigning the output path in between."
    )


def test_no_hana_script_other_than_156_writes_docs_index_html():
    """The durable, naming-independent backstop, scoped to this
    session's own Hana pipeline (other tournaments -- KB, TOP120, OK
    Open -- have their own separate, pre-existing, already-authorized
    root-HOME writers that are out of scope here and must not be
    touched): among every Hana-related script, only
    scripts/156_build_home_page.py may reference docs/index.html as an
    output path. If any other Hana script (present or future, whatever
    it ends up being named) starts targeting root HOME, this fails."""
    writers = []
    for script in SCRIPTS_DIR.glob("*.py"):
        if "hana" not in script.name.lower() and script.name != "156_build_home_page.py":
            continue
        source = script.read_text(encoding="utf-8")
        if '"docs" / "index.html"' in source or "'docs' / 'index.html'" in source:
            writers.append(script.name)
    assert writers == ["156_build_home_page.py"], (
        f"expected exactly scripts/156_build_home_page.py to reference docs/index.html as an "
        f"output path among Hana's own scripts, found: {writers}"
    )


def test_home_page_output_never_references_the_kb_final_image():
    """Builds the real homepage via its real script and inspects the
    actual generated docs/index.html -- not the builder's own source
    text. Per later operator instruction, root HOME's leaderboard-table
    IS now expected (see test_hana_home_r1_data_consistency.py for the
    full R1-mirror contract); the one thing that must never appear,
    under either architecture, is the KB FINAL tournament's own result
    image."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_build_home_page", SCRIPTS_DIR / "156_build_home_page.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build()

    html = module.DOCS_INDEX.read_text(encoding="utf-8")
    assert "우승 (3).png" not in html and "kb-2026090003" not in html, (
        "docs/index.html must never reference the KB FINAL tournament image"
    )
