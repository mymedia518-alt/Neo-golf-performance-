from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
HTML_PATH = HERE / "index.html"
SHOT_DIR = HERE / "screenshots"
SHOT_DIR.mkdir(exist_ok=True)

VIEWPORTS = {
    "desktop_1440x900": (1440, 900),
    "mobile_390x844": (390, 844),
}

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for name, (w, h) in VIEWPORTS.items():
        page = browser.new_page(viewport={"width": w, "height": h})
        page.goto(f"file://{HTML_PATH}")
        page.wait_for_timeout(200)
        out = SHOT_DIR / f"{name}.png"
        page.screenshot(path=str(out), full_page=True)
        scroll_w = page.evaluate("document.documentElement.scrollWidth")
        client_w = page.evaluate("document.documentElement.clientWidth")
        print(f"wrote {out} -- {name}: scrollWidth={scroll_w} clientWidth={client_w} "
              f"{'OK' if scroll_w <= client_w + 1 else 'FAIL overflow'}")
        page.close()
    browser.close()
