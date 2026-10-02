"""Replay Test (Evidence First Architecture, 2026-10-02 mission):
Evidence Warehouse -> Round Transition Engine -> Projection Builder ->
render_round_page() -> SHA256 compare against the currently-published
HTML. Proves the new architecture's output is byte-identical to what
the existing, already-live pipeline produces for the SAME real round,
without replacing that live pipeline's own entry point (parse_leaderboard
via scripts/196-199 stays the operational path -- see
EVIDENCE_FIRST_REPLAY_REPORT.md for why).

All writes go through tmp_path -- the real evidence_warehouse/ (read
input) and the real docs/ HTML (read-only comparison target) are never
modified by this test."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from klpga.neo_win import projection_builder as pb
from klpga.neo_win.hitejinro_round_page import render_round_page

pytestmark = pytest.mark.round_pipeline

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONTENT = _REPO_ROOT / "klpga_pipeline" / "content" / "website_v2"
_WAREHOUSE = _CONTENT / "evidence_warehouse"
_DOCS_R2 = _REPO_ROOT / "docs" / "tournaments" / "2026" / "2026100005" / "r2" / "index.html"

requires_warehouse = pytest.mark.skipif(
    not (_WAREHOUSE / "tournament" / "2026100005" / "R2" / "leaderboard_raw.html").is_file(),
    reason="Evidence Warehouse for 2026100005 R2 not present in this checkout",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@requires_warehouse
def test_r2_projection_matches_every_legacy_field_of_the_real_leaderboard():
    """Evidence Warehouse + Round Transition Engine + Projection Builder
    must reproduce, for all 108 real entrants, the exact same
    finish_position/scores/withdrawn/disqualified/missed_cut values the
    live pipeline's own parse_leaderboard(2) already produced -- proof
    the two are computing the same real facts, not just coincidentally
    similar ones."""
    projection = pb.build_projection(2, warehouse_root=_WAREHOUSE, content_root=_CONTENT)
    current = json.loads((_CONTENT / "2026100005_LEADERBOARD.json").read_text(encoding="utf-8"))

    proj_by_id = {r["player_id"]: r for r in projection["records"]}
    cur_by_id = {r["player_id"]: r for r in current["records"]}
    assert set(proj_by_id) == set(cur_by_id)

    fields = [
        "finish_position", "finish_position_numeric", "score_to_par",
        "r1_score", "r2_score", "r3_score", "r4_score",
        "withdrawn", "disqualified", "missed_cut",
    ]
    mismatches = [
        (pid, f, cur_by_id[pid].get(f), proj_by_id[pid].get(f))
        for pid in cur_by_id for f in fields
        if cur_by_id[pid].get(f) != proj_by_id[pid].get(f)
    ]
    assert mismatches == [], f"{len(mismatches)} field mismatches: {mismatches[:10]}"


@requires_warehouse
def test_r2_replay_html_is_byte_identical_to_the_live_published_page(tmp_path):
    """The real, strict Replay Test: Evidence Warehouse alone (never
    LEADERBOARD.json as an input) all the way to rendered HTML, SHA256
    compared against the currently-published docs/.../r2/index.html.
    Must match exactly -- round 2 is the tournament's current real
    round, so this is the meaningful, operationally-relevant replay
    target (see EVIDENCE_FIRST_REPLAY_REPORT.md for why round 1's own
    published page is NOT used as a replay target: it predates two
    real, already-documented fixes unrelated to this architecture)."""
    for name in (
        "2026100005_ENTRY_KRANKING_JOIN.json",
        "HITEJINRO_2026100005_PRE_M4_CANDIDATE_V1.json",
        "2026100005_TOURNAMENT_INFO.json",
    ):
        (tmp_path / name).write_bytes((_CONTENT / name).read_bytes())

    projection = pb.build_projection(2, warehouse_root=_WAREHOUSE, content_root=_CONTENT)
    (tmp_path / "2026100005_LEADERBOARD.json").write_text(
        json.dumps(projection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )

    tourney = json.loads((_CONTENT / "2026100005_TOURNAMENT_INFO.json").read_text(encoding="utf-8"))
    start, end = tourney["start_date"], tourney["end_date"]
    date_range = f"{start[:4]}.{start[4:6]}.{start[6:8]} — {end[4:6]}.{end[6:8]}"
    html = render_round_page(2, tournament_name=tourney["event_name"], date_range=date_range, content_root=tmp_path)
    replay_path = tmp_path / "r2_replay.html"
    replay_path.write_text(html, encoding="utf-8", newline="\n")

    assert _sha256(replay_path) == _sha256(_DOCS_R2), (
        "Replay Test FAILED: Evidence Warehouse -> Projection -> HTML is not byte-identical "
        "to the live published R2 page."
    )
