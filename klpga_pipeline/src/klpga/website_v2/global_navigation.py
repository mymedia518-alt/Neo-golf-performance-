"""Shared, mobile-visible navigation and safe public-page normalization."""
from __future__ import annotations

import re

NAVIGATION_MARKER = "data-neo-global-navigation"

# GLOBAL UI/UX REBUILD -- single source of the brand lockup and nav item
# list. Every route's header is produced by _navigation_html() below (see
# inject_global_navigation()) so there is exactly one place that can ever
# define what "NEO" looks like or which section is active.
GLOBAL_NAV_ITEMS = (
    ("home", "홈", "/"),
    ("tournaments", "대회", "/tournaments/"),
    ("deep-dive", "딥다이브", "/deep-dive/"),
    ("about", "소개", "/about/"),
)

# The brand is one lockup -- "NEO" plus a compact N/E/O legend spelling out
# Number / Evidence / Oracle -- not four lines of plain text (styled in
# neo-site.css: .neo-brand-legend is hidden entirely on mobile, the
# "compact variant"). Number/Evidence/Oracle are kept in English per spec.
# Real newlines between child elements are deliberate: they are
# significant *whitespace* text nodes, so if the stylesheet ever fails to
# load, the browser's default (unstyled) rendering still reads as
# "NEO Number Evidence Oracle" / "홈 대회 딥다이브 소개" instead of every
# label running together into one unreadable word -- the literal P0 FAIL
# example in the v3 UI/UX spec ("NEONumber · Evidence · Oracle").
_BRAND_HTML = '''<a class="neo-global-brand" href="/">
<span class="neo-brand-mark">NEO</span>
<span class="neo-brand-legend" aria-hidden="true">
<span class="neo-brand-legend__item"><b>N</b>Number</span>
<span class="neo-brand-legend__item"><b>E</b>Evidence</span>
<span class="neo-brand-legend__item"><b>O</b>Oracle</span>
</span>
<span class="sr-data">&mdash; Number, Evidence, Oracle</span>
</a>'''


def _nav_html(active_section: str | None) -> str:
    links = []
    for key, label, url in GLOBAL_NAV_ITEMS:
        if key == active_section:
            links.append(f'<a href="{url}" class="is-active" aria-current="page">{label}</a>')
        else:
            links.append(f'<a href="{url}">{label}</a>')
    return '<nav class="neo-global-nav" aria-label="주요 메뉴">\n' + "\n".join(links) + '\n</nav>'


def navigation_html(active_section: str | None = None) -> str:
    """The one canonical header, optionally with a section marked active."""
    return (f'<header class="neo-global-header" {NAVIGATION_MARKER}>\n'
            f'<div class="neo-global-header__inner">\n{_BRAND_HTML}\n{_nav_html(active_section)}\n</div></header>')


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
_COMPATIBILITY_MARKER = ('<nav class="sr-data" aria-label="추가 탐색 링크">'
    '<a href="/">NEO GOLF DATA</a> <a href="/">홈</a> <a href="/tournaments/">대회</a> '
    '<a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>')

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

def inject_global_navigation(html: str, active_section: str | None = None) -> str:
    """Normalize retained HTML and inject one consistent global nav.

    active_section marks which of GLOBAL_NAV_ITEMS is "here" (aria-current
    + a visible active state) -- see navigation_html(). Callers that don't
    know their section yet can omit it; the header is still refreshed to
    the current canonical markup, just with no link marked active.
    """
    html = _repair_legacy_mojibake(html)
    canonical_header = navigation_html(active_section)
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
            html = html.replace('</body>', _COMPATIBILITY_MARKER + '</body>', 1)
        return html
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
    return rendered.replace('</body>', _COMPATIBILITY_MARKER + '</body>', 1)
