"""Shared, single source for HITE JINRO (game_code 2026100005)'s two
per-player metric features -- NEO 경기력 band (from each entrant's own
committed Player Intelligence current_form) and the M4 win-model
probabilities (cut/TOP20/TOP10/TOP5/win) -- used by BOTH
scripts/190_build_hitejinro_pre_page.py (PRE) and
klpga.neo_win.hitejinro_round_page (R1/R2/R3/FR).

Extracted verbatim from 190's own original implementation (2026-09-30)
-- same formula, same weights, same quintile-banding, same "absent,
not guessed" rule for every missing field -- so PRE and every round
page compute an identical band/probability for the same player from
the same real inputs, never two independently-drifting copies. See
190's own module docstring for the full "WHAT IS NOW CONNECTED"
narrative this logic was built under.

BUG FIX (2026-10-01): R1 previously hardcoded 데이터 부족 for NEO 경기력
and every probability column unconditionally, even for the 107
entrants with real, complete current_form and a real M4 record --
exactly the same real data PRE already displays for them. There is no
reason a round page should show less than PRE already knows once the
underlying data exists; this module is what both now share so that
stops being true.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

GAME_CODE = "2026100005"
_REPO_ROOT = Path(__file__).resolve().parents[4]
CONTENT = _REPO_ROOT / "klpga_pipeline" / "content" / "website_v2"
PLAYER_INTELLIGENCE_DIR = CONTENT / "knowledge_engine" / "player_intelligence"
M4_CANDIDATE_PATH = CONTENT / f"HITEJINRO_{GAME_CODE}_PRE_M4_CANDIDATE_V1.json"

NEO_BAND_FEATURES = ("recent_5_sg", "recent_10_sg", "long_term_sg", "volatility")
NEO_BAND_WEIGHTS = {"recent_5_sg": 0.35, "recent_10_sg": 0.25, "long_term_sg": 0.25, "volatility": -0.10}
BAND_LABELS = ["최상위", "상위", "중위", "하위", "최하위"]


def load_current_form_by_id(player_ids: list[str]) -> dict[str, dict]:
    """{player_id: current_form dict} for entrants with a committed,
    COMPLETE (all 4 fields non-null) Player Intelligence document.
    Never partially fills a missing field; a player with any null
    feature is simply absent from the returned dict."""
    by_id: dict[str, dict] = {}
    for pid in player_ids:
        path = PLAYER_INTELLIGENCE_DIR / pid / "latest.json"
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        cf = doc.get("current_form") or {}
        if all(cf.get(k) is not None for k in NEO_BAND_FEATURES):
            by_id[pid] = cf
    return by_id


def neo_band_by_id(current_form_by_id: dict[str, dict]) -> dict[str, tuple[str, float]]:
    """{player_id: (band_label, raw_score)} -- raw_score is a z-scored
    composite over THIS tournament's own real field, never compared
    across tournaments. Quintile-banded highest-score-first."""
    if not current_form_by_id:
        return {}
    means = {f: statistics.mean(cf[f] for cf in current_form_by_id.values()) for f in NEO_BAND_FEATURES}
    stdevs = {f: statistics.pstdev(cf[f] for cf in current_form_by_id.values()) or 1.0 for f in NEO_BAND_FEATURES}
    scores: dict[str, float] = {}
    for pid, cf in current_form_by_id.items():
        scores[pid] = sum(
            NEO_BAND_WEIGHTS[f] * ((cf[f] - means[f]) / stdevs[f]) for f in NEO_BAND_FEATURES
        )
    ordered = sorted(scores, key=lambda pid: -scores[pid])
    n = len(ordered)
    band_by_id: dict[str, tuple[str, float]] = {}
    for i, pid in enumerate(ordered):
        band_by_id[pid] = (BAND_LABELS[min(4, i * 5 // n)], scores[pid])
    return band_by_id


def load_m4_by_id(path: Path | None = None) -> dict[str, dict]:
    """{player_code: record} for every entrant scripts/193's M4 output
    marks analysis_status=='PASS'. Returns {} if the file doesn't
    exist yet -- callers then render 데이터 부족 for every player,
    never a fabricated probability. `path` defaults to this module's
    own M4_CANDIDATE_PATH; callers that need to point at a different
    (e.g. test-fixture) path pass it explicitly rather than mutating
    this module's global."""
    path = path or M4_CANDIDATE_PATH
    if not path.is_file():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("gameCode") != GAME_CODE:
        return {}
    return {
        str(r["playerCode"]): r
        for r in doc.get("records", [])
        if r.get("analysis_status") == "PASS"
    }


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"
