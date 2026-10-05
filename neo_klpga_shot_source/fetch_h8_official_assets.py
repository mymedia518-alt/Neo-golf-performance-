"""Fetch Blue Heron East Hole 8's two official course-guide images.

Tournament H8 = Blue Heron East Hole 8 (confirmed: NEO_COURSE_IDENTITY_VERIFICATION.md,
18-hole systematic yardage cross-check, Blue tee 377yd = Tournament 377yd exact match).

URL template confirmed real (not guessed) from real network traffic during the
West Hole 3 fetch (see fetch_blueheron_hole_images.py docstring):
  https://blueheron.co.kr/static/pc/origin/assets/images/page/course-information-hole-information-{kind}-{side}-hole{NN}.png
This script only substitutes side=east, hole=08 into that already-verified template.
No new URL pattern is invented here.

Run this on a machine that can actually reach blueheron.co.kr (this sandbox's
egress to that host is blocked by container policy -- confirmed via direct
curl test, 403 connect_rejected). Needs only the Python standard library.

Usage:
    python fetch_h8_official_assets.py
    (or from repo root:)
    python neo_klpga_shot_source/fetch_h8_official_assets.py
"""
from __future__ import annotations
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "https://blueheron.co.kr/static/pc/origin/assets/images/page/course-information-hole-information-{kind}-east-hole08.png"
HERE = Path(__file__).parent
OUT_DIR = HERE / "course_maps" / "blue_heron" / "east" / "hole_08"

TARGETS = {
    "visual": OUT_DIR / "visual.png",
    "tip": OUT_DIR / "tip.png",
}


def fetch(kind: str, out_path: Path) -> dict:
    url = BASE.format(kind=kind)
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 NEO-Golf-Data/1.0",
        "Referer": "https://www.blueheron.co.kr/",
    })
    try:
        with urlopen(req, timeout=20) as r:
            data = r.read()
            status = r.status
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        return {"kind": kind, "url": url, "status": status, "bytes": len(data), "saved_to": str(out_path)}
    except HTTPError as e:
        return {"kind": kind, "url": url, "status": e.code, "error": str(e)}
    except URLError as e:
        return {"kind": kind, "url": url, "error": f"URLError: {e.reason}"}
    except Exception as e:
        return {"kind": kind, "url": url, "error": str(e)}


def main():
    print(f"Target directory: {OUT_DIR}")
    results = []
    for kind, out_path in TARGETS.items():
        r = fetch(kind, out_path)
        results.append(r)
        if "error" in r:
            print(f"FAIL {kind}: {r}")
        else:
            print(f"OK   {kind}: {r['bytes']} bytes -> {r['saved_to']}")
    ok = sum(1 for r in results if "error" not in r)
    print(f"\n{ok}/2 fetched.")
    if ok == 2:
        print("Next: run verify_h8_official_assets.py")


if __name__ == "__main__":
    main()
