"""P0 PRODUCTION INCIDENT -- STALE R1 LIVE DATA: regression tests for
the two rendering fixes in scripts/84_build_ok_open_pre_website_candidate.py
(_r1_live_leaderboard_section):

1. Tied leaders must ALL be shown under "현재 선두", never arbitrarily
   just the first one.
2. A stale snapshot (age > freshness_gate.STALE_THRESHOLD_SECONDS)
   must show the honest STALE_NOTICE_MARKER instead of implying the
   normal 30-minute live cadence is still current -- and a fresh
   snapshot must NOT show that notice.

Uses monkeypatch on the module's own R1_LIVE_SNAPSHOT path (never a
re-implementation of the renderer) so each scenario is fully isolated
from the real, currently-stale production snapshot on disk."""
import datetime
import json
from pathlib import Path

import importlib.util

SPEC = importlib.util.spec_from_file_location(
    "ok_open_builder", Path(__file__).parents[1] / "scripts" / "84_build_ok_open_pre_website_candidate.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from klpga.website_v2.freshness_gate import STALE_NOTICE_MARKER  # noqa: E402


def _snapshot(collected_at: str, rows: list) -> dict:
    return {
        "collected_at": collected_at,
        "player_table": rows,
        "expected_cut_distribution": {"p10": 1.0, "p50": 2.0, "p90": 3.0},
        "neo_movers": {},
    }


def _row(pid, name, score, holes="9"):
    return {
        "player_id": pid,
        "player_name": name,
        "rank_display": "1",
        "total_under_par": score,
        "total_under_par_display": str(score),
        "holes_completed": holes,
        "today_under_par": score,
        "gap_to_leader": 0,
        "cut_pct": None,
        "top20_pct": None,
        "top10_pct": None,
        "top5_pct": None,
        "win_pct": None,
        "pre_win_probability": None,
        "status": None,
    }


def _write_snapshot(tmp_path, snapshot):
    path = tmp_path / "snap.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    return path


def test_three_way_tie_shows_all_three_leader_names(tmp_path, monkeypatch):
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    rows = [_row("1", "선수A", -4), _row("2", "선수B", -4), _row("3", "선수C", -4), _row("4", "선수D", -3)]
    snapshot_path = _write_snapshot(tmp_path, _snapshot(now_iso, rows))
    monkeypatch.setattr(builder, "R1_LIVE_SNAPSHOT", snapshot_path)
    section = builder._r1_live_leaderboard_section("", {})
    assert "선수A, 선수B, 선수C" in section
    assert "선수D" not in section.split("</section>")[0].split("현재 선두")[1].split("</strong>")[0]


def test_single_leader_shows_just_that_name(tmp_path, monkeypatch):
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    rows = [_row("1", "선수A", -5), _row("2", "선수B", -3)]
    snapshot_path = _write_snapshot(tmp_path, _snapshot(now_iso, rows))
    monkeypatch.setattr(builder, "R1_LIVE_SNAPSHOT", snapshot_path)
    section = builder._r1_live_leaderboard_section("", {})
    idx = section.index("현재 선두")
    grid_entry = section[idx : idx + 120]
    assert "선수A</strong>" in grid_entry
    assert "," not in grid_entry.split("</strong>")[0]


def test_fresh_snapshot_shows_normal_cadence_note(tmp_path, monkeypatch):
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    snapshot_path = _write_snapshot(tmp_path, _snapshot(now_iso, [_row("1", "선수A", -2)]))
    monkeypatch.setattr(builder, "R1_LIVE_SNAPSHOT", snapshot_path)
    section = builder._r1_live_leaderboard_section("", {})
    assert "라이브 업데이트 주기 30분" in section
    assert STALE_NOTICE_MARKER not in section


def test_stale_snapshot_shows_delay_notice_not_the_normal_cadence_claim(tmp_path, monkeypatch):
    old_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)).isoformat().replace("+00:00", "Z")
    snapshot_path = _write_snapshot(tmp_path, _snapshot(old_iso, [_row("1", "선수A", -2)]))
    monkeypatch.setattr(builder, "R1_LIVE_SNAPSHOT", snapshot_path)
    section = builder._r1_live_leaderboard_section("", {})
    assert STALE_NOTICE_MARKER in section
    assert "라이브 업데이트 주기 30분" not in section
