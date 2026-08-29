"""Export the game_code=2026080001 POST-R3 finalist roster (player_code,
player_name) from the live, already-validated production page
(../docs/index.html at the repo root) to a small, checked-in CSV that
the player-team/sponsor collector (scripts/56) reads as its player
list.

This project's own hard-validation work earlier in the same session
confirmed this page carries exactly 62 finalists, each with a
`data-player-journey-trigger` row carrying `data-player-code` and
`data-player-name` — see docs/index.html's Player Journey feature. This
script re-derives the roster CSV from that same, single already-proven
source rather than hand-maintaining a second copy that could drift out
of sync with it.

Duplicate player_code / player_name are hard failures here (never
silently deduplicated) — a duplicate would indicate the source page
itself regressed since the 62/62 validation.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SITE_HTML_PATH = ROOT.parent / "docs" / "index.html"
OUTPUT_CSV_PATH = ROOT / "data" / "roster" / "r3_finalists_2026080001.csv"


def extract_roster(html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    seen_codes: set[str] = set()
    seen_names: set[str] = set()
    dup_codes: set[str] = set()
    dup_names: set[str] = set()
    for tr in soup.select("tr[data-player-journey-trigger]"):
        code = tr.get("data-player-code")
        name = tr.get("data-player-name")
        if not code or not name:
            raise ValueError(f"Trigger row missing data-player-code/data-player-name: {tr}")
        if code in seen_codes:
            dup_codes.add(code)
        if name in seen_names:
            dup_names.add(name)
        seen_codes.add(code)
        seen_names.add(name)
        rows.append((code, name))

    if dup_codes or dup_names:
        raise ValueError(
            f"Duplicate player_code(s) {sorted(dup_codes)} or player_name(s) "
            f"{sorted(dup_names)} found in docs/index.html's Player Journey "
            "trigger rows — refusing to export a roster with duplicates."
        )
    return rows


def main() -> int:
    print(f"[STEP 01] reading {SITE_HTML_PATH}", flush=True)
    html = SITE_HTML_PATH.read_text(encoding="utf-8")

    roster = extract_roster(html)
    print(f"[STEP 02] extracted {len(roster)} finalist rows", flush=True)

    if len(roster) != 62:
        print(
            f"HARD FAIL: expected exactly 62 finalists (the already-validated "
            f"count for game_code=2026080001 POST-R3), got {len(roster)}.",
            flush=True,
        )
        return 1

    kim_na_young = [name for code, name in roster if name == "김나영"]
    kim_na_young_code = [code for code, name in roster if name == "김나영"]
    if kim_na_young_code and kim_na_young_code[0] != "10114":
        print(
            f"HARD FAIL: 김나영's player_code is {kim_na_young_code[0]!r}, expected "
            "'10114' — this project has a documented history of a digit-transposed "
            "typo (11014) for this exact player. Refusing to export.",
            flush=True,
        )
        return 1

    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["player_code", "player_name"])
        for code, name in roster:
            writer.writerow([code, name])

    print(f"[STEP 03] wrote {OUTPUT_CSV_PATH} ({len(roster)} rows)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
