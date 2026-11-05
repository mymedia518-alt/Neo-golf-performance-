"""Flip HOME's featured-tournament card from the previous tournament
(제20회 S-OIL 챔피언십, now finished) to the new current tournament
(대보 하우스디 챔피언십, game_code 2026110001) -- the standard
"flip HOME from previous tournament's FINAL to this tournament's
PRE/current" step every prior tournament transition on this site has
used (see START_TOURNAMENT.md).

SCOPE: the featured-tournament card at the very top of home ONLY
(<a class="home-tournament-card neo-home-featured-tournament">).
Nothing else on docs/index.html is touched -- per explicit operator
instruction, the "최근 종료 대회" line and the full "최종 결과" table
section below it (S-OIL's real final results) stay exactly as they
are: real, correct, already-published content about the tournament
that actually just finished, independent of which tournament is now
"current".

Since no PRE/entry-list page exists yet for 2026110001 (out of scope
for this task -- see the live win-probability page build), the card
links to the one real, already-published page this tournament has:
/tournaments/2026/2026110001/live/ (real-time win probability,
REFERENCE_ESTIMATE/참고 예상 disclosed there).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT.parent / "docs" / "index.html"

OLD_CARD = (
    '<a class="home-tournament-card neo-home-featured-tournament" href="#home-fr-records" '
    'aria-label="제20회 S-OIL 챔피언십 최종 결과로 이동">'
    '<p class="meta">이번 대회 · 2026년 10월 29일~11월 1일 · 엘리시안 제주</p>'
    '<h3>제20회 S-OIL 챔피언십</h3>'
    '<p class="section-link-row">최종 결과가 아래로 이어집니다 ↓</p></a>'
)

NEW_CARD = (
    '<a class="home-tournament-card neo-home-featured-tournament" href="/tournaments/2026/2026110001/live/" '
    'aria-label="대보 하우스디 챔피언십 실시간 우승확률로 이동">'
    '<p class="meta">이번 대회 · 2026년 11월 6일~11월 8일 · 서원밸리CC 서원힐스</p>'
    '<h3>대보 하우스디 챔피언십</h3>'
    '<p class="section-link-row">실시간 우승확률 보기 →</p></a>'
)


def main() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")

    count = html.count(OLD_CARD)
    if count != 1:
        raise RuntimeError(
            f"expected exactly 1 occurrence of the current featured-tournament card, found {count} -- "
            "refusing to patch (home.html may have changed since this script was written)."
        )

    patched = html.replace(OLD_CARD, NEW_CARD)

    if "최근 종료 대회" not in patched:
        raise RuntimeError("the '최근 종료 대회' line disappeared -- refusing to write a patch that touched it")
    if "최종 결과 <small>68명</small>" not in patched:
        raise RuntimeError("the FINAL RESULTS table section header disappeared -- refusing to write a patch that touched it")
    if patched.count(OLD_CARD.split("<h3>")[0]) != 0:
        pass  # sanity: old card's opening markup should be fully gone (checked by the replace itself)

    before_minus_card = html.replace(OLD_CARD, "")
    after_minus_card = patched.replace(NEW_CARD, "")
    if before_minus_card != after_minus_card:
        raise RuntimeError(
            "the patch changed something outside the featured-tournament card -- refusing to write it. "
            "This is a hard assert: every byte of the page other than the swapped card must be identical."
        )

    INDEX_PATH.write_text(patched, encoding="utf-8")
    print(f"patched {INDEX_PATH}: featured-tournament card flipped to 대보 하우스디 챔피언십 (2026110001)")
    print("verified: everything else in index.html is byte-identical (최근 종료 대회 line + 최종 결과 table untouched)")


if __name__ == "__main__":
    main()
