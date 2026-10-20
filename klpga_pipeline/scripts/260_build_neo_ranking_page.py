"""Build docs/ranking/index.html -- the real, permanent K-Ranking page.

BRAND DIRECTION (2026-10-20): NEO GOLF DATA is a data-analysis company,
not a content-curation site. This page shows the real official
K-Ranking (KLPGA's own weekly published ranking, content/website_v2/
HOME_PLAYER_MASTER_TOP120.json -- 120 real players, real source URL,
real retrieval timestamp) and nothing else as a "ranking".

NEO Ranking is deliberately NOT shown as a ranking here. Per
content/website_v2/NEO_RANKING_PUBLICATION_GATE_DECISION.json,
NEO_RANKING_PUBLICATION is BLOCKED -- none of the three candidate
models (V1/V2A/V2B) pass all 11 required validation gates (all three
fail EXPOSURE_BIAS). This is an existing, actively-enforced governance
decision (already referenced by scripts/190's own production page
builder); this script does not modify, bypass, or soften it. Instead
of a ranking table, NEO Ranking gets a status card stating the real
gate outcome, its source file, and the date that decision was last
recorded (git log date of the gate-decision file), with a link to
/neo-lab/ for the full verification evidence.

A richer "최근 10R/5R SG 비교" column set exists in a prior candidate
(scripts/88_build_neo_top120_candidate.py's render_clean()) but
depends on content/website_v2/historical_sg_warehouse_corrected.json,
which does not currently exist in this repo (confirmed: no such file
anywhere in the tree). This script does not attempt to reconstruct
that missing multi-stage warehouse pipeline -- out of scope for a
homepage rebuild -- so it shows only what is actually present: the
official K-Ranking fields themselves (rank/name/rating/points/event
count), never a fabricated or partially-computed SG column.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.global_navigation import (  # noqa: E402
    ensure_footer_copyright, inject_build_provenance, inject_global_navigation,
)

OUT_PAGE = REPO_ROOT / "docs" / "ranking" / "index.html"
TOP120_PATH = CONTENT / "HOME_PLAYER_MASTER_TOP120.json"
GATE_PATH = CONTENT / "NEO_RANKING_PUBLICATION_GATE_DECISION.json"


def _git_log_date(path: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%ai", "--", str(path.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT, text=True,
        ).strip()
        return out.split(" ")[0] if out else "확인 불가"
    except (subprocess.CalledProcessError, OSError):
        return "확인 불가"


def _source_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def main() -> None:
    top120 = json.loads(TOP120_PATH.read_text(encoding="utf-8"))
    records = top120["records"]
    assert len(records) == 120, f"expected 120 K-Ranking records, found {len(records)}"
    ranking_week = top120["ranking_week"]
    official_source = top120["official_source"]
    retrieved_at = top120["retrieved_at"]

    gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    gate_status = gate["NEO_RANKING_PUBLICATION"]
    gate_rationale = gate["rationale"]
    gate_date = _git_log_date(GATE_PATH)

    rows_html = []
    for r in sorted(records, key=lambda r: r["official_k_rank"]):
        rows_html.append(
            "<tr>"
            f"<td data-label='순위'>{r['official_k_rank']}</td>"
            f"<th scope='row' data-label='선수'><a href='/player/{escape(r['player_id'])}/'>{escape(r['player_name'])}</a></th>"
            f"<td data-label='포인트'>{escape(r['total_points'])}</td>"
            f"<td data-label='레이팅'>{escape(r['rating'])}</td>"
            f"<td data-label='출전'>{r['event_count']}</td>"
            "</tr>"
        )

    body = (
        '<header data-neo-global-navigation></header><main>'
        '<section class="page-head"><p class="kicker">랭킹</p>'
        '<h1>K-Ranking</h1>'
        f"<p>KLPGA가 매주 발표하는 공식 랭킹입니다. 기준 주차 {escape(ranking_week)}, "
        f"수집 시각 {escape(retrieved_at)} · <a href='{escape(official_source)}' rel='noopener'>공식 출처 ↗</a></p>"
        '</section>'
        '<section class="product-section">'
        '<div class="table-scroll" tabindex="0" aria-label="K-Ranking 표 가로 스크롤">'
        "<table class='data-table'><thead><tr><th>순위</th><th>선수</th><th>포인트</th><th>레이팅</th><th>출전</th></tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody></table></div>"
        "</section>"
        '<section class="product-section" id="neo-ranking-status">'
        "<h2>NEO Ranking</h2>"
        f"<p><strong>검증 진행 중 · 공개 보류</strong> — NEO Ranking은 아직 공개 기준을 통과하지 못했습니다.</p>"
        f"<p>검증 게이트 판정: <code>{escape(gate_status)}</code> (기준일 {escape(gate_date)}, "
        f"근거 파일 <code>NEO_RANKING_PUBLICATION_GATE_DECISION.json</code>)</p>"
        f"<p>{escape(gate_rationale)}</p>"
        "<p>검증 과정과 세부 근거는 <a href='/neo-lab/'>NEO LAB</a>에서 확인할 수 있습니다.</p>"
        "</section>"
        "</main>"
    )

    html = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>K-Ranking · NEO GOLF DATA</title>"
        f"<meta name='description' content='KLPGA 공식 K-Ranking 전체 120명. NEO Ranking은 검증 진행 중으로 공개 보류 상태입니다.'>"
        '<link rel="canonical" href="https://neogolfdata.com/ranking/">'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        "</head><body>" + body +
        '<footer class="site-footer"><div class="site-footer__inner"><p>NEO · Number · Evidence · Oracle</p></div></footer>'
        "</body></html>"
    )

    html = inject_global_navigation(html, active_section="ranking")
    html = ensure_footer_copyright(html)
    html = inject_build_provenance(html, _source_git_sha(), datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))

    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({"written": str(OUT_PAGE), "k_ranking_rows": len(records), "gate_status": gate_status}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
