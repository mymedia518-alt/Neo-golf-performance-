"""End-to-end regression test for the real bug reported from a live
5-tournament Windows run: player_round == 4 * player_event EXACTLY
across all 336 collected player_event rows, meaning every collected
player had all 4 rounds and made_cut/withdrawn/disqualified were all
zero. That's not plausible as "none of 5 real tournaments had a cut" —
the root cause was that collect_all_rounds_for_game only checked
players already present in the final round's response for missing
individual scores, so a player entirely ABSENT from that response (a
real CUT case) was never detected or collected at all.

This test exercises the full real pipeline — collect_all_rounds_for_game
-> merge_player_rows -> build_rows — against a fake HTTP client, and
asserts the CUT player actually ends up in the output with the correct
made_cut=0 flag and only 2 rounds played, instead of being silently
dropped."""
from __future__ import annotations

from klpga.collectors.aggregate import build_rows, merge_player_rows
from klpga.collectors.leaderboard import collect_all_rounds_for_game


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

    def post_text(self, url, data=None, **kwargs):
        rnd = int(data["round"])
        return self.html_by_round.get(rnd, "").replace("{round}", str(rnd))


def test_cut_player_is_collected_with_made_cut_zero_not_silently_dropped():
    # 선수A makes the cut and finishes all 4 rounds. 선수B is cut after
    # round 2 and never appears on the final round's leaderboard at all.
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

    rounds_data = collect_all_rounds_for_game(client, "G1", final_round=4)
    merged = merge_player_rows(rounds_data)
    player_rows, player_event_rows, player_round_rows = build_rows("G1", 2026, "G1", merged, final_round=4)

    assert {p["player_id"] for p in player_rows} == {"111", "112"}

    event_by_player = {e["player_id"]: e for e in player_event_rows}

    player_a = event_by_player["111"]
    assert player_a["made_cut"] == 1
    assert player_a["rounds_played"] == 4
    assert player_a["total_score"] == 276

    player_b = event_by_player["112"]
    assert player_b["made_cut"] == 0, "CUT player must be recorded with made_cut=0, not silently dropped"
    assert player_b["withdrawn"] == 0
    assert player_b["disqualified"] == 0
    assert player_b["finish_position"] == "CUT"
    assert player_b["rounds_played"] == 2
    assert player_b["r1_score"] == 75
    assert player_b["r2_score"] == 79
    assert player_b["r3_score"] is None
    assert player_b["r4_score"] is None
    # total_score is None here because 선수B's cumulative data-score was
    # never observed as a real number in this fixture (blank in the
    # only response they appear in) — must stay NULL, not be
    # back-computed as 75+79 (that's not what data-score means: it's
    # the site's own cumulative total, not a value we should derive).
    assert player_b["total_score"] is None

    round_rows_b = [r for r in player_round_rows if r["player_id"] == "112"]
    assert {r["round_number"] for r in round_rows_b} == {1, 2}


def test_real_999_sentinel_pattern_is_not_counted_as_a_completed_round():
    """Regression test using the ACTUAL confirmed live pattern (see
    docs/SITE_STRUCTURE_TODO.md, gameCode=2026080002, playerCode=9777):
    a player who completes round 1 with a real score/rank, then shows
    data-rank="999" with data-score/data-totunderpar/data-todayunderpar
    all reset to "0" (placeholders) on round 2 — NOT literal "CUT"/"WD"/
    "DQ" text, which this site apparently never uses. made_cut must be
    0, the placeholder "0" round2 score must NOT be counted as a real
    completed round, and withdrawn/disqualified must stay 0 (unconfirmed
    from this endpoint, not guessed) while finish_position preserves the
    raw "999" so this group stays identifiable."""
    final_html = _row_html(1, "선수A", "111", r1="70", r2="67", r3="68", r4="71", total="276")
    round1_html = (
        _row_html(1, "선수A", "111", r1="70", today="-2")
        + _row_html(84, "선수B", "112", r1="75", today="3", underpar="3", hole="9")
    )
    round2_html = (
        _row_html(1, "선수A", "111", r1="70", r2="67", today="-3")
        + _row_html(999, "선수B", "112", r1="75", r2="0", today="0", underpar="0", total="0", hole="1")
    )
    round3_html = _row_html(1, "선수A", "111", r1="70", r2="67", r3="68", today="-1")
    client = FakeLeaderboardClient(
        {4: final_html, 1: round1_html, 2: round2_html, 3: round3_html}
    )

    rounds_data = collect_all_rounds_for_game(client, "G1", final_round=4)
    merged = merge_player_rows(rounds_data)
    _, player_event_rows, player_round_rows = build_rows("G1", 2026, "G1", merged, final_round=4)

    player_b = next(e for e in player_event_rows if e["player_id"] == "112")
    assert player_b["made_cut"] == 0
    assert player_b["withdrawn"] == 0
    assert player_b["disqualified"] == 0
    assert player_b["finish_position"] == "999"
    assert player_b["finish_position_numeric"] is None
    assert player_b["rounds_played"] == 1, "the placeholder round2 '0' must not count as a completed round"
    assert player_b["r1_score"] == 75
    assert player_b["r2_score"] is None
    assert player_b["total_score"] is None, "round2's placeholder data-score='0' must not be treated as real"

    round_rows_b = [r for r in player_round_rows if r["player_id"] == "112"]
    assert {r["round_number"] for r in round_rows_b} == {1}


def test_zero_valid_rounds_pattern_stores_real_zero_not_null():
    """Regression test using the ACTUAL confirmed live pattern for
    playerCode 9750 (see docs/SITE_STRUCTURE_TODO.md, gameCode=2026080002):
    a player who is ALREADY the "999" sentinel on round 1 itself, with
    data-round1score="0" — i.e. zero valid rounds anywhere, not one.
    rounds_played must be the real, confirmed 0 — NOT NULL, which would
    misread as "unknown" rather than "verified zero." made_cut must
    still be 0, and this player must not be silently dropped from
    player_event."""
    final_html = _row_html(1, "선수A", "111", r1="70", r2="67", r3="68", r4="71", total="276")
    round1_html = (
        _row_html(1, "선수A", "111", r1="70", today="-2")
        + _row_html(999, "선수C", "999999", r1="0", today="0", underpar="0", total="0", hole="1")
    )
    client = FakeLeaderboardClient({4: final_html, 1: round1_html})

    rounds_data = collect_all_rounds_for_game(client, "G1", final_round=4)
    merged = merge_player_rows(rounds_data)
    player_rows, player_event_rows, _ = build_rows("G1", 2026, "G1", merged, final_round=4)

    assert "999999" in {p["player_id"] for p in player_rows}, "must not be silently dropped"

    player_c = next(e for e in player_event_rows if e["player_id"] == "999999")
    assert player_c["made_cut"] == 0
    assert player_c["finish_position"] == "999"
    assert player_c["rounds_played"] == 0, "a confirmed zero round count must be stored as 0, not NULL"
    assert player_c["r1_score"] is None
    assert player_c["total_score"] is None
