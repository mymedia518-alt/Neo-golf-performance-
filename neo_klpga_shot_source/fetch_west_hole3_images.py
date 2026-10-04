"""Fetch the real official Blue Heron West Hole 3 images, found by the
headless-browser DOM-event-dispatch probe (verify_course_identity_west_hole3_v2.py)
when it navigated the real course-map widget to West Hole 3:
  https://blueheron.co.kr/static/pc/origin/assets/images/page/course-information-hole-information-visual-west-hole03.png
  https://blueheron.co.kr/static/pc/origin/assets/images/page/course-information-hole-information-tip-west-hole03.png
Real URLs captured from real network traffic, not guessed.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from urllib.request import Request, urlopen

URLS = {
    "west_hole03_visual.png": "https://blueheron.co.kr/static/pc/origin/assets/images/page/course-information-hole-information-visual-west-hole03.png",
    "west_hole03_tip.png": "https://blueheron.co.kr/static/pc/origin/assets/images/page/course-information-hole-information-tip-west-hole03.png",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="west_hole3_images")
    a = ap.parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, url in URLS.items():
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 NEO-Golf-Data/1.0"})
        with urlopen(req, timeout=20) as r:
            data = r.read()
        (out / name).write_bytes(data)
        print(name, len(data), "bytes")


if __name__ == "__main__":
    main()
