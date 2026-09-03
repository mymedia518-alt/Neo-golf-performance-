"""Shared, mobile-visible navigation for every public NEO page."""
from __future__ import annotations

import re

NAVIGATION_MARKER = "data-neo-global-navigation"
NAVIGATION_HTML = f'''<header class="neo-global-header" {NAVIGATION_MARKER}>
<div class="neo-global-header__inner"><a class="neo-global-brand" href="/">NEO GOLF DATA</a>
<nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/">홈</a><a href="/tournaments/">대회</a><a href="/deep-dive/">딥다이브</a><a href="/about/">소개</a></nav></div></header>'''

NAVIGATION_CSS = """.neo-global-header{width:100%;max-width:none;margin:0;padding:0;border:0;border-bottom:1px solid #dfe5ea;background:#fff;color:#17202a}.neo-global-header__inner{display:flex;align-items:center;justify-content:space-between;gap:1rem;width:min(calc(100% - 2rem),1240px);margin:auto;padding:.8rem 0}.neo-global-brand{flex:0 0 auto;color:#17202a;text-decoration:none;font:800 1rem/1.2 Pretendard,\"Apple SD Gothic Neo\",\"Noto Sans KR\",sans-serif;letter-spacing:.04em}.neo-global-header .neo-global-nav{display:flex;align-items:center;gap:.35rem 1rem;overflow-x:auto;white-space:nowrap}.neo-global-header .neo-global-nav a{display:inline-flex;align-items:center;min-height:44px;margin:0;padding:.25rem 0;color:#65717d;text-decoration:none;font:700 .82rem/1.2 Pretendard,\"Apple SD Gothic Neo\",\"Noto Sans KR\",sans-serif}@media(max-width:760px){.neo-global-header__inner{align-items:flex-start;flex-direction:column;gap:.1rem;width:min(calc(100% - 1.25rem),1240px);padding:.55rem 0}.neo-global-header .neo-global-nav{display:flex!important;width:100%;gap:0 1rem}.neo-global-header .neo-global-nav a{display:inline-flex!important;min-height:44px}}\n"""

KOREAN_UI_REPLACEMENTS = {
    ">HOME</a>": ">홈</a>",
    ">TOURNAMENTS</a>": ">대회</a>",
    ">DEEP DIVE</a>": ">딥다이브</a>",
    ">ABOUT</a>": ">소개</a>",
    "TOURNAMENTS · NEO GOLF DATA": "대회 · NEO GOLF DATA",
    "DEEP DIVE · NEO GOLF DATA": "딥다이브 · NEO GOLF DATA",
    "ABOUT NEO GOLF DATA": "NEO GOLF DATA 소개",
    "About NEO GOLF DATA": "NEO GOLF DATA 소개",
    "LAYER A · NEO MODEL": "분석 1 · NEO 모델",
    "LAYER B · PERFORMANCE ANALYSIS": "분석 2 · 경기력 분석",
    "TOURNAMENT PREDICTION": "대회 예측",
    "NEXT UPDATE": "다음 업데이트",
    "R1 DATA UNAVAILABLE": "1라운드 데이터 없음",
    "NEO R1 Tournament Prediction": "NEO 1라운드 대회 예측",
    "NEO R2 Tournament Prediction": "NEO 2라운드 대회 예측",
    "Independent Golf Data Project": "독립 골프 데이터 프로젝트",
    "Number · Evidence · Oracle": "숫자 · 근거 · 통찰",
    ">NUMBER<": ">숫자<",
    ">EVIDENCE<": ">근거<",
    ">ORACLE<": ">통찰<",
    ">GOLF DATA<": ">골프 데이터<",
    "Predictions and probability models are proprietary to NEO GOLF DATA.": "예측과 확률 모델의 권리는 NEO GOLF DATA에 있습니다.",
    "Tournament results and player information are based on publicly available data.": "대회 결과와 선수 정보는 공개 데이터를 바탕으로 합니다.",
    "All Rights Reserved.": "모든 권리 보유.",
}


def inject_global_navigation(html: str) -> str:
    """Inject the shared navigation once without changing page-specific content."""
    for source, replacement in KOREAN_UI_REPLACEMENTS.items():
        html = html.replace(source, replacement)
    if NAVIGATION_MARKER in html:
        return html
    required_links = ('href="/">홈</a>', 'href="/tournaments/">대회</a>', 'href="/deep-dive/">딥다이브</a>', 'href="/about/">소개</a>')
    if 'href="/">NEO GOLF DATA</a>' in html and all(link in html for link in required_links):
        return html
    stylesheet = '<link rel="stylesheet" href="/assets/navigation.css">'
    linked = html.replace("</head>", f"{stylesheet}</head>", 1) if "</head>" in html else stylesheet + html
    rendered, count = re.subn(r"(<body[^>]*>)", rf"\1{NAVIGATION_HTML}", linked, count=1, flags=re.IGNORECASE)
    if count == 0:
        rendered, count = re.subn(r"(<header(?:\s|>))", rf"{NAVIGATION_HTML}\1", linked, count=1, flags=re.IGNORECASE)
    if count != 1:
        raise ValueError("public HTML must contain an opening body or header element")
    return rendered
