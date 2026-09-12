from klpga.parsers.leaderboard_parser import parse_round_leaderboard_html

def test_explicit_wd_overrides_rank_999_sentinel_exact_case():
    html='''<li data-rank="999" data-name="성유진" data-inghole="1" data-score="0" data-round1score="69" data-round2score="74" data-round3score="0"><div _gameCode="2026090003" _playerCode="8881" _round="3"></div><table><tr><td>WD</td></tr></table></li>'''
    r=parse_round_leaderboard_html(html, game_code="2026090003", round_number=3)
    assert len(r)==1 and r[0].status=="WD" and r[0].rank_display=="999"
