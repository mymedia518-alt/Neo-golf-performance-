"""Generate the NEO KLPGA Seed Race public page from locked artifact data.

Source of truth (read directly, nothing hardcoded from memory or prior chat):
  artifacts/seed_race/seed_probability.csv
  artifacts/seed_race/seed_probability_whatif.csv
  artifacts/seed_race/final_60th_money_distribution.csv

No new model, no re-weighted probabilities, no new assumptions. This script only
renders e21e05b's already-verified numbers into the NEO GOLF DATA visual language
(colors/fonts copied from docs/about/index.html and docs/tournaments/.../final/index.html).
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


seed_rows = read_csv(SR / "seed_probability.csv")
whatif_rows = read_csv(SR / "seed_probability_whatif.csv")
dist_rows = read_csv(SR / "final_60th_money_distribution.csv")
dist = {r["metric"]: r["value"] for r in dist_rows}

# bubble range: current_rank 55..70 inclusive, as specified
bubble = [r for r in seed_rows if 55 <= int(float(r["current_rank"])) <= 70]
bubble.sort(key=lambda r: int(float(r["current_rank"])))
assert len(bubble) == 16, f"expected 16 players (55-70), got {len(bubble)}"

row60 = next(r for r in bubble if int(float(r["current_rank"])) == 60)
row61 = next(r for r in bubble if int(float(r["current_rank"])) == 61)
assert row60["player"] == "김새로미"
assert row60["current_money"] == "147312262"

CUR_60_MONEY = int(row60["current_money"])
PROB_60 = float(row60["prob_top60"])  # 0.3193
RAW_N = 60000
RAW_SURVIVE = round(PROB_60 * RAW_N)  # cross-checked against simulation_validation.json separately

P10 = int(dist["simulated_final_60th_p10"])
MEDIAN = int(dist["simulated_final_60th_median"])
P90 = int(dist["simulated_final_60th_p90"])
assert P10 == 164840244 and MEDIAN == 172303371 and P90 == 180291768

parkgyeol = [r for r in whatif_rows if r["player"] == "박결"]
parkgyeol_by_scn = {r["hj_scenario"]: r for r in parkgyeol}
PG_BASELINE = float(parkgyeol[0]["baseline_prob_top60_expected"])
PG_CUR_RANK = int(float(parkgyeol[0]["current_rank"]))
WHATIF_ORDER = ["CUT", "30위", "20위", "10위", "5위"]
for s in WHATIF_ORDER:
    assert s in parkgyeol_by_scn, f"missing scenario {s} in whatif csv"


def won(n):
    return f"{n:,}원"


def pct1(x):
    return f"{x * 100:.1f}%"


def krname(name):
    return name


# ---- bubble section rows (also emits data-* attrs for the automated test) ----
bubble_html = []
for r in bubble:
    rank = int(float(r["current_rank"]))
    money = int(r["current_money"])
    med_rank = r["median_final_rank"]
    med_rank_disp = str(int(float(med_rank)))
    prob = float(r["prob_top60"])
    name = r["player"]
    is_current_60 = rank == 60
    seed_line_before = rank == 61  # draw the line between 60 and 61
    bar_w = max(2, round(prob * 100))
    row_class = "bubble-row"
    if is_current_60:
        row_class += " bubble-row-current60"
    line_html = (
        '<div class="seed-line-marker" role="separator" aria-label="상금순위 Top60 기준선">'
        '<span class="seed-line-text">Top60 기준선</span></div>'
    ) if seed_line_before else ""
    bubble_html.append(f"""{line_html}
    <div class="{row_class}" data-rank="{rank}" data-player="{name}" data-money="{money}" data-prob="{prob:.4f}" data-medrank="{med_rank_disp}">
      <div class="bubble-rank">{rank}<span class="bubble-rank-unit">위</span></div>
      <div class="bubble-name">{name}{' <span class="bubble-tag">현재 60위</span>' if is_current_60 else ''}</div>
      <div class="bubble-money">{won(money)}</div>
      <div class="bubble-bar-wrap">
        <div class="bubble-bar" style="width:{bar_w}%"></div>
      </div>
      <div class="bubble-prob">{pct1(prob)}</div>
      <div class="bubble-medrank">예상 최종 {med_rank_disp}위</div>
    </div>""")
bubble_rows_html = "\n".join(bubble_html)

# ---- what-if ladder ----
ladder_items = [("현재", PG_BASELINE)] + [(s, float(parkgyeol_by_scn[s]["prob_top60"])) for s in WHATIF_ORDER]
max_p = max(p for _, p in ladder_items)
ladder_html = []
for label, p in ladder_items:
    w = max(2, round((p / max_p) * 100))
    hi = " ladder-bar-hi" if label == "5위" else ""
    ladder_html.append(f"""
    <div class="ladder-row">
      <div class="ladder-label">{label}</div>
      <div class="ladder-bar-wrap"><div class="ladder-bar{hi}" style="width:{w}%"></div></div>
      <div class="ladder-pct" data-whatif-scn="{label}" data-whatif-pct="{p:.4f}">{pct1(p)}</div>
    </div>""")
ladder_rows_html = "\n".join(ladder_html)

cutline_p10_gap = P10 - CUR_60_MONEY
cutline_median_gap = MEDIAN - CUR_60_MONEY
cutline_p90_gap = P90 - CUR_60_MONEY

html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NEO KLPGA 2026 상금순위 Top60 시뮬레이션</title>
<meta name="description" content="현재 60위 김새로미, 상금순위 Top60 확률 31.9% — NEO KLPGA 2026 상금순위 Top60 시뮬레이션">
<meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;700;800&amp;family=Noto+Sans+KR:wght@400;500;700&amp;family=Roboto+Mono:wght@400;600&amp;display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #dde5f3;
    --bg-alt: #cfdaef;
    --card-bg: #ffffff;
    --border: #b8c6e2;
    --text: #16213e;
    --text-dim: #5b6b85;
    --accent: #0f9488;
    --accent-blue: #2f5fd9;
    --pill-bg: #dff5f0;
    --pill-text: #0b7d6f;
    --row-alt: #eaf0fa;
    --warn: #b23b3b;
    --gold: #b8860b;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 24px 16px 60px;
    background: var(--bg);
    color: var(--text);
    font-family: "Noto Sans KR", sans-serif;
    word-break: keep-all;
    overflow-wrap: break-word;
  }}
  header, main, footer {{ max-width: 720px; margin-left: auto; margin-right: auto; }}

  .wordmark {{ --row: clamp(12px, 3vw, 16px); display: flex; align-items: center; gap: clamp(12px, 3.2vw, 20px); margin-bottom: 10px; }}
  .wordmark-letters {{ display: flex; flex-direction: column; gap: calc(var(--row) * 0.15); flex-shrink: 0; }}
  .letter-row {{ display: flex; align-items: baseline; gap: calc(var(--row) * 0.42); white-space: nowrap; }}
  .letter {{ font-family: "Big Shoulders Display", sans-serif; font-weight: 800; font-size: calc(var(--row) * 1.15); line-height: 1; color: var(--accent); }}
  .letter-word {{ font-family: "Big Shoulders Display", sans-serif; font-weight: 600; font-size: calc(var(--row) * 0.72); line-height: 1; letter-spacing: 0.04em; color: var(--text-dim); white-space: nowrap; }}
  .wordmark-name {{ font-family: "Big Shoulders Display", sans-serif; font-weight: 800; font-size: calc(var(--row) * 3.0); line-height: 1; letter-spacing: 0.015em; color: var(--text); white-space: normal; }}
  .header-about-link {{ display: inline-block; margin: 2px 0 0; color: var(--accent); text-decoration: none; font-size: 12px; font-weight: 600; }}
  .header-about-link:hover, .header-about-link:focus-visible {{ text-decoration: underline; }}

  main {{ padding-top: 8px; }}
  .eyebrow {{ font-family: "Roboto Mono", monospace; font-size: 12px; font-weight: 600; letter-spacing: 0.14em; color: var(--accent); text-transform: uppercase; margin: 0 0 10px; }}

  /* HERO */
  .scope-banner {{ background: #fdf2e0; border: 1px solid #e3c488; color: #7a5410; border-radius: 10px; padding: 10px 14px; font-size: 12.5px; line-height: 1.6; margin: 18px 0 0; }}
  .scope-banner strong {{ color: #7a5410; }}

  section.hero {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; padding: 30px 24px; margin: 18px 0 32px; box-shadow: 0 1px 4px rgba(22,33,62,0.08); text-align: center; }}
  section.hero h1 {{
    font-family: "Big Shoulders Display", sans-serif;
    font-weight: 800;
    font-size: clamp(24px, 6.5vw, 34px);
    line-height: 1.25;
    margin: 0 0 22px;
    text-wrap: balance;
  }}
  .hero-card {{ background: var(--bg-alt); border-radius: 14px; padding: 22px 18px; max-width: 420px; margin: 0 auto 18px; }}
  .hero-rank-pill {{ display: inline-block; background: var(--pill-bg); color: var(--pill-text); font-size: 12px; font-weight: 700; padding: 4px 12px; border-radius: 999px; margin-bottom: 10px; }}
  .hero-name {{ font-family: "Big Shoulders Display", sans-serif; font-size: clamp(26px, 7vw, 32px); font-weight: 800; margin: 0 0 6px; }}
  .hero-money {{ font-family: "Roboto Mono", monospace; font-size: clamp(18px, 5vw, 22px); font-weight: 700; color: var(--text-dim); margin: 0 0 18px; }}
  .hero-prob-label {{ font-size: 13px; font-weight: 700; color: var(--text-dim); margin: 0 0 4px; }}
  .hero-prob {{ font-family: "Big Shoulders Display", sans-serif; font-size: clamp(48px, 14vw, 68px); font-weight: 800; color: var(--accent); line-height: 1; margin: 0; }}
  .hero-sub {{ font-size: 15px; font-weight: 700; color: var(--text); margin: 18px 0 0; line-height: 1.6; }}

  /* SECTIONS generic */
  section.block {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; padding: 26px 22px; margin-bottom: 28px; box-shadow: 0 1px 4px rgba(22,33,62,0.06); }}
  section.block h2 {{
    font-family: "Big Shoulders Display", sans-serif;
    font-weight: 700;
    font-size: clamp(20px, 5vw, 25px);
    margin: 0 0 18px;
    letter-spacing: 0.01em;
  }}
  section.block p {{ font-size: 15px; line-height: 1.85; margin: 0 0 14px; color: var(--text); }}
  section.block p.dim {{ color: var(--text-dim); font-size: 13.5px; }}

  /* MOVING CUT LINE */
  .cutline-current {{ display: flex; justify-content: space-between; align-items: baseline; background: var(--row-alt); border-radius: 10px; padding: 12px 16px; margin-bottom: 18px; }}
  .cutline-current-label {{ font-size: 13px; font-weight: 700; color: var(--text-dim); }}
  .cutline-current-value {{ font-family: "Roboto Mono", monospace; font-size: 17px; font-weight: 800; }}
  .cutline-scenarios {{ display: flex; flex-direction: column; gap: 12px; margin-bottom: 16px; }}
  .cutline-row {{ display: grid; grid-template-columns: 84px 1fr 150px; align-items: center; gap: 10px; }}
  .cutline-scn-label {{ font-size: 13px; font-weight: 700; color: var(--text-dim); }}
  .cutline-track {{ position: relative; height: 10px; background: var(--row-alt); border-radius: 999px; overflow: hidden; }}
  .cutline-fill {{ position: absolute; left: 0; top: 0; bottom: 0; background: linear-gradient(90deg, var(--accent-blue), var(--accent)); border-radius: 999px; }}
  .cutline-amount {{ font-family: "Roboto Mono", monospace; font-size: 13.5px; font-weight: 700; text-align: right; }}
  .cutline-amount .gap {{ display: block; font-size: 11px; color: var(--accent); font-weight: 700; }}
  .cutline-callout {{ background: var(--bg-alt); border-radius: 10px; padding: 14px 16px; font-size: 14.5px; font-weight: 700; line-height: 1.7; color: var(--text); }}

  /* SEED BUBBLE */
  .bubble-scroll {{ display: flex; flex-direction: column; }}
  .seed-line-marker {{ position: relative; height: 1px; background: var(--warn); margin: 10px 0 10px -22px; width: calc(100% + 44px); }}
  .seed-line-text {{ position: absolute; right: 0; top: -9px; background: var(--warn); color: #fff; font-size: 10.5px; font-weight: 800; letter-spacing: 0.04em; padding: 2px 8px; border-radius: 999px; }}
  .bubble-row {{
    display: grid;
    grid-template-columns: 34px 1fr 58px;
    grid-template-rows: auto auto auto;
    column-gap: 10px;
    row-gap: 2px;
    align-items: center;
    padding: 9px 4px;
    border-bottom: 1px solid var(--row-alt);
  }}
  .bubble-row:last-child {{ border-bottom: none; }}
  .bubble-rank {{ grid-row: 1 / 3; font-family: "Roboto Mono", monospace; font-weight: 800; font-size: 15px; color: var(--text-dim); }}
  .bubble-rank-unit {{ font-size: 10px; font-weight: 600; margin-left: 1px; }}
  .bubble-name {{ font-size: 14px; font-weight: 700; grid-column: 2; }}
  .bubble-tag {{ display: inline-block; background: var(--pill-bg); color: var(--pill-text); font-size: 10px; font-weight: 800; padding: 1px 7px; border-radius: 999px; margin-left: 6px; vertical-align: middle; }}
  .bubble-money {{ font-family: "Roboto Mono", monospace; font-size: 11.5px; color: var(--text-dim); grid-column: 2; }}
  .bubble-bar-wrap {{ grid-column: 2; height: 7px; background: var(--row-alt); border-radius: 999px; overflow: hidden; margin-top: 3px; }}
  .bubble-bar {{ height: 100%; background: var(--accent); border-radius: 999px; }}
  .bubble-prob {{ grid-column: 3; grid-row: 1 / 3; font-family: "Roboto Mono", monospace; font-weight: 800; font-size: 16px; text-align: right; color: var(--accent-blue); }}
  .bubble-medrank {{ grid-column: 2; font-size: 10.5px; color: var(--text-dim); margin-top: 1px; }}
  .bubble-row-current60 {{ background: var(--bg-alt); border-radius: 10px; margin: 0 -10px; padding: 9px 14px; }}
  .bubble-row-current60 .bubble-prob {{ color: var(--accent); }}

  /* WHAT-IF LADDER */
  .whatif-player {{ display: flex; align-items: baseline; gap: 10px; margin-bottom: 4px; }}
  .whatif-name {{ font-family: "Big Shoulders Display", sans-serif; font-weight: 800; font-size: 24px; }}
  .whatif-rank {{ font-size: 13px; font-weight: 700; color: var(--text-dim); }}
  .ladder-row {{ display: grid; grid-template-columns: 64px 1fr 56px; align-items: center; gap: 10px; margin: 10px 0; }}
  .ladder-label {{ font-size: 13px; font-weight: 700; color: var(--text-dim); }}
  .ladder-bar-wrap {{ height: 16px; background: var(--row-alt); border-radius: 999px; overflow: hidden; }}
  .ladder-bar {{ height: 100%; background: var(--accent-blue); border-radius: 999px; }}
  .ladder-bar-hi {{ background: var(--accent); }}
  .ladder-pct {{ font-family: "Roboto Mono", monospace; font-weight: 800; font-size: 14px; text-align: right; }}
  .whatif-note {{ margin-top: 14px; }}

  /* METHODOLOGY */
  section.method {{ background: var(--bg-alt); border-radius: 14px; padding: 22px 20px; margin-bottom: 28px; }}
  section.method h2 {{ font-size: 16px; font-family: "Big Shoulders Display", sans-serif; font-weight: 700; margin: 0 0 12px; }}
  section.method p {{ font-size: 13.5px; line-height: 1.8; color: var(--text-dim); margin: 0 0 10px; }}
  section.method p.warn-box {{ background: #fff; border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; color: var(--text); font-weight: 600; }}
  section.method p:last-child {{ margin-bottom: 0; }}

  footer {{ margin-top: 40px; padding-top: 24px; border-top: 1px solid var(--border); padding-bottom: 8px; text-align: center; color: var(--text-dim); font-size: 11px; line-height: 1.7; }}
  .footer-line {{ margin: 0; }}
  .footer-link {{ color: var(--text-dim); text-decoration: underline; text-decoration-color: transparent; }}
  .footer-link:hover, .footer-link:focus-visible {{ text-decoration-color: currentColor; }}

  @media (max-width: 480px) {{
    body {{ padding: 16px 10px 40px; }}
    .wordmark {{ --row: 8px; }}
    .wordmark-name {{ white-space: normal; line-height: 1.05; }}
    section.hero {{ padding: 24px 16px; }}
    section.block {{ padding: 20px 16px; }}
    .cutline-row {{ grid-template-columns: 64px 1fr; }}
    .cutline-amount {{ grid-column: 1 / 3; text-align: left; }}
    .bubble-row {{ grid-template-columns: 28px 1fr 50px; }}
    .seed-line-marker {{ margin: 10px 0 10px -16px; width: calc(100% + 32px); }}
    .ladder-row {{ grid-template-columns: 52px 1fr 48px; }}
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
    <div class="wordmark-name">2026 상금순위 Top60</div>
  </div>
  <a class="header-about-link" href="/about/">NEO GOLF DATA 소개</a>
</header>

<main>

  <div class="scope-banner" data-testid="scope-banner">이 페이지는 <strong>2026시즌 상금순위 Top60 확률</strong>만 계산합니다. 2027 KLPGA 출전자격(시드) 여부는 별도 공식 기준이 추가로 적용될 수 있어, 이 확률과 동일하다고 단정하지 않습니다.</div>

  <section class="hero" data-testid="hero">
    <h1>현재 60위인데,<br>상금순위 Top60 확률은 31.9%</h1>
    <div class="hero-card">
      <span class="hero-rank-pill">현재 60위</span>
      <p class="hero-name">김새로미</p>
      <p class="hero-money" data-field="hero-money">{won(CUR_60_MONEY)}</p>
      <p class="hero-prob-label">NEO 상금순위 Top60 확률</p>
      <p class="hero-prob" data-field="hero-prob">{pct1(PROB_60)}</p>
    </div>
    <p class="hero-sub">현재 순위보다 중요한 것은<br>시즌 마지막 날의 순위다.</p>
  </section>

  <section class="block" data-testid="moving-cutline">
    <p class="eyebrow">Moving Cut Line</p>
    <h2>60위선은 멈춰 있지 않는다</h2>
    <div class="cutline-current">
      <span class="cutline-current-label">현재 60위 상금</span>
      <span class="cutline-current-value" data-field="current-money">{won(CUR_60_MONEY)}</span>
    </div>
    <div class="cutline-scenarios">
      <div class="cutline-row">
        <span class="cutline-scn-label">낮은 시나리오</span>
        <span class="cutline-track"><span class="cutline-fill" style="width:{round(P10/P90*100)}%"></span></span>
        <span class="cutline-amount" data-field="p10">{won(P10)}<span class="gap">+{cutline_p10_gap:,}</span></span>
      </div>
      <div class="cutline-row">
        <span class="cutline-scn-label">중앙 시나리오</span>
        <span class="cutline-track"><span class="cutline-fill" style="width:{round(MEDIAN/P90*100)}%"></span></span>
        <span class="cutline-amount" data-field="median">{won(MEDIAN)}<span class="gap">+{cutline_median_gap:,}</span></span>
      </div>
      <div class="cutline-row">
        <span class="cutline-scn-label">높은 시나리오</span>
        <span class="cutline-track"><span class="cutline-fill" style="width:100%"></span></span>
        <span class="cutline-amount" data-field="p90">{won(P90)}<span class="gap">+{cutline_p90_gap:,}</span></span>
      </div>
    </div>
    <div class="cutline-callout">
      지금의 {won(CUR_60_MONEY)}은 중앙 시나리오 기준 60위 상금({won(MEDIAN)})보다 낮다 — 현재 1억4,731만원이 시즌 종료 때는 안전선이 아닐 수 있다.
    </div>
  </section>

  <section class="block" data-testid="seed-bubble">
    <p class="eyebrow">Top60 Bubble</p>
    <h2>55위 ~ 70위, 지금 이 순간의 경계선</h2>
    <p class="dim">현재 순위와 NEO가 계산한 상금순위 Top60 확률은 같은 순서로 움직이지 않는다. 57위(지한솔, {pct1(float(next(r for r in bubble if r['player']=='지한솔')['prob_top60']))})는 58위(안재희, {pct1(float(next(r for r in bubble if r['player']=='안재희')['prob_top60']))})보다 한 자리 위인데도 Top60 확률 차이는 두 배 이상이고, 현재 60위 김새로미({pct1(PROB_60)})와 현재 61위 한아름({pct1(float(row61['prob_top60']))})은 순위표에서는 '안'과 '밖'으로 나뉘지만 Top60 확률은 거의 붙어 있다.</p>
    <div class="bubble-scroll">
{bubble_rows_html}
    </div>
  </section>

  <section class="block" data-testid="whatif">
    <p class="eyebrow">What-If</p>
    <h2>이번 대회 한 번이 바꾸는 확률</h2>
    <div class="whatif-player">
      <span class="whatif-name">박결</span>
      <span class="whatif-rank">현재 {PG_CUR_RANK}위</span>
    </div>
    <p class="dim">이번 대회(HJ중공업·동부건설) 성적만 다르게 가정하고, 나머지 선수들의 결과는 같은 시뮬레이션 안에서 그대로 함께 움직인 결과다.</p>
    <div class="ladder" data-testid="whatif-ladder">
{ladder_rows_html}
    </div>
    <p class="whatif-note dim">박결에게 "본선 통과 정도"(컷 탈락 → 20위)는 확률을 거의 못 바꾼다 — 상금이 10위에서 5위로 가는 구간에서 급등하기 때문에, 확실한 top5가 아니면 큰 의미가 없다.</p>
  </section>

  <section class="method" data-testid="methodology">
    <h2>어떻게 계산했나</h2>
    <p>현재 상금순위와 확인된 남은 대회 상금 구조를 바탕으로, 남은 시즌을 60,000번 반복해 각 경우의 최종 상금순위를 다시 계산했다.</p>
    <p>매번 경쟁 선수들의 상금도 함께 변한다. 따라서 단순히 "현재 60위 상금을 넘는가"를 계산한 것이 아니다.</p>
    <p class="warn-box">이 확률은 경기 결과를 보장하는 값이 아니라, 현재 확인 가능한 정보로 계산한 모델 추정치다.</p>
    <p>상금배분표의 일부 구간은 공식 기준점 사이를 보간했으며, 보간 방식에 따른 불확실성이 존재한다 — 예를 들어 이 페이지의 헤드라인 확률(31.9%)도 보간 방식을 바꾸면 최대 약 3.8%p 달라질 수 있다.</p>
    <p class="warn-box">이 페이지가 계산한 것은 "2026시즌 상금순위가 60위 안에서 끝나는가"이다. 실제 다음 시즌 KLPGA 출전자격은 우승에 따른 자격 유효기간, 대회 등급별 기준 차이, 상금순위 외의 별도 자격 등 추가 공식 기준의 영향을 받을 수 있으며, 이 페이지는 그 기준까지 전부 반영하지 않았다.</p>
  </section>

  <section class="block" data-testid="public-copy" style="text-align:left;">
    <p class="eyebrow">NEO KLPGA 2026 상금순위 Top60 시뮬레이션</p>
    <p>KLPGA 상금순위 60위는 다음 시즌 출전자격 논의에서 자주 언급되는 경계선이다.</p>
    <p>10월 6일 현재 60위는 김새로미. 상금은 {won(CUR_60_MONEY)}다.</p>
    <p>그렇다면 지금 60위니까 안전할까?</p>
    <p>NEO가 남은 시즌의 상금 이동을 60,000번 시뮬레이션했다. NEO 시뮬레이션에서 김새로미의 상금순위 Top60 확률은 {pct1(PROB_60)}로 계산됐다.</p>
    <p>이유는 간단하다. 60위 커트라인도 함께 움직이기 때문이다.</p>
    <p class="dim">상금순위표는 오늘의 위치를 보여준다. NEO는 그 위치에서 시즌 마지막 날 상금순위가 어떻게 끝날지의 가능성을 계산한다.</p>
  </section>

</main>

<footer>
  <div class="footer-line">&copy; 2026 NEO GOLF DATA. All Rights Reserved.</div>
  <div class="footer-line">이 페이지의 확률은 NEO GOLF DATA가 공개된 KLPGA 상금순위·상금분배 정보를 바탕으로 계산한 모델 추정치이며, 실제 대회 결과를 보장하지 않습니다.</div>
  <div class="footer-line">Tournament results and player information are based on publicly available data.</div>
  <div class="footer-line"><a class="footer-link" href="/about/">NEO GOLF DATA 소개</a></div>
</footer>

</body>
</html>
"""

OUT.write_text(html, encoding="utf-8")
print(f"wrote {OUT} ({len(html)} bytes)")
print(f"CUR_60_MONEY={CUR_60_MONEY} PROB_60={PROB_60} RAW_SURVIVE~={RAW_SURVIVE}/{RAW_N}")
print(f"P10={P10} MEDIAN={MEDIAN} P90={P90}")
