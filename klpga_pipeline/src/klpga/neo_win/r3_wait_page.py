"""R3 HOUSE: the real, public R3 route -- truthful WAIT/empty state
until a real, gate-passed R3 exists. Mirrors klpga.neo_win.r2_wait_page
exactly, one round later.
"""
from __future__ import annotations

from klpga.website_v2.global_navigation import inject_global_navigation
from klpga.website_v2.shell import breadcrumb_html

STAGE_NOT_READY_META = '<meta name="neo-stage-publication-ready" content="false">'


def render_r3_wait_page(*, tournament_name: str, game_code: str) -> str:
    breadcrumb = breadcrumb_html(tournament_name, None, "R3")
    shell = (
        "<!doctype html><html lang=\"ko\"><head>"
        f"{STAGE_NOT_READY_META}"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>NEO GOLF DATA · {tournament_name} R3</title>"
        "<link rel=\"stylesheet\" href=\"/assets/neo-site.css\">"
        "<link rel=\"stylesheet\" href=\"/assets/neo.css\">"
        "</head><body>"
        "<main>"
        f"{breadcrumb}"
        "<section class=\"page-head\">"
        f"<p class=\"kicker\">{tournament_name}</p>"
        "<h1>3라운드 결과 대기 중</h1>"
        "<p>공식 3라운드 결과가 아직 발표되지 않았습니다. 공식 데이터가 확인되는 대로 "
        "실제 리더보드와 확률 정보를 이 페이지에 게시합니다.</p>"
        "</section>"
        "<section class=\"product-section\">"
        "<p>추정치나 예상 순위는 표시하지 않습니다 — 확인되지 않은 정보는 "
        "게시하지 않는다는 원칙에 따라, 공식 소스가 확정한 결과만 게시합니다.</p>"
        "</section>"
        "</main>"
        "<footer class=\"site-footer\"><div class=\"site-footer__inner\">"
        "<p class=\"site-footer__copyright\">© 2026 NEO GOLF DATA. All Rights Reserved.</p>"
        "</div></footer>"
        "</body></html>"
    )
    return inject_global_navigation(shell, active_section="tournaments")


def is_wait_page(html: str) -> bool:
    return STAGE_NOT_READY_META in html
