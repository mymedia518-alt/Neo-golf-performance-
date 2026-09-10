"""KB 2026090003 R1 public page -- deployment-critical publication gate.

Covers: official population reconciliation, PRE immutability, R1
freeze integrity, no future leakage, probability bounds/coherence,
118 active / 2 WD, duplicate identity, sponsor invariant, HOME
unchanged, unrelated-route lockdown, R1 page build, production
artifact consistency. This is the gate scripts/109_build_kb_r1_page.py
and the whole KB R1 deployment depend on passing before any push to
production.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
DOCS = REPO_ROOT / "docs"
GAME_CODE = "2026090003"


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def _freeze() -> dict:
    return _load(f"{GAME_CODE}_R1_5PROB_FROZEN_V1.json")


def test_official_population_reconciles_120():
    freeze = _freeze()
    entry = _load(f"{GAME_CODE}_ENTRY_SNAPSHOT.json")
    entry_ids = {e["player_id"] for e in entry["entries"]}
    predicted_ids = {p["player_id"] for p in freeze["predictions"]}
    excluded_ids = {e["player_id"] for e in freeze["excluded_players"]}
    wd_ids = {w["playerCode"] for w in freeze["official_wd"]}
    assert len(entry_ids) == 120
    assert (predicted_ids | excluded_ids | wd_ids) == entry_ids
    assert len(predicted_ids) + len(excluded_ids) + len(wd_ids) == 120


def test_pre_immutability():
    actual_sha = hashlib.sha256((CONTENT / f"{GAME_CODE}_PRE_5PROB_V2_FROZEN.json").read_bytes()).hexdigest()
    assert actual_sha == "456d465e05f919c96ab827a68004aafb1ad971a7a128e6b44c461c9eb41fef36"


def test_r1_freeze_integrity_hashes_match_real_files():
    freeze = _freeze()
    assert freeze["model_freeze_sha256"] == hashlib.sha256((CONTENT / "NEO_R1_MODEL_V1_FREEZE.json").read_bytes()).hexdigest()
    assert freeze["tournament_master_dates_sha256"] == hashlib.sha256((CONTENT / "TOURNAMENT_MASTER_DATES_V1.json").read_bytes()).hexdigest()
    recomputed = hashlib.sha256(
        json.dumps(freeze["predictions"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert recomputed == freeze["prediction_values_sha256"]


def test_no_future_leakage_r1_uses_only_r1_and_pre_data():
    """The frozen model's only two features are pre_score (PRE-time)
    and r1_z (R1-observed) -- guard against a future edit smuggling in
    a later-round field name."""
    freeze = _freeze()
    for p in freeze["predictions"]:
        assert set(p.keys()) == {
            "player_id", "player_name", "r1_score", "r1_to_par", "r1_rank_display",
            "pre_score", "r1_z", "cut", "top20", "top10", "top5", "win",
        }


def test_probability_bounds_and_coherence():
    freeze = _freeze()
    for p in freeze["predictions"]:
        vals = [p["win"], p["top5"], p["top10"], p["top20"], p["cut"]]
        assert all(0.0 <= v <= 1.0 for v in vals)
        assert vals == sorted(vals)


def test_118_active_2_wd():
    freeze = _freeze()
    assert freeze["r1_active_count"] == 118
    assert freeze["official_wd_count"] == 2


def test_no_duplicate_identity():
    freeze = _freeze()
    ids = [p["player_id"] for p in freeze["predictions"]] + [e["player_id"] for e in freeze["excluded_players"]]
    assert len(ids) == len(set(ids))


def test_sponsor_invariant_on_r1_page():
    """Every player row's <th> must carry exactly one player-name span
    immediately followed by exactly one player-sponsor span (possibly
    empty, never fabricated -- only real verified sponsors from
    KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V2.json)."""
    from html import escape as html_escape

    r1_html = (DOCS / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html").read_text(encoding="utf-8")
    audit = _load("KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V2.json")
    verified_sponsors = {html_escape(r["sponsor"]) for r in audit["newly_recovered_sponsors"]}

    rows = re.findall(r"<th scope='row'>(.*?)</th>", r1_html)
    assert len(rows) >= 100
    for row in rows:
        m = re.match(r"<span class='player-name'>.*?</span><span class='player-sponsor'>(.*?)</span>$", row)
        assert m, f"row does not match the exact name+sponsor pattern: {row!r}"
        sponsor = m.group(1)
        if sponsor:
            assert sponsor in verified_sponsors, f"unverified sponsor text on page: {sponsor!r}"


def test_home_page_unchanged():
    """HOME (docs/index.html) must never be touched by the KB R1
    deployment."""
    result = subprocess.run(
        ["git", "diff", "--stat", "HEAD", "--", "docs/index.html"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == ""


def test_unrelated_routes_still_locked():
    import importlib.util

    spec = importlib.util.spec_from_file_location("lockdown", ROOT / "scripts" / "apply_public_site_lockdown.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    problems = mod.verify_lockdown()
    assert problems == []


def test_r1_page_exists_and_stage_nav_links_to_pre_and_r1():
    r1_html = (DOCS / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html").read_text(encoding="utf-8")
    assert 'href="/tournaments/2026/2026090003/pre/"' in r1_html
    assert '<strong class="status">R1</strong>' in r1_html

    pre_html = (DOCS / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html").read_text(encoding="utf-8")
    assert '<a class="stage-nav__link" href="/tournaments/2026/2026090003/r1/">R1</a>' in pre_html


def test_production_artifact_consistency_r1_score_matches_official_evidence():
    freeze = _freeze()
    r1ev = _load(f"NEO_KB_{GAME_CODE}_R1_OFFICIAL_RESULT_EVIDENCE_V1.json")
    official_by_id = {p["playerCode"]: p for p in r1ev["players"]}
    for p in freeze["predictions"] + [
        {**e, "r1_score": None} for e in freeze["excluded_players"]
    ]:
        official = official_by_id.get(p["player_id"])
        if official is None or p.get("r1_score") is None:
            continue
        assert p["r1_score"] == official["r1Score"]
