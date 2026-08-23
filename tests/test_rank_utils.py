from klpga.rank_utils import classify_model_scope, parse_rank, placement_flags


def test_parse_rank_numeric():
    assert parse_rank("1") == (1, True)
    assert parse_rank("T5") == (5, True)


def test_parse_rank_cut():
    assert parse_rank("CUT") == (None, False)
    assert parse_rank("MC") == (None, False)


def test_parse_rank_wd_dq_unknown():
    assert parse_rank("WD") == (None, None)
    assert parse_rank("DQ") == (None, None)


def test_parse_rank_none_or_garbage():
    assert parse_rank(None) == (None, None)
    assert parse_rank("") == (None, None)
    assert parse_rank("???") == (None, None)


def test_placement_flags():
    assert placement_flags(1) == (True, True, True, True)
    assert placement_flags(5) == (False, True, True, True)
    assert placement_flags(10) == (False, False, True, True)
    assert placement_flags(20) == (False, False, False, True)
    assert placement_flags(21) == (False, False, False, False)
    assert placement_flags(None) == (False, False, False, False)


def test_classify_model_scope():
    assert classify_model_scope("정규투어", "완료") is True
    assert classify_model_scope("이벤트", "완료") is False
    assert classify_model_scope("정규투어", "취소") is False
    assert classify_model_scope(None, "완료") is None
    assert classify_model_scope("정규투어", None) is None
