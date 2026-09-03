"""Shared, mobile-visible navigation and safe public-page normalization."""
from __future__ import annotations

import re

NAVIGATION_MARKER = "data-neo-global-navigation"
NAVIGATION_HTML = f'''<header class="neo-global-header" {NAVIGATION_MARKER}>
<div class="neo-global-header__inner"><a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO</span><span class="neo-brand-sub">Number · Evidence · Oracle</span></a>
<nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/">홈</a><a href="/tournaments/">대회</a><a href="/deep-dive/">딥다이브</a><a href="/about/">소개</a></nav></div></header>'''

# Correctly-encoded, well-formed compatibility footer: one visible-text
# "NEO GOLF DATA" link plus the same four nav destinations, each a
# complete <a href="...">...</a> element. A prior version of this
# constant held a mis-encoded literal (CP949 bytes saved into a
# UTF-8-declared file) with dangling href="..." fragments outside any
# opening <a> tag; every generated page inherited that mojibake. Kept
# as a single named constant, used in both call sites below, so the
# two copies cannot drift out of sync again.
_COMPATIBILITY_MARKER = ('<!-- navigation compatibility marker -->'
    '<a href="/">NEO GOLF DATA</a> <a href="/">홈</a> <a href="/tournaments/">대회</a> '
    '<a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a>')

NAVIGATION_CSS = """.neo-global-header{width:100%;border-bottom:1px solid #dfe5ea;background:#fff;color:#17202a}.neo-global-header__inner{display:flex;align-items:center;justify-content:space-between;gap:1rem;width:min(calc(100% - 2rem),1240px);margin:auto;padding:.7rem 0}.neo-global-brand{display:inline-flex;align-items:baseline;gap:.55rem;flex:0 0 auto;color:#17202a;text-decoration:none}.neo-brand-mark{font:850 1rem/1.2 Pretendard,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;letter-spacing:.08em}.neo-brand-sub{color:#65717d;font:600 .7rem/1.2 Pretendard,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;letter-spacing:.02em}.neo-global-header .neo-global-nav{display:flex;align-items:center;gap:.35rem 1rem;overflow-x:auto;white-space:nowrap}.neo-global-header .neo-global-nav a{display:inline-flex;align-items:center;min-height:44px;margin:0;padding:.25rem 0;color:#65717d;text-decoration:none;font:700 .82rem/1.2 Pretendard,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}.neo-global-header .neo-global-nav a:hover,.neo-global-header .neo-global-nav a:focus-visible{color:#0f5c46}@media(max-width:760px){.neo-global-header__inner{align-items:flex-start;flex-direction:column;gap:.2rem;width:min(calc(100% - 1.25rem),1240px);padding:.55rem 0}.neo-global-header .neo-global-nav{display:flex!important;width:100%;gap:0 1rem}.neo-global-header .neo-global-nav a{display:inline-flex!important;min-height:44px}}"""

def _repair_legacy_mojibake(html: str) -> str:
    try:
        return html.encode("cp949").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return html

def inject_global_navigation(html: str) -> str:
    """Normalize retained HTML and inject one consistent global nav."""
    html = _repair_legacy_mojibake(html)
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
    html = re.sub(r'(<[^>]*class="[^"]*next-update-label[^"]*"[^>]*>).*?(</[^>]+>)', r'\1대회 종료\2', html, flags=re.I|re.S)
    html = re.sub(r'(<[^>]*class="[^"]*next-update-text[^"]*"[^>]*>).*?(</[^>]+>)', r'\1최종 결과 보존\2', html, flags=re.I|re.S)
    if NAVIGATION_MARKER in html:
        if 'href="/">NEO GOLF DATA</a>' not in html:
            html = html.replace('</body>', _COMPATIBILITY_MARKER + '</body>', 1)
        return html
    stylesheet = '<link rel="stylesheet" href="/assets/navigation.css">'
    linked = html.replace("</head>", f"{stylesheet}</head>", 1) if "</head>" in html else stylesheet + html
    rendered, count = re.subn(r"(<body[^>]*>)", rf"\1{NAVIGATION_HTML}", linked, count=1, flags=re.IGNORECASE)
    if count == 0:
        rendered, count = re.subn(r"(<header(?:\s|>))", rf"{NAVIGATION_HTML}\1", linked, count=1, flags=re.IGNORECASE)
    if count != 1:
        raise ValueError("public HTML must contain an opening body or header element")
    return rendered.replace('</body>', _COMPATIBILITY_MARKER + '</body>', 1)
