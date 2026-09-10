"""Build the public KB 2026090003 R1 page from the frozen
2026090003_R1_5PROB_FROZEN_V1.json, mirroring the live PRE page's exact
HTML structure/CSS classes (docs/tournaments/2026/2026090003/pre/index.html)
so R1 looks and behaves consistently with it. Also updates the PRE
page's own stage-nav to link forward to R1 (was a disabled placeholder).

SPONSOR INVARIANT: every displayed player name is followed by a
<span class='player-sponsor'> using ONLY KB_2026090003_SPONSOR_
INTEGRITY_AUDIT_V2.json's verified_official sponsors -- never guessed.
A player without a verified sponsor gets an empty span, exactly like
the PRE page already does for its own unverified players.
"""
from __future__ import annotations

import json
import re
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root (docs/ lives here, not under klpga_pipeline/)
PIPELINE_ROOT = Path(__file__).resolve().parents[1]
CONTENT = PIPELINE_ROOT / "content" / "website_v2"
GAME_CODE = "2026090003"
PRE_PAGE = ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html"
R1_PAGE = ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html"


def load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def build_r1_page() -> str:
    freeze = load(f"{GAME_CODE}_R1_5PROB_FROZEN_V1.json")
    sponsor_audit = load("KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V2.json")
    sponsor_by_id = {r["player_id"]: r["sponsor"] for r in sponsor_audit["newly_recovered_sponsors"]}
    pre_frozen = load(f"{GAME_CODE}_PRE_5PROB_V2_FROZEN.json")
    pre_win_by_id = {p["playerCode"]: p["win_probability"] for p in pre_frozen["predictions"]}

    all_rows = list(freeze["predictions"]) + [
        {**e, "r1_score": None, "r1_to_par": None, "r1_rank_display": None, "cut": None, "top20": None, "top10": None, "top5": None, "win": None}
        for e in freeze["excluded_players"]
    ]
    all_rows.sort(key=lambda r: (r["r1_to_par"] is None, r["r1_to_par"] if r["r1_to_par"] is not None else 0))

    def pct(v):
        return "—" if v is None else f"{v * 100:.2f}%"

    def cell(v, label):
        cls = "" if v is None else " class='win'"
        return f"<td{cls} data-label='{label}'>{pct(v)}</td>"

    rows_html = []
    for r in all_rows:
        pid = r["player_id"]
        sponsor = escape(sponsor_by_id.get(pid, ""))
        name = escape(r["player_name"])
        to_par = r["r1_to_par"]
        to_par_display = "—" if to_par is None else (f"{to_par:+d}" if to_par != 0 else "E")
        score_display = "—" if r["r1_score"] is None else str(r["r1_score"])
        rows_html.append(
            "<tr>"
            f"<th scope='row'><span class='player-name'>{name}</span><span class='player-sponsor'>{sponsor}</span></th>"
            f"<td data-label='R1 스코어'>{score_display}</td>"
            f"<td data-label='R1 TO PAR'>{to_par_display}</td>"
            + cell(r["cut"], "컷 통과확률")
            + cell(r["top20"], "TOP20")
            + cell(r["top10"], "TOP10")
            + cell(r["top5"], "TOP5")
            + cell(r["win"], "우승확률")
            + "</tr>"
        )

    movers = []
    for p in freeze["predictions"]:
        pre_win = pre_win_by_id.get(p["player_id"])
        if pre_win is not None:
            movers.append((p["player_name"], sponsor_by_id.get(p["player_id"], ""), pre_win, p["win"]))
    movers.sort(key=lambda m: (m[3] - m[2]), reverse=True)
    top_movers = movers[:3]
    movers_html = "".join(
        f"<li><strong>{escape(name)}</strong> {escape(sponsor) or ''} — PRE {pre_w*100:.2f}% → R1 {r1_w*100:.2f}% "
        f"({'+' if r1_w - pre_w >= 0 else ''}{(r1_w - pre_w) * 100:.2f}pt)</li>"
        for name, sponsor, pre_w, r1_w in top_movers
    )

    excluded_names = ", ".join(escape(e["player_name"]) for e in freeze["excluded_players"])
    wd_names = ", ".join(escape(w["playerCode"]) for w in freeze["official_wd"])

    body = (
        '<nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><a href="/tournaments/">대회</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><span>KB금융 골든라이프 챔피언십</span>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><span aria-current="page">R1</span></nav>'
        '<section class="hero" id="tournament"><div><p class="eyebrow">R1 업데이트</p>'
        '<h1>KB금융 골든라이프 챔피언십</h1><p class="meta">2026.09.10 — 09.13</p></div>'
        '<strong class="status">R1</strong></section>'
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/pre/">사전 분석 PRE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r1/" aria-current="page">R1</a></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R2</span></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R3</span></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">FINAL</span></li>'
        '</ol></nav>'
        '<section class="panel leaderboard-panel" id="r1">'
        f'<div class="leaderboard-head"><h2>R1 결과 및 업데이트된 확률 <small>{len(freeze["predictions"])}명 예측</small></h2>'
        f'<p class="note">R1 완료 118명 · 기권(WD) 2명 · PRE 이력 부족으로 확률 미산출 {len(freeze["excluded_players"])}명({excluded_names})</p></div>'
        '<div class="table-wrap"><table class="data leaderboard-table"><thead><tr>'
        "<th>선수</th><th>R1 스코어</th><th>R1 TO PAR</th><th>컷 통과확률</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div></section>"
        '<section class="panel" id="pre-r1-movement"><h2>PRE → R1 주요 변동</h2>'
        f"<ul>{movers_html}</ul>"
        "<p class=\"note\">우승확률 기준 PRE 대비 R1 이후 가장 크게 상승한 3명. NEO_R1_MODEL_V1 (PRE 사전 강도 + R1 관측 성적 결합, 검증된 고정 모델)로 산출.</p>"
        "</section>"
    )

    return body


PRE_STAGE_NAV_RE = re.compile(r'<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R1</span></li>')
PRE_STAGE_NAV_REPLACEMENT = f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r1/">R1</a></li>'


def update_pre_page_stage_nav(pre_html: str) -> str:
    updated, count = PRE_STAGE_NAV_RE.subn(PRE_STAGE_NAV_REPLACEMENT, pre_html, count=1)
    if count != 1:
        raise ValueError("expected exactly one disabled R1 stage-nav placeholder in the PRE page -- refusing to guess")
    return updated


def main() -> int:
    pre_html = PRE_PAGE.read_text(encoding="utf-8")
    header_prefix = pre_html.split("<main>", 1)[0] + "<main>"
    footer_suffix = "</main>" + pre_html.split("</main>", 1)[1]
    r1_html = header_prefix.replace(">PRE 참가 선수", ">R1 업데이트").replace('"status">PRE<', '"status">R1<') + build_r1_page() + footer_suffix
    r1_html = r1_html.replace("<title>NEO GOLF DATA · KB금융 골든라이프 챔피언십</title>", "<title>NEO GOLF DATA · KB금융 골든라이프 챔피언십 R1</title>")

    R1_PAGE.parent.mkdir(parents=True, exist_ok=True)
    R1_PAGE.write_text(r1_html, encoding="utf-8", newline="\n")

    updated_pre_html = update_pre_page_stage_nav(pre_html)
    PRE_PAGE.write_text(updated_pre_html, encoding="utf-8", newline="\n")

    print(json.dumps({"r1_page": str(R1_PAGE), "pre_page_updated": str(PRE_PAGE)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
