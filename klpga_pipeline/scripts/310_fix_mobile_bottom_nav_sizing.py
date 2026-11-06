"""Fix drastically oversized dimensions in the site-wide mobile bottom
navigation (docs/assets/neo-site.css, "NEO MOBILE BOTTOM NAV" block,
introduced in commit ee7dfb1b "Add mobile bottom navigation").

CONFIRMED REAL BUG (2026-11-06, reported by operator from a real
Android Chrome device, reproduced on the live-probability page but
present site-wide since every page shares this CSS file): each of the
6 bottom nav tabs rendered at min-height:210px with 2.8rem (44.8px)
label text and 3.7rem (59.2px) icon glyphs -- a single tab taller than
most phones' visible viewport minus content. This was never caught by
this session's own Playwright QA because headless Chromium's default
browser context does not set `pointer:coarse`/`hover:none`, so the
`@media (hover:none) and (pointer:coarse)` block (the file's current
selector, tightened at some point from the original commit's
`@media (max-device-width:700px)`) never activated in any screenshot
taken this session -- confirmed by deliberately emulating a real touch
device below.

Recalibrated to ordinary mobile bottom-tab-bar proportions (iOS/
Material reference range is ~48-64px total height): ~58px tab height,
~20px icon glyph, ~10px label -- a ~3.6x size reduction, not a redesign
(same grid-of-6, same icons, same active-state treatment, same safe-
area handling -- only the four numeric values that were out of scale
are changed).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT.parent / "docs" / "assets" / "neo-site.css"

REPLACEMENTS = [
    (
        "gap:.1rem;min-width:0;min-height:210px;padding:1rem .15rem 1.15rem;\n    font-size:2.8rem;line-height:1.15;text-align:center;",
        "gap:.1rem;min-width:0;min-height:52px;padding:.3rem .15rem .35rem;\n    font-size:.65rem;line-height:1.15;text-align:center;",
    ),
    (
        "display:block;color:var(--muted);font-size:3.7rem;line-height:1.1;font-weight:500;",
        "display:block;color:var(--muted);font-size:1.3rem;line-height:1.1;font-weight:500;",
    ),
    (
        'content:"";position:absolute;left:20%;right:20%;bottom:18px;height:6px;',
        'content:"";position:absolute;left:20%;right:20%;bottom:3px;height:2px;',
    ),
    (
        "main{padding-bottom:250px}",
        # Plain `main` ties in specificity with neo.css's own
        # @media(max-width:760px){main{padding:18px 16px}} -- which
        # loads AFTER this file in every page's <head> and so wins the
        # cascade on any ≤760px viewport (i.e. every real phone),
        # making the original padding-bottom:250px dead code all along
        # (the oversized nav was never actually being cleared). `body
        # main` (specificity 0,0,0,2) reliably wins over bare `main`
        # regardless of file order, so the real nav height is finally
        # accounted for.
        "body main{padding-bottom:64px}",
    ),
]


def main() -> None:
    css = CSS_PATH.read_text(encoding="utf-8")

    for old, new in REPLACEMENTS:
        count = css.count(old)
        if count != 1:
            raise RuntimeError(f"expected exactly 1 occurrence of {old!r}, found {count} -- refusing to patch")
        css = css.replace(old, new)

    CSS_PATH.write_text(css, encoding="utf-8")
    print(f"patched {CSS_PATH}: recalibrated 4 oversized mobile-bottom-nav values to normal tab-bar proportions")


if __name__ == "__main__":
    main()
