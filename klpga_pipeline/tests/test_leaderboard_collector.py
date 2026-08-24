"""Tests for klpga.collectors.leaderboard's collection strategy.

Corrected after a real bug found on live data (see leaderboard.py's
module docstring): the original strategy only checked players already
present in the final round's response for missing individual scores, so
a player entirely ABSENT from that response (a real CUT/WD/DQ case) was
never detected at all. Fixed by always fetching round 1 too (the
guaranteed full starting field) and comparing player_code sets. No
network access — a fake client stands in for PoliteHttpClient.
"""
from __future__ import annotations

from klpga.collectors.leaderboard import collect_all_rounds_for_game, discover_final_round


def _row_html(rank, name, code, r1="", r2="", r3="", r4="", total="", underpar="-1", today="-1", hole="18"):
    return (
        f'<ul class="lb-row" data-rank="{rank}" data-name="{name}" '
        f'data-totunderpar="{underpar}" data-inghole="{hole}" data-todayunderpar="{today}" '
        f'data-score="{total}" data-round1score="{r1}" data-round2score="{r2}" '
        f'data-round3score="{r3}" data-round4score="{r4}">'
        f'<li class="player-detail" _gamecode="G1" _playercode="{code}" _playername="{name}" '
        f'_playerengname="{name}-EN" _round="{{round}}" _hole="{hole}"></li></ul>'
    )


class FakeLeaderboardClient:
    def __init__(self, html_by_round: dict[int, str]):
        self.html_by_round = html_by_round
        self.calls: list[dict] = []

    def post_text(self, url, data=None, **kwargs):
        self.calls.append(dict(data or {}))
        rnd = int(data["round"])
        html = self.html_by_round.get(rnd, "")
        return html.replace("{round}", str(rnd))


def test_identical_field_on_round1_and_final_round_needs_only_two_requests():
    """When round 1 and the final round have the exact same set of
    players (a real confirmed no-cut/no-dropout case) and every row
    already has all 4 round scores, only round 1 and the final round
    need fetching."""
    final_html = (
        _row_html(1, "선수A", "111", r1="70", r2="67", r3="68", r4="71", total="276")
        + _row_html(2, "선수B", "112", r1="72", r2="70", r3="69", r4="70", total="281")
    )
    round1_html = (
        _row_html(1, "선수A", "111", r1="70", today="-2")
        + _row_html(2, "선수B", "112", r1="72", today="0")
    )
    client = FakeLeaderboardClient({4: final_html, 1: round1_html})

    results = collect_all_rounds_for_game(client, "G1", final_round=4)

    assert set(results.keys()) == {1, 4}
    assert len(client.calls) == 2
    assert {c["round"] for c in client.calls} == {"1", "4"}


def test_player_entirely_absent_from_final_round_triggers_full_intermediate_fetch():
    """Regression test for the real bug: a CUT player completely ABSENT
    from the final round's response (not just missing fields on a
    present row) must be detected by diffing round 1's field against
    the final round's, and every intermediate round fetched to locate
    where their data (and CUT/WD/DQ status) actually is."""
    # Only 선수A (111) appears on the final round -- 선수B (112) was cut
    # after round 2 and simply isn't in this response at all.
    final_html = _row_html(1, "선수A", "111", r1="70", r2="67", r3="68", r4="71", total="276")
    round1_html = (
        _row_html(1, "선수A", "111", r1="70", today="-2")
        + _row_html(1, "선수B", "112", r1="75", today="+3")
    )
    round2_html = (
        _row_html(1, "선수A", "111", r1="70", r2="67", today="-3")
        + _row_html("CUT", "선수B", "112", r1="75", r2="79", today="+7")
    )
    round3_html = _row_html(1, "선수A", "111", r1="70", r2="67", r3="68", today="-1")
    client = FakeLeaderboardClient(
        {4: final_html, 1: round1_html, 2: round2_html, 3: round3_html}
    )

    results = collect_all_rounds_for_game(client, "G1", final_round=4)

    assert set(results.keys()) == {1, 2, 3, 4}
    assert {c["round"] for c in client.calls} == {"1", "2", "3", "4"}


def test_discover_final_round_probes_downward_to_first_non_empty_round():
    # Tournament only had 3 rounds; round 4 returns no rows.
    r3_html = _row_html(1, "선수A", "111", r1="70", r2="67", r3="68", total="205")
    client = FakeLeaderboardClient({4: "", 3: r3_html})

    final_round, rows = discover_final_round(client, "G1", max_round=4)

    assert final_round == 3
    assert len(rows) == 1
    assert {c["round"] for c in client.calls} == {"4", "3"}
