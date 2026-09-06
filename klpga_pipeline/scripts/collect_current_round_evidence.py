"""Collect fresh official facts and scorecards for a manually reviewed update.

Does not modify schedules, historical snapshots, models, or production pages.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bs4 import BeautifulSoup
from klpga import config
from klpga.http_client import PoliteHttpClient
from klpga.collectors.leaderboard import fetch_round_leaderboard_html
from klpga.collectors.group_page import fetch_group_page_html
from klpga.parsers.group_page_parser import parse_round_grouping
from klpga.parsers.leaderboard_parser import parse_round_leaderboard_html
from klpga.website_v2.official_data import parse_player_holes, parse_sg_html, validate_sg_record


def expected_completed_holes(through, raw_hole, starting_tee):
    """Cross-check only: published count comes from recorded scorecard holes.

    Live 2026-09-06 evidence: 14H / OUT has 13 recorded scores; F* / IN
    has 18 recorded scores and raw hole 9. Historical resolver semantics
    are intentionally not changed by this manual collection command.
    """
    if through in ("F", "F*"):
        return 18
    hole, tee = int(raw_hole), int(starting_tee)
    if not 1 <= hole <= 18 or tee not in (1, 10):
        raise ValueError("unverified current hole or starting tee")
    if through.rstrip("*") != f"{hole}H":
        raise ValueError("official visible progress disagrees with raw hole")
    return (hole - tee) % 18


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game-code", required=True)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    client = PoliteHttpClient(cache_dir=out / "cache")

    def save(name, payload):
        (out / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    event_list = client.post_json(config.GAME_LIST_ENDPOINT, data={"season": args.game_code[:4], "tourType": "RE", "year": ""}, use_cache=False)
    event = next(x for x in event_list["gameList"] if x["gameCode"] == args.game_code)
    assert event["gameMethod"] == "0" and 1 <= args.round <= event["totalRound"]
    save("tournament.json", event)
    status, group_html = fetch_group_page_html(client, args.game_code)
    assert status == 200
    (out / "group-official.html").write_text(group_html, encoding="utf-8")
    groups = parse_round_grouping(group_html, args.round)
    group_by = {str(x.player_code): x for x in groups}
    # Resume already archived cards, but revalidate every one against a fresh
    # leaderboard and refresh any card whose facts no longer match.
    cards = json.loads((out / "scorecards.json").read_text(encoding="utf-8")) if (out / "scorecards.json").exists() else {}
    for attempt in range(5):
        html = fetch_round_leaderboard_html(client, args.game_code, args.round, use_cache=False)
        at = datetime.now(timezone.utc).isoformat()
        (out / f"leaderboard-{attempt}.html").write_text(html, encoding="utf-8")
        rows = parse_round_leaderboard_html(html, game_code=args.game_code, round_number=args.round)
        soup = BeautifulSoup(html, "html.parser")
        buttons = {b.get("_playercode"): b for b in soup.select("[id=btnDetail]")}
        assert rows and len(rows) == len({r.player_code for r in rows})
        mismatches = []
        for index, row in enumerate(rows):
            pid = str(row.player_code)
            assert pid in group_by and group_by[pid].starting_tee in ("1", "10")
            assert row.status is None, f"unresolved official status: {pid} {row.status}"
            b = buttons[pid]
            visible = [td.get_text(" ", strip=True) for td in b.find("table").find_all("td")]
            through = visible[6]
            # data-inghole is the course hole currently in progress. F is
            # separate official evidence of completion, including IN starters.
            tee = int(group_by[pid].starting_tee)
            expected_count = expected_completed_holes(through, row.holes_completed, tee)
            today = 0 if row.today_under_par_display == "E" else int(row.today_under_par_display)
            total = 0 if row.total_under_par_display == "E" else int(row.total_under_par_display)

            def matches(card):
                current = [x for x in card if x["round"] == args.round]
                return (len(current) == expected_count
                        and sum(x["relative_to_par"] for x in current) == today
                        and sum(x["relative_to_par"] for x in card) == total
                        and sum(x["strokes"] for x in card) == row.total_strokes)

            if pid not in cards or not matches(cards[pid]):
                params = {k: b.get("_" + k.lower(), "") for k in ("gameCode", "playerCode", "playerName", "playerEngName", "groupNo", "playerImg", "round", "hole", "level", "ballModelText")}
                card_html = client.post_text("https://klpga.co.kr/load/leaderboard/playerDetail", data=params, use_cache=False)
                (out / f"card-{pid}.html").write_text(card_html, encoding="utf-8")
                cards[pid] = parse_player_holes(card_html, player=row.player_name, player_id=pid)
            if not matches(cards[pid]):
                mismatches.append(pid)
            if index % 10 == 0:
                print(f"attempt={attempt} checked={index+1}/{len(rows)} mismatches={len(mismatches)}", flush=True)
        save("scorecards.json", cards)
        if mismatches:
            print(f"Refreshing moving official snapshot: {mismatches}", flush=True)
            continue
        # Re-fetch after the full card sweep; catch changes during collection.
        latest = fetch_round_leaderboard_html(client, args.game_code, args.round, use_cache=False)
        latest_rows = parse_round_leaderboard_html(latest, game_code=args.game_code, round_number=args.round)
        if [asdict(x) for x in latest_rows] != [asdict(x) for x in rows]:
            print("Leaderboard advanced during verification; reconciling again", flush=True)
            continue
        break
    else:
        raise RuntimeError("official leaderboard and scorecards did not converge; no publication")

    sg_html = client.post_text("https://klpga.co.kr/load/leaderboard/strokesGained_detail", data={"gameCode": args.game_code, "round": str(args.round)}, use_cache=False)
    sg_at = datetime.now(timezone.utc).isoformat()
    (out / "sg-official.html").write_text(sg_html, encoding="utf-8")
    sg = parse_sg_html(sg_html, scope="single_round", round_number=args.round)
    names = {r.player_name: r.player_code for r in rows}
    assert len(names) == len(rows), "SG name-only join is ambiguous"
    for record in sg:
        assert record["player"] in names
        record["player_id"] = names[record["player"]]
        record["validation"] = validate_sg_record(record)
        assert record["validation"]["total_within_tolerance"] and record["validation"]["t2g_within_tolerance"]
    save("sg.json", {"retrieved_at": sg_at, "records": sg})
    data = []
    for row in rows:
        card = [x for x in cards[row.player_code] if x["round"] == args.round]
        tee = int(group_by[row.player_code].starting_tee)
        order = [(tee - 1 + i) % 18 + 1 for i in range(len(card))]
        assert {x["hole"] for x in card} == set(order), "non-contiguous completed holes"
        data.append({**asdict(row), "starting_tee": tee, "raw_inghole": row.holes_completed,
                     "holes_completed": len(card), "progress_display": "F" if len(card) == 18 else f"{row.holes_completed}H",
                     "rank_display": buttons[row.player_code].find("table").find_all("td")[1].get_text(strip=True)})
    save("validated-current.json", {"game_code": args.game_code, "round": args.round,
         "stage": "FINAL_LIVE" if args.round == event["totalRound"] else f"R{args.round}_LIVE",
         "collected_at": at, "official_updated_at": None, "row_count": len(data),
         "completion_source": "official scorecard numeric hole scores; starting-tee sequence verified",
         "player_table": data, "sg_retrieved_at": sg_at, "sg": sg})
    print(json.dumps({"validated": len(data), "at": at, "leader": data[0], "sg": len(sg)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
