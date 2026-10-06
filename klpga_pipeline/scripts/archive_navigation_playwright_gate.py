"""Playwright click-through QA for the archive navigation feature.

Serves docs/ over a local HTTP server (so root-relative hrefs resolve),
then actually clicks through: HOME -> 대회 기록 -> each tournament name ->
existing record page, and HOME -> 현재 대회 -> HJ scaffold. Also clicks a
couple of existing R1/R2/R3/FR links inside a real tournament to confirm
they still work. Runs at both 1440x900 and 390x844.
"""
import http.server
import socketserver
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2] / "docs"
PORT = 8799
socketserver.TCPServer.allow_reuse_address = True

results = []


def check(label, ok, extra=""):
    results.append((label, ok, extra))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" -- {extra}" if extra else ""))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def log_message(self, fmt, *args):
        pass


def run_server():
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        httpd.serve_forever()


server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
time.sleep(0.5)

BASE = f"http://127.0.0.1:{PORT}"


def run_viewport(w, h, label):
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = browser.new_page(viewport={"width": w, "height": h})

        # HOME -> 현재 대회
        page.goto(f"{BASE}/")
        check(f"[{label}] HOME loads, title mentions HJ", "HJ중공업" in page.title(), page.title())
        page.click('a:has-text("현재 대회")')
        page.wait_for_load_state("networkidle")
        check(f"[{label}] HOME -> 현재 대회 click -> HJ scaffold", "2026100004" in page.url, page.url)
        check(f"[{label}] HJ scaffold shows reader-language locked-state notice",
              "변형 스테이블포드 방식으로 진행됩니다" in page.content() and "준비되는 대로 공개합니다" in page.content())
        check(f"[{label}] HJ scaffold has NO internal-sounding '예측 잠금'/'모델 검증' labels",
              "예측 잠금" not in page.content() and "모델 검증" not in page.content())
        check(f"[{label}] HJ scaffold has NO probability markers",
              "우승확률" not in page.content() and "Win%" not in page.content())

        # HOME -> 대회 기록
        page.goto(f"{BASE}/")
        page.click('a:has-text("대회 기록")')
        page.wait_for_load_state("networkidle")
        check(f"[{label}] HOME -> 대회 기록 click -> archive index", page.url.rstrip("/").endswith("/tournaments"), page.url)

        # click each real tournament's NAME (not a separate button) -- all 5 are now real records
        for name, url_fragment in [
            ("제26회 하이트진로 챔피언십", "2026100005/fr"),
            ("하나금융그룹 챔피언십", "2026090002/final"),
            ("KB금융 골든라이프 챔피언십", "2026090003/final"),
            ("OK저축은행 읏맨 오픈", "ok-savings-bank-open/r3"),
            ("제15회 KG 레이디스 오픈", "kg-ladies-open/final"),
        ]:
            page.goto(f"{BASE}/tournaments/")
            link = page.locator(f'.archive-card h2 a:has-text("{name}")')
            check(f"[{label}] archive card name '{name}' is a real clickable link (not a separate 보기/상세 button)",
                  link.count() == 1)
            link.click()
            page.wait_for_load_state("networkidle")
            check(f"[{label}] clicking '{name}' -> real record page ({url_fragment})",
                  url_fragment in page.url, page.url)
            check(f"[{label}] '{name}' record page is NOT the placeholder stub",
                  "공사중" not in page.title())
            check(f"[{label}] '{name}' record page has no mojibake (replacement char)",
                  "�" not in page.content())
            # click every real stage link inside this tournament, confirm no 404 / no overflow
            page.goto(f"{BASE}/tournaments/")
            card = page.locator(f'.archive-card:has(h2:has-text("{name}"))')
            stage_hrefs = card.locator(".stage-links a").evaluate_all("els => els.map(e => e.getAttribute('href'))")
            for href in stage_hrefs:
                resp = page.goto(BASE + href)
                check(f"[{label}] {name} stage link {href} -> 200 (no 404)", resp.status == 200, resp.status)
                check(f"[{label}] {name} stage link {href} no mojibake", "�" not in page.content())

        # 하이트진로's deep-dive is self-flagged mock data -- must not be reachable from the archive
        page.goto(f"{BASE}/tournaments/")
        hitejinro_card = page.locator('.archive-card:has(h2:has-text("하이트진로"))')
        check(f"[{label}] mock-data deep-dive page is NOT linked from the 하이트진로 archive card",
              hitejinro_card.locator('a:has-text("딥 다이브")').count() == 0)

        # 하이트진로 public stages == PRE/R1/R2/R3/FR exactly -- 최종 검증/코스 분석 hidden
        check(f"[{label}] 최종 검증 NOT shown on 하이트진로 archive card",
              hitejinro_card.locator('a:has-text("최종 검증")').count() == 0)
        check(f"[{label}] 코스 분석 NOT shown on 하이트진로 archive card",
              hitejinro_card.locator('a:has-text("코스 분석")').count() == 0)
        hitejinro_stage_labels = hitejinro_card.locator(".stage-links a").all_inner_texts()
        check(f"[{label}] 하이트진로 public stages == [사전 분석, R1, R2, R3, FR] exactly",
              hitejinro_stage_labels == ["사전 분석", "R1", "R2", "R3", "FR"], hitejinro_stage_labels)
        for stage_label in ["사전 분석", "R1", "R2", "R3", "FR"]:
            link = hitejinro_card.locator(f'.stage-links a:has-text("{stage_label}")')
            check(f"[{label}] 하이트진로 {stage_label} stage link clickable", link.count() == 1)
            link.click()
            page.wait_for_load_state("networkidle")
            check(f"[{label}] 하이트진로 {stage_label} click landed on a real page (not 공사중)",
                  "공사중" not in page.title())
            page.go_back()
            page.wait_for_load_state("networkidle")

        # HJ current-tournament nav from archive page back to HOME works, no javascript:void / # hrefs anywhere
        all_hrefs = page.eval_on_selector_all("a", "els => els.map(e => e.getAttribute('href'))")
        bad = [h for h in all_hrefs if h in (None, "", "#") or (h and h.startswith("javascript:"))]
        check(f"[{label}] archive page has zero javascript:void/# placeholder links", len(bad) == 0, bad)

        # click into a real tournament's R1/R2/R3/FR stage links from the archive card directly
        page.goto(f"{BASE}/tournaments/")
        r1_link = page.locator('.archive-card:has(h2:has-text("KB금융")) .stage-links a:has-text("R1")')
        check(f"[{label}] KB archive card R1 stage link exists", r1_link.count() == 1)
        r1_link.click()
        page.wait_for_load_state("networkidle")
        check(f"[{label}] KB R1 stage link -> real R1 page", "2026090003/r1" in page.url, page.url)

        page.goto(f"{BASE}/tournaments/")
        fr_link_on_archive = page.locator('.archive-card:has(h2:has-text("KB금융")) .stage-links a:has-text("FR")')
        check(f"[{label}] KB archive card FR stage link exists", fr_link_on_archive.count() == 1)

        # viewport / overflow check on archive + HJ scaffold + HOME
        for url, pagelabel in [(f"{BASE}/tournaments/", "archive"), (f"{BASE}/tournaments/2026/2026100004/", "HJ"), (f"{BASE}/", "HOME")]:
            page.goto(url)
            sw = page.evaluate("document.documentElement.scrollWidth")
            cw = page.evaluate("document.documentElement.clientWidth")
            check(f"[{label}] {pagelabel} no horizontal overflow", sw <= cw + 1, f"scrollWidth={sw} clientWidth={cw}")

        browser.close()


run_viewport(1440, 900, "desktop_1440x900")
run_viewport(390, 844, "mobile_390x844")

print()
failures = [r for r in results if not r[1]]
print(f"TOTAL: {len(results)}  PASS: {len(results)-len(failures)}  FAIL: {len(failures)}")
if failures:
    for label, ok, extra in failures:
        print(" - FAIL:", label, extra)
    raise SystemExit(1)
