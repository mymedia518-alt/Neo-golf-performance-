"""Build the candidate site with a small, official-schedule-driven HOME."""
from __future__ import annotations

import json, re, sys
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
from klpga.collectors.tournaments import fetch_game_list
from klpga.http_client import PoliteHttpClient
from klpga.website_v2 import build_beta001_candidate
from klpga.website_v2.shell import render_page

SCHEDULE_SOURCE = "https://klpga.co.kr/ajax/tourInfo/getGameList"

def _next_event():
    client = PoliteHttpClient(cache_dir=ROOT / "data/raw_cache/http")
    listings = [x for x in fetch_game_list(client, 2026) if x.is_regular_tour and x.is_stroke_play and x.start_date and x.start_date >= date.today()]
    if not listings:
        raise RuntimeError("official schedule has no upcoming stroke-play event")
    event = min(listings, key=lambda x: x.start_date)
    return {"game_code": event.game_code, "name": event.game_title, "start_date": event.start_date.isoformat(), "end_date": event.end_date.isoformat() if event.end_date else None, "venue": event.course_text or event.course_eng_text, "holes": (event.raw or {}).get("totalRound", 0) * 18 or None, "rounds": (event.raw or {}).get("totalRound"), "format": "스트로크 플레이" if event.is_stroke_play else event.game_method, "purse": event.prize_money, "source": SCHEDULE_SOURCE, "retrieved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")}

def _home(event):
    start = date.fromisoformat(event["start_date"])
    label = f"{start:%m.%d} START"
    dates = f"{event['start_date'][:4]}.{event['start_date'][5:7]}.{event['start_date'][8:]} — {event['end_date'][0:4]}.{event['end_date'][5:7]}.{event['end_date'][8:]}" if event.get("end_date") else event["start_date"]
    format_line = f"{event['holes']}홀 · {event['format']}" if event.get("holes") else event["format"]
    body = ("<section class=\"coming-soon\"><p class=\"coming-soon__eyebrow\">NEO GOLF DATA</p>"
            "<h1>골프를 결과가 아닌 데이터로 읽습니다.</h1>"
            "<div class=\"coming-soon__event\"><p class=\"coming-soon__label\">다음 대회</p>"
            f"<h2>{escape(event['name'])}</h2><p>{dates}</p><p>{escape(event['venue'] or '공식 코스 정보 확인 중')}<br>{escape(format_line)}</p>"
            "</div><p class=\"coming-soon__copy\">NEO GOLF DATA가 다음 대회부터 시작합니다.<br>"
            "대회 전부터 마지막 라운드까지 숫자가 어떻게 움직이는지 기록하고,<br>"
            "결과가 나온 뒤 예측과 실제 경기를 다시 분석합니다.</p>"
            f"<p class=\"coming-soon__start\">{label}</p></section>")
    return render_page(title="NEO GOLF DATA", active_section="home", body_html=body)

def main():
    content = ROOT / "content/website_v2"
    manifest = ROOT / "evidence/beta001/manifest.json"
    output = ROOT / "candidate/website-v2"
    build_beta001_candidate(content / "beta001.json", manifest, REPO_ROOT, output)
    event = _next_event()
    (output / "data").mkdir(parents=True, exist_ok=True)
    (output / "data/next_event.json").write_text(json.dumps(event, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    home_html = _home(event)
    # The temporary public surface is intentionally not a doorway into
    # unfinished analysis. Preserve historical routes on disk, but keep the
    # HOME header/footer navigation limited to the wordmark and context.
    home_html = re.sub(r'<nav class="global-nav"[^>]*>.*?</nav>', "", home_html, flags=re.S)
    home_html = re.sub(r'<nav aria-label="[^"]*">.*?</nav>', "", home_html, flags=re.S)
    (output / "index.html").write_text(home_html + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"home": str(output / "index.html"), "next_event": event}, ensure_ascii=False))

if __name__ == "__main__": main()
