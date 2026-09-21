from klpga.collectors.cmpro_shots import parse_cmpro_players, parse_cmpro_shots, validate_cmpro_hole

SAMPLE = """
<div _playerCode="10097" _playerName="김민선7"></div>
<div class="map-playertext" _shot="1"><h3>SHOT 1</h3><h4>비거리 261.4 yds / 러프 / 남은거리 265.2 yds</h4></div>
<div class="map-playertext" _shot="2"><h3>SHOT 2</h3><h4>비거리 166.0 yds / 페어웨이 / 남은거리 99.2 yds</h4></div>
<div class="map-playertext" _shot="3"><h3>SHOT 3</h3><h4>비거리 94.1 yds / 그린 / 남은거리 5.1 yds</h4></div>
<div class="map-playertext" _shot="4"><h3>SHOT 4</h3><h4>비거리 5.2 yds / 그린 / 남은거리 0.1 yds</h4></div>
<div class="map-playertext" _shot="5"><h3>SHOT 5</h3><h4>비거리 0.1 yds / 홀인 / 남은거리 0.0 yds</h4></div>
"""

def test_cmpro_sample_reconstructs_state_and_passes():
    shots = parse_cmpro_shots(SAMPLE)
    assert len(shots) == 5
    assert shots[0].start_lie == "티"
    assert shots[1].start_distance_yd == 265.2
    assert shots[1].start_lie == "러프"
    assert shots[-1].hole_out
    assert validate_cmpro_hole(shots) == "PASS"

def test_cmpro_player_code_and_name():
    assert parse_cmpro_players(SAMPLE) == {"10097": "김민선7"}

def test_cmpro_sequence_gap_fails():
    html = SAMPLE.replace("SHOT 2", "SHOT 7")
    assert validate_cmpro_hole(parse_cmpro_shots(html)) == "FAIL_SHOT_SEQUENCE"
