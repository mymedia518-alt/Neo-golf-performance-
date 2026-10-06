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
        check(f"[{label}] HJ scaffold shows 예측 잠금 notice", "예측 잠금" in page.content())
        check(f"[{label}] HJ scaffold has NO probability markers",
              "우승확률" not in page.content() and "Win%" not in page.content())

        # HOME -> 대회 기록
        page.goto(f"{BASE}/")
        page.click('a:has-text("대회 기록")')
        page.wait_for_load_state("networkidle")
        check(f"[{label}] HOME -> 대회 기록 click -> archive index", page.url.rstrip("/").endswith("/tournaments"), page.url)

        # click each real tournament's NAME (not a separate button)
        for name, url_fragment in [
            ("제26회 하이트진로 챔피언십", "2026100005/fr"),
            ("하나금융그룹 챔피언십", "2026090002/final"),
            ("KB금융 골든라이프 챔피언십", "2026090003/final"),
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

        # OK / KG are placeholder-only -- name must NOT be a dead/fake link
        page.goto(f"{BASE}/tournaments/")
        for name in ["OK저축은행 읏맨 오픈", "제15회 KG 레이디스 오픈"]:
            card = page.locator(f'.archive-card:has(h2:has-text("{name}"))')
            link_in_name = card.locator("h2 a")
            check(f"[{label}] placeholder tournament '{name}' name is NOT a dead/fake link",
                  link_in_name.count() == 0)
            check(f"[{label}] placeholder tournament '{name}' shows honest status text",
                  "실제 기록 준비 중" in card.inner_text())

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
