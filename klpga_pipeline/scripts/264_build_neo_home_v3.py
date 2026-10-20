"""Build docs/index.html -- the real six-section composite HOME.

BRAND DIRECTION (2026-10-20, operator instruction): NEO GOLF DATA is a
golf DATA ANALYSIS company, not a content-curation site. Root HOME is
now a single, fixed structure, always the same shape regardless of
tournament state (see home_ownership_guard.py's OWNER SUPERSESSION 2
note for the policy change this reverses):

  1. 브랜드 소개 -- one short line stating what NEO does.
  2. 랭킹 -- real official K-Ranking preview (top 10 of the real
     HOME_PLAYER_MASTER_TOP120.json, 120 real entrants) + link to the
     full /ranking/ page. NEO Ranking is NOT shown as a ranking: per
     content/website_v2/NEO_RANKING_PUBLICATION_GATE_DECISION.json
     (NEO_RANKING_PUBLICATION=BLOCKED, all three candidate models fail
     EXPOSURE_BIAS), it renders only as a "검증 진행 중 · 공개 보류"
     status card with a link to /neo-lab/ for the evidence. This repo
     already enforces this distinction live (scripts/190's own
     production page builder cites the same gate) -- this script does
     not modify or bypass it.
  3. 대회 데이터 -- the real most-recently-resolved tournament (per
     klpga.website_v2.tournament_chronology, calendar-driven, never
     guessed), its real official result if complete, and a link to its
     real, unmodified stage page. The tournament's own dedicated pages
     (PRE/R1/R2/FR) are completely untouched -- this is a summary card
     only, reusing already-published facts (ICEBERG_2026100003_
     FR_OFFICIAL_V1.json's own winner/winner_to_par via the registry
     entry scripts/263 also depends on).
  4. Deep Dive -- links to the real player analysis pages that exist
     (docs/player/<id>/, excluding any still-"공사중" placeholder) and
     the real tournament archive hub.
  5. NEO LAB -- one-line summary + link to the full methodology page.
  6. 회사 소개와 데이터 기준 -- one-line summary + link to /about/.

Every section shows real counts/cards only when real data backs them;
no section is padded with invented statistics or placeholder cards.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.global_navigation import (  # noqa: E402
    ensure_footer_copyright, inject_build_provenance, inject_global_navigation,
)
from klpga.website_v2.home_ownership_guard import (  # noqa: E402
    COMPOSITE_HOME_OWNER, CURRENT_TOURNAMENT_OWNER, TOP120_OWNER,
    assert_home_write_allowed, embed_game_code, embed_owner,
)
from klpga.website_v2.official_schedule import load_official_schedule  # noqa: E402
from klpga.website_v2.previous_tournament_link import latest_published_stage_url  # noqa: E402
from klpga.website_v2.tournament_chronology import resolve_tournament_chronology  # noqa: E402

DOCS_INDEX = REPO_ROOT / "docs" / "index.html"
TOP120_PATH = CONTENT / "HOME_PLAYER_MASTER_TOP120.json"
GATE_PATH = CONTENT / "NEO_RANKING_PUBLICATION_GATE_DECISION.json"
PLAYER_DIR = REPO_ROOT / "docs" / "player"
TOP_K_PREVIEW = 10


def _source_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def _git_log_date(path: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%ai", "--", str(path.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT, text=True,
        ).strip()
        return out.split(" ")[0] if out else "확인 불가"
    except (subprocess.CalledProcessError, OSError):
        return "확인 불가"


def _real_player_cards() -> list[dict]:
    out = []
    for d in sorted(PLAYER_DIR.iterdir()):
        page = d / "index.html"
        if not page.is_file():
            continue
        html = page.read_text(encoding="utf-8")
        import re
        title_m = re.search(r"<title>(.*?)</title>", html)
        title = title_m.group(1) if title_m else ""
        if "공사중" in title or not title:
            continue
        name = title.split("·")[0].strip()
        out.append({"player_id": d.name, "name": name})
    return out


def main() -> None:
    # SECTION 2: K-Ranking preview
    top120 = json.loads(TOP120_PATH.read_text(encoding="utf-8"))
    records = sorted(top120["records"], key=lambda r: r["official_k_rank"])
    assert len(records) == 120, f"expected 120 K-Ranking records, found {len(records)}"
    preview = records[:TOP_K_PREVIEW]
    ranking_week = top120["ranking_week"]

    gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    gate_status = gate["NEO_RANKING_PUBLICATION"]
    gate_date = _git_log_date(GATE_PATH)

    ranking_rows = "".join(
        f"<tr><td data-label='순위'>{r['official_k_rank']}</td>"
        f"<th scope='row' data-label='선수'><a href='/player/{escape(r['player_id'])}/'>{escape(r['player_name'])}</a></th>"
        f"<td data-label='포인트'>{escape(r['total_points'])}</td></tr>"
        for r in preview
    )

    # SECTION 3: real tournament data (calendar-resolved, never guessed)
    registry = json.loads((CONTENT / "TOURNAMENT_SITE_REGISTRY.json").read_text(encoding="utf-8-sig"))["tournaments"]
    schedule = load_official_schedule(CONTENT / "OFFICIAL_KLPGA_SCHEDULE.json")
    chronology = resolve_tournament_chronology(schedule, registry, as_of=date.today())
    current = chronology.get("current")
    last = chronology.get("last")
    featured = current or last
    tournament_section_html = ""
    if featured is not None and featured.url_base:
        stage_url = latest_published_stage_url(featured.url_base, repo_root=REPO_ROOT)
        status_label = "진행 중" if current is not None else "최근 종료"
        result_line = ""
        if featured.winner:
            score = f" ({featured.winning_score})" if featured.winning_score else ""
            result_line = f"<p>우승: <strong>{escape(featured.winner)}</strong>{escape(score)}</p>"
        tournament_section_html = (
            f"<p class='meta'>{escape(status_label)} · {escape(featured.date_range_display)}"
            + (f" · {escape(featured.venue)}" if featured.venue else "") + "</p>"
            f"<h3>{escape(featured.tournament_name)}</h3>"
            + result_line +
            f"<p><a href='{escape(stage_url)}'>공식 기록 보기 →</a></p>"
        )
    else:
        tournament_section_html = "<p>현재 공개된 대회 데이터가 없습니다.</p>"

    # SECTION 4: Deep Dive preview
    players = _real_player_cards()
    deep_dive_cards = "".join(
        f"<li class='card'><a href='/player/{escape(p['player_id'])}/'>{escape(p['name'])}</a></li>"
        for p in players[:6]
    )

    body = (
        '<header data-neo-global-navigation></header><main>'
        # 1. 브랜드 소개
        '<section class="home-section home-brand-intro">'
        '<p class="kicker">NEO GOLF DATA</p>'
        "<h1>골프 기록을 분석해 경기력을 읽습니다</h1>"
        "<p>NEO GOLF DATA는 KLPGA 공식 기록을 수집·정리·분석하는 데이터 분석 회사입니다. "
        "K-Ranking과 NEO Ranking을 제공하고, 선수·대회 분석을 Deep Dive에서, "
        "예측과 검증 과정을 NEO LAB에서 확인할 수 있습니다.</p>"
        "</section>"
        # 2. 랭킹
        '<section class="home-section" id="ranking">'
        '<div class="section-heading"><div><p class="section-label">랭킹</p>'
        f"<h2>K-Ranking <small>{escape(ranking_week)} 기준</small></h2></div></div>"
        "<div class='table-scroll' tabindex='0'><table class='home-ranking-preview'>"
        "<thead><tr><th>순위</th><th>선수</th><th>포인트</th></tr></thead>"
        f"<tbody>{ranking_rows}</tbody></table></div>"
        "<p class='section-link-row'><a href='/ranking/'>K-Ranking 전체 120명 보기 →</a></p>"
        "<div class='neo-status-card'><p class='status-pill'>NEO Ranking · 검증 진행 중 · 공개 보류</p>"
        f"<p>검증 게이트 판정: <code>{escape(gate_status)}</code> (기준일 {escape(gate_date)}). "
        "검증 기준을 통과하지 못한 순위·점수는 공개하지 않습니다.</p>"
        "<p><a href='/neo-lab/'>검증 근거 보기 →</a></p></div>"
        "</section>"
        # 3. 대회 데이터
        '<section class="home-section" id="tournament-data">'
        '<div class="section-heading"><div><p class="section-label">대회 데이터</p>'
        "<h2>대회 공식 기록</h2></div></div>"
        + tournament_section_html +
        "</section>"
        # 4. Deep Dive
        '<section class="home-section" id="deep-dive">'
        '<div class="section-heading"><div><p class="section-label">딥다이브</p>'
        "<h2>선수·대회 분석</h2></div></div>"
        f"<ul class='card-list'>{deep_dive_cards}</ul>"
        "<p class='section-link-row'><a href='/deep-dive/'>Deep Dive 전체 보기 →</a></p>"
        "</section>"
        # 5. NEO LAB
        '<section class="home-section" id="neo-lab">'
        '<div class="section-heading"><div><p class="section-label">NEO LAB</p>'
        "<h2>데이터와 모델을 검증하는 방식</h2></div></div>"
        "<p>NEO GOLF DATA가 공식 기록을 확인하고, 예측을 검증하는 방식을 설명합니다. "
        "검증 기준을 통과하지 못한 지표는 공개하지 않습니다.</p>"
        "<p class='section-link-row'><a href='/neo-lab/'>NEO LAB 보기 →</a></p>"
        "</section>"
        # 6. 회사 소개와 데이터 기준
        '<section class="home-section" id="about">'
        '<div class="section-heading"><div><p class="section-label">소개</p>'
        "<h2>회사 소개와 데이터 기준</h2></div></div>"
        "<p>분석 범위, 기록 기준, 자료 출처와 한계를 설명합니다.</p>"
        "<p class='section-link-row'><a href='/about/'>자세히 보기 →</a></p>"
        "</section>"
        "</main>"
    )

    head = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>NEO GOLF DATA · 골프 데이터 분석</title>"
        "<meta name='description' content='NEO GOLF DATA는 KLPGA 공식 기록을 분석하는 데이터 분석 회사입니다. K-Ranking, 대회 공식 기록, 선수 분석, 검증 과정을 제공합니다.'>"
        '<link rel="canonical" href="https://neogolfdata.com/">'
        '<meta property="og:title" content="NEO GOLF DATA">'
        "<meta property='og:description' content='골프 기록을 분석해 경기력을 읽습니다.'>"
        '<meta property="og:url" content="https://neogolfdata.com/">'
        '<meta property="og:type" content="website">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="/assets/neo.css">'
        "</head><body>"
    )
    html = head + body + '<footer class="site-footer"><div class="site-footer__inner"><p>NEO · Number · Evidence · Oracle</p></div></footer></body></html>'

    html = inject_global_navigation(html, active_section="home")
    html = ensure_footer_copyright(html)
    html = inject_build_provenance(html, _source_git_sha(), datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    html = embed_owner(html, COMPOSITE_HOME_OWNER)
    if featured is not None:
        html = embed_game_code(html, featured.game_code)

    # The prior owner could be EITHER TOP120_OWNER or CURRENT_TOURNAMENT_
    # OWNER depending on what state root HOME was last left in (see
    # OWNER SUPERSESSION 2) -- read whichever is actually on disk and
    # pass that as allow_transfer_from (assert_home_write_allowed only
    # accepts one value per call, and a no-op transfer when root HOME
    # is already COMPOSITE_HOME_OWNER-owned or unclaimed is harmless).
    from klpga.website_v2.home_ownership_guard import extract_owner
    existing_owner = extract_owner(DOCS_INDEX.read_text(encoding="utf-8")) if DOCS_INDEX.is_file() else None
    transfer_from = existing_owner if existing_owner in (TOP120_OWNER, CURRENT_TOURNAMENT_OWNER) else CURRENT_TOURNAMENT_OWNER
    assert_home_write_allowed(
        DOCS_INDEX, COMPOSITE_HOME_OWNER, repo_root=REPO_ROOT, allow_transfer_from=transfer_from,
    )

    DOCS_INDEX.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({
        "written": str(DOCS_INDEX),
        "k_ranking_preview_rows": len(preview),
        "neo_ranking_gate_status": gate_status,
        "featured_tournament": featured.tournament_name if featured else None,
        "deep_dive_player_cards": len(players[:6]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
