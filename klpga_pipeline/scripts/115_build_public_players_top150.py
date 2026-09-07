"""Build PUBLIC_PLAYERS_TOP150.json -- NEO SITE V5 simplification (2026-09-07
correction): the public standing players board is now defined ONLY by
current official K-Ranking position, ranks 1-150. This SUPERSEDES the
evidence-based ACTIVE_KLPGA_TOUR_PLAYER_MASTER approach (scripts/110,
now removed) -- that approach required per-player qualification/
membership evidence that could only ever be partially collected in this
sandbox; the simplified rule needs only an official K-Rank snapshot.

Two real, already-collected official K-Rank snapshots exist, both dated
the same ranking week (2026-W35, both sourced from
https://k-rankings.klpga.co.kr/allplayer.jsp):
  - HOME_PLAYER_MASTER_TOP120.json: a clean, contiguous, official Top120
    snapshot (ranks 1-120, all 120 present).
  - OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json: per-entrant K-Rank lookups
    for the 120 OK Open 2026 entrants specifically (whatever rank each
    of them happens to hold, from 1 to 667) -- of these, 14 happen to
    fall in the 121-150 range this script also needs.

Combined, these give REAL, verified coverage for 134 of the 150 target
positions (120 + 14). The remaining 16 rank positions (121-150 minus the
14 confirmed) are NOT filled with a guess or a placeholder row -- they
are recorded explicitly as missing_rank_positions, and
collection_status honestly reports the gap. This is the same honesty
policy as every other artifact in this project: never fabricate what
was not actually collected.

Player names for the 14 extra records (which carry official_rank but no
name field in their source) are resolved via HOME_REGULAR_TOUR_PLAYER_
MASTER.json's canonical player_id -> player_name map -- the same
canonical identity source scripts/112 already uses, never a guess.

official_sponsor is attached from OK_OPEN_2026_CURRENT_PLAYER_MASTER.json
(current_official_sponsor, itself sourced from official KLPGA profile
pages) wherever a Top150 player happens to also be an OK Open 2026
entrant; every other Top150 player's sponsor is left None (never
invented) -- KLPGA profile sponsor evidence for the ~30 non-OK-Open
players among the Top150 has not been collected in this sandbox.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

TOP120_PATH = CONTENT / "HOME_PLAYER_MASTER_TOP120.json"
OK_OPEN_RANKING_PATH = CONTENT / "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json"
HOME_MASTER_PATH = CONTENT / "HOME_REGULAR_TOUR_PLAYER_MASTER.json"
OK_OPEN_CURRENT_MASTER_PATH = CONTENT / "OK_OPEN_2026_CURRENT_PLAYER_MASTER.json"
OUT_PATH = CONTENT / "PUBLIC_PLAYERS_TOP150.json"

TARGET_RANK_MIN = 1
TARGET_RANK_MAX = 150
ALLPLAYER_URL = "https://k-rankings.klpga.co.kr/allplayer.jsp"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _attempt_live_fetch_for_missing_positions(missing: list[int]) -> tuple[dict[int, dict], str | None]:
    """Real attempt to close the 121-150 gap against the live official
    source, per the explicit "확보할 수 없으면 추정하지 말고 BLOCKED로
    남긴다" instruction: try first, never estimate. Returns (filled,
    error) -- filled is always {} unless the live fetch genuinely
    succeeds and yields parseable rank rows; error is the real
    exception string on failure, never swallowed silently."""
    if not missing:
        return {}, None
    try:
        import requests
        r = requests.get(ALLPLAYER_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001 -- report the real network failure, never mask it
        return {}, f"{type(exc).__name__}: {exc}"
    # A real response was received but this script does not yet parse
    # allplayer.jsp's markup (no successful fetch has occurred in this
    # sandbox to develop the parser against) -- returning no rows here
    # is itself honest: never guess a parse of an untested response.
    return {}, "LIVE_RESPONSE_RECEIVED_BUT_NOT_YET_PARSEABLE"


def build() -> dict:
    top120 = json.loads(TOP120_PATH.read_text(encoding="utf-8"))
    ok_rank = json.loads(OK_OPEN_RANKING_PATH.read_text(encoding="utf-8"))
    home_master = json.loads(HOME_MASTER_PATH.read_text(encoding="utf-8"))
    ok_current_master = (
        json.loads(OK_OPEN_CURRENT_MASTER_PATH.read_text(encoding="utf-8"))
        if OK_OPEN_CURRENT_MASTER_PATH.is_file() else {"records": []}
    )

    canonical_name_by_id = {str(r["player_id"]): r["player_name"] for r in home_master["records"]}
    sponsor_by_id = {
        str(r["player_id"]): r["current_official_sponsor"]
        for r in ok_current_master.get("records", ())
        if r.get("current_official_sponsor")
    }

    by_rank: dict[int, dict] = {}

    for r in top120["records"]:
        rank = r["official_k_rank"]
        by_rank[rank] = {
            "rank": rank,
            "player_id": str(r["player_id"]),
            "player_name": r["player_name"],
            "official_sponsor": sponsor_by_id.get(str(r["player_id"])),
            "k_rank_source": {
                "artifact": "HOME_PLAYER_MASTER_TOP120.json",
                "official_source": top120.get("official_source"),
                "ranking_week": top120.get("ranking_week"),
                "retrieved_at": r.get("retrieved_at"),
            },
        }

    for r in ok_rank["records"]:
        rank = r.get("official_rank")
        if rank is None or not (TARGET_RANK_MIN <= rank <= TARGET_RANK_MAX) or rank in by_rank:
            continue
        pid = str(r["player_id"])
        name = canonical_name_by_id.get(pid)
        if not name:
            continue  # never guess a name for an unresolved identity
        by_rank[rank] = {
            "rank": rank,
            "player_id": pid,
            "player_name": name,
            "official_sponsor": sponsor_by_id.get(pid),
            "k_rank_source": {
                "artifact": "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json",
                "official_source": ok_rank.get("official_source"),
                "ranking_week": ok_rank.get("ranking_date"),
                "retrieved_at": ok_rank.get("retrieved_at"),
            },
        }

    confirmed_ranks = sorted(by_rank)
    missing_ranks = [rank for rank in range(TARGET_RANK_MIN, TARGET_RANK_MAX + 1) if rank not in by_rank]
    filled, live_fetch_error = _attempt_live_fetch_for_missing_positions(missing_ranks)
    for rank, record in filled.items():
        by_rank[rank] = record
    confirmed_ranks = sorted(by_rank)
    blocked_positions = [
        {
            "rank": rank,
            "status": "BLOCKED",
            "reason": "no live KLPGA network access in this sandbox -- never estimated",
            "live_fetch_error": live_fetch_error,
        }
        for rank in range(TARGET_RANK_MIN, TARGET_RANK_MAX + 1) if rank not in by_rank
    ]
    players = [by_rank[rank] for rank in confirmed_ranks]

    doc = {
        "schema_version": "neo_public_players_top150_v1",
        "population_kind": "public_klpga_kranking_top150",
        "population_definition": (
            "최신 공식 K-Ranking 1~150위. 대회 출전 여부와 무관 -- 546명 "
            "역사 마스터(HOME_REGULAR_TOUR_PLAYER_MASTER.json)나 개별 "
            "자격/시드 증거가 아니라 공식 K-Ranking 순위 하나만을 기준으로 한다."
        ),
        "distinct_from": (
            "HOME_REGULAR_TOUR_PLAYER_MASTER.json (546명, 역사 데이터, 내부 전용, "
            "공개 판별에 사용하지 않음). 대회 Entry List와도 무관 -- 대회 페이지는 "
            "이 Top150과 별개로 공식 Entry List 전원을 표시한다."
        ),
        "target_rank_range": [TARGET_RANK_MIN, TARGET_RANK_MAX],
        "ranking_week": top120.get("ranking_week"),
        "sources": [
            {"artifact": "HOME_PLAYER_MASTER_TOP120.json", "coverage": "ranks 1-120, complete"},
            {"artifact": "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json", "coverage": "ranks 121-150, partial (only OK Open 2026 entrants ranked in this band)"},
        ],
        "confirmed_rank_count": len(confirmed_ranks),
        "missing_rank_positions": [b["rank"] for b in blocked_positions],
        "blocked_positions": blocked_positions,
        "collection_status": (
            "COMPLETE" if not blocked_positions else
            "PARTIAL_121_150_BLOCKED_NO_LIVE_KLPGA_NETWORK_ACCESS"
        ),
        "generated_at": now(),
        "players": players,
    }
    doc["artifact_hash"] = hashlib.sha256(
        json.dumps(players, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "confirmed_rank_count": doc["confirmed_rank_count"],
        "blocked_count": len(blocked_positions),
        "collection_status": doc["collection_status"],
    }, ensure_ascii=False))
    return doc


if __name__ == "__main__":
    build()
