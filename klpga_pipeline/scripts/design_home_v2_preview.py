"""HOME V2 design preview (branch design/home-ranking-v2-20260910) --
NOT part of the production build/promotion pipeline. Renders a
self-contained static HTML page for local visual review only; never
writes into docs/ and is never wired into scripts/86/88/94.

DESIGN DIRECTION (owner brief): NEO GOLF DATA as a sports-data
company -- numbers over explanation, structure over cards, information
hierarchy over decoration. Mobile-first: the ranking rows and
tournament strip are built as CSS Grid with reassigned grid-template-
areas per breakpoint (same DOM, no duplicate markup, no JS) so nothing
ever needs horizontal scroll -- see PAGE_CSS.

DATA SAFETY (owner brief section 5): this script uses ONLY real,
already-collected data --
  - population + official K-Rank: HOME_PLAYER_MASTER_TOP120.json
    (120 real players, real official_k_rank, real player_id/name,
    real ranking_week -- the only source for the optional "2026 · W36"
    header metadata)
  - sponsor: HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V2.json (verified
    official only; unverified stays a blank slot, never guessed --
    re-verified 2026-09-10: 80 VERIFIED_OFFICIAL + 40 unverified = 120,
    exact match against the population, 김민솔 -> "두산건설 We've" confirmed)
  - tournament strip: klpga.website_v2.tournament_chronology's own
    resolve_tournament_chronology() against the real official schedule
    + site registry -- the exact same real data source the current
    production HOME's tournament cards already use
  - NEO RANK / NEO SCORE: NO approved public source exists yet --
    home_ranking.py's FORMULA_STATE is BLOCKED_FORMULA_NOT_APPROVED /
    NEO_RANKING_VERSION is None, and the separate NEO_RANKING_
    VALIDATION_MODEL_V1.json is explicitly publication_class
    VALIDATION_MODEL_NOT_PRODUCTION / weight_status HEURISTIC_FOR_
    EVALUATION_NOT_FITTED_OR_APPROVED. This preview renders the NEO
    RANK / NEO SCORE columns structurally (so the visual hierarchy is
    reviewable) but leaves every cell "--" -- never a fabricated
    number, never a sentinel. See _fmt1() for the decimal display
    contract this "--" path already obeys.

DECIMAL DISPLAY CONTRACT (owner brief section 1): every decimal shown
in HOME V2 is formatted to exactly 1 place, at render time only --
_fmt1() never rounds/mutates a stored value, it only formats whatever
value is handed to it for THIS page. Whole-number ranks (NEO rank,
K-Rank) are never routed through _fmt1 -- they display as plain
integers.
"""
from __future__ import annotations

import json
import re
import sys
from html import escape
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
CONTENT = PIPELINE_ROOT / "content" / "website_v2"
OUTPUT_DIR = PIPELINE_ROOT / "candidate" / "home-ranking-v2-preview"

sys.path.insert(0, str(PIPELINE_ROOT / "src"))
from klpga.website_v2.global_navigation import GLOBAL_NAV_ITEMS, navigation_html  # noqa: E402
from klpga.website_v2.tournament_chronology import build_home_tournament_chronology  # noqa: E402
from klpga.tournament_context import SITE_REGISTRY_PATH, load_active_tournament_context  # noqa: E402


def load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def _fmt1(value: float | int | None, *, signed: bool = False) -> str:
    """HOME V2 DECIMAL DISPLAY CONTRACT (section 1): format a decimal
    to exactly 1 place for DISPLAY ONLY -- never mutates/rounds any
    stored value, this function's return value is never written back
    anywhere. None means "no approved value" and always renders "--",
    never a fabricated number or a sentinel like 999999."""
    if value is None:
        return "—"
    return f"{value:+.1f}" if signed else f"{value:.1f}"


def _resolve_stage_link(url_base: str, registry_entry: dict) -> tuple[str, str]:
    """Real link resolution -- reuses the exact rule scripts/88 already
    applies to HOME's tournament cards: the LAST stage the site
    registry's own hub_card.nav_stages records for this tournament.
    Never invented -- a tournament with no url_base yet (no public
    page) returns ("", "") and the caller renders plain text only."""
    if not url_base:
        return "", ""
    stages = list((registry_entry.get("hub_card") or {}).get("nav_stages") or [])
    if not stages:
        return url_base, ""
    stage = stages[-1]
    label = {"pre": "PRE", "r1": "R1", "r2": "R2", "r3": "R3", "final": "FINAL"}.get(stage, stage.upper())
    return f"{url_base}{stage}/", label


def build_header() -> str:
    """Desktop nav (real GLOBAL_NAV_ITEMS links, unchanged from
    production) plus a zero-JS mobile menu -- a native <details> whose
    own open/close needs no script at all -- built from the SAME real
    link list so the two can never drift apart. CSS alone decides
    which one is visible at a given width (see PAGE_CSS)."""
    base = navigation_html(active_section="home")
    active_attrs = ' class="is-active" aria-current="page"'
    mobile_links = "".join(
        f'<a href="{escape(url)}"{active_attrs if key == "home" else ""}>{escape(label)}</a>'
        for key, label, url in GLOBAL_NAV_ITEMS
    )
    mobile_menu = (
        '<details class="neo-mobile-menu">'
        '<summary>MENU</summary>'
        f'<nav class="neo-global-nav neo-global-nav--mobile" aria-label="주요 메뉴 (모바일)">{mobile_links}</nav>'
        '</details>'
    )
    updated, count = re.subn(r"</div></header>$", mobile_menu + "</div></header>", base.rstrip())
    if count != 1:
        raise ValueError("could not locate global header's closing tag to attach the mobile menu")
    return updated


def build_tournament_strip() -> str:
    registry = json.loads(SITE_REGISTRY_PATH.read_text(encoding="utf-8-sig"))["tournaments"]
    ctx = load_active_tournament_context()
    chronology = build_home_tournament_chronology(registry, ctx)

    def col(kind: str, label: str, facts) -> str:
        if facts is None or not facts.tournament_name:
            return (
                f'<div class="t-strip__col t-strip__col--{kind}">'
                f'<p class="t-strip__label">{label}</p>'
                '<p class="t-strip__name">—</p><p class="t-strip__meta">—</p></div>'
            )
        # Real-link resolution: same rule scripts/88 already applies to
        # every one of HOME's tournament cards (prev/current/next
        # alike) -- resolve to the tournament's own latest real
        # published stage, never the bare (often route-less) base URL.
        stage_url, stage_label = _resolve_stage_link(facts.url_base, registry.get(facts.game_code, {}))
        name_html = f'<a href="{escape(stage_url)}">{escape(facts.tournament_name)}</a>' if stage_url else escape(facts.tournament_name)
        meta = escape(facts.date_range_display)
        if kind == "current":
            dot = ' <span class="t-strip__dot" aria-hidden="true">●</span>'
            if stage_url:
                meta += f' · <a class="t-strip__stage" href="{escape(stage_url)}">{escape(stage_label)} →</a>'
        else:
            dot = ""
        return (
            f'<div class="t-strip__col t-strip__col--{kind}">'
            f'<p class="t-strip__label">{label}{dot}</p>'
            f'<p class="t-strip__name">{name_html}</p>'
            f'<p class="t-strip__meta">{meta}</p></div>'
        )

    return (
        '<nav class="t-strip" aria-label="대회 일정">'
        + col("prev", "PREVIOUS", chronology.get("last"))
        + col("current", "CURRENT", chronology.get("current"))
        + col("next", "NEXT", chronology.get("next"))
        + "</nav>"
    )


def _rank_row(*, neo_rank, player_name, sponsor, neo_score, k_rank) -> str:
    sponsor_html = escape(sponsor) if sponsor else ""
    return (
        '<div class="rank-row" role="row">'
        f'<div class="col-neo-rank" role="cell">{neo_rank}</div>'
        f'<div class="col-player-name" role="cell"><span class="player-name">{escape(player_name)}</span></div>'
        f'<div class="col-sponsor" role="cell"><span class="player-sponsor">{sponsor_html}</span></div>'
        f'<div class="col-neo-score" role="cell">{neo_score}</div>'
        f'<div class="col-k-rank" role="cell"><span class="k-rank-label">K-RANK</span><span class="k-rank-value">{k_rank}</span></div>'
        '</div>'
    )


def build_ranking_table() -> tuple[str, int, str | None]:
    top120 = load("HOME_PLAYER_MASTER_TOP120.json")
    sponsor_audit = load("HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V2.json")
    sponsor_by_id = {r["player_id"]: r["sponsor"] for r in sponsor_audit["newly_recovered_sponsors"]}

    records = sorted(top120["records"], key=lambda r: r["official_k_rank"])
    rows = [
        _rank_row(
            neo_rank="—",
            player_name=r["player_name"],
            sponsor=sponsor_by_id.get(r["player_id"]),
            neo_score=_fmt1(None),  # no approved NEO Score source yet -- see module docstring
            k_rank=r["official_k_rank"],
        )
        for r in records
    ]
    return "".join(rows), len(records), top120.get("ranking_week")


def _week_meta_html(ranking_week: str | None) -> str:
    if not ranking_week:
        return ""
    m = re.match(r"^(\d{4})-W(\d{1,2})$", ranking_week)
    if not m:
        return ""
    year, week = m.groups()
    return f'<p class="rank-head__meta">{escape(year)} · W{escape(week)}</p>'


PAGE_CSS = """
:root{--ink:#0b0f14;--muted:#6b7680;--line:#e4e7eb;--accent:#0b6b53;--bg:#ffffff;--content-max:900px;--side-pad:20px}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Pretendard","Noto Sans KR",-apple-system,BlinkMacSystemFont,sans-serif;-webkit-font-smoothing:antialiased;overflow-x:hidden}
.neo-global-header{min-height:52px;display:flex;align-items:center;border-bottom:1px solid var(--line)}
.neo-global-header__inner{width:100%;max-width:var(--content-max);margin:0 auto;padding:0 var(--side-pad);display:flex;align-items:center;justify-content:space-between;gap:24px}
.neo-global-brand{display:flex;align-items:baseline;gap:8px;text-decoration:none;color:var(--ink);flex:0 0 auto}
.neo-brand-mark{font-weight:800;font-size:.92rem;letter-spacing:.01em;white-space:nowrap}
.neo-brand-legend{display:none}
.neo-global-header__inner>nav.neo-global-nav{display:flex;gap:18px;flex-wrap:nowrap;white-space:nowrap}
.neo-global-nav a{color:var(--muted);text-decoration:none;font-size:.82rem;font-weight:600}
.neo-global-nav a.is-active{color:var(--ink)}
.neo-global-nav a:hover{color:var(--ink)}
.neo-mobile-menu{display:none;position:relative}
.neo-mobile-menu summary{cursor:pointer;list-style:none;font-size:.78rem;font-weight:700;letter-spacing:.04em;color:var(--ink);padding:4px 0}
.neo-mobile-menu summary::-webkit-details-marker{display:none}
.neo-mobile-menu[open] summary{color:var(--accent)}
.neo-mobile-menu nav.neo-global-nav--mobile{position:absolute;right:0;top:32px;min-width:132px;background:#fff;border:1px solid var(--line);padding:10px 14px;display:flex;flex-direction:column;gap:10px;z-index:30;box-sizing:border-box}
main{max-width:var(--content-max);margin:0 auto;padding:0 var(--side-pad)}

/* ---- tournament strip ---- */
.t-strip{display:grid;grid-template-columns:1fr 1.4fr 1fr;grid-template-areas:"prev current next";gap:0;border-bottom:1px solid var(--line);padding:14px 0 12px}
.t-strip__col{min-width:0;padding:0 18px;border-left:1px solid var(--line)}
.t-strip__col--prev{grid-area:prev;border-left:0;padding-left:0}
.t-strip__col--current{grid-area:current}
.t-strip__col--next{grid-area:next}
.t-strip__label{margin:0 0 4px;font-size:.68rem;font-weight:700;letter-spacing:.06em;color:var(--muted)}
.t-strip__col--current .t-strip__label{color:var(--accent)}
.t-strip__dot{color:var(--accent);font-size:.6rem}
.t-strip__name{margin:0;font-size:.9rem;font-weight:600;overflow-wrap:break-word;word-break:keep-all}
.t-strip__col--current .t-strip__name{font-size:1.05rem;font-weight:800}
.t-strip__col--prev .t-strip__name,.t-strip__col--next .t-strip__name{color:var(--muted);font-weight:500}
.t-strip__name a{color:inherit;text-decoration:none}
.t-strip__name a:hover{text-decoration:underline}
.t-strip__meta{margin:2px 0 0;font-size:.76rem;color:var(--muted);font-variant-numeric:tabular-nums;overflow-wrap:break-word}
.t-strip__stage{color:var(--accent);font-weight:700;text-decoration:none}
.t-strip__stage:hover{text-decoration:underline}

/* ---- NEO RANKING header ---- */
.rank-head{padding:28px 0 4px}
.rank-head__row{display:flex;align-items:baseline;justify-content:space-between;gap:16px;flex-wrap:wrap}
.rank-head__row h1{margin:0;font-size:2rem;font-weight:800;letter-spacing:-.02em}
.rank-head__meta{margin:0;font-size:.78rem;font-weight:600;color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap}
.rank-head__sub{margin:4px 0 0;color:var(--muted);font-size:.86rem}

/* ---- ranking table (CSS Grid rows, never an HTML <table> --
   nothing to horizontally scroll, so nothing does) ---- */
.rank-table{margin:16px 0 40px}
.rank-row{display:grid;grid-template-columns:48px 1fr 96px 76px;column-gap:14px;row-gap:2px;align-items:start;padding:9px 0;border-bottom:1px solid var(--line)}
.rank-row--head{grid-template-areas:"neo player score krank";padding:0 0 8px;border-bottom:1px solid var(--ink);font-size:.68rem;font-weight:700;letter-spacing:.06em;color:var(--muted)}
.rank-row:not(.rank-row--head){grid-template-areas:"neo player score krank" ".   sponsor .     .    "}
.col-neo-rank{grid-area:neo;text-align:right;font:800 1.05rem/1.25 ui-monospace,"SF Mono",Consolas,monospace;font-variant-numeric:tabular-nums;color:var(--ink)}
.rank-row--head .col-neo-rank{font:inherit;text-align:right}
.col-player-name{grid-area:player;min-width:0}
.col-sponsor{grid-area:sponsor;min-width:0}
.col-neo-score{grid-area:score;text-align:right;font-weight:700;font-variant-numeric:tabular-nums}
.col-k-rank{grid-area:krank;text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}
.col-neo-score .short{display:none}
.k-rank-label{display:none}
.player-name{display:block;font-weight:700;font-size:.92rem;overflow-wrap:break-word}
.player-sponsor{display:block;color:var(--muted);font-size:.74rem;margin-top:1px;overflow-wrap:break-word}

/* ---- footer ---- */
.site-footer{border-top:1px solid var(--line);margin-top:40px}
.site-footer__inner{max-width:var(--content-max);margin:0 auto;padding:20px var(--side-pad)}
.site-footer__inner p{margin:0;font-size:.76rem;color:var(--muted)}
.site-footer__copyright{margin-top:4px!important}

/* ---- mobile (<=640px): rebuild, not a shrink ---- */
@media(max-width:640px){
:root{--side-pad:16px}
.neo-global-header__inner>nav.neo-global-nav{display:none}
.neo-mobile-menu{display:block}

.t-strip{grid-template-columns:1fr 1fr;grid-template-areas:"current current" "prev next";row-gap:12px;padding:12px 0 10px}
.t-strip__col--current{border-left:0;padding-left:0;padding-bottom:10px;border-bottom:1px solid var(--line)}
.t-strip__col--prev{border-left:0;padding-left:0;padding-right:12px}
.t-strip__col--next{border-left:1px solid var(--line);padding-left:12px}

.rank-head__meta{display:none}
.rank-head__row h1{font-size:1.5rem}

.rank-row{grid-template-columns:30px 1fr 54px;column-gap:8px}
.rank-row--head{grid-template-areas:"neo player score"}
.rank-row:not(.rank-row--head){grid-template-areas:"neo player score" ".   sponsor sponsor" ".   krank   krank"}
.col-neo-score .full{display:none}
.col-neo-score .short{display:inline}
.col-k-rank{grid-area:krank;text-align:left;font-size:.68rem}
.k-rank-label{display:inline;font-weight:700;letter-spacing:.04em;margin-right:4px}
.col-neo-rank{font-size:.92rem}
.player-name{font-size:.88rem}
}
"""


def build_page() -> str:
    header = build_header()
    strip = build_tournament_strip()
    rows_html, n, ranking_week = build_ranking_table()
    week_meta = _week_meta_html(ranking_week)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEO RANKING -- HOME V2 DESIGN PREVIEW</title>
<style>{PAGE_CSS}</style>
</head><body>
{header}
<main>
{strip}
<section class="rank-head">
<div class="rank-head__row"><h1>NEO RANKING</h1>{week_meta}</div>
<p class="rank-head__sub">NEO가 평가한 KLPGA 선수 순위</p>
</section>
<div class="rank-table" role="table" aria-label="NEO Ranking · {n}명">
<div class="rank-row rank-row--head" role="row">
<div class="col-neo-rank" role="columnheader">NEO</div>
<div class="col-player-name" role="columnheader">PLAYER</div>
<div class="col-neo-score" role="columnheader"><span class="full">NEO SCORE</span><span class="short">SCORE</span></div>
<div class="col-k-rank" role="columnheader">K-RANK</div>
</div>
{rows_html}
</div>
</main>
<footer class="site-footer"><div class="site-footer__inner">
<p>NEO · Number · Evidence · Oracle</p>
<p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p>
</div></footer>
</body></html>"""


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html = build_page()
    out_path = OUTPUT_DIR / "index.html"
    out_path.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({"preview": str(out_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
