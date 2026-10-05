"""Verify Blue Heron East Hole 8's official visual.png / tip.png after fetch.

This checks only objective, measurable facts (file existence, PNG validity,
resolution, size, successful decode, basic color-composition plausibility).
It does NOT and CANNOT assert "this is definitely Hole 8" from pixel content
alone -- these illustrations carry no embedded hole-number text, so content
identity is a human visual-comparison step (against the coordinate-validated
hole_8.png landmarks: lake on the right side approaching the green, greenside
bunkers), not something this script fabricates a verdict for.

Run after fetch_h8_official_assets.py / .ps1 has populated:
  neo_klpga_shot_source/course_maps/blue_heron/east/hole_08/visual.png
  neo_klpga_shot_source/course_maps/blue_heron/east/hole_08/tip.png

Also supports --self-test, which runs the same checks against a known-real
sample pair already in this repo's git history (West Hole 3 visual/tip,
fetched in an earlier session) to prove the verification logic itself works,
without touching or fabricating the real H8 target files.
"""
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path

HERE = Path(__file__).parent
TARGET_DIR = HERE / "course_maps" / "blue_heron" / "east" / "hole_08"

# Known-real reference stats from the SAME asset family (different hole,
# already fetched + committed in an earlier session) -- used only as a
# loose plausibility range, never as a correctness proof for H8 itself.
REFERENCE_STATS = {
    "visual": {"size_hint": (527, 704), "note": "West Hole 3 / East Hole 1 visual.png, both 527x704"},
    "tip": {"size_hint": (623, 233), "note": "West Hole 3 tip.png (== elevation_reference.png, byte-identical), 623x233"},
}


def check_file(path: Path, kind: str) -> dict:
    result = {"kind": kind, "path": str(path)}
    if not path.exists():
        result["status"] = "MISSING"
        return result

    result["file_size_bytes"] = path.stat().st_size
    with open(path, "rb") as f:
        header = f.read(8)
    result["png_magic_valid"] = header == b"\x89PNG\r\n\x1a\n"
    if not result["png_magic_valid"]:
        result["status"] = "FAIL (not a valid PNG header)"
        return result

    try:
        from PIL import Image
        im = Image.open(path)
        im.load()  # force actual decode, not just header parse
        result["resolution"] = list(im.size)
        result["mode"] = im.mode
        result["decode_ok"] = True

        # objective color-composition facts only -- plausibility signal,
        # not a content-identity verdict
        rgba = im.convert("RGBA")
        w, h = rgba.size
        px = rgba.load()
        sample_n, green_n, blue_n, white_n = 0, 0, 0, 0
        step = max(1, (w * h) // 20000)  # sample for speed on large images
        i = 0
        for y in range(0, h, max(1, h // 140) or 1):
            for x in range(0, w, max(1, w // 140) or 1):
                r, g, b, a = px[x, y]
                if a < 10:
                    continue
                sample_n += 1
                if g > r and g > b and g > 80:
                    green_n += 1
                elif b > 140 and b > r + 15:
                    blue_n += 1
                elif r > 240 and g > 240 and b > 240:
                    white_n += 1
        result["color_plausibility"] = {
            "sampled_px": sample_n,
            "pct_green": round(100 * green_n / sample_n, 1) if sample_n else None,
            "pct_blue_waterish": round(100 * blue_n / sample_n, 1) if sample_n else None,
            "pct_white_bg": round(100 * white_n / sample_n, 1) if sample_n else None,
        }

        ref = REFERENCE_STATS.get(kind)
        if ref:
            result["matches_known_family_resolution"] = (list(im.size) == list(ref["size_hint"]))
            result["reference_note"] = ref["note"]

        result["status"] = "DECODE_OK -- content identity NOT verified (needs human visual comparison against hole_8.png landmarks)"
    except Exception as e:
        result["decode_ok"] = False
        result["status"] = f"FAIL (decode error: {e})"

    return result


def build_review_html(results: list[dict], out_html: Path, visual_path: Path, tip_path: Path):
    def img_tag(p: Path):
        if p.exists():
            return f'<img src="file://{p}" style="max-width:100%;border:1px solid #ccc">'
        return '<div style="padding:40px;background:#eee;text-align:center">MISSING</div>'

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>H8 official asset review</title>
<style>body{{font:14px sans-serif;padding:20px;max-width:1000px;margin:0 auto}}
.row{{display:flex;gap:20px;margin-bottom:20px}}
.col{{flex:1}}
pre{{background:#f5f5f5;padding:10px;font-size:11px;overflow:auto}}
h2{{font-size:15px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700}}
.ok{{background:#dcfce7;color:#166534}} .missing{{background:#fee2e2;color:#991b1b}}
</style></head><body>
<h1>Blue Heron East Hole 8 -- official asset review (DEV ONLY, not public UI)</h1>
<p>Content identity is NOT auto-confirmed. Compare against hole_8.png's known landmarks by eye.</p>
<div class="row">
<div class="col"><h2>visual.png</h2>{img_tag(visual_path)}</div>
<div class="col"><h2>tip.png</h2>{img_tag(tip_path)}</div>
</div>
<pre>{json.dumps(results, ensure_ascii=False, indent=2)}</pre>
</body></html>"""
    out_html.write_text(html, encoding="utf-8")


def run(target_dir: Path, label: str):
    visual_path = target_dir / "visual.png"
    tip_path = target_dir / "tip.png"
    results = [check_file(visual_path, "visual"), check_file(tip_path, "tip")]

    print(f"=== {label}: {target_dir} ===")
    for r in results:
        print(json.dumps(r, ensure_ascii=False, indent=2))

    both_present = visual_path.exists() and tip_path.exists()
    if not both_present:
        print("\nWAITING FOR H8 OFFICIAL ASSET -- not both files present yet.")
        return results, False

    review_html = target_dir / "review.html"
    build_review_html(results, review_html, visual_path, tip_path)
    print(f"\nWrote {review_html} -- open it (or screenshot it) to visually compare both images.")
    return results, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true",
                     help="Run the same checks against the known West-Hole-3 sample already in git history, to prove the verification logic works without touching the real H8 target.")
    a = ap.parse_args()

    if a.self_test:
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp()) / "self_test"
        tmp.mkdir(parents=True)
        repo_root = HERE.parent
        for kind, commit, src in [
            ("visual", "654c0c2", "neo_klpga_shot_source/hole_images/west_hole03_visual_reference.png"),
            ("tip", "654c0c2", "neo_klpga_shot_source/hole_images/west_hole03_elevation_reference.png"),
        ]:
            data = subprocess.run(["git", "show", f"{commit}:{src}"], cwd=repo_root, capture_output=True, check=True).stdout
            (tmp / f"{kind}.png").write_bytes(data)
        run(tmp, "SELF-TEST (West Hole 3 sample, not H8 -- proves the script works)")
        return

    run(TARGET_DIR, "H8 TARGET")


if __name__ == "__main__":
    main()
