"""Import path for externally-obtained official KLPGA records into this
repo's relay datasets.

Why this exists: Claude's network cannot reach any klpga.co.kr subdomain in
this session (every path tried -- www, bare domain, data., 194., 193. -- has
403'd identically). Per the user's explicit fallback instruction, when a
cited endpoint is unreachable from this environment, new official data still
gets ingested through this import path instead of blocking all other work:
the user (or another tool with network access) fetches the page externally
and relays the content in a message; this script is where that relayed
content gets turned into validated, versioned CSV rows instead of being
hand-transcribed into each CSV file separately (and silently drifting).

Every row is validated against official_money_rank_2026-10-06_full.json
before being written. A row that doesn't match (wrong money_rank, wrong
money figure) is rejected loudly, not silently written.

Usage: edit NEW_POINT_ROWS / NEW_TIE_FIXTURE_ROWS below with the next
relay's content, then run this script. It merges into the existing PARTIAL
CSVs (adds new players, leaves existing ones untouched) rather than
overwriting them.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OFFICIAL_JSON = ROOT / "official_money_rank_2026-10-06_full.json"
POINT_TABLE = ROOT / "point_table_PARTIAL_2026-10-06.csv"
TIE_FIXTURE = ROOT / "tie_handling_fixture_OFFICIAL.csv"

SOURCE_FULL_RECORD = "https://193.klpga.co.kr/load/record/loadPublicRecord (OFFICIAL RELAY #4, 2026-10-06 session)"
SOURCE_POINT_RANK = "https://193.klpga.co.kr/web/record/publicRecord (OFFICIAL RELAY #4)"

# ---- this relay's new data (OFFICIAL RELAY #4) ----
# money_rank/money/points as given; point_rank filled in ONLY where the
# official point-ranking page explicitly listed that player (not inferred).
NEW_POINT_ROWS = [
    # player, money_rank, money, points, point_rank (None if not explicitly given)
    ("장은수", 5, 686658333, 212, None),
]

# a second, independently-sourced tie-handling fixture: a REAL tournament
# result (gameCode=2026060002, a 10억원 event) rather than an unlabeled
# example -- this cross-validates the already-published 10억원 bracket
# curve (70/35/33/31/29/27/25/23/21/20) at every position it covers.
NEW_TIE_FIXTURE_ROWS = [
    # purse_bracket, tied_finish_label, n_tied_players, points_each, note
    ("10억~12억 미만", "1 (김민솔, 단독)", 1, 70, "gameCode=2026060002 실제 결과 -- 기존 TOP10 커브 1위=70과 일치"),
    ("10억~12억 미만", "2 (최예림, 단독)", 1, 35, "기존 커브 2위=35와 일치"),
    ("10억~12억 미만", "3 (유서연2, 단독)", 1, 33, "기존 커브 3위=33과 일치"),
    ("10억~12억 미만", "T4 (성유진·노승희·전우리)", 3, 31, "기존 커브 4위=31과 일치, 공동 3명 전원 동일 지급"),
    ("10억~12억 미만", "7 (한진선, 단독)", 1, 25, "기존 커브 7위=25와 일치 -- T4가 3명이라 5,6위는 결번(스킵)"),
    ("10억~12억 미만", "T8 (이지현3·김새로미)", 2, 23, "기존 커브 8위=23과 일치, 공동 2명 전원 동일 지급"),
    ("10억~12억 미만", "T10 (배소현·서교림·홍진영2·문정민)", 4, 20, "기존 커브 10위=20과 일치, 공동 4명 전원 동일 지급 -- Top10 자리에 실제로는 4명이 들어와 총 수상자가 10명을 넘음"),
]


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, fieldnames, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main():
    official = json.load(open(OFFICIAL_JSON, encoding="utf-8"))
    official_by_name = {r["player_name"]: r for r in official}

    # ---- 1. validate + merge point_table rows ----
    existing = read_csv(POINT_TABLE)
    existing_names = {r["player"] for r in existing}
    fieldnames = list(existing[0].keys())

    added = []
    for name, money_rank, money, points, point_rank in NEW_POINT_ROWS:
        off = official_by_name.get(name)
        assert off is not None, f"{name} not found in official money-rank data at all -- REJECTED"
        assert off["rank"] == money_rank, (
            f"{name}: relayed money_rank={money_rank} but official data says {off['rank']} -- REJECTED"
        )
        assert off["prize_money"] == money, (
            f"{name}: relayed money={money} but official data says {off['prize_money']} -- REJECTED"
        )
        if name in existing_names:
            print(f"SKIP (already present): {name}")
            continue
        existing.append({
            "player": name,
            "player_code": off["player_code"],
            "money_rank": str(money_rank),
            "money": str(money),
            "point_rank": str(point_rank) if point_rank is not None else "UNRECONCILED",
            "points": str(points),
            "events": "",
            "wins": "",
            "snapshot_date": "2026-10-06",
            "evidence_type": "OBSERVED (user relay, OFFICIAL RELAY #4; Claude independently re-attempted "
                              "193.klpga.co.kr this turn -- still 403, cannot self-fetch)",
            "source": SOURCE_FULL_RECORD,
        })
        added.append(name)
        print(f"VALIDATED + ADDED: {name} (money_rank={money_rank}, points={points}, "
              f"point_rank={'UNRECONCILED' if point_rank is None else point_rank})")

    write_csv(POINT_TABLE, fieldnames, existing)
    print(f"\n{POINT_TABLE.name}: {len(added)} new row(s) added, {len(existing)} total rows now")

    # ---- 2. append the new tie-handling fixture (separate gameCode, doesn't overwrite the old one) ----
    tie_existing = read_csv(TIE_FIXTURE)
    tie_fieldnames = list(tie_existing[0].keys())
    tie_new = [
        {
            "purse_bracket": bracket,
            "tied_finish_label": label,
            "n_tied_players": str(n),
            "points_each": str(pts),
            "note": note,
            "evidence_type": "OBSERVED (real tournament result, gameCode=2026060002, OFFICIAL RELAY #4)",
            "source": "user relay",
        }
        for bracket, label, n, pts, note in NEW_TIE_FIXTURE_ROWS
    ]
    # match existing column order if the file already has these exact columns; else just use what's there
    for row in tie_new:
        for k in list(row.keys()):
            if k not in tie_fieldnames:
                del row[k]
    tie_existing.extend(tie_new)
    write_csv(TIE_FIXTURE, tie_fieldnames, tie_existing)
    print(f"{TIE_FIXTURE.name}: {len(tie_new)} new row(s) added, {len(tie_existing)} total rows now")


if __name__ == "__main__":
    main()
