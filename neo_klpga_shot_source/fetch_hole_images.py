"""Fetch real KLPGA hole background images (confirmed real URL pattern
from the site's own rendering code, see evidence_playerDetail_9115.html)
for use as Artifact map backgrounds. Also records real image dimensions
to check against the site's own SVG viewBox (0 0 708 471) before trusting
any coordinate overlay.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from urllib.request import Request, urlopen

BASE = "https://klpga.co.kr"


def fetch_hole_image(game, hole, variant, out_dir, cookie=None):
    suffix = "_G" if variant == "green" else ""
    url = f"{BASE}/DATA/holeImg2/{game}/{hole}{suffix}.png?ver=2026-10-02_1"
    headers = {
        "Referer": f"{BASE}/web/leaderboard/leaderboard?gameCode={game}",
        "User-Agent": "Mozilla/5.0 NEO-Golf-Data/1.0",
    }
    if cookie:
        headers["Cookie"] = cookie
    req = Request(url, headers=headers, method="GET")
    with urlopen(req, timeout=30) as r:
        data = r.read()
        status = r.status
    out_path = Path(out_dir) / f"hole_{hole}{suffix}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return status, out_path, len(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--holes", default="12")
    ap.add_argument("--cookie")
    ap.add_argument("--out-dir", default="hole_images")
    a = ap.parse_args()

    for hole in [int(x) for x in a.holes.split(",")]:
        for variant in ("overview", "green"):
            try:
                status, path, size = fetch_hole_image(a.game, hole, variant, a.out_dir, a.cookie)
                print(f"PASS hole={hole} variant={variant} status={status} size={size} -> {path}")
            except Exception as e:
                print(f"FAIL hole={hole} variant={variant}: {e}")


if __name__ == "__main__":
    main()
