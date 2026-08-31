"""Build the OK Open PRE candidate from the canonical public master only."""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "content" / "website_v2" / "OK_OPEN_2026_PRE_PUBLIC_MASTER.json"
OUT = ROOT / "candidate" / "website-v2-ok-open-pre"

BANDS = {
    "VERY_HIGH": "최상위 구간",
    "HIGH": "상위 구간",
    "TYPICAL": "중위 구간",
    "LOW": "하위 구간",
    "VERY_LOW": "최하위 구간",
    "INSUFFICIENT_EVIDENCE": "평가 보류",
}

CSS = """
:root{--ink:#17202a;--muted:#65717d;--line:#dfe5ea;--accent:#0c6b68;--soft:#f4f7f7}
*{box-sizing:border-box}body{margin:0;color:var(--ink);font-family:Pretendard,"Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",system-ui,sans-serif;background:#fff;line-height:1.45}header,main{max-width:1240px;margin:auto;padding:22px 28px}header{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line)}.brand{font-weight:800;letter-spacing:.04em;color:var(--ink);text-decoration:none}nav a{margin-left:18px;color:var(--muted);text-decoration:none;font-size:14px}h1{font-size:clamp(28px,4vw,44px);margin:12px 0 8px;letter-spacing:-.04em}h2{font-size:20px;margin:0 0 14px}.eyebrow{font-size:12px;font-weight:700;letter-spacing:.12em;color:var(--accent);text-transform:uppercase}.meta,.note{color:var(--muted);font-size:14px}.hero{padding:42px 0 28px;display:flex;justify-content:space-between;gap:30px;align-items:end}.status{font-size:14px;color:var(--accent);border:1px solid #acd0cc;border-radius:999px;padding:7px 13px}.grid{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(280px,.8fr);gap:22px}.panel{border:1px solid var(--line);border-radius:14px;background:#fff;padding:20px}.table-wrap{overflow-x:auto}.data{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}.data th,.data td{padding:11px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;font-size:14px}.data th:first-child,.data td:first-child{text-align:left}.data tbody tr:hover{background:var(--soft)}.player{display:block;font-weight:700;text-align:left}.sponsor{display:block;color:var(--muted);font-size:12px;font-weight:400;text-align:left;margin-top:2px}.band{display:inline-block;padding:3px 7px;border-radius:999px;background:#edf4f3;color:#245c58;font-size:12px}.win{font-weight:800;color:var(--accent)}.evolution{min-height:240px}.checkpoint{border-left:3px solid var(--accent);padding:12px 14px;background:var(--soft);margin-top:18px}.metric{font-size:32px;font-weight:800;font-variant-numeric:tabular-nums}.help{margin-top:22px;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}.sr-only{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}@media(max-width:760px){header,main{padding:18px 16px}header nav{display:none}.hero{padding-top:28px;display:block}.status{display:inline-block;margin-top:14px}.grid{grid-template-columns:1fr}.panel{padding:14px}.data{min-width:700px}.table-wrap:after{content:"↔ 표를 옆으로 밀어 더 많은 열 보기";display:block;color:var(--muted);font-size:12px;padding-top:8px}.data th,.data td{padding:10px 8px}}
"""

def pct(value):
    return "—" if value is None else f"{float(value)*100:.2f}%"
def value(value):
    return "—" if value is None else html.escape(str(value))

def build() -> Path:
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    records = list(master["records"])
    if len(records) != 120:
        raise ValueError(f"canonical master must contain 120 records, got {len(records)}")
    # Neutral, reproducible display order: official K-RANKING, then canonical ID.
    records.sort(key=lambda r: (r.get("official_klpga_rank") is None, r.get("official_klpga_rank") or 10**9, str(r["player_id"])))
    rows = []
    for r in records:
        name = value(r.get("current_official_player_name"))
        sponsor = value(r.get("current_official_sponsor"))
        band = BANDS.get(r.get("neo_performance_band"), "평가 보류")
        rows.append(f"<tr><th scope='row'><span class='player'>{name}</span><span class='sponsor'>{sponsor}</span></th><td>{value(r.get('official_klpga_rank'))}</td><td><span class='band' title='최근 경기력 증거를 통계적으로 구분한 구간'>{html.escape(band)}</span></td><td>{value(r.get('sg_total_rank'))}</td><td class='win'>{pct(r.get('win_probability'))}</td></tr>")
    html_doc = f"""<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>NEO GOLF DATA · OK저축은행 읏맨 오픈</title><link rel=\"stylesheet\" href=\"assets/neo.css\"></head><body><header><a class=\"brand\" href=\"./\">NEO GOLF DATA</a><nav><a href=\"#tournament\">대회</a><a href=\"#pre\">예측 기록</a><a href=\"#about\">NEO 소개</a></nav></header><main><section class=\"hero\" id=\"tournament\"><div><p class=\"eyebrow\">다음 대회 · PRE</p><h1>OK저축은행 읏맨 오픈</h1><p class=\"meta\">2026.09.04 — 09.06 · 포천아도니스 · 54홀 스트로크 플레이</p></div><strong class=\"status\">예측 확정 전</strong></section><div class=\"grid\"><section class=\"panel\" id=\"pre\"><h2>PRE 참가 선수 <small>{len(records)}명</small></h2><p class=\"note\">K-RANKING은 누적 성과, NEO는 최근 경기력을 봅니다.</p><div class=\"table-wrap\"><table class=\"data\"><thead><tr><th>선수</th><th>KLPGA K-RANKING</th><th>NEO 경기력 구간</th><th>SG Total 순위</th><th>우승확률</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><div class=\"help\">K-RANKING이 ‘쌓아온 성과’를 보여준다면, NEO는 ‘지금의 경기력’을 봅니다. 두 지표는 서로 다른 시간축과 평가 기준을 사용합니다.</div></section><aside class=\"panel evolution\"><p class=\"eyebrow\">PRE · 우승 가능성 변화</p><h2>우승 가능성 변화</h2><p class=\"note\">검증된 PRE 체크포인트만 표시합니다. R1·R2·FINAL 결과가 생기기 전에는 관측값을 만들지 않습니다.</p><div class=\"checkpoint\"><div class=\"metric\">PRE</div><p class=\"note\">참가 선수별 우승확률은 표에서 확인할 수 있습니다.</p></div></aside></div></main></body></html>"""
    if OUT.exists(): shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    (OUT / "assets" / "neo.css").write_text(CSS, encoding="utf-8")
    (OUT / "index.html").write_text(html_doc, encoding="utf-8")
    (OUT / "pre").mkdir()
    (OUT / "pre" / "index.html").write_text(html_doc.replace('href="assets/neo.css"','href="../assets/neo.css"'), encoding="utf-8")
    manifest = {"source_master": str(MASTER.relative_to(ROOT)).replace("\\", "/"), "entry_count": len(records), "public_columns": ["선수", "KLPGA K-RANKING", "NEO 경기력 구간", "SG Total 순위", "우승확률"]}
    (OUT / "data").mkdir()
    (OUT / "data" / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return OUT

if __name__ == "__main__":
    print(build())
