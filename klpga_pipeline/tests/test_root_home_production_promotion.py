"""ROOT HOME RECOVERY regression coverage
(scripts/111_promote_top120_root_home_only.py).

The failure this locks in: an earlier task merged the mobile HOME
color/readability work all the way to the neo-website-v2 branch and
had it build successfully on GitHub Pages, then reported the feature
as shipped -- without ever checking that the actual Pages-served
docs/index.html contained it. It didn't: the feature existed only in
klpga_pipeline/candidate/, and docs/ was still serving unrelated,
older content. A production promotion must never be considered
successful on candidate evidence alone -- every test below asserts
against the production-bound docs/ tree itself, never candidate/.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DOCS = REPO_ROOT / "docs"

sys.path.insert(0, str(ROOT / "src"))
from klpga.website_v2.home_ownership_guard import (  # noqa: E402
    CURRENT_TOURNAMENT_OWNER,
    TOP120_OWNER,
    HomeOwnershipError,
    embed_owner,
)


def _load_promotion_module():
    path = ROOT / "scripts" / "111_promote_top120_root_home_only.py"
    spec = importlib.util.spec_from_file_location("root_home_promotion", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ---------------------------------------------------------------------
# The production-bound output itself (not candidate/) -- the exact gap
# the earlier task's "feature is live" claim was wrong about.
# ---------------------------------------------------------------------

def test_production_docs_root_home_actually_contains_the_feature():
    """This is the check that was skipped before: read docs/index.html
    itself (what GitHub Pages actually serves), not
    candidate/neo-data-home-top120/index.html (what the earlier task
    verified instead)."""
    home = (DOCS / "index.html").read_text(encoding="utf-8")
    assert 'content="top120-v1"' in home
    assert home.count("data-player-row") == 120
    assert home.count('class="player-name"') == 120
    assert len([m for m in home.split('class="player-sponsor"') if True]) - 1 > 0
    assert "metric-sg" in home
    assert "k-rank-cell" in home
    assert "999999" not in home


def test_production_docs_root_home_has_mobile_breakpoint_css():
    css = (DOCS / "assets" / "neo-site.css").read_text(encoding="utf-8")
    assert "@media(max-width:760px)" in css
    assert ".home-table tbody tr{" in css


def test_production_kb_tournament_routes_survived_the_root_home_change():
    """STEP 5 tournament-route-safety: promoting root HOME back to
    TOP120 must never regress the live KB PRE/R1 pages sitting at their
    own route."""
    for stage in ("pre", "r1"):
        page = DOCS / "tournaments" / "2026" / "2026090003" / stage / "index.html"
        html = page.read_text(encoding="utf-8")
        assert "KB금융 골든라이프 챔피언십" in html
        assert html != ""


def test_production_lockdown_routes_still_placeholder_after_root_home_change():
    """The narrow root-HOME-only promotion must never leak the
    candidate's real ranking/about/deep-dive/neo-lab/tournament-hub
    content into docs/ -- those stay under apply_public_site_lockdown.py's
    approved-routes-only policy."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import apply_public_site_lockdown as lockdown  # noqa: E402

    assert lockdown.verify_lockdown() == []
    for rel in lockdown.LOCKED_HTML_PATHS:
        assert (DOCS / rel).read_text(encoding="utf-8") == lockdown.PLACEHOLDER_HTML


# ---------------------------------------------------------------------
# The promotion function itself, in isolation (tmp_path)
# ---------------------------------------------------------------------

@pytest.fixture()
def promotion_module():
    return _load_promotion_module()


def _top120_home_html(owner: str = TOP120_OWNER) -> str:
    return embed_owner(
        '<!doctype html><html lang="ko"><head><title>K-Ranking TOP120</title></head>'
        '<body><div data-player-row="1" class="player-name">x</div></body></html>',
        owner,
    )


def _valid_home_css() -> str:
    return (
        "@media(max-width:760px){.home-table tbody tr{display:grid}}"
        ".metric-sg{}.k-rank-cell{}.metric-pos{}.metric-neg{}.metric-empty{}"
    )


def _wire_promotion_paths(promotion_module, monkeypatch, tmp_path, *, css: str | None = _valid_home_css()):
    """Sets up an isolated candidate/docs tree and points every module-
    level path constant at it, so promote_root_home_only() can be
    exercised without touching the real repo."""
    candidate_root = tmp_path / "candidate_root"
    (candidate_root / "assets").mkdir(parents=True)
    docs = tmp_path / "docs"
    (docs / "assets").mkdir(parents=True)

    css_source = candidate_root / "assets" / "neo-site.css"
    if css is not None:
        css_source.write_text(css, encoding="utf-8")
    css_dest = docs / "assets" / "neo-site.css"

    monkeypatch.setattr(promotion_module, "CANDIDATE", candidate_root)
    monkeypatch.setattr(promotion_module, "SOURCE", candidate_root / "index.html")
    monkeypatch.setattr(promotion_module, "DEST", docs / "index.html")
    monkeypatch.setattr(promotion_module, "CSS_SOURCE", css_source)
    monkeypatch.setattr(promotion_module, "CSS_DEST", css_dest)
    monkeypatch.setattr(promotion_module, "REPO_ROOT", tmp_path)
    return candidate_root, docs


def test_promotion_refuses_when_candidate_owner_is_not_top120_owner(tmp_path, promotion_module, monkeypatch):
    candidate_root, docs = _wire_promotion_paths(promotion_module, monkeypatch, tmp_path)
    promotion_module.SOURCE.write_text(_top120_home_html(owner="some-other-owner"), encoding="utf-8")

    with pytest.raises(promotion_module.RootHomePromotionError):
        promotion_module.promote_root_home_only()
    assert not promotion_module.DEST.exists()


def test_promotion_refuses_when_candidate_css_is_missing_required_home_rules(tmp_path, promotion_module, monkeypatch):
    """A broken/incomplete stylesheet must never be promoted -- this is
    the exact class of gap that left docs/assets/neo-site.css stale and
    the mobile color feature invisible on production despite
    docs/index.html itself carrying the right markup."""
    _wire_promotion_paths(promotion_module, monkeypatch, tmp_path, css="body{color:red}")
    promotion_module.SOURCE.write_text(_top120_home_html(), encoding="utf-8")

    with pytest.raises(promotion_module.RootHomePromotionError, match="missing required HOME rule"):
        promotion_module.promote_root_home_only()
    assert not promotion_module.DEST.exists()
    assert not promotion_module.CSS_DEST.exists()


def test_promotion_refuses_when_existing_owner_is_not_the_anticipated_transfer_source(tmp_path, promotion_module, monkeypatch):
    """assert_home_write_allowed's allow_transfer_from is scoped to
    exactly CURRENT_TOURNAMENT_OWNER -- an unrelated third owner must
    still hard-stop, never be silently overwritten."""
    candidate_root, docs = _wire_promotion_paths(promotion_module, monkeypatch, tmp_path)
    promotion_module.SOURCE.write_text(_top120_home_html(owner=TOP120_OWNER), encoding="utf-8")
    promotion_module.DEST.write_text(embed_owner("<html></html>", "some-unrelated-owner"), encoding="utf-8")

    with pytest.raises(promotion_module.RootHomePromotionError):
        promotion_module.promote_root_home_only()
    assert "some-unrelated-owner" in promotion_module.DEST.read_text(encoding="utf-8")


def test_promotion_succeeds_transferring_from_current_tournament_owner(tmp_path, promotion_module, monkeypatch):
    candidate_root, docs = _wire_promotion_paths(promotion_module, monkeypatch, tmp_path)
    promotion_module.SOURCE.write_text(_top120_home_html(owner=TOP120_OWNER), encoding="utf-8")
    promotion_module.DEST.write_text(embed_owner("<html>old KB content</html>", CURRENT_TOURNAMENT_OWNER), encoding="utf-8")

    previous_owner = promotion_module.promote_root_home_only()
    assert previous_owner == CURRENT_TOURNAMENT_OWNER
    written = promotion_module.DEST.read_text(encoding="utf-8")
    assert 'content="top120-v1"' in written
    assert "old KB content" not in written
    assert promotion_module.CSS_DEST.read_text(encoding="utf-8") == _valid_home_css()


def test_promotion_writes_nothing_else(tmp_path, promotion_module, monkeypatch):
    """The whole point of this script over scripts/94: it touches
    exactly index.html and assets/neo-site.css."""
    candidate_root, docs = _wire_promotion_paths(promotion_module, monkeypatch, tmp_path)
    promotion_module.SOURCE.write_text(_top120_home_html(), encoding="utf-8")
    (candidate_root / "ranking.html").write_text("should never be touched", encoding="utf-8")
    (docs / "ranking.html").write_text("locked placeholder", encoding="utf-8")
    (docs / "assets" / "neo.css").write_text("unrelated, untouched", encoding="utf-8")

    promotion_module.promote_root_home_only()
    assert (docs / "ranking.html").read_text(encoding="utf-8") == "locked placeholder"
    assert (docs / "assets" / "neo.css").read_text(encoding="utf-8") == "unrelated, untouched"
