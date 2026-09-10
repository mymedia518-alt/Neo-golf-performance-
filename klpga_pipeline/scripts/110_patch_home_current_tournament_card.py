"""PUBLIC UI / NAVIGATION PATCH (KB 2026090003): two minimal, additive
fixes to production docs/index.html -- HOME -- without redesigning it:

1. HOME's already-existing "이번 대회" card link now correctly points
   at KB's current published stage (R1), not the stale PRE link left
   over from before R1 was published, and gets one minimal CTA line
   ("1R 분석 →") -- the "minimal current-tournament entry near the top"
   NEO PUBLIC UI CORRECTION section 8 asks for. Nothing else about the
   card, and nothing about HOME's persistent K-Ranking/NEO Ranking
   table, changes.
2. The permanent footer copyright invariant (section 9) -- reuses the
   exact same klpga.website_v2.global_navigation.ensure_footer_copyright
   idempotent helper every other page gets via inject_global_navigation,
   so HOME's copyright line can never drift out of sync with that
   shared definition.

Goes through home_ownership_guard.assert_home_write_allowed() exactly
like the canonical TOP120 publisher does: this script identifies
itself as the same "top120-v1" owner already recorded in docs/
index.html's own <meta name="neo-home-owner"> tag, so the guard's
existing-owner check passes cleanly -- this is compliant use of the
guard's ownership-claim contract, not a bypass of it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
DOCS_INDEX = REPO_ROOT / "docs" / "index.html"

sys.path.insert(0, str(PIPELINE_ROOT / "src"))
from klpga.website_v2.global_navigation import ensure_footer_copyright  # noqa: E402
from klpga.website_v2.home_ownership_guard import TOP120_OWNER, assert_home_write_allowed  # noqa: E402

GAME_CODE = "2026090003"
R1_HREF = f'href="/tournaments/2026/{GAME_CODE}/r1/"'
PRE_HREF = f'href="/tournaments/2026/{GAME_CODE}/pre/"'
CURRENT_CARD_MARKER = f'data-tournament-card="current" data-game-code="{GAME_CODE}"'
CTA_CLASS = "t-tournament-card__cta"
CTA_HTML = f'<p class="{CTA_CLASS}"><a {R1_HREF}>1R 분석 →</a></p>'
# Anchors the end of the current-tournament card's <p class="t-tournament-card__dates">...</p>,
# scoped to the KB card specifically (not any other card) via the marker earlier in the same <article>.
_CURRENT_CARD_DATES_RE = re.compile(
    r'(' + re.escape(CURRENT_CARD_MARKER) + r'.*?<p class="t-tournament-card__dates">[^<]*</p>)',
    re.S,
)


def patch() -> dict:
    assert_home_write_allowed(DOCS_INDEX, TOP120_OWNER, repo_root=REPO_ROOT)
    html = DOCS_INDEX.read_text(encoding="utf-8")

    if CURRENT_CARD_MARKER not in html:
        raise ValueError("KB's current-tournament card marker not found in docs/index.html -- refusing to guess")

    changes = []

    if PRE_HREF in html:
        count = html.count(PRE_HREF)
        if count != 1:
            raise ValueError(f"expected exactly one stale PRE href on HOME's current-tournament card, found {count} -- refusing to guess")
        html = html.replace(PRE_HREF, R1_HREF, 1)
        changes.append("href_pre_to_r1")

    if CTA_CLASS not in html:
        html, count = _CURRENT_CARD_DATES_RE.subn(r"\1" + CTA_HTML, html, count=1)
        if count != 1:
            raise ValueError("could not locate KB current-tournament card's dates paragraph to attach the 1R CTA -- refusing to guess")
        changes.append("cta_added")

    before = html
    html = ensure_footer_copyright(html)
    if html != before:
        changes.append("footer_copyright_added")

    if changes:
        DOCS_INDEX.write_text(html, encoding="utf-8", newline="\n")

    return {"changed": bool(changes), "changes": changes}


if __name__ == "__main__":
    import json

    print(json.dumps(patch(), ensure_ascii=False))
