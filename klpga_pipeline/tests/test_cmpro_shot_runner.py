import sys
import sqlite3
import pytest
from scripts.collect_cmpro_shots import SCHEMA,collect_hole,is_bad_status
SAMPLE='''<div class="map-playertext">SHOT 1 비거리 200.0 yds / 그린 / 남은거리 10.0 yds</div><div class="map-playertext">SHOT 2 비거리 10.0 yds / 홀인 / 남은거리 0.0 yds</div>'''
def test_collect_hole_is_idempotent_and_resume_skips_pass(tmp_path,monkeypatch):
 import scripts.collect_cmpro_shots as m
 monkeypatch.setattr(m,"fetch_player_info_html",lambda *a,**k:SAMPLE)
 c=sqlite3.connect(tmp_path/"x.sqlite");c.executescript(SCHEMA)
 assert collect_hole(object(),c,"G","P","선수",4,18)==("PASS",2)
 assert collect_hole(object(),c,"G","P","선수",4,18)==("SKIP_PASS",0)
 assert c.execute("select count(*) from shot_event").fetchone()[0]==2


def test_player_score_scope_excludes_unplayed_rounds():
 import scripts.collect_cmpro_shots as m
 html='<div _round="1"><span _hole="1">4</span><span _hole="18">5</span></div><div _round="2"><span _hole="1">4</span></div>'
 assert m.parse_cmpro_played_holes(html)=={1:[1,18],2:[1]}


# ---------------------------------------------------------------
# NEO CMPRO FULL COLLECTION QA fix (2026-09-21): a player whose real,
# fetched official playerScore fragment carries zero round/hole
# entries must classify as NOT_APPLICABLE, not as a QA failure -- and
# this must hold for ANY player code the real data produces, never a
# hardcoded list of specific players.
# ---------------------------------------------------------------

def test_is_bad_status_allows_pass_skip_and_not_applicable():
 assert is_bad_status("PASS") is False
 assert is_bad_status("SKIP_PASS") is False
 assert is_bad_status("NOT_APPLICABLE") is False


def test_is_bad_status_flags_real_qa_failures():
 assert is_bad_status("EMPTY") is True
 assert is_bad_status("FAIL_SHOT_SEQUENCE") is True
 assert is_bad_status("FAIL_STATE_LINK") is True
 assert is_bad_status("WARN_NOT_HOLED") is True


def test_main_treats_zero_played_holes_as_not_applicable_for_arbitrary_player_codes(tmp_path,monkeypatch):
 """Two synthetic player codes never seen elsewhere in this codebase --
 proves the NOT_APPLICABLE classification is driven purely by the
 (mocked) real playerScore fetch result, not by player identity."""
 import scripts.collect_cmpro_shots as m
 players={"ZQ001":"테스트선수A","ZQ002":"테스트선수B"}
 monkeypatch.setattr(m,"fetch_cmpro_leaderboard_html",lambda *a,**k:"")
 monkeypatch.setattr(m,"parse_cmpro_players",lambda html:players)
 def fake_score_html(client,game,code,use_cache=True):
  if code=="ZQ001":
   return '<div _round="4"><span _hole="18">4</span></div>'
  return ""  # real fetched fragment for ZQ002 carries no round/hole markup
 monkeypatch.setattr(m,"fetch_player_score_html",fake_score_html)
 monkeypatch.setattr(m,"fetch_player_info_html",lambda *a,**k:SAMPLE)
 out=tmp_path/"zq.sqlite"
 monkeypatch.setattr(sys,"argv",["collect_cmpro_shots.py","--game","TESTGAME","--out",str(out)])
 m.main()  # must not raise SystemExit
 conn=sqlite3.connect(out)
 assert conn.execute("select qa_status from hole_audit where player_code='ZQ001'").fetchone()==("PASS",)
 assert conn.execute("select count(*) from hole_audit where player_code='ZQ002'").fetchone()[0]==0


def test_main_still_fails_on_a_real_qa_failure_not_masked_by_the_fix(tmp_path,monkeypatch):
 import scripts.collect_cmpro_shots as m
 players={"ZQ003":"테스트선수C"}
 monkeypatch.setattr(m,"fetch_cmpro_leaderboard_html",lambda *a,**k:"")
 monkeypatch.setattr(m,"parse_cmpro_players",lambda html:players)
 monkeypatch.setattr(m,"fetch_player_score_html",lambda *a,**k:'<div _round="1"><span _hole="1">4</span></div>')
 monkeypatch.setattr(m,"fetch_player_info_html",lambda *a,**k:"<html>no shot markers here</html>")
 out=tmp_path/"zq3.sqlite"
 monkeypatch.setattr(sys,"argv",["collect_cmpro_shots.py","--game","TESTGAME","--out",str(out)])
 with pytest.raises(SystemExit) as exc:
  m.main()
 assert exc.value.code==2
