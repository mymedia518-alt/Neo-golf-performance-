"""COURSE IDENTITY, decisive step: a single hole's yardage matching
(West Hole 3 = 410YD White tee = KLPGA Tournament H12's own 410yd) could
in principle be a coincidence. This fetches ALL 9 West holes AND all 9
East holes' real title/par/yardage from the real course-map widget (the
same real DOM-event-dispatch + page navigation already proven to work
for West Hole 3) and prints the full real sequence, so it can be
compared against KLPGA's own real per-hole yardage/par already collected
in this project's RAW (holeInfo.yds / holeInfo.stdScore for Tournament
H1-18) -- a full 18-hole systematic match is decisive evidence, not a
single lucky coincidence.
"""
from __future__ import annotations
import json, re
from pathlib import Path


def extract_hole_facts(html: str):
    out = {}
    m = re.search(r'<div class="title">\s*(\w+ Hole \d+)\s*</div>', html)
    out["title"] = m.group(1).strip() if m else None
    m = re.search(r'<div class="number">\s*(\d+)\s*</div>\s*<div class="name">\s*Par\s*</div>', html)
    out["par"] = m.group(1) if m else None
    m = re.search(r'<div class="number">\s*(\d+)\s*</div>\s*<div class="name">\s*Hdcp\s*</div>', html)
    out["hdcp"] = m.group(1) if m else None
    m = re.search(r'<div class="number">\s*(\d+)\s*</div>\s*<div class="name">\s*Yard\s*</div>', html)
    out["blue_yard"] = m.group(1) if m else None
    m = re.search(r'<th>\s*White\s*</th>.*?<td>\s*(\d+)YD\s*</td>', html, re.S)
    white = re.search(r'<tbody>.*?<td>\s*\d+YD\s*</td>\s*<td>\s*(\d+)YD\s*</td>', html, re.S)
    out["white_yard"] = white.group(1) if white else None
    tip = re.search(r'<div class="tip">\s*(.{0,400}?)\s*</div>', html, re.S)
    out["tip_text"] = re.sub(r"\s+", " ", tip.group(1)).strip() if tip else None
    return out


def run(out_dir: Path):
    from playwright.sync_api import sync_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {"west": {}, "east": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("https://www.blueheron.co.kr/", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(1000)
        for side in ("west", "east"):
            for n in range(1, 10):
                hole_id = f"hole0{n}"
                try:
                    page.evaluate(
                        """(args) => {
                            const [side, holeId] = args;
                            const sel = document.querySelector('#course-map-title-' + side + '-hole');
                            if (sel) {
                                sel.value = holeId;
                                sel.dispatchEvent(new Event('change', {bubbles: true}));
                                sel.dispatchEvent(new Event('input', {bubbles: true}));
                            }
                        }""",
                        [side, hole_id],
                    )
                    page.wait_for_timeout(1800)
                    html = page.content()
                    facts = extract_hole_facts(html)
                    results[side][hole_id] = facts
                    (out_dir / f"{side}_{hole_id}.html").write_text(html, encoding="utf-8")
                except Exception as e:
                    results[side][hole_id] = {"error": str(e)}
                # go back to homepage for a clean state before next hole
                page.goto("https://www.blueheron.co.kr/", wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(500)
        browser.close()
    (out_dir / "full_18_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for side in results:
        for hole_id, facts in results[side].items():
            print(side, hole_id, facts)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="course_identity_full_18")
    a = ap.parse_args()
    run(Path(a.out_dir))
