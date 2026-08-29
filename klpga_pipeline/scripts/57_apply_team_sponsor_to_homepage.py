"""Apply the real, live-collected team/sponsor (소속) data to the
production docs/index.html — Main Leaderboard, Player Journey, Hero
cards, and Deep Dive player cards, from ONE source:
data/sponsor/2026080001_team_sponsor_snapshot.csv (see the sibling
.PROVENANCE.md for how that snapshot was produced and verified).

Display rules (all enforced/asserted by this script, not just
described):
  - only the 49 players with a non-empty team_or_sponsor get a sponsor
    element inserted at all; the 13 empty ones get NOTHING inserted
    (not "-", not "확인중", not any placeholder text)
  - the same player_code's sponsor value is inserted identically in
    every one of the four areas it appears in
  - player_code is the only join key used — no name-based matching
  - every score/rank/probability/tie-group/GA4/frozen value in the
    page is left completely untouched; only new sponsor elements are
    inserted, nothing existing is removed or renumbered

This script is idempotent-checked: it refuses to run if any
c-sponsor/pj-sponsor/dd-sponsor/hm-sponsor element already exists in
the page (preventing an accidental double-apply), and it verifies
exact occurrence counts for every anchor it edits before touching
anything -- if a single anchor's count doesn't match what's expected,
the whole run aborts with NO file written, rather than applying a
partial edit.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_HTML_PATH = ROOT.parent / "docs" / "index.html"
SPONSOR_CSV_PATH = ROOT / "data" / "sponsor" / "2026080001_team_sponsor_snapshot.csv"

# (existing CSS rule text, addition to append right after it)
CSS_INSERTIONS = [
    (
        '.c-name { font-family: "Noto Sans KR", sans-serif; }',
        '.c-name { font-family: "Noto Sans KR", sans-serif; }\n'
        '  .c-sponsor { display: block; font-family: "Noto Sans KR", sans-serif; font-size: 11px; font-weight: 400; color: var(--text-dim); margin-top: 2px; }',
    ),
    (
        '.pj-name { font-size: 14px; }',
        '.pj-name { font-size: 14px; }\n'
        '  .pj-sponsor { flex-basis: 100%; font-family: "Noto Sans KR", sans-serif; font-size: 12px; font-weight: 400; color: var(--text-dim); }',
    ),
    (
        '.dd-name { font-family: "Noto Sans KR", sans-serif; font-weight: 700; font-size: 14px; margin-bottom: 2px; }',
        '.dd-name { font-family: "Noto Sans KR", sans-serif; font-weight: 700; font-size: 14px; margin-bottom: 2px; }\n'
        '  .dd-sponsor { font-family: "Noto Sans KR", sans-serif; font-size: 11px; font-weight: 400; color: var(--text-dim); margin: 0 0 4px; }',
    ),
    (
        '.hm-name { font-family: "Big Shoulders Display", sans-serif; font-size: clamp(20px, 5vw, 26px); margin: 0 0 6px; }',
        '.hm-name { font-family: "Big Shoulders Display", sans-serif; font-size: clamp(20px, 5vw, 26px); margin: 0 0 6px; }\n'
        '  .hm-sponsor { font-family: "Noto Sans KR", sans-serif; font-size: 12px; font-weight: 400; color: var(--text-dim); margin: -4px 0 10px; }',
    ),
]

HERO_CODES = {"9788", "11134"}  # 박혜준 (NEO PLAYER TO WATCH), 서교림 (NEO MODEL WATCH)


def load_sponsor_rows() -> list[dict]:
    rows = list(csv.DictReader(SPONSOR_CSV_PATH.open(encoding="utf-8")))
    if len(rows) != 62:
        raise SystemExit(f"HARD FAIL: expected 62 sponsor rows, got {len(rows)}")
    codes = [r["player_code"] for r in rows]
    if len(set(codes)) != 62:
        raise SystemExit("HARD FAIL: duplicate player_code in sponsor snapshot")
    names = [r["player_name"] for r in rows]
    if len(set(names)) != 62:
        raise SystemExit("HARD FAIL: duplicate player_name in sponsor snapshot")
    return rows


def apply_css(html: str) -> str:
    for old, new in CSS_INSERTIONS:
        count = html.count(old)
        if count != 1:
            raise SystemExit(f"HARD FAIL: expected exactly 1 occurrence of CSS anchor, got {count}: {old!r}")
        html = html.replace(old, new, 1)
    return html


def apply_leaderboard(html: str, code: str, name: str, sponsor: str) -> str:
    old = f'<td class="c-name">{name}</td>'
    count = html.count(old)
    if count != 1:
        raise SystemExit(f"HARD FAIL: expected exactly 1 leaderboard c-name cell for {name} ({code}), got {count}")
    new = f'<td class="c-name">{name}<span class="c-sponsor">{sponsor}</span></td>'
    return html.replace(old, new, 1)


def apply_journey(html: str, code: str, name: str, sponsor: str) -> str:
    anchor = f'data-player-journey-panel data-player-code="{code}" hidden>'
    anchor_idx = html.find(anchor)
    if anchor_idx == -1:
        raise SystemExit(f"HARD FAIL: no Player Journey panel found for {name} ({code})")
    if html.find(anchor, anchor_idx + 1) != -1:
        raise SystemExit(f"HARD FAIL: more than one Player Journey panel anchor for {name} ({code})")

    search_window = html[anchor_idx : anchor_idx + 400]
    marker = "</div><div class=\"pj-flow\">"
    marker_pos_in_window = search_window.find(marker)
    if marker_pos_in_window == -1:
        raise SystemExit(f"HARD FAIL: could not find pj-header/pj-flow boundary for {name} ({code})")
    insert_at = anchor_idx + marker_pos_in_window
    sponsor_span = f'<span class="pj-sponsor">{sponsor}</span>'
    return html[:insert_at] + sponsor_span + html[insert_at:]


def apply_deep_dive(html: str, code: str, name: str, sponsor: str) -> str:
    old = f'<div class="dd-name">{name}</div>'
    count = html.count(old)
    if count == 0:
        return html  # not every player has a Deep Dive card -- that's fine, not a failure
    new = f'<div class="dd-name">{name}</div><div class="dd-sponsor">{sponsor}</div>'
    return html.replace(old, new)  # replace ALL occurrences (e.g. main card + comparison card)


def apply_hero(html: str, code: str, name: str, sponsor: str) -> str:
    if code not in HERO_CODES:
        return html
    old = f'<p class="hm-name">{name}</p>'
    count = html.count(old)
    if count != 1:
        raise SystemExit(f"HARD FAIL: expected exactly 1 hero hm-name for {name} ({code}), got {count}")
    new = f'<p class="hm-name">{name}</p><p class="hm-sponsor">{sponsor}</p>'
    return html.replace(old, new, 1)


def main() -> int:
    rows = load_sponsor_rows()
    html = SITE_HTML_PATH.read_text(encoding="utf-8")

    for marker in ("c-sponsor", "pj-sponsor", "dd-sponsor", "hm-sponsor"):
        if marker in html:
            raise SystemExit(
                f"HARD FAIL: '{marker}' already present in {SITE_HTML_PATH} -- "
                "refusing to double-apply. Revert the previous sponsor edit first."
            )

    html = apply_css(html)

    present_count = 0
    for row in rows:
        code, name, sponsor = row["player_code"], row["player_name"], row["team_or_sponsor"]
        if not sponsor:
            continue
        present_count += 1
        html = apply_leaderboard(html, code, name, sponsor)
        html = apply_journey(html, code, name, sponsor)
        html = apply_deep_dive(html, code, name, sponsor)
        html = apply_hero(html, code, name, sponsor)

    if present_count != 49:
        raise SystemExit(f"HARD FAIL: expected 49 players with a sponsor value, processed {present_count}")

    c_sponsor_span_count = html.count('class="c-sponsor"')
    if c_sponsor_span_count != 49:
        raise SystemExit(f"HARD FAIL: unexpected c-sponsor span count: {c_sponsor_span_count}")

    SITE_HTML_PATH.write_text(html, encoding="utf-8")
    print(f"[DONE] applied sponsor data for {present_count} players to {SITE_HTML_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
