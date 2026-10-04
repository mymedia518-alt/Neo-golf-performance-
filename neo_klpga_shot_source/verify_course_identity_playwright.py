"""Independent COURSE IDENTITY verification (headless-browser pass).

The plain-urllib fetch (verify_course_identity.py) reached blueheron.co.kr
for real (HTTP 200) but only got a client-rendered JS shell -- no
hole-by-hole content in the static HTML. This script drives a real
headless browser so the site's own JS actually runs, and records every
network request it makes while loading the course-guide page: XHR/fetch
calls, JS bundle URLs, any course/hole API, image asset URLs,
background-image CSS, and canvas/SVG sources. Goal is to find the real
West Hole 3 geometry/image the official site serves, to compare against
klpga.co.kr's hole_12.png -- never asserts a match without this.

Never fabricates network traffic: if the page truly makes no further
requests (fully static after JS init, or geo/anti-bot blocked), that is
reported as a real negative result, not papered over.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

CANDIDATE_PATHS = [
    "/", "/course", "/course/guide", "/course/west", "/course/course",
    "/kor/course/course.asp", "/sub/course/course.asp",
    "/golf/course", "/intro/course.php", "/sub/course_guide.php",
]


def run(out_dir: Path):
    from playwright.sync_api import sync_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for path in CANDIDATE_PATHS:
            url = f"https://www.blueheron.co.kr{path}"
            page = browser.new_page()
            requests_seen = []

            def on_request(req):
                requests_seen.append({"url": req.url, "method": req.method, "resource_type": req.resource_type})

            page.on("request", on_request)
            record = {"url": url}
            try:
                resp = page.goto(url, wait_until="networkidle", timeout=20000)
                record["status"] = resp.status if resp else None
                page.wait_for_timeout(1500)
                html = page.content()
                safe = url.replace("https://", "").replace("/", "_") or "root"
                (out_dir / f"{safe}.rendered.html").write_text(html, encoding="utf-8")
                record["rendered_bytes"] = len(html)

                # Look for hole/course-identifying text after JS render.
                hits = re.findall(r"(west|서코스|서\s*코스|3번\s*홀|파\s*4|par\s*4|410|428|hole\s*3)", html, re.I)
                record["keyword_hits_in_rendered_dom"] = hits[:30]

                # Pull out anything that looks like an image/background-image asset.
                imgs = re.findall(r'(?:src|background-image)\s*[:=]\s*["\']?(https?://[^"\')\s]+\.(?:png|jpg|jpeg|svg|webp))', html, re.I)
                record["image_assets_in_rendered_dom"] = sorted(set(imgs))[:30]

                # Network requests this page actually made (XHR/fetch/script/image).
                xhr = [r for r in requests_seen if r["resource_type"] in ("xhr", "fetch")]
                scripts = [r for r in requests_seen if r["resource_type"] == "script"]
                images = [r for r in requests_seen if r["resource_type"] == "image"]
                record["xhr_fetch_requests"] = xhr
                record["script_requests"] = [s["url"] for s in scripts]
                record["image_requests"] = [i["url"] for i in images]
                record["total_requests_observed"] = len(requests_seen)
            except Exception as e:
                record["error"] = str(e)
            finally:
                page.close()
            results.append(record)
        browser.close()
    (out_dir / "playwright_course_identity_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in results:
        print(json.dumps({k: v for k, v in r.items() if k not in ("xhr_fetch_requests",)}, ensure_ascii=False)[:500])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="course_identity_check_playwright")
    a = ap.parse_args()
    run(Path(a.out_dir))
