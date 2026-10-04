"""COURSE IDENTITY, step 2 (retry): the first click attempt failed --
Playwright's .click() refuses because the course-map widget sits inside
a fullpage.js slide that is not currently the active/visible section
(element exists in the DOM, confirmed, but is not "visible" per
Playwright's actionability check). This retries by dispatching the
underlying DOM events directly (scrollIntoView + a real 'click'/'change'
event dispatch via page.evaluate), which does not require the element
to pass a visibility check, while still being a real interaction with
the real page's own JS (not a fabricated network call).
"""
from __future__ import annotations
import json
from pathlib import Path


def run(out_dir: Path):
    from playwright.sync_api import sync_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        requests_seen = []
        page.on("request", lambda req: requests_seen.append({"url": req.url, "resource_type": req.resource_type}))
        page.goto("https://www.blueheron.co.kr/", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(1000)
        before_count = len(requests_seen)

        eval_result = page.evaluate(
            """() => {
                const out = {};
                const li = document.querySelector('div.west li.hole03');
                out.li_found = !!li;
                if (li) {
                    li.scrollIntoView();
                    li.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                }
                const sel = document.querySelector('#course-map-title-west-hole');
                out.select_found = !!sel;
                if (sel) {
                    sel.value = 'hole03';
                    sel.dispatchEvent(new Event('change', {bubbles: true}));
                    sel.dispatchEvent(new Event('input', {bubbles: true}));
                }
                return out;
            }"""
        )
        result["eval_result"] = eval_result
        page.wait_for_timeout(2500)
        after_count = len(requests_seen)
        result["requests_before"] = before_count
        result["requests_after"] = after_count
        result["new_requests"] = requests_seen[before_count:after_count]

        html_after = page.content()
        (out_dir / "after_dispatch_west_hole03.html").write_text(html_after, encoding="utf-8")
        result["rendered_bytes_after"] = len(html_after)

        import re
        # Capture the live course-map-hole-img / course-map-content area if present
        m = re.search(r'course-map-hole-img.{0,2000}', html_after, re.S)
        result["course_map_hole_img_area"] = m.group(0) if m else None
        m2 = re.search(r'<div class="content">.{0,500}', html_after, re.S)

        for kw in ["Par 4", "PAR 4", "428", "410", "Pro Tip", "bunker", "Bunker", "forest", "야드", "파4", "벙커"]:
            idx = html_after.find(kw)
            result[f"found::{kw}"] = idx if idx >= 0 else None
            if idx >= 0:
                result[f"context::{kw}"] = html_after[max(0, idx-200):idx+200]

        browser.close()
    (out_dir / "west_hole3_v2_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "course_map_hole_img_area"}, ensure_ascii=False, indent=2)[:3000])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="course_identity_check_west_hole3_v2")
    a = ap.parse_args()
    run(Path(a.out_dir))
