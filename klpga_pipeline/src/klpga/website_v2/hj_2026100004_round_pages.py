"""R2/R3 page rendering for HJ 2026100004 only.

Scoped to this one tournament's own page structure/CSS classes, matching
the hand-authored R1 page byte-for-byte in markup conventions (same
`.leaderboard-table`/`.status-badge`/`.cut-divider` classes already in
docs/assets/neo.css -- no new CSS). Not imported by any other
tournament's builder, per this repo's established self-contained-per-
-tournament convention (see klpga.neo_win.hitejinro_round_page).
"""
from __future__ import annotations

from html import escape
from pathlib import Path

from klpga.website_v2.player_identity import render_player_identity

GAME_CODE = "2026100004"
REPO_ROOT = Path(__file__).resolve().parents[4]
DOCS_ROOT = REPO_ROOT / "docs"
TOURNAMENT_DOCS_ROOT = DOCS_ROOT / "tournaments" / "2026" / GAME_CODE


def esc(value) -> str:
    return escape(str(value), quote=True)


def rank_labels(scores: list[int]) -> list[str]:
    """Standard golf tie-rank labels ('T1','T1','3',...) for scores
    already sorted descending (higher = better, matches Stableford
    points)."""
    labels = []
    i = 0
    n = len(scores)
    while i < n:
        j = i
        while j + 1 < n and scores[j + 1] == scores[i]:
            j += 1
        tie_size = j - i + 1
        label = str(i + 1) if tie_size == 1 else f"T{i + 1}"
        labels.extend([label] * tie_size)
        i = j + 1
    return labels


def name_cell(*, nationality: str, name: str, sponsor: str, status_badge: str | None = None) -> str:
    """Player identity cell: flag + name/sponsor (sponsor directly
    BELOW the name, per neo-site.css's site-wide GLOBAL SPONSOR RULE --
    see klpga.website_v2.player_identity.render_player_identity, the
    one shared markup for this; no inline display:inline override here,
    which is what previously defeated that rule) + an optional CUT/WD
    status badge as a separate sibling element, never appended to the
    name/sponsor text itself."""
    identity = render_player_identity(name, sponsor)
    flag_cell = (
        f"<img src=\"/assets/flags/{esc(nationality)}.svg\" alt=\"\" width=\"16\" height=\"12\" style=\"grid-column:1;grid-row:1;display:block;margin-top:3px\">"
        if nationality else "<span aria-hidden=\"true\" style=\"grid-column:1;grid-row:1\"></span>"
    )
    badge = f" <span class='status-badge'>{esc(status_badge)}</span>" if status_badge else ""
    identity_cell = f"<span style=\"grid-column:2;grid-row:1;text-align:left\">{identity}{badge}</span>"
    player_grid = (
        "<span style=\"display:inline-grid;grid-template-columns:16px minmax(0,1fr);"
        "column-gap:6px;align-items:start;width:10rem;vertical-align:top;text-align:left\">"
        f"{flag_cell}{identity_cell}</span>"
    )
    return f"<th scope=\"row\" style=\"text-align:center\" data-label=\"선수\">{player_grid}</th>"



def video_section_html(filename: str, *, game_code: str = GAME_CODE) -> str:
    """Same markup pattern as klpga.website_v2.hj_pre_video_section.
    hj_pre_video_section_html -- width:100%;max-width:100%;height:auto
    keeps the video at its own native aspect ratio (this tournament's
    clips are 1080x1920, i.e. 9:16 portrait) instead of being stretched/
    cropped to fill the viewport or forced into a 1:1 square."""
    return (
        "<section class='panel' id='final-video'><p class='note'>NEO GOLF DATA</p>"
        "<video controls playsinline style='display:block;width:100%;max-width:100%;height:auto' "
        f"src='/assets/tournaments/{game_code}/{filename}'></video></section>"
    )


def image_section_html(filename: str, alt: str, *, game_code: str = GAME_CODE, section_id: str) -> str:
    """Same width:100%;max-width:100%;height:auto pattern as
    video_section_html -- keeps the image at its own native aspect
    ratio, no crop/stretch, no overflow at any viewport width."""
    return (
        f"<section class='panel' id='{esc(section_id)}'><p class='note'>NEO GOLF DATA</p>"
        f"<img src='/assets/tournaments/{game_code}/{filename}' alt='{esc(alt)}' "
        "style='display:block;width:100%;max-width:100%;height:auto'></section>"
    )


def cut_divider_row(label: str, total_cols: int) -> str:
    return f"<tr class='cut-divider'><td colspan='{total_cols}'>{esc(label)}</td></tr>"


GLOBAL_HEADER = (
    "<header class=\"neo-global-header\" data-neo-global-navigation>"
    "<div class=\"neo-global-header__inner\">"
    "<a class=\"neo-global-brand\" href=\"/\"><span class=\"neo-brand-mark\">NEO GOLF DATA</span>"
    "<span class=\"neo-brand-legend\"><span class=\"neo-brand-legend__item\">NUMBER</span>"
    "<span class=\"neo-brand-legend__item\">EVIDENCE</span>"
    "<span class=\"neo-brand-legend__item\">ORACLE</span></span></a>"
    "<nav class=\"neo-global-nav\" aria-label=\"주요 메뉴\"><a href=\"/\">홈</a>"
    "<a href=\"/tournaments/\" class=\"is-active\" aria-current=\"page\">대회 기록</a>"
    "<a href=\"/ranking/\">랭킹</a><a href=\"/deep-dive/\">딥다이브</a>"
    "<a href=\"/neo-lab/\">NEO LAB</a><a href=\"/about/\">소개</a></nav></div></header>"
)

FOOTER = (
    "<footer class=\"site-footer\"><div class=\"site-footer__inner\">"
    "<p class=\"site-footer__copyright\">© 2026 NEO GOLF DATA. All Rights Reserved.</p>"
    "</div></footer>"
)

STAGE_META = [
    ("pre", "PRE"),
    ("r1", "R1"),
    ("r2", "R2"),
    ("r3", "R3"),
    ("fr", "FR"),
]


def stage_nav_html(active_stage: str, *, live_stages: set[str]) -> str:
    """Build the stage-nav block. `live_stages` are stages with a real
    published page (get a real <a>); everything else not active renders
    as the established disabled <span> placeholder."""
    items = []
    for key, label in STAGE_META:
        href = f"/tournaments/2026/{GAME_CODE}/{key}/"
        if key == active_stage:
            items.append(
                f"<li class=\"stage-nav__item\"><a class=\"stage-nav__link is-active\" "
                f"aria-current=\"page\" href=\"{href}\">{label}</a></li>"
            )
        elif key in live_stages:
            items.append(f"<li class=\"stage-nav__item\"><a class=\"stage-nav__link\" href=\"{href}\">{label}</a></li>")
        else:
            items.append(
                "<li class=\"stage-nav__item\"><span class=\"stage-nav__link is-disabled\" "
                f"aria-disabled=\"true\">{label}</span></li>"
            )
    return "<nav class=\"stage-nav\" aria-label=\"대회 단계\" data-stage-nav><ol class=\"stage-nav__list\">" + "".join(items) + "</ol></nav>"


def page_shell(*, title: str, description: str, canonical_suffix: str, breadcrumb_label: str, intro_html: str, stage_nav: str, body_html: str) -> str:
    return (
        "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{esc(title)}</title>"
        f"<meta name=\"description\" content=\"{esc(description)}\">"
        f"<link rel=\"canonical\" href=\"https://neogolfdata.com/tournaments/2026/{GAME_CODE}/{canonical_suffix}/\">"
        "<link rel=\"stylesheet\" href=\"/assets/neo-site.css\"><link rel=\"stylesheet\" href=\"/assets/neo.css\">"
        "<style>.neo-global-header__inner{padding-inline:clamp(1rem,2.5vw,2.5rem)}</style>"
        "</head><body>"
        f"{GLOBAL_HEADER}"
        "<main>"
        "<nav class=\"breadcrumb\" aria-label=\"현재 위치\"><a href=\"/\">홈</a>"
        "<span class=\"breadcrumb__sep\"> &gt; </span><a href=\"/tournaments/\">대회 기록</a>"
        "<span class=\"breadcrumb__sep\"> &gt; </span>"
        f"<a href=\"/tournaments/2026/{GAME_CODE}/\">HJ중공업·동부건설 챔피언십</a>"
        "<span class=\"breadcrumb__sep\"> &gt; </span>"
        f"<span aria-current=\"page\">{esc(breadcrumb_label)}</span></nav>"
        f"{intro_html}"
        f"{stage_nav}"
        f"{body_html}"
        "</main>"
        f"{FOOTER}"
        "</body></html>"
    )
