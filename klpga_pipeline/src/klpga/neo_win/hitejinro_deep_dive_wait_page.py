"""HITE JINRO (game_code 2026100005) Course Deep Dive -- real, public
WAIT/empty state, same established shape as r2_wait_page.py/
r3_wait_page.py: with no real hole-by-hole course data, this never
fabricates a field average score, birdie+/bogey+ rate, danger zone, or
hole-difficulty figure -- it says, truthfully, that Deep Dive data does
not exist yet, and names exactly why (klpga.neo_win.
final_course_deep_dive.connect_course_deep_dive() returns BLOCKED for
this game_code: real hole-by-hole scoring only exists once rounds are
actually played, and this tournament has not started -- see that
module's own docstring for the full REQUIRED_FIELDS contract this page
starts serving real content for, unchanged, the moment a real
COURSE_DEEP_DIVE.json artifact exists for this game_code).
"""
from __future__ import annotations

from klpga.website_v2.global_navigation import inject_global_navigation
from klpga.website_v2.shell import breadcrumb_html

STAGE_NOT_READY_META = '<meta name="neo-stage-publication-ready" content="false">'


def render_deep_dive_wait_page(*, tournament_name: str, game_code: str, reason: str) -> str:
    breadcrumb = breadcrumb_html(tournament_name, f"/tournaments/2026/{game_code}/pre/", "딥 다이브")
    shell = (
        "<!doctype html><html lang=\"ko\"><head>"
        f"{STAGE_NOT_READY_META}"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>NEO GOLF DATA · {tournament_name} 딥 다이브</title>"
        "<link rel=\"stylesheet\" href=\"/assets/neo-site.css\">"
        "<link rel=\"stylesheet\" href=\"/assets/neo.css\">"
        "</head><body>"
        "<main>"
        f"{breadcrumb}"
        "<section class=\"page-head\">"
        f"<p class=\"kicker\">{tournament_name}</p>"
        "<h1>코스 딥 다이브 준비 중</h1>"
        "<p>실제 홀별 경기 데이터가 아직 존재하지 않습니다. 라운드가 실제로 진행되어 "
        "공식 홀별 스코어가 확인되는 대로, 필드 평균 스코어·버디+/보기+ 비율·위험 홀·"
        "홀 난이도를 이 페이지에 게시합니다.</p>"
        "</section>"
        "<section class=\"product-section\">"
        "<p>추정치나 예상 수치는 표시하지 않습니다 — 확인되지 않은 정보는 게시하지 "
        f"않는다는 원칙에 따라, 공식 소스가 확정한 결과만 게시합니다. ({reason})</p>"
        "</section>"
        "</main>"
        "<footer class=\"site-footer\"><div class=\"site-footer__inner\">"
        "<p class=\"site-footer__copyright\">© 2026 NEO GOLF DATA. All Rights Reserved.</p>"
        "</div></footer>"
        "</body></html>"
    )
    # Route the "대회" nav item to this tournament's own real PRE page
    # rather than the generic /tournaments/ index -- the established
    # r2_wait_page.py/r3_wait_page.py precedent this module otherwise
    # follows omits this override (plain active_section="tournaments"),
    # but nav_overrides exists in global_navigation.py specifically for
    # "a page that must route '대회' to a specific currently-published
    # page" (that module's own docstring), and every other 2026100005
    # page built this session already does this -- fixed here for
    # consistency rather than propagating what looks like an
    # unintentional gap in that precedent.
    return inject_global_navigation(
        shell, active_section="tournaments",
        nav_overrides={"tournaments": f"/tournaments/2026/{game_code}/pre/"},
    )


def is_wait_page(html: str) -> bool:
    return STAGE_NOT_READY_META in html
