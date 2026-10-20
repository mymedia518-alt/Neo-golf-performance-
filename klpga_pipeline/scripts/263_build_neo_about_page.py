"""Build docs/about/index.html -- company/data-standards page.

Content is grounded in what this repo actually does, not aspirational
copy: official-source-only collection, the hash-verification and
player-identity-linkage conventions already used throughout the
pipeline (see e.g. klpga.website_v2.official_data, player_identity),
and an honest statement of current scope/limits (which tournaments are
covered, that NEO Ranking is not yet published, that course-level
analysis does not exist yet). No invented company history, team, or
metrics.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.global_navigation import (  # noqa: E402
    ensure_footer_copyright, inject_build_provenance, inject_global_navigation,
)

OUT_PAGE = REPO_ROOT / "docs" / "about" / "index.html"


def _source_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def main() -> None:
    body = (
        '<header data-neo-global-navigation></header><main>'
        '<section class="page-head"><p class="kicker">소개</p>'
        "<h1>NEO GOLF DATA</h1>"
        "<p>NEO GOLF DATA는 골프 기록을 수집·정리·분석하는 데이터 분석 회사입니다. "
        "영상이나 뉴스를 만드는 콘텐츠 사이트가 아니라, KLPGA 공식 기록을 기반으로 "
        "경기력을 읽을 수 있는 수치와 분석을 제공합니다.</p>"
        "</section>"
        '<section class="product-section"><h2>데이터 기준</h2>'
        "<dl class='data-standards'>"
        "<dt>수집 범위</dt><dd>KLPGA 공식 홈페이지에 게시되는 대회 리더보드, Strokes Gained(SG) 세부 기록, "
        "K-Ranking을 대상으로 합니다.</dd>"
        "<dt>선수 식별</dt><dd>모든 선수 기록은 KLPGA 공식 선수 코드(playerCode)로 연결합니다. "
        "동명이인이나 다른 시즌의 기록이 섞이지 않도록 선수 코드 단위로 검증합니다.</dd>"
        "<dt>결측 처리</dt><dd>공식 자료로 확인되지 않는 값은 추정하거나 0으로 채우지 않고 "
        "“데이터 부족” 또는 빈 칸으로 남깁니다.</dd>"
        "<dt>예측과 실제 결과</dt><dd>대회 중 제공하는 확률·순위 예측은 그 시점까지의 공식 기록만으로 "
        "계산하며, 이후 실제 결과로 소급해 바꾸지 않습니다. 실제 결과는 별도 항목으로 표시합니다.</dd>"
        "<dt>검증 기준을 통과하지 못한 모델</dt><dd>자체 검증을 통과하지 못한 지표나 모델은 "
        "순위·점수로 공개하지 않습니다. 현재 상태는 <a href='/neo-lab/'>NEO LAB</a>에서 확인할 수 있습니다.</dd>"
        "</dl></section>"
        '<section class="product-section"><h2>현재 범위와 한계</h2>'
        "<ul>"
        "<li>선수 분석은 공식 기록이 충분히 확보된 선수부터 순서대로 제공하며, 전체 선수를 다루지 않습니다.</li>"
        "<li>코스 단위 분석은 아직 제공하지 않습니다.</li>"
        "<li>NEO Ranking은 검증을 통과하지 못해 공개하지 않습니다.</li>"
        "</ul></section>"
        "</main>"
    )

    html = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>NEO GOLF DATA 소개</title>"
        "<meta name='description' content='NEO GOLF DATA는 KLPGA 공식 기록을 기반으로 골프 데이터를 수집·정리·분석하는 데이터 분석 회사입니다.'>"
        '<link rel="canonical" href="https://neogolfdata.com/about/">'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        "</head><body>" + body +
        '<footer class="site-footer"><div class="site-footer__inner"><p>NEO GOLF DATA</p></div></footer>'
        "</body></html>"
    )

    html = inject_global_navigation(html, active_section="about")
    html = ensure_footer_copyright(html)
    html = inject_build_provenance(html, _source_git_sha(), datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))

    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({"written": str(OUT_PAGE)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
