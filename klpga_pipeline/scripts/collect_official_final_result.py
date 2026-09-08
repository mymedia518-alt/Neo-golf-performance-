"""Collect one completed tournament's official final leaderboard.

This is the missing bridge between the official KLPGA website and the
two-event validation pipeline.  It fetches the confirmed KLPGA
roundLeaderboard HTML for the final round, preserves that raw response,
parses it with the project's existing parser, and writes a scoreable final
result plus a source-audit manifest.

Safety rules:
* --live is mandatory; without it no network request is made.
* No news article, live snapshot, screen capture, or forecast is accepted
  as a final result.
* The result is not written unless the response contains player rows and
  exactly one numeric rank-1 row.
* Existing result artifacts are preserved unless --overwrite is explicit.

Example:
    python scripts/collect_official_final_result.py ^
      --repo-root . ^
      --game-code 2026120001 ^
      --final-round 3 ^
      --result-path klpga_pipeline/content/website_v2/OK_OPEN_2026_FINAL_RESULT.json ^
      --source-audit-path klpga_pipeline/content/website_v2/OK_OPEN_2026_FINAL_RESULT_SOURCE_AUDIT.json ^
      --raw-dir outputs/official_final_results ^
      --live
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT / "src"))

from klpga import config  # noqa: E402
from klpga.collectors.leaderboard import fetch_round_leaderboard_html  # noqa: E402
from klpga.http_client import PoliteHttpClient  # noqa: E402
from klpga.parsers.leaderboard_parser import parse_round_leaderboard_html  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(text, encoding="utf-8")
    os.replace(temp_path, path)


def repo_relative(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def row_to_record(row: Any) -> dict[str, Any]:
    """Keep the parser's confirmed fields; never infer missing values."""
    values = asdict(row)
    return {
        "player_id": values.get("player_code"),
        "player_code": values.get("player_code"),
        "player_name": values.get("player_name"),
        "player_eng_name": values.get("player_eng_name"),
        "rank_display": values.get("rank_display"),
        "rank_numeric": values.get("rank"),
        "rank": values.get("rank"),
        "tie_flag": values.get("tie_flag"),
        "status": values.get("status"),
        "total_under_par_display": values.get("total_under_par_display"),
        "total_under_par": values.get("total_under_par"),
        "today_under_par_display": values.get("today_under_par_display"),
        "today_under_par": values.get("today_under_par"),
        "total_strokes": values.get("total_strokes"),
        "holes_completed": values.get("holes_completed"),
        "round1_score": values.get("round1_score"),
        "round2_score": values.get("round2_score"),
        "round3_score": values.get("round3_score"),
        "round4_score": values.get("round4_score"),
        "round_number": values.get("round_number"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--final-round", type=int, required=True)
    parser.add_argument("--result-path", required=True)
    parser.add_argument("--source-audit-path", required=True)
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    result_path = (repo_root / args.result_path).resolve()
    source_audit_path = (repo_root / args.source_audit_path).resolve()
    raw_dir = (repo_root / args.raw_dir).resolve() / str(args.game_code)
    raw_path = raw_dir / f"round{args.final_round}.html"
    cache_dir = Path(args.cache_dir).resolve() if args.cache_dir else repo_root / "data" / "raw_cache" / "http"

    if args.final_round < 1 or args.final_round > 4:
        print("HARD_STOP: --final-round must be between 1 and 4")
        return 2
    if not args.overwrite and (result_path.exists() or source_audit_path.exists()):
        print("HARD_STOP: official result or source audit already exists")
        print(f"RESULT: {result_path}")
        print(f"SOURCE AUDIT: {source_audit_path}")
        print("Use --overwrite only after reviewing the existing frozen artifact.")
        return 3

    client = PoliteHttpClient(cache_dir=cache_dir)
    endpoint = getattr(config, "ROUND_LEADERBOARD_ENDPOINT", "https://klpga.co.kr/load/leaderboard/roundLeaderboard")

    print("=== KLPGA OFFICIAL FINAL RESULT COLLECTOR ===")
    print(f"GAME CODE: {args.game_code}")
    print(f"FINAL ROUND: {args.final_round}")
    print(f"ENDPOINT: {endpoint}")
    print("LIVE REQUEST: YES")

    try:
        html = fetch_round_leaderboard_html(
            client,
            str(args.game_code),
            args.final_round,
            use_cache=False,
        )
    except Exception as exc:  # pragma: no cover - depends on live network
        print(f"HARD_STOP: official KLPGA request failed: {exc!r}")
        return 4

    raw_bytes = html.encode("utf-8")
    raw_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(raw_path, html)
    raw_sha256 = sha256_bytes(raw_bytes)

    try:
        rows = parse_round_leaderboard_html(
            html,
            game_code=str(args.game_code),
            round_number=args.final_round,
        )
    except Exception as exc:
        print(f"HARD_STOP: official response parse failed: {exc!r}")
        print(f"RAW RESPONSE PRESERVED: {raw_path}")
        return 5

    records = [row_to_record(row) for row in rows]
    player_codes = [str(row["player_code"]) for row in records if row.get("player_code") is not None]
    duplicates = sorted({code for code in player_codes if player_codes.count(code) > 1})
    rank1 = [row for row in records if row.get("rank_numeric") == 1]
    if not records:
        print("HARD_STOP: official final response contained no player rows")
        print(f"RAW RESPONSE PRESERVED: {raw_path}")
        return 6
    if not player_codes or len(player_codes) != len(set(player_codes)):
        print(f"HARD_STOP: player identity key problem; duplicates={duplicates}")
        print(f"RAW RESPONSE PRESERVED: {raw_path}")
        return 7
    if len(rank1) != 1:
        print(f"HARD_STOP: expected exactly one numeric rank-1 row, found {len(rank1)}")
        print(f"RAW RESPONSE PRESERVED: {raw_path}")
        return 8

    retrieved_at = utc_now()
    result_payload = {
        "schema_version": "neo_official_final_result_v1",
        "artifact": "OFFICIAL_FINAL_RESULT",
        "game_code": str(args.game_code),
        "stage": "FINAL_OFFICIAL",
        "final_round": args.final_round,
        "format_holes": args.final_round * 18,
        "source_type": "KLPGA_OFFICIAL_ROUND_LEADERBOARD",
        "official_source_host": "klpga.co.kr",
        "retrieved_at_utc": retrieved_at,
        "future_data_excluded": True,
        "records": records,
    }
    result_text = json.dumps(result_payload, ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(result_path, result_text)

    audit_payload = {
        "schema_version": "neo_official_source_audit_v1",
        "artifact": "OFFICIAL_FINAL_RESULT_SOURCE_AUDIT",
        "game_code": str(args.game_code),
        "source_type": "KLPGA_OFFICIAL_ROUND_LEADERBOARD",
        "public_page_url": f"https://klpga.co.kr/web/leaderboard/leaderboard?gameCode={args.game_code}&scorecard=Y",
        "endpoint": endpoint,
        "request": {
            "method": "POST",
            "form": {"gameCode": str(args.game_code), "round": str(args.final_round)},
            "cache_used": False,
        },
        "retrieved_at_utc": retrieved_at,
        "raw_response_path": repo_relative(raw_path, repo_root),
        "raw_response_sha256": raw_sha256,
        "result_path": repo_relative(result_path, repo_root),
        "result_sha256": sha256_file(result_path),
        "final_round": args.final_round,
        "row_count": len(records),
        "rank1_count": len(rank1),
        "player_code_unique": len(player_codes) == len(set(player_codes)),
        "official_final_confirmed": True,
        "not_from": [
            "news_article",
            "live_snapshot",
            "manual_screen_capture",
            "forecast_artifact",
        ],
    }
    atomic_write_text(
        source_audit_path,
        json.dumps(audit_payload, ensure_ascii=False, indent=2) + "\n",
    )

    winner = rank1[0]
    print(f"OFFICIAL ROWS: {len(records)}")
    print(f"WINNER: {winner.get('player_name')} ({winner.get('player_code')})")
    print(f"RAW RESPONSE: {raw_path}")
    print(f"RESULT JSON: {result_path}")
    print(f"SOURCE AUDIT: {source_audit_path}")
    print("OFFICIAL FINAL RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
