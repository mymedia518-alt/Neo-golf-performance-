"""Build the real NEO GOLF DATA homepage at docs/index.html.

ARCHITECTURE (operator explicit instruction, superseding this branch's
earlier "compact homepage, no leaderboard" correction): root HOME must
show the current tournament's R1 leaderboard directly -- all 108
players, visible the moment www.neogolfdata.com loads, no extra click
through to /tournaments/2026/2026090002/r1/ required. This is the
CURRENT_TOURNAMENT_OWNER full-mirror pattern (see
klpga.website_v2.home_ownership_guard's module docstring) already used
by KB's own production homepage (scripts/109_build_kb_r1_page.py) --
applying it to Hana is a deliberate owner decision, not a reversion of
the earlier fix (which corrected a *different* problem: R1's own
per-round page had briefly been overwritten wholesale onto root HOME
with no separate homepage identity at all -- that page-ownership
defect stays fixed; this script has always been, and remains, the
sole legitimate writer of docs/index.html).

Per explicit instruction:
- docs/tournaments/2026/2026090002/pre/index.html, .../r1/index.html,
  the PRE archive, and every HANA_2026090002_*.json data file are
  NEVER read for writing and NEVER modified by this script -- the
  JSON loading / row-formatting logic below is a deliberate, read-only
  DUPLICATE of scripts/151_build_hana_r1_page.py's own logic (same
  convention 139/151 already use for their shared sponsor-loading
  logic: each tournament-page builder stays self-contained and never
  imports another builder script -- see docs/OPERATING_RULES.md rule
  4). Both scripts read the same source JSON and apply the identical
  rank/tie/to-par formatting rules, so their rendered tables are
  provably identical in content; see
  klpga_pipeline/tests/test_hana_home_r1_data_consistency.py.
- R1 순위: duplicate-rank groups get a "T" prefix (T1/T3/T7 etc.),
  exactly as 151 already derives it from the verified official rank
  numbers -- no new data.
- 1R 스코어: To-Par notation only (format_to_par: "E"/"+N"/"-N"), never
  the raw stroke count -- guarded by
  klpga.website_v2.round_page_contract.assert_cumulative_score_is_relative_to_par,
  the same guard 151 itself runs.

Markup/CSS are 100% reused from what 151_build_hana_r1_page.py already
established for this tournament (same global-header, hero, stage-nav,
leaderboard-panel/table-wrap--flat-scroll/leaderboard-table classes,
player-cell flag+name+sponsor pattern) -- no new CSS, no new visual
language.

og:title/description/url/type + twitter:card stay homepage-generic
(NEO GOLF DATA brand identity, never a specific tournament's name) --
per explicit prior operator instruction, unaffected by this change.
og:image on root HOME remains intentionally omitted (see prior
instruction: the only image files in docs/assets/ were the KB FINAL
tournament's own result image, which must never be the homepage's
representative image) -- root HOME's own <head> is left byte-for-byte
untouched by this module's later SHARE-PAGE addition below.

SHARE PAGE (operator instruction: Threads' cached link-preview for
www.neogolfdata.com kept showing the old KB FINAL page even after root
HOME was fixed, because Threads caches a URL's OG tags rather than
re-fetching on every share). A second, cache-bust-only route,
docs/share/index.html, is built from this exact same real homepage
body (identical header/hero/leaderboard/stage-nav/footer -- genuinely
"the real NEO GOLF DATA homepage screen", never a stripped-down or
fabricated substitute) under its own URL
(https://www.neogolfdata.com/share/) with its own fresh OG tags,
including a real, newly-rendered representative image
(docs/assets/og-neo-golf-data.png -- a brand card built from this
site's own established colors/wordmark via
scratchpad/shoot_og.py+og_card.html, sha256 confirmed distinct from
both KB FINAL image files) that Threads has never cached before. Root
HOME (docs/index.html) itself is not modified by adding this route:
build() below is untouched from before; only a new build_share()
function and its own head/output-path constants are added.
"""
from __future__ import annotations

import json
import sys
from html import escape as _esc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.round_score_format import format_to_par  # noqa: E402
from klpga.website_v2.round_page_contract import assert_cumulative_score_is_relative_to_par  # noqa: E402
from klpga.website_v2.home_ownership_guard import (  # noqa: E402
    CURRENT_TOURNAMENT_OWNER,
    assert_home_write_allowed,
)

DOCS_INDEX = REPO_ROOT / "docs" / "index.html"
SHARE_PAGE = REPO_ROOT / "docs" / "share" / "index.html"
OG_IMAGE_URL = "https://www.neogolfdata.com/assets/og-neo-golf-data.png"
OG_IMAGE_WIDTH = 2400
OG_IMAGE_HEIGHT = 1260

TOURNAMENT_NAME = "하나금융그룹 챔피언십"
TOURNAMENT_DATE_META = "2026.09.17 — 09.20"
TOURNAMENT_WINNER_META = "2025 우승 이다연 · 279타(-9)"
TOURNAMENT_VENUE_META = "더헤븐 · West, South · Par 72"
GAME_CODE = "2026090002"
URL_BASE = f"/tournaments/2026/{GAME_CODE}/"

# Tournament-specific share route (operator instruction: a second,
# game-code-scoped share URL, distinct from the generic /share/ cache
# bust above, carrying its own tournament-named OG copy and a real
# screenshot of the actual R1 first screen as its image -- never the
# generic brand card, never the KB FINAL image).
SHARE_TOURNAMENT_PAGE = REPO_ROOT / "docs" / "share" / GAME_CODE / "index.html"
R1_OG_IMAGE_URL = "https://www.neogolfdata.com/assets/hana-2026090002-r1-og.png"
R1_OG_IMAGE_WIDTH = 2400
R1_OG_IMAGE_HEIGHT = 1260

# Short-URL alias for the tournament share page (operator instruction):
# docs/2026090002/index.html -- same real R1 108-player screen, same
# title/description/image as /share/2026090002/, only og:url differs
# (the short root-level path itself). Never modifies
# SHARE_TOURNAMENT_PAGE or the R1 OG image it points at.
SHORT_SHARE_PAGE = REPO_ROOT / "docs" / GAME_CODE / "index.html"

# Real, currently-published stages only (docs/tournaments/2026/2026090002/
# has exactly pre/ and r1/ today) -- R2/R3/FR render as disabled
# placeholders, the exact same convention R1's own stage-nav already
# uses for its own not-yet-published stages.
_PUBLISHED_STAGES = {"pre", "r1"}
_STAGE_LABELS = [("pre", "사전 분석 PRE"), ("r1", "R1"), ("r2", "R2"), ("r3", "R3"), ("fr", "FR")]
_CURRENT_STAGE = "r1"

_NOWRAP_INSUFFICIENT = "<span style='white-space:nowrap'>데이터 부족</span>"


def _stage_nav_html() -> str:
    items = []
    for stage, label in _STAGE_LABELS:
        if stage in _PUBLISHED_STAGES:
            current = ' aria-current="page"' if stage == _CURRENT_STAGE else ""
            items.append(f'<li class="stage-nav__item"><a class="stage-nav__link" href="{URL_BASE}{stage}/"{current}>{label}</a></li>')
        else:
            items.append(f'<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">{label}</span></li>')
    return f'<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">{"".join(items)}</ol></nav>'


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def _load_country_by_id() -> dict[str, str]:
    match = _load("HANA_2026090002_ENTRY_FLAG_MATCH_V2.json")
    country_by_id = {r["player_id"]: r["country_code"] for r in match["records"]}
    for r in _load("HANA_2026090002_R1_NEW_ENTRANT_IDENTITY_EVIDENCE_V1.json")["records"]:
        pid = r["player_id"]
        assert pid not in country_by_id, f"unexpected: {pid} already has a PRE-stage flag record"
        country_by_id[pid] = r["country_code"]
    return country_by_id


def _load_sponsor_by_id() -> dict[str, str]:
    """Same merge logic/sources as 151_build_hana_r1_page.py's own
    _load_sponsor_by_id() -- duplicated here (not imported), same
    self-contained-builder convention -- see this module's docstring."""
    sources: list[tuple[str, str, str, set[str]]] = [
        ("KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V3.json", "newly_recovered_sponsors", "status", {"VERIFIED_OFFICIAL"}),
        ("HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V2.json", "newly_recovered_sponsors", "status", {"VERIFIED_OFFICIAL"}),
        ("OPERATOR_REPORTED_SPONSOR_EVIDENCE_V2.json", "records", "evidence_status", {"VERIFIED_OFFICIAL_OPERATOR_REPORTED"}),
        ("OPERATOR_REPORTED_SPONSOR_EVIDENCE_V3.json", "records", "evidence_status", {"VERIFIED_OFFICIAL_OPERATOR_REPORTED"}),
        ("HANA_2026090002_R1_NEW_ENTRANT_IDENTITY_EVIDENCE_V1.json", "records", "evidence_status", {"VERIFIED_OFFICIAL_R1_LEADERBOARD"}),
    ]
    sponsor_by_id: dict[str, str] = {}
    for filename, list_key, status_key, allowed in sources:
        data = _load(filename)
        for r in data[list_key]:
            if r.get(status_key) not in allowed:
                continue
            sponsor = r.get("sponsor")
            if not sponsor:
                continue
            pid = str(r["player_id"])
            existing = sponsor_by_id.get(pid)
            assert existing is None or existing == sponsor, (
                f"conflicting verified sponsor for player_id {pid}: {existing!r} vs {sponsor!r} ({filename})"
            )
            sponsor_by_id[pid] = sponsor
    return sponsor_by_id


def _player_cell(pid: str, name: str, country_by_id: dict[str, str], sponsor_by_id: dict[str, str]) -> str:
    flag_cell = ""
    country_code = country_by_id.get(pid)
    if country_code:
        flag_cell = (
            f"<img src='/assets/flags/{country_code}.svg' alt='' width='16' height='12' "
            f"style='display:inline-block;vertical-align:middle;margin-right:4px'>"
        )
    sponsor = sponsor_by_id.get(pid)
    sponsor_text = _esc(sponsor) if sponsor else ""
    sponsor_cell = f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span>"
    return (
        f"{flag_cell}<span class='player-name' style='display:inline;vertical-align:middle'>{_esc(name)}</span>"
        f"{sponsor_cell}"
    )


def _prob_cell(rec: dict, key: str, label: str) -> str:
    val = rec[key]
    if val == "데이터 부족":
        return f"<td data-label='{label}'>{_NOWRAP_INSUFFICIENT}</td>"
    return f"<td class='win' data-label='{label}'>{_esc(val)}</td>"


def _build_rows_html() -> tuple[str, int]:
    r1_result = _load("HANA_2026090002_R1_PLAYER_RESULT_V1.json")
    analysis = _load("HANA_2026090002_R1_ANALYSIS_V1.json")
    records = r1_result["records"]
    analysis_by_id = {r["player_id"]: r for r in analysis["records"]}
    assert len(records) == 108
    assert len(analysis_by_id) == 108

    country_by_id = _load_country_by_id()
    sponsor_by_id = _load_sponsor_by_id()

    def _sort_key(r):
        return (r["rank"] is None, r["rank"] if r["rank"] is not None else 0, int(r["player_id"]))

    rank_counts: dict[int, int] = {}
    for r in records:
        if r["status"] != "WD" and r["rank"] is not None:
            rank_counts[r["rank"]] = rank_counts.get(r["rank"], 0) + 1

    rows_html = []
    for r in sorted(records, key=_sort_key):
        pid = r["player_id"]
        arec = analysis_by_id[pid]
        is_wd = r["status"] == "WD"
        if is_wd or r["rank"] is None:
            rank_cell = "—"
        elif rank_counts[r["rank"]] > 1:
            rank_cell = f"T{r['rank']}"
        else:
            rank_cell = str(r["rank"])
        score_display = "WD" if is_wd else format_to_par(r["total_under_par"])
        if not is_wd and score_display != "—":
            assert_cumulative_score_is_relative_to_par(score_display, label="1R", player=r["official_display_name"])
        player_cell = _player_cell(pid, r["official_display_name"], country_by_id, sponsor_by_id)

        band = arec["neo_performance_band"]
        band_cell = _NOWRAP_INSUFFICIENT if band == "데이터 부족" else f"<span class='band' role='img' aria-label='NEO 경기력 {_esc(band)}'>{_esc(band)}</span>"

        rows_html.append(
            f"<tr><td data-label='순위'>{rank_cell}</td>"
            f"<th scope='row' data-label='선수' style='white-space:nowrap;text-align:left'>{player_cell}</th>"
            f"<td data-label='1R'>{_esc(score_display)}</td>"
            f"<td data-label='NEO 경기력'>{band_cell}</td>"
            f"{_prob_cell(arec, 'cut_probability', '컷 통과율')}"
            f"{_prob_cell(arec, 'top20_probability', 'TOP20')}"
            f"{_prob_cell(arec, 'top10_probability', 'TOP10')}"
            f"{_prob_cell(arec, 'top5_probability', 'TOP5')}"
            f"{_prob_cell(arec, 'win_probability', '우승확률')}"
            f"</tr>"
        )

    return "".join(rows_html), len(rows_html)


def _body_html(current_stage_href: str, rows_html: str) -> str:
    """The real NEO GOLF DATA homepage screen -- header, hero, stage-nav,
    full R1 leaderboard, footer. Shared verbatim by root HOME (build())
    and the /share/ cache-bust route (build_share()) below so the two
    can never visually diverge; only each page's own <head> differs."""
    return (
        f'<body><header class="neo-global-header" data-neo-global-navigation><div class="neo-global-header__inner">'
        f'<a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO GOLF DATA</span>'
        f'<span class="neo-brand-legend"><span class="neo-brand-legend__item">NUMBER</span>'
        f'<span class="neo-brand-legend__item">EVIDENCE</span><span class="neo-brand-legend__item">ORACLE</span></span></a>'
        f'<nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/" class="is-active" aria-current="page">홈</a>'
        f'<a href="{current_stage_href}">대회</a><a href="/ranking/">랭킹</a><a href="/deep-dive/">딥다이브</a>'
        f'<a href="/neo-lab/">NEO LAB</a><a href="/about/">소개</a></nav></div></header>'
        f'<main><style>@media(max-width:760px){{.hana-tourinfo-sep{{display:none}}.hana-tourinfo-holes{{display:block}}}}</style>'
        f'<section class="hero" id="home-hero"><div><p class="eyebrow">R1 결과</p><h1>{TOURNAMENT_NAME}</h1>'
        f'<p class="meta">{TOURNAMENT_DATE_META}</p><p class="meta">{TOURNAMENT_WINNER_META}</p>'
        f'<p class="meta">{TOURNAMENT_VENUE_META}<span class="hana-tourinfo-sep"> · </span>'
        f'<span class="hana-tourinfo-holes">72홀 스트로크 플레이</span></p></div>'
        f'<p class="round-update-note">2R 종료 후 업데이트</p></section>{_stage_nav_html()}'
        f'<section class="panel leaderboard-panel" id="r1"><div class="leaderboard-head"><h2>R1 결과 <small>108명</small></h2></div>'
        f'<div class="table-wrap table-wrap--flat-scroll"><table class="data leaderboard-table leaderboard-table--flat-scroll">'
        f'<thead><tr><th>순위</th><th>선수</th><th>1R</th><th>NEO 경기력</th><th>컷 통과율</th><th>TOP20</th><th>TOP10</th>'
        f'<th>TOP5</th><th>우승확률</th></tr></thead><tbody>{rows_html}</tbody></table></div></section></main>'
        f'<nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        f'<a href="{current_stage_href}">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>'
        f'<footer class="site-footer"><div class="site-footer__inner">'
        f'<p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p></div></footer></body>'
    )


def build() -> None:
    current_stage_href = f"{URL_BASE}{_CURRENT_STAGE}/"
    rows_html, row_count = _build_rows_html()
    assert row_count == 108, f"expected 108 R1 rows on the homepage leaderboard, got {row_count}"

    head = (
        f'<head><meta name="neo-home-owner" content="{CURRENT_TOURNAMENT_OWNER}">'
        f'<meta name="neo-stage-publication-ready" content="true"><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>NEO GOLF DATA · {TOURNAMENT_NAME}</title>'
        f'<meta property="og:title" content="NEO GOLF DATA">'
        f'<meta property="og:description" content="KLPGA 공식 데이터 기반 골프 분석">'
        f'<meta property="og:url" content="https://neogolfdata.com/">'
        f'<meta property="og:type" content="website">'
        f'<meta name="twitter:card" content="summary_large_image">'
        f'<link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="/assets/neo.css"></head>'
    )
    html = f'<!DOCTYPE html>\n<html lang="ko">{head}{_body_html(current_stage_href, rows_html)}</html>'

    assert "우승 (3).png" not in html and "kb-2026090003" not in html, "homepage must never reference the KB FINAL image"

    assert_home_write_allowed(
        DOCS_INDEX,
        CURRENT_TOURNAMENT_OWNER,
        repo_root=REPO_ROOT,
        allow_transfer_from=CURRENT_TOURNAMENT_OWNER,
    )
    DOCS_INDEX.write_text(html, encoding="utf-8")
    print("wrote", DOCS_INDEX)
    print("rows:", row_count)


def build_share() -> None:
    """docs/share/index.html -- a cache-bust-only route so Threads'
    stale link-preview cache for www.neogolfdata.com (still showing the
    old KB FINAL page) can be replaced by sharing this new URL instead.
    Same real homepage body as root HOME; its own head carries fresh OG
    tags including a real, newly-rendered representative image that was
    never part of the KB FINAL page. Never writes docs/index.html."""
    current_stage_href = f"{URL_BASE}{_CURRENT_STAGE}/"
    rows_html, row_count = _build_rows_html()
    assert row_count == 108, f"expected 108 R1 rows on the share-page leaderboard, got {row_count}"

    head = (
        f'<head><meta name="neo-stage-publication-ready" content="true"><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>NEO GOLF DATA</title>'
        f'<meta property="og:title" content="NEO GOLF DATA">'
        f'<meta property="og:description" content="KLPGA 공식 데이터 기반 골프 분석">'
        f'<meta property="og:url" content="https://www.neogolfdata.com/share/">'
        f'<meta property="og:type" content="website">'
        f'<meta property="og:image" content="{OG_IMAGE_URL}">'
        f'<meta property="og:image:width" content="{OG_IMAGE_WIDTH}">'
        f'<meta property="og:image:height" content="{OG_IMAGE_HEIGHT}">'
        f'<meta name="twitter:card" content="summary_large_image">'
        f'<meta name="twitter:image" content="{OG_IMAGE_URL}">'
        f'<link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="/assets/neo.css"></head>'
    )
    html = f'<!DOCTYPE html>\n<html lang="ko">{head}{_body_html(current_stage_href, rows_html)}</html>'

    assert "우승 (3).png" not in html and "kb-2026090003" not in html, "share page must never reference the KB FINAL image"
    assert OG_IMAGE_URL in html, "share page must carry the new representative image, never omit it"

    SHARE_PAGE.parent.mkdir(parents=True, exist_ok=True)
    SHARE_PAGE.write_text(html, encoding="utf-8")
    print("wrote", SHARE_PAGE)
    print("rows:", row_count)


def build_share_tournament() -> None:
    """docs/share/2026090002/index.html -- a tournament-named share
    route (operator instruction) carrying Hana-specific OG copy and a
    real screenshot of the actual R1 first screen as its image (see
    scratchpad/shoot_r1_og.py, run separately since this module has no
    browser dependency) -- never the generic /share/ brand card, never
    the KB FINAL image/text. Same real homepage body as root HOME.
    Never writes docs/index.html or the generic docs/share/index.html."""
    current_stage_href = f"{URL_BASE}{_CURRENT_STAGE}/"
    rows_html, row_count = _build_rows_html()
    assert row_count == 108, f"expected 108 R1 rows on the tournament share-page leaderboard, got {row_count}"

    head = (
        f'<head><meta name="neo-stage-publication-ready" content="true"><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>NEO GOLF DATA · {TOURNAMENT_NAME} R1</title>'
        f'<meta property="og:title" content="NEO GOLF DATA · {TOURNAMENT_NAME} R1">'
        f'<meta property="og:description" content="{TOURNAMENT_NAME} R1 공식 결과와 NEO 분석">'
        f'<meta property="og:url" content="https://www.neogolfdata.com/share/{GAME_CODE}/">'
        f'<meta property="og:type" content="website">'
        f'<meta property="og:image" content="{R1_OG_IMAGE_URL}">'
        f'<meta property="og:image:width" content="{R1_OG_IMAGE_WIDTH}">'
        f'<meta property="og:image:height" content="{R1_OG_IMAGE_HEIGHT}">'
        f'<meta name="twitter:card" content="summary_large_image">'
        f'<meta name="twitter:image" content="{R1_OG_IMAGE_URL}">'
        f'<link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="/assets/neo.css"></head>'
    )
    html = f'<!DOCTYPE html>\n<html lang="ko">{head}{_body_html(current_stage_href, rows_html)}</html>'

    assert "우승 (3).png" not in html and "kb-2026090003" not in html, (
        "tournament share page must never reference the KB FINAL image"
    )
    assert "KB금융그룹 챔피언십" not in html, "tournament share page must never reference the KB FINAL tournament name"
    assert R1_OG_IMAGE_URL in html, "tournament share page must carry the real R1-screenshot image, never omit it"

    SHARE_TOURNAMENT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    SHARE_TOURNAMENT_PAGE.write_text(html, encoding="utf-8")
    print("wrote", SHARE_TOURNAMENT_PAGE)
    print("rows:", row_count)


def build_short_share() -> None:
    """docs/2026090002/index.html -- a short-URL alias for
    /share/2026090002/ (operator instruction). Identical real R1
    108-player body, identical title/description/image; only og:url
    points at the short path itself. Never writes SHARE_TOURNAMENT_PAGE
    or any other existing route, and never touches the R1 OG image
    file it references."""
    current_stage_href = f"{URL_BASE}{_CURRENT_STAGE}/"
    rows_html, row_count = _build_rows_html()
    assert row_count == 108, f"expected 108 R1 rows on the short share-page leaderboard, got {row_count}"

    head = (
        f'<head><meta name="neo-stage-publication-ready" content="true"><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>NEO GOLF DATA · {TOURNAMENT_NAME} R1</title>'
        f'<meta property="og:title" content="NEO GOLF DATA · {TOURNAMENT_NAME} R1">'
        f'<meta property="og:description" content="{TOURNAMENT_NAME} R1 공식 결과와 NEO 분석">'
        f'<meta property="og:url" content="https://www.neogolfdata.com/{GAME_CODE}/">'
        f'<meta property="og:type" content="website">'
        f'<meta property="og:image" content="{R1_OG_IMAGE_URL}">'
        f'<meta property="og:image:width" content="{R1_OG_IMAGE_WIDTH}">'
        f'<meta property="og:image:height" content="{R1_OG_IMAGE_HEIGHT}">'
        f'<meta name="twitter:card" content="summary_large_image">'
        f'<meta name="twitter:image" content="{R1_OG_IMAGE_URL}">'
        f'<link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="/assets/neo.css"></head>'
    )
    html = f'<!DOCTYPE html>\n<html lang="ko">{head}{_body_html(current_stage_href, rows_html)}</html>'

    assert "우승 (3).png" not in html and "kb-2026090003" not in html, (
        "short share page must never reference the KB FINAL image"
    )
    assert "KB금융그룹 챔피언십" not in html, "short share page must never reference the KB FINAL tournament name"
    assert R1_OG_IMAGE_URL in html, "short share page must carry the real R1-screenshot image, never omit it"

    SHORT_SHARE_PAGE.parent.mkdir(parents=True, exist_ok=True)
    SHORT_SHARE_PAGE.write_text(html, encoding="utf-8")
    print("wrote", SHORT_SHARE_PAGE)
    print("rows:", row_count)


if __name__ == "__main__":
    build()
    build_share()
    build_share_tournament()
    build_short_share()
