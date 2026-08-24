"""Tests for klpga.collectors.leaderboard — specifically the request-count
optimization from spec section 5 (reuse the final round's response when
it already has all 4 round scores; only fetch an earlier round when a
player's score for it is actually missing). No network access — a fake
client stands in for PoliteHttpClient."""
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


def test_final_round_with_full_history_needs_only_one_request():
    final_html = (
        _row_html(1, "선수A", "111", r1="70", r2="67", r3="68", r4="71", total="276")
        + _row_html(2, "선수B", "112", r1="72", r2="70", r3="69", r4="70", total="281")
    )
    client = FakeLeaderboardClient({4: final_html})

    results = collect_all_rounds_for_game(client, "G1", final_round=4)

    assert set(results.keys()) == {4}
    assert len(client.calls) == 1
    assert client.calls[0] == {"gameCode": "G1", "round": "4"}


def test_cut_player_missing_earlier_round_triggers_one_targeted_extra_call():
    # Final round (4) response: player A has all 4 rounds; CUT player B is
    # missing round1 in this response (simulating the "may not be included"
    # case called out in the spec).
    final_html = (
        _row_html(1, "선수A", "111", r1="70", r2="67", r3="68", r4="71", total="276")
        + _row_html("CUT", "선수B", "112", r1="", r2="79", r3="68", r4="", total="", today="")
    )
    round1_html = _row_html(1, "선수A", "111", r1="70", today="-2") + _row_html(
        "CUT", "선수B", "112", r1="75", today="+3"
    )
    client = FakeLeaderboardClient({4: final_html, 1: round1_html})

    results = collect_all_rounds_for_game(client, "G1", final_round=4)

    assert set(results.keys()) == {4, 1}
    # exactly 2 requests total: the final round, plus the one missing round
    assert len(client.calls) == 2
    assert {c["round"] for c in client.calls} == {"4", "1"}
    # round 2/3 were NOT re-fetched even though they weren't 100% verified
    # for every player, because no row was missing a round2/round3 score
    assert all(c["round"] != "2" and c["round"] != "3" for c in client.calls)


def test_discover_final_round_probes_downward_to_first_non_empty_round():
    # Tournament only had 3 rounds; round 4 returns no rows.
    r3_html = _row_html(1, "선수A", "111", r1="70", r2="67", r3="68", total="205")
    client = FakeLeaderboardClient({4: "", 3: r3_html})

    final_round, rows = discover_final_round(client, "G1", max_round=4)

    assert final_round == 3
    assert len(rows) == 1
    assert {c["round"] for c in client.calls} == {"4", "3"}
