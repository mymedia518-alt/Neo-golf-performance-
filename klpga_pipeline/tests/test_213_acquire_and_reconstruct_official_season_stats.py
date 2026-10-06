"""Tests for scripts/213_acquire_and_reconstruct_official_season_stats
.py -- the two-layer gate (pre-flight pilot + per-call) and the
season-to-date cumulative reconstruction, using a fake client so no
real network call happens."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "213_acquire_and_reconstruct_official_season_stats.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("acquire_213", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["acquire_213"] = module
    spec.loader.exec_module(module)
    return module


# A minimal real-shaped publicRecordSeasonDetail fragment, one row per
# target metric, parameterized by rounds/numerator/denominator so a
# FakeClient can return a different, correctly-scoped body per gameCode.
def _fragment(rounds: int, dd_num: float, dd_den: int, fw_num: int, fw_den: int, gir_num: int) -> str:
    gir_pct = round(gir_num / (rounds * 18) * 100, 4)
    dd_val = round(dd_num / dd_den, 4)
    fw_val = round(fw_num / fw_den * 100, 4)
    return f"""
    <h2 class="content-title">스코어</h2>
    <table><tbody>
    <tr><td class="text-start bg-lightblue">평균타수</td><td>70.0</td><td></td>
        <td class="text-start bg-lightblue">전체타수</td><td>{rounds * 70}.000</td>
        <td class="text-start bg-lightblue">라운드수</td><td>{rounds}</td></tr>
    </tbody></table>
    <h2 class="content-title">기술</h2>
    <table><tbody>
    <tr><td class="text-start bg-lightblue">드라이브 거리</td><td>{dd_val}</td><td></td>
        <td class="text-start bg-lightblue">전체 비거리</td><td>{dd_num}</td>
        <td class="text-start bg-lightblue">전체 측정 홀</td><td>{dd_den}</td></tr>
    <tr><td class="text-start bg-lightblue">페어웨이 안착률</td><td>{fw_val}</td><td></td>
        <td class="text-start bg-lightblue">페어웨이 안착 수</td><td>{fw_num}</td>
        <td class="text-start bg-lightblue">전체 측정 홀</td><td>{fw_den}</td></tr>
    <tr><td class="text-start bg-lightblue">그린적중률</td><td>{gir_pct}</td><td></td>
        <td class="text-start bg-lightblue">그린적중수</td><td>{gir_num}</td>
        <td class="text-start bg-lightblue">-</td><td>-</td></tr>
    </tbody></table>
    """


class FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


class FakeClient:
    """Returns a different, correctly tournament-scoped fragment per
    gameCode, keyed from a dict the test supplies -- simulates the
    real endpoint's confirmed per-tournament scoping behavior."""

    def __init__(self, bodies_by_game_code: dict[str, str]):
        self.bodies_by_game_code = bodies_by_game_code
        self.calls: list[tuple] = []

    def _throttle(self, host):
        pass

    def _do_request(self, method, url, **kwargs):
        data = kwargs.get("data") or {}
        game_code = data.get("gameCode")
        self.calls.append((method, url, game_code))
        body = self.bodies_by_game_code.get(game_code, "<html><body>no data</body></html>")
        return FakeResponse(200, body)


def test_preflight_pilot_passes_when_scoping_matches_ground_truth():
    mod = _load_module()
    bodies = {"T1": _fragment(rounds=4, dd_num=1000, dd_den=4, fw_num=28, fw_den=56, gir_num=40)}
    client = FakeClient(bodies)
    entries = [{"player_code": "P1", "season": 2023,
                "pre_cutoff_tournaments": [{"game_code": "T1", "start_date": "2023-01-01",
                                             "real_rounds_this_tournament": 4}]}]
    ok, results = mod.run_preflight_pilot(client, entries)
    assert ok is True
    assert results[0]["gate_passed"] is True


def test_preflight_pilot_fails_when_endpoint_returns_wrong_scope():
    mod = _load_module()
    # the fragment claims 8 rounds but ground truth for this tournament is 4 -- scope mismatch
    bodies = {"T1": _fragment(rounds=8, dd_num=1000, dd_den=4, fw_num=28, fw_den=56, gir_num=40)}
    client = FakeClient(bodies)
    entries = [{"player_code": "P1", "season": 2023,
                "pre_cutoff_tournaments": [{"game_code": "T1", "start_date": "2023-01-01",
                                             "real_rounds_this_tournament": 4}]}]
    ok, results = mod.run_preflight_pilot(client, entries)
    assert ok is False
    assert results[0]["gate_passed"] is False


def test_acquire_and_reconstruct_player_sums_two_gate_passed_tournaments_weighted():
    mod = _load_module()
    bodies = {
        "T1": _fragment(rounds=4, dd_num=1000.0, dd_den=4, fw_num=28, fw_den=56, gir_num=40),
        "T2": _fragment(rounds=3, dd_num=750.0, dd_den=3, fw_num=21, fw_den=42, gir_num=30),
    }
    client = FakeClient(bodies)
    entry = {
        "player_name": "테스트선수", "player_code": "P1", "season": 2023,
        "expected_pre_cutoff_rounds_total": 7,
        "pre_cutoff_tournaments": [
            {"game_code": "T1", "start_date": "2023-01-01", "real_rounds_this_tournament": 4},
            {"game_code": "T2", "start_date": "2023-02-01", "real_rounds_this_tournament": 3},
        ],
    }
    result = mod.acquire_and_reconstruct_player(client, entry, save_html=False, out_dir=Path("/tmp"))
    assert result["n_tournaments_gate_passed"] == 2
    # driving distance: (1000+750)/(4+3) = 250.0 exactly
    assert result["reconstructed"]["driving_distance"]["value"] == 250.0
    # fairway: (28+21)/(56+42) * 100 = 50.0 exactly
    assert result["reconstructed"]["fairway_accuracy"]["value"] == 50.0
    # gir: (40+30)/((4*18)+(3*18)) * 100 = 70/126*100 = 55.5556
    assert result["reconstructed"]["gir"]["value"] == 55.5556


def test_acquire_and_reconstruct_player_excludes_gate_failed_tournament():
    mod = _load_module()
    bodies = {
        "T1": _fragment(rounds=4, dd_num=1000.0, dd_den=4, fw_num=28, fw_den=56, gir_num=40),
        # T2's fragment lies about its own rounds (says 9, ground truth says 3) -- must be excluded
        "T2": _fragment(rounds=9, dd_num=99999.0, dd_den=1, fw_num=0, fw_den=1, gir_num=0),
    }
    client = FakeClient(bodies)
    entry = {
        "player_name": "테스트선수", "player_code": "P1", "season": 2023,
        "expected_pre_cutoff_rounds_total": 7,
        "pre_cutoff_tournaments": [
            {"game_code": "T1", "start_date": "2023-01-01", "real_rounds_this_tournament": 4},
            {"game_code": "T2", "start_date": "2023-02-01", "real_rounds_this_tournament": 3},
        ],
    }
    result = mod.acquire_and_reconstruct_player(client, entry, save_html=False, out_dir=Path("/tmp"))
    assert result["n_tournaments_gate_passed"] == 1
    assert result["reconstructed"]["driving_distance"]["value"] == 250.0  # T1 only, T2's 99999 excluded
