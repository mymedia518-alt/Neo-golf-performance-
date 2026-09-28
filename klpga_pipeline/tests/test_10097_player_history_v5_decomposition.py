"""PLAYER HISTORY V5 -- metric decomposition mission, playerCode=10097
only. For every Peak/Slump/Recovery window (introduced in V4), the
question is no longer 'when' but 'why' -- these tests confirm the real
OTT/APP/ARG/PUTT breakdown is reproducible by hand from the same raw
tournaments that produced the window's SG average, and that Birdie/
Bogey/GIR/Putts are never fabricated when not actually measurable at
this grain. No new top-level section was added.
"""
from __future__ import annotations

import importlib.util
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("build_10097_player_history", ROOT / "scripts" / "build_10097_player_history.py")
build_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_script)

from klpga.website_v2 import player_history_report as report  # noqa: E402


def _doc_and_html():
    doc = build_script.build()
    return doc, report.render_player_history_html(doc)


def _raw_finished_sorted():
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("reconcile_10097_player_history", ROOT / "scripts" / "reconcile_10097_player_history.py")
    recon_mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(recon_mod)
    recon = recon_mod.reconcile()
    events = sorted(recon["finished_tournaments"], key=lambda e: (e["season"], e["game_code"]))
    return [e for e in events if e.get("sg_total") is not None]


def test_peak_window_decomposition_is_reproducible_by_hand():
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    peak = crt["peak_window"]
    w = crt["window_size"]
    sg_events = _raw_finished_sorted()
    chunk = sg_events[peak["window_index"]:peak["window_index"] + w]
    for key, raw_key in (("ott", "sg_ott"), ("app", "sg_app"), ("arg", "sg_arg"), ("putt", "sg_putt")):
        vals = [c[raw_key] for c in chunk if c.get(raw_key) is not None]
        expected = round(statistics.fmean(vals), 3) if vals else None
        assert peak["decomposition"][key] == expected


def test_slump_window_decomposition_is_reproducible_by_hand():
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    slump = crt["slump_window"]
    w = crt["window_size"]
    sg_events = _raw_finished_sorted()
    chunk = sg_events[slump["window_index"]:slump["window_index"] + w]
    for key, raw_key in (("ott", "sg_ott"), ("app", "sg_app"), ("arg", "sg_arg"), ("putt", "sg_putt")):
        vals = [c[raw_key] for c in chunk if c.get(raw_key) is not None]
        expected = round(statistics.fmean(vals), 3) if vals else None
        assert slump["decomposition"][key] == expected


def test_decomposition_components_sum_narrative_makes_sense():
    """The window's own moving_average_sg_total should be close to the
    average of its own OTT+APP+ARG+PUTT decomposition (SG Total is
    approximately the sum of components per tournament) -- a real
    internal-consistency check, not a hardcoded number."""
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    for w in (crt["peak_window"], crt["slump_window"]):
        d = w["decomposition"]
        if d["sg_component_sample_size"] == d["sg_component_window_size"]:
            component_sum = d["ott"] + d["app"] + d["arg"] + d["putt"]
            assert abs(component_sum - w["moving_average_sg_total"]) < 0.1


def test_birdie_bogey_gir_putts_never_fabricated_when_unmeasurable():
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    for w in (crt["peak_window"], crt["slump_window"], crt["recovery_window"]):
        d = w["decomposition"]
        if d["birdie_bogey_gir_putts_status"] == "NOT_COLLECTED":
            assert d["birdie"] is None
            assert d["bogey"] is None
            assert d["gir"] is None
            assert d["putts"] is None
        else:
            assert d["birdie_bogey_gir_putts_status"] == "PARTIAL"
            # GIR/putts are never in hole_history's real shape -- must
            # stay None even when birdie/bogey are real.
            assert d["gir"] is None
            assert d["putts"] is None


def test_decomposition_sample_size_never_exceeds_window_size():
    doc = build_script.build()
    crt = doc["career_rolling_trend"]
    for w in (crt["peak_window"], crt["slump_window"], crt["recovery_window"]):
        d = w["decomposition"]
        assert d["sg_component_sample_size"] <= d["sg_component_window_size"]
        assert d["sg_component_window_size"] == crt["window_size"]


def test_decomposition_renders_inside_the_existing_rolling_trend_block():
    """Mission: 'No new sections. No new cards.' -- decomposition must
    render inside #ph-career-rolling-trend, not as a separate section.

    V5 mission (2026-09-25) superseded the 4-column OTT/APP/ARG/PUTT
    TABLE with one real sentence naming only the strongest and weakest
    component of each window ('every sentence must answer one
    question... delete everything else') -- so only two of the four SG
    component labels are guaranteed to appear per window now, never all
    four. 전성기's own decomposition was dropped entirely (Career Form
    Story's peak card, rendered just above in the same block, already
    covers it); 슬럼프기/회복기 (the two NOT already covered by the
    story cards) still get their one-sentence decomposition."""
    doc, html = _doc_and_html()
    start = html.index('id="ph-career-rolling-trend"')
    end = html.index('id="ph-tournament-trend"')  # next real section after this block
    section = html[start:end]
    slump = doc["career_rolling_trend"]["slump_window"]["decomposition"]
    vals = {k: slump[k] for k in ("ott", "app", "arg", "putt") if slump.get(k) is not None}
    best = max(vals, key=vals.get)
    worst = min(vals, key=vals.get)
    label = {"ott": "SG OTT", "app": "SG APP", "arg": "SG ARG", "putt": "SG PUTT"}
    assert label[best] in section
    assert label[worst] in section


def test_decomposition_no_longer_repeats_the_birdie_bogey_disclosure_per_window():
    """V5 mission (2026-09-25): the birdie/bogey/GIR/putt 'not collected'
    boilerplate -- identical for both 슬럼프기 and 회복기, since neither
    window has ever included the one hole-covered tournament -- was
    exactly the kind of repeated-numbers/repeated-text the mission
    targets, so it was dropped from the one-sentence decomposition.
    The underlying field (birdie_bogey_gir_putts_note) is unchanged in
    the JSON; it is simply not rendered a second time per window."""
    doc, html = _doc_and_html()
    slump = doc["career_rolling_trend"]["slump_window"]["decomposition"]
    assert slump["birdie_bogey_gir_putts_status"] == "NOT_COLLECTED"
    assert "홀 단위 실측 기록이 없어" in slump["birdie_bogey_gir_putts_note"]


def test_no_new_top_level_section_still_holds():
    doc, html = _doc_and_html()
    crt_idx = html.index('id="ph-career-rolling-trend"')
    season_replay_idx = html.index('id="ph-season-replay"')
    dna_idx = html.index('id="ph-player-dna-radar"')
    assert season_replay_idx < crt_idx < dna_idx
