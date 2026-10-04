"""COURSE IDENTITY, step 2: the headless-browser trace of
blueheron.co.kr's homepage confirmed a real course-map widget with a
West Course hole picker (li.hole01..hole09 under div.west, and a
matching <select id="course-map-title-west-hole">) -- the real site
genuinely organizes the course as West 9 + East 9 (18 holes total),
each hole 1-9. This drives that picker to "hole03" (West Hole 3) and
captures whatever appears: any newly-visible DOM content (par, yardage,
hazard description), any new network request (XHR/fetch/image) the
click triggers, and the resulting DOM around the course-map area --
real evidence, never asserted from search-engine paraphrase.
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

        clicked = False
        click_method = None
        try:
            page.click("div.west li.hole03", timeout=5000)
            clicked = True
            click_method = "click div.west li.hole03"
        except Exception as e1:
            try:
                page.select_option("#course-map-title-west-hole", "hole03")
                clicked = True
                click_method = "select_option #course-map-title-west-hole -> hole03"
            except Exception as e2:
                result["click_errors"] = [str(e1), str(e2)]

        page.wait_for_timeout(2500)
        after_count = len(requests_seen)
        new_requests = requests_seen[before_count:after_count]

        html_after = page.content()
        (out_dir / "after_click_west_hole03.html").write_text(html_after, encoding="utf-8")

        import re
        m = re.search(r'course-map[^"]*"[^>]*>.{0,3000}', html_after, re.S)
        course_map_area = m.group(0) if m else None

        result.update({
            "clicked": clicked, "click_method": click_method,
            "requests_before_click": before_count, "requests_after_click": after_count,
            "new_requests_triggered_by_click": new_requests,
            "course_map_area_snippet": course_map_area,
            "rendered_bytes_after_click": len(html_after),
        })

        # Also look for any element that became visible/changed carrying
        # real par/yardage/hazard text near the course-map area.
        for kw in ["Par 4", "PAR 4", "428", "410", "Pro Tip", "bunker", "forest", "야드", "파4", "벙커", "숲"]:
            idx = html_after.find(kw)
            result[f"found_after_click::{kw}"] = idx if idx >= 0 else None

        browser.close()
    (out_dir / "west_hole3_click_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "course_map_area_snippet"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="course_identity_check_west_hole3")
    a = ap.parse_args()
    run(Path(a.out_dir))
