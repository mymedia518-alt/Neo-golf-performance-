"""Build ACTIVE_KLPGA_TOUR_PLAYER_MASTER.json -- the current-season active
KLPGA regular-tour player universe, kept strictly separate from
HOME_REGULAR_TOUR_PLAYER_MASTER.json (546 players: everyone observed in
the trailing-100-event historical warehouse, spanning multiple seasons,
with no per-player current-status evidence at all -- confirmed by that
file's own hardcoded population_validation_state:
"BLOCKED_CURRENT_REGISTRY_EQUIVALENCE_NOT_PROVEN").

WHY NOT K-RANK TOP 150: K-Rank is a cumulative-points ranking. A player
can rank inside the top 150 by points while no longer holding a current
KLPGA regular-tour card (e.g. she has since left the tour), and a
current card-holder can rank outside the top 150. Truncating by K-Rank
would silently misclassify both directions. (Note for the record: this
repository's existing production top-120 population, built by
scripts/94_promote_top120_to_production.py + scripts/87/88, already
IS a K-Rank truncation -- exactly this anti-pattern -- but that is a
separate, existing pipeline this script does not touch or fix; this
script exists so PLAYERS can stop repeating it.)

THE ONLY REAL PER-PLAYER MEMBERSHIP EVIDENCE CONFIRMED IN THIS REPO:
the KLPGA official player-profile page (https://klpga.co.kr/web/profile/
mainRecord?playerCode=<id>) carries a "등급" (grade/membership) label --
scripts/72_collect_ok_open_public_master.py's collect_profiles() already
fetches this, one player at a time, for the 120 players in one
tournament's entry list (see OK_OPEN_2026_CURRENT_PLAYER_MASTER.json).
Observed values there: "정회원" (regular member) 116/120, "I-Tour 회원"
2/120, "실기평가 대상자" (skills-evaluation candidate) 2/120. Only
"정회원" is treated as confirmed current regular-tour membership here --
"I-Tour 회원" is a distinct (non-regular-tour) membership track and
"실기평가 대상자" is explicitly not-yet-a-member. This mapping
(ACTIVE_REGULAR_TOUR_STATUS_VALUES below) is the ONLY classification
rule this script applies; it is not a guess -- it is what "정회원"
literally means on KLPGA's own site. No bulk seed-list/roster endpoint
is confirmed anywhere in this repo (see NEO SITE V5 Mission 2 research
notes) -- membership must be checked one player at a time via this
profile endpoint.

HONESTY CONTRACT: this script never fabricates a status. Every
candidate (drawn from HOME_REGULAR_TOUR_PLAYER_MASTER.json, the only
existing broad player-id pool) that has not actually had its profile
page fetched and read is left OUT of the public active-player list and
recorded separately under pending_collection, never silently defaulted
to active or inactive. Today, in this sandboxed environment, KLPGA's
site is not reachable (network egress blocked) -- so this run
necessarily produces a PARTIAL universe: every candidate id that
already has real, previously-collected evidence (currently only the
120 ids in OK_OPEN_2026_CURRENT_PLAYER_MASTER.json, collected earlier
this project against live klpga.co.kr) is classified for real; every
other candidate is left pending. Re-running this script with live
network access will fetch the remaining candidates and fill the
universe in further -- nothing here needs to change for that, only
_fetch_profile()'s live path needs to actually succeed.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

HOME_MASTER_PATH = CONTENT / "HOME_REGULAR_TOUR_PLAYER_MASTER.json"
OK_OPEN_CURRENT_MASTER_PATH = CONTENT / "OK_OPEN_2026_CURRENT_PLAYER_MASTER.json"
OK_OPEN_RANKING_PATH = CONTENT / "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json"
OUT_PATH = CONTENT / "ACTIVE_KLPGA_TOUR_PLAYER_MASTER.json"

PROFILE_URL = "https://klpga.co.kr/web/profile/mainRecord"

# The one and only classification rule -- see module docstring.
ACTIVE_REGULAR_TOUR_STATUS_VALUES = {"정회원"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _label_value(soup: BeautifulSoup, label_text: str) -> str | None:
    lab = soup.find("label", string=lambda x: x and x.strip() == label_text)
    if lab is None:
        return None
    parent = lab.parent
    tags = parent.find_all("h5")
    return tags[-1].get_text(" ", strip=True) if tags else ""


def _fetch_profile(session: requests.Session, player_id: str) -> dict | None:
    """Live-fetch one player's official profile page. Returns None (never
    a fabricated/guessed record) on any network or parse failure -- the
    caller must record the candidate as pending, not silently drop or
    default it."""
    try:
        r = session.get(PROFILE_URL, params={"playerCode": player_id}, timeout=30)
        r.raise_for_status()
    except requests.exceptions.RequestException:
        return None
    soup = BeautifulSoup(r.content.decode("utf-8", "replace"), "html.parser")
    search = soup.select_one("input.playerSearch")
    current_name = (search.get("playerholder") if search else None)
    if not current_name:
        current_name = (search.get("placeholder") if search else None)
    if not current_name and soup.select_one(".ph-player h3"):
        current_name = soup.select_one(".ph-player h3").get_text(" ", strip=True)
    status = _label_value(soup, "등급")
    sponsor = _label_value(soup, "소속")
    if not current_name:
        return None
    return {
        "current_official_player_name": current_name,
        "tour_status": status,
        "official_sponsor": sponsor or None,
        "official_source": f"{PROFILE_URL}?playerCode={player_id}",
        "retrieved_at": now(),
    }


def _bootstrap_from_existing_collection() -> dict[str, dict]:
    """Real, already-collected evidence from an earlier live run against
    klpga.co.kr (scripts/72), reused here instead of re-fetched -- same
    player-profile endpoint, same "등급" field, just gathered for one
    tournament's 120-entrant field rather than the full candidate pool.
    Never invented: every value here traces to a real HTTP fetch whose
    retrieved_at timestamp is preserved."""
    if not OK_OPEN_CURRENT_MASTER_PATH.is_file():
        return {}
    doc = json.loads(OK_OPEN_CURRENT_MASTER_PATH.read_text(encoding="utf-8"))
    out = {}
    for rec in doc.get("records", ()):
        pid = str(rec.get("player_id"))
        if not rec.get("current_official_player_name"):
            continue
        out[pid] = {
            "current_official_player_name": rec["current_official_player_name"],
            "tour_status": rec.get("current_player_status"),
            "official_sponsor": rec.get("current_official_sponsor"),
            "official_source": rec.get("official_source"),
            "retrieved_at": rec.get("retrieved_at"),
        }
    return out


def _load_k_rank() -> dict[str, int]:
    if not OK_OPEN_RANKING_PATH.is_file():
        return {}
    doc = json.loads(OK_OPEN_RANKING_PATH.read_text(encoding="utf-8"))
    return {
        str(x["player_id"]): x["official_rank"]
        for x in doc.get("records", ())
        if x.get("validation_state") == "PASS" and x.get("official_rank") is not None
    }


def build(*, attempt_live_fetch: bool = True, live_fetch_limit: int | None = None) -> dict:
    home_master = json.loads(HOME_MASTER_PATH.read_text(encoding="utf-8"))
    candidates = home_master["records"]
    k_rank_by_id = _load_k_rank()
    already_collected = _bootstrap_from_existing_collection()

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"})

    active_players: list[dict] = []
    non_regular_excluded: list[dict] = []
    pending_collection: list[dict] = []
    live_fetch_attempts = 0

    for cand in candidates:
        pid = str(cand["player_id"])
        evidence = already_collected.get(pid)
        if evidence is None and attempt_live_fetch and (
            live_fetch_limit is None or live_fetch_attempts < live_fetch_limit
        ):
            live_fetch_attempts += 1
            evidence = _fetch_profile(session, pid)
            time.sleep(0.15)

        if evidence is None:
            pending_collection.append({
                "player_id": pid,
                "player_name": cand["player_name"],
                "reason": "NOT_YET_PROFILE_CHECKED_AGAINST_OFFICIAL_SOURCE",
            })
            continue

        record = {
            "player_id": pid,
            "player_name": evidence["current_official_player_name"],
            "official_sponsor": evidence.get("official_sponsor") or None,
            "tour_status": evidence.get("tour_status"),
            "tour_status_source": {
                "official_source": evidence.get("official_source"),
                "retrieved_at": evidence.get("retrieved_at"),
            },
            "k_rank": k_rank_by_id.get(pid),
            # Every NEO-derived metric below is unpublished/blocked
            # site-wide pending formula approval -- never fabricated,
            # matching the same policy already enforced on HOME.
            "neo_rank": None,
            "performance_sg": None,
            "form": None,
            "volatility": None,
            "trend": None,
            "events": None,
            "data_as_of": evidence.get("retrieved_at"),
        }
        if evidence.get("tour_status") in ACTIVE_REGULAR_TOUR_STATUS_VALUES:
            active_players.append(record)
        else:
            record["exclusion_reason"] = (
                f"tour_status {evidence.get('tour_status')!r} is not in "
                f"ACTIVE_REGULAR_TOUR_STATUS_VALUES {sorted(ACTIVE_REGULAR_TOUR_STATUS_VALUES)}"
            )
            non_regular_excluded.append(record)

    active_players.sort(key=lambda r: (r["player_name"], r["player_id"]))
    payload_for_hash = {
        "active_players": active_players,
        "non_regular_excluded": non_regular_excluded,
    }
    artifact_hash = hashlib.sha256(
        json.dumps(payload_for_hash, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    doc = {
        "schema_version": "neo_active_klpga_tour_player_master_v1",
        "population_kind": "active_klpga_regular_tour_player_universe",
        "population_definition": (
            "Players from the 546-player historical master whose official "
            "KLPGA profile page (등급 label) has been confirmed to read "
            "'정회원' (regular member) as of the recorded retrieval time. "
            "NOT a K-Rank truncation. See module docstring for the full "
            "classification rule and its evidentiary basis."
        ),
        "distinct_from": "HOME_REGULAR_TOUR_PLAYER_MASTER.json (546-player historical composite, no current-status evidence)",
        "target_scope_note": "official current-season regular-tour seed/playing-right pool, approximately up to 150 players",
        "generated_at": now(),
        "candidate_pool_source": "HOME_REGULAR_TOUR_PLAYER_MASTER.json",
        "candidate_pool_size": len(candidates),
        "collection_completeness": {
            "candidates_total": len(candidates),
            "profile_checked": len(active_players) + len(non_regular_excluded),
            "active_confirmed": len(active_players),
            "non_regular_excluded": len(non_regular_excluded),
            "pending_collection": len(pending_collection),
            "status": (
                "COMPLETE" if not pending_collection else
                "PARTIAL_PENDING_LIVE_KLPGA_NETWORK_ACCESS"
            ),
        },
        "active_players": active_players,
        "non_regular_excluded": non_regular_excluded,
        "pending_collection": pending_collection,
        "artifact_hash": artifact_hash,
    }
    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(doc["collection_completeness"], ensure_ascii=False))
    return doc


if __name__ == "__main__":
    raise SystemExit(0 if build() else 1)
