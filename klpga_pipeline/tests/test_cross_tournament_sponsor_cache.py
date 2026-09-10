"""OWNER DECISION -- sponsor population is not optional (PRODUCT
PRESENTATION RECOVERY, item 1: populate every officially verified
sponsor available from existing evidence/cache, never guess).

Regression coverage for klpga.website_v2.player_identity's
cross_tournament_verified_sponsor_cache()/sponsor_with_cross_tournament
_fallback() -- the narrow, six-point-gated fallback that lets a
player's already-verified sponsor from ANOTHER tournament's own
independent collection populate a field where THIS tournament's own
collection never actually attempted enrichment. Never name-matched,
never overwrites a genuine "checked, none" result, never guessed.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

_SPEC84 = importlib.util.spec_from_file_location(
    "sponsor_cache_s84", ROOT / "scripts" / "84_build_ok_open_pre_website_candidate.py"
)
builder84 = importlib.util.module_from_spec(_SPEC84)
_SPEC84.loader.exec_module(builder84)

_SPEC88 = importlib.util.spec_from_file_location(
    "sponsor_cache_s88", ROOT / "scripts" / "88_build_neo_top120_candidate.py"
)
builder88 = importlib.util.module_from_spec(_SPEC88)
_SPEC88.loader.exec_module(builder88)

from klpga.website_v2.player_identity import (  # noqa: E402
    cross_tournament_verified_sponsor_cache, sponsor_with_cross_tournament_fallback, verified_sponsor,
)

_NEVER_CHECKED = "optional live profile enrichment was not requested"


def test_direct_sponsor_never_needs_the_fallback():
    record = {"identity_validation": "PASS", "current_official_sponsor": "실제소속사", "player_id": "1"}
    assert sponsor_with_cross_tournament_fallback(record, {"1": "다른소속사"}) == "실제소속사"


def test_fallback_applies_only_when_never_actually_checked():
    record = {
        "identity_validation": "PASS", "current_official_sponsor": None,
        "player_id": "42", "failure_reason": _NEVER_CHECKED,
    }
    assert sponsor_with_cross_tournament_fallback(record, {"42": "캐시된소속사"}) == "캐시된소속사"


def test_fallback_never_overwrites_a_genuine_checked_and_none_result():
    """A record that WAS actually checked (any other failure_reason, or
    none at all) and still has no sponsor must stay blank -- a
    cross-tournament cache value must never override a real negative
    result from this tournament's own collection."""
    record = {
        "identity_validation": "PASS", "current_official_sponsor": None,
        "player_id": "42", "failure_reason": "live profile fetched, no sponsor listed",
    }
    assert sponsor_with_cross_tournament_fallback(record, {"42": "캐시된소속사"}) is None
    record_no_reason = {"identity_validation": "PASS", "current_official_sponsor": None, "player_id": "42"}
    assert sponsor_with_cross_tournament_fallback(record_no_reason, {"42": "캐시된소속사"}) is None


def test_fallback_never_applies_when_active_record_identity_is_unconfirmed():
    record = {
        "identity_validation": "UNCONFIRMED", "current_official_sponsor": None,
        "player_id": "42", "failure_reason": _NEVER_CHECKED,
    }
    assert sponsor_with_cross_tournament_fallback(record, {"42": "캐시된소속사"}) is None


def test_fallback_is_player_id_keyed_never_name_matched():
    """The cache dict itself is keyed by player_id; a record's own name
    is never consulted -- an unrelated player_id simply misses."""
    record = {
        "identity_validation": "PASS", "current_official_sponsor": None,
        "player_id": "999999-unknown", "failure_reason": _NEVER_CHECKED,
    }
    assert sponsor_with_cross_tournament_fallback(record, {"42": "캐시된소속사"}) is None


def test_cache_excludes_records_missing_official_source_or_identity_pass(tmp_path):
    other_master = tmp_path / "SYN0001_CURRENT_PLAYER_MASTER.json"
    other_master.write_text(json.dumps({"records": [
        {"player_id": "1", "identity_validation": "PASS", "current_official_sponsor": "A스폰서", "official_source": "https://official/1"},
        {"player_id": "2", "identity_validation": "PASS", "current_official_sponsor": "B스폰서", "official_source": ""},
        {"player_id": "3", "identity_validation": "UNCONFIRMED", "current_official_sponsor": "C스폰서", "official_source": "https://official/3"},
    ]}), encoding="utf-8")
    cache = cross_tournament_verified_sponsor_cache(exclude_paths=set(), content_dir=tmp_path)
    assert cache == {"1": "A스폰서"}


def test_cache_drops_a_player_id_with_conflicting_sponsors_across_sources(tmp_path):
    """Two different source tournaments disagreeing on the same
    player_id's sponsor is an unresolved conflict -- dropped entirely,
    never guessed which source is right."""
    (tmp_path / "SYN0001_CURRENT_PLAYER_MASTER.json").write_text(json.dumps({"records": [
        {"player_id": "7", "identity_validation": "PASS", "current_official_sponsor": "X스폰서", "official_source": "https://official/7a"},
    ]}), encoding="utf-8")
    (tmp_path / "SYN0002_CURRENT_PLAYER_MASTER.json").write_text(json.dumps({"records": [
        {"player_id": "7", "identity_validation": "PASS", "current_official_sponsor": "Y스폰서", "official_source": "https://official/7b"},
        {"player_id": "8", "identity_validation": "PASS", "current_official_sponsor": "Z스폰서", "official_source": "https://official/8"},
    ]}), encoding="utf-8")
    cache = cross_tournament_verified_sponsor_cache(exclude_paths=set(), content_dir=tmp_path)
    assert "7" not in cache
    assert cache["8"] == "Z스폰서"


def test_cache_excludes_the_given_exclude_paths(tmp_path):
    active = tmp_path / "ACTIVE0001_CURRENT_PLAYER_MASTER.json"
    active.write_text(json.dumps({"records": [
        {"player_id": "1", "identity_validation": "PASS", "current_official_sponsor": "자기소속사", "official_source": "https://official/1"},
    ]}), encoding="utf-8")
    cache = cross_tournament_verified_sponsor_cache(exclude_paths={active}, content_dir=tmp_path)
    assert cache == {}


def test_kb_pre_populates_real_cross_tournament_sponsors_not_guessed(tmp_path):
    """Integration proof against the real KB build: exactly the audited
    94/120 KB field players (SPONSOR OFFICIAL-EVIDENCE RECOVERY V2 added
    a third evidence tier -- operator-reported KLPGA checks -- to the
    shared resolver itself, growing this from V1's 90 to 94) get a real,
    PASS-gated, official-source-backed sponsor from either OK Open's own
    independent collection or the operator-reported tier; the remaining
    26 stay genuinely COLLECTION_BLOCKED (no qualifying evidence yet
    collected, never guessed)."""
    out = builder84.build("2026090003")
    html = (out / "tournaments/2026/2026090003/pre/index.html").read_text(encoding="utf-8")
    import re
    spans = re.findall(r"<span class='player-sponsor'>([^<]*)</span>", html)
    assert len(spans) == 120
    populated = sum(1 for s in spans if s.strip())
    kb = json.loads((CONTENT / "2026090003_CURRENT_PLAYER_MASTER.json").read_text(encoding="utf-8"))["records"]
    cache = cross_tournament_verified_sponsor_cache(content_dir=CONTENT)
    expected = len({str(r["player_id"]) for r in kb} & set(cache))
    assert populated == expected
    # every KB record's own current_official_sponsor is null (real
    # fixture state) -- so every populated sponsor in the rendered
    # page necessarily came from the cross-tournament cache, never a
    # guess, and never from the active record's own (empty) field.
    assert all(not r.get("current_official_sponsor") for r in kb)
    assert "확인 중" not in html and "미확인" not in html


def test_kb_pre_never_shows_sponsor_for_a_player_not_in_the_cache(tmp_path):
    out = builder84.build("2026090003")
    html = (out / "tournaments/2026/2026090003/pre/index.html").read_text(encoding="utf-8")
    kb = json.loads((CONTENT / "2026090003_CURRENT_PLAYER_MASTER.json").read_text(encoding="utf-8"))["records"]
    ok_open = json.loads((CONTENT / "OK_OPEN_2026_CURRENT_PLAYER_MASTER.json").read_text(encoding="utf-8"))["records"]
    ok_ids = {str(r["player_id"]) for r in ok_open if verified_sponsor(r)}
    not_cached = [r for r in kb if str(r["player_id"]) not in ok_ids]
    assert not_cached, "fixture assumption: at least one KB player has no OK Open cache entry"
    r = not_cached[0]
    name = r["current_official_player_name"]
    idx = html.find(f">{name}<")
    assert idx != -1, name
    row_tail = html[idx : idx + 200]
    assert "<span class='player-sponsor'></span>" in row_tail


# ---------------------------------------------------------------------------
# OWNER REVIEW: SPONSOR CONTRACT IS GLOBAL -- the same resolution now
# also applies to HOME's TOP120 table (scripts/88), reusing the exact
# same klpga.website_v2.player_identity functions KB PRE uses -- no
# HOME-specific duplicate of the gate logic.
# ---------------------------------------------------------------------------

def test_home_populates_sponsors_for_top120_players_in_the_active_field():
    """A TOP120 player who is also in the active tournament's own field
    gets sponsor_with_cross_tournament_fallback() applied against their
    own direct record first (same as KB PRE)."""
    summary = builder88.build()
    assert summary["cohort_count"] == 120
    html = (builder88.OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    import re
    identities = re.findall(r'<span class="player-name">([^<]+)</span><span class="player-sponsor">([^<]*)</span>', html)
    assert len(identities) == 120
    populated = {name: sponsor for name, sponsor in identities if sponsor}
    assert populated, "expected at least one real cross-tournament sponsor on HOME"
    assert "확인 중" not in html and "미확인" not in html


def test_home_populates_sponsors_for_top120_players_outside_the_active_field_too():
    """A TOP120 player who is NOT in the active tournament's own field
    has no direct record to check at all -- the shared cross-tournament
    cache is the only evidence that exists for them, and it applies
    directly (still PASS-gated + official_source-backed, never a
    guess) rather than leaving them blank just because they aren't in
    this season's currently-active field."""
    top120 = json.loads((CONTENT / "HOME_PLAYER_MASTER_TOP120.json").read_text(encoding="utf-8"))["records"]
    kb = json.loads((CONTENT / "2026090003_CURRENT_PLAYER_MASTER.json").read_text(encoding="utf-8"))["records"]
    kb_ids = {str(r["player_id"]) for r in kb}
    ok_open = json.loads((CONTENT / "OK_OPEN_2026_CURRENT_PLAYER_MASTER.json").read_text(encoding="utf-8"))["records"]
    ok_sponsor_by_id = {str(r["player_id"]): r.get("current_official_sponsor") for r in ok_open if verified_sponsor(r)}
    outside_field_with_evidence = [
        r for r in top120 if str(r["player_id"]) not in kb_ids and str(r["player_id"]) in ok_sponsor_by_id
    ]
    assert outside_field_with_evidence, "fixture assumption: at least one TOP120 player outside KB's field has OK Open evidence"
    sample = outside_field_with_evidence[0]
    builder88.build()
    html = (builder88.OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    expected_sponsor = ok_sponsor_by_id[str(sample["player_id"])]
    idx = html.find(f">{sample['player_name']}<")
    assert idx != -1, sample["player_name"]
    row_tail = html[idx : idx + 200]
    assert f"<span class=\"player-sponsor\">{expected_sponsor}</span>" in row_tail


def test_home_sponsor_coverage_matches_the_generic_resolver_exactly():
    """No HOME-specific fudge factor: the exact populated/blank split
    on the rendered page must match calling the shared resolver
    directly against the same inputs."""
    top120 = json.loads((CONTENT / "HOME_PLAYER_MASTER_TOP120.json").read_text(encoding="utf-8"))["records"]
    kb_master_path = CONTENT / "2026090003_CURRENT_PLAYER_MASTER.json"
    kb = json.loads(kb_master_path.read_text(encoding="utf-8"))["records"]
    kb_by_id = {str(r["player_id"]): r for r in kb}
    cache = cross_tournament_verified_sponsor_cache(exclude_paths={kb_master_path})
    expected_populated = 0
    for row in top120:
        pid = str(row["player_id"])
        record = kb_by_id.get(pid)
        sponsor = sponsor_with_cross_tournament_fallback(record, cache) if record else cache.get(pid)
        if sponsor:
            expected_populated += 1
    builder88.build()
    html = (builder88.OUTPUT / "ranking" / "index.html").read_text(encoding="utf-8")
    import re
    spans = re.findall(r'<span class="player-sponsor">([^<]*)</span>', html)
    assert len(spans) == 120
    assert sum(1 for s in spans if s.strip()) == expected_populated
