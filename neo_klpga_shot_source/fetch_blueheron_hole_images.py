"""Fetch real official Blue Heron hole images for an arbitrary side+hole.

URL pattern confirmed real (not guessed) from the West Hole 3 fetch's own
real network traffic:
  .../page/course-information-hole-information-visual-{side}-hole{NN}.png
  .../page/course-information-hole-information-tip-{side}-hole{NN}.png
This substitutes side/number into that confirmed pattern and verifies
with a real HTTP fetch -- a 404 here is a real negative result, not
papered over.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = "https://blueheron.co.kr/static/pc/origin/assets/images/page/course-information-hole-information-{kind}-{side}-hole{num:02d}.png"


def fetch(url, out_path):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 NEO-Golf-Data/1.0"})
    try:
        with urlopen(req, timeout=20) as r:
            data = r.read()
        out_path.write_bytes(data)
        return {"url": url, "status": 200, "bytes": len(data)}
    except HTTPError as e:
        return {"url": url, "status": e.code, "error": str(e)}
    except Exception as e:
        return {"url": url, "error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", required=True, choices=["east", "west"])
    ap.add_argument("--hole", required=True, type=int)
    ap.add_argument("--out-dir", default="blueheron_hole_images")
    a = ap.parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for kind in ("visual", "tip"):
        url = BASE.format(kind=kind, side=a.side, num=a.hole)
        out_path = out / f"{a.side}_hole{a.hole:02d}_{kind}.png"
        r = fetch(url, out_path)
        results.append(r)
        print(r)


if __name__ == "__main__":
    main()
