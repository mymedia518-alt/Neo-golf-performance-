"""Historical SG recovery (manual, one-off): re-collect a single completed
stroke-play tournament's official cumulative + round-by-round Strokes
Gained tables directly from klpga.co.kr, for independent verification
against what the official page already displays -- never estimated,
never converted from raw strokes.

Reuses, verbatim, the same official endpoints/params/parsers
scripts/63_collect_historical_sg_warehouse.py's collect_by_game_code()
already uses: BASE/SG_PATH/LB_PATH, parse_leaderboard_html, parse_sg_html,
validate_sg_record, standardize_player_name. The only additions this
task needs that script 63 does not already provide:
  - PoliteHttpClient (rate-limited) instead of script 63's raw
    requests.post, so a one-off historical recovery run never hammers
    the live official site.
  - Explicit raw-response preservation (URL, params, retrieved_at,
    sha256) for independent audit -- script 63 parses and discards the
    HTML immediately.
  - A cumulative-vs-sum-of-rounds consistency check across BOTH scopes
    together -- neither script 63 nor official_data.py ever assembled
    both scopes for the same player in one place before.

Writes ONLY to the caller-supplied --output directory. Never touches
historical_sg_warehouse.json, content/website_v2/knowledge_engine/, or
any published page.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.http_client import PoliteHttpClient  # noqa: E402
from klpga.website_v2.official_data import (  # noqa: E402
    parse_leaderboard_html,
    parse_sg_html,
    validate_sg_record,
)
from klpga.analytics.sg_performance import standardize_player_name, validate_sg_records  # noqa: E402

BASE = "https://klpga.co.kr"
SG_PATH = "/load/leaderboard/strokesGained_detail"
LB_PATH = "/load/leaderboard/roundLeaderboard"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game-code", required=True)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--tournament", required=True)
    ap.add_argument("--end-date", required=True, help="YYYY-MM-DD official end date, from TOURNAMENT_INFO/official schedule -- never inferred from game_code order")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    code = args.game_code
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    client = PoliteHttpClient(cache_dir=out / "http_cache")

    manifest: dict = {
        "game_code": code,
        "season": args.season,
        "tournament": args.tournament,
        "official_end_date": args.end_date,
        "official_sg_page": f"{BASE}/web/leaderboard/strokesGained?gameCode={code}",
        "collection_started_at": datetime.now(timezone.utc).isoformat(),
        "requests": [],
    }

    def fetch(path: str, data: dict, label: str) -> str:
        url = BASE + path
        retrieved_at = datetime.now(timezone.utc).isoformat()
        text = client.post_text(url, data=data, use_cache=False)
        digest = sha256(text)
        raw_name = f"{label}.html"
        (raw_dir / raw_name).write_text(text, encoding="utf-8")
        manifest["requests"].append({
            "label": label, "url": url, "params": data,
            "retrieved_at": retrieved_at, "sha256": digest,
            "bytes": len(text.encode("utf-8")), "saved_as": f"raw/{raw_name}",
        })
        return text

    round_ids: dict[int, dict[str, str]] = {}
    latest_round = 0
    for rnd in (4, 3, 2, 1):
        html = fetch(LB_PATH, {"gameCode": code, "round": str(rnd)}, f"roundLeaderboard_r{rnd}")
        rows = parse_leaderboard_html(html)
        if rows:
            round_ids[rnd] = {str(r.get("player")): str(r.get("player_id")) for r in rows if r.get("player_id")}
            if not latest_round:
                latest_round = rnd

    if not latest_round:
        manifest["status"] = "error"
        manifest["error"] = "roundLeaderboard returned no rows for rounds 4..1"
        (out / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("FAILED: no leaderboard rows at all")
        sys.exit(1)

    name_to_id_any_round = {name: pid for mapping in round_ids.values() for name, pid in mapping.items()}

    all_rows: list[dict] = []
    per_scope_counts: dict[str, int] = {}
    for rnd in (None, *range(1, latest_round + 1)):
        label = "sg_cumulative" if rnd is None else f"sg_r{rnd}"
        html = fetch(SG_PATH, {"gameCode": code, "round": "" if rnd is None else str(rnd)}, label)
        scope = "tournament_cumulative" if rnd is None else "single_round"
        parsed = parse_sg_html(html, scope=scope, round_number=rnd)
        per_scope_counts[label] = len(parsed)
        lookup = name_to_id_any_round if rnd is None else round_ids.get(rnd, {})
        for row in parsed:
            pid = lookup.get(str(row.get("player")))
            row.update({
                "player_id": pid,
                "identity_state": "RETAINED" if pid else "UNRESOLVED_IDENTITY",
                "season": args.season, "game_code": code, "tournament": args.tournament,
                "date": args.end_date,
                "source": f"{BASE}{SG_PATH} POST gameCode={code}, round={'blank' if rnd is None else rnd}",
                "retrieved_at": manifest["requests"][-1]["retrieved_at"],
                "validation": validate_sg_record(row),
            })
            row.update(standardize_player_name(row.get("player"), pid))
            all_rows.append(row)

    batch_validation = validate_sg_records(all_rows)

    by_player_cumulative = {r["player_id"]: r for r in all_rows if r["scope"] == "tournament_cumulative" and r["player_id"]}
    by_player_rounds: dict[str, list[dict]] = {}
    for r in all_rows:
        if r["scope"] == "single_round" and r["player_id"]:
            by_player_rounds.setdefault(r["player_id"], []).append(r)

    cumulative_consistency = []
    for pid, cum in by_player_cumulative.items():
        rounds = by_player_rounds.get(pid, [])
        rounds_sum = sum(float(r["total"]) for r in rounds)
        delta = round(float(cum["total"]) - rounds_sum, 3)
        cumulative_consistency.append({
            "player_id": pid, "player": cum.get("player"),
            "rounds_collected": len(rounds), "rounds_expected": cum.get("rounds"),
            "cumulative_total": cum["total"], "sum_of_round_totals": round(rounds_sum, 3),
            "delta": delta, "within_tolerance": abs(delta) <= 0.1,
            "round_count_matches": len(rounds) == cum.get("rounds"),
        })

    missing_rounds = [c for c in cumulative_consistency if not c["round_count_matches"]]
    inconsistent = [c for c in cumulative_consistency if not c["within_tolerance"]]

    manifest["status"] = "success"
    manifest["latest_round_detected"] = latest_round
    manifest["per_scope_row_counts"] = per_scope_counts
    manifest["total_rows"] = len(all_rows)
    manifest["batch_validation"] = batch_validation
    manifest["cumulative_vs_rounds_check"] = {
        "players_checked": len(cumulative_consistency),
        "players_missing_rounds": len(missing_rounds),
        "players_inconsistent_total": len(inconsistent),
        "missing_rounds_detail": missing_rounds,
        "inconsistent_detail": inconsistent,
    }
    manifest["collection_finished_at"] = datetime.now(timezone.utc).isoformat()

    (out / "RECORDS.json").write_text(json.dumps(all_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"status=success game_code={code} latest_round={latest_round} rows={len(all_rows)} "
        f"missing_rounds={len(missing_rounds)} inconsistent={len(inconsistent)} "
        f"dup={batch_validation['duplicate_count']} missing_identity={batch_validation['missing_identity']}"
    )


if __name__ == "__main__":
    main()
