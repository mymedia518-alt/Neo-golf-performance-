# Technical debt log

## Cache large JSON fixtures in Player Intelligence provenance tests

- **File**: `tests/test_10097_player_intelligence_provenance_v10.py`
- **Found**: 2026-10-01, while diagnosing why a full-suite
  (`python -m pytest`, no filter) run was taking far longer than
  expected during the HITE JINRO round-pipeline refactor.
- **Confirmed pre-existing and unrelated to that refactor**: the file
  was last modified 2026-09-27 (`git log -1 -- tests/test_10097_...py`
  → commit `164d5b3`, "Player History V7-V14..."), 4 days before this
  session's `klpga.neo_win.hitejinro_round_pipeline` /
  `scripts/run_round_pipeline.py` work, and never imports any of
  `hitejinro_round_pipeline`, `hitejinro_round_page`, `run_round_pipeline`,
  or any of `scripts/196-203`.

### Current state

The file has 9 test functions. Every one of them calls a plain,
unmemoized helper:

```python
def _doc():
    return build_script.build()
```

`build_script.build()` → `_load_inputs()` → `build_master_dataset()`
loads and `json.loads()`-parses roughly 47 MB of JSON from disk
**every single call**, dominated by `historical_sg_warehouse_corrected.json`
alone at 34.9 MB (plus `empirical_sg_corrected_v2/player_event_series.json`
at 6.9 MB, `.../incremental_windows.json` at 5.0 MB, and several smaller
files). With 9 test functions each calling `_doc()` once, that's **9
full reloads and re-parses of the same ~47 MB** in one test file alone.

### Evidence (`py-spy dump --pid <pytest pid>` while the full suite was running)

```
Thread <pid> (active+gil): "MainThread"
    raw_decode (json/decoder.py:353)
    decode (json/decoder.py:337)
    loads (json/__init__.py:346)
    _load (build_10097_master_player_analysis.py:47)
    build_master_dataset (build_10097_master_player_analysis.py:67)
    _load_inputs (build_10097_player_intelligence_report.py:134)
    build (build_10097_player_intelligence_report.py:2333)
    _doc (tests/test_10097_player_intelligence_provenance_v10.py:48)
    test_computed_percentiles_and_counts_stay_derived (tests/test_10097_player_intelligence_provenance_v10.py:119)
    ...
```

This is genuine CPU-bound `json.loads` work (not a hang, not an
infinite loop, not a deadlock) — it is simply doing 9x more parsing
than the test assertions actually need, since none of the 9 tests
mutate the inputs between calls.

### Proposed fix (not applied in this commit — out of scope for the
round-pipeline refactor; this file is intentionally left untouched)

Convert `_doc()` into a cached fixture so the 9 tests in this file
share one parse instead of nine independent ones:

```python
import pytest

@pytest.fixture(scope="module")
def doc():
    return build_script.build()
```

(and update each `test_*` to take `doc` as a parameter instead of
calling `_doc()`), or equivalently wrap the existing free function with
`functools.lru_cache(maxsize=1)` if changing the test signatures is
undesirable. Either should cut this file's contribution to a full-suite
run by roughly 8/9.
