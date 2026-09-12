import json
from pathlib import Path

P=Path(__file__).resolve().parents[1]/'evidence/NEO_EXPOSURE_GATE_DECOMPOSITION_V1.json'
def test_old_gate_reproducibility_and_universe():
 d=json.loads(P.read_text(encoding='utf-8')); assert d['old_gate_reproduction']['V1']['n']==104; assert d['old_gate_reproduction']['V2B']['n']==105; assert d['old_gate_reproduction']['reproducibility']=='PASS'
def test_sign_convention_and_score_rank_distinction():
 d=json.loads(P.read_text(encoding='utf-8')); assert d['old_gate_reproduction']['V1']['spearman_rounds_vs_rank']<0; assert d['underlying_score_test']=='NOT_EVALUABLE'
def test_permutation_configuration_is_frozen():
 d=json.loads(P.read_text(encoding='utf-8')); assert d['permutation']['seed']==20260912; assert d['permutation']['permutations']==1000
