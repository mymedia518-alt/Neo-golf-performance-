"""P0 MODEL SAFETY PATCH -- LIVE PROBABILITY PUBLICATION BLOCK.

Independent Red Team review confirmed the R1 live simulation
(klpga.neo_win.r1_live_probability) has a HIGH-confidence defect:
partial-round state is ignored and the expected-round-score baseline
mixes field-relative, tournament-cumulative Strokes-Gained figures
into what is presented as a par-relative single-round expectation.
Until a corrected V2 model is built and independently validated,
scripts/84_build_ok_open_pre_website_candidate.py must never publish
any output derived from that simulation -- proven here against the
REAL current build (which is BLOCKED) and against a synthetic
VALIDATED scenario (proving the gate is a real conditional, not a
hardcoded removal that happens to look right today)."""
from pathlib import Path

import importlib.util

SPEC = importlib.util.spec_from_file_location(
    "ok_open_builder", Path(__file__).parents[1] / "scripts" / "84_build_ok_open_pre_website_candidate.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

BLOCKED_HEADER_MARKERS = ("<th>Cut%</th>", "<th>Top20%</th>", "<th>Top10%</th>", "<th>Top5%</th>", "<th>Win%</th>", "<th>PRE 대비 Win Δ</th>")
BLOCKED_SECTION_MARKERS = ("<h2>NEO Movers", "NEO 예상 컷 (분포)")
FACTUAL_HEADERS = ("<th>순위</th>", "<th>선수</th>", "<th>현재스코어</th>", "<th>완료홀</th>", "<th>오늘스코어</th>", "<th>선두와 타수차</th>", "<th>상태</th>")


def test_model_is_currently_blocked():
    from klpga.neo_win.r1_live_probability import LIVE_PROBABILITY_MODEL_STATUS

    assert LIVE_PROBABILITY_MODEL_STATUS == "BLOCKED"
    assert builder.MODEL_VALIDATED_FOR_PUBLICATION is False


def test_real_build_omits_every_blocked_header_and_section():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    for marker in BLOCKED_HEADER_MARKERS + BLOCKED_SECTION_MARKERS:
        assert marker not in html, f"{marker} must not appear while the model is blocked"


def test_real_build_never_shows_the_actual_published_probability_values():
    # The specific numbers that were live before this patch -- proves
    # this is a real removal, not merely hiding the column label.
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    for value in ("36.9%", "13.7%", "16.4%"):
        assert value not in html


def test_real_build_keeps_every_factual_column():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    for header in FACTUAL_HEADERS:
        assert header in html


def test_real_build_omits_the_blocked_note_from_the_page():
    # The long "비공개 처리됩니다" explanatory paragraph is deliberately
    # NOT shown to the public -- the absent probability columns already
    # say everything there is to say; MODEL_BLOCKED_NOTE stays defined
    # in the module as documented rationale, it is just never rendered.
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert builder.MODEL_BLOCKED_NOTE not in html
    assert "비공개 처리됩니다" not in html


def test_real_build_row_never_shows_zero_percent_or_a_fabricated_placeholder():
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    # A withheld metric must be OMITTED, never rendered as 0% (which
    # would misrepresent "not published" as "computed to be zero").
    idx = html.index("<span class='player'>양효진</span>")
    row_end = html.index("</tr>", idx)
    row_tail = html[idx:row_end]
    assert "0.0%" not in row_tail
    assert "0%" not in row_tail


def test_affiliation_and_tied_leaders_are_unaffected_by_the_model_block():
    # This patch must not regress the two most recent, unrelated fixes.
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    assert "<span class='player'>양효진</span><span class='sponsor'>대보건설</span>" in html
    assert "양효진, 이예원, 신다인" in html  # 3-way tie still fully shown
    idx = html.find("오수민 0809(A)")
    assert idx != -1
    assert "대방건설" not in html[idx : idx + 400]


def test_gate_is_a_real_conditional_not_a_hardcoded_removal(monkeypatch):
    # Prove the omission is driven by MODEL_VALIDATED_FOR_PUBLICATION,
    # not baked permanently into the template -- flipping it back on
    # (as a future V2-validated model would) must restore the columns.
    monkeypatch.setattr(builder, "MODEL_VALIDATED_FOR_PUBLICATION", True)
    out = builder.build()
    html = (out / "tournaments/2026/ok-savings-bank-open/r1/index.html").read_text(encoding="utf-8")
    for marker in BLOCKED_HEADER_MARKERS + BLOCKED_SECTION_MARKERS:
        assert marker in html
    assert builder.MODEL_BLOCKED_NOTE not in html
