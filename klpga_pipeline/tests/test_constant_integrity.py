"""Adversarial tests for the value-only LIVE publication boundary.

The small model/result/template below are synthetic test fixtures only.
They are not NEO models, official data, or publishable baseline contracts.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from klpga.website_v2.constant_integrity import (
    ConstantIntegrityError, bind_snapshot_values, digest, inject_values,
    validate_constants, validate_live_tree, validate_snapshot_provenance,
)


@pytest.fixture
def bundle(tmp_path):
    template = (b'<!doctype html>\r\n<html><head><link rel="stylesheet" href="/assets/site.css">'
                b'</head><body><nav><a href="/">NEO</a></nav><p class="player">Player</p>'
                b'<p class="sponsor">Verified sponsor</p><time id="stamp">2026-09-06T05:00:00Z</time>'
                b'<table><thead><tr><th id="sg-label">SG</th><th id="win-label">Win</th>'
                b'<th id="top5-label">Top5</th><th id="top10-label">Top10</th>'
                b'<th id="top20-label">Top20</th></tr></thead><tbody><tr>'
                b'<td id="sg">1.0</td><td id="win">50.0%</td><td id="top5">80.0%</td>'
                b'<td id="top10">90.0%</td><td id="top20">99.0%</td>'
                b'</tr></tbody></table></body></html>\r\n')
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'assets/site.css').write_bytes(b'body { color: black; }')
    (tmp_path / 'model.py').write_bytes(b'# test dependency only\n')
    contract = {
        'schema_version': 1, 'baseline_commit': 'TEST_ONLY',
        'template_sha256': digest(template), 'model_version': 'TEST_ONLY',
        'model_files': {'model.py': digest((tmp_path / 'model.py').read_bytes())},
        'asset_files': {'assets/site.css': digest((tmp_path / 'assets/site.css').read_bytes())},
        'features': {'sponsor': '.sponsor', 'navigation': 'nav',
                     **{k: f'#{k}-label' for k in ('sg', 'win', 'top5', 'top10', 'top20')}},
        'slots': [{'key': k, 'field': k, 'selector': '#'+k, 'player_id': '1',
                   'format': '{:.1f}' if k == 'sg' else '{:.1f}%'}
                  for k in ('sg', 'win', 'top5', 'top10', 'top20')]
                 + [{'key': 'stamp', 'field': 'snapshot_timestamp', 'selector': '#stamp'}],
    }
    snapshot = {'game_code': 'test', 'round': 3, 'collected_at': '2026-09-06T05:01:00Z',
                'player_table': [{'player_code': '1'}]}
    raw = json.dumps(snapshot).encode()
    result = {'validation_status': 'VALIDATED', 'game_code': 'test', 'round': 3,
              'model_version': 'TEST_ONLY', 'model_files': contract['model_files'],
              'input_snapshot_sha256': digest(raw), 'input_snapshot_timestamp': snapshot['collected_at'],
              'n_simulations': 10, 'records': [{'player_id': '1', 'sg': 2.0, 'win_pct': 100.,
                                              'top5_pct': 100., 'top10_pct': 100., 'top20_pct': 100.}]}
    return tmp_path, template, contract, raw, snapshot, result


def candidate(bundle):
    root, template, contract, raw, snapshot, result = bundle
    return inject_values(template, contract, bind_snapshot_values(snapshot, result, contract))


def check(bundle, output):
    root, template, contract, *_ = bundle
    return validate_constants(template=template, candidate=output, contract=contract, asset_root=root, model_root=root)


def test_variable_injection_preserves_original_bytes_and_crlf(bundle):
    output = candidate(bundle)
    assert check(bundle, output)['constant_integrity'] == 'PASS'
    assert output.count(b'\r\n') == bundle[1].count(b'\r\n')
    assert b'<p class="sponsor">Verified sponsor</p>' in output
    assert b'<td id="win">100.0%</td>' in output


@pytest.mark.parametrize('label', ['SG', 'Win', 'Top5', 'Top10', 'Top20'])
def test_removing_probability_or_sg_label_hard_fails(bundle, label):
    output = candidate(bundle).replace(('>'+label+'</th>').encode(), b'>Removed</th>')
    with pytest.raises(ConstantIntegrityError):
        check(bundle, output)


@pytest.mark.parametrize('old,new', [
    (b'Verified sponsor', b'Different sponsor'),
    (b'href="/"', b'href="/other"'),
    (b'NEO</a>', b'OTHER</a>'),
    (b'<table>', b'<table class="redesigned">'),
    (b'\r\n', b'\n'),
    (b'<p class="sponsor">Verified sponsor</p>', b''),
])
def test_constant_mutations_hard_fail(bundle, old, new):
    with pytest.raises(ConstantIntegrityError):
        check(bundle, candidate(bundle).replace(old, new))


@pytest.mark.parametrize('path', ['assets/site.css', 'model.py'])
def test_changed_css_or_calculation_code_hard_fails(bundle, path):
    (bundle[0] / path).write_bytes(b'changed')
    with pytest.raises(ConstantIntegrityError):
        check(bundle, candidate(bundle))


def test_sponsor_cannot_be_misdeclared_as_variable(bundle):
    bundle[2]['slots'].append({'key': 'bad', 'field': 'sg', 'selector': '.sponsor'})
    with pytest.raises(ConstantIntegrityError, match='CONSTANT identity'):
        inject_values(bundle[1], bundle[2], {})


def test_html_injection_cannot_hide_inside_variable(bundle):
    values = bind_snapshot_values(bundle[4], bundle[5], bundle[2])
    values['win'] = '<script>bad()</script>'
    with pytest.raises(ConstantIntegrityError, match='non-value'):
        inject_values(bundle[1], bundle[2], values)


@pytest.mark.parametrize('field,value', [
    ('input_snapshot_sha256', 'old'), ('input_snapshot_timestamp', 'old'),
    ('model_version', 'unreviewed'), ('model_files', {}),
    ('validation_status', 'BLOCKED'), ('n_simulations', 0), ('round', 2),
])
def test_stale_or_unvalidated_probability_provenance_hard_fails(bundle, field, value):
    result = deepcopy(bundle[5]); result[field] = value
    with pytest.raises(ConstantIntegrityError):
        validate_snapshot_provenance(snapshot_bytes=bundle[3], snapshot=bundle[4], model_result=result, contract=bundle[2])


def test_same_snapshot_provenance_passes(bundle):
    validate_snapshot_provenance(snapshot_bytes=bundle[3], snapshot=bundle[4], model_result=bundle[5], contract=bundle[2])


def test_missing_contract_blocks_before_production_write(bundle):
    root = bundle[0]
    production = root / 'production'; production.mkdir()
    live = production / 'index.html'; live.write_bytes(b'<main data-current-round="3">old</main>')
    before = live.read_bytes()
    with pytest.raises(ConstantIntegrityError, match='contract is missing'):
        validate_live_tree(candidate_root=root, production_root=production,
                           contract_path=root / 'missing.json', repository_root=root)
    assert live.read_bytes() == before


def test_promotion_checks_constant_guard_before_any_copy(bundle, monkeypatch):
    root = bundle[0]
    path = Path(__file__).parents[1] / 'scripts/94_promote_top120_to_production.py'
    spec = importlib.util.spec_from_file_location('promotion_constant_test', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    production = root / 'production'; production.mkdir()
    live = production / 'index.html'; live.write_bytes(b'<main data-current-round="3">old</main>')
    monkeypatch.setattr(module, 'SOURCE', root)
    monkeypatch.setattr(module, 'DEST', production)
    monkeypatch.setattr(module, 'CONTENT', root / 'no-contract')
    with pytest.raises(module.PromotionError, match='contract is missing'):
        module.promote()
    assert b'old' in live.read_bytes()


def test_baseline_hash_cannot_be_silently_replaced(bundle):
    bundle[2]['template_sha256'] = 'different'
    with pytest.raises(ConstantIntegrityError, match='template hash'):
        inject_values(bundle[1], bundle[2], {})
