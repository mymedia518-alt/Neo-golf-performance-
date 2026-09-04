"""Build the OK Open PRE candidate from the canonical public master only."""
from __future__ import annotations

import html
import json
import hashlib
import subprocess
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "content" / "website_v2" / "OK_OPEN_2026_PRE_PUBLIC_MASTER.json"
OUT = ROOT / "candidate" / "website-v2-ok-open-pre"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.global_navigation import inject_global_navigation  # noqa: E402
from klpga.website_v2.shell import breadcrumb_html, stage_nav_html  # noqa: E402
from klpga.website_v2.tournament_state import OK_BASE, OK_DISPLAY_NAME, ok_open_available_stages  # noqa: E402


def _ok_stage_items(current: str) -> list[tuple[str, str | None, bool]]:
    # Same shared component KG uses (shell.stage_nav_html). Which stages
    # are real (not a disabled/fake link) comes from the single shared
    # tournament_state.ok_open_available_stages() -- the same function
    # HOME's tournament-day hero reads -- not a second, hand-duplicated
    # copy of this dict.
    real = ok_open_available_stages()
    return [
        (label.upper(), real.get(key), key == current)
        for key, label in (("pre", "PRE"), ("r1", "R1"), ("r2", "R2"), ("final", "FINAL"))
    ]

BANDS = {
    "VERY_HIGH": "최상위",
    "HIGH": "상위",
    "TYPICAL": "중위",
    "LOW": "하위",
    "VERY_LOW": "최하위",
    "INSUFFICIENT_EVIDENCE": "데이터 부족",
}

CSS = """
:root{--ink:#17202a;--muted:#65717d;--line:#dfe5ea;--accent:#0c6b68;--soft:#f4f7f7}
*{box-sizing:border-box}body{margin:0;color:var(--ink);font-family:Pretendard,"Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",system-ui,sans-serif;background:#fff;line-height:1.45}main{max-width:1240px;margin:auto;padding:22px 28px}h1{font-size:clamp(26px,2.6vw,38px);margin:8px 0 6px;letter-spacing:-.03em;word-break:keep-all;overflow-wrap:normal}h2{font-size:20px;margin:0 0 14px}.eyebrow{font-size:12px;font-weight:700;letter-spacing:.12em;color:var(--accent);text-transform:uppercase}.meta,.note{color:var(--muted);font-size:14px}.hero{padding:20px 0 18px;display:flex;justify-content:space-between;gap:30px;align-items:end}.status{font-size:14px;color:var(--accent);border:1px solid #acd0cc;border-radius:999px;padding:7px 13px}.grid{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(280px,.8fr);gap:22px;align-items:start}.panel{border:1px solid var(--line);border-radius:14px;background:#fff;padding:20px}.table-wrap{overflow-x:auto}.data{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}.data th,.data td{padding:11px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;font-size:14px}.data th:first-child,.data td:first-child{text-align:left}.data tbody tr:hover{background:var(--soft)}.player{display:block;font-weight:700;text-align:left}.sponsor{display:block;color:var(--muted);font-size:12px;font-weight:400;text-align:left;margin-top:2px}.band{display:inline-block;padding:3px 7px;border-radius:999px;background:#edf4f3;color:#245c58;font-size:12px}.win{font-weight:800;color:var(--accent)}.evolution{display:flex;flex-direction:column}.checkpoint{display:flex;align-items:baseline;gap:10px;border-left:3px solid var(--accent);padding:10px 14px;background:var(--soft);margin-top:12px}.checkpoint .note{margin:0}.metric{font-size:22px;font-weight:800;font-variant-numeric:tabular-nums;flex-shrink:0}.help{margin-top:22px;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}.sr-only{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}@media(max-width:760px){main{padding:18px 16px}.hero{padding-top:28px;display:block}.status{display:inline-block;margin-top:14px}.grid{grid-template-columns:1fr}.panel{padding:14px}.data{min-width:700px}.table-wrap:after{content:"↔ 표를 옆으로 밀어 더 많은 열 보기";display:block;color:var(--muted);font-size:12px;padding-top:8px}.data th,.data td{padding:10px 8px}}
/* MOBILE_CONTAINMENT */
.grid > *,.panel{min-width:0}.table-wrap{width:100%;max-width:100%;overflow-x:auto;overflow-y:hidden}
/* Public table is centered; numeric columns retain tabular numerals. */
.data th,.data td{text-align:center}.data th:first-child,.data td:first-child{text-align:center}.player,.sponsor{text-align:center}
.info-control{border:0;background:transparent;color:var(--accent);font:inherit;font-weight:700;cursor:pointer;padding:2px 4px}.info-popover{display:none;position:absolute;z-index:2;max-width:260px;margin-top:6px;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:#fff;box-shadow:0 4px 14px #17202a1a;color:var(--ink);font-size:13px;font-weight:400}.info-popover.is-open{display:block}
@media(max-width:760px){.info-popover{position:fixed;left:16px;right:16px;top:112px;width:auto;max-width:none;margin:0}}
"""

def pct(value):
    return "—" if value is None else f"{float(value)*100:.2f}%"
def value(value):
    return "—" if value is None else html.escape(str(value))

def build() -> Path:
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    # Use the repository's canonical blob bytes so Windows newline conversion
    # cannot produce a stale provenance hash for the consumed master.
    rel_master = MASTER.relative_to(ROOT.parent).as_posix()
    try:
        source_bytes = subprocess.check_output(["git", "cat-file", "-p", f"HEAD:{rel_master}"], cwd=ROOT.parent)
    except (OSError, subprocess.CalledProcessError):
        source_bytes = MASTER.read_bytes()
    master_sha = hashlib.sha256(source_bytes).hexdigest().upper()
    records = list(master["records"])
    if len(records) != 120:
        raise ValueError(f"canonical master must contain 120 records, got {len(records)}")
    # Neutral, reproducible display order: official K-RANKING, then canonical ID.
    records.sort(key=lambda r: (r.get("official_klpga_rank") is None, r.get("official_klpga_rank") or 10**9, str(r["player_id"])))
    rows = []
    for r in records:
        name = value(r.get("current_official_player_name"))
        sponsor = value(r.get("current_official_sponsor"))
        enum = r.get("neo_performance_band")
        band = BANDS.get(enum, "데이터 부족")
        accessible = {"VERY_HIGH":"최상위", "HIGH":"상위", "TYPICAL":"중위", "LOW":"하위", "VERY_LOW":"최하위", "INSUFFICIENT_EVIDENCE":"데이터 부족"}.get(enum, "데이터 부족")
        rows.append(f"<tr><th scope='row'><span class='player'>{name}</span><span class='sponsor'>{sponsor}</span></th><td>{value(r.get('official_klpga_rank'))}</td><td><span class='band' role='img' aria-label='NEO 경기력 {html.escape(accessible)}'>{html.escape(band)}</span></td><td>{value(r.get('sg_total_rank'))}</td><td class='win'>{pct(r.get('win_probability'))}</td></tr>")
    # base_url=None: OK Open has no distinct "overview" route the way KG
    # does (its PRE page IS the tournament's landing page) -- linking the
    # breadcrumb's tournament-name crumb to a route that doesn't exist
    # would 404, so it renders as plain text instead (see breadcrumb_html).
    breadcrumb = breadcrumb_html(OK_DISPLAY_NAME, None, "PRE")
    stage_nav = stage_nav_html(_ok_stage_items("pre"))
    html_doc = f"""<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>NEO GOLF DATA · OK저축은행 읏맨 오픈</title><link rel=\"stylesheet\" href=\"/assets/neo-site.css\"><link rel=\"stylesheet\" href=\"assets/neo.css\"></head><body><header data-neo-global-navigation></header><main>{breadcrumb}<section class=\"hero\" id=\"tournament\"><div><p class=\"eyebrow\">다음 대회 · PRE</p><h1>OK저축은행 읏맨 오픈</h1><p class=\"meta\">2026.09.04 — 09.06 · 포천아도니스 · 54홀 스트로크 플레이</p></div><strong class=\"status\">예측 확정 전</strong></section>{stage_nav}<div class=\"grid\"><section class=\"panel\" id=\"pre\"><h2>PRE 참가 선수 <small>{len(records)}명</small></h2><p class=\"note\">K-RANKING은 누적 성과, NEO는 최근 경기력을 봅니다.</p><div class=\"table-wrap\"><table class=\"data\"><thead><tr><th>선수</th><th>KLPGA K-RANKING</th><th>NEO 경기력 구간</th><th>SG Total 순위</th><th>우승확률</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><div class=\"help\">K-RANKING이 ‘쌓아온 성과’를 보여준다면, NEO는 ‘지금의 경기력’을 봅니다. 두 지표는 서로 다른 시간축과 평가 기준을 사용합니다.</div></section><aside class=\"panel evolution\"><p class=\"eyebrow\">PRE · 우승 가능성 변화</p><h2>우승 가능성 변화</h2><p class=\"note\">검증된 PRE 체크포인트만 표시합니다. R1·R2·FINAL 결과가 생기기 전에는 관측값을 만들지 않습니다.</p><div class=\"checkpoint\"><div class=\"metric\">PRE</div><p class=\"note\">참가 선수별 우승확률은 표에서 확인할 수 있습니다.</p></div></aside></div></main></body></html>"""
    html_doc = html_doc.replace("NEO 경기력 구간", "NEO 경기력 ⓘ")
    html_doc = html_doc.replace('href="tournaments/2026/ok-savings-bank-open/', 'href="/tournaments/2026/ok-savings-bank-open/')
    html_doc = html_doc.replace("<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">", "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><meta name=\"neo-public-master-sha256\" content=\"" + master_sha + "\">")
    html_doc = html_doc.replace('<a href="#pre">예측 기록</a>', '<a href="tournaments/2026/ok-savings-bank-open/pre/">예측 기록</a>')
    html_doc = html_doc.replace("<th>NEO 경기력 ⓘ</th>", "<th class='band-head'>NEO 경기력 <button type='button' class='info-control' aria-label='NEO 경기력 설명' aria-expanded='false' aria-controls='neo-info'>ⓘ</button><span id='neo-info' class='info-popover' role='tooltip'>최근 공식 경기 데이터를 출전 선수들과 비교한 상대적 경기력 위치입니다.</span></th>")
    html_doc = html_doc.replace("지금의 경기력", "최근 경기력")
    html_doc = html_doc.replace("</body></html>", "<script>(function(){const b=document.querySelector('.info-control'),p=document.getElementById('neo-info');if(!b||!p)return;function close(){p.classList.remove('is-open');b.setAttribute('aria-expanded','false')}b.addEventListener('click',function(){const open=p.classList.toggle('is-open');b.setAttribute('aria-expanded',String(open));if(open)p.focus()});b.addEventListener('keydown',function(e){if(e.key==='Escape')close()});document.addEventListener('click',function(e){if(!b.contains(e.target)&&!p.contains(e.target))close()})})();</script></body></html>")
    if OUT.exists(): shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    (OUT / "assets" / "neo.css").write_text(CSS, encoding="utf-8")
    html_doc = inject_global_navigation(html_doc, active_section="tournaments")
    (OUT / "index.html").write_text(html_doc, encoding="utf-8")
    (OUT / "pre").mkdir()
    (OUT / "pre" / "index.html").write_text(html_doc.replace('href="assets/neo.css"','href="../assets/neo.css"'), encoding="utf-8")
    route_root = OUT / "tournaments" / "2026" / "ok-savings-bank-open"
    route = route_root / "pre"
    route.mkdir(parents=True)
    route_html = html_doc.replace('href="assets/neo.css"', 'href="../../../../assets/neo.css"')
    (route / "index.html").write_text(route_html, encoding="utf-8")
    for stage in ("r1", "r2", "final"):
        stage_dir = route_root / stage
        stage_dir.mkdir(parents=True)
        crumb = breadcrumb_html(OK_DISPLAY_NAME, None, stage.upper())
        nav = stage_nav_html(_ok_stage_items(stage))
        stage_doc = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                     f'<meta name="neo-public-master-sha256" content="{master_sha}"><title>NEO GOLF DATA · {stage.upper()}</title>'
                     f'<link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="../../../assets/neo.css"></head>'
                     f'<body><header data-neo-global-navigation></header><main>{crumb}<section class="panel"><p class="eyebrow">{stage.upper()} · 아직 시작 전</p>'
                     f'<h1>공식 {stage.upper()} 데이터가 아직 없습니다.</h1><p class="note">공식 단계 산출물이 생성되면 이 화면에서 확인할 수 있습니다. 현재는 예측값이나 결과를 만들지 않습니다.</p>{nav}</section></main></body></html>')
        (stage_dir / "index.html").write_text(inject_global_navigation(stage_doc, active_section="tournaments"), encoding="utf-8")
    about = """<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>NEO GOLF DATA · NEO 소개</title><link rel=\"stylesheet\" href=\"../assets/neo.css\"></head><body><header data-neo-global-navigation></header><main><section class=\"panel about\" id=\"about\"><p class=\"eyebrow\">NEO 소개</p><h1>결과만으로는 보이지 않는 경기력을 데이터에서 봅니다.</h1><p>NEO GOLF DATA는 KLPGA 공식 경기 기록을 바탕으로 선수들의 경기 데이터를 동일한 기준으로 측정하고 비교합니다.</p><p>우승, TOP10, 상금, K-RANKING은 선수가 쌓아온 중요한 결과입니다. NEO는 여기에 또 하나의 관점을 더합니다.</p><p>최근 공식 경기 데이터를 비교해 출전 선수들 사이에서 관측된 경기력의 상대적 위치를 보여줍니다.</p><p>이것은 선수의 가치나 미래 성적에 대한 등급이 아닙니다. 골프의 결과에는 큰 변동성이 있으며 높은 경기력 위치가 우승이나 TOP10을 보장하지 않습니다.</p><p>NEO는 분석 시점에 사용할 수 있었던 데이터를 보존하고, 실제 결과와 비교하며 분석 방법을 계속 검증합니다.</p></section></main></body></html>"""
    (OUT / "about").mkdir()
    (OUT / "about" / "index.html").write_text(inject_global_navigation(about), encoding="utf-8")
    manifest = {"source_master": str(MASTER.relative_to(ROOT)).replace("\\", "/"), "entry_count": len(records), "public_columns": ["선수", "KLPGA K-RANKING", "NEO 경기력 ⓘ", "SG Total 순위", "우승확률"]}
    manifest["source_master_sha256"] = master_sha
    (OUT / "data").mkdir()
    (OUT / "data" / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for generated in OUT.rglob("*"):
        if generated.is_file() and generated.suffix.lower() in {".html", ".css", ".js", ".json"}:
            generated.write_text(generated.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    return OUT

if __name__ == "__main__":
    print(build())
