"""Independent course-identity verification: confirm whether
klpga.co.kr's hole_12.png for gameCode=2026100005 actually corresponds
to Blue Heron Golf Club's real West Hole 3 -- a claim NOT established
by coordinate registration (that only proves the image and Shot
Tracker coordinates share a frame, not what the image depicts).

Fetches the official Blue Heron CC site's course-guide pages for real
West Hole 3 data (par, yardage, hazard description, hole image if
available) to compare against. Never asserts a match without this
independent evidence.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

CANDIDATE_URLS = [
    "https://www.blueheron.co.kr/",
    "https://www.blueheron.co.kr/course",
    "https://www.blueheron.co.kr/course/guide",
    "https://www.blueheron.co.kr/golf/course",
    "https://www.blueheron.co.kr/sub/course.php",
    "https://www.blueheron.co.kr/sub/course_guide.php",
    "https://www.blueheron.co.kr/intro/course.php",
]


def fetch(url, out_dir):
    headers = {"User-Agent": "Mozilla/5.0 NEO-Golf-Data/1.0 (course-identity-verification)"}
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=20) as r:
            data = r.read()
            status = r.status
            final_url = r.geturl()
        safe_name = url.replace("https://", "").replace("/", "_") or "root"
        out_path = Path(out_dir) / f"{safe_name}.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        return {"url": url, "final_url": final_url, "status": status, "bytes": len(data), "saved": str(out_path)}
    except HTTPError as e:
        return {"url": url, "error": f"HTTP {e.code}"}
    except URLError as e:
        return {"url": url, "error": str(e.reason)}
    except Exception as e:
        return {"url": url, "error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="course_identity_check")
    a = ap.parse_args()
    for url in CANDIDATE_URLS:
        r = fetch(url, a.out_dir)
        print(r)


if __name__ == "__main__":
    main()
