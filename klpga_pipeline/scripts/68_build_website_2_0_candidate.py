"""Build an isolated, data-driven Website 2.0 candidate."""
from __future__ import annotations
import json, re, sqlite3, sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
OUT = ROOT / "candidate" / "website-v2-0"

def stage_labels(total_rounds: int) -> list[str]:
    rounds = max(1, int(total_rounds))
    return ["\ub300\ud68c", *[f"R{i}" for i in range(1, rounds)], "FINAL"]

def stage_route(label: str) -> str:
    return {"\ub300\ud68c": "/index.html", "FINAL": "/final/index.html"}.get(label, f"/{label.lower()}/index.html")

def _clean_name(name: object, player_id: str) -> str:
    value = str(name or "").strip()
    return f"\uc120\uc218 {player_id}" if ("\ufffd" in value or "?" in value or not value) else value

def _decode_unicode_escapes(value: str) -> str:
    """Repair literal \\uXXXX sequences emitted by legacy candidate tooling."""
    needle = chr(92) + "u"
    return re.sub(re.escape(needle) + r"([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), value)

def _metric(window: dict, key: str) -> object:
    return ((window or {}).get("components") or {}).get(key, {}).get("mean")

def _fmt(value: object) -> str:
    return "\u2014" if value is None else f"{float(value):+.2f}"

def probability_graph(points: list[dict]) -> str:
    """Render only frozen checkpoint points; never interpolates missing data."""
    if not points:
        return '<div class="chart-empty" role="img" aria-label="\uc544\uc9c1 \uacf5\uac1c\ub41c \uc6b0\uc2b9 \ud655\ub960 \uccb4\ud06c\ud3ec\uc778\ud2b8 \uc5c6\uc74c">\uc608\uce21 \uccb4\ud06c\ud3ec\uc778\ud2b8 \uc5c6\uc74c</div>'
    valid = [p for p in points if p.get("probability") is not None]
    if not valid:
        return '<div class="chart-empty">\uc608\uce21 \uccb4\ud06c\ud3ec\uc778\ud2b8 \uc5c6\uc74c</div>'
    labels = [escape(str(p.get("checkpoint"))) for p in valid]
    vals = [float(p["probability"]) for p in valid]
    width, height, pad = 560, 250, 42
    ymax = max(10, ((max(vals) + 4) // 5) * 5)
    coords = []
    for i, val in enumerate(vals):
        x = pad + (width - 2 * pad) * (i / max(1, len(vals) - 1))
        y = height - pad - (height - 2 * pad) * val / ymax
        coords.append((x, y, val))
    path = " ".join(("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y, _) in enumerate(coords))
    ticks = "".join(f'<text x="{pad-8}" y="{height-pad-(height-2*pad)*t/ymax+4:.1f}" text-anchor="end">{t:g}%</text>' for t in range(0, int(ymax)+1, max(5, int(ymax/5))))
    points_svg = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5"/><text class="point-label" x="{x:.1f}" y="{y-10:.1f}" text-anchor="middle">{v:.2f}%</text>' for x, y, v in coords)
    xlabels = "".join(f'<text x="{x:.1f}" y="{height-12:.1f}" text-anchor="middle">{labels[i]}</text>' for i, (x, _, _) in enumerate(coords))
    return f'<svg class="probability-chart" viewBox="0 0 {width} {height}" role="img" aria-label="\uc6b0\uc2b9 \uac00\ub2a5\uc131 \ubcc0\ud654"><g class="axis">{ticks}<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height-pad}"/><line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}"/></g><path class="line" d="{path}"/>{points_svg}{xlabels}</svg>'

def load_inputs():
    schedule = {"game_code":"2026120001","name":"\uc624\uc800\ucd95\uc740\ud589 \uc74f\ub9e8 \uc624\ud508","start_date":"2026-09-04","end_date":"2026-09-06","venue":"\ud3ec\ucc9c\uc544\ub3c4\ub2c8\uc2a4","holes":54,"rounds":3,"format":"\uc2a4\ud2b8\ub85c\ud06c \ud50c\ub808\uc774","purse":1000000000,"source":"https://klpga.co.kr/ajax/tourInfo/getGameList","retrieved_at":datetime.now(timezone.utc).isoformat()}
    schedule["name"] = "OK" + "\\uc800\\ucd95\\uc740\\ud589 \\uc74f\\ub9e8 \\uc624\\ud508"
    schedule["retrieved_at"] = "2026-08-30T23:39:09Z"
    entries = json.loads((CONTENT / "OK_OPEN_2026_ENTRY_SNAPSHOT.json").read_text(encoding="utf-8"))["entries"]
    db_path = Path(r"C:/Users/user/Desktop/Neo-golf-performance-/klpga_pipeline/data/klpga.sqlite")
    sponsor_by, probability_by = {}, {}
    if db_path.exists():
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            sponsor_by = {str(pid): (sponsor or "—") for pid, sponsor in conn.execute("SELECT player_id, team_or_sponsor FROM player_master")}
        try:
            sys.path.insert(0, str(Path(r"C:/Users/user/Desktop/Neo-golf-performance-/klpga_pipeline/src")))
            from klpga.models.inference import run_inference
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as source_conn:
                with sqlite3.connect(":memory:") as conn:
                    source_conn.backup(conn)
                    conn.executemany("INSERT OR REPLACE INTO tournament_entry (game_code, player_code, player_name_display, nationality, qualification_category, qualification_reason, source, collected_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [("2026120001", str(e.get("player_id")), str(e.get("player_name") or ""), e.get("nationality"), e.get("qualification_category"), e.get("qualification_reason"), "frozen_entry_snapshot", "2026-08-30T00:00:00Z") for e in entries])
                    inferred = run_inference(conn, "2026120001", cutoff_date_arg="2026-09-04", tournament_name_arg=schedule["name"])
            probability_by = {str(p.player_code): p.win_probability for p in inferred.predictions}
        except (ImportError, RuntimeError, ValueError):
            probability_by = {}
    for entry in entries:
        pid = str(entry.get("player_id")); entry["sponsor"] = sponsor_by.get(pid, "—"); entry["win_probability"] = probability_by.get(pid)
    entries = sorted(entries, key=lambda e: (-(e.get("win_probability") if e.get("win_probability") is not None else -1), str(e.get("player_id"))))
    for rank, entry in enumerate(entries, 1): entry["neo_rank"] = rank
    profiles = {str(p["player_id"]): p for p in json.loads((CONTENT / "OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json").read_text(encoding="utf-8"))["profiles"]}
    return schedule, entries, profiles

def render_dashboard(schedule: dict, entries: list[dict], profiles: dict, current_stage: str = "\ub300\ud68c", checkpoints: list[dict] | None = None) -> str:
    stages = stage_labels(schedule["rounds"]); checkpoints = checkpoints or []
    stage_html = "".join(f'<a href="{escape(stage_route(s))}" class="stage-tab{" active" if s == current_stage else ""}"{" aria-current=\"page\"" if s == current_stage else ""} data-stage="{escape(s)}">{escape(s)}</a>' for s in stages)
    rows, cards = [], []
    for entry in entries:
        pid = str(entry.get("player_id")); name = _clean_name(entry.get("canonical_name") or entry.get("player_name"), pid)
        sponsor = escape(str(entry.get("sponsor") or "—")); win = entry.get("win_probability"); win_text = "—" if win is None else f"{float(win)*100:.2f}%"
        rows.append(f'<tr data-player-id="{escape(pid)}"><td>—</td><td>{entry.get("neo_rank", "—")}</td><th scope="row"><button class="player-select" data-player-id="{escape(pid)}">{escape(name)}</button><small class="sponsor">{sponsor}</small><small class="pre-win">우승 {win_text}</small></th><td>—</td><td>—</td><td>—</td>' + ''.join('<td class="pending">\u2014</td>' for _ in range(6)) + f'<td>—</td><td>—</td><td>—</td><td>—</td><td>{win_text}</td></tr>')
        if len(cards) < 3:
            w = profiles.get(pid, {}).get("windows", {}).get("recent5", {}); metrics = [("PUTT","putting"),("ARG","around_green"),("APP","approach"),("OTT","off_the_tee"),("T2G","tee_to_green"),("TOTAL","total")]
            cells = "".join(f'<div><span>{label}</span><strong>{_fmt(_metric(w,key))}</strong></div>' for label,key in metrics)
            cards.append(f'<article class="performance-card" data-player-id="{escape(pid)}"><h3>{escape(name)}</h3><p>\ucd5c\uadfc 5\uacbd\uae30 \u00b7 SG \ud3c9\uade0</p><div class="metric-grid">{cells}</div><small>\ud45c\ubcf8 {w.get("event_count",0)}\uac1c \ub300\ud68c</small></article>')
    if not rows:
        rows.append('<tr><td colspan="11" class="empty-state">현재 표시할 선수가 없습니다.</td></tr>')
        cards.append('<div class="empty-state" role="status">선수 경기력 데이터가 준비되면 이곳에 표시됩니다.</div>')
    config = json.dumps({"game_code":schedule["game_code"],"rounds":schedule["rounds"],"stages":stages,"probability_checkpoints":checkpoints}, ensure_ascii=False)
    prefix = "" if current_stage == "\ub300\ud68c" else "../"
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>NEO GOLF DATA · {escape(schedule["name"])}</title><link rel="stylesheet" href="{prefix}assets/dashboard.css"></head><body data-config='{escape(config)}'><header class="site-header"><a class="brand" href="/">NEO GOLF DATA</a><nav aria-label="\uc8fc\uc694 \uba54\ub274"><a href="/">\ud648</a><a href="#schedule">\ub300\ud68c \uc77c\uc815</a><a href="#tournament">\ub300\ud68c</a><a href="#forecast">\uc608\uce21 \uae30\ub85d</a><a href="#deep-dive">DEEP DIVE</a><a href="#about">NEO \uc18c\uac1c</a></nav></header><main><section class="tournament-head" id="tournament"><div><p class="eyebrow">\ub300\ud68c</p><h1>{escape(schedule["name"])}</h1><p class="meta">{schedule["start_date"]} — {schedule["end_date"]} · {escape(schedule["venue"])} · {schedule["holes"]}\ud640 · {escape(schedule["format"])}</p></div><strong class="status">\uc608\uc815</strong></section><nav class="stage-tabs" aria-label="\ub300\ud68c \ub77c\uc6b4\ub4dc">{stage_html}</nav><section class="dashboard-grid"><div class="table-panel"><div class="panel-heading"><div><p class="eyebrow">\ucc38\uac00\uc790 {len(entries)}\uba85</p><h2>\uc120\uc218\ubcc4 \ub370\uc774\ud130</h2></div><div class="view-switch" role="group" aria-label="\ud45c\uc2dc \ubc29\uc2dd"><button class="mode active" data-mode="ranks" aria-pressed="true">RANKS</button><button class="mode" data-mode="values" aria-pressed="false">VALUES</button></div></div><p class="availability">\ub300\ud68c \uc804 \uc0c1\ud0dc · \ud604\uc7ac \ub77c\uc6b4\ub4dc \uacb0\uacfc\uc640 \ub300\ud68c SG\ub294 \uacf5\uc2dd \uc9d1\uacc4 \ud6c4 \ud45c\uc2dc\ub429\ub2c8\ub2e4.</p><div class="table-wrap"><table class="data-table"><thead><tr><th>\uc21c\uc704</th><th>\uc120\uc218</th><th>SCORE</th><th>THRU</th><th>\ud604\uc7ac \ub77c\uc6b4\ub4dc</th><th>SG PUTT</th><th>SG ARG</th><th>SG APP</th><th>SG OTT</th><th>SG T2G</th><th>SG TOTAL</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></div><aside class="evolution" id="forecast"><p class="eyebrow">\ud504\ub9ac\uc988\ub85c \ud655\uc815\ub41c \uccb4\ud06c\ud3ec\uc778\ud2b8</p><h2>\uc6b0\uc2b9 \uac00\ub2a5\uc131 \ubcc0\ud654</h2><p class="muted">\uacf5\uc2dd NEO \uc608\uce21 \uccb4\ud06c\ud3ec\uc778\ud2b8\ub9cc \ud45c\uc2dc\ud569\ub2c8\ub2e4.</p>{probability_graph(checkpoints)}</aside></section><section class="performance" id="deep-dive"><div class="panel-heading"><div><p class="eyebrow">\uacfc\uac70 \uc131\ub2a5 \ucc38\uace0</p><h2>\uc120\ud0dd\ud55c \uc120\uc218\uc758 SG \ud750\ub984</h2></div><div class="range-tabs"><button class="range active">\uc774\ubc88 \ub300\ud68c</button><button class="range">\ucd5c\uadfc 5\uacbd\uae30</button><button class="range">\ucd5c\uadfc 10\uacbd\uae30</button><button class="range">\uc2dc\uc98c</button></div></div><p class="availability">\uc774\ubc88 \ub300\ud68c SG\uc640 \uad6c\ubd84\ud55c \uacfc\uac70 \uac80\uc99d SG \ud3c9\uade0\uc785\ub2c8\ub2e4.</p><div class="cards">{''.join(cards)}</div></section></main><script src="{prefix}assets/dashboard.js" defer></script></body></html>'''

def build():
    schedule, entries, profiles = load_inputs(); (OUT / "assets").mkdir(parents=True, exist_ok=True)
    schedule = {k: _decode_unicode_escapes(str(v)) if isinstance(v, str) else v for k, v in schedule.items()}
    for stage in stage_labels(schedule["rounds"]):
        target = OUT if stage == "\ub300\ud68c" else OUT / stage.lower(); target.mkdir(parents=True, exist_ok=True)
        html = _decode_unicode_escapes(render_dashboard(schedule, entries, profiles, stage))
        html = html.replace('<th>순위</th><th>선수</th>', '<th>예상순위</th><th>KLPGA 랭킹</th><th>NEO 랭킹</th><th>선수</th>')
        html = html.replace('<th>SG TOTAL</th></tr>', '<th>SG TOTAL</th><th>SG Total 순위</th><th>TOP 20</th><th>TOP 10</th><th>TOP 5</th><th>우승</th></tr>')
        if stage == "\ub300\ud68c":
            """
            items = "".join(f'<li><span>{escape(_clean_name(e.get("canonical_name") or e.get("player_name"), str(e.get("player_id"))))}</span><strong>{(f"{float(e[\"win_probability\"])*100:.2f}%" if e.get("win_probability") is not None else "—")}</strong></li>' for e in entries[:10])
            html = html.replace('</aside>', '<section class="pre-probabilities"><h3>PRE 우승 가능성</h3><ol>' + items + '</ol><p>현재 정보에서 가능한 결과의 분포입니다.</p></section></aside>')
            """
        (target / "index.html").write_text(html, encoding="utf-8")
    (OUT / "data").mkdir(exist_ok=True); (OUT / "data/tournament.json").write_text(json.dumps(schedule, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return OUT

if __name__ == "__main__": print(build())
