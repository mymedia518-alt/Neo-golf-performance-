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

NAVIGATION_CSS = """.neo-global-header{width:100%;border-bottom:1px solid #dfe5ea;background:#fff;color:#17202a}.neo-global-header__inner{display:flex;align-items:center;justify-content:space-between;gap:1rem;width:min(calc(100% - 2rem),1240px);margin:auto;padding:.7rem 0}.neo-global-brand{display:inline-flex;align-items:baseline;gap:.55rem;flex:0 0 auto;color:#17202a;text-decoration:none}.neo-brand-mark{font:850 1rem/1.2 Pretendard,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;letter-spacing:.08em}.neo-brand-sub{color:#65717d;font:600 .7rem/1.2 Pretendard,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;letter-spacing:.02em}.neo-global-header .neo-global-nav{display:flex;align-items:center;gap:.35rem 1rem;overflow-x:auto;white-space:nowrap}.neo-global-header .neo-global-nav a{display:inline-flex;align-items:center;min-height:44px;margin:0;padding:.25rem 0;color:#65717d;text-decoration:none;font:700 .82rem/1.2 Pretendard,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}.neo-global-header .neo-global-nav a:hover,.neo-global-header .neo-global-nav a:focus-visible{color:#0f5c46}@media(max-width:760px){.neo-global-header__inner{align-items:flex-start;flex-direction:column;gap:.2rem;width:min(calc(100% - 1.25rem),1240px);padding:.55rem 0}.neo-global-header .neo-global-nav{display:flex!important;width:100%;gap:0 1rem}.neo-global-header .neo-global-nav a{display:inline-flex!important;min-height:44px}}"""

BUILD_SHA_META_NAME = "neo-build-source-sha"

def inject_build_provenance(html: str, source_sha: str) -> str:
    """Embed a non-visible <meta> marker naming the source-repo commit
    this page was built from (see scripts/88_build_neo_top120_candidate.py
    for how it's stamped). Never shown in the UI -- it exists so a later
    QA pass can ask "what SHA is this live page actually serving" by
    fetching the page and reading the tag, rather than trusting that a
    git push implies a deployed page."""
    tag = f'<meta name="{BUILD_SHA_META_NAME}" content="{source_sha}">'
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
    stylesheet = '<link rel="stylesheet" href="/assets/navigation.css">'
    linked = html.replace("</head>", f"{stylesheet}</head>", 1) if "</head>" in html else stylesheet + html
    rendered, count = re.subn(r"(<body[^>]*>)", rf"\1{canonical_header}", linked, count=1, flags=re.IGNORECASE)
    if count == 0:
        rendered, count = re.subn(r"(<header(?:\s|>))", rf"{canonical_header}\1", linked, count=1, flags=re.IGNORECASE)
    if count != 1:
        raise ValueError("public HTML must contain an opening body or header element")
    return rendered.replace('</body>', _COMPATIBILITY_MARKER + '</body>', 1)
