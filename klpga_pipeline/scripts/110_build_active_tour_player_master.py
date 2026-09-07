"""Build ACTIVE_KLPGA_TOUR_PLAYER_MASTER.json (v2) -- the current-season
KLPGA REGULAR-TOUR PLAYING-RIGHT player universe, kept strictly separate
from both:
  A. HOME_REGULAR_TOUR_PLAYER_MASTER.json -- 546 players, the full
     historical composite, no per-player current-status evidence at all.
  C. any single tournament's official entry list (e.g.
     OK_OPEN_2026_ENTRY_SNAPSHOT.json) -- being IN a tournament's field
     is evidence that a player played THAT tournament, never itself
     evidence of season-long regular-tour playing rights (see
     TOURNAMENT_PRE_FREEZE_ARCHITECTURE notes in scripts/112 and the
     NEO SITE V5 architecture-correction brief, item 3: "Never silently
     use B as a substitute for C" -- and the converse holds too).

ARCHITECTURE CORRECTION (v2, supersedes v1): v1 treated KLPGA profile
membership status "정회원" (regular member) as the active-tour proxy.
This was WRONG -- "정회원" is a membership-track classification, not a
statement of *current-season regular-tour seed/playing-right status*.
The two are different KLPGA concepts. A player can be a 정회원 without
holding a 2026 regular-tour seed, and (per real evidence found in this
repo, see below) a player can hold real 2026 regular-tour seed/exempt
evidence while carrying a non-정회원 membership label.

THE REAL EVIDENCE THIS SCRIPT NOW USES:
KLPGA's own official entry-list disclosure for a 2026 regular-tour event
(OK_OPEN_2026_ENTRY_SNAPSHOT.json) carries two fields per entrant:
`qualification_category` and `qualification_reason`. `qualification_
category` is either "자격자" (a formal/automatic qualifying entrant --
KLPGA's own category label for "entered under a defined eligibility
rule") or a discretionary invite category ("추천자"/recommended,
"초청자"/invited -- tournament-specific wildcards, NOT season-wide
eligibility). Every real "자격자" row in the collected data carries a
non-empty `qualification_reason` naming the specific KLPGA regular-tour
exemption/seed category that earned entry -- e.g. "시드순위자" (seed-
rank holder), "2025 정규투어 상금순위 60위 이내" (retained seed via
prior-season prize-money rank), "2025 드림투어 상금순위 20위 이내"
(promoted into the regular tour via the developmental tour), tournament-
win exemptions, "영구시드권 선수" (permanent seed rights), "부상선수
시드권" (injured-player protected seed), "K-10 클럽" (career money-list
exemption). These are KLPGA's own official qualifying-category labels,
disclosed on the entry list itself -- not this project's invention, and
not a K-Rank derivation. A "자격자" row IS the authoritative evidence
this script needs: it is season-level (these are exactly the categories
KLPGA's annual seed-ranking rules define), not tournament-specific, even
though the disclosure happens to be embedded in one tournament's entry
list. By contrast, a "추천자"/"초청자" row (qualification_reason is
always empty for these, confirmed in the collected data) proves only
that she played in THIS ONE tournament -- it is not treated as season-
wide seed evidence.

CLASSIFICATION RULE (the only rule this script applies):
  ACTIVE_CONFIRMED   -- entry-list qualification_category == "자격자"
                        AND qualification_reason is not empty, AND no
                        conflicting membership-track evidence (see next).
  INACTIVE_CONFIRMED -- official KLPGA profile membership status is a
                        distinct, non-regular-tour track ("I-Tour 회원"
                        or "실기평가 대상자" -- not-yet-a-member) AND
                        there is no season-seed evidence above.
  PENDING_EVIDENCE   -- everything else: no evidence collected yet for
                        this candidate; OR she entered only via a
                        discretionary category with no disclosed season-
                        seed reason; OR the two evidence sources actively
                        conflict (see CONFLICT HANDLING) -- never
                        resolved by guessing, always left explicit.

CONFLICT HANDLING: two real candidates in the collected data show a
genuine conflict -- profile membership status "I-Tour 회원" (a distinct,
non-regular-tour track) but entry-list qualification_reason naming a
real regular-tour seed category ("시드순위자", "2026 일반대회 우승자").
Rather than silently picking one source, both are classified
PENDING_EVIDENCE with the conflict recorded verbatim on the record
(conflict_evidence field) for human review.

TARGET SCOPE: "~150" is a scope target for what the complete universe is
expected to look like once evidence collection is complete -- NOT a
truncation threshold. This script never pads toward it and never
truncates to it; it reports the actual confirmed count from actual
evidence, whatever that number is.

HONESTY CONTRACT: every candidate (drawn from HOME_REGULAR_TOUR_PLAYER_
MASTER.json, the only existing broad player-id pool) is classified
explicitly into exactly one of the three states above, with provenance.
Nothing is silently defaulted. In this sandboxed environment KLPGA's
site is unreachable (network egress blocked), so this run's evidence is
limited to the 120 players already collected in OK_OPEN_2026_ENTRY_
SNAPSHOT.json / OK_OPEN_2026_CURRENT_PLAYER_MASTER.json (both collected
earlier this project against live klpga.co.kr) -- every other candidate
is PENDING_EVIDENCE, not guessed either way. Re-running with live
network access (see _fetch_profile's live path) would extend coverage
without changing this classification rule.
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
OK_OPEN_ENTRY_SNAPSHOT_PATH = CONTENT / "OK_OPEN_2026_ENTRY_SNAPSHOT.json"
OK_OPEN_CURRENT_MASTER_PATH = CONTENT / "OK_OPEN_2026_CURRENT_PLAYER_MASTER.json"
OK_OPEN_RANKING_PATH = CONTENT / "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json"
OUT_PATH = CONTENT / "ACTIVE_KLPGA_TOUR_PLAYER_MASTER.json"

PROFILE_URL = "https://klpga.co.kr/web/profile/mainRecord"

# KLPGA's own entry-list category label for a formal/automatic
# qualifying entrant (as opposed to a tournament-specific discretionary
# invite). See module docstring.
FORMAL_QUALIFICATION_CATEGORY = "자격자"

# Membership-track values that are, by KLPGA's own membership-track
# definition, distinct from (and not a subset of) the regular-tour
# membership track. See module docstring's CLASSIFICATION RULE.
NON_REGULAR_TOUR_MEMBERSHIP_TRACKS = {"I-Tour 회원", "실기평가 대상자"}


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
    default it. This is membership-track evidence only (see
    _fetch_entry_qualification for the season-seed evidence source)."""
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


def _load_entry_qualification() -> dict[str, dict]:
    """player_id -> {qualification_category, qualification_reason,
    source_url, retrieved_at} from the real, already-collected OK Open
    2026 entry-list disclosure. This is the season-seed evidence source
    (see module docstring)."""
    if not OK_OPEN_ENTRY_SNAPSHOT_PATH.is_file():
        return {}
    doc = json.loads(OK_OPEN_ENTRY_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    out = {}
    for e in doc.get("entries", ()):
        pid = str(e.get("player_id"))
        out[pid] = {
            "qualification_category": e.get("qualification_category"),
            "qualification_reason": e.get("qualification_reason"),
            "source_url": doc.get("source_url"),
            "retrieved_at": doc.get("retrieved_at"),
        }
    return out


def _load_profile_evidence() -> dict[str, dict]:
    """player_id -> membership-track + sponsor + name evidence, reused
    from the real live collection already performed for OK Open 2026's
    field (scripts/72). This is the membership-track evidence source
    (see module docstring)."""
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


def _classify(pid: str, name: str, qualification: dict | None, profile: dict | None) -> tuple[str, dict]:
    """Returns (state, detail) where state is one of ACTIVE_CONFIRMED /
    INACTIVE_CONFIRMED / PENDING_EVIDENCE and detail carries the
    evidence-specific fields for that state. See module docstring's
    CLASSIFICATION RULE and CONFLICT HANDLING."""
    has_season_seed_evidence = bool(
        qualification
        and qualification.get("qualification_category") == FORMAL_QUALIFICATION_CATEGORY
        and qualification.get("qualification_reason")
    )
    profile_status = profile.get("tour_status") if profile else None
    is_non_regular_track = profile_status in NON_REGULAR_TOUR_MEMBERSHIP_TRACKS

    if has_season_seed_evidence and is_non_regular_track:
        return "PENDING_EVIDENCE", {
            "reason": "conflicting_evidence",
            "conflict_evidence": {
                "entry_qualification_reason": qualification["qualification_reason"],
                "entry_qualification_category": qualification["qualification_category"],
                "profile_membership_track": profile_status,
            },
        }
    if has_season_seed_evidence:
        return "ACTIVE_CONFIRMED", {
            "reason": "entry_list_formal_qualification",
            "qualification_category": qualification["qualification_category"],
            "qualification_reason": qualification["qualification_reason"],
            "evidence_source_url": qualification.get("source_url"),
            "evidence_retrieved_at": qualification.get("retrieved_at"),
        }
    if is_non_regular_track:
        return "INACTIVE_CONFIRMED", {
            "reason": "non_regular_tour_membership_track",
            "profile_membership_track": profile_status,
            "evidence_source_url": profile.get("official_source") if profile else None,
            "evidence_retrieved_at": profile.get("retrieved_at") if profile else None,
        }
    if qualification is not None:
        return "PENDING_EVIDENCE", {
            "reason": "discretionary_entry_no_season_seed_evidence",
            "qualification_category": qualification.get("qualification_category"),
            "qualification_reason": qualification.get("qualification_reason"),
        }
    return "PENDING_EVIDENCE", {"reason": "no_collected_evidence"}


def build(*, attempt_live_fetch: bool = True, live_fetch_limit: int | None = None) -> dict:
    home_master = json.loads(HOME_MASTER_PATH.read_text(encoding="utf-8"))
    candidates = home_master["records"]
    k_rank_by_id = _load_k_rank()
    qualification_by_id = _load_entry_qualification()
    profile_by_id = _load_profile_evidence()

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"})

    active_players: list[dict] = []
    inactive_players: list[dict] = []
    pending_players: list[dict] = []
    live_fetch_attempts = 0

    for cand in candidates:
        pid = str(cand["player_id"])
        qualification = qualification_by_id.get(pid)
        profile = profile_by_id.get(pid)

        if profile is None and attempt_live_fetch and (
            live_fetch_limit is None or live_fetch_attempts < live_fetch_limit
        ):
            live_fetch_attempts += 1
            fetched = _fetch_profile(session, pid)
            time.sleep(0.15)
            if fetched is not None:
                profile = fetched

        name = (profile or {}).get("current_official_player_name") or cand["player_name"]
        state, detail = _classify(pid, name, qualification, profile)

        base = {
            "player_id": pid,
            "player_name": name,
            "classification": state,
        }
        base.update(detail)

        if state == "ACTIVE_CONFIRMED":
            record = {
                "player_id": pid,
                "player_name": name,
                "official_sponsor": (profile or {}).get("official_sponsor") or None,
                "tour_status": (profile or {}).get("tour_status"),
                "tour_status_source": {
                    "official_source": detail.get("evidence_source_url"),
                    "retrieved_at": detail.get("evidence_retrieved_at"),
                    "qualification_category": detail.get("qualification_category"),
                    "qualification_reason": detail.get("qualification_reason"),
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
                "data_as_of": detail.get("evidence_retrieved_at"),
            }
            active_players.append(record)
        elif state == "INACTIVE_CONFIRMED":
            inactive_players.append(base)
        else:
            pending_players.append(base)

    active_players.sort(key=lambda r: (r["player_name"], r["player_id"]))
    inactive_players.sort(key=lambda r: (r["player_name"], r["player_id"]))
    pending_players.sort(key=lambda r: r["player_id"])

    payload_for_hash = {
        "active_players": active_players,
        "inactive_players": inactive_players,
    }
    artifact_hash = hashlib.sha256(
        json.dumps(payload_for_hash, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    doc = {
        "schema_version": "neo_active_klpga_tour_player_master_v2",
        "population_kind": "current_season_regular_tour_playing_right_player_universe",
        "population_definition": (
            "Players with authoritative KLPGA evidence of CURRENT-SEASON "
            "regular-tour playing eligibility/status (seed rank, retained "
            "or promoted exempt category, tournament-win exemption, "
            "permanent/protected seed, career money-list exemption -- see "
            "module docstring). Explicitly NOT a KLPGA '정회원' membership-"
            "status proxy, NOT a K-Rank Top 150 truncation, and NOT an "
            "arbitrary truncation of the 546-player historical master."
        ),
        "distinct_from": (
            "A. HOME_REGULAR_TOUR_PLAYER_MASTER.json (546-player historical "
            "composite, no current-status evidence) -- untouched by this script. "
            "C. any single tournament's entry list (e.g. OK_OPEN_2026_ENTRY_"
            "SNAPSHOT.json) -- field membership alone is never treated as "
            "season-wide playing-right evidence; only the disclosed "
            "qualification_category/reason is."
        ),
        "target_scope_note": (
            "~150 is a scope target for what the complete universe is "
            "expected to look like once evidence collection is complete -- "
            "NOT a cutoff. This document reports only the actually-"
            "confirmed count from actual evidence."
        ),
        "classification_states": ["ACTIVE_CONFIRMED", "INACTIVE_CONFIRMED", "PENDING_EVIDENCE"],
        "classification_rule": (
            "ACTIVE_CONFIRMED: entry-list qualification_category=='자격자' "
            "(KLPGA's own formal/automatic-qualification label, as opposed "
            "to discretionary '추천자'/'초청자' invites) AND a non-empty "
            "qualification_reason naming a specific regular-tour seed/exempt "
            "category, with no conflicting membership-track evidence. "
            "INACTIVE_CONFIRMED: official profile membership track is a "
            "distinct non-regular-tour track (I-Tour 회원 / 실기평가 대상자) "
            "and no season-seed evidence exists. PENDING_EVIDENCE: no "
            "evidence collected yet; OR entry was via a discretionary "
            "category with no disclosed season-seed reason; OR the two "
            "evidence sources conflict (never silently resolved -- see "
            "conflict_evidence on the affected record)."
        ),
        "evidence_sources": [
            "OK_OPEN_2026_ENTRY_SNAPSHOT.json (qualification_category/qualification_reason)",
            "OK_OPEN_2026_CURRENT_PLAYER_MASTER.json (official KLPGA profile membership track + sponsor)",
            "https://klpga.co.kr/web/profile/mainRecord?playerCode=<id> (live fetch when reachable)",
        ],
        "generated_at": now(),
        "candidate_pool_source": "HOME_REGULAR_TOUR_PLAYER_MASTER.json",
        "candidate_pool_size": len(candidates),
        "counts": {
            "candidates_total": len(candidates),
            "active_confirmed": len(active_players),
            "inactive_confirmed": len(inactive_players),
            "pending_evidence": len(pending_players),
            "status": (
                "COMPLETE" if not any(p["classification"] == "PENDING_EVIDENCE" and p["reason"] == "no_collected_evidence" for p in pending_players)
                else "PARTIAL_PENDING_LIVE_KLPGA_NETWORK_ACCESS"
            ),
        },
        "active_players": active_players,
        "inactive_players": inactive_players,
        "pending_players": pending_players,
        "artifact_hash": artifact_hash,
    }
    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(doc["counts"], ensure_ascii=False))
    return doc


if __name__ == "__main__":
    raise SystemExit(0 if build() else 1)
