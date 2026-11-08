"""Replace docs/ranking/index.html's <main class="ranking-page">...</main>
block with the operator-supplied 2026-11-08 NEO 랭킹 content (100
players, reflecting the Daebo HausD Championship's final results),
leaving the header, <style>, and <script> blocks -- and the SG-profile
<dialog> that follows </main> -- byte-for-byte untouched. Mirrors
scripts/302's exact pattern for the 2026-11-01 update.

Source: klpga_pipeline/content/website_v2/ranking-main-2026-11-08.html
(built from the operator-supplied 100-player rank/score/rounds/events
table; player_id/flag/sponsor resolved against existing repo player
records; formal/참고 status assigned per this page's own documented
rule -- 40+ rounds formal, 20-39 참고 -- not the V1_FROZEN events>=10
rule, since the live page's own copy states the rounds-based rule).
"""
from __future__ import annotations

from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
CONTENT = PIPELINE_ROOT / "content" / "website_v2"
RANKING_PAGE = REPO_ROOT / "docs" / "ranking" / "index.html"
NEW_MAIN_PATH = CONTENT / "ranking-main-2026-11-08.html"

OLD_MAIN_START = '<main class="ranking-page">'
OLD_MAIN_END = "</main>"


def main() -> None:
    html = RANKING_PAGE.read_text(encoding="utf-8")
    new_main = NEW_MAIN_PATH.read_text(encoding="utf-8")

    assert new_main.startswith(OLD_MAIN_START), "new main content does not start with the expected <main> tag"
    assert new_main.endswith(OLD_MAIN_END), "new main content does not end with </main>"
    assert new_main.count("<tr") == 101, f"expected 101 <tr> (1 thead + 100 body rows), found {new_main.count('<tr')}"

    start = html.find(OLD_MAIN_START)
    assert start != -1, "ranking-page main block not found verbatim"
    end = html.find(OLD_MAIN_END, start) + len(OLD_MAIN_END)
    assert html.count(OLD_MAIN_START) == 1, f"expected exactly 1 ranking-page main block, found {html.count(OLD_MAIN_START)}"

    html2 = html[:start] + new_main + html[end:]
    assert html2 != html
    assert html2.count("<dialog") == html.count("<dialog"), "the SG-profile dialog after </main> must be untouched"
    assert html2.count("<script>") == html.count("<script>"), "script blocks must be untouched"
    assert html2.count("<style>") == html.count("<style>") if "<style>" in html else True

    RANKING_PAGE.write_text(html2, encoding="utf-8")
    print("written", str(RANKING_PAGE))


if __name__ == "__main__":
    main()
