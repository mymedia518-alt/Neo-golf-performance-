"""R2 PUBLIC TABLE COLUMN FIX (fix/kb-r2-official-cut-gate-20260911):
regression proving the real, committed R2 page carries the exact
required PUBLIC column contract:

    순위 | 선수 | 합계 | 2R | Top20 | Top10 | Top5 | 우승

PROBABILITY COLUMN ORDER HOTFIX (base dd4640f): the probability columns
were reordered widest-population-first (TOP20, TOP10, TOP5), WIN still
last -- desktop and mobile share this identical order since each `<td>`
carries its own `data-label` and moves as one unit (see r2_real_page.py's
own comment at the row-building call site).

SG TOTAL/OTT/APP/ARG/PUTT are removed from this PUBLIC table (WIN moved
to the last column) -- SG data itself is NOT deleted from any artifact,
pipeline, or model input; see r2_sg_pipeline.py and its own tests,
which are completely untouched by this fix. Every check here reads the
REAL, committed docs/tournaments/2026/2026090003/r2/index.html
directly, never a synthetic fixture standing in for it (test_r2_real_
page.py already covers the synthetic-renderer contract)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
REAL_PAGE_PATH = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090003" / "r2" / "index.html"

REQUIRED_PUBLIC_COLUMNS = ["순위", "선수", "합계", "2R", "Top20", "Top10", "Top5", "우승"]
FORBIDDEN_SG_LABELS = ["SG TOTAL", "SG OTT", "SG APP", "SG ARG", "SG PUTT"]


def _real_html() -> str:
    assert REAL_PAGE_PATH.is_file(), f"real R2 page not found at {REAL_PAGE_PATH}"
    return REAL_PAGE_PATH.read_text(encoding="utf-8")


def _rows(html: str) -> list[str]:
    body = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    return re.findall(r"<tr data-player-id='[^']+'>(?:(?!</tr>).)*</tr>", body)


def test_real_page_header_carries_exactly_the_8_required_public_columns_in_order():
    html = _real_html()
    header = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL).group(1)
    labels = re.findall(r"<th>([^<]*)</th>", header)
    assert labels == REQUIRED_PUBLIC_COLUMNS


def test_real_page_has_no_sg_column_anywhere():
    html = _real_html()
    for label in FORBIDDEN_SG_LABELS:
        assert label not in html, f"forbidden SG label {label!r} still present in the public R2 page"


def test_real_page_every_row_has_exactly_8_cells_in_the_required_order():
    html = _real_html()
    rows = _rows(html)
    assert rows, "no rendered rows found"
    for row in rows:
        cell_labels = re.findall(r"data-label='([^']+)'", row)
        assert cell_labels == REQUIRED_PUBLIC_COLUMNS, f"row cell order diverges: {cell_labels}"


def test_real_page_win_is_the_last_cell_in_every_row():
    html = _real_html()
    for row in _rows(html):
        cell_labels = re.findall(r"data-label='([^']+)'", row)
        assert cell_labels[-1] == "우승"


def test_real_page_every_percent_value_keeps_the_percent_sign_on_the_same_text_node():
    """'Keep each probability value and % on one line': the % must
    never be split into its own tag/node -- confirms the DOM never
    gives the browser a place to break between the number and %.

    PROBABILITY FORMATTER HOTFIX (base fb4f165): a cell's text can now
    also be the exact-zero "0%" or the near-zero "<0.1%" contract (see
    klpga.website_v2.probability_format) -- both stay on one text node
    just like the one-decimal case, so the underlying guarantee this
    test checks is unchanged, only the accepted text shapes widen. The
    extraction itself must match up to the literal `</td>`, not the
    next `<`, because "<0.1%" itself starts with `<`."""
    html = _real_html()
    win_cells = re.findall(r"<td class='win' data-label='(?:Top5|Top10|Top20|우승)'>(.*?)</td>", html)
    assert win_cells, "no probability cells found"
    for cell_text in win_cells:
        if cell_text == "—":
            continue
        assert re.fullmatch(r"0%|<0\.1%|[+-]?\d+\.\d%", cell_text), f"unexpected probability cell text: {cell_text!r}"


def test_real_page_official_rank_total_2r_unchanged_by_this_fix():
    """The column reorder/removal must never touch official
    rank/합계/2R values -- cross-checked against the same rendered-
    output gate Task L wired into publication."""
    import json

    from klpga.neo_win.r2_rendered_output_gate import validate_r2_rendered_output

    freeze = json.loads((ROOT / "content" / "website_v2" / "2026090003_R2_FROZEN_EVIDENCE.json").read_text(encoding="utf-8"))
    validate_r2_rendered_output(_real_html(), freeze)  # must not raise


def test_real_page_stage_nav_still_intact_after_this_fix():
    html = _real_html()
    assert 'href="/tournaments/2026/2026090003/pre/"' in html
    assert 'href="/tournaments/2026/2026090003/r1/"' in html
    assert 'href="/tournaments/2026/2026090003/r2/" aria-current="page"' in html
    assert html.count('class="stage-nav__disabled"') == 2  # R3 + FINAL only


def test_real_page_win_probabilities_unchanged_from_the_frozen_forecast():
    """The column fix is presentation-only -- every rendered probability
    must still trace exactly to the frozen forecast artifact (never
    recomputed/recalibrated by this task). PROBABILITY FORMATTER HOTFIX
    (base fb4f165): expected display text now goes through the SAME
    shared formatter the renderer itself uses, rather than a locally
    duplicated `.1f%` rule -- keeps this real-data regression honest
    against whatever the real formatter contract currently is."""
    import json

    from klpga.website_v2.probability_format import format_public_probability

    forecast = json.loads((ROOT / "content" / "website_v2" / "2026090003_POST_R2_FINAL_FORECAST.json").read_text(encoding="utf-8"))
    html = _real_html()
    rows = _rows(html)

    def cell(row: str, label: str) -> str:
        m = re.search(rf"data-label='{label}'[^>]*>(.*?)</td>", row)
        return m.group(1) if m else None

    rendered_by_id = {}
    for row in rows:
        pid_m = re.search(r"data-player-id='([^']+)'", row)
        rendered_by_id[pid_m.group(1)] = {
            "win": cell(row, "우승"), "top5": cell(row, "Top5"),
            "top10": cell(row, "Top10"), "top20": cell(row, "Top20"),
        }

    def expected_pct(v):
        return "—" if v is None else format_public_probability(v)

    checked = 0
    for r in forecast["records"]:
        pid = str(r["player_id"])
        disp = rendered_by_id.get(pid)
        assert disp is not None, f"forecasted player {pid} missing from rendered page"
        checked += 1
        assert disp["win"] == expected_pct(r["win_pct"])
        assert disp["top5"] == expected_pct(r["top5_pct"])
        assert disp["top10"] == expected_pct(r["top10_pct"])
        assert disp["top20"] == expected_pct(r["top20_pct"])
    assert checked == len(forecast["records"])
