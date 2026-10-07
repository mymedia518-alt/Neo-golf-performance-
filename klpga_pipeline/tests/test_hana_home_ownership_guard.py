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


def test_home_page_output_never_references_the_kb_final_image(tmp_path, monkeypatch):
    """Builds the real homepage via its real script and inspects the
    generated HTML -- not the builder's own source text. Per later
    operator instruction, root HOME's leaderboard-table IS now expected
    (see test_hana_home_r1_data_consistency.py for the full R1-mirror
    contract); the one thing that must never appear, under either
    architecture, is the KB FINAL tournament's own result image.

    PRODUCTION-SAFETY (incident 2026-10-07, operator-flagged): this test
    used to call the real module.build() with module.DOCS_INDEX left
    pointed at the real, live docs/index.html -- 156 is Hana's (an
    OLDER, no-longer-current tournament's) HOME builder, and its own
    ownership-guard call passes allow_transfer_from=CURRENT_TOURNAMENT_
    OWNER (itself), which makes the guard a no-op against ANY other
    current-tournament-class owner, including whichever tournament (HJ
    2026100004, at the time of the incident) is actually current. This
    test running under a broad `pytest -k home` selection silently
    clobbered the real production HOME with Hana's stale template and
    that clobbered file was then accidentally committed. Redirecting
    module.DOCS_INDEX to a tmp_path BEFORE calling build() keeps this
    test exercising the exact same real content-generation code path
    while making it structurally impossible for it to touch the real
    file -- regardless of what the ownership guard does or doesn't catch."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_build_home_page", SCRIPTS_DIR / "156_build_home_page.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "DOCS_INDEX", tmp_path / "index.html")
    module.build()

    html = module.DOCS_INDEX.read_text(encoding="utf-8")
    assert "우승 (3).png" not in html and "kb-2026090003" not in html, (
        "docs/index.html must never reference the KB FINAL tournament image"
    )


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def test_real_production_home_carries_hj_game_code_marker():
    """Precondition for the guard test below: the real, committed
    docs/index.html must already carry HJ's own neo-home-game-code
    marker (embedded by build_tournament_archive_and_hj_scaffold.py's
    build_home()) -- if this ever stops being true, the guard test
    below would pass for the wrong reason (no marker to protect)."""
    from klpga.website_v2.home_ownership_guard import extract_game_code

    real_docs_index = REPO_ROOT / "docs" / "index.html"
    html = real_docs_index.read_text(encoding="utf-8")
    assert extract_game_code(html) == "2026100004"


def test_stale_hana_builder_cannot_clobber_real_production_home_once_hj_has_claimed_it():
    """Regression lock for the 2026-10-07 incident: reproduces the exact
    dangerous call -- importing scripts/156_build_home_page.py and
    calling its real build() against the REAL repo paths, with no
    tmp_path isolation at all -- and asserts it is now hard-blocked by
    the game-code-aware ownership guard (home_ownership_guard.
    assert_home_write_allowed's writer_game_code check), instead of
    silently clobbering the real file the way it did before this fix.
    Confirms both the raise AND that the real file is provably
    untouched (SHA256 identical before and after the blocked attempt)."""
    import importlib.util

    from klpga.website_v2.home_ownership_guard import HomeOwnershipError

    real_docs_index = REPO_ROOT / "docs" / "index.html"
    sha_before = _sha256(real_docs_index)

    spec = importlib.util.spec_from_file_location("_build_home_page_unisolated", SCRIPTS_DIR / "156_build_home_page.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with pytest.raises(HomeOwnershipError, match="game_code"):
        module.build()

    sha_after = _sha256(real_docs_index)
    assert sha_after == sha_before, (
        "the real docs/index.html must be byte-identical after a blocked "
        "stale-builder write attempt -- the guard must raise BEFORE any write"
    )
