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

# point_rank display is now UNLOCKED for the 55-80 bubble, but the 2027 SEED CUTOFF is still
# unresolved -- these cutoff-implying phrases must stay banned regardless of the unlock.
for forbidden in ["시드확률", "안전확률", "탈락확률", "포인트 60위가 시드 경계", "안전권"]:
    check(f'forbidden cutoff-implying phrase "{forbidden}" absent', forbidden in full_text, False)
check('explicit "point_rank unlocked != seed cutoff" disclosure present',
      "이 포인트순위는 2027 시드 cutoff가 아니다" in full_text, True)

# ---- 2. point_table_PARTIAL rows match HTML connector rows exactly ----
point_rows = read_csv(SR / "point_table_PARTIAL_2026-10-06.csv")
point_rows_ranked = [r for r in point_rows if r["point_rank"] != "UNRECONCILED"]
point_rows_sorted = sorted(point_rows_ranked, key=lambda r: int(r["point_rank"]))
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

# ---- 5. bubble list: all 26 players (55-80), real points + full-field point_rank + delta ----
seed_rows = read_csv(SR / "seed_probability.csv")
bubble_csv = [r for r in seed_rows if 55 <= int(float(r["current_rank"])) <= 80]
bubble_points = read_csv(SR / "point_values_bubble_55_80_2026-10-06.csv")
bubble_points_by_rank = {int(r["current_rank"]): r for r in bubble_points}
pending_rows = soup.select('[data-testid="bubble-pending"] .pending-row')
check("bubble pending row count == 26", len(pending_rows), 26)
bubble_by_rank = {int(float(r["current_rank"])): r for r in bubble_csv}
official = json.load(open(SR / "official_money_rank_2026-10-06_full.json", encoding="utf-8"))
official_by_name = {r["player_name"]: r for r in official}

# internal self-consistency of the relayed point_rank/delta data, independent of build.py:
# delta must equal current_rank - point_rank for every non-blank row, and point_rank must be
# monotonic with points (desc) with exact ties sharing identical point_rank.
confirmed_bp_rows = [r for r in bubble_points if r["points_status"] == "CONFIRMED_VALUE"]
check("20 non-blank rows have a confirmed points value", len(confirmed_bp_rows), 20)
for r in confirmed_bp_rows:
    want_delta = int(r["current_rank"]) - int(r["point_rank"])
    check(f"{r['player']} delta arithmetic (current_rank - point_rank)", int(r["delta"]), want_delta)
by_points_desc = sorted(confirmed_bp_rows, key=lambda r: -int(r["points"]))
prev = None
for r in by_points_desc:
    if prev is not None:
        if int(r["points"]) == int(prev["points"]):
            check(f"{r['player']}/{prev['player']} tied points share identical point_rank",
                  r["point_rank"], prev["point_rank"])
        else:
            check(f"point_rank monotonic: {r['player']} point_rank >= {prev['player']} point_rank",
                  int(r["point_rank"]) >= int(prev["point_rank"]), True)
    prev = r

for el in pending_rows:
    rank = int(el["data-rank"])
    want_name = bubble_by_rank[rank]["player"]
    check(f"bubble rank{rank} name matches seed_probability.csv", el["data-player"], want_name)
    bp = bubble_points_by_rank[rank]
    off = official_by_name[bp["player"]]
    check(f"bubble rank{rank} money matches official data", str(off["prize_money"]), bp["money"])
    txt = el.get_text()
    if bp["points_status"] == "CONFIRMED_VALUE":
        check(f"bubble rank{rank} shows real points value from CSV", f"{bp['points']}점" in txt, True)
        check(f"bubble rank{rank} shows correct point_rank from CSV",
              f"포인트 {bp['point_rank']}위" in txt, True)
        delta = int(bp["delta"])
        if delta > 0:
            want_badge = f"▲{delta}"
        elif delta < 0:
            want_badge = f"▼{-delta}"
        else:
            want_badge = "0"
        check(f"bubble rank{rank} shows correct delta badge", want_badge in txt, True)
    else:
        check(f"bubble rank{rank} (blank in source) shows dash, not a fabricated 0 or number",
              "—" in txt, True)
        check(f"bubble rank{rank} blank does NOT show a numeric points value",
              f"{bp['money']}점" in txt, False)  # sanity: money string never mistaken for a points value
        check(f"bubble rank{rank} blank shows no numeric 포인트순위 N위 claim",
              bool(re.search(r"포인트순위\s*\d+\s*위", txt)), False)
        check(f"bubble rank{rank} blank shows 포인트순위 — (no rank without a points value)",
              "포인트순위 —" in txt, True)

# named examples explicitly called out by the user -- exact HTML assertions
NAMED_EXAMPLES = [
    ("김나현2", 71, 48, "▲23"),
    ("홍정민", 66, 45, "▲21"),
    ("조아연", 59, 41, "▲18"),
    ("김새로미", 60, 52, "▲8"),
    ("안재희", 58, 70, "▼12"),
]
for name, money_rank, point_rank, badge in NAMED_EXAMPLES:
    el = next(e for e in pending_rows if int(e["data-rank"]) == money_rank)
    txt = el.get_text()
    check(f"named example {name} ({money_rank}->{point_rank}{badge}): point_rank in row",
          f"포인트 {point_rank}위" in txt, True)
    check(f"named example {name} ({money_rank}->{point_rank}{badge}): delta badge in row",
          badge in txt, True)
    check(f"named example {name} row player name matches", el["data-player"], name)

# footnote for blanks present
check('blank-points footnote (A/B/C semantics) present',
      "획득 실적 없음" in full_text and "자격 미충족" in full_text and "자료 누락" in full_text, True)

# exactly one GROUP B badge in the bubble list (홍정민, rank 66)
elig_rows = read_csv(SR / "eligibility_crosscheck_55_80.csv")
group_b_rows = [r for r in elig_rows if r["final_2027_group"] == "B"]
check("exactly 1 GROUP B player in eligibility CSV", len(group_b_rows), 1)
check("that player is 홍정민", group_b_rows[0]["player"] if group_b_rows else None, "홍정민")
confirmed_badges_in_bubble = [el for el in pending_rows if "tag-confirmed" in el.decode_contents()]
check("exactly 1 '별도 시드 확보' tag in bubble list", len(confirmed_badges_in_bubble), 1)
check("that tagged row is rank 66 (홍정민)",
      confirmed_badges_in_bubble[0]["data-rank"] if confirmed_badges_in_bubble else None, "66")

# ---- 5b. hero reversal cards: computed from delta (current_rank - point_rank), data-driven ----
confirmed_delta = [(int(r["current_rank"]), r["player"], int(r["point_rank"]), int(r["delta"]))
                    for r in bubble_points if r["points_status"] == "CONFIRMED_VALUE"]
up_sorted = sorted(confirmed_delta, key=lambda t: -t[3])
want_top3_up = up_sorted[:3]
want_biggest_down = min(confirmed_delta, key=lambda t: t[3])
check("data-driven top-3 UP == [김나현2, 홍정민, 조아연]",
      [t[1] for t in want_top3_up], ["김나현2", "홍정민", "조아연"])
check("data-driven biggest DOWN == 안재희", want_biggest_down[1], "안재희")

hcards = soup.select('[data-testid="bubble-hero-cards"] .hcard')
check("hero card count == 5 (4 grid cards + 1 special 김새로미 card)", len(hcards), 5)
hcard_texts = [c.get_text() for c in hcards]
for rank, name, prank, delta in want_top3_up + [want_biggest_down]:
    badge = f"▲{delta}" if delta > 0 else (f"▼{-delta}" if delta < 0 else "0")
    matched = any(name in t and f"{rank}위" in t and f"{prank}위" in t and badge in t for t in hcard_texts)
    check(f"hero card for {name} ({rank}->{prank}, {badge}) present and correct", matched, True)
check("hero card for 홍정민 includes independent-exemption badge",
      any("홍정민" in t and "별도 시드 확보" in t for t in hcard_texts), True)

# special 김새로미 callout card (60->52, exact boundary reframing, no "안전권" wording)
ksr_card = soup.select_one('[data-testid="hcard-kimsaeromi"]')
check("김새로미 special card present", ksr_card is not None, True)
if ksr_card:
    ksr_txt = ksr_card.get_text()
    check("김새로미 card shows 60위 -> 52위", "60위" in ksr_txt and "52위" in ksr_txt, True)
    check("김새로미 card shows ▲8 badge", "▲8" in ksr_txt, True)
    check("김새로미 card exact required copy present",
          "상금 기준에서는 정확히 경계선. 포인트로 보면 위치가 8계단 달라진다." in ksr_txt, True)
    check("김새로미 card does NOT use 안전권 wording", "안전권" in ksr_txt, False)

# hero-fact concrete opening line
check('hero-fact line "상금 71위 김나현2는 포인트 48위다. 23계단이 달라진다." present',
      "상금 71위 김나현2는 포인트 48위다. 23계단이 달라진다." in full_text, True)

# ---- 6. tie-handling fixture: TWO tables (10억 real-event, 12억 example), each matches its CSV subset exactly ----
tie_fixture = read_csv(SR / "tie_handling_fixture_OFFICIAL.csv")
tie_10eok = [r for r in tie_fixture if r["purse_bracket"] == "10억~12억 미만"]
tie_12eok = [r for r in tie_fixture if r["purse_bracket"] == "12억~15억 미만"]
check("tie fixture CSV has 11 total rows (4 original + 7 new)", len(tie_fixture), 11)
check("10억 bracket tie fixture rows == 7", len(tie_10eok), 7)
check("12억 bracket tie fixture rows == 4", len(tie_12eok), 4)

tie_tables = soup.select(".tie-fixture .curve-table")
check("two tie-handling fixture tables present (10억 real event + 12억 example)", len(tie_tables), 2)
for csv_subset, html_table, label in [(tie_10eok, tie_tables[0] if len(tie_tables) > 0 else None, "10억"),
                                        (tie_12eok, tie_tables[1] if len(tie_tables) > 1 else None, "12억")]:
    if html_table is None:
        check(f"{label} tie table present", False, True)
        continue
    rows_html = html_table.select("tr")[1:]
    check(f"{label} tie table row count matches CSV subset", len(rows_html), len(csv_subset))
    for csv_row, html_row in zip(csv_subset, rows_html):
        cells = [td.get_text(strip=True) for td in html_row.select("td")]
        check(f"{label} tie row '{csv_row['tied_finish_label']}' label", cells[0], csv_row["tied_finish_label"])
        check(f"{label} tie row '{csv_row['tied_finish_label']}' points", cells[2], csv_row["points_each"])

check('tie-handling explanation text present (no averaging/splitting)',
      "나눠서 각 10.3점이 아니다" in full_text, True)
check('cross-validation callout: 10억원 real event matches the published TOP10 curve exactly',
      "1위부터 10위까지 전부 정확히 일치한다" in full_text, True)
check('callout that ties can push total point-earners above 10',
      "10명보다 많은 선수가 포인트를 받을 수 있다" in full_text, True)

# ---- 6b. 장은수 (new point-value-only row, no reconciled rank) handled honestly ----
point_table_rows = read_csv(SR / "point_table_PARTIAL_2026-10-06.csv")
jangeunsu = next(r for r in point_table_rows if r["player"] == "장은수")
check("장은수 money_rank matches official data", jangeunsu["money_rank"], "5")
off_jes = official_by_name["장은수"]
check("장은수 money matches official data", str(off_jes["prize_money"]), jangeunsu["money"])
check("장은수 point_rank recorded as UNRECONCILED (not guessed)", jangeunsu["point_rank"], "UNRECONCILED")
check("장은수 NOT included in the 5-player money<->point rank connector module",
      any(el.select_one(".connector-name") and el.select_one(".connector-name").get_text(strip=True) == "장은수"
          for el in connector_rows),
      False)
check("page explicitly notes 장은수's points are known but her point_rank is not",
      "장은수" in full_text and "정확한 포인트 순위는 아직 알 수 없다" in full_text, True)

# ---- 7. WHY copy scoped explicitly to "10억원 일반대회" (not generalized) ----
check('WHY/TOP10 copy explicitly scopes the "0 beyond 10th" rule to 10억원 일반대회',
      "10억원 일반대회에서는 Top10" in full_text, True)
check('copy does not claim the rule applies to all tournaments/majors generally',
      "다른 대회 규모·메이저에도 똑같이 적용된다고 일반화하지 않는다" in full_text, True)
check('copy uses "Top10 순위" framing (position-based), never "10명만" (headcount framing, '
      "wrong once ties are involved)",
      "10명만" in full_text, False)
check('WHY section uses the exact requested phrasing "Top10 순위에 들어야 쌓인다"',
      "대상포인트는 Top10 순위에 들어야 쌓인다" in full_text, True)
check('WHY section uses the exact requested phrasing "컷을 통과해도 쌓인다"',
      "상금은 컷을 통과해도 쌓인다" in full_text, True)
check('WHY section closing line updated to "어떤 기준으로 보느냐에 따라 순위는 크게 달라질 수 있다"',
      "어떤 기준으로 보느냐에 따라 순위는 크게 달라질 수 있다" in full_text, True)

# ---- 8. no internal jargon / no bubble point-rank numbers invented ----
INTERNAL_TERMS = [
    "Monte Carlo", "monte carlo", "Plackett", "Gumbel", "τ", "tau",
    "gameCode", "viewBox", "GROUP A", "GROUP B", "GROUP C", "GROUP D",
    "RULE_CONFIRMED", "OFFICIAL_ENTRY_CONFIRMED", "evidence_level", "final_2027_group",
    "JSON", "payout curve", "UNRECONCILED", "CONFIRMED_VALUE", "BLANK_UNRESOLVED",
    "OBSERVED_FULL_FIELD_COMPUTED", "NOT_APPLICABLE",
]
for term in INTERNAL_TERMS:
    check(f'internal term "{term}" absent', term in raw_html, False)

print()
if failures:
    print(f"RESULT: FAIL ({len(failures)} failing checks)")
    for f in failures:
        print(" -", f)
    sys.exit(1)
else:
    print("RESULT: ALL CHECKS PASS")
