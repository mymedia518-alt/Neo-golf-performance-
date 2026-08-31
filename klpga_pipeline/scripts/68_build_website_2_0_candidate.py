"""Build the isolated NEO Website 2.0 data-dashboard candidate."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
OUT = ROOT / "candidate" / "website-v2-0"


def stage_labels(total_rounds: int) -> list[str]:
    rounds = max(1, int(total_rounds))
    return ["대회", *[f"R{i}" for i in range(1, rounds)], "FINAL"]


def _clean_name(name: object, player_id: str) -> str:
    value = str(name or "").strip()
    # Existing snapshot/source contains replacement characters. Never expose
    # mojibake; canonical player_id remains the identity key.
    if "�" in value or "?" in value or not value:
        return f"선수 {player_id}"
    return value


def _metric(window: dict, key: str) -> object:
    return (window.get("components") or {}).get(key, {}).get("mean")


def _fmt(value: object) -> str:
    return "—" if value is None else f"{float(value):+.2f}"


def load_inputs() -> tuple[dict, list[dict], dict]:
    # next_event is a prior candidate artifact; authoritative schedule values
    # are normalized here and provenance remains the official endpoint.
    schedule = {
        "game_code": "2026120001",
        "name": "OK저축은행 읏맨 오픈",
        "start_date": "2026-09-04",
        "end_date": "2026-09-06",
        "venue": "포천아도니스",
        "holes": 54,
        "rounds": 3,
        "format": "스트로크 플레이",
        "purse": 1000000000,
        "source": "https://klpga.co.kr/ajax/tourInfo/getGameList",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }
    entries_doc = json.loads((CONTENT / "OK_OPEN_2026_ENTRY_SNAPSHOT.json").read_text(encoding="utf-8"))
    perf_doc = json.loads((CONTENT / "OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json").read_text(encoding="utf-8"))
    entries = entries_doc["entries"]
    profiles = {str(p["player_id"]): p for p in perf_doc["profiles"]}
    return schedule, entries, profiles


def render_dashboard(schedule: dict, entries: list[dict], profiles: dict) -> str:
    stages = stage_labels(schedule["rounds"])
    stage_html = "".join(f'<a href="#" class="stage-tab{' active' if i == 0 else ''}" aria-current="page" data-stage="{escape(s)}">{escape(s)}</a>' for i, s in enumerate(stages))
    rows = []
    cards = []
    for idx, entry in enumerate(entries):
        pid = str(entry.get("player_id"))
        name = _clean_name(entry.get("canonical_name") or entry.get("player_name"), pid)
        rows.append(f'<tr data-player-id="{escape(pid)}"><td>—</td><th scope="row"><button class="player-select" data-player-id="{escape(pid)}">{escape(name)}</button><small>{escape(pid)}</small></th><td>—</td><td>—</td><td>—</td><td class="pending">—</td><td class="pending">—</td><td class="pending">—</td><td class="pending">—</td><td class="pending">—</td><td class="pending">—</td></tr>')
        if len(cards) < 3:
            p = profiles.get(pid, {})
            w = p.get("windows", {}).get("recent5", {})
            metrics = [("PUTT", "putting"), ("ARG", "around_green"), ("APP", "approach"), ("OTT", "off_the_tee"), ("T2G", "tee_to_green"), ("TOTAL", "total")]
            cells = "".join(f'<div><span>{label}</span><strong>{_fmt(_metric(w, key))}</strong></div>' for label, key in metrics)
            cards.append(f'<article class="performance-card" data-player-id="{escape(pid)}"><h3>{escape(name)}</h3><p>최근 5경기 · SG 평균</p><div class="metric-grid">{cells}</div><small>표본 {w.get("event_count", 0)}개 대회</small></article>')
    config = json.dumps({"game_code": schedule["game_code"], "rounds": schedule["rounds"], "stages": stages, "probability_checkpoints": []}, ensure_ascii=False)
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>NEO GOLF DATA · {escape(schedule['name'])}</title><link rel="stylesheet" href="assets/dashboard.css"></head><body data-config='{escape(config)}'>
<header class="site-header"><a class="brand" href="/">NEO GOLF DATA</a><nav aria-label="주요 메뉴"><a href="/">홈</a><a href="#schedule">대회 일정</a><a href="#tournament">대회</a><a href="#forecast">예측 기록</a><a href="#deep-dive">DEEP DIVE</a><a href="#about">NEO 소개</a></nav></header>
<main><section class="tournament-head" id="tournament"><div><p class="eyebrow">대회</p><h1>{escape(schedule['name'])}</h1><p class="meta">{escape(schedule['start_date'])} — {escape(schedule['end_date'])} · {escape(schedule['venue'])} · {schedule['holes']}홀 · {escape(schedule['format'])}</p></div><strong class="status">예정</strong></section>
<nav class="stage-tabs" aria-label="대회 라운드">{stage_html}</nav>
<section class="dashboard-grid"><div class="table-panel"><div class="panel-heading"><div><p class="eyebrow">참가자 {len(entries)}명</p><h2>선수별 데이터</h2></div><div class="view-switch" role="group" aria-label="표시 방식"><button class="mode active" data-mode="ranks" aria-pressed="true">RANKS</button><button class="mode" data-mode="values" aria-pressed="false">VALUES</button></div></div><p class="availability">대회 전 상태 · 현재 라운드 결과와 대회 SG는 공식 집계 후 표시됩니다.</p><div class="table-wrap"><table class="data-table"><thead><tr><th>순위</th><th>선수</th><th>SCORE</th><th>THRU</th><th>현재 라운드</th><th>SG PUTT</th><th>SG ARG</th><th>SG APP</th><th>SG OTT</th><th>SG T2G</th><th>SG TOTAL</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></div>
<aside class="evolution" id="forecast"><p class="eyebrow">체크포인트 기반</p><h2>우승 가능성 변화</h2><p class="muted">공식 NEO 예측 체크포인트가 공개되면 PRE·R1·R2·FINAL 순서로 표시됩니다.</p><div class="chart-empty" role="img" aria-label="아직 공개된 우승 확률 체크포인트 없음">예측 체크포인트 없음</div><a class="text-link" href="#deep-dive">데이터 기준 보기 →</a></aside></section>
<section class="performance" id="deep-dive"><div class="panel-heading"><div><p class="eyebrow">과거 성능 참고</p><h2>선택한 선수의 SG 흐름</h2></div><div class="range-tabs"><button class="range active">이번 대회</button><button class="range">최근 5경기</button><button class="range">최근 10경기</button><button class="range">시즌</button></div></div><p class="availability">이번 대회 SG와 혼동하지 않도록, 아래 수치는 대회 전 검증된 과거 SG 평균입니다.</p><div class="cards">{''.join(cards)}</div></section></main><script src="assets/dashboard.js" defer></script></body></html>'''


def build() -> Path:
    schedule, entries, profiles = load_inputs()
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    (OUT / "data").mkdir(exist_ok=True)
    (OUT / "index.html").write_text(render_dashboard(schedule, entries, profiles), encoding="utf-8")
    (OUT / "data/tournament.json").write_text(json.dumps(schedule, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return OUT


if __name__ == "__main__":
    print(build())
