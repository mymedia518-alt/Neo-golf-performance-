"""Build docs/neo-lab/index.html -- explains, in plain language, how
NEO GOLF DATA collects and verifies its data, and why NEO Ranking is
currently held back from publication.

Reuses the honest, non-jargon framing already established by
scripts/88_build_neo_top120_candidate.py's own _neo_lab_html() (never
internal pipeline vocabulary like VALIDATING/PASS/BLOCKED as a badge),
extended with the real, sourced reason NEO Ranking specifically is not
public yet: content/website_v2/NEO_RANKING_PUBLICATION_GATE_DECISION.json
(NEO_RANKING_PUBLICATION=BLOCKED, all three candidate models fail the
EXPOSURE_BIAS gate) and the real backtest write-up
(klpga_pipeline/docs/NEO_RANKING_V1_REDTEAM_BACKTEST.md, verdict
REJECT). Both are cited with their own file path and last-recorded
date so a visitor can trace the claim back to its source, per operator
instruction (게이트 판정과 검증 자료의 출처·기준일을 확인해 방문자가
현재 상태와 공개 보류 이유를 이해할 수 있게 한다).
"""
from __future__ import annotations

import json
import re
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

OUT_PAGE = REPO_ROOT / "docs" / "neo-lab" / "index.html"
GATE_PATH = CONTENT / "NEO_RANKING_PUBLICATION_GATE_DECISION.json"
BACKTEST_MD_PATH = ROOT / "docs" / "NEO_RANKING_V1_REDTEAM_BACKTEST.md"


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


def _backtest_verdict() -> str:
    text = BACKTEST_MD_PATH.read_text(encoding="utf-8")
    m = re.search(r"> 판정: \*\*(.*?)\*\*\s*—\s*(.*)", text)
    if not m:
        return "확인 불가"
    return f"{m.group(1)} — {m.group(2)}"


def main() -> None:
    gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    gate_status = gate["NEO_RANKING_PUBLICATION"]
    gate_rationale = gate["rationale"]
    gate_date = _git_log_date(GATE_PATH)
    failing_gates = gate["failing_gates_by_candidate"]
    backtest_verdict = _backtest_verdict()
    backtest_date = _git_log_date(BACKTEST_MD_PATH)

    candidate_rows = []
    for candidate, gates in failing_gates.items():
        gates_text = ", ".join(gates) if gates else "없음"
        candidate_rows.append(f"<tr><td data-label='모델'>{escape(candidate)}</td><td data-label='통과하지 못한 검증 항목'>{escape(gates_text)}</td></tr>")

    body = (
        '<header data-neo-global-navigation></header><main>'
        '<section class="neo-page-head"><p class="kicker">NEO LAB</p>'
        "<h1>NEO는 숫자를 어떻게 만드나요</h1>"
        "<p>NEO GOLF DATA가 골프 데이터를 수집하고 검증하는 방식을 설명합니다.</p>"
        "</section>"
        '<section class="neo-panel"><h2>공식 기록만 사용합니다</h2>'
        "<p>모든 순위와 기록은 KLPGA 공식 자료를 기준으로 합니다. 확인되지 않은 정보는 추정하지 않고 빈 칸으로 남깁니다.</p></section>"
        '<section class="neo-panel" id="neo-ranking-verification"><h2>NEO Ranking 검증 현황</h2>'
        "<div class='neo-status-card'>"
        f"<p class='status-pill'>검증 진행 중 · 공개 보류</p>"
        f"<p>판정 기준일 {escape(gate_date)}</p></div>"
        "<p>NEO Ranking은 선수의 최근 경기력을 수치로 비교해보려는 자체 모델입니다. "
        "공개하려면 11개 검증 항목을 모두 통과해야 하며, 지금까지 시도한 세 가지 버전(V1·V2A·V2B) 모두 "
        "'노출 편향(EXPOSURE_BIAS)' 검증을 통과하지 못해 공개하지 않습니다.</p>"
        "<div class='neo-table-wrap'><div class='table-scroll' tabindex='0'><table class='neo-table'><thead><tr><th>모델</th><th>통과하지 못한 검증 항목</th></tr></thead>"
        f"<tbody>{''.join(candidate_rows)}</tbody></table></div></div>"
        f"<p class='meta'>근거: {escape(gate_rationale)}</p>"
        f"<p class='meta'>출처 파일: <code>content/website_v2/NEO_RANKING_PUBLICATION_GATE_DECISION.json</code> (기준일 {escape(gate_date)})</p>"
        f"<p class='meta'>배경 검증 보고서: <code>klpga_pipeline/docs/NEO_RANKING_V1_REDTEAM_BACKTEST.md</code> (기준일 {escape(backtest_date)}) — {escape(backtest_verdict)}</p>"
        "<p>검증 기준을 통과하는 항목부터 순서대로 공개하며, 기준을 통과하지 못한 지표는 이 페이지에도, "
        "다른 어떤 페이지에도 순위나 점수로 표시하지 않습니다.</p>"
        "</section>"
        '<section class="neo-panel"><h2>대회별 "NEO 경기력"과는 다릅니다</h2>'
        "<p>일부 대회 페이지에 보이는 'NEO 경기력'은 그 대회에 실제로 출전한 선수들만을 대상으로, "
        "같은 계산식을 해당 대회 안에서만 적용한 참고 지표입니다. 시즌 전체를 비교하는 순위가 아니며, "
        "'NEO Ranking'이나 시즌 랭킹으로 표시하지 않습니다.</p></section>"
        '<section class="neo-panel"><h2>스폰서 표기</h2>'
        "<p>선수 이름 아래 스폰서는 KLPGA 공식 프로필에서 확인된 경우에만 표시합니다. 확인되지 않은 스폰서는 표시하지 않습니다.</p></section>"
        "</main>"
    )

    html = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>NEO LAB · NEO GOLF DATA</title>"
        "<meta name='description' content='NEO GOLF DATA의 데이터 수집·검증 방식과 NEO Ranking 공개 보류 사유를 설명합니다.'>"
        '<link rel="canonical" href="https://neogolfdata.com/neo-lab/">'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        "</head><body>" + body +
        '<footer class="site-footer"><div class="site-footer__inner"><p>NEO GOLF DATA</p></div></footer>'
        "</body></html>"
    )

    html = inject_global_navigation(html, active_section="neo-lab")
    html = ensure_footer_copyright(html)
    html = inject_build_provenance(html, _source_git_sha(), datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))

    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({"written": str(OUT_PAGE), "gate_status": gate_status, "backtest_verdict": backtest_verdict}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
