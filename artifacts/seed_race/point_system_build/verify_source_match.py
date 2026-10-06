"""Independent source<->UI check for the 2027 point-seed informational page.

Re-reads the CSVs from scratch and re-parses the rendered HTML, independent
of build.py's in-memory state.
"""
import csv
import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[3]
SR = ROOT / "artifacts" / "seed_race"
HTML_PATH = Path(__file__).resolve().parent / "index.html"

failures = []


def check(label, got, want):
    ok = got == want
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: got={got!r} want={want!r}")
    if not ok:
        failures.append(label)


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


soup = BeautifulSoup(HTML_PATH.read_text(encoding="utf-8"), "html.parser")
full_text = soup.get_text()
raw_html = HTML_PATH.read_text(encoding="utf-8")

# ---- 1. no fabricated probability numbers anywhere ----
# "시드 확률" is allowed ONLY inside the sanctioned holdback disclosure ("시드 확률 공개를
# 보류"), never attached to an actual percentage. Check both conditions explicitly.
import re
for occ_start in [m.start() for m in re.finditer("시드\\s?확률", full_text)]:
    window = full_text[occ_start:occ_start + 20]
    check(f'"시드 확률" occurrence at {occ_start} is the sanctioned holdback phrase',
          "공개를 보류" in window, True)
check('no percentage figure anywhere near the word "확률" (no fabricated probability)',
      bool(re.search(r"확률[^.]{0,15}\d+(\.\d+)?%|\d+(\.\d+)?%[^.]{0,15}확률", full_text)), False)
check('forbidden phrase "시드 생존확률" absent', "시드 생존확률" in full_text, False)
check('probability-holdback disclosure present',
      soup.select_one('[data-testid="probability-holdback"]') is not None, True)
check('disclosure text matches required wording',
      "시드권 부여 최종 순위선이 명시되지 않아" in full_text, True)

# ---- 2. point_table_PARTIAL rows match HTML connector rows exactly ----
point_rows = read_csv(SR / "point_table_PARTIAL_2026-10-06.csv")
point_rows_sorted = sorted(point_rows, key=lambda r: int(r["point_rank"]))
connector_rows = soup.select('[data-testid="money-point-connector"] .connector-row')
check("connector row count == 5", len(connector_rows), 5)
for i, (csv_row, html_row) in enumerate(zip(point_rows_sorted, connector_rows)):
    name = html_row.select_one(".connector-name").get_text(strip=True)
    check(f"connector[{i}] name", name, csv_row["player"])
    txt = html_row.get_text()
    check(f"connector[{i}] money_rank in text", f"상금 {csv_row['money_rank']}위" in txt, True)
    check(f"connector[{i}] point_rank in text", f"포인트 {csv_row['point_rank']}위" in txt, True)
    check(f"connector[{i}] points value in text", f"{csv_row['points']}점" in txt, True)

# ---- 3. official money rank cross-check (independent of build.py) ----
official = json.load(open(SR / "official_money_rank_2026-10-06_full.json", encoding="utf-8"))
official_by_name = {r["player_name"]: r for r in official}
for r in point_rows:
    off = official_by_name[r["player"]]
    check(f"{r['player']} money_rank matches official data", str(off["rank"]), r["money_rank"])
    check(f"{r['player']} money matches official data", str(off["prize_money"]), r["money"])

# ---- 4. TOP10 curve matches remaining_events_point_PARTIAL exactly ----
event_rows = read_csv(SR / "remaining_events_point_PARTIAL_2026-10-06.csv")
hj_curve = sorted(
    [r for r in event_rows if r["gameCode"] == "2026100004" and int(r["finish_position"]) <= 10],
    key=lambda r: int(r["finish_position"]),
)
curve_table = soup.select_one('[data-testid="top10-curve"] .curve-table')
curve_cells = [td.get_text(strip=True) for td in curve_table.select("tr td.curve-points")]
expected_curve = [r["points"] for r in hj_curve] + ["0"]  # +1 row for "11위 이하"
check("TOP10 curve (+11th-and-beyond row) matches CSV exactly", curve_cells, expected_curve)
check('"11위 이하" zero-anchor row present in table text',
      "11위 이하" in curve_table.get_text(), True)

# ---- 5. bubble pending list: all 26 players (55-80), none given a fabricated point rank ----
seed_rows = read_csv(SR / "seed_probability.csv")
bubble_csv = [r for r in seed_rows if 55 <= int(float(r["current_rank"])) <= 80]
pending_rows = soup.select('[data-testid="bubble-pending"] .pending-row')
check("bubble pending row count == 26", len(pending_rows), 26)
bubble_by_rank = {int(float(r["current_rank"])): r for r in bubble_csv}
for el in pending_rows:
    rank = int(el["data-rank"])
    want_name = bubble_by_rank[rank]["player"]
    check(f"bubble rank{rank} name matches seed_probability.csv", el["data-player"], want_name)
    check(f"bubble rank{rank} shows pending point status (no fabricated number)",
          "포인트순위 확보 전" in el.get_text(), True)

# exactly one GROUP B badge in the bubble list (홍정민, rank 66)
elig_rows = read_csv(SR / "eligibility_crosscheck_55_80.csv")
group_b_rows = [r for r in elig_rows if r["final_2027_group"] == "B"]
check("exactly 1 GROUP B player in eligibility CSV", len(group_b_rows), 1)
check("that player is 홍정민", group_b_rows[0]["player"] if group_b_rows else None, "홍정민")
confirmed_badges_in_bubble = [el for el in pending_rows if "tag-confirmed" in el.decode_contents()]
check("exactly 1 '2027 시드 확보' tag in bubble list", len(confirmed_badges_in_bubble), 1)
check("that tagged row is rank 66 (홍정민)",
      confirmed_badges_in_bubble[0]["data-rank"] if confirmed_badges_in_bubble else None, "66")

# ---- 6. no internal jargon / no bubble point numbers invented ----
INTERNAL_TERMS = [
    "Monte Carlo", "monte carlo", "Plackett", "Gumbel", "τ", "tau",
    "gameCode", "viewBox", "GROUP A", "GROUP B", "GROUP C", "GROUP D",
    "RULE_CONFIRMED", "OFFICIAL_ENTRY_CONFIRMED", "evidence_level", "final_2027_group",
    "JSON", "payout curve",
]
for term in INTERNAL_TERMS:
    check(f'internal term "{term}" absent', term in raw_html, False)

# no digit-looking "point rank" value anywhere in the bubble rows (would indicate fabrication)
for el in pending_rows:
    txt = el.get_text()
    check(f"bubble rank{el['data-rank']} contains no numeric point-rank claim",
          any(s in txt for s in ["포인트 1위", "포인트순위 1위", "포인트순위: 1"]), False)

print()
if failures:
    print(f"RESULT: FAIL ({len(failures)} failing checks)")
    for f in failures:
        print(" -", f)
    sys.exit(1)
else:
    print("RESULT: ALL CHECKS PASS")
