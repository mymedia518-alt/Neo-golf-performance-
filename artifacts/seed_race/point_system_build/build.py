"""Generate the "2027 포인트 시드 전쟁" informational page.

Source of truth (read directly):
  artifacts/seed_race/point_table_PARTIAL_2026-10-06.csv       (5 real point-rank rows)
  artifacts/seed_race/remaining_events_point_PARTIAL_2026-10-06.csv (HJ/S-OIL full TOP10 curve, ICEBURG partial)
  artifacts/seed_race/seed_probability.csv                      (55-80 money bubble, for the "point data pending" list)
  artifacts/seed_race/eligibility_crosscheck_55_80.csv           (confirmed 2027 independent exemptions)
  artifacts/seed_race/official_money_rank_2026-10-06_full.json   (money rank/money cross-check)

This page does NOT publish any seed probability number -- the official
points-rank cutoff is unresolved (see SEED_POINT_SYSTEM_GAP.md). It only
publishes what's actually confirmed: the rule-change itself, the TOP10
point curve for the 10억~12억미만 bracket (HJ/S-OIL), the real
money-rank-vs-point-rank reversals we have data for, and confirmed
independent 2027 exemptions.

OFFICIAL RELAY #5 (this build): the user relayed a full official
2026-10-06 snapshot (money_rank 1-121, incl. target_points) and, for the
55-80 money bubble, the resulting point_rank + delta already computed
against that full field. point_rank display for this 26-player subset is
now UNLOCKED -- it is no longer a Claude-side sort of a 26-player subset
(which was explicitly banned), but a relayed result of ranking the full
field. Claude independently verified internal self-consistency before
accepting it: all 20 non-blank delta values (= current_rank - point_rank)
check out arithmetically, and point_rank is monotonic with points value
and exactly tied where points are tied (points=25 x4, =60 x2, =23 x2).
The 2027 SEED CUTOFF (how many point_rank positions actually carry a seed)
remains unresolved, so probability/seed-survival language stays banned
regardless of this unlock.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SR = ROOT / "artifacts" / "seed_race"
OUT = Path(__file__).resolve().parent / "index.html"


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


point_rows = read_csv(SR / "point_table_PARTIAL_2026-10-06.csv")
event_rows = read_csv(SR / "remaining_events_point_PARTIAL_2026-10-06.csv")
seed_rows = read_csv(SR / "seed_probability.csv")
elig_rows = read_csv(SR / "eligibility_crosscheck_55_80.csv")
bubble_points = read_csv(ROOT / "artifacts" / "seed_race" / "point_values_bubble_55_80_2026-10-06.csv")
tie_fixture = read_csv(ROOT / "artifacts" / "seed_race" / "tie_handling_fixture_OFFICIAL.csv")
official = json.load(open(SR / "official_money_rank_2026-10-06_full.json", encoding="utf-8"))
official_by_name = {r["player_name"]: r for r in official}

assert len(bubble_points) == 26
bubble_points_by_rank = {int(r["current_rank"]): r for r in bubble_points}
for r in bubble_points:
    off = official_by_name[r["player"]]
    assert str(off["rank"]) == r["current_rank"] and str(off["prize_money"]) == r["money"], \
        f"bubble cross-check mismatch for {r['player']}"

assert len(point_rows) == 6, f"expected 6 known point rows, got {len(point_rows)}"
# connector/delta module needs a RECONCILED point_rank on both sides -- 장은수's point value
# is known but her official point_rank was never explicitly listed (only ranks 1-5 were), so
# she's excluded from the rank<->rank module here (UNRECONCILED != a number to sort/diff against).
point_rows_ranked = [r for r in point_rows if r["point_rank"] != "UNRECONCILED"]
assert len(point_rows_ranked) == 5, f"expected 5 rank-reconciled point rows, got {len(point_rows_ranked)}"
point_rows_sorted = sorted(point_rows_ranked, key=lambda r: int(r["point_rank"]))
for r in point_rows_sorted:
    off = official_by_name[r["player"]]
    assert str(off["rank"]) == r["money_rank"] and str(off["prize_money"]) == r["money"], \
        f"mismatch for {r['player']}"

bubble = [r for r in seed_rows if 55 <= int(float(r["current_rank"])) <= 80]
bubble.sort(key=lambda r: int(float(r["current_rank"])))
assert len(bubble) == 26

elig_by_rank = {int(r["current_rank"]): r for r in elig_rows}

# HJ / S-OIL TOP10 curve (identical bracket, both 10억 purse)
hj_curve = sorted(
    [r for r in event_rows if r["gameCode"] == "2026100004" and int(r["finish_position"]) <= 10],
    key=lambda r: int(r["finish_position"]),
)
assert [int(r["points"]) for r in hj_curve] == [70, 35, 33, 31, 29, 27, 25, 23, 21, 20]

iceburg_known = [r for r in event_rows if r["gameCode"] == "2026100003"]
assert len(iceburg_known) == 1 and int(iceburg_known[0]["points"]) == 90


def won(n):
    return f"{n:,}원"


# ---- money-rank <-> point-rank connector rows (only the 5 known players) ----
connector_html = []
for r in point_rows_sorted:
    delta = int(r["money_rank"]) - int(r["point_rank"])
    delta_text = f"+{delta}" if delta > 0 else str(delta)
    delta_class = "delta-up" if delta > 0 else ("delta-down" if delta < 0 else "delta-flat")
    connector_html.append(f"""
    <div class="connector-row">
      <div class="connector-name">{r['player']}</div>
      <div class="connector-ranks">
        <span class="connector-money">상금 {r['money_rank']}위</span>
        <span class="connector-arrow">→</span>
        <span class="connector-point">포인트 {r['point_rank']}위</span>
        <span class="connector-delta {delta_class}">{delta_text}</span>
      </div>
      <div class="connector-vals">{won(int(r['money']))} · {r['points']}점</div>
    </div>""")
connector_rows_html = "\n".join(connector_html)

def delta_badge(delta):
    if delta > 0:
        return f"▲{delta}", "delta-up"
    if delta < 0:
        return f"▼{-delta}", "delta-down"
    return "0", "delta-flat"


# ---- bubble list (55-80 money rank): real points + full-field point_rank + delta ----
bubble_html = []
confirmed_rows = []  # bubble_points rows with a real points value (dict, delta cast to int)
for r in bubble:
    rank = int(float(r["current_rank"]))
    name = r["player"]
    money = int(r["current_money"])
    elig = elig_by_rank.get(rank, {})
    group = elig.get("final_2027_group", "")
    tag = ""
    if group == "B":
        tag = '<span class="bubble-tag tag-confirmed">별도 시드 확보</span>'
    bp = bubble_points_by_rank[rank]
    if bp["points_status"] == "CONFIRMED_VALUE":
        bp = dict(bp)
        bp["delta"] = int(bp["delta"])
        confirmed_rows.append(bp)
        badge_text, badge_class = delta_badge(bp["delta"])
        delta_html = f'<span class="pending-delta {badge_class}">{badge_text}</span>' if bp["delta"] != 0 else f'<span class="pending-delta delta-flat">{badge_text}</span>'
        point_block = (
            f'<span class="pending-points-val">{bp["points"]}점</span>'
            f'<div class="pending-rank-row"><span class="pending-point-rank">포인트 {bp["point_rank"]}위</span>{delta_html}</div>'
        )
    else:
        point_block = (
            '<span class="pending-points-blank">—<sup>*</sup></span>'
            '<div class="pending-rank-row"><span class="pending-point-rank-blank">포인트순위 —</span></div>'
        )
    bubble_html.append(f"""
    <div class="pending-row" data-rank="{rank}" data-player="{name}" data-points="{bp['points'] or ''}" data-point-rank="{bp.get('point_rank', '') or ''}">
      <div class="pending-rank">{rank}<span class="pending-rank-unit">위</span></div>
      <div class="pending-name">{name}{tag}</div>
      <div class="pending-money">{won(money)}</div>
      <div class="pending-point">대상포인트 {point_block}</div>
    </div>""")
bubble_rows_html = "\n".join(bubble_html)

# ---- hero reversal cards -- computed from data (top-3 biggest UP, biggest DOWN), not hand-picked ----
up_sorted = sorted(confirmed_rows, key=lambda r: -r["delta"])
top3_up = up_sorted[:3]
biggest_down = min(confirmed_rows, key=lambda r: r["delta"])
assert [r["player"] for r in top3_up] == ["김나현2", "홍정민", "조아연"], \
    f"unexpected top-3 UP ordering: {[r['player'] for r in top3_up]}"
assert biggest_down["player"] == "안재희", f"unexpected biggest DOWN: {biggest_down['player']}"

HERO_CARDS = [("이 구간에서 포인트 기준으로 가장 많이 올라간다", r) for r in top3_up]
HERO_CARDS.append(("이 구간에서 포인트 기준으로 가장 많이 내려간다", biggest_down))

hero_card_html = []
for label, r in HERO_CARDS:
    rank = int(r["current_rank"])
    elig = elig_by_rank.get(rank, {})
    exempt_html = ('<span class="hcard-exempt">별도 시드 확보</span>' if elig.get("final_2027_group") == "B" else "")
    badge_text, badge_class = delta_badge(r["delta"])
    hero_card_html.append(f"""
    <div class="hcard">
      <div class="hcard-label">{label}</div>
      <div class="hcard-name">{r['player']}{exempt_html}</div>
      <div class="hcard-stats">상금 {rank}위 → 포인트 {r['point_rank']}위</div>
      <div class="hcard-points"><span class="pending-delta {badge_class}">{badge_text}</span></div>
    </div>""")
hero_cards_html = "\n".join(hero_card_html)

# 김새로미 -- special callout: the exact money-rank Top60 boundary, reframed by point_rank
kimsaeromi = bubble_points_by_rank[60]
assert kimsaeromi["player"] == "김새로미"
assert kimsaeromi["points_status"] == "CONFIRMED_VALUE"
ksr_delta = int(kimsaeromi["delta"])
ksr_badge_text, ksr_badge_class = delta_badge(ksr_delta)

# 홍정민 confirmed exemption detail
hjm = next(r for r in elig_rows if r["player"] == "홍정민")
assert hjm["final_2027_group"] == "B"

html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>2027 KLPGA 시드 전쟁 — 상금 60위만 보면 틀린다</title>
<meta name="description" content="2027시즌부터 KLPGA 정규투어 시드 기준이 상금순위에서 포인트순위로 바뀐다. 공식 cutoff는 아직 없어 확률은 보류하지만, 바뀐 기준으로 다시 본 순위를 공개한다.">
<meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;700;800&amp;family=Noto+Sans+KR:wght@400;500;700&amp;family=Roboto+Mono:wght@400;600&amp;display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #dde5f3; --bg-alt: #cfdaef; --card-bg: #ffffff; --border: #b8c6e2;
    --text: #16213e; --text-dim: #5b6b85; --accent: #0f9488; --accent-blue: #2f5fd9;
    --pill-bg: #dff5f0; --pill-text: #0b7d6f; --row-alt: #eaf0fa; --warn: #b23b3b;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 24px 16px 60px; background: var(--bg); color: var(--text);
    font-family: "Noto Sans KR", sans-serif; word-break: keep-all; overflow-wrap: break-word; }}
  header, main, footer {{ max-width: 720px; margin-left: auto; margin-right: auto; }}

  .wordmark {{ --row: clamp(12px, 3vw, 16px); display: flex; align-items: center; gap: clamp(12px, 3.2vw, 20px); margin-bottom: 10px; }}
  .wordmark-letters {{ display: flex; flex-direction: column; gap: calc(var(--row) * 0.15); flex-shrink: 0; }}
  .letter-row {{ display: flex; align-items: baseline; gap: calc(var(--row) * 0.42); white-space: nowrap; }}
  .letter {{ font-family: "Big Shoulders Display", sans-serif; font-weight: 800; font-size: calc(var(--row) * 1.15); line-height: 1; color: var(--accent); }}
  .letter-word {{ font-family: "Big Shoulders Display", sans-serif; font-weight: 600; font-size: calc(var(--row) * 0.72); line-height: 1; letter-spacing: 0.04em; color: var(--text-dim); white-space: nowrap; }}
  .wordmark-name {{ font-family: "Big Shoulders Display", sans-serif; font-weight: 800; font-size: calc(var(--row) * 2.6); line-height: 1; letter-spacing: 0.015em; color: var(--text); white-space: normal; }}
  .header-about-link {{ display: inline-block; margin: 2px 0 0; color: var(--accent); text-decoration: none; font-size: 12px; font-weight: 600; }}

  main {{ padding-top: 8px; }}
  .eyebrow {{ font-family: "Roboto Mono", monospace; font-size: 12px; font-weight: 600; letter-spacing: 0.14em; color: var(--accent); text-transform: uppercase; margin: 0 0 10px; }}

  .scope-banner {{ background: #fdf2e0; border: 1px solid #e3c488; color: #7a5410; border-radius: 10px; padding: 12px 14px; font-size: 12.5px; line-height: 1.7; margin: 18px 0 0; }}
  .scope-banner strong {{ color: #7a5410; }}

  section.hero {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; padding: 30px 24px; margin: 18px 0 32px; box-shadow: 0 1px 4px rgba(22,33,62,0.08); text-align: center; }}
  section.hero h1 {{ font-family: "Big Shoulders Display", sans-serif; font-weight: 800; font-size: clamp(24px, 6.5vw, 32px); line-height: 1.25; margin: 0 0 16px; }}
  .hero-fact {{ font-family: "Roboto Mono", monospace; font-weight: 700; font-size: 14px; color: var(--accent-blue); background: var(--bg-alt); border-radius: 10px; padding: 10px 14px; margin: 0 0 14px; display: inline-block; }}
  .hero-sub {{ font-size: 14.5px; line-height: 1.8; color: var(--text-dim); margin: 0; }}

  section.block {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; padding: 26px 22px; margin-bottom: 28px; box-shadow: 0 1px 4px rgba(22,33,62,0.06); }}
  section.block h2 {{ font-family: "Big Shoulders Display", sans-serif; font-weight: 700; font-size: clamp(20px, 5vw, 25px); margin: 0 0 18px; }}
  section.block p {{ font-size: 15px; line-height: 1.85; margin: 0 0 14px; color: var(--text); }}
  section.block p.dim {{ color: var(--text-dim); font-size: 13.5px; }}

  .rule-card {{ background: var(--bg-alt); border-radius: 12px; padding: 18px; margin: 0 0 14px; }}
  .rule-old-new {{ display: flex; align-items: center; gap: 12px; justify-content: center; font-family: "Big Shoulders Display", sans-serif; font-weight: 800; font-size: 20px; flex-wrap: wrap; }}
  .rule-old {{ color: var(--text-dim); text-decoration: line-through; }}
  .rule-arrow {{ color: var(--accent); }}
  .rule-new {{ color: var(--accent); }}
  .rule-date {{ text-align: center; font-size: 12px; color: var(--text-dim); margin-top: 8px; font-weight: 700; }}

  .connector-row {{ display: flex; flex-direction: column; gap: 4px; padding: 12px 0; border-bottom: 1px solid var(--row-alt); }}
  .connector-row:last-child {{ border-bottom: none; }}
  .connector-name {{ font-weight: 800; font-size: 15px; }}
  .connector-ranks {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 13px; font-weight: 700; }}
  .connector-money {{ color: var(--text-dim); }}
  .connector-arrow {{ color: var(--border); }}
  .connector-point {{ color: var(--accent-blue); }}
  .connector-delta {{ font-family: "Roboto Mono", monospace; font-size: 12px; padding: 1px 8px; border-radius: 999px; }}
  .delta-up {{ background: var(--pill-bg); color: var(--pill-text); }}
  .delta-down {{ background: #fbe4e4; color: var(--warn); }}
  .delta-flat {{ background: var(--row-alt); color: var(--text-dim); }}
  .connector-vals {{ font-family: "Roboto Mono", monospace; font-size: 11.5px; color: var(--text-dim); }}

  .pending-row {{ display: grid; grid-template-columns: 34px 1fr auto; column-gap: 10px; align-items: center; padding: 8px 4px; border-bottom: 1px solid var(--row-alt); font-size: 13px; }}
  .pending-row:last-child {{ border-bottom: none; }}
  .pending-rank {{ font-family: "Roboto Mono", monospace; font-weight: 800; color: var(--text-dim); }}
  .pending-rank-unit {{ font-size: 10px; font-weight: 600; }}
  .pending-name {{ font-weight: 700; }}
  .bubble-tag {{ display: inline-block; font-size: 9.5px; font-weight: 800; padding: 1px 6px; border-radius: 999px; margin-left: 6px; vertical-align: middle; }}
  .tag-confirmed {{ background: var(--accent); color: #fff; }}
  .pending-money {{ font-family: "Roboto Mono", monospace; font-size: 11px; color: var(--text-dim); grid-column: 2; }}
  .pending-point {{ grid-column: 3; grid-row: 1 / 3; display: flex; flex-direction: column; align-items: flex-end; gap: 3px; text-align: right; }}
  .pending-points-val {{ font-family: "Roboto Mono", monospace; font-weight: 800; font-size: 14px; color: var(--accent-blue); }}
  .pending-points-blank {{ font-family: "Roboto Mono", monospace; font-weight: 800; font-size: 14px; color: var(--text-dim); }}
  .pending-point-note {{ font-size: 9.5px; font-weight: 600; color: var(--text-dim); white-space: nowrap; }}
  .pending-rank-row {{ display: flex; align-items: center; gap: 5px; flex-wrap: nowrap; }}
  .pending-point-rank {{ font-size: 10.5px; font-weight: 700; color: var(--text-dim); white-space: nowrap; }}
  .pending-point-rank-blank {{ font-size: 10.5px; font-weight: 700; color: var(--text-dim); white-space: nowrap; }}
  .pending-delta {{ font-family: "Roboto Mono", monospace; font-size: 10.5px; font-weight: 800; padding: 0px 6px; border-radius: 999px; white-space: nowrap; }}

  .curve-table {{ width: 100%; border-collapse: collapse; margin: 0 0 10px; font-size: 13px; }}
  .curve-table th, .curve-table td {{ padding: 6px 4px; text-align: center; border-bottom: 1px solid var(--row-alt); }}
  .curve-table th {{ color: var(--text-dim); font-weight: 700; font-size: 11px; }}
  .curve-bar-wrap {{ width: 100%; height: 6px; background: var(--row-alt); border-radius: 999px; overflow: hidden; margin-top: 2px; }}
  .curve-bar {{ height: 100%; background: var(--accent-blue); border-radius: 999px; }}
  .curve-points {{ font-family: "Roboto Mono", monospace; font-weight: 800; color: var(--accent-blue); }}

  .tie-fixture {{ background: var(--bg-alt); border-radius: 12px; padding: 14px 16px; margin-top: 16px; }}
  .tie-fixture-title {{ font-weight: 800; font-size: 13px; margin: 0 0 10px; color: var(--text); }}

  .hero-card-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
  .hcard {{ background: var(--bg-alt); border-radius: 12px; padding: 14px 12px; }}
  .hcard-label {{ font-size: 10.5px; font-weight: 700; color: var(--text-dim); margin-bottom: 6px; line-height: 1.4; }}
  .hcard-name {{ font-weight: 800; font-size: 16px; margin-bottom: 4px; }}
  .hcard-exempt {{ display: inline-block; background: var(--accent); color: #fff; font-size: 9px; font-weight: 800; padding: 1px 6px; border-radius: 999px; margin-left: 5px; vertical-align: middle; }}
  .hcard-stats {{ font-size: 11px; color: var(--text-dim); margin-bottom: 6px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
  .hcard-points {{ font-family: "Roboto Mono", monospace; font-weight: 800; font-size: 20px; color: var(--accent-blue); }}

  .hcard-special {{ margin-top: 10px; border: 1px solid var(--accent); background: #eef8f6; }}
  .hcard-special .hcard-label {{ color: var(--accent); }}
  .hcard-special-copy {{ font-size: 13px; line-height: 1.7; color: var(--text); margin: 8px 0 0; }}

  .exempt-card {{ display: flex; align-items: center; gap: 12px; background: var(--bg-alt); border-radius: 12px; padding: 14px 16px; margin: 0 0 10px; }}
  .exempt-badge {{ background: var(--accent); color: #fff; font-size: 11px; font-weight: 800; padding: 3px 10px; border-radius: 999px; white-space: nowrap; }}
  .exempt-badge.pending {{ background: var(--row-alt); color: var(--text-dim); }}
  .exempt-name {{ font-weight: 800; font-size: 14.5px; }}
  .exempt-detail {{ font-size: 12px; color: var(--text-dim); }}

  @media (max-width: 480px) {{
    .hero-card-grid {{ grid-template-columns: 1fr; }}
  }}

  section.disclosure {{ background: var(--bg-alt); border-radius: 14px; padding: 22px 20px; margin-bottom: 28px; }}
  section.disclosure h2 {{ font-size: 16px; font-family: "Big Shoulders Display", sans-serif; font-weight: 700; margin: 0 0 12px; }}
  section.disclosure p {{ font-size: 13.5px; line-height: 1.85; color: var(--text-dim); margin: 0; }}

  section.method {{ background: var(--bg-alt); border-radius: 14px; padding: 22px 20px; margin-bottom: 28px; }}
  section.method h2 {{ font-size: 16px; font-family: "Big Shoulders Display", sans-serif; font-weight: 700; margin: 0 0 12px; }}
  section.method p {{ font-size: 13px; line-height: 1.8; color: var(--text-dim); margin: 0 0 10px; }}
  section.method p:last-child {{ margin-bottom: 0; }}

  footer {{ margin-top: 40px; padding-top: 24px; border-top: 1px solid var(--border); padding-bottom: 8px; text-align: center; color: var(--text-dim); font-size: 11px; line-height: 1.7; }}

  @media (max-width: 480px) {{
    body {{ padding: 16px 10px 40px; }}
    .wordmark {{ --row: 8px; }}
    section.hero, section.block {{ padding: 20px 16px; }}
    .rule-old-new {{ font-size: 16px; }}
  }}
</style>
</head>
<body>

<header>
  <div class="wordmark">
    <div class="wordmark-letters">
      <div class="letter-row"><span class="letter">N</span><span class="letter-word">NUMBER</span></div>
      <div class="letter-row"><span class="letter">E</span><span class="letter-word">EVIDENCE</span></div>
      <div class="letter-row"><span class="letter">O</span><span class="letter-word">ORACLE</span></div>
    </div>
    <div class="wordmark-name">2027 포인트 시드 전쟁</div>
  </div>
  <a class="header-about-link" href="/about/">NEO GOLF DATA 소개</a>
</header>

<main>

  <div class="scope-banner" data-testid="scope-banner">KLPGA는 2027시즌부터 포인트순위를 정규투어 시드권 부여 기준으로 바꾼다고 공식 발표했습니다(기준 자체는 확인됨). 55~80위 선수들의 <strong>대상포인트·포인트순위 값은 이제 공개</strong>합니다(공식 전체 선수 기록 기반). 다만 <strong>"몇 위까지 시드를 받는지"는 현재 확인된 공식 발표에 없어</strong>, NEO는 시드 확률 공개를 보류합니다. 포인트순위 공개와 시드 cutoff 확정은 서로 다른 일입니다.</div>

  <section class="hero" data-testid="hero">
    <h1>상금 60위만 보면 틀린다<br>2027 KLPGA 시드 전쟁</h1>
    <p class="hero-fact" data-testid="hero-fact">상금 71위 김나현2는 포인트 48위다. 23계단이 달라진다.</p>
    <p class="hero-sub">2027년부터 시드 기준이 상금순위에서 포인트순위로 바뀐다.<br>그러면 지금까지 우리가 보던 "상금 60위 싸움"도 다시 봐야 한다.</p>
  </section>

  <section class="block" data-testid="rule-change">
    <p class="eyebrow">Official Rule Change</p>
    <h2>올해부터 계산법이 바뀐다</h2>
    <div class="rule-card">
      <div class="rule-old-new">
        <span class="rule-old">상금순위</span>
        <span class="rule-arrow">→</span>
        <span class="rule-new">포인트순위</span>
      </div>
      <p class="rule-date">KLPGA 공식 발표 2026-09-29 · 2027시즌 정규투어 시드권 부여 기준</p>
    </div>
    <p>"얼마를 벌었나?"가 아니라 "몇 점을 쌓았나?"가 기준이 된다.</p>
    <p class="dim">상금이 사라진 것이 아니다. 시드를 결정하는 자가 바뀐 것이다 — 좋은 성적을 내면 상금과 포인트를 동시에 얻는다. 둘은 함께 움직이지만, 대회별 상금 규모와 포인트 배점 구조가 다르기 때문에 완전히 같은 순위는 아니다.</p>
  </section>

  <section class="block" data-testid="money-point-connector">
    <p class="eyebrow">Money ↔ Point</p>
    <h2>같은 시즌, 같은 선수들이다</h2>
    <p class="dim">기준만 바꿨는데 순위가 달라졌다 — 지금까지 공식적으로 확인된 포인트 데이터 {len(point_rows_sorted)}명 전체({point_rows_sorted[0]['snapshot_date']} 기준)를 그대로 보여준다.</p>
    <div class="connector-list">
{connector_rows_html}
    </div>
    <p class="dim" style="margin-top:14px;">가장 큰 역전: <strong style="color:var(--text)">김민솔(상금 1위 → 포인트 2위)과 서교림(상금 2위 → 포인트 1위)</strong>의 자리가 바뀐다 — 상금은 김민솔이 더 많지만(15.3억 vs 14.1억) 포인트는 서교림이 더 높다(563 vs 486).</p>
    <p class="dim">참고: 장은수(상금 5위, 686,658,333원)의 누적 포인트(212점)도 추가로 확인됐지만, 공식 포인트 순위표는 5위(이다연, 311점)까지만 공개돼 있어 장은수의 정확한 포인트 순위는 아직 알 수 없다.</p>
  </section>

  <section class="block" data-testid="bubble-hero-cards">
    <p class="eyebrow">55 ~ 80위 상금 버블존</p>
    <h2>기준을 바꾸면, 순위가 뒤집힌다</h2>
    <p class="dim">아래 4장은 <strong>상금순위 → 포인트순위 변동이 가장 큰 선수들</strong>이다(코드가 실제 데이터에서 계산, 미리 고른 선수 아님). 포인트순위는 공식 전체 선수 기록을 기준으로 산출된 값이며, 이 26명만 따로 정렬한 숫자가 아니다.</p>
    <div class="hero-card-grid">
{hero_cards_html}
    </div>
    <div class="hcard hcard-special" data-testid="hcard-kimsaeromi">
      <div class="hcard-label">가장 중요한 한 명</div>
      <div class="hcard-name">김새로미</div>
      <div class="hcard-stats">상금 60위 → 포인트 {kimsaeromi['point_rank']}위 <span class="pending-delta {ksr_badge_class}">{ksr_badge_text}</span></div>
      <p class="hcard-special-copy">상금 기준에서는 정확히 경계선. 포인트로 보면 위치가 8계단 달라진다.</p>
    </div>
  </section>

  <section class="block" data-testid="bubble-pending">
    <h2>55~80위 전체 — 상금, 대상포인트, 포인트순위</h2>
    <p class="dim">상금순위는 공식 확정값이다. 대상포인트와 포인트순위는 공식 전체 선수(1~121위) 기록을 사용자가 공식 페이지에서 직접 확인해 전달한 값으로, Claude가 26명만 따로 정렬한 숫자가 아니다 — 포인트 값이 같은 선수들끼리는 포인트순위도 정확히 같다는 점까지 데이터로 재확인했다.</p>
    <p class="dim"><strong>주의: 이 포인트순위는 2027 시드 cutoff가 아니다.</strong> "몇 위까지 시드를 받는지"는 여전히 공식 미확인이라, 포인트순위 공개와 별개로 누가 시드를 유지하고 누가 탈락하는지에 대한 판정은 계속 보류한다.</p>
    <div class="pending-list">
{bubble_rows_html}
    </div>
    <p class="dim" style="margin-top:10px;">* 대상포인트가 "—"인 선수는 원본 자료에 값이 비어 있었다 — (A) 2026시즌 대상포인트 획득 실적 없음 (B) 대상포인트 순위 자격 미충족 (C) 자료 누락, 셋 중 무엇인지 아직 특정하지 못해 그대로 빈칸으로 둔다. 이 선수들은 포인트순위도 매기지 않는다(점수 없이 순위를 매길 수 없다).</p>
  </section>

  <section class="block" data-testid="top10-curve">
    <p class="eyebrow">Point System</p>
    <h2>포인트는 상위권에 집중된다</h2>
    <p>10억원 일반대회에서는 Top10 순위에 대상포인트가 부여된다. 11위 이하는 대상포인트가 없다 — HJ중공업·동부건설, S-OIL(둘 다 10억원 규모)의 공식 배점:</p>
    <table class="curve-table">
      <tr><th>순위</th><th>포인트</th><th></th></tr>
      {"".join(f'<tr><td>{i+1}위</td><td class="curve-points">{p}</td><td><div class="curve-bar-wrap"><div class="curve-bar" style="width:{round(p/70*100)}%"></div></div></td></tr>' for i, p in enumerate([70,35,33,31,29,27,25,23,21,20]))}
      <tr><td>11위 이하</td><td class="curve-points">0</td><td></td></tr>
    </table>
    <p class="dim">이 "11위부터 0점" 규칙은 10억원 일반대회 기준이며, 다른 대회 규모·메이저에도 똑같이 적용된다고 일반화하지 않는다 — 아이스버그골프·서울신문(15억원 규모)은 1위 포인트(90)만 공식 확인됐고, 2위 이하 배점은 아직 확보되지 않았다.</p>
    <div class="tie-fixture">
      <p class="tie-fixture-title">공동순위는 어떻게 처리할까 — 실제 공식 대회 결과 2건</p>
      <p class="dim" style="margin-bottom:10px;">10억원 규모 대회의 실제 결과: 위 TOP10 배점표와 1위부터 10위까지 전부 정확히 일치한다 — 이 배점표가 추정이 아니라 실제로 적용되고 있음을 다시 확인해준다.</p>
      <table class="curve-table">
        <tr><th>순위</th><th>인원</th><th>1인당 포인트</th></tr>
        {"".join(f'<tr><td>{r["tied_finish_label"]}</td><td>{r["n_tied_players"]}명</td><td class="curve-points">{r["points_each"]}</td></tr>' for r in tie_fixture if r["purse_bracket"] == "10억~12억 미만")}
      </table>
      <p class="dim" style="margin:14px 0 10px;">12억원 대회 사례:</p>
      <table class="curve-table">
        <tr><th>순위</th><th>인원</th><th>1인당 포인트</th></tr>
        {"".join(f'<tr><td>{r["tied_finish_label"]}</td><td>{r["n_tied_players"]}명</td><td class="curve-points">{r["points_each"]}</td></tr>' for r in tie_fixture if r["purse_bracket"] == "12억~15억 미만")}
      </table>
      <p class="dim">두 사례 모두 공동순위라고 포인트를 나눠 갖거나 평균내지 않는다 — 공동 순위자 전원이 그 순위의 포인트를 동일하게 받는다(예: 10억원 대회 T4 세 명 모두 31점씩, 나눠서 각 10.3점이 아니다). 공동순위 때문에 Top10 자리에 실제로는 10명보다 많은 선수가 포인트를 받을 수 있다(위 10억원 대회 사례는 공동 10위가 4명이라 총 13명이 포인트를 받았다).</p>
    </div>
  </section>

  <section class="block" data-testid="why-reversal">
    <p class="eyebrow">Why</p>
    <h2>왜 순위가 뒤집힐까</h2>
    <p>상금과 포인트는 모두 좋은 성적에서 나온다. 하지만 계산법은 다르다.</p>
    <p>상금은 컷을 통과해도 쌓인다. 대상포인트는 Top10 순위에 들어야 쌓인다.</p>
    <p>그래서 같은 시즌, 같은 선수라도 어떤 기준으로 보느냐에 따라 순위는 크게 달라질 수 있다.</p>
  </section>

  <section class="block" data-testid="independent-seed">
    <p class="eyebrow">Independent Seed</p>
    <h2>포인트순위가 전부는 아니다</h2>
    <p class="dim">포인트 경쟁과 별개로, 공식적으로 확인된 독립 출전자격 경로만 표시한다. 확정된 것만 초록 배지, 조건부·미확인은 회색으로 구분한다.</p>
    <div class="exempt-card">
      <span class="exempt-badge">2027 시드 확보</span>
      <div>
        <div class="exempt-name">홍정민</div>
        <div class="exempt-detail">2025 KLPGA 챔피언십(메이저) 우승 — 2025~2028시즌 시드 규정 적용, 2027 포함</div>
      </div>
    </div>
    <div class="exempt-card">
      <span class="exempt-badge pending">조건부 · 미확인</span>
      <div>
        <div class="exempt-name">IQT(인터내셔널 퀄리파잉 토너먼트) 우승자</div>
        <div class="exempt-detail">공식 특전상 익년 정규투어 시드권 부여 — 55~80위 구간에 해당자는 현재 확인된 바 없음</div>
      </div>
    </div>
    <div class="exempt-card">
      <span class="exempt-badge pending">조건부 · 미확인</span>
      <div>
        <div class="exempt-name">K-10 클럽 / 생애누적상금 25억 이상 특별시드</div>
        <div class="exempt-detail">이사회 심사로 연 최대 4명 — 자동 시드 아님, 결정 전까지 확정 배지 부여 안 함</div>
      </div>
    </div>
  </section>

  <section class="disclosure" data-testid="probability-holdback">
    <p class="eyebrow">Why NEO Holds Back</p>
    <h2>NEO가 확률 공개를 보류한 이유</h2>
    <p>KLPGA는 2027시즌부터 정규투어 시드권 부여 기준을 상금순위에서 포인트순위로 변경한다고 발표했다. 다만 현재 확인 가능한 공식 발표에는 시드권이 부여되는 최종 포인트순위가 명시되지 않았다. NEO는 공식 기준 확인 전 시드확률을 공개하지 않는다.</p>
  </section>

  <section class="method" data-testid="methodology">
    <h2>어떻게 만들었나</h2>
    <p>이 페이지의 모든 수치는 공식적으로 확인된 자료(사용자가 공식 페이지에서 직접 확인해 전달한 내용 포함)에서만 가져왔다. 포인트를 상금에서 임의로 환산하지 않았다 — 대회 상금 규모별 공식 배점표를 그대로 사용했다.</p>
    <p>55~80위 버블존 선수들의 대상포인트·포인트순위는 공식 전체 선수(1~121위) 기록을 기반으로 확인됐다. 포인트 값이 같은 선수들끼리 포인트순위도 정확히 같다는 점(동점 처리), 상금순위와 포인트순위의 차이값이 모든 선수에서 산술적으로 맞는다는 점을 전부 재확인한 뒤 공개했다 — 26명만 따로 정렬한 숫자가 아니다.</p>
    <p>포인트순위 시드 cutoff(몇 위까지 시드를 받는지), 아이스버그골프·서울신문의 2위 이하 배점은 아직 공식적으로 확보되지 않아 이 페이지에 숫자를 넣지 않았다.</p>
    <p>기존 상금순위 Top60 확률 시뮬레이션(60,000회)은 이 페이지와 별개로 그대로 유지되고 있으며, 변경되지 않았다.</p>
  </section>

</main>

<footer>
  <div>&copy; 2026 NEO GOLF DATA. All Rights Reserved.</div>
  <div>이 페이지는 공식 발표·공식 자료를 기반으로 하되, 포인트순위 시드 cutoff가 아직 확인되지 않아 확률은 표시하지 않습니다.</div>
  <div><a href="/about/" style="color:var(--text-dim)">NEO GOLF DATA 소개</a></div>
</footer>

</body>
</html>
"""

OUT.write_text(html, encoding="utf-8")
print(f"wrote {OUT} ({len(html)} bytes)")
print(f"point_rows={len(point_rows_sorted)} bubble_rows={len(bubble)} hj_curve_len={len(hj_curve)}")
