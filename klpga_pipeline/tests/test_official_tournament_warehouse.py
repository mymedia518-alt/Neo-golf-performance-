import pytest
from klpga.official_tournament_warehouse import freeze_source, build_round_exposure, freeze_tournament_snapshot

def test_raw_sha_and_idempotency(tmp_path):
    a=freeze_source(game_code="20260001",source_type="scoreRecord",source_url="u",raw=b"x",out_dir=tmp_path)
    b=freeze_source(game_code="20260001",source_type="scoreRecord",source_url="u",raw=b"x",out_dir=tmp_path)
    assert a["sha256"]==b["sha256"] and a["path"]==b["path"]
def test_nulls_preserved_and_identity_keyed():
    x=build_round_exposure([{"playerCode":"1","round":1,"round_score":None}],game_code="G")
    assert x[0]["round_score"] is None
    with pytest.raises(ValueError): build_round_exposure([{"playerCode":"1","round":1},{"playerCode":"1","round":1}],game_code="G")
def test_snapshot_has_no_model_fields(tmp_path):
    _,d=freeze_tournament_snapshot(game_code="G",tournament={},entries=[],rounds=[],courses=[],provenance=[],out_dir=tmp_path)
    assert d["schema"]=="OFFICIAL_TOURNAMENT_WAREHOUSE_V1" and "neo_score" not in d
