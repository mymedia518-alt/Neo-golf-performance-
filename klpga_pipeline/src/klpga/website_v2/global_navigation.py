"""Shared, mobile-visible navigation and safe public-page normalization."""
from __future__ import annotations

import re

NAVIGATION_MARKER = "data-neo-global-navigation"

# GLOBAL UI/UX REBUILD -- single source of the brand lockup and nav item
# list. Every route's header is produced by _navigation_html() below (see
# inject_global_navigation()) so there is exactly one place that can ever
# define what "NEO" looks like or which section is active.
#
# The default "대회" destination stays the generic /tournaments/ hub --
# this constant is shared by every build in the repo, including isolated
# per-tournament/candidate builds and test fixtures that have no
# knowledge of, and no route for, whichever tournament happens to be
# currently live in production. A caller that needs "대회" to route to a
# specific currently-published stage (e.g. scripts/109_build_kb_r1_page.py
# routing it to KB's R1 page while KB is the only real public tournament
# content) passes nav_overrides={"tournaments": "<url>"} to
# inject_global_navigation()/navigation_html() instead of changing this
# shared default -- see PUBLICATION FIX (KB 2026090003).
GLOBAL_NAV_ITEMS = (
    ("home", "홈", "/"),
    ("tournaments", "대회", "/tournaments/"),
    ("ranking", "랭킹", "/ranking/"),
    ("deep-dive", "딥다이브", "/deep-dive/"),
    ("neo-lab", "NEO LAB", "/neo-lab/"),
    ("about", "소개", "/about/"),
)

# PUBLIC UI Phase 8 -- the one immutable brand lockup every public page
# must show in its top-left brand area: the "NEO GOLF DATA" wordmark,
# then NUMBER / EVIDENCE / ORACLE stacked one per line underneath (never
# abbreviated to single letters, never run together on one line -- that
# was the literal P0 FAIL example in the v3 UI/UX spec, "NEONumber ·
# Evidence · Oracle"). The retired "KLPGA PERFORMANCE TERMINAL" tagline
# is never part of this lockup. Real newlines between child elements are
# deliberate significant whitespace text nodes, so even with no
# stylesheet loaded the unstyled rendering still reads as separate words
# instead of one unreadable run-on string.
_BRAND_HTML = '''<a class="neo-global-brand" href="/">
<span class="neo-brand-mark">NEO GOLF DATA</span>
<span class="neo-brand-legend">
<span class="neo-brand-legend__item">NUMBER</span>
<span class="neo-brand-legend__item">EVIDENCE</span>
<span class="neo-brand-legend__item">ORACLE</span>
</span>
</a>'''


def _nav_html(active_section: str | None, nav_overrides: dict[str, str] | None = None) -> str:
    overrides = nav_overrides or {}
    links = []
    for key, label, url in GLOBAL_NAV_ITEMS:
        url = overrides.get(key, url)
        if key == active_section:
            links.append(f'<a href="{url}" class="is-active" aria-current="page">{label}</a>')
        else:
            links.append(f'<a href="{url}">{label}</a>')
    return '<nav class="neo-global-nav" aria-label="주요 메뉴">\n' + "\n".join(links) + '\n</nav>'


def navigation_html(active_section: str | None = None, nav_overrides: dict[str, str] | None = None) -> str:
    """The one canonical header, optionally with a section marked active
    and/or a per-call nav_overrides={item_key: url} override (see
    GLOBAL_NAV_ITEMS's own docstring for why this is an override, not a
    change to the shared default)."""
    return (f'<header class="neo-global-header" {NAVIGATION_MARKER}>\n'
            f'<div class="neo-global-header__inner">\n{_BRAND_HTML}\n{_nav_html(active_section, nav_overrides)}\n</div></header>')


# Back-compat constant: the no-active-section rendering, still used by any
# caller that has not been updated to pass an active_section explicitly.
NAVIGATION_HTML = navigation_html(None)

# Correctly-encoded, well-formed compatibility footer: a screen-reader
# only (not visually rendered -- see .sr-data in neo-site.css) fallback
# link set duplicating the four nav destinations, each a complete
# <a href="...">...</a> element. A prior version of this constant held
# a mis-encoded literal (CP949 bytes saved into a UTF-8-declared file)
# with dangling href="..." fragments outside any opening <a> tag; every
# generated page inherited that mojibake. Kept as a single named
# constant, used in both call sites below, so the two copies cannot
# drift out of sync again. Visually hidden (not merely a second visible
# "NEO GOLF DATA" link stacked under the real footer) per the v3 design
# pass -- repeating the brand name at the very bottom of every page
# read as leftover/placeholder chrome, not real content.
def _compatibility_marker_html(nav_overrides: dict[str, str] | None = None) -> str:
    tournaments_url = (nav_overrides or {}).get("tournaments", "/tournaments/")
    return ('<nav class="sr-data" aria-label="추가 탐색 링크">'
        '<a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        f'<a href="{tournaments_url}">대회</a> '
        '<a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>')


# Back-compat constant: the no-overrides rendering, still used by any
# caller that has not been updated to pass nav_overrides explicitly.
_COMPATIBILITY_MARKER = _compatibility_marker_html()

# FOOTER COPYRIGHT INVARIANT (permanent, all public pages): every real
# public page must carry this line somewhere in its footer -- see
# ensure_footer_copyright() below, called from inject_global_navigation()
# so every page that already goes through the one shared header pass
# also gets this for free, with no per-page/per-script edits required.
FOOTER_COPYRIGHT_CLASS = "site-footer__copyright"
FOOTER_COPYRIGHT_TEXT = "© 2026 NEO GOLF DATA. All Rights Reserved."
FOOTER_COPYRIGHT_HTML = f'<p class="{FOOTER_COPYRIGHT_CLASS}">{FOOTER_COPYRIGHT_TEXT}</p>'
_SITE_FOOTER_RE = re.compile(r'(<footer class="site-footer"><div class="site-footer__inner">)(.*?)(</div></footer>)', re.S)


def ensure_footer_copyright(html: str) -> str:
    """Idempotent: if the copyright line is already present, no-op. If a
    real <footer class="site-footer"> wrapper exists, the copyright line
    is appended inside it (any existing tagline, e.g. "NEO · Number ·
    Evidence · Oracle", is left untouched -- this only ADDS the
    copyright, never replaces a page's own footer text). If no such
    footer exists yet on this page at all, a minimal stand-alone one is
    inserted before </body>."""
    if FOOTER_COPYRIGHT_CLASS in html:
        return html
    html, count = _SITE_FOOTER_RE.subn(
        lambda m: m.group(1) + m.group(2) + FOOTER_COPYRIGHT_HTML + m.group(3),
        html, count=1,
    )
    if count == 1:
        return html
    minimal_footer = f'<footer class="site-footer"><div class="site-footer__inner">{FOOTER_COPYRIGHT_HTML}</div></footer>'
    return html.replace("</body>", minimal_footer + "</body>", 1)

# Two deliberately separate fields -- not one, and not a single SHA
# claiming to name "this build's own commit".
#
# A build always happens BEFORE the commit that promotes+ships it exists
# (build -> promote -> commit, in that order), so the git SHA available
# at build time (`git rev-parse HEAD`) can only ever be the PARENT of the
# commit that actually ships this HTML -- embedding it under a name that
# implies self-identity (the old "neo-build-source-sha") is misleading:
# it will structurally read as "one commit behind" forever, on every
# single promotion, even when the deployment is perfectly fresh. There
# is no fix that embeds a commit's own hash inside itself (the hash is a
# hash of the content, including that field) -- so this contract does
# not pretend to solve that. Instead:
#   - neo-build-source-commit: honestly labeled as the PARENT commit --
#     "the commit this build's source code was checked out from", not
#     "this build's commit". Useful for a human tracing lineage, not for
#     an automated commit == source-commit equality check.
#   - neo-build-id: a separate, non-git, self-consistent identifier for
#     THIS specific build/promotion event (a UTC timestamp). Every page
#     produced by the same build carries the identical value, so a
#     verifier can confirm "is the page I'm looking at from the build I
#     just ran" (build_id equality) without needing it to equal any git
#     commit hash at all.
BUILD_SOURCE_COMMIT_META_NAME = "neo-build-source-commit"
BUILD_ID_META_NAME = "neo-build-id"
# Back-compat alias, still exported: the historical, misleadingly-named
# constant some older call sites/tests may still reference.
BUILD_SHA_META_NAME = BUILD_SOURCE_COMMIT_META_NAME


# Matches every provenance <meta> tag this function has ever emitted,
# across every naming scheme that has existed: the retired single-field
# "neo-build-source-sha", and the current pair. Stripped before a fresh
# pair is inserted -- see inject_build_provenance() below for why this
# matters: it is NOT just cosmetic dedup.
_PROVENANCE_META_RE = re.compile(
    r'<meta name="(?:neo-build-source-sha|neo-build-source-commit|neo-build-id)" content="[^"]*">'
)


def inject_build_provenance(html: str, source_commit: str, build_id: str) -> str:
    """Embed two non-visible <meta> markers: the parent commit this
    build's source came from, and a build-id unique to this specific
    build/promotion event (see BUILD_SOURCE_COMMIT_META_NAME/
    BUILD_ID_META_NAME docs above for why these are two separate,
    honestly-scoped fields rather than one self-referential commit SHA).
    Never shown in the UI -- exists so a later QA pass can ask "what
    build is this live page actually serving" by fetching the page and
    reading the tags, rather than trusting that a git push implies a
    deployed page.

    Idempotent by construction: any provenance tag(s) already present
    (from this or an earlier build, under this or the retired naming
    scheme) are stripped first. Most pages are regenerated from scratch
    every build and never had a stale tag to strip -- but KG R1/R2 are
    hand-maintained files carried forward via a docs/ -> candidate/
    copytree every build, so without this a live-inspected red-team
    audit found this function had been blindly *prepending* a new tag
    on top of the old one, build after build: docs/tournaments/2026/
    kg-ladies-open/r1/index.html had accumulated two different stale
    neo-build-source-sha tags with two different values before this fix."""
    html = _PROVENANCE_META_RE.sub("", html)
    tag = (f'<meta name="{BUILD_SOURCE_COMMIT_META_NAME}" content="{source_commit}">'
           f'<meta name="{BUILD_ID_META_NAME}" content="{build_id}">')
    if "<head>" in html:
        return html.replace("<head>", f"<head>{tag}", 1)
    if "<head " in html:
        idx = html.index("<head ")
        close = html.index(">", idx) + 1
        return html[:close] + tag + html[close:]
    return tag + html

def _repair_legacy_mojibake(html: str) -> str:
    try:
        return html.encode("cp949").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return html

def inject_global_navigation(html: str, active_section: str | None = None, nav_overrides: dict[str, str] | None = None) -> str:
    """Normalize retained HTML and inject one consistent global nav.

    active_section marks which of GLOBAL_NAV_ITEMS is "here" (aria-current
    + a visible active state) -- see navigation_html(). Callers that don't
    know their section yet can omit it; the header is still refreshed to
    the current canonical markup, just with no link marked active.

    nav_overrides={item_key: url} overrides one or more GLOBAL_NAV_ITEMS
    destinations for THIS call only (see that constant's own docstring) --
    e.g. a page that must route "대회" to a specific currently-published
    tournament stage instead of the generic hub, without changing where
    every other build/page's "대회" link points.
    """
    html = _repair_legacy_mojibake(html)
    canonical_header = navigation_html(active_section, nav_overrides)
    compat_marker = _compatibility_marker_html(nav_overrides)
    replacements = {
        ">HOME</a>": ">홈</a>", ">TOURNAMENTS</a>": ">대회</a>",
        ">DEEP DIVE</a>": ">딥다이브</a>", ">ABOUT</a>": ">소개</a>",
        "TOURNAMENTS · NEO GOLF DATA": "대회 · NEO GOLF DATA",
        "DEEP DIVE · NEO GOLF DATA": "딥다이브 · NEO GOLF DATA",
        "ABOUT NEO GOLF DATA": "NEO GOLF DATA 소개", "About NEO GOLF DATA": "NEO GOLF DATA 소개",
        "NEXT UPDATE": "다음 업데이트", "3라운드 진행중": "대회 종료",
        "다음 업데이트 예정": "대회 종료", "R3 진행중": "3라운드 종료",
    }
    for source, replacement in replacements.items():
        html = html.replace(source, replacement)
    html = html.replace('href="/predictions/"', 'href="/tournaments/"')
    # Closed KG event pages must not retain stale live-update copy.
    # Matches every next-update-* class variant seen across the site's
    # several page templates (label/text/value etc.), not just the two
    # names one generator happens to use -- a class-name mismatch here
    # previously let "3R 종료 후 업데이트 예정" survive untouched on the
    # R2 production-page template.
    html = re.sub(r'(<[^>]*class="[^"]*next-update-label[^"]*"[^>]*>).*?(</[^>]+>)', r'\1대회 종료\2', html, flags=re.I|re.S)
    html = re.sub(r'(<[^>]*class="[^"]*next-update-(?:text|value)[^"]*"[^>]*>).*?(</[^>]+>)', r'\1최종 결과 보존\2', html, flags=re.I|re.S)
    if NAVIGATION_MARKER in html:
        # A marked header is never trusted as "already correct" -- it is
        # always refreshed to the current canonical NAVIGATION_HTML, even
        # if a header was already present (whether a page-specific one a
        # generator wrote itself, or a stale header injected by an
        # earlier version of this function on a previous build). Without
        # this, a copied/carried-forward page (KG R1/R2, which never
        # regenerate their own header) stays frozen at whatever brand
        # text NAVIGATION_HTML happened to be the first time it was
        # stamped, silently drifting out of sync with every other page
        # as this constant evolves -- exactly the "multiple header
        # systems" defect found in v3 Phase 3.
        html, count = re.subn(
            r"<header[^>]*" + re.escape(NAVIGATION_MARKER) + r"[^>]*>.*?</header>",
            canonical_header.replace("\\", "\\\\"), html, count=1, flags=re.S,
        )
        if count != 1:
            raise ValueError("marked header present but could not be matched for refresh")
        if 'href="/">NEO GOLF DATA</a>' not in html:
            html = html.replace('</body>', compat_marker + '</body>', 1)
        else:
            # Same "never trusted as already correct" rule as the header
            # above: an existing compatibility marker is refreshed in
            # place, not left frozen at whatever it happened to read the
            # first time this page was stamped -- otherwise its own
            # "대회" link (a second, separate copy of the destination the
            # visible nav link above just refreshed) silently drifts out
            # of sync on every subsequent nav change.
            html, marker_count = re.subn(
                r'<nav class="sr-data"[^>]*>.*?</nav>',
                compat_marker.replace("\\", "\\\\"),
                html, count=1, flags=re.S,
            )
            if marker_count != 1:
                raise ValueError("compatibility marker present but could not be matched for refresh")
        return ensure_footer_copyright(html)
    # No separate stylesheet is injected here: every real page template
    # already links /assets/neo-site.css itself (the one stylesheet that
    # actually styles .neo-global-header), so a second, drifting copy
    # (the retired assets/navigation.css) is not needed -- that file used
    # to get linked here and then never cleaned up on later builds
    # (later builds only refresh the <header> element, not the rest of
    # <head>), leaving a stale reference to CSS containing classes
    # (.neo-brand-sub) no current markup even uses.
    rendered, count = re.subn(r"(<body[^>]*>)", rf"\1{canonical_header}", html, count=1, flags=re.IGNORECASE)
    if count == 0:
        rendered, count = re.subn(r"(<header(?:\s|>))", rf"{canonical_header}\1", html, count=1, flags=re.IGNORECASE)
    if count != 1:
        raise ValueError("public HTML must contain an opening body or header element")
    return ensure_footer_copyright(rendered.replace('</body>', compat_marker + '</body>', 1))
