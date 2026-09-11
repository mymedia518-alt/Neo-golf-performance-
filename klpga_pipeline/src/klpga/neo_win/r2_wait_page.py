"""R2 HOUSE: the real, public R2 route -- truthful WAIT/empty state
until a real, gate-passed R2 exists.

Renders the actual page served at <url_base>r2/index.html. With no
real R2 data it never fabricates a leaderboard, SG, CUT, or
probability -- it says, truthfully, that R2 has not started/been
published yet. It carries scripts/88_build_neo_top120_candidate.py's
STAGE_READINESS_MARKER so the HOME STATE ROUTER never mistakes its
mere existence for a real, ready stage (see that module's docstring on
the marker) -- HOME stays on R1 until render_r2_ready_page() (called
only once the R2 publication gate passes) replaces this file.

Sponsor invariant: trivially preserved -- a WAIT page has zero player
rows, so there is no sponsor slot to omit or fabricate.
"""
from __future__ import annotations

from klpga.website_v2.global_navigation import inject_global_navigation
from klpga.website_v2.shell import breadcrumb_html

STAGE_NOT_READY_META = '<meta name="neo-stage-publication-ready" content="false">'
"""Byte-identical to scripts/88_build_neo_top120_candidate.py's
STAGE_READINESS_MARKER substring -- kept as a literal string, not an
import, so this module has no dependency on a scripts/ file (scripts/
imports src/, never the reverse)."""


def render_r2_wait_page(*, tournament_name: str, game_code: str) -> str:
    """The complete, real HTML for R2's public route while real R2 data
    is absent. Truthful copy only -- no leaderboard table, no SG
    section, no CUT/probability content, no fabricated row. Carries the
    same shared breadcrumb every real tournament page carries (UX spec
    3/16, "각 generator가 자기 UI를 만들지 않는다") -- base_url=None since
    R2 is a stage crumb, not an overview page (mirrors OK Open's own
    convention in shell.breadcrumb_html's own docstring)."""
    breadcrumb = breadcrumb_html(tournament_name, None, "R2")
    shell = (
        "<!doctype html><html lang=\"ko\"><head>"
        f"{STAGE_NOT_READY_META}"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>NEO GOLF DATA · {tournament_name} R2</title>"
        "<link rel=\"stylesheet\" href=\"/assets/neo-site.css\">"
        "<link rel=\"stylesheet\" href=\"/assets/neo.css\">"
        "</head><body>"
        "<main>"
        f"{breadcrumb}"
        "<section class=\"page-head\">"
        f"<p class=\"kicker\">{tournament_name}</p>"
        "<h1>2라운드 결과 대기 중</h1>"
        "<p>공식 2라운드 결과가 아직 발표되지 않았습니다. 공식 데이터가 확인되는 대로 "
        "실제 리더보드, 컷 결과, 확률 정보를 이 페이지에 게시합니다.</p>"
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
