"""Build the public KB 2026090003 R1 page from the frozen
2026090003_R1_5PROB_FROZEN_V1.json and the frozen official R1 result
evidence, mirroring the live PRE page's exact HTML structure/CSS
classes (docs/tournaments/2026/2026090003/pre/index.html) so R1 looks
and behaves consistently with it. Also updates the PRE page's own
stage-nav to link forward to R1 (was a disabled placeholder), refreshes
both pages' shared header/footer via inject_global_navigation() (so a
global_navigation.py change always reaches these two already-baked
static pages, not just future full-site rebuilds), and adds the
round-update-status line to each page's hero.

PUBLIC UI / NAVIGATION PATCH (NEO PUBLIC UI CORRECTION): the R1 table
uses the immutable public column order and probability order, keeps
public copy minimal (no internal/developer terminology), and the
"대회" top-nav link is overridden (via global_navigation's nav_overrides,
never the shared default) to KB's current published stage.

R1 TABLE: ordered by OFFICIAL R1 RANKING (never NEO probability),
preserving genuine tied ranks exactly as the official evidence encodes
them (repeated rank values -> "T<rank>"). All 118 R1-active players are
always shown, including the 7 with no NEO_V1_score history -- for
those, the 5 prediction columns render "--" (never dropped from the
leaderboard, never a fabricated probability).

SPONSOR INVARIANT: every displayed player name carries a sponsor slot
immediately below it (klpga.website_v2.player_identity.render_player_
identity), sourced ONLY from KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V2
.json's verified_official sponsors -- never guessed. A player without a
verified sponsor gets an empty (but present) sponsor slot.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root (docs/ lives here, not under klpga_pipeline/)
PIPELINE_ROOT = Path(__file__).resolve().parents[1]
CONTENT = PIPELINE_ROOT / "content" / "website_v2"
GAME_CODE = "2026090003"
PRE_PAGE = ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html"
R1_PAGE = ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html"

sys.path.insert(0, str(PIPELINE_ROOT / "src"))
from klpga.website_v2.global_navigation import inject_global_navigation  # noqa: E402
from klpga.website_v2.player_identity import render_player_identity  # noqa: E402
from klpga.website_v2.home_ownership_guard import (  # noqa: E402
    CURRENT_TOURNAMENT_OWNER, TOP120_OWNER, assert_home_write_allowed, embed_owner, extract_owner,
)

DOCS_INDEX = ROOT / "docs" / "index.html"
ARCHIVE_INDEX = ROOT / "docs_internal_archive" / "index.html"

# PUBLICATION FIX (KB 2026090003): "대회" routes to KB's current
# published stage (R1) for THIS page only -- never a change to
# global_navigation.GLOBAL_NAV_ITEMS's shared default, which stays the
# generic /tournaments/ hub for every other build/page/test fixture.
NAV_OVERRIDES = {"tournaments": f"/tournaments/2026/{GAME_CODE}/r1/"}


def load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def _to_par_display(raw: str) -> str:
    n = int(raw)
    if n == 0:
        return "E"
    return f"+{n}" if n > 0 else str(n)


def build_r1_page() -> str:
    freeze = load(f"{GAME_CODE}_R1_5PROB_FROZEN_V1.json")
    official = load(f"NEO_KB_{GAME_CODE}_R1_OFFICIAL_RESULT_EVIDENCE_V1.json")
    sponsor_audit = load("KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V2.json")
    sponsor_by_id = {r["player_id"]: r["sponsor"] for r in sponsor_audit["newly_recovered_sponsors"]}
    pre_frozen = load(f"{GAME_CODE}_PRE_5PROB_V2_FROZEN.json")
    pre_win_by_id = {p["playerCode"]: p["win_probability"] for p in pre_frozen["predictions"]}

    prediction_by_id = {p["player_id"]: p for p in freeze["predictions"]}
    official_players = official["players"]  # already official-rank-ordered, 118 entries
    official_by_id = {op["playerCode"]: op for op in official_players}
    rank_counts = Counter(op["rank"] for op in official_players)

    def rank_display(rank: str) -> str:
        return f"T{rank}" if rank_counts[rank] > 1 else rank

    def pct(v):
        return "—" if v is None else f"{v * 100:.2f}%"

    def cell(v, label):
        cls = "" if v is None else " class='win'"
        return f"<td{cls} data-label='{label}'>{pct(v)}</td>"

    rows_html = []
    for op in official_players:
        pid = op["playerCode"]
        pred = prediction_by_id.get(pid)
        identity = render_player_identity(op["name"], sponsor_by_id.get(pid), quote="'")
        rows_html.append(
            "<tr>"
            f"<td data-label='순위'>{rank_display(op['rank'])}</td>"
            f"<th scope='row' data-label='선수'>{identity}</th>"
            f"<td data-label='합계'>{_to_par_display(op['toPar'])}</td>"
            f"<td data-label='1R'>{op['r1Score']}</td>"
            + cell(pred["cut"] if pred else None, "컷 통과")
            + cell(pred["top20"] if pred else None, "Top20")
            + cell(pred["top10"] if pred else None, "Top10")
            + cell(pred["top5"] if pred else None, "Top5")
            + cell(pred["win"] if pred else None, "우승")
            + "</tr>"
        )

    movers = []
    for p in freeze["predictions"]:
        pre_win = pre_win_by_id.get(p["player_id"])
        op = official_by_id.get(p["player_id"])
        if pre_win is not None and op is not None:
            movers.append((p["player_name"], sponsor_by_id.get(p["player_id"], ""), pre_win, p["win"]))
    movers.sort(key=lambda m: (m[3] - m[2]), reverse=True)
    top_movers = movers[:3]
    # Reuses the site's own existing .mover-list/.delta pattern (see
    # scripts/84_build_ok_open_pre_website_candidate.py's _mover_line) --
    # already-proven flex row (identity left, movement right, no
    # bullets, border-bottom separator) instead of a second, newly
    # invented layout, exactly what the alignment-bug fix calls for.
    movers_html = "".join(
        f"<li>{render_player_identity(name, sponsor, quote=chr(39))}"
        f"<span class='delta'>PRE {pre_w*100:.2f}% → R1 {r1_w*100:.2f}%</span></li>"
        for name, sponsor, pre_w, r1_w in top_movers
    )

    excluded_count = len(freeze["excluded_players"])
    footnote = (
        f'<p class="note">※ {excluded_count}명은 데이터 부족으로 예측 제외</p>'
        if excluded_count else ""
    )

    body = (
        '<nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><a href="/tournaments/">대회</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><span>KB금융 골든라이프 챔피언십</span>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><span aria-current="page">R1</span></nav>'
        '<section class="hero" id="tournament"><div><p class="eyebrow">R1 업데이트</p>'
        '<h1>KB금융 골든라이프 챔피언십</h1><p class="meta">2026.09.10 — 09.13</p></div>'
        '<strong class="status">R1</strong></section>'
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/pre/">사전 분석 PRE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r1/" aria-current="page">R1</a></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R2</span></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R3</span></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">FINAL</span></li>'
        '</ol></nav>'
        '<section class="panel leaderboard-panel" id="r1">'
        '<div class="leaderboard-head"><h2>1R 결과</h2></div>'
        '<div class="table-wrap"><table class="data leaderboard-table"><thead><tr>'
        "<th>순위</th><th>선수</th><th>합계</th><th>1R</th>"
        "<th>컷 통과</th><th>Top20</th><th>Top10</th><th>Top5</th><th>우승</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div>"
        + footnote +
        "</section>"
        '<section class="panel" id="pre-r1-movement"><h2>PRE → R1</h2>'
        f"<ul class='mover-list'>{movers_html}</ul>"
        "</section>"
    )

    return body


# PUBLIC UI IMMUTABLE INVARIANT: round-update-status copy for every
# current/future tournament stage page -- see NEO PUBLIC UI CORRECTION
# section 6. Deliberately a fixed table (not derived from stage_order
# position math) so the exact required wording ("FR", not "최종 라운드")
# is never accidentally reworded by a future refactor.
ROUND_UPDATE_COPY = {
    "pre": "1R 종료 후 업데이트",
    "r1": "2R 종료 후 업데이트",
    "r2": "3R 종료 후 업데이트",
    "r3": "FR 종료 후 업데이트",
    "fr": "대회 종료",
}

_ROUND_UPDATE_NOTE_RE = re.compile(r'<p class="round-update-note">.*?</p>')


def _ensure_round_update_note(hero_and_after: str, stage: str) -> str:
    """Idempotent: refreshes an existing round-update-note in place
    (never lets it go stale/duplicate on a re-run), or inserts one right
    after the stage <strong class="status"> badge if none exists yet."""
    note = f'<p class="round-update-note">{ROUND_UPDATE_COPY[stage]}</p>'
    if _ROUND_UPDATE_NOTE_RE.search(hero_and_after):
        return _ROUND_UPDATE_NOTE_RE.sub(note, hero_and_after, count=1)
    return re.sub(r'(<strong class="status">[^<]*</strong>)', rf"\1{note}", hero_and_after, count=1)


PRE_STAGE_NAV_RE = re.compile(r'<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R1</span></li>')
PRE_STAGE_NAV_REPLACEMENT = f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r1/">R1</a></li>'


def update_pre_page_stage_nav(pre_html: str) -> str:
    if PRE_STAGE_NAV_REPLACEMENT in pre_html:
        return pre_html  # idempotent: already linked by an earlier run
    updated, count = PRE_STAGE_NAV_RE.subn(PRE_STAGE_NAV_REPLACEMENT, pre_html, count=1)
    if count != 1:
        raise ValueError("expected exactly one disabled R1 stage-nav placeholder in the PRE page -- refusing to guess")
    return updated


def write_root_home(root_html: str) -> None:
    """OWNER-APPROVED SUPERSESSION: root HOME temporarily becomes the
    current tournament's latest approved stage (R1) instead of the
    K-Ranking x NEO Ranking page -- see home_ownership_guard.py's
    OWNER SUPERSESSION note. The prior real HOME content is preserved
    (never deleted) under docs_internal_archive/index.html, exactly
    once, mirroring apply_public_site_lockdown.py's own archive-never-
    overwrite pattern -- its build/data implementation is untouched."""
    if DOCS_INDEX.is_file():
        existing = DOCS_INDEX.read_text(encoding="utf-8")
        if extract_owner(existing) != CURRENT_TOURNAMENT_OWNER and not ARCHIVE_INDEX.is_file():
            ARCHIVE_INDEX.parent.mkdir(parents=True, exist_ok=True)
            ARCHIVE_INDEX.write_text(existing, encoding="utf-8", newline="\n")

    assert_home_write_allowed(DOCS_INDEX, CURRENT_TOURNAMENT_OWNER, repo_root=ROOT, allow_transfer_from=TOP120_OWNER)
    DOCS_INDEX.write_text(embed_owner(root_html, CURRENT_TOURNAMENT_OWNER), encoding="utf-8", newline="\n")


def main() -> int:
    # Refresh PRE's shared header/footer to the current canonical config
    # (global_navigation.py) before deriving anything from it, and route
    # its own "대회" link to KB's current published stage (R1) via
    # nav_overrides -- PRE/R1 are hand-carried static files, not
    # regenerated by the normal full-site build, so without this refresh
    # they would stay frozen on whatever nav/footer config existed the
    # first time this script ran.
    pre_html = inject_global_navigation(PRE_PAGE.read_text(encoding="utf-8"), active_section="tournaments", nav_overrides=NAV_OVERRIDES)
    pre_html = _ensure_round_update_note(pre_html, "pre")
    header_prefix = pre_html.split("<main>", 1)[0] + "<main>"
    footer_suffix = "</main>" + pre_html.split("</main>", 1)[1]
    r1_body = build_r1_page()
    r1_html = header_prefix.replace(">PRE 참가 선수", ">R1 업데이트").replace('"status">PRE<', '"status">R1<') + r1_body + footer_suffix
    r1_html = r1_html.replace("<title>NEO GOLF DATA · KB금융 골든라이프 챔피언십</title>", "<title>NEO GOLF DATA · KB금융 골든라이프 챔피언십 R1</title>")
    r1_html = _ensure_round_update_note(r1_html, "r1")

    R1_PAGE.parent.mkdir(parents=True, exist_ok=True)
    R1_PAGE.write_text(r1_html, encoding="utf-8", newline="\n")

    updated_pre_html = update_pre_page_stage_nav(pre_html)
    PRE_PAGE.write_text(updated_pre_html, encoding="utf-8", newline="\n")

    # ROOT HOME = current KB R1 (owner decision -- see write_root_home()).
    # Reuses the exact same header_prefix/footer_suffix/body (r1_body)
    # as the R1 route above (never a second, independently maintained
    # copy), only re-marking "홈" (not "대회") as the active nav link.
    home_header_prefix = inject_global_navigation(header_prefix, active_section="home", nav_overrides=NAV_OVERRIDES)
    root_html = home_header_prefix + r1_body + footer_suffix
    root_html = _ensure_round_update_note(root_html, "r1")
    write_root_home(root_html)

    print(json.dumps({"r1_page": str(R1_PAGE), "pre_page_updated": str(PRE_PAGE), "root_home": str(DOCS_INDEX)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
