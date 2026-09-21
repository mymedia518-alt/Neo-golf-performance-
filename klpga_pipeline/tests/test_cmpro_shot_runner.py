import sqlite3
from scripts.collect_cmpro_shots import SCHEMA,collect_hole
SAMPLE='''<div class="map-playertext">SHOT 1 비거리 200.0 yds / 그린 / 남은거리 10.0 yds</div><div class="map-playertext">SHOT 2 비거리 10.0 yds / 홀인 / 남은거리 0.0 yds</div>'''
def test_collect_hole_is_idempotent_and_resume_skips_pass(tmp_path,monkeypatch):
 import scripts.collect_cmpro_shots as m
 monkeypatch.setattr(m,"fetch_player_info_html",lambda *a,**k:SAMPLE)
 c=sqlite3.connect(tmp_path/"x.sqlite");c.executescript(SCHEMA)
 assert collect_hole(object(),c,"G","P","선수",4,18)==("PASS",2)
 assert collect_hole(object(),c,"G","P","선수",4,18)==("SKIP_PASS",0)
 assert c.execute("select count(*) from shot_event").fetchone()[0]==2
