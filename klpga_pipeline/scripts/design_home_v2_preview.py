"""HOME V2 design preview (branch design/home-ranking-v2-20260910) --
NOT part of the production build/promotion pipeline. Renders a
self-contained static HTML page for local visual review only; never
writes into docs/ and is never wired into scripts/86/88/94.

DESIGN DIRECTION (owner brief): NEO GOLF DATA as a sports-data
company -- numbers over explanation, structure over cards, information
hierarchy over decoration. See the rendered page itself for the full
visual spec; this docstring covers only the DATA contract.

DATA SAFETY (owner brief section 5): this script uses ONLY real,
already-collected data --
  - population + official K-Rank: HOME_PLAYER_MASTER_TOP120.json
    (120 real players, real official_k_rank, real player_id/name)
  - sponsor: HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V2.json (verified
    official only; unverified stays a blank slot, never guessed)
  - tournament strip: klpga.website_v2.tournament_chronology's own
    resolve_tournament_chronology() against the real official schedule
    + site registry -- the exact same real data source the current
    production HOME's tournament cards already use
  - NEO RANK / NEO SCORE: NO approved public source exists yet --
    home_ranking.py's FORMULA_STATE is BLOCKED_FORMULA_NOT_APPROVED /
    NEO_RANKING_VERSION is None, and the separate NEO_RANKING_
    VALIDATION_MODEL_V1.json is explicitly publication_class
    VALIDATION_MODEL_NOT_PRODUCTION / weight_status HEURISTIC_FOR_
    EVALUATION_NOT_FITTED_OR_APPROVED (see scripts/88's own render_clean
    docstring for the identical rule already enforced in production).
    This preview renders the NEO RANK / NEO SCORE columns structurally
    (so the visual hierarchy is reviewable) but leaves every cell "--"
    -- never a fabricated number, never a sentinel.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from html import escape
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_ROOT.parent
CONTENT = PIPELINE_ROOT / "content" / "website_v2"
OUTPUT_DIR = PIPELINE_ROOT / "candidate" / "home-ranking-v2-preview"

sys.path.insert(0, str(PIPELINE_ROOT / "src"))
from klpga.website_v2.global_navigation import navigation_html  # noqa: E402
from klpga.website_v2.player_identity import render_player_identity  # noqa: E402
from klpga.website_v2.tournament_chronology import build_home_tournament_chronology  # noqa: E402
from klpga.tournament_context import SITE_REGISTRY_PATH, load_active_tournament_context  # noqa: E402


def load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


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


def build_ranking_table() -> tuple[str, int]:
    top120 = load("HOME_PLAYER_MASTER_TOP120.json")
    sponsor_audit = load("HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V2.json")
    sponsor_by_id = {r["player_id"]: r["sponsor"] for r in sponsor_audit["newly_recovered_sponsors"]}

    records = sorted(top120["records"], key=lambda r: r["official_k_rank"])
    rows = []
    for r in records:
        pid = r["player_id"]
        identity = render_player_identity(r["player_name"], sponsor_by_id.get(pid))
        rows.append(
            '<tr>'
            f'<td class="col-neo-rank">—</td>'
            f'<th scope="row" class="col-player">{identity}</th>'
            f'<td class="col-neo-score">—</td>'
            f'<td class="col-k-rank">{r["official_k_rank"]}</td>'
            '</tr>'
        )
    return "".join(rows), len(records)


PAGE_CSS = """
:root{--ink:#0b0f14;--muted:#6b7680;--line:#e4e7eb;--accent:#0b6b53;--bg:#ffffff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Pretendard","Noto Sans KR",-apple-system,BlinkMacSystemFont,sans-serif;-webkit-font-smoothing:antialiased}
.neo-global-header{height:52px;display:flex;align-items:center;border-bottom:1px solid var(--line)}
.neo-global-header__inner{width:100%;max-width:1120px;margin:0 auto;padding:0 20px;display:flex;align-items:center;justify-content:space-between;gap:24px}
.neo-global-brand{display:flex;align-items:baseline;gap:8px;text-decoration:none;color:var(--ink)}
.neo-brand-mark{font-weight:800;font-size:.92rem;letter-spacing:.01em}
.neo-brand-legend{display:none}
.neo-global-nav{display:flex;gap:18px;flex-wrap:wrap}
.neo-global-nav a{color:var(--muted);text-decoration:none;font-size:.82rem;font-weight:600}
.neo-global-nav a.is-active{color:var(--ink)}
.neo-global-nav a:hover{color:var(--ink)}
main{max-width:1120px;margin:0 auto;padding:0 20px}
.t-strip{display:grid;grid-template-columns:1fr 1.4fr 1fr;gap:0;border-bottom:1px solid var(--line);padding:14px 0 12px}
.t-strip__col{padding:0 18px;border-left:1px solid var(--line)}
.t-strip__col:first-child{border-left:0;padding-left:0}
.t-strip__label{margin:0 0 4px;font-size:.68rem;font-weight:700;letter-spacing:.06em;color:var(--muted)}
.t-strip__col--current .t-strip__label{color:var(--accent)}
.t-strip__dot{color:var(--accent);font-size:.6rem}
.t-strip__name{margin:0;font-size:.9rem;font-weight:600}
.t-strip__col--current .t-strip__name{font-size:1.05rem;font-weight:800}
.t-strip__col--prev .t-strip__name,.t-strip__col--next .t-strip__name{color:var(--muted);font-weight:500}
.t-strip__name a{color:inherit;text-decoration:none}
.t-strip__name a:hover{text-decoration:underline}
.t-strip__meta{margin:2px 0 0;font-size:.76rem;color:var(--muted);font-variant-numeric:tabular-nums}
.t-strip__stage{color:var(--accent);font-weight:700;text-decoration:none}
.t-strip__stage:hover{text-decoration:underline}
.rank-head{padding:32px 0 6px}
.rank-head__eyebrow{margin:0 0 4px;font-size:.72rem;font-weight:700;letter-spacing:.08em;color:var(--muted);text-transform:uppercase}
.rank-head h1{margin:0 0 6px;font-size:1.7rem;font-weight:800;letter-spacing:-.01em}
.rank-head p{margin:0;color:var(--muted);font-size:.86rem}
.rank-table-wrap{overflow-x:auto;margin:18px 0 40px}
.rank-table{width:100%;border-collapse:collapse}
.rank-table thead th{text-align:left;font-size:.68rem;font-weight:700;letter-spacing:.06em;color:var(--muted);padding:0 12px 10px;border-bottom:1px solid var(--ink)}
.rank-table td,.rank-table th{padding:11px 12px;border-bottom:1px solid var(--line);font-size:.9rem;vertical-align:middle}
.rank-table .col-neo-rank{width:64px;text-align:right;font:800 1.15rem/1 "SF Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums;color:var(--ink)}
.rank-table .col-player{text-align:left}
.rank-table .col-neo-score{width:110px;text-align:right;font-weight:700;font-variant-numeric:tabular-nums}
.rank-table .col-k-rank{width:80px;text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}
.rank-table thead .col-neo-rank,.rank-table thead .col-neo-score,.rank-table thead .col-k-rank{text-align:right}
.player-name{display:block;font-weight:700}
.player-sponsor{display:block;color:var(--muted);font-size:.76rem;margin-top:2px}
.site-footer{border-top:1px solid var(--line);margin-top:40px}
.site-footer__inner{max-width:1120px;margin:0 auto;padding:20px}
.site-footer__inner p{margin:0;font-size:.76rem;color:var(--muted)}
.site-footer__copyright{margin-top:4px!important}
@media(max-width:720px){
.t-strip{grid-template-columns:1fr}
.t-strip__col{border-left:0;border-top:1px solid var(--line);padding:10px 0 0;margin-top:10px}
.t-strip__col:first-child{border-top:0;margin-top:0}
.rank-table .col-neo-score{width:auto}
main{padding:0 16px}
}
"""


def build_page() -> str:
    header = navigation_html(active_section="home")
    strip = build_tournament_strip()
    rows_html, n = build_ranking_table()
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEO RANKING -- HOME V2 DESIGN PREVIEW</title>
<style>{PAGE_CSS}</style>
</head><body>
{header}
<main>
{strip}
<section class="rank-head">
<p class="rank-head__eyebrow">NEO GOLF DATA</p>
<h1>NEO RANKING</h1>
<p>NEO가 평가한 KLPGA 선수 순위</p>
</section>
<div class="rank-table-wrap">
<table class="rank-table">
<thead><tr><th class="col-neo-rank">NEO</th><th class="col-player">PLAYER</th><th class="col-neo-score">NEO SCORE</th><th class="col-k-rank">K-RANK</th></tr></thead>
<tbody>{rows_html}</tbody>
</table>
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
