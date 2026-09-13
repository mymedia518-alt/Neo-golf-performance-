"""4R FINAL PRE-BUILD Phase 8: the public FINAL route's structural
shell, pre-built before any official FR/R4 result exists.

Mirrors klpga.neo_win.r3_wait_page exactly (same truthful WAIT/empty
state discipline, same NEO design system, same STAGE_NOT_READY_META
convention) -- generalized one stage further, to FINAL. The 10 content
slots the mission specifies are represented as empty, clearly-labeled
containers with zero numbers in them; nothing here is a number that
could be mistaken for a real result. Once FINAL truth + a real report
exist, a future final_real_page.py (not buildable before real data
exists, per the mission's own rule) fills these same slot ids -- this
module defines the ids/order now so that page has nothing left to
invent.

Public UI invariants preserved unchanged from every prior round's
page: sponsor directly under player name, blank (never guessed) if no
official evidence, no internal QA/model-state/file-path/provenance
text anywhere in the body.
"""
from __future__ import annotations

from klpga.website_v2.global_navigation import inject_global_navigation
from klpga.website_v2.shell import breadcrumb_html

STAGE_NOT_READY_META = '<meta name="neo-stage-publication-ready" content="false">'

# Slot order mirrors the mission's Phase 8 list 1-10 exactly. Each id
# is what a future final_real_page.py must fill; this page renders
# them as empty containers only, never placeholder numbers.
FINAL_SLOT_IDS = (
    "final-slot-title",
    "final-slot-winner",
    "final-slot-leaderboard",
    "final-slot-neo-pre-win-probability",
    "final-slot-forecast-vs-actual",
    "final-slot-positive-surprises",
    "final-slot-negative-surprises",
    "final-slot-course-deep-dive",
    "final-slot-neo-validation-score",
    "final-slot-related-deep-dive-links",
)


def render_final_wait_page(*, tournament_name: str, game_code: str) -> str:
    breadcrumb = breadcrumb_html(tournament_name, None, "FINAL")
    slot_divs = "".join(f'<div id="{slot_id}" class="final-slot" data-neo-slot-empty="true"></div>' for slot_id in FINAL_SLOT_IDS)
    shell = (
        "<!doctype html><html lang=\"ko\"><head>"
        f"{STAGE_NOT_READY_META}"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>NEO GOLF DATA · {tournament_name} FINAL</title>"
        "<link rel=\"stylesheet\" href=\"/assets/neo-site.css\">"
        "<link rel=\"stylesheet\" href=\"/assets/neo.css\">"
        "</head><body>"
        "<main>"
        f"{breadcrumb}"
        "<section class=\"page-head\">"
        f"<p class=\"kicker\">{tournament_name}</p>"
        "<h1>최종 결과 대기 중</h1>"
        "<p>공식 최종 라운드 결과가 아직 발표되지 않았습니다. 공식 데이터가 확인되는 대로 "
        "최종 리더보드, NEO 사전 예측과 실제 결과 비교, 코스 분석을 이 페이지에 게시합니다.</p>"
        "</section>"
        "<section class=\"product-section\">"
        "<p>추정치나 예상 결과는 표시하지 않습니다 — 확인되지 않은 정보는 "
        "게시하지 않는다는 원칙에 따라, 공식 소스가 확정한 결과만 게시합니다.</p>"
        f"{slot_divs}"
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
